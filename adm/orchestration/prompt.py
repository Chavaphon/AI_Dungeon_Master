"""Context assembly (WBS 6.2, CLAUDE.md sections 8 and 9.1).

Every model call's prompt is built here from a template in `config/prompts/`.
The prompt is two messages and never more: a system message holding every
block, and a user message holding the current player input. The last K turns
are written into the system message as a `Player:` / `DM:` transcript, never
sent as `assistant` messages: with chat turns, every candidate model stopped
calling tools from K = 8 (docs/context_budget.md section 5).

Order (section 8): the template's fixed blocks (preamble, state, tools or
facts), then the rolling summary, then the last K turns, then the condition's
instruction, then the input. The condition lives only in the template: a
template uses the placeholders it contains and ignores the rest, so a caller
passes the same inputs in every condition (invariant 7) and nothing here
branches on A, B, C or D (docs/conventions.md section 1).

Placeholders are exact tokens replaced with `str.replace`, since the D
instruction holds literal braces. `{summary}` and `{history}` each fill a whole
paragraph, and the paragraph is dropped when there is nothing to put in it.
Files are read in universal-newline mode, so a CRLF checkout gives the same
prompt bytes as an LF one (invariant 4).

Tokens are estimated, not counted: there is no tokeniser offline, and asking
Ollama would add a model call that can change later replies
(docs/model_selection.md section 3). `estimate_tokens` is deterministic and
over-counts every prompt recorded in the 3.5 runs (docs/context_budget.md
section 9). If a prompt would not fit, the oldest turns are dropped one at a
time (section 8), and the turn record's `k_used` logs the reduction. The turn
loop assembles the turn's largest prompt first (the D tool call, or the single
A-C call) and passes its `k_used` to the turn's other calls, so a turn has one K.
"""

from __future__ import annotations

import copy
import json
import math
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from adm.engine.state import GameState
from adm.orchestration.client import Message, ModelConfig, Phase, build_options

ROOT = Path(__file__).resolve().parents[2]
PROMPTS_DIR = ROOT / "config" / "prompts"
TOOLS_SCHEMA_PATH = ROOT / "schemas" / "tools.schema.json"

Doc = dict[str, Any]

# The condition templates of CLAUDE.md section 9.1, the rolling summary's (section
# 8.1, the same in every condition), and the placeholders each holds.
TEMPLATES: dict[str, frozenset[str]] = {
    "a": frozenset({"summary", "history"}),
    "b": frozenset({"state_json", "summary", "history"}),
    "c": frozenset({"state_json", "summary", "history"}),
    "d_toolcall": frozenset({"state_json", "tools_json", "summary", "history"}),
    "d_narration": frozenset({"narration_facts_json", "summary", "history"}),
    "summary": frozenset({"summary", "history"}),
}
# The two blocks shared by every template.
BLOCKS: dict[str, frozenset[str]] = {
    "summary_block": frozenset({"summary_text"}),
    "history_block": frozenset({"transcript"}),
}

# Placeholders that fill a whole paragraph, dropped when empty.
_PARAGRAPH_SLOTS = {"{summary}": "summary", "{history}": "history"}
_PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")

# Calibrated on the frozen model's 3.5 sweep (docs/context_budget.md section 9): real
# prompts ran 3.61 to 3.87 characters per token, so 3.5 over-counts all of them.
CHARS_PER_TOKEN = 3.5
# The chat template's role header and end-of-turn tokens around each message.
MESSAGE_OVERHEAD = 5

TokenCounter = Callable[[Sequence[Message]], int]


class PromptTooLarge(Exception):
    """Even with no verbatim turns the prompt does not fit: the state is beyond the
    authoring ceiling (docs/decisions.md, WBS 3.5). A bug, never a turn failure."""


@dataclass(frozen=True)
class HistoryTurn:
    """One verbatim turn: the player's input and the DM's narration (context_budget §1.1)."""

    player_input: str
    narration: str


@dataclass(frozen=True)
class AssembledPrompt:
    messages: tuple[Message, ...]
    k_used: int
    k_reduced: bool
    estimated_tokens: int


# --- templates ---------------------------------------------------------------


def placeholders(text: str) -> set[str]:
    """Every `{name}` token in a template. The D instruction's JSON braces hold spaces
    or quotes, so they never match."""
    return set(_PLACEHOLDER.findall(text))


