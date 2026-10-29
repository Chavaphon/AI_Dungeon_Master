"""The tool-call validator (WBS 5.1 and 5.2, CLAUDE.md sections 6.2 and 6.3,
docs/tool_contract.md).

`validate(state, call)` checks a proposed call in the fixed order of
docs/tool_contract.md section 1 and returns the first failure, or the validated
call. Step 1 is the shape check (WBS 5.1); steps 2 to 6 are the state
preconditions (WBS 5.2). It is the only way a call reaches the engine, for the
player's call and for the NPC policy's (adm/engine/npc.py).

Step 1, the shape check, uses `args_<tool>` in schemas/tools.schema.json, the same
definitions the model is shown (decision 2026-10-02, point 4), so the two
cannot drift apart. A call passes it exactly when it validates against
`proposed_call`. It fails with `SCHEMA_VIOLATION` in these cases:

1. The call is not an object, or has a top-level key other than `tool` and
   `arguments`.
2. A null tool carries `arguments`. A bare `{"tool": null}` passes; it is the
   turn loop's narration-only case.
3. The tool is not one of the seven.
4. `arguments` is missing or not an object.
5. An argument is missing or has the wrong type, value or enum member. These
   are checked in signature order. The value case is a `delta` of 0.
6. An argument is unknown. These are checked last, sorted.

The message names the argument and the type it should have, so a weak model
can fix the call on its retry. `valid_options` follows docs/tool_contract.md
section 4: the seven tools for an unknown tool, the allowed values for a bad
enum, and the expected argument names for a missing, extra or wrongly typed
argument. Otherwise it is `{}`.

JSON Schema counts `12.0` as an integer, so the shape check accepts it. The
validated call holds `12`, so the engine only ever sees Python ints.

Steps 2 to 6, the preconditions, check a shaped call against the current state.
Within a step, arguments are checked in signature order.

2. Existence: `UNKNOWN_ENTITY` for a combatant, weapon or NPC id that is not in
   the state, `ITEM_NOT_DEFINED`, `UNKNOWN_QUEST`, `SPELL_NOT_SUPPORTED`.
3. Argument values: `SKILL_NOT_SUPPORTED`, `DC_OUT_OF_RANGE`,
   `MISSING_JUSTIFICATION`.
4. Encounter: `ENCOUNTER_OVER` for attack, dodge and Fire Bolt with no active
   encounter (Cure Wounds is exempt), then `NOT_YOUR_TURN` during one.
5. Actor: `ACTOR_UNCONSCIOUS`, `NOT_A_CASTER`, `NO_SPELL_SLOT`, `NOT_A_WEAPON`,
   `WEAPON_NOT_IN_INVENTORY`. `modify_inventory` names an owner, not an actor,
   so an unconscious owner passes.
6. Target and effect: `TARGET_UNCONSCIOUS`, `NEGATIVE_QUANTITY`,
   `RELATIONSHIP_STEP_TOO_LARGE`, `ILLEGAL_QUEST_TRANSITION`.

The message names the offending value and the state values behind the
rejection (CLAUDE.md section 7.1), and `valid_options` follows
docs/tool_contract.md section 4. A `NEGATIVE_QUANTITY` with none of the item
held has `{}`, since a delta of 0 is itself a `SCHEMA_VIOLATION`.

During an encounter `NOT_YOUR_TURN` comes before `ACTOR_UNCONSCIOUS`, and the
active combatant is always conscious, so an unconscious actor is only reached
outside an encounter: a skill check, or a Cure Wounds. The check stays for
every tool of the matrix as a guard.

The validator never changes the state. The engine functions keep their own
guards and raise if a call reaches them without passing here.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from functools import cache
from pathlib import Path
from typing import Any, Literal

from jsonschema import Draft202012Validator
from pydantic import BaseModel, ConfigDict

from adm.engine.checks import MAX_DC, MIN_DC, SUPPORTED_SKILLS
from adm.engine.inventory import held, most_negative_delta
from adm.engine.quests import legal_transitions
from adm.engine.relationships import MIN_JUSTIFICATION, other_direction, step
from adm.engine.spells import CURE_WOUNDS, FIRE_BOLT
from adm.engine.state import Combatant, GameState

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "tools.schema.json"

ToolName = Literal[
    "attack",
    "cast_spell",
    "dodge",
    "skill_check",
    "modify_inventory",
    "update_npc_relationship",
    "update_quest",
]
RejectionCode = Literal[
    "SCHEMA_VIOLATION",
    "UNKNOWN_ENTITY",
    "ITEM_NOT_DEFINED",
    "UNKNOWN_QUEST",
    "SPELL_NOT_SUPPORTED",
    "SKILL_NOT_SUPPORTED",
    "DC_OUT_OF_RANGE",
    "MISSING_JUSTIFICATION",
    "ENCOUNTER_OVER",
    "NOT_YOUR_TURN",
    "ACTOR_UNCONSCIOUS",
    "NOT_A_CASTER",
    "NO_SPELL_SLOT",
    "NOT_A_WEAPON",
    "WEAPON_NOT_IN_INVENTORY",
    "TARGET_UNCONSCIOUS",
    "NEGATIVE_QUANTITY",
    "RELATIONSHIP_STEP_TOO_LARGE",
    "ILLEGAL_QUEST_TRANSITION",
]

_JSON_TYPES = {"string": "a string", "integer": "an integer"}


class ToolCall(BaseModel):
    """A call that passed the shape check. `tool` is None for `{"tool": null}`."""

    model_config = ConfigDict(frozen=True)

    tool: ToolName | None
    arguments: dict[str, Any]


class Rejection(BaseModel):
    """`result_rejected` in tools.schema.json."""

    model_config = ConfigDict(frozen=True)

    tool: str | None
    rejection_code: RejectionCode
    message: str
    valid_options: dict[str, list[Any]]

    def to_dict(self) -> dict[str, Any]:
        return {"ok": False, **self.model_dump(mode="json"), "retry_allowed": True}


@cache
def _schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def tool_names() -> list[str]:
    """The seven tools, in schema order."""
    return list(_schema()["$defs"]["tool_name"]["enum"])


def tool_arguments(tool: str) -> dict[str, Any]:
    """`args_<tool>`: the argument schema of one tool."""
    return _schema()["$defs"][f"args_{tool}"]


@cache
def _proposed_call_validator() -> Draft202012Validator:
    schema = _schema()
    return Draft202012Validator({**schema, "$ref": "#/$defs/proposed_call"})


def _json_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "a boolean"
    if isinstance(value, int | float):
        return "a number"
    if isinstance(value, str):
        return "a string"
    if isinstance(value, list):
        return "an array"
    return "an object"


def _expected(prop: dict[str, Any]) -> str:
    if "enum" in prop:
        return "one of " + ", ".join(json.dumps(v) for v in prop["enum"])
    return _JSON_TYPES[prop["type"]]


def _violation(tool: Any, message: str, valid_options: dict[str, list[Any]]) -> Rejection:
    return Rejection(
        tool=tool if isinstance(tool, str) or tool is None else json.dumps(tool),
        rejection_code="SCHEMA_VIOLATION",
        message=message,
        valid_options=valid_options,
    )


def _check_argument(tool: str, name: str, prop: dict[str, Any], value: Any) -> Rejection | None:
    errors = list(Draft202012Validator(prop).iter_errors(value))
    if not errors:
        return None
    error = errors[0]
    if error.validator == "enum":
        return _violation(
            tool,
            f"{name} must be {_expected(prop)}, got {json.dumps(value)}.",
            {name: list(prop["enum"])},
        )
    if error.validator == "type":
        return _violation(
            tool,
            f"{name} must be {_expected(prop)}, got {_json_type(value)} {json.dumps(value)}.",
            {"arguments": list(tool_arguments(tool)["properties"])},
        )
    # The only other rule in an argument schema is `delta`'s `not: {const: 0}`.
    return _violation(tool, f"{name} must be a non-zero integer, got {json.dumps(value)}.", {})


def _normalised(arguments: Mapping[str, Any]) -> dict[str, Any]:
    return {
        name: int(value) if isinstance(value, float) and value.is_integer() else value
        for name, value in arguments.items()
    }


def check_shape(call: Any) -> ToolCall | Rejection:
    """Step 1 of the validation order: the call's shape, against tools.schema.json."""
    if not isinstance(call, Mapping):
        return _violation(
            None,
            f'A call must be an object {{"tool": ..., "arguments": {{...}}}}, '
            f"got {_json_type(call)}.",
            {},
        )
    tool = call.get("tool")
    extra = sorted(set(call) - {"tool", "arguments"})
    if "tool" not in call or extra:
        found = f"unknown key {extra[0]}" if extra else "no tool key"
        return _violation(
            tool, f'A call has only the keys "tool" and "arguments"; found {found}.', {}
        )

    if tool is None:
        if "arguments" in call:
            return _violation(None, 'A null tool takes no arguments: reply {"tool": null}.', {})
        return ToolCall(tool=None, arguments={})

    names = tool_names()
    if tool not in names:
        return _violation(
            tool,
            f"tool must be one of {', '.join(names)}, got {json.dumps(tool)}.",
            {"tool": names},
        )

    schema = tool_arguments(tool)
    expected_names = list(schema["properties"])
    arguments = call.get("arguments")
    if not isinstance(arguments, Mapping):
        got = "no arguments" if "arguments" not in call else _json_type(arguments)
        return _violation(
            tool,
            f"arguments must be an object with {', '.join(expected_names)}, got {got}.",
            {"arguments": expected_names},
        )

    for name, prop in schema["properties"].items():
        if name not in arguments:
            return _violation(
                tool,
                f"Missing argument {name}, which must be {_expected(prop)}. "
                f"{tool} takes {', '.join(expected_names)}.",
                {"arguments": expected_names},
            )
        rejection = _check_argument(tool, name, prop, arguments[name])
        if rejection is not None:
            return rejection
    unknown = sorted(set(arguments) - set(expected_names))
    if unknown:
        return _violation(
            tool,
            f"Unknown argument {unknown[0]}. {tool} takes {', '.join(expected_names)}.",
            {"arguments": expected_names},
        )

    # Every rule of the schema has been checked above; this keeps the two in step.
    assert _proposed_call_validator().is_valid(call), call
    return ToolCall(tool=tool, arguments=_normalised(arguments))


