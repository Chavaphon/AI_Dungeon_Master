"""Context budget and the choice of K (WBS 3.5).

K is the number of past turns kept verbatim in the prompt (CLAUDE.md section 8).
A verbatim turn is the player's input and the DM's narration, as a user and an
assistant message. It is the same in every condition (invariant 7), since A to C
have no tool calls to keep. The largest prompt is condition D's tool call: the
preamble, the state, the tool definitions, the summary, K turns and the input.

Three phases, each against every model given:

- `narration`: how long a narration reply really is. The draft d_narration
  prompt for each result example, at temperature 0.7 and the 300-token cap.
- `tokens`: prompt tokens for the D tool-call prompt with the worst-case state
  (context_ceiling_state.json), swept over K. From it: the per-turn template
  overhead, the summary and input cost, the largest K that fits the context
  with every narration at its cap (`k_fit_worst`), and any K where Ollama
  silently truncated the prompt.
- `accuracy`: the 20 tool-call cases of WBS 3.3 with the summary and K
  history turns prepended, scored as in 3.3, so that a K that fits can also be
  shown to still work.

Two history formats (`--history`). `messages` sends each past turn as a user
and an assistant chat message. `transcript` writes the past turns into a
<history> block of the system prompt, as "Player:" and "DM:" lines, so that
the only messages are the system prompt and the current input.

Prompts are drafts. The summary's place in the prompt is decided by WBS 6.2 and
the templates are frozen by WBS 7.5; nothing is written to config/prompts/.
Model tags come only from the command line (CLAUDE.md section 2.2).

Run: python -m adm.bench.context --model <tag> [--model <tag> ...]
"""

import json
import math
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

import httpx
import typer
from rich.console import Console
from rich.table import Table

from adm.bench.toolcall import (
    EXAMPLES,
    OPTIONS,
    PREAMBLE,
    STATE_BLOCK,
    TOOLCALL_INSTRUCTION,
    TOOLS_BLOCK,
    Doc,
    chat_body,
    load_cases,
    load_state,
    mean,
    p95,
    preflight,
    safe_name,
    score,
    summarise,
    tool_definitions,
)

CEILING_PATH = Path(__file__).with_name("context_ceiling_state.json")
HISTORY_PATH = Path(__file__).with_name("context_history.json")

# CLAUDE.md section 2.2.
CONTEXT_TOKENS: int = OPTIONS["num_ctx"]
TOOLCALL_MAX_TOKENS: int = OPTIONS["num_predict"]
NARRATION_MAX_TOKENS = 300
NARRATION_TEMPERATURE = 0.7
# CLAUDE.md section 8.1.
SUMMARY_MAX_TOKENS = 200

PHASES = ("narration", "tokens", "accuracy")
HISTORY_FORMATS = ("messages", "transcript")
DEFAULT_KS = (0, 8, 16)
NARRATION_SEEDS = 5
TOKEN_SWEEP_STEP = 4
MINIMAL_PAIRS = 16
# The K selection rule: no rate may fall more than one case in twenty below K = 0.
TOLERANCE = 0.05

# Stands in for a one-token message where only the template around it is measured.
FILLER = "."

# Draft: where the rolling summary sits is WBS 6.2's decision.
SUMMARY_BLOCK = """\
Summary of earlier turns:

<summary>
{summary}
</summary>"""

# Draft, for the transcript format: the last K turns, after the summary (section 8).
HISTORY_BLOCK = """\
The most recent turns of the game, oldest first:

<history>
{transcript}
</history>"""

# Verbatim from CLAUDE.md section 9.1 (c.txt and d_narration.txt).
SELF_CHECK_BLOCK = """\
Before you reply, check your narration against the state above:
every item you mention must be in the inventory, every character must
appear in the state, and any description of health must match the
recorded hit points. Revise silently, then give only the final narration."""

NARRATION_BLOCK = """\
The rules engine has resolved the action. These facts are authoritative
and complete. Narrate them. Do not add mechanical outcomes that are not
listed, and do not contradict any value here.

<facts>
{narration_facts_json}
</facts>"""


# --- fixtures ---


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_ceiling_state() -> Doc:
    return _load_json(CEILING_PATH)


def load_history() -> Doc:
    return _load_json(HISTORY_PATH)


def load_result(name: str) -> Doc:
    return _load_json(EXAMPLES / f"{name}.json")


