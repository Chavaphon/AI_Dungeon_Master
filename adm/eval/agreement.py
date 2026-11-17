"""Inter-rater agreement, Krippendorff's alpha, and Objective 3 (WBS 10.5).

    python -m adm.eval.agreement \\
        --m1-labels results/m1_labels.jsonl --m1-labels results/m1_labels_SS.jsonl \\
        --m5-ratings results/m5_ratings.jsonl --m5-ratings results/m5_ratings_SS.jsonl \\
        --checksums experiments/main_grid.sha256 --doc docs/agreement.md

**M1** (CLAUDE.md section 10.4: alpha on the 20% double-scored overlap). The
16 overlap runs are recomputed from the runs `experiments/main_grid.json` plans
(`m1.overlap_runs`), with `--checksums` checked against
`experiments/main_grid.sha256`, and the two annotators' lines are paired by
`m1_agreement.pair` (one line each per overlap turn, the same checker
candidates). The unit is one turn and one rubric category, valued by the number
of divergences (decision 58): alpha is interval per category and pooled, and
nominal on whether a turn has any divergence. Each annotator's review counts
(`accepted`, `edited`) are reported beside it, because both start from AI drafts
(decision log 2026-11-15).

**M5** (`docs/narrative_quality.md` section 8). Both raters rated all 64
excerpts. Each must have exactly one line per excerpt of `results/m5_key.json`
and nothing else. Alpha is ordinal, per item (coherence, vividness, tone,
engagement), over the 64 excerpts; the exact-agreement share and each rater's
mean are given beside it.

**Objective 3** is met when the pooled M1 alpha is at least 0.6: the overlap of
section 10.4 is M1's (Week 5 checkpoint, decision 1). Every other alpha is
checked against 0.6 and reported, and does not decide the objective. No
interval is computed for alpha.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Annotated, Any

import typer

from adm.eval import m1
from adm.eval.annotate import load_scenarios
from adm.eval.integrity import file_sha256
from adm.eval.m1_agreement import OverlapError, label_counts, pair, read_lines
from adm.eval.m1_rates import load_sample_logs
from adm.eval.metrics import DatasetError, write_results
from adm.eval.rubric_pilot import RUBRIC, TARGET, alpha

Doc = dict[str, Any]

M5_ITEMS = ("coherence", "vividness", "tone", "engagement")


class RatingError(ValueError):
    """The two raters' M5 ratings do not pair up over the excerpts."""


# --- M1 ------------------------------------------------------------------------


def _review(lines: Sequence[Doc]) -> dict[str, int]:
    # a line with no `review` was relabelled with --redo, without the draft shown
    counts = Counter(str(ln.get("review") or "relabelled") for ln in lines)
    return dict(sorted(counts.items()))


def m1_agreement(pairs: Sequence[tuple[Doc, Doc]]) -> Doc:
    """Alpha on the paired overlap: per category and pooled (interval), any
    divergence (nominal), with totals, differing units and review counts."""
    first = [label_counts(a) for a, _ in pairs]
    second = [label_counts(b) for _, b in pairs]

    def entry(categories: Sequence[str]) -> Doc:
        units: list[list[float | None]] = [
            [float(x[c]), float(y[c])]
            for x, y in zip(first, second, strict=True)
            for c in categories
        ]
        a = alpha(units, "interval")
        return {
            "totals": [
                sum(x[c] for x in first for c in categories),
                sum(y[c] for y in second for c in categories),
            ],
            "alpha": a,
            "metric": "interval",
            "meets": a is not None and a >= TARGET,
        }

    per_category = {c: entry([c]) for c in RUBRIC}
    pooled = entry(RUBRIC)
    any_units: list[list[float | None]] = [
        [float(bool(+x)), float(bool(+y))] for x, y in zip(first, second, strict=True)
    ]
    a_any = alpha(any_units, "nominal")
    return {
        "turns": len(pairs),
        "per_category": per_category,
        "pooled": pooled,
        "any": {
            "totals": [sum(bool(+x) for x in first), sum(bool(+y) for y in second)],
            "alpha": a_any,
            "metric": "nominal",
            "meets": a_any is not None and a_any >= TARGET,
        },
        "units_differ": sum(
            x[c] != y[c] for x, y in zip(first, second, strict=True) for c in RUBRIC
        ),
        "units": len(pairs) * len(RUBRIC),
        "review": [_review([a for a, _ in pairs]), _review([b for _, b in pairs])],
    }


