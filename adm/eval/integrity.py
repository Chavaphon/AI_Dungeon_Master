"""The run integrity check (WBS 9.3): is the main-grid dataset whole, crash-free
and correctly seeded, before annotation begins?

    python -m adm.eval.integrity --manifest experiments/main_grid.json

It reads the logs under `runs/` and the batch runner's attempt ledger
(`results/batch/attempts.jsonl`, WBS 7.6), and never calls the model or imports
orchestration (docs/conventions.md section 1). It is run on the copy the
annotators will read, so it also catches a log damaged on its way to the Drive.

**Completeness.** Every run the manifest plans has a log, and every log passes
the run-log validator (`adm.eval.validate`, WBS 7.7): the audit-log schema and
its rules, its own run fields, one record per scripted input with the scripted
text, and state hashes that replay. Logs the manifest does not plan (the smoke
runs, a dry run) are listed and not checked, and so are files under
`runs/{condition}/` that are not a log in its place.

**Crashes.** The ledger is the only record of what happened while a run was
played, so every planned run must have one, and its last attempt must be
`complete`, with no transport retry, the log's record count and the run's seed.
Every run must have been played with the same model and digest; the batch
runner already refuses one that does not match `config/model.json` before it
plays anything, and `eval` may not read the model config itself
(docs/conventions.md section 1). A log in place with no such line
did not come from the batch runner, so nothing shows it had no transport retry.
Attempts that did not complete before a later one did, logs left under
`runs/pending/` and logs moved to `runs/aborted/` are listed as the crash
history. Turn failures are counted, and narrated turns with an empty narration
are listed, for the annotators: a re-run reproduces both byte for byte
(invariant 4), so they are data, not gaps.

**Seeds.** Every (scenario, condition) cell holds a log for each of the
manifest's seeds, the same in every cell. Each record's `seed` is its log's (the validator), each
state hash replays from that seed (the validator), and each ledger line's
`seed` is its run's.

**Gaps** are the planned runs that fail any check above. The fix is in
`docs/run_integrity.md` section 4: fetch the log again if only this copy is
damaged, otherwise move it to `runs/aborted/` and let the batch runner play it
again (WBS 9.10).

**Checksums.** `--write-checksums` writes the sha256 of every planned log in
`sha256sum` format, and `--checksums` checks this copy against such a file, so
whoever reads the logs later can confirm they hold the dataset that was checked.

The command exits 0 only when there is no gap and no checksum mismatch. `--out`
also writes the report as JSON.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Any

import typer

from adm.engine.audit import log_path, run_id, turn_failure_counts
from adm.engine.scenario import Scenario, load_scenario
from adm.eval.checker import CONDITIONS, RunKey
from adm.eval.validate import validate_runs

Doc = dict[str, Any]

LEDGER = Path("results/batch/attempts.jsonl")
COMPLETE = "complete"  # adm.orchestration.batch.COMPLETE; not imported (conventions §1)
PENDING = "pending"
ABORTED = "aborted"


@dataclass
class RunIntegrity:
    key: RunKey
    records: int = 0
    sha256: str | None = None
    errors: list[str] = field(default_factory=list)
    history: list[str] = field(default_factory=list)

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
            "sha256": self.sha256,
            "errors": self.errors,
            "history": self.history,
        }


@dataclass
class Report:
    runs: list[RunIntegrity]
    seeds: list[int]
    unplanned: list[str] = field(default_factory=list)
    strays: list[str] = field(default_factory=list)
    pending: list[str] = field(default_factory=list)
    aborted: list[str] = field(default_factory=list)
    seed_errors: list[str] = field(default_factory=list)
    models: dict[str, int] = field(default_factory=dict)
    checksum_errors: list[str] = field(default_factory=list)
    turn_failures: dict[str, int] = field(default_factory=dict)
    empty_narrations: list[str] = field(default_factory=list)

    @property
    def gaps(self) -> list[str]:
        return [r.run_id for r in self.runs if r.errors]

    @property
    def model_errors(self) -> list[str]:
        if len(self.models) <= 1:
            return []
        return ["runs were played with more than one model: " + ", ".join(self.models)]

    @property
    def ok(self) -> bool:
        return not (self.gaps or self.seed_errors or self.model_errors or self.checksum_errors)

    @property
    def record_count(self) -> int:
        return sum(r.records for r in self.runs)

    def to_dict(self) -> Doc:
        return {
            "ok": self.ok,
            "gaps": self.gaps,
            "planned": len(self.runs),
            "records": self.record_count,
            "seeds": self.seeds,
            "seed_errors": self.seed_errors,
            "models": self.models,
            "model_errors": self.model_errors,
            "checksum_errors": self.checksum_errors,
            "unplanned": self.unplanned,
            "strays": self.strays,
            "pending": self.pending,
            "aborted": self.aborted,
            "turn_failures": self.turn_failures,
            "empty_narrations": self.empty_narrations,
            "runs": [r.to_dict() for r in self.runs],
        }


# --- the manifest and the ledger ---------------------------------------------


def load_plan(manifest: Path) -> tuple[list[RunKey], dict[str, Scenario], list[int]]:
    """The runs a batch manifest plans, in the batch runner's order, its
    scenarios by id, and its seeds."""
    doc = json.loads(manifest.read_text(encoding="utf-8"))
    scenarios = {s.scenario_id: s for s in (load_scenario(Path(p)) for p in doc["scenarios"])}
    seeds = list(doc["seeds"])
    planned = [(c, sid, seed) for seed in seeds for sid in scenarios for c in doc["conditions"]]
    return planned, scenarios, seeds


def read_ledger(path: Path) -> dict[str, list[Doc]]:
    """The ledger's lines by run id, in the order they were written."""
    lines: dict[str, list[Doc]] = defaultdict(list)
    if path.exists():
        with path.open(encoding="utf-8") as ledger:
            for line in ledger:
                if line.strip():
                    entry = json.loads(line)
                    lines[entry["run_id"]].append(entry)
    return lines


