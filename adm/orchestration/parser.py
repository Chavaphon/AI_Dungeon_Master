"""Model output to proposed tool call (WBS 6.3, CLAUDE.md sections 7 and 7.1).

The tool-call reply of condition D is plain text: no grammar and no JSON mode
(CLAUDE.md section 15, item 26). This module turns that text into a *proposed*
tool call, or into a parse failure, and nothing else (invariant 6). It never
reads state and never checks the tool contract: an unknown tool, a missing
argument or the string `"null"` in place of `null` is a parsed call that the
validator rejects with `SCHEMA_VIOLATION` (docs/tool_contract.md section 1).

Recovery is deliberately small (docs/decisions.md, WBS 6.3 entry). The call is
taken from a code fence or from prose around it, and three repairs that cannot
change what the model meant are made: trailing commas, Python's `None`, `True`
and `False`, and closing brackets missing at the end of a cut-off reply. Text
inside JSON strings is never edited. Every repair is listed on the result, so
that the parser does not hide the failures M2 counts.

A failure is a value, not an exception (docs/conventions.md section 3). Its
`message` is the one logged in the audit record (docs/audit_log.md); the retry
prompt sent back to the model belongs to the failure pipeline (WBS 6.4).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Literal

Doc = dict[str, Any]
FailureReason = Literal["no_json", "no_tool_key"]

EXPECTED_FORMAT = 'Expected one JSON object of the form {"tool": ..., "arguments": {...}}.'

# Repair tags, in the order they are reported.
REPAIRS = (
    "code_fence",
    "surrounding_text",
    "multiple_objects",
    "trailing_comma",
    "python_literal",
    "closed_truncation",
)

_FENCE = re.compile(r"```[A-Za-z]*[ \t]*\n?(.*?)```", re.DOTALL)
_PYTHON_LITERALS = {"None": "null", "True": "true", "False": "false"}
_CLOSERS = {"{": "}", "[": "]"}
_DECODER = json.JSONDecoder()


@dataclass(frozen=True)
class ParsedCall:
    """A proposed tool call, not yet validated. `call` always has a `tool` key."""

    call: Doc
    repairs: tuple[str, ...] = ()


@dataclass(frozen=True)
class ParseFailure:
    """The reply holds no JSON object with a `tool` key (`turn_failure: unparseable`)."""

    reason: FailureReason
    message: str = EXPECTED_FORMAT


def parse_tool_call(raw: str) -> ParsedCall | ParseFailure:
    """The first JSON object with a `tool` key in the reply, or why there is none."""
    repairs: set[str] = set()
    text = raw
    fenced = _FENCE.search(raw)
    if fenced:
        text = fenced.group(1)
        repairs.add("code_fence")

    found, saw_object = _first_call(text)
    if found is None:
        found, saw_repaired = _first_call(text, repair=True)
        saw_object = saw_object or saw_repaired
    if found is None:
        return ParseFailure("no_tool_key" if saw_object else "no_json")

    call, start, rest, fixed = found
    repairs |= fixed
    if text[:start].strip() or rest.strip():
        repairs.add("surrounding_text")
    if _first_call(rest)[0] is not None:
        repairs.add("multiple_objects")
    return ParsedCall(call=call, repairs=tuple(r for r in REPAIRS if r in repairs))


# --- extraction --------------------------------------------------------------

_Found = tuple[Doc, int, str, set[str]]


def _first_call(text: str, *, repair: bool = False) -> tuple[_Found | None, bool]:
    """The first object with a `tool` key, trying each `{` in turn.

    Without `repair`, objects are decoded as written; with it, only objects
    that needed a safe repair are tried. Returns the call, where it starts, the
    text after it and the repairs made, or None; and whether any object
    without a `tool` key was decoded on the way.
    """
    saw_object = False
    for match in re.finditer(r"\{", text):
        candidate, fixed = text[match.start() :], set()
        if repair:
            repaired = _repair(candidate)
            if repaired is None:
                continue
            candidate, fixed = repaired
        try:
            parsed, end = _DECODER.raw_decode(candidate)
        except ValueError:
            continue
        if isinstance(parsed, dict):
            if "tool" in parsed:
                return (parsed, match.start(), candidate[end:], fixed), saw_object
            saw_object = True
    return None, saw_object


# --- repair ------------------------------------------------------------------


def _repair(text: str) -> tuple[str, set[str]] | None:
    """Make the safe repairs to the object that `text` opens with.

    Scans to the bracket that closes the opening `{` and leaves the text after
    it untouched. Returns None if nothing was repaired, or if the text ends
    inside a string: closing that string would invent content.
    """
    out: list[str] = []
    stack: list[str] = []
    fixed: set[str] = set()
    in_string = escaped = False
    i = 0
    while i < len(text):
        c = text[i]
        if in_string:
            out.append(c)
            if escaped:
                escaped = False
            elif c == "\\":
                escaped = True
            elif c == '"':
                in_string = False
        elif c == '"':
            in_string = True
            out.append(c)
        elif c in _CLOSERS:
            stack.append(_CLOSERS[c])
            out.append(c)
        elif c in "}]":
            out.append(c)
            if stack and stack[-1] == c:
                stack.pop()
                if not stack:
                    return ("".join(out) + text[i + 1 :], fixed) if fixed else None
        elif c == "," and text[i + 1 :].lstrip()[:1] in ("}", "]"):
            fixed.add("trailing_comma")
        elif literal := _python_literal(text, i):
            out.append(_PYTHON_LITERALS[literal])
            fixed.add("python_literal")
            i += len(literal)
            continue
        else:
            out.append(c)
        i += 1

    if in_string:
        return None
    body = "".join(out).rstrip()
    if body.endswith(","):
        body = body[:-1]
        fixed.add("trailing_comma")
    fixed.add("closed_truncation")
    return body + "".join(reversed(stack)), fixed


def _python_literal(text: str, i: int) -> str | None:
    """The Python literal starting at `text[i]` as a whole word, if any."""
    for literal in _PYTHON_LITERALS:
        end = i + len(literal)
        if (
            text.startswith(literal, i)
            and not (i > 0 and _is_word(text[i - 1]))
            and not (end < len(text) and _is_word(text[end]))
        ):
            return literal
    return None


def _is_word(c: str) -> bool:
    return c.isalnum() or c == "_"
