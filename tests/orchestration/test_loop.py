"""Failure pipeline (WBS 6.4): each of the five CLAUDE.md section 7.1 modes is
retried with a structured error and recovers within the budget, the budget of
two retries is never exceeded, and exhausting it ends the phase in a named
`turn_failure` (the done-when of #63, a CONTROL artefact).

No test calls a model: a fake client returns recorded replies.

Run: pytest tests/orchestration/test_loop.py -v
"""

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from adm.bench import context as bench
from adm.engine.combat import attack, dodge
from adm.engine.dice import DiceRoller
from adm.engine.state import GameState, load_state, state_hash
from adm.engine.validator import ToolCall
from adm.orchestration import prompt
from adm.orchestration.client import Message, ModelReply, Phase, build_options, load_model_config
from adm.orchestration.loop import (
    MAX_TOOLCALL_ATTEMPTS,
    RETRY_BUDGET,
    ToolPhase,
    run_tool_phase,
    turn_failure_kind,
)
from adm.orchestration.parser import EXPECTED_FORMAT
from adm.orchestration.prompt import HistoryTurn

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = ROOT / "schemas"
EXAMPLES = SCHEMAS / "examples"
FIXTURES = Path(__file__).parent / "fixtures"

Doc = dict[str, Any]

TEXTS = prompt.load_templates()
CONFIG = load_model_config()
K = CONFIG.K_verbatim_turns
HISTORY = bench.load_history()
TURNS = [HistoryTurn(t["player_input"], t["narration"]) for t in HISTORY["turns"]]
SUMMARY = HISTORY["summary"]
SEED = 12345
PLAYER_INPUT = "I bash the wounded rat with my torch"


def _recorded(model: str, case_id: str) -> str:
    for line in (FIXTURES / "recorded_toolcall_outputs.jsonl").read_text("utf-8").splitlines():
        record = json.loads(line)
        if (record["model"], record["case_id"]) == (model, case_id):
            return str(record["raw_output"])
    raise KeyError(case_id)


def _call(tool: str | None, **arguments: Any) -> str:
    return json.dumps({"tool": tool, "arguments": arguments} if tool else {"tool": None})


# One raw reply per outcome, against schemas/examples/state_02_mid_combat.json, where
# it is pc_lyra's turn. The unparseable and schema replies were recorded in Week 2.
VALID = _call("attack", attacker_id="pc_lyra", target_id="npc_rat_01", weapon_id="item_short_sword")
NULL = _call(None)
UNPARSEABLE = _recorded("llama3.1:8b", "tc08_attack_direct")
SCHEMA = _recorded("granite4.2:8b", "tc15_dodge_indirect")  # {"tool": "dodge"}
UNKNOWN = _call(
    "attack", attacker_id="pc_lyra", target_id="npc_goblin_01", weapon_id="item_short_sword"
)
PRECONDITION = _call(
    "attack", attacker_id="pc_lyra", target_id="npc_rat_01", weapon_id="item_torch"
)
REPLIES = {
    "valid": VALID,
    "null": NULL,
    "unparseable": UNPARSEABLE,
    "schema": SCHEMA,
    "unknown_entity": UNKNOWN,
    "precondition": PRECONDITION,
}


def _schema(name: str) -> Doc:
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


REGISTRY = Registry().with_resources(
    (s["$id"], Resource.from_contents(s))
    for s in (_schema(n) for n in ("audit.schema.json", "state.schema.json", "tools.schema.json"))
)
AUDIT_ID = _schema("audit.schema.json")["$id"]


def _validator(pointer: str) -> Draft202012Validator:
    return Draft202012Validator({"$ref": f"{AUDIT_ID}#/{pointer}"}, registry=REGISTRY)