def _first_line(text: Any) -> str:
    return str(text).strip().splitlines()[0] if text else ""


def ledger_errors(key: RunKey, entries: Sequence[Doc], records: int | None) -> list[str]:
    """Where a run's ledger lines fail to show one clean, complete attempt.
    `records` is the log's record count, None if there is no log."""
    if not entries:
        return ["no ledger line: nothing shows how this log was played"]
    last = entries[-1]
    if last.get("outcome") != COMPLETE:
        detail = _first_line(last.get("error"))
        return [f"last ledger attempt is {last.get('outcome')}" + (f": {detail}" if detail else "")]
    errors: list[str] = []
    if last.get("seed") != key[2]:
        errors.append(f"the ledger's complete line has seed {last.get('seed')!r}")
    if last.get("transport_retries") != 0:
        errors.append(f"the complete attempt had {last.get('transport_retries')} transport retries")
    if records is not None and last.get("records") != records:
        errors.append(f"the ledger counts {last.get('records')} records, the log holds {records}")
    return errors


def played_with(entries: Sequence[Doc]) -> str | None:
    """`model@digest` of a run's complete attempt, None if it has none."""
    if not entries or entries[-1].get("outcome") != COMPLETE:
        return None
    return f"{entries[-1].get('model')}@{entries[-1].get('model_digest')}"


def history(entries: Sequence[Doc]) -> list[str]:
    """Every ledger line before the last: attempts that did not complete."""
    lines = []
    for entry in entries[:-1]:
        detail = _first_line(entry.get("error"))
        attempt = entry.get("attempt")
        where = f"attempt {attempt}" if attempt is not None else "resume"
        lines.append(f"{where} {entry.get('outcome')}" + (f": {detail}" if detail else ""))
    return lines


# --- the logs ----------------------------------------------------------------


def log_keys(runs_dir: Path) -> list[RunKey]:
    """Every log in place under `runs/{condition}/{scenario_id}/{seed}.jsonl`,
    found as `adm.eval.checker.load_runs` finds them, without reading them."""
    return sorted(
        (condition, path.parent.name, int(path.stem))
        for condition in CONDITIONS
        for path in (runs_dir / condition).glob("*/*.jsonl")
        if path.stem.isdigit()
    )


def strays(runs_dir: Path) -> list[str]:
    """Files under `runs/{condition}/` that are not a log in its place, such as
    a folder copied into the wrong place. No tool reads them."""
    return sorted(
        path.as_posix()
        for condition in CONDITIONS
        for path in (runs_dir / condition).rglob("*")
        if path.is_file()
        and not (
            path.suffix == ".jsonl"
            and path.stem.isdigit()
            and path.parent.parent == runs_dir / condition
        )
    )


def read_records(path: Path) -> tuple[list[Doc], str | None]:
    """A log's records, and an error if a line is not one JSON object: a log
    cut short or damaged in a copy."""
    records: list[Doc] = []
    with path.open(encoding="utf-8") as log:
        for number, line in enumerate(log, start=1):
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                return records, f"line {number} is not JSON"
            if not isinstance(record, dict):
                return records, f"line {number} is not a JSON object"
            records.append(record)
    return records, None


