"""Audit-log turn record v1.0 (WBS 2.4): the schema validates the example records
and rejects records that break CLAUDE.md sections 7 and 11.

`record_errors` covers the rules JSON Schema cannot express (see
docs/audit_log.md). It lives in adm/engine/audit.py since WBS 5.3, where the
audit-log writer refuses any record it flags. The valid example is also
replayed: its state_diff, applied to the mid-combat example state, must
reproduce state_after_hash.

Run: pytest tests/test_audit_log.py -v
"""

import copy
import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from test_state_schema import VALIDATOR as STATE_VALIDATOR
from test_state_schema import cross_field_errors

from adm.engine.audit import apply_diff, record_errors, step_part

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas"
EXAMPLES = SCHEMAS / "examples"


def _schema(name: str) -> dict[str, Any]:
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


SCHEMA = _schema("audit.schema.json")
REGISTRY = Registry().with_resources(
    (s["$id"], Resource.from_contents(s))
    for s in (_schema("state.schema.json"), _schema("tools.schema.json"))
)
VALIDATOR = Draft202012Validator(SCHEMA, registry=REGISTRY)

RECORD_EXAMPLES = sorted(EXAMPLES.glob("audit_turn_*.json"))
STATE_BEFORE = EXAMPLES / "state_02_mid_combat.json"

Record = dict[str, Any]


def _load(path: Path) -> Record:
    return json.loads(path.read_text(encoding="utf-8"))


def _valid() -> Record:
    return _load(EXAMPLES / "audit_turn_valid.json")


def _rejected() -> Record:
    return _load(EXAMPLES / "audit_turn_rejected.json")


def _schema_errors(record: Record) -> list[str]:
    return [e.message for e in VALIDATOR.iter_errors(record)]


