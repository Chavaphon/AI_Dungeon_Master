"""The replay harness (WBS 4.18): a seed plus a scenario reproduces a session.

Invariant 4: the same `(seed, scenario_id, condition)` reproduces a
byte-identical run. This module serves it in two ways.

`replay_script(scenario, seed)` plays the scenario's scripted inputs through the
engine alone, with no model. Each input proposes exactly its `expected_call`, or
`{"tool": null}` when that is null. The turn then runs as a scripted condition D
turn does in `adm/orchestration/session.py`, with the same engine functions in
the same order:

1. The encounter due before the input opens (`due_encounter`, `open_encounter`).
   The NPCs who win initiative act as `before_call` steps.
2. The call goes through `dispatch_scripted`, the one write path. A skill check
   runs with the scenario's DC and advantage (CLAUDE.md section 4.7).
3. A rejected call is a failed turn. It does not advance and nothing runs after
   it, as when condition D's retry budget runs out on the same call (section
   7.1). Its `turn_failure` is named the same way.
4. Otherwise the steps after the call (`after_call`) and `turn_increment` run.
   A null call is a narration-only turn, which advances (decision 34).

So the replay is the run that condition D gives when the model proposes every
expected call. It is the ground truth of conditions A to C (CLAUDE.md section
9): the state the scenario script says should hold at each input. Rejections
such as `ENCOUNTER_OVER` are kept, as in any scripted run (decision 23). The
`DiceRoller` is made once from the seed (invariant 3), so the replay depends on
nothing but the scenario and the seed. `to_jsonl` writes it in the canonical
JSON of docs/conventions.md section 2, so two replays of one seed can be
compared byte for byte.

Each `ReplayTurn` uses the audit record's names for the fields the two share
(CLAUDE.md section 11), with one validation entry and no model calls, and adds
`state`, the state after the turn.

`replay_view` and `log_differences` compare two audit logs of one run the way
CLAUDE.md section 11 says a byte-identical replay is compared: every field
except the timings `timestamp`, `latency_ms`, `eval_ms` and `turn_latency_ms`
(decision 31).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Any

from adm.engine.audit import Step, changed_paths, engine_fields, failure_kind
from adm.engine.dice import DiceRoller
from adm.engine.scenario import Scenario, due_encounter, initial_state
from adm.engine.tools import after_call, dispatch_scripted, increment_turn, open_encounter

Doc = dict[str, Any]

NULL_CALL: Doc = {"tool": None}

# The fields left out of a replay comparison (CLAUDE.md section 11).
RECORD_TIMINGS = ("timestamp", "turn_latency_ms")
CALL_TIMINGS = ("latency_ms", "eval_ms")


@dataclass(frozen=True)
class ReplayTurn:
    """One scripted input, played by the engine with its expected call."""

    input_index: int
    turn_number: int
    player_input: str
    executed_call: Doc | None
    validation: Doc
    engine_steps: list[Doc]
    rolls: list[Doc]
    state_before_hash: str
    state_after_hash: str
    state_diff: list[Doc]
    turn_failure: str | None
    narration_only: bool
    state: Doc

    def to_dict(self) -> Doc:
        return asdict(self)


def replay_script(scenario: Scenario, seed: int) -> list[ReplayTurn]:
    """Play every scripted input of `scenario` with its expected call, from the
    turn-0 state of a run with `seed`."""
    state = initial_state(scenario, seed)
    roller = DiceRoller(seed)
    started = 0
    turns: list[ReplayTurn] = []
    for index, scripted in enumerate(scenario.scripted_inputs):
        before = state.to_dict()
        steps: list[Step] = []
        encounter = due_encounter(scenario.encounters, started, index, state)
        if encounter is not None:
            steps += open_encounter(state, roller, encounter.combatant_ids)
            started += 1

        call = scripted.expected_call or NULL_CALL
        entry = dispatch_scripted(state, roller, call, scripted)
        executed = entry["ok"] and entry["tool"] is not None
        if executed:
            steps += after_call(state, roller, entry["tool"])
        if entry["ok"]:
            steps.append(increment_turn(state))

        turns.append(
            ReplayTurn(
                input_index=index,
                turn_number=before["turn_number"] + 1,
                player_input=scripted.text,
                executed_call=call if executed else None,
                validation=entry,
                **engine_fields(before, steps, entry if executed else None, state),
                turn_failure=None if entry["ok"] else failure_kind(entry),
                narration_only=entry["ok"] and not executed,
                state=state.to_dict(),
            )
        )
    return turns


def to_jsonl(turns: Sequence[ReplayTurn]) -> str:
    """The replay as JSON Lines, one turn per line, in canonical JSON."""
    return "".join(
        json.dumps(t.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
        for t in turns
    )


# --- comparing two runs ------------------------------------------------------


def replay_view(record: Doc) -> Doc:
    """An audit record without its timings: what a replay must reproduce."""
    view = {k: v for k, v in record.items() if k not in RECORD_TIMINGS}
    view["model_calls"] = [
        {k: v for k, v in call.items() if k not in CALL_TIMINGS} for call in record["model_calls"]
    ]
    return view


def log_differences(first: Sequence[Doc], second: Sequence[Doc]) -> list[str]:
    """Where two audit logs of one run differ, timings aside: one line per
    record and path. An empty list means the second run replays the first."""
    differences = [
        f"record {i}: {path or '<record>'}"
        for i, (a, b) in enumerate(zip(first, second, strict=False))
        for path in changed_paths(replay_view(a), replay_view(b))
    ]
    if len(first) != len(second):
        differences.append(f"{len(first)} records against {len(second)}")
    return differences
