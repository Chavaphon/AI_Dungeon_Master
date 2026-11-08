"""Rubric pilot (WBS 8.11): Krippendorff's alpha between two annotators who label
the same turns by docs/rubric.md.

    # each annotator labels results/checker_validation/sheet.md on their own:
    #   SD -> results/checker_validation/labels.csv   (the 8.10 labels)
    #   XX -> results/checker_validation/labels_XX.csv
    python -m adm.eval.rubric_pilot --labels SD=results/checker_validation/labels.csv \\
        --labels XX=results/checker_validation/labels_XX.csv

**The turns** are the 30 of the 8.10 sample (`sample.json`): both dry-run
scenarios, `s01_cellar` and `long01_border_road`, under A to D. The pilot needs
no run logs: agreement is computed from the labels alone.

**The unit** is one turn and one rubric category, and its value is the number of
divergences of that category the annotator recorded in that turn (rubric section
3: every divergence counts). Alpha uses the interval metric on these counts, so
1 against 2 is a smaller disagreement than 0 against 3. It is reported per
category, over all four categories pooled, and, with the nominal metric, on
whether a turn has any divergence at all. `RULE` and `NOTE` rows are not rubric
categories and are left out.

**For 8.12** the report lists every unit where the counts differ, with both
annotators' phrases, and the turns where an annotator wrote `6.4` in `notes`: a
one-step stance case left unrecorded under the adjacency allowance (rubric
section 7 point 1).
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping, Sequence
from itertools import combinations
from pathlib import Path
from typing import Annotated, Literal

import typer

from adm.eval.checker_validation import Label, read_labels

RUBRIC = ("PHANTOM", "CONTRADICT", "RESOURCE", "RELATION")
TARGET = 0.6  # CLAUDE.md section 10.4
RESULTS_START = "<!-- results:start -->"
RESULTS_END = "<!-- results:end -->"

Metric = Literal["nominal", "interval"]


def alpha(units: Sequence[Sequence[float | None]], metric: Metric = "interval") -> float | None:
    """Krippendorff's alpha. Each unit lists one value per annotator, `None` where
    that annotator gave none. Units with fewer than two values are not pairable
    and are dropped. Returns `None` when alpha is undefined: no pairable values,
    or every pairable value the same (no expected disagreement)."""
    coincidence: Counter[tuple[float, float]] = Counter()
    for unit in units:
        values = [v for v in unit if v is not None]
        m = len(values)
        if m < 2:
            continue
        for i, j in combinations(range(m), 2):
            coincidence[(values[i], values[j])] += 1 / (m - 1)
            coincidence[(values[j], values[i])] += 1 / (m - 1)
    totals: Counter[float] = Counter()
    for (c, _), w in coincidence.items():
        totals[c] += w
    n = sum(totals.values())
    if n <= 1:
        return None

    def delta(c: float, k: float) -> float:
        return float(c != k) if metric == "nominal" else (c - k) ** 2

    observed = sum(w * delta(c, k) for (c, k), w in coincidence.items()) / n
    expected = sum(totals[c] * totals[k] * delta(c, k) for c in totals for k in totals) / (
        n * (n - 1)
    )
    if expected == 0:
        return None
    return 1 - observed / expected


def counts(labels: Sequence[Label]) -> Counter[tuple[str, str]]:
    """Divergences per (sample id, category), rubric categories only."""
    return Counter((lb.sample_id, lb.category) for lb in labels if lb.category in RUBRIC)


def _fmt(a: float | None) -> str:
    return "–" if a is None else f"{a:.3f}"


def _meets(a: float | None) -> str:
    return "–" if a is None else ("yes" if a >= TARGET else "**no**")


def _cell(count: int, phrases: Sequence[str]) -> str:
    quoted = "; ".join(f"“{p}”" for p in phrases).replace("|", "\\|")
    return f"{count}: {quoted}" if quoted else str(count)


def report(sample_ids: Sequence[str], annotated: Mapping[str, Sequence[Label]]) -> str:
    """The results block of docs/rubric_pilot.md."""
    names = list(annotated)
    per = {name: counts(labels) for name, labels in annotated.items()}

    def units(categories: Sequence[str]) -> list[list[float | None]]:
        return [
            [float(per[name][(sid, cat)]) for name in names]
            for sid in sample_ids
            for cat in categories
        ]

    rows = [
        "| Units | " + " | ".join(f"{n}: divergences" for n in names) + " | Alpha | Metric | "
        f"Meets {TARGET} |",
        "|---|" + "---|" * len(names) + "---|---|---|",
    ]

    def row(title: str, categories: Sequence[str]) -> None:
        a = alpha(units(categories), "interval")
        totals = " | ".join(
            str(sum(per[n][(s, c)] for s in sample_ids for c in categories)) for n in names
        )
        rows.append(f"| {title} | {totals} | {_fmt(a)} | interval | {_meets(a)} |")

    for category in RUBRIC:
        row(f"`{category}`", [category])
    row("**All four, pooled**", RUBRIC)
    any_units: list[list[float | None]] = [
        [float(any(per[n][(sid, c)] for c in RUBRIC)) for n in names] for sid in sample_ids
    ]
    a_any = alpha(any_units, "nominal")
    turns_any = " | ".join(str(int(sum(u[i] for u in any_units))) for i in range(len(names)))
    rows.append(
        f"| Turn has any divergence | {turns_any} (turns) | {_fmt(a_any)} | nominal | "
        f"{_meets(a_any)} |"
    )

    phrases = {
        name: {
            key: [lb.phrase for lb in labels if (lb.sample_id, lb.category) == key]
            for key in per[name]
        }
        for name, labels in annotated.items()
    }
    diff = [
        "| Turn | Category | " + " | ".join(names) + " |",
        "|---|---|" + "---|" * len(names),
    ]
    n_diff = 0
    for sid in sample_ids:
        for cat in RUBRIC:
            if len({per[n][(sid, cat)] for n in names}) > 1:
                n_diff += 1
                cells = " | ".join(
                    _cell(per[n][(sid, cat)], phrases[n].get((sid, cat), [])) for n in names
                )
                diff.append(f"| {sid} | `{cat}` | {cells} |")

    adjacency = [
        f"- {n}: "
        + (", ".join(sorted({lb.sample_id for lb in annotated[n] if "6.4" in lb.notes})) or "none")
        for n in names
    ]
    return "\n".join(
        [
            f"Annotators: {', '.join(names)}. Turns: {len(sample_ids)}. "
            f"Units: {len(sample_ids)} turns × {len(RUBRIC)} categories. "
            f"Target: alpha ≥ {TARGET} (CLAUDE.md §10.4).",
            "",
            "### Agreement",
            "",
            *rows,
            "",
            "Alpha is `–` where it is undefined: every value the same, so there is no "
            "disagreement to expect (usually a category nobody recorded).",
            "",
            f"### Disagreements ({n_diff}), for 8.12",
            "",
            *(diff if n_diff else ["None."]),
            "",
            "### One-step stance cases noted `6.4` (rubric §7 point 1)",
            "",
            *adjacency,
        ]
    )


def write_results(doc: Path, block: str) -> None:
    text = doc.read_text(encoding="utf-8")
    start, end = text.index(RESULTS_START), text.index(RESULTS_END)
    doc.write_text(
        text[: start + len(RESULTS_START)] + "\n" + block + "\n" + text[end:], encoding="utf-8"
    )


def _parse(spec: str) -> tuple[str, Path]:
    name, sep, path = spec.partition("=")
    if not sep or not name.strip() or not path.strip():
        raise typer.BadParameter(f"{spec!r}: expected NAME=PATH, e.g. SD=labels.csv")
    return name.strip(), Path(path.strip())


app = typer.Typer(add_completion=False)


@app.command()
def main(
    labels: Annotated[
        list[str],
        typer.Option(help="NAME=PATH of one annotator's labels.csv. Give it once per annotator."),
    ],
    sample: Annotated[Path, typer.Option(help="The 8.10 sample.json.")] = Path(
        "results/checker_validation/sample.json"
    ),
    doc: Annotated[Path, typer.Option(help="Document whose results block is rewritten.")] = Path(
        "docs/rubric_pilot.md"
    ),
) -> None:
    """Compute Krippendorff's alpha between the annotators and write the results."""
    specs = [_parse(s) for s in labels]
    if len(specs) < 2:
        raise typer.BadParameter("give --labels for at least two annotators")
    if len({n for n, _ in specs}) != len(specs):
        raise typer.BadParameter("annotator names must differ")
    ids = [d["sample_id"] for d in json.loads(sample.read_text(encoding="utf-8"))]
    annotated = {name: read_labels(path, set(ids)) for name, path in specs}
    block = report(ids, annotated)
    write_results(doc, block)
    typer.echo(block)


if __name__ == "__main__":
    app()
