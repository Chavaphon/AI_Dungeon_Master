"""Skill checks: strength, perception and stealth against a DC (WBS 4.9,
CLAUDE.md section 4.7).

The roll is `1d20 + ability modifier + proficiency bonus if proficient`, and the
check succeeds when the total is at least the DC. A skill check changes no
state and does not use the turn action.

This is rule code: it assumes the validator (WBS 5.2) has already rejected an
unsupported skill (`SKILL_NOT_SUPPORTED`) or a DC outside 5..25
(`DC_OUT_OF_RANGE`). Reaching here with either is a programmer error, so it
raises instead of returning a rejection.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from adm.engine.abilities import PROFICIENCY_BONUS, Ability, combatant_modifier
from adm.engine.dice import AdvantageMode, DiceRoller, RollResult
from adm.engine.state import Combatant, Skill

SKILL_ABILITY: dict[Skill, Ability] = {
    "strength": "str",
    "perception": "wis",
    "stealth": "dex",
}
SUPPORTED_SKILLS: tuple[Skill, ...] = tuple(SKILL_ABILITY)
MIN_DC = 5
MAX_DC = 25


class CheckResult(BaseModel):
    """One resolved skill check and the single d20 roll behind it."""

    model_config = ConfigDict(frozen=True)

    actor: str
    skill: Skill
    dc: int
    check_total: int
    advantage_mode: AdvantageMode
    success: bool
    roll: RollResult

    def narration_facts(self) -> dict[str, Any]:
        """`facts_skill_check` in tools.schema.json."""
        return self.model_dump(mode="json", exclude={"roll"})


def skill_bonus(actor: Combatant, skill: Skill) -> int:
    """The modifier added to the d20: ability modifier plus proficiency if proficient."""
    if skill not in SKILL_ABILITY:
        raise ValueError(f"unsupported skill {skill!r}")
    bonus = combatant_modifier(actor, SKILL_ABILITY[skill])
    if skill in actor.proficient_skills:
        bonus += PROFICIENCY_BONUS
    return bonus


def skill_check(
    roller: DiceRoller,
    actor: Combatant,
    skill: Skill,
    dc: int,
    advantage_mode: AdvantageMode = "normal",
) -> CheckResult:
    """Roll `skill` for `actor` against `dc`. Success if the total is at least `dc`."""
    if not MIN_DC <= dc <= MAX_DC:
        raise ValueError(f"dc {dc} is outside {MIN_DC}..{MAX_DC}")
    bonus = skill_bonus(actor, skill)
    roll = roller.roll(f"1d20{bonus:+d}", advantage_mode)
    return CheckResult(
        actor=actor.display_name,
        skill=skill,
        dc=dc,
        check_total=roll.total,
        advantage_mode=advantage_mode,
        success=roll.total >= dc,
        roll=roll,
    )
