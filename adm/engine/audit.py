"""State diffs and the audit-log writer (WBS 5.3, CLAUDE.md section 11, docs/audit_log.md).

Every engine write returns the diff of what it changed, as `state_diff_entry`s
(`{path, from, to}`). This module holds that diff to account (invariant 2):

- `apply_diff` replays a diff on a state in its JSON form. Each entry's `from`
  must be the value it replaces. A `from` of `null` adds a key (a new inventory
  item, a new owner) or appends to a list (a relationship's `history`).
- `check_write` replays a write's diff on the state from before it and requires
  the result to be the state after it. A change with no diff entry, or an entry
  that does not match the change, raises `UnrecordedWrite`, which names the
  paths that differ. `adm/engine/tools.py` runs it on every write it makes.
- `engine_fields` builds the engine's part of a turn record: `engine_steps`,
  the top-level `state_diff` and `rolls` (the before-call steps, then the
  executed call's result, then the after-call steps, docs/audit_log.md section
  2), and the two state hashes. It runs `check_write` over the whole turn, so a
  record cannot be built for a turn whose diff misses a write.

`AuditLog` appends turn records to `runs/{condition}/{scenario_id}/{seed}.jsonl`,
one JSON object per line. It refuses a record that fails `schemas/audit.schema.json`
or the rules the schema cannot express (`record_errors`, docs/audit_log.md section
3), or that belongs to another run, and then writes nothing. Each line is flushed
and synced before `append` returns, so a run that dies keeps every turn it wrote.
The record is written as given, in compact JSON; the timings in it come from
orchestration (docs/conventions.md section 2). `turn_failure_counts` counts a
log's failed turns by kind (WBS 6.5).
"""

from __future__ import annotations

import copy
import json
import os
from collections import Counter
from collections.abc import Sequence
from functools import cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from adm.engine.combat import EngineStep
from adm.engine.npc import NpcActionStep
from adm.engine.state import GameState, data_hash, state_hash

SCHEMAS = Path(__file__).resolve().parents[2] / "schemas"

RETRY_BUDGET = 2  # CLAUDE.md section 7.1: 3 toolcall attempts at most
FAILURE_KIND = {"SCHEMA_VIOLATION": "schema", "UNKNOWN_ENTITY": "unknown_entity"}

Doc = dict[str, Any]
Step = EngineStep | NpcActionStep


class DiffMismatch(ValueError):
    """A diff entry whose `from` is not the value at its path."""


class UnrecordedWrite(RuntimeError):
    """A write whose diff does not account for what it changed (invariant 2)."""


class InvalidRecord(ValueError):
    """A turn record the audit log refuses to write."""


# --- state diffs -------------------------------------------------------------


def apply_diff(data: Doc, diff: Sequence[Doc]) -> Doc:
    """Replay `diff` on a copy of `data`, a state in its JSON form, and return it."""
    data = copy.deepcopy(data)
    for entry in diff:
        path = entry["path"]
        *parents, leaf = path.split(".")
        node: Any = data
        for key in parents:
            node = node[int(key)] if isinstance(node, list) else node[key]
        if isinstance(node, list):
            index = int(leaf)
            if index > len(node):
                raise DiffMismatch(f"{path}: index {index} skips past the end of the list")
            current = node[index] if index < len(node) else None
        else:
            current = node.get(leaf)
        if current != entry["from"]:
            raise DiffMismatch(f"{path} is {current!r}, but the diff says from {entry['from']!r}")
        if isinstance(node, list) and index == len(node):
            node.append(entry["to"])
        else:
            node[int(leaf) if isinstance(node, list) else leaf] = entry["to"]
    return data


def changed_paths(before: Any, after: Any, prefix: str = "") -> list[str]:
    """The paths at which two JSON values differ, in sorted order."""
    if isinstance(before, dict) and isinstance(after, dict):
        keys = sorted(set(before) | set(after))
        return [
            path
            for key in keys
            for path in changed_paths(before.get(key), after.get(key), f"{prefix}{key}.")
        ]
    if isinstance(before, list) and isinstance(after, list) and len(before) == len(after):
        return [
            path
            for i, (b, a) in enumerate(zip(before, after, strict=True))
            for path in changed_paths(b, a, f"{prefix}{i}.")
        ]
    return [] if before == after else [prefix.rstrip(".")]


def check_write(before: Doc, diff: Sequence[Doc], state: GameState) -> None:
    """Require `diff`, replayed on `before`, to give exactly `state`."""
    try:
        replayed = apply_diff(before, diff)
    except DiffMismatch as exc:
        raise UnrecordedWrite(f"the diff does not replay: {exc}") from exc
    after = state.to_dict()
    if replayed != after:
        paths = ", ".join(changed_paths(replayed, after))
        raise UnrecordedWrite(f"the state changed without a matching diff entry at {paths}")


def step_part(step: Doc, key: str) -> list[Any]:
    """An engine step's `state_diff` or `rolls`; an NPC action keeps them in its result."""
    return step["result"][key] if step["step"] == "npc_action" else step[key]