def longest_input(history: Doc) -> str:
    """The longest player input among the history turns and the 3.3 cases."""
    inputs = [t["player_input"] for t in history["turns"]] + [c["input"] for c in load_cases()]
    return max(inputs, key=len)


# --- prompts ---


def _state_json(state: Doc) -> str:
    return json.dumps(state, indent=2, ensure_ascii=False)


def toolcall_system_prompt(state: Doc, summary: str | None, history: str | None = None) -> str:
    """Condition D, call 1: preamble, state, tools, summary, history, instruction."""
    parts = [
        PREAMBLE,
        STATE_BLOCK.format(state_json=_state_json(state)),
        TOOLS_BLOCK.format(tools_json=json.dumps(tool_definitions(), indent=2)),
    ]
    if summary is not None:
        parts.append(SUMMARY_BLOCK.format(summary=summary))
    if history is not None:
        parts.append(HISTORY_BLOCK.format(transcript=history))
    parts.append(TOOLCALL_INSTRUCTION)
    return "\n\n".join(parts)


def self_check_system_prompt(state: Doc, summary: str | None) -> str:
    """Condition C, the largest of the narration-only prompts."""
    parts = [PREAMBLE, STATE_BLOCK.format(state_json=_state_json(state)), SELF_CHECK_BLOCK]
    if summary is not None:
        parts.append(SUMMARY_BLOCK.format(summary=summary))
    return "\n\n".join(parts)


def narration_system_prompt(facts: list[Doc]) -> str:
    """Condition D, call 2. The facts are a JSON array (CLAUDE.md section 9.1)."""
    facts_json = json.dumps(facts, indent=2, ensure_ascii=False)
    return "\n\n".join([PREAMBLE, NARRATION_BLOCK.format(narration_facts_json=facts_json)])


def _last(turns: list[Doc], k: int) -> list[Doc]:
    if not 0 <= k <= len(turns):
        raise ValueError(f"k={k} is outside 0..{len(turns)}")
    return turns[len(turns) - k :]


def history_messages(turns: list[Doc], k: int) -> list[Doc]:
    """The last k turns, oldest first, each as a user and an assistant message."""
    messages: list[Doc] = []
    for turn in _last(turns, k):
        messages.append({"role": "user", "content": turn["player_input"]})
        messages.append({"role": "assistant", "content": turn["narration"]})
    return messages


def build_messages(system: str, turns: list[Doc], k: int, player_input: str) -> list[Doc]:
    """CLAUDE.md section 8 order: system prompt, last k turns, current input."""
    return [
        {"role": "system", "content": system},
        *history_messages(turns, k),
        {"role": "user", "content": player_input},
    ]


def history_transcript(turns: list[Doc], k: int) -> str:
    """The last k turns, oldest first, as "Player:" and "DM:" lines."""
    return "\n\n".join(
        f"Player: {t['player_input']}\nDM: {t['narration']}" for t in _last(turns, k)
    )


def toolcall_messages(
    state: Doc,
    summary: str | None,
    turns: list[Doc],
    k: int,
    player_input: str,
    history_format: str,
) -> list[Doc]:
    """The D tool-call prompt with k past turns in the given history format."""
    if history_format == "transcript":
        history = history_transcript(turns, k) if k else None
        system = toolcall_system_prompt(state, summary, history)
        return build_messages(system, [], 0, player_input)
    if history_format != "messages":
        raise ValueError(f"unknown history format {history_format!r}")
    return build_messages(toolcall_system_prompt(state, summary), turns, k, player_input)


def token_count_options() -> Doc:
    return {**OPTIONS, "num_predict": 1}


def narration_options(seed: int) -> Doc:
    return {
        **OPTIONS,
        "num_predict": NARRATION_MAX_TOKENS,
        "temperature": NARRATION_TEMPERATURE,
        "seed": seed,
    }


# --- arithmetic ---


def fit_line(xs: list[float], ys: list[float]) -> tuple[float, float]:
    """Least-squares intercept and slope."""
    if len(xs) < 2:
        raise ValueError("need at least two points")
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / sxx
    return my - slope * mx, slope


def truncated_at(ks: list[int], counts: list[int]) -> list[int]:
    """Each K whose prompt did not grow over the K before it: Ollama cut the prompt."""
    return [k for k, prev, now in zip(ks[1:], counts, counts[1:], strict=False) if now <= prev]


