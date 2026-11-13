"""Metrics M1 to M6 (CLAUDE.md section 10.4), computed from the audit logs.

    python -m adm.eval.metrics m2 --checksums experiments/main_grid.sha256 \\
        --doc docs/m2_tool_calls.md

Only M2 is here so far (WBS 10.3); the others join as subcommands. The module
reads logs and never calls the model or imports orchestration
(docs/conventions.md section 1).

**The dataset** is the runs `experiments/main_grid.json` plans, read from
`runs/`. Every planned log must be there, and with `--checksums` every one must
match `experiments/main_grid.sha256`, the bytes the 9.3 integrity check passed
(decision 60). Anything else stops the command: a metric of the wrong data is
worse than none.

**M2** is condition D only, since A to C have no tool phase. Per turn (one audit
record, failed turns included):

- **Rejected turn**: at least one toolcall attempt failed, that is a
  `validation` entry with `ok: false`, either a rejection envelope or an
  unparseable reply. A `{"tool": null}` reply is not a rejection: it is valid,
  and the first one of a turn is re-prompted by design (decision 32).
- **Recovered turn**: a rejected turn whose `turn_failure` is null, so the retry
  budget did not run out. It either executed a call or ended narration-only
  after a `{"tool": null}` reply; both are counted and shown apart.

The headline **invalid tool-call rate** is rejected turns over turns; the
**rejected-attempt rate**, every failed attempt over turns, is given beside it
and can exceed 1. The **recovery rate** is recovered turns over rejected turns.
Pooled rates are ratios of sums over all runs, so a long run weighs more than a
short one, as its turns do.

**Intervals** are 95% percentile bootstraps over whole runs, 10,000 resamples,
stratified by condition (CLAUDE.md section 10.5). The bootstrap's RNG is one
`random.Random(BOOTSTRAP_SEED)` per interval, so a report is reproducible. It
is not game dice, so invariant 3 does not cover it; this is the one module
outside `engine/dice.py` allowed to import `random` (tests/test_boundaries.py).
"""

from __future__ import annotations

import json
import math
import random
from collections import Counter
from collections.abc import Callable, Hashable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Any, TypeVar

import typer

from adm.engine.audit import log_path, read_log, run_id, turn_failure_counts
from adm.eval.checker import RunKey
from adm.eval.integrity import file_sha256, load_plan, read_checksums

Doc = dict[str, Any]
T = TypeVar("T")

RESAMPLES = 10_000
BOOTSTRAP_SEED = 20261101  # the day the analysis was fixed (CLAUDE.md section 10.5)
CONFIDENCE = 0.95
CONDITION = "D"
RESULTS_START = "<!-- results:start -->"
RESULTS_END = "<!-- results:end -->"


# --- the bootstrap ------------------------------------------------------------


def percentile(values: Sequence[float], q: float) -> float:
    """The `q` quantile of `values`, interpolated linearly between order
    statistics (numpy's default)."""
    ordered = sorted(values)
    pos = q * (len(ordered) - 1)
    low = math.floor(pos)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (pos - low)


def bootstrap(
    units: Sequence[T],
    statistic: Callable[[Sequence[T]], float | None],
    *,
    strata: Callable[[T], Hashable] | None = None,
    resamples: int = RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
    confidence: float = CONFIDENCE,
) -> tuple[float, float] | None:
    """A percentile bootstrap interval of `statistic` over `units` (whole runs).

    Each resample draws, with replacement, as many units from each stratum as it
    holds, so a stratum's size never changes. A resample where the statistic is
    undefined (`None`, e.g. a rate with nothing to divide by) is skipped; if all
    are, there is no interval."""
    groups: dict[Hashable, list[T]] = {}
    for unit in units:
        groups.setdefault(strata(unit) if strata else None, []).append(unit)
    rng = random.Random(seed)
    values = []
    for _ in range(resamples):
        sample = [g[rng.randrange(len(g))] for g in groups.values() for _ in g]
        value = statistic(sample)
        if value is not None:
            values.append(value)
    if not values:
        return None
    tail = (1 - confidence) / 2
    return percentile(values, tail), percentile(values, 1 - tail)


