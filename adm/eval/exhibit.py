"""The side-by-side condition A versus D exhibit: one defence slide (WBS 10.8).

    python -m adm.eval.exhibit --checksums experiments/main_grid.sha256 \\
        --doc docs/exhibit_a_vs_d.md

**A pair** is one scripted combat input at one seed of the M1 sample, with
condition A's and condition D's narrated turns beside each other: the
scenario's `expected_call` is an `attack` or `cast_spell`, and D executed a
call of the same tool. **Two rows**, fixed before the draw (docs/decisions.md,
2026-11-19): row 1, what the engine fixes (A has a `CONTRADICT` or `RULE`
label, D has none at all); row 2, what it does not (D has a `CONTRADICT`
label though its narrator had the facts). Within a row the qualifying pairs are
taken in sha256 order, the first one used, the two rows on different inputs.

**Each side** shows its narration with the labelled divergences in bold (SD's
9.5 labels, rubric v1.0) and the truth it is scored against for the combatants
the call names: A's replayed ground truth, D's logged state and D's facts.

**The slide carries the measured result** of 10.1 (`results/m1.json`) so that
the two rows are never read as the overall finding: H1 is not supported.

The slide is PNG and SVG in the style of `adm/eval/figures.py`; matplotlib is
imported only to draw it.
"""

from __future__ import annotations

import hashlib
import io
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any

import typer

from adm.engine.combat import hp_band
from adm.engine.scenario import Scenario
from adm.eval import m1
from adm.eval.catalogue import Mark, attempts, facts, marked, marks
from adm.eval.figures import METADATA, REFERENCE, SERIES, STYLE, SURFACE, TEXT, TEXT_2, load
from adm.eval.integrity import file_sha256, load_plan
from adm.eval.m1_agreement import read_lines
from adm.eval.m1_rates import LabelError, load_sample_logs, runs_m1
from adm.eval.metrics import DatasetError, write_results

if TYPE_CHECKING:
    from matplotlib.figure import Figure

Doc = dict[str, Any]

DRAW = "10.8-v1"
COMBAT = ("attack", "cast_spell")
MECHANICAL = ("CONTRADICT", "RULE")
ACTOR_FIELDS = ("target_id", "attacker_id", "caster_id")
FORMATS = ("png", "svg")
NAME = "fig_a_vs_d"


class ExhibitError(ValueError):
    """A row cannot be filled from the data as the rule says."""


@dataclass(frozen=True)
class Side:
    """One condition's turn at the pair's input."""

    run_id: str
    narration: str
    marks: tuple[Mark, ...]
    state: Doc  # the state the turn is scored against
    call: Doc | None  # D's executed call; A's replayed expected call
    record: Doc


@dataclass(frozen=True)
class Pair:
    scenario_id: str
    seed: int
    input_index: int
    player_input: str
    a: Side
    d: Side

    @property
    def unit(self) -> str:
        return f"{self.scenario_id}/{self.seed}/{self.input_index}"


@dataclass(frozen=True)
class Row:
    number: int
    title: str
    rule: str
    test: Callable[[Pair], bool]


def _fixes(p: Pair) -> bool:
    return any(m.category in MECHANICAL for m in p.a.marks) and not p.d.marks


def _does_not(p: Pair) -> bool:
    return any(m.category == "CONTRADICT" for m in p.d.marks)


ROWS = (
    Row(1, "What the engine fixes", "A has a CONTRADICT or RULE label, D has none", _fixes),
    Row(
        2, "What it does not", "D has a CONTRADICT label, though it was given the facts", _does_not
    ),
)


# --- the pairs -----------------------------------------------------------------


def pairs(
    items: Sequence[Any],
    lines: Sequence[Doc],
    annotator: str,
    scenarios: Mapping[str, Scenario],
) -> list[Pair]:
    """Every combat input of the sample with A's and D's narrated turns."""
    mine = {line["turn_id"]: line for line in lines if line.get("annotator") == annotator}
    sides: dict[tuple[str, int, int], dict[str, Side]] = {}
    for item in items:
        r = item.turn.record
        if r["condition"] not in ("A", "D"):
            continue
        side = Side(
            run_id=r["run_id"],
            narration=item.turn.narration,
            marks=tuple(marks(mine[item.turn_id], item.turn.narration)),
            state=item.turn.state,
            call=item.turn.call,
            record=r,
        )
        sides.setdefault((r["scenario_id"], r["seed"], r["input_index"]), {})[r["condition"]] = side
    out = []
    for (sid, seed, index), both in sorted(sides.items()):
        if set(both) != {"A", "D"}:
            continue  # D's turn at this input failed, so it is not narrated
        expected = scenarios[sid].scripted_inputs[index].expected_call
        executed = both["D"].call
        if not expected or expected["tool"] not in COMBAT:
            continue
        if not executed or executed.get("tool") != expected["tool"]:
            continue
        player_input = both["A"].record["player_input"]
        out.append(Pair(sid, seed, index, player_input, both["A"], both["D"]))
    return out


