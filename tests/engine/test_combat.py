"""Initiative, turn order, tie-break and round advance (WBS 4.4, CLAUDE.md section 4.4),
and attack resolution (WBS 4.5, CLAUDE.md section 4.5).

The tie-break tests build `InitiativeEntry` values with chosen totals, so each
rule is tested on its own. The end-to-end tests roll with a real seeded
`DiceRoller`, and look for a seed that gives the case they need.

Run: pytest tests/engine/test_combat.py -v
"""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from adm.engine.combat import (
    AttackOutcome,
    InitiativeEntry,
    advance_initiative,
    attack,
    hp_band,
    initiative_order,
    roll_initiative,
    start_encounter,
)
from adm.engine.dice import DiceRoller, RollResult
from adm.engine.state import GameState, load_state

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "schemas" / "examples"
ENCOUNTER = ["pc_lyra", "npc_rat_01", "npc_rat_02"]

_SCHEMAS = [
    json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))
    for name in ("state.schema.json", "tools.schema.json", "audit.schema.json")
]
_REGISTRY = Registry().with_resources((s["$id"], Resource.from_contents(s)) for s in _SCHEMAS)
STEP_VALIDATOR = Draft202012Validator(
    {"$ref": _SCHEMAS[2]["$id"] + "#/$defs/bookkeeping_step"}, registry=_REGISTRY
)
RESULT_VALIDATOR = Draft202012Validator(
    {"$ref": _SCHEMAS[1]["$id"] + "#/$defs/tool_result"}, registry=_REGISTRY
)


@pytest.fixture
def exploring() -> GameState:
    return load_state(EXAMPLES / "state_01_exploration.json")


@pytest.fixture
def mid_combat() -> GameState:
    return load_state(EXAMPLES / "state_02_mid_combat.json")


def _entry(combatant_id: str, dex: int, total: int) -> InitiativeEntry:
    roll = RollResult(
        notation="1d20",
        individual_dice=[total],
        modifier=0,
        total=total,
        advantage_mode="normal",
    )
    return InitiativeEntry(combatant_id=combatant_id, dex=dex, roll=roll)


def _knock_out(state: GameState, combatant_id: str) -> None:
    state.combatants[combatant_id].current_hp = 0
    state.combatants[combatant_id].status = "unconscious"


def _assert_valid(state: GameState) -> None:
    GameState.from_dict(state.to_dict())


# --- rolling and ordering (rule suite) ---------------------------------------


def test_initiative_is_d20_plus_dex_modifier_in_listed_order(exploring: GameState) -> None:
    combatants = [exploring.combatants[cid] for cid in ENCOUNTER]
    entries = roll_initiative(DiceRoller(12345), combatants)
    assert [e.combatant_id for e in entries] == ENCOUNTER
    # Lyra has dex 16 (+3); the rats dex 15 (+2).
    assert [e.roll.notation for e in entries] == ["1d20+3", "1d20+2", "1d20+2"]
    for e in entries:
        assert e.roll.total == e.roll.individual_dice[0] + e.roll.modifier


def test_order_is_highest_total_first() -> None:
    entries = [_entry("npc_a", 10, 8), _entry("npc_b", 10, 19), _entry("pc_c", 10, 12)]
    assert initiative_order(entries) == ["npc_b", "pc_c", "npc_a"]


def test_tie_breaks_on_higher_dex_score_not_modifier() -> None:
    # dex 14 and 15 both give +2; the score itself decides.
    entries = [_entry("npc_a", 14, 15), _entry("npc_b", 15, 15)]
    assert initiative_order(entries) == ["npc_b", "npc_a"]


def test_tie_on_total_and_dex_breaks_on_smaller_id() -> None:
    entries = [_entry(cid, 15, 12) for cid in ("pc_lyra", "npc_rat_02", "npc_rat_01")]
    assert initiative_order(entries) == ["npc_rat_01", "npc_rat_02", "pc_lyra"]


def test_same_seed_gives_the_same_order(exploring: GameState) -> None:
    orders = set()
    for _ in range(2):
        state = exploring.model_copy(deep=True)
        start_encounter(state, DiceRoller(2026), ENCOUNTER)
        orders.add(tuple(state.initiative_order))
    assert len(orders) == 1


def test_seeded_tie_between_the_rats_is_broken_by_id(exploring: GameState) -> None:
    # Both rats have dex 15: a tied total must put npc_rat_01 first, whatever the listed order.
    for seed in range(1000):
        rats = [exploring.combatants["npc_rat_02"], exploring.combatants["npc_rat_01"]]
        entries = roll_initiative(DiceRoller(seed), rats)
        if entries[0].roll.total == entries[1].roll.total:
            break
    else:
        raise AssertionError("no seed found")
    assert initiative_order(entries) == ["npc_rat_01", "npc_rat_02"]


