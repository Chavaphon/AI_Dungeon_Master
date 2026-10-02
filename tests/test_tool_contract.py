"""Tool contract v0.9 (WBS 2.3): the schema accepts the example calls and results,
rejects ones that break CLAUDE.md section 6, and stays in sync with the tables in
CLAUDE.md sections 6.1 and 6.3 and the matrix in docs/tool_contract.md.

`facts_errors` covers the arithmetic JSON Schema cannot express (see
docs/tool_contract.md). The runtime checks belong to the validator, WBS 5.1-5.2.

Run: pytest tests/test_tool_contract.py -v
"""

import copy
import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
STATE_SCHEMA = json.loads((ROOT / "schemas" / "state.schema.json").read_text(encoding="utf-8"))
SCHEMA = json.loads((ROOT / "schemas" / "tools.schema.json").read_text(encoding="utf-8"))
REGISTRY = Registry().with_resources(
    (s["$id"], Resource.from_contents(s)) for s in (STATE_SCHEMA, SCHEMA)
)
CALL_VALIDATOR = Draft202012Validator(
    {"$ref": SCHEMA["$id"] + "#/$defs/proposed_call"}, registry=REGISTRY
)
RESULT_VALIDATOR = Draft202012Validator(
    {"$ref": SCHEMA["$id"] + "#/$defs/tool_result"}, registry=REGISTRY
)

EXAMPLES = ROOT / "schemas" / "examples"
CALL_EXAMPLES = sorted(EXAMPLES.glob("toolcall_*.json"))
RESULT_EXAMPLES = sorted(EXAMPLES.glob("result_*.json"))

TOOLS = SCHEMA["$defs"]["tool_name"]["enum"]
CODES = SCHEMA["$defs"]["rejection_code"]["enum"]
ADDED_CODES = {"NOT_A_CASTER"}  # decision 2026-10-02, not yet in CLAUDE.md section 6.3
JSON_TYPES = {"str": "string", "int": "integer"}

Doc = dict[str, Any]


def _load(path: Path) -> Doc:
    return json.loads(path.read_text(encoding="utf-8"))


def _errors(validator: Draft202012Validator, doc: Doc) -> list[str]:
    return [e.message for e in validator.iter_errors(doc)]


def _section(text: str, heading: str) -> str:
    start = text.index(heading)
    end = text.find("\n#", start + len(heading))
    return text[start : end if end != -1 else None]


def hp_band(current: int, maximum: int) -> str:
    """CLAUDE.md section 10.2. The engine's copy belongs to WBS 4.x."""
    ratio = current / maximum
    if ratio == 0:
        return "unconscious"
    if ratio <= 0.35:
        return "badly_hurt"
    if ratio <= 0.75:
        return "wounded"
    return "healthy"


def facts_errors(result: Doc) -> list[str]:
    """Rules between fields of one result that JSON Schema cannot express."""
    if not result["ok"]:
        return []
    errors: list[str] = []
    facts = result["narration_facts"]

    if "target_hp_after" in facts:
        after, maximum = facts["target_hp_after"], facts["target_hp_max"]
        if not 0 <= after <= maximum:
            errors.append(f"target_hp_after {after} outside [0, {maximum}]")
        if facts["target_hp_band"] != hp_band(after, maximum):
            errors.append(f"band {facts['target_hp_band']} for {after}/{maximum}")
        if (facts["target_status"] == "unconscious") != (after == 0):
            errors.append(f"status {facts['target_status']} at {after} HP")

    if "damage" in facts:
        if not facts["hit"] and (facts["damage"] or facts["critical"]):
            errors.append("a miss deals no damage and is not a critical")
        expected = max(0, facts["target_hp_before"] - facts["damage"])
        if facts["target_hp_after"] != expected:
            errors.append(f"target_hp_after should be {expected}")

    if "healed_applied" in facts:
        room = facts["target_hp_max"] - facts["target_hp_before"]
        if facts["healed_applied"] != min(facts["healed_rolled"], room):
            errors.append("healed_applied is not the rolled heal capped at max_hp")
        if facts["target_hp_after"] != facts["target_hp_before"] + facts["healed_applied"]:
            errors.append("target_hp_after does not equal before + applied")
        if facts["revived"] != (facts["target_hp_before"] == 0):
            errors.append("revived must be true exactly when the target was at 0 HP")

    if "check_total" in facts and facts["success"] != (facts["check_total"] >= facts["dc"]):
        errors.append("success must be check_total >= dc")

    quantity = facts.get("quantity_after")
    if quantity is not None and quantity != facts["quantity_before"] + facts["delta"]:
        errors.append("quantity_after does not equal before + delta")

    return errors


