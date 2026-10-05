"""Context budget (WBS 3.5): the fixtures are well formed, the prompts follow
CLAUDE.md sections 8 and 9.1, the K arithmetic is right, and a full run
completes unattended against a fake Ollama.

No test calls a model. The fake server is an httpx.MockTransport whose token
count is a fixed function of the messages, so the derived figures are exact.

Run: pytest tests/bench/test_context.py -v
"""

import importlib.util
import json
import math
import re
from pathlib import Path
from typing import Any

import httpx
import pytest

from adm.bench import context, toolcall

ROOT = Path(__file__).resolve().parents[2]
HISTORY = context.load_history()
CEILING = context.load_ceiling_state()

Doc = dict[str, Any]


def _state_schema_module() -> Any:
    """tests/test_state_schema.py, loaded by path: it holds the cross-field rules."""
    path = ROOT / "tests" / "test_state_schema.py"
    spec = importlib.util.spec_from_file_location("_state_schema_reference", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- the fixtures ---


def test_ceiling_state_is_a_valid_state() -> None:
    module = _state_schema_module()
    assert module._schema_errors(CEILING) == []
    assert module.cross_field_errors(CEILING) == []


def test_ceiling_state_is_the_documented_authoring_ceiling() -> None:
    combatants = CEILING["combatants"].values()
    assert sum(c["is_player_character"] for c in combatants) == 1
    assert sum(c["faction"] == "hostile" for c in combatants) == 6
    assert len(CEILING["npc_relationships"]) == 3
    assert len(CEILING["item_definitions"]) == 12
    assert len(CEILING["quests"]) == 4
    assert CEILING["encounter_active"] is True


def test_ceiling_state_is_larger_than_every_example() -> None:
    ceiling = len(json.dumps(CEILING))
    for path in (ROOT / "schemas" / "examples").glob("state_*.json"):
        assert ceiling > len(json.dumps(json.loads(path.read_text(encoding="utf-8"))))


def test_history_has_enough_turns_for_the_sweep() -> None:
    assert len(HISTORY["turns"]) == 32
    for turn in HISTORY["turns"]:
        assert turn["player_input"].strip() and turn["narration"].strip()


def test_history_and_summary_hold_no_numbers() -> None:
    # No dice notation in narration (section 9.1), no numeric state in the summary (8.1).
    texts = [HISTORY["summary"]] + [t["narration"] for t in HISTORY["turns"]]
    assert not [t for t in texts if re.search(r"\d", t)]


def test_narration_probes_name_successful_results() -> None:
    probes = HISTORY["narration_probes"]
    assert len(probes) == 8
    for probe in probes:
        result = context.load_result(probe["result"])
        assert result["ok"] is True and result["narration_facts"]


# --- the prompts ---


def test_toolcall_prompt_puts_the_summary_after_tools_and_before_the_instruction() -> None:
    prompt = context.toolcall_system_prompt(CEILING, "Lyra found a key.")
    positions = [
        prompt.index("You are the Dungeon Master"),
        prompt.index("The authoritative game state"),
        prompt.index("<tools>"),
        prompt.index("<summary>\nLyra found a key.\n</summary>"),
        prompt.index("Decide the single game action"),
    ]
    assert positions == sorted(positions)


def test_toolcall_prompt_without_summary_is_the_3_3_prompt() -> None:
    state = toolcall.load_state("state_02_mid_combat")
    assert context.toolcall_system_prompt(state, None) == toolcall.build_system_prompt(state)


def test_self_check_prompt_follows_section_9_1() -> None:
    prompt = context.self_check_system_prompt(CEILING, None)
    assert prompt.index("The authoritative game state") < prompt.index("Before you reply")
    assert "<tools>" not in prompt


def test_narration_prompt_carries_the_facts_as_an_array() -> None:
    facts = [context.load_result("result_attack")["narration_facts"]]
    prompt = context.narration_system_prompt(facts)
    assert "The rules engine has resolved the action." in prompt
    assert json.dumps(facts, indent=2, ensure_ascii=False) in prompt
    assert "<state>" not in prompt


def test_messages_follow_section_8_order() -> None:
    turns = HISTORY["turns"]
    messages = context.build_messages("SYSTEM", turns, 3, "now")
    assert [m["role"] for m in messages] == [
        "system",
        "user",
        "assistant",
        "user",
        "assistant",
        "user",
        "assistant",
        "user",
    ]
    # the last three turns, oldest first
    assert messages[1]["content"] == turns[-3]["player_input"]
    assert messages[6]["content"] == turns[-1]["narration"]
    assert messages[-1] == {"role": "user", "content": "now"}


def test_k_zero_has_no_history_and_k_out_of_range_is_refused() -> None:
    assert len(context.build_messages("S", HISTORY["turns"], 0, "now")) == 2
    with pytest.raises(ValueError):
        context.history_messages(HISTORY["turns"], len(HISTORY["turns"]) + 1)
    with pytest.raises(ValueError):
        context.history_messages(HISTORY["turns"], -1)


def test_accuracy_request_at_k_zero_is_the_3_3_request() -> None:
    case = toolcall.load_cases()[7]
    state = toolcall.load_state(case["state"])
    ours = context.accuracy_request("m", case, HISTORY, 0, thinking=True, fmt=None)
    assert ours == toolcall.build_chat_request("m", case, state, thinking=True)


def test_accuracy_request_above_zero_adds_summary_and_history() -> None:
    case = toolcall.load_cases()[0]
    request = context.accuracy_request("m", case, HISTORY, 8, thinking=False, fmt="json")
    assert "<summary>" in request["messages"][0]["content"]
    assert len(request["messages"]) == 1 + 2 * 8 + 1
    assert request["messages"][-1]["content"] == case["input"]
    assert request["format"] == "json"


def test_narration_options_use_section_2_2_values() -> None:
    options = context.narration_options(3)
    assert options["temperature"] == 0.7
    assert options["num_predict"] == 300
    assert options["seed"] == 3
    assert options["num_ctx"] == 8192
    assert set(options) == set(toolcall.OPTIONS)


def test_token_count_options_generate_one_token() -> None:
    options = context.token_count_options()
    assert options["num_predict"] == 1 and options["temperature"] == 0.0


# --- the arithmetic ---


def test_k_fit_uses_the_free_space_after_prefix_and_reply() -> None:
    # 8192 - 200 - 4000 = 3992 free, 380 per turn -> 10
    assert context.k_fit(4000, 380, reply_tokens=200) == 10
    assert context.k_fit(8000, 380, reply_tokens=200) == 0
    assert context.k_fit(4000, 0, reply_tokens=200) == 0


def test_fit_line_recovers_a_line() -> None:
    intercept, slope = context.fit_line([0, 4, 8], [100, 140, 180])
    assert intercept == pytest.approx(100) and slope == pytest.approx(10)


def test_truncation_is_flagged_where_the_prompt_stops_growing() -> None:
    assert context.truncated_at([0, 4, 8, 12], [100, 140, 180, 220]) == []
    assert context.truncated_at([0, 4, 8, 12], [100, 140, 140, 130]) == [8, 12]


def _row(k: int, valid: float, tool: float) -> Doc:
    return {"k": k, "schema_valid_rate": valid, "tool_match_rate": tool}


def test_largest_stable_k_allows_one_case_in_twenty() -> None:
    rows = [_row(0, 1.0, 0.80), _row(8, 0.95, 0.75), _row(16, 0.90, 0.80)]
    assert context.largest_stable_k(rows, limit=16) == 8


def test_largest_stable_k_respects_the_limit() -> None:
    rows = [_row(0, 1.0, 0.8), _row(8, 1.0, 0.8), _row(16, 1.0, 0.8)]
    assert context.largest_stable_k(rows, limit=10) == 8


def test_largest_stable_k_needs_a_baseline() -> None:
    assert context.largest_stable_k([_row(8, 1.0, 1.0)], limit=16) is None


# --- the runner, against a fake Ollama ---


MODEL = "fake-model:1b"
PER_MESSAGE = 3
NARRATION_TOKENS = 90


def _fake_tokens(messages: list[Doc]) -> int:
    return sum(math.ceil(len(m["content"]) / 4) + PER_MESSAGE for m in messages)


def _fake_ollama(chat_calls: list[Doc], cap: int | None = None) -> httpx.MockTransport:
    replies = {c["input"]: json.dumps(c["expected"]) for c in toolcall.load_cases()}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": MODEL, "digest": "d" * 64}]})
        if path == "/api/show":
            return httpx.Response(200, json={"capabilities": ["completion"]})
        if path == "/api/ps":
            return httpx.Response(
                200, json={"models": [{"name": MODEL, "size": 10, "size_vram": 10}]}
            )
        if path == "/api/chat":
            body = json.loads(request.content)
            chat_calls.append(body)
            tokens = _fake_tokens(body["messages"])
            if cap is not None:
                tokens = min(tokens, cap)
            options = body["options"]
            if options["num_predict"] == 1:
                content, count = "", 1
            elif options["temperature"] == 0.7:
                content, count = "You swing and the rat squeals.", NARRATION_TOKENS
            else:
                content = replies.get(body["messages"][-1]["content"], '{"tool": null}')
                count = 20
            return httpx.Response(
                200,
                json={
                    "message": {"role": "assistant", "content": content},
                    "prompt_eval_count": tokens,
                    "eval_count": count,
                    "eval_duration": 1_000_000_000,
                    "done_reason": "stop",
                },
            )
        return httpx.Response(404, json={"error": "not found"})

    return httpx.MockTransport(handler)


def _run(
    tmp_path: Path, models: list[str], cap: int | None = None, **kwargs: Any
) -> tuple[Doc, list[Doc]]:
    calls: list[Doc] = []
    transport = _fake_ollama(calls, cap)
    with httpx.Client(base_url="http://ollama.test", transport=transport) as client:
        summary = context.run(models, client=client, out_dir=tmp_path, **kwargs)
    return summary, calls


def test_token_phase_derives_exact_figures(tmp_path: Path) -> None:
    summary, _ = _run(tmp_path, [MODEL], phases=("tokens",))
    tokens = summary["models"][0]["tokens"]
    longest = context.longest_input(HISTORY)

    # two one-token messages, each with the fake's per-message template
    assert tokens["pair_overhead"] == pytest.approx(2 * PER_MESSAGE)
    assert tokens["input_tokens"] == math.ceil(len(longest) / 4)
    assert tokens["worst_turn"] == 2 * PER_MESSAGE + tokens["input_tokens"] + 300
    assert tokens["truncated_at"] == []
    expected = math.floor((8192 - 200 - tokens["worst_prefix"]) / tokens["worst_turn"])
    assert tokens["k_fit_worst"] == expected
    assert [p["k"] for p in tokens["sweep"]] == list(range(0, 33, 4))


def test_token_phase_flags_a_truncated_prompt(tmp_path: Path) -> None:
    summary, _ = _run(tmp_path, [MODEL], cap=6000, phases=("tokens",))
    assert summary["models"][0]["tokens"]["truncated_at"]


def test_narration_phase_reports_lengths(tmp_path: Path) -> None:
    summary, calls = _run(tmp_path, [MODEL], phases=("narration",), seeds=2)
    narration = summary["models"][0]["narration"]
    assert narration["n"] == 16 and narration["errors"] == 0
    assert narration["tokens_mean"] == NARRATION_TOKENS and narration["at_cap"] == 0
    # warm-up plus 8 probes x 2 seeds
    assert len(calls) == 1 + 16
    assert {c["options"]["seed"] for c in calls[1:]} == {0, 1}


def test_full_run_tests_k_fit_for_accuracy(tmp_path: Path) -> None:
    summary, _ = _run(tmp_path, [MODEL])
    result = summary["models"][0]
    k_fit = result["tokens"]["k_fit_worst"]
    rows = result["accuracy"]["rows"]

    assert [r["k"] for r in rows] == sorted({0, 8, 16, k_fit})
    assert all(r["n"] == 20 and r["tool_match_rate"] == 1.0 for r in rows)
    assert result["accuracy"]["largest_stable_k"] == k_fit
    for suffix in ("narration", "tokens", "accuracy"):
        assert (tmp_path / f"fake-model_1b.{suffix}.jsonl").is_file()
    saved = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert saved["budget"]["context_tokens"] == 8192


def test_accuracy_sweep_sends_history(tmp_path: Path) -> None:
    _, calls = _run(tmp_path, [MODEL], phases=("accuracy",), ks=(4,), fmt="json")
    toolcalls = calls[1:]
    assert len(toolcalls) == 2 * 20
    assert {len(c["messages"]) for c in toolcalls} == {2, 2 + 2 * 4}
    assert all(c["format"] == "json" for c in toolcalls)
    assert (tmp_path / "fake-model_1b.accuracy-json.jsonl").is_file()


def test_missing_model_is_skipped(tmp_path: Path) -> None:
    summary, _ = _run(tmp_path, ["absent:7b", MODEL], phases=("tokens",))
    absent, present = summary["models"]
    assert "not installed" in absent["error"]
    assert present["tokens"]["k_fit_worst"] >= 0


# --- the transcript history format ---


def test_transcript_puts_the_last_k_turns_in_the_system_prompt() -> None:
    turns = HISTORY["turns"]
    messages = context.toolcall_messages(CEILING, "S.", turns, 2, "now", "transcript")
    assert [m["role"] for m in messages] == ["system", "user"]
    system = messages[0]["content"]
    first = f"Player: {turns[-2]['player_input']}\nDM: {turns[-2]['narration']}"
    assert first in system
    assert system.index(first) < system.index(turns[-1]["narration"])
    assert turns[-3]["narration"] not in system
    positions = [
        system.index("<summary>"),
        system.index("<history>"),
        system.index("Decide the single game action"),
    ]
    assert positions == sorted(positions)


def test_transcript_at_k_zero_has_no_history_block() -> None:
    messages = context.toolcall_messages(CEILING, None, HISTORY["turns"], 0, "now", "transcript")
    assert "<history>" not in messages[0]["content"]


def test_accuracy_request_at_k_zero_is_the_same_in_both_formats() -> None:
    case = toolcall.load_cases()[3]
    kwargs: Doc = {"thinking": False, "fmt": None}
    transcript = context.accuracy_request(
        "m", case, HISTORY, 0, history_format="transcript", **kwargs
    )
    assert transcript == context.accuracy_request("m", case, HISTORY, 0, **kwargs)


def test_unknown_history_format_is_refused() -> None:
    with pytest.raises(ValueError):
        context.toolcall_messages(CEILING, None, HISTORY["turns"], 1, "now", "xml")


def test_transcript_run_measures_a_heading_and_sends_two_messages(tmp_path: Path) -> None:
    summary, calls = _run(
        tmp_path, [MODEL], phases=("tokens", "accuracy"), history_format="transcript"
    )
    tokens = summary["models"][0]["tokens"]
    assert tokens["history_heading"] > 0
    assert tokens["truncated_at"] == []
    assert {len(c["messages"]) for c in calls[1:]} == {2}
    assert (tmp_path / "fake-model_1b.tokens-transcript.jsonl").is_file()
    assert (tmp_path / "fake-model_1b.accuracy-transcript.jsonl").is_file()
