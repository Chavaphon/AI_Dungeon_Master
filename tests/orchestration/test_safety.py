"""The output safety filter (WBS 6.9): sentences with a blocked term are removed,
an empty result becomes the fallback line, combat is left alone, and the filter
is deterministic. The turn-loop side (logged, flagged, counted) is in
test_loop.py, and the audit rule in test_audit_log.py.

Run: pytest tests/orchestration/test_safety.py -v
"""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from adm.orchestration.safety import BLOCKED_TERMS, FALLBACK, filter_narration


@pytest.mark.parametrize(
    "text",
    [
        "Your blade bites into the rat's flank, and it shrieks and drags itself back.",
        "The bandit's blood spatters the bridge as he falls, unconscious.",
        "You draw your naked steel and kill the light in the lantern.",
        "Sextant in hand, the smuggler grips the rope.",  # no whole-word match
        "",
    ],
)
def test_combat_and_ordinary_narration_pass_unchanged(text: str) -> None:
    result = filter_narration(text)
    assert (result.text, result.filtered, result.matched) == (text, False, ())


def test_only_the_sentence_with_a_blocked_term_is_removed() -> None:
    text = "The rat shrieks. A voice whispers of suicide in the dark! You stand firm?"
    result = filter_narration(text)
    assert result.text == "The rat shrieks. You stand firm?"
    assert result.filtered is True
    assert result.matched == ("suicide",)


def test_matching_ignores_case_and_spans_whitespace() -> None:
    result = filter_narration("He snarls: KILL\n  YOURSELF. Then he runs.")
    assert result.text == "Then he runs."
    assert result.matched == ("kill\n  yourself",)


def test_a_hyphenated_term_matches_whole() -> None:
    assert filter_narration("Talk of self-harm. The fire crackles.").text == "The fire crackles."
    assert not filter_narration("The self-harmony of the choir.").filtered


def test_nothing_left_shows_the_fallback() -> None:
    result = filter_narration("Talk of suicide. More talk of suicide.")
    assert result.text == FALLBACK
    assert result.filtered is True
    assert result.matched == ("suicide", "suicide")


def test_other_terms_can_be_passed() -> None:
    result = filter_narration("The goblin swears. The goblin runs.", terms=["swears"])
    assert (result.text, result.filtered) == ("The goblin runs.", True)


def test_every_blocked_term_is_caught() -> None:
    for term in BLOCKED_TERMS:
        result = filter_narration(f"Something about {term} here. The torch gutters.")
        assert result.text == "The torch gutters.", term


@given(text=st.text(max_size=300))
def test_the_filter_is_deterministic_and_never_leaves_a_blocked_term(text: str) -> None:
    first, second = filter_narration(text), filter_narration(text)
    assert first == second
    if first.filtered:
        assert filter_narration(first.text).filtered is False or first.text == FALLBACK
    else:
        assert first.text == text
