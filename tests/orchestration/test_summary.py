"""Rolling summary (WBS 6.7): regenerated after every K-th narrated turn, folding
the turns since the last one into the previous summary, bounded by the 200-token
cap and cut at a sentence when it hits it, and logged in the turn record's
shape (the done-when of #69).

No test calls a model: a fake client returns recorded replies.

Run: pytest tests/orchestration/test_summary.py -v
"""

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from adm.bench import context as bench
from adm.orchestration import prompt, summary
from adm.orchestration.client import (
    SUMMARY_MAX_TOKENS,
    SUMMARY_TEMPERATURE,
    Message,
    ModelReply,
    Phase,
    build_options,
    load_model_config,
)
from adm.orchestration.prompt import HistoryTurn, PromptTooLarge
from adm.orchestration.summary import cut_at_sentence, is_due, regenerate, summary_messages

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = ROOT / "schemas"

Doc = dict[str, Any]

TEXTS = prompt.load_templates()
CONFIG = load_model_config()
K = CONFIG.K_verbatim_turns
HISTORY = bench.load_history()
TURNS = [HistoryTurn(t["player_input"], t["narration"]) for t in HISTORY["turns"]]
PREVIOUS = HISTORY["summary"]
SEED = 12345

INTRO = "You keep the running record of a text-based fantasy role-playing game."
INSTRUCTION_START = "Write a new summary of the whole game so far"
SUMMARY_HEAD = "Summary of earlier turns:"
HISTORY_HEAD = "The most recent turns of the game, oldest first:"
PREAMBLE_START = "You are the Dungeon Master"


def _schema(name: str) -> Doc:
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


REGISTRY = Registry().with_resources(
    (s["$id"], Resource.from_contents(s))
    for s in (_schema(n) for n in ("audit.schema.json", "state.schema.json", "tools.schema.json"))
)
AUDIT_ID = _schema("audit.schema.json")["$id"]


def _validator(definition: str) -> Draft202012Validator:
    return Draft202012Validator({"$ref": f"{AUDIT_ID}#/$defs/{definition}"}, registry=REGISTRY)


class FakeClient:
    """Returns recorded replies in order and keeps every request."""

    def __init__(self, *replies: tuple[str, str]) -> None:
        self.replies = list(replies)
        self.calls: list[tuple[tuple[Message, ...], Phase, int]] = []

    def chat(self, messages: Sequence[Message], *, phase: Phase, seed: int) -> ModelReply:
        self.calls.append((tuple(messages), phase, seed))
        text, done_reason = self.replies.pop(0)
        return ModelReply(text, 2900, 120, 1800, done_reason, 0)


def _system(previous: str | None = PREVIOUS, turns: Sequence[HistoryTurn] = TURNS[:K]) -> str:
    messages = summary_messages(TEXTS, CONFIG, previous=previous, turns=turns)
    return messages[0]["content"]


# --- schedule ---


def test_due_after_every_kth_turn_and_never_at_zero() -> None:
    assert [n for n in range(0, 33) if is_due(n, K)] == [8, 16, 24, 32]


def test_a_50_turn_session_regenerates_at_least_five_times() -> None:
    # CLAUDE.md section 12: long scenarios need at least five regenerations.
    assert sum(is_due(n, K) for n in range(1, 51)) == 6


# --- prompt ---


def test_prompt_holds_the_previous_summary_every_turn_and_the_instruction_last() -> None:
    messages = summary_messages(TEXTS, CONFIG, previous=PREVIOUS, turns=TURNS[:K])
    system = messages[0]["content"]
    assert [m["role"] for m in messages] == ["system", "user"]
    assert messages[1]["content"] == summary.SUMMARY_REQUEST
    assert system.startswith(INTRO + "\n\n")
    assert f"{SUMMARY_HEAD}\n\n<summary>\n{PREVIOUS}\n</summary>" in system
    expected = prompt.history_transcript(TURNS[:K])
    assert f"{HISTORY_HEAD}\n\n<history>\n{expected}\n</history>" in system
    assert system.index(SUMMARY_HEAD) < system.index(HISTORY_HEAD) < system.index(INSTRUCTION_START)


def test_first_regeneration_has_no_summary_block_and_no_gap() -> None:
    system = _system(previous=None)
    assert SUMMARY_HEAD not in system
    assert "\n\n\n" not in system
    assert system.startswith(INTRO + "\n\n" + HISTORY_HEAD)