def k_fit(prefix_tokens: float, turn_tokens: float, *, reply_tokens: int) -> int:
    """The largest K with prefix + K turns + reply inside the context window."""
    free = CONTEXT_TOKENS - reply_tokens - prefix_tokens
    if turn_tokens <= 0 or free <= 0:
        return 0
    return math.floor(free / turn_tokens)


def largest_stable_k(rows: list[Doc], limit: int, tolerance: float = TOLERANCE) -> int | None:
    """The largest tested K <= limit whose schema-valid and tool-match rates are no
    more than `tolerance` below the K = 0 rates. None without a K = 0 row."""
    base = next((r for r in rows if r["k"] == 0), None)
    if base is None:
        return None
    stable = [
        r["k"]
        for r in rows
        if r["k"] <= limit
        and all(
            r[key] is not None and r[key] >= base[key] - tolerance - 1e-9
            for key in ("schema_valid_rate", "tool_match_rate")
        )
    ]
    return max(stable) if stable else None


# --- requests ---


def _chat(client: httpx.Client, body: Doc) -> tuple[Doc, float]:
    started = time.perf_counter()
    response = client.post("/api/chat", json=body)
    response.raise_for_status()
    return response.json(), time.perf_counter() - started


def _prompt_tokens(client: httpx.Client, model: str, messages: list[Doc], *, thinking: bool) -> int:
    body = chat_body(model, messages, thinking=thinking, fmt=None, options=token_count_options())
    reply, _ = _chat(client, body)
    return int(reply["prompt_eval_count"])


def _tag(history_format: str, fmt: str | None = None) -> str:
    """File suffix: nothing for the messages format in prompt mode."""
    parts = [p for p in (history_format if history_format != "messages" else None, fmt) if p]
    return "".join(f"-{p}" for p in parts)


def _write_jsonl(path: Path, records: list[Doc]) -> None:
    with path.open("w", encoding="utf-8") as sink:
        for record in records:
            sink.write(json.dumps(record, ensure_ascii=False) + "\n")


# --- phase 1: narration length ---


def measure_narration(
    client: httpx.Client,
    model: str,
    meta: Doc,
    history: Doc,
    *,
    seeds: int,
    out_dir: Path,
    log: Any = None,
) -> Doc:
    records = []
    for probe in history["narration_probes"]:
        facts = [load_result(probe["result"])["narration_facts"]]
        messages = [
            {"role": "system", "content": narration_system_prompt(facts)},
            {"role": "user", "content": probe["player_input"]},
        ]
        for seed in range(seeds):
            body = chat_body(
                model,
                messages,
                thinking=meta["thinking"],
                fmt=None,
                options=narration_options(seed),
            )
            record: Doc = {"probe": probe["result"], "seed": seed, "error": None}
            try:
                reply, wall = _chat(client, body)
                record.update(
                    raw_output=reply["message"]["content"],
                    eval_count=reply.get("eval_count"),
                    done_reason=reply.get("done_reason"),
                    wall_s=wall,
                )
            except (httpx.HTTPError, ValueError, KeyError) as exc:
                record["error"] = f"{type(exc).__name__}: {exc}"
            records.append(record)
            if log:
                log(f"{model} narration {probe['result']} s{seed}: {record.get('eval_count')}")
    _write_jsonl(out_dir / f"{safe_name(model)}.narration.jsonl", records)

    lengths = [float(r["eval_count"]) for r in records if r.get("eval_count")]
    at_cap = [
        r
        for r in records
        if r.get("done_reason") == "length" or (r.get("eval_count") or 0) >= NARRATION_MAX_TOKENS
    ]
    return {
        "n": len(records),
        "errors": sum(1 for r in records if r["error"]),
        "tokens_mean": mean(lengths),
        "tokens_p95": p95(lengths),
        "tokens_max": max(lengths) if lengths else None,
        "at_cap": len(at_cap),
    }


# --- phase 2: token accounting ---


