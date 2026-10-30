"""Scenario loader and encounter schedule (WBS 6.10): every scenario loads into
a legal turn-0 state, and encounters start before their input, in order, one at
a time, waiting while the one before is still active.

Run: pytest tests/engine/test_scenario.py -v
"""

import json
from pathlib import Path

import pytest

from adm.engine.dice import DiceRoller
from adm.engine.scenario import (
    Encounter,
    ScenarioValidationError,
    due_encounter,
    initial_state,
    load_scenario,
)
from adm.engine.state import GameState
from adm.engine.tools import open_encounter

ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = sorted((ROOT / "scenarios").glob("*.json"))
EXAMPLE = ROOT / "schemas" / "examples" / "scenario_s00_example.json"
S01 = ROOT / "scenarios" / "s01_cellar.json"
SEED = 12345


@pytest.mark.parametrize("path", [EXAMPLE, *SCENARIOS], ids=lambda p: p.stem)
def test_every_scenario_loads_into_a_turn_0_state(path: Path) -> None:
    scenario = load_scenario(path)
    state = initial_state(scenario, SEED)
    assert (state.scenario_id, state.seed) == (scenario.scenario_id, SEED)
    assert (state.turn_number, state.round_number) == (0, 0)
    assert not state.encounter_active
    assert state.initiative_order == [] and state.active_combatant_id is None
    assert state.encounter_outcome is None
    data = state.to_dict()
    assert {k: data[k] for k in scenario.initial_state} == scenario.initial_state


def test_initial_state_does_not_share_the_scenarios_maps() -> None:
    scenario = load_scenario(S01)
    state = initial_state(scenario, SEED)
    state.inventory["pc_lyra"]["item_torch"] = 0
    assert scenario.initial_state["inventory"]["pc_lyra"]["item_torch"] == 2


def test_a_scenario_that_breaks_the_schema_is_refused(tmp_path: Path) -> None:
    data = json.loads(S01.read_text(encoding="utf-8"))
    del data["opening_narration"]
    path = tmp_path / "s01_cellar.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ScenarioValidationError, match="opening_narration"):
        load_scenario(path)


# --- the encounter schedule ---

FIRST = Encounter(before_input=3, combatant_ids=["pc_lyra", "npc_rat_01"])
SECOND = Encounter(before_input=5, combatant_ids=["pc_lyra", "npc_rat_02"])


def _state() -> GameState:
    return initial_state(load_scenario(S01), SEED)


def test_an_encounter_starts_before_its_input_and_not_earlier() -> None:
    state = _state()
    assert [due_encounter([FIRST], 0, i, state) for i in range(3)] == [None] * 3
    assert due_encounter([FIRST], 0, 3, state) == FIRST


def test_encounters_start_in_order_and_once() -> None:
    state = _state()
    assert due_encounter([FIRST, SECOND], 0, 6, state) == FIRST, "the first waits for none"
    assert due_encounter([FIRST, SECOND], 1, 6, state) == SECOND
    assert due_encounter([FIRST, SECOND], 2, 6, state) is None


def test_a_due_encounter_waits_while_one_is_active() -> None:
    state = _state()
    open_encounter(state, DiceRoller(SEED), FIRST.combatant_ids)
    assert state.encounter_active
    assert due_encounter([FIRST, SECOND], 1, 5, state) is None
    state.encounter_active = False  # as if it had ended; the schedule only reads it
    assert due_encounter([FIRST, SECOND], 1, 9, state) == SECOND, "it starts once that one ends"