class FakeClient:
    """Returns recorded replies in order and keeps every request."""

    def __init__(self, *replies: str) -> None:
        self.replies = list(replies)
        self.calls: list[tuple[tuple[Message, ...], Phase, int]] = []

    def chat(self, messages: Sequence[Message], *, phase: Phase, seed: int) -> ModelReply:
        self.calls.append((tuple(messages), phase, seed))
        return ModelReply(self.replies.pop(0), 3120, 40, 2200, 650, "stop", 0)

    def feedback(self, attempt: int) -> str:
        """The retry message sent with `attempt`, the error of the attempt before it."""
        return self.calls[attempt - 1][0][-1]["content"]


class Engine:
    """Executes attack and dodge on the state, as the turn loop's dispatch will."""

    def __init__(self, state: GameState) -> None:
        self.state = state
        self.roller = DiceRoller(SEED)
        self.executed: list[ToolCall] = []

    def __call__(self, call: ToolCall) -> Doc:
        self.executed.append(call)
        args = call.arguments
        if call.tool == "attack":
            outcome = attack(
                self.state, self.roller, args["attacker_id"], args["target_id"], args["weapon_id"]
            )
            return {"ok": True, "tool": "attack", **outcome.to_dict()}
        assert call.tool == "dodge"
        return {"ok": True, "tool": "dodge", **dodge(self.state, args["actor_id"]).to_dict()}


def _state() -> GameState:
    return load_state(EXAMPLES / "state_02_mid_combat.json")


def _run(
    *replies: str, state: GameState | None = None, config: Any = CONFIG
) -> tuple[ToolPhase, FakeClient, Engine]:
    client = FakeClient(*replies)
    engine = Engine(state or _state())
    result = run_tool_phase(
        client,
        config,
        TEXTS,
        engine.state,
        player_input=PLAYER_INPUT,
        history=TURNS[:K],
        summary=SUMMARY,
        seed=SEED,
        execute=engine,
    )
    return result, client, engine


def _rejection_in(feedback: str) -> Doc:
    """The rejection envelope a `retry_rejected` message carries, on its own line."""
    return json.loads(feedback.splitlines()[1])


# --- budget ---


def test_the_budget_is_two_retries() -> None:
    assert (RETRY_BUDGET, MAX_TOOLCALL_ATTEMPTS) == (2, 3)


def test_a_valid_first_call_is_executed_with_no_retry() -> None:
    result, client, engine = _run(VALID)
    assert len(client.calls) == 1
    assert engine.executed == [result.executed_call]
    assert result.executed_call is not None and result.executed_call.tool == "attack"
    assert result.result is result.validation[-1] and result.result["ok"] is True
    assert (result.turn_failure, result.narration_only) == (None, False)
    assert [m["role"] for m in client.calls[0][0]] == ["system", "user"]
    assert all(phase == "toolcall" and seed == SEED for _, phase, seed in client.calls)


# --- mode 1: unparseable output ---


def test_unparseable_output_is_retried_with_the_format_and_one_example() -> None:
    result, client, _ = _run(UNPARSEABLE, VALID)
    assert result.executed_call is not None and result.turn_failure is None
    assert result.proposed_calls[0] is None
    parse_failure = {"ok": False, "failure": "unparseable", "message": EXPECTED_FORMAT}
    assert result.validation[0] == parse_failure
    feedback = client.feedback(2)
    assert EXPECTED_FORMAT in feedback
    example = json.loads(feedback.splitlines()[3])
    assert example["arguments"]["actor_id"] == "pc_lyra"  # the state's PC, never an unknown id


def test_unparseable_output_three_times_is_a_turn_failure() -> None:
    result, client, engine = _run(UNPARSEABLE, UNPARSEABLE, UNPARSEABLE, VALID)
    assert len(client.calls) == 3, "the fourth reply must never be requested"
    assert result.turn_failure == "unparseable"
    assert result.executed_call is None and engine.executed == []
    assert result.proposed_calls == (None, None, None)


# --- mode 2: SCHEMA_VIOLATION ---


