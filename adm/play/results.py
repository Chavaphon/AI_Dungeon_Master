"""Result lines: one line per mechanical outcome of a turn (CLAUDE.md section
15, item 42; WBS 13.2).

`play` shows them before each narration. They are read from the turn's audit
record only (`engine_steps`, `validation`, `executed_call`), so they are
display only: nothing is added to the record or to any prompt.

Veteran mode shows the rolls, AC and DC:

    Lyra -> giant rat (short sword): 17 vs AC 12, hit, 7 damage; giant rat 4/11 HP

Beginner mode, the default, says the same outcome in plain words, with no
numbers from the dice and the beginner vocabulary (`adm/play/vocabulary.py`):

    You hit giant rat 2 with your short sword. Giant rat 2 is wounded.

Beginner lines call the player character "you" and number combatants who share
a name, as `/status` does, so they also read the state they are given, a copy.
"""

from __future__ import annotations

from typing import Any

from adm.engine.state import GameState
from adm.play.commands import combatant_labels
from adm.play.vocabulary import BAND_WORDS, QUEST_WORDS, Mode

# (tool, the call's arguments, narration_facts)
Outcome = tuple[str, dict[str, Any], dict[str, Any]]


def result_lines(record: dict[str, Any], state: GameState, mode: Mode) -> list[str]:
    """One line per mechanical outcome of a turn, in the order it happened: the
    NPC actions before the call, the player's executed call, then the NPC
    actions after it. A failed or narration-only turn shows just the NPC
    actions that ran."""
    outcomes = _outcomes(record)
    if mode is Mode.VETERAN:
        return [_result_line(tool, facts) for tool, _, facts in outcomes]
    names = _Names(state)
    return [_plain_line(tool, args, facts, names) for tool, args, facts in outcomes]


def _outcomes(record: dict[str, Any]) -> list[Outcome]:
    steps = record["engine_steps"]

    def npc(when: str) -> list[Outcome]:
        return [
            (s["result"]["tool"], s["call"]["arguments"], s["result"]["narration_facts"])
            for s in steps
            if s["step"] == "npc_action" and s["when"] == when
        ]

    player: list[Outcome] = []
    call = record["executed_call"]
    last = record["validation"][-1] if record["validation"] else None
    if call is not None and last is not None and last.get("ok"):
        player = [(last["tool"], call.get("arguments", {}), last["narration_facts"])]
    return [*npc("before_call"), *player, *npc("after_call")]


# --- veteran -------------------------------------------------------------------


def _result_line(tool: str, f: dict[str, Any]) -> str:
    if tool == "attack" or (tool == "cast_spell" and f["spell"] == "fire bolt"):
        who = f["attacker"] if tool == "attack" else f["caster"]
        how = f["weapon"] if tool == "attack" else "Fire Bolt"
        mode = "" if f["advantage_mode"] == "normal" else f", {f['advantage_mode']}"
        outcome = "critical hit" if f["critical"] else ("hit" if f["hit"] else "miss")
        damage = f", {f['damage']} damage" if f["hit"] else ""
        return (
            f"{who} -> {f['target']} ({how}): {f['attack_roll']} vs AC {f['target_ac']}{mode}, "
            f"{outcome}{damage}; {f['target']} {f['target_hp_after']}/{f['target_hp_max']} HP"
        )
    if tool == "cast_spell":
        revived = ", revived" if f["revived"] else ""
        return (
            f"{f['caster']} -> {f['target']} (Cure Wounds): +{f['healed_applied']} HP{revived}; "
            f"{f['target']} {f['target_hp_after']}/{f['target_hp_max']} HP; "
            f"{f['slots_remaining']} slot(s) left"
        )
    if tool == "dodge":
        return f"{f['actor']} dodges"
    if tool == "skill_check":
        mode = "" if f["advantage_mode"] == "normal" else f", {f['advantage_mode']}"
        outcome = "success" if f["success"] else "failure"
        roll = f"{f['check_total']} vs DC {f['dc']}{mode}"
        return f"{f['actor']} {f['skill']} check: {roll}, {outcome}"
    if tool == "modify_inventory":
        return f"{f['actor']} {f['delta']:+d} {f['item']} (now {f['quantity_after']})"
    if tool == "update_npc_relationship":
        return f"{f['npc']}: {f['stance_before']} -> {f['stance_after']}"
    if tool == "update_quest":
        return (
            f"Quest {f['quest']}: {f['state_before']} -> {f['state_after']} "
            f"(stage {f['stage_after']}/{f['max_stage']})"
        )
    raise ValueError(f"no result line for tool {tool!r}")


# --- beginner ------------------------------------------------------------------


