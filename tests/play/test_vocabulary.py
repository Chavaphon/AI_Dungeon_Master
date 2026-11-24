"""Play modes and the beginner vocabulary (WBS 13.2).

Run: pytest tests/play/test_vocabulary.py -v
"""

import pytest

from adm.play.vocabulary import JARGON, TERMS, Mode


def test_beginner_is_the_first_mode() -> None:
    assert [m.value for m in Mode] == ["beginner", "veteran"]


def test_the_vocabulary_is_the_issue_table() -> None:
    assert TERMS == {
        "HP": "health",
        "AC": "how hard to hit",
        "DC": "difficulty",
        "spell slot": "spell charge",
        "initiative": "turn order",
        "advantage": "you have the upper hand",
        "disadvantage": "the odds are against you",
        "cantrip": "a spell you can always cast",
        "unconscious": "knocked out",
    }


@pytest.mark.parametrize("text", ["1d20", "roll a d20", "2d8+3", "+5", "vs AC 12", "DC 12", "4 HP"])
def test_jargon_is_found(text: str) -> None:
    assert JARGON.search(text)


@pytest.mark.parametrize(
    "text",
    ["giant rat 1", "stage 3 of 3", "Loading llama3.1:8b...", "added 2", "HPs", "a dc"],
)
def test_plain_words_are_not_jargon(text: str) -> None:
    assert JARGON.search(text) is None
