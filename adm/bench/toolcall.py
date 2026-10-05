"""Tool-calling micro-benchmark (WBS 3.3).

Sends the 20 cases in toolcall_cases.json to each candidate model through
Ollama's /api/chat and scores each reply. The prompt is the condition D
tool-call prompt of CLAUDE.md section 9.1. The primary score is
`schema_valid`: the raw reply parses as one JSON object, unchanged, and
validates against `proposed_call` in schemas/tools.schema.json. That is the
figure for the 80 per cent trigger of risk R1. The other scores are reported
alongside it:

- `schema_valid_lenient`: valid after stripping code fences and surrounding
  prose. It shows how much a recovering parser (WBS 6.3) would gain.
- `tool_match`, `args_match`: whether the lenient parse names the expected
  tool and arguments. Keys in a case's `ignore_args` are judgement calls (a
  DC, a justification) and are not compared.

Model tags come from the command line and appear nowhere in code
(CLAUDE.md section 2.2). `think: false` is sent to models whose /api/show
lists the `thinking` capability (docs/model_shortlist.md section 5).

Run: python -m adm.bench.toolcall --model <tag> [--model <tag> ...]
"""

import copy
import json
import math
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

import httpx
import typer
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from rich.console import Console
from rich.table import Table

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = ROOT / "schemas"
EXAMPLES = SCHEMAS / "examples"
CASES_PATH = Path(__file__).with_name("toolcall_cases.json")

Doc = dict[str, Any]

# Draft of config/prompts/d_toolcall.txt for WBS 3.3. The frozen copy is WBS 7.5.
# Preamble, state block and instruction are verbatim from CLAUDE.md section 9.1.
# The tool-definition block is not worded there; this wording is the draft.
PREAMBLE = """\
You are the Dungeon Master for a text-based fantasy role-playing game.
Narrate in the second person, present tense. Keep each reply to 2-4 sentences.
Describe only what the player character could perceive.
Do not speak or act for the player character.
Do not use headings, lists, or dice notation in narration."""

STATE_BLOCK = """\
The authoritative game state is given below as JSON. It is correct.
Your narration must be consistent with it.

<state>
{state_json}
</state>"""

TOOLS_BLOCK = """\
The tools you can call are defined below as JSON.

<tools>
{tools_json}
</tools>"""

TOOLCALL_INSTRUCTION = """\
Decide the single game action that the player's input represents.
Reply with one JSON object and nothing else:
{"tool": "<tool name>", "arguments": { ... }}
If the input is pure conversation with no mechanical effect, reply
with exactly: {"tool": null}"""

# Values from CLAUDE.md section 2.2. Every sampling parameter is set so that no
# model default leaks into a run (docs/model_shortlist.md section 5).
OPTIONS: Doc = {
    "num_ctx": 8192,
    "num_predict": 200,
    "temperature": 0.0,
    "top_p": 1.0,
    "top_k": 0,
    "min_p": 0.0,
    "seed": 0,
    "repeat_penalty": 1.0,
    "presence_penalty": 0.0,
    "frequency_penalty": 0.0,
}

WARM_UP_PROMPT = 'Reply with the JSON object {"tool": null} and nothing else.'


# --- schemas, cases and states ---


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


_STATE_SCHEMA = _load_json(SCHEMAS / "state.schema.json")
_TOOLS_SCHEMA = _load_json(SCHEMAS / "tools.schema.json")
_REGISTRY = Registry().with_resources(
    (s["$id"], Resource.from_contents(s)) for s in (_STATE_SCHEMA, _TOOLS_SCHEMA)
)
_CALL_VALIDATOR = Draft202012Validator(
    {"$ref": _TOOLS_SCHEMA["$id"] + "#/$defs/proposed_call"}, registry=_REGISTRY
)


def tool_definitions() -> list[Doc]:
    """The model-facing tool list, derived from args_* (docs/tool_contract.md section 5)."""
    definitions = []
    for tool in _TOOLS_SCHEMA["$defs"]["tool_name"]["enum"]:
        args = copy.deepcopy(_TOOLS_SCHEMA["$defs"][f"args_{tool}"])
        description = args.pop("description")
        definitions.append({"name": tool, "description": description, "parameters": args})
    return definitions


def schema_errors(call: Any) -> list[str]:
    return [e.message for e in _CALL_VALIDATOR.iter_errors(call)]


def load_cases(path: Path = CASES_PATH) -> list[Doc]:
    return _load_json(path)["cases"]


def load_state(name: str) -> Doc:
    return _load_json(EXAMPLES / f"{name}.json")


# --- the request ---


