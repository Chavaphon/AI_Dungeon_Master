"""Replay harness (WBS 4.18): a seed plus a scenario reproduces a session.

Two replays of one seed are byte-identical for every scenario, and a different
seed gives a different replay. The replay's state hashes chain from the run's
turn-0 state, and each turn's diff replays to its after-hash. Rejected and null
expected calls, and the scenario's skill-check DC, are handled as a scripted
condition D turn handles them. `log_differences` compares two audit logs with
the timings left out (CLAUDE.md section 11).

The comparison with a condition D session that proposes every expected call is
in tests/orchestration/test_session.py, since it needs the turn loop.

Run: pytest tests/engine/test_replay.py -v
"""

import json
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from adm.engine.audit import apply_diff
from adm.engine.replay import ReplayTurn, log_differences, replay_script, to_jsonl
from adm.engine.scenario import Scenario, initial_state, load_scenario
from adm.engine.state import data_hash

ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = sorted((ROOT / "scenarios").glob("*.json"))
CELLAR = load_scenario(ROOT / "scenarios" / "s01_cellar.json")
SHRINE = load_scenario(ROOT / "scenarios" / "s03_forest_shrine.json")
SEED = 12345

Doc = dict[str, Any]


def _with_inputs(scenario: Scenario, inputs: list[Doc], encounters: list[Doc]) -> Scenario:
    data = scenario.model_dump(mode="json")
    return Scenario.model_validate({**data, "scripted_inputs": inputs, "encounters": encounters})


# --- byte-identical ----------------------------------------------------------


@pytest.mark.parametrize("path", SCENARIOS, ids=[p.stem for p in SCENARIOS])
def test_two_replays_of_one_seed_are_byte_identical(path: Path) -> None:
    scenario = load_scenario(path)
    first = to_jsonl(replay_script(scenario, SEED)).encode("utf-8")
    second = to_jsonl(replay_script(load_scenario(path), SEED)).encode("utf-8")
    assert first == second
    assert first.count(b"\n") == len(scenario.scripted_inputs)


@settings(max_examples=25, deadline=None)
@given(seed=st.integers(min_value=0, max_value=2**32 - 1))
def test_any_seed_replays_identically(seed: int) -> None:
    assert to_jsonl(replay_script(CELLAR, seed)) == to_jsonl(replay_script(CELLAR, seed))


def test_another_seed_gives_another_replay() -> None:
    first, second = replay_script(CELLAR, SEED), replay_script(CELLAR, SEED + 1)
    assert [t.rolls for t in first] != [t.rolls for t in second]


# --- the replayed session ----------------------------------------------------


@pytest.mark.parametrize("path", SCENARIOS, ids=[p.stem for p in SCENARIOS])
def test_the_replay_chains_its_state_hashes_from_turn_zero(path: Path) -> None:
    scenario = load_scenario(path)
    data = initial_state(scenario, SEED).to_dict()
    turns = replay_script(scenario, SEED)
    for turn in turns:
        assert data_hash(data) == turn.state_before_hash
        data = apply_diff(data, turn.state_diff)
        assert data_hash(data) == turn.state_after_hash == data_hash(turn.state)
    assert [t.input_index for t in turns] == list(range(len(scenario.scripted_inputs)))
    # Every scenario opens at least one encounter and plays it.
    steps = [s["step"] for t in turns for s in t.engine_steps]
    assert "encounter_start" in steps and "npc_action" in steps


def test_a_turn_uses_the_audit_records_field_names() -> None:
    schema = json.loads((ROOT / "schemas" / "audit.schema.json").read_text(encoding="utf-8"))
    fields = set(replay_script(CELLAR, SEED)[0].to_dict()) - {"validation", "state"}
    assert fields <= set(schema["properties"])


def test_a_rejected_expected_call_is_a_failed_turn_that_does_not_advance() -> None:
    swing = {
        "tool": "attack",
        "arguments": {
            "attacker_id": "pc_lyra",
            "target_id": "npc_rat_01",
            "weapon_id": "item_short_sword",
        },
    }
    scenario = _with_inputs(
        CELLAR,
        [
            {"text": "I swing at a rat", "expected_call": swing},
            {"text": "I wait", "expected_call": None},
        ],
        [],
    )
    failed, waited = replay_script(scenario, SEED)

    assert failed.validation["rejection_code"] == "ENCOUNTER_OVER"
    assert failed.turn_failure == "precondition" and failed.executed_call is None
    assert failed.state_diff == [] and failed.state_before_hash == failed.state_after_hash
    assert not failed.narration_only
    # The failed turn did not advance, so the next input plays the same turn.
    assert failed.turn_number == waited.turn_number == 1


def test_a_null_expected_call_is_narration_only_and_advances() -> None:
    looking: ReplayTurn = replay_script(CELLAR, SEED)[0]
    assert CELLAR.scripted_inputs[0].expected_call is None
    assert looking.validation == {"ok": True, "tool": None}
    assert looking.narration_only and looking.executed_call is None
    assert looking.turn_failure is None
    assert looking.state_diff == [{"path": "turn_number", "from": 0, "to": 1}]


def test_a_scripted_skill_check_uses_the_scenarios_dc_and_advantage() -> None:
    check = SHRINE.scripted_inputs[6]
    assert check.expected_call is not None and check.check_advantage == "advantage"
    turn = replay_script(SHRINE, SEED)[6]
    facts = turn.validation["narration_facts"]
    assert facts["dc"] == check.expected_call["arguments"]["dc"]
    assert facts["advantage_mode"] == "advantage"
    (roll,) = turn.rolls
    assert len(roll["individual_dice"]) == 2


# --- comparing two audit logs ------------------------------------------------


def _record(**changes: Any) -> Doc:
    record = {
        "run_id": "D_s01_cellar_12345",
        "timestamp": "2026-11-03T10:00:00Z",
        "narration": "Water laps at the barrels.",
        "model_calls": [
            {"phase": "toolcall", "raw_output": "{}", "latency_ms": 900, "eval_ms": 300}
        ],
        "turn_latency_ms": 1200,
    }
    return {**record, **changes}


def test_logs_that_differ_only_in_timings_replay() -> None:
    later = _record(
        timestamp="2026-11-04T09:00:00Z",
        model_calls=[{"phase": "toolcall", "raw_output": "{}", "latency_ms": 1, "eval_ms": 1}],
        turn_latency_ms=5,
    )
    assert log_differences([_record()], [later]) == []


def test_any_other_difference_is_reported_by_record_and_path() -> None:
    reply = [{"phase": "toolcall", "raw_output": "null", "latency_ms": 900, "eval_ms": 300}]
    changed = [_record(), _record(narration="Silence."), _record(model_calls=reply)]
    assert log_differences([_record()] * 3, changed) == [
        "record 1: narration",
        "record 2: model_calls.0.raw_output",
    ]


def test_a_log_with_a_missing_record_does_not_replay() -> None:
    assert log_differences([_record(), _record()], [_record()]) == ["2 records against 1"]
