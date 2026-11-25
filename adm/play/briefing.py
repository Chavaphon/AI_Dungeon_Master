"""The scenario briefing before play (WBS 13.4).

Before the first input, `play` shows who the player is, what they carry, their
quests, the people they know and the places they can go, so that a new player
does not start blind. The briefing is built from a copy of the starting state
and the scenario's own fields (no schema change), and makes no model call and
no audit record (CLAUDE.md section 15, item 79).

It never names a combatant who first appears in an `encounters` entry: at the
start every hostile combatant and its gear are already in `combatants` and
`inventory`, so the briefing reads only the player character, the player's own
inventory, the quests, the NPCs of `npc_relationships` that are in no
encounter, and `locations`. The opening narration is the scenario's own text,
shown as written.

It is written to be read at a glance: short sentences addressed to the player,
one bullet per thing, and panels of one width with a blank line between them.
Beginner mode (the default) uses the vocabulary of `adm/play/vocabulary.py`
and shows no numbers; veteran mode adds health in HP, armour class, ability
scores and each weapon's damage dice.
"""

from __future__ import annotations

from dataclasses import dataclass

from rich.console import Group, RenderableType
from rich.constrain import Constrain
from rich.panel import Panel
from rich.text import Text

from adm.engine.combat import hp_band
from adm.engine.scenario import Scenario
from adm.engine.state import Combatant, GameState, Item
from adm.play.vocabulary import BAND_WORDS, QUEST_WORDS, TERMS, Mode

# CLAUDE.md section 15, item 42: the title is labelled as AI narration.
AI_LABEL = "Narrated by AI"
BEGIN = "Take a moment to read, then press Enter to begin "

BULLET = "• "
WEAPON_USE = "a weapon, use it to attack"
ITEM_USE = "an item you can use"
ABILITIES = ("str", "dex", "con", "int", "wis", "cha")
# Every panel is this wide, or the terminal's width if that is less.
WIDTH = 72


@dataclass(frozen=True)
class Section:
    """One panel of the briefing: a title and its lines of plain text."""

    title: str
    lines: tuple[str, ...]


def hidden_combatants(scenario: Scenario) -> frozenset[str]:
    """Every combatant the player meets in an encounter, the player aside:
    the briefing never names them."""
    pcs = {
        cid for cid, c in scenario.initial_state["combatants"].items() if c["is_player_character"]
    }
    return frozenset(cid for e in scenario.encounters for cid in e.combatant_ids) - pcs


def sections(scenario: Scenario, state: GameState, mode: Mode) -> list[Section]:
    """The briefing for `scenario` at its start, as `mode` shows it. `state`
    is the session's starting state and is only read."""
    pc = _player(state)
    places = tuple(BULLET + _cap(p) for p in scenario.locations)
    return [
        Section(f"{scenario.display_name}  {AI_LABEL}", (scenario.opening_narration,)),
        Section("You are...", _you(pc, mode)),
        Section("You carry...", _carry(state, pc, mode)),
        Section("Your quests", _quests(state)),
        Section("People you know", _people(scenario, state)),
        Section("Places", places or ("No places are named yet.",)),
    ]


def briefing(scenario: Scenario, state: GameState, mode: Mode) -> RenderableType:
    """The briefing as `rich` panels, one per section, all one width, with a
    blank line between them. The scenario's own panel is set apart."""
    panels: list[RenderableType] = []
    for n, s in enumerate(sections(scenario, state, mode)):
        if n:
            panels.append(Text())
        panels.append(
            Panel(
                Text("\n".join(s.lines)),
                title=Text(s.title, style="bold"),
                title_align="left",
                border_style="bold" if n == 0 else "dim",
                padding=(0, 2),
            )
        )
    return Constrain(Group(*panels), width=WIDTH)


# --- the sections ----------------------------------------------------------------


def _player(state: GameState) -> Combatant:
    return next(c for c in state.combatants.values() if c.is_player_character)


def _you(pc: Combatant, mode: Mode) -> tuple[str, ...]:
    band = BAND_WORDS[hp_band(pc.current_hp, pc.max_hp)]
    if mode is Mode.BEGINNER:
        lines = [f"You are {pc.display_name}, and you feel {band}."]
    else:
        abilities = pc.abilities.model_dump(by_alias=True)
        lines = [
            f"You are {pc.display_name}: {pc.current_hp}/{pc.max_hp} HP ({band}), "
            f"armour class {pc.armour_class}.",
            "Ability scores: " + ", ".join(f"{a} {abilities[a]}" for a in ABILITIES),
        ]
    lines.append("")
    lines += _spells(pc, mode)
    return tuple(lines)


def _spells(pc: Combatant, mode: Mode) -> list[str]:
    if pc.spell_slots_1 is None:
        return ["You do not know any spells."]
    slots = pc.spell_slots_1
    plural = "" if slots == 1 else "s"
    if mode is Mode.BEGINNER:
        fire = "a fire attack you can always cast"
        cure = f"heals, {slots} {TERMS['spell slot']}{plural} left"
    else:
        fire = "cantrip, always ready"
        cure = f"heals, {slots} spell slot{plural} left"
    return ["Your spells:", f"{BULLET}Fire Bolt: {fire}", f"{BULLET}Cure Wounds: {cure}"]


def _carry(state: GameState, pc: Combatant, mode: Mode) -> tuple[str, ...]:
    # Only the player's own inventory: an enemy's weapon would name the enemy.
    held = state.inventory.get(pc.combatant_id, {})
    lines = []
    for item_id in sorted(held):
        if held[item_id] < 1:
            continue
        item = state.item_definitions[item_id]
        count = f" ({held[item_id]})" if held[item_id] > 1 else ""
        lines.append(f"{BULLET}{_cap(item.display_name)}{count}: {_use(item, mode)}")
    return tuple(lines) or ("You carry nothing.",)


def _use(item: Item, mode: Mode) -> str:
    if not item.is_weapon:
        return ITEM_USE
    if mode is Mode.BEGINNER or item.damage_dice is None:
        return WEAPON_USE
    bonus = item.damage_bonus or 0
    sign = f"+{bonus}" if bonus > 0 else (str(bonus) if bonus < 0 else "")
    return f"{WEAPON_USE} (damage {item.damage_dice}{sign})"


def _quests(state: GameState) -> tuple[str, ...]:
    # Worded as /quests words them (adm/play/commands.py), in both modes.
    lines = []
    for quest_id in sorted(state.quests):
        q = state.quests[quest_id]
        stage = f", stage {q.stage} of {q.max_stage}" if q.state == "active" else ""
        lines.append(f"{BULLET}{q.display_name}: {QUEST_WORDS[q.state]}{stage}")
    return tuple(lines) or ("You have no quests yet.",)


def _people(scenario: Scenario, state: GameState) -> tuple[str, ...]:
    # Stances are worded as the result lines word them (adm/play/results.py).
    hidden = hidden_combatants(scenario)
    lines = [
        f"{BULLET}{_cap(npc.display_name)}: {npc.stance} towards you"
        for npc_id, npc in sorted(state.npc_relationships.items())
        if npc_id not in hidden
    ]
    return tuple(lines) or ("You do not know anyone here yet.",)


def _cap(name: str) -> str:
    # "the Keeper" starts a line as "The Keeper".
    return name[:1].upper() + name[1:]
