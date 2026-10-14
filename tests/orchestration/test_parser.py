"""Tool-call parser (WBS 6.3): raw model output becomes a proposed tool call or
a parse failure, never anything else (invariant 6), and recovery is limited to
extraction and the safe repairs.

The recorded cases are model replies from the Week 2 benchmarks, copied from
the gitignored `results/bench/` into
`fixtures/recorded_toolcall_outputs.jsonl`; `source` names the run file and
line. The benchmark had no fenced, broken or cut-off JSON
(docs/model_benchmark.md), so those cases are hand-written below and are not
counted as recorded.

No test calls a model.

Run: pytest tests/orchestration/test_parser.py -v
"""

import json
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from adm.orchestration import parser as ps

Doc = dict[str, Any]

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = ROOT / "schemas"
EXAMPLES = sorted((SCHEMAS / "examples").glob("toolcall_*.json"))
RECORDED_PATH = Path(__file__).parent / "fixtures" / "recorded_toolcall_outputs.jsonl"
RECORDED = [json.loads(line) for line in RECORDED_PATH.read_text(encoding="utf-8").splitlines()]


def _schema(name: str) -> Doc:
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


AUDIT = _schema("audit.schema.json")
REGISTRY = Registry().with_resources(
    (s["$id"], Resource.from_contents(s))
    for s in (AUDIT, _schema("state.schema.json"), _schema("tools.schema.json"))
)


def _audit_def(name: str) -> Draft202012Validator:
    return Draft202012Validator({"$ref": f"{AUDIT['$id']}#/$defs/{name}"}, registry=REGISTRY)


PARSED_CALL = _audit_def("parsed_call")
PARSE_FAILURE = _audit_def("parse_failure")

DODGE = '{"tool": "dodge", "arguments": {"actor_id": "pc_lyra"}}'


def _parsed(raw: str) -> ps.ParsedCall:
    result = ps.parse_tool_call(raw)
    assert isinstance(result, ps.ParsedCall), result
    PARSED_CALL.validate(result.call)
    return result


def _failure(raw: str) -> ps.ParseFailure:
    result = ps.parse_tool_call(raw)
    assert isinstance(result, ps.ParseFailure), result
    return result


# --- recorded Week 2 outputs -------------------------------------------------


def test_at_least_twenty_recorded_malformed_outputs():
    """CLAUDE.md section 13: every recorded case broke the tool contract."""
    raws = [case["raw_output"] for case in RECORDED]
    assert len(set(raws)) == len(raws) >= 20


@pytest.mark.parametrize("case", RECORDED, ids=[case["source"] for case in RECORDED])
def test_recorded_output(case: Doc):
    if case["expect"] == "unparseable":
        assert _failure(case["raw_output"]).reason == case["reason"]
    else:
        result = _parsed(case["raw_output"])
        assert result.call["tool"] == case["tool"]
        assert result.repairs == tuple(case["repairs"])


def test_recorded_trailing_tag_is_cut_off():
    raw = next(c["raw_output"] for c in RECORDED if "</think>" in c["raw_output"])
    assert _parsed(raw).call == json.loads(DODGE)


def test_recorded_string_null_is_left_for_the_validator():
    """`{"tool": "null"}` is not normalised: it is a SCHEMA_VIOLATION, not no_tool."""
    raw = next(c["raw_output"] for c in RECORDED if c.get("tool") == "null")
    assert _parsed(raw).call == {"tool": "null"}


# --- well-formed replies -----------------------------------------------------


@pytest.mark.parametrize("path", EXAMPLES, ids=[p.stem for p in EXAMPLES])
def test_example_call_parses_unchanged(path: Path):
    raw = path.read_text(encoding="utf-8")
    assert ps.parse_tool_call(raw) == ps.ParsedCall(call=json.loads(raw), repairs=())


@given(
    call=st.sampled_from([json.loads(p.read_text(encoding="utf-8")) for p in EXAMPLES]),
    before=st.text(alphabet=st.characters(blacklist_characters="{}`")),
    after=st.text(alphabet=st.characters(blacklist_characters="{}`")),
)
def test_call_inside_any_prose_is_extracted(call: Doc, before: str, after: str):
    result = ps.parse_tool_call(before + json.dumps(call) + after)
    assert isinstance(result, ps.ParsedCall)
    assert result.call == call
    assert set(result.repairs) <= {"surrounding_text"}


# --- extraction (hand-written, not recorded) ---------------------------------


@pytest.mark.parametrize(
    ("raw", "repairs"),
    [
        (f"```json\n{DODGE}\n```", ("code_fence",)),
        (f"```\n{DODGE}\n```", ("code_fence",)),
        (f"Here is the action:\n```json\n{DODGE}\n```\nGood luck!", ("code_fence",)),
        (f"I will dodge.\n{DODGE}", ("surrounding_text",)),
        (f"{DODGE}\nYou brace yourself.", ("surrounding_text",)),
        (f"  \n{DODGE}\n  ", ()),
        (f"[{DODGE}]", ("surrounding_text",)),
    ],
    ids=[
        "fence-json",
        "fence-bare",
        "fence-in-prose",
        "prose-before",
        "prose-after",
        "whitespace",
        "in-array",
    ],
)
def test_extraction(raw: str, repairs: tuple[str, ...]):
    result = _parsed(raw)
    assert result.call == json.loads(DODGE)
    assert result.repairs == repairs