def model_tool_definitions() -> list[Doc]:
    """The model-facing tool list (prompt d_toolcall.txt), derived from args_*."""
    definitions = []
    for tool in TOOLS:
        args = copy.deepcopy(SCHEMA["$defs"][f"args_{tool}"])
        description = args.pop("description")
        definitions.append({"name": tool, "description": description, "parameters": args})
    return definitions


# --- the schema and its examples ---


def test_schema_is_valid_draft_2020_12() -> None:
    Draft202012Validator.check_schema(SCHEMA)


def test_every_tool_has_a_call_and_result_example() -> None:
    called = {_load(p)["tool"] for p in CALL_EXAMPLES}
    resulted = {_load(p)["tool"] for p in RESULT_EXAMPLES if _load(p)["ok"]}
    assert called == {*TOOLS, None}
    assert resulted == set(TOOLS)


@pytest.mark.parametrize("path", CALL_EXAMPLES, ids=lambda p: p.stem)
def test_call_example_validates(path: Path) -> None:
    assert _errors(CALL_VALIDATOR, _load(path)) == []


@pytest.mark.parametrize("path", RESULT_EXAMPLES, ids=lambda p: p.stem)
def test_result_example_validates(path: Path) -> None:
    result = _load(path)
    assert _errors(RESULT_VALIDATOR, result) == []
    assert facts_errors(result) == []


# --- sync with CLAUDE.md and docs/tool_contract.md ---


def test_rejection_codes_match_claude_md() -> None:
    table = _section((ROOT / "CLAUDE.md").read_text(encoding="utf-8"), "### 6.3")
    documented = re.findall(r"^\| `([A-Z_]+)` \|", table, flags=re.MULTILINE)
    assert len(CODES) == len(set(CODES))
    assert set(CODES) - ADDED_CODES == set(documented)


def test_signatures_match_claude_md() -> None:
    table = _section((ROOT / "CLAUDE.md").read_text(encoding="utf-8"), "### 6.1")
    rows = re.findall(r"^\| `([a-z_]+)` \| (.+?) \| `\w+` \|$", table, flags=re.MULTILINE)
    assert [name for name, _ in rows] == TOOLS
    for name, params in rows:
        expected = re.findall(r"`(\w+): (\w+)`", params)
        args = SCHEMA["$defs"][f"args_{name}"]
        assert list(args["properties"]) == [p for p, _ in expected]
        assert args["required"] == [p for p, _ in expected]
        for param, py_type in expected:
            prop = args["properties"][param]
            assert prop.get("type", "string") == JSON_TYPES[py_type], f"{name}.{param}"


def test_every_code_is_reachable_in_the_doc_matrix() -> None:
    matrix = _section((ROOT / "docs" / "tool_contract.md").read_text(encoding="utf-8"), "## 3.")
    rows = dict(re.findall(r"^\| `([A-Z_]+)` \|(.+)\|$", matrix, flags=re.MULTILINE))
    assert list(rows) == CODES, "matrix rows must list every code, in validation order"
    for code, cells in rows.items():
        assert "✓" in cells, f"{code} is raised by no tool"


def test_every_tool_has_facts() -> None:
    for tool in TOOLS:
        assert f"facts_{tool}" in SCHEMA["$defs"]


def test_model_tool_definitions_are_described() -> None:
    definitions = model_tool_definitions()
    assert [d["name"] for d in definitions] == TOOLS
    for definition in definitions:
        assert definition["description"]
        for param, prop in definition["parameters"]["properties"].items():
            assert prop.get("description"), f"{definition['name']}.{param}"


# --- rejections ---


def _parent(doc: Doc, keys: list[str]) -> Any:
    node: Any = doc
    for key in keys:
        node = node[int(key)] if isinstance(node, list) else node[key]
    return node


def _set(path: str, value: Any) -> Callable[[Doc], None]:
    *parents, leaf = path.split(".")

    def mutate(doc: Doc) -> None:
        _parent(doc, parents)[leaf] = value

    return mutate


def _delete(path: str) -> Callable[[Doc], None]:
    *parents, leaf = path.split(".")

    def mutate(doc: Doc) -> None:
        del _parent(doc, parents)[leaf]

    return mutate


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


@pytest.mark.parametrize("example,mutate", CALL_REJECTS.values(), ids=CALL_REJECTS.keys())
def test_call_schema_rejects(example: str, mutate: Callable[[Doc], None]) -> None:
    call = _load(EXAMPLES / f"toolcall_{example}.json")
    mutate(call)
    assert _errors(CALL_VALIDATOR, call), "schema accepted an invalid call"


CALL_ACCEPTS = {
    "unprefixed_id": ("attack", _set("arguments.target_id", "rat")),
    "unknown_spell": ("cast_spell", _set("arguments.spell_id", "spell_fireball")),
    "unknown_skill": ("skill_check", _set("arguments.skill", "athletics")),
    "dc_out_of_range": ("skill_check", _set("arguments.dc", 40)),
    "short_justification": ("update_npc_relationship", _set("arguments.justification", "ok")),
}


