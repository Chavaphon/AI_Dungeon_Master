"""State diffs, the one write path and the audit-log writer (WBS 5.3, invariant 2).

"Every write produces a diff record": `dispatch` and the engine-step functions of
adm/engine/tools.py replay each write's diff on the state from before it and
compare it with the state after. The sabotage tests make a write change the
state without a matching diff entry and check that it raises. The turn tests
play whole turns, build the record the turn loop will build, write it with
`AuditLog` and replay the log to the after-hash. The property test does that for
any call on any example state.

Run: pytest tests/engine/test_audit.py -v
"""

import json
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from test_preconditions import VARIANTS, Edit, any_call, example_state

import adm.engine.tools as tools
from adm.engine.audit import (
    AuditLog,
    DiffMismatch,
    InvalidRecord,
    UnrecordedWrite,
    apply_diff,
    changed_paths,
    check_write,
    engine_fields,
    log_path,
    read_log,
    record_errors,
    schema_errors,
)
from adm.engine.combat import EngineStep, StateChange, start_encounter
from adm.engine.dice import DiceRoller
from adm.engine.state import GameState, data_hash, load_state, state_hash
from adm.engine.tools import after_call, dispatch, increment_turn, open_encounter
from adm.engine.validator import validate

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "schemas" / "examples"
ENCOUNTER = ["pc_lyra", "npc_rat_01", "npc_rat_02"]

_SCHEMAS = [
    json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))
    for name in ("state.schema.json", "tools.schema.json", "audit.schema.json")
]
_REGISTRY = Registry().with_resources((s["$id"], Resource.from_contents(s)) for s in _SCHEMAS)
RESULT_VALIDATOR = Draft202012Validator(
    {"$ref": _SCHEMAS[1]["$id"] + "#/$defs/tool_result"}, registry=_REGISTRY
)
STEP_VALIDATOR = Draft202012Validator(
    {"$ref": _SCHEMAS[2]["$id"] + "#/$defs/engine_step"}, registry=_REGISTRY
)

Doc = dict[str, Any]

ATTACK = {
    "tool": "attack",
    "arguments": {
        "attacker_id": "pc_lyra",
        "target_id": "npc_rat_02",
        "weapon_id": "item_short_sword",
    },
}


@pytest.fixture
def mid_combat() -> GameState:
    return load_state(EXAMPLES / "state_02_mid_combat.json")


@pytest.fixture
def exploring() -> GameState:
    return load_state(EXAMPLES / "state_01_exploration.json")


# --- a stand-in for the turn loop (WBS 6.4) ----------------------------------


def play_turn(state: GameState, roller: DiceRoller, call: Doc) -> tuple[Doc, Doc, list[Any]]:
    """Dispatch one call as the loop would on its only attempt, and run the
    engine steps after it. Returns the turn's start state, the validation entry
    and the steps. A rejected or null call changes nothing (CLAUDE.md 7.1)."""
    before = state.to_dict()
    entry = dispatch(state, roller, call)
    steps: list[Any] = []
    if entry["ok"] and entry["tool"] is not None:
        steps = after_call(state, roller, entry["tool"]) + [increment_turn(state)]
    return before, entry, steps


