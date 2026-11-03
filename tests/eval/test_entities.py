"""Entity-mention extraction (WBS 8.6): flags items and NPCs absent from state,
the done-when of #84.

The worked `PHANTOM` examples of docs/rubric.md section 4.1 give exactly the
divergences the rubric counts, and its section 3 and 6.1 conventions hold:
repeats count once, parts and scenery are not flagged, and an item at quantity
0 keeps its definition. Names in scope are never flagged, in any scenario.
Candidates in a negated or hypothetical sentence, and proper nouns, are low
confidence.

Run: pytest tests/eval/test_entities.py -v
"""

import copy
from pathlib import Path

import pytest

from adm.engine.scenario import Scenario, load_scenario
from adm.eval.entities import (
    AMBIGUOUS_WORDS,
    CHARACTER_WORDS,
    ITEM_WORDS,
    Scope,
    phantom_candidates,
    singular,
)

ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = sorted((ROOT / "scenarios").glob("*.json"))
# docs/rubric.md section 4 uses the cellar of the example scenario.
EXAMPLE = load_scenario(ROOT / "schemas" / "examples" / "scenario_s00_example.json")
SCOPE = Scope.of(EXAMPLE, EXAMPLE.initial_state)


def _found(narration: str, scope: Scope = SCOPE) -> list[tuple[str, str, str]]:
    return [(c.kind, c.mention, c.confidence) for c in phantom_candidates(narration, scope)]


# --- docs/rubric.md section 4.1 ----------------------------------------------


def test_p1_a_lantern_no_one_has_is_one_phantom_item() -> None:
    narration = (
        "You raise your lantern, and its light catches two pairs of red eyes behind the barrels."
    )
    assert _found(narration) == [("item", "lantern", "high")]


def test_p2_a_stranger_and_a_dagger_are_two_phantoms() -> None:
    narration = "A hooded stranger steps out from behind the barrels and draws a curved dagger."
    assert _found(narration) == [("character", "stranger", "high"), ("item", "dagger", "high")]


def test_p3_parts_of_an_in_scope_entity_are_not_phantoms() -> None:
    narration = (
        "Your sword bites into the rat's flank, and its yellow teeth snap at your ankle "
        "as it twists away."
    )
    assert _found(narration) == []


def test_p4_listed_locations_are_in_scope() -> None:
    assert _found("Water drips down the cellar stairs and pools around the barrels.") == []


# --- counting and conventions ------------------------------------------------


def test_a_repeat_in_one_narration_counts_once() -> None:
    """Rubric section 3 rule 3, at the first mention."""
    narration = "The stranger smiles. The stranger draws a knife, then a second knife."
    candidates = phantom_candidates(narration, SCOPE)
    assert [(c.kind, c.mention) for c in candidates] == [
        ("character", "stranger"),
        ("item", "knife"),
    ]
    assert narration[candidates[0].start : candidates[0].end] == "stranger"


def test_plurals_and_possessives_match_their_singular() -> None:
    assert _found("Two lanterns hang from the beams.") == [("item", "lanterns", "high")]
    assert _found("Your torches gutter as the Keeper's voice echoes.") == []
    assert _found("You pass the rats a crust.") == []


def test_an_item_at_quantity_zero_keeps_its_definition() -> None:
    """Rubric example R-neg: a definition keeps the name in scope."""
    state = copy.deepcopy(EXAMPLE.initial_state)
    owner = next(iter(state["inventory"]))
    item = next(iter(state["inventory"][owner]))
    state["inventory"][owner][item] = 0
    name = state["item_definitions"][item]["display_name"]
    assert _found(f"You think of the {name} you used to carry.", Scope.of(EXAMPLE, state)) == []


def test_scenery_parts_and_worn_things_are_not_items() -> None:
    """Rubric section 6.1 rules 2 and 5."""
    narration = (
        "Dust drifts in the torchlight. Cobwebs cling to the walls, and your cloak "
        "and boots are soaked through."
    )
    assert _found(narration) == []


def test_a_negated_or_hypothetical_mention_is_low_confidence() -> None:
    assert _found("You have no lantern, only your torches.") == [("item", "lantern", "low")]
    assert _found("If a guardsman came down the stairs, you would hear him.") == [
        ("character", "guardsman", "low")
    ]


def test_ambiguous_words_are_low_confidence() -> None:
    assert _found("You keep your guard up as the rat circles.") == [("character", "guard", "low")]
    assert _found("A figure moves at the top of the stairs.") == [("character", "figure", "low")]


def test_an_unknown_name_in_mid_sentence_is_a_low_confidence_proper_noun() -> None:
    narration = 'You remember what Mira told you. "Beware the Black Tower," she said.'
    assert _found(narration) == [
        ("proper_noun", "Mira", "low"),
        ("proper_noun", "Black Tower", "low"),
    ]


def test_known_names_sentence_openers_and_spells_are_not_proper_nouns() -> None:
    narration = (
        'Lyra watches the Keeper. "Down here," he says. Then Fire Bolt flares, and '
        "You see the rat fall: Silence follows."
    )
    assert _found(narration) == []


# --- every scenario ----------------------------------------------------------


@pytest.mark.parametrize("path", SCENARIOS, ids=[p.stem for p in SCENARIOS])
def test_no_name_in_scope_is_ever_flagged(path: Path) -> None:
    """A narration made of every display name and location of a scenario has no
    candidate: an in-scope name is never a phantom."""
    scenario: Scenario = load_scenario(path)
    scope = Scope.of(scenario, scenario.initial_state)
    narration = " ".join(f"You see {name} beside {name}." for name in scope.names)
    assert phantom_candidates(narration, scope) == []


def test_the_lexicons_are_disjoint_and_singular() -> None:
    assert not ITEM_WORDS & CHARACTER_WORDS
    assert not (ITEM_WORDS | CHARACTER_WORDS) & AMBIGUOUS_WORDS.keys()
    for word in ITEM_WORDS | CHARACTER_WORDS | AMBIGUOUS_WORDS.keys():
        assert singular(word) == word, word
