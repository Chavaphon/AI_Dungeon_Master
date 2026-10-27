"""Engine-controlled NPC turns (WBS 4.19, docs/npc_policy.md).

The policy tests change one thing in a known state and check the chosen call.
The turn tests roll with a real seeded `DiceRoller` and look for a seed that
gives the case they need. The whole-fight tests play the first encounter of
every scenario to its end, with the player character attacking.

Run: pytest tests/engine/test_npc.py -v
"""

import json
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from adm.engine.combat import EngineStep, attack, dodge, start_encounter
from adm.engine.dice import DiceRoller
from adm.engine.npc import (
    NpcActionStep,
    after_player_action,
    choose_action,
    run_npc_turns,
    take_npc_turn,
)
from adm.engine.state import GameState, load_state

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "schemas" / "examples"
SCENARIOS = sorted((ROOT / "scenarios").glob("*.json"))
ENCOUNTER = ["pc_lyra", "npc_rat_01", "npc_rat_02"]

_SCHEMAS = [
    json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))
    for name in ("state.schema.json", "tools.schema.json", "audit.schema.json")
]
_REGISTRY = Registry().with_resources((s["$id"], Resource.from_contents(s)) for s in _SCHEMAS)
STEP_VALIDATOR = Draft202012Validator(
    {"$ref": _SCHEMAS[2]["$id"] + "#/$defs/engine_step"}, registry=_REGISTRY
)

Step = EngineStep | NpcActionStep


@pytest.fixture
def exploring() -> GameState:
    return load_state(EXAMPLES / "state_01_exploration.json")


@pytest.fixture
def mid_combat() -> GameState:
    # Order npc_rat_01, pc_lyra, npc_rat_02; Lyra (14 of 20, AC 14) is active in
    # round 3. npc_rat_01 is at 4 of 11; npc_rat_02 is at 11 of 11 and Dodging.
    return load_state(EXAMPLES / "state_02_mid_combat.json")


def _seed_for(*dice: tuple[int, int]) -> int:
    """A seed whose first draws are the given `(sides, value)` dice, in order."""
    for seed in range(200_000):
        roller = DiceRoller(seed)
        if all(roller.roll(f"1d{sides}").total == value for sides, value in dice):
            return seed
    raise AssertionError(f"no seed found for {dice}")


def _knock_out(state: GameState, combatant_id: str) -> None:
    state.combatants[combatant_id].current_hp = 0
    state.combatants[combatant_id].status = "unconscious"


def _assert_legal(state: GameState) -> None:
    for c in state.combatants.values():
        assert 0 <= c.current_hp <= c.max_hp
        assert (c.status == "unconscious") == (c.current_hp == 0)
    GameState.from_dict(state.to_dict())


def _validate(steps: list[Step]) -> None:
    for step in steps:
        STEP_VALIDATOR.validate(step.to_dict())


def _npc_calls(steps: list[Step]) -> list[tuple[str, dict[str, str]]]:
    return [(s.call.tool, s.call.arguments) for s in steps if isinstance(s, NpcActionStep)]


# --- the policy --------------------------------------------------------------


def test_a_hostile_attacks_the_player_character_with_its_weapon(mid_combat: GameState) -> None:
    call = choose_action(mid_combat, "npc_rat_01")
    assert call.tool == "attack"
    assert call.arguments == {
        "attacker_id": "npc_rat_01",
        "target_id": "pc_lyra",
        "weapon_id": "item_rat_bite",
    }


def test_the_target_is_the_opponent_with_the_lowest_hp(mid_combat: GameState) -> None:
    # npc_rat_02 joins the party: npc_rat_01 now has two opponents.
    mid_combat.combatants["npc_rat_02"].faction = "party"
    assert choose_action(mid_combat, "npc_rat_01").arguments["target_id"] == "npc_rat_02"
    mid_combat.combatants["npc_rat_02"].current_hp = 3
    mid_combat.combatants["pc_lyra"].current_hp = 2
    assert choose_action(mid_combat, "npc_rat_01").arguments["target_id"] == "pc_lyra"


def test_an_hp_tie_breaks_on_the_smaller_id(mid_combat: GameState) -> None:
    mid_combat.combatants["npc_rat_02"].faction = "party"
    mid_combat.combatants["npc_rat_02"].current_hp = 14  # Lyra is at 14 too
    assert choose_action(mid_combat, "npc_rat_01").arguments["target_id"] == "npc_rat_02"


def test_a_party_npc_attacks_the_hostiles(mid_combat: GameState) -> None:
    mid_combat.combatants["npc_rat_02"].faction = "party"
    call = choose_action(mid_combat, "npc_rat_02")
    assert call.tool == "attack"
    assert call.arguments["target_id"] == "npc_rat_01"


def test_unconscious_opponents_are_never_targeted(mid_combat: GameState) -> None:
    mid_combat.combatants["npc_rat_02"].faction = "party"
    _knock_out(mid_combat, "npc_rat_02")
    assert choose_action(mid_combat, "npc_rat_01").arguments["target_id"] == "pc_lyra"