def build_record(before: Doc, call: Doc, entry: Doc, steps: list[Any], state: GameState) -> Doc:
    """The turn record the loop writes: a rejection is retried with the same call
    until the budget is spent; the model calls are fixed stand-ins."""
    ran = entry["ok"] and entry["tool"] is not None
    attempts = 1 if entry["ok"] else 3
    failure = None
    if not entry["ok"]:
        kinds = {"SCHEMA_VIOLATION": "schema", "UNKNOWN_ENTITY": "unknown_entity"}
        failure = kinds.get(entry["rejection_code"], "precondition")
    model_calls = [
        {
            "phase": "toolcall",
            "attempt": n,
            "prompt_tokens": 3000,
            "completion_tokens": 40,
            "latency_ms": 2000,
            "eval_ms": 600,
            "raw_output": json.dumps(call),
        }
        for n in range(1, attempts + 1)
    ]
    if failure is None:
        model_calls.append(
            {
                "phase": "narration",
                "attempt": 1,
                "prompt_tokens": 500,
                "completion_tokens": 50,
                "latency_ms": 3000,
                "eval_ms": 900,
                "raw_output": "The cellar water ripples.",
            }
        )
    return {
        "run_id": f"D_{before['scenario_id']}_{before['seed']}",
        "condition": "D",
        "scenario_id": before["scenario_id"],
        "seed": before["seed"],
        "turn_number": before["turn_number"] + 1,
        "input_index": before["turn_number"],
        "timestamp": "2026-11-09T14:22:31Z",
        "player_input": "I do the thing",
        "model_calls": model_calls,
        "proposed_calls": [call] * attempts,
        "validation": [entry] * attempts,
        "executed_call": call if ran else None,
        **engine_fields(before, steps, entry if ran else None, state),
        "narration": "" if failure else "The cellar water ripples.",
        "narration_filtered": False,
        "turn_failure": failure,
        "narration_only": entry == {"ok": True, "tool": None},
        "k_used": 8,
        "summary_regenerated": False,
        "summary": None,
        "turn_latency_ms": 10_000,
    }


def assert_writable(record: Doc) -> None:
    assert schema_errors(record) == []
    assert record_errors(record) == []


# --- apply_diff --------------------------------------------------------------


def test_apply_diff_sets_adds_and_appends() -> None:
    data = {"a": {"b": 1}, "inventory": {"pc": {"x": 2}}, "history": [{"n": 0}]}
    diff = [
        {"path": "a.b", "from": 1, "to": 2},
        {"path": "inventory.pc.y", "from": None, "to": 1},
        {"path": "inventory.npc", "from": None, "to": {"z": 1}},
        {"path": "history.1", "from": None, "to": {"n": 1}},
        {"path": "history.0.n", "from": 0, "to": 5},
    ]
    assert apply_diff(data, diff) == {
        "a": {"b": 2},
        "inventory": {"pc": {"x": 2, "y": 1}, "npc": {"z": 1}},
        "history": [{"n": 5}, {"n": 1}],
    }
    assert data["a"]["b"] == 1, "apply_diff must not change its input"


@pytest.mark.parametrize(
    "entry",
    [
        {"path": "a.b", "from": 7, "to": 2},
        {"path": "a.c", "from": 0, "to": 2},  # a new key comes from null
        {"path": "history.2", "from": None, "to": 1},  # past the end of the list
    ],
)
def test_apply_diff_refuses_a_wrong_from(entry: Doc) -> None:
    with pytest.raises(DiffMismatch):
        apply_diff({"a": {"b": 1}, "history": [0]}, [entry])


def test_changed_paths_names_each_leaf() -> None:
    before = {"a": {"b": 1, "c": [1, 2]}, "d": None}
    after = {"a": {"b": 1, "c": [1, 3]}, "d": None, "e": 0}
    assert changed_paths(before, after) == ["a.c.1", "e"]


def test_check_write_accepts_an_exact_diff(mid_combat: GameState) -> None:
    before = mid_combat.to_dict()
    mid_combat.combatants["pc_lyra"].current_hp = 9
    check_write(
        before, [{"path": "combatants.pc_lyra.current_hp", "from": 14, "to": 9}], mid_combat
    )


def test_check_write_names_an_unrecorded_change(mid_combat: GameState) -> None:
    before = mid_combat.to_dict()
    mid_combat.combatants["pc_lyra"].current_hp = 9
    mid_combat.round_number = 4
    diff = [{"path": "combatants.pc_lyra.current_hp", "from": 14, "to": 9}]
    with pytest.raises(UnrecordedWrite, match=r"at round_number$"):
        check_write(before, diff, mid_combat)


def test_check_write_refuses_an_entry_with_no_change(mid_combat: GameState) -> None:
    before = mid_combat.to_dict()
    with pytest.raises(UnrecordedWrite, match="combatants.pc_lyra.current_hp"):
        check_write(
            before, [{"path": "combatants.pc_lyra.current_hp", "from": 14, "to": 9}], mid_combat
        )


# --- dispatch ----------------------------------------------------------------

