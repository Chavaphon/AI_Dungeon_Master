"""The status panel after each turn (WBS 13.5, #253): your health as a word and
a bar (numbers in veteran mode), spell charges and dodging; in a fight, the
round, whose turn it is and the turn order. It only reads the state.

Run: pytest tests/play/test_status.py -v
"""

import io
from pathlib import Path

import pytest
from rich.console import Console

from adm.engine.replay import replay_script
from adm.engine.scenario import initial_state, load_scenario
from adm.engine.state import GameState, state_hash
from adm.play.status import BAR_CELLS, EMPTY, FULL, TITLE, health_cells, status_panel
from adm.play.vocabulary import JARGON, Mode

ROOT = Path(__file__).resolve().parents[2]
S01 = load_scenario(ROOT / "scenarios" / "s01_cellar.json")
SEED = 12345


def _text(state: GameState, mode: Mode, *, bar: bool = True) -> str:
    console = Console(file=io.StringIO(), width=100, record=True)
    console.print(status_panel(state, mode, bar=bar))
    return console.export_text()


def _in_a_fight() -> GameState:
    for turn in replay_script(S01, SEED):
        state = GameState.from_dict(turn.state)
        if state.encounter_active:
            return state
    raise AssertionError("s01's fight never started")


def test_outside_a_fight() -> None:
    text = _text(initial_state(S01, SEED), Mode.BEGINNER)
    assert TITLE in text
    assert f"Lyra: healthy  {FULL * BAR_CELLS}" in text
    assert "Spell charges left for Cure Wounds: 2" in text
    assert "Turn order" not in text and "dodging" not in text


def test_in_a_fight() -> None:
    state = _in_a_fight()
    text = _text(state, Mode.BEGINNER)
    assert f"Fight, round {state.round_number}." in text
    assert "Turn order:" in text
    assert "giant rat 1:" in text and "giant rat 2:" in text, "shared names are numbered"
    assert " > " in text, "the active combatant is marked"


@pytest.mark.parametrize("state", [initial_state(S01, SEED), _in_a_fight()])
def test_beginner_shows_no_numbers_and_veteran_does(state: GameState) -> None:
    beginner, veteran = _text(state, Mode.BEGINNER), _text(state, Mode.VETERAN)
    assert JARGON.search(beginner) is None, JARGON.search(beginner)
    assert "/20 HP" in veteran
    assert "Spell slots left for Cure Wounds" in veteran


def test_dodging_is_shown() -> None:
    state = initial_state(S01, SEED)
    state.combatants["pc_lyra"].dodging = True
    assert "You are dodging" in _text(state, Mode.BEGINNER)


def test_a_non_caster_has_no_spell_line() -> None:
    scenario = load_scenario(ROOT / "scenarios" / "s02_toll_bridge.json")
    assert "Cure Wounds" not in _text(initial_state(scenario, SEED), Mode.BEGINNER)


def test_the_bar_can_be_left_out() -> None:
    text = _text(initial_state(S01, SEED), Mode.BEGINNER, bar=False)
    assert FULL not in text and EMPTY not in text
    assert "Lyra: healthy" in text


@pytest.mark.parametrize(("hp", "cells"), [(20, 10), (19, 10), (14, 7), (7, 4), (1, 1), (0, 0)])
def test_the_bar_is_in_proportion_and_never_empty_while_standing(hp: int, cells: int) -> None:
    assert health_cells(hp, 20) == cells


def test_the_panel_only_reads_the_state() -> None:
    for state in (initial_state(S01, SEED), _in_a_fight()):
        before = state_hash(state)
        for mode in Mode:
            _text(state, mode)
        assert state_hash(state) == before
