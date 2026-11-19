"""M5 narrative quality per condition, and H2 (WBS 11.3).

    python -m adm.eval.m5_scores \\
        --m5-ratings results/m5_ratings.jsonl --m5-ratings results/m5_ratings_SS.jsonl \\
        --doc docs/m5_scores.md

Fixed in the decision log (2026-11-19, "M5 scores and H2, fixed before the
figures") before the key was read against the ratings.

**Unit.** An excerpt, one per run (`docs/narrative_quality.md` section 1).
`results/m5_key.json` maps it to its run, so to its condition, scenario and
seed. Each condition must have 16 excerpts and each scenario one per condition,
all at one seed. Both raters must pair over the key as in 10.5
(`agreement.pair_ratings`).

**Score.** An excerpt's score on an item is the mean of the two raters'
ratings; a condition's score is the mean over its excerpts, with the median
beside it.

**H2 and RQ3** (CLAUDE.md section 10.5). Per item, the D minus A difference in
mean score, with the shared run-level bootstrap (`metrics.bootstrap`,
stratified by condition). B - A and C - A are given beside it. D is worse on an
item when the interval lies wholly below 0, better when wholly above, otherwise
no difference is shown; H2 is contradicted if D is worse on any item. No margin
was fixed, so an interval containing 0 does not show that D is no worse.

**Beside the headline**, fixed beforehand: the same differences for each rater
alone; the D - A interval paired by scenario (resampling the scenarios); and
the condition means for short scenarios and long sessions apart, no interval.
"""

from __future__ import annotations

import json
import statistics
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any

import typer

from adm.eval.agreement import M5_ITEMS, RatingError, pair_ratings
from adm.eval.integrity import file_sha256
from adm.eval.m1_agreement import read_lines
from adm.eval.metrics import BOOTSTRAP_SEED, RESAMPLES, bootstrap, write_results

Doc = dict[str, Any]

CONDITIONS = ("A", "B", "C", "D")
EXCERPTS_PER_CONDITION = 16
LONG_PREFIX = "long"


class ExcerptKeyError(ValueError):
    """The excerpt key does not give one excerpt per scenario and condition."""


@dataclass(frozen=True)
class Excerpt:
    excerpt_id: str
    condition: str
    scenario: str
    seed: int
    ratings: tuple[Mapping[str, int], Mapping[str, int]]  # (first rater, second rater)

    def score(self, item: str, rater: int | None = None) -> float:
        """The pooled score (mean of the two raters), or one rater's rating."""
        if rater is None:
            return (self.ratings[0][item] + self.ratings[1][item]) / 2
        return float(self.ratings[rater][item])

    @property
    def long(self) -> bool:
        return self.scenario.startswith(LONG_PREFIX)


def parse_run_id(run_id: str) -> tuple[str, str, int]:
    condition, rest = run_id.split("_", 1)
    scenario, seed = rest.rsplit("_", 1)
    return condition, scenario, int(seed)


def excerpts(
    key: Mapping[str, Mapping[str, Any]], pairs: Sequence[tuple[Doc, Doc]]
) -> list[Excerpt]:
    """Join the key to the paired ratings, and check one excerpt per scenario and
    condition at one seed per scenario. `pairs` is in sorted excerpt-id order."""
    ids = sorted(key)
    out = []
    for eid, (a, b) in zip(ids, pairs, strict=True):
        if a["excerpt_id"] != eid or b["excerpt_id"] != eid:
            raise ExcerptKeyError(f"ratings are not in key order at {eid}")
        cond, scen, seed = parse_run_id(key[eid]["run_id"])
        out.append(Excerpt(eid, cond, scen, seed, (a, b)))
    problems = []
    for c in CONDITIONS:
        n = sum(e.condition == c for e in out)
        if n != EXCERPTS_PER_CONDITION:
            problems.append(f"condition {c} has {n} excerpts, not {EXCERPTS_PER_CONDITION}")
    by_scenario: dict[str, list[Excerpt]] = {}
    for e in out:
        by_scenario.setdefault(e.scenario, []).append(e)
    for scen, es in sorted(by_scenario.items()):
        if sorted(e.condition for e in es) != list(CONDITIONS):
            problems.append(f"{scen} does not have one excerpt per condition")
        if len({e.seed for e in es}) != 1:
            problems.append(f"{scen} mixes seeds")
    if problems:
        raise ExcerptKeyError("; ".join(problems))
    return out


def mean_score(item: str, condition: str, rater: int | None = None):
    def stat(units: Sequence[Excerpt]) -> float | None:
        xs = [e.score(item, rater) for e in units if e.condition == condition]
        return sum(xs) / len(xs) if xs else None

    return stat


