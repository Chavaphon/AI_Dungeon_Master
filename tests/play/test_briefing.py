"""The scenario briefing before play (WBS 13.4, #252): who the player is, what
they carry, their quests, the people they know and the places, built from the
starting state and the scenario's own fields, that never names a combatant of
an encounter and renders for every scenario in both modes.

Run: pytest tests/play/test_briefing.py -v
"""

import io
import re
from pathlib import Path

import pytest
from rich.console import Console

from adm.engine.scenario import Encounter, Scenario, initial_state, load_scenario
from adm.engine.state import state_hash
from adm.play.briefing import AI_LABEL, Section, briefing, hidden_combatants, sections
from adm.play.vocabulary import JARGON, Mode

ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = sorted((ROOT / "scenarios").glob("*.json"))
SEED = 12345
S01 = load_scenario(ROOT / "scenarios" / "s01_cellar.json")


def _scenarios() -> list[Scenario]:
    return [load_scenario(path) for path in SCENARIOS]


def test_there_are_sixteen_scenarios() -> None:
    assert len(SCENARIOS) == 16


def _spoilers(scenario: Scenario) -> set[str]:
    """What would give an encounter away: each hidden combatant's id and name,
    and the name of every item only hidden combatants hold."""
    state = initial_state(scenario, SEED)
    hidden = hidden_combatants(scenario)
    assert hidden, f"{scenario.scenario_id} has an encounter"
    words = {cid for cid in hidden} | {state.combatants[cid].display_name for cid in hidden}
    shown = {i for cid, held in state.inventory.items() if cid not in hidden for i in held}
    for cid in hidden:
        for item_id in state.inventory.get(cid, {}):
            if item_id not in shown:
                words |= {item_id, state.item_definitions[item_id].display_name}
    return words


@pytest.mark.parametrize("mode", list(Mode))
@pytest.mark.parametrize("scenario", _scenarios(), ids=lambda s: s.scenario_id)
def test_the_briefing_never_names_a_combatant_of_an_encounter(
    scenario: Scenario, mode: Mode
) -> None:
    """The acceptance of #252. The opening narration is the scenario's own
    text, and the quest and place names are shown as the scenario writes them
    ("The Bandit Toll"); with those taken out, nothing the briefing adds names
    a combatant the player meets in an encounter, or its gear."""
    title, *rest = sections(scenario, initial_state(scenario, SEED), mode)
    assert title.lines == (scenario.opening_narration,)
    text = "\n".join(line for s in rest for line in s.lines)
    authored = [q["display_name"] for q in scenario.initial_state["quests"].values()]
    for name in [*authored, *scenario.locations]:
        text = re.sub(re.escape(name), "", text, flags=re.IGNORECASE)
    for word in _spoilers(scenario):
        found = re.search(rf"\b{re.escape(word)}(e?s)?\b", text, flags=re.IGNORECASE)
        assert found is None, f"{scenario.scenario_id} names {word!r}"


def test_an_npc_who_fights_later_is_not_among_the_people_you_know() -> None:
    fights = S01.encounters[0].combatant_ids
    scenario = S01.model_copy(
        update={"encounters": [Encounter(before_input=3, combatant_ids=[*fights, "npc_keeper"])]}
    )
    people = sections(scenario, initial_state(S01, SEED), Mode.BEGINNER)[4]
    assert people == Section("People you know", ("Nobody yet.",))
    assert "npc_keeper" in hidden_combatants(scenario)
    assert "pc_lyra" not in hidden_combatants(scenario), "the player is never hidden"


def _render(scenario: Scenario, mode: Mode) -> str:
    console = Console(file=io.StringIO(), width=80, record=True)
    console.print(briefing(scenario, initial_state(scenario, SEED), mode))
    return console.export_text()


@pytest.mark.parametrize("mode", list(Mode))
@pytest.mark.parametrize("scenario", _scenarios(), ids=lambda s: s.scenario_id)
def test_the_briefing_renders_for_every_scenario(scenario: Scenario, mode: Mode) -> None:
    """The acceptance of #252: every scenario, both modes, without error; the
    beginner briefing shows no dice notation, modifiers, AC, DC or HP."""
    text = _render(scenario, mode)
    words = " ".join(text.replace("│", " ").split())
    assert f"{scenario.display_name} {AI_LABEL}" in words
    assert " ".join(scenario.opening_narration.split()) in words
    for title in ("You are...", "You carry...", "Your quests", "People you know", "Places"):
        assert title in text
    if mode is Mode.BEGINNER:
        assert JARGON.search(text) is None, JARGON.search(text)


def test_the_briefing_only_reads_the_state() -> None:
    state = initial_state(S01, SEED)
    before = state_hash(state)
    for mode in Mode:
        sections(S01, state, mode)
        briefing(S01, state, mode)
    assert state_hash(state) == before


# --- the s01 briefing, word for word ------------------------------------------------


def test_the_s01_beginner_briefing() -> None:
    assert sections(S01, initial_state(S01, SEED), Mode.BEGINNER)[1:] == [
        Section(
            "You are...",
            (
                "Name: Lyra",
                "Health: healthy",
                "Spells: Fire Bolt (a spell you can always cast), "
                "Cure Wounds (2 spell charges left)",
            ),
        ),
        Section(
            "You carry...",
            ("Short sword: a weapon, use it to attack", "Torch x2: an item you can use"),
        ),
        Section("Your quests", ("The Missing Ledger: not started",)),
        Section("People you know", ("The Keeper: unfriendly towards you",)),
        Section("Places", ("The cellar", "The cellar stairs", "The barrels")),
    ]


def test_the_s01_veteran_briefing_adds_the_numbers() -> None:
    you, carry = sections(S01, initial_state(S01, SEED), Mode.VETERAN)[1:3]
    assert you.lines == (
        "Name: Lyra",
        "Health: 20/20 HP (healthy)",
        "Armour class: 14",
        "Ability scores: str 12, dex 16, con 14, int 10, wis 13, cha 11",
        "Spells: Fire Bolt (cantrip), Cure Wounds (2 spell slots left)",
    )
    assert carry.lines == (
        "Short sword: a weapon, use it to attack (damage 1d6+3)",
        "Torch x2: an item you can use",
    )


def test_a_non_caster_is_told_they_cast_no_spells() -> None:
    scenario = load_scenario(ROOT / "scenarios" / "s02_toll_bridge.json")
    you = sections(scenario, initial_state(scenario, SEED), Mode.BEGINNER)[1]
    assert you.lines[-1] == "Spells: none, you cannot cast spells"
