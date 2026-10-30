"""Smoke runs for Milestone 1 / gate G2 (WBS 6.11).

Ten scripted condition D runs over the long scenarios, listed in
experiments/smoke_grid.json. The gate is met when at least nine of the ten
complete without an unrecoverable failure (TASK_CHECKLIST.md, G2), which is
also the Objective 2 criterion: condition D sustains a 50-turn session.

`python -m adm.cli smoke` plays each run as `python -m adm.cli run --condition D`
does, with a freshly loaded model (CLAUDE.md section 2.2), through the `Runner`
it passes in; this module only schedules the runs and reads their logs, so it
imports the engine and nothing else (docs/conventions.md section 1). A run is
**complete** when it raised nothing and its audit log holds exactly one record
per scripted input, in order. An exception (a model error after the client's
retries, an illegal state, a refused record) or a missing input makes it
**unrecoverable**. A failed turn is not: the pipeline recovers from it by
design (CLAUDE.md section 7.1), so it is counted, not fatal.

Every other figure is read back from the audit logs:

- `schema_valid_first`: first toolcall attempts that parse and pass the schema
  (neither unparseable nor `SCHEMA_VIOLATION`), over turns. It is the figure for
  risk R1's 80 per cent trigger (docs/decisions.md, WBS 3.7 point 3).
- `rejected_turns`, `recovered_turns`: turns with at least one failed attempt,
  and those of them that still executed or ended narration-only (M2's shape).
- Turn failures by kind, narration-only turns, summary regenerations, turns
  whose K was reduced, turn latency (mean, p95) and tokens per second
  (`completion_tokens / eval_ms`, mean over model calls, M6).

A run whose log already exists is not played again: a complete log is read as
it is, and an incomplete one counts as unrecoverable, so the driver can be
restarted after an interruption without overwriting evidence.

Run: python -m adm.cli smoke --manifest experiments/smoke_grid.json
"""

from __future__ import annotations

import json
import traceback
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

from adm.bench.toolcall import mean, p95
from adm.engine.audit import log_path, read_log, turn_failure_counts
from adm.engine.scenario import Scenario, load_scenario

Doc = dict[str, Any]
# Plays one run; raises on an unrecoverable failure.
Runner = Callable[[Scenario, int, Path], None]

CONDITION = "D"
GATE_COMPLETE = 9
GATE_ATTEMPTED = 10
R1_TRIGGER = 0.80


def load_manifest(path: Path) -> list[Doc]:
    """The runs of a smoke manifest: `{"runs": [{"scenario": path, "seed": int}]}`."""
    runs = json.loads(path.read_text(encoding="utf-8"))["runs"]
    pairs = [(r["scenario"], r["seed"]) for r in runs]
    if len(set(pairs)) != len(pairs):
        raise ValueError(f"{path} lists a run twice")
    return runs


def _schema_valid(entry: Doc) -> bool:
    return entry.get("failure") != "unparseable" and entry.get("rejection_code") != (
        "SCHEMA_VIOLATION"
    )


def summarise_run(records: Sequence[Doc], inputs: int, k: int, error: str | None) -> Doc:
    """The figures of one run, from its audit log."""
    indices = [r["input_index"] for r in records]
    turns = len(records)
    rejected = [r for r in records if any(not v["ok"] for v in r["validation"])]
    calls = [c for r in records for c in r["model_calls"]]
    speeds = [c["completion_tokens"] / (c["eval_ms"] / 1000) for c in calls if c["eval_ms"] > 0]
    latencies = [r["turn_latency_ms"] / 1000 for r in records]
    first = [r["validation"][0] for r in records if r["validation"]]
    return {
        "complete": error is None and indices == list(range(inputs)),
        "error": error,
        "inputs": inputs,
        "turns": turns,
        "narrated": sum(1 for r in records if r["turn_failure"] is None),
        "final_turn_number": records[-1]["turn_number"] if records else 0,
        "turn_failures": dict(turn_failure_counts(records)),
        "narration_only": sum(1 for r in records if r["narration_only"]),
        "toolcall_attempts": sum(len(r["validation"]) for r in records),
        "schema_valid_first": sum(1 for v in first if _schema_valid(v)),
        "rejected_turns": len(rejected),
        "recovered_turns": sum(1 for r in rejected if r["turn_failure"] is None),
        "summaries": sum(1 for r in records if r["summary_regenerated"]),
        "k_reduced": sum(1 for r in records if r["k_used"] < k),
        "encounters": sum(
            1 for r in records for s in r["engine_steps"] if s["step"] == "encounter_start"
        ),
        "latency_mean_s": mean(latencies),
        "latency_p95_s": p95(latencies),
        "tokens_per_s_mean": mean(speeds),
    }


