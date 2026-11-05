"""HP band, status and HP-number comparison (WBS 8.7): implements the 8.2 rule
exactly, the done-when of #85.

The rule is docs/rubric.md section 5. The worked examples C1, C3 and C4 give
the divergences the rubric counts; 14 of 20 is `wounded` and adjacent bands are
not forgiven (5.2); events, negations, figurative uses, the past and the future
and effort are not band phrases (5.3); each combatant is scored on its own HP
after the turn, at most once per narration (5.4); an unconscious combatant that
acts is a divergence, and "falls back" is not a band phrase (5.5). The actual
band always comes from the engine's `hp_band`.

Run: pytest tests/eval/test_bands.py -v
"""

import copy
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from adm.engine.combat import hp_band
from adm.engine.scenario import load_scenario
from adm.eval.bands import LEXICON, band_candidates

ROOT = Path(__file__).resolve().parents[2]
# docs/rubric.md section 4: Lyra has max_hp 20, the two giant rats 11.
EXAMPLE = load_scenario(ROOT / "schemas" / "examples" / "scenario_s00_example.json")


def _state(lyra: int = 20, rat1: int = 11, rat2: int = 11) -> dict:
    state = copy.deepcopy(EXAMPLE.initial_state)
    for cid, hp in (("pc_lyra", lyra), ("npc_rat_01", rat1), ("npc_rat_02", rat2)):
        state["combatants"][cid]["current_hp"] = hp
        state["combatants"][cid]["status"] = "unconscious" if hp == 0 else "active"
    return state


def _found(narration: str, state: dict) -> list[tuple[str, str, str]]:
    return [(c.kind, c.mention, c.confidence) for c in band_candidates(narration, state)]


# --- docs/rubric.md section 4.2 ----------------------------------------------


def test_c1_barely_standing_at_14_of_20_is_one_contradict() -> None:
    narration = "You stagger back, barely standing, your vision swimming."
    [c] = band_candidates(narration, _state(lyra=14))
    assert (c.kind, c.mention, c.confidence) == ("band", "barely standing", "high")
    assert c.subject == ("pc_lyra",)
    assert (c.implied, c.actual) == (("badly_hurt",), ("wounded",))
    assert narration[c.start : c.end] == c.mention


def test_c3_unhurt_at_18_of_20_is_no_divergence() -> None:
    narration = "You shake the water from your boots, unhurt, and turn toward the second rat."
    assert _found(narration, _state(lyra=18)) == []


def test_c4_no_band_phrase_is_not_scored() -> None:
    assert _found("You grit your teeth and lift your sword again.", _state(lyra=14)) == []


# --- section 5.2: 14 of 20, no adjacency allowance ---------------------------


@pytest.mark.parametrize(
    ("phrase", "flagged"),
    [
        ("near death", True),
        ("on the brink", True),
        ("gravely wounded", True),
        ("unhurt", True),
        ("barely a scratch", True),
        ("wounded", False),
        ("bleeding", False),
    ],
)
def test_14_of_20_is_wounded_and_only_a_wounded_phrase_fits(phrase: str, flagged: bool) -> None:
    assert hp_band(14, 20) == "wounded"
    assert bool(_found(f"You are {phrase}.", _state(lyra=14))) is flagged


@pytest.mark.parametrize(("hp", "band"), [(15, "wounded"), (16, "healthy"), (7, "badly_hurt")])
def test_the_thresholds_are_the_engines_and_exact_ratios_fall_in_the_lower_band(
    hp: int, band: str
) -> None:
    [c] = band_candidates("You are out cold.", _state(lyra=hp))
    assert c.actual == (band,)


# --- section 5.3: what a band phrase is --------------------------------------


@pytest.mark.parametrize(
    "narration",
    [
        "The blade hurt you.",  # 1: an event, not a condition
        "You wounded the rat.",
        "You are far from dying.",  # 2: negated
        "You are no longer bleeding.",
        "You are not hurt.",
        "The dying torchlight flickers over you.",  # 3: about something else
        "You duck as the barrels collapse.",
        "Night falls over you.",
        "You grit your teeth, panting.",  # 5: effort
    ],
)
def test_events_negations_and_figurative_phrases_are_not_scored(narration: str) -> None:
    assert _found(narration, _state(lyra=20)) == []


@pytest.mark.parametrize(
    ("phrase", "hp", "flagged"),
    [
        ("badly wounded", 14, True),  # badly_hurt against wounded
        ("badly wounded", 5, False),
        ("barely hurt", 18, False),  # healthy
        ("barely hurt", 14, True),
        ("slightly wounded", 18, False),  # healthy or wounded: ambiguous, not flagged
        ("slightly wounded", 14, False),
        ("slightly wounded", 5, True),
    ],
)
def test_intensity_words_decide_the_band(phrase: str, hp: int, flagged: bool) -> None:
    found = band_candidates(f"You are {phrase}.", _state(lyra=hp))
    assert bool(found) is flagged
    if found:
        assert found[0].mention == phrase


