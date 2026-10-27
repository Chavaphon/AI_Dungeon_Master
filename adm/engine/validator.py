"""The tool-call validator (WBS 5.1, CLAUDE.md section 6.2, docs/tool_contract.md).

The validator checks a proposed call in the fixed order of docs/tool_contract.md
section 1 and returns the first failure. WBS 5.1 builds step 1, the shape check.
WBS 5.2 adds the state preconditions after it.

The shape check uses `args_<tool>` in schemas/tools.schema.json, the same
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
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from functools import cache
from pathlib import Path
from typing import Any, Literal

from jsonschema import Draft202012Validator
from pydantic import BaseModel, ConfigDict

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