def test_only_combatants_in_the_encounter_are_targets(exploring: GameState) -> None:
    # npc_rat_02 is kept for a later encounter; as a party NPC it is not a target.
    exploring.combatants["npc_rat_02"].faction = "party"
    exploring.combatants["npc_rat_02"].current_hp = 1
    start_encounter(exploring, DiceRoller(1), ["pc_lyra", "npc_rat_01"])
    assert choose_action(exploring, "npc_rat_01").arguments["target_id"] == "pc_lyra"


@pytest.mark.parametrize(
    ("held", "weapon"),
    [
        ({"item_short_sword": 1, "item_rat_bite": 1}, "item_rat_bite"),  # sorted first
        ({"item_torch": 2, "item_short_sword": 1}, "item_short_sword"),  # not a weapon
        ({"item_rat_bite": 0, "item_short_sword": 1}, "item_short_sword"),  # not held
    ],
)
def test_the_weapon_is_the_first_held_weapon_in_id_order(
    mid_combat: GameState, held: dict[str, int], weapon: str
) -> None:
    mid_combat.inventory["npc_rat_01"] = held
    assert choose_action(mid_combat, "npc_rat_01").arguments["weapon_id"] == weapon


@pytest.mark.parametrize("held", [{}, {"item_torch": 1}, {"item_rat_bite": 0}])
def test_an_npc_with_no_weapon_dodges(mid_combat: GameState, held: dict[str, int]) -> None:
    mid_combat.inventory["npc_rat_01"] = held
    call = choose_action(mid_combat, "npc_rat_01")
    assert call.tool == "dodge"
    assert call.arguments == {"actor_id": "npc_rat_01"}


def test_an_npc_with_no_inventory_dodges(mid_combat: GameState) -> None:
    del mid_combat.inventory["npc_rat_01"]
    assert choose_action(mid_combat, "npc_rat_01").tool == "dodge"


def test_a_neutral_npc_dodges(mid_combat: GameState) -> None:
    mid_combat.combatants["npc_rat_01"].faction = "neutral"
    assert choose_action(mid_combat, "npc_rat_01").tool == "dodge"


def test_the_policy_changes_nothing(mid_combat: GameState) -> None:
    before = mid_combat.to_dict()
    choose_action(mid_combat, "npc_rat_01")
    assert mid_combat.to_dict() == before


# --- NPC turns ---------------------------------------------------------------


def test_npc_turns_reproduce_the_audit_example(mid_combat: GameState) -> None:
    # Lyra's sword has just taken npc_rat_02 from 11 to 3. Then npc_rat_02 bites
    # her (11 + 4 = 15 hits AC 14; 3 + 2 = 5 damage) and npc_rat_01 misses (6 + 4).
    mid_combat.combatants["npc_rat_02"].current_hp = 3
    seed = _seed_for((20, 11), (4, 3), (20, 6))
    steps = after_player_action(mid_combat, DiceRoller(seed))
    example = json.loads((EXAMPLES / "audit_turn_valid.json").read_text(encoding="utf-8"))
    assert [s.to_dict() for s in steps] == example["engine_steps"][:-1]  # less turn_increment
    _validate(steps)
    assert mid_combat.active_combatant_id == "pc_lyra"
    assert mid_combat.round_number == 4
    assert mid_combat.combatants["pc_lyra"].current_hp == 9
    _assert_legal(mid_combat)


def test_npcs_who_win_initiative_act_before_the_call(exploring: GameState) -> None:
    def first_actor(seed: int) -> str | None:
        state = exploring.model_copy(deep=True)
        start_encounter(state, DiceRoller(seed), ENCOUNTER)
        return state.active_combatant_id

    seed = next(s for s in range(1000) if first_actor(s) != "pc_lyra")
    roller = DiceRoller(seed)
    start_encounter(exploring, roller, ENCOUNTER)
    first = exploring.active_combatant_id
    steps = run_npc_turns(exploring, roller, "before_call")
    assert {s.when for s in steps} == {"before_call"}
    assert _npc_calls(steps)[0][1]["attacker_id"] == first
    assert exploring.active_combatant_id == "pc_lyra"
    _validate(steps)
    _assert_legal(exploring)


def test_no_npc_turns_when_the_player_character_acts_first(mid_combat: GameState) -> None:
    before = mid_combat.to_dict()
    assert run_npc_turns(mid_combat, DiceRoller(1), "before_call") == []
    assert mid_combat.to_dict() == before


def test_npc_turns_stop_at_defeat(mid_combat: GameState) -> None:
    mid_combat.combatants["pc_lyra"].current_hp = 1
    steps = after_player_action(mid_combat, DiceRoller(_seed_for((20, 15), (4, 1))))
    assert [s.step for s in steps] == [
        "initiative_advance",
        "dodge_expiry",
        "npc_action",
        "encounter_end",
    ]
    assert mid_combat.encounter_outcome == "defeat"
    assert mid_combat.encounter_active is False
    _validate(steps)
    _assert_legal(mid_combat)


