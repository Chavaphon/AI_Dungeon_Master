"""Inventory add and remove with quantity rules (WBS 4.14, CLAUDE.md section 6.1,
docs/tool_contract.md section 2).

`modify_inventory(actor_id, item_id, delta)` changes one inventory by `delta`.
`actor_id` is the inventory's owner, not someone acting, so the owner may be
unconscious: the player character can loot a downed rat after a victory. There
is no transfer between inventories; taking an item from someone is not a tool.

Quantity rules:

1. A quantity is never negative. A `delta` that would take it below 0 is the
   validator's `NEGATIVE_QUANTITY`, and its `valid_options` is the most negative
   legal delta, `-held` (`most_negative_delta`).
2. A quantity that reaches 0 keeps its key (WBS 2.2), so "the torch is used up"
   stays visible in the state and the diff.
3. An item the owner has never held is added at `delta`. Its diff entry has
   `from: null`, as a new key does elsewhere (result_update_npc_relationship.json).
   An owner with no inventory at all gets one, as `inventory.<owner>` from `null`.
4. A `delta` of 0 is a `SCHEMA_VIOLATION` (WBS 5.1); it never reaches here.

`modify_inventory` changes the state in place and returns the parts of the
result envelope. It assumes the validator (WBS 5.2) has already rejected an
unknown owner (`UNKNOWN_ENTITY`), an undefined item (`ITEM_NOT_DEFINED`) and a
delta that breaks rule 1. Reaching here with any of them, or with a delta of 0,
raises, so a negative quantity cannot be written whatever the caller does. It
does not use the turn action, and the turn check (`NOT_YOUR_TURN`) is the
validator's.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from adm.engine.combat import StateChange
from adm.engine.state import GameState


class InventoryFacts(BaseModel):
    """`facts_modify_inventory` in tools.schema.json."""

    model_config = ConfigDict(frozen=True)

    actor: str
    item: str
    delta: int
    quantity_before: int
    quantity_after: int


class InventoryOutcome(BaseModel):
    """The `narration_facts`, `state_diff` and `rolls` of an inventory result envelope."""

    model_config = ConfigDict(frozen=True)

    facts: InventoryFacts
    state_diff: list[StateChange]

    def to_dict(self) -> dict[str, Any]:
        return {
            "narration_facts": self.facts.model_dump(mode="json"),
            "state_diff": [c.model_dump(mode="json", by_alias=True) for c in self.state_diff],
            "rolls": [],
        }


def held(state: GameState, actor_id: str, item_id: str) -> int:
    """How many of `item_id` the owner holds; 0 for an item never held."""
    return state.inventory.get(actor_id, {}).get(item_id, 0)


def most_negative_delta(state: GameState, actor_id: str, item_id: str) -> int:
    """The `NEGATIVE_QUANTITY` valid option: remove everything held, and no more."""
    return -held(state, actor_id, item_id)


def modify_inventory(state: GameState, actor_id: str, item_id: str, delta: int) -> InventoryOutcome:
    """Add `delta` of `item_id` to `actor_id`'s inventory (negative removes)."""
    if actor_id not in state.combatants:
        raise ValueError(f"{actor_id} is not a combatant")
    if item_id not in state.item_definitions:
        raise ValueError(f"{item_id} is not defined")
    if delta == 0:
        raise ValueError("delta is 0")
    before = held(state, actor_id, item_id)
    after = before + delta
    if after < 0:
        raise ValueError(f"{actor_id} holds {before} of {item_id}; cannot apply {delta:+d}")

    diff: list[StateChange] = []
    if actor_id not in state.inventory:
        diff.append(StateChange(path=f"inventory.{actor_id}", from_=None, to={item_id: after}))
        state.inventory[actor_id] = {item_id: after}
    else:
        items = state.inventory[actor_id]
        diff.append(
            StateChange(path=f"inventory.{actor_id}.{item_id}", from_=items.get(item_id), to=after)
        )
        items[item_id] = after

    facts = InventoryFacts(
        actor=state.combatants[actor_id].display_name,
        item=state.item_definitions[item_id].display_name,
        delta=delta,
        quantity_before=before,
        quantity_after=after,
    )
    return InventoryOutcome(facts=facts, state_diff=diff)
