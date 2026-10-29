"""Quest log transitions (WBS 4.16, CLAUDE.md section 5.2, docs/tool_contract.md
section 2).

`update_quest(quest_id, transition)` moves a quest along this table, and nothing
else is legal:

| Transition | From                          | To                         |
|------------|-------------------------------|----------------------------|
| `start`    | `not_started`, stage 0        | `active`, stage 1          |
| `advance`  | `active`, `stage < max_stage` | `active`, stage + 1        |
| `complete` | `active`                      | `completed`, stage unchanged |
| `fail`     | `active`                      | `failed`, stage unchanged  |

So `stage` only goes up, never past `max_stage`, and `completed` and `failed`
are final. `complete` does not require `stage == max_stage`: a quest may end
early, as `fail` may.

Any other transition is `ILLEGAL_QUEST_TRANSITION`. Its `valid_options` is the
transitions legal from the quest's current state, in table order
(`legal_transitions`); it is empty for a finished quest.

`update_quest` changes the state in place and returns the parts of the result
envelope. Its diff is the `state` entry then the `stage` entry, each only if it
changes (result_update_quest.json). It assumes the validator (WBS 5.2) has
already rejected an unknown quest (`UNKNOWN_QUEST`) and an illegal transition.
Reaching here with an unknown quest raises `ValueError`; with an illegal
transition it raises `IllegalQuestTransition`, which names the code and the
valid options, so an illegal transition cannot be written whatever the caller
does. It has no actor and no turn check, and does not use the turn action.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from adm.engine.combat import StateChange
from adm.engine.state import GameState, Quest, QuestState

Transition = Literal["start", "advance", "complete", "fail"]
TRANSITIONS: tuple[Transition, ...] = ("start", "advance", "complete", "fail")
ILLEGAL_QUEST_TRANSITION = "ILLEGAL_QUEST_TRANSITION"


class IllegalQuestTransition(ValueError):
    """A transition the table does not allow from the quest's current state."""

    code = ILLEGAL_QUEST_TRANSITION

    def __init__(self, quest: Quest, transition: str) -> None:
        self.valid_options: dict[str, list[str]] = {"transition": legal_transitions(quest)}
        super().__init__(
            f"{self.code}: {quest.quest_id} is {quest.state} at stage {quest.stage} of"
            f" {quest.max_stage}; cannot {transition}"
        )


class QuestFacts(BaseModel):
    """`facts_update_quest` in tools.schema.json."""

    model_config = ConfigDict(frozen=True)

    quest: str
    transition: Transition
    state_before: QuestState
    state_after: QuestState
    stage_before: int
    stage_after: int
    max_stage: int


class QuestOutcome(BaseModel):
    """The `narration_facts`, `state_diff` and `rolls` of a quest result envelope."""

    model_config = ConfigDict(frozen=True)

    facts: QuestFacts
    state_diff: list[StateChange]

    def to_dict(self) -> dict[str, Any]:
        return {
            "narration_facts": self.facts.model_dump(mode="json"),
            "state_diff": [c.model_dump(mode="json", by_alias=True) for c in self.state_diff],
            "rolls": [],
        }


def _after(quest: Quest, transition: str) -> tuple[QuestState, int] | None:
    """The quest's `(state, stage)` after `transition`, or None if it is illegal."""
    if transition == "start" and quest.state == "not_started":
        return "active", 1
    if transition == "advance" and quest.state == "active" and quest.stage < quest.max_stage:
        return "active", quest.stage + 1
    if transition == "complete" and quest.state == "active":
        return "completed", quest.stage
    if transition == "fail" and quest.state == "active":
        return "failed", quest.stage
    return None


def legal_transitions(quest: Quest) -> list[Transition]:
    """The transitions legal from the quest's current state, in table order."""
    return [t for t in TRANSITIONS if _after(quest, t) is not None]


def update_quest(state: GameState, quest_id: str, transition: Transition) -> QuestOutcome:
    """Apply `transition` to `quest_id`."""
    if quest_id not in state.quests:
        raise ValueError(f"{quest_id} is not a quest")
    quest = state.quests[quest_id]
    after = _after(quest, transition)
    if after is None:
        raise IllegalQuestTransition(quest, transition)

    state_before, stage_before = quest.state, quest.stage
    state_after, stage_after = after
    path = f"quests.{quest_id}"
    diff: list[StateChange] = []
    if state_after != state_before:
        diff.append(StateChange(path=f"{path}.state", from_=state_before, to=state_after))
    if stage_after != stage_before:
        diff.append(StateChange(path=f"{path}.stage", from_=stage_before, to=stage_after))
    quest.state, quest.stage = state_after, stage_after

    facts = QuestFacts(
        quest=quest.display_name,
        transition=transition,
        state_before=state_before,
        state_after=state_after,
        stage_before=stage_before,
        stage_after=stage_after,
        max_stage=quest.max_stage,
    )
    return QuestOutcome(facts=facts, state_diff=diff)