def test_a_hedged_sentence_is_low_confidence() -> None:
    assert _found("If you were dying, you would know.", _state(lyra=20)) == [
        ("band", "dying", "low")
    ]


# --- section 5.4: which hit points are compared ------------------------------


def test_the_hp_after_the_turn_is_compared() -> None:
    # Cure Wounds brought Lyra from 6 to 16 of 20: healthy.
    [c] = band_candidates("Warm light washes over you, but you are still bleeding.", _state(16))
    assert (c.implied, c.actual) == (("wounded",), ("healthy",))


def test_each_combatant_is_scored_on_its_own_band() -> None:
    # Lyra 20/20 healthy; the rats 2/11 badly_hurt.
    state = _state(lyra=20, rat1=2, rat2=2)
    assert _found("The giant rat is barely standing.", state) == []
    assert _found("You are barely standing.", state) == [("band", "barely standing", "high")]
    assert [c.subject for c in band_candidates("The wounded rat snarls.", state)] == [
        ("npc_rat_01", "npc_rat_02")
    ]


def test_two_combatants_wrong_are_two_candidates_and_one_combatant_is_one() -> None:
    state = _state(lyra=20, rat1=11, rat2=11)
    two = band_candidates("You are near death. The giant rat is near death too.", state)
    assert [c.subject for c in two] == [("pc_lyra",), ("npc_rat_01", "npc_rat_02")]
    one = band_candidates("You are near death, on the brink, dying.", state)
    assert [(c.mention, c.subject) for c in one] == [("near death", ("pc_lyra",))]


def test_a_phrase_that_fits_any_combatant_it_may_describe_is_not_flagged() -> None:
    # Lyra healthy, the rats out cold: "it crumples" could be a rat.
    state = _state(lyra=20, rat1=0, rat2=0)
    assert _found("You strike the rat. It crumples, out cold.", state) == []
    # Neither a 3/11 rat nor a healthy Lyra is unconscious: flagged, low confidence.
    state = _state(lyra=20, rat1=3, rat2=3)
    assert _found("You strike the rat. It crumples.", state) == [("band", "crumples", "low")]


# --- section 5.5: unconscious, band and status -------------------------------


def test_falls_is_unconscious_only_when_it_means_going_down() -> None:
    assert _found("The giant rat falls back, hissing.", _state(rat1=11, rat2=11)) == []
    assert _found("The giant rat falls to the floor.", _state(rat1=0, rat2=0)) == []
    assert _found("The giant rat collapses.", _state(rat1=5, rat2=5)) == [
        ("band", "collapses", "low")
    ]


def test_an_unconscious_combatant_acting_is_one_contradict() -> None:
    [c] = band_candidates("The giant rat lunges at your ankle.", _state(rat1=0, rat2=0))
    assert (c.kind, c.mention, c.confidence, c.actual) == (
        "status",
        "rat lunges",
        "high",
        ("unconscious",),
    )
    assert _found("You swing your sword.", _state(lyra=0)) == [("status", "You swing", "high")]
    # One rat still up: the narration may be about it.
    assert _found("The giant rat lunges at your ankle.", _state(rat1=0, rat2=5)) == []


def test_dying_at_zero_is_one_contradict_not_two() -> None:
    # "dying" is a band phrase and the rat also acts: one combatant, one divergence.
    found = band_candidates("The dying rat bites.", _state(rat1=0, rat2=0))
    assert [(c.kind, c.implied, c.actual) for c in found] == [
        ("band", ("badly_hurt",), ("unconscious",))
    ]


# --- HP numbers ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("narration", "flagged"),
    [
        ("You have 3 hit points left.", True),
        ("You have 5 hit points left.", False),
        ("You are down to five HP.", False),
        ("You stand at 5 of 20 hit points.", False),
        ("You stand at 5 of 22 hit points.", True),
        ("You lose 3 hit points.", False),  # a change, not a value
        ("The rat's bite deals 4 hit points of damage to you.", False),
    ],
)
def test_a_stated_hp_number_is_compared_with_current_hp(narration: str, flagged: bool) -> None:
    found = band_candidates(narration, _state(lyra=5))
    assert [c.kind for c in found] == (["hp_number"] if flagged else [])


# --- properties -----------------------------------------------------------------


@given(hp=st.integers(min_value=0, max_value=20), band=st.sampled_from(sorted(LEXICON)))
def test_a_phrase_of_the_actual_band_is_never_flagged(hp: int, band: str) -> None:
    for phrase in LEXICON[band]:
        if band == hp_band(hp, 20):
            assert _found(f"You are {phrase}.", _state(lyra=hp)) == []


@given(hp=st.integers(min_value=0, max_value=20))
def test_a_plain_phrase_of_another_band_is_always_flagged(hp: int) -> None:
    actual = hp_band(hp, 20)
    plain = {"healthy": "unhurt", "wounded": "wounded", "badly_hurt": "near death"}
    plain["unconscious"] = "out cold"
    for band, phrase in plain.items():
        found = _found(f"You are {phrase}.", _state(lyra=hp))
        assert bool(found) is (band != actual)
