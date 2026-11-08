"""Relationship-stance comparison for the automated checker (WBS 8.8, CLAUDE.md
section 10.3 item 5).

`RELATION` is narration that treats an NPC in a way that does not fit its
recorded `stance` (docs/rubric.md sections 2 and 6.4). This module finds the
part a lexicon can decide and reports **candidates with a confidence flag**.

**Who is scored** (rubric section 6.4 rule 1): only the NPCs in
`npc_relationships`. A hostile creature with no stance, such as a giant rat,
never has a `RELATION` candidate. The stance is the one after the turn (rule 2),
which is the state the checker scores against.

**Stance markers** (`MARKERS`) are words for how an NPC treats the party. Each
implies a set of stances on the ladder `hostile, unfriendly, neutral, friendly,
allied`:

- `hostile`: open hostility ("spits", "threatens", "orders you out").
- `cold`: `hostile` or `unfriendly` ("glares", "coldly", "scowls", "sneers").
- `warm`: `friendly` or `allied` ("beams", "hugs", "warmly", "old friend").

There are no neutral markers. Businesslike behaviour ("nods", "points") is at
most two steps from either end of the ladder and is the commonest tone, so it
is left to the human pass rather than flagged.

**The rule** (rubric section 6.4 rule 3): behaviour that fits the recorded
stance, or one step either side, is not a divergence. A marker is a candidate
when **every** stance it implies is more than `ADJACENCY` steps from the
recorded one. So hostility toward a `neutral` NPC is flagged (the done-when of
WBS 8.8), as is warmth toward an `unfriendly` one (rubric example L1) and
hostility toward a `friendly` one (L2), while coldness toward `unfriendly` (L3)
or `neutral` is not. The allowance was kept at the rubric v1.0 freeze (WBS 8.12)
after the 8.11 pilot; setting `ADJACENCY` to 0 drops it.

**Not scored**, so the checker under-reports as CLAUDE.md section 10.2 requires:

1. A negated marker ("does not smile", "without warmth").
2. The player character's behaviour: a marker straight after "you" or the
   player character's name ("you glare at the Keeper").
3. A sentence that mixes warm markers with cold or hostile ones for the same
   NPC ("smiles coldly", "grins and threatens"): the tone is ambiguous.

**Who a marker is about**: the NPCs named in its sentence by any word of their
`display_name` except articles and size, age or colour words ("Keeper" for
"the Keeper", "Tobin" for "old Tobin"). With none named, those of the sentence
before. A marker is flagged only when it does not fit any of them.

**Confidence** is `high` for a marker that is not in `AMBIGUOUS` ("smiles",
"laughs", "grins" and "friend" can be mocking), about a single NPC named in its
own sentence, in a sentence that addresses the party (second person, the player
character's name or a quotation) with no hedge word. Everything else is `low`.

**One per NPC**: at most one candidate per NPC per narration, the first
high-confidence one or else the first (rubric section 3 rules 2 and 3).

**Known blind spots**, for WBS 8.10 to measure: markers outside the lexicon
(sarcasm, threats in dialogue without a marker word, "refuses to speak to
you"); behaviour toward someone other than the party ("the Keeper spits at the
rat"), flagged low when the sentence does not address the party; pronoun
subjects in a sentence naming several NPCs; and every one-step mismatch, which
the allowance forgives by design.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Literal

from adm.eval.bands import (
    DESCRIPTIVE,
    HEDGE,
    SECOND_PERSON,
    Token,
    name_word,
    negated,
    tokenize,
)
from adm.eval.entities import sentences

Doc = dict[str, Any]
Tone = Literal["hostile", "cold", "warm"]
Confidence = Literal["high", "low"]

LADDER = ("hostile", "unfriendly", "neutral", "friendly", "allied")
# Rubric section 6.4 rule 3: one step either side of the stance is forgiven.
ADJACENCY = 1

IMPLIES: dict[Tone, frozenset[str]] = {
    "hostile": frozenset({"hostile"}),
    "cold": frozenset({"hostile", "unfriendly"}),
    "warm": frozenset({"friendly", "allied"}),
}

# With inflections in place of lemmatisation, as in adm/eval/bands.py.
MARKERS: dict[Tone, tuple[str, ...]] = {
    "hostile": (
        "spit",
        "spits",
        "spat",
        "spitting",
        "threaten",
        "threatens",
        "threatened",
        "threatening",
        "threateningly",
        "menacing",
        "menacingly",
        "orders you out",
        "ordered you out",
        "get out",
        "shoves you",
        "shoved you",
        "slaps you",
        "slapped you",
        "attacks you",
        "attacked you",
        "hate",
        "hates",
        "hated",
        "loathe",
        "loathes",
        "loathing",
        "hostile",
        "hostility",
        "furious",
        "furiously",
        "enraged",
        "venom",
        "venomously",
        "brandishes",
        "brandished",
    ),
    "cold": (
        "coldly",
        "icily",
        "glare",
        "glares",
        "glared",
        "glaring",
        "scowl",
        "scowls",
        "scowled",
        "scowling",
        "sneer",
        "sneers",
        "sneered",
        "sneering",
        "frown",
        "frowns",
        "frowned",
        "frowning",
        "grunt",
        "grunts",
        "grunted",
        "curt",
        "curtly",
        "suspicious",
        "suspiciously",
        "distrustful",
        "distrustfully",
        "dismissive",
        "dismissively",
        "contempt",
        "contemptuously",
        "disdain",
        "disdainfully",
        "snarl",
        "snarls",
        "snarled",
        "snarling",
        "snaps at you",
        "snapped at you",
        "grumbles",
        "grumbled",
        "grudgingly",
        "unfriendly",
        "curses",
        "cursed",
    ),
    "warm": (
        "beam",
        "beams",
        "beamed",
        "beaming",
        "warmly",
        "warm smile",
        "warm welcome",
        "hug",
        "hugs",
        "hugged",
        "embrace",
        "embraces",
        "embraced",
        "old friend",
        "my friend",
        "friend",
        "friendly",
        "kindly",
        "fondly",
        "affectionately",
        "cheerfully",
        "gladly",
        "delighted",
        "welcomes you",
        "welcomed you",
        "claps you on the shoulder",
        "clapped you on the shoulder",
        "smile",
        "smiles",
        "smiled",
        "smiling",
        "grin",
        "grins",
        "grinned",
        "grinning",
        "laugh",
        "laughs",
        "laughed",
        "laughing",
    ),
}
# Markers that are often mocking or about something else: always low confidence.
AMBIGUOUS = frozenset(
    [
        "smile",
        "smiles",
        "smiled",
        "smiling",
        "grin",
        "grins",
        "grinned",
        "grinning",
        "laugh",
        "laughs",
        "laughed",
        "laughing",
        "friend",
        "grunt",
        "grunts",
        "grunted",
        "frown",
        "frowns",
        "frowned",
        "frowning",
        "curses",
        "cursed",
        "get out",
        "hate",
        "hates",
        "hated",
    ]
)

PHRASES: dict[tuple[str, ...], Tone] = {
    tuple(m.split()): tone for tone, markers in MARKERS.items() for m in markers
}
_LONGEST = max(len(k) for k in PHRASES)
_QUOTES = frozenset("\"“”‘’'")
_SKIP_BEFORE = frozenset(["and", "then", "also", "only", "just", "openly", "briefly"])


@dataclass(frozen=True)
class Npcs:
    """The NPCs with a stance, each naming word, and the player character's words."""

    names: Mapping[str, frozenset[str]]
    stance: Mapping[str, str]
    party: frozenset[str]

    @classmethod
    def of(cls, state: Mapping[str, Any]) -> Npcs:
        names: dict[str, set[str]] = {}
        stance: dict[str, str] = {}
        for nid in sorted(state.get("npc_relationships", {})):
            npc = state["npc_relationships"][nid]
            stance[nid] = npc["stance"]
            for token in tokenize(npc["display_name"]):
                if token.word not in DESCRIPTIVE:
                    names.setdefault(name_word(token.word), set()).add(nid)
        party = set(SECOND_PERSON)
        for c in state.get("combatants", {}).values():
            if c.get("is_player_character"):
                party |= {t.word for t in tokenize(c["display_name"])}
        return cls({w: frozenset(ids) for w, ids in names.items()}, stance, frozenset(party))

    def named(self, word: str) -> frozenset[str]:
        return self.names.get(name_word(word), frozenset())


