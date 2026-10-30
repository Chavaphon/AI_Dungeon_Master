"""The output safety filter (WBS 6.9, CLAUDE.md section 7).

The narration call's reply passes through `filter_narration` before the player
sees it and before it is logged as `narration`. The filter is a fixed lexicon
over sentences, with no model call and no randomness, so a replay filters the
same turns the same way (invariant 4), and it is the same in every condition
(invariant 7):

1. The text is split into sentences after `.`, `!` or `?` and whitespace.
2. A sentence that contains a blocked term (`BLOCKED_TERMS`) is removed. Terms
   match whole words, ignoring case; a term of several words matches across
   any run of whitespace.
3. If every sentence is removed, the player sees `FALLBACK` instead.

Combat violence is the game, so it is not blocked. The lexicon is out-of-genre
content only: sexual content and self-harm. It is a draft for the team to
confirm (docs/decisions.md, WBS 6.9).

**Filtered turns are counted, never silently dropped.** A filtered turn is still
narrated, logged and played: `narration` holds the filtered text,
`narration_filtered` is true, and the narration call's `raw_output` keeps the
unfiltered reply. The audit log refuses a record whose flag disagrees with its
text (`adm.engine.audit.record_errors`), and `filtered_turn_count` counts them
for the report.
Divergence scoring (M1) reads `narration`, the text the player saw.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

BLOCKED_TERMS: tuple[str, ...] = (
    # sexual content
    "rape",
    "raped",
    "rapes",
    "raping",
    "rapist",
    "sex",
    "sexual",
    "sexually",
    "porn",
    "pornographic",
    "orgasm",
    "genitals",
    # self-harm
    "suicide",
    "self-harm",
    "kill yourself",
    "killing yourself",
)
FALLBACK = "The moment passes, and the scene moves on."

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def _pattern(terms: Sequence[str]) -> re.Pattern[str]:
    words = (r"\s+".join(re.escape(w) for w in term.split()) for term in terms)
    return re.compile(r"(?<![\w-])(?:" + "|".join(words) + r")(?![\w-])", re.IGNORECASE)


_BLOCKED = _pattern(BLOCKED_TERMS)


@dataclass(frozen=True)
class SafetyResult:
    """What the player is shown, whether it differs from the reply, and why."""

    text: str
    filtered: bool
    matched: tuple[str, ...]


def filter_narration(text: str, terms: Sequence[str] | None = None) -> SafetyResult:
    """Remove every sentence of `text` that holds a blocked term."""
    blocked = _BLOCKED if terms is None else _pattern(terms)
    kept: list[str] = []
    matched: list[str] = []
    for sentence in _SENTENCE_END.split(text):
        found = [m.group(0).lower() for m in blocked.finditer(sentence)]
        if found:
            matched.extend(found)
        else:
            kept.append(sentence)
    if not matched:
        return SafetyResult(text, False, ())
    shown = " ".join(kept).strip() or FALLBACK
    return SafetyResult(shown, True, tuple(matched))
