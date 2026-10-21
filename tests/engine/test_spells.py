"""Fire Bolt (WBS 4.11) and Cure Wounds (WBS 4.12), CLAUDE.md section 4.6.

Fire Bolt is a ranged spell attack on the attack code path (`resolve_attack`):
`1d20 + spell attack bonus` against AC, 1d10 damage, 2d10 on a critical, and no
resource spent. Cure Wounds heals `1d8 + spellcasting modifier`, minimum 1, never
past max HP, revives an unconscious target and spends one level-1 slot. The tests
roll with a real seeded `DiceRoller` and look for a seed that gives the case they
need.

Run: pytest tests/engine/test_spells.py -v
"""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from adm.engine.combat import advance_initiative
from adm.engine.dice import DiceRoller
from adm.engine.spells import SpellOutcome, cure_wounds, fire_bolt
from adm.engine.state import GameState, load_state

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "schemas" / "examples"

_SCHEMAS = [
    json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))
    for name in ("state.schema.json", "tools.schema.json")
]
_REGISTRY = Registry().with_resources((s["$id"], Resource.from_contents(s)) for s in _SCHEMAS)
RESULT_VALIDATOR = Draft202012Validator(
    {"$ref": _SCHEMAS[1]["$id"] + "#/$defs/tool_result"}, registry=_REGISTRY
)


@pytest.fixture
def mid_combat() -> GameState:
    # Lyra (spell attack +5, 2 slots) is active and the rats have AC 12.
    # npc_rat_01 is at 4 of 11 HP; npc_rat_02 is at 11 of 11 and Dodging.
    return load_state(EXAMPLES / "state_02_mid_combat.json")


def _seed_for(*dice: tuple[int, int]) -> int:
    """A seed whose first draws are the given `(sides, value)` dice, in order."""
    for seed in range(200_000):
        roller = DiceRoller(seed)
        if all(roller.roll(f"1d{sides}").total == value for sides, value in dice):
            return seed
    raise AssertionError(f"no seed found for {dice}")


def _bolt(state: GameState, target_id: str, seed: int) -> SpellOutcome:
    return fire_bolt(state, DiceRoller(seed), "pc_lyra", target_id)


def _result(outcome: SpellOutcome) -> dict:
    return {"ok": True, "tool": "cast_spell", **outcome.to_dict()}


def _assert_valid(state: GameState) -> None:
    GameState.from_dict(state.to_dict())


@pytest.mark.rule_suite("spells")
def test_fire_bolt_reproduces_the_contract_example(mid_combat: GameState) -> None:
    # Disadvantage keeps the 8: 8 + 5 = 13 hits AC 12, then 1d10 rolls 7.
    outcome = _bolt(mid_combat, "npc_rat_02", _seed_for((20, 15), (20, 8), (10, 7)))
    example = json.loads(
        (EXAMPLES / "result_cast_spell_fire_bolt.json").read_text(encoding="utf-8")
    )
    assert _result(outcome) == example
    RESULT_VALIDATOR.validate(_result(outcome))
    assert mid_combat.combatants["npc_rat_02"].current_hp == 4
    _assert_valid(mid_combat)


def test_fire_bolt_uses_the_spell_attack_bonus_not_a_weapon(mid_combat: GameState) -> None:
    # 9 + 2 = 11 misses AC 12; the short sword's +5 would have hit.
    mid_combat.combatants["pc_lyra"].spell_attack_bonus = 2
    outcome = _bolt(mid_combat, "npc_rat_01", _seed_for((20, 9)))
    assert outcome.rolls[0].notation == "1d20+2"
    assert outcome.facts.attack_roll == 11
    assert outcome.facts.hit is False
    assert outcome.facts.damage == 0
    assert outcome.state_diff == []
    assert len(outcome.rolls) == 1  # no damage roll on a miss
    RESULT_VALIDATOR.validate(_result(outcome))


@pytest.mark.rule_suite("spells")
def test_fire_bolt_critical_rolls_2d10(mid_combat: GameState) -> None:
    mid_combat.combatants["npc_rat_01"].current_hp = 11
    outcome = _bolt(mid_combat, "npc_rat_01", _seed_for((20, 20), (10, 3), (10, 4)))
    damage_roll = outcome.rolls[1]
    assert damage_roll.notation == "2d10"
    assert damage_roll.individual_dice == [3, 4]
    assert damage_roll.modifier == 0
    assert outcome.facts.critical is True
    assert outcome.facts.damage == 7
    assert mid_combat.combatants["npc_rat_01"].current_hp == 4
    RESULT_VALIDATOR.validate(_result(outcome))


