"""Failure pipeline (WBS 6.4): each of the five CLAUDE.md section 7.1 modes is
retried with a structured error and recovers within the budget, the budget of
two retries is never exceeded, and exhausting it ends the phase in a named
`turn_failure` (the done-when of #63, a CONTROL artefact).

Exhausted-budget fallback (WBS 6.5): a failed turn is written to the audit log,
does not advance, and is counted (the done-when of #64).

Narration call (WBS 6.6): the narration prompt carries the turn's
`narration_facts`, every number in them, in the order things happened, and no
state; the narrated turn is written to the audit log (the done-when of #65).

No test calls a model: a fake client returns recorded replies.

Run: pytest tests/orchestration/test_loop.py -v
"""

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from adm.bench import context as bench
from adm.engine.audit import (
    AuditLog,
    InvalidRecord,
    apply_diff,
    filtered_turn_count,
    turn_failure_counts,
)
from adm.engine.combat import attack, dodge, start_encounter
from adm.engine.dice import DiceRoller
from adm.engine.npc import NpcActionStep
from adm.engine.state import GameState, data_hash, load_state, state_hash
from adm.engine.tools import after_call, increment_turn, open_encounter
from adm.engine.validator import ToolCall
from adm.orchestration import prompt
from adm.orchestration.client import Message, ModelReply, Phase, build_options, load_model_config
from adm.orchestration.loop import (
    MAX_TOOLCALL_ATTEMPTS,
    REPHRASE,
    RETRY_BUDGET,
    ToolPhase,
    TurnTimer,
    fail_turn,
    narrate,
    narrate_turn,
    run_tool_phase,
    turn_facts,
    turn_failure_kind,
)
from adm.orchestration.parser import EXPECTED_FORMAT
from adm.orchestration.prompt import HistoryTurn
from adm.orchestration.safety import FALLBACK

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


# --- exhausted budget: the failed turn (WBS 6.5) ---

FAILURE_KINDS = ["unparseable", "schema", "unknown_entity", "precondition"]
REJECTED_EXAMPLE = json.loads((EXAMPLES / "audit_turn_rejected.json").read_text("utf-8"))


class FakeClock:
    """Ten seconds pass between readings."""

    def __init__(self) -> None:
        self.t = 100.0

    def __call__(self) -> float:
        self.t += 10.0
        return self.t


def _timer() -> TurnTimer:
    return TurnTimer(clock=FakeClock(), now=lambda: datetime(2026, 11, 9, 14, 22, 31, tzinfo=UTC))


def _log(tmp_path: Path, state: GameState) -> AuditLog:
    return AuditLog(tmp_path, "D", state.scenario_id, state.seed)


def _fail(
    log: AuditLog,
    state: GameState,
    *replies: str,
    before: Doc | None = None,
    steps: Sequence[Any] = (),
    input_index: int | None = 7,
) -> Any:
    before = state.to_dict() if before is None else before
    phase, _, _ = _run(*replies, state=state)
    return fail_turn(
        log,
        state,
        before,
        steps,
        phase,
        input_index=input_index,
        player_input=PLAYER_INPUT,
        timer=_timer(),
    )


@pytest.mark.parametrize("kind", FAILURE_KINDS)
def test_an_exhausted_budget_is_logged_and_the_turn_does_not_advance(
    kind: str, tmp_path: Path
) -> None:
    state = _state()
    before = state.to_dict()
    log = _log(tmp_path, state)
    failed = _fail(log, state, *[REPLIES[kind]] * MAX_TOOLCALL_ATTEMPTS)

    record = failed.record
    assert log.records() == [record], "the failed turn must be in the audit log"
    assert record["turn_failure"] == kind
    assert state.to_dict() == before, "a failed turn changed the state"
    assert record["turn_number"] == state.turn_number + 1, "the next turn repeats this number"
    assert record["engine_steps"] == record["state_diff"] == record["rolls"] == []
    assert [c["phase"] for c in record["model_calls"]] == ["toolcall"] * MAX_TOOLCALL_ATTEMPTS
    assert record["narration"] == failed.message == REPHRASE
    assert failed.carried_facts == ()
    assert (record["timestamp"], record["turn_latency_ms"]) == ("2026-11-09T14:22:31Z", 10_000)


def test_the_failed_record_matches_the_rejected_example(tmp_path: Path) -> None:
    # schemas/examples/audit_turn_rejected.json: NOT_A_WEAPON, unparseable, NOT_A_WEAPON.
    state = _state()
    record = _fail(_log(tmp_path, state), state, PRECONDITION, UNPARSEABLE, PRECONDITION).record
    assert record.keys() == REJECTED_EXAMPLE.keys()
    same = [
        "run_id",
        "turn_number",
        "input_index",
        "executed_call",
        "engine_steps",
        "state_before_hash",
        "state_after_hash",
        "narration",
        "turn_failure",
        "narration_only",
    ]
    assert {k: record[k] for k in same} == {k: REJECTED_EXAMPLE[k] for k in same}