def test_prompt_has_no_state_and_no_narration_preamble() -> None:
    system = _system()
    assert "<state>" not in system and PREAMBLE_START not in system


def test_instruction_forbids_numeric_state() -> None:
    instruction = TEXTS["summary"].split("\n\n")[-1]
    for word in ("events", "unresolved threads", "numbers", "hit points", "spell slots"):
        assert word in instruction


def test_prompt_is_byte_identical_across_calls() -> None:
    assert _system() == _system()


def test_a_prompt_that_would_drop_a_turn_raises() -> None:
    full = prompt.estimate_tokens(summary_messages(TEXTS, CONFIG, previous=None, turns=TURNS[:K]))
    reply_cap = build_options(CONFIG, "summary", 0)["num_predict"]
    tight = CONFIG.model_copy(update={"context_tokens": full + reply_cap - 1})
    with pytest.raises(PromptTooLarge):
        summary_messages(TEXTS, tight, previous=None, turns=TURNS[:K])


# --- the call ---


def test_call_uses_the_summary_phase_and_the_run_seed() -> None:
    client = FakeClient(("Lyra entered the cellar.", "stop"))
    regenerate(client, CONFIG, TEXTS, previous=None, turns=TURNS[:K], seed=SEED)
    [(messages, phase, seed)] = client.calls
    assert phase == "summary" and seed == SEED
    assert messages == summary_messages(TEXTS, CONFIG, previous=None, turns=TURNS[:K])
    options = build_options(CONFIG, phase, seed)
    assert options["temperature"] == SUMMARY_TEMPERATURE == 0.0
    assert options["num_predict"] == SUMMARY_MAX_TOKENS == 200


def test_summary_rolls_forward() -> None:
    client = FakeClient(("First summary.", "stop"), ("Second summary.", "stop"))
    first = regenerate(client, CONFIG, TEXTS, previous=None, turns=TURNS[:K], seed=SEED)
    second = regenerate(
        client, CONFIG, TEXTS, previous=first.text, turns=TURNS[K : 2 * K], seed=SEED
    )
    later = client.calls[1][0][0]["content"]
    assert f"<summary>\n{first.text}\n</summary>" in later
    assert TURNS[K].narration in later and TURNS[2 * K - 1].narration in later
    assert TURNS[K - 1].narration not in later
    assert second.text == "Second summary."


# --- the cap ---


def test_a_reply_that_stops_is_kept_whole() -> None:
    client = FakeClient(("  Lyra found a key. Maren is silent  \n", "stop"))
    result = regenerate(client, CONFIG, TEXTS, previous=None, turns=TURNS[:K], seed=SEED)
    assert result.text == "Lyra found a key. Maren is silent"
    assert result.truncated is False


def test_a_reply_at_the_cap_is_cut_after_its_last_sentence() -> None:
    raw = "Lyra found a key. The smugglers fled! Was Maren with them? The Keeper sa"
    client = FakeClient((raw, "length"))
    result = regenerate(client, CONFIG, TEXTS, previous=None, turns=TURNS[:K], seed=SEED)
    assert result.text == "Lyra found a key. The smugglers fled! Was Maren with them?"
    assert result.truncated is True
    assert result.model_call()["raw_output"] == raw


@pytest.mark.parametrize(
    ("text", "cut"),
    [
        ('Hollis said "Thank you." Then he l', 'Hollis said "Thank you."'),
        ("She left (for good.) The ri", "She left (for good.)"),
        ("Unresolved: the ledger.", "Unresolved: the ledger."),
        ("The ledger is in the strongbox behind", "The ledger is in the strongbox behind"),
        ("A key marked 3.5 was fou", "A key marked 3.5 was fou"),
    ],
)
def test_cut_at_sentence(text: str, cut: str) -> None:
    assert cut_at_sentence(text) == cut


# --- the log ---


@pytest.mark.parametrize(("done_reason", "truncated"), [("stop", False), ("length", True)])
def test_regeneration_is_logged_in_the_turn_record_shape(done_reason: str, truncated: bool) -> None:
    client = FakeClient(("Lyra found a key. Th", done_reason))
    result = regenerate(client, CONFIG, TEXTS, previous=None, turns=TURNS[:K], seed=SEED)
    record, call = result.record(), result.model_call()
    _validator("summary").validate(record)
    _validator("model_call").validate(call)
    assert record == {"text": result.text, "truncated": truncated}
    assert call["phase"] == "summary" and call["attempt"] == 1