def difference(item: str, condition: str, rater: int | None = None):
    """Mean score of `condition` minus that of A."""
    this, base = mean_score(item, condition, rater), mean_score(item, "A", rater)

    def stat(units: Sequence[Excerpt]) -> float | None:
        x, y = this(units), base(units)
        return None if x is None or y is None else x - y

    return stat


def paired_difference(item: str, condition: str = "D"):
    """Mean over scenarios of (condition - A) within a scenario; the unit is a
    scenario's list of excerpts."""

    def stat(scenarios: Sequence[Sequence[Excerpt]]) -> float | None:
        diffs = []
        for es in scenarios:
            by = {e.condition: e for e in es}
            diffs.append(by[condition].score(item) - by["A"].score(item))
        return sum(diffs) / len(diffs) if diffs else None

    return stat


def reading(interval: Sequence[float] | None) -> str:
    if interval is None:
        return "undefined"
    low, high = interval
    if high < 0:
        return "worse"
    if low > 0:
        return "better"
    return "no difference shown"


def _ci(units, stat: Callable, *, strata, resamples: int, seed: int) -> list[float] | None:
    ci = bootstrap(units, stat, strata=strata, resamples=resamples, seed=seed)
    return list(ci) if ci else None


def scores_report(
    units: Sequence[Excerpt],
    raters: Sequence[str],
    *,
    resamples: int = RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> Doc:
    def by_cond(e: Excerpt) -> str:
        return e.condition

    by_scenario: dict[str, list[Excerpt]] = {}
    for e in units:
        by_scenario.setdefault(e.scenario, []).append(e)
    scenario_units = [by_scenario[s] for s in sorted(by_scenario)]

    items: Doc = {}
    for item in M5_ITEMS:
        conds = {}
        for c in CONDITIONS:
            mine = [e for e in units if e.condition == c]
            pooled = [e.score(item) for e in mine]
            conds[c] = {
                "excerpts": len(mine),
                "mean": statistics.fmean(pooled),
                "median": statistics.median(pooled),
                "rater_means": [statistics.fmean(e.score(item, r) for e in mine) for r in (0, 1)],
                "short_mean": statistics.fmean(e.score(item) for e in mine if not e.long),
                "long_mean": statistics.fmean(e.score(item) for e in mine if e.long),
            }
        diffs = {}
        for c in CONDITIONS[1:]:
            ci = _ci(units, difference(item, c), strata=by_cond, resamples=resamples, seed=seed)
            diffs[f"{c}-A"] = {
                "value": difference(item, c)(units),
                "interval": ci,
                "reading": reading(ci),
            }
        per_rater = []
        for r in (0, 1):
            stat = difference(item, "D", r)
            ci = _ci(units, stat, strata=by_cond, resamples=resamples, seed=seed)
            per_rater.append({"value": stat(units), "interval": ci, "reading": reading(ci)})
        paired = paired_difference(item)
        pci = _ci(scenario_units, paired, strata=None, resamples=resamples, seed=seed)
        items[item] = {
            "conditions": conds,
            "differences": diffs,
            "per_rater": per_rater,
            "paired": {
                "value": paired(scenario_units),
                "interval": pci,
                "reading": reading(pci),
            },
        }
    worse = [i for i in M5_ITEMS if items[i]["differences"]["D-A"]["reading"] == "worse"]
    return {
        "raters": list(raters),
        "excerpts": len(units),
        "scenarios": len(scenario_units),
        "bootstrap": {"resamples": resamples, "seed": seed, "confidence": 0.95},
        "items": items,
        "h2": {"worse_items": worse, "contradicted": bool(worse)},
    }


# --- rendering -----------------------------------------------------------------


def _n(x: float | None, digits: int = 2, sign: bool = False) -> str:
    if x is None:
        return "–"
    return f"{x:+.{digits}f}" if sign else f"{x:.{digits}f}"


def _span(ci: Sequence[float] | None) -> str:
    return "–" if ci is None else f"{_n(ci[0], sign=True)} to {_n(ci[1], sign=True)}"


def render(report: Doc) -> str:
    first, second = report["raters"]
    b = report["bootstrap"]
    h2 = report["h2"]
    verdict = (
        f"**contradicted**: D is worse than A on {', '.join(h2['worse_items'])}"
        if h2["contradicted"]
        else "**not contradicted**: on no item does the D − A interval lie wholly below 0. "
        "No margin was fixed, so this does not show that D is no worse"
    )
    lines = [
        f"{report['excerpts']} excerpts, one per run, {report['scenarios']} scenarios × 4 "
        f"conditions; raters {first} and {second}. Score: the mean of the two raters' "
        "ratings, 1 to 5. Intervals: 95% percentile bootstrap over whole runs, "
        f"{b['resamples']:,} resamples, stratified by condition, seed {b['seed']}.",
        "",
        f"**H2** (D − A per item, D worse when the interval lies wholly below 0): {verdict}.",
        "",
        "### Mean score per condition",
        "",
        "Mean of the 16 excerpts' scores, median in brackets.",
        "",
        "| Item | A | B | C | D |",
        "|---|---|---|---|---|",
    ]
    for item, e in report["items"].items():
        cells = " | ".join(
            f"{_n(e['conditions'][c]['mean'])} ({_n(e['conditions'][c]['median'], 1)})"
            for c in CONDITIONS
        )
        lines.append(f"| {item} | {cells} |")
    lines += [
        "",
        "### Difference from condition A (H2, RQ3)",
        "",
        "| Item | B − A | 95% interval | C − A | 95% interval | **D − A** | 95% interval "
        "| Reading |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for item, e in report["items"].items():
        d = e["differences"]
        lines.append(
            f"| {item} | {_n(d['B-A']['value'], sign=True)} | {_span(d['B-A']['interval'])} | "
            f"{_n(d['C-A']['value'], sign=True)} | {_span(d['C-A']['interval'])} | "
            f"**{_n(d['D-A']['value'], sign=True)}** | {_span(d['D-A']['interval'])} | "
            f"{d['D-A']['reading']} |"
        )
    lines += [
        "",
        "### D − A for each rater alone, and paired by scenario",
        "",
        f"| Item | {first} alone | 95% interval | Reading | {second} alone | 95% interval | "
        "Reading | Paired by scenario | 95% interval |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for item, e in report["items"].items():
        r0, r1, p = e["per_rater"][0], e["per_rater"][1], e["paired"]
        lines.append(
            f"| {item} | {_n(r0['value'], sign=True)} | {_span(r0['interval'])} | "
            f"{r0['reading']} | "
            f"{_n(r1['value'], sign=True)} | {_span(r1['interval'])} | {r1['reading']} | "
            f"{_n(p['value'], sign=True)} | {_span(p['interval'])} |"
        )
    lines += [
        "",
        "### Each rater's mean, and short scenarios against long sessions",
        "",
        f"Means per condition: {first} / {second}, then the pooled score over the 12 short "
        "scenarios / the 4 long sessions, no interval.",
        "",
        f"| Item | Condition | {first} / {second} | Short / long |",
        "|---|---|---|---|",
    ]
    for item, e in report["items"].items():
        for c in CONDITIONS:
            x = e["conditions"][c]
            lines.append(
                f"| {item} | {c} | {_n(x['rater_means'][0])} / {_n(x['rater_means'][1])} | "
                f"{_n(x['short_mean'])} / {_n(x['long_mean'])} |"
            )
    return "\n".join(lines)


# --- the command ---------------------------------------------------------------

app = typer.Typer(add_completion=False)


@app.command()
def main(
    m5_ratings: Annotated[
        list[Path], typer.Option(help="An m5_ratings.jsonl file; give both raters' files.")
    ],
    first: Annotated[str, typer.Option(help="The first M5 rater (9.8).")] = "SS",
    second: Annotated[str, typer.Option(help="The second M5 rater (9.9).")] = "SD",
    m5_key: Annotated[Path, typer.Option(help="The M5 excerpt key.")] = Path("results/m5_key.json"),
    out: Annotated[Path, typer.Option(help="Where the report is written as JSON.")] = Path(
        "results/m5_scores.json"
    ),
    doc: Annotated[
        Path | None, typer.Option(help="Document whose results block is rewritten.")
    ] = None,
) -> None:
    """M5 per condition and H2, the D - A difference per item (WBS 11.3)."""
    if first == second:
        raise typer.BadParameter("the two raters must differ")
    try:
        key = json.loads(m5_key.read_text(encoding="utf-8"))
        pairs = pair_ratings(read_lines(m5_ratings), first, second, sorted(key))
        units = excerpts(key, pairs)
    except (RatingError, ExcerptKeyError) as exc:
        typer.echo(f"M5 scores are not computable: {exc}", err=True)
        raise typer.Exit(1) from exc
    report = {
        "dataset": {
            "m5_ratings": {p.as_posix(): file_sha256(p) for p in m5_ratings},
            "m5_key": file_sha256(m5_key),
        },
        **scores_report(units, [first, second]),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    block = render(report)
    if doc is not None:
        write_results(doc, block)
    typer.echo(block)


if __name__ == "__main__":
    app()