def _rate(part: int, whole: int) -> float | None:
    return part / whole if whole else None


def summarise(runs: Sequence[Doc]) -> Doc:
    """Totals and the two verdicts: gate G2 and risk R1."""
    turns = sum(r["turns"] for r in runs)
    failures: dict[str, int] = {}
    for r in runs:
        for kind, n in r["turn_failures"].items():
            failures[kind] = failures.get(kind, 0) + n
    complete = sum(1 for r in runs if r["complete"])
    schema_valid = _rate(sum(r["schema_valid_first"] for r in runs), turns)
    rejected = sum(r["rejected_turns"] for r in runs)
    latencies = [r["latency_mean_s"] for r in runs if r["latency_mean_s"] is not None]
    return {
        "attempted": len(runs),
        "complete": complete,
        "gate_g2_met": len(runs) >= GATE_ATTEMPTED and complete >= GATE_COMPLETE,
        "turns": turns,
        "turn_failures": failures,
        "turn_failure_rate": _rate(sum(failures.values()), turns),
        "narration_only": sum(r["narration_only"] for r in runs),
        "schema_valid_first_rate": schema_valid,
        "r1_fired": schema_valid is not None and schema_valid < R1_TRIGGER,
        "rejected_turn_rate": _rate(rejected, turns),
        "recovery_rate": _rate(sum(r["recovered_turns"] for r in runs), rejected),
        "latency_mean_s": mean(latencies),
        "latency_p95_s_max": max((r["latency_p95_s"] or 0 for r in runs), default=None),
    }


def smoke(
    manifest: Sequence[Doc],
    *,
    runs_dir: Path,
    runner: Runner,
    k: int,
    log: Callable[[str], None] = print,
) -> Doc:
    """Play every run of the manifest that has no log yet, then summarise all."""
    results: list[Doc] = []
    for entry in manifest:
        scenario = load_scenario(Path(entry["scenario"]))
        seed = entry["seed"]
        path = log_path(runs_dir, CONDITION, scenario.scenario_id, seed)
        error: str | None = None
        if path.exists():
            log(f"{scenario.scenario_id} seed {seed}: log exists, read as it is")
        else:
            log(f"{scenario.scenario_id} seed {seed}: running")
            try:
                runner(scenario, seed, runs_dir)
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                log(f"{scenario.scenario_id} seed {seed}: unrecoverable\n{traceback.format_exc()}")
        records = read_log(path) if path.exists() else []
        result = summarise_run(records, len(scenario.scripted_inputs), k, error)
        results.append(
            {"scenario_id": scenario.scenario_id, "seed": seed, "log": str(path), **result}
        )
        outcome = "complete" if result["complete"] else "INCOMPLETE"
        log(f"{scenario.scenario_id} seed {seed}: {outcome}")
    return {"runs": results, "totals": summarise(results)}


# --- command line ---


def _percent(value: float | None) -> str:
    return "-" if value is None else f"{value:.1%}"


def _number(value: float | None, digits: int = 1) -> str:
    return "-" if value is None else f"{value:.{digits}f}"


def _table(summary: Doc) -> Table:
    table = Table(title="Smoke runs (WBS 6.11)")
    columns = ("run", "done", "turns", "failed", "null", "schema 1st", "recovered", "sum", "mean s")
    for column in columns:
        table.add_column(column)
    for r in summary["runs"]:
        table.add_row(
            f"{r['scenario_id']} {r['seed']}",
            "yes" if r["complete"] else "NO",
            f"{r['turns']}/{r['inputs']}",
            str(sum(r["turn_failures"].values())),
            str(r["narration_only"]),
            _percent(_rate(r["schema_valid_first"], r["turns"])),
            f"{r['recovered_turns']}/{r['rejected_turns']}",
            str(r["summaries"]),
            _number(r["latency_mean_s"]),
        )
    return table


def write_summary(summary: Doc, out_dir: Path) -> Path:
    """Write `summary.json` under `out_dir` and return its path."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "summary.json"
    path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def report(console: Console, summary: Doc) -> None:
    """The per-run table and the gate G2 and risk R1 verdicts."""
    totals = summary["totals"]
    console.print(_table(summary))
    verdict = "met" if totals["gate_g2_met"] else "NOT met"
    r1 = "FIRED" if totals["r1_fired"] else "not fired"
    console.print(
        f"{totals['complete']}/{totals['attempted']} complete: gate G2 {verdict}. "
        f"First-attempt schema-valid {_percent(totals['schema_valid_first_rate'])} (R1 {r1}).",
        markup=False,
    )