@dataclass(frozen=True)
class StanceCandidate:
    """A marker whose implied stances are all too far from the recorded one."""

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
            "kind": "stance",
            "mention": self.mention,
            "span": [self.start, self.end],
            "confidence": self.confidence,
            "sentence": self.sentence,
            "subject": list(self.subject),
            "implied": list(self.implied),
            "actual": list(self.actual),
        }


def distance(stance: str, implied: Iterable[str]) -> int:
    """Steps on the ladder from `stance` to the nearest implied stance."""
    here = LADDER.index(stance)
    return min(abs(here - LADDER.index(s)) for s in implied)


def _markers(tokens: list[Token], party: frozenset[str]) -> list[tuple[int, int, Tone]]:
    """Every marker in a sentence that is not negated and not the party's own
    behaviour: its first token, its length and its tone."""
    found = []
    i = 0
    while i < len(tokens):
        for n in range(min(_LONGEST, len(tokens) - i), 0, -1):
            tone = PHRASES.get(tuple(t.word for t in tokens[i : i + n]))
            if tone is not None:
                break
        else:
            i += 1
            continue
        j = i - 1
        while j >= 0 and (tokens[j].word in _SKIP_BEFORE or tokens[j].word.endswith("ly")):
            j -= 1
        by_party = j >= 0 and tokens[j].word in party and tokens[j].word != "your"
        if not by_party and not negated(tokens, i):
            found.append((i, n, tone))
        i += n
    return found