def measure_tokens(
    client: httpx.Client,
    model: str,
    meta: Doc,
    history: Doc,
    *,
    history_format: str = "messages",
    out_dir: Path,
    log: Any = None,
) -> Doc:
    ceiling = load_ceiling_state()
    turns, summary = history["turns"], history["summary"]
    longest = longest_input(history)
    minimal = [{"player_input": FILLER, "narration": FILLER}] * MINIMAL_PAIRS
    thinking = meta["thinking"]
    records: list[Doc] = []

    def count(
        probe: str, summary_text: str | None, pairs: list[Doc], k: int, player_input: str
    ) -> int:
        messages = toolcall_messages(ceiling, summary_text, pairs, k, player_input, history_format)
        tokens = _prompt_tokens(client, model, messages, thinking=thinking)
        records.append({"probe": probe, "k": k, "prompt_eval_count": tokens})
        if log:
            log(f"{model} tokens {probe} k={k}: {tokens}")
        return tokens

    path = out_dir / f"{safe_name(model)}.tokens{_tag(history_format)}.jsonl"
    try:
        base = count("base", None, [], 0, FILLER)
        with_summary = count("summary", summary, [], 0, FILLER)
        with_input = count("input", None, [], 0, longest)
        one_minimal = count("minimal_pairs", None, minimal, 1, FILLER)
        with_minimal = count("minimal_pairs", None, minimal, MINIMAL_PAIRS, FILLER)
        ks = list(range(0, len(turns) + 1, TOKEN_SWEEP_STEP))
        sweep = [count("sweep", summary, turns, k, longest) for k in ks]
        c_messages = build_messages(self_check_system_prompt(ceiling, summary), [], 0, longest)
        c_prefix = _prompt_tokens(client, model, c_messages, thinking=thinking)
        records.append({"probe": "condition_c", "k": 0, "prompt_eval_count": c_prefix})
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        _write_jsonl(path, records)
        return {"error": f"{type(exc).__name__}: {exc}"}
    _write_jsonl(path, records)

    summary_tokens = with_summary - base
    # The input replaces FILLER, itself about one token.
    input_tokens = with_input - base + 1
    # Each minimal pair is the template around two FILLER texts. The first pair also
    # pays for anything said once, such as the transcript's <history> heading.
    pair_overhead = (with_minimal - one_minimal) / (MINIMAL_PAIRS - 1) - 2
    history_heading = one_minimal - base - (pair_overhead + 2)
    worst_turn = math.ceil(pair_overhead + input_tokens + NARRATION_MAX_TOKENS)
    # The summary is budgeted at its cap, not at the fixture's length.
    worst_prefix = math.ceil(with_input + SUMMARY_MAX_TOKENS + history_heading)
    c_worst_prefix = c_prefix - summary_tokens + SUMMARY_MAX_TOKENS

    cut = truncated_at(ks, sweep)
    clean = [(k, n) for k, n in zip(ks, sweep, strict=True) if k not in cut]
    per_turn_typical = None
    if len(clean) >= 2:
        _, per_turn_typical = fit_line([float(k) for k, _ in clean], [float(n) for _, n in clean])

    return {
        "base_prefix": base,
        "summary_tokens": summary_tokens,
        "input_tokens": input_tokens,
        "pair_overhead": pair_overhead,
        "history_heading": history_heading,
        "per_turn_typical": per_turn_typical,
        "worst_turn": worst_turn,
        "worst_prefix": worst_prefix,
        "c_worst_prefix": c_worst_prefix,
        "sweep": [{"k": k, "prompt_tokens": n} for k, n in zip(ks, sweep, strict=True)],
        "truncated_at": cut,
        "k_fit_worst": k_fit(worst_prefix, worst_turn, reply_tokens=TOOLCALL_MAX_TOKENS),
        "k_fit_typical": None
        if per_turn_typical is None
        else k_fit(worst_prefix, math.ceil(per_turn_typical), reply_tokens=TOOLCALL_MAX_TOKENS),
        "k_fit_worst_condition_c": k_fit(
            c_worst_prefix, worst_turn, reply_tokens=NARRATION_MAX_TOKENS
        ),
    }


# --- phase 3: accuracy against K ---


def accuracy_request(
    model: str,
    case: Doc,
    history: Doc,
    k: int,
    *,
    thinking: bool,
    fmt: str | None,
    history_format: str = "messages",
) -> Doc:
    """K = 0 is the 3.3 prompt exactly, with no summary; K > 0 adds the summary too."""
    summary = history["summary"] if k else None
    state = load_state(case["state"])
    messages = toolcall_messages(state, summary, history["turns"], k, case["input"], history_format)
    return chat_body(model, messages, thinking=thinking, fmt=fmt)


