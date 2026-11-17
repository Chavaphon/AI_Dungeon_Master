"""M1 growth against turn index, with intervals (WBS 10.2; RQ2).

    python -m adm.eval.m1_growth --labels results/m1_labels.jsonl \\
        --checksums experiments/main_grid.sha256 --doc docs/m1_growth.md

**The data** are those of 10.1 (`adm/eval/m1_rates.py`): the 9.5 M1 sample of
64 whole runs, the first annotator's labels, checked the same way, and the same
count per turn (confirmed candidates plus added labels in the four rubric
categories; `RULE` is M4). A failed condition D turn is not narrated by the
model and is not in the sample.

**The turn index** is the scripted position, `input_index + 1`, from 1 to 50 in
a long session. It names the same scripted input in every condition, so a failed
D turn does not shift D's later turns against A's (decision 23). `turn_number`
differs from it only in D, after a failed turn.

**The slope** of a condition is the least-squares slope of the per-turn
divergence count on the position, pooled over the turns of its runs. It is
reported as the change in the rate (divergences per 100 turns) for every 10
turns played: 1,000 x the slope per turn. **RQ2** (CLAUDE.md section 10.5) is
carried by the four long sessions, 4 runs per condition, all 50 inputs long. A
condition's divergences grow with the session when its slope's 95% interval lies
above 0. The difference from A (B-A, C-A, D-A) is given with its interval.

**Intervals** are the shared percentile bootstrap (`metrics.bootstrap`): whole
runs, 10,000 resamples, stratified by condition, seed 20261101. A difference's
resample draws each condition's runs separately.

**Fixed beforehand**, with the rest: the long-session slopes also without
`PHANTOM` (as in 10.1); the slopes of the 12 short scenarios as context, with no
interval, since their scripts differ by position; and the long-session rate in
five bins of 10 positions, for the growth-curve figure (10.6).
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any

import typer

from adm.engine.audit import run_id
from adm.eval import m1
from adm.eval.annotate import load_scenarios
from adm.eval.checker import RunKey
from adm.eval.integrity import file_sha256
from adm.eval.m1_agreement import label_counts, read_lines
from adm.eval.m1_rates import BASELINE, SENSITIVITY, LabelError, load_sample_logs, runs_m1
from adm.eval.metrics import (
    BOOTSTRAP_SEED,
    CONFIDENCE,
    RESAMPLES,
    DatasetError,
    bootstrap,
    write_results,
)
from adm.eval.rubric_pilot import RUBRIC

Doc = dict[str, Any]

PER_TURNS = 10  # the slope is reported per 10 turns played
SCALE = 100 * PER_TURNS  # ... of the rate per 100 turns
BINS = ((1, 10), (11, 20), (21, 30), (31, 40), (41, 50))


@dataclass(frozen=True)
class RunTurns:
    """The narrated turns of one sampled run: position and divergence counts."""

    key: RunKey
    points: tuple[tuple[int, Mapping[str, int]], ...]

    @property
    def condition(self) -> str:
        return self.key[0]

    @property
    def long(self) -> bool:
        return self.key[1].startswith("long")


# --- the data ------------------------------------------------------------------


def runs_turns(
    sample: Sequence[RunKey], items: Sequence[Any], lines: Sequence[Doc], annotator: str
) -> list[RunTurns]:
    """Per sampled run, each narrated turn's position and counts. The labels are
    checked exactly as 10.1 checks them (`m1_rates.runs_m1`)."""
    runs_m1(sample, items, lines, annotator)  # raises LabelError
    mine = {line["turn_id"]: line for line in lines if line.get("annotator") == annotator}
    keys = {run_id(*key): key for key in sample}
    by_run: dict[str, list[tuple[int, Mapping[str, int]]]] = {rid: [] for rid in keys}
    for item in items:
        counts = label_counts(mine[item.turn_id])
        by_run[item.run_id].append((item.input_index + 1, {c: counts.get(c, 0) for c in RUBRIC}))
    return sorted(
        (RunTurns(keys[rid], tuple(points)) for rid, points in by_run.items()),
        key=lambda r: r.key,
    )


# --- the figures ---------------------------------------------------------------


def _y(counts: Mapping[str, int], categories: Sequence[str]) -> int:
    return sum(counts.get(c, 0) for c in categories)


def slope(categories: Sequence[str] = RUBRIC) -> Callable[[Sequence[RunTurns]], float | None]:
    """The pooled least-squares slope of divergences per turn on position, as
    the change in the rate per 100 turns for every 10 turns played."""

    def stat(runs: Sequence[RunTurns]) -> float | None:
        xs: list[int] = []
        ys: list[int] = []
        for r in runs:
            for x, counts in r.points:
                xs.append(x)
                ys.append(_y(counts, categories))
        if len(xs) < 2:
            return None
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        sxx = sum((x - mx) ** 2 for x in xs)
        if not sxx:
            return None
        sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
        return SCALE * sxy / sxx

    return stat


def difference(
    condition: str, categories: Sequence[str] = RUBRIC
) -> Callable[[Sequence[RunTurns]], float | None]:
    """The slope of `condition` minus the slope of the baseline."""
    of = slope(categories)

    def stat(runs: Sequence[RunTurns]) -> float | None:
        top = of([r for r in runs if r.condition == condition])
        bottom = of([r for r in runs if r.condition == BASELINE])
        return None if top is None or bottom is None else top - bottom

    return stat


def binned(runs: Sequence[RunTurns]) -> list[Doc]:
    """The rate per 100 turns in each bin of positions, pooled over `runs`."""
    out = []
    for low, high in BINS:
        turns = divergences = 0
        for r in runs:
            for x, counts in r.points:
                if low <= x <= high:
                    turns += 1
                    divergences += _y(counts, RUBRIC)
        out.append(
            {
                "positions": [low, high],
                "turns": turns,
                "divergences": divergences,
                "rate": 100 * divergences / turns if turns else None,
            }
        )
    return out


def _with_interval(
    runs: Sequence[RunTurns], stat: Callable[[Sequence[RunTurns]], float | None], **kw: Any
) -> Doc:
    interval = bootstrap(runs, stat, strata=lambda r: r.condition, **kw)
    return {"value": stat(runs), "interval": list(interval) if interval else None}


def growth_report(
    runs: Sequence[RunTurns], *, resamples: int = RESAMPLES, seed: int = BOOTSTRAP_SEED
) -> Doc:
    """RQ2: the long-session slope per condition, the differences from A, the
    sensitivity without `PHANTOM`, the short-scenario context and the bins."""
    kw = {"resamples": resamples, "seed": seed}
    conditions = sorted({r.condition for r in runs})
    long = {c: [r for r in runs if r.condition == c and r.long] for c in conditions}
    short = {c: [r for r in runs if r.condition == c and not r.long] for c in conditions}
    per_condition = {}
    for c in conditions:
        s = _with_interval(long[c], slope(), **kw)
        low_high = s["interval"]
        per_condition[c] = {
            "long_runs": len(long[c]),
            "long_turns": sum(len(r.points) for r in long[c]),
            "slope": s,
            "grows": low_high is not None and low_high[0] > 0,
            "slope_without_phantom": _with_interval(long[c], slope(SENSITIVITY), **kw),
            "short_runs": len(short[c]),
            "short_slope": slope()(short[c]),
            "bins": binned(long[c]),
        }
    differences = {}
    for c in conditions:
        if c == BASELINE or BASELINE not in long:
            continue
        pair = long[c] + long[BASELINE]
        d = _with_interval(pair, difference(c), **kw)
        differences[c] = {
            "all": d,
            "excludes_zero": d["interval"] is not None
            and (d["interval"][0] > 0 or d["interval"][1] < 0),
            "without_phantom": _with_interval(pair, difference(c, SENSITIVITY), **kw),
        }
    return {
        "bootstrap": {
            "resamples": resamples,
            "seed": seed,
            "confidence": CONFIDENCE,
            "unit": "run",
        },
        "index": "input_index + 1",
        "slope_unit": f"change in divergences per 100 turns per {PER_TURNS} turns played",
        "conditions": per_condition,
        "differences": differences,
        "per_run": [
            {
                "run_id": run_id(*r.key),
                "turns": len(r.points),
                "slope": slope()([r]),
            }
            for r in runs
        ],
    }


# --- the report ----------------------------------------------------------------


def _num(value: float | None, digits: int = 1) -> str:
    return "–" if value is None else f"{value:+.{digits}f}"


def _plain(value: float | None, digits: int = 1) -> str:
    return "–" if value is None else f"{value:.{digits}f}"


def _ci(entry: Doc, digits: int = 1) -> str:
    if entry["interval"] is None:
        return "–"
    low, high = entry["interval"]
    return f"{_num(low, digits)} to {_num(high, digits)}"


def render(report: Doc) -> str:
    """The results block of docs/m1_growth.md."""
    b, per = report["bootstrap"], report["conditions"]
    lines = [
        f"Turn index: scripted position ({report['index']}). Slope: "
        f"{report['slope_unit']}, least squares pooled over a condition's runs. "
        f"Intervals: {b['confidence']:.0%} percentile bootstrap over whole runs, "
        f"{b['resamples']:,} resamples, stratified by condition, seed {b['seed']}.",
        "",
        "### Long sessions: slope per condition (RQ2)",
        "",
        "| Condition | Runs | Turns | Slope | 95% interval | Grows | "
        "Without `PHANTOM` | 95% interval |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for c, p in per.items():
        lines.append(
            f"| {c} | {p['long_runs']} | {p['long_turns']} | **{_num(p['slope']['value'])}** | "
            f"{_ci(p['slope'])} | {'yes' if p['grows'] else 'no'} | "
            f"{_num(p['slope_without_phantom']['value'])} | {_ci(p['slope_without_phantom'])} |"
        )
    lines += [
        "",
        "### Difference from condition A",
        "",
        "| Difference | Slope | 95% interval | Excludes 0 | Without `PHANTOM` | 95% interval |",
        "|---|---|---|---|---|---|",
    ]
    for c, d in report["differences"].items():
        lines.append(
            f"| {c} − A | **{_num(d['all']['value'])}** | {_ci(d['all'])} | "
            f"{'yes' if d['excludes_zero'] else 'no'} | "
            f"{_num(d['without_phantom']['value'])} | {_ci(d['without_phantom'])} |"
        )
    header = " | ".join(f"{lo}–{hi}" for lo, hi in BINS)
    lines += [
        "",
        "### Long sessions: rate per 100 turns by position",
        "",
        "Pooled over the condition's long-session runs; for the growth-curve figure (10.6).",
        "",
        f"| Condition | {header} |",
        "|---|" + "---|" * len(BINS),
    ]
    for c, p in per.items():
        cells = [_plain(bin_["rate"]) for bin_ in p["bins"]]
        lines.append(f"| {c} | " + " | ".join(cells) + " |")
    lines += [
        "",
        "### Short scenarios, for context",
        "",
        "Slope over the 12 short scenarios, no interval: their scripts differ by position.",
        "",
        "| Condition | Runs | Slope |",
        "|---|---|---|",
        *(f"| {c} | {p['short_runs']} | {_num(p['short_slope'])} |" for c, p in per.items()),
    ]
    return "\n".join(lines)


# --- the command ---------------------------------------------------------------

app = typer.Typer(add_completion=False)


@app.command()
def main(
    labels: Annotated[Path, typer.Option(help="The first annotator's m1_labels.jsonl.")] = Path(
        "results/m1_labels.jsonl"
    ),
    annotator: Annotated[str, typer.Option(help="The first annotator (9.5).")] = "SD",
    runs: Annotated[Path, typer.Option(help="The runs directory.")] = Path("runs"),
    scenarios: Annotated[Path, typer.Option(help="Directory of the scenario files.")] = Path(
        "scenarios"
    ),
    manifest: Annotated[Path, typer.Option(help="The batch manifest of the dataset.")] = Path(
        "experiments/main_grid.json"
    ),
    checksums: Annotated[
        Path | None, typer.Option(help="sha256sum file the logs must match (decision 60).")
    ] = None,
    out: Annotated[Path, typer.Option(help="Where the report is written as JSON.")] = Path(
        "results/m1_growth.json"
    ),
    doc: Annotated[
        Path | None, typer.Option(help="Document whose results block is rewritten.")
    ] = None,
    resamples: Annotated[int, typer.Option(help="Bootstrap resamples.", min=1)] = RESAMPLES,
) -> None:
    """RQ2: divergence growth against turn index per condition (WBS 10.2)."""
    try:
        logs = load_sample_logs(runs, manifest, checksums)
        sample = sorted(logs)
        found = load_scenarios(scenarios, {sid for _, sid, _ in sample})
        items = list(m1.sample_turns(sample, logs, found))
        per_run = runs_turns(sample, items, read_lines([labels]), annotator)
    except (DatasetError, LabelError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    report = {
        "dataset": {
            "manifest": manifest.as_posix(),
            "checksums": checksums.as_posix() if checksums else None,
            "labels": labels.as_posix(),
            "labels_sha256": file_sha256(labels),
            "annotator": annotator,
        },
        **growth_report(per_run, resamples=resamples),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    block = render(report)
    if doc is not None:
        write_results(doc, block)
    typer.echo(block)


if __name__ == "__main__":
    app()
