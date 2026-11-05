"""Hit-point band, status and HP-number comparison for the automated checker
(WBS 8.7, CLAUDE.md section 10.3 items 2 and 3).

It implements the rule of docs/rubric.md section 5 (WBS 8.2) for the part a
lexicon can decide, and reports `CONTRADICT` **candidates with a confidence
flag**. The thresholds are not defined here: the actual band always comes from
`hp_band` in `adm/engine/combat.py`, the one definition the engine and the
checker share (docs/conventions.md section 1). This module adds only the phrase
lexicon of CLAUDE.md section 10.2 and the rules for reading it.

**Band phrases** (`LEXICON`) are matched case-insensitively. There is no
lemmatiser, so each lexicon entry lists its inflections ("collapses",
"collapsed", "fell"). The longest phrase wins: "close to collapse" is
`badly_hurt`, not `unconscious`. Each phrase implies a *set* of bands:

- An intensity word before "wounded", "hurt", "injured" or "bleeding" decides
  the band (rubric section 5.3): "badly wounded" is `badly_hurt`, "barely hurt"
  is `healthy`, and "slightly wounded" is `healthy` or `wounded`, because the
  rubric scores no divergence when a phrase can honestly be read as either of
  two bands and the actual band is one of them.
- A divergence is a phrase whose bands do not include the actual band. Adjacent
  bands are **not** forgiven (rubric section 5.2): "barely standing" at 14 of
  20 is a candidate.

**Not band phrases** (rubric section 5.3), skipped so the checker under-reports
as CLAUDE.md section 10.2 requires:

1. Events: a phrase followed by its object ("the blade hurt you", "you
   wounded the rat").
2. Negation within three words before ("not hurt", "no longer bleeding", "far
   from dying").
3. Figurative uses about something else: an adjective directly before a noun
   that is not a combatant ("the dying torchlight", "a battered shield"), and a
   verb whose subject is not a combatant ("the barrels collapse", "night
   falls"). "The wounded rat" is attributed to the rat.
4. "Falls", "collapses" and "crumples" that do not mean losing consciousness
   ("falls back", "falls silent"; rubric section 5.5 rule 1).

The past and the future ("one more hit and you'll fall", "earlier you were
nearly killed") cannot be told apart reliably, so a sentence with a hedge word
makes its candidates `low` confidence instead of skipping them.

**Who a phrase is about** (rubric section 5.4 rule 2). "You", "your" and the
player character's name are the player character. An NPC combatant is named by
any word of its `display_name` other than a size or colour word ("rat" for
"giant rat"). A phrase is attributed, in order, to the combatant named just
before or after it, then to every combatant named in its sentence, then to
those of the sentence before. It is a candidate only when its bands include the
band of **none** of them, so a phrase that might be about someone it fits is
never flagged. Anything but a single named subject is `low` confidence.

**Status** (rubric section 5.5 rule 2): a combatant at 0 HP named directly
before an attack, speech or flight verb ("the rat lunges", "you swing") is one
`CONTRADICT`. A combatant above 0 HP narrated as down is the band check.

**HP numbers**: "3 hit points left", "7 of 20 HP" is a candidate when no subject
has that `current_hp` (and that `max_hp`, if given). A number after "loses",
"takes", "deals", "heals" and the like is a change, not a value, and is skipped.

**One per combatant** (rubric section 5.4 rule 3, section 3 rule 2): a
narration gets at most one candidate per subject, the first high-confidence one
or else the first.

**Known blind spots**, for WBS 8.10 to measure: band phrases outside the
lexicon ("fully restored", "half dead"); pronoun subjects in a sentence with
several combatants; a phrase that fits a bystander in the same sentence; acting
verbs after a pronoun ("it lunges"); past and future claims (flagged, low);
and spelled-out HP numbers above thirty.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Literal

from adm.engine.combat import HpBand, hp_band
from adm.eval.entities import sentences

Doc = dict[str, Any]
Kind = Literal["band", "status", "hp_number"]
Confidence = Literal["high", "low"]

HEALTHY: HpBand = "healthy"
WOUNDED: HpBand = "wounded"
BADLY_HURT: HpBand = "badly_hurt"
UNCONSCIOUS: HpBand = "unconscious"

# CLAUDE.md section 10.2, with inflections in place of lemmatisation.
LEXICON: dict[HpBand, tuple[str, ...]] = {
    HEALTHY: (
        "unhurt",
        "unharmed",
        "unscathed",
        "fresh",
        "barely a scratch",
        "fine",
        "uninjured",
    ),
    WOUNDED: (
        "hurt",
        "wounded",
        "bleeding",
        "bleeds",
        "bleed",
        "bled",
        "bruised",
        "battered",
        "injured",
        "sore",
    ),
    BADLY_HURT: (
        "barely standing",
        "near death",
        "dying",
        "at death's door",
        "close to collapse",
        "gravely wounded",
        "on the brink",
        "failing",
    ),
    UNCONSCIOUS: (
        "unconscious",
        "collapse",
        "collapses",
        "collapsed",
        "collapsing",
        "fall",
        "falls",
        "fell",
        "fallen",
        "falling",
        "out cold",
        "senseless",
        "crumple",
        "crumples",
        "crumpled",
        "crumpling",
    ),
}
# Lexicon words that are a band phrase only in some senses: always low confidence.
AMBIGUOUS = frozenset(
    [
        "fine",
        "fresh",
        "sore",
        "failing",
        "collapse",
        "collapses",
        "collapsed",
        "collapsing",
        "fall",
        "falls",
        "fell",
        "fallen",
        "falling",
        "crumple",
        "crumples",
        "crumpled",
        "crumpling",
    ]
)
# Lexicon words that are verbs: they need a combatant subject (rule 3).
VERBS = frozenset(
    [
        "bleeds",
        "bleed",
        "bled",
        "collapse",
        "collapses",
        "collapsed",
        "collapsing",
        "fall",
        "falls",
        "fell",
        "fallen",
        "falling",
        "crumple",
        "crumples",
        "crumpled",
        "crumpling",
    ]
)
# Rubric section 5.3: intensity words decide the band of these words.
INTENSIFIABLE = frozenset(["wounded", "hurt", "injured", "bleeding"])
INTENSITY: dict[str, frozenset[HpBand]] = {
    **dict.fromkeys(
        [
            "badly",
            "gravely",
            "seriously",
            "terribly",
            "severely",
            "grievously",
            "mortally",
            "critically",
            "heavily",
            "horribly",
            "deeply",
        ],
        frozenset({BADLY_HURT}),
    ),
    **dict.fromkeys(["barely", "hardly", "scarcely"], frozenset({HEALTHY})),
    **dict.fromkeys(["slightly", "lightly", "mildly"], frozenset({HEALTHY, WOUNDED})),
}

_NEGATIONS = frozenset(["not", "no", "never", "nor", "without", "cannot"])
_NEGATION_PAIRS = frozenset({("far", "from"), ("no", "longer")})
# Words after a phrase that make it an event ("hurt you") or fall away from a
# combatant ("falls back").
_OBJECTS = frozenset(
    [
        "you",
        "him",
        "her",
        "it",
        "them",
        "the",
        "a",
        "an",
        "its",
        "his",
        "their",
        "your",
        "my",
        "our",
        "this",
        "that",
    ]
)
_NOT_DOWN = frozenset(
    [
        "back",
        "away",
        "aside",
        "behind",
        "forward",
        "silent",
        "still",
        "quiet",
        "short",
        "apart",
        "upon",
        "into",
        "in",
    ]
)
# Words an adjective may stand before without describing something else.
_FUNCTION = frozenset(
    [
        "and",
        "but",
        "or",
        "as",
        "yet",
        "now",
        "still",
        "from",
        "by",
        "with",
        "at",
        "in",
        "on",
        "after",
        "against",
        "beside",
        "under",
        "near",
        "to",
        "for",
        "of",
        "again",
        "too",
        "even",
    ]
)
_JOINERS = frozenset(["and", "then", "but", "or", "yet", "finally", "suddenly"])
_PRONOUNS = frozenset(["it", "he", "she", "they", "who", "which"])
SECOND_PERSON = frozenset(["you", "your", "yours", "yourself"])
# Words of a display name that do not name it alone.
DESCRIPTIVE = frozenset(
    [
        "the",
        "a",
        "an",
        "of",
        "giant",
        "little",
        "big",
        "wild",
        "grey",
        "gray",
        "old",
        "young",
        "great",
    ]
)
HEDGE = re.compile(
    r"\b(if|would|could|might|will|should|unless|earlier|almost|nearly|once|before)\b|['’]ll\b",
    re.IGNORECASE,
)

# Rubric section 5.5 rule 2: attacking, speaking or fleeing.
_ACT_FORMS = {
    "attack": ("attacks", "attacked"),
    "bite": ("bites", "bit"),
    "lunge": ("lunges", "lunged"),
    "strike": ("strikes", "struck"),
    "swing": ("swings", "swung"),
    "slash": ("slashes", "slashed"),
    "stab": ("stabs", "stabbed"),
    "claw": ("claws", "clawed"),
    "charge": ("charges", "charged"),
    "leap": ("leaps", "leapt", "leaped"),
    "pounce": ("pounces", "pounced"),
    "flee": ("flees", "fled"),
    "run": ("runs", "ran"),
    "retreat": ("retreats", "retreated"),
    "say": ("says", "said"),
    "shout": ("shouts", "shouted"),
    "speak": ("speaks", "spoke"),
    "cast": ("casts",),
    "shoot": ("shoots", "shot"),
    "kick": ("kicks", "kicked"),
    "grab": ("grabs", "grabbed"),
}
# Third-person forms follow a name; base forms follow "you".
ACTS_THIRD = frozenset(f for forms in _ACT_FORMS.values() for f in forms)
ACTS_YOU = frozenset(_ACT_FORMS) | ACTS_THIRD

_NUMBER_WORDS = {
    w: i
    for i, w in enumerate(
        [
            "zero",
            "one",
            "two",
            "three",
            "four",
            "five",
            "six",
            "seven",
            "eight",
            "nine",
            "ten",
            "eleven",
            "twelve",
            "thirteen",
            "fourteen",
            "fifteen",
            "sixteen",
            "seventeen",
            "eighteen",
            "nineteen",
            "twenty",
        ]
    )
}
_NUM = r"(\d+|" + "|".join(_NUMBER_WORDS) + r")"
_HP_NUMBER = re.compile(
    rf"\b{_NUM}(?:\s*(?:/|of|out of)\s*{_NUM})?\s+(?:hit points?|hp|health)\b", re.IGNORECASE
)
_CHANGE = frozenset(
    [
        "lose",
        "loses",
        "lost",
        "losing",
        "take",
        "takes",
        "took",
        "taking",
        "deal",
        "deals",
        "dealt",
        "dealing",
        "heal",
        "heals",
        "healed",
        "healing",
        "restore",
        "restores",
        "restored",
        "regain",
        "regains",
        "regained",
        "recover",
        "recovers",
        "recovered",
        "for",
        "extra",
        "another",
        "more",
    ]
)

_TOKEN = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)*")


def _key(phrase: str) -> tuple[str, ...]:
    return tuple(phrase.replace("’", "'").lower().split())


PHRASES: dict[tuple[str, ...], HpBand] = {
    _key(p): band for band, phrases in LEXICON.items() for p in phrases
}
_LONGEST = max(len(k) for k in PHRASES)


@dataclass(frozen=True)
class Token:
    word: str
    start: int
    end: int


@dataclass(frozen=True)
class Combatants:
    """Who a narration can describe: each naming word and the combatants it names."""

    names: Mapping[str, frozenset[str]]
    bands: Mapping[str, HpBand]
    hp: Mapping[str, tuple[int, int]]

    @classmethod
    def of(cls, state: Mapping[str, Any]) -> Combatants:
        names: dict[str, set[str]] = {}
        bands: dict[str, HpBand] = {}
        hp: dict[str, tuple[int, int]] = {}
        for cid in sorted(state.get("combatants", {})):
            c = state["combatants"][cid]
            bands[cid] = hp_band(c["current_hp"], c["max_hp"])
            hp[cid] = (c["current_hp"], c["max_hp"])
            words = [w.lower() for w in _TOKEN.findall(c["display_name"])]
            if c.get("is_player_character"):
                words += SECOND_PERSON
            for word in words:
                if word not in DESCRIPTIVE:
                    names.setdefault(name_word(word), set()).add(cid)
        return cls({w: frozenset(ids) for w, ids in names.items()}, bands, hp)

    def named(self, word: str) -> frozenset[str]:
        return self.names.get(name_word(word), frozenset())


@dataclass(frozen=True)
class BandCandidate:
    """A phrase whose HP claim fits none of the combatants it may describe."""

    kind: Kind
    mention: str
    start: int
    end: int
    confidence: Confidence
    sentence: str
    subject: tuple[str, ...]
    implied: tuple[str, ...]
    actual: tuple[str, ...]

    def to_dict(self) -> Doc:
        return {
            "kind": self.kind,
            "mention": self.mention,
            "span": [self.start, self.end],
            "confidence": self.confidence,
            "sentence": self.sentence,
            "subject": list(self.subject),
            "implied": list(self.implied),
            "actual": list(self.actual),
        }


def name_word(word: str) -> str:
    word = re.sub(r"['’]s$", "", word)
    if len(word) > 3 and word.endswith("s") and not word.endswith(("ss", "us", "is")):
        return word[:-1]
    return word


def tokenize(sentence: str) -> list[Token]:
    return [
        Token(m.group().lower().replace("’", "'"), m.start(), m.end())
        for m in _TOKEN.finditer(sentence)
    ]


def adjacent(sentence: str, left: Token, right: Token) -> bool:
    """Whether only whitespace separates two tokens."""
    return not sentence[left.end : right.start].strip()


def _match(tokens: list[Token], i: int) -> tuple[int, HpBand] | None:
    """The longest lexicon phrase starting at token `i`: its length and band."""
    for n in range(min(_LONGEST, len(tokens) - i), 0, -1):
        band = PHRASES.get(tuple(t.word for t in tokens[i : i + n]))
        if band is not None:
            return n, band
    return None


def negated(tokens: list[Token], i: int) -> bool:
    before = [t.word for t in tokens[max(0, i - 3) : i]]
    pairs = set(zip(before, before[1:], strict=False))
    return any(w in _NEGATIONS or w.endswith("n't") for w in before) or bool(
        pairs & _NEGATION_PAIRS
    )


def subject_before(
    sentence: str, tokens: list[Token], i: int, cast: Combatants
) -> frozenset[str] | None:
    """The combatants named just before token `i`, skipping adverbs. `None` when
    the word before is no combatant: the phrase is about something else. An
    empty set when it is a pronoun, a joiner or punctuation: ask the sentence."""
    j = i - 1
    while j >= 0 and tokens[j].word.endswith("ly") and tokens[j].word not in cast.names:
        j -= 1
    if j < 0 or not adjacent(sentence, tokens[j], tokens[j + 1]):
        return frozenset()
    word = tokens[j].word
    if named := cast.named(word):
        return named
    if word in _PRONOUNS or word in _JOINERS:
        return frozenset()
    return None


def _sentence_subjects(tokens: list[Token], cast: Combatants) -> list[frozenset[str]]:
    """Each distinct group of combatants named in a sentence, in order."""
    groups: list[frozenset[str]] = []
    for t in tokens:
        named = cast.named(t.word)
        if named and named not in groups:
            groups.append(named)
    return groups


def _bands_of(cast: Combatants, subject: frozenset[str]) -> tuple[str, ...]:
    return tuple(sorted({cast.bands[c] for c in subject}))


def _phrase_candidates(
    sentence: str,
    base: int,
    tokens: list[Token],
    cast: Combatants,
    previous: list[frozenset[str]],
    hedged: bool,
) -> Iterable[BandCandidate]:
    here = _sentence_subjects(tokens, cast)
    i = 0
    while i < len(tokens):
        found = _match(tokens, i)
        if found is None:
            i += 1
            continue
        n, band = found
        first, last = tokens[i], tokens[i + n - 1]
        nxt = tokens[i + n] if i + n < len(tokens) else None
        phrase = tuple(t.word for t in tokens[i : i + n])
        i += n
        bands = frozenset({band})
        direct: frozenset[str] | None = frozenset()
        sure = n > 1 or phrase[0] not in AMBIGUOUS

        if negated(tokens, i - n):
            continue
        if nxt is not None and adjacent(sentence, last, nxt):
            if nxt.word in _OBJECTS:  # an event: "hurt you", "fell the rat"
                continue
            if phrase[-1] in VERBS and nxt.word in _NOT_DOWN:  # "falls back"
                continue
        if n == 1 and phrase[0] in INTENSIFIABLE and i - n > 0:
            intensity = INTENSITY.get(tokens[i - n - 1].word)
            if intensity is not None:
                bands, first = intensity, tokens[i - n - 1]
        if n == 1 and phrase[0] in VERBS:
            direct = subject_before(sentence, tokens, i - n, cast)
            if direct is None:  # "the barrels collapse"
                continue
        elif (
            n == 1
            and nxt is not None
            and adjacent(sentence, last, nxt)
            and nxt.word not in _FUNCTION
            and not nxt.word.endswith("ly")
        ):
            direct = cast.named(nxt.word)  # "the wounded rat"
            if not direct:  # "the dying torchlight"
                continue
        elif i - n > 0 and adjacent(sentence, tokens[i - n - 1], tokens[i - n]):
            direct = cast.named(tokens[i - n - 1].word)  # "Lyra, unhurt" is not adjacent

        if direct:
            subjects, single = [direct], True
        elif here:
            subjects, single = here, len(here) == 1
        elif previous:
            subjects, single = previous, False
        else:
            continue
        subject = frozenset().union(*subjects)
        actual = _bands_of(cast, subject)
        if bands & set(actual):
            continue
        yield BandCandidate(
            "band",
            sentence[first.start : last.end],
            base + first.start,
            base + last.end,
            "high" if sure and single and not hedged else "low",
            sentence,
            tuple(sorted(subject)),
            tuple(sorted(bands)),
            actual,
        )


def _status_candidates(
    sentence: str, base: int, tokens: list[Token], cast: Combatants, hedged: bool
) -> Iterable[BandCandidate]:
    for i, t in enumerate(tokens):
        if t.word not in ACTS_YOU:
            continue
        subject = subject_before(sentence, tokens, i, cast)
        if not subject:
            continue
        you = tokens[i - 1].word in SECOND_PERSON
        if t.word not in (ACTS_YOU if you else ACTS_THIRD):
            continue
        actual = _bands_of(cast, subject)
        if actual != (UNCONSCIOUS,):
            continue
        start = next(j for j in range(i - 1, -1, -1) if cast.named(tokens[j].word))
        yield BandCandidate(
            "status",
            sentence[tokens[start].start : t.end],
            base + tokens[start].start,
            base + t.end,
            "low" if hedged else "high",
            sentence,
            tuple(sorted(subject)),
            ("active",),
            actual,
        )


def _number(text: str) -> int:
    return int(text) if text.isdigit() else _NUMBER_WORDS[text.lower()]


def _number_candidates(
    sentence: str,
    base: int,
    tokens: list[Token],
    cast: Combatants,
    previous: list[frozenset[str]],
    hedged: bool,
) -> Iterable[BandCandidate]:
    here = _sentence_subjects(tokens, cast)
    subjects = here or previous
    if not subjects:
        return
    for m in _HP_NUMBER.finditer(sentence):
        before = [t.word for t in tokens if t.end <= m.start()][-3:]
        if any(w in _CHANGE for w in before):  # "loses 3 hit points"
            continue
        current = _number(m.group(1))
        maximum = _number(m.group(2)) if m.group(2) else None
        subject = frozenset().union(*subjects)
        if any(cast.hp[c][0] == current and maximum in (None, cast.hp[c][1]) for c in subject):
            continue
        yield BandCandidate(
            "hp_number",
            m.group(),
            base + m.start(),
            base + m.end(),
            "high" if len(here) == 1 and not hedged else "low",
            sentence,
            tuple(sorted(subject)),
            (f"{current}" if maximum is None else f"{current}/{maximum}",),
            tuple(sorted({f"{cast.hp[c][0]}/{cast.hp[c][1]}" for c in subject})),
        )


def band_candidates(narration: str, state: Mapping[str, Any]) -> list[BandCandidate]:
    """Every HP `CONTRADICT` candidate in `narration`, at most one per subject."""
    cast = Combatants.of(state)
    found: list[BandCandidate] = []
    previous: list[frozenset[str]] = []
    for base, sentence in sentences(narration):
        tokens = tokenize(sentence)
        hedged = bool(HEDGE.search(sentence))
        found += _phrase_candidates(sentence, base, tokens, cast, previous, hedged)
        found += _status_candidates(sentence, base, tokens, cast, hedged)
        found += _number_candidates(sentence, base, tokens, cast, previous, hedged)
        previous = _sentence_subjects(tokens, cast) or previous
    kept: dict[tuple[str, ...], BandCandidate] = {}
    for c in sorted(found, key=lambda c: (c.confidence != "high", c.start)):
        kept.setdefault(c.subject, c)
    return sorted(kept.values(), key=lambda c: c.start)
