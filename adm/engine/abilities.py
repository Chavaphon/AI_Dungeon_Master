"""Ability scores, modifiers, proficiency bonus and armour class (WBS 4.3,
CLAUDE.md section 4.1).

Ability scores are stored in the scenario and never rolled. The modifier is
`floor((score - 10) / 2)`, computed with `math.floor` so that odd scores below
10 round down: score 7 gives -2, not -1. Proficiency is a flat +2 for every
combatant. Armour class is stored per combatant and read as it is, never
derived from armour or dexterity (CLAUDE.md section 15, decision 1).
"""

from __future__ import annotations

import math
from typing import Literal

from adm.engine.state import Combatant

Ability = Literal["str", "dex", "con", "int", "wis", "cha"]

ABILITIES: tuple[Ability, ...] = ("str", "dex", "con", "int", "wis", "cha")
MIN_SCORE = 1
MAX_SCORE = 20
PROFICIENCY_BONUS = 2


def ability_modifier(score: int) -> int:
    """The modifier for an ability score in 1..20."""
    # bool is an int subclass; a True score is a programmer error, not 1.
    if isinstance(score, bool) or not isinstance(score, int):
        raise TypeError(f"ability score must be an int, got {type(score).__name__}")
    if not MIN_SCORE <= score <= MAX_SCORE:
        raise ValueError(f"ability score {score} is outside {MIN_SCORE}..{MAX_SCORE}")
    return math.floor((score - 10) / 2)


def ability_score(combatant: Combatant, ability: Ability) -> int:
    if ability not in ABILITIES:
        raise ValueError(f"unknown ability {ability!r}")
    return combatant.abilities.model_dump(by_alias=True)[ability]


def combatant_modifier(combatant: Combatant, ability: Ability) -> int:
    """The combatant's modifier for one ability, e.g. `dex` for initiative."""
    return ability_modifier(ability_score(combatant, ability))


def armour_class(combatant: Combatant) -> int:
    """The stored armour class. Deliberately not derived from anything."""
    return combatant.armour_class
