"""Entity-mention extraction for the automated checker (WBS 8.6, CLAUDE.md section 10.3 item 1).

`PHANTOM` is a narration naming an item, character or location that is in
neither the state nor the scenario (docs/rubric.md section 2). This module
finds the mechanically decidable part of that: mentions that match nothing in
scope. It reports **candidates with a confidence flag**, never final scores. A
human confirms or rejects each one (CLAUDE.md section 10.3).

**Scope** (`Scope.of`) is every `display_name` in the state and in the
scenario, the scenario's `locations` and its title, and the two spells the
engine owns. A word is in scope when it is a word of one of those names. So
"the rat" is in scope for "giant rat", "sword" for "short sword", and "Keeper"
for "the Keeper". An item at quantity 0 keeps its definition, so it stays in
scope (docs/rubric.md, example R-neg).

**Candidates** (`phantom_candidates`) are three kinds of mention:

- `item`: a word from `ITEM_WORDS`, things a character can pick up, use, give
  or spend (rubric section 6.1 rule 2), that is not in scope. "You raise your
  lantern" in a scenario with no lantern.
- `character`: a word from `CHARACTER_WORDS`, people and creatures, that is
  not in scope. "A hooded stranger steps out".
- `proper_noun`: a run of capitalised words in mid-sentence, none of which is
  in scope. "You recall Mira's warning". It is always low confidence, since a
  name can be a place, a deity or a figure of speech.

Plurals are matched in the singular ("lanterns" is "lantern"), and a
possessive `'s` is dropped. A word that repeats in one narration is reported
once, at its first mention (rubric section 3 rule 3).

**Confidence** is `high` for an item or character word in a plain sentence. It
is `low` for every proper noun, for the words in `AMBIGUOUS_WORDS` ("guard",
"ring", "figure"), and for any mention in a sentence with a negation or a
hypothetical ("you have no lantern", "if a guard came"). Ambiguity is resolved
in favour of no divergence (CLAUDE.md section 10.2), so the checker
under-reports: a candidate needs a lexicon word or a capitalised name, and
anything else is left to the human pass.

**Known blind spots**, for WBS 8.10 to measure: phantom locations unless they
are capitalised ("the crypt below"); too many of a kind ("three rats" when the
state has two); a phantom item or creature whose noun is not in a lexicon; a
phantom whose noun is a word of an in-scope name ("a silver key" when an iron
key is in scope); and parts and features, which are never flagged (rubric
section 6.1 rules 1 and 5).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Literal

Doc = dict[str, Any]
Kind = Literal["item", "character", "proper_noun"]
Confidence = Literal["high", "low"]

# The engine's two spells (CLAUDE.md section 4.6); their ids are not in the state.
SPELL_NAMES = ("Fire Bolt", "Cure Wounds")
ENTITY_TABLES = ("combatants", "item_definitions", "npc_relationships", "quests")

# Things that can be picked up, used, given or spent (rubric section 6.1 rule 2).
# Left out on purpose: generic words that can name an in-scope item ("blade",
# "weapon", "gear"), worn things that are part of a character ("cloak", "boot",
# "helm"; rule 5), fixtures ("crate", "ladder") and words that are mostly verbs
# ("note", "lock", "whistle").
ITEM_WORDS = frozenset(
    [
        "amulet",
        "arrow",
        "axe",
        "bag",
        "bandage",
        "battleaxe",
        "blanket",
        "book",
        "bottle",
        "bracelet",
        "brooch",
        "bucket",
        "candle",
        "chalice",
        "claymore",
        "coin",
        "collar",
        "compass",
        "crossbow",
        "crowbar",
        "cudgel",
        "dagger",
        "dart",
        "diary",
        "flask",
        "flute",
        "gem",
        "glaive",
        "goblet",
        "hammer",
        "handaxe",
        "harp",
        "hatchet",
        "idol",
        "ingot",
        "javelin",
        "jewel",
        "journal",
        "key",
        "knife",
        "lance",
        "lantern",
        "ledger",
        "letter",
        "locket",
        "lockpick",
        "longbow",
        "longsword",
        "lute",
        "mace",
        "manifest",
        "map",
        "medallion",
        "mug",
        "necklace",
        "parchment",
        "pickaxe",
        "pitchfork",
        "potion",
        "pouch",
        "purse",
        "quarterstaff",
        "quill",
        "rapier",
        "ration",
        "relic",
        "rope",
        "sack",
        "satchel",
        "scimitar",
        "scroll",
        "scythe",
        "shield",
        "shovel",
        "sickle",
        "signet",
        "spear",
        "spellbook",
        "spoon",
        "spyglass",
        "statuette",
        "sword",
        "talisman",
        "tankard",
        "tinderbox",
        "tome",
        "torch",
        "totem",
        "trident",
        "trinket",
        "vial",
        "wand",
        "warhammer",
        "whip",
    ]
)

# People and creatures.
CHARACTER_WORDS = frozenset(
    [
        "abbot",
        "apprentice",
        "archer",
        "assassin",
        "bandit",
        "bard",
        "beggar",
        "blacksmith",
        "boar",
        "boy",
        "brigand",
        "captain",
        "cat",
        "child",
        "cleric",
        "constable",
        "crab",
        "cultist",
        "deer",
        "dog",
        "dragon",
        "dwarf",
        "elf",
        "farmer",
        "ferryman",
        "fisherman",
        "fox",
        "gargoyle",
        "ghoul",
        "girl",
        "gnome",
        "goblin",
        "guardsman",
        "harpy",
        "hermit",
        "hound",
        "innkeeper",
        "knight",
        "kobold",
        "leech",
        "mage",
        "merchant",
        "miner",
        "monk",
        "ogre",
        "orc",
        "peasant",
        "pilgrim",
        "priest",
        "prince",
        "princess",
        "queen",
        "rat",
        "raven",
        "servant",
        "shopkeeper",
        "skeleton",
        "smuggler",
        "snake",
        "soldier",
        "spider",
        "stranger",
        "thief",
        "thug",
        "troll",
        "urchin",
        "villager",
        "wanderer",
        "warrior",
        "witch",
        "wizard",
        "wolf",
        "woman",
        "wraith",
        "zombie",
    ]
)

# Words that are a phantom only in some senses: "on guard", "the wind whistles
# past the horn", "a ghost of a smile", "a figure in the mist". Flagged with low
# confidence.
AMBIGUOUS_WORDS: dict[str, Kind] = {
    **dict.fromkeys(
        [
            "bow",
            "chain",
            "chest",
            "club",
            "horn",
            "lamp",
            "mask",
            "net",
            "oil",
            "ring",
            "staff",
            "wine",
            "cider",
            "cart",
        ],
        "item",
    ),
    **dict.fromkeys(
        [
            "bat",
            "beast",
            "brother",
            "creature",
            "drunk",
            "figure",
            "ghost",
            "guard",
            "hunter",
            "keeper",
            "king",
            "lord",
            "man",
            "noble",
            "scout",
            "shape",
            "sister",
            "someone",
        ],
        "character",
    ),
}
LEXICON = ITEM_WORDS | CHARACTER_WORDS | AMBIGUOUS_WORDS.keys()

_WORD = re.compile(r"[A-Za-z]+(?:[-'’][A-Za-z]+)*")
_SENTENCE_END = re.compile(r"(?<=[.!?])[\"'”’)]*\s+")
_SENTENCE_OPENERS = set("\"“'‘([:;—–-")
_HEDGE = re.compile(
    r"\b(no|not|never|without|nothing|none|nobody|if|would|could|might|perhaps|maybe)\b"
    r"|n['’]t\b",
    re.IGNORECASE,
)
# Capitalised words that are not names wherever they appear.
_NOT_NAMES = frozenset({"i", "you", "your", "yours", "dm", "player"})


def singular(word: str) -> str:
    """A crude singular of a lowercase word: enough to match "lanterns" to
    "lantern" and "torches" to "torch", with no lemmatiser to install."""
    word = re.sub(r"['’]s$", "", word)
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 4 and word.endswith(("ches", "shes", "sses", "xes")):
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith(("ss", "us", "is")):
        return word[:-1]
    return word


def words(text: str) -> list[str]:
    """The singular lowercase words of `text`; hyphenated words also count by part."""
    out = []
    for match in _WORD.finditer(text):
        token = match.group().lower()
        out.append(singular(token))
        out += [singular(part) for part in re.split(r"[-'’]", token) if len(part) > 1]
    return out


@dataclass(frozen=True)
class Scope:
    """The names a narration may use without a `PHANTOM` (docs/rubric.md section 1)."""

    names: tuple[str, ...]
    words: frozenset[str]

    @classmethod
    def of(cls, scenario: Any, state: Mapping[str, Any]) -> Scope:
        """The scope of one turn: the state's and the scenario's display names,
        the scenario's locations and title, and the spells."""
        names: list[str] = [scenario.display_name, *scenario.locations, *SPELL_NAMES]
        for source in (scenario.initial_state, state):
            for table in ENTITY_TABLES:
                names += [entity["display_name"] for entity in source.get(table, {}).values()]
        unique = tuple(dict.fromkeys(names))
        return cls(unique, frozenset(w for name in unique for w in words(name)))

    def __contains__(self, word: str) -> bool:
        return singular(word.lower()) in self.words


