"""M1, the divergence rate per condition, with intervals (WBS 10.1; RQ1, H1).

    python -m adm.eval.m1_rates --labels results/m1_labels.jsonl \\
        --checksums experiments/main_grid.sha256 --doc docs/m1_rates.md

**The data.** The M1 sample of WBS 9.5 (`adm/eval/m1.py`): 64 whole runs, one
seed per scenario with all four conditions at it, recomputed here from the
runs `experiments/main_grid.json` plans, so the G2 smoke logs never enter.
With `--checksums`, every log read must match `experiments/main_grid.sha256`
(decision 60). The labels are the first annotator's (`--annotator`, SD), who
labelled every sampled turn; the second annotator's overlap labels are for
agreement (10.5), not for the rate. The command refuses a labels file that does
not give that annotator exactly one line for every sampled turn, or that was
shown other checker candidates than the sample gives now.

**The count** of a turn is its divergences by rubric v1.0: the confirmed
checker candidates plus the added labels, in the four rubric categories
(`m1_agreement.label_counts`, the unit of 9.6 and decision 58). `RULE` labels
are M4 and are left out. The denominator is the narrated turns: a failed
condition D turn shows the engine's request to rephrase, not the model's
narration, so it is not in the sample (9.4, 9.5).

**The rate** of a condition is 100 x divergences / narrated turns, pooled over
its 16 runs as a ratio of sums, so a 50-turn run weighs more than a 30-turn one,
as its turns do. It is given overall and per category.

**H1** (CLAUDE.md section 10.5): D has at least 50% fewer divergences per 100
turns than A, tested by the D/A ratio of the pooled rates being at most 0.5 with
its 95% interval excluding 1. The B/A and C/A ratios are given beside it.

**Intervals** are the shared percentile bootstrap (`metrics.bootstrap`): whole
runs, 10,000 resamples, stratified by condition, seed 20261101. A ratio's
resample draws the two conditions' runs separately, each stratum keeping its 16.

**Sensitivity**, fixed with the rest before the figures were read: the H1 ratio
without `PHANTOM`, since `PHANTOM` holds the one inconsistency 9.5 found (items
named only in a player input, `docs/m1_annotation.md` section 3).
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any

import typer

from adm.engine.audit import log_path, read_log, run_id
from adm.eval import m1
from adm.eval.annotate import load_scenarios
from adm.eval.checker import RunKey
from adm.eval.integrity import file_sha256, load_plan, read_checksums
from adm.eval.m1_agreement import label_counts, read_lines
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

BASELINE = "A"
H1_RATIO = 0.5  # CLAUDE.md section 10.5
SENSITIVITY = tuple(c for c in RUBRIC if c != "PHANTOM")


class LabelError(ValueError):
    """The labels do not cover the M1 sample as the tool shows it."""


@dataclass(frozen=True)
class RunM1:
    """The M1 counts of one sampled run."""

    key: RunKey
    turns: int
    counts: Mapping[str, int]
    turns_with_any: int

    @property
    def condition(self) -> str:
        return self.key[0]

    @property
    def long(self) -> bool:
        return self.key[1].startswith("long")

    def divergences(self, categories: Sequence[str] = RUBRIC) -> int:
        return sum(self.counts.get(c, 0) for c in categories)


# --- the data ------------------------------------------------------------------


def load_sample_logs(
    runs_dir: Path, manifest: Path, checksums: Path | None
) -> dict[RunKey, list[Doc]]:
    """The logs of the M1 sample, drawn from the runs `manifest` plans, each
    checked against the checksum file when one is given."""
    sample = m1.draw_runs(load_plan(manifest)[0])
    paths = {key: log_path(runs_dir, *key) for key in sample}
    missing = [run_id(*key) for key, path in paths.items() if not path.is_file()]
    if missing:
        raise DatasetError(f"No log for sampled runs: {', '.join(missing)}")
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


def _shown(candidates: Sequence[Doc]) -> list[Doc]:
    return [{f: c.get(f) for f in m1.CANDIDATE_FIELDS} for c in candidates]


def runs_m1(
    sample: Sequence[RunKey], items: Sequence[m1.M1Turn], lines: Sequence[Doc], annotator: str
) -> list[RunM1]:
    """Per sampled run, its narrated turns and labelled divergences. Every
    sampled turn must have exactly one line by `annotator`, shown the same
    candidates."""
    mine: dict[str, Doc] = {}
    dupes = []
    for line in lines:
        if line.get("annotator") != annotator:
            continue
        if line["turn_id"] in mine:
            dupes.append(line["turn_id"])
        mine[line["turn_id"]] = line
    wanted = {item.turn_id: item for item in items}
    problems = []
    if dupes:
        problems.append(f"{len(dupes)} turns labelled twice, e.g. {dupes[:3]}")
    missing = [t for t in wanted if t not in mine]
    if missing:
        problems.append(f"{len(missing)} sampled turns have no line, e.g. {missing[:3]}")
    outside = [t for t in mine if t not in wanted]
    if outside:
        problems.append(f"{len(outside)} lines are not sampled turns, e.g. {outside[:3]}")
    differ = [
        t
        for t, item in wanted.items()
        if t in mine
        and (
            _shown(mine[t]["candidates"]) != list(item.candidates)
            or mine[t]["run_id"] != item.run_id
        )
    ]
    if differ:
        problems.append(f"{len(differ)} turns differ from the sample, e.g. {differ[:3]}")
    if problems:
        raise LabelError(f"labels of {annotator}: " + "; ".join(problems))

    keys = {run_id(*key): key for key in sample}
    by_run: dict[str, list[Counter[str]]] = {rid: [] for rid in keys}
    for item in items:
        by_run[item.run_id].append(label_counts(mine[item.turn_id]))
    runs = []
    for rid, counts in by_run.items():
        total: Counter[str] = Counter()
        for c in counts:
            total.update(c)
        runs.append(
            RunM1(
                key=keys[rid],
                turns=len(counts),
                counts={c: total.get(c, 0) for c in RUBRIC},
                turns_with_any=sum(bool(+c) for c in counts),
            )
        )
    return sorted(runs, key=lambda r: r.key)


# --- the figures ---------------------------------------------------------------


def rate(categories: Sequence[str] = RUBRIC) -> Callable[[Sequence[RunM1]], float | None]:
    """Divergences per 100 narrated turns, pooled as a ratio of sums."""

    def stat(runs: Sequence[RunM1]) -> float | None:
        turns = sum(r.turns for r in runs)
        return 100 * sum(r.divergences(categories) for r in runs) / turns if turns else None

    return stat


def ratio(
    condition: str, categories: Sequence[str] = RUBRIC
) -> Callable[[Sequence[RunM1]], float | None]:
    """The pooled rate of `condition` over the pooled rate of the baseline."""
    of = rate(categories)

    def stat(runs: Sequence[RunM1]) -> float | None:
        top = of([r for r in runs if r.condition == condition])
        bottom = of([r for r in runs if r.condition == BASELINE])
        return None if top is None or not bottom else top / bottom

    return stat


def _with_interval(
    runs: Sequence[RunM1], stat: Callable[[Sequence[RunM1]], float | None], **kw: Any
) -> Doc:
    interval = bootstrap(runs, stat, strata=lambda r: r.condition, **kw)
    return {"value": stat(runs), "interval": list(interval) if interval else None}


def m1_report(
    runs: Sequence[RunM1], *, resamples: int = RESAMPLES, seed: int = BOOTSTRAP_SEED
) -> Doc:
    """M1 per condition with intervals, the ratios to A, H1 and the sensitivity."""
    kw = {"resamples": resamples, "seed": seed}
    conditions = sorted({r.condition for r in runs})
    by: dict[str, list[RunM1]] = {c: [r for r in runs if r.condition == c] for c in conditions}
    per_condition = {}
    for c, group in by.items():
        per_condition[c] = {
            "runs": len(group),
            "turns": sum(r.turns for r in group),
            "turns_with_any": sum(r.turns_with_any for r in group),
            "divergences": {k: sum(r.counts[k] for r in group) for k in RUBRIC},
            "rate": _with_interval(group, rate(), **kw),
            "by_category": {k: _with_interval(group, rate([k]), **kw) for k in RUBRIC},
            "short": rate()([r for r in group if not r.long]),
            "long": rate()([r for r in group if r.long]),
        }
    ratios = {}
    for c in conditions:
        if c == BASELINE:
            continue
        pair = by[c] + by[BASELINE]
        ratios[c] = {
            "all": _with_interval(pair, ratio(c), **kw),
            "without_phantom": _with_interval(pair, ratio(c, SENSITIVITY), **kw),
        }
    h1 = None
    if "D" in ratios:
        d = ratios["D"]["all"]
        low_high = d["interval"]
        h1 = {
            "ratio": d["value"],
            "interval": low_high,
            "at_most_half": d["value"] is not None and d["value"] <= H1_RATIO,
            "excludes_one": low_high is not None and low_high[1] < 1,
        }
        h1["supported"] = h1["at_most_half"] and h1["excludes_one"]
    return {
        "bootstrap": {
            "resamples": resamples,
            "seed": seed,
            "confidence": CONFIDENCE,
            "unit": "run",
        },
        "runs": len(runs),
        "turns": sum(r.turns for r in runs),
        "conditions": per_condition,
        "ratios": ratios,
        "h1": h1,
        "per_run": [
            {
                "run_id": run_id(*r.key),
                "turns": r.turns,
                "divergences": r.divergences(),
                **dict(r.counts),
            }
            for r in runs
        ],
    }


# --- the report ----------------------------------------------------------------


def _num(value: float | None, digits: int = 1) -> str:
    return "–" if value is None else f"{value:.{digits}f}"


def _ci(entry: Doc, digits: int = 1) -> str:
    if entry["interval"] is None:
        return "–"
    low, high = entry["interval"]
    return f"{_num(low, digits)} to {_num(high, digits)}"


def render(report: Doc) -> str:
    """The results block of docs/m1_rates.md."""
    b, per = report["bootstrap"], report["conditions"]
    lines = [
        f"{report['runs']} runs, {report['turns']} narrated turns, labels of the first "
        f"annotator. Rates are divergences per 100 narrated turns, pooled over runs. "
        f"Intervals: {b['confidence']:.0%} percentile bootstrap over whole runs, "
        f"{b['resamples']:,} resamples, stratified by condition, seed {b['seed']}.",
        "",
        "### M1 per condition",
        "",
        "| Condition | Runs | Turns | Divergences | Turns with any | Rate | 95% interval |",
        "|---|---|---|---|---|---|---|",
    ]
    for c, p in per.items():
        total = sum(p["divergences"].values())
        lines.append(
            f"| {c} | {p['runs']} | {p['turns']} | {total} | {p['turns_with_any']} | "
            f"**{_num(p['rate']['value'])}** | {_ci(p['rate'])} |"
        )
    lines += [
        "",
        "### Per category",
        "",
        "Count, then rate per 100 turns with its 95% interval.",
        "",
        "| Condition | " + " | ".join(f"`{k}`" for k in RUBRIC) + " |",
        "|---|" + "---|" * len(RUBRIC),
    ]
    for c, p in per.items():
        cells = [
            f"{p['divergences'][k]}: {_num(p['by_category'][k]['value'])} "
            f"({_ci(p['by_category'][k])})"
            for k in RUBRIC
        ]
        lines.append(f"| {c} | " + " | ".join(cells) + " |")
    lines += [
        "",
        "### Ratio to condition A",
        "",
        "| Ratio | All categories | 95% interval | Without `PHANTOM` | 95% interval |",
        "|---|---|---|---|---|",
    ]
    for c, r in report["ratios"].items():
        lines.append(
            f"| {c}/A | **{_num(r['all']['value'], 2)}** | {_ci(r['all'], 2)} | "
            f"{_num(r['without_phantom']['value'], 2)} | {_ci(r['without_phantom'], 2)} |"
        )
    h1 = report["h1"]
    if h1 is not None:
        verdict = "**supported**" if h1["supported"] else "**not supported**"
        lines += [
            "",
            f"**H1** (D/A at most {H1_RATIO}, 95% interval excluding 1): {verdict}. "
            f"D/A = {_num(h1['ratio'], 2)}, interval {_ci({'interval': h1['interval']}, 2)}; "
            f"at most {H1_RATIO}: {'yes' if h1['at_most_half'] else 'no'}; "
            f"interval excludes 1: {'yes' if h1['excludes_one'] else 'no'}.",
        ]
    lines += [
        "",
        "### Short scenarios and long sessions",
        "",
        "Rate per 100 turns, no interval; RQ2 (10.2) takes up the long sessions.",
        "",
        "| Condition | 12 short scenarios | 4 long sessions |",
        "|---|---|---|",
        *(f"| {c} | {_num(p['short'])} | {_num(p['long'])} |" for c, p in per.items()),
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
        "results/m1.json"
    ),
    doc: Annotated[
        Path | None, typer.Option(help="Document whose results block is rewritten.")
    ] = None,
    resamples: Annotated[int, typer.Option(help="Bootstrap resamples.", min=1)] = RESAMPLES,
) -> None:
    """M1: divergences per 100 narrated turns per condition, and H1 (WBS 10.1)."""
    try:
        logs = load_sample_logs(runs, manifest, checksums)
        sample = sorted(logs)
        found = load_scenarios(scenarios, {sid for _, sid, _ in sample})
        items = list(m1.sample_turns(sample, logs, found))
        per_run = runs_m1(sample, items, read_lines([labels]), annotator)
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
        **m1_report(per_run, resamples=resamples),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    block = render(report)
    if doc is not None:
        write_results(doc, block)
    typer.echo(block)


if __name__ == "__main__":
    app()
