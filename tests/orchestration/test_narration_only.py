"""Condition A, B and C harnesses (WBS 7.1 to 7.3): the narration-only runner.

Condition A runs a scenario end to end, the done-when of #77. Each scripted
input gets one narration call on template `a`, with no state, no tool
definitions and no tool phase. Condition B (the done-when of #79) injects the
input's ground-truth state exactly as condition D's tool-call prompt injects a
state: everything up to `</state>` is byte-identical for the same state, and B
differs from A only by that block. Condition C (the done-when of #80) differs
from B only by the self-check instruction at the end of its system message.
Every turn is logged and passes the audit
schema and its section 3 rules. The record's state hashes and turn number are
the replay's ground truth (CLAUDE.md section 9). K, the history, the rolling
summary and the safety filter work as in condition D (invariant 7). Two runs of
one seed are identical apart from the timings (invariant 4).

No test calls a model: a fake client answers each phase and keeps every request.

Run: pytest tests/orchestration/test_narration_only.py -v
"""

import json
from collections.abc import Sequence
from pathlib import Path

import pytest

from adm.engine.audit import read_log
from adm.engine.replay import log_differences, replay_script
from adm.engine.scenario import Scenario, load_scenario
from adm.engine.state import GameState, data_hash
from adm.orchestration import prompt
from adm.orchestration.client import Message, ModelReply, Phase, load_model_config
from adm.orchestration.narration_only import (
    NarrationOnlySession,
    NarrationOnlyStart,
    NotScripted,
)
from adm.orchestration.prompt import Doc
from adm.orchestration.session import new_run_log, run_script

ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = sorted((ROOT / "scenarios").glob("*.json"))
CELLAR = load_scenario(ROOT / "scenarios" / "s01_cellar.json")
TEXTS = prompt.load_templates()
CONFIG = load_model_config()
K = CONFIG.K_verbatim_turns
SEED = 12345

NARRATION = "Water laps at the barrels as you peer into the dark."
UNSAFE = "The rat shrieks. A voice whispers of suicide in the dark. You stand firm."
SUMMARY = "Lyra searched the cellar for the Keeper's ledger."


class NarratingClient:
    """Answers every narration with `narration` and every summary with SUMMARY.
    A toolcall request fails the test. Keeps every request."""

    def __init__(self, narration: str = NARRATION) -> None:
        self.narration = narration
        self.calls: list[tuple[tuple[Message, ...], Phase, int]] = []

    def chat(self, messages: Sequence[Message], *, phase: Phase, seed: int) -> ModelReply:
        assert phase != "toolcall", "conditions A to C have no tool phase"
        self.calls.append((tuple(messages), phase, seed))
        reply = SUMMARY if phase == "summary" else self.narration
        return ModelReply(reply, 3000, 40, 0, 0, "stop", 0)

    def narration_prompts(self) -> list[tuple[Message, ...]]:
        return [m for m, phase, _ in self.calls if phase == "narration"]


def _harness(
    runs: Path,
    scenario: Scenario = CELLAR,
    client: NarratingClient | None = None,
    template: str = "a",
    **config: int,
) -> NarrationOnlySession:
    log = new_run_log(runs, template.upper(), scenario.scenario_id, SEED)
    model = CONFIG.model_copy(update=config) if config else CONFIG
    return NarrationOnlyStart(template)(
        client or NarratingClient(), model, TEXTS, scenario, log, seed=SEED
    )


@pytest.mark.parametrize("template", ["a", "b", "c"])
@pytest.mark.parametrize("path", SCENARIOS, ids=[p.stem for p in SCENARIOS])
def test_the_condition_runs_a_scenario_end_to_end(
    tmp_path: Path, path: Path, template: str
) -> None:
    scenario = load_scenario(path)
    condition = template.upper()
    harness = _harness(tmp_path, scenario, template=template)
    turns = run_script(harness)

    # AuditLog.append refuses a record that breaks the schema or its rules.
    records = read_log(harness.log.path)
    inputs = scenario.scripted_inputs
    assert [t.record for t in turns] == records
    assert harness.log.path == tmp_path / condition / scenario.scenario_id / f"{SEED}.jsonl"
    assert [r["input_index"] for r in records] == list(range(len(inputs)))
    assert [r["player_input"] for r in records] == [i.text for i in inputs]
    for record in records:
        assert record["condition"] == condition
        assert record["run_id"] == f"{condition}_{scenario.scenario_id}_{SEED}"
        assert [c["phase"] for c in record["model_calls"]][0] == "narration"
        assert record["narration"] == NARRATION
        assert record["proposed_calls"] == record["validation"] == record["engine_steps"] == []
        assert record["executed_call"] is None and record["turn_failure"] is None
    # One narration call per input, and nothing else but the summaries.
    client = harness.client
    assert isinstance(client, NarratingClient)
    assert len(client.narration_prompts()) == len(inputs)
    assert {seed for _, _, seed in client.calls} == {SEED}
    # A injects no state; B injects each input's ground truth, the hashed state.
    truth = replay_script(scenario, SEED)
    for messages, record, ground in zip(client.narration_prompts(), records, truth, strict=True):
        system = messages[0]["content"]
        if template == "a":
            assert "<state>" not in system
        else:
            injected = _injected(system)
            assert injected == ground.state
            assert data_hash(injected) == record["state_after_hash"]


