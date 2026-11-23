"""In-game slash commands (WBS 13.1): what each command shows, read from the
state it is given, which it never changes.

Run: pytest tests/play/test_commands.py -v
"""

import io
from pathlib import Path

import pytest
from rich.console import Console

from adm.engine.dice import DiceRoller
from adm.engine.scenario import initial_state, load_scenario
from adm.engine.state import GameState, state_hash
from adm.engine.tools import open_encounter
from adm.play.commands import COMMANDS, QUIT, UNKNOWN, combatant_labels, is_command, run_command

ROOT = Path(__file__).resolve().parents[2]
SCENARIO = load_scenario(ROOT / "scenarios" / "s01_cellar.json")
SEED = 12345


def _state() -> GameState:
    return initial_state(SCENARIO, SEED)


def _show(text: str, state: GameState) -> str:
    out = io.StringIO()
    Console(file=out, width=120, color_system=None).print(run_command(text, state).renderable)
    return out.getvalue()


def test_only_inputs_starting_with_a_slash_are_commands() -> None:
    assert is_command("/help") and is_command("/") and is_command("/nope")
    assert not is_command("I look around") and not is_command("look /help")


def test_inventory_lists_what_the_player_carries() -> None:
    out = _show("/inventory", _state())
    assert "short sword x1 (weapon)" in out
    assert "torch x2" in out and "torch x2 (weapon)" not in out
    assert "bite" not in out, "the rats' inventories are not the player's"


def test_quests_show_each_quest_and_its_state() -> None:
    out = _show("/quests", _state())
    assert "The Missing Ledger: not started" in out


def test_status_outside_a_fight() -> None:
    state = _state()
    pc = state.combatants["pc_lyra"]
    out = _show("/status", state)
    assert f"Lyra: {pc.current_hp}/{pc.max_hp} HP (healthy)" in out
    assert "No fight in progress." in out


def test_status_in_a_fight_shows_the_round_turn_and_order() -> None:
    state = _state()
    open_encounter(state, DiceRoller(SEED), SCENARIO.encounters[0].combatant_ids)
    out = _show("/status", state)
    labels = combatant_labels(state)
    assert labels["npc_rat_01"] == "giant rat 1" and labels["npc_rat_02"] == "giant rat 2"
    assert labels["pc_lyra"] == "Lyra", "a unique name is not numbered"
    assert f"round {state.round_number}. {labels[state.active_combatant_id]}'s turn." in out
    order = out[out.index("Turn order:") :]
    positions = [order.index(f" {labels[c]}: ") for c in state.initiative_order]
    assert positions == sorted(positions), "listed in initiative order"


def test_help_lists_every_command() -> None:
    out = _show("/help", _state())
    for name in [*COMMANDS, "/quit"]:
        assert name in out


@pytest.mark.parametrize("text", ["/HELP", "/help me please", "/Help"])
def test_the_command_word_ignores_case_and_arguments(text: str) -> None:
    assert _show(text, _state()) == _show("/help", _state())


@pytest.mark.parametrize("text", ["/nope", "/", "/helpme", "/ help"])
def test_an_unknown_command_says_so(text: str) -> None:
    result = run_command(text, _state())
    assert not result.quit
    assert _show(text, _state()).strip() == UNKNOWN


@pytest.mark.parametrize("text", sorted(QUIT))
def test_quit_ends_the_session(text: str) -> None:
    assert run_command(text, _state()).quit


def test_rules_never_claim_5e() -> None:
    out = _show("/rules", _state()) + _show("/glossary", _state())
    assert "5e" not in out and "inspired by" in out


@pytest.mark.parametrize("text", [*COMMANDS, "/quit", "/nope"])
def test_no_command_changes_the_state(text: str) -> None:
    state = _state()
    open_encounter(state, DiceRoller(SEED), SCENARIO.encounters[0].combatant_ids)
    before = state_hash(state)
    _show(text, state)
    assert state_hash(state) == before