def state_hash(state: dict[str, Any]) -> str:
    """docs/conventions.md section 2: the serialisation used for hashing."""
    text = json.dumps(state, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_schema_is_valid_draft_2020_12() -> None:
    Draft202012Validator.check_schema(SCHEMA)


def test_three_examples_exist() -> None:
    assert [p.stem for p in RECORD_EXAMPLES] == [
        "audit_turn_condition_b",
        "audit_turn_rejected",
        "audit_turn_valid",
    ]


@pytest.mark.parametrize("path", RECORD_EXAMPLES, ids=lambda p: p.stem)
def test_example_validates(path: Path) -> None:
    record = _load(path)
    assert _schema_errors(record) == []
    assert record_errors(record) == []


@pytest.mark.parametrize("path", RECORD_EXAMPLES, ids=lambda p: p.stem)
def test_example_starts_from_the_mid_combat_state(path: Path) -> None:
    assert _load(path)["state_before_hash"] == state_hash(_load(STATE_BEFORE))


def test_valid_example_replays_to_its_after_hash() -> None:
    record = _valid()
    after = apply_diff(_load(STATE_BEFORE), record["state_diff"])
    assert state_hash(after) == record["state_after_hash"]
    assert list(STATE_VALIDATOR.iter_errors(after)) == []
    assert cross_field_errors(after) == []
    assert after["turn_number"] == record["turn_number"]


def test_record_is_one_jsonl_line() -> None:
    line = json.dumps(_valid(), ensure_ascii=False)
    assert "\n" not in line
    assert json.loads(line) == _valid()


def _set(path: str, value: Any) -> Callable[[Record], None]:
    *parents, leaf = path.split(".")

    def mutate(record: Record) -> None:
        node: Any = record
        for key in parents:
            node = node[int(key)] if isinstance(node, list) else node[key]
        if isinstance(node, list):
            node[int(leaf)] = value
        else:
            node[leaf] = value

    return mutate


def _delete(path: str) -> Callable[[Record], None]:
    *parents, leaf = path.split(".")

    def mutate(record: Record) -> None:
        node: Any = record
        for key in parents:
            node = node[int(key)] if isinstance(node, list) else node[key]
        del node[leaf]

    return mutate


def _fourth_attempt(record: Record) -> None:
    call = copy.deepcopy(record["model_calls"][-1])
    call["attempt"] = 4
    record["model_calls"].append(call)
    record["proposed_calls"].append(record["proposed_calls"][-1])
    record["validation"].append(record["validation"][-1])


SCHEMA_REJECTS = {
    "unknown_key": _set("location", "cellar"),
    "missing_key": _delete("engine_steps"),
    "unknown_condition": _set("condition", "E"),
    "bad_run_id": _set("run_id", "D-s01_cellar-12345"),
    "turn_number_0": _set("turn_number", 0),
    "local_timestamp": _set("timestamp", "2026-11-09 21:22:31+07:00"),
    "bad_hash": _set("state_before_hash", "md5:abc"),
    "unknown_phase": _set("model_calls.0.phase", "planning"),
    "attempt_0": _set("model_calls.0.attempt", 0),
    "negative_latency": _set("model_calls.0.latency_ms", -1),
    "negative_eval_ms": _set("model_calls.0.eval_ms", -1),
    "missing_eval_ms": _delete("model_calls.0.eval_ms"),
    "negative_turn_latency": _set("turn_latency_ms", -1),
    "missing_turn_latency": _delete("turn_latency_ms"),
    "proposed_call_not_object": _set("proposed_calls.0", "attack the rat"),
    "unknown_rejection_code": _set(
        "validation.0", {**_rejected()["validation"][0], "rejection_code": "TOO_FAR"}
    ),
    "executed_null_tool": _set("executed_call", {"tool": None}),
    "executed_bad_arguments": _set("executed_call.arguments.dc", 12),
    "unknown_engine_step": _set("engine_steps.0.step", "npc_flee"),
    "bad_roll": _set("rolls.0.individual_dice", [0]),
    "bad_diff_path": _set("state_diff.0.path", "Combatants.npc_rat_02.hp"),
    "unknown_turn_failure": _set("turn_failure", "timeout"),
    "summary_without_truncated": _set("summary", {"text": "Lyra fought rats."}),
}


@pytest.mark.parametrize("mutate", SCHEMA_REJECTS.values(), ids=SCHEMA_REJECTS.keys())
def test_schema_rejects(mutate: Callable[[Record], None]) -> None:
    record = _valid()
    mutate(record)
    assert _schema_errors(record), "schema accepted an invalid record"


def test_schema_rejects_four_attempts_on_a_failed_turn() -> None:
    record = _rejected()
    _fourth_attempt(record)
    assert _schema_errors(record)


def _drop_engine_step(index: int) -> Callable[[Record], None]:
    def mutate(record: Record) -> None:
        del record["engine_steps"][index]

    return mutate


def _as_condition_b(record: Record) -> None:
    record["condition"] = "B"
    record["run_id"] = "B_s01_cellar_12345"


VALID_CROSS_FIELD_REJECTS = {
    "run_id_disagrees": _set("run_id", "D_s02_crypt_12345"),
    "tool_phase_in_condition_b": _as_condition_b,
    "attempts_misnumbered": _set("model_calls.0.attempt", 2),
    "executed_differs_from_proposed": _set("executed_call.arguments.target_id", "npc_rat_01"),
    "step_missing_from_diff": _drop_engine_step(1),
    "diff_out_of_order": lambda r: r["state_diff"].reverse(),
    "roll_missing": lambda r: r["rolls"].pop(),
    "hashes_equal_with_diff": lambda r: r.update(state_after_hash=r["state_before_hash"]),
    "failure_on_a_good_turn": _set("turn_failure", "precondition"),
    "narration_only_on_a_tool_turn": _set("narration_only", True),
    "two_narration_calls": lambda r: r["model_calls"].append(copy.deepcopy(r["model_calls"][1])),
    "summary_flag_without_text": _set("summary_regenerated", True),
    "turn_shorter_than_calls": _set("turn_latency_ms", 1000),
    "eval_longer_than_call": _set("model_calls.1.eval_ms", 4000),
}

REJECTED_CROSS_FIELD_REJECTS = {
    "failure_kind_disagrees": _set("turn_failure", "schema"),
    "no_failure_after_budget": _set("turn_failure", None),
    "executed_after_rejection": _set("executed_call", _valid()["executed_call"]),
    "parse_failure_with_a_call": _set("proposed_calls.1", _valid()["executed_call"]),
    "narration_on_failed_turn": lambda r: r["model_calls"].append(
        {**_valid()["model_calls"][1], "attempt": 1}
    ),
}


@pytest.mark.parametrize(
    "mutate", VALID_CROSS_FIELD_REJECTS.values(), ids=VALID_CROSS_FIELD_REJECTS.keys()
)
def test_cross_field_rejects_on_valid_turn(mutate: Callable[[Record], None]) -> None:
    record = _valid()
    mutate(record)
    assert _schema_errors(record) == [], "case should pass the schema and fail only in Python"
    assert record_errors(record)


@pytest.mark.parametrize(
    "mutate", REJECTED_CROSS_FIELD_REJECTS.values(), ids=REJECTED_CROSS_FIELD_REJECTS.keys()
)
def test_cross_field_rejects_on_rejected_turn(mutate: Callable[[Record], None]) -> None:
    record = _rejected()
    mutate(record)
    assert _schema_errors(record) == [], "case should pass the schema and fail only in Python"
    assert record_errors(record)


def test_npc_actions_may_run_before_the_call() -> None:
    # An NPC that wins initiative acts before the player's first call of the
    # encounter (WBS 4.19): its steps are before_call and come first.
    record = _valid()
    steps = record["engine_steps"]
    for step in steps[:-1]:  # all but turn_increment
        step["when"] = "before_call"
    result = record["validation"][-1]
    for key in ("state_diff", "rolls"):
        record[key] = (
            [x for s in steps[:-1] for x in step_part(s, key)]
            + result[key]
            + step_part(steps[-1], key)
        )
    assert _schema_errors(record) == []
    assert record_errors(record) == []


def test_narration_only_turn_is_consistent() -> None:
    record = _valid()
    null_call = {"tool": None}
    record.update(
        player_input="I wave at the rats",
        proposed_calls=[null_call],
        validation=[{"ok": True, "tool": None}],
        executed_call=None,
        engine_steps=[],
        rolls=[],
        state_diff=[],
        state_after_hash=record["state_before_hash"],
        narration_only=True,
    )
    record["model_calls"][0]["raw_output"] = json.dumps(null_call)
    assert _schema_errors(record) == []
    assert record_errors(record) == []
