"""The narration-only harness of conditions A to C (WBS 7.1, CLAUDE.md section 9).

Conditions A to C produce narration only, in a single model call. There is no
tool phase and no state mutation. A turn is:

1. Assemble the condition's template (`a`, `b` or `c`) with the rolling summary,
   the last K turns and the player's input, exactly as condition D assembles its
   prompts (CLAUDE.md section 8). The template decides what it uses: `a` holds
   no state, so the state passed in is dropped (docs/conventions.md section 1).
   If the prompt would not fit, K is reduced for the turn and logged as `k_used`.
2. One `narration` call: temperature 0.7 and the narration reply cap, as for
   condition D's call 2 (section 2.2).
3. The safety filter, then the rolling summary after every K-th turn, then the
   turn record. Both are the same as in condition D (decision 40, section 8.1).

The state a turn is scored against is the ground truth of section 9: the state
after the input in `replay_script` (adm/engine/replay.py), which plays each
input's `expected_call` with the run's seed. Both state hashes of an A to C
record are that state, and the state passed to the template is the same one
(docs/audit_log.md section 4.4). `turn_number` is the replay's, so it repeats
exactly where an oracle condition D run would repeat it. The replay is computed
once, when the run starts. The harness never writes it or any other state
(invariant 1).

Every turn is narrated, so every turn joins the verbatim history. A to C have no
failed turns, `narration_only` is false, and the record's tool-phase fields are
empty (docs/audit_log.md section 3).

The ground truth exists only for scripted inputs, so `play` refuses a turn
without its `input_index`. Interactive play stays condition D (`adm/cli.py`).
`NarrationOnlyStart(template)` is the `HarnessStart` that the CLI registers for
a condition, so A, B and C differ only in their template (invariant 7).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from adm.engine.audit import AuditLog, run_id
from adm.engine.replay import ReplayTurn, replay_script
from adm.engine.scenario import Scenario, ScriptedInput
from adm.engine.state import GameState
from adm.orchestration.client import ModelClient, ModelConfig
from adm.orchestration.loop import TurnTimer
from adm.orchestration.prompt import Doc, HistoryTurn, assemble, prompt_budget
from adm.orchestration.safety import SafetyResult, filter_narration
from adm.orchestration.summary import Summary, is_due, regenerate

# The condition each template is run as.
CONDITIONS = {"a": "A", "b": "B", "c": "C"}


class NotScripted(ValueError):
    """A narration-only turn without a scripted input has no ground truth."""


@dataclass(frozen=True)
class NarrationOnlyTurn:
    """A condition A to C turn as written to the audit log."""

    record: Doc
    safety: SafetyResult
    summary: Summary | None

    @property
    def message(self) -> str:
        """What the player is shown: the narration after the safety filter."""
        return self.safety.text


@dataclass
class NarrationOnlySession:
    client: ModelClient
    config: ModelConfig
    texts: Mapping[str, str]
    scenario: Scenario
    log: AuditLog
    template: str
    seed: int
    truth: list[ReplayTurn]
    history: list[HistoryTurn] = field(default_factory=list)
    summary: str | None = None
    # The narrated turns since the summary was last regenerated.
    unsummarised: list[HistoryTurn] = field(default_factory=list)

    @property
    def condition(self) -> str:
        return CONDITIONS[self.template]

    def play(
        self,
        player_input: str,
        *,
        input_index: int | None = None,
        scripted: ScriptedInput | None = None,
    ) -> NarrationOnlyTurn:
        """Narrate one scripted input and log it."""
        if input_index is None:
            raise NotScripted(f"condition {self.condition} plays scripted inputs only")
        timer = TurnTimer()
        truth = self.truth[input_index]
        k = self.config.K_verbatim_turns
        assembled = assemble(
            self.texts,
            self.template,
            player_input=player_input,
            history=self.history,
            summary=self.summary,
            k=k,
            budget=prompt_budget(self.config, "narration"),
            state=GameState.from_dict(truth.state),
        )
        reply = self.client.chat(assembled.messages, phase="narration", seed=self.seed)
        safety = filter_narration(reply.raw_output.strip())
        calls = [reply.model_call("narration", 1)]

        played = HistoryTurn(player_input, safety.text)
        regenerated = None
        if is_due(len(self.history) + 1, k):
            regenerated = regenerate(
                self.client,
                self.config,
                self.texts,
                previous=self.summary,
                turns=[*self.unsummarised, played],
                seed=self.seed,
            )
            calls.append(regenerated.model_call())

        record = {
            "run_id": run_id(self.condition, self.scenario.scenario_id, self.seed),
            "condition": self.condition,
            "scenario_id": self.scenario.scenario_id,
            "seed": self.seed,
            "turn_number": truth.turn_number,
            "input_index": input_index,
            "timestamp": timer.timestamp,
            "player_input": player_input,
            "model_calls": calls,
            "proposed_calls": [],
            "validation": [],
            "executed_call": None,
            "engine_steps": [],
            "rolls": [],
            "state_before_hash": truth.state_after_hash,
            "state_after_hash": truth.state_after_hash,
            "state_diff": [],
            "narration": safety.text,
            "narration_filtered": safety.filtered,
            "turn_failure": None,
            "narration_only": False,
            "k_used": assembled.k_used,
            "summary_regenerated": regenerated is not None,
            "summary": regenerated.record() if regenerated else None,
            "turn_latency_ms": timer.elapsed_ms(),
        }
        self.log.append(record)

        self.history.append(played)
        if regenerated is not None:
            self.summary = regenerated.text
            self.unsummarised = []
        else:
            self.unsummarised.append(played)
        return NarrationOnlyTurn(record, safety, regenerated)


@dataclass(frozen=True)
class NarrationOnlyStart:
    """The `HarnessStart` of the condition that runs `template`."""

    template: str

    def __post_init__(self) -> None:
        if self.template not in CONDITIONS:
            raise ValueError(f"{self.template!r} is not a narration-only template")

    def __call__(
        self,
        client: ModelClient,
        config: ModelConfig,
        texts: Mapping[str, str],
        scenario: Scenario,
        log: AuditLog,
        *,
        seed: int,
    ) -> NarrationOnlySession:
        return NarrationOnlySession(
            client, config, texts, scenario, log, self.template, seed, replay_script(scenario, seed)
        )
