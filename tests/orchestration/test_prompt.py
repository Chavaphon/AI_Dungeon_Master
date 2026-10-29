"""Context assembly (WBS 6.2): the templates hold the CLAUDE.md section 9.1 text,
blocks come in the section 8 order, the history is a transcript and never chat
turns, K is reduced from the oldest turn, and the worst-case prompt fits the
context window at K = 8 (the done-when of #58 and the risk R3 trigger).

No test calls a model.

Run: pytest tests/orchestration/test_prompt.py -v
"""

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

from adm.bench import context as bench
from adm.engine.state import GameState
from adm.orchestration import prompt
from adm.orchestration.client import load_model_config
from adm.orchestration.prompt import HistoryTurn, PromptTooLarge, assemble

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "schemas" / "examples"

Doc = dict[str, Any]

# Verbatim from CLAUDE.md section 9.1.
PREAMBLE = """\
You are the Dungeon Master for a text-based fantasy role-playing game.
Narrate in the second person, present tense. Keep each reply to 2-4 sentences.
Describe only what the player character could perceive.
Do not speak or act for the player character.
Do not use headings, lists, or dice notation in narration."""

STATE_HEAD = """\
The authoritative game state is given below as JSON. It is correct.
Your narration must be consistent with it.

<state>"""

SELF_CHECK = """\
Before you reply, check your narration against the state above:
every item you mention must be in the inventory, every character must
appear in the state, and any description of health must match the
recorded hit points. Revise silently, then give only the final narration."""

TOOLCALL_INSTRUCTION = """\
Decide the single game action that the player's input represents.
Reply with one JSON object and nothing else:
{"tool": "<tool name>", "arguments": { ... }}
If the input is pure conversation with no mechanical effect, reply
with exactly: {"tool": null}"""

NARRATION_HEAD = """\
The rules engine has resolved the action. These facts are authoritative
and complete. Narrate them. Do not add mechanical outcomes that are not
listed, and do not contradict any value here.

<facts>"""

TOOLS_HEAD = "The tools you can call are defined below as JSON."
SUMMARY_HEAD = "Summary of earlier turns:"
HISTORY_HEAD = "The most recent turns of the game, oldest first:"

# 3.5 run 20261005T054107Z, llama3.1:8b, D tool-call prompt with the ceiling state,
# the fixture summary, the longest input and K transcript turns: K -> prompt_eval_count.
RECORDED_LLAMA_SWEEP = {
    0: 4428,
    4: 4725,
    8: 5002,
    12: 5268,
    16: 5548,
    20: 5846,
    24: 6151,
    28: 6442,
    32: 6727,
}

# A narration at the 300-token cap. The 3.5 fixture turns ran 4.34 characters per
# token, so 4.4 per token is longer than any 300-token narration of that prose.
CAP_NARRATION_CHARS = 1320

TEXTS = prompt.load_templates()
CONFIG = load_model_config()
CEILING = GameState.from_dict(bench.load_ceiling_state())
HISTORY = bench.load_history()
TURNS = [HistoryTurn(t["player_input"], t["narration"]) for t in HISTORY["turns"]]
FACTS = [json.loads((EXAMPLES / "result_attack.json").read_text("utf-8"))["narration_facts"]]
STATE = GameState.from_dict(json.loads((EXAMPLES / "state_02_mid_combat.json").read_text("utf-8")))
CONDITION_TEMPLATES = ("a", "b", "c", "d_toolcall")


def _system(template: str, **overrides: Any) -> str:
    kwargs: Doc = {
        "player_input": "I swing at the rat.",
        "history": TURNS[:3],
        "summary": "You came down into the cellar.",
        "k": 8,
        "budget": 10**6,
        "state": STATE,
        "facts": FACTS,
    }
    kwargs.update(overrides)
    return assemble(TEXTS, template, **kwargs).messages[0]["content"]