# --- M2 ------------------------------------------------------------------------


@dataclass(frozen=True)
class RunM2:
    """The M2 counts of one condition D run."""

    key: RunKey
    turns: int
    attempts: int
    rejected_attempts: int
    rejected_turns: int
    recovered_executed: int
    recovered_narration_only: int
    first_attempt_null: int
    turn_failures: dict[str, int] = field(default_factory=dict)
    codes: dict[str, int] = field(default_factory=dict)
    recovered_attempts: dict[int, int] = field(default_factory=dict)

    @property
    def scenario_id(self) -> str:
        return self.key[1]

    @property
    def recovered_turns(self) -> int:
        return self.recovered_executed + self.recovered_narration_only

    @property
    def failed_turns(self) -> int:
        return sum(self.turn_failures.values())


def _code(entry: Doc) -> str:
    return entry.get("rejection_code") or entry.get("failure") or "unknown"


def m2_run(key: RunKey, records: Sequence[Doc]) -> RunM2:
    """Count one run's attempts, rejections and recoveries from its log."""
    codes: Counter[str] = Counter()
    attempts_used: Counter[int] = Counter()
    rejected_turns = executed = narration_only = first_null = 0
    for r in records:
        attempts = r["validation"]
        failed = [v for v in attempts if not v["ok"]]
        codes.update(_code(v) for v in failed)
        first_null += bool(attempts) and attempts[0]["ok"] and attempts[0].get("tool") is None
        if not failed:
            continue
        rejected_turns += 1
        if r["turn_failure"] is None:
            attempts_used[len(attempts)] += 1
            if r["executed_call"] is None:
                narration_only += 1
            else:
                executed += 1
    return RunM2(
        key=key,
        turns=len(records),
        attempts=sum(len(r["validation"]) for r in records),
        rejected_attempts=sum(codes.values()),
        rejected_turns=rejected_turns,
        recovered_executed=executed,
        recovered_narration_only=narration_only,
        first_attempt_null=first_null,
        turn_failures=dict(turn_failure_counts(records)),
        codes=dict(codes),
        recovered_attempts=dict(sorted(attempts_used.items())),
    )


def _ratio(numerator: str, denominator: str) -> Callable[[Sequence[RunM2]], float | None]:
    def rate(runs: Sequence[RunM2]) -> float | None:
        den = sum(getattr(r, denominator) for r in runs)
        return sum(getattr(r, numerator) for r in runs) / den if den else None

    return rate


# name -> (numerator, denominator), both RunM2 attributes
RATES = {
    "rejected_turn_rate": ("rejected_turns", "turns"),
    "rejected_attempt_rate": ("rejected_attempts", "turns"),
    "recovery_rate": ("recovered_turns", "rejected_turns"),
}
TOTALS = (
    "turns",
    "attempts",
    "rejected_attempts",
    "rejected_turns",
    "recovered_turns",
    "recovered_executed",
    "recovered_narration_only",
    "failed_turns",
    "first_attempt_null",
)


def _sum_counts(counts: Sequence[Mapping[Any, int]]) -> Counter[Any]:
    total: Counter[Any] = Counter()
    for c in counts:
        total.update(c)
    return total


def _by_count(counts: Counter[str]) -> dict[str, int]:
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))


