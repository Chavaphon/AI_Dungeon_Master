"""A condition D session (WBS 6.10, 6.11): the turn loop of CLAUDE.md section 7,
one player input at a time, typed by a person or taken from the scenario script.

`new_run_log` opens the run's audit log, and refuses one that already exists
for the same `(scenario_id, seed)`, so two sessions never share a run id.
`Session.start` builds the turn-0 state from the scenario and the run's one
`DiceRoller`.

`Session.play` plays one turn:

1. Start the encounter that is due before this input (`scenario.due_encounter`).
   Interactive play counts the player's inputs from 0, failed turns included.
   The NPCs who win initiative act now, as `before_call` steps.
2. The tool phase (`loop.run_tool_phase`). A validated call is executed by
   `tools.dispatch`, the one write path.
3. A turn whose budget ran out is logged by `loop.fail_turn` and does not
   advance. The facts of its NPC actions wait for the next narrated turn.
4. Otherwise the engine steps after the call (`tools.after_call`) and
   `turn_increment` run, and `loop.narrate_turn` narrates and logs the turn,
   regenerating the rolling summary after every K-th narrated turn.

Every narrated turn joins the verbatim history; a failed turn has no narration
and does not. `input_index` is null in interactive play (docs/audit_log.md
section 1). The session writes state only through the engine (invariant 1).

`run_script` plays a scenario's scripted inputs in order, with `input_index`
set, and moves on after a failed turn (CLAUDE.md section 7.1). For a scripted
skill check the scenario's `dc` and `check_advantage` are authoritative
(CLAUDE.md section 4.7): the model's call is validated as proposed, then
executed with the scenario's `dc` and advantage. `proposed_calls` and
`executed_call` keep the model's call, so its `dc` is logged, and the result's
`narration_facts` carry the DC that was rolled against (docs/decisions.md,
WBS 6.11).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from adm.engine.audit import AuditLog, Step
from adm.engine.dice import DiceRoller
from adm.engine.scenario import Scenario, ScriptedInput, due_encounter, initial_state
from adm.engine.state import GameState
from adm.engine.tools import after_call, dispatch, increment_turn, open_encounter
from adm.engine.validator import ToolCall
from adm.orchestration.client import ModelClient, ModelConfig
from adm.orchestration.loop import (
    CONDITION,
    FailedTurn,
    NarratedTurn,
    TurnTimer,
    fail_turn,
    narrate_turn,
    run_tool_phase,
)
from adm.orchestration.prompt import Doc, HistoryTurn
from adm.orchestration.summary import is_due


class RunExists(FileExistsError):
    """A session would append to the audit log of an earlier run."""


def new_run_log(runs_dir: Path, scenario_id: str, seed: int) -> AuditLog:
    """The audit log of a new condition D run, which must not exist yet."""
    log = AuditLog(runs_dir, CONDITION, scenario_id, seed)
    if log.path.exists():
        raise RunExists(f"{log.path} already exists; choose another seed or move it")
    return log


@dataclass
class Session:
    client: ModelClient
    config: ModelConfig
    texts: Mapping[str, str]
    scenario: Scenario
    state: GameState
    roller: DiceRoller
    log: AuditLog
    history: list[HistoryTurn] = field(default_factory=list)
    summary: str | None = None
    # The narrated turns since the summary was last regenerated.
    unsummarised: list[HistoryTurn] = field(default_factory=list)
    # NPC facts from failed turns, for the next narrated turn.
    carried_facts: tuple[Doc, ...] = ()
    inputs_received: int = 0
    encounters_started: int = 0
    # The scripted input being played, if any: it fixes a skill check's DC.
    scripted: ScriptedInput | None = None

    @classmethod
    def start(
        cls,
        client: ModelClient,
        config: ModelConfig,
        texts: Mapping[str, str],
        scenario: Scenario,
        log: AuditLog,
        *,
        seed: int,
    ) -> Session:
        state = initial_state(scenario, seed)
        return cls(client, config, texts, scenario, state, DiceRoller(seed), log)

    @property
    def seed(self) -> int:
        return self.state.seed

    def play(
        self,
        player_input: str,
        *,
        input_index: int | None = None,
        scripted: ScriptedInput | None = None,
    ) -> NarratedTurn | FailedTurn:
        """Play one turn on the player's input and return what was logged.
        A scripted turn passes its input and `input_index`."""
        self.scripted = scripted
        timer = TurnTimer()
        before = self.state.to_dict()
        steps: list[Step] = []
        encounter = due_encounter(
            self.scenario.encounters, self.encounters_started, self.inputs_received, self.state
        )
        self.inputs_received += 1
        if encounter is not None:
            steps += open_encounter(self.state, self.roller, encounter.combatant_ids)
            self.encounters_started += 1

        phase = run_tool_phase(
            self.client,
            self.config,
            self.texts,
            self.state,
            player_input=player_input,
            history=self.history,
            summary=self.summary,
            seed=self.seed,
            execute=self._execute,
        )
        if phase.turn_failure is not None:
            failed = fail_turn(
                self.log,
                self.state,
                before,
                steps,
                phase,
                input_index=input_index,
                player_input=player_input,
                timer=timer,
            )
            self.carried_facts += failed.carried_facts
            return failed

        if phase.executed_call is not None:
            steps += after_call(self.state, self.roller, phase.executed_call.tool)
        steps.append(increment_turn(self.state))
        due = is_due(len(self.history) + 1, self.config.K_verbatim_turns)
        turn = narrate_turn(
            self.log,
            self.client,
            self.config,
            self.texts,
            self.state,
            before,
            steps,
            phase,
            carried_facts=self.carried_facts,
            input_index=input_index,
            player_input=player_input,
            history=self.history,
            summary=self.summary,
            seed=self.seed,
            timer=timer,
            fold=self.unsummarised if due else None,
        )
        self.carried_facts = ()
        played = HistoryTurn(player_input, turn.message)
        self.history.append(played)
        if turn.summary is not None:
            self.summary = turn.summary.text
            self.unsummarised = []
        else:
            self.unsummarised.append(played)
        return turn

    def _execute(self, call: ToolCall) -> Doc:
        proposed = call.model_dump(mode="json")
        scripted = self.scripted
        expected = scripted.expected_call if scripted is not None else None
        if expected is None or expected["tool"] != "skill_check" or call.tool != "skill_check":
            return dispatch(self.state, self.roller, proposed)
        # The scenario's DC and advantage, not the model's (CLAUDE.md section 4.7).
        arguments = {**proposed["arguments"], "dc": expected["arguments"]["dc"]}
        advantage = scripted.check_advantage if scripted is not None else None
        return dispatch(
            self.state,
            self.roller,
            {**proposed, "arguments": arguments},
            check_advantage=advantage or "normal",
        )


def run_script(
    session: Session,
    on_turn: Callable[[int, NarratedTurn | FailedTurn], None] | None = None,
) -> list[NarratedTurn | FailedTurn]:
    """Play every scripted input of the session's scenario, in order, calling
    `on_turn` after each. A failed turn is logged and the run takes the next
    input (CLAUDE.md section 7.1)."""
    turns: list[NarratedTurn | FailedTurn] = []
    for index, scripted in enumerate(session.scenario.scripted_inputs):
        turn = session.play(scripted.text, input_index=index, scripted=scripted)
        turns.append(turn)
        if on_turn is not None:
            on_turn(index, turn)
    return turns