# --- M5 ------------------------------------------------------------------------


def pair_ratings(
    lines: Sequence[Doc], first: str, second: str, excerpt_ids: Sequence[str]
) -> list[tuple[Doc, Doc]]:
    """The (first, second) ratings of every excerpt, in `excerpt_ids` order."""
    wanted = set(excerpt_ids)
    by: dict[str, dict[str, Doc]] = {first: {}, second: {}}
    problems = []
    for name in (first, second):
        dupes = []
        for ln in lines:
            if ln.get("rater") != name:
                continue
            if ln["excerpt_id"] in by[name]:
                dupes.append(ln["excerpt_id"])
            by[name][ln["excerpt_id"]] = ln
        if dupes:
            problems.append(f"{name} rated {len(dupes)} excerpts twice, e.g. {dupes[:3]}")
        missing = [e for e in excerpt_ids if e not in by[name]]
        if missing:
            problems.append(f"{name} has no rating for {len(missing)} excerpts, e.g. {missing[:3]}")
        outside = sorted(e for e in by[name] if e not in wanted)
        if outside:
            problems.append(f"{name} rated {len(outside)} unknown excerpts, e.g. {outside[:3]}")
        bad = [
            e
            for e, ln in by[name].items()
            if any(not isinstance(ln.get(i), int) or not 1 <= ln[i] <= 5 for i in M5_ITEMS)
        ]
        if bad:
            problems.append(f"{name} has {len(bad)} ratings outside 1 to 5, e.g. {bad[:3]}")
    if problems:
        raise RatingError("; ".join(problems))
    return [(by[first][e], by[second][e]) for e in excerpt_ids]


def m5_agreement(pairs: Sequence[tuple[Doc, Doc]]) -> Doc:
    """Ordinal alpha per M5 item, with exact agreement and each rater's mean."""
    items = {}
    for item in M5_ITEMS:
        units: list[list[float | None]] = [[float(a[item]), float(b[item])] for a, b in pairs]
        a = alpha(units, "ordinal")
        n = len(pairs)
        items[item] = {
            "alpha": a,
            "metric": "ordinal",
            "meets": a is not None and a >= TARGET,
            "exact": sum(x[item] == y[item] for x, y in pairs) / n if n else None,
            "means": [
                sum(x[item] for x, _ in pairs) / n if n else None,
                sum(y[item] for _, y in pairs) / n if n else None,
            ],
            "distribution": [
                dict(sorted(Counter(x[item] for x, _ in pairs).items())),
                dict(sorted(Counter(y[item] for _, y in pairs).items())),
            ],
        }
    return {"excerpts": len(pairs), "items": items}


# --- the report ----------------------------------------------------------------


def objective_3(m1_part: Doc) -> Doc:
    a = m1_part["pooled"]["alpha"]
    return {"alpha": a, "target": TARGET, "met": a is not None and a >= TARGET}


def _fmt(a: float | None) -> str:
    return "–" if a is None else f"{a:.3f}"


def _meets(entry: Mapping[str, Any]) -> str:
    return "–" if entry["alpha"] is None else ("yes" if entry["meets"] else "**no**")


