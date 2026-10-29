"""The post-write invariant assertion (WBS 5.4): an illegal state raises rather
than persists.

`check_state` (adm/engine/state.py) runs the state schema and its cross-field
rules. The write path in adm/engine/tools.py runs it after every write. The
sabotage tests make a write produce an illegal state with a diff that accounts
for it, so only `check_state` can catch it. Each one checks that the write
raises `IllegalState` and that the state is put back exactly as it was. The
session tests play every scenario's encounters through the write path, so
every write of a real fight is checked, including s08's second encounter after
a victory.

Run: pytest tests/engine/test_invariants.py -v
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import adm.engine.tools as tools
from adm.engine.audit import UnrecordedWrite
from adm.engine.combat import EngineStep, StateChange, start_encounter
from adm.engine.dice import DiceRoller
from adm.engine.npc import choose_action
from adm.engine.state import (
    GameState,
    IllegalState,
    StateValidationError,
    check_state,
    load_state,
    save_state,
)
from adm.engine.tools import after_call, dispatch, increment_turn, open_encounter

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "schemas" / "examples"
SCENARIOS = sorted((ROOT / "scenarios").glob("*.json"))
STATES = sorted(EXAMPLES.glob("state_*.json"))
ENCOUNTER = ["pc_lyra", "npc_rat_01", "npc_rat_02"]
DODGE = {"tool": "dodge", "arguments": {"actor_id": "pc_lyra"}}

Doc = dict[str, Any]


@pytest.fixture
def mid_combat() -> GameState:
    return load_state(EXAMPLES / "state_02_mid_combat.json")


@pytest.fixture
def exploring() -> GameState:
    return load_state(EXAMPLES / "state_01_exploration.json")


# --- check_state -------------------------------------------------------------


@pytest.mark.parametrize("path", STATES, ids=lambda p: p.stem)
def test_the_example_states_are_legal(path: Path) -> None:
    check_state(load_state(path))


@pytest.mark.parametrize("path", SCENARIOS, ids=lambda p: p.stem)
def test_every_scenario_starts_legal(path: Path) -> None:
    state, _ = _scenario_state(path)
    check_state(state)


ILLEGAL: dict[str, Callable[[GameState], None]] = {
    "hp_above_max": lambda s: setattr(s.combatants["pc_lyra"], "current_hp", 21),
    "negative_hp": lambda s: setattr(s.combatants["pc_lyra"], "current_hp", -1),
    "zero_hp_but_active": lambda s: setattr(s.combatants["npc_rat_01"], "current_hp", 0),
    "negative_slots": lambda s: setattr(s.combatants["pc_lyra"], "spell_slots_1", -1),
    "negative_quantity": lambda s: s.inventory["pc_lyra"].update(item_torch=-1),
    "undefined_item_held": lambda s: s.inventory["pc_lyra"].update(item_lantern=1),
    "stage_beyond_max": lambda s: setattr(s.quests["quest_missing_ledger"], "stage", 4),
    "stance_off_its_history": lambda s: setattr(
        s.npc_relationships["npc_keeper"], "stance", "allied"
    ),
    "active_not_in_order": lambda s: setattr(s, "active_combatant_id", "npc_ghost"),
    "outcome_during_encounter": lambda s: setattr(s, "encounter_outcome", "victory"),
    "defeat_with_a_conscious_pc": lambda s: (
        setattr(s, "encounter_active", False),
        setattr(s, "initiative_order", []),
        setattr(s, "active_combatant_id", None),
        setattr(s, "encounter_outcome", "defeat"),
    ),
}


@pytest.mark.parametrize("mutate", ILLEGAL.values(), ids=ILLEGAL)
def test_check_state_raises_on_an_illegal_state(
    mid_combat: GameState, mutate: Callable[[GameState], None]
) -> None:
    mutate(mid_combat)
    with pytest.raises(IllegalState, match="illegal state after a write"):
        check_state(mid_combat)


def test_an_illegal_state_is_a_state_validation_error() -> None:
    assert issubclass(IllegalState, StateValidationError)


@pytest.mark.parametrize("mutate", ILLEGAL.values(), ids=ILLEGAL)
def test_an_illegal_state_is_never_saved(
    mid_combat: GameState, mutate: Callable[[GameState], None], tmp_path: Path
) -> None:
    mutate(mid_combat)
    path = tmp_path / "state.json"
    with pytest.raises(StateValidationError):
        save_state(mid_combat, path)
    assert not path.exists()


def test_an_illegal_state_file_does_not_load(tmp_path: Path) -> None:
    data = json.loads((EXAMPLES / "state_02_mid_combat.json").read_text(encoding="utf-8"))
    data["combatants"]["pc_lyra"]["current_hp"] = 25
    path = tmp_path / "state.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(StateValidationError, match="current_hp 25 outside"):
        load_state(path)


# --- the write path: an illegal state raises rather than persists ------------


def _diff(path: str, before: Any, after: Any) -> Doc:
    return {"path": path, "from": before, "to": after}


def _also(change: Callable[[GameState], Doc]) -> Callable[..., Doc]:
    """The dodge executor, changed to also make `change` and report it in its
    diff, so that the diff check passes and only the state check can object."""
    executor = tools.DISPATCH["dodge"]

    def sabotaged(state: GameState, roller: DiceRoller, a: Doc, mode: Any) -> Doc:
        outcome = executor(state, roller, a, mode)
        outcome["state_diff"].append(change(state))
        return outcome

    return sabotaged


def _heal_past_max(state: GameState) -> Doc:
    state.combatants["pc_lyra"].current_hp = 25
    return _diff("combatants.pc_lyra.current_hp", 14, 25)


def _overspend_slots(state: GameState) -> Doc:
    state.combatants["pc_lyra"].spell_slots_1 = -1
    return _diff("combatants.pc_lyra.spell_slots_1", 2, -1)


def _skip_a_stage(state: GameState) -> Doc:
    state.quests["quest_missing_ledger"].stage = 4
    return _diff("quests.quest_missing_ledger.stage", 2, 4)


def _drop_hp_but_stay_active(state: GameState) -> Doc:
    state.combatants["npc_rat_01"].current_hp = 0
    return _diff("combatants.npc_rat_01.current_hp", 4, 0)


SABOTAGE = {
    "hp_above_max": (_heal_past_max, "current_hp 25 outside"),
    "negative_slots": (_overspend_slots, "spell_slots_1"),
    "stage_beyond_max": (_skip_a_stage, "stage 4 beyond max_stage"),
    "zero_hp_but_active": (_drop_hp_but_stay_active, "npc_rat_01"),
}


@pytest.mark.parametrize("change,reason", SABOTAGE.values(), ids=SABOTAGE)
def test_a_tool_that_leaves_an_illegal_state_raises_and_is_undone(
    mid_combat: GameState,
    monkeypatch: pytest.MonkeyPatch,
    change: Callable[[GameState], Doc],
    reason: str,
) -> None:
    monkeypatch.setitem(tools.DISPATCH, "dodge", _also(change))
    before = mid_combat.to_dict()
    with pytest.raises(IllegalState, match=reason):
        dispatch(mid_combat, DiceRoller(7), DODGE)
    assert mid_combat.to_dict() == before


def test_an_engine_step_that_leaves_an_illegal_state_raises_and_is_undone(
    mid_combat: GameState, monkeypatch: pytest.MonkeyPatch
) -> None:
    def sabotaged(state: GameState, roller: DiceRoller) -> list[EngineStep]:
        state.active_combatant_id = "npc_ghost"
        change = StateChange(path="active_combatant_id", from_="pc_lyra", to="npc_ghost")
        return [
            EngineStep(step="initiative_advance", when="after_call", state_diff=[change], rolls=[])
        ]

    monkeypatch.setattr(tools, "after_player_action", sabotaged)
    before = mid_combat.to_dict()
    with pytest.raises(IllegalState, match="npc_ghost is not in initiative_order"):
        after_call(mid_combat, DiceRoller(7), "attack")
    assert mid_combat.to_dict() == before


def test_an_encounter_start_that_leaves_an_illegal_state_raises_and_is_undone(
    exploring: GameState, monkeypatch: pytest.MonkeyPatch
) -> None:
    def sabotaged(state: GameState, roller: DiceRoller, ids: list[str]) -> EngineStep:
        step = start_encounter(state, roller, ids)
        state.encounter_outcome = "victory"
        change = StateChange(path="encounter_outcome", from_=None, to="victory")
        return step.model_copy(update={"state_diff": [*step.state_diff, change]})

    monkeypatch.setattr(tools, "start_encounter", sabotaged)
    before = exploring.to_dict()
    with pytest.raises(IllegalState):
        open_encounter(exploring, DiceRoller(7), ENCOUNTER)
    assert exploring.to_dict() == before


def test_an_unrecorded_write_is_undone_too(
    mid_combat: GameState, monkeypatch: pytest.MonkeyPatch
) -> None:
    executor = tools.DISPATCH["dodge"]

    def silent(state: GameState, roller: DiceRoller, a: Doc, mode: Any) -> Doc:
        outcome = executor(state, roller, a, mode)
        state.round_number = 9
        return outcome

    monkeypatch.setitem(tools.DISPATCH, "dodge", silent)
    before = mid_combat.to_dict()
    with pytest.raises(UnrecordedWrite):
        dispatch(mid_combat, DiceRoller(7), DODGE)
    assert mid_combat.to_dict() == before


def test_an_engine_guard_that_raises_mid_write_is_undone(
    mid_combat: GameState, monkeypatch: pytest.MonkeyPatch
) -> None:
    def half_done(state: GameState, roller: DiceRoller, a: Doc, mode: Any) -> Doc:
        state.combatants["pc_lyra"].dodging = True
        raise ValueError("an engine guard fired")

    monkeypatch.setitem(tools.DISPATCH, "dodge", half_done)
    before = mid_combat.to_dict()
    with pytest.raises(ValueError, match="engine guard"):
        dispatch(mid_combat, DiceRoller(7), DODGE)
    assert mid_combat.to_dict() == before


def test_a_legal_write_is_kept(mid_combat: GameState) -> None:
    entry = dispatch(mid_combat, DiceRoller(7), DODGE)
    assert entry["ok"]
    assert mid_combat.combatants["pc_lyra"].dodging is True
    increment_turn(mid_combat)
    assert mid_combat.turn_number == 8


# --- whole scenarios through the write path ----------------------------------


def _scenario_state(path: Path, seed: int = 0) -> tuple[GameState, Doc]:
    scenario = json.loads(path.read_text(encoding="utf-8"))
    state = GameState.from_dict(
        {
            "schema_version": scenario["schema_version"],
            "scenario_id": scenario["scenario_id"],
            "seed": seed,
            "turn_number": 0,
            "round_number": 0,
            "active_combatant_id": None,
            "initiative_order": [],
            "encounter_active": False,
            "encounter_outcome": None,
            **scenario["initial_state"],
        }
    )
    return state, scenario


def _play(path: Path, seed: int) -> GameState:
    """Play every encounter of a scenario through the write path: the player
    character takes the action the NPC policy would take for it."""
    state, scenario = _scenario_state(path, seed)
    roller = DiceRoller(seed)
    for encounter in scenario["encounters"]:
        if state.combatants[_pc(state)].status != "active":
            break  # a defeat ends the scenario's fighting
        open_encounter(state, roller, encounter["combatant_ids"])
        for _ in range(300):
            if not state.encounter_active:
                break
            call = choose_action(state, _pc(state))
            entry = dispatch(state, roller, call.model_dump(mode="json"))
            assert entry["ok"], entry
            after_call(state, roller, call.tool)
            increment_turn(state)
        else:
            raise AssertionError("the fight did not end")
        assert state.encounter_outcome in ("victory", "defeat")
        check_state(state)
    return state


def _pc(state: GameState) -> str:
    return next(cid for cid, c in state.combatants.items() if c.is_player_character)


@pytest.mark.parametrize("path", SCENARIOS, ids=lambda p: p.stem)
def test_every_scenario_plays_through_without_an_illegal_state(path: Path) -> None:
    _play(path, seed=12345)


def test_a_victory_before_a_later_encounter_is_legal() -> None:
    # s08_old_mine: the kobolds, then the spider. Between the two the state is
    # `victory` with the spider still active, which is legal (WBS 5.4).
    path = ROOT / "scenarios" / "s08_old_mine.json"
    for seed in range(50):
        state, scenario = _scenario_state(path, seed)
        roller = DiceRoller(seed)
        open_encounter(state, roller, scenario["encounters"][0]["combatant_ids"])
        while state.encounter_active:
            call = choose_action(state, _pc(state))
            dispatch(state, roller, call.model_dump(mode="json"))
            after_call(state, roller, call.tool)
            increment_turn(state)
        if state.encounter_outcome == "victory":
            assert state.combatants["npc_giant_spider"].status == "active"
            check_state(state)
            return
    raise AssertionError("no seed wins the first encounter")


@settings(max_examples=40, deadline=None)
@given(
    path=st.sampled_from(SCENARIOS),
    seed=st.integers(0, 1_000_000),
)
def test_any_seed_plays_through_without_an_illegal_state(path: Path, seed: int) -> None:
    state = _play(path, seed)
    check_state(state)