@pytest.mark.rule_suite("spells")
def test_fire_bolt_costs_no_slot_and_works_with_none_left(mid_combat: GameState) -> None:
    mid_combat.combatants["pc_lyra"].spell_slots_1 = 0
    mid_combat.combatants["npc_rat_01"].current_hp = 11
    seed = _seed_for((20, 15), (10, 2), (20, 15), (10, 2))
    roller = DiceRoller(seed)
    for _ in range(2):  # a cantrip is usable every turn
        outcome = fire_bolt(mid_combat, roller, "pc_lyra", "npc_rat_01")
        assert outcome.facts.hit is True
        assert [c.path for c in outcome.state_diff] == ["combatants.npc_rat_01.current_hp"]
    assert mid_combat.combatants["pc_lyra"].spell_slots_1 == 0
    assert mid_combat.combatants["npc_rat_01"].current_hp == 7


def test_fire_bolt_natural_1_misses_whatever_the_bonus(mid_combat: GameState) -> None:
    mid_combat.combatants["pc_lyra"].spell_attack_bonus = 30
    outcome = _bolt(mid_combat, "npc_rat_01", _seed_for((20, 1)))
    assert outcome.facts.attack_roll == 31
    assert outcome.facts.hit is False
    assert outcome.facts.damage == 0


def test_fire_bolt_to_zero_knocks_out(mid_combat: GameState) -> None:
    outcome = _bolt(mid_combat, "npc_rat_01", _seed_for((20, 15), (10, 9)))
    rat = mid_combat.combatants["npc_rat_01"]
    assert outcome.facts.damage == 9
    assert (rat.current_hp, rat.status) == (0, "unconscious")
    assert outcome.facts.target_hp_band == "unconscious"
    assert outcome.facts.target_status == "unconscious"
    RESULT_VALIDATOR.validate(_result(outcome))
    _assert_valid(mid_combat)


def test_fire_bolt_on_an_unconscious_target_raises(mid_combat: GameState) -> None:
    rat = mid_combat.combatants["npc_rat_01"]
    rat.current_hp, rat.status = 0, "unconscious"
    with pytest.raises(ValueError, match="unconscious"):
        _bolt(mid_combat, "npc_rat_01", 1)


def test_fire_bolt_by_a_non_caster_raises(mid_combat: GameState) -> None:
    with pytest.raises(ValueError, match="not a caster"):
        fire_bolt(mid_combat, DiceRoller(1), "npc_rat_01", "pc_lyra")


def test_same_seed_gives_the_same_fire_bolt(mid_combat: GameState) -> None:
    results = [
        _bolt(mid_combat.model_copy(deep=True), "npc_rat_01", 99).to_dict() for _ in range(2)
    ]
    assert results[0] == results[1]


# --- Cure Wounds (WBS 4.12) ---------------------------------------------------
# Lyra has spellcasting modifier +3 and 2 level-1 slots, and is at 14 of 20 HP.


def _cure(state: GameState, target_id: str, seed: int) -> SpellOutcome:
    return cure_wounds(state, DiceRoller(seed), "pc_lyra", target_id)


@pytest.mark.rule_suite("spells")
def test_cure_wounds_reproduces_the_contract_example(mid_combat: GameState) -> None:
    # 6 + 3 = 9 rolled, but only 6 fits under max HP; one slot is spent.
    outcome = _cure(mid_combat, "pc_lyra", _seed_for((8, 6)))
    example = json.loads(
        (EXAMPLES / "result_cast_spell_cure_wounds.json").read_text(encoding="utf-8")
    )
    assert _result(outcome) == example
    RESULT_VALIDATOR.validate(_result(outcome))
    lyra = mid_combat.combatants["pc_lyra"]
    assert (lyra.current_hp, lyra.spell_slots_1) == (20, 1)
    _assert_valid(mid_combat)


@pytest.mark.rule_suite("spells")
@pytest.mark.parametrize(
    ("d8", "applied", "hp_after"),
    [
        (2, 5, 19),  # below the cap: 5 rolled, 6 of room
        (3, 6, 20),  # exactly at the cap: 6 rolled, 6 of room
        (8, 6, 20),  # past the cap: 11 rolled, 6 applied
    ],
)
def test_cure_wounds_never_exceeds_max_hp(
    mid_combat: GameState, d8: int, applied: int, hp_after: int
) -> None:
    outcome = _cure(mid_combat, "pc_lyra", _seed_for((8, d8)))
    assert outcome.facts.healed_rolled == d8 + 3
    assert outcome.facts.healed_applied == applied
    assert outcome.facts.target_hp_after == hp_after
    assert mid_combat.combatants["pc_lyra"].current_hp == hp_after
    RESULT_VALIDATOR.validate(_result(outcome))