def render(report: Doc) -> str:
    """The results block of docs/agreement.md."""
    first, second = report["m1_annotators"]
    m1p, m5p, obj = report["m1"], report["m5"], report["objective_3"]
    verdict = "**met**" if obj["met"] else "**not met**"
    lines = [
        f"**Objective 3** (pooled M1 alpha at least {obj['target']}): {verdict}, "
        f"alpha = {_fmt(obj['alpha'])}. Both annotators' M1 labels start from AI "
        "drafts by the same model (§4).",
        "",
        f"### M1: the 20% overlap, {m1p['turns']} turns",
        "",
        f"| Unit | {first} | {second} | Alpha | Metric | Meets {TARGET} |",
        "|---|---|---|---|---|---|",
    ]
    for c, e in m1p["per_category"].items():
        lines.append(
            f"| `{c}` | {e['totals'][0]} | {e['totals'][1]} | {_fmt(e['alpha'])} | "
            f"interval | {_meets(e)} |"
        )
    e = m1p["pooled"]
    lines.append(
        f"| **All four, pooled** | {e['totals'][0]} | {e['totals'][1]} | "
        f"**{_fmt(e['alpha'])}** | interval | {_meets(e)} |"
    )
    e = m1p["any"]
    lines.append(
        f"| Turn has any divergence | {e['totals'][0]} | {e['totals'][1]} | "
        f"{_fmt(e['alpha'])} | nominal | {_meets(e)} |"
    )
    review = ", ".join(
        f"{name}: " + ", ".join(f"{k} {v}" for k, v in counts.items())
        for name, counts in zip((first, second), m1p["review"], strict=True)
    )
    lines += [
        "",
        f"{m1p['units_differ']} of {m1p['units']} units differ. Review of the overlap turns: "
        f"{review}.",
        "",
        f"### M5: narrative quality, {m5p['excerpts']} excerpts",
        "",
        f"| Item | Alpha | Metric | Meets {TARGET} | Exact agreement | "
        f"Mean {report['m5_raters'][0]} | Mean {report['m5_raters'][1]} |",
        "|---|---|---|---|---|---|---|",
    ]
    for item, e in m5p["items"].items():
        lines.append(
            f"| {item} | {_fmt(e['alpha'])} | ordinal | {_meets(e)} | {e['exact']:.0%} | "
            f"{e['means'][0]:.2f} | {e['means'][1]:.2f} |"
        )
    lines += ["", "Ratings per item, 1 to 5:", ""]
    for item, e in m5p["items"].items():
        dist = " · ".join(
            f"{name} " + " ".join(f"{k}:{v}" for k, v in d.items())
            for name, d in zip(report["m5_raters"], e["distribution"], strict=True)
        )
        lines.append(f"- {item}: {dist}")
    return "\n".join(lines)


# --- the command ---------------------------------------------------------------

app = typer.Typer(add_completion=False)


@app.command()
def main(
    m1_labels: Annotated[
        list[Path], typer.Option(help="An m1_labels.jsonl file; give both annotators' files.")
    ],
    m5_ratings: Annotated[
        list[Path], typer.Option(help="An m5_ratings.jsonl file; give both raters' files.")
    ],
    first: Annotated[str, typer.Option(help="The first M1 annotator (9.5).")] = "SD",
    second: Annotated[str, typer.Option(help="The M1 overlap annotator (9.6).")] = "SS",
    m5_first: Annotated[str, typer.Option(help="The first M5 rater (9.8).")] = "SS",
    m5_second: Annotated[str, typer.Option(help="The second M5 rater (9.9).")] = "SD",
    m5_key: Annotated[Path, typer.Option(help="The M5 excerpt key.")] = Path("results/m5_key.json"),
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
        "results/agreement.json"
    ),
    doc: Annotated[
        Path | None, typer.Option(help="Document whose results block is rewritten.")
    ] = None,
) -> None:
    """Krippendorff's alpha for M1 and M5, and Objective 3 (WBS 10.5)."""
    if first == second or m5_first == m5_second:
        raise typer.BadParameter("the two annotators must differ")
    try:
        logs = load_sample_logs(runs, manifest, checksums)
        overlap = m1.overlap_runs(sorted(logs))
        found = load_scenarios(scenarios, {sid for _, sid, _ in overlap})
        turn_ids = [t.turn_id for t in m1.sample_turns(overlap, logs, found)]
        m1_pairs = pair(read_lines(m1_labels), first, second, turn_ids)
        excerpt_ids = sorted(json.loads(m5_key.read_text(encoding="utf-8")))
        m5_pairs = pair_ratings(read_lines(m5_ratings), m5_first, m5_second, excerpt_ids)
    except (DatasetError, OverlapError, RatingError) as exc:
        typer.echo(f"Agreement is not computable: {exc}", err=True)
        raise typer.Exit(1) from exc
    m1_part = m1_agreement(m1_pairs)
    report = {
        "dataset": {
            "manifest": manifest.as_posix(),
            "checksums": checksums.as_posix() if checksums else None,
            "m1_labels": {p.as_posix(): file_sha256(p) for p in m1_labels},
            "m5_ratings": {p.as_posix(): file_sha256(p) for p in m5_ratings},
            "m5_key": file_sha256(m5_key),
        },
        "m1_annotators": [first, second],
        "m5_raters": [m5_first, m5_second],
        "m1": m1_part,
        "m5": m5_agreement(m5_pairs),
        "objective_3": objective_3(m1_part),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    block = render(report)
    if doc is not None:
        write_results(doc, block)
    typer.echo(block)


if __name__ == "__main__":
    app()
