"""Prompt templates v1.0 (WBS 7.5): every file in config/prompts/ matches the hash in
docs/prompt_templates.md section 1, and the condition templates differ exactly as its
section 2 says.

A failure here means a frozen template changed. That needs a docs/decisions.md entry
and the new hash in docs/prompt_templates.md, in the same pull request.

No test calls a model.

Run: pytest tests/orchestration/test_prompt_freeze.py -v
"""

import hashlib
import re
from pathlib import Path

import pytest

from adm.orchestration import prompt

ROOT = Path(__file__).resolve().parents[2]
FREEZE_DOC = ROOT / "docs" / "prompt_templates.md"

# A section 1 row: | `name.txt` | role | placeholders | `sha256:<hex>` |
_ROW = re.compile(r"^\| `([a-z_]+\.txt)` \|.*\| `sha256:([0-9a-f]{64})` \|$", re.MULTILINE)

# The condition-specific paragraphs of section 2, verbatim.
STATE = [
    "The authoritative game state is given below as JSON. It is correct.\n"
    "Your narration must be consistent with it.",
    "<state>\n{state_json}\n</state>",
]
TOOLS = [
    "The tools you can call are defined below as JSON.",
    "<tools>\n{tools_json}\n</tools>",
]
INSTRUCTION = [
    "Decide the single game action that the player's input represents.\n"
    "Reply with one JSON object and nothing else:\n"
    '{"tool": "<tool name>", "arguments": { ... }}\n'
    "If the input is pure conversation with no mechanical effect, reply\n"
    'with exactly: {"tool": null}',
]
FACTS = [
    "The rules engine has resolved the action. These facts are authoritative\n"
    "and complete. Narrate them. Do not add mechanical outcomes that are not\n"
    "listed, and do not contradict any value here.",
    "<facts>\n{narration_facts_json}\n</facts>",
]
SHARED_TAIL = ["{summary}", "{history}"]

TEXTS = prompt.load_templates()


def _frozen() -> dict[str, str]:
    return dict(_ROW.findall(FREEZE_DOC.read_text(encoding="utf-8")))


def _sha256(path: Path) -> str:
    """The hash of the file's text with LF line endings, as committed."""
    return hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()


def _paragraphs(name: str) -> list[str]:
    return TEXTS[name].split("\n\n")


# --- the freeze record ---


def test_every_prompt_file_is_in_the_freeze_record() -> None:
    on_disk = {p.name for p in prompt.PROMPTS_DIR.glob("*.txt")}
    assert set(_frozen()) == on_disk, (
        "config/prompts/ and docs/prompt_templates.md section 1 list different files"
    )


def test_every_loaded_template_is_frozen() -> None:
    loaded = {f"{name}.txt" for name in [*prompt.TEMPLATES, *prompt.BLOCKS, *prompt.RETRIES]}
    assert loaded == set(_frozen())


@pytest.mark.parametrize("name", sorted(_frozen()))
def test_template_matches_its_frozen_hash(name: str) -> None:
    assert _sha256(prompt.PROMPTS_DIR / name) == _frozen()[name], (
        f"config/prompts/{name} differs from the frozen text. A change needs a "
        "docs/decisions.md entry and the new hash in docs/prompt_templates.md section 1."
    )


def test_hash_ignores_crlf_checkouts(tmp_path: Path) -> None:
    text = (prompt.PROMPTS_DIR / "a.txt").read_text(encoding="utf-8")
    crlf = tmp_path / "a.txt"
    crlf.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
    assert _sha256(crlf) == _frozen()["a.txt"]


# --- the line-by-line differences (section 2) ---


def test_every_condition_template_shares_preamble_summary_and_history() -> None:
    preamble = _paragraphs("a")[0]
    assert len(preamble.splitlines()) == 6
    for name in ("a", "b", "c", "d_toolcall", "d_narration"):
        paragraphs = _paragraphs(name)
        assert paragraphs[0] == preamble
        at = paragraphs.index("{summary}")
        assert paragraphs[at : at + 2] == SHARED_TAIL


def test_a_is_the_preamble_summary_and_history() -> None:
    assert _paragraphs("a") == [_paragraphs("a")[0], *SHARED_TAIL]


def test_b_is_a_plus_the_state_block() -> None:
    a = _paragraphs("a")
    assert _paragraphs("b") == [a[0], *STATE, *a[1:]]


def test_d_toolcall_is_b_plus_tools_and_instruction() -> None:
    b = _paragraphs("b")
    assert _paragraphs("d_toolcall") == [*b[:3], *TOOLS, *b[3:], *INSTRUCTION]


def test_d_narration_is_a_plus_the_facts_block() -> None:
    assert _paragraphs("d_narration") == [*_paragraphs("a"), *FACTS]


@pytest.mark.parametrize(
    ("name", "lines"), [("a", 10), ("b", 17), ("c", 22), ("d_toolcall", 29), ("d_narration", 18)]
)
def test_line_counts_match_the_freeze_record(name: str, lines: int) -> None:
    assert len(TEXTS[name].splitlines()) == lines