def draw_key(row: Row, pair: Pair) -> str:
    return hashlib.sha256(f"{DRAW}/{row.number}/{pair.unit}".encode()).hexdigest()


def draw(candidates: Sequence[Pair]) -> list[tuple[Row, Pair, int]]:
    """Each row's pair: the first qualifying pair in its hash order, on an input
    no earlier row used; with the size of the row's pool."""
    used: set[str] = set()
    out = []
    for row in ROWS:
        pool = [p for p in candidates if row.test(p)]
        chosen = next(
            (p for p in sorted(pool, key=lambda p: draw_key(row, p)) if p.unit not in used), None
        )
        if chosen is None:
            raise ExhibitError(f"row {row.number}: no pair qualifies")
        used.add(chosen.unit)
        out.append((row, chosen, len(pool)))
    return out


# --- what each side shows ------------------------------------------------------


def named(pair: Pair) -> list[str]:
    """The combatants the call names, target first: from A's replayed call and
    D's executed call."""
    ids: list[str] = []
    for side in (pair.a, pair.d):
        args = (side.call or {}).get("arguments", {})
        for f in ACTOR_FIELDS:
            if args.get(f) and args[f] not in ids:
                ids.append(args[f])
    return ids


def brief(state: Doc, ids: Sequence[str]) -> list[str]:
    """One short line per named combatant: name, HP, band, status."""
    out = []
    for cid in ids:
        c = state["combatants"].get(cid)
        if c is not None:
            band = hp_band(c["current_hp"], c["max_hp"]).replace("_", " ")
            out.append(
                f"{c['display_name']}: {c['current_hp']}/{c['max_hp']} HP, {band}, {c['status']}"
            )
    return out


def fact_line(f: Doc) -> str:
    """One readable line for an attack or spell's narration facts."""
    actor = f.get("attacker") or f.get("caster") or "?"
    means = f.get("weapon") or f.get("spell") or "action"
    target = f.get("target", "?")
    if "hit" in f:
        how = "critical hit on" if f.get("critical") else ("hits" if f["hit"] else "misses")
        roll = f" (roll {f['attack_roll']} vs AC {f['target_ac']})" if "attack_roll" in f else ""
        head = f"{actor}'s {means} {how} {target}{roll}"
    else:
        head = f"{actor}'s {means} on {target}"
    if "target_hp_after" in f:
        band = str(f.get("target_hp_band", "")).replace("_", " ")
        head += (
            f": {f['target_hp_before']} to {f['target_hp_after']} of {f['target_hp_max']} HP, "
            f"{band}, {f.get('target_status', '')}"
        )
    return head


def segments(narration: str, found: Sequence[Mark]) -> list[tuple[str, bool]]:
    """The narration as (text, bold) runs, each labelled span bold; a span that
    overlaps an earlier one stays plain."""
    out, at = [], 0
    for start, end in sorted(m.span for m in found if m.span):
        if start < at or end > len(narration):
            continue
        out += [(narration[at:start], False), (narration[start:end], True)]
        at = end
    out.append((narration[at:], False))
    return [(" ".join(t.split()), b) for t, b in out if t.strip()]


# --- the slide -----------------------------------------------------------------


def measured(m1_report: Doc) -> str:
    """The 10.1 result the slide must carry."""
    per = m1_report["conditions"]
    a, d = per["A"], per["D"]
    h1 = m1_report["h1"]
    low, high = h1["interval"]
    return (
        f"Measured over the whole M1 sample: A {a['rate']['value']:.1f} and D "
        f"{d['rate']['value']:.1f} divergences per 100 narrated turns ({a['turns']} and "
        f"{d['turns']} turns); D/A {h1['ratio']:.2f}, 95% interval {low:.2f} to {high:.2f}. "
        f"H1 (D/A at most 0.5) is not supported. Both rows are drawn by a fixed rule; "
        f"neither is the average."
    )


TITLE = "The engine makes the numbers right. It does not make the narrator use them."
SUBTITLE = (
    "Same scripted input, same seed: condition A (the model narrates alone) beside "
    "condition D (the rules engine resolves the action, the model narrates its facts)."
)
KEY = (
    "Bold: a divergence labelled under rubric v1.0 (first annotator). "
    "Sources: docs/exhibit_a_vs_d.md, docs/m1_rates.md."
)
LEFT, COL_A, COL_D, COL_W, LABEL_W, FULL_W = 0.04, 0.215, 0.605, 0.355, 0.15, 0.92