def test_failed_scripted_turns_repeat_the_turn_number_and_are_counted(tmp_path: Path) -> None:
    # A scripted run moves on to the next input after a failed turn (CLAUDE.md 7.1).
    state = _state()
    log = _log(tmp_path, state)
    _fail(log, state, PRECONDITION, SCHEMA, PRECONDITION, input_index=7)
    _fail(log, state, UNPARSEABLE, UNPARSEABLE, UNPARSEABLE, input_index=8)
    records = log.records()
    assert [r["input_index"] for r in records] == [7, 8]
    assert [r["turn_number"] for r in records] == [state.turn_number + 1] * 2
    assert turn_failure_counts(records) == {"precondition": 1, "unparseable": 1}


def _seed_where_an_npc_goes_first(state: GameState) -> int:
    for seed in range(1000):
        trial = state.model_copy(deep=True)
        start_encounter(trial, DiceRoller(seed), ["pc_lyra", "npc_rat_01", "npc_rat_02"])
        if trial.active_combatant_id != "pc_lyra":
            return seed
    raise AssertionError("no seed found")


def test_a_failed_turn_keeps_the_encounter_that_started_before_it(tmp_path: Path) -> None:
    state = load_state(EXAMPLES / "state_01_exploration.json")
    before = state.to_dict()
    roller = DiceRoller(_seed_where_an_npc_goes_first(state))
    steps = open_encounter(state, roller, ["pc_lyra", "npc_rat_01", "npc_rat_02"])
    npc_facts = [s.result["narration_facts"] for s in steps if isinstance(s, NpcActionStep)]
    assert npc_facts, "the seed should let an NPC act before the PC"

    failed = _fail(_log(tmp_path, state), state, *[UNPARSEABLE] * 3, before=before, steps=steps)

    record = failed.record
    assert {s["when"] for s in record["engine_steps"]} == {"before_call"}
    assert data_hash(apply_diff(before, record["state_diff"])) == record["state_after_hash"]
    assert list(failed.carried_facts) == npc_facts, "NPC facts go to the next narrated turn"
    assert state.active_combatant_id == "pc_lyra", "initiative stays with the player"
    assert state.turn_number == before["turn_number"]
    assert record["turn_number"] == state.turn_number + 1


def test_only_an_exhausted_budget_is_a_failed_turn(tmp_path: Path) -> None:
    state = _state()
    with pytest.raises(ValueError, match="exhausted"):
        _fail(_log(tmp_path, state), state, PRECONDITION, VALID)


def test_a_failed_turn_cannot_run_steps_after_the_call(tmp_path: Path) -> None:
    state = _state()
    before = state.to_dict()
    log = _log(tmp_path, state)
    steps = [increment_turn(state)]
    with pytest.raises(InvalidRecord, match="after_call"):
        _fail(log, state, *[PRECONDITION] * 3, before=before, steps=steps)
    assert not log.path.exists()


# --- the narrated turn (WBS 6.6) ---

NARRATION = "\nYour blade bites into the rat's flank, and it shrieks and drags itself back.\n"
SUMMARY_REPLY = "Lyra fought the rats in the flooded cellar. The ledger is still missing."
VALID_EXAMPLE = json.loads((EXAMPLES / "audit_turn_valid.json").read_text("utf-8"))


def _play(
    log: AuditLog,
    state: GameState,
    *replies: str,
    before: Doc | None = None,
    steps: Sequence[Any] = (),
    carried: Sequence[Doc] = (),
    fold: Sequence[HistoryTurn] | None = None,
    config: Any = CONFIG,
    narration: str = NARRATION,
) -> tuple[Any, FakeClient, ToolPhase]:
    """Play the tool phase on `replies`, the engine steps after it, and the
    narrated turn; `steps` are the before-call steps of an encounter."""
    before = state.to_dict() if before is None else before
    phase, _, engine = _run(*replies, state=state, config=config)
    steps = list(steps)
    if phase.executed_call is not None:
        steps += after_call(state, engine.roller, phase.executed_call.tool)
    steps.append(increment_turn(state))
    client = FakeClient(narration, SUMMARY_REPLY)
    turn = narrate_turn(
        log,
        client,
        config,
        TEXTS,
        state,
        before,
        steps,
        phase,
        carried_facts=carried,
        input_index=7,
        player_input=PLAYER_INPUT,
        history=TURNS[:K],
        summary=SUMMARY,
        seed=SEED,
        timer=_timer(),
        fold=fold,
    )
    return turn, client, phase


