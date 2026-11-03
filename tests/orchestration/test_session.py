"""Interactive session (WBS 6.10, 7.4): a session plays the turn loop end to end on
a scenario, one input at a time. Encounters start before the player's n-th
input, failed turns included; failed turns do not advance and their NPC facts
reach the next narration; narrated turns build the history and the rolling
summary; every turn is in the audit log; and `run_script` runs any
condition's harness the same way (WBS 7.4).

No test calls a model: a fake client answers each phase from a script.

Run: pytest tests/orchestration/test_session.py -v
"""

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from adm.engine.audit import AuditLog, read_log
from adm.engine.combat import start_encounter
from adm.engine.dice import DiceRoller
from adm.engine.replay import log_differences, replay_script
from adm.engine.scenario import Scenario, ScriptedInput, initial_state, load_scenario
from adm.orchestration import prompt
from adm.orchestration.client import Message, ModelReply, Phase, load_model_config
from adm.orchestration.loop import REPHRASE, FailedTurn, NarratedTurn
from adm.orchestration.session import RunExists, Session, new_run_log, run_script

ROOT = Path(__file__).resolve().parents[2]
SCENARIO = load_scenario(ROOT / "scenarios" / "s01_cellar.json")
ENCOUNTER = SCENARIO.encounters[0]  # before input 3: pc_lyra and both rats
TEXTS = prompt.load_templates()
CONFIG = load_model_config()
K = CONFIG.K_verbatim_turns
SEED = 12345

Doc = dict[str, Any]

LOOK = json.dumps(
    {
        "tool": "skill_check",
        "arguments": {"actor_id": "pc_lyra", "skill": "perception", "dc": 12},
    }
)
NULL = json.dumps({"tool": None})
GARBLED = "I think Lyra should look around."
NARRATION = "Water laps at the barrels as you peer into the dark."
SUMMARY = "Lyra searched the cellar for the Keeper's ledger."


class ScriptedClient:
    """Answers toolcall requests from `toolcalls` in order, and every narration
    and summary request with a fixed reply. Keeps every request."""

    def __init__(self, *toolcalls: str) -> None:
        self.toolcalls = list(toolcalls)
        self.seed = SEED
        self.calls: list[tuple[tuple[Message, ...], Phase]] = []

    def chat(self, messages: Sequence[Message], *, phase: Phase, seed: int) -> ModelReply:
        assert seed == self.seed
        self.calls.append((tuple(messages), phase))
        reply = {"narration": NARRATION, "summary": SUMMARY}.get(phase)
        if reply is None:
            reply = self.toolcalls.pop(0)
        # Zero latency: the real turn_latency_ms must not be shorter than its calls.
        return ModelReply(reply, 3000, 40, 0, 0, "stop", 0)

    def phases(self) -> list[Phase]:
        return [phase for _, phase in self.calls]

    def last(self, phase: Phase) -> tuple[Message, ...]:
        return [m for m, p in self.calls if p == phase][-1]


def _session(tmp_path: Path, client: ScriptedClient, seed: int = SEED) -> Session:
    client.seed = seed
    log = new_run_log(tmp_path, "D", SCENARIO.scenario_id, seed)
    return Session.start(client, CONFIG, TEXTS, SCENARIO, log, seed=seed)


def _facts_in(system: str) -> list[Doc]:
    return json.loads(system.split("<facts>\n")[1].split("\n</facts>")[0])


def test_a_session_plays_and_logs_every_turn(tmp_path: Path) -> None:
    client = ScriptedClient(LOOK, LOOK)
    session = _session(tmp_path, client)
    turns = [session.play("I look around the cellar"), session.play("I listen for scratching")]

    assert all(isinstance(t, NarratedTurn) for t in turns)
    assert [t.message for t in turns] == [NARRATION, NARRATION]
    records = read_log(session.log.path)
    assert records == [t.record for t in turns]
    assert [r["turn_number"] for r in records] == [1, 2]
    assert [r["input_index"] for r in records] == [None, None], "interactive play"
    assert session.state.turn_number == 2
    assert client.phases() == ["toolcall", "narration"] * 2
    # The second turn's prompt holds the first turn verbatim.
    assert "I look around the cellar" in client.last("toolcall")[0]["content"]


