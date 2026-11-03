"""The batch runner (WBS 7.6): every `(seed, scenario, condition)` run of a
manifest, one at a time, unattended, and resumable.

    python -m adm.cli batch --manifest experiments/main_grid.json

**Manifest.** `{"description", "scenarios": [path], "conditions": [str],
"seeds": [int]}`, every combination run once (CLAUDE.md section 10.5: 16
scenarios x 4 conditions x 3 seeds). The order is seed, then scenario, then
condition, so a batch that stops early leaves whole `(scenario, seed)` cells,
each played under every condition.

**One run.** The `Runner` the CLI passes in plays a run through the same
`open_session` and `run_script` as `adm.cli run`, on a freshly loaded model
(CLAUDE.md section 2.2), and returns the transport retries of its model calls.
The log is written under `runs/pending/` and moved to its place,
`runs/{condition}/{scenario_id}/{seed}.jsonl`, only when the run covers every
scripted input and had no transport retry. So a log in its place is a whole,
clean run, and a run is never played twice once it is there.

**Resume.** Run the same command again. A run whose log is in place and covers
the script is skipped without loading the model. Anything partial (a log left
under `runs/pending/` by a killed batch, or an incomplete log in place, such as
an interrupted `adm.cli run`) cannot be continued, because the model's replies
depend on every request it has served since it was loaded (docs/model_selection.md
section 3). It is moved to `runs/aborted/{condition}/{scenario_id}/{seed}.{UTC}.jsonl`,
never deleted, and the run is played again from the start.

**Failures**, per attempt, at most `max_attempts` attempts per run per
invocation:

- Any transport retry: the run is not guaranteed to replay byte-identically
  (docs/decisions.md, 2026-10-13, point 4), so it is aborted and played again.
- A `ModelError`: aborted and played again. On the last attempt, or at once for
  `ModelConfigMismatch`, the batch stops, since every later run would fail too.
- Any other exception is a bug and is deterministic: the run is aborted, not
  retried, and the batch goes on to the next run.
- Ctrl+C: the run is aborted and the interrupt propagates.

A run that does not finish cleanly stays pending for the next invocation
(WBS 9.10). Every attempt and every discarded log gets one line in the ledger,
`results/batch/attempts.jsonl`, which is provenance only: resuming reads the
logs, not the ledger.
"""

from __future__ import annotations

import json
import os
import traceback
from collections.abc import Callable, Collection, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from adm.engine.audit import covers_script, log_path, read_log, run_id
from adm.engine.scenario import Scenario, load_scenario
from adm.orchestration.client import MAX_SEED, ModelConfigMismatch, ModelError

Doc = dict[str, Any]

MAX_ATTEMPTS = 3
PENDING = "pending"
ABORTED = "aborted"

# Ledger outcomes.
COMPLETE = "complete"
TAINTED = "tainted"
MODEL_ERROR = "model_error"
ERROR = "error"
INTERRUPTED = "interrupted"


@dataclass(frozen=True)
class PlannedRun:
    condition: str
    scenario: Scenario
    seed: int

    @property
    def run_id(self) -> str:
        return run_id(self.condition, self.scenario.scenario_id, self.seed)

    def log(self, runs_dir: Path) -> Path:
        return log_path(runs_dir, self.condition, self.scenario.scenario_id, self.seed)


# Plays one run with its log under the given runs directory, on a freshly
# loaded model, and returns the transport retries of its model calls.
Runner = Callable[[PlannedRun, Path], int]


class ManifestError(ValueError):
    """A batch manifest that cannot be run."""


def _unique(values: list[Any], what: str, path: Path) -> None:
    if len(set(values)) != len(values):
        raise ManifestError(f"{path} lists a {what} twice")


def load_manifest(path: Path, conditions: Collection[str]) -> list[PlannedRun]:
    """Every run of a manifest, seed by seed, scenario by scenario, condition by
    condition. `conditions` are the ones that have a harness."""
    doc = json.loads(path.read_text(encoding="utf-8"))
    paths, wanted, seeds = doc["scenarios"], doc["conditions"], doc["seeds"]
    for values, what in ((paths, "scenario"), (wanted, "condition"), (seeds, "seed")):
        if not values:
            raise ManifestError(f"{path} lists no {what}")
        _unique(values, what, path)
    unknown = [c for c in wanted if c not in conditions]
    if unknown:
        raise ManifestError(f"{path}: condition {unknown[0]} has no harness")
    for seed in seeds:
        if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= MAX_SEED:
            raise ManifestError(f"{path}: seed {seed!r} is not in 0..{MAX_SEED}")
    scenarios = [load_scenario(Path(p)) for p in paths]
    _unique([s.scenario_id for s in scenarios], "scenario id", path)
    return [PlannedRun(c, s, seed) for seed in seeds for s in scenarios for c in wanted]


@dataclass
class BatchResult:
    planned: int
    complete: list[str] = field(default_factory=list)
    played: int = 0
    errors: list[str] = field(default_factory=list)
    pending: list[str] = field(default_factory=list)
    stopped: str | None = None

    @property
    def done(self) -> bool:
        return len(self.complete) == self.planned


class _StopBatch(Exception):
    pass


