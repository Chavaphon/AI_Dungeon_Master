"""Spells (CLAUDE.md section 4.6): Fire Bolt (WBS 4.11).

Fire Bolt is a cantrip and a ranged spell attack. It takes the attack code path,
`resolve_attack` in combat.py, with the caster's `spell_attack_bonus` in place of
a weapon's attack bonus and `1d10` damage with no bonus. So it has the same rules
as a weapon attack: disadvantage against a Dodging target, a natural 20 always
hits and rolls `2d10`, a natural 1 always misses, and HP stops at 0. It costs no
resource and can be cast every turn, with or without spell slots left.

`fire_bolt` changes the state in place and returns the parts of the result
envelope (docs/tool_contract.md section 2). It assumes the validator (WBS 5.2)
has already rejected the call if it breaks a precondition; reaching here with a
non-caster or an unconscious target raises. Ending the turn is an engine step
after the tool, not part of it.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from adm.engine.combat import AttackRollFacts, StateChange, resolve_attack
from adm.engine.dice import DiceRoller, RollResult
from adm.engine.state import GameState

FIRE_BOLT = "spell_fire_bolt"
FIRE_BOLT_DAMAGE = "1d10"


class FireBoltFacts(AttackRollFacts):
    """The Fire Bolt branch of `facts_cast_spell` in tools.schema.json."""

    caster: str
    target: str
    spell: Literal["fire bolt"] = "fire bolt"


class SpellOutcome(BaseModel):
    """The `narration_facts`, `state_diff` and `rolls` of a spell's result envelope."""

    model_config = ConfigDict(frozen=True)

    facts: FireBoltFacts
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