def test_a_failed_turn_does_not_advance_or_join_the_history(tmp_path: Path) -> None:
    client = ScriptedClient(GARBLED, GARBLED, GARBLED, LOOK)
    session = _session(tmp_path, client)
    failed = session.play("mumble")
    assert isinstance(failed, FailedTurn) and failed.message == REPHRASE
    assert session.state.turn_number == 0 and session.history == []

    narrated = session.play("I look around the cellar")
    assert [r["turn_number"] for r in read_log(session.log.path)] == [1, 1]
    assert narrated.record["turn_failure"] is None
    assert "mumble" not in client.last("toolcall")[0]["content"]


def test_the_encounter_starts_before_the_inputs_index_counting_failed_turns(
    tmp_path: Path,
) -> None:
    # Input 0 fails, inputs 1 and 2 are narrated: the encounter opens on input 3,
    # which is only the third played turn.
    client = ScriptedClient(GARBLED, GARBLED, GARBLED, LOOK, LOOK, LOOK)
    session = _session(tmp_path, client)
    for text in ("mumble", "I look around", "I listen"):
        session.play(text)
    assert not session.state.encounter_active
    steps = [s["step"] for r in read_log(session.log.path) for s in r["engine_steps"]]
    assert "encounter_start" not in steps

    turn = session.play("I look for the rats")
    steps = turn.record["engine_steps"]
    assert steps[0]["step"] == "encounter_start"
    assert session.state.encounter_active
    assert set(session.state.initiative_order) == set(ENCOUNTER.combatant_ids)
    assert turn.record["turn_number"] == 3
    assert session.encounters_started == 1


def _seed_where_an_npc_goes_first() -> int:
    for seed in range(1000):
        trial = initial_state(SCENARIO, seed)
        start_encounter(trial, DiceRoller(seed), ENCOUNTER.combatant_ids)
        if trial.active_combatant_id != "pc_lyra":
            return seed
    raise AssertionError("no seed found")


def test_npc_facts_of_a_failed_turn_open_the_next_narration(tmp_path: Path) -> None:
    seed = _seed_where_an_npc_goes_first()
    client = ScriptedClient(LOOK, LOOK, LOOK, GARBLED, GARBLED, GARBLED, LOOK)
    session = _session(tmp_path, client, seed)
    for text in ("I look around", "I listen", "I wait"):
        session.play(text)
    failed = session.play("mumble")  # input 3: the rats act first, then the call fails
    assert isinstance(failed, FailedTurn) and failed.carried_facts
    assert session.state.active_combatant_id == "pc_lyra"

    narrated = session.play("I look for the rats")
    facts = _facts_in(client.last("narration")[0]["content"])
    assert facts == [*failed.carried_facts, narrated.record["validation"][-1]["narration_facts"]]
    assert session.carried_facts == ()
    assert narrated.record["engine_steps"][-1]["step"] == "turn_increment"


def test_the_summary_is_regenerated_after_every_k_narrated_turns(tmp_path: Path) -> None:
    client = ScriptedClient(*[LOOK] * (K + 1))
    session = _session(tmp_path, client)
    turns = [session.play(f"I look around, step {i}") for i in range(K + 1)]

    regenerated = [t.record["summary_regenerated"] for t in turns]
    assert regenerated == [False] * (K - 1) + [True, False]
    assert session.summary == SUMMARY
    assert session.unsummarised == [session.history[-1]]
    assert len(session.history) == K + 1
    # The summary call folds in all K turns, the last one included.
    summary_prompt = client.last("summary")[0]["content"]
    assert all(f"step {i}" in summary_prompt for i in range(K))
    assert SUMMARY in client.last("toolcall")[0]["content"], "later prompts carry it"


def test_a_narration_only_turn_is_narrated_and_advances(tmp_path: Path) -> None:
    client = ScriptedClient(NULL, NULL)
    session = _session(tmp_path, client)
    turn = session.play("I tell the Keeper I will find the ledger")
    assert isinstance(turn, NarratedTurn) and turn.record["narration_only"]
    assert session.state.turn_number == 1
    assert _facts_in(client.last("narration")[0]["content"]) == []


def test_a_run_that_already_has_a_log_is_refused(tmp_path: Path) -> None:
    session = _session(tmp_path, ScriptedClient(LOOK))
    session.play("I look around")
    with pytest.raises(RunExists):
        new_run_log(tmp_path, "D", SCENARIO.scenario_id, SEED)
    assert len(read_log(session.log.path)) == 1


# --- scripted runs (WBS 6.11) ------------------------------------------------

SHRINE = load_scenario(ROOT / "scenarios" / "s03_forest_shrine.json")
# Input 6: perception at DC 11 with advantage, before the encounter at input 7.
SHRINE_CHECK = SHRINE.scripted_inputs[6]


