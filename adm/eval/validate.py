"""The run-log validator (WBS 7.7): is every log on disk a whole, valid run?

    python -m adm.eval.validate --runs runs/dry_run --manifest experiments/dry_run.json

It reads every run log under `runs/{condition}/{scenario_id}/{seed}.jsonl`, as
the checker does, and never calls the model or imports orchestration
(docs/conventions.md section 1). The audit-log writer already refuses a bad
record (`adm.engine.audit.AuditLog.append`); this re-checks what is actually on
disk, after the batch runner has moved it, so a log that was truncated, edited
or written by an older build is caught before it is scored.

**Per log**, each a list of errors:

1. Every record passes `schemas/audit.schema.json` (`schema_errors`) and the
   rules the schema cannot express (`record_errors`, docs/audit_log.md
   section 3).
2. Every record's `condition`, `scenario_id`, `seed` and `run_id` are the
   log's own (its path).
3. The log holds one record per scripted input, in order (`covers_script`).
4. Every record's `player_input` is the text of its scripted input, so every
   condition got the same stimuli (invariant 7).
5. The state hashes replay: condition D from its diffs, A to C from
   `replay_script` (`adm.eval.checker.scored_states`).

Checks 3 to 5 run only on a log whose records pass 1, since they read fields
the schema guarantees.

**Against a manifest** (`--manifest`, the batch runner's format): a planned
run with no log is an error; a log the manifest does not plan is listed, not
counted as an error.

The command prints one line per run and exits 0 only when there is no error.
`--out` also writes the report as JSON.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Any

import typer

from adm.engine.audit import covers_script, record_errors, run_id, schema_errors
from adm.engine.scenario import Scenario, load_scenario
from adm.eval.checker import LogMismatch, RunKey, load_runs, scored_states

Doc = dict[str, Any]

# Errors shown per run on the command line; the JSON report holds all of them.
SHOWN = 5


@dataclass
class RunReport:
    key: RunKey
    records: int
    errors: list[str] = field(default_factory=list)

    @property
    def run_id(self) -> str:
        return run_id(*self.key)

    def to_dict(self) -> Doc:
        condition, scenario_id, seed = self.key
        return {
            "run_id": self.run_id,
            "condition": condition,
            "scenario_id": scenario_id,
            "seed": seed,
            "records": self.records,
            "errors": self.errors,
        }


@dataclass
class Report:
    runs: list[RunReport]
    missing: list[str] = field(default_factory=list)
    unplanned: list[str] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(len(r.errors) for r in self.runs) + len(self.missing)

    @property
    def ok(self) -> bool:
        return self.error_count == 0

    def to_dict(self) -> Doc:
        return {
            "ok": self.ok,
            "errors": self.error_count,
            "runs": [r.to_dict() for r in self.runs],
            "missing": self.missing,
            "unplanned": self.unplanned,
        }


def validate_log(key: RunKey, records: Sequence[Doc], scenario: Scenario | None) -> list[str]:
    """Every error of one run log. `scenario` is None when its file is missing."""
    condition, scenario_id, seed = key
    errors: list[str] = []
    if not records:
        return ["the log is empty"]
    own = {
        "condition": condition,
        "scenario_id": scenario_id,
        "seed": seed,
        "run_id": run_id(condition, scenario_id, seed),
    }
    for position, record in enumerate(records):
        where = f"record {position}"
        broken = schema_errors(record)
        if broken:
            errors.extend(f"{where}: {e}" for e in broken)
            continue
        errors.extend(f"{where}: {e}" for e in record_errors(record))
        for name, value in own.items():
            if record[name] != value:
                errors.append(f"{where}: {name} is {record[name]!r}, the log is {value!r}")
    if errors:
        return errors
    if scenario is None:
        return [f"no scenario file for {scenario_id}"]

    inputs = scenario.scripted_inputs
    if not covers_script(records, len(inputs)):
        indexes = [r["input_index"] for r in records]
        return [f"input_index runs {_span(indexes)}, not 0..{len(inputs) - 1}, once each"]
    for record, scripted in zip(records, inputs, strict=True):
        if record["player_input"] != scripted.text:
            errors.append(
                f"input {record['input_index']}: player_input is not the scripted input's text"
            )
    try:
        scored_states(scenario, records)
    except LogMismatch as exc:
        errors.append(str(exc))
    return errors


def _span(indexes: Sequence[Any]) -> str:
    if len(indexes) <= 6:
        return str(list(indexes))
    return f"[{indexes[0]}, {indexes[1]}, ..., {indexes[-1]}] ({len(indexes)} records)"


def planned_runs(manifest: Path) -> list[RunKey]:
    """Every run a batch manifest plans (adm/orchestration/batch.py's format)."""
    doc = json.loads(manifest.read_text(encoding="utf-8"))
    ids = [load_scenario(Path(p)).scenario_id for p in doc["scenarios"]]
    return [(c, sid, seed) for seed in doc["seeds"] for sid in ids for c in doc["conditions"]]


def validate_runs(
    runs: Mapping[RunKey, Sequence[Doc]],
    scenarios: Mapping[str, Scenario],
    planned: Sequence[RunKey] | None = None,
) -> Report:
    """Validate every run log, and check them against the planned runs if given."""
    report = Report(
        [
            RunReport(key, len(runs[key]), validate_log(key, runs[key], scenarios.get(key[1])))
            for key in sorted(runs)
        ]
    )
    if planned is not None:
        wanted = set(planned)
        report.missing = [run_id(*k) for k in planned if k not in runs]
        report.unplanned = [run_id(*k) for k in sorted(runs) if k not in wanted]
    return report


def write_report(path: Path, report: Report) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(tmp, path)


# --- the command line --------------------------------------------------------

app = typer.Typer(add_completion=False)


@app.command()
def main(
    runs: Annotated[Path, typer.Option(help="Directory of the run logs.")] = Path("runs"),
    manifest: Annotated[
        Path | None,
        typer.Option(exists=True, dir_okay=False, help="Batch manifest the logs should cover."),
    ] = None,
    scenarios: Annotated[Path, typer.Option(help="Directory of the scenario files.")] = Path(
        "scenarios"
    ),
    out: Annotated[Path | None, typer.Option(help="JSON file the report is written to.")] = None,
) -> None:
    """Check every run log against the audit-log schema, its script and its hashes."""
    logs = load_runs(runs)
    loaded = {
        sid: load_scenario(scenarios / f"{sid}.json")
        for sid in sorted({k[1] for k in logs})
        if (scenarios / f"{sid}.json").exists()
    }
    planned = planned_runs(manifest) if manifest is not None else None
    report = validate_runs(logs, loaded, planned)

    for run in report.runs:
        status = "ok" if not run.errors else f"{len(run.errors)} errors"
        typer.echo(f"{run.run_id}: {run.records} records, {status}")
        for error in run.errors[:SHOWN]:
            typer.echo(f"  {error}")
        if len(run.errors) > SHOWN:
            typer.echo(f"  ... {len(run.errors) - SHOWN} more")
    for label, ids in (("Missing", report.missing), ("Not in the manifest", report.unplanned)):
        if ids:
            typer.echo(f"{label}: {', '.join(ids)}")
    records = sum(r.records for r in report.runs)
    verdict = "valid" if report.ok else f"{report.error_count} errors"
    typer.echo(f"{len(report.runs)} runs, {records} records: {verdict}")
    if out is not None:
        write_report(out, report)
        typer.echo(f"Report: {out}")
    if not report.ok:
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
