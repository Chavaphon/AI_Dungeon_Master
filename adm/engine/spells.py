"""Spells (CLAUDE.md section 4.6): Fire Bolt (WBS 4.11) and Cure Wounds (WBS 4.12).

Fire Bolt is a cantrip and a ranged spell attack. It takes the attack code path,
`resolve_attack` in combat.py, with the caster's `spell_attack_bonus` in place of
a weapon's attack bonus and `1d10` damage with no bonus. So it has the same rules
as a weapon attack: disadvantage against a Dodging target, a natural 20 always
hits and rolls `2d10`, a natural 1 always misses, and HP stops at 0. It costs no
resource and can be cast every turn, with or without spell slots left.

Cure Wounds has no attack roll. It heals `1d8 + spellcasting modifier`, minimum
1, but never past the target's max HP: `healed_rolled` is the roll and
`healed_applied` what fit, which is 0 at full HP. It spends one level-1 slot
whatever it heals. It may target an unconscious combatant, which comes back
`active` and acts on its next turn in the existing initiative order, and it is
legal outside an encounter. Its diff is the HP, the status on a revival, then
the slot.

Each spell changes the state in place and returns the parts of the result
envelope (docs/tool_contract.md section 2). It assumes the validator (WBS 5.2)
has already rejected the call if it breaks a precondition; reaching here with a
non-caster, a Fire Bolt at an unconscious target or a Cure Wounds with no slot
left raises. Ending the turn is an engine step after the tool, not part of it.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from adm.engine.combat import AttackRollFacts, HpBand, StateChange, hp_band, resolve_attack
from adm.engine.dice import DiceRoller, RollResult
from adm.engine.state import GameState, Status

FIRE_BOLT = "spell_fire_bolt"
FIRE_BOLT_DAMAGE = "1d10"
CURE_WOUNDS = "spell_cure_wounds"
CURE_WOUNDS_HEALING = "1d8"


class FireBoltFacts(AttackRollFacts):
    """The Fire Bolt branch of `facts_cast_spell` in tools.schema.json."""

    caster: str
    target: str
    spell: Literal["fire bolt"] = "fire bolt"


class CureWoundsFacts(BaseModel):
    """The Cure Wounds branch of `facts_cast_spell` in tools.schema.json."""

    model_config = ConfigDict(frozen=True)

    caster: str
    target: str
    spell: Literal["cure wounds"] = "cure wounds"
    healed_rolled: int
    healed_applied: int
    target_hp_before: int
    target_hp_after: int
    target_hp_max: int
    target_hp_band: HpBand
    target_status: Status
    revived: bool
    slots_remaining: int


class SpellOutcome(BaseModel):
    """The `narration_facts`, `state_diff` and `rolls` of a spell's result envelope."""

    model_config = ConfigDict(frozen=True)

    facts: FireBoltFacts | CureWoundsFacts
    state_diff: list[StateChange]
    rolls: list[RollResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "narration_facts": self.facts.model_dump(mode="json"),
            "state_diff": [c.model_dump(mode="json", by_alias=True) for c in self.state_diff],
            "rolls": [r.to_dict() for r in self.rolls],
        }


def fire_bolt(state: GameState, roller: DiceRoller, caster_id: str, target_id: str) -> SpellOutcome:
    """Cast Fire Bolt (section 4.6) at `target_id` and apply it to `state`."""
    caster = state.combatants[caster_id]
    if caster.spell_attack_bonus is None:
        raise ValueError(f"{caster_id} is not a caster")
    roll_facts, diff, rolls = resolve_attack(
        state, roller, target_id, caster.spell_attack_bonus, FIRE_BOLT_DAMAGE, 0
    )
    facts = FireBoltFacts(
        caster=caster.display_name,
        target=state.combatants[target_id].display_name,
        **roll_facts.model_dump(),
    )
    return SpellOutcome(facts=facts, state_diff=diff, rolls=rolls)


def cure_wounds(
    state: GameState, roller: DiceRoller, caster_id: str, target_id: str
) -> SpellOutcome:
    """Cast Cure Wounds (section 4.6) on `target_id` and apply it to `state`."""
    caster = state.combatants[caster_id]
    if caster.spellcasting_modifier is None or caster.spell_slots_1 is None:
        raise ValueError(f"{caster_id} is not a caster")
    if caster.spell_slots_1 == 0:
        raise ValueError(f"{caster_id} has no level-1 spell slot left")
    target = state.combatants[target_id]

    roll = roller.roll(f"{CURE_WOUNDS_HEALING}{caster.spellcasting_modifier:+d}")
    healed_rolled = max(1, roll.total)
    hp_before = target.current_hp
    healed_applied = min(healed_rolled, target.max_hp - hp_before)
    revived = target.status == "unconscious"

    diff: list[StateChange] = []
    path = f"combatants.{target_id}"
    if healed_applied:
        diff.append(
            StateChange(path=f"{path}.current_hp", from_=hp_before, to=hp_before + healed_applied)
        )
        target.current_hp = hp_before + healed_applied
    if revived:
        diff.append(StateChange(path=f"{path}.status", from_="unconscious", to="active"))
        target.status = "active"
    slots_before = caster.spell_slots_1
    diff.append(
        StateChange(
            path=f"combatants.{caster_id}.spell_slots_1", from_=slots_before, to=slots_before - 1
        )
    )
    caster.spell_slots_1 = slots_before - 1

    facts = CureWoundsFacts(
        caster=caster.display_name,
        target=target.display_name,
        healed_rolled=healed_rolled,
        healed_applied=healed_applied,
        target_hp_before=hp_before,
        target_hp_after=target.current_hp,
        target_hp_max=target.max_hp,
        target_hp_band=hp_band(target.current_hp, target.max_hp),
        target_status=target.status,
        revived=revived,
        slots_remaining=caster.spell_slots_1,
    )
    return SpellOutcome(facts=facts, state_diff=diff, rolls=[roll])
