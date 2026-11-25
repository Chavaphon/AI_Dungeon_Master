"""The status panel shown after each turn of `play` (WBS 13.5).

Your health as a word and a bar (with the numbers in veteran mode), your spell
charges and whether you are dodging; in a fight, the round, whose turn it is
and the turn order. It only reads the state it is given, a copy of the
session's, so it never changes what is logged or sent to the model (CLAUDE.md
section 15, item 80). Beginner mode uses the vocabulary of
`adm/play/vocabulary.py` and shows no AC, DC or HP numbers.
"""

from __future__ import annotations

from rich.panel import Panel
from rich.text import Text

from adm.engine.combat import hp_band
from adm.engine.state import Combatant, GameState
from adm.play.commands import combatant_labels
from adm.play.vocabulary import BAND_WORDS, TERMS, Mode

TITLE = "Status"
BAR_CELLS = 10
FULL, EMPTY = "█", "░"
# An HP band's bar colour; the band's word is always shown beside it.
BAR_STYLES = {
    "healthy": "green",
    "wounded": "yellow",
    "badly_hurt": "red",
    "unconscious": "red",
}


def status_panel(state: GameState, mode: Mode, *, bar: bool = True) -> Panel:
    """The status of `state` as `mode` shows it; `bar` draws the health bar,
    which `--no-color` leaves out. `state` is only read."""
    pc = _player(state)
    body = Text()
    body.append(f"{pc.display_name}: {_health(pc, mode)}")
    if bar:
        band = hp_band(pc.current_hp, pc.max_hp)
        filled = health_cells(pc.current_hp, pc.max_hp)
        body.append("  ")
        body.append(FULL * filled + EMPTY * (BAR_CELLS - filled), style=BAR_STYLES[band])
    lines: list[str] = []
    if pc.spell_slots_1 is not None:
        charge = TERMS["spell slot"] if mode is Mode.BEGINNER else "spell slot"
        lines.append(f"{_cap(charge)}s left for Cure Wounds: {pc.spell_slots_1}")
    if pc.dodging:
        lines.append("You are dodging: attacks against you are harder until your next turn.")
    if state.encounter_active:
        labels = combatant_labels(state)
        active = labels[state.active_combatant_id or ""]
        lines += ["", f"Fight, round {state.round_number}. {active}'s turn.", "Turn order:"]
        for cid in state.initiative_order:
            marker = ">" if cid == state.active_combatant_id else " "
            lines.append(f" {marker} {labels[cid]}: {_health(state.combatants[cid], mode)}")
    for line in lines:
        body.append("\n" + line)
    return Panel(body, title=TITLE, title_align="left", expand=False)


def health_cells(current_hp: int, max_hp: int) -> int:
    """How many of the bar's cells are full: in proportion, rounded, and at
    least one while any health is left."""
    if current_hp <= 0:
        return 0
    return max(1, round(BAR_CELLS * current_hp / max_hp))


def _player(state: GameState) -> Combatant:
    return next(c for c in state.combatants.values() if c.is_player_character)


def _health(c: Combatant, mode: Mode) -> str:
    band = BAND_WORDS[hp_band(c.current_hp, c.max_hp)]
    if mode is Mode.BEGINNER:
        return band
    return f"{c.current_hp}/{c.max_hp} HP ({band})"


def _cap(word: str) -> str:
    return word[:1].upper() + word[1:]