# --- encounter start ---------------------------------------------------------


def test_start_encounter_sets_order_round_and_first_actor(exploring: GameState) -> None:
    step = start_encounter(exploring, DiceRoller(12345), ENCOUNTER)
    assert exploring.encounter_active is True
    assert sorted(exploring.initiative_order) == sorted(ENCOUNTER)
    assert exploring.round_number == 1
    assert exploring.active_combatant_id == exploring.initiative_order[0]
    assert step.step == "encounter_start"
    assert step.when == "before_call"
    assert len(step.rolls) == 3
    STEP_VALIDATOR.validate(step.to_dict())
    _assert_valid(exploring)


def test_start_encounter_diff_records_every_change(exploring: GameState) -> None:
    step = start_encounter(exploring, DiceRoller(7), ENCOUNTER)
    paths = {c.path: (c.from_, c.to) for c in step.state_diff}
    assert paths == {
        "encounter_active": (False, True),
        "initiative_order": ([], exploring.initiative_order),
        "round_number": (0, 1),
        "active_combatant_id": (None, exploring.active_combatant_id),
    }


def test_a_later_encounter_restarts_at_round_one_and_clears_the_outcome() -> None:
    state = load_state(EXAMPLES / "state_03_after_victory.json")
    for rat in ("npc_rat_01", "npc_rat_02"):
        state.combatants[rat].current_hp = 5
        state.combatants[rat].status = "active"
    start_encounter(state, DiceRoller(3), ENCOUNTER)
    assert state.round_number == 1
    assert state.encounter_outcome is None
    _assert_valid(state)


def test_unconscious_combatant_keeps_a_slot_but_does_not_act_first(exploring: GameState) -> None:
    for seed in range(1000):
        state = exploring.model_copy(deep=True)
        order = initiative_order(
            roll_initiative(DiceRoller(seed), [state.combatants[c] for c in ENCOUNTER])
        )
        if order[0] == "npc_rat_01":
            break
    else:
        raise AssertionError("no seed found")
    _knock_out(state, "npc_rat_01")
    start_encounter(state, DiceRoller(seed), ENCOUNTER)
    assert state.initiative_order == order
    assert state.active_combatant_id == order[1]