def measure_accuracy(
    client: httpx.Client,
    model: str,
    meta: Doc,
    history: Doc,
    *,
    ks: list[int],
    fmt: str | None,
    history_format: str = "messages",
    out_dir: Path,
    log: Any = None,
) -> list[Doc]:
    rows, records = [], []
    for k in ks:
        at_k = []
        for case in load_cases():
            body = accuracy_request(
                model,
                case,
                history,
                k,
                thinking=meta["thinking"],
                fmt=fmt,
                history_format=history_format,
            )
            record: Doc = {"case_id": case["id"], "k": k, "format": fmt}
            record.update(raw_output=None, error=None)
            started = time.perf_counter()
            try:
                reply, _ = _chat(client, body)
                record["raw_output"] = reply["message"]["content"]
                for key in ("prompt_eval_count", "eval_count", "eval_duration"):
                    record[key] = reply.get(key)
            except (httpx.HTTPError, ValueError, KeyError) as exc:
                record["error"] = f"{type(exc).__name__}: {exc}"
            record["wall_s"] = time.perf_counter() - started
            record.update(score(record["raw_output"] or "", case["expected"], case["ignore_args"]))
            at_k.append(record)
            if log:
                mark = "ok" if record["tool_match"] else "x"
                log(f"{model} k={k} {case['id']}: {mark}")
        records.extend(at_k)
        row = summarise(model, {"k": k}, at_k)
        rows.append({key: value for key, value in row.items() if key != "model"})
    tag = _tag(history_format, fmt)
    _write_jsonl(out_dir / f"{safe_name(model)}.accuracy{tag}.jsonl", records)
    return rows


# --- the run ---


def run(
    models: list[str],
    *,
    client: httpx.Client,
    out_dir: Path,
    phases: tuple[str, ...] = PHASES,
    ks: tuple[int, ...] = DEFAULT_KS,
    fmt: str | None = None,
    history_format: str = "messages",
    seeds: int = NARRATION_SEEDS,
    log: Any = None,
) -> Doc:
    """Run the chosen phases on every model. Writes per-phase jsonl and summary.json."""
    out_dir.mkdir(parents=True, exist_ok=True)
    history = load_history()
    summary: Doc = {
        "started": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "phases": list(phases),
        "format": fmt,
        "history_format": history_format,
        "budget": {
            "context_tokens": CONTEXT_TOKENS,
            "toolcall_max_tokens": TOOLCALL_MAX_TOKENS,
            "narration_max_tokens": NARRATION_MAX_TOKENS,
            "summary_max_tokens": SUMMARY_MAX_TOKENS,
            "tolerance": TOLERANCE,
        },
        "history_turns": len(history["turns"]),
        "options": OPTIONS,
        "models": [],
    }

    for model in models:
        try:
            meta = preflight(client, model, fmt)
        except (LookupError, httpx.HTTPError, ValueError, KeyError) as exc:
            summary["models"].append({"model": model, "error": f"{type(exc).__name__}: {exc}"})
            if log:
                log(f"[red]skipped {model}: {exc}[/red]")
            continue
        if log and meta["gpu_share"] is not None and meta["gpu_share"] < 1.0:
            log(f"[yellow]{model} is only {meta['gpu_share']:.0%} on the GPU[/yellow]")
        result: Doc = {"model": model, **meta}
        common = {"out_dir": out_dir, "log": log}

        if "narration" in phases:
            result["narration"] = measure_narration(
                client, model, meta, history, seeds=seeds, **common
            )
        k_limit = len(history["turns"])
        if "tokens" in phases:
            result["tokens"] = measure_tokens(
                client, model, meta, history, history_format=history_format, **common
            )
            k_limit = min(k_limit, result["tokens"].get("k_fit_worst", k_limit))
        if "accuracy" in phases:
            tested = sorted({0, *ks, *([k_limit] if "tokens" in phases else [])})
            tested = [k for k in tested if k <= len(history["turns"])]
            rows = measure_accuracy(
                client,
                model,
                meta,
                history,
                ks=tested,
                fmt=fmt,
                history_format=history_format,
                **common,
            )
            result["accuracy"] = {
                "rows": rows,
                "k_limit": k_limit,
                "largest_stable_k": largest_stable_k(rows, k_limit),
            }
        summary["models"].append(result)

    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return summary


# --- command line ---


def _cell(value: Any, spec: str = "") -> str:
    if value is None:
        return "-"
    return format(value, spec) if spec else str(value)