# --- seeds, leftovers and checksums ------------------------------------------


def seed_errors(
    logs: Sequence[RunKey],
    scenarios: Mapping[str, Scenario],
    conditions: Sequence[str],
    seeds: Sequence[int],
) -> list[str]:
    """Cells with no log for one of the manifest's seeds. Other seeds (a smoke
    run in the same folder) are allowed."""
    found: dict[tuple[str, str], set[int]] = defaultdict(set)
    for condition, scenario_id, seed in logs:
        found[(scenario_id, condition)].add(seed)
    errors = []
    for scenario_id in scenarios:
        for condition in conditions:
            have = found[(scenario_id, condition)]
            if not set(seeds) <= have:
                missing = sorted(set(seeds) - have)
                errors.append(f"{condition} {scenario_id}: no log for seeds {missing}")
    return errors


def leftovers(runs_dir: Path, planned: Sequence[RunKey], folder: str) -> list[str]:
    """Logs of planned runs left under `runs/pending/` or `runs/aborted/`."""
    found = []
    for condition, scenario_id, seed in planned:
        place = log_path(runs_dir / folder, condition, scenario_id, seed).parent
        found.extend(p.as_posix() for p in sorted(place.glob(f"{seed}.*jsonl")))
    return found


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checksum_lines(runs_dir: Path, report: Report) -> list[str]:
    """`sha256sum` lines for every planned log on disk, in plan order."""
    return [
        f"{r.sha256}  {log_path(runs_dir, *r.key).as_posix()}"
        for r in report.runs
        if r.sha256 is not None
    ]


def read_checksums(path: Path) -> dict[str, str]:
    sums = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            digest, name = line.split(maxsplit=1)
            sums[name.lstrip("*").strip()] = digest
    return sums


def checksum_errors(runs_dir: Path, report: Report, expected: Mapping[str, str]) -> list[str]:
    """Where this copy's logs differ from a checksum file of the checked dataset."""
    have = {log_path(runs_dir, *r.key).as_posix(): r.sha256 for r in report.runs}
    errors = []
    for name, digest in expected.items():
        if name not in have:
            errors.append(f"{name}: in the checksum file, not planned by the manifest")
        elif have[name] is None:
            errors.append(f"{name}: no such log")
        elif have[name] != digest:
            errors.append(f"{name}: sha256 differs from the checksum file")
    errors.extend(f"{name}: not in the checksum file" for name in have if name not in expected)
    return errors


# --- the check ---------------------------------------------------------------


def check(runs_dir: Path, manifest: Path, ledger: Path) -> Report:
    """The integrity report of every run `manifest` plans."""
    planned, scenarios, seeds = load_plan(manifest)
    conditions = list(dict.fromkeys(k[0] for k in planned))
    wanted = set(planned)
    logs = log_keys(runs_dir)
    ours: dict[RunKey, list[Doc]] = {}
    unreadable: dict[RunKey, str] = {}
    for key in planned:
        if key in logs:
            ours[key], error = read_records(log_path(runs_dir, *key))
            if error is not None:
                unreadable[key] = error
    readable = {k: v for k, v in ours.items() if k not in unreadable}
    validation = {r.key: r.errors for r in validate_runs(readable, scenarios).runs}
    lines = read_ledger(ledger)

    report = Report(
        runs=[],
        seeds=seeds,
        unplanned=[run_id(*k) for k in logs if k not in wanted],
        strays=strays(runs_dir),
        pending=leftovers(runs_dir, planned, PENDING),
        aborted=leftovers(runs_dir, planned, ABORTED),
        seed_errors=seed_errors(logs, scenarios, conditions, seeds),
    )
    failures: Counter[str] = Counter()
    models: Counter[str] = Counter()
    for key in planned:
        run = RunIntegrity(key)
        entries = lines.get(run_id(*key), [])
        if key not in ours:
            run.errors.append("no log")
        else:
            records = ours[key]
            run.records = len(records)
            run.sha256 = file_sha256(log_path(runs_dir, *key))
            run.errors.extend([unreadable[key]] if key in unreadable else validation[key])
            if not run.errors:
                failures.update(turn_failure_counts(records))
                report.empty_narrations.extend(
                    f"{run.run_id} input {r['input_index']}"
                    for r in records
                    if r["turn_failure"] is None and not str(r["narration"]).strip()
                )
        run.errors.extend(ledger_errors(key, entries, run.records if key in ours else None))
        run.history = history(entries)
        model = played_with(entries)
        if model is not None:
            models[model] += 1
        report.runs.append(run)
    report.turn_failures = dict(sorted(failures.items()))
    report.models = dict(sorted(models.items()))
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


