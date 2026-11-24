"""Action hints in beginner mode (WBS 13.7).

Before each input, beginner mode shows "You could try:" and two to four things
the player could type, worked out from the current state:

    You could try:
      attack the giant rat 1 with your short sword
      cast Fire Bolt at the giant rat 1
      dodge

In a fight on the player's turn: attack the first conscious enemy in the turn
order with the first weapon held, Fire Bolt at it (casters only), Cure Wounds on
the most hurt member of the party (while charges are left), and dodge. Outside a
fight: look around, talk to a known NPC, use an item carried. Fewer than two is
padded with a skill check that is always open: look around in a fight, sneak
outside one. The order is fixed, so the same state always gives the same hints.
A knocked-out player character, after a lost fight, gets no hints.

Each hint carries the tool call it stands for, and only hints whose call the
validator accepts in that state are shown (`adm.engine.validator.validate`),
so a hint never suggests an action the engine would reject at that moment. The
calls are never executed and never sent anywhere: this module reads the state
and the validator only, never the dice or the model (CLAUDE.md section 15,
item 76). A fight that is due before the next input is not foreseen, because
starting one rolls the turn order.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from adm.engine.inventory import held
from adm.engine.spells import CURE_WOUNDS, FIRE_BOLT
from adm.engine.state import Combatant, GameState
from adm.engine.validator import Rejection, validate
from adm.play.commands import combatant_labels

TITLE = "You could try:"
MIN_HINTS = 2
MAX_HINTS = 4
# The DC a hint's skill check is validated with. Any DC in range passes; the
# model chooses its own when the player types the hint, and it is never shown.
HINT_DC = 10


@dataclass(frozen=True)
class Hint:
    """Something the player could type, and the tool call it stands for
    (`{"tool": None}` for talk, which has no mechanical effect)."""

    text: str
    call: dict[str, Any]


def hints(state: GameState) -> list[Hint]:
    """Up to four hints for the player's next input in `state`, which is only
    read, each one a call the validator accepts in `state`: at least two while
    the player character is conscious, none once they are knocked out."""
    pc = _player(state)
    if pc.status != "active":
        return []  # knocked out: the fight is lost and there is nothing to try
    fight = state.encounter_active and state.active_combatant_id == pc.combatant_id
    candidates, padding = (
        (_fight(state, pc), _look(pc)) if fight else (_exploring(state, pc), _sneak(pc))
    )
    legal = [h for h in candidates if _accepted(state, h)]
    if len(legal) < MIN_HINTS and _accepted(state, padding):
        legal.append(padding)
    return legal[:MAX_HINTS]


def _accepted(state: GameState, hint: Hint) -> bool:
    return not isinstance(validate(state, hint.call), Rejection)


def hint_block(state: GameState) -> str | None:
    """The hints for `state` as `play` shows them, or None if there are none."""
    found = hints(state)
    if not found:
        return None
    return "\n".join([TITLE, *(f"  {h.text}" for h in found)])


# --- the candidates ----------------------------------------------------------


def _player(state: GameState) -> Combatant:
    return next(c for c in state.combatants.values() if c.is_player_character)


def _named(label: str) -> str:
    """A name as the player would type it: "the giant rat", but "Bram"."""
    return label if label[:1].isupper() or label.startswith("the ") else f"the {label}"


def _skill_check(pc: Combatant, skill: str) -> dict[str, Any]:
    arguments = {"actor_id": pc.combatant_id, "skill": skill, "dc": HINT_DC}
    return {"tool": "skill_check", "arguments": arguments}


def _look(pc: Combatant) -> Hint:
    return Hint("look around", _skill_check(pc, "perception"))


def _sneak(pc: Combatant) -> Hint:
    return Hint("sneak ahead quietly", _skill_check(pc, "stealth"))


def _held_items(state: GameState, pc: Combatant, *, weapons: bool) -> list[str]:
    return sorted(
        item_id
        for item_id in state.inventory.get(pc.combatant_id, {})
        if held(state, pc.combatant_id, item_id) > 0
        and state.item_definitions[item_id].is_weapon is weapons
    )


def _is_caster(c: Combatant) -> bool:
    return None not in (c.spell_attack_bonus, c.spellcasting_modifier, c.spell_slots_1)


def _fight(state: GameState, pc: Combatant) -> list[Hint]:
    labels = combatant_labels(state)
    pc_id = pc.combatant_id
    enemies = [
        cid
        for cid in state.initiative_order
        if state.combatants[cid].faction == "hostile" and state.combatants[cid].status == "active"
    ]
    found: list[Hint] = []
    weapons = _held_items(state, pc, weapons=True)
    if enemies and weapons:
        enemy, weapon = enemies[0], weapons[0]
        name = state.item_definitions[weapon].display_name
        found.append(
            Hint(
                f"attack {_named(labels[enemy])} with your {name}",
                {
                    "tool": "attack",
                    "arguments": {"attacker_id": pc_id, "target_id": enemy, "weapon_id": weapon},
                },
            )
        )
    if enemies and _is_caster(pc):
        enemy = enemies[0]
        found.append(
            Hint(
                f"cast Fire Bolt at {_named(labels[enemy])}",
                {
                    "tool": "cast_spell",
                    "arguments": {"caster_id": pc_id, "spell_id": FIRE_BOLT, "target_id": enemy},
                },
            )
        )
    hurt = sorted(
        (c.current_hp / c.max_hp, cid)
        for cid, c in state.combatants.items()
        if c.faction == "party" and c.current_hp < c.max_hp
    )
    if _is_caster(pc) and (pc.spell_slots_1 or 0) > 0 and hurt:
        target = hurt[0][1]
        whom = "yourself" if target == pc_id else _named(labels[target])
        found.append(
            Hint(
                f"cast Cure Wounds on {whom}",
                {
                    "tool": "cast_spell",
                    "arguments": {"caster_id": pc_id, "spell_id": CURE_WOUNDS, "target_id": target},
                },
            )
        )
    found.append(Hint("dodge", {"tool": "dodge", "arguments": {"actor_id": pc_id}}))
    return found


def _exploring(state: GameState, pc: Combatant) -> list[Hint]:
    found = [_look(pc)]
    npcs = [
        npc_id
        for npc_id in sorted(state.npc_relationships)
        if npc_id not in state.combatants or state.combatants[npc_id].status == "active"
    ]
    if npcs:
        name = state.npc_relationships[npcs[0]].display_name
        found.append(Hint(f"talk to {_named(name)}", {"tool": None}))
    items = _held_items(state, pc, weapons=False)
    if items:
        item = items[0]
        found.append(
            Hint(
                f"use your {state.item_definitions[item].display_name}",
                {
                    "tool": "modify_inventory",
                    "arguments": {"actor_id": pc.combatant_id, "item_id": item, "delta": -1},
                },
            )
        )
    return found