def load_templates(directory: Path = PROMPTS_DIR) -> dict[str, str]:
    """Every template and block, each checked to hold exactly its placeholders."""
    texts = {}
    for name, expected in {**TEMPLATES, **BLOCKS}.items():
        text = (directory / f"{name}.txt").read_text(encoding="utf-8").removesuffix("\n")
        if (found := placeholders(text)) != expected:
            raise ValueError(f"{name}.txt has placeholders {sorted(found)}, not {sorted(expected)}")
        texts[name] = text
    return texts


# --- blocks ------------------------------------------------------------------


def tool_definitions() -> list[Doc]:
    """The model-facing tool list, derived from args_* (docs/tool_contract.md section 5)."""
    schema = json.loads(TOOLS_SCHEMA_PATH.read_text(encoding="utf-8"))
    definitions = []
    for tool in schema["$defs"]["tool_name"]["enum"]:
        args = copy.deepcopy(schema["$defs"][f"args_{tool}"])
        description = args.pop("description")
        definitions.append({"name": tool, "description": description, "parameters": args})
    return definitions


def state_json(state: GameState) -> str:
    return json.dumps(state.to_dict(), sort_keys=True, indent=2, ensure_ascii=False)


@cache
def tools_json() -> str:
    return json.dumps(tool_definitions(), indent=2, ensure_ascii=False)


def facts_json(facts: Sequence[Doc]) -> str:
    """The facts of the player's call and each NPC action, in the order they happened
    (CLAUDE.md section 9.1)."""
    return json.dumps(list(facts), indent=2, ensure_ascii=False)


def history_transcript(turns: Sequence[HistoryTurn]) -> str:
    """The turns, oldest first, as "Player:" and "DM:" lines."""
    return "\n\n".join(f"Player: {t.player_input}\nDM: {t.narration}" for t in turns)


# --- tokens ------------------------------------------------------------------


def estimate_tokens(messages: Sequence[Message]) -> int:
    return sum(math.ceil(len(m["content"]) / CHARS_PER_TOKEN) + MESSAGE_OVERHEAD for m in messages)


def prompt_budget(config: ModelConfig, phase: Phase) -> int:
    """The context window less the reply's cap: Ollama's num_ctx holds both."""
    return config.context_tokens - build_options(config, phase, 0)["num_predict"]


# --- assembly ----------------------------------------------------------------


def _render(template: str, values: Mapping[str, str]) -> str:
    paragraphs = []
    for paragraph in template.split("\n\n"):
        if slot := _PARAGRAPH_SLOTS.get(paragraph):
            if values[slot]:
                paragraphs.append(values[slot])
            continue
        for name in placeholders(paragraph):
            paragraph = paragraph.replace(f"{{{name}}}", values[name])
        paragraphs.append(paragraph)
    return "\n\n".join(paragraphs)


def assemble(
    texts: Mapping[str, str],
    template: str,
    *,
    player_input: str,
    history: Sequence[HistoryTurn],
    summary: str | None,
    k: int,
    budget: int,
    state: GameState | None = None,
    facts: Sequence[Doc] | None = None,
    count: TokenCounter = estimate_tokens,
) -> AssembledPrompt:
    """The prompt with the largest K' <= k whose estimate fits `budget`.

    `history` is every verbatim turn the loop holds, oldest first; the last K'
    are used, so a reduction drops the oldest and never cuts the middle.
    """
    if k < 0:
        raise ValueError(f"k must be >= 0, got {k}")
    needed = placeholders(texts[template])
    values: dict[str, str] = {}
    if "state_json" in needed:
        if state is None:
            raise ValueError(f"{template} needs the state")
        values["state_json"] = state_json(state)
    if "tools_json" in needed:
        values["tools_json"] = tools_json()
    if "narration_facts_json" in needed:
        if facts is None:
            raise ValueError(f"{template} needs the narration facts")
        values["narration_facts_json"] = facts_json(facts)
    values["summary"] = texts["summary_block"].replace("{summary_text}", summary) if summary else ""

    k_max = min(k, len(history))
    for k_used in range(k_max, -1, -1):
        turns = history[len(history) - k_used :] if k_used else []
        values["history"] = (
            texts["history_block"].replace("{transcript}", history_transcript(turns))
            if turns
            else ""
        )
        messages = (
            {"role": "system", "content": _render(texts[template], values)},
            {"role": "user", "content": player_input},
        )
        tokens = count(messages)
        if tokens <= budget:
            return AssembledPrompt(messages, k_used, k_used < k_max, tokens)
    raise PromptTooLarge(
        f"{template} needs {tokens} tokens with no history; the budget is {budget}"
    )