@pytest.mark.parametrize("template", ["a", "b", "c"])
def test_the_state_hashes_and_turn_numbers_are_the_replays(tmp_path: Path, template: str) -> None:
    harness = _harness(tmp_path, template=template)
    run_script(harness)
    truth = replay_script(CELLAR, SEED)
    for record, turn in zip(read_log(harness.log.path), truth, strict=True):
        assert record["state_before_hash"] == record["state_after_hash"] == turn.state_after_hash
        assert record["turn_number"] == turn.turn_number
        assert record["state_diff"] == [] and record["rolls"] == []
    # A rejected expected call repeats the turn number, as an oracle D run does.
    assert any(t.turn_failure for t in truth)
    numbers = [t.turn_number for t in truth]
    assert len(set(numbers)) < len(numbers)


def test_the_prompt_holds_no_state_and_no_tools(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    looking = CELLAR.scripted_inputs[0]
    harness.play(looking.text, input_index=0, scripted=looking)

    assert isinstance(harness.client, NarratingClient)
    (messages,) = harness.client.narration_prompts()
    system, user = messages
    assert system == {"role": "system", "content": TEXTS["a"].split("\n\n{summary}")[0]}
    assert user == {"role": "user", "content": looking.text}
    for leaked in ("<state>", "pc_lyra", "current_hp", "attack_bonus", '"tool"'):
        assert leaked not in system["content"]


def test_history_and_summary_follow_condition_ds_strategy(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    turns = run_script(harness)
    records = [t.record for t in turns]

    regenerated = [i for i, r in enumerate(records) if r["summary_regenerated"]]
    assert regenerated == [i for i in range(len(records)) if (i + 1) % K == 0]
    assert all(
        r["summary"] == {"text": SUMMARY, "truncated": False} for r in records if r["summary"]
    )
    assert all(r["k_used"] == min(K, i) for i, r in enumerate(records))
    # Input K+1 sees the summary and exactly the last K turns, oldest first.
    assert isinstance(harness.client, NarratingClient)
    system = harness.client.narration_prompts()[K + 1][0]["content"]
    assert f"<summary>\n{SUMMARY}\n</summary>" in system
    transcript = system.split("<history>\n")[1].split("\n</history>")[0]
    inputs = CELLAR.scripted_inputs
    expected = [f"Player: {s.text}\nDM: {NARRATION}" for s in inputs[1 : K + 1]]
    assert transcript == "\n\n".join(expected)


def test_k_is_reduced_and_logged_when_the_prompt_does_not_fit(tmp_path: Path) -> None:
    # A window just big enough for the bare prompt and a few turns. The turns
    # stop before the first summary, whose prompt would not fit either.
    harness = _harness(tmp_path, context_tokens=CONFIG.narration_max_tokens + 250)
    used = [
        harness.play(s.text, input_index=i, scripted=s).record["k_used"]
        for i, s in enumerate(CELLAR.scripted_inputs[: K - 1])
    ]
    assert used[0] == 0
    assert used[-1] < K - 2, used


def test_the_safety_filter_runs_as_in_condition_d(tmp_path: Path) -> None:
    harness = _harness(tmp_path, client=NarratingClient(UNSAFE))
    looking = CELLAR.scripted_inputs[0]
    turn = harness.play(looking.text, input_index=0, scripted=looking)
    assert turn.record["narration"] == turn.message == "The rat shrieks. You stand firm."
    assert turn.record["narration_filtered"] is True
    assert turn.record["model_calls"][0]["raw_output"] == UNSAFE
    assert harness.history[-1].narration == turn.message


def test_a_turn_without_its_input_index_is_refused(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    with pytest.raises(NotScripted):
        harness.play("I look around")
    assert not harness.log.path.exists()


def test_two_runs_of_one_seed_are_identical_apart_from_the_timings(tmp_path: Path) -> None:
    first = _harness(tmp_path / "first")
    second = _harness(tmp_path / "second")
    run_script(first)
    run_script(second)
    assert log_differences(read_log(first.log.path), read_log(second.log.path)) == []


def test_only_the_narration_only_templates_start_a_harness() -> None:
    with pytest.raises(ValueError):
        NarrationOnlyStart("d_narration")


# --- condition B (WBS 7.2): state injected identically to condition D --------

PREAMBLE = TEXTS["a"].split("\n\n{summary}")[0]
STATE_END = "\n</state>"


def _state_end(system: str) -> int:
    """Where the state block ends: just after `</state>`."""
    return system.index(STATE_END) + len(STATE_END)


def _injected(system: str) -> Doc:
    return json.loads(system.split("<state>\n")[1].split(STATE_END)[0])


def _b_prompts(runs: Path, scenario: Scenario = CELLAR) -> tuple[NarrationOnlySession, list]:
    harness = _harness(runs, scenario, template="b")
    run_script(harness)
    assert isinstance(harness.client, NarratingClient)
    return harness, harness.client.narration_prompts()


def test_b_injects_the_state_byte_for_byte_as_condition_ds_tool_call(tmp_path: Path) -> None:
    """The done-when of #79: given the same state, B's prompt and D's tool-call
    prompt are identical from the first byte to `</state>`: the same preamble,
    lead-in, serialisation and place."""
    _, prompts = _b_prompts(tmp_path)
    budget = prompt.prompt_budget(CONFIG, "toolcall")
    for messages, ground in zip(prompts, replay_script(CELLAR, SEED), strict=True):
        state = GameState.from_dict(ground.state)
        b_system = messages[0]["content"]
        d_system = prompt.assemble(
            TEXTS,
            "d_toolcall",
            player_input=messages[1]["content"],
            history=[],
            summary=None,
            k=0,
            budget=budget,
            state=state,
        ).messages[0]["content"]
        assert b_system[: _state_end(b_system)] == d_system[: _state_end(d_system)]
        assert f"<state>\n{prompt.state_json(state)}{STATE_END}" in b_system
        assert "<tools>" not in b_system and '"tool"' not in b_system


def test_b_differs_from_a_only_by_the_state_block(tmp_path: Path) -> None:
    a = _harness(tmp_path, template="a")
    run_script(a)
    b, b_prompts = _b_prompts(tmp_path)
    assert isinstance(a.client, NarratingClient)
    a_prompts = a.client.narration_prompts()
    assert len(a_prompts) == len(b_prompts) == len(CELLAR.scripted_inputs)
    for a_messages, b_messages in zip(a_prompts, b_prompts, strict=True):
        b_system = b_messages[0]["content"]
        assert b_system.startswith(PREAMBLE + "\n\nThe authoritative game state")
        without_state = PREAMBLE + b_system[_state_end(b_system) :]
        assert without_state == a_messages[0]["content"]
        assert b_messages[1] == a_messages[1]
    # The same narrations, so the same records apart from the condition and timings.
    a_records, b_records = read_log(a.log.path), read_log(b.log.path)
    for record in (*a_records, *b_records):
        record.update(condition="-", run_id="-")
    assert log_differences(a_records, b_records) == []


# --- condition C (WBS 7.3): B plus the self-check instruction ----------------

SELF_CHECK = TEXTS["c"].removeprefix(TEXTS["b"] + "\n\n")


def test_c_differs_from_b_only_by_the_self_check_instruction(tmp_path: Path) -> None:
    """The done-when of #80: for every input, C's narration prompt is B's with
    the self-check instruction after the history, and nothing else differs: the
    same state, summary, history and input, the same summary prompts, and the
    same records apart from the condition and timings."""
    assert TEXTS["c"] == TEXTS["b"] + "\n\n" + SELF_CHECK
    assert SELF_CHECK.startswith("Before you reply, check your narration against the state")
    b = _harness(tmp_path, template="b")
    c = _harness(tmp_path, template="c")
    run_script(b)
    run_script(c)

    assert isinstance(b.client, NarratingClient) and isinstance(c.client, NarratingClient)
    assert [phase for _, phase, _ in b.client.calls] == [phase for _, phase, _ in c.client.calls]
    narrated = 0
    for (b_messages, phase, _), (c_messages, _, _) in zip(
        b.client.calls, c.client.calls, strict=True
    ):
        if phase == "narration":
            narrated += 1
            b_system, c_system = b_messages[0]["content"], c_messages[0]["content"]
            assert c_system == b_system + "\n\n" + SELF_CHECK
            assert c_messages[1:] == b_messages[1:]
        else:
            assert c_messages == b_messages
    assert narrated == len(CELLAR.scripted_inputs)

    b_records, c_records = read_log(b.log.path), read_log(c.log.path)
    for record in (*b_records, *c_records):
        record.update(condition="-", run_id="-")
    assert log_differences(b_records, c_records) == []