def test_first_call_wins_and_the_second_is_flagged():
    result = _parsed('{"tool": null}\n{"tool": "dodge", "arguments": {"actor_id": "pc_lyra"}}')
    assert result.call == {"tool": None}
    assert result.repairs == ("surrounding_text", "multiple_objects")


def test_object_without_tool_is_skipped():
    result = _parsed('<state>{"turn_number": 3}</state> ' + DODGE)
    assert result.call == json.loads(DODGE)


def test_contract_is_not_checked():
    """Unknown tools and missing arguments are the validator's SCHEMA_VIOLATION."""
    assert _parsed('{"tool": "attack"}').call == {"tool": "attack"}
    assert _parsed('{"tool": "dash", "arguments": {}}').call["tool"] == "dash"
    assert _parsed('{"tool": "skill_check", "arguments": {"dc": "12"}}').repairs == ()


# --- safe repairs (hand-written, not recorded) -------------------------------


@pytest.mark.parametrize(
    ("raw", "call", "repairs"),
    [
        (
            '{"tool": "dodge", "arguments": {"actor_id": "pc_lyra",},}',
            json.loads(DODGE),
            ("trailing_comma",),
        ),
        (
            '{"tool": "dodge", "arguments": {"actor_id": "pc_lyra"\n,\n}\n}',
            json.loads(DODGE),
            ("trailing_comma",),
        ),
        ('{"tool": None}', {"tool": None}, ("python_literal",)),
        (
            '{"tool": "update_quest", "arguments": {"quest_id": "quest_x", "transition": "start"',
            {"tool": "update_quest", "arguments": {"quest_id": "quest_x", "transition": "start"}},
            ("closed_truncation",),
        ),
        (
            '{"tool": "dodge", "arguments": {"actor_id": "pc_lyra"},',
            json.loads(DODGE),
            ("trailing_comma", "closed_truncation"),
        ),
        (
            f"```json\n{DODGE[:-1]}",
            json.loads(DODGE),
            ("surrounding_text", "closed_truncation"),
        ),
        (
            'Action: {"tool": "dodge", "arguments": {"actor_id": "pc_lyra",}} You brace.',
            json.loads(DODGE),
            ("surrounding_text", "trailing_comma"),
        ),
    ],
    ids=[
        "trailing-commas",
        "trailing-comma-newlines",
        "python-none",
        "truncated",
        "truncated-after-comma",
        "truncated-in-open-fence",
        "repair-in-prose",
    ],
)
def test_safe_repair(raw: str, call: Doc, repairs: tuple[str, ...]):
    result = _parsed(raw)
    assert result.call == call
    assert result.repairs == repairs


def test_strings_are_never_edited():
    justification = 'She said None, True, False, {braces}, [x,] and \\"quotes\\",'
    raw = (
        '{"tool": "update_npc_relationship", "arguments": {"npc_id": "npc_keeper", '
        f'"direction": "up", "justification": "{justification}",}}}}'
    )
    result = _parsed(raw)
    assert result.call["arguments"]["justification"] == json.loads(f'"{justification}"')
    assert result.repairs == ("trailing_comma",)


def test_word_containing_a_literal_is_not_repaired():
    _failure('{"tool": "dodge", "arguments": {"actor_id": Nonesuch}}')


# --- failures ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "reason"),
    [
        ("", "no_json"),
        ("I attack the rat!", "no_json"),
        ("[1, 2]", "no_json"),
        ('"dodge"', "no_json"),
        ("{'tool': 'dodge', 'arguments': {'actor_id': 'pc_lyra'}}", "no_json"),
        ('{tool: "dodge"}', "no_json"),
        ('{"tool": "update_npc_relationship", "arguments": {"justification": "Becau', "no_json"),
        ('{"action": "attack", "target": "npc_rat_01"}', "no_tool_key"),
        ('<state>{"turn_number": 3}</state>', "no_tool_key"),
        ('{"arguments": {"actor_id": "pc_lyra",}}', "no_tool_key"),
    ],
    ids=[
        "empty",
        "prose",
        "array",
        "string",
        "single-quotes",
        "unquoted-key",
        "cut-inside-string",
        "other-object",
        "echoed-state",
        "repaired-without-tool",
    ],
)
def test_unparseable(raw: str, reason: str):
    failure = _failure(raw)
    assert failure.reason == reason
    PARSE_FAILURE.validate({"ok": False, "failure": "unparseable", "message": failure.message})


def test_failure_message_matches_the_audit_example():
    example = json.loads((SCHEMAS / "examples" / "audit_turn_rejected.json").read_text("utf-8"))
    messages = [v.get("message") for v in example["validation"] if v.get("failure")]
    assert messages == [ps.EXPECTED_FORMAT]