def build_system_prompt(state: Doc) -> str:
    return "\n\n".join(
        [
            PREAMBLE,
            STATE_BLOCK.format(state_json=json.dumps(state, indent=2, ensure_ascii=False)),
            TOOLS_BLOCK.format(tools_json=json.dumps(tool_definitions(), indent=2)),
            TOOLCALL_INSTRUCTION,
        ]
    )


def chat_body(
    model: str,
    messages: list[Doc],
    *,
    thinking: bool,
    fmt: str | None,
    options: Doc | None = None,
) -> Doc:
    body: Doc = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": dict(OPTIONS if options is None else options),
    }
    if thinking:
        body["think"] = False
    if fmt is not None:
        body["format"] = fmt
    return body


def build_chat_request(
    model: str, case: Doc, state: Doc, *, thinking: bool = False, fmt: str | None = None
) -> Doc:
    messages = [
        {"role": "system", "content": build_system_prompt(state)},
        {"role": "user", "content": case["input"]},
    ]
    return chat_body(model, messages, thinking=thinking, fmt=fmt)


# --- scoring ---

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def parse_strict(raw: str) -> Doc | None:
    try:
        parsed = json.loads(raw.strip())
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None


def parse_lenient(raw: str) -> Doc | None:
    """The first JSON object in the reply, ignoring code fences and prose around it."""
    fenced = _FENCE.search(raw)
    text = fenced.group(1) if fenced else raw
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", text):
        try:
            parsed, _ = decoder.raw_decode(text, match.start())
        except ValueError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _without(arguments: Any, ignore: list[str]) -> Any:
    if not isinstance(arguments, dict):
        return arguments
    return {k: v for k, v in arguments.items() if k not in ignore}


def score(raw: str, expected: Doc, ignore_args: list[str]) -> Doc:
    strict = parse_strict(raw)
    lenient = parse_lenient(raw)
    errors = schema_errors(strict) if strict is not None else []
    lenient_valid = lenient is not None and not schema_errors(lenient)

    tool_match = lenient is not None and "tool" in lenient and lenient["tool"] == expected["tool"]
    args_match = tool_match and _without(lenient.get("arguments"), ignore_args) == _without(
        expected.get("arguments"), ignore_args
    )
    return {
        "strict_parse": strict is not None,
        "lenient_parse": lenient is not None,
        "schema_valid": strict is not None and not errors,
        "schema_valid_lenient": lenient_valid,
        "schema_errors": errors[:5],
        "tool_match": tool_match,
        "args_match": bool(args_match),
    }


# --- the run ---


