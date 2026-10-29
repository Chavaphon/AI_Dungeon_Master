"""Tool dispatch: the one write path (WBS 5.3, docs/conventions.md section 1).

`dispatch(state, roller, call)` is how a proposed tool call reaches the state.
It validates the call (WBS 5.1, 5.2), runs the engine function for its tool
from the dispatch table and returns the validation entry of the turn record
(docs/audit_log.md section 1):

- a rejection: the `result_rejected` envelope, with the state unchanged;
- `{"tool": null}`: `{"ok": true, "tool": null}`, with the state unchanged;
- otherwise the full `result_ok`: `narration_facts`, `state_diff` and `rolls`.

The engine's own writes around the call go through the same check:

- `open_encounter`: `encounter_start`, then the turns of the NPCs who won
  initiative, as `before_call` steps (WBS 4.19).
- `after_call`: after an action-using call (`attack`, `cast_spell`, `dodge`)
  during an encounter, the encounter end or the NPC turns until the turn comes
  back to the player character (`after_player_action`). Other calls, and a Cure
  Wounds outside an encounter, have no steps.
- `increment_turn`: the `turn_increment` step.

Every write, the call's and each of these, is checked twice before it returns:
its diff must account for every change (`check_write`, invariant 2, WBS 5.3),
and the state after it must be legal (`check_state`, the post-write invariant
assertion, WBS 5.4): the state schema and its cross-field rules, which include
`0 <= current_hp <= max_hp` (invariant 5). If either check fails, or the engine
function itself raises, the state is put back as it was before the write and
the exception propagates, so an illegal state raises rather than persists. It is
a bug, not a rejection: the roller has moved on, so the run cannot go on.

Which of these a turn runs, and when, is the turn loop's (WBS 6.4). It collects
the steps and the executed result into `engine_fields` (adm/engine/audit.py),
which checks the whole turn's diff once more.

A skill check's advantage comes from the scenario (`check_advantage`), not from
a call argument, so `dispatch` takes it as a keyword. It is ignored for the
other tools.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, TypeVar

from adm.engine.audit import Step, check_write, step_part
from adm.engine.checks import skill_check
from adm.engine.combat import EngineStep, StateChange, attack, dodge, start_encounter
from adm.engine.dice import AdvantageMode, DiceRoller
from adm.engine.inventory import modify_inventory
from adm.engine.npc import after_player_action, run_npc_turns
from adm.engine.quests import update_quest
from adm.engine.relationships import update_npc_relationship
from adm.engine.spells import FIRE_BOLT, cure_wounds, fire_bolt
from adm.engine.state import GameState, check_state
from adm.engine.validator import Rejection, validate

Doc = dict[str, Any]
Executor = Callable[[GameState, DiceRoller, Doc, AdvantageMode], Doc]
T = TypeVar("T")

# CLAUDE.md section 4.5: the tools that use the turn's action.
ACTION_TOOLS = ("attack", "cast_spell", "dodge")


def _attack(state: GameState, roller: DiceRoller, a: Doc, _: AdvantageMode) -> Doc:
    return attack(state, roller, a["attacker_id"], a["target_id"], a["weapon_id"]).to_dict()


def _cast_spell(state: GameState, roller: DiceRoller, a: Doc, _: AdvantageMode) -> Doc:
    spell = fire_bolt if a["spell_id"] == FIRE_BOLT else cure_wounds
    return spell(state, roller, a["caster_id"], a["target_id"]).to_dict()


def _dodge(state: GameState, roller: DiceRoller, a: Doc, _: AdvantageMode) -> Doc:
    return dodge(state, a["actor_id"]).to_dict()


def _skill_check(state: GameState, roller: DiceRoller, a: Doc, mode: AdvantageMode) -> Doc:
    result = skill_check(roller, state.combatants[a["actor_id"]], a["skill"], a["dc"], mode)
    return {
        "narration_facts": result.narration_facts(),
        "state_diff": [],
        "rolls": [result.roll.to_dict()],
    }


def _modify_inventory(state: GameState, roller: DiceRoller, a: Doc, _: AdvantageMode) -> Doc:
    return modify_inventory(state, a["actor_id"], a["item_id"], a["delta"]).to_dict()


def _update_npc_relationship(state: GameState, roller: DiceRoller, a: Doc, _: AdvantageMode) -> Doc:
    return update_npc_relationship(state, a["npc_id"], a["direction"], a["justification"]).to_dict()


def _update_quest(state: GameState, roller: DiceRoller, a: Doc, _: AdvantageMode) -> Doc:
    return update_quest(state, a["quest_id"], a["transition"]).to_dict()


DISPATCH: dict[str, Executor] = {
    "attack": _attack,
    "cast_spell": _cast_spell,
    "dodge": _dodge,
    "skill_check": _skill_check,
    "modify_inventory": _modify_inventory,
    "update_npc_relationship": _update_npc_relationship,
    "update_quest": _update_quest,
}


def _restore(state: GameState, data: Doc) -> None:
    """Put `state` back as `data`, its JSON form from before a write."""
    restored = GameState.model_validate(data)
    for name in GameState.model_fields:
        setattr(state, name, getattr(restored, name))


def _write(state: GameState, write: Callable[[], T], diff_of: Callable[[T], list[Doc]]) -> T:
    """Run one write and check it: its diff, then the state after it. On any
    failure the state is put back as it was and the exception propagates."""
    before = state.to_dict()
    try:
        result = write()
        check_write(before, diff_of(result), state)
        check_state(state)
    except Exception:
        _restore(state, before)
        raise
    return result


def _steps_diff(steps: Sequence[Step]) -> list[Doc]:
    return [x for s in steps for x in step_part(s.to_dict(), "state_diff")]


def dispatch(
    state: GameState,
    roller: DiceRoller,
    call: Any,
    *,
    check_advantage: AdvantageMode = "normal",
) -> Doc:
    """Validate and execute a proposed call, and return its validation entry."""
    checked = validate(state, call)
    if isinstance(checked, Rejection):
        return checked.to_dict()
    if checked.tool is None:
        return {"ok": True, "tool": None}
    execute = DISPATCH[checked.tool]
    outcome = _write(
        state,
        lambda: execute(state, roller, checked.arguments, check_advantage),
        lambda outcome: outcome["state_diff"],
    )
    return {"ok": True, "tool": checked.tool, **outcome}


def open_encounter(
    state: GameState, roller: DiceRoller, combatant_ids: Sequence[str]
) -> list[Step]:
    """Start an encounter and play the NPCs who come before the player character."""

    def write() -> list[Step]:
        steps: list[Step] = [start_encounter(state, roller, combatant_ids)]
        return steps + run_npc_turns(state, roller, "before_call")

    return _write(state, write, _steps_diff)


def after_call(state: GameState, roller: DiceRoller, tool: str) -> list[Step]:
    """The engine steps after an executed call of `tool`."""
    if tool not in ACTION_TOOLS or not state.encounter_active:
        return []
    return _write(state, lambda: list(after_player_action(state, roller)), _steps_diff)


def increment_turn(state: GameState) -> EngineStep:
    """The `turn_increment` step: the turn just played is counted."""

    def write() -> EngineStep:
        change = StateChange(path="turn_number", from_=state.turn_number, to=state.turn_number + 1)
        state.turn_number += 1
        return EngineStep(step="turn_increment", when="after_call", state_diff=[change], rolls=[])

    return _write(state, write, lambda step: _steps_diff([step]))
