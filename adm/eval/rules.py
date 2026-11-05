"""Rule violations for the automated checker: M4 (WBS 8.9, CLAUDE.md section 10.3
item 6).

M4 counts the four rule breaks of section 10.3 item 6: negative hit points, a
spell slot spent below zero, an action out of turn order and an action after
the encounter has ended. It is computed in every condition, in two parts that
write the same record with `category: "RULE"` (M4, not an M1 divergence):

**`state_audit`**, the state itself. Every turn's state after, executed call and
engine steps are checked: `current_hp` outside 0 to `max_hp`, `spell_slots_1`
or an inventory quantity below zero, an `attack`, `cast_spell` or `dodge` (the
player's or an `npc_action`) by a combatant that is not `active_combatant_id`,
and a combat action with no active encounter (Cure Wounds exempt, CLAUDE.md
section 6.3). The engine refuses all of these, so in condition D, and in A to
C's replayed ground truth, the expected count is zero: a non-zero count is a
harness bug, reported at full confidence with an empty `span`.

**`rule_violation`**, the narration against the state. In conditions A to C the
model plays the rules in prose, and in D it may narrate past what the engine
did. Each candidate is a narrated event the rules forbid, given the turn's
state and what the engine (D) or the ground truth (A to C) did:

- `after_encounter_end`: a combatant narrated attacking ("the rat lunges",
  "you swing") in a turn that began after the encounter ended
  (`encounter_outcome` set, no encounter active before or after).
- `out_of_turn`: during an encounter, a combatant narrated attacking when it
  made no attack or spell this turn: neither the executed call's actor nor an
  `npc_action`. A combatant group ("the rat" for two giant rats) is flagged
  only if none of it acted.
- `slot_below_zero`: Cure Wounds narrated ("you cast Cure Wounds", "a healing
  spell") when the player character had no level-1 slot before the turn.
- `negative_hp`: narration stating hit points below zero ("-3 hit points",
  "negative hit points").

An attack is an attack verb straight after a combatant's name ("the rat
lunges") or after "you" ("you swing"), with the subject found as in
`adm/eval/bands.py`. Negated verbs and the player's own attempts are handled
like the other checks: confidence is `low` for the player character as subject
(the player's input may ask for it), for a "healing spell" rather than the
spell's name, and in a sentence with a hedge word. A narration gets at most one
candidate per rule and subject.

**Known blind spots**, for WBS 8.10 to measure: attacks after a pronoun ("it
lunges"); attacks the lexicon misses ("sinks its teeth into you"); two attacks
by one combatant in a turn; spell slots narrated as spent without naming the
spell; and an attack narrated as an earlier event in the past perfect, which
may be flagged.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from adm.eval.bands import (
    HEDGE,
    SECOND_PERSON,
    Combatants,
    Token,
    negated,
    subject_before,
    tokenize,
)
from adm.eval.entities import sentences

Doc = dict[str, Any]
Rule = Literal["negative_hp", "slot_below_zero", "out_of_turn", "after_encounter_end"]
StateRule = Literal[
    "negative_hp",
    "hp_above_max",
    "slot_below_zero",
    "negative_quantity",
    "out_of_turn",
    "after_encounter_end",
]
Confidence = Literal["high", "low"]

ACTION_TOOLS = frozenset(["attack", "cast_spell", "dodge"])
ATTACK_TOOLS = frozenset(["attack", "cast_spell"])
CURE_WOUNDS = "spell_cure_wounds"
ACTOR_ARGUMENT = {"attack": "attacker_id", "cast_spell": "caster_id", "dodge": "actor_id"}

# Attack verbs: base forms follow "you"; third-person and past forms follow a name.
_ATTACK_FORMS = {
    "attack": ("attacks", "attacked"),
    "bite": ("bites", "bit"),
    "lunge": ("lunges", "lunged"),
    "strike": ("strikes", "struck"),
    "swing": ("swings", "swung"),
    "slash": ("slashes", "slashed"),
    "stab": ("stabs", "stabbed"),
    "claw": ("claws", "clawed"),
    "charge": ("charges", "charged"),
    "pounce": ("pounces", "pounced"),
    "shoot": ("shoots", "shot"),
    "kick": ("kicks", "kicked"),
    "hurl": ("hurls", "hurled"),
}
ATTACKS_THIRD = frozenset(f for forms in _ATTACK_FORMS.values() for f in forms)
ATTACKS_YOU = frozenset(_ATTACK_FORMS) | ATTACKS_THIRD

# Cure Wounds by name is sure; a description of healing magic is not.
_CURE_NAMED = re.compile(r"\bcure wounds\b", re.IGNORECASE)
_CURE_DESCRIBED = re.compile(r"\bhealing (?:spell|magic|prayer|light)\b", re.IGNORECASE)
_NEGATIVE_HP = re.compile(
    r"(?:(?<![\w-])-\s?\d+|\bminus \d+|\bnegative)\s+(?:hit points?|hp)\b"
    r"|\bbelow zero (?:hit points?|hp)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RuleCandidate:
    """One rule break: narrated (`rule_violation`) or in the state (`state_audit`)."""

    check: Literal["rule_violation", "state_audit"]
    kind: str
    mention: str
    start: int
    end: int
    confidence: Confidence
    sentence: str
    subject: tuple[str, ...]

    def to_dict(self) -> Doc:
        return {
            "kind": self.kind,
            "mention": self.mention,
            "span": [self.start, self.end],
            "confidence": self.confidence,
            "sentence": self.sentence,
            "subject": list(self.subject),
        }


# --- what the engine did -------------------------------------------------------


@dataclass(frozen=True)
class Act:
    """One action-using call in a turn, with the state of play when it ran."""

    actor: str
    tool: str
    spell: str | None
    active: str | None
    encounter: bool


def acts(before: Mapping[str, Any], call: Doc | None, steps: Sequence[Doc]) -> Iterator[Act]:
    """The turn's action-using calls in order: `npc_action` steps and the executed
    call, each with the active combatant and encounter flag at that moment."""
    active, encounter = before.get("active_combatant_id"), bool(before.get("encounter_active"))

    def act(c: Doc) -> Act | None:
        if c.get("tool") not in ACTION_TOOLS:
            return None
        args = c.get("arguments", {})
        actor = args.get(ACTOR_ARGUMENT[c["tool"]])
        return Act(actor, c["tool"], args.get("spell_id"), active, encounter)

    def advance(step: Doc) -> None:
        nonlocal active, encounter
        for change in step.get("state_diff", []):
            if change["path"] == "active_combatant_id":
                active = change["to"]
            elif change["path"] == "encounter_active":
                encounter = bool(change["to"])

    for when in ("before_call", "after_call"):
        if when == "after_call" and call is not None and (a := act(call)) is not None:
            yield a
        for step in steps:
            if step.get("when") != when:
                continue
            if step.get("step") == "npc_action" and (a := act(step["call"])) is not None:
                yield a
            advance(step)


def _combat_action(a: Act) -> bool:
    return not (a.tool == "cast_spell" and a.spell == CURE_WOUNDS)


def state_violations(
    state: Mapping[str, Any], before: Mapping[str, Any], call: Doc | None, steps: Sequence[Doc]
) -> list[RuleCandidate]:
    """Every rule the turn's state or engine actions break. Zero by construction."""
    found: list[RuleCandidate] = []

    def add(kind: str, mention: str, subject: str) -> None:
        found.append(RuleCandidate("state_audit", kind, mention, 0, 0, "high", "", (subject,)))

    for cid in sorted(state.get("combatants", {})):
        c = state["combatants"][cid]
        if c["current_hp"] < 0:
            add("negative_hp", f"combatants.{cid}.current_hp = {c['current_hp']}", cid)
        elif c["current_hp"] > c["max_hp"]:
            add("hp_above_max", f"combatants.{cid}.current_hp = {c['current_hp']}", cid)
        slots = c.get("spell_slots_1")
        if slots is not None and slots < 0:
            add("slot_below_zero", f"combatants.{cid}.spell_slots_1 = {slots}", cid)
    for owner in sorted(state.get("inventory", {})):
        for item, quantity in sorted(state["inventory"][owner].items()):
            if quantity < 0:
                add("negative_quantity", f"inventory.{owner}.{item} = {quantity}", owner)
    for a in acts(before, call, steps):
        if not a.encounter and _combat_action(a):
            add("after_encounter_end", f"{a.tool} by {a.actor} with no active encounter", a.actor)
        elif a.encounter and a.actor != a.active:
            add("out_of_turn", f"{a.tool} by {a.actor} while {a.active} is active", a.actor)
    return found


