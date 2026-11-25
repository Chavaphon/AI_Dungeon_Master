"""In-game slash commands (WBS 13.1).

Any input that starts with `/` is a command. `play` handles it before the turn
loop, so a command makes no model call, writes no audit record and does not
count toward an encounter's `before_input` (CLAUDE.md section 15, items 36 and
74). `/status`, `/inventory` and `/quests` only read the state they are given;
`/help`, `/rules` and `/glossary` are fixed text. In beginner mode (WBS 13.2, the
default) every command uses the beginner vocabulary and shows no dice notation
or AC, DC or HP; veteran mode shows the numbers.

    /help       what you can type, and the commands; points to HOW_TO_PLAY.md
    /status     your health, spells and the fight in progress
    /inventory  what you carry
    /quests     your quests and how far along they are
    /rules      the rules in brief
    /glossary   the game's terms
    /quit       end the session (`/exit` does the same)
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from rich.console import RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from adm.engine.combat import hp_band
from adm.engine.state import Combatant, GameState
from adm.play.guide import POINTER
from adm.play.vocabulary import BAND_WORDS, QUEST_WORDS, TERMS, Mode

UNKNOWN = "Unknown command. Type /help for the list."
# Shown once, under the opening narration, so a new player finds the commands.
HINT = "Type /help for commands, /quit to stop."
PREFIX = "/"


@dataclass(frozen=True)
class CommandResult:
    """What a command shows, and whether it ends the session."""

    renderable: RenderableType
    quit: bool = False


def is_command(text: str) -> bool:
    """Whether a player's input is a slash command rather than a game input."""
    return text.startswith(PREFIX)


def run_command(text: str, state: GameState, mode: Mode) -> CommandResult:
    """Run the command `text` names against `state`, which is only read, as
    `mode` shows it. The command word is matched without case; anything after
    it is ignored."""
    words = text.split()
    name = words[0].lower() if words else PREFIX
    if name in QUIT:
        return CommandResult(Text("Ending the session."), quit=True)
    command = COMMANDS.get(name)
    if command is None:
        return CommandResult(Text(UNKNOWN))
    return CommandResult(command.show(state, mode))


# --- the commands ------------------------------------------------------------


def _panel(title: str, lines: list[str]) -> Panel:
    return Panel(Text("\n".join(lines)), title=title, title_align="left", expand=False)


def _player(state: GameState) -> Combatant:
    return next(c for c in state.combatants.values() if c.is_player_character)


def combatant_labels(state: GameState) -> dict[str, str]:
    """Each combatant's display name, numbered in id order where several share
    one ("giant rat 1", "giant rat 2"), so the player can tell them apart."""
    by_name: dict[str, list[str]] = {}
    for cid in sorted(state.combatants):
        by_name.setdefault(state.combatants[cid].display_name, []).append(cid)
    labels: dict[str, str] = {}
    for name, ids in by_name.items():
        for n, cid in enumerate(ids, start=1):
            labels[cid] = name if len(ids) == 1 else f"{name} {n}"
    return labels


def _health(c: Combatant, mode: Mode) -> str:
    band = BAND_WORDS[hp_band(c.current_hp, c.max_hp)]
    if mode is Mode.BEGINNER:
        return band
    return f"{c.current_hp}/{c.max_hp} HP ({band})"


def _help(state: GameState, mode: Mode) -> Panel:
    # The short version of HOW_TO_PLAY.md (WBS 13.3), the same in both modes.
    lines = [
        "Type what your character does in plain English, one action at a time:",
        '  "I look around"   "I attack the rat with my sword"   "I talk to the guard"',
        "",
        "In a fight everyone takes turns. On yours: attack, cast a spell or dodge.",
        "Looking around, sneaking, using items and talking do not use your turn.",
        "With no health left you are knocked out, not dead. Cure Wounds heals.",
        "Asked to rephrase? Try one action at a time, and name who or what.",
        "",
        "Commands (they do not use your turn and the Dungeon Master never sees them):",
    ]
    width = max(len(name) for name in COMMANDS)
    lines += [f"  {name:<{width}}  {c.summary}" for name, c in COMMANDS.items()]
    lines.append(f"  {'/quit':<{width}}  end the session")
    lines += ["", POINTER]
    return _panel("Help", lines)


