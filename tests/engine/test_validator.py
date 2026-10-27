"""The shape check of the tool-call validator (WBS 5.1, docs/tool_contract.md section 1).

The reject and accept cases are those of tests/test_tool_contract.py, so the
validator is held to the same schema the contract tests hold the examples to. A
property test checks that the validator agrees with `proposed_call` on any call.

Run: pytest tests/engine/test_validator.py -v
"""

import copy
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from adm.engine.validator import Rejection, ToolCall, check_shape, tool_names

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "schemas" / "examples"
CALL_EXAMPLES = sorted(EXAMPLES.glob("toolcall_*.json"))

_SCHEMAS = [
    json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))
    for name in ("state.schema.json", "tools.schema.json")
]
_REGISTRY = Registry().with_resources((s["$id"], Resource.from_contents(s)) for s in _SCHEMAS)
_TOOLS_ID = _SCHEMAS[1]["$id"]
CALL_VALIDATOR = Draft202012Validator(
    {"$ref": _TOOLS_ID + "#/$defs/proposed_call"}, registry=_REGISTRY
)
RESULT_VALIDATOR = Draft202012Validator(
    {"$ref": _TOOLS_ID + "#/$defs/tool_result"}, registry=_REGISTRY
)

Doc = dict[str, Any]


def _call(example: str) -> Doc:
    return json.loads((EXAMPLES / f"toolcall_{example}.json").read_text(encoding="utf-8"))


def _rejected(call: Any) -> Rejection:
    result = check_shape(call)
    assert isinstance(result, Rejection), f"accepted {call}"
    assert result.rejection_code == "SCHEMA_VIOLATION"
    RESULT_VALIDATOR.validate(result.to_dict())
    return result


def _with(example: str, **arguments: Any) -> Doc:
    call = _call(example)
    call["arguments"].update(arguments)
    return call


def _without(example: str, name: str) -> Doc:
    call = _call(example)
    del call["arguments"][name]
    return call


# --- the contract cases ------------------------------------------------------


@pytest.mark.parametrize("path", CALL_EXAMPLES, ids=[p.stem for p in CALL_EXAMPLES])
def test_every_example_call_passes(path: Path) -> None:
    call = json.loads(path.read_text(encoding="utf-8"))
    result = check_shape(call)
    assert isinstance(result, ToolCall)
    assert result.tool == call["tool"]
    assert result.arguments == call.get("arguments", {})


def _set(path: str, value: Any) -> Callable[[Doc], None]:
    *parents, leaf = path.split(".")

    def mutate(doc: Doc) -> None:
        node = doc
        for key in parents:
            node = node[key]
        node[leaf] = value

    return mutate


def _delete(path: str) -> Callable[[Doc], None]:
    *parents, leaf = path.split(".")

    def mutate(doc: Doc) -> None:
        node = doc
        for key in parents:
            node = node[key]
        del node[leaf]

    return mutate


# The CALL_REJECTS and CALL_ACCEPTS of tests/test_tool_contract.py.
CALL_REJECTS = {
    "unknown_tool": ("attack", _set("tool", "dash")),
    "extra_argument": ("attack", _set("arguments.advantage", True)),
    "missing_argument": ("attack", _delete("arguments.weapon_id")),
    "id_wrong_type": ("attack", _set("arguments.target_id", 1)),
    "dc_wrong_type": ("skill_check", _set("arguments.dc", "12")),
    "dc_float": ("skill_check", _set("arguments.dc", 12.5)),
    "zero_delta": ("modify_inventory", _set("arguments.delta", 0)),
    "bad_direction": ("update_npc_relationship", _set("arguments.direction", "sideways")),
    "bad_transition": ("update_quest", _set("arguments.transition", "restart")),
    "null_tool_with_arguments": ("null", _set("arguments", {})),
    "tool_without_arguments": ("dodge", _delete("arguments")),
    "unknown_top_level_key": ("dodge", _set("reason", "the rat is fast")),
}