@dataclass(frozen=True)
class _Pen:
    """Writes word-wrapped text on a figure, in figure fractions."""

    fig: Figure

    def write(
        self,
        x: float,
        y: float,
        width: float,
        runs: Sequence[tuple[str, bool]],
        size: float,
        color: str = TEXT,
    ) -> float:
        """Draw (text, bold) runs word by word from the top-left (x, y),
        wrapping at `width`; return the y below the last line."""
        renderer = self.fig.canvas.get_renderer()
        fw, fh = self.fig.bbox.width, self.fig.bbox.height
        line = size * 1.4 * self.fig.dpi / 72 / fh
        space = size * 0.3 * self.fig.dpi / 72 / fw
        cx = x
        for text, bold in runs:
            for word in text.split():
                weight = "bold" if bold else "normal"
                t = self.fig.text(cx, y, word, fontsize=size, color=color, va="top")
                t.set_fontweight(weight)
                w = t.get_window_extent(renderer).width / fw
                if cx > x and cx + w > x + width:
                    cx, y = x, y - line
                    t.set_position((cx, y))
                cx += w + space
        return y - line

    def rule(self, y: float) -> None:
        from matplotlib.lines import Line2D

        line = Line2D([LEFT, LEFT + FULL_W], [y, y], color=REFERENCE, lw=0.6)
        line.set_transform(self.fig.transFigure)
        self.fig.lines.append(line)


def _side(pen: _Pen, x: float, y: float, side: Side, truth, size: float) -> float:
    y = pen.write(x, y, COL_W, segments(side.narration, side.marks), size)
    for label, lines in truth:
        y = pen.write(
            x, y - 0.006, COL_W, [(label, True), ("; ".join(lines), False)], size - 1.5, TEXT_2
        )
    return y


def _row(pen: _Pen, y: float, row: Row, pair: Pair, size: float) -> float:
    yl = pen.write(LEFT, y, LABEL_W, [(f"{row.number}. {row.title}", True)], 11)
    yl = pen.write(LEFT, yl - 0.006, LABEL_W, [(f'"{pair.player_input}"', False)], 9.5, TEXT_2)
    where = f"{pair.scenario_id}, seed {pair.seed}, input {pair.input_index}"
    yl = pen.write(LEFT, yl - 0.006, LABEL_W, [(where, False)], 8, TEXT_2)
    ids = named(pair)
    ya = _side(pen, COL_A, y, pair.a, [("Truth (replay): ", brief(pair.a.state, ids))], size)
    d_truth = [
        ("Facts given: ", [fact_line(f) for f in facts(pair.d.record)]),
        ("Truth (engine): ", brief(pair.d.state, ids)),
    ]
    yd = _side(pen, COL_D, y, pair.d, d_truth, size)
    return min(ya, yd, yl)