# --- steps 2 to 6: the state preconditions (WBS 5.2) -------------------------

SPELLS = [FIRE_BOLT, CURE_WOUNDS]
# The ENCOUNTER_OVER valid options: what is still legal with no encounter.
NO_ENCOUNTER_TOOLS = [
    "cast_spell",
    "skill_check",
    "modify_inventory",
    "update_npc_relationship",
    "update_quest",
]
COMBATANT_ARGS = ("attacker_id", "caster_id", "actor_id", "target_id")
# tool -> the argument naming whose turn the call is for (NOT_YOUR_TURN)
ACTOR_ARG = {
    "attack": "attacker_id",
    "cast_spell": "caster_id",
    "dodge": "actor_id",
    "skill_check": "actor_id",
    "modify_inventory": "actor_id",
}
# The tools whose actor must be conscious. modify_inventory names an owner.
ACTING_TOOLS = ("attack", "cast_spell", "dodge", "skill_check")


def _reject(
    call: ToolCall, code: RejectionCode, message: str, valid_options: dict[str, list[Any]]
) -> Rejection:
    return Rejection(
        tool=call.tool, rejection_code=code, message=message, valid_options=valid_options
    )


def _signature(call: ToolCall) -> list[tuple[str, Any]]:
    """The call's arguments in signature order."""
    assert call.tool is not None
    return [(name, call.arguments[name]) for name in tool_arguments(call.tool)["properties"]]


