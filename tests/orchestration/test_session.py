"""Interactive session (WBS 6.10): a session plays the turn loop end to end on
a scenario, one input at a time. Encounters start before the player's n-th
input, failed turns included; failed turns do not advance and their NPC facts
reach the next narration; narrated turns build the history and the rolling
summary; and every turn is in the audit log.

No test calls a model: a fake client answers each phase from a script.

Run: pytest tests/orchestration/test_session.py -v
"""

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from adm.engine.audit import read_log
from adm.engine.combat import start_encounter
from adm.engine.dice import DiceRoller
from adm.engine.scenario import initial_state, load_scenario
from adm.orchestration import prompt
from adm.orchestration.client import Message, ModelReply, Phase, load_model_config
from adm.orchestration.loop import REPHRASE, FailedTurn, NarratedTurn
from adm.orchestration.session import RunExists, Session, new_run_log

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
    log = new_run_log(tmp_path, SCENARIO.scenario_id, seed)
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
        new_run_log(tmp_path, SCENARIO.scenario_id, SEED)
    assert len(read_log(session.log.path)) == 1
