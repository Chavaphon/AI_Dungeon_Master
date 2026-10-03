"""Audit-log turn record v0.9 (WBS 2.4): the schema validates the example records
and rejects records that break CLAUDE.md sections 7 and 11.

`record_errors` covers the rules JSON Schema cannot express (see
docs/audit_log.md). The valid example is also replayed: its state_diff, applied
to the mid-combat example state, must reproduce state_after_hash. The runtime
writer belongs to WBS 5.3.

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

RETRY_BUDGET = 2  # CLAUDE.md section 7.1: 3 toolcall attempts at most
FAILURE_KIND = {"SCHEMA_VIOLATION": "schema", "UNKNOWN_ENTITY": "unknown_entity"}

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


def apply_diff(state: dict[str, Any], diff: list[dict[str, Any]]) -> dict[str, Any]:
    state = copy.deepcopy(state)
    for entry in diff:
        *parents, leaf = entry["path"].split(".")
        node = state
        for key in parents:
            node = node[key]
        assert node[leaf] == entry["from"], f"{entry['path']} is {node[leaf]!r}, diff says from"
        node[leaf] = entry["to"]
    return state


def _failure_kind(entry: Record) -> str:
    if entry.get("failure") == "unparseable":
        return "unparseable"
    return FAILURE_KIND.get(entry.get("rejection_code", ""), "precondition")


def _step_part(step: Record, key: str) -> list[Any]:
    return step["result"][key] if step["step"] == "npc_action" else step[key]


def record_errors(record: Record) -> list[str]:
    errors: list[str] = []
    condition = record["condition"]
    phases = [call["phase"] for call in record["model_calls"]]
    attempts = [c["attempt"] for c in record["model_calls"] if c["phase"] == "toolcall"]
    proposed, validation = record["proposed_calls"], record["validation"]
    executed, failure = record["executed_call"], record["turn_failure"]

    expected_id = f"{condition}_{record['scenario_id']}_{record['seed']}"
    if record["run_id"] != expected_id:
        errors.append(f"run_id {record['run_id']} should be {expected_id}")

    if condition != "D":
        if attempts or proposed or validation or executed or record["engine_steps"]:
            errors.append(f"condition {condition} has a tool phase")
        if record["state_diff"] or failure or record["narration_only"]:
            errors.append(f"condition {condition} changed state or failed a turn")

    if attempts != list(range(1, len(attempts) + 1)):
        errors.append(f"toolcall attempts are numbered {attempts}")
    if len(attempts) > RETRY_BUDGET + 1:
        errors.append(f"{len(attempts)} toolcall attempts exceed the retry budget")
    if not len(attempts) == len(proposed) == len(validation):
        errors.append("model_calls, proposed_calls and validation are not aligned")

    for i, (call, entry) in enumerate(zip(proposed, validation, strict=False)):
        if (call is None) != (entry.get("failure") == "unparseable"):
            errors.append(f"attempt {i + 1}: parse result and validation disagree")
        if call is not None and (call["tool"] is None) != (entry.get("tool", "") is None):
            errors.append(f"attempt {i + 1}: a null tool must be validated as no_tool")
        if entry["ok"] and entry.get("tool") is not None and i != len(validation) - 1:
            errors.append(f"attempt {i + 1} succeeded but the loop kept retrying")
    if sum(1 for e in validation[:-1] if e["ok"]) > 1:
        errors.append("more than one re-prompt after a null tool call")

    last = validation[-1] if validation else None
    ran = last is not None and last["ok"] and last.get("tool") is not None
    if ran and executed != proposed[-1]:
        errors.append("executed_call is not the last proposed call")
    if not ran and executed is not None:
        errors.append("executed_call is set but no attempt succeeded")

    if failure is not None:
        if last is None or last["ok"] or len(validation) != RETRY_BUDGET + 1:
            errors.append("turn_failure without an exhausted retry budget")
        elif failure != _failure_kind(last):
            errors.append(f"turn_failure {failure} does not match the last attempt")
        if record["state_diff"] or record["engine_steps"]:
            errors.append("a failed turn changed state")
    elif last is not None and not last["ok"]:
        errors.append("last attempt failed but turn_failure is null")

    is_null_turn = last is not None and last["ok"] and last.get("tool") is None
    if record["narration_only"] != (condition == "D" and failure is None and is_null_turn):
        errors.append("narration_only does not match the toolcall outcome")

    steps = record["engine_steps"]
    whens = [s["when"] for s in steps]
    if whens != sorted(whens, key=lambda w: w != "before_call"):
        errors.append("a before_call step comes after an after_call step")
    tool_part = last if ran else {"state_diff": [], "rolls": []}
    for key in ("state_diff", "rolls"):
        expected = (
            [x for s in steps if s["when"] == "before_call" for x in _step_part(s, key)]
            + tool_part[key]
            + [x for s in steps if s["when"] == "after_call" for x in _step_part(s, key)]
        )
        if record[key] != expected:
            errors.append(f"{key} is not the steps and the tool result in order")

    if (record["state_before_hash"] == record["state_after_hash"]) != (not record["state_diff"]):
        errors.append("state hashes do not match whether state_diff is empty")

    narration_calls = phases.count("narration")
    if narration_calls != (0 if failure else 1):
        errors.append(f"{narration_calls} narration calls for this turn")
    summary_calls = phases.count("summary")
    if not (summary_calls <= 1 and record["summary_regenerated"] == bool(summary_calls)):
        errors.append("summary_regenerated does not match the summary calls")
    if record["summary_regenerated"] != (record["summary"] is not None):
        errors.append("summary_regenerated does not match the summary field")

    return errors


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
    "proposed_call_not_object": _set("proposed_calls.0", "attack the rat"),
    "unknown_rejection_code": _set(
        "validation.0", {**_rejected()["validation"][0], "rejection_code": "TOO_FAR"}
    ),
    "executed_null_tool": _set("executed_call", {"tool": None}),
    "executed_bad_arguments": _set("executed_call.arguments.dc", 12),
    "unknown_engine_step": _set("engine_steps.0.step", "npc_flee"),
    "npc_action_before_call": _set("engine_steps.2.when", "before_call"),
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