def engine_fields(before: Doc, steps: Sequence[Step], result: Doc | None, state: GameState) -> Doc:
    """The engine's fields of a turn record, for a turn that started from `before`
    (`state.to_dict()` at the start of the turn) and ended in `state`. `result`
    is the executed call's `result_ok`, or None if no call ran."""
    step_docs = [s.to_dict() for s in steps]
    whens = [s["when"] for s in step_docs]
    if whens != sorted(whens, key=lambda w: w != "before_call"):
        raise ValueError(f"a before_call step comes after an after_call step: {whens}")
    if result is not None and not (result["ok"] and result.get("tool")):
        raise ValueError("result must be the result_ok of an executed call")

    parts: Doc = {}
    for key in ("state_diff", "rolls"):
        parts[key] = (
            [x for s in step_docs if s["when"] == "before_call" for x in step_part(s, key)]
            + (result[key] if result is not None else [])
            + [x for s in step_docs if s["when"] == "after_call" for x in step_part(s, key)]
        )
    check_write(before, parts["state_diff"], state)
    return {
        "engine_steps": step_docs,
        "rolls": parts["rolls"],
        "state_before_hash": data_hash(before),
        "state_after_hash": state_hash(state),
        "state_diff": parts["state_diff"],
    }


# --- the turn record ---------------------------------------------------------


@cache
def _record_validator() -> Draft202012Validator:
    schemas = {
        name: json.loads((SCHEMAS / name).read_text(encoding="utf-8"))
        for name in ("audit.schema.json", "state.schema.json", "tools.schema.json")
    }
    registry = Registry().with_resources(
        (s["$id"], Resource.from_contents(s)) for s in schemas.values()
    )
    return Draft202012Validator(schemas["audit.schema.json"], registry=registry)


def schema_errors(record: Doc) -> list[str]:
    """Where `record` breaks schemas/audit.schema.json."""
    errors = sorted(_record_validator().iter_errors(record), key=lambda e: list(e.absolute_path))
    return [f"{e.json_path}: {e.message}" for e in errors]


def _failure_kind(entry: Doc) -> str:
    if entry.get("failure") == "unparseable":
        return "unparseable"
    return FAILURE_KIND.get(entry.get("rejection_code", ""), "precondition")


def record_errors(record: Doc) -> list[str]:
    """Where `record` breaks the rules of docs/audit_log.md section 3, which JSON
    Schema cannot express. Assumes the record passes the schema."""
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
        if any(s["when"] == "after_call" for s in record["engine_steps"]):
            errors.append("a failed turn has after_call steps")
    elif last is not None and not last["ok"]:
        errors.append("last attempt failed but turn_failure is null")

    increments = [i for i, s in enumerate(record["engine_steps"]) if s["step"] == "turn_increment"]
    if condition == "D" and failure is None and increments != [len(record["engine_steps"]) - 1]:
        errors.append("a turn that did not fail must end with one turn_increment")

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
            [x for s in steps if s["when"] == "before_call" for x in step_part(s, key)]
            + tool_part[key]
            + [x for s in steps if s["when"] == "after_call" for x in step_part(s, key)]
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

    if record["turn_latency_ms"] < sum(c["latency_ms"] for c in record["model_calls"]):
        errors.append("turn_latency_ms is shorter than the turn's model calls")
    for call in record["model_calls"]:
        if call["eval_ms"] > call["latency_ms"]:
            errors.append(f"{call['phase']} call {call['attempt']}: eval_ms exceeds latency_ms")

    return errors


# --- the JSONL writer --------------------------------------------------------


def run_id(condition: str, scenario_id: str, seed: int) -> str:
    """docs/identifiers.md section 3."""
    return f"{condition}_{scenario_id}_{seed}"


def log_path(runs_dir: Path, condition: str, scenario_id: str, seed: int) -> Path:
    """`runs/{condition}/{scenario_id}/{seed}.jsonl` (CLAUDE.md section 11)."""
    return runs_dir / condition / scenario_id / f"{seed}.jsonl"


class AuditLog:
    """The append-only turn log of one run."""

    def __init__(self, runs_dir: Path, condition: str, scenario_id: str, seed: int) -> None:
        self.run_id = run_id(condition, scenario_id, seed)
        self.path = log_path(runs_dir, condition, scenario_id, seed)

    def append(self, record: Doc) -> None:
        """Check `record` and write it as one line. Nothing is written if it fails."""
        errors = schema_errors(record)
        if not errors:
            errors = record_errors(record)
            if record["run_id"] != self.run_id:
                errors.append(f"record of run {record['run_id']} in the log of {self.run_id}")
        if errors:
            raise InvalidRecord(f"turn record refused for {self.path}:\n" + "\n".join(errors))
        line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as log:
            log.write(line + "\n")
            log.flush()
            os.fsync(log.fileno())

    def records(self) -> list[Doc]:
        """Every record written so far, in order; none if the log does not exist."""
        return read_log(self.path) if self.path.exists() else []


def read_log(path: Path) -> list[Doc]:
    """The records of a JSONL audit log, in order."""
    with path.open(encoding="utf-8") as log:
        return [json.loads(line) for line in log]


def turn_failure_counts(records: Sequence[Doc]) -> Counter[str]:
    """How many turns failed, by `turn_failure` kind (CLAUDE.md section 7.1:
    turn failures are a reported metric)."""
    return Counter(r["turn_failure"] for r in records if r["turn_failure"] is not None)