LEGAL = {
    "attack": ("mid_combat", ATTACK),
    "fire_bolt": (
        "mid_combat",
        {
            "tool": "cast_spell",
            "arguments": {
                "caster_id": "pc_lyra",
                "spell_id": "spell_fire_bolt",
                "target_id": "npc_rat_01",
            },
        },
    ),
    "cure_wounds_revives": (
        "after_victory",
        {
            "tool": "cast_spell",
            "arguments": {
                "caster_id": "pc_lyra",
                "spell_id": "spell_cure_wounds",
                "target_id": "npc_rat_01",
            },
        },
    ),
    "dodge": ("mid_combat", {"tool": "dodge", "arguments": {"actor_id": "pc_lyra"}}),
    "skill_check": (
        "exploring",
        {"tool": "skill_check", "arguments": {"actor_id": "pc_lyra", "skill": "stealth", "dc": 12}},
    ),
    "new_inventory_item": (
        "exploring",
        {
            "tool": "modify_inventory",
            "arguments": {"actor_id": "pc_lyra", "item_id": "item_rat_bite", "delta": 1},
        },
    ),
    "relationship": (
        "exploring",
        {
            "tool": "update_npc_relationship",
            "arguments": {
                "npc_id": "npc_keeper",
                "direction": "up",
                "justification": "Lyra returned the ledger.",
            },
        },
    ),
    "quest": (
        "exploring",
        {
            "tool": "update_quest",
            "arguments": {"quest_id": "quest_missing_ledger", "transition": "start"},
        },
    ),
}


@pytest.mark.parametrize("name,call", LEGAL.values(), ids=LEGAL)
def test_dispatch_returns_the_result_and_its_diff_replays(name: str, call: Doc) -> None:
    state = example_state(name)
    before = state.to_dict()
    entry = dispatch(state, DiceRoller(7), call)
    RESULT_VALIDATOR.validate(entry)
    assert entry["ok"] and entry["tool"] == call["tool"]
    assert apply_diff(before, entry["state_diff"]) == state.to_dict()
    GameState.from_dict(state.to_dict())


def test_dispatch_returns_a_rejection_and_changes_nothing(mid_combat: GameState) -> None:
    call = {"tool": "dodge", "arguments": {"actor_id": "npc_rat_01"}}
    before = state_hash(mid_combat)
    entry = dispatch(mid_combat, DiceRoller(7), call)
    assert entry == validate(mid_combat, call).to_dict()
    assert entry["rejection_code"] == "NOT_YOUR_TURN"
    assert state_hash(mid_combat) == before


def test_dispatch_of_the_null_tool_is_no_tool(mid_combat: GameState) -> None:
    before = state_hash(mid_combat)
    assert dispatch(mid_combat, DiceRoller(7), {"tool": None}) == {"ok": True, "tool": None}
    assert state_hash(mid_combat) == before


def test_the_scenario_sets_a_skill_check_advantage(exploring: GameState) -> None:
    call = LEGAL["skill_check"][1]
    entry = dispatch(exploring, DiceRoller(7), call, check_advantage="advantage")
    assert entry["narration_facts"]["advantage_mode"] == "advantage"
    assert len(entry["rolls"][0]["individual_dice"]) == 2
    assert dispatch(exploring, DiceRoller(7), call)["rolls"][0]["advantage_mode"] == "normal"


def test_the_dispatch_table_has_the_seven_tools() -> None:
    from adm.engine.validator import tool_names

    assert sorted(tools.DISPATCH) == sorted(tool_names())


# --- every write produces a diff record --------------------------------------


def _hp_also_drops(executor: Any) -> Any:
    """`executor`, changed to also cut the actor's HP without saying so."""

    def sabotaged(state: GameState, roller: DiceRoller, a: Doc, mode: Any) -> Doc:
        outcome = executor(state, roller, a, mode)
        state.combatants["pc_lyra"].current_hp -= 1
        return outcome

    return sabotaged