def m2(runs: Sequence[RunM2], *, resamples: int = RESAMPLES, seed: int = BOOTSTRAP_SEED) -> Doc:
    """The pooled M2 figures with their bootstrap intervals, the rejections by
    code, the failures by kind and a row per scenario."""
    rates = {}
    for name, (num, den) in RATES.items():
        stat = _ratio(num, den)
        interval = bootstrap(runs, stat, strata=lambda r: r.key[0], resamples=resamples, seed=seed)
        rates[name] = {
            "value": stat(runs),
            "interval": list(interval) if interval else None,
            "numerator": sum(getattr(r, num) for r in runs),
            "denominator": sum(getattr(r, den) for r in runs),
        }
    scenarios: dict[str, list[RunM2]] = {}
    for r in runs:
        scenarios.setdefault(r.scenario_id, []).append(r)
    return {
        "bootstrap": {
            "resamples": resamples,
            "seed": seed,
            "confidence": CONFIDENCE,
            "unit": "run",
        },
        "runs": len(runs),
        "totals": {name: sum(getattr(r, name) for r in runs) for name in TOTALS},
        "rates": rates,
        "recovered_attempts": {
            str(k): v for k, v in sorted(_sum_counts([r.recovered_attempts for r in runs]).items())
        },
        "codes": _by_count(_sum_counts([r.codes for r in runs])),
        "turn_failures": _by_count(_sum_counts([r.turn_failures for r in runs])),
        "scenarios": [
            {
                "scenario_id": sid,
                "runs": len(group),
                **{name: sum(getattr(r, name) for r in group) for name in TOTALS[:5]},
                "failed_turns": sum(r.failed_turns for r in group),
                "rejected_turn_rate": _ratio("rejected_turns", "turns")(group),
                "recovery_rate": _ratio("recovered_turns", "rejected_turns")(group),
            }
            for sid, group in scenarios.items()
        ],
    }


# --- the dataset ---------------------------------------------------------------


class DatasetError(ValueError):
    """The logs on disk are not the dataset the manifest and checksums name."""


def load_d_runs(runs_dir: Path, manifest: Path, checksums: Path | None) -> dict[RunKey, list[Doc]]:
    """The condition D logs `manifest` plans, in plan order, checked against a
    `sha256sum` file of the dataset when one is given."""
    planned = [key for key in load_plan(manifest)[0] if key[0] == CONDITION]
    paths = {key: log_path(runs_dir, *key) for key in planned}
    missing = [run_id(*key) for key, path in paths.items() if not path.is_file()]
    if missing:
        raise DatasetError(f"No log for planned runs: {', '.join(missing)}")
    if checksums is not None:
        expected = read_checksums(checksums)
        errors = []
        for path in paths.values():
            name = path.relative_to(runs_dir).as_posix()
            if name not in expected:
                errors.append(f"{path.as_posix()}: not in the checksum file")
            elif file_sha256(path) != expected[name]:
                errors.append(f"{path.as_posix()}: sha256 differs from the checksum file")
        if errors:
            raise DatasetError("\n".join(errors))
    return {key: read_log(path) for key, path in paths.items()}


# --- the report ------------------------------------------------------------------


def _pct(value: float | None) -> str:
    return "–" if value is None else f"{value:.1%}"


def _interval(rate: Doc) -> str:
    if rate["interval"] is None:
        return "–"
    low, high = rate["interval"]
    return f"{_pct(low)} to {_pct(high)}"


LABELS = {
    "rejected_turn_rate": "**Invalid tool-call rate** (rejected turns / turns)",
    "rejected_attempt_rate": "Rejected attempts / turns",
    "recovery_rate": "**Recovery rate** (recovered / rejected turns)",
}


