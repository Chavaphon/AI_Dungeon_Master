"""In-game slash commands (WBS 13.1): what each command shows, read from the
state it is given, which it never changes; in beginner mode (WBS 13.2), with
no jargon.

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
from adm.play.vocabulary import JARGON, Mode

ROOT = Path(__file__).resolve().parents[2]
SCENARIO = load_scenario(ROOT / "scenarios" / "s01_cellar.json")
SEED = 12345


def _state() -> GameState:
    return initial_state(SCENARIO, SEED)


def _show(text: str, state: GameState, mode: Mode = Mode.VETERAN) -> str:
    out = io.StringIO()
    renderable = run_command(text, state, mode).renderable
    Console(file=out, width=120, color_system=None).print(renderable)
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
    result = run_command(text, _state(), Mode.BEGINNER)
    assert not result.quit
    assert _show(text, _state()).strip() == UNKNOWN


@pytest.mark.parametrize("text", sorted(QUIT))
def test_quit_ends_the_session(text: str) -> None:
    assert run_command(text, _state(), Mode.BEGINNER).quit


@pytest.mark.parametrize("mode", list(Mode))
def test_rules_never_claim_5e(mode: Mode) -> None:
    out = _show("/rules", _state(), mode) + _show("/glossary", _state(), mode)
    assert "5e" not in out and "inspired by" in out


@pytest.mark.parametrize("text", [*COMMANDS, "/quit", "/nope"])
def test_no_command_changes_the_state(text: str) -> None:
    state = _state()
    open_encounter(state, DiceRoller(SEED), SCENARIO.encounters[0].combatant_ids)
    before = state_hash(state)
    for mode in Mode:
        _show(text, state, mode)
    assert state_hash(state) == before


# --- beginner mode (WBS 13.2) --------------------------------------------------


def _fight() -> GameState:
    state = _state()
    open_encounter(state, DiceRoller(SEED), SCENARIO.encounters[0].combatant_ids)
    state.combatants["pc_lyra"].dodging = True
    return state


@pytest.mark.parametrize("text", [*COMMANDS, "/quit", "/nope"])
@pytest.mark.parametrize("state", [_state, _fight], ids=["outside", "in_a_fight"])
def test_no_beginner_command_shows_jargon(text: str, state: object) -> None:
    out = _show(text, state(), Mode.BEGINNER)  # type: ignore[operator]
    assert JARGON.search(out) is None, out


def test_beginner_status_shows_health_in_words() -> None:
    out = _show("/status", _fight(), Mode.BEGINNER)
    assert "Lyra: healthy" in out
    assert "Spell charges for Cure Wounds: 2. Fire Bolt is a spell you can always cast." in out
    assert "giant rat 1: healthy" in out and "Turn order:" in out


def test_veteran_status_keeps_the_numbers() -> None:
    out = _show("/status", _fight(), Mode.VETERAN)
    assert "HP (healthy)" in out and "Spell slots for Cure Wounds: 2." in out


@pytest.mark.parametrize("text", ["/rules", "/glossary"])
def test_beginner_and_veteran_rules_differ(text: str) -> None:
    assert _show(text, _state(), Mode.BEGINNER) != _show(text, _state(), Mode.VETERAN)