def test_a_tool_write_without_its_diff_entry_raises(
    mid_combat: GameState, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(tools.DISPATCH, "dodge", _hp_also_drops(tools.DISPATCH["dodge"]))
    with pytest.raises(UnrecordedWrite, match="combatants.pc_lyra.current_hp"):
        dispatch(mid_combat, DiceRoller(7), {"tool": "dodge", "arguments": {"actor_id": "pc_lyra"}})


def test_a_tool_diff_that_claims_a_change_not_made_raises(
    mid_combat: GameState, monkeypatch: pytest.MonkeyPatch
) -> None:
    executor = tools.DISPATCH["dodge"]

    def boasting(state: GameState, roller: DiceRoller, a: Doc, mode: Any) -> Doc:
        outcome = executor(state, roller, a, mode)
        outcome["state_diff"].append({"path": "round_number", "from": 3, "to": 4})
        return outcome

    monkeypatch.setitem(tools.DISPATCH, "dodge", boasting)
    with pytest.raises(UnrecordedWrite, match="round_number"):
        dispatch(mid_combat, DiceRoller(7), {"tool": "dodge", "arguments": {"actor_id": "pc_lyra"}})


def test_an_engine_step_without_its_diff_entry_raises(
    mid_combat: GameState, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = tools.after_player_action

    def sabotaged(state: GameState, roller: DiceRoller) -> list[Any]:
        steps = real(state, roller)
        state.quests["quest_missing_ledger"].stage = 3
        return steps

    monkeypatch.setattr(tools, "after_player_action", sabotaged)
    dispatch(mid_combat, DiceRoller(7), ATTACK)
    with pytest.raises(UnrecordedWrite, match="quests.quest_missing_ledger.stage"):
        after_call(mid_combat, DiceRoller(7), "attack")


def test_an_encounter_start_without_its_diff_entry_raises(
    exploring: GameState, monkeypatch: pytest.MonkeyPatch
) -> None:
    def sabotaged(state: GameState, roller: DiceRoller, ids: list[str]) -> EngineStep:
        step = start_encounter(state, roller, ids)
        state.combatants["npc_rat_01"].dodging = True
        return step

    monkeypatch.setattr(tools, "start_encounter", sabotaged)
    with pytest.raises(UnrecordedWrite, match="combatants.npc_rat_01.dodging"):
        open_encounter(exploring, DiceRoller(7), ENCOUNTER)


def test_a_write_outside_the_write_path_fails_the_turn_record(mid_combat: GameState) -> None:
    before, entry, steps = play_turn(mid_combat, DiceRoller(7), ATTACK)
    mid_combat.inventory["pc_lyra"]["item_torch"] = 5  # not through dispatch
    with pytest.raises(UnrecordedWrite, match="inventory.pc_lyra.item_torch"):
        engine_fields(before, steps, entry, mid_combat)


# --- engine steps ------------------------------------------------------------


def test_increment_turn_is_a_turn_increment_step(mid_combat: GameState) -> None:
    step = increment_turn(mid_combat)
    assert mid_combat.turn_number == 8
    assert step.state_diff == [StateChange(path="turn_number", from_=7, to=8)]
    STEP_VALIDATOR.validate(step.to_dict())


@pytest.mark.parametrize(
    "name,call",
    [LEGAL["skill_check"], LEGAL["quest"], LEGAL["cure_wounds_revives"]],
    ids=["skill_check", "update_quest", "cure_wounds_outside_an_encounter"],
)
def test_no_engine_steps_after_a_call_that_keeps_the_turn(name: str, call: Doc) -> None:
    state = example_state(name)
    roller = DiceRoller(7)
    entry = dispatch(state, roller, call)
    assert after_call(state, roller, entry["tool"]) == []


def test_after_an_action_the_npcs_play_until_the_pc_is_back(mid_combat: GameState) -> None:
    roller = DiceRoller(7)
    dispatch(mid_combat, roller, ATTACK)
    steps = after_call(mid_combat, roller, "attack")
    assert steps and all(s.when == "after_call" for s in steps)
    assert not mid_combat.encounter_active or mid_combat.active_combatant_id == "pc_lyra"
    for step in steps:
        STEP_VALIDATOR.validate(step.to_dict())


def _seed_where_an_npc_goes_first(state: GameState) -> int:
    for seed in range(1000):
        trial = state.model_copy(deep=True)
        start_encounter(trial, DiceRoller(seed), ENCOUNTER)
        if trial.active_combatant_id != "pc_lyra":
            return seed
    raise AssertionError("no seed found")


def test_open_encounter_plays_the_npcs_ahead_of_the_pc(exploring: GameState) -> None:
    roller = DiceRoller(_seed_where_an_npc_goes_first(exploring))
    steps = open_encounter(exploring, roller, ENCOUNTER)
    assert [s.step for s in steps][:2] == ["encounter_start", "npc_action"]
    assert {s.when for s in steps} == {"before_call"}
    assert exploring.active_combatant_id == "pc_lyra" or not exploring.encounter_active


# --- turn records ------------------------------------------------------------


def test_a_played_turn_is_a_writable_record(mid_combat: GameState) -> None:
    before, entry, steps = play_turn(mid_combat, DiceRoller(12345), ATTACK)
    record = build_record(before, ATTACK, entry, steps, mid_combat)
    assert_writable(record)
    assert record["state_diff"][: len(entry["state_diff"])] == entry["state_diff"]
    assert record["engine_steps"][-1]["step"] == "turn_increment"
    assert record["state_before_hash"] == state_hash(
        load_state(EXAMPLES / "state_02_mid_combat.json")
    )
    assert data_hash(apply_diff(before, record["state_diff"])) == record["state_after_hash"]


def test_before_call_steps_come_first_in_the_record(exploring: GameState) -> None:
    roller = DiceRoller(_seed_where_an_npc_goes_first(exploring))
    before = exploring.to_dict()
    steps = open_encounter(exploring, roller, ENCOUNTER)
    call = {
        "tool": "attack",
        "arguments": {
            "attacker_id": "pc_lyra",
            "target_id": "npc_rat_01",
            "weapon_id": "item_short_sword",
        },
    }
    entry = dispatch(exploring, roller, call)
    steps += after_call(exploring, roller, "attack") + [increment_turn(exploring)]
    record = build_record(before, call, entry, steps, exploring)
    assert_writable(record)
    start = record["engine_steps"][0]
    assert record["state_diff"][: len(start["state_diff"])] == start["state_diff"]
    assert data_hash(apply_diff(before, record["state_diff"])) == record["state_after_hash"]


def test_a_rejected_turn_records_no_change(mid_combat: GameState) -> None:
    call = {"tool": "dodge", "arguments": {"actor_id": "npc_rat_01"}}
    before, entry, steps = play_turn(mid_combat, DiceRoller(7), call)
    record = build_record(before, call, entry, steps, mid_combat)
    assert_writable(record)
    assert record["turn_failure"] == "precondition"
    assert record["state_diff"] == [] and record["state_before_hash"] == record["state_after_hash"]


def test_engine_fields_refuse_steps_out_of_order(mid_combat: GameState) -> None:
    before, entry, steps = play_turn(mid_combat, DiceRoller(7), ATTACK)
    late = EngineStep(step="turn_increment", when="before_call", state_diff=[], rolls=[])
    with pytest.raises(ValueError, match="before_call step comes after"):
        engine_fields(before, [*steps, late], entry, mid_combat)


def test_engine_fields_take_only_an_executed_result(mid_combat: GameState) -> None:
    before = mid_combat.to_dict()
    entry = dispatch(mid_combat, DiceRoller(7), {"tool": "dodge", "arguments": {"actor_id": "x"}})
    with pytest.raises(ValueError, match="result_ok"):
        engine_fields(before, [], entry, mid_combat)


# --- the JSONL writer --------------------------------------------------------


def _example(name: str) -> Doc:
    return json.loads((EXAMPLES / f"audit_turn_{name}.json").read_text(encoding="utf-8"))


def _log_for(record: Doc, runs: Path) -> AuditLog:
    return AuditLog(runs, record["condition"], record["scenario_id"], record["seed"])


def test_the_log_path_is_condition_scenario_seed(tmp_path: Path) -> None:
    assert log_path(tmp_path, "D", "s01_cellar", 12345) == tmp_path / "D/s01_cellar/12345.jsonl"
    log = AuditLog(tmp_path, "D", "s01_cellar", 12345)
    assert log.run_id == "D_s01_cellar_12345"
    assert log.records() == []


@pytest.mark.parametrize("name", ["valid", "rejected", "condition_b"])
def test_the_example_records_are_written_one_per_line(name: str, tmp_path: Path) -> None:
    record = _example(name)
    log = _log_for(record, tmp_path)
    log.append(record)
    log.append(record)
    lines = log.path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert [json.loads(line) for line in lines] == [record, record]
    assert read_log(log.path) == log.records() == [record, record]


@pytest.mark.parametrize(
    "mutate,reason",
    [
        (lambda r: r.update(location="cellar"), "Additional properties"),
        (lambda r: r.update(turn_failure="schema"), "turn_failure"),
        (lambda r: r.update(state_diff=[]), "state_diff is not the steps"),
        (lambda r: r.update(run_id="D_s01_cellar_99", seed=99), "in the log of D_s01_cellar_12345"),
    ],
    ids=["schema", "failure_with_success", "diff_missing_writes", "other_run"],
)
def test_the_log_refuses_a_bad_record_and_writes_nothing(
    mutate: Any, reason: str, tmp_path: Path
) -> None:
    record = _example("valid")
    log = _log_for(record, tmp_path)
    mutate(record)
    with pytest.raises(InvalidRecord, match=reason):
        log.append(record)
    assert not log.path.exists()


def test_a_refused_record_leaves_earlier_lines_alone(tmp_path: Path) -> None:
    record = _example("valid")
    log = _log_for(record, tmp_path)
    log.append(record)
    with pytest.raises(InvalidRecord):
        log.append({**record, "narration_only": True})
    assert log.records() == [record]


def _session(runs: Path, seed: int) -> Path:
    """Play the first encounter of the example state to its end and log it. The
    first turn opens the encounter, so its record starts with those steps."""
    state = load_state(EXAMPLES / "state_01_exploration.json")
    roller = DiceRoller(seed)
    log = AuditLog(runs, "D", state.scenario_id, state.seed)
    before = state.to_dict()
    steps = open_encounter(state, roller, ENCOUNTER)
    while state.encounter_active:
        target = min(
            cid
            for cid, c in state.combatants.items()
            if c.faction == "hostile" and c.status == "active"
        )
        call = {
            "tool": "attack",
            "arguments": {
                "attacker_id": "pc_lyra",
                "target_id": target,
                "weapon_id": "item_short_sword",
            },
        }
        entry = dispatch(state, roller, call)
        steps += after_call(state, roller, "attack") + [increment_turn(state)]
        log.append(build_record(before, call, entry, steps, state))
        before, steps = state.to_dict(), []
        assert state.turn_number < 100, "the fight did not end"
    return log.path


def test_a_logged_session_replays_and_is_byte_identical(tmp_path: Path) -> None:
    first = _session(tmp_path / "a", 99)
    second = _session(tmp_path / "b", 99)
    assert first.read_bytes() == second.read_bytes()

    records = read_log(first)
    assert len(records) >= 2
    data = load_state(EXAMPLES / "state_01_exploration.json").to_dict()
    for record in records:
        assert data_hash(data) == record["state_before_hash"]
        data = apply_diff(data, record["state_diff"])
        assert data_hash(data) == record["state_after_hash"]
    assert data["encounter_active"] is False
    assert [r["turn_number"] for r in records] == list(range(1, len(records) + 1))


# --- any call, any state -----------------------------------------------------


@settings(max_examples=300, deadline=None)
@given(variant=st.sampled_from(VARIANTS), call=any_call, seed=st.integers(0, 10_000))
def test_any_turn_is_fully_recorded(
    variant: tuple[str, tuple[Edit, ...]], call: Doc, seed: int
) -> None:
    """Whatever the call, the turn's diff replays to its after-hash and the
    record passes the schema and the section 3 rules."""
    state = example_state(variant[0], *variant[1])
    before, entry, steps = play_turn(state, DiceRoller(seed), call)
    record = build_record(before, call, entry, steps, state)
    assert_writable(record)
    assert data_hash(apply_diff(before, record["state_diff"])) == record["state_after_hash"]
