"""Metrics M1 to M6 (CLAUDE.md section 10.4), computed from the audit logs.

    python -m adm.eval.metrics m2 --checksums experiments/main_grid.sha256 \\
        --doc docs/m2_tool_calls.md

    python -m adm.eval.metrics m4 --checksums experiments/main_grid.sha256 \\
        --doc docs/m4_rule_violations.md [--labels results/m1_labels.jsonl]
    python -m adm.eval.metrics m6 --checksums experiments/main_grid.sha256 \\
        --doc docs/m6_latency.md

M2 (WBS 10.3), M4 and M6 (WBS 10.4) are here; the others join as subcommands.
The module reads logs and never calls the model or imports orchestration
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

**M4** is all four conditions (decision 56): per narrated turn (failed D turns
are not scored, as in the checker), the `rule_violation` and `state_audit`
candidates of `adm/eval/checker.py`. M4 is high-confidence `rule_violation` plus
`state_audit` per 100 narrated turns; low-confidence candidates are given
apart. With `--labels`, one annotator's 9.5 labels on the M1 sample (decision
61) give the confirmed rule breaks: `RULE` candidates confirmed plus `RULE`
breaks added, per 100 narrated turns, and the precision of the candidates shown.

**M6** is all four conditions: seconds per turn is `turn_latency_ms / 1000` over
every record, failed turns included, since the player waited for them too.
Tokens per second is `completion_tokens / eval_ms` per model call, a mean over
calls, as in docs/smoke_runs.md; a call with no `eval_ms` is left out and
counted. The target is p95 under 10 s per turn in D (CLAUDE.md section 10.5),
met only when the p95 and its interval's upper bound are both under it.

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
from typing import Annotated, Any, TypeVar, get_args

import typer

from adm.engine.audit import log_path, read_log, run_id, turn_failure_counts
from adm.engine.scenario import Scenario
from adm.eval.checker import RunKey, Turn, check_turn, rule_violation, state_audit, turns
from adm.eval.integrity import file_sha256, load_plan, read_checksums
from adm.eval.m1 import draw_runs
from adm.eval.rules import StateRule

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


# --- shared helpers ------------------------------------------------------------


def _per100(numerator: str, denominator: str) -> Callable[[Sequence[Any]], float | None]:
    ratio = _ratio(numerator, denominator)

    def rate(runs: Sequence[Any]) -> float | None:
        value = ratio(runs)
        return None if value is None else 100 * value

    return rate


def _rate_doc(
    runs: Sequence[Any],
    numerator: str,
    denominator: str,
    *,
    resamples: int,
    seed: int,
    strata: Callable[[Any], Hashable] | None = None,
) -> Doc:
    """A rate per 100 with its run-level bootstrap interval and its counts."""
    stat = _per100(numerator, denominator)
    interval = bootstrap(runs, stat, strata=strata, resamples=resamples, seed=seed)
    return {
        "value": stat(runs),
        "interval": list(interval) if interval else None,
        "numerator": sum(getattr(r, numerator) for r in runs),
        "denominator": sum(getattr(r, denominator) for r in runs),
    }


def _bootstrap_doc(resamples: int, seed: int) -> Doc:
    return {"resamples": resamples, "seed": seed, "confidence": CONFIDENCE, "unit": "run"}


def _by_condition(runs: Sequence[Any]) -> dict[str, list[Any]]:
    """Runs grouped by condition (their key's first part), conditions sorted."""
    groups: dict[str, list[Any]] = {}
    for r in runs:
        groups.setdefault(r.key[0], []).append(r)
    return dict(sorted(groups.items()))


# --- M4 ------------------------------------------------------------------------

RULE_KINDS = get_args(StateRule)
M4_CHECKS = (rule_violation, state_audit)


@dataclass(frozen=True)
class RunM4:
    """The M4 counts of one run: its narrated turns and its `RULE` candidates.
    `kinds` maps each rule to its counts as `rule_violation` high, low and
    `state_audit`."""

    key: RunKey
    narrated: int
    high: int
    low: int
    state_audit: int
    kinds: dict[str, dict[str, int]] = field(default_factory=dict)

    @property
    def m4(self) -> int:
        return self.high + self.state_audit


def m4_run(key: RunKey, narrated: Sequence[Turn]) -> RunM4:
    """Count one run's `RULE` candidates over its narrated turns."""
    kinds: dict[str, Counter[str]] = {}
    for turn in narrated:
        for c in check_turn(turn, M4_CHECKS):
            column = "state_audit" if c["check"] == "state_audit" else c["confidence"]
            kinds.setdefault(c["kind"], Counter())[column] += 1
    total = _sum_counts(list(kinds.values()))
    return RunM4(
        key=key,
        narrated=len(narrated),
        high=total["high"],
        low=total["low"],
        state_audit=total["state_audit"],
        kinds={k: dict(sorted(v.items())) for k, v in sorted(kinds.items())},
    )


@dataclass(frozen=True)
class RunLabels:
    """One annotator's `RULE` labels on one run of the M1 sample: the checker's
    candidates shown and confirmed, by confidence, and the rule breaks added."""

    key: RunKey
    narrated: int
    shown_high: int
    shown_low: int
    confirmed_high: int
    confirmed_low: int
    added: int

    @property
    def shown(self) -> int:
        return self.shown_high + self.shown_low

    @property
    def confirmed_candidates(self) -> int:
        return self.confirmed_high + self.confirmed_low

    @property
    def confirmed(self) -> int:
        return self.confirmed_candidates + self.added


def read_labels(path: Path, annotator: str) -> dict[tuple[str, int], Doc]:
    """One annotator's M1 label lines, by run id and input index."""
    labels: dict[tuple[str, int], Doc] = {}
    with path.open(encoding="utf-8") as lines:
        for line in lines:
            if not line.strip():
                continue
            doc = json.loads(line)
            if doc["annotator"] != annotator:
                continue
            key = (doc["run_id"], int(doc["input_index"]))
            if key in labels:
                raise DatasetError(f"{path.as_posix()}: two lines for {key[0]} input {key[1]}")
            labels[key] = doc
    return labels


def label_runs(
    sample: Mapping[RunKey, Sequence[Turn]], labels: Mapping[tuple[str, int], Doc]
) -> list[RunLabels]:
    """The `RULE` labels of every sample run. Every narrated turn of the sample
    must have a label line: a metric of a part-annotated sample is refused."""
    if not sample:
        raise DatasetError("No run of the M1 sample is in the dataset (decision 61).")
    missing: list[str] = []
    counted: list[RunLabels] = []
    for key, narrated in sample.items():
        shown: Counter[str] = Counter()
        confirmed: Counter[str] = Counter()
        added = 0
        for turn in narrated:
            line = labels.get((str(turn.record["run_id"]), int(turn.record["input_index"])))
            if line is None:
                missing.append(f"{turn.record['run_id']} input {turn.record['input_index']}")
                continue
            for c in line["candidates"]:
                if c["category"] == "RULE":
                    shown[c["confidence"]] += 1
                    confirmed[c["confidence"]] += bool(c["confirmed"])
            added += sum(1 for a in line["added"] if a["category"] == "RULE")
        counted.append(
            RunLabels(
                key=key,
                narrated=len(narrated),
                shown_high=shown["high"],
                shown_low=shown["low"],
                confirmed_high=confirmed["high"],
                confirmed_low=confirmed["low"],
                added=added,
            )
        )
    if missing:
        more = f" and {len(missing) - 5} more" if len(missing) > 5 else ""
        head = ", ".join(missing[:5]) + more
        raise DatasetError(f"{len(missing)} sample turns have no label line: {head}")
    return counted


def _share(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def m4(
    runs: Sequence[RunM4],
    labelled: Sequence[RunLabels] | None = None,
    *,
    annotator: str | None = None,
    resamples: int = RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> Doc:
    """M4 per condition with its bootstrap interval, the candidates by rule and,
    given an annotator's labels on the M1 sample, the confirmed rule breaks."""
    options = {"resamples": resamples, "seed": seed}
    groups = _by_condition(runs)
    conditions = {
        c: {
            "runs": len(group),
            **{name: sum(getattr(r, name) for r in group) for name in M4_TOTALS},
            "m4": _rate_doc(group, "m4", "narrated", **options),
            "low_per_100": _per100("low", "narrated")(group),
        }
        for c, group in groups.items()
    }
    conditions["all"] = {
        "runs": len(runs),
        **{name: sum(getattr(r, name) for r in runs) for name in M4_TOTALS},
        "m4": _rate_doc(runs, "m4", "narrated", strata=lambda r: r.key[0], **options),
        "low_per_100": _per100("low", "narrated")(runs),
    }
    kinds = {
        kind: {
            c: dict(_sum_counts([r.kinds.get(kind, {}) for r in group]))
            for c, group in groups.items()
        }
        for kind in sorted({k for r in runs for k in r.kinds}, key=_kind_order)
    }
    return {
        "bootstrap": _bootstrap_doc(resamples, seed),
        "runs": len(runs),
        "conditions": conditions,
        "kinds": kinds,
        "labels": None if labelled is None else _labels_doc(labelled, annotator, options),
    }


M4_TOTALS = ("narrated", "high", "low", "state_audit", "m4")
LABEL_TOTALS = (
    "narrated",
    "shown_high",
    "shown_low",
    "confirmed_high",
    "confirmed_low",
    "added",
    "confirmed",
)


def _kind_order(kind: str) -> tuple[int, str]:
    return (RULE_KINDS.index(kind) if kind in RULE_KINDS else len(RULE_KINDS), kind)


def _labels_doc(labelled: Sequence[RunLabels], annotator: str | None, options: Doc) -> Doc:
    def row(group: Sequence[RunLabels], strata: Callable[[Any], Hashable] | None) -> Doc:
        t = {name: sum(getattr(r, name) for r in group) for name in LABEL_TOTALS}
        return {
            "runs": len(group),
            **t,
            "rate": _rate_doc(group, "confirmed", "narrated", strata=strata, **options),
            "precision_high": _share(t["confirmed_high"], t["shown_high"]),
            "precision_low": _share(t["confirmed_low"], t["shown_low"]),
        }

    conditions = {c: row(group, None) for c, group in _by_condition(labelled).items()}
    conditions["all"] = row(labelled, lambda r: r.key[0])
    return {"annotator": annotator, "runs": len(labelled), "conditions": conditions}


# --- M6 ------------------------------------------------------------------------

M6_TARGET_S = 10.0
M6_TARGET_CONDITION = "D"
PHASES = ("toolcall", "narration", "summary")


@dataclass(frozen=True)
class RunM6:
    """The M6 timings of one run: seconds per turn, every record, and tokens per
    second of each model call whose generation time was logged."""

    key: RunKey
    seconds: tuple[float, ...]
    rates: tuple[tuple[str, float], ...]
    zero_eval: int


def m6_run(key: RunKey, records: Sequence[Doc]) -> RunM6:
    """One run's seconds per turn (`turn_latency_ms`) and tokens per second per
    call (`completion_tokens / eval_ms`), skipping calls with no `eval_ms`."""
    rates: list[tuple[str, float]] = []
    zero = 0
    for r in records:
        for call in r["model_calls"]:
            if call["eval_ms"] > 0:
                rates.append((call["phase"], 1000 * call["completion_tokens"] / call["eval_ms"]))
            else:
                zero += 1
    return RunM6(
        key=key,
        seconds=tuple(r["turn_latency_ms"] / 1000 for r in records),
        rates=tuple(rates),
        zero_eval=zero,
    )


def _seconds(runs: Sequence[RunM6]) -> list[float]:
    return [s for r in runs for s in r.seconds]


def _mean(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _p95(runs: Sequence[RunM6]) -> float | None:
    seconds = _seconds(runs)
    return percentile(seconds, 0.95) if seconds else None


def _mean_seconds(runs: Sequence[RunM6]) -> float | None:
    return _mean(_seconds(runs))


def m6(runs: Sequence[RunM6], *, resamples: int = RESAMPLES, seed: int = BOOTSTRAP_SEED) -> Doc:
    """Seconds per turn (mean, p50, p95, max) and tokens per second (mean over
    calls, overall and per phase) per condition, the mean and p95 with their
    bootstrap intervals, and the p95 target of CLAUDE.md section 10.5."""
    conditions: dict[str, Doc] = {}
    for c, group in _by_condition(runs).items():
        seconds = _seconds(group)
        rates = [rate for r in group for rate in r.rates]
        mean_iv = bootstrap(group, _mean_seconds, resamples=resamples, seed=seed)
        p95_iv = bootstrap(group, _p95, resamples=resamples, seed=seed)
        conditions[c] = {
            "runs": len(group),
            "turns": len(seconds),
            "seconds": {
                "mean": _mean(seconds),
                "mean_interval": list(mean_iv) if mean_iv else None,
                "p50": percentile(seconds, 0.5) if seconds else None,
                "p95": _p95(group),
                "p95_interval": list(p95_iv) if p95_iv else None,
                "max": max(seconds) if seconds else None,
            },
            "tokens_per_second": {
                "calls": len(rates),
                "calls_without_eval_ms": sum(r.zero_eval for r in group),
                "mean": _mean([v for _, v in rates]),
                "phases": {
                    phase: {"calls": len(values), "mean": _mean(values)}
                    for phase in PHASES
                    if (values := [v for p, v in rates if p == phase])
                },
            },
        }
    target = None
    if M6_TARGET_CONDITION in conditions:
        s = conditions[M6_TARGET_CONDITION]["seconds"]
        upper = s["p95_interval"][1] if s["p95_interval"] else None
        target = {
            "condition": M6_TARGET_CONDITION,
            "limit_seconds": M6_TARGET_S,
            "p95": s["p95"],
            "p95_upper": upper,
            "met": s["p95"] is not None
            and s["p95"] < M6_TARGET_S
            and upper is not None
            and upper < M6_TARGET_S,
        }
    return {
        "bootstrap": _bootstrap_doc(resamples, seed),
        "runs": len(runs),
        "conditions": conditions,
        "target": target,
    }


# --- the dataset ---------------------------------------------------------------


class DatasetError(ValueError):
    """The logs on disk are not the dataset the manifest and checksums name."""


def load_planned_runs(
    runs_dir: Path,
    manifest: Path,
    checksums: Path | None,
    conditions: Sequence[str] = (CONDITION,),
) -> dict[RunKey, list[Doc]]:
    """The logs `manifest` plans in `conditions`, in plan order, checked against
    a `sha256sum` file of the dataset when one is given."""
    planned = [key for key in load_plan(manifest)[0] if key[0] in conditions]
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


def _num(value: float | None, digits: int = 2) -> str:
    return "–" if value is None else f"{value:.{digits}f}"


def _span(interval: Sequence[float] | None, digits: int = 2) -> str:
    if interval is None:
        return "–"
    low, high = interval
    return f"{_num(low, digits)} to {_num(high, digits)}"


def _bootstrap_line(b: Doc) -> str:
    return (
        f"Intervals: {b['confidence']:.0%} percentile bootstrap over whole runs, "
        f"{b['resamples']:,} resamples, seed {b['seed']}"
    )


def _label(condition: str) -> str:
    return "**All**" if condition == "all" else condition


def render_m4(report: Doc) -> str:
    """The results block of docs/m4_rule_violations.md."""
    conditions = report["conditions"]
    real = [c for c in conditions if c != "all"]
    rows = [
        f"| {_label(c)} | {d['runs']} | {d['narrated']} | {d['high']} | {d['state_audit']} | "
        f"**{_num(d['m4']['value'])}** | {_span(d['m4']['interval'])} | {d['low']} | "
        f"{_num(d['low_per_100'])} |"
        for c, d in conditions.items()
    ]
    kinds = [
        f"| `{kind}` | "
        + " | ".join(
            "{} / {} / {}".format(
                *(by_condition.get(c, {}).get(col, 0) for col in ("high", "low", "state_audit"))
            )
            for c in real
        )
        + " |"
        for kind, by_condition in report["kinds"].items()
    ]
    lines = [
        f"Conditions {', '.join(real)}, {report['runs']} runs, "
        f"{conditions['all']['narrated']} narrated turns. {_bootstrap_line(report['bootstrap'])}; "
        "the All row is stratified by condition.",
        "",
        "### M4 per condition",
        "",
        "M4 = (`rule_violation` high + `state_audit`) per 100 narrated turns (decision 56).",
        "",
        "| Condition | Runs | Narrated turns | `rule_violation` high | `state_audit` | "
        "**M4 per 100 turns** | 95% interval | `rule_violation` low | Low per 100 turns |",
        "|---|---|---|---|---|---|---|---|---|",
        *rows,
        "",
        "### Candidates by rule",
        "",
        "Each cell is `rule_violation` high / `rule_violation` low / `state_audit`.",
        "",
        f"| Rule | {' | '.join(real)} |",
        "|---|" + "---|" * len(real),
        *(kinds or [f"| none |{' – |' * len(real)}"]),
        "",
        "### Confirmed by the human pass (M1 sample)",
        "",
    ]
    labels = report["labels"]
    if labels is None:
        lines.append(
            "Not computed: run with `--labels results/m1_labels.jsonl` once the 9.5 labels "
            "are on this machine."
        )
        return "\n".join(lines)
    lines += [
        f"Annotator {labels['annotator']}, {labels['runs']} runs of the M1 sample (decision 61). "
        "Confirmed = `RULE` candidates the annotator confirmed plus `RULE` breaks added.",
        "",
        "| Condition | Runs | Narrated turns | Shown high / low | Confirmed high / low | Added | "
        "**Confirmed per 100 turns** | 95% interval | Precision high | Precision low |",
        "|---|---|---|---|---|---|---|---|---|---|",
        *(
            f"| {_label(c)} | {d['runs']} | {d['narrated']} | {d['shown_high']} / "
            f"{d['shown_low']} | {d['confirmed_high']} / {d['confirmed_low']} | {d['added']} | "
            f"**{_num(d['rate']['value'])}** | {_span(d['rate']['interval'])} | "
            f"{_pct(d['precision_high'])} | {_pct(d['precision_low'])} |"
            for c, d in labels["conditions"].items()
        ),
    ]
    return "\n".join(lines)


def render_m6(report: Doc) -> str:
    """The results block of docs/m6_latency.md."""
    conditions = report["conditions"]
    turns_total = sum(d["turns"] for d in conditions.values())
    seconds = [
        f"| {c} | {d['runs']} | {d['turns']} | {_num(s['mean'])} | {_span(s['mean_interval'])} | "
        f"{_num(s['p50'])} | **{_num(s['p95'])}** | {_span(s['p95_interval'])} | "
        f"{_num(s['max'])} |"
        for c, d in conditions.items()
        for s in [d["seconds"]]
    ]

    def phase(t: Doc, name: str) -> str:
        p = t["phases"].get(name)
        return "–" if p is None else f"{_num(p['mean'], 1)} ({p['calls']:,})"

    rates = [
        f"| {c} | {t['calls']:,} | **{_num(t['mean'], 1)}** | "
        + " | ".join(phase(t, name) for name in PHASES)
        + " |"
        for c, d in conditions.items()
        for t in [d["tokens_per_second"]]
    ]
    skipped = sum(d["tokens_per_second"]["calls_without_eval_ms"] for d in conditions.values())
    lines = [
        f"Conditions {', '.join(conditions)}, {report['runs']} runs, {turns_total} turns "
        f"(failed turns included). {_bootstrap_line(report['bootstrap'])}.",
        "",
    ]
    target = report["target"]
    if target is not None:
        verdict = "met" if target["met"] else "not met"
        lines += [
            f"**Target: p95 under {target['limit_seconds']:.0f} s per turn in condition "
            f"{target['condition']}. p95 = {_num(target['p95'])} s, upper 95% bound "
            f"{_num(target['p95_upper'])} s: {verdict}.**",
            "",
        ]
    lines += [
        "### Seconds per turn",
        "",
        "| Condition | Runs | Turns | Mean | 95% interval | p50 | **p95** | 95% interval | Max |",
        "|---|---|---|---|---|---|---|---|---|",
        *seconds,
        "",
        "### Tokens per second",
        "",
        "Mean over model calls of `completion_tokens / eval_ms`; calls per cell in brackets.",
        "",
        f"| Condition | Calls | Mean | {' | '.join(n.capitalize() for n in PHASES)} |",
        "|---|---|---|---|---|---|",
        *rates,
        "",
        f"Calls with no `eval_ms` logged, left out: {skipped}.",
    ]
    return "\n".join(lines)


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
        logs = load_planned_runs(runs, manifest, checksums)
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


RunsOpt = Annotated[Path, typer.Option(help="The runs directory.")]
ManifestOpt = Annotated[Path, typer.Option(help="The batch manifest of the dataset.")]
ChecksumsOpt = Annotated[
    Path | None, typer.Option(help="sha256sum file the logs must match (decision 60).")
]
DocOpt = Annotated[Path | None, typer.Option(help="Document whose results block is rewritten.")]
ResamplesOpt = Annotated[int, typer.Option(help="Bootstrap resamples.", min=1)]
ALL_CONDITIONS = ("A", "B", "C", "D")


def _load(runs: Path, manifest: Path, checksums: Path | None) -> dict[RunKey, list[Doc]]:
    try:
        return load_planned_runs(runs, manifest, checksums, ALL_CONDITIONS)
    except DatasetError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc


def _emit(
    report: Doc, block: str, manifest: Path, checksums: Path | None, out: Path, doc: Path | None
) -> None:
    report = {
        "dataset": {
            "manifest": manifest.as_posix(),
            "checksums": checksums.as_posix() if checksums else None,
        },
        **report,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if doc is not None:
        write_results(doc, block)
    typer.echo(block)


@app.command("m4")
def m4_command(
    runs: RunsOpt = Path("runs"),
    manifest: ManifestOpt = Path("experiments/main_grid.json"),
    checksums: ChecksumsOpt = None,
    labels: Annotated[
        Path | None, typer.Option(help="M1 label file (9.5) for the confirmed table.")
    ] = None,
    annotator: Annotated[str, typer.Option(help="Whose M1 labels are counted.")] = "SD",
    out: Annotated[Path, typer.Option(help="Where the report is written as JSON.")] = Path(
        "results/m4.json"
    ),
    doc: DocOpt = None,
    resamples: ResamplesOpt = RESAMPLES,
) -> None:
    """M4: rule-violation rate per condition, all four conditions (WBS 10.4)."""
    logs = _load(runs, manifest, checksums)
    scenarios: dict[str, Scenario] = load_plan(manifest)[1]
    narrated = {key: list(turns(scenarios[key[1]], records)) for key, records in logs.items()}
    labelled = None
    if labels is not None:
        try:
            sample = {key: narrated[key] for key in draw_runs(list(narrated))}
            labelled = label_runs(sample, read_labels(labels, annotator))
        except DatasetError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(1) from exc
    report = m4(
        [m4_run(key, ts) for key, ts in narrated.items()],
        labelled,
        annotator=annotator if labelled is not None else None,
        resamples=resamples,
    )
    _emit(report, render_m4(report), manifest, checksums, out, doc)


@app.command("m6")
def m6_command(
    runs: RunsOpt = Path("runs"),
    manifest: ManifestOpt = Path("experiments/main_grid.json"),
    checksums: ChecksumsOpt = None,
    out: Annotated[Path, typer.Option(help="Where the report is written as JSON.")] = Path(
        "results/m6.json"
    ),
    doc: DocOpt = None,
    resamples: ResamplesOpt = RESAMPLES,
) -> None:
    """M6: seconds per turn and tokens per second, all four conditions (WBS 10.4)."""
    logs = _load(runs, manifest, checksums)
    report = m6([m6_run(key, records) for key, records in logs.items()], resamples=resamples)
    _emit(report, render_m6(report), manifest, checksums, out, doc)


if __name__ == "__main__":
    app()
