"""The tool phase of a condition D turn and its failure pipeline (WBS 6.4,
CLAUDE.md sections 7 and 7.1).

Model call 1 runs at temperature 0.0 and proposes a call. The proposal is
parsed (`parser.parse_tool_call`), validated (`validator.validate`) and, if it
passes, executed by the caller's `execute`. Anything else is one of the five
section 7.1 modes, and the model is retried with a structured error:

1. Unparseable output: the expected format with one example (`retry_unparseable`).
2. `SCHEMA_VIOLATION`, 3. `UNKNOWN_ENTITY` and 4. every state-precondition code:
   the full rejection envelope (`retry_rejected`). Its message names the
   offending field and type, or the state values behind the rejection, and its
   `valid_options` lists what would have passed.
5. `{"tool": null}`: re-prompted once with an explicit instruction to select a
   tool (`retry_no_tool`). The first null of a turn is always re-prompted; the
   loop has no way to tell input that clearly needs a tool from conversation
   (docs/decisions.md, WBS 6.4). A second null, or a null on the last attempt,
   ends the phase as `narration_only`.

The retry budget is two, so there are at most three toolcall calls and the
loop cannot run on (CLAUDE.md section 1.2, CONTROL). A retry sends the first
call's prompt unchanged, then every earlier reply as an `assistant` message
and its error as a `user` message. When all three attempts fail, the phase ends
with a `turn_failure` named after the last attempt: `unparseable`, `schema`,
`unknown_entity` or `precondition` (docs/audit_log.md section 3). What a failed
turn does next, and writing its record, belong to the turn loop (WBS 6.5).

The phase reads the state and never writes it: only `execute`, called at most
once and only for a validated call, reaches the engine (invariants 1 and 6).
A `ModelUnavailable` from the client is not a turn failure and propagates.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from adm.engine.state import GameState
from adm.engine.validator import Rejection, ToolCall, validate
from adm.orchestration.client import Message, ModelClient, ModelConfig
from adm.orchestration.parser import ParseFailure, parse_tool_call
from adm.orchestration.prompt import Doc, HistoryTurn, assemble, prompt_budget, retry_feedback

TEMPLATE = "d_toolcall"
RETRY_BUDGET = 2
MAX_TOOLCALL_ATTEMPTS = 1 + RETRY_BUDGET

TurnFailure = Literal["unparseable", "schema", "unknown_entity", "precondition"]
# Every other rejection code is a state precondition.
_FAILURE_BY_CODE: dict[str, TurnFailure] = {
    "SCHEMA_VIOLATION": "schema",
    "UNKNOWN_ENTITY": "unknown_entity",
}

# Executes a validated call and returns its full `result_ok` envelope.
Execute = Callable[[ToolCall], Doc]


@dataclass(frozen=True)
class ToolPhase:
    """The tool phase's part of the turn record (docs/audit_log.md section 1).

    `model_calls`, `proposed_calls` and `validation` have one entry per attempt.
    `executed_call` is set exactly when the last attempt succeeded, and its
    `result_ok` is then the last validation entry.
    """

    model_calls: tuple[Doc, ...]
    proposed_calls: tuple[Doc | None, ...]
    validation: tuple[Doc, ...]
    executed_call: ToolCall | None
    turn_failure: TurnFailure | None
    narration_only: bool
    k_used: int

    @property
    def result(self) -> Doc | None:
        return self.validation[-1] if self.executed_call is not None else None


def turn_failure_kind(entry: Mapping[str, object]) -> TurnFailure:
    """The `turn_failure` a failed attempt's validation entry stands for."""
    if entry.get("failure") == "unparseable":
        return "unparseable"
    return _FAILURE_BY_CODE.get(str(entry["rejection_code"]), "precondition")


def _pc_id(state: GameState) -> str:
    return next(cid for cid, c in state.combatants.items() if c.is_player_character)


def run_tool_phase(
    client: ModelClient,
    config: ModelConfig,
    texts: Mapping[str, str],
    state: GameState,
    *,
    player_input: str,
    history: Sequence[HistoryTurn],
    summary: str | None,
    seed: int,
    execute: Execute,
) -> ToolPhase:
    """Propose, validate and execute the player's call, retrying at most twice."""
    budget = prompt_budget(config, "toolcall")
    k_used = config.K_verbatim_turns
    model_calls: list[Doc] = []
    proposed: list[Doc | None] = []
    validation: list[Doc] = []
    followups: list[Message] = []
    null_reprompted = False

    def phase(
        executed: ToolCall | None = None,
        failure: TurnFailure | None = None,
        narration_only: bool = False,
    ) -> ToolPhase:
        return ToolPhase(
            tuple(model_calls),
            tuple(proposed),
            tuple(validation),
            executed,
            failure,
            narration_only,
            k_used,
        )

    for attempt in range(1, MAX_TOOLCALL_ATTEMPTS + 1):
        assembled = assemble(
            texts,
            TEMPLATE,
            player_input=player_input,
            history=history,
            summary=summary,
            k=k_used,
            budget=budget,
            state=state,
            followups=followups,
        )
        k_used = assembled.k_used
        reply = client.chat(assembled.messages, phase="toolcall", seed=seed)
        model_calls.append(reply.model_call("toolcall", attempt))

        parsed = parse_tool_call(reply.raw_output)
        if isinstance(parsed, ParseFailure):
            proposed.append(None)
            validation.append({"ok": False, "failure": "unparseable", "message": parsed.message})
            feedback = retry_feedback(texts, "retry_unparseable", {"pc_id": _pc_id(state)})
        else:
            proposed.append(parsed.call)
            checked = validate(state, parsed.call)
            if isinstance(checked, Rejection):
                envelope = checked.to_dict()
                validation.append(envelope)
                values = {"rejection_json": json.dumps(envelope, ensure_ascii=False)}
                feedback = retry_feedback(texts, "retry_rejected", values)
            elif checked.tool is None:
                validation.append({"ok": True, "tool": None})
                if null_reprompted or attempt == MAX_TOOLCALL_ATTEMPTS:
                    return phase(narration_only=True)
                null_reprompted = True
                feedback = retry_feedback(texts, "retry_no_tool", {})
            else:
                validation.append(execute(checked))
                return phase(executed=checked)

        followups += [
            {"role": "assistant", "content": reply.raw_output},
            {"role": "user", "content": feedback},
        ]

    return phase(failure=turn_failure_kind(validation[-1]))