@pytest.mark.parametrize(
    ("ids", "match"),
    [([], "at least one"), (["pc_lyra", "pc_lyra"], "repeated"), (["npc_ghost"], "unknown")],
)
def test_bad_encounter_lists_raise(exploring: GameState, ids: list[str], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        start_encounter(exploring, DiceRoller(1), ids)


def test_starting_during_an_encounter_raises(mid_combat: GameState) -> None:
    with pytest.raises(ValueError, match="already active"):
        start_encounter(mid_combat, DiceRoller(1), ENCOUNTER)


# --- turn advance and round wrap (rule suite) --------------------------------


def test_advance_moves_to_the_next_in_order(mid_combat: GameState) -> None:
    # Order: npc_rat_01, pc_lyra, npc_rat_02; pc_lyra is active in round 3.
    step = advance_initiative(mid_combat)
    assert mid_combat.active_combatant_id == "npc_rat_02"
    assert mid_combat.round_number == 3
    # Same step as the first initiative_advance in the valid audit example.
    example = json.loads((EXAMPLES / "audit_turn_valid.json").read_text(encoding="utf-8"))
    assert step.to_dict() == example["engine_steps"][0]


def test_wrapping_the_order_increments_the_round(mid_combat: GameState) -> None:
    mid_combat.active_combatant_id = "npc_rat_02"
    step = advance_initiative(mid_combat)
    assert mid_combat.active_combatant_id == "npc_rat_01"
    assert mid_combat.round_number == 4
    STEP_VALIDATOR.validate(step.to_dict())
    assert [c.path for c in step.state_diff] == ["active_combatant_id", "round_number"]


def test_advance_skips_an_unconscious_combatant(mid_combat: GameState) -> None:
    mid_combat.active_combatant_id = "npc_rat_01"
    _knock_out(mid_combat, "pc_lyra")
    advance_initiative(mid_combat)
    assert mid_combat.active_combatant_id == "npc_rat_02"
    assert mid_combat.initiative_order == ["npc_rat_01", "pc_lyra", "npc_rat_02"]


def test_skipping_across_the_wrap_increments_the_round_once(mid_combat: GameState) -> None:
    mid_combat.active_combatant_id = "npc_rat_02"
    _knock_out(mid_combat, "npc_rat_01")
    advance_initiative(mid_combat)
    assert mid_combat.active_combatant_id == "pc_lyra"
    assert mid_combat.round_number == 4


def test_sole_conscious_combatant_takes_the_next_round(mid_combat: GameState) -> None:
    _knock_out(mid_combat, "npc_rat_01")
    _knock_out(mid_combat, "npc_rat_02")
    advance_initiative(mid_combat)
    assert mid_combat.active_combatant_id == "pc_lyra"
    assert mid_combat.round_number == 4


def test_a_full_cycle_returns_to_the_first_actor_one_round_later(mid_combat: GameState) -> None:
    for _ in mid_combat.initiative_order:
        advance_initiative(mid_combat)
    assert mid_combat.active_combatant_id == "pc_lyra"
    assert mid_combat.round_number == 4
    _assert_valid(mid_combat)


def test_advance_outside_an_encounter_raises(exploring: GameState) -> None:
    with pytest.raises(ValueError, match="no active encounter"):
        advance_initiative(exploring)


# --- attack resolution (WBS 4.5, rule suite) ---------------------------------
# In state_02_mid_combat Lyra (short sword: +5, 1d6+3) is active and the rats
# have AC 12. npc_rat_01 is at 4 of 11 HP; npc_rat_02 is at 11 of 11 and Dodging.


def _seed_for(*dice: tuple[int, int]) -> int:
    """A seed whose first draws are the given `(sides, value)` dice, in order."""
    for seed in range(200_000):
        roller = DiceRoller(seed)
        if all(roller.roll(f"1d{sides}").total == value for sides, value in dice):
            return seed
    raise AssertionError(f"no seed found for {dice}")


def _sword(state: GameState, target_id: str, seed: int) -> AttackOutcome:
    return attack(state, DiceRoller(seed), "pc_lyra", target_id, "item_short_sword")


def _result(outcome: AttackOutcome) -> dict:
    return {"ok": True, "tool": "attack", **outcome.to_dict()}


def test_attack_reproduces_the_contract_example(mid_combat: GameState) -> None:
    mid_combat.combatants["npc_rat_01"].current_hp = 11
    outcome = _sword(mid_combat, "npc_rat_01", _seed_for((20, 12), (6, 4)))
    example = json.loads((EXAMPLES / "result_attack.json").read_text(encoding="utf-8"))
    assert _result(outcome) == example
    RESULT_VALIDATOR.validate(_result(outcome))
    assert mid_combat.combatants["npc_rat_01"].current_hp == 4
    _assert_valid(mid_combat)


def test_attack_total_equal_to_ac_hits(mid_combat: GameState) -> None:
    # 7 + 5 = 12, exactly the rat's AC.
    outcome = _sword(mid_combat, "npc_rat_01", _seed_for((20, 7)))
    assert outcome.facts.attack_roll == 12
    assert outcome.facts.hit is True
    assert outcome.facts.critical is False
    assert len(outcome.rolls) == 2


def test_attack_below_ac_misses_and_changes_nothing(mid_combat: GameState) -> None:
    before = mid_combat.to_dict()
    outcome = _sword(mid_combat, "npc_rat_01", _seed_for((20, 6)))
    assert outcome.facts.attack_roll == 11
    assert outcome.facts.hit is False
    assert outcome.facts.damage == 0
    assert outcome.facts.target_hp_after == outcome.facts.target_hp_before == 4
    assert outcome.state_diff == []
    assert len(outcome.rolls) == 1  # no damage roll on a miss
    assert mid_combat.to_dict() == before
    RESULT_VALIDATOR.validate(_result(outcome))


def test_natural_20_hits_any_ac_and_is_critical(mid_combat: GameState) -> None:
    mid_combat.combatants["npc_rat_01"].armour_class = 30
    outcome = _sword(mid_combat, "npc_rat_01", _seed_for((20, 20)))
    assert outcome.facts.attack_roll == 25
    assert outcome.facts.hit is True
    assert outcome.facts.critical is True


def test_natural_1_misses_whatever_the_bonus(mid_combat: GameState) -> None:
    mid_combat.item_definitions["item_short_sword"].attack_bonus = 30
    outcome = _sword(mid_combat, "npc_rat_01", _seed_for((20, 1)))
    assert outcome.facts.attack_roll == 31
    assert outcome.facts.hit is False
    assert outcome.facts.damage == 0


def test_critical_doubles_the_dice_and_not_the_modifier(mid_combat: GameState) -> None:
    mid_combat.combatants["npc_rat_01"].current_hp = 11
    outcome = _sword(mid_combat, "npc_rat_01", _seed_for((20, 20), (6, 2), (6, 3)))
    damage_roll = outcome.rolls[1]
    assert damage_roll.notation == "2d6+3"
    assert damage_roll.individual_dice == [2, 3]
    assert damage_roll.modifier == 3
    assert outcome.facts.damage == 2 + 3 + 3  # the +3 once, not twice
    assert mid_combat.combatants["npc_rat_01"].current_hp == 3
    RESULT_VALIDATOR.validate(_result(outcome))


def test_damage_past_zero_clamps_and_knocks_out(mid_combat: GameState) -> None:
    outcome = _sword(mid_combat, "npc_rat_01", _seed_for((20, 15), (6, 6)))
    rat = mid_combat.combatants["npc_rat_01"]
    assert outcome.facts.damage == 9
    assert rat.current_hp == 0
    assert rat.status == "unconscious"
    assert outcome.facts.target_hp_after == 0
    assert outcome.facts.target_hp_band == "unconscious"
    assert outcome.facts.target_status == "unconscious"
    assert [(c.path, c.from_, c.to) for c in outcome.state_diff] == [
        ("combatants.npc_rat_01.current_hp", 4, 0),
        ("combatants.npc_rat_01.status", "active", "unconscious"),
    ]
    RESULT_VALIDATOR.validate(_result(outcome))
    _assert_valid(mid_combat)


def test_damage_is_never_negative(mid_combat: GameState) -> None:
    mid_combat.item_definitions["item_short_sword"].damage_bonus = -5
    outcome = _sword(mid_combat, "npc_rat_01", _seed_for((20, 15), (6, 1)))
    assert outcome.facts.hit is True
    assert outcome.rolls[1].total == -4
    assert outcome.facts.damage == 0
    assert outcome.state_diff == []
    assert mid_combat.combatants["npc_rat_01"].current_hp == 4


def test_attack_on_a_dodging_target_has_disadvantage(mid_combat: GameState) -> None:
    outcome = _sword(mid_combat, "npc_rat_02", _seed_for((20, 18), (20, 3)))
    roll = outcome.rolls[0]
    assert roll.advantage_mode == "disadvantage"
    assert roll.individual_dice == [18, 3]
    assert outcome.facts.attack_roll == 8
    assert outcome.facts.advantage_mode == "disadvantage"
    assert outcome.facts.hit is False


def test_natural_20_is_judged_after_disadvantage_selection(mid_combat: GameState) -> None:
    mid_combat.combatants["npc_rat_02"].armour_class = 30
    outcome = _sword(mid_combat, "npc_rat_02", _seed_for((20, 20), (20, 5)))
    assert outcome.facts.critical is False
    assert outcome.facts.hit is False


def test_attacker_may_target_itself(mid_combat: GameState) -> None:
    outcome = _sword(mid_combat, "pc_lyra", 1)
    assert outcome.facts.target == "Lyra"
    assert outcome.facts.target_ac == 14
    _assert_valid(mid_combat)


def test_same_seed_gives_the_same_attack(mid_combat: GameState) -> None:
    results = [
        _sword(mid_combat.model_copy(deep=True), "npc_rat_01", 99).to_dict() for _ in range(2)
    ]
    assert results[0] == results[1]


def test_attacking_an_unconscious_target_raises(mid_combat: GameState) -> None:
    _knock_out(mid_combat, "npc_rat_01")
    with pytest.raises(ValueError, match="unconscious"):
        _sword(mid_combat, "npc_rat_01", 1)


def test_attacking_with_a_non_weapon_raises(mid_combat: GameState) -> None:
    with pytest.raises(ValueError, match="not a weapon"):
        attack(mid_combat, DiceRoller(1), "pc_lyra", "npc_rat_01", "item_torch")


# --- hit-point bands (CLAUDE.md section 10.2) --------------------------------


@pytest.mark.parametrize(
    ("current", "maximum", "band"),
    [
        (20, 20, "healthy"),
        (16, 20, "healthy"),
        (15, 20, "wounded"),  # 0.75 exactly
        (14, 20, "wounded"),  # the CLAUDE.md section 10.2 example
        (4, 11, "wounded"),  # 0.36
        (7, 20, "badly_hurt"),  # 0.35 exactly
        (1, 20, "badly_hurt"),
        (0, 20, "unconscious"),
    ],
)
def test_hp_band_thresholds(current: int, maximum: int, band: str) -> None:
    assert hp_band(current, maximum) == band