def stance_candidates(narration: str, state: Mapping[str, Any]) -> list[StanceCandidate]:
    """Every `RELATION` candidate in `narration`, at most one per NPC."""
    npcs = Npcs.of(state)
    if not npcs.stance:
        return []
    found: list[StanceCandidate] = []
    previous: list[frozenset[str]] = []
    for base, sentence in sentences(narration):
        tokens = tokenize(sentence)
        here: list[frozenset[str]] = []
        for t in tokens:
            named = npcs.named(t.word)
            if named and named not in here:
                here.append(named)
        subjects, own = (here, True) if here else (previous, False)
        previous = here or previous
        markers = _markers(tokens, npcs.party)
        tones = {tone for _, _, tone in markers}
        if not subjects or not markers or ("warm" in tones and len(tones) > 1):
            continue
        subject = frozenset().union(*subjects)
        addressed = any(t.word in npcs.party for t in tokens) or bool(_QUOTES & set(sentence))
        plain = own and len(subjects) == 1 and addressed and not HEDGE.search(sentence)
        for i, n, tone in markers:
            implied = IMPLIES[tone]
            if any(distance(npcs.stance[s], implied) <= ADJACENCY for s in subject):
                continue
            first, last = tokens[i], tokens[i + n - 1]
            mention = sentence[first.start : last.end]
            found.append(
                StanceCandidate(
                    mention,
                    base + first.start,
                    base + last.end,
                    "high" if plain and mention.lower() not in AMBIGUOUS else "low",
                    sentence,
                    tuple(sorted(subject)),
                    tuple(s for s in LADDER if s in implied),
                    tuple(sorted({npcs.stance[s] for s in subject})),
                )
            )
    kept: dict[tuple[str, ...], StanceCandidate] = {}
    for c in sorted(found, key=lambda c: (c.confidence != "high", c.start)):
        kept.setdefault(c.subject, c)
    return sorted(kept.values(), key=lambda c: c.start)
