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
`unknown_entity` or `precondition` (docs/audit_log.md section 3).

The phase reads the state and never writes it: only `execute`, called at most
once and only for a validated call, reaches the engine (invariants 1 and 6).
A `ModelUnavailable` from the client is not a turn failure and propagates.

`fail_turn` ends a turn whose budget ran out (WBS 6.5). There is no narration
call, no step after the call and no `turn_increment`, so neither `turn_number`
nor initiative advances; the record is still appended, and the player sees
`REPHRASE`. The before-call steps of an encounter that started before the turn
stay in its record, and the facts of their NPC actions are carried to the next
narrated turn (docs/decisions.md, WBS 6.5). Interactive play asks for new input
and a scripted run takes its next input, so both simply play the next turn.

`narrate_turn` ends every other turn (WBS 6.6, CLAUDE.md section 9.1). Model
call 2 runs at temperature 0.7 on `d_narration`, which holds no state: only the
turn's `narration_facts`, as one array in the order things happened (`turn_facts`):
facts carried from a failed turn, the NPC actions before the call, the player's
executed call, then the NPC actions after it. A narration-only turn has no call,
so its array holds only NPC facts, and is often empty. The narration call reuses
the tool phase's `k_used`, so a turn has one K; a narration prompt is far smaller
than the tool-call one, so one that would need K reduced is a bug and raises.
The caller runs the engine steps after the call, `turn_increment` included,
before narrating, and passes `fold` when the rolling summary is due: it is then
regenerated from this turn's narration before the record is appended.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

from adm.engine.audit import AuditLog, Step, engine_fields, run_id
from adm.engine.npc import NpcActionStep
from adm.engine.state import GameState
from adm.engine.validator import Rejection, ToolCall, validate
from adm.orchestration.client import Message, ModelClient, ModelConfig, ModelReply
from adm.orchestration.parser import ParseFailure, parse_tool_call
from adm.orchestration.prompt import (
    Doc,
    HistoryTurn,
    PromptTooLarge,
    assemble,
    prompt_budget,
    retry_feedback,
)
from adm.orchestration.summary import Summary, regenerate

TEMPLATE = "d_toolcall"
RETRY_BUDGET = 2
MAX_TOOLCALL_ATTEMPTS = 1 + RETRY_BUDGET
REPHRASE = "I couldn't turn that into an action. Could you rephrase it?"

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


# --- the turn record and the failed turn (WBS 6.5) ---------------------------

CONDITION = "D"


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass
class TurnTimer:
    """A turn's `timestamp` and `turn_latency_ms`, from receiving the player's
    input to writing the record (docs/audit_log.md section 1). Start one when the
    input arrives; timings are taken only in orchestration (docs/conventions.md
    section 2)."""

    clock: Callable[[], float] = time.perf_counter
    now: Callable[[], datetime] = _utc_now
    started: float = field(init=False)
    timestamp: str = field(init=False)

    def __post_init__(self) -> None:
        self.started = self.clock()
        self.timestamp = self.now().strftime("%Y-%m-%dT%H:%M:%SZ")

    def elapsed_ms(self) -> int:
        return round((self.clock() - self.started) * 1000)


def turn_record(
    state: GameState,
    before: Doc,
    steps: Sequence[Step],
    phase: ToolPhase,
    *,
    input_index: int | None,
    player_input: str,
    narration: str,
    narration_filtered: bool,
    later_calls: Sequence[Doc] = (),
    summary: Doc | None = None,
    timer: TurnTimer,
) -> Doc:
    """The condition D turn record of a turn that started from `before`
    (`state.to_dict()` when the input arrived) and ended in `state`. `steps` are
    the turn's engine steps, and `later_calls` its model calls after the tool
    phase, in order."""
    return {
        "run_id": run_id(CONDITION, state.scenario_id, state.seed),
        "condition": CONDITION,
        "scenario_id": state.scenario_id,
        "seed": state.seed,
        "turn_number": before["turn_number"] + 1,
        "input_index": input_index,
        "timestamp": timer.timestamp,
        "player_input": player_input,
        "model_calls": [*phase.model_calls, *later_calls],
        "proposed_calls": list(phase.proposed_calls),
        "validation": list(phase.validation),
        "executed_call": (
            phase.executed_call.model_dump(mode="json") if phase.executed_call else None
        ),
        **engine_fields(before, steps, phase.result, state),
        "narration": narration,
        "narration_filtered": narration_filtered,
        "turn_failure": phase.turn_failure,
        "narration_only": phase.narration_only,
        "k_used": phase.k_used,
        "summary_regenerated": summary is not None,
        "summary": summary,
        "turn_latency_ms": timer.elapsed_ms(),
    }


@dataclass(frozen=True)
class FailedTurn:
    """A turn that exhausted its retry budget, as written to the audit log.

    `carried_facts` are the `narration_facts` of the NPC actions among its
    before-call steps, in order. No narration call saw them, so the next
    narrated turn puts them first in its `{narration_facts_json}`.
    """

    record: Doc
    carried_facts: tuple[Doc, ...]

    @property
    def message(self) -> str:
        """What the player is shown in place of narration."""
        return str(self.record["narration"])