def write_checksums(path: Path, lines: Sequence[str]) -> str:
    """Write the checksum file with LF endings; return its own sha256, the
    digest of the whole dataset."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(line + "\n" for line in lines)
    path.write_bytes(text.encode("utf-8"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --- the command line --------------------------------------------------------

app = typer.Typer(add_completion=False)
SHOWN = 5


@app.command()
def main(
    manifest: Annotated[
        Path, typer.Option(exists=True, dir_okay=False, help="Batch manifest the logs cover.")
    ] = Path("experiments/main_grid.json"),
    runs: Annotated[Path, typer.Option(help="Directory of the run logs.")] = Path("runs"),
    ledger: Annotated[Path, typer.Option(help="The batch runner's attempt ledger.")] = LEDGER,
    out: Annotated[Path | None, typer.Option(help="JSON file the report is written to.")] = None,
    write_checksums_to: Annotated[
        Path | None,
        typer.Option("--write-checksums", help="Write the sha256 of every planned log here."),
    ] = None,
    checksums: Annotated[
        Path | None,
        typer.Option(exists=True, dir_okay=False, help="Check the logs against this sha256 file."),
    ] = None,
) -> None:
    """Check that every planned run is complete, crash-free and correctly seeded."""
    report = check(runs, manifest, ledger)
    if checksums is not None:
        report.checksum_errors = checksum_errors(runs, report, read_checksums(checksums))

    for run in report.runs:
        if run.errors or run.history:
            typer.echo(f"{run.run_id}: {len(run.errors)} errors")
            for line in run.errors[:SHOWN]:
                typer.echo(f"  {line}")
            if len(run.errors) > SHOWN:
                typer.echo(f"  ... {len(run.errors) - SHOWN} more")
            for line in run.history:
                typer.echo(f"  history: {line}")

    complete = len(report.runs) - len([r for r in report.runs if r.errors])
    typer.echo(
        f"Completeness: {complete} of {len(report.runs)} planned runs whole and valid, "
        f"{report.record_count} records"
    )
    crashed = sum(1 for r in report.runs if r.history)
    typer.echo(
        f"Crashes: {crashed} runs with an earlier failed attempt, "
        f"{len(report.pending)} pending logs, {len(report.aborted)} aborted logs"
    )
    for label, items in (("Pending", report.pending), ("Aborted", report.aborted)):
        for item in items:
            typer.echo(f"  {label}: {item}")
    typer.echo(f"Seeds: {report.seeds} in every cell" if not report.seed_errors else "Seeds:")
    for line in report.seed_errors:
        typer.echo(f"  {line}")
    for model, count in report.models.items():
        typer.echo(f"Model: {model}, {count} runs")
    for line in report.model_errors:
        typer.echo(f"  {line}")
    failures = ", ".join(f"{k} {v}" for k, v in report.turn_failures.items()) or "none"
    typer.echo(f"Turn failures (data, not crashes): {failures}")
    typer.echo(f"Empty narrations in narrated turns: {len(report.empty_narrations)}")
    for item in report.empty_narrations:
        typer.echo(f"  {item}")
    if report.unplanned:
        typer.echo(f"Not in the manifest (not checked): {', '.join(report.unplanned)}")
    if report.strays:
        typer.echo(f"Not a log in its place (no tool reads them): {len(report.strays)} files")
        for item in report.strays:
            typer.echo(f"  {item}")
    if checksums is not None:
        status = "match" if not report.checksum_errors else f"{len(report.checksum_errors)} errors"
        typer.echo(f"Checksums against {checksums.as_posix()}: {status}")
        for line in report.checksum_errors[:SHOWN]:
            typer.echo(f"  {line}")
    typer.echo(f"Gaps: {', '.join(report.gaps) if report.gaps else 'none'}")
    if write_checksums_to is not None:
        digest = write_checksums(write_checksums_to, checksum_lines(runs, report))
        typer.echo(f"Checksums: {write_checksums_to.as_posix()} (sha256 {digest})")
    if out is not None:
        write_report(out, report)
        typer.echo(f"Report: {out.as_posix()}")
    if not report.ok:
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
