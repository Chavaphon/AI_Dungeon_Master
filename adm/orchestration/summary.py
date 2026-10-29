"""Rolling summary (WBS 6.7, CLAUDE.md section 8.1).

The summary is regenerated after every K-th narrated turn by its own model call,
at temperature 0.0 with a 200-token cap (`client.build_options`). K is
`K_verbatim_turns`, never a turn's reduced `k_used`. A failed turn has no
narration, so it is not a turn here.

Each regeneration folds the K turns played since the last one into the
previous summary. Those turns are still in the verbatim window, so for up to K
turns a turn is in both. Nothing is ever in neither: a turn leaves the window
only after it is in the summary (docs/decisions.md, WBS 6.7).

The prompt is `config/prompts/summary.txt`, built by `prompt.assemble` with the
same summary and history blocks as every other call, and the same in every
condition (invariant 7). It holds no state, so the summary has no numbers to
restate. The summary must see every turn it folds in, so a prompt that would
need K reduced is a bug and raises.

A reply that hits the cap ends with `done_reason` "length". It is cut after its
last complete sentence and logged as `truncated`; the uncut reply stays in the
model call's `raw_output`. This module writes nothing to state (invariant 1).
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from adm.orchestration.client import Message, ModelClient, ModelConfig, ModelReply
from adm.orchestration.prompt import Doc, HistoryTurn, PromptTooLarge, assemble, prompt_budget

TEMPLATE = "summary"
# `assemble` always sends one user message; the instruction is in the template.
SUMMARY_REQUEST = "Write the summary."

# A sentence ends at . ! or ?, with any closing quotes or brackets, before a space or the end.
_SENTENCE_END = re.compile(r"[.!?][\"'”’)\]]*(?=\s|$)")


@dataclass(frozen=True)
class Summary:
    text: str
    truncated: bool
    reply: ModelReply

    def record(self) -> Doc:
        """The turn record's `summary` field (docs/audit_log.md section 1)."""
        return {"text": self.text, "truncated": self.truncated}

    def model_call(self) -> Doc:
        """The turn record's `model_calls` entry for the summary call."""
        return self.reply.model_call("summary", 1)


def is_due(turns_played: int, k: int) -> bool:
    """Whether the summary is regenerated after this many narrated turns."""
    return turns_played > 0 and turns_played % k == 0


def cut_at_sentence(text: str) -> str:
    """The text up to its last complete sentence, or all of it if it has none."""
    ends = list(_SENTENCE_END.finditer(text))
    return text[: ends[-1].end()] if ends else text


def summary_messages(
    texts: Mapping[str, str],
    config: ModelConfig,
    *,
    previous: str | None,
    turns: Sequence[HistoryTurn],
) -> tuple[Message, ...]:
    """The summary prompt: the previous summary and every turn since, oldest first."""
    assembled = assemble(
        texts,
        TEMPLATE,
        player_input=SUMMARY_REQUEST,
        history=turns,
        summary=previous,
        k=len(turns),
        budget=prompt_budget(config, "summary"),
    )
    if assembled.k_reduced:
        raise PromptTooLarge(
            f"the summary prompt fits only {assembled.k_used} of {len(turns)} turns"
        )
    return assembled.messages


def regenerate(
    client: ModelClient,
    config: ModelConfig,
    texts: Mapping[str, str],
    *,
    previous: str | None,
    turns: Sequence[HistoryTurn],
    seed: int,
) -> Summary:
    """The new summary of `previous` and `turns`, cut if the reply hit the cap."""
    messages = summary_messages(texts, config, previous=previous, turns=turns)
    reply = client.chat(messages, phase="summary", seed=seed)
    text = reply.raw_output.strip()
    truncated = reply.done_reason == "length"
    if truncated:
        text = cut_at_sentence(text)
    return Summary(text, truncated, reply)