def _facts_in(system: str) -> list[Doc]:
    """The array a narration prompt's `<facts>` block holds."""
    return json.loads(system.split("<facts>\n")[1].split("\n</facts>")[0])


def _npc_facts(steps: Sequence[Doc], when: str) -> list[Doc]:
    """The facts of a record's `npc_action` steps at `when`."""
    return [
        s["result"]["narration_facts"]
        for s in steps
        if s["step"] == "npc_action" and s["when"] == when
    ]


def test_the_narration_call_receives_the_numbers_and_no_state(tmp_path: Path) -> None:
    state = _state()
    turn, client, phase = _play(_log(tmp_path, state), state, VALID)
    (messages, call_phase, seed), *_ = client.calls
    system = messages[0]["content"]

    assert (call_phase, seed) == ("narration", SEED)
    assert build_options(CONFIG, call_phase, seed)["temperature"] == CONFIG.temperature
    assert [m["role"] for m in messages] == ["system", "user"]
    assert messages[1]["content"] == PLAYER_INPUT
    assert "<state>" not in system and '"combatants"' not in system
    facts = _facts_in(system)
    assert facts == list(turn.narration.facts)
    player = facts[0]
    assert player == phase.result["narration_facts"]
    for key in ("attack_roll", "damage", "target_hp_before", "target_hp_after", "target_hp_band"):
        assert f'"{key}": {json.dumps(player[key])}' in system, f"{key} is not in the prompt"


def test_the_narrated_turn_is_logged_and_advances(tmp_path: Path) -> None:
    state = _state()
    before = state.to_dict()
    log = _log(tmp_path, state)
    turn, _, _ = _play(log, state, VALID)

    record = turn.record
    assert log.records() == [record]
    assert record.keys() == VALID_EXAMPLE.keys()
    assert [c["phase"] for c in record["model_calls"]] == ["toolcall", "narration"]
    assert record["model_calls"][-1]["raw_output"] == NARRATION
    assert record["narration"] == turn.message == NARRATION.strip()
    assert (record["narration_filtered"], record["narration_only"]) == (False, False)
    assert record["turn_failure"] is None
    assert record["turn_number"] == before["turn_number"] + 1 == state.turn_number
    assert (record["summary_regenerated"], record["summary"]) == (False, None)


def _open(state: GameState) -> list[Any]:
    """Start the rat encounter with a seed where an NPC acts before the PC."""
    roller = DiceRoller(_seed_where_an_npc_goes_first(state))
    return open_encounter(state, roller, ["pc_lyra", "npc_rat_01", "npc_rat_02"])


def test_the_facts_follow_the_order_of_the_turn(tmp_path: Path) -> None:
    state = load_state(EXAMPLES / "state_01_exploration.json")
    before = state.to_dict()
    opening = _open(state)
    turn, client, phase = _play(_log(tmp_path, state), state, VALID, before=before, steps=opening)

    steps = turn.record["engine_steps"]
    first, after = _npc_facts(steps, "before_call"), _npc_facts(steps, "after_call")
    assert first and after, "NPCs should act both before and after the player"
    expected = [*first, phase.result["narration_facts"], *after]
    assert _facts_in(client.calls[0][0][0]["content"]) == expected


def test_facts_carried_from_a_failed_turn_come_first(tmp_path: Path) -> None:
    state = load_state(EXAMPLES / "state_01_exploration.json")
    log = _log(tmp_path, state)
    before = state.to_dict()
    opening = _open(state)
    failed = _fail(log, state, *[UNPARSEABLE] * 3, before=before, steps=opening)
    assert failed.carried_facts

    turn, client, phase = _play(log, state, VALID, carried=failed.carried_facts)
    carried = list(failed.carried_facts)
    facts = _facts_in(client.calls[0][0][0]["content"])
    assert facts[: len(carried)] == carried
    assert facts[len(carried)] == phase.result["narration_facts"]
    numbers = [r["turn_number"] for r in log.records()]
    assert numbers == [before["turn_number"] + 1] * 2, "the failed turn's number repeats"


def test_a_narration_only_turn_is_narrated_with_no_facts(tmp_path: Path) -> None:
    state = _state()
    log = _log(tmp_path, state)
    turn, client, phase = _play(log, state, NULL, NULL)

    assert phase.narration_only and phase.result is None
    assert "<facts>\n[]\n</facts>" in client.calls[0][0][0]["content"]
    assert turn.narration.facts == ()
    assert log.records() == [turn.record] and turn.record["narration_only"] is True


def test_turn_facts_without_a_call_or_steps_are_empty() -> None:
    assert turn_facts([], None) == []