def _tables(summary: Doc) -> list[Table]:
    narration = Table(title="Narration length (tokens, cap 300)")
    history_format = summary["history_format"]
    tokens = Table(title=f"Token budget, D tool-call prompt, ceiling state ({history_format})")
    accuracy = Table(
        title=f"Accuracy against K (format: {summary['format'] or 'prompt'}, {history_format})"
    )
    for column in ("model", "n", "err", "mean", "p95", "max", "at cap"):
        narration.add_column(column)
    for column in (
        "model",
        "prefix",
        "summary",
        "input",
        "pair ovh",
        "turn typ",
        "turn worst",
        "K fit worst",
        "K fit typ",
        "truncated",
    ):
        tokens.add_column(column)
    for column in ("model", "K", "n", "err", "schema-valid", "tool", "args", "mean s", "prompt"):
        accuracy.add_column(column)

    for m in summary["models"]:
        if "error" in m:
            narration.add_row(m["model"], "-", m["error"])
            continue
        if n := m.get("narration"):
            narration.add_row(
                m["model"],
                str(n["n"]),
                str(n["errors"]),
                _cell(n["tokens_mean"], ".0f"),
                _cell(n["tokens_p95"], ".0f"),
                _cell(n["tokens_max"], ".0f"),
                str(n["at_cap"]),
            )
        if t := m.get("tokens"):
            if "error" in t:
                tokens.add_row(m["model"], t["error"])
            else:
                tokens.add_row(
                    m["model"],
                    str(t["worst_prefix"]),
                    str(t["summary_tokens"]),
                    str(t["input_tokens"]),
                    _cell(t["pair_overhead"], ".1f"),
                    _cell(t["per_turn_typical"], ".1f"),
                    str(t["worst_turn"]),
                    str(t["k_fit_worst"]),
                    str(t["k_fit_typical"]),
                    str(t["truncated_at"] or "-"),
                )
        if a := m.get("accuracy"):
            for row in a["rows"]:
                accuracy.add_row(
                    m["model"],
                    str(row["k"]),
                    str(row["n"]),
                    str(row["errors"]),
                    _cell(row["schema_valid_rate"], ".0%"),
                    _cell(row["tool_match_rate"], ".0%"),
                    _cell(row["args_match_rate"], ".0%"),
                    _cell(row["latency_mean_s"], ".2f"),
                    _cell(row["prompt_tokens_mean"], ".0f"),
                )
    return [t for t in (narration, tokens, accuracy) if t.row_count]


def main(
    model: Annotated[list[str], typer.Option("--model", help="Ollama tag; repeat for more.")],
    phase: Annotated[
        list[str] | None, typer.Option("--phase", help="narration, tokens or accuracy; repeat.")
    ] = None,
    k: Annotated[
        list[int] | None, typer.Option("--k", min=0, help="K to test for accuracy; repeat.")
    ] = None,
    fmt: Annotated[
        str | None, typer.Option("--format", help="Send Ollama's format field, e.g. json.")
    ] = None,
    history_format: Annotated[
        str, typer.Option("--history", help="messages or transcript.")
    ] = "messages",
    seeds: Annotated[int, typer.Option(min=1)] = NARRATION_SEEDS,
    host: str = "http://localhost:11434",
    out: Path = Path("results/bench/context"),
    timeout: float = 300.0,
) -> None:
    """Measure the context budget and choose K (WBS 3.5) against local Ollama models."""
    if fmt not in (None, "json"):
        raise typer.BadParameter("only 'json' is supported", param_hint="--format")
    if history_format not in HISTORY_FORMATS:
        raise typer.BadParameter("messages or transcript", param_hint="--history")
    phases = tuple(phase) if phase else PHASES
    if unknown := set(phases) - set(PHASES):
        raise typer.BadParameter(f"unknown phase {sorted(unknown)}", param_hint="--phase")
    console = Console()
    out_dir = out / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    with httpx.Client(base_url=host, timeout=timeout) as client:
        summary = run(
            model,
            client=client,
            out_dir=out_dir,
            phases=phases,
            ks=tuple(k) if k else DEFAULT_KS,
            fmt=fmt,
            history_format=history_format,
            seeds=seeds,
            log=console.print,
        )
    for table in _tables(summary):
        console.print(table)
    console.print(f"Records and summary in {out_dir}")


if __name__ == "__main__":
    typer.run(main)
