"""Ability scores, modifiers, proficiency bonus and armour class (WBS 4.3):
boundary scores are covered, negatives round down, and armour class is read as
stored rather than derived.

Run: pytest tests/engine/test_abilities.py -v
"""

from pathlib import Path

import pytest

from adm.engine.abilities import (
    ABILITIES,
    PROFICIENCY_BONUS,
    ability_modifier,
    ability_score,
    armour_class,
    combatant_modifier,
)
from adm.engine.state import Combatant, load_state

ROOT = Path(__file__).resolve().parents[2]
MID_COMBAT = ROOT / "schemas" / "examples" / "state_02_mid_combat.json"


@pytest.fixture
def combatants() -> dict[str, Combatant]:
    return load_state(MID_COMBAT).combatants


# --- ability modifier (rule suite: 4 cases) --------------------------------


@pytest.mark.parametrize(("score", "expected"), [(1, -5), (20, 5)])
def test_modifier_at_the_score_boundaries(score: int, expected: int) -> None:
    assert ability_modifier(score) == expected


@pytest.mark.parametrize(("score", "expected"), [(7, -2), (9, -1), (3, -4)])
def test_odd_scores_below_10_round_down(score: int, expected: int) -> None:
    # Integer truncation towards zero would give -1, 0 and -3 here.
    assert ability_modifier(score) == expected


@pytest.mark.parametrize(("score", "expected"), [(10, 0), (11, 0), (12, 1), (13, 1)])
def test_modifier_around_10(score: int, expected: int) -> None:
    assert ability_modifier(score) == expected


@pytest.mark.parametrize("score", [0, 21, -1])
def test_scores_outside_1_to_20_are_rejected(score: int) -> None:
    with pytest.raises(ValueError, match="outside 1..20"):
        ability_modifier(score)


# --- supporting checks ------------------------------------------------------


def test_every_score_matches_the_formula() -> None:
    table = {score: ability_modifier(score) for score in range(1, 21)}
    assert table == {s: (s - 10) // 2 for s in range(1, 21)}
    assert sorted(set(table.values())) == list(range(-5, 6))


@pytest.mark.parametrize("score", [True, 10.0, "10"])
def test_non_int_scores_are_programmer_errors(score: object) -> None:
    with pytest.raises(TypeError):
        ability_modifier(score)  # type: ignore[arg-type]


def test_ability_scores_are_read_by_name(combatants: dict[str, Combatant]) -> None:
    lyra = combatants["pc_lyra"]
    scores = {ability: ability_score(lyra, ability) for ability in ABILITIES}
    assert scores == {"str": 12, "dex": 16, "con": 14, "int": 10, "wis": 13, "cha": 11}


def test_unknown_ability_is_rejected(combatants: dict[str, Combatant]) -> None:
    with pytest.raises(ValueError, match="unknown ability"):
        ability_score(combatants["pc_lyra"], "luck")  # type: ignore[arg-type]


def test_combatant_modifiers(combatants: dict[str, Combatant]) -> None:
    assert combatant_modifier(combatants["pc_lyra"], "dex") == 3
    assert combatant_modifier(combatants["pc_lyra"], "int") == 0
    assert combatant_modifier(combatants["npc_rat_01"], "str") == -2
    assert combatant_modifier(combatants["npc_rat_01"], "int") == -4


def test_proficiency_bonus_is_a_flat_2() -> None:
    assert PROFICIENCY_BONUS == 2


def test_armour_class_is_stored_not_derived(combatants: dict[str, Combatant]) -> None:
    lyra = combatants["pc_lyra"]
    # 10 + dex modifier would be 13; the stored value wins.
    assert armour_class(lyra) == 14 != 10 + combatant_modifier(lyra, "dex")
    assert armour_class(combatants["npc_rat_01"]) == 12