# --- what the narration says -----------------------------------------------------


def _attacks(
    sentence: str, tokens: list[Token], cast: Combatants
) -> Iterable[tuple[int, frozenset[str]]]:
    """Each attack verb with a named subject: its token index and the subject."""
    for i, t in enumerate(tokens):
        if t.word not in ATTACKS_YOU or negated(tokens, i):
            continue
        subject = subject_before(sentence, tokens, i, cast)
        if not subject:
            continue
        you = tokens[i - 1].word in SECOND_PERSON
        if t.word in (ATTACKS_YOU if you else ATTACKS_THIRD):
            yield i, subject


def narrated_violations(
    narration: str,
    state: Mapping[str, Any],
    before: Mapping[str, Any],
    call: Doc | None,
    steps: Sequence[Doc],
) -> list[RuleCandidate]:
    """Every rule break the narration describes, given what the turn did."""
    cast = Combatants.of(state)
    pcs = frozenset(
        cid for cid, c in state.get("combatants", {}).items() if c.get("is_player_character")
    )
    ended = (
        before.get("encounter_outcome") is not None
        and not before.get("encounter_active")
        and not state.get("encounter_active")
    )
    running = bool(before.get("encounter_active") or state.get("encounter_active"))
    attackers = {a.actor for a in acts(before, call, steps) if a.tool in ATTACK_TOOLS}
    no_slots = any(
        before["combatants"][cid].get("spell_slots_1") == 0
        for cid in pcs
        if cid in before.get("combatants", {})
    )

    found: list[RuleCandidate] = []
    for base, sentence in sentences(narration):
        tokens = tokenize(sentence)
        hits: list[tuple[Rule, int, int, bool, Iterable[str]]] = []
        for i, subject in _attacks(sentence, tokens, cast):
            j = next(k for k in range(i - 1, -1, -1) if cast.named(tokens[k].word))
            span = (tokens[j].start, tokens[i].end)
            npc_only = not subject & pcs
            if ended:
                hits.append(("after_encounter_end", *span, npc_only, subject))
            elif running and not subject & attackers:
                hits.append(("out_of_turn", *span, npc_only, subject))
        if no_slots:
            for pattern, sure in ((_CURE_NAMED, True), (_CURE_DESCRIBED, False)):
                for m in pattern.finditer(sentence):
                    if not negated(tokens, sum(1 for t in tokens if t.end <= m.start())):
                        hits.append(("slot_below_zero", m.start(), m.end(), sure, pcs))
        for m in _NEGATIVE_HP.finditer(sentence):
            named = frozenset().union(*(cast.named(t.word) for t in tokens))
            hits.append(("negative_hp", m.start(), m.end(), True, named))
        hedged = bool(HEDGE.search(sentence))
        found += [
            RuleCandidate(
                "rule_violation",
                kind,
                sentence[start:end],
                base + start,
                base + end,
                "high" if sure and not hedged else "low",
                sentence,
                tuple(sorted(subject)),
            )
            for kind, start, end, sure, subject in hits
        ]

    kept: dict[tuple[str, tuple[str, ...]], RuleCandidate] = {}
    for c in sorted(found, key=lambda c: (c.confidence != "high", c.start)):
        kept.setdefault((c.kind, c.subject), c)
    return sorted(kept.values(), key=lambda c: c.start)
