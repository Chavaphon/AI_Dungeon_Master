"""Skill checks (WBS 4.9): each of strength, perception and stealth is tested at,
above and below the DC, and the result matches `facts_skill_check`.

The d20 comes from a real seeded `DiceRoller`. To put a check exactly at, above
or below the DC, a test first rolls once with a seed to learn the total, then
replays the same seed against a DC chosen from that total.

Run: pytest tests/engine/test_checks.py -v
"""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from adm.engine.checks import SUPPORTED_SKILLS, skill_bonus, skill_check
from adm.engine.dice import DiceRoller
from adm.engine.state import Combatant, GameState, load_state, state_hash

ROOT = Path(__file__).resolve().parents[2]
MID_COMBAT = ROOT / "schemas" / "examples" / "state_02_mid_combat.json"

_SCHEMAS = [
    json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))
    for name in ("state.schema.json", "tools.schema.json")
]
_REGISTRY = Registry().with_resources((s["$id"], Resource.from_contents(s)) for s in _SCHEMAS)


def _validator(definition: str) -> Draft202012Validator:
    return Draft202012Validator(
        {"$ref": _SCHEMAS[1]["$id"] + f"#/$defs/{definition}"}, registry=_REGISTRY
    )


FACTS_VALIDATOR = _validator("facts_skill_check")
ROLL_VALIDATOR = _validator("roll_result")


@pytest.fixture
def state() -> GameState:
    return load_state(MID_COMBAT)


@pytest.fixture
def lyra(state: GameState) -> Combatant:
    return state.combatants["pc_lyra"]


def _seed_with_total_in(actor: Combatant, skill: str, low: int, high: int) -> tuple[int, int]:
    """The first seed whose check total lies in low..high, and that total."""
    for seed in range(1000):
        total = skill_check(DiceRoller(seed), actor, skill, 10).check_total
        if low <= total <= high:
            return seed, total
    raise AssertionError("no seed found")


# --- bonus per skill ---------------------------------------------------------


@pytest.mark.parametrize(
    ("combatant_id", "skill", "expected"),
    [
        ("pc_lyra", "strength", 1),  # str 12, not proficient
        ("pc_lyra", "perception", 1),  # wis 13, not proficient
        ("pc_lyra", "stealth", 5),  # dex 16 (+3), proficient (+2)
        ("npc_rat_01", "strength", -2),  # str 7: a negative bonus
        ("npc_rat_01", "perception", 2),  # wis 10 (+0), proficient (+2)
    ],
)
def test_skill_bonus(state: GameState, combatant_id: str, skill: str, expected: int) -> None:
    assert skill_bonus(state.combatants[combatant_id], skill) == expected


# --- at, above and below the DC (rule suite) ---------------------------------


@pytest.mark.parametrize("skill", SUPPORTED_SKILLS)
@pytest.mark.parametrize(
    ("dc_offset", "success"),
    [(0, True), (-1, True), (1, False)],
    ids=["at_dc", "above_dc", "below_dc"],
)
def test_check_against_dc(lyra: Combatant, skill: str, dc_offset: int, success: bool) -> None:
    # The total must leave room for DC = total +/- 1 inside 5..25.
    seed, total = _seed_with_total_in(lyra, skill, 6, 24)
    result = skill_check(DiceRoller(seed), lyra, skill, total + dc_offset)
    assert result.check_total == total
    assert result.success is success


def test_negative_bonus_can_fail_on_a_roll_that_would_otherwise_pass(state: GameState) -> None:
    rat = state.combatants["npc_rat_01"]
    seed, total = _seed_with_total_in(rat, "strength", 5, 23)
    result = skill_check(DiceRoller(seed), rat, "strength", total + 2)
    assert result.roll.individual_dice[0] == total + 2  # the raw d20 alone would meet the DC
    assert result.success is False


# --- roll shape and narration facts ------------------------------------------


def test_total_is_d20_plus_bonus(lyra: Combatant) -> None:
    result = skill_check(DiceRoller(12345), lyra, "stealth", 15)
    assert result.roll.notation == "1d20+5"
    assert result.check_total == result.roll.individual_dice[0] + 5 == result.roll.total
    ROLL_VALIDATOR.validate(result.roll.to_dict())


def test_zero_bonus_rolls_a_bare_d20(state: GameState) -> None:
    # npc_rat_01 has wis 10 and is proficient; strip the proficiency to get +0.
    rat = state.combatants["npc_rat_01"].model_copy(update={"proficient_skills": []})
    result = skill_check(DiceRoller(1), rat, "perception", 10)
    assert result.roll.notation == "1d20"
    assert result.roll.modifier == 0


def test_narration_facts_match_the_schema(lyra: Combatant) -> None:
    result = skill_check(DiceRoller(7), lyra, "perception", 12)
    facts = result.narration_facts()
    FACTS_VALIDATOR.validate(facts)
    assert facts == {
        "actor": "Lyra",
        "skill": "perception",
        "dc": 12,
        "check_total": result.roll.total,
        "advantage_mode": "normal",
        "success": result.roll.total >= 12,
    }


@pytest.mark.parametrize("mode", ["advantage", "disadvantage"])
def test_scenario_granted_advantage(lyra: Combatant, mode: str) -> None:
    result = skill_check(DiceRoller(99), lyra, "perception", 12, mode)
    dice = result.roll.individual_dice
    kept = max(dice) if mode == "advantage" else min(dice)
    assert len(dice) == 2
    assert result.check_total == kept + 1
    assert result.narration_facts()["advantage_mode"] == mode


def test_same_seed_reproduces_the_check(lyra: Combatant) -> None:
    first = skill_check(DiceRoller(2026), lyra, "stealth", 14)
    second = skill_check(DiceRoller(2026), lyra, "stealth", 14)
    assert first == second


def test_a_check_changes_no_state(state: GameState) -> None:
    before = state_hash(state)
    skill_check(DiceRoller(3), state.combatants["pc_lyra"], "stealth", 14)
    assert state_hash(state) == before


# --- programmer errors (the validator rejects these first) -------------------


@pytest.mark.parametrize("dc", [4, 26])
def test_dc_outside_5_to_25_raises(lyra: Combatant, dc: int) -> None:
    with pytest.raises(ValueError, match="outside 5..25"):
        skill_check(DiceRoller(1), lyra, "stealth", dc)


@pytest.mark.parametrize("dc", [5, 25])
def test_dc_boundaries_are_allowed(lyra: Combatant, dc: int) -> None:
    assert skill_check(DiceRoller(1), lyra, "stealth", dc).dc == dc


def test_unsupported_skill_raises(lyra: Combatant) -> None:
    with pytest.raises(ValueError, match="unsupported skill"):
        skill_check(DiceRoller(1), lyra, "athletics", 10)  # type: ignore[arg-type]
