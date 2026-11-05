"""Relationship-stance comparison (WBS 8.8): detects hostile narration of a
recorded-neutral NPC, the done-when of #86.

The worked `RELATION` examples of docs/rubric.md section 4.4 give exactly the
divergences the rubric counts. Section 6.4 holds: only NPCs with a stance are
scored, against the stance after the turn, and behaviour one step either side
of the stance is forgiven. Negated markers, the player character's own
behaviour and mixed tones are not scored.

Run: pytest tests/eval/test_stance.py -v
"""

import copy
import itertools
from pathlib import Path

import pytest

from adm.engine.scenario import load_scenario
from adm.eval import stance as stance_module
from adm.eval.stance import LADDER, MARKERS, distance, stance_candidates

ROOT = Path(__file__).resolve().parents[2]
# docs/rubric.md section 4: the Keeper is an NPC in npc_relationships.
EXAMPLE = load_scenario(ROOT / "schemas" / "examples" / "scenario_s00_example.json")
SCENARIOS = sorted((ROOT / "scenarios").glob("*.json"))


def _state(stance: str) -> dict:
    state = copy.deepcopy(EXAMPLE.initial_state)
    state["npc_relationships"]["npc_keeper"]["stance"] = stance
    return state


def _found(narration: str, stance: str) -> list[tuple[str, str]]:
    return [(c.mention, c.confidence) for c in stance_candidates(narration, _state(stance))]


# --- the done-when ------------------------------------------------------------


@pytest.mark.parametrize(
    "narration",
    [
        "The Keeper spits at your feet.",
        "The Keeper threatens you with a raised fist.",
        '"Get out of my cellar," the Keeper says, menacingly.',
    ],
)
def test_hostile_narration_of_a_neutral_npc_is_a_relation_candidate(narration: str) -> None:
    [c] = stance_candidates(narration, _state("neutral"))
    assert c.confidence == "high"
    assert (c.subject, c.implied, c.actual) == (("npc_keeper",), ("hostile",), ("neutral",))
    assert narration[c.start : c.end] == c.mention


# --- docs/rubric.md section 4.4 ----------------------------------------------


def test_l1_warmth_toward_unfriendly_is_one_relation() -> None:
    narration = "The Keeper beams and pulls you into a hug like an old friend."
    [c] = stance_candidates(narration, _state("unfriendly"))
    assert (c.mention, c.confidence, c.implied) == ("beams", "high", ("friendly", "allied"))


def test_l2_hostility_toward_friendly_is_one_relation() -> None:
    narration = "The Keeper spits at your feet and orders you out of the cellar."
    assert _found(narration, "friendly") == [("spits", "high")]


def test_l3_coldness_fits_unfriendly() -> None:
    assert _found("The Keeper eyes you coldly and answers with a single grunt.", "unfriendly") == []


def test_l4_businesslike_fits_neutral() -> None:
    narration = "The Keeper nods and points you toward the stairs without a word."
    assert _found(narration, "neutral") == []


# --- section 6.4 --------------------------------------------------------------


def test_only_npcs_with_a_stance_are_scored() -> None:
    # The giant rats are hostile combatants with no stance (rule 1).
    assert _found("The giant rat snarls and spits at you.", "allied") == []


def test_the_stance_after_the_turn_is_scored() -> None:
    # update_npc_relationship ran this turn, unfriendly -> neutral: warmth is one step away.
    assert _found("The Keeper smiles warmly at you.", "neutral") == []
    assert _found("The Keeper smiles warmly at you.", "unfriendly") == [("warmly", "high")]


@pytest.mark.parametrize(
    ("tone", "recorded", "flagged"),
    [
        ("hostile", "hostile", False),
        ("hostile", "unfriendly", False),
        ("hostile", "neutral", True),
        ("hostile", "allied", True),
        ("cold", "neutral", False),
        ("cold", "friendly", True),
        ("warm", "neutral", False),
        ("warm", "unfriendly", True),
        ("warm", "hostile", True),
    ],
)
def test_one_step_either_side_is_forgiven_and_two_is_not(
    tone: str, recorded: str, flagged: bool
) -> None:
    marker = {"hostile": "spits", "cold": "glares", "warm": "beams"}[tone]
    assert bool(_found(f"The Keeper {marker} at you.", recorded)) is flagged


def test_without_the_allowance_any_mismatch_is_flagged(monkeypatch: pytest.MonkeyPatch) -> None:
    # Rubric section 7 point 1: the pilot may drop the allowance.
    monkeypatch.setattr(stance_module, "ADJACENCY", 0)
    assert _found("The Keeper glares at you.", "neutral") == [("glares", "high")]


def test_distance_is_steps_to_the_nearest_implied_stance() -> None:
    for a, b in itertools.product(LADDER, LADDER):
        assert distance(a, [b]) == abs(LADDER.index(a) - LADDER.index(b))
    assert distance("neutral", ["hostile", "unfriendly"]) == 1


# --- what is not scored -------------------------------------------------------


@pytest.mark.parametrize(
    "narration",
    [
        "The Keeper does not smile.",  # negated
        "The Keeper answers without warmth, but never with hostility.",
        "You glare at the Keeper.",  # the player character's behaviour
        "You spit on the floor and the Keeper looks away.",
        "The Keeper smiles coldly at you.",  # mixed tones
        "The cellar is silent.",  # no NPC
    ],
)
def test_negations_the_party_and_mixed_tones_are_not_scored(narration: str) -> None:
    for recorded in LADDER:
        assert _found(narration, recorded) == [], recorded


# --- confidence and counting --------------------------------------------------


def test_ambiguous_inherited_and_unaddressed_markers_are_low() -> None:
    assert _found("The Keeper grins at you.", "hostile") == [("grins", "low")]
    assert _found("You climb the stairs. The Keeper waits. He spits at you.", "neutral") == [
        ("spits", "low")
    ]
    assert _found("The Keeper spits on the floor.", "neutral") == [("spits", "low")]
    assert _found("If the Keeper spits at you, leave.", "neutral") == [("spits", "low")]


def test_one_candidate_per_npc_per_narration() -> None:
    narration = "The Keeper glares at you. Then he spits at your feet and threatens you."
    assert _found(narration, "friendly") == [("glares", "high")]


# --- every scenario -----------------------------------------------------------


@pytest.mark.parametrize("path", SCENARIOS, ids=lambda p: p.stem)
def test_every_stance_npc_can_be_named_and_its_own_stance_is_never_flagged(path: Path) -> None:
    scenario = load_scenario(path)
    state = scenario.initial_state
    for npc in state["npc_relationships"].values():
        tones = [t for t, implied in stance_module.IMPLIES.items() if npc["stance"] in implied]
        for tone in tones:
            marker = next(m for m in MARKERS[tone] if m not in stance_module.AMBIGUOUS)
            narration = f"{npc['display_name'].capitalize()} says to you, {marker}."
            assert stance_candidates(narration, state) == [], (npc["npc_id"], marker)
        far = [
            t
            for t, implied in stance_module.IMPLIES.items()
            if distance(npc["stance"], implied) > 1
        ]
        for tone in far:
            narration = f"{npc['display_name'].capitalize()} {MARKERS[tone][0]} at you."
            [c] = stance_candidates(narration, state)
            assert npc["npc_id"] in c.subject