@pytest.mark.rule_suite("spells")
def test_cure_wounds_heals_at_least_1(mid_combat: GameState) -> None:
    # 1 - 3 = -2 rolled, raised to the minimum of 1.
    mid_combat.combatants["pc_lyra"].spellcasting_modifier = -3
    outcome = _cure(mid_combat, "npc_rat_01", _seed_for((8, 1)))
    assert outcome.rolls[0].notation == "1d8-3"
    assert outcome.rolls[0].total == -2
    assert outcome.facts.healed_rolled == outcome.facts.healed_applied == 1
    assert mid_combat.combatants["npc_rat_01"].current_hp == 5
    RESULT_VALIDATOR.validate(_result(outcome))


def test_cure_wounds_at_full_hp_heals_0_and_still_spends_the_slot(mid_combat: GameState) -> None:
    mid_combat.combatants["pc_lyra"].current_hp = 20
    outcome = _cure(mid_combat, "pc_lyra", _seed_for((8, 5)))
    assert outcome.facts.healed_rolled == 8
    assert outcome.facts.healed_applied == 0
    assert outcome.facts.slots_remaining == 1
    assert [(c.path, c.from_, c.to) for c in outcome.state_diff] == [
        ("combatants.pc_lyra.spell_slots_1", 2, 1),
    ]
    RESULT_VALIDATOR.validate(_result(outcome))


@pytest.mark.rule_suite("zero_hp")
def test_cure_wounds_revives_and_the_combatant_acts_in_its_slot(mid_combat: GameState) -> None:
    # Order is rat_01, Lyra, rat_02 and Lyra is active. She heals the downed rat_01.
    rat = mid_combat.combatants["npc_rat_01"]
    rat.current_hp, rat.status = 0, "unconscious"
    outcome = _cure(mid_combat, "npc_rat_01", _seed_for((8, 2)))
    assert (rat.current_hp, rat.status) == (5, "active")
    assert outcome.facts.revived is True
    assert outcome.facts.target_hp_before == 0
    assert outcome.facts.target_status == "active"
    assert outcome.facts.target_hp_band == "wounded"
    assert [(c.path, c.from_, c.to) for c in outcome.state_diff] == [
        ("combatants.npc_rat_01.current_hp", 0, 5),
        ("combatants.npc_rat_01.status", "unconscious", "active"),
        ("combatants.pc_lyra.spell_slots_1", 2, 1),
    ]
    RESULT_VALIDATOR.validate(_result(outcome))
    _assert_valid(mid_combat)
    advance_initiative(mid_combat)  # rat_02
    advance_initiative(mid_combat)  # wraps to rat_01, no longer skipped
    assert mid_combat.active_combatant_id == "npc_rat_01"


def test_cure_wounds_on_a_conscious_target_does_not_revive(mid_combat: GameState) -> None:
    outcome = _cure(mid_combat, "npc_rat_01", _seed_for((8, 2)))
    assert outcome.facts.revived is False
    assert [c.path for c in outcome.state_diff] == [
        "combatants.npc_rat_01.current_hp",
        "combatants.pc_lyra.spell_slots_1",
    ]


def test_cure_wounds_works_outside_an_encounter() -> None:
    state = load_state(EXAMPLES / "state_01_exploration.json")
    assert state.encounter_active is False
    lyra = state.combatants["pc_lyra"]
    lyra.current_hp = 10
    slots = lyra.spell_slots_1
    assert slots
    outcome = _cure(state, "pc_lyra", _seed_for((8, 4)))
    assert outcome.facts.healed_applied == 4 + lyra.spellcasting_modifier
    assert lyra.spell_slots_1 == slots - 1
    _assert_valid(state)


def test_cure_wounds_with_no_slot_left_raises(mid_combat: GameState) -> None:
    mid_combat.combatants["pc_lyra"].spell_slots_1 = 0
    with pytest.raises(ValueError, match="no level-1 spell slot"):
        _cure(mid_combat, "pc_lyra", 1)
    assert mid_combat.combatants["pc_lyra"].current_hp == 14


def test_cure_wounds_by_a_non_caster_raises(mid_combat: GameState) -> None:
    with pytest.raises(ValueError, match="not a caster"):
        cure_wounds(mid_combat, DiceRoller(1), "npc_rat_01", "npc_rat_01")