def test_the_narration_call_uses_the_turns_k(tmp_path: Path) -> None:
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
    state = _state()
    turn, client, phase = _play(_log(tmp_path, state), state, PRECONDITION, VALID, config=tight)

    assert 0 < phase.k_used < K and turn.record["k_used"] == phase.k_used
    system = client.calls[0][0][0]["content"]
    oldest = K - phase.k_used
    assert TURNS[oldest].narration in system and TURNS[oldest - 1].narration not in system


def test_a_narration_prompt_that_would_need_a_smaller_k_raises() -> None:
    facts = [json.loads((EXAMPLES / "result_attack.json").read_text("utf-8"))["narration_facts"]]
    full = prompt.assemble(
        TEXTS,
        "d_narration",
        player_input=PLAYER_INPUT,
        history=TURNS[:K],
        summary=SUMMARY,
        k=K,
        budget=10**6,
        facts=facts,
    )
    reply_cap = build_options(CONFIG, "narration", 0)["num_predict"]
    tight = CONFIG.model_copy(update={"context_tokens": full.estimated_tokens - 1 + reply_cap})
    client = FakeClient(NARRATION)
    with pytest.raises(prompt.PromptTooLarge, match="narration"):
        narrate(
            client,
            tight,
            TEXTS,
            facts=facts,
            player_input=PLAYER_INPUT,
            history=TURNS[:K],
            summary=SUMMARY,
            k=K,
            seed=SEED,
        )
    assert client.calls == []


def test_a_due_summary_folds_in_this_turns_narration(tmp_path: Path) -> None:
    state = _state()
    turn, client, _ = _play(_log(tmp_path, state), state, VALID, fold=TURNS[: K - 1])

    assert [phase for _, phase, _ in client.calls] == ["narration", "summary"]
    summary_system = client.calls[1][0][0]["content"]
    assert f"DM: {NARRATION.strip()}" in summary_system and SUMMARY in summary_system
    record = turn.record
    assert [c["phase"] for c in record["model_calls"]] == ["toolcall", "narration", "summary"]
    assert record["summary_regenerated"] is True
    assert record["summary"] == {"text": SUMMARY_REPLY, "truncated": False}
    assert turn.summary is not None and turn.summary.text == SUMMARY_REPLY


# --- the safety filter (WBS 6.9) ---

UNSAFE = "The rat shrieks. A voice whispers of suicide in the dark. You stand firm."


def test_a_filtered_turn_is_logged_flagged_and_counted(tmp_path: Path) -> None:
    state = _state()
    log = _log(tmp_path, state)
    turn, _, _ = _play(log, state, VALID, narration=UNSAFE)

    record = turn.record
    assert record["narration"] == turn.message == "The rat shrieks. You stand firm."
    assert record["narration_filtered"] is True
    assert record["model_calls"][-1]["raw_output"] == UNSAFE, "the reply is kept unfiltered"
    assert log.records() == [record], "a filtered turn is still logged"
    assert record["turn_number"] == state.turn_number, "and still played"
    assert filtered_turn_count(log.records()) == 1


def test_a_reply_with_nothing_safe_left_shows_the_fallback(tmp_path: Path) -> None:
    state = _state()
    turn, _, _ = _play(_log(tmp_path, state), state, VALID, narration="Talk of suicide.")
    assert turn.message == turn.record["narration"] == FALLBACK
    assert turn.record["narration_filtered"] is True


def test_the_summary_folds_in_the_filtered_narration(tmp_path: Path) -> None:
    state = _state()
    turn, client, _ = _play(
        _log(tmp_path, state), state, VALID, fold=TURNS[: K - 1], narration=UNSAFE
    )
    summary_system = client.calls[1][0][0]["content"]
    assert f"DM: {turn.message}" in summary_system
    assert "suicide" not in summary_system


def test_an_unfiltered_turn_is_not_counted(tmp_path: Path) -> None:
    state = _state()
    log = _log(tmp_path, state)
    _play(log, state, VALID)
    assert filtered_turn_count(log.records()) == 0


def test_a_failed_tool_phase_is_not_narrated(tmp_path: Path) -> None:
    state = _state()
    log = _log(tmp_path, state)
    phase, _, _ = _run(*[PRECONDITION] * 3, state=state)
    client = FakeClient(NARRATION)
    with pytest.raises(ValueError, match="fail_turn"):
        narrate_turn(
            log,
            client,
            CONFIG,
            TEXTS,
            state,
            state.to_dict(),
            [],
            phase,
            input_index=7,
            player_input=PLAYER_INPUT,
            history=TURNS[:K],
            summary=SUMMARY,
            seed=SEED,
            timer=_timer(),
        )
    assert client.calls == [] and not log.path.exists()