CALL_ACCEPTS = {
    "unprefixed_id": ("attack", _set("arguments.target_id", "rat")),
    "unknown_spell": ("cast_spell", _set("arguments.spell_id", "spell_fireball")),
    "unknown_skill": ("skill_check", _set("arguments.skill", "athletics")),
    "dc_out_of_range": ("skill_check", _set("arguments.dc", 40)),
    "short_justification": ("update_npc_relationship", _set("arguments.justification", "ok")),
}


@pytest.mark.parametrize("example,mutate", CALL_REJECTS.values(), ids=CALL_REJECTS.keys())
def test_contract_rejects_are_schema_violations(
    example: str, mutate: Callable[[Doc], None]
) -> None:
    call = _call(example)
    mutate(call)
    _rejected(call)


@pytest.mark.parametrize("example,mutate", CALL_ACCEPTS.values(), ids=CALL_ACCEPTS.keys())
def test_value_checks_are_left_to_their_own_codes(
    example: str, mutate: Callable[[Doc], None]
) -> None:
    call = _call(example)
    mutate(call)
    assert isinstance(check_shape(call), ToolCall)


# --- messages and valid_options ----------------------------------------------

ATTACK_ARGS = ["attacker_id", "target_id", "weapon_id"]
CHECK_ARGS = ["actor_id", "skill", "dc"]


def test_wrong_type_names_the_field_and_the_expected_type() -> None:
    rejection = _rejected(_with("skill_check", dc="12"))
    assert rejection.tool == "skill_check"
    assert rejection.message == 'dc must be an integer, got a string "12".'
    assert rejection.valid_options == {"arguments": CHECK_ARGS}


def test_an_id_given_as_a_number_must_be_a_string() -> None:
    rejection = _rejected(_with("attack", target_id=1))
    assert rejection.message == "target_id must be a string, got a number 1."
    assert rejection.valid_options == {"arguments": ATTACK_ARGS}


def test_a_boolean_is_not_an_integer() -> None:
    rejection = _rejected(_with("skill_check", dc=True))
    assert rejection.message == "dc must be an integer, got a boolean true."


def test_a_fractional_dc_is_not_an_integer() -> None:
    assert _rejected(_with("skill_check", dc=12.5)).message == (
        "dc must be an integer, got a number 12.5."
    )


def test_a_missing_argument_is_named_with_its_type() -> None:
    rejection = _rejected(_without("attack", "weapon_id"))
    assert rejection.message == (
        "Missing argument weapon_id, which must be a string. "
        "attack takes attacker_id, target_id, weapon_id."
    )
    assert rejection.valid_options == {"arguments": ATTACK_ARGS}


def test_an_unknown_argument_is_named() -> None:
    rejection = _rejected(_with("attack", advantage=True))
    assert rejection.message == (
        "Unknown argument advantage. attack takes attacker_id, target_id, weapon_id."
    )
    assert rejection.valid_options == {"arguments": ATTACK_ARGS}


def test_a_bad_enum_lists_the_allowed_values() -> None:
    rejection = _rejected(_with("update_npc_relationship", direction="sideways"))
    assert rejection.message == 'direction must be one of "up", "down", got "sideways".'
    assert rejection.valid_options == {"direction": ["up", "down"]}
    rejection = _rejected(_with("update_quest", transition="restart"))
    assert rejection.valid_options == {"transition": ["start", "advance", "complete", "fail"]}


def test_a_zero_delta_is_rejected() -> None:
    rejection = _rejected(_with("modify_inventory", delta=0))
    assert rejection.message == "delta must be a non-zero integer, got 0."
    assert rejection.valid_options == {}


@pytest.mark.parametrize("tool", ["dash", "null", "Attack", 5])
def test_an_unknown_tool_lists_the_seven(tool: Any) -> None:
    call = _call("dodge")
    call["tool"] = tool
    rejection = _rejected(call)
    assert rejection.valid_options == {"tool": tool_names()}
    assert len(tool_names()) == 7
    assert rejection.tool == (tool if isinstance(tool, str) else "5")


