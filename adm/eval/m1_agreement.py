"""M1 agreement check (WBS 9.6): the overlap labels of two annotators pair up.

    python -m adm.eval.m1_agreement --labels results/m1_labels.jsonl \\
        --labels results/m1_labels_SS.jsonl

9.6 is done when agreement is computable. This checks that it is, on the label
files the annotation tool writes (`python -m adm.eval.annotate m1`), and prints
the agreement:

1. **The overlap** is recomputed from the logs (`m1.overlap_runs`, 16 runs on
   the main grid), so a file that covers a different sample is caught.
2. **Pairing.** The second annotator has exactly one line for every overlap
   turn and none outside it; the first annotator has one for every overlap
   turn; both were shown the same checker candidates. Any failure is refused
   with every problem listed.
3. **Agreement** uses the unit of the rubric pilot (decision 58,
   `adm/eval/rubric_pilot.py`): one turn and one rubric category, valued by the
   number of divergences recorded, confirmed candidates plus added labels.
   Krippendorff's alpha is interval on those counts, per category and pooled,
   and nominal on whether a turn has any divergence. `RULE` is M4, not a rubric
   category, and is left out.

It writes nothing. WBS 10.5 reports the agreement.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Annotated, Any

import typer

from adm.eval import m1
from adm.eval.annotate import load_runs, load_scenarios
from adm.eval.rubric_pilot import RUBRIC, TARGET, alpha

Doc = dict[str, Any]
Pair = tuple[Doc, Doc]


class OverlapError(ValueError):
    """The two annotators' overlap labels do not pair up."""


def label_counts(line: Doc) -> Counter[str]:
    """Divergences per rubric category in one annotated turn."""
    found = [c["category"] for c in line["candidates"] if c["confirmed"]]
    found += [a["category"] for a in line["added"]]
    return Counter(c for c in found if c in RUBRIC)


def _shown(line: Doc) -> list[Doc]:
    return [{f: c.get(f) for f in m1.CANDIDATE_FIELDS} for c in line["candidates"]]


def _n(count: int, noun: str) -> str:
    return f"{count} {noun}" + ("" if count == 1 else "s")


def _ids(ids: Sequence[str]) -> str:
    return ", ".join(ids[:5]) + (" …" if len(ids) > 5 else "")


def pair(lines: Sequence[Doc], first: str, second: str, turn_ids: Sequence[str]) -> list[Pair]:
    """The (first, second) lines of every overlap turn, in `turn_ids` order."""
    problems: list[str] = []
    by: dict[str, dict[str, Doc]] = {first: {}, second: {}}
    for name in (first, second):
        dupes = []
        for ln in lines:
            if ln["annotator"] != name:
                continue
            if ln["turn_id"] in by[name]:
                dupes.append(ln["turn_id"])
            by[name][ln["turn_id"]] = ln
        if dupes:
            problems.append(f"{name} has {_n(len(dupes), 'duplicate line')}: {_ids(dupes)}")
    wanted = set(turn_ids)
    for name in (first, second):
        missing = [t for t in turn_ids if t not in by[name]]
        if missing:
            problems.append(f"{name} has no line for {_n(len(missing), 'turn')}: {_ids(missing)}")
    outside = sorted(t for t in by[second] if t not in wanted)
    if outside:
        lines_out = _n(len(outside), "line")
        problems.append(f"{second} has {lines_out} outside the overlap: {_ids(outside)}")
    differ = [
        t
        for t in turn_ids
        if t in by[first] and t in by[second] and _shown(by[first][t]) != _shown(by[second][t])
    ]
    if differ:
        problems.append(
            f"{_n(len(differ), 'turn')} shown with different checker candidates: {_ids(differ)}"
        )
    if problems:
        raise OverlapError("; ".join(problems))
    return [(by[first][t], by[second][t]) for t in turn_ids]


def _fmt(a: float | None) -> str:
    return "–" if a is None else f"{a:.3f}"


def _meets(a: float | None) -> str:
    return "–" if a is None else ("yes" if a >= TARGET else "**no**")


def report(pairs: Sequence[Pair], first: str, second: str) -> str:
    """A Markdown table of the agreement on the paired overlap."""
    per: Mapping[str, list[Counter[str]]] = {
        first: [label_counts(a) for a, _ in pairs],
        second: [label_counts(b) for _, b in pairs],
    }
    names = (first, second)
    rows = [
        f"| {len(pairs)} turns | {first} | {second} | Alpha | Metric | Meets {TARGET} |",
        "|---|---|---|---|---|---|",
    ]

    def row(title: str, categories: Sequence[str]) -> None:
        units: list[list[float | None]] = [
            [float(per[n][i][c]) for n in names] for i in range(len(pairs)) for c in categories
        ]
        a = alpha(units, "interval")
        totals = " | ".join(str(sum(c[k] for c in per[n] for k in categories)) for n in names)
        rows.append(f"| {title} | {totals} | {_fmt(a)} | interval | {_meets(a)} |")

    for category in RUBRIC:
        row(f"`{category}`", [category])
    row("**All four, pooled**", RUBRIC)
    any_units: list[list[float | None]] = [
        [float(bool(+per[n][i])) for n in names] for i in range(len(pairs))
    ]
    a_any = alpha(any_units, "nominal")
    turns_any = " | ".join(str(sum(bool(+c) for c in per[n])) for n in names)
    rows.append(
        f"| Turn has any divergence | {turns_any} | {_fmt(a_any)} | nominal | {_meets(a_any)} |"
    )
    differ = sum(per[first][i][c] != per[second][i][c] for i in range(len(pairs)) for c in RUBRIC)
    rows.append(f"| Units that differ | {differ} | of {len(pairs) * len(RUBRIC)} | | | |")
    return "\n".join(rows)


def read_lines(paths: Sequence[Path]) -> list[Doc]:
    return [
        json.loads(text)
        for path in paths
        for text in path.read_text(encoding="utf-8").splitlines()
        if text.strip()
    ]


app = typer.Typer(add_completion=False)


@app.command()
def main(
    labels: Annotated[
        list[Path], typer.Option(help="An m1_labels.jsonl file. Give it once per file.")
    ],
    first: Annotated[str, typer.Option(help="The first annotator (9.5).")] = "SD",
    second: Annotated[str, typer.Option(help="The overlap annotator (9.6).")] = "SS",
    runs: Annotated[Path, typer.Option(help="Directory of the run logs.")] = Path("runs"),
    scenarios: Annotated[Path, typer.Option(help="Directory of the scenario files.")] = Path(
        "scenarios"
    ),
) -> None:
    """Check the M1 overlap pairs up and print Krippendorff's alpha."""
    if first == second:
        raise typer.BadParameter("the two annotators must differ")
    logs = load_runs(runs)
    overlap = m1.overlap_runs(m1.draw_runs(sorted(logs)))
    found = load_scenarios(scenarios, {sid for _, sid, _ in overlap})
    turn_ids = [t.turn_id for t in m1.sample_turns(overlap, logs, found)]
    try:
        pairs = pair(read_lines(labels), first, second, turn_ids)
    except OverlapError as exc:
        typer.echo(f"Agreement is not computable: {exc}", err=True)
        raise typer.Exit(1) from exc
    typer.echo(f"{len(overlap)} overlap runs, {len(pairs)} turns paired.\n")
    typer.echo(report(pairs, first, second))


if __name__ == "__main__":
    app()