def test_schema_violation_is_retried_with_the_field_and_its_type() -> None:
    result, client, _ = _run(SCHEMA, VALID)
    assert result.executed_call is not None
    rejection = _rejection_in(client.feedback(2))
    assert rejection == result.validation[0]
    assert rejection["rejection_code"] == "SCHEMA_VIOLATION"
    assert "arguments must be an object with actor_id" in rejection["message"]
    assert rejection["valid_options"] == {"arguments": ["actor_id"]}


def test_schema_violation_three_times_is_a_turn_failure() -> None:
    result, client, _ = _run(SCHEMA, SCHEMA, SCHEMA, VALID)
    assert len(client.calls) == 3 and result.turn_failure == "schema"


# --- mode 3: UNKNOWN_ENTITY ---


def test_unknown_entity_is_retried_with_valid_options() -> None:
    result, client, _ = _run(UNKNOWN, VALID)
    assert result.executed_call is not None
    rejection = _rejection_in(client.feedback(2))
    assert rejection["rejection_code"] == "UNKNOWN_ENTITY"
    assert "npc_goblin_01" in rejection["message"]
    assert rejection["valid_options"]["target_id"]


def test_unknown_entity_three_times_is_a_turn_failure() -> None:
    result, client, _ = _run(UNKNOWN, UNKNOWN, UNKNOWN)
    assert len(client.calls) == 3 and result.turn_failure == "unknown_entity"


# --- mode 4: state precondition ---


def test_precondition_is_retried_with_the_reason_and_valid_options() -> None:
    result, client, _ = _run(PRECONDITION, VALID)
    assert result.executed_call is not None
    rejection = _rejection_in(client.feedback(2))
    assert rejection["rejection_code"] == "NOT_A_WEAPON"
    assert "item_torch" in rejection["message"]
    assert rejection["valid_options"] == {"weapon_id": ["item_short_sword"]}


def test_the_rejected_turn_example_ends_in_a_precondition_failure() -> None:
    # schemas/examples/audit_turn_rejected.json: NOT_A_WEAPON, unparseable, NOT_A_WEAPON.
    state = _state()
    before = state_hash(state)
    result, client, _ = _run(PRECONDITION, UNPARSEABLE, PRECONDITION, state=state)
    assert len(client.calls) == 3 and result.turn_failure == "precondition"
    assert [v.get("rejection_code") for v in result.validation] == [
        "NOT_A_WEAPON",
        None,
        "NOT_A_WEAPON",
    ]
    assert state_hash(state) == before, "a failed tool phase changed the state"


@pytest.mark.parametrize(
    ("last", "kind"),
    [
        ("unparseable", "unparseable"),
        ("schema", "schema"),
        ("unknown_entity", "unknown_entity"),
        ("precondition", "precondition"),
    ],
)
def test_the_last_attempt_names_the_turn_failure(last: str, kind: str) -> None:
    result, _, _ = _run(PRECONDITION, SCHEMA, REPLIES[last])
    assert result.turn_failure == kind == turn_failure_kind(result.validation[-1])


# --- mode 5: no tool call ---


def test_a_null_reply_is_re_prompted_to_select_a_tool() -> None:
    result, client, _ = _run(NULL, VALID)
    assert result.executed_call is not None and not result.narration_only
    assert result.validation[0] == {"ok": True, "tool": None}
    assert client.feedback(2) == TEXTS["retry_no_tool"]


def test_a_second_null_reply_ends_the_phase_narration_only() -> None:
    result, client, engine = _run(NULL, NULL, VALID)
    assert len(client.calls) == 2
    assert (result.narration_only, result.turn_failure, result.executed_call) == (True, None, None)
    assert engine.executed == []


@pytest.mark.parametrize(
    "replies",
    [
        (PRECONDITION, NULL, NULL),
        (NULL, PRECONDITION, NULL),
        (PRECONDITION, SCHEMA, NULL),
    ],
)
def test_a_null_reply_is_re_prompted_at_most_once(replies: tuple[str, ...]) -> None:
    result, client, _ = _run(*replies)
    assert len(client.calls) == 3
    assert (result.narration_only, result.turn_failure) == (True, None)
    no_tool = [m for m in client.calls[-1][0] if m["content"] == TEXTS["retry_no_tool"]]
    assert len(no_tool) <= 1


