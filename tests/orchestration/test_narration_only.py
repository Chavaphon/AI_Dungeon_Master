"""Condition A harness (WBS 7.1): runs a scenario end to end, the done-when of #77.

Each scripted input gets one narration call on template `a`, with no state, no
tool definitions and no tool phase. Every turn is logged and passes the audit
schema and its section 3 rules. The record's state hashes and turn number are
the replay's ground truth (CLAUDE.md section 9). K, the history, the rolling
summary and the safety filter work as in condition D (invariant 7). Two runs of
one seed are identical apart from the timings (invariant 4).

No test calls a model: a fake client answers each phase and keeps every request.

Run: pytest tests/orchestration/test_narration_only.py -v
"""

from collections.abc import Sequence
from pathlib import Path

import pytest

from adm.engine.audit import read_log
from adm.engine.replay import log_differences, replay_script
from adm.engine.scenario import Scenario, load_scenario
from adm.orchestration import prompt
from adm.orchestration.client import Message, ModelReply, Phase, load_model_config
from adm.orchestration.narration_only import (
    NarrationOnlySession,
    NarrationOnlyStart,
    NotScripted,
)
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
        assert phase != "toolcall", "condition A has no tool phase"
        self.calls.append((tuple(messages), phase, seed))
        reply = SUMMARY if phase == "summary" else self.narration
        return ModelReply(reply, 3000, 40, 0, 0, "stop", 0)

    def narration_prompts(self) -> list[tuple[Message, ...]]:
        return [m for m, phase, _ in self.calls if phase == "narration"]


def _harness(
    runs: Path, scenario: Scenario = CELLAR, client: NarratingClient | None = None, **config: int
) -> NarrationOnlySession:
    log = new_run_log(runs, "A", scenario.scenario_id, SEED)
    model = CONFIG.model_copy(update=config) if config else CONFIG
    return NarrationOnlyStart("a")(
        client or NarratingClient(), model, TEXTS, scenario, log, seed=SEED
    )


@pytest.mark.parametrize("path", SCENARIOS, ids=[p.stem for p in SCENARIOS])
def test_condition_a_runs_a_scenario_end_to_end(tmp_path: Path, path: Path) -> None:
    scenario = load_scenario(path)
    harness = _harness(tmp_path, scenario)
    turns = run_script(harness)

    # AuditLog.append refuses a record that breaks the schema or its rules.
    records = read_log(harness.log.path)
    inputs = scenario.scripted_inputs
    assert [t.record for t in turns] == records
    assert harness.log.path == tmp_path / "A" / scenario.scenario_id / f"{SEED}.jsonl"
    assert [r["input_index"] for r in records] == list(range(len(inputs)))
    assert [r["player_input"] for r in records] == [i.text for i in inputs]
    for record in records:
        assert record["condition"] == "A" and record["run_id"] == f"A_{scenario.scenario_id}_{SEED}"
        assert [c["phase"] for c in record["model_calls"]][0] == "narration"
        assert record["narration"] == NARRATION
        assert record["proposed_calls"] == record["validation"] == record["engine_steps"] == []
        assert record["executed_call"] is None and record["turn_failure"] is None
    # One narration call per input, and nothing else but the summaries.
    client = harness.client
    assert isinstance(client, NarratingClient)
    assert len(client.narration_prompts()) == len(inputs)
    assert {seed for _, _, seed in client.calls} == {SEED}


def test_the_state_hashes_and_turn_numbers_are_the_replays(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
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
