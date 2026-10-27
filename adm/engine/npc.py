"""Engine-controlled NPC turns (WBS 4.19, CLAUDE.md section 4.8, docs/npc_policy.md).

Every combatant except the player character is played by the engine, with fixed
rules over the current state and no model call. The rules were agreed at the
Week 3 checkpoint (docs/decisions.md, 2026-10-24, decision 3):

1. An NPC's opponents are the conscious combatants in the initiative order of
   the opposing faction: `party` for a `hostile`, `hostile` for a `party` NPC.
   A `neutral` NPC has none.
2. Its target is the opponent with the lowest `current_hp`, ties broken by the
   smaller `combatant_id`.
3. Its weapon is the first weapon id in its sorted inventory that it holds
   (quantity above 0).
4. With a weapon and a target it attacks; otherwise it dodges.

The policy rolls no dice of its own, so the only rolls in an NPC turn are those
of its attack, from the run's one seeded `DiceRoller` (invariant 3).

`after_player_action` is what the engine does after the player character's
action-using call (`attack`, `cast_spell`, `dodge`): end the encounter if it is
over, otherwise pass the turn on and play every NPC turn until the turn comes
back to the PC or the encounter ends. When an encounter starts and an NPC wins
initiative, `run_npc_turns(..., when="before_call")` plays the NPCs ahead of the
PC before the player's call, so initiative alone decides who acts first. Each
NPC turn is an `npc_action` step, then `encounter_end` if the fight is over,
then `initiative_advance` and `dodge_expiry` (docs/audit_log.md section 2).

`take_npc_turn` is the one place an NPC call is executed. The validator (WBS
5.2) checks it there like a player's call; the policy only proposes legal calls,
so a rejection would be a bug in the policy and raises.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from adm.engine.combat import (
    EngineStep,
    When,
    advance_initiative,
    attack,
    dodge,
    end_encounter_if_over,
    expire_dodge,
)
from adm.engine.dice import DiceRoller
from adm.engine.state import Faction, GameState

OPPONENTS: dict[Faction, Faction | None] = {
    "hostile": "party",
    "party": "hostile",
    "neutral": None,
}


class NpcCall(BaseModel):
    """The `executed_call` of an `npc_action` step (audit.schema.json)."""

    model_config = ConfigDict(frozen=True)

    tool: Literal["attack", "dodge"]
    arguments: dict[str, str]


class NpcActionStep(BaseModel):
    """An `npc_action` step: the engine's call for an NPC and its full `result_ok`."""

    model_config = ConfigDict(frozen=True)

    step: Literal["npc_action"] = "npc_action"
    when: When
    call: NpcCall
    result: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


def _target(state: GameState, npc_id: str) -> str | None:
    opposing = OPPONENTS[state.combatants[npc_id].faction]
    opponents = [
        state.combatants[cid]
        for cid in state.initiative_order
        if state.combatants[cid].faction == opposing and state.combatants[cid].status == "active"
    ]
    if not opponents:
        return None
    return min(opponents, key=lambda c: (c.current_hp, c.combatant_id)).combatant_id


def _weapon(state: GameState, npc_id: str) -> str | None:
    held = state.inventory.get(npc_id, {})
    return next(
        (
            item_id
            for item_id in sorted(held)
            if held[item_id] > 0 and state.item_definitions[item_id].is_weapon
        ),
        None,
    )


def choose_action(state: GameState, npc_id: str) -> NpcCall:
    """The policy: attack the weakest opponent with the first weapon held, or dodge."""
    target, weapon = _target(state, npc_id), _weapon(state, npc_id)
    if target is None or weapon is None:
        return NpcCall(tool="dodge", arguments={"actor_id": npc_id})
    return NpcCall(
        tool="attack",
        arguments={"attacker_id": npc_id, "target_id": target, "weapon_id": weapon},
    )


def take_npc_turn(state: GameState, roller: DiceRoller, when: When) -> NpcActionStep:
    """Choose and execute the active NPC's action, and return its `npc_action` step."""
    if not state.encounter_active:
        raise ValueError("no active encounter")
    assert state.active_combatant_id is not None
    npc_id = state.active_combatant_id
    if state.combatants[npc_id].is_player_character:
        raise ValueError(f"{npc_id} is the player character, not an NPC")
    call = choose_action(state, npc_id)
    args = call.arguments
    if call.tool == "attack":
        outcome = attack(state, roller, args["attacker_id"], args["target_id"], args["weapon_id"])
        result = {"ok": True, "tool": "attack", **outcome.to_dict()}
    else:
        result = {"ok": True, "tool": "dodge", **dodge(state, args["actor_id"]).to_dict()}
    return NpcActionStep(when=when, call=call, result=result)


Step = EngineStep | NpcActionStep


def _pass_turn(state: GameState, when: When) -> list[Step]:
    """Advance initiative, then expire the new active combatant's Dodge."""
    steps: list[Step] = [advance_initiative(state, when=when)]
    expiry = expire_dodge(state, when=when)
    if expiry is not None:
        steps.append(expiry)
    return steps


def _npc_is_active(state: GameState) -> bool:
    if not state.encounter_active:
        return False
    assert state.active_combatant_id is not None
    return not state.combatants[state.active_combatant_id].is_player_character


def run_npc_turns(state: GameState, roller: DiceRoller, when: When) -> list[Step]:
    """Play NPC turns from the active combatant until the player character is
    active or the encounter ends."""
    steps: list[Step] = []
    while _npc_is_active(state):
        steps.append(take_npc_turn(state, roller, when))
        end = end_encounter_if_over(state, when=when)
        if end is not None:
            steps.append(end)
            break
        steps.extend(_pass_turn(state, when))
    return steps


def after_player_action(state: GameState, roller: DiceRoller) -> list[Step]:
    """The engine steps after the player character's action-using call: end the
    encounter if it is over, otherwise pass the turn and play the NPC turns."""
    end = end_encounter_if_over(state)
    if end is not None:
        return [end]
    return _pass_turn(state, "after_call") + run_npc_turns(state, roller, "after_call")