def p95(values: list[float]) -> float | None:
    """Nearest-rank 95th percentile."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[math.ceil(0.95 * len(ordered)) - 1]


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def safe_name(model: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", model)


def preflight(client: httpx.Client, model: str, fmt: str | None) -> Doc:
    """Digest, capabilities and GPU share. Raises LookupError if the model is absent."""
    tags = client.get("/api/tags")
    tags.raise_for_status()
    installed = {m["name"]: m for m in tags.json()["models"]}
    if model not in installed:
        raise LookupError(f"{model} is not installed in Ollama")

    show = client.post("/api/show", json={"model": model})
    show.raise_for_status()
    thinking = "thinking" in show.json().get("capabilities", [])

    # Untimed warm-up, so that loading the model is not counted against case 1.
    warm = chat_body(
        model, [{"role": "user", "content": WARM_UP_PROMPT}], thinking=thinking, fmt=fmt
    )
    client.post("/api/chat", json=warm).raise_for_status()

    gpu_share = None
    ps = client.get("/api/ps")
    ps.raise_for_status()
    for loaded in ps.json().get("models", []):
        if loaded.get("name") == model and loaded.get("size"):
            gpu_share = loaded["size_vram"] / loaded["size"]

    return {"digest": installed[model].get("digest"), "thinking": thinking, "gpu_share": gpu_share}


def _run_case(
    client: httpx.Client, model: str, case: Doc, *, thinking: bool, fmt: str | None
) -> Doc:
    request = build_chat_request(model, case, load_state(case["state"]), thinking=thinking, fmt=fmt)
    record: Doc = {"raw_output": None, "error": None}
    started = time.perf_counter()
    try:
        response = client.post("/api/chat", json=request)
        response.raise_for_status()
        reply = response.json()
        record["raw_output"] = reply["message"]["content"]
        for key in (
            "total_duration",
            "load_duration",
            "prompt_eval_count",
            "eval_count",
            "eval_duration",
        ):
            record[key] = reply.get(key)
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        record["error"] = f"{type(exc).__name__}: {exc}"
    record["wall_s"] = time.perf_counter() - started

    record.update(score(record["raw_output"] or "", case["expected"], case["ignore_args"]))
    return record


def summarise(model: str, meta: Doc, records: list[Doc]) -> Doc:
    def rate(key: str) -> float | None:
        return mean([1.0 if r[key] else 0.0 for r in records])

    answered = [r for r in records if r["error"] is None]
    latencies = [r["wall_s"] for r in answered]
    speeds = [
        r["eval_count"] / (r["eval_duration"] / 1e9)
        for r in answered
        if r.get("eval_count") and r.get("eval_duration")
    ]
    prompt_tokens = [float(r["prompt_eval_count"]) for r in answered if r.get("prompt_eval_count")]
    return {
        "model": model,
        **meta,
        "n": len(records),
        "errors": len(records) - len(answered),
        "strict_parse_rate": rate("strict_parse"),
        "schema_valid_rate": rate("schema_valid"),
        "schema_valid_lenient_rate": rate("schema_valid_lenient"),
        "tool_match_rate": rate("tool_match"),
        "args_match_rate": rate("args_match"),
        "latency_mean_s": mean(latencies),
        "latency_p95_s": p95(latencies),
        "tokens_per_s_mean": mean(speeds),
        "prompt_tokens_mean": mean(prompt_tokens),
    }


def run(
    models: list[str],
    *,
    client: httpx.Client,
    out_dir: Path,
    fmt: str | None = None,
    repeats: int = 1,
    limit: int | None = None,
    log: Any = None,
) -> Doc:
    """Run every case on every model. Writes <model>.jsonl per model and summary.json."""
    out_dir.mkdir(parents=True, exist_ok=True)
    cases = load_cases()[:limit]
    summary: Doc = {
        "started": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "format": fmt,
        "repeats": repeats,
        "cases": len(cases),
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

        records = []
        with (out_dir / f"{safe_name(model)}.jsonl").open("w", encoding="utf-8") as sink:
            for repeat in range(repeats):
                for case in cases:
                    record = {
                        "case_id": case["id"],
                        "repeat": repeat,
                        "model": model,
                        "format": fmt,
                        **_run_case(client, model, case, thinking=meta["thinking"], fmt=fmt),
                    }
                    records.append(record)
                    sink.write(json.dumps(record, ensure_ascii=False) + "\n")
                    sink.flush()
                    if log:
                        mark = "ok" if record["schema_valid"] else "x"
                        log(f"{model} {case['id']} r{repeat}: {mark}")
        summary["models"].append(summarise(model, meta, records))

    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return summary


# --- command line ---


def _percent(value: float | None) -> str:
    return "-" if value is None else f"{value:.0%}"


def _number(value: float | None, digits: int = 1) -> str:
    return "-" if value is None else f"{value:.{digits}f}"


def _table(summary: Doc) -> Table:
    table = Table(title=f"Tool-call micro-benchmark (format: {summary['format'] or 'prompt'})")
    for column in (
        "model",
        "n",
        "err",
        "schema-valid",
        "lenient",
        "tool",
        "args",
        "mean s",
        "p95 s",
        "tok/s",
        "GPU",
    ):
        table.add_column(column)
    for m in summary["models"]:
        if "error" in m:
            table.add_row(m["model"], "-", m["error"])
            continue
        table.add_row(
            m["model"],
            str(m["n"]),
            str(m["errors"]),
            _percent(m["schema_valid_rate"]),
            _percent(m["schema_valid_lenient_rate"]),
            _percent(m["tool_match_rate"]),
            _percent(m["args_match_rate"]),
            _number(m["latency_mean_s"], 2),
            _number(m["latency_p95_s"], 2),
            _number(m["tokens_per_s_mean"]),
            _percent(m["gpu_share"]),
        )
    return table


def main(
    model: Annotated[list[str], typer.Option("--model", help="Ollama tag; repeat for more.")],
    fmt: Annotated[
        str | None, typer.Option("--format", help="Send Ollama's format field, e.g. json.")
    ] = None,
    repeats: Annotated[int, typer.Option(min=1)] = 1,
    limit: Annotated[int | None, typer.Option(min=1, help="Run only the first N cases.")] = None,
    host: str = "http://localhost:11434",
    out: Path = Path("results/bench/toolcall"),
    timeout: float = 120.0,
) -> None:
    """Run the 20-case tool-calling micro-benchmark (WBS 3.3) against local Ollama models."""
    if fmt not in (None, "json"):
        raise typer.BadParameter("only 'json' is supported", param_hint="--format")
    console = Console()
    out_dir = out / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    with httpx.Client(base_url=host, timeout=timeout) as client:
        summary = run(
            model,
            client=client,
            out_dir=out_dir,
            fmt=fmt,
            repeats=repeats,
            limit=limit,
            log=console.print,
        )
    console.print(_table(summary))
    console.print(f"Records and summary in {out_dir}")


if __name__ == "__main__":
    typer.run(main)