@pytest.mark.parametrize("arguments", [None, [], "actor_id=pc_lyra"])
def test_arguments_must_be_an_object(arguments: Any) -> None:
    call = _call("dodge")
    call["arguments"] = arguments
    rejection = _rejected(call)
    assert rejection.message.startswith("arguments must be an object with actor_id, got ")
    assert rejection.valid_options == {"arguments": ["actor_id"]}


def test_missing_arguments_are_named() -> None:
    call = _call("dodge")
    del call["arguments"]
    assert _rejected(call).message == "arguments must be an object with actor_id, got no arguments."


def test_a_null_tool_takes_no_arguments() -> None:
    rejection = _rejected({"tool": None, "arguments": {}})
    assert rejection.tool is None
    assert rejection.valid_options == {}


@pytest.mark.parametrize("call", [[], "attack", None, 3])
def test_a_call_must_be_an_object(call: Any) -> None:
    assert _rejected(call).tool is None


def test_an_unknown_top_level_key_is_named() -> None:
    call = _call("dodge")
    call["reason"] = "the rat is fast"
    assert "unknown key reason" in _rejected(call).message


# --- order and the validated call --------------------------------------------


def test_arguments_are_checked_in_signature_order() -> None:
    call = _with("attack", attacker_id=7)
    del call["arguments"]["weapon_id"]
    assert _rejected(call).message.startswith("attacker_id must be a string")


def test_a_renamed_argument_reports_the_missing_one_first() -> None:
    call = _without("attack", "target_id")
    call["arguments"]["target"] = "npc_rat_01"
    assert _rejected(call).message.startswith("Missing argument target_id")


def test_the_null_tool_passes() -> None:
    assert check_shape({"tool": None}) == ToolCall(tool=None, arguments={})


def test_an_integral_float_becomes_an_int() -> None:
    result = check_shape(_with("skill_check", dc=12.0))
    assert isinstance(result, ToolCall)
    assert result.arguments["dc"] == 12
    assert type(result.arguments["dc"]) is int


def test_the_call_is_not_changed() -> None:
    call = _with("modify_inventory", delta=-1.0)
    before = copy.deepcopy(call)
    check_shape(call)
    assert call == before


# --- agreement with the schema -----------------------------------------------

_values = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(-3, 30),
    st.floats(-3, 30, allow_nan=False),
    st.sampled_from(["", "pc_lyra", "up", "down", "start", "advance", "x" * 12]),
    st.lists(st.integers(), max_size=1),
)
_keys = st.sampled_from(
    ["attacker_id", "target_id", "weapon_id", "caster_id", "spell_id", "actor_id", "skill"]
    + ["dc", "item_id", "delta", "npc_id", "direction", "justification", "quest_id"]
    + ["transition", "extra"]
)
_calls = st.fixed_dictionaries(
    {"tool": st.one_of(st.none(), st.sampled_from([*tool_names(), "dash"]))},
    optional={
        "arguments": st.one_of(st.dictionaries(_keys, _values, max_size=4), _values),
        "reason": st.just("why"),
    },
)


def _complete(tool: str) -> st.SearchStrategy[Doc]:
    """Calls with every argument of `tool` present, so many of them pass."""
    names = list(_call(tool)["arguments"])
    return st.fixed_dictionaries(
        {"tool": st.just(tool), "arguments": st.fixed_dictionaries({n: _values for n in names})}
    )


_complete_calls = st.sampled_from(tool_names()).flatmap(_complete)


@settings(max_examples=400, deadline=None)
@given(call=st.one_of(_calls, _complete_calls))
def test_the_shape_check_agrees_with_proposed_call(call: Doc) -> None:
    result = check_shape(call)
    assert isinstance(result, ToolCall) == CALL_VALIDATOR.is_valid(call)
    if isinstance(result, Rejection):
        assert result.rejection_code == "SCHEMA_VIOLATION"
        RESULT_VALIDATOR.validate(result.to_dict())