def test_victory_on_the_players_action_runs_no_npc_turns(mid_combat: GameState) -> None:
    _knock_out(mid_combat, "npc_rat_01")
    _knock_out(mid_combat, "npc_rat_02")
    steps = after_player_action(mid_combat, DiceRoller(1))
    assert [s.step for s in steps] == ["encounter_end"]
    assert mid_combat.encounter_outcome == "victory"


def test_an_unconscious_npc_is_skipped(mid_combat: GameState) -> None:
    _knock_out(mid_combat, "npc_rat_02")
    steps = after_player_action(mid_combat, DiceRoller(1))
    assert [call[1]["attacker_id"] for call in _npc_calls(steps)] == ["npc_rat_01"]
    assert mid_combat.active_combatant_id == "pc_lyra"


def test_a_dodging_player_is_attacked_at_disadvantage_until_her_turn(
    mid_combat: GameState,
) -> None:
    dodge(mid_combat, "pc_lyra")
    steps = after_player_action(mid_combat, DiceRoller(7))
    attacks = [s.result for s in steps if isinstance(s, NpcActionStep)]
    assert [a["narration_facts"]["advantage_mode"] for a in attacks] == ["disadvantage"] * 2
    last = steps[-1]
    assert isinstance(last, EngineStep) and last.step == "dodge_expiry"
    assert [(c.path, c.to) for c in last.state_diff] == [("combatants.pc_lyra.dodging", False)]
    assert mid_combat.combatants["pc_lyra"].dodging is False


def test_an_npc_with_no_weapon_takes_the_dodge_action(mid_combat: GameState) -> None:
    mid_combat.active_combatant_id = "npc_rat_01"
    mid_combat.inventory["npc_rat_01"] = {}
    step = take_npc_turn(mid_combat, DiceRoller(1), "after_call")
    assert step.result == {
        "ok": True,
        "tool": "dodge",
        "narration_facts": {"actor": "giant rat"},
        "state_diff": [{"path": "combatants.npc_rat_01.dodging", "from": False, "to": True}],
        "rolls": [],
    }
    STEP_VALIDATOR.validate(step.to_dict())


def test_taking_the_player_characters_turn_raises(mid_combat: GameState) -> None:
    with pytest.raises(ValueError, match="player character"):
        take_npc_turn(mid_combat, DiceRoller(1), "after_call")


def test_taking_an_npc_turn_outside_an_encounter_raises(exploring: GameState) -> None:
    with pytest.raises(ValueError, match="no active encounter"):
        take_npc_turn(exploring, DiceRoller(1), "after_call")


# --- whole fights ------------------------------------------------------------


def _first_encounter(path: Path) -> tuple[GameState, list[str]]:
    scenario = json.loads(path.read_text(encoding="utf-8"))
    state = GameState.from_dict(
        {
            "schema_version": scenario["schema_version"],
            "scenario_id": scenario["scenario_id"],
            "seed": 0,
            "turn_number": 0,
            "round_number": 0,
            "active_combatant_id": None,
            "initiative_order": [],
            "encounter_active": False,
            "encounter_outcome": None,
            **scenario["initial_state"],
        }
    )
    return state, scenario["encounters"][0]["combatant_ids"]


def _fight(path: Path, seed: int) -> list[dict]:
    """Play the first encounter to its end: the PC attacks the target the NPC
    policy would pick for it, and the engine plays every NPC turn."""
    state, combatant_ids = _first_encounter(path)
    roller = DiceRoller(seed)
    steps: list[Step] = [start_encounter(state, roller, combatant_ids)]
    steps += run_npc_turns(state, roller, "before_call")
    for _ in range(200):
        if not state.encounter_active:
            break
        pc_id = state.active_combatant_id
        assert pc_id is not None and state.combatants[pc_id].is_player_character
        call = choose_action(state, pc_id)
        assert call.tool == "attack"
        attack(state, roller, **call.arguments)
        steps += after_player_action(state, roller)
        _assert_legal(state)
    else:
        raise AssertionError("the fight did not end")
    assert state.encounter_outcome in ("victory", "defeat")
    for step in steps:
        if isinstance(step, NpcActionStep) and step.call.tool == "attack":
            args = step.call.arguments
            assert state.inventory[args["attacker_id"]][args["weapon_id"]] > 0
    _validate(steps)
    return [s.to_dict() for s in steps]


@pytest.mark.parametrize("path", SCENARIOS, ids=[p.stem for p in SCENARIOS])
def test_every_scenario_fight_ends_and_replays_identically(path: Path) -> None:
    assert _fight(path, 12345) == _fight(path, 12345)


@settings(max_examples=50, deadline=None)
@given(seed=st.integers(min_value=0, max_value=2**32 - 1))
def test_any_seed_gives_a_legal_fight_that_ends(seed: int) -> None:
    _fight(ROOT / "scenarios" / "s01_cellar.json", seed)
