"""Initiative, turn order, tie-break and round advance (WBS 4.4, CLAUDE.md section 4.4).

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
    InitiativeEntry,
    advance_initiative,
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