def _contract_module() -> Any:
    """tests/test_tool_contract.py, loaded by path: it holds the reference derivation."""
    path = ROOT / "tests" / "test_tool_contract.py"
    spec = importlib.util.spec_from_file_location("_tool_contract_reference", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- templates ---


@pytest.mark.parametrize("name", [*CONDITION_TEMPLATES, "d_narration"])
def test_every_template_starts_with_the_shared_preamble(name: str) -> None:
    assert TEXTS[name].startswith(PREAMBLE + "\n\n")


@pytest.mark.parametrize("name", ["b", "c", "d_toolcall"])
def test_state_block_is_verbatim(name: str) -> None:
    assert STATE_HEAD + "\n{state_json}\n</state>" in TEXTS[name]


def test_a_and_d_narration_carry_no_state() -> None:
    assert "<state>" not in TEXTS["a"]
    assert "<state>" not in TEXTS["d_narration"]


def test_condition_blocks_are_verbatim() -> None:
    assert TEXTS["c"].endswith(SELF_CHECK)
    assert TEXTS["d_toolcall"].endswith(TOOLCALL_INSTRUCTION)
    assert TEXTS["d_narration"].endswith(NARRATION_HEAD + "\n{narration_facts_json}\n</facts>")


def test_b_and_c_differ_only_by_the_self_check() -> None:
    assert TEXTS["c"] == TEXTS["b"] + "\n\n" + SELF_CHECK


def test_a_template_with_a_wrong_placeholder_is_refused(tmp_path: Path) -> None:
    for name in [*prompt.TEMPLATES, *prompt.BLOCKS, *prompt.RETRIES]:
        text = (prompt.PROMPTS_DIR / f"{name}.txt").read_text(encoding="utf-8")
        (tmp_path / f"{name}.txt").write_text(text, encoding="utf-8")
    (tmp_path / "a.txt").write_text(PREAMBLE + "\n\n{state_json}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="a.txt"):
        prompt.load_templates(tmp_path)


def test_crlf_files_load_the_same_text(tmp_path: Path) -> None:
    for name in [*prompt.TEMPLATES, *prompt.BLOCKS, *prompt.RETRIES]:
        text = (prompt.PROMPTS_DIR / f"{name}.txt").read_text(encoding="utf-8")
        (tmp_path / f"{name}.txt").write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
    assert prompt.load_templates(tmp_path) == TEXTS


# --- order and content ---


def test_toolcall_prompt_follows_section_8_order() -> None:
    system = _system("d_toolcall")
    marks = [PREAMBLE, STATE_HEAD, TOOLS_HEAD, SUMMARY_HEAD, HISTORY_HEAD, TOOLCALL_INSTRUCTION]
    positions = [system.index(m) for m in marks]
    assert positions == sorted(positions)
    assert system.endswith(TOOLCALL_INSTRUCTION)


def test_self_check_prompt_puts_the_instruction_last() -> None:
    system = _system("c")
    marks = [PREAMBLE, STATE_HEAD, SUMMARY_HEAD, HISTORY_HEAD, SELF_CHECK]
    positions = [system.index(m) for m in marks]
    assert positions == sorted(positions)


def test_narration_prompt_carries_the_facts_as_an_array_and_no_state() -> None:
    system = _system("d_narration")
    assert prompt.facts_json(FACTS) in system
    assert system.endswith("</facts>")
    assert "<state>" not in system and "<tools>" not in system


def test_state_is_injected_as_sorted_json() -> None:
    expected = json.dumps(STATE.to_dict(), sort_keys=True, indent=2, ensure_ascii=False)
    assert prompt.state_json(STATE) == expected
    assert expected in _system("b")


def test_tool_definitions_match_the_contract_reference() -> None:
    assert prompt.tool_definitions() == _contract_module().model_tool_definitions()
    assert json.dumps(prompt.tool_definitions(), indent=2) in _system("d_toolcall")


def test_conditions_share_summary_and_history_byte_for_byte() -> None:
    """Invariant 7: the same inputs give the same shared blocks in every condition."""
    shared = _system("a")
    for name in CONDITION_TEMPLATES:
        system = _system(name)
        assert shared.removeprefix(PREAMBLE) in system
    assert "<state>" not in shared


def test_assembly_is_byte_identical_across_calls() -> None:
    assert _system("d_toolcall") == _system("d_toolcall")


def test_missing_state_or_facts_is_a_programming_error() -> None:
    with pytest.raises(ValueError, match="state"):
        _system("b", state=None)
    with pytest.raises(ValueError, match="facts"):
        _system("d_narration", facts=None)


# --- history ---


def test_history_is_the_last_k_turns_oldest_first_as_a_transcript() -> None:
    system = _system("a", history=TURNS[:5], k=3)
    expected = "\n\n".join(f"Player: {t.player_input}\nDM: {t.narration}" for t in TURNS[2:5])
    assert f"<history>\n{expected}\n</history>" in system
    assert TURNS[1].narration not in system


@pytest.mark.parametrize("name", list(prompt.TEMPLATES))
def test_messages_are_one_system_and_one_user_message(name: str) -> None:
    messages = assemble(
        TEXTS,
        name,
        player_input="I look around.",
        history=TURNS[:8],
        summary="Earlier things.",
        k=8,
        budget=10**6,
        state=STATE,
        facts=FACTS,
    ).messages
    assert [m["role"] for m in messages] == ["system", "user"]
    assert messages[1]["content"] == "I look around."


@pytest.mark.parametrize("name", list(prompt.TEMPLATES))
def test_empty_summary_and_history_leave_no_gap(name: str) -> None:
    system = _system(name, history=[], summary=None)
    assert "\n\n\n" not in system
    assert SUMMARY_HEAD not in system and HISTORY_HEAD not in system
    assert not system.endswith("\n")


def test_summary_without_history_and_history_without_summary() -> None:
    assert SUMMARY_HEAD in _system("a", history=[]) and HISTORY_HEAD not in _system("a", history=[])
    assert HISTORY_HEAD in _system("a", summary=None)
    assert SUMMARY_HEAD not in _system("a", summary=None)


# --- K reduction ---


def _by_turns(messages: Any) -> int:
    """A fake counter: one token per verbatim turn in the prompt."""
    return messages[0]["content"].count("\nDM: ")


def test_k_is_reduced_from_the_oldest_turn() -> None:
    result = assemble(
        TEXTS,
        "d_toolcall",
        player_input="I attack.",
        history=TURNS[:8],
        summary="Earlier things.",
        k=8,
        budget=5,
        state=STATE,
        count=_by_turns,
    )
    assert (result.k_used, result.k_reduced) == (5, True)
    system = result.messages[0]["content"]
    for kept in TURNS[3:8]:
        assert kept.narration in system
    for dropped in TURNS[:3]:
        assert dropped.narration not in system
    assert system.startswith(PREAMBLE) and system.endswith(TOOLCALL_INSTRUCTION)


def test_fewer_turns_than_k_is_not_a_reduction() -> None:
    result = assemble(
        TEXTS,
        "a",
        player_input=".",
        history=TURNS[:3],
        summary=None,
        k=8,
        budget=10**6,
    )
    assert (result.k_used, result.k_reduced) == (3, False)


def test_no_fit_even_at_k_zero_raises() -> None:
    with pytest.raises(PromptTooLarge):
        assemble(
            TEXTS,
            "d_toolcall",
            player_input=".",
            history=TURNS[:8],
            summary=None,
            k=8,
            budget=100,
            state=CEILING,
        )


def test_followups_come_after_the_input_and_are_counted() -> None:
    followups = (
        {"role": "assistant", "content": "I attack the rat."},
        {"role": "user", "content": TEXTS["retry_no_tool"]},
    )
    kwargs: Doc = {
        "player_input": "I attack.",
        "history": TURNS[:8],
        "summary": None,
        "k": 8,
        "state": STATE,
    }
    plain = assemble(TEXTS, "d_toolcall", budget=10**6, **kwargs)
    retry = assemble(TEXTS, "d_toolcall", budget=10**6, followups=followups, **kwargs)
    assert retry.messages == (*plain.messages, *followups)
    assert retry.estimated_tokens == prompt.estimate_tokens(retry.messages)
    budget = plain.estimated_tokens
    tight = assemble(TEXTS, "d_toolcall", budget=budget, followups=followups, **kwargs)
    assert tight.k_used < plain.k_used and tight.messages[1:] == retry.messages[1:]


def test_retry_feedback_fills_its_placeholders() -> None:
    unparseable = prompt.retry_feedback(TEXTS, "retry_unparseable", {"pc_id": "pc_lyra"})
    assert '"actor_id": "pc_lyra"' in unparseable and "{pc_id}" not in unparseable
    rejected = prompt.retry_feedback(TEXTS, "retry_rejected", {"rejection_json": "{}"})
    assert rejected.splitlines()[1] == "{}"
    assert prompt.retry_feedback(TEXTS, "retry_no_tool", {}) == TEXTS["retry_no_tool"]


def test_negative_k_is_refused() -> None:
    with pytest.raises(ValueError):
        _system("a", k=-1)


# --- budget ---


def test_budget_reserves_the_reply_cap_for_each_phase() -> None:
    assert prompt.prompt_budget(CONFIG, "toolcall") == 8192 - 200
    assert prompt.prompt_budget(CONFIG, "narration") == 8192 - 300


@pytest.mark.parametrize(("k", "recorded"), sorted(RECORDED_LLAMA_SWEEP.items()))
def test_estimate_never_undercounts_a_recorded_llama_prompt(k: int, recorded: int) -> None:
    messages = bench.toolcall_messages(
        bench.load_ceiling_state(),
        HISTORY["summary"],
        HISTORY["turns"],
        k,
        bench.longest_input(HISTORY),
        "transcript",
    )
    assert prompt.estimate_tokens(messages) >= recorded


@pytest.mark.parametrize(
    ("name", "phase"),
    [
        ("d_toolcall", "toolcall"),
        ("a", "narration"),
        ("b", "narration"),
        ("c", "narration"),
        ("d_narration", "narration"),
    ],
)
def test_worst_case_prompt_fits_at_frozen_k(name: str, phase: Any) -> None:
    """Ceiling state, a summary over its 200-token cap, K turns with every narration
    at its 300-token cap, and the longest input: no reduction is needed."""
    k = CONFIG.K_verbatim_turns
    worst_turns = [
        HistoryTurn(t.player_input, (t.narration * 10)[:CAP_NARRATION_CHARS]) for t in TURNS[-k:]
    ]
    facts = [
        json.loads((EXAMPLES / f"{n}.json").read_text("utf-8"))["narration_facts"]
        for n in ("result_attack", "result_cast_spell_fire_bolt", "result_attack")
    ]
    budget = prompt.prompt_budget(CONFIG, phase)
    result = assemble(
        TEXTS,
        name,
        player_input=bench.longest_input(HISTORY),
        history=worst_turns,
        summary=HISTORY["summary"],
        k=k,
        budget=budget,
        state=CEILING,
        facts=facts,
    )
    assert (result.k_used, result.k_reduced) == (k, False)
    assert result.estimated_tokens <= budget