def _status(state: GameState, mode: Mode) -> Panel:
    pc = _player(state)
    lines = [f"{pc.display_name}: {_health(pc, mode)}"]
    if pc.dodging:
        lines.append("You are dodging: attacks against you are harder until your next turn.")
    if pc.spell_slots_1 is not None and mode is Mode.BEGINNER:
        lines.append(
            f"Spell charges for Cure Wounds: {pc.spell_slots_1}. Fire Bolt is {TERMS['cantrip']}."
        )
    elif pc.spell_slots_1 is not None:
        lines.append(f"Spell slots for Cure Wounds: {pc.spell_slots_1}. Fire Bolt is always ready.")
    lines.append("")
    if not state.encounter_active:
        lines.append("No fight in progress.")
        return _panel("Status", lines)
    labels = combatant_labels(state)
    active = labels[state.active_combatant_id or ""]
    lines.append(f"Fight in progress, round {state.round_number}. {active}'s turn.")
    lines.append("Turn order:")
    for cid in state.initiative_order:
        marker = ">" if cid == state.active_combatant_id else " "
        lines.append(f" {marker} {labels[cid]}: {_health(state.combatants[cid], mode)}")
    return _panel("Status", lines)


def _inventory(state: GameState, mode: Mode) -> Panel:
    pc = _player(state)
    held = state.inventory.get(pc.combatant_id, {})
    lines = []
    for item_id in sorted(held):
        if held[item_id] < 1:
            continue
        item = state.item_definitions[item_id]
        weapon = " (weapon)" if item.is_weapon else ""
        lines.append(f"{item.display_name} x{held[item_id]}{weapon}")
    return _panel("Inventory", lines or ["You carry nothing."])


def _quests(state: GameState, mode: Mode) -> Panel:
    lines = []
    for quest_id in sorted(state.quests):
        q = state.quests[quest_id]
        stage = f", stage {q.stage} of {q.max_stage}" if q.state == "active" else ""
        lines.append(f"{q.display_name}: {QUEST_WORDS[q.state]}{stage}")
    return _panel("Quests", lines or ["You have no quests."])


# Veteran mode.
RULES = [
    "A small rule set inspired by tabletop fantasy role-playing games.",
    "",
    "Fights: everyone takes turns in a fixed order, rolled when the fight starts.",
    "On your turn you do one thing: attack, cast a spell, or dodge.",
    "Looking around, sneaking, lifting, using items and talking do not use your turn.",
    "There is no map: everyone in the fight is close enough to reach.",
    "",
    "Attacks: a d20 roll plus your bonus must reach the target's AC to hit.",
    "A natural 20 always hits and doubles the damage dice; a natural 1 always misses.",
    "Dodging makes attacks against you harder until the start of your next turn.",
    "",
    "Health: at 0 HP a character is knocked out, not killed, and cannot be attacked.",
    "Cure Wounds brings a knocked-out character back. The fight is won when every",
    "enemy is knocked out, and lost if you are.",
    "",
    "Spells: Fire Bolt is a fire attack you can cast every turn.",
    "Cure Wounds heals and uses one spell slot; slots do not come back.",
    "",
    "Skills: strength (lifting, forcing), perception (noticing), stealth (sneaking).",
    "A skill check succeeds if a d20 roll plus your bonus reaches the DC.",
]

