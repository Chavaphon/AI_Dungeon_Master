"""Play modes and the beginner vocabulary (WBS 13.2).

`play` runs in beginner mode by default and in veteran mode with
`--mode veteran`. The mode is display only: it changes what the player sees,
never what is logged or sent to the model (CLAUDE.md section 15, item 75).

Beginner mode uses the plain words of `TERMS` in place of the game's jargon,
and shows no dice notation, modifiers, or AC, DC or HP numbers. Every
beginner-mode screen (13.2 to 13.8) takes its words from here, so a player
meets one name for each idea. `JARGON` is what beginner output must never
contain; the tests check every beginner screen against it.
"""

from __future__ import annotations

import re
from enum import StrEnum


class Mode(StrEnum):
    """How much of the rules `play` shows."""

    BEGINNER = "beginner"
    VETERAN = "veteran"


# The game's term -> its beginner wording (issue #255).
TERMS: dict[str, str] = {
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

# An HP band (`engine.combat.hp_band`) in words, in both modes.
BAND_WORDS: dict[str, str] = {
    "healthy": "healthy",
    "wounded": "wounded",
    "badly_hurt": "badly hurt",
    "unconscious": TERMS["unconscious"],
}

# A quest state in words, in both modes.
QUEST_WORDS: dict[str, str] = {
    "not_started": "not started",
    "active": "in progress",
    "completed": "completed",
    "failed": "failed",
}

# Dice notation ("1d20", "d8"), a signed modifier ("+5") or the words AC, DC, HP.
JARGON = re.compile(r"\b\d*d\d+\b|\+\d|\b(?:AC|DC|HP)\b")