def render_m2(report: Doc) -> str:
    """The results block of docs/m2_tool_calls.md."""
    t, b = report["totals"], report["bootstrap"]
    rates = [
        f"| {LABELS[name]} | {rate['numerator']} / {rate['denominator']} | "
        f"{_pct(rate['value'])} | {_interval(rate)} |"
        for name, rate in report["rates"].items()
    ]
    used = report["recovered_attempts"]
    scenarios = [
        f"| {s['scenario_id']} | {s['runs']} | {s['turns']} | {s['rejected_turns']} | "
        f"{_pct(s['rejected_turn_rate'])} | {s['recovered_turns']} | "
        f"{_pct(s['recovery_rate'])} | {s['failed_turns']} |"
        for s in report["scenarios"]
    ]
    return "\n".join(
        [
            f"Condition D, {report['runs']} runs, {t['turns']} turns, {t['attempts']} toolcall "
            f"attempts. Intervals: {b['confidence']:.0%} percentile bootstrap over whole runs, "
            f"{b['resamples']:,} resamples, seed {b['seed']}.",
            "",
            "### Rates",
            "",
            "| Rate | Count | Value | 95% interval |",
            "|---|---|---|---|",
            *rates,
            "",
            "### How rejected turns ended",
            "",
            "| Ending | Turns |",
            "|---|---|",
            f"| Recovered, a call executed | {t['recovered_executed']} |",
            f'| Recovered, narration-only after a `{{"tool": null}}` reply '
            f"| {t['recovered_narration_only']} |",
            f"| Failed: retry budget exhausted | {t['failed_turns']} |",
            f"| **Rejected turns** | **{t['rejected_turns']}** |",
            "",
            "Attempts used by recovered turns: "
            + ", ".join(f"{k} attempts {v}" for k, v in used.items())
            + ". "
            f'Turns whose first reply was `{{"tool": null}}` (re-prompted, not a rejection): '
            f"{t['first_attempt_null']}.",
            "",
            "### Rejections by code, over all attempts",
            "",
            "| Code | Attempts |",
            "|---|---|",
            *(f"| `{code}` | {n} |" for code, n in report["codes"].items()),
            "",
            "### Failed turns by kind",
            "",
            "| `turn_failure` | Turns |",
            "|---|---|",
            *(f"| `{kind}` | {n} |" for kind, n in report["turn_failures"].items()),
            "",
            "### Per scenario",
            "",
            "| Scenario | Runs | Turns | Rejected | Rate | Recovered | Recovery | Failed |",
            "|---|---|---|---|---|---|---|---|",
            *scenarios,
        ]
    )


def write_results(doc: Path, block: str) -> None:
    text = doc.read_text(encoding="utf-8")
    start, end = text.index(RESULTS_START), text.index(RESULTS_END)
    doc.write_text(
        text[: start + len(RESULTS_START)] + "\n" + block + "\n" + text[end:], encoding="utf-8"
    )


# --- the command ---------------------------------------------------------------

app = typer.Typer(add_completion=False)


@app.callback()
def main() -> None:
    """Compute the metrics of CLAUDE.md section 10.4 from the audit logs."""


@app.command("m2")
def m2_command(
    runs: Annotated[Path, typer.Option(help="The runs directory.")] = Path("runs"),
    manifest: Annotated[Path, typer.Option(help="The batch manifest of the dataset.")] = Path(
        "experiments/main_grid.json"
    ),
    checksums: Annotated[
        Path | None, typer.Option(help="sha256sum file the logs must match (decision 60).")
    ] = None,
    out: Annotated[Path, typer.Option(help="Where the report is written as JSON.")] = Path(
        "results/m2.json"
    ),
    doc: Annotated[
        Path | None, typer.Option(help="Document whose results block is rewritten.")
    ] = None,
    resamples: Annotated[int, typer.Option(help="Bootstrap resamples.", min=1)] = RESAMPLES,
) -> None:
    """M2: invalid tool-call and recovery rates, condition D (WBS 10.3)."""
    try:
        logs = load_d_runs(runs, manifest, checksums)
    except DatasetError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    report = m2([m2_run(key, records) for key, records in logs.items()], resamples=resamples)
    report = {
        "dataset": {
            "manifest": manifest.as_posix(),
            "checksums": checksums.as_posix() if checksums else None,
        },
        **report,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    block = render_m2(report)
    if doc is not None:
        write_results(doc, block)
    typer.echo(block)


if __name__ == "__main__":
    app()