def fail_turn(
    log: AuditLog,
    state: GameState,
    before: Doc,
    steps: Sequence[Step],
    phase: ToolPhase,
    *,
    input_index: int | None,
    player_input: str,
    timer: TurnTimer,
) -> FailedTurn:
    """Log a turn whose tool phase exhausted the retry budget (CLAUDE.md 7.1).

    `steps` may only be the before-call steps of an encounter that started
    before this turn: the loop runs nothing after a failed call, so the turn
    does not advance. `log.append` refuses the record otherwise.
    """
    if phase.turn_failure is None:
        raise ValueError("fail_turn needs a tool phase that exhausted its retry budget")
    record = turn_record(
        state,
        before,
        steps,
        phase,
        input_index=input_index,
        player_input=player_input,
        narration=REPHRASE,
        narration_filtered=False,
        timer=timer,
    )
    log.append(record)
    return FailedTurn(record, tuple(_npc_facts(steps, "before_call")))


# --- the narrated turn (WBS 6.6) ---------------------------------------------

NARRATION_TEMPLATE = "d_narration"


def _npc_facts(steps: Sequence[Step], when: str) -> list[Doc]:
    return [
        s.result["narration_facts"]
        for s in steps
        if isinstance(s, NpcActionStep) and s.when == when
    ]


def turn_facts(steps: Sequence[Step], result: Doc | None, carried: Sequence[Doc] = ()) -> list[Doc]:
    """The `{narration_facts_json}` array of a turn, in the order things happened:
    `carried` from a failed turn, the NPC actions before the call, the executed
    call's facts (`result` is its `result_ok`, None if no call ran), then the NPC
    actions after it (CLAUDE.md section 9.1)."""
    player = [result["narration_facts"]] if result is not None else []
    return [*carried, *_npc_facts(steps, "before_call"), *player, *_npc_facts(steps, "after_call")]


@dataclass(frozen=True)
class Narration:
    text: str
    facts: tuple[Doc, ...]
    reply: ModelReply

    def model_call(self) -> Doc:
        """The turn record's `model_calls` entry for the narration call."""
        return self.reply.model_call("narration", 1)


def narrate(
    client: ModelClient,
    config: ModelConfig,
    texts: Mapping[str, str],
    *,
    facts: Sequence[Doc],
    player_input: str,
    history: Sequence[HistoryTurn],
    summary: str | None,
    k: int,
    seed: int,
) -> Narration:
    """Model call 2: narrate `facts`, with the turn's K."""
    assembled = assemble(
        texts,
        NARRATION_TEMPLATE,
        player_input=player_input,
        history=history,
        summary=summary,
        k=k,
        budget=prompt_budget(config, "narration"),
        facts=facts,
    )
    if assembled.k_reduced:
        raise PromptTooLarge(f"the narration prompt fits only {assembled.k_used} of {k} turns")
    reply = client.chat(assembled.messages, phase="narration", seed=seed)
    return Narration(reply.raw_output.strip(), tuple(facts), reply)


@dataclass(frozen=True)
class NarratedTurn:
    """A narrated turn as written to the audit log, with the summary it regenerated."""

    record: Doc
    narration: Narration
    summary: Summary | None

    @property
    def message(self) -> str:
        """What the player is shown."""
        return self.narration.text


def narrate_turn(
    log: AuditLog,
    client: ModelClient,
    config: ModelConfig,
    texts: Mapping[str, str],
    state: GameState,
    before: Doc,
    steps: Sequence[Step],
    phase: ToolPhase,
    *,
    carried_facts: Sequence[Doc] = (),
    input_index: int | None,
    player_input: str,
    history: Sequence[HistoryTurn],
    summary: str | None,
    seed: int,
    timer: TurnTimer,
    fold: Sequence[HistoryTurn] | None = None,
) -> NarratedTurn:
    """Narrate a turn whose tool phase did not fail, and log it.

    `steps` are all the turn's engine steps, ending with `turn_increment`;
    `log.append` refuses the record otherwise. `carried_facts` come from the
    failed turn before this one, if any. `fold` is given when the rolling summary
    is due: the narrated turns since its last regeneration, without this one.
    """
    if phase.turn_failure is not None:
        raise ValueError("narrate_turn needs a tool phase that did not fail; use fail_turn")
    narration = narrate(
        client,
        config,
        texts,
        facts=turn_facts(steps, phase.result, carried_facts),
        player_input=player_input,
        history=history,
        summary=summary,
        k=phase.k_used,
        seed=seed,
    )
    later_calls = [narration.model_call()]
    regenerated = None
    if fold is not None:
        turns = [*fold, HistoryTurn(player_input, narration.text)]
        regenerated = regenerate(client, config, texts, previous=summary, turns=turns, seed=seed)
        later_calls.append(regenerated.model_call())
    record = turn_record(
        state,
        before,
        steps,
        phase,
        input_index=input_index,
        player_input=player_input,
        narration=narration.text,
        narration_filtered=False,
        later_calls=later_calls,
        summary=regenerated.record() if regenerated else None,
        timer=timer,
    )
    log.append(record)
    return NarratedTurn(record, narration, regenerated)