def _is_caster(combatant: Combatant) -> bool:
    return None not in (
        combatant.spell_attack_bonus,
        combatant.spellcasting_modifier,
        combatant.spell_slots_1,
    )


def _held_weapons(state: GameState, combatant_id: str) -> list[str]:
    return sorted(
        item_id
        for item_id, quantity in state.inventory.get(combatant_id, {}).items()
        if quantity > 0 and state.item_definitions[item_id].is_weapon
    )


def _conscious(state: GameState) -> list[str]:
    return sorted(cid for cid, c in state.combatants.items() if c.status == "active")


def _is_damaging(call: ToolCall) -> bool:
    """Attack and Fire Bolt: the calls that need an encounter and a conscious target."""
    return call.tool == "attack" or (
        call.tool == "cast_spell" and call.arguments["spell_id"] == FIRE_BOLT
    )


def _existence(state: GameState, call: ToolCall) -> Rejection | None:
    for name, value in _signature(call):
        if name in COMBATANT_ARGS and value not in state.combatants:
            return _reject(
                call,
                "UNKNOWN_ENTITY",
                f"{name} {value} is not a combatant in the current state.",
                {name: sorted(state.combatants)},
            )
        if name == "weapon_id" and value not in state.item_definitions:
            return _reject(
                call,
                "UNKNOWN_ENTITY",
                f"weapon_id {value} is not an item in the current state.",
                {name: _held_weapons(state, call.arguments["attacker_id"])},
            )
        if name == "npc_id" and value not in state.npc_relationships:
            return _reject(
                call,
                "UNKNOWN_ENTITY",
                f"npc_id {value} is not an NPC with a relationship in the current state.",
                {name: sorted(state.npc_relationships)},
            )
        if name == "item_id" and value not in state.item_definitions:
            return _reject(
                call,
                "ITEM_NOT_DEFINED",
                f"item_id {value} is not a defined item.",
                {name: sorted(state.item_definitions)},
            )
        if name == "quest_id" and value not in state.quests:
            return _reject(
                call,
                "UNKNOWN_QUEST",
                f"quest_id {value} is not a quest in the current state.",
                {name: sorted(state.quests)},
            )
        if name == "spell_id" and value not in SPELLS:
            return _reject(
                call,
                "SPELL_NOT_SUPPORTED",
                f"spell_id {value} is not supported; the only spells are {' and '.join(SPELLS)}.",
                {name: SPELLS},
            )
    return None


