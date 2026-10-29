"""NPC relationship ladder: one step per event, justification required (WBS 4.15,
CLAUDE.md sections 5.2 and 6.1, docs/tool_contract.md section 2).

The ladder is `hostile, unfriendly, neutral, friendly, allied`, in that order.
`update_npc_relationship(npc_id, direction, justification)` moves an NPC's stance
one step: `up` is friendlier, `down` more hostile.

Rules:

1. **One step per event.** The call has a direction, not a target stance, so it
   cannot ask for more than one step. A bigger change takes several calls, each
   with its own justification, and each lands in `history`. Moving up from
   `allied` or down from `hostile` would leave the ladder, and is the
   validator's `RELATIONSHIP_STEP_TOO_LARGE`, with the other direction as its
   valid option (`other_direction`).
2. **Justification required.** At least 10 characters (`MIN_JUSTIFICATION`),
   counted as written, as the state schema counts them. Fewer is the
   validator's `MISSING_JUSTIFICATION`. It is stored verbatim in the history
   entry and the `narration_facts`.
3. **History.** Each change appends `{turn, from, to, justification}` with
   `turn = turn_number`, the state's turn before the current one advances. Its
   diff entry is `npc_relationships.<npc>.history.<n>` from `null`, after the
   stance entry (result_update_npc_relationship.json).

`update_npc_relationship` changes the state in place and returns the parts of
the result envelope. It assumes the validator (WBS 5.2) has already rejected an
unknown NPC (`UNKNOWN_ENTITY`), a short justification and a step off the
ladder. Reaching here with any of them, or with a direction other than `up` or
`down`, raises, so neither a two-step change nor an unjustified one can be
written whatever the caller does. It has no actor and no turn check, and does
not use the turn action.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from adm.engine.combat import StateChange
from adm.engine.state import GameState, RelationshipChange, Stance

LADDER: tuple[Stance, ...] = ("hostile", "unfriendly", "neutral", "friendly", "allied")
MIN_JUSTIFICATION = 10

Direction = Literal["up", "down"]
_STEP: dict[Direction, int] = {"up": 1, "down": -1}


class RelationshipFacts(BaseModel):
    """`facts_update_npc_relationship` in tools.schema.json."""

    model_config = ConfigDict(frozen=True)

    npc: str
    stance_before: Stance
    stance_after: Stance
    justification: str


class RelationshipOutcome(BaseModel):
    """The `narration_facts`, `state_diff` and `rolls` of a relationship result envelope."""

    model_config = ConfigDict(frozen=True)

    facts: RelationshipFacts
    state_diff: list[StateChange]

    def to_dict(self) -> dict[str, Any]:
        return {
            "narration_facts": self.facts.model_dump(mode="json"),
            "state_diff": [c.model_dump(mode="json", by_alias=True) for c in self.state_diff],
            "rolls": [],
        }


def step(stance: Stance, direction: Direction) -> Stance | None:
    """The stance one step from `stance`, or None past either end of the ladder."""
    index = LADDER.index(stance) + _STEP[direction]
    return LADDER[index] if 0 <= index < len(LADDER) else None


def other_direction(direction: Direction) -> Direction:
    """The `RELATIONSHIP_STEP_TOO_LARGE` valid option."""
    return "down" if direction == "up" else "up"


def update_npc_relationship(
    state: GameState, npc_id: str, direction: Direction, justification: str
) -> RelationshipOutcome:
    """Move `npc_id`'s stance one step `direction`, and record why."""
    if npc_id not in state.npc_relationships:
        raise ValueError(f"{npc_id} has no relationship")
    if direction not in _STEP:
        raise ValueError(f"direction {direction!r} is not up or down")
    if len(justification) < MIN_JUSTIFICATION:
        raise ValueError(f"justification {justification!r} is under {MIN_JUSTIFICATION} characters")
    relationship = state.npc_relationships[npc_id]
    before = relationship.stance
    after = step(before, direction)
    if after is None:
        raise ValueError(f"{npc_id} is {before}; cannot move {direction}")

    entry = RelationshipChange.model_validate(
        {"turn": state.turn_number, "from": before, "to": after, "justification": justification}
    )
    path = f"npc_relationships.{npc_id}"
    diff = [
        StateChange(path=f"{path}.stance", from_=before, to=after),
        StateChange(
            path=f"{path}.history.{len(relationship.history)}",
            from_=None,
            to=entry.model_dump(mode="json", by_alias=True),
        ),
    ]
    relationship.stance = after
    relationship.history.append(entry)

    facts = RelationshipFacts(
        npc=relationship.display_name,
        stance_before=before,
        stance_after=after,
        justification=justification,
    )
    return RelationshipOutcome(facts=facts, state_diff=diff)