def _shrine_session(tmp_path: Path, client: ScriptedClient) -> Session:
    log = new_run_log(tmp_path, "D", SHRINE.scenario_id, SEED)
    return Session.start(client, CONFIG, TEXTS, SHRINE, log, seed=SEED)


def _shrine_look(dc: int) -> str:
    arguments = {**SHRINE_CHECK.expected_call["arguments"], "dc": dc}
    return json.dumps({"tool": "skill_check", "arguments": arguments})


def test_a_scripted_skill_check_uses_the_scenarios_dc_and_advantage(tmp_path: Path) -> None:
    assert SHRINE_CHECK.check_advantage == "advantage"
    session = _shrine_session(tmp_path, ScriptedClient(_shrine_look(20)))
    turn = session.play(SHRINE_CHECK.text, input_index=6, scripted=SHRINE_CHECK)

    record = read_log(session.log.path)[0]
    assert record == turn.record and record["input_index"] == 6
    # The model's dc is what was proposed and is the logged executed call.
    assert record["proposed_calls"][0]["arguments"]["dc"] == 20
    assert record["executed_call"]["arguments"]["dc"] == 20
    # The engine rolled against the scenario's DC, with its advantage.
    facts = record["validation"][-1]["narration_facts"]
    assert facts["dc"] == SHRINE_CHECK.expected_call["arguments"]["dc"] == 11
    assert facts["advantage_mode"] == "advantage"
    assert facts["success"] == (facts["check_total"] >= 11)
    (roll,) = record["rolls"]
    assert roll["advantage_mode"] == "advantage" and len(roll["individual_dice"]) == 2


def test_a_scripted_skill_check_still_validates_the_models_dc(tmp_path: Path) -> None:
    session = _shrine_session(tmp_path, ScriptedClient(_shrine_look(30), _shrine_look(12)))
    turn = session.play(SHRINE_CHECK.text, input_index=6, scripted=SHRINE_CHECK)

    validation = turn.record["validation"]
    assert validation[0]["rejection_code"] == "DC_OUT_OF_RANGE"
    assert validation[1]["narration_facts"]["dc"] == 11


def test_a_skill_check_the_script_did_not_expect_keeps_the_models_dc(tmp_path: Path) -> None:
    looking = SCENARIO.scripted_inputs[0]  # "I look around the cellar": expected_call null
    assert looking.expected_call is None
    look = json.loads(LOOK)
    look["arguments"]["dc"] = 17
    session = _session(tmp_path, ScriptedClient(json.dumps(look)))
    turn = session.play(looking.text, input_index=0, scripted=looking)

    facts = turn.record["validation"][-1]["narration_facts"]
    assert facts["dc"] == 17 and facts["advantage_mode"] == "normal"


def test_a_failed_scripted_turn_keeps_its_input_index(tmp_path: Path) -> None:
    session = _session(tmp_path, ScriptedClient(GARBLED, GARBLED, GARBLED))
    scripted = SCENARIO.scripted_inputs[0]
    failed = session.play(scripted.text, input_index=0, scripted=scripted)
    assert isinstance(failed, FailedTurn)
    assert failed.record["input_index"] == 0


class LoopingClient(ScriptedClient):
    """Fails the first turn's three attempts, then always looks around."""

    def chat(self, messages: Sequence[Message], *, phase: Phase, seed: int) -> ModelReply:
        if phase == "toolcall" and not self.toolcalls:
            self.toolcalls.append(LOOK)
        return super().chat(messages, phase=phase, seed=seed)


def test_run_script_plays_every_input_and_moves_on_after_a_failed_turn(tmp_path: Path) -> None:
    session = _session(tmp_path, LoopingClient(GARBLED, GARBLED, GARBLED))
    seen: list[int] = []
    turns = run_script(session, on_turn=lambda index, turn: seen.append(index))

    inputs = SCENARIO.scripted_inputs
    records = read_log(session.log.path)
    assert len(turns) == len(records) == len(inputs) == len(seen)
    assert [r["input_index"] for r in records] == list(range(len(inputs))) == seen
    assert [r["player_input"] for r in records] == [i.text for i in inputs]
    assert records[0]["turn_failure"] == "unparseable"
    # The failed input 0 repeats turn 1; the encounter still opens before input 3.
    assert [r["turn_number"] for r in records[:2]] == [1, 1]
    assert records[3]["engine_steps"][0]["step"] == "encounter_start"


# --- the common runner (WBS 7.4) ---------------------------------------------