@dataclass(frozen=True)
class Candidate:
    """A mention that matches nothing in scope: a `PHANTOM` candidate."""

    kind: Kind
    mention: str
    start: int
    end: int
    confidence: Confidence
    sentence: str

    def to_dict(self) -> Doc:
        return {
            "kind": self.kind,
            "mention": self.mention,
            "span": [self.start, self.end],
            "confidence": self.confidence,
            "sentence": self.sentence,
        }


def sentences(text: str) -> Iterable[tuple[int, str]]:
    start = 0
    for match in _SENTENCE_END.finditer(text):
        yield start, text[start : match.start()]
        start = match.end()
    if start < len(text):
        yield start, text[start:]


def _opens_sentence(sentence: str, offset: int) -> bool:
    """Whether the word at `offset` is the first word of the sentence or of a
    quotation, clause after a colon, or aside, where any word is capitalised."""
    before = sentence[:offset].rstrip()
    return not before or before[-1] in _SENTENCE_OPENERS


def phantom_candidates(narration: str, scope: Scope) -> list[Candidate]:
    """Every `PHANTOM` candidate in `narration`, in order of first mention."""
    found: dict[tuple[Kind, str], Candidate] = {}

    def add(kind: Kind, key: str, start: int, end: int, sure: bool, sentence: str) -> None:
        confidence: Confidence = "high" if sure and not _HEDGE.search(sentence) else "low"
        found.setdefault(
            (kind, key), Candidate(kind, narration[start:end], start, end, confidence, sentence)
        )

    for base, sentence in sentences(narration):
        tokens = list(_WORD.finditer(sentence))
        i = 0
        while i < len(tokens):
            match = tokens[i]
            word = singular(match.group().lower())
            start, end = base + match.start(), base + match.end()
            if word not in scope.words:
                if word in ITEM_WORDS:
                    add("item", word, start, end, True, sentence)
                elif word in CHARACTER_WORDS:
                    add("character", word, start, end, True, sentence)
                elif word in AMBIGUOUS_WORDS:
                    add(AMBIGUOUS_WORDS[word], word, start, end, False, sentence)
            # A run of capitalised words in mid-sentence is a name.
            if match.group()[0].isupper() and not _opens_sentence(sentence, match.start()):
                j = i
                while j + 1 < len(tokens) and tokens[j + 1].group()[0].isupper():
                    j += 1
                run = tokens[i : j + 1]
                run_words = [singular(t.group().lower()) for t in run]
                known = any(w in scope.words or w in _NOT_NAMES for w in run_words)
                lexical = all(w in LEXICON for w in run_words)
                if not known and not lexical:
                    span = (base + run[0].start(), base + run[-1].end())
                    add("proper_noun", " ".join(run_words), *span, False, sentence)
                i = j + 1
                continue
            i += 1
    return sorted(found.values(), key=lambda c: c.start)