def _time(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


class _Batch:
    def __init__(
        self,
        runs_dir: Path,
        runner: Runner,
        ledger: Path,
        context: Doc,
        log: Callable[[str], None],
        clock: Callable[[], datetime],
    ) -> None:
        self.runs_dir = runs_dir
        self.staging = runs_dir / PENDING
        self.runner = runner
        self.ledger = ledger
        self.context = context
        self.say = log
        self.clock = clock

    def abort(self, path: Path, run: PlannedRun) -> Path | None:
        """Move a partial or unusable log to runs/aborted/, never over another."""
        if not path.exists():
            return None
        stamp = self.clock().strftime("%Y%m%dT%H%M%SZ")
        folder = run.log(self.runs_dir / ABORTED).parent
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / f"{run.seed}.{stamp}.jsonl"
        n = 1
        while target.exists():
            n += 1
            target = folder / f"{run.seed}.{stamp}-{n}.jsonl"
        os.replace(path, target)
        return target

    def write(self, run: PlannedRun, outcome: str, **fields: Any) -> None:
        entry = {
            "run_id": run.run_id,
            "condition": run.condition,
            "scenario_id": run.scenario.scenario_id,
            "seed": run.seed,
            "outcome": outcome,
            **{k: v.as_posix() if isinstance(v, Path) else v for k, v in fields.items()},
            **self.context,
        }
        self.ledger.parent.mkdir(parents=True, exist_ok=True)
        with self.ledger.open("a", encoding="utf-8") as out:
            out.write(json.dumps(entry, ensure_ascii=False) + "\n")
            out.flush()
            os.fsync(out.fileno())

    def resume(self, run: PlannedRun) -> bool:
        """True if the run is already complete; otherwise clear what is left of it."""
        inputs = len(run.scenario.scripted_inputs)
        final = run.log(self.runs_dir)
        if final.exists():
            records = read_log(final)
            if covers_script(records, inputs):
                return True
            aborted = self.abort(final, run)
            self.write(run, INTERRUPTED, records=len(records), aborted_log=aborted)
            self.say(f"{run.run_id}: incomplete log moved to {aborted}")
        staged = run.log(self.staging)
        if staged.exists():
            records = read_log(staged)
            aborted = self.abort(staged, run)
            self.write(run, INTERRUPTED, records=len(records), aborted_log=aborted)
            self.say(f"{run.run_id}: interrupted attempt moved to {aborted}")
        return False

    def attempt(self, run: PlannedRun, attempt: int, last: bool) -> str:
        """Play the run once. Returns the outcome; raises `_StopBatch`."""
        staged = run.log(self.staging)
        started = self.clock()
        retries = 0
        error: str | None = None
        try:
            retries = self.runner(run, self.staging)
        except KeyboardInterrupt:
            self.finish(run, attempt, started, INTERRUPTED, 0, "KeyboardInterrupt")
            raise
        except ModelConfigMismatch as exc:
            self.finish(run, attempt, started, MODEL_ERROR, 0, f"{type(exc).__name__}: {exc}")
            raise _StopBatch(str(exc)) from exc
        except ModelError as exc:
            error = f"{type(exc).__name__}: {exc}"
            self.finish(run, attempt, started, MODEL_ERROR, 0, error)
            if last:
                raise _StopBatch(error) from exc
            return MODEL_ERROR
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
            self.finish(run, attempt, started, ERROR, 0, error)
            return ERROR

        records = read_log(staged) if staged.exists() else []
        if retries:
            self.finish(run, attempt, started, TAINTED, retries, None)
            return TAINTED
        if not covers_script(records, len(run.scenario.scripted_inputs)):
            error = f"the log holds {len(records)} records, not one per scripted input"
            self.finish(run, attempt, started, ERROR, 0, error)
            return ERROR
        final = run.log(self.runs_dir)
        final.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staged, final)
        self.write(
            run,
            COMPLETE,
            attempt=attempt,
            started=_time(started),
            finished=_time(self.clock()),
            transport_retries=0,
            records=len(records),
            log=final,
        )
        return COMPLETE

    def finish(
        self,
        run: PlannedRun,
        attempt: int,
        started: datetime,
        outcome: str,
        retries: int,
        error: str | None,
    ) -> None:
        """Log an attempt that did not complete, and move its log aside."""
        staged = run.log(self.staging)
        records = len(read_log(staged)) if staged.exists() else 0
        aborted = self.abort(staged, run)
        self.write(
            run,
            outcome,
            attempt=attempt,
            started=_time(started),
            finished=_time(self.clock()),
            transport_retries=retries,
            records=records,
            error=error,
            aborted_log=aborted,
        )
        detail = f" ({retries} transport retries)" if outcome == TAINTED else ""
        first_line = f": {error.splitlines()[0]}" if error else ""
        self.say(f"{run.run_id}: attempt {attempt} {outcome}{detail}{first_line}")


def run_batch(
    plan: Iterable[PlannedRun],
    *,
    runs_dir: Path,
    runner: Runner,
    ledger: Path,
    max_attempts: int = MAX_ATTEMPTS,
    context: Doc | None = None,
    log: Callable[[str], None] = print,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> BatchResult:
    """Play every run of `plan` whose log is not complete yet. `context` is
    added to every ledger line (manifest, model, digest)."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    runs = list(plan)
    batch = _Batch(runs_dir, runner, ledger, context or {}, log, clock)
    result = BatchResult(planned=len(runs))
    for position, run in enumerate(runs, start=1):
        prefix = f"[{position}/{len(runs)}] {run.run_id}"
        if result.stopped is not None:
            result.pending.append(run.run_id)
            continue
        if batch.resume(run):
            result.complete.append(run.run_id)
            continue
        log(f"{prefix}: running")
        outcome = None
        try:
            for attempt in range(1, max_attempts + 1):
                result.played += 1
                outcome = batch.attempt(run, attempt, last=attempt == max_attempts)
                if outcome in (COMPLETE, ERROR):
                    break
        except _StopBatch as exc:
            result.stopped = str(exc)
            log(f"{prefix}: batch stopped: {exc}")
        if outcome == COMPLETE:
            result.complete.append(run.run_id)
            log(f"{prefix}: complete")
        elif outcome == ERROR:
            result.errors.append(run.run_id)
        else:
            result.pending.append(run.run_id)
    return result
