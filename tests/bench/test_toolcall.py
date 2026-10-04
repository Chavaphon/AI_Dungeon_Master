"""Tool-calling micro-benchmark (WBS 3.3): the 20 cases are well formed, the
prompt follows CLAUDE.md section 9.1, the scorer grades recorded outputs
correctly, and a full run completes unattended against a fake Ollama.

No test calls a model. The fake server is an httpx.MockTransport.

Run: pytest tests/bench/test_toolcall.py -v
"""

import importlib.util
import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from adm.bench import toolcall

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "schemas" / "tools.schema.json").read_text(encoding="utf-8"))
TOOLS = SCHEMA["$defs"]["tool_name"]["enum"]
SPELLS = {"spell_fire_bolt", "spell_cure_wounds"}

Doc = dict[str, Any]


def _contract_module() -> Any:
    """tests/test_tool_contract.py, loaded by path: it holds the reference derivation."""
    path = ROOT / "tests" / "test_tool_contract.py"
    spec = importlib.util.spec_from_file_location("_tool_contract_reference", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- the cases ---


CASES = toolcall.load_cases()


def test_there_are_exactly_twenty_cases_with_unique_ids() -> None:
    assert len(CASES) == 20
    assert len({c["id"] for c in CASES}) == 20


def test_cases_cover_every_tool_and_null() -> None:
    assert {c["expected"]["tool"] for c in CASES} == {*TOOLS, None}


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_expected_call_is_a_valid_proposed_call(case: Doc) -> None:
    assert toolcall.schema_errors(case["expected"]) == []


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_expected_ids_exist_in_the_case_state(case: Doc) -> None:
    state = toolcall.load_state(case["state"])
    known = (
        set(state["combatants"])
        | set(state["item_definitions"])
        | set(state["npc_relationships"])
        | set(state["quests"])
        | SPELLS
    )
    arguments = case["expected"].get("arguments", {})
    missing = [v for k, v in arguments.items() if k.endswith("_id") and v not in known]
    assert not missing


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_ignored_arguments_exist_on_the_expected_call(case: Doc) -> None:
    assert set(case["ignore_args"]) <= set(case["expected"].get("arguments", {}))


# --- the prompt ---


def test_tool_definitions_match_the_contract_reference() -> None:
    assert toolcall.tool_definitions() == _contract_module().model_tool_definitions()


def test_system_prompt_follows_section_9_1_order() -> None:
    state = toolcall.load_state("state_02_mid_combat")
    prompt = toolcall.build_system_prompt(state)
    state_json = json.dumps(state, indent=2, ensure_ascii=False)
    positions = [
        prompt.index("You are the Dungeon Master"),
        prompt.index("The authoritative game state"),
        prompt.index(state_json),
        prompt.index("<tools>"),
        prompt.index("Decide the single game action"),
    ]
    assert positions == sorted(positions)
    for tool in TOOLS:
        assert f'"name": "{tool}"' in prompt


def test_chat_request_carries_the_player_input_as_the_user_message() -> None:
    case = CASES[0]
    request = toolcall.build_chat_request("m", case, toolcall.load_state(case["state"]))
    assert request["messages"][0]["role"] == "system"
    assert request["messages"][1] == {"role": "user", "content": case["input"]}
    assert request["stream"] is False


def test_every_sampling_option_is_set_explicitly() -> None:
    request = toolcall.build_chat_request("m", CASES[0], toolcall.load_state(CASES[0]["state"]))
    options = request["options"]
    assert options["num_ctx"] == 8192
    assert options["num_predict"] == 200
    assert options["temperature"] == 0.0
    for key in ("top_p", "top_k", "min_p", "seed", "repeat_penalty", "presence_penalty"):
        assert key in options


def test_think_false_is_sent_only_to_thinking_models() -> None:
    state = toolcall.load_state(CASES[0]["state"])
    thinking = toolcall.build_chat_request("m", CASES[0], state, thinking=True)
    plain = toolcall.build_chat_request("m", CASES[0], state, thinking=False)
    assert thinking["think"] is False
    assert "think" not in plain


def test_format_is_sent_only_in_json_mode() -> None:
    state = toolcall.load_state(CASES[0]["state"])
    assert "format" not in toolcall.build_chat_request("m", CASES[0], state)
    assert toolcall.build_chat_request("m", CASES[0], state, fmt="json")["format"] == "json"


# --- the scorer ---


ATTACK = {
    "tool": "attack",
    "arguments": {
        "attacker_id": "pc_lyra",
        "target_id": "npc_rat_01",
        "weapon_id": "item_short_sword",
    },
}
SKILL = {"tool": "skill_check", "arguments": {"actor_id": "pc_lyra", "skill": "stealth", "dc": 12}}


def test_clean_json_scores_fully() -> None:
    s = toolcall.score(json.dumps(ATTACK), ATTACK, [])
    assert s["strict_parse"] and s["schema_valid"] and s["schema_valid_lenient"]
    assert s["tool_match"] and s["args_match"]


def test_fenced_json_is_valid_only_leniently() -> None:
    raw = "```json\n" + json.dumps(ATTACK) + "\n```"
    s = toolcall.score(raw, ATTACK, [])
    assert not s["strict_parse"] and not s["schema_valid"]
    assert s["lenient_parse"] and s["schema_valid_lenient"] and s["tool_match"]


def test_prose_around_json_is_valid_only_leniently() -> None:
    raw = "Sure! Here is the call: " + json.dumps(ATTACK) + " Let me know."
    s = toolcall.score(raw, ATTACK, [])
    assert not s["schema_valid"] and s["schema_valid_lenient"] and s["args_match"]


def test_unparseable_output_scores_nothing() -> None:
    s = toolcall.score("I attack the rat!", ATTACK, [])
    assert not any(
        s[k] for k in ("strict_parse", "lenient_parse", "schema_valid", "tool_match", "args_match")
    )


def test_null_tool_with_arguments_is_schema_invalid() -> None:
    s = toolcall.score('{"tool": null, "arguments": {}}', {"tool": None}, [])
    assert s["strict_parse"] and not s["schema_valid"] and s["tool_match"]


def test_bare_null_tool_scores_fully() -> None:
    s = toolcall.score('{"tool": null}', {"tool": None}, [])
    assert s["schema_valid"] and s["tool_match"] and s["args_match"]


def test_unknown_tool_is_schema_invalid() -> None:
    s = toolcall.score('{"tool": "dash", "arguments": {"actor_id": "pc_lyra"}}', ATTACK, [])
    assert s["strict_parse"] and not s["schema_valid"] and not s["tool_match"]
    assert s["schema_errors"]


def test_wrong_argument_type_is_schema_invalid() -> None:
    raw = json.dumps({**SKILL, "arguments": {**SKILL["arguments"], "dc": "12"}})
    s = toolcall.score(raw, SKILL, ["dc"])
    assert not s["schema_valid"] and s["tool_match"]


def test_ignored_argument_does_not_affect_args_match() -> None:
    raw = json.dumps({**SKILL, "arguments": {**SKILL["arguments"], "dc": 15}})
    assert toolcall.score(raw, SKILL, ["dc"])["args_match"]
    assert not toolcall.score(raw, SKILL, [])["args_match"]


def test_wrong_target_misses_args_match_only() -> None:
    wrong = {**ATTACK, "arguments": {**ATTACK["arguments"], "target_id": "npc_rat_02"}}
    s = toolcall.score(json.dumps(wrong), ATTACK, [])
    assert s["schema_valid"] and s["tool_match"] and not s["args_match"]


def test_json_array_is_not_a_parse() -> None:
    s = toolcall.score("[1, 2]", ATTACK, [])
    assert not s["strict_parse"] and not s["lenient_parse"]


# --- the runner, against a fake Ollama ---


MODEL = "fake-model:1b"
DIGEST = "abcdef123456" + "0" * 52
TIMEOUT_INPUT = CASES[1]["input"]


def _fake_ollama(chat_calls: list[Doc]) -> httpx.MockTransport:
    replies = {c["input"]: json.dumps(c["expected"]) for c in CASES}
    replies[CASES[2]["input"]] = "not json at all"

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": MODEL, "digest": DIGEST}]})
        if path == "/api/show":
            return httpx.Response(200, json={"capabilities": ["completion", "thinking"]})
        if path == "/api/ps":
            return httpx.Response(
                200, json={"models": [{"name": MODEL, "size": 1000, "size_vram": 900}]}
            )
        if path == "/api/chat":
            body = json.loads(request.content)
            chat_calls.append(body)
            user = body["messages"][-1]["content"]
            if user == TIMEOUT_INPUT:
                raise httpx.ReadTimeout("timed out", request=request)
            content = replies.get(user, '{"tool": null}')
            return httpx.Response(
                200,
                json={
                    "message": {"role": "assistant", "content": content},
                    "total_duration": 2_000_000_000,
                    "load_duration": 1_000_000,
                    "prompt_eval_count": 1500,
                    "eval_count": 40,
                    "eval_duration": 1_000_000_000,
                },
            )
        return httpx.Response(404, json={"error": "not found"})

    return httpx.MockTransport(handler)


def _run(tmp_path: Path, models: list[str], **kwargs: Any) -> tuple[Doc, list[Doc]]:
    calls: list[Doc] = []
    with httpx.Client(base_url="http://ollama.test", transport=_fake_ollama(calls)) as client:
        summary = toolcall.run(models, client=client, out_dir=tmp_path, **kwargs)
    return summary, calls


def test_full_run_completes_and_scores_unattended(tmp_path: Path) -> None:
    summary, calls = _run(tmp_path, [MODEL])
    result = summary["models"][0]

    assert result["model"] == MODEL
    assert result["digest"] == DIGEST
    assert result["gpu_share"] == pytest.approx(0.9)
    assert result["thinking"] is True
    assert result["n"] == 20
    assert result["errors"] == 1
    # 18 of 20 valid: one timeout, one non-JSON reply.
    assert result["schema_valid_rate"] == pytest.approx(18 / 20)
    assert result["tool_match_rate"] == pytest.approx(18 / 20)
    assert result["tokens_per_s_mean"] == pytest.approx(40.0)
    assert result["prompt_tokens_mean"] == pytest.approx(1500)

    # warm-up plus 20 cases, every one with think false
    assert len(calls) == 21
    assert all(c["think"] is False for c in calls)


def test_run_writes_one_record_per_case_and_a_summary(tmp_path: Path) -> None:
    _run(tmp_path, [MODEL])
    lines = (tmp_path / "fake-model_1b.jsonl").read_text(encoding="utf-8").splitlines()
    records = [json.loads(line) for line in lines]
    assert [r["case_id"] for r in records] == [c["id"] for c in CASES]

    timed_out = records[1]
    assert timed_out["error"] and not timed_out["schema_valid"]
    assert records[2]["raw_output"] == "not json at all"
    assert records[0]["raw_output"] == json.dumps(CASES[0]["expected"])

    saved = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert saved["models"][0]["n"] == 20
    assert saved["format"] is None


def test_missing_model_is_skipped_and_others_still_run(tmp_path: Path) -> None:
    summary, _ = _run(tmp_path, ["absent:7b", MODEL])
    absent, present = summary["models"]
    assert absent["model"] == "absent:7b" and "not installed" in absent["error"]
    assert present["n"] == 20


def test_limit_and_repeats(tmp_path: Path) -> None:
    summary, calls = _run(tmp_path, [MODEL], limit=3, repeats=2)
    assert summary["models"][0]["n"] == 6
    assert len(calls) == 1 + 6


def test_json_mode_is_recorded_and_sent(tmp_path: Path) -> None:
    summary, calls = _run(tmp_path, [MODEL], fmt="json", limit=1)
    assert summary["format"] == "json"
    assert calls[-1]["format"] == "json"


def test_p95_uses_nearest_rank() -> None:
    assert toolcall.p95([float(x) for x in range(1, 21)]) == 19.0
    assert toolcall.p95([5.0]) == 5.0
    assert toolcall.p95([]) is None