@pytest.mark.parametrize("example,mutate", CALL_ACCEPTS.values(), ids=CALL_ACCEPTS.keys())
def test_call_schema_leaves_value_checks_to_their_own_codes(
    example: str, mutate: Callable[[Doc], None]
) -> None:
    """These pass SCHEMA_VIOLATION so the validator can return the specific code
    and valid_options (docs/tool_contract.md section 1)."""
    call = _load(EXAMPLES / f"toolcall_{example}.json")
    mutate(call)
    assert _errors(CALL_VALIDATOR, call) == []


RESULT_REJECTS = {
    "unknown_code": ("rejected_target_unconscious", _set("rejection_code", "TOO_FAR")),
    "missing_code": ("rejected_target_unconscious", _delete("rejection_code")),
    "retry_not_allowed": ("rejected_target_unconscious", _set("retry_allowed", False)),
    "empty_message": ("rejected_target_unconscious", _set("message", "")),
    "options_not_list": ("rejected_target_unconscious", _set("valid_options.target_id", "x")),
    "ok_with_code": ("attack", _set("rejection_code", "SCHEMA_VIOLATION")),
    "facts_of_other_tool": ("dodge", _set("tool", "attack")),
    "unknown_fact": ("attack", _set("narration_facts.mood", "angry")),
    "missing_band": ("attack", _delete("narration_facts.target_hp_band")),
    "unknown_band": ("attack", _set("narration_facts.target_hp_band", "fine")),
    "negative_damage": ("attack", _set("narration_facts.damage", -1)),
    "unknown_spell": ("cast_spell_fire_bolt", _set("narration_facts.spell", "fireball")),
    "fire_bolt_with_heal": ("cast_spell_fire_bolt", _set("narration_facts.healed_applied", 1)),
    "cure_without_slots": ("cast_spell_cure_wounds", _delete("narration_facts.slots_remaining")),
    "cure_with_attack_roll": ("cast_spell_cure_wounds", _set("narration_facts.attack_roll", 9)),
    "dc_out_of_range": ("skill_check", _set("narration_facts.dc", 30)),
    "negative_quantity": ("modify_inventory", _set("narration_facts.quantity_after", -1)),
    "unknown_stance": ("update_npc_relationship", _set("narration_facts.stance_after", "loyal")),
    "unknown_quest_state": ("update_quest", _set("narration_facts.state_after", "abandoned")),
    "bad_dice_notation": ("attack", _set("rolls.0.notation", "1d7+5")),
    "bad_advantage_mode": ("attack", _set("rolls.0.advantage_mode", "double")),
    "diff_without_path": ("attack", _delete("state_diff.0.path")),
}


@pytest.mark.parametrize("example,mutate", RESULT_REJECTS.values(), ids=RESULT_REJECTS.keys())
def test_result_schema_rejects(example: str, mutate: Callable[[Doc], None]) -> None:
    result = _load(EXAMPLES / f"result_{example}.json")
    mutate(result)
    assert _errors(RESULT_VALIDATOR, result), "schema accepted an invalid result"


FACTS_REJECTS = {
    "wrong_band": ("attack", _set("narration_facts.target_hp_band", "badly_hurt")),
    "hp_does_not_add_up": ("attack", _set("narration_facts.target_hp_after", 5)),
    "miss_with_damage": ("attack", _set("narration_facts.hit", False)),
    "status_at_zero_hp": ("attack", _set("narration_facts.target_hp_after", 0)),
    "heal_over_cap": ("cast_spell_cure_wounds", _set("narration_facts.healed_applied", 9)),
    "revived_when_conscious": ("cast_spell_cure_wounds", _set("narration_facts.revived", True)),
    "success_below_dc": ("skill_check", _set("narration_facts.dc", 13)),
    "quantity_mismatch": ("modify_inventory", _set("narration_facts.quantity_after", 2)),
}


@pytest.mark.parametrize("example,mutate", FACTS_REJECTS.values(), ids=FACTS_REJECTS.keys())
def test_facts_rejects(example: str, mutate: Callable[[Doc], None]) -> None:
    result = _load(EXAMPLES / f"result_{example}.json")
    mutate(result)
    assert facts_errors(result), "facts_errors accepted inconsistent facts"


def test_claude_md_attack_example_band_is_wrong() -> None:
    """CLAUDE.md section 6.2 gives 4 of 11 HP as badly_hurt; section 10.2 makes it
    wounded (0.36 > 0.35). The example here uses wounded; fix section 6.2 at the 2.6
    freeze, then delete this test."""
    assert hp_band(4, 11) == "wounded"