class _Names:
    """How a beginner line names a combatant: "you" for the player character,
    otherwise its display name, numbered where several share it."""

    def __init__(self, state: GameState) -> None:
        self.labels = combatant_labels(state)
        self.pc = next(c for c in state.combatants.values() if c.is_player_character).combatant_id

    def is_you(self, cid: str) -> bool:
        return cid == self.pc

    def of(self, cid: str, fallback: str) -> str:
        return "you" if self.is_you(cid) else self.labels.get(cid, fallback)

    def target(self, actor: str, target: str, fallback: str) -> str:
        if actor == target:
            return "yourself" if self.is_you(actor) else "itself"
        return self.of(target, fallback)

    def verb(self, cid: str, you: str, other: str) -> str:
        return you if self.is_you(cid) else other

    def possessive(self, cid: str, fallback: str) -> str:
        return "your" if self.is_you(cid) else f"{self.of(cid, fallback)}'s"


def _cap(text: str) -> str:
    return text[:1].upper() + text[1:]


def _odds(names: _Names, cid: str, name: str, advantage_mode: str) -> str:
    if advantage_mode == "advantage":
        return f"{_cap(name)} {names.verb(cid, 'have', 'has')} the upper hand. "
    if advantage_mode == "disadvantage":
        return f"The odds are against {name}. "
    return ""


def _health(names: _Names, cid: str, name: str, band: str) -> str:
    return f"{_cap(name)} {names.verb(cid, 'are', 'is')} {BAND_WORDS[band]}."


def _charges(n: int) -> str:
    if n == 0:
        return "No spell charges left."
    return f"{n} spell charge{'' if n == 1 else 's'} left."


def _plain_line(tool: str, args: dict[str, Any], f: dict[str, Any], names: _Names) -> str:
    if tool == "attack" or (tool == "cast_spell" and f["spell"] == "fire bolt"):
        actor = args["attacker_id"] if tool == "attack" else args["caster_id"]
        who = names.of(actor, f["attacker"] if tool == "attack" else f["caster"])
        target_id = args["target_id"]
        whom = names.target(actor, target_id, f["target"])
        if tool == "attack":
            how = f"with {names.verb(actor, 'your', 'its')} {f['weapon']}"
        else:
            how = "with Fire Bolt"
        odds = _odds(names, actor, who, f["advantage_mode"])
        if not f["hit"]:
            return f"{odds}{_cap(who)} {names.verb(actor, 'miss', 'misses')} {whom}."
        critical = " A critical hit!" if f["critical"] else ""
        hit = f"{_cap(who)} {names.verb(actor, 'hit', 'hits')} {whom} {how}.{critical}"
        hurt = _health(names, target_id, names.of(target_id, f["target"]), f["target_hp_band"])
        return f"{odds}{hit} {hurt}"
    if tool == "cast_spell":
        actor, target_id = args["caster_id"], args["target_id"]
        who = names.of(actor, f["caster"])
        whom = names.target(actor, target_id, f["target"])
        healed = names.of(target_id, f["target"])
        line = f"{_cap(who)} {names.verb(actor, 'cast', 'casts')} Cure Wounds on {whom}."
        if f["revived"]:
            line += f" {_cap(healed)} {names.verb(target_id, 'wake', 'wakes')} up."
        line += " " + _health(names, target_id, healed, f["target_hp_band"])
        if names.is_you(actor):
            line += " " + _charges(f["slots_remaining"])
        return line
    if tool == "dodge":
        actor = args["actor_id"]
        if names.is_you(actor):
            return "You dodge: attacks against you are harder until your next turn."
        return f"{_cap(names.of(actor, f['actor']))} dodges."
    if tool == "skill_check":
        actor = args["actor_id"]
        who = names.of(actor, f["actor"])
        odds = _odds(names, actor, who, f["advantage_mode"])
        outcome = "success" if f["success"] else "failure"
        return f"{odds}{_cap(names.possessive(actor, f['actor']))} {f['skill']} check: {outcome}."
    if tool == "modify_inventory":
        actor = args["actor_id"]
        who = _cap(names.of(actor, f["actor"]))
        n, after = abs(f["delta"]), f["quantity_after"]
        # "1 torch", or "torch x2" as /inventory counts: no plural is invented.
        what = f"1 {f['item']}" if n == 1 else f"{f['item']} x{n}"
        if f["delta"] > 0:
            return f"{who} {names.verb(actor, 'gain', 'gains')} {what} ({after} now)."
        return f"{who} {names.verb(actor, 'lose', 'loses')} {what} ({after} left)."
    if tool == "update_npc_relationship":
        return (
            f"{_cap(f['npc'])} now feels {f['stance_after']} towards you "
            f"(was {f['stance_before']})."
        )
    if tool == "update_quest":
        stage = (
            f", stage {f['stage_after']} of {f['max_stage']}"
            if f["state_after"] == "active"
            else ""
        )
        return f"Quest {f['quest']}: {QUEST_WORDS[f['state_after']]}{stage}."
    raise ValueError(f"no result line for tool {tool!r}")