def slide(rows: Sequence[tuple[Row, Pair, int]], m1_report: Doc, size: float = 10.5) -> Figure:
    """The 16:9 slide: two rows, A beside D, the measured result underneath.
    The narration shrinks until everything fits."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    while True:
        fig = Figure(figsize=(13.333, 7.5))
        FigureCanvasAgg(fig)
        pen = _Pen(fig)
        pen.write(LEFT, 0.955, FULL_W, [(TITLE, True)], 19)
        pen.write(LEFT, 0.895, FULL_W, [(SUBTITLE, False)], 11, TEXT_2)
        y = 0.835
        pen.write(COL_A, y, COL_W, [("Condition A", True)], 11, SERIES)
        pen.write(COL_D, y, COL_W, [("Condition D", True)], 11, SERIES)
        y -= 0.04
        for row, pair, _ in rows:
            pen.rule(y + 0.012)
            y = _row(pen, y, row, pair, size) - 0.03
        pen.rule(y + 0.012)
        y = pen.write(LEFT, y, FULL_W, [(measured(m1_report), False)], 9.5)
        y = pen.write(LEFT, y - 0.004, FULL_W, [(KEY, False)], 8, TEXT_2)
        if y > 0.03 or size <= 7:
            return fig
        size -= 0.5


def write_slide(rows: Sequence[tuple[Row, Pair, int]], m1_report: Doc, out_dir: Path) -> list[Path]:
    import matplotlib

    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    with matplotlib.rc_context({**STYLE, "savefig.dpi": 150}):
        fig = slide(rows, m1_report)
        for ext in FORMATS:
            buffer = io.BytesIO()
            fig.savefig(buffer, format=ext, metadata=METADATA[ext], facecolor=SURFACE)
            data = buffer.getvalue()
            if ext == "svg":  # LF on every platform, as git stores it
                data = data.replace(b"\r\n", b"\n")
            path = out_dir / f"{NAME}.{ext}"
            path.write_bytes(data)
            paths.append(path)
    return paths


# --- the doc -------------------------------------------------------------------


def _q(text: str) -> str:
    return " ".join(text.split()).replace("|", "\\|")


def _labels(side: Side) -> list[str]:
    if not side.marks:
        return ["No divergence labelled."]
    return [f'{i}. `{m.category}` "{_q(m.phrase)}"' for i, m in enumerate(side.marks, 1)]


def render(rows: Sequence[tuple[Row, Pair, int]], m1_report: Doc, paths: Sequence[Path]) -> str:
    out = [
        measured(m1_report),
        "",
        "| Row | Rule | Pair | Drawn from |",
        "|---|---|---|---|",
        *(
            f"| {row.number}. {row.title} | {row.rule} | `{p.scenario_id}`, seed {p.seed}, "
            f"input {p.input_index} | {pool} pairs |"
            for row, p, pool in rows
        ),
    ]
    for row, p, _ in rows:
        ids = named(p)
        out += [
            "",
            f"### Row {row.number}. {row.title}",
            "",
            f"**Player** (`{p.scenario_id}`, seed {p.seed}, scripted input {p.input_index}): "
            f'"{_q(p.player_input)}"',
            "",
            f"#### Condition A (`{p.a.run_id}`)",
            "",
            f"> {marked(p.a.narration, p.a.marks)}",
            "",
            *_labels(p.a),
            "",
            "Truth it is scored against (replayed ground truth): "
            + "; ".join(brief(p.a.state, ids)),
            "",
            f"#### Condition D (`{p.d.run_id}`)",
            "",
            "Tool-call attempts:",
            "",
            *(f"{i}. `{a}`" for i, a in enumerate(attempts(p.d.record), 1)),
            "",
            "Facts given to the narrator:",
            "",
            *(f"- {fact_line(f)}" for f in facts(p.d.record)),
            "",
            f"> {marked(p.d.narration, p.d.marks)}",
            "",
            *_labels(p.d),
            "",
            "Truth it is scored against (logged state): " + "; ".join(brief(p.d.state, ids)),
        ]
    out += ["", "### Files", "", "| File | sha256 |", "|---|---|"]
    out += [f"| `{p.as_posix()}` | `{hashlib.sha256(p.read_bytes()).hexdigest()}` |" for p in paths]
    return "\n".join(out)


# --- the command ---------------------------------------------------------------

app = typer.Typer(add_completion=False)


@app.command()
def main(
    labels: Annotated[Path, typer.Option(help="The first annotator's m1_labels.jsonl.")] = Path(
        "results/m1_labels.jsonl"
    ),
    annotator: Annotated[str, typer.Option(help="The first annotator (9.5).")] = "SD",
    m1_path: Annotated[Path, typer.Option("--m1", help="The 10.1 report (m1_rates).")] = Path(
        "results/m1.json"
    ),
    runs: Annotated[Path, typer.Option(help="The runs directory.")] = Path("runs"),
    manifest: Annotated[Path, typer.Option(help="The batch manifest of the dataset.")] = Path(
        "experiments/main_grid.json"
    ),
    checksums: Annotated[
        Path | None, typer.Option(help="sha256sum file the logs must match (decision 60).")
    ] = None,
    out: Annotated[Path, typer.Option(help="Directory the slide is written to.")] = Path(
        "docs/report/figures"
    ),
    doc: Annotated[
        Path | None, typer.Option(help="Document whose results block is rewritten.")
    ] = None,
) -> None:
    """Draw the A-versus-D exhibit and its slide (WBS 10.8)."""
    try:
        m1_report = load(m1_path)
        if m1_report["dataset"]["labels_sha256"] != file_sha256(labels):
            raise ExhibitError(f"{m1_path.as_posix()} is not of these labels")
        _, scenarios, _ = load_plan(manifest)
        logs = load_sample_logs(runs, manifest, checksums)
        sample = sorted(logs)
        items = list(m1.sample_turns(sample, logs, scenarios))
        lines = read_lines([labels])
        runs_m1(sample, items, lines, annotator)  # the labels are checked as in 10.1
        rows = draw(pairs(items, lines, annotator, scenarios))
    except (DatasetError, LabelError, ExhibitError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    paths = write_slide(rows, m1_report, out)
    if doc is not None:
        write_results(doc, render(rows, m1_report, paths))
    for row, p, pool in rows:  # ASCII only: the Windows console cannot print the narration
        typer.echo(f"row {row.number}: {p.unit} (from {pool})")


if __name__ == "__main__":
    app()