def _argument_values(state: GameState, call: ToolCall) -> Rejection | None:
    for name, value in _signature(call):
        if name == "skill" and value not in SUPPORTED_SKILLS:
            return _reject(
                call,
                "SKILL_NOT_SUPPORTED",
                f"skill {value} is not supported; use {', '.join(SUPPORTED_SKILLS)}.",
                {name: list(SUPPORTED_SKILLS)},
            )
        if name == "dc" and not MIN_DC <= value <= MAX_DC:
            return _reject(
                call,
                "DC_OUT_OF_RANGE",
                f"dc {value} is outside {MIN_DC}..{MAX_DC}.",
                {name: [MIN_DC, MAX_DC]},
            )
        if name == "justification" and len(value) < MIN_JUSTIFICATION:
            return _reject(
                call,
                "MISSING_JUSTIFICATION",
                f"justification must be at least {MIN_JUSTIFICATION} characters, got {len(value)}.",
                {},
            )
    return None


def _encounter(state: GameState, call: ToolCall) -> Rejection | None:
    assert call.tool is not None
    if (_is_damaging(call) or call.tool == "dodge") and not state.encounter_active:
        what = (
            f"{FIRE_BOLT} cannot be cast"
            if call.tool == "cast_spell"
            else f"{call.tool} cannot be used"
        )
        ended = (
            f" The last encounter ended in {state.encounter_outcome}."
            if state.encounter_outcome
            else ""
        )
        return _reject(
            call,
            "ENCOUNTER_OVER",
            f"No encounter is active, so {what}.{ended}",
            {"tool": NO_ENCOUNTER_TOOLS, "spell_id": [CURE_WOUNDS]},
        )
    actor_arg = ACTOR_ARG.get(call.tool)
    if actor_arg is None or not state.encounter_active:
        return None
    actor_id = call.arguments[actor_arg]
    if actor_id != state.active_combatant_id:
        return _reject(
            call,
            "NOT_YOUR_TURN",
            f"It is {state.active_combatant_id}'s turn, not {actor_id}'s.",
            {actor_arg: [state.active_combatant_id]},
        )
    return None