class RecordingHarness:
    """A stand-in for another condition's harness: anything with a scenario, a
    log and `play` is run by `run_script` exactly as condition D is."""

    def __init__(self, log: AuditLog) -> None:
        self.scenario = SCENARIO
        self.log = log
        self.played: list[tuple[str, int | None, ScriptedInput | None]] = []

    def play(
        self,
        player_input: str,
        *,
        input_index: int | None = None,
        scripted: ScriptedInput | None = None,
    ) -> FailedTurn:
        self.played.append((player_input, input_index, scripted))
        return FailedTurn({"turn_failure": None, "narration": player_input}, ())


def test_run_script_runs_any_harness_the_same_way(tmp_path: Path) -> None:
    harness = RecordingHarness(new_run_log(tmp_path, "A", SCENARIO.scenario_id, SEED))
    turns = run_script(harness)

    inputs = SCENARIO.scripted_inputs
    assert harness.played == [(s.text, i, s) for i, s in enumerate(inputs)]
    assert [t.message for t in turns] == [s.text for s in inputs]


def test_a_run_log_is_named_by_its_condition(tmp_path: Path) -> None:
    log = new_run_log(tmp_path, "B", SCENARIO.scenario_id, SEED)
    assert log.run_id == f"B_{SCENARIO.scenario_id}_{SEED}"
    assert log.path == tmp_path / "B" / SCENARIO.scenario_id / f"{SEED}.jsonl"
    # Another condition's run of the same scenario and seed is a different run.
    new_run_log(tmp_path, "D", SCENARIO.scenario_id, SEED)


# --- replay (WBS 4.18, invariant 4) ------------------------------------------

SCENARIOS = sorted((ROOT / "scenarios").glob("*.json"))
# The record fields a replay turn shares with the audit record.
REPLAYED = (
    "input_index",
    "turn_number",
    "player_input",
    "executed_call",
    "engine_steps",
    "rolls",
    "state_before_hash",
    "state_after_hash",
    "state_diff",
    "turn_failure",
    "narration_only",
)


class OracleClient(ScriptedClient):
    """Proposes `reply`, the current input's expected call, on every toolcall
    attempt: the model the replay harness stands for."""

    reply = NULL

    def chat(self, messages: Sequence[Message], *, phase: Phase, seed: int) -> ModelReply:
        self.toolcalls = [self.reply]
        return super().chat(messages, phase=phase, seed=seed)


def _oracle_run(runs: Path, scenario: Scenario, seed: int = SEED) -> list[Doc]:
    """A scripted condition D run whose model proposes every expected call."""
    client = OracleClient()
    client.seed = seed
    log = new_run_log(runs, "D", scenario.scenario_id, seed)
    session = Session.start(client, CONFIG, TEXTS, scenario, log, seed=seed)
    for index, scripted in enumerate(scenario.scripted_inputs):
        client.reply = json.dumps(scripted.expected_call or {"tool": None})
        session.play(scripted.text, input_index=index, scripted=scripted)
    return read_log(log.path)


@pytest.mark.parametrize("path", SCENARIOS, ids=[p.stem for p in SCENARIOS])
def test_a_session_proposing_the_expected_calls_is_the_replay(tmp_path: Path, path: Path) -> None:
    """The replay harness is the A to C ground truth (CLAUDE.md section 9): the
    run condition D gives when the model proposes every expected call."""
    scenario = load_scenario(path)
    records = _oracle_run(tmp_path, scenario)
    turns = replay_script(scenario, SEED)
    assert len(records) == len(turns) == len(scenario.scripted_inputs)
    for record, turn in zip(records, turns, strict=True):
        replayed = turn.to_dict()
        assert {k: record[k] for k in REPLAYED} == {k: replayed[k] for k in REPLAYED}
        assert record["validation"][-1] == turn.validation


@pytest.mark.parametrize("scenario_id", ["s01_cellar", "long01_border_road"])
def test_two_runs_of_one_seed_are_identical_apart_from_the_timings(
    tmp_path: Path, scenario_id: str
) -> None:
    """Invariant 4 at the session level: the same model replies, seed and
    scenario reproduce the audit log in every field but the timings
    (CLAUDE.md section 11)."""
    scenario = load_scenario(ROOT / "scenarios" / f"{scenario_id}.json")
    first = _oracle_run(tmp_path / "first", scenario)
    second = _oracle_run(tmp_path / "second", scenario)
    assert log_differences(first, second) == []
    assert any(r["summary_regenerated"] for r in first)
    assert log_differences(first, _oracle_run(tmp_path / "other", scenario, SEED + 1))