# Beginner mode: the same rules in the beginner vocabulary, with no numbers.
BEGINNER_RULES = [
    "A small rule set inspired by tabletop fantasy role-playing games.",
    "",
    "Fights: everyone takes turns in a fixed turn order, set when the fight starts.",
    "On your turn you do one thing: attack, cast a spell, or dodge.",
    "Looking around, sneaking, lifting, using items and talking do not use your turn.",
    "There is no map: everyone in the fight is close enough to reach.",
    "",
    "Attacks: the dice decide whether you hit. Some enemies are harder to hit than others.",
    "A lucky roll always hits and does extra harm; an unlucky one always misses.",
    "Dodging makes attacks against you harder until the start of your next turn.",
    "",
    "Health: a character with no health left is knocked out, not killed, and cannot",
    "be attacked. Cure Wounds brings a knocked-out character back. The fight is won",
    "when every enemy is knocked out, and lost if you are.",
    "",
    "Spells: Fire Bolt is a fire attack, a spell you can always cast.",
    "Cure Wounds heals and uses one spell charge; charges do not come back.",
    "",
    "Skills: strength (lifting, forcing), perception (noticing), stealth (sneaking).",
    "The dice decide whether a skill check succeeds; harder tasks have a higher difficulty.",
    "When you have the upper hand the dice favour you; when the odds are against you,",
    "they do not.",
]

# Veteran mode.
GLOSSARY = [
    ("HP", "hit points: your health. At 0 you are knocked out."),
    ("AC", "armour class: how hard you are to hit."),
    ("DC", "difficulty class: the number a skill check must reach."),
    ("d20", "a twenty-sided die; 1d8 means one eight-sided die."),
    ("spell slot", "a charge for Cure Wounds. Slots do not come back."),
    ("cantrip", "a spell that needs no slot, such as Fire Bolt."),
    ("initiative", "the roll that fixes the turn order of a fight."),
    ("round", "one pass through the turn order."),
    ("Dodge", "an action that makes you harder to hit until your next turn."),
    ("advantage", "roll two d20 and keep the higher; disadvantage keeps the lower."),
    ("skill check", "a d20 roll to see if you manage something risky."),
    ("NPC", "non-player character: anyone the game controls, friend or foe."),
]


# Beginner mode: the words beginner screens use, explained without jargon.
BEGINNER_GLOSSARY = [
    (TERMS["HP"], "how much harm you can take. With none left you are knocked out."),
    (TERMS["unconscious"], "out of the fight until healed. Nobody dies in this game."),
    (TERMS["AC"], "how tough a character is to hit with an attack."),
    (TERMS["DC"], "how hard a skill check is."),
    (TERMS["spell slot"], "what Cure Wounds uses up. Charges do not come back."),
    (TERMS["cantrip"], "a spell that needs no charge, such as Fire Bolt."),
    (TERMS["initiative"], "who acts when in a fight, fixed when the fight starts."),
    ("round", "one pass through the turn order."),
    ("dodge", "an action that makes you harder to hit until your next turn."),
    ("the upper hand", "the dice are on your side for this roll."),
    ("the odds are against you", "the dice are against you for this roll."),
    ("skill check", "a roll to see if you manage something risky."),
]


def _rules(state: GameState, mode: Mode) -> Panel:
    return _panel("Rules", BEGINNER_RULES if mode is Mode.BEGINNER else RULES)


def _glossary(state: GameState, mode: Mode) -> Panel:
    # A grid, so a long meaning wraps under itself rather than under the terms.
    grid = Table.grid(padding=(0, 2))
    grid.add_column(no_wrap=True)
    grid.add_column()
    for term, meaning in BEGINNER_GLOSSARY if mode is Mode.BEGINNER else GLOSSARY:
        grid.add_row(term, meaning)
    return Panel(grid, title="Glossary", title_align="left", expand=False)


@dataclass(frozen=True)
class Command:
    summary: str
    show: Callable[[GameState, Mode], RenderableType]


COMMANDS: dict[str, Command] = {
    "/help": Command("what you can type, and these commands", _help),
    "/status": Command("your health, spells and the fight in progress", _status),
    "/inventory": Command("what you carry", _inventory),
    "/quests": Command("your quests and how far along they are", _quests),
    "/rules": Command("the rules in brief", _rules),
    "/glossary": Command("the game's terms", _glossary),
}
QUIT = frozenset({"/quit", "/exit"})