def _actor(state: GameState, call: ToolCall) -> Rejection | None:
    if call.tool not in ACTOR_ARG:
        return None
    actor_arg = ACTOR_ARG[call.tool]
    actor_id = call.arguments[actor_arg]
    actor = state.combatants[actor_id]
    if call.tool in ACTING_TOOLS and actor.status != "active":
        options = [state.active_combatant_id] if state.encounter_active else _conscious(state)
        return _reject(
            call,
            "ACTOR_UNCONSCIOUS",
            f"{actor_id} is unconscious and cannot act.",
            {actor_arg: options},
        )
    if call.tool == "cast_spell":
        if not _is_caster(actor):
            casters = [cid for cid in _conscious(state) if _is_caster(state.combatants[cid])]
            return _reject(
                call, "NOT_A_CASTER", f"{actor_id} cannot cast spells.", {actor_arg: casters}
            )
        if call.arguments["spell_id"] == CURE_WOUNDS and actor.spell_slots_1 == 0:
            return _reject(
                call,
                "NO_SPELL_SLOT",
                f"{actor_id} has 0 level-1 spell slots left, and {CURE_WOUNDS} needs one.",
                {"spell_id": [FIRE_BOLT]},
            )
    if call.tool == "attack":
        weapon_id = call.arguments["weapon_id"]
        if not state.item_definitions[weapon_id].is_weapon:
            return _reject(
                call,
                "NOT_A_WEAPON",
                f"{weapon_id} is not a weapon.",
                {"weapon_id": _held_weapons(state, actor_id)},
            )
        if held(state, actor_id, weapon_id) == 0:
            return _reject(
                call,
                "WEAPON_NOT_IN_INVENTORY",
                f"{actor_id} does not hold {weapon_id}.",
                {"weapon_id": _held_weapons(state, actor_id)},
            )
    return None


def _target_and_effect(state: GameState, call: ToolCall) -> Rejection | None:
    args = call.arguments
    if _is_damaging(call):
        target_id = args["target_id"]
        if state.combatants[target_id].status != "active":
            attacker_arg = "attacker_id" if call.tool == "attack" else "caster_id"
            faction = state.combatants[args[attacker_arg]].faction
            targets = [cid for cid in _conscious(state) if state.combatants[cid].faction != faction]
            return _reject(
                call,
                "TARGET_UNCONSCIOUS",
                f"{target_id} is unconscious and cannot be attacked.",
                {"target_id": targets},
            )
    if call.tool == "modify_inventory":
        actor_id, item_id, delta = args["actor_id"], args["item_id"], args["delta"]
        before = held(state, actor_id, item_id)
        if before + delta < 0:
            return _reject(
                call,
                "NEGATIVE_QUANTITY",
                f"{actor_id} holds {before} of {item_id}; delta {delta:+d} would leave "
                f"{before + delta}.",
                {"delta": [most_negative_delta(state, actor_id, item_id)]} if before else {},
            )
    if call.tool == "update_npc_relationship":
        npc_id, direction = args["npc_id"], args["direction"]
        stance = state.npc_relationships[npc_id].stance
        if step(stance, direction) is None:
            return _reject(
                call,
                "RELATIONSHIP_STEP_TOO_LARGE",
                f"{npc_id} is already {stance}, the end of the ladder; "
                f"its stance cannot move {direction}.",
                {"direction": [other_direction(direction)]},
            )
    if call.tool == "update_quest":
        quest_id, transition = args["quest_id"], args["transition"]
        quest = state.quests[quest_id]
        legal = legal_transitions(quest)
        if transition not in legal:
            return _reject(
                call,
                "ILLEGAL_QUEST_TRANSITION",
                f"{quest_id} is {quest.state} at stage {quest.stage} of {quest.max_stage}; "
                f"it cannot {transition}.",
                {"transition": list(legal)},
            )
    return None


_STEPS = (_existence, _argument_values, _encounter, _actor, _target_and_effect)


def check_preconditions(state: GameState, call: ToolCall) -> Rejection | None:
    """Steps 2 to 6 of the validation order: the first precondition `call` breaks
    in `state`, or None. `call` has passed the shape check."""
    if call.tool is None:
        return None
    for check in _STEPS:
        rejection = check(state, call)
        if rejection is not None:
            return rejection
    return None


def validate(state: GameState, call: Any) -> ToolCall | Rejection:
    """Validate a proposed call against the schema and then `state`. Returns the
    validated call, or the first rejection."""
    shaped = check_shape(call)
    if isinstance(shaped, Rejection):
        return shaped
    rejection = check_preconditions(state, shaped)
    return shaped if rejection is None else rejection