# --- retry messages ---


def test_retries_append_each_reply_and_its_error_to_the_first_prompt() -> None:
    _, client, _ = _run(PRECONDITION, UNPARSEABLE, VALID)
    first, second, third = (messages for messages, _, _ in client.calls)
    assert second[:2] == first and third[:4] == second
    assert [m["role"] for m in third] == ["system", "user", *["assistant", "user"] * 2]
    assert (second[2]["content"], third[4]["content"]) == (PRECONDITION, UNPARSEABLE)
    assert third[5]["content"] == client.feedback(3)
    assert EXPECTED_FORMAT in client.feedback(3)


def test_a_retry_that_would_overflow_drops_the_oldest_turns() -> None:
    first = prompt.assemble(
        TEXTS,
        "d_toolcall",
        player_input=PLAYER_INPUT,
        history=TURNS[:K],
        summary=SUMMARY,
        k=K,
        budget=10**6,
        state=_state(),
    )
    reply_cap = build_options(CONFIG, "toolcall", 0)["num_predict"]
    tight = CONFIG.model_copy(update={"context_tokens": first.estimated_tokens + reply_cap})
    result, client, _ = _run(PRECONDITION, VALID, config=tight)
    assert client.calls[0][0] == first.messages
    assert 0 < result.k_used < K
    retry_system = client.calls[1][0][0]["content"]
    assert TURNS[0].narration not in retry_system and TURNS[K - 1].narration in retry_system


# --- the audit record ---


@pytest.mark.parametrize(
    "replies",
    [
        (VALID,),
        (NULL, NULL),
        (PRECONDITION, UNPARSEABLE, PRECONDITION),
        (SCHEMA, UNKNOWN, VALID),
    ],
)
def test_the_phase_fields_validate_against_the_audit_schema(replies: tuple[str, ...]) -> None:
    result, _, _ = _run(*replies)
    _validator("properties/model_calls").validate(list(result.model_calls))
    _validator("properties/proposed_calls").validate(list(result.proposed_calls))
    _validator("properties/validation").validate(list(result.validation))
    if result.executed_call is not None:
        _validator("$defs/executed_call").validate(result.executed_call.model_dump(mode="json"))
    assert [c["attempt"] for c in result.model_calls] == list(range(1, len(replies) + 1))


# --- CONTROL: the loop always stops ---


@settings(max_examples=200, deadline=None)
@given(st.lists(st.sampled_from(sorted(REPLIES)), min_size=MAX_TOOLCALL_ATTEMPTS, max_size=6))
def test_any_reply_sequence_stops_within_the_budget(kinds: list[str]) -> None:
    state = _state()
    before = state_hash(state)
    result, client, engine = _run(*(REPLIES[k] for k in kinds), state=state)

    n = len(client.calls)
    assert 1 <= n <= MAX_TOOLCALL_ATTEMPTS
    assert len(result.model_calls) == len(result.proposed_calls) == len(result.validation) == n
    assert len(engine.executed) <= 1
    if engine.executed:
        assert kinds[n - 1] == "valid" and "valid" not in kinds[: n - 1]
        assert result.executed_call == engine.executed[0]
    else:
        assert state_hash(state) == before
    outcomes = [result.executed_call is not None, result.narration_only, result.turn_failure]
    assert sum(bool(o) for o in outcomes) == 1, "exactly one way out of the phase"
    if result.turn_failure is not None:
        assert n == MAX_TOOLCALL_ATTEMPTS and kinds[n - 1] == result.turn_failure
    no_tool = [m for m in client.calls[-1][0] if m["content"] == TEXTS["retry_no_tool"]]
    assert len(no_tool) <= 1
