"""The three M1 figures of the report's Results (WBS 10.6).

    python -m adm.eval.figures --doc docs/figures.md

Drawn from the JSON reports that the 10.1 and 10.2 commands write
(`results/m1.json`, `results/m1_growth.json`), for docs/report_outline.md
section 5:

- **fig_m1_rate** (5.1, RQ1 and H1): (a) M1 per condition, divergences per 100
  narrated turns, with its 95% interval; (b) the ratios B/A, C/A and D/A with
  their intervals, against 1 (no difference) and H1's 0.5.
- **fig_m1_growth** (5.2, RQ2): the long-session rate in the 10.2 bins of ten
  scripted positions, one panel per condition with the other three in grey
  behind it, and the panel's slope with its interval in the title.
- **fig_m1_taxonomy** (5.3): the rate per rubric category per condition, with
  intervals and the count of divergences beside each condition.

**No new number.** Every value drawn is one the 10.1 or 10.2 report already
holds; this module computes no statistic, so none can be chosen for how it
looks. The two reports must come from the same labels and logs.

**Condition is never colour alone.** It is named by an axis position or a panel
title. Four hues on one plot cannot all be told apart under colour-vision
deficiency, so there is one series colour, with grey for context and reference
lines.

**Reproducible bytes.** PNG at 300 dpi and SVG, with no date or software stamp,
the bundled DejaVu Sans, a fixed SVG hash salt and LF line endings in the SVG, so
a second run with the same matplotlib writes the same files on any platform. The
docs block records the inputs' sha256 with line endings as LF, since
`Path.write_text` writes CRLF on Windows.

matplotlib is in the `analysis` extra, not `dev`. It is imported only to draw,
so the tests of everything else run in CI without it.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any

import typer

from adm.eval.m1_growth import BINS
from adm.eval.m1_rates import BASELINE, H1_RATIO
from adm.eval.metrics import write_results
from adm.eval.rubric_pilot import RUBRIC

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure

Doc = dict[str, Any]

CONDITIONS = ("A", "B", "C", "D")
CATEGORY_NAMES = {  # CLAUDE.md section 10.1
    "PHANTOM": "phantom entity",
    "CONTRADICT": "state contradiction",
    "RESOURCE": "resource error",
    "RELATION": "relationship contradiction",
}
NAMES = ("fig_m1_rate", "fig_m1_growth", "fig_m1_taxonomy")
FORMATS = ("png", "svg")
SECTIONS = {"fig_m1_rate": "5.1", "fig_m1_growth": "5.2", "fig_m1_taxonomy": "5.3"}

# One series colour (the dataviz reference palette's slot 1) and recessive inks.
SERIES = "#2a78d6"
CONTEXT = "#c9c8c3"
TEXT = "#0b0b0b"
TEXT_2 = "#52514e"
REFERENCE = "#8a8984"
GRID = "#e6e5e1"
SURFACE = "#ffffff"
H1_SHADE = "#eef4fc"

STYLE = {
    "font.family": "DejaVu Sans",
    "font.size": 8,
    "axes.titlesize": 8.5,
    "axes.labelsize": 8,
    "axes.edgecolor": REFERENCE,
    "axes.labelcolor": TEXT_2,
    "axes.titlecolor": TEXT,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.unicode_minus": True,
    "xtick.color": TEXT_2,
    "ytick.color": TEXT,
    "xtick.labelsize": 7.5,
    "ytick.labelsize": 8,
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
    "savefig.dpi": 300,
    "svg.hashsalt": "adm-wbs-10.6",
}
METADATA = {"png": {"Software": None}, "svg": {"Date": None, "Creator": None}}


class InputError(ValueError):
    """The 10.1 and 10.2 reports do not hold what the figures draw."""


@dataclass(frozen=True)
class Row:
    """One value with its 95% interval, drawn as a dot on a line."""

    label: str
    value: float
    low: float
    high: float


@dataclass(frozen=True)
class GrowthPanel:
    """One condition's long-session rate per bin, and its RQ2 slope."""

    condition: str
    rates: tuple[float | None, ...]
    slope: Row


# --- the data ------------------------------------------------------------------


def load(path: Path) -> Doc:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InputError(f"{path.as_posix()}: {exc}") from exc


def input_sha256(path: Path) -> str:
    """sha256 of the file with line endings as LF, the same on every platform."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _row(label: str, entry: Doc | None, where: str) -> Row:
    if not entry or entry.get("value") is None or not entry.get("interval"):
        raise InputError(f"{where}: no value with an interval")
    low, high = entry["interval"]
    return Row(label, entry["value"], low, high)


def _condition(report: Doc, key: str, condition: str) -> Doc:
    try:
        return report[key][condition]
    except (KeyError, TypeError) as exc:
        raise InputError(f"no condition {condition} under {key!r}") from exc


def check_inputs(m1: Doc, growth: Doc) -> None:
    """Both reports must be of the same labels, logs and bootstrap, and hold
    every condition."""
    for field in ("labels_sha256", "annotator", "manifest", "checksums"):
        a, b = m1.get("dataset", {}).get(field), growth.get("dataset", {}).get(field)
        if a != b:
            raise InputError(f"the 10.1 and 10.2 reports differ in {field}: {a} and {b}")
    if m1.get("bootstrap") != growth.get("bootstrap"):
        raise InputError("the 10.1 and 10.2 reports used different bootstraps")
    for c in CONDITIONS:
        _condition(m1, "conditions", c)
        _condition(growth, "conditions", c)


def rate_rows(m1: Doc) -> list[Row]:
    """M1 per condition with its interval (10.1)."""
    return [_row(c, _condition(m1, "conditions", c)["rate"], f"M1 rate of {c}") for c in CONDITIONS]


def ratio_rows(m1: Doc) -> list[Row]:
    """Each condition's rate over A's, all categories (10.1)."""
    return [
        _row(f"{c}/{BASELINE}", _condition(m1, "ratios", c)["all"], f"M1 ratio {c}/{BASELINE}")
        for c in CONDITIONS
        if c != BASELINE
    ]


def taxonomy_rows(m1: Doc) -> list[tuple[str, list[Row]]]:
    """Per rubric category, each condition's rate with its interval, labelled
    with the condition's count of divergences in that category (10.1)."""
    out = []
    for k in RUBRIC:
        rows = []
        for c in CONDITIONS:
            per = _condition(m1, "conditions", c)
            rows.append(
                _row(f"{c} ({per['divergences'][k]})", per["by_category"][k], f"{k} rate of {c}")
            )
        out.append((k, rows))
    return out


def bin_labels(growth: Doc) -> list[str]:
    """The 10.2 bins as axis labels; every condition must have exactly them."""
    expected = [[low, high] for low, high in BINS]
    for c in CONDITIONS:
        got = [b["positions"] for b in _condition(growth, "conditions", c)["bins"]]
        if got != expected:
            raise InputError(f"bins of {c} are {got}, not the 10.2 bins {expected}")
    return [f"{low}–{high}" if high else f"{low}+" for low, high in BINS]


def growth_panels(growth: Doc) -> list[GrowthPanel]:
    """Per condition, the long-session rate per bin and the RQ2 slope (10.2)."""
    bin_labels(growth)
    panels = []
    for c in CONDITIONS:
        per = _condition(growth, "conditions", c)
        panels.append(
            GrowthPanel(
                condition=c,
                rates=tuple(b["rate"] for b in per["bins"]),
                slope=_row(c, per["slope"], f"long-session slope of {c}"),
            )
        )
    return panels


def signed(value: float) -> str:
    """+5.7, −3.3: the sign always shown, with a true minus."""
    return f"{value:+.1f}".replace("-", "−")


# --- the drawing ---------------------------------------------------------------


def _upper(value: float, step: float) -> float:
    return step * math.ceil(value / step)


def _intervals(ax: Axes, rows: Sequence[Row], fmt: str) -> None:
    """Dots with interval lines, the first row on top, each labelled with its
    value just past the interval's upper end."""
    ys = list(range(len(rows) - 1, -1, -1))
    for y, r in zip(ys, rows, strict=True):
        ax.plot([r.low, r.high], [y, y], color=SERIES, lw=1.6, solid_capstyle="round", zorder=3)
        ax.plot(r.value, y, "o", ms=6, color=SERIES, mec=SURFACE, mew=0.8, zorder=4)
        ax.annotate(
            fmt.format(r.value),
            (r.high, y),
            xytext=(5, 0),
            textcoords="offset points",
            va="center",
            fontsize=7.5,
            color=TEXT_2,
        )
    ax.set_yticks(ys, [r.label for r in rows])
    ax.set_ylim(-0.6, len(rows) - 0.4)
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.grid(axis="x", color=GRID, lw=0.6)
    ax.set_axisbelow(True)


def rate_figure(m1: Doc) -> Figure:
    from matplotlib.figure import Figure

    fig = Figure(figsize=(7.0, 2.4), layout="constrained")
    a, b = fig.subplots(1, 2, gridspec_kw={"width_ratios": [1.1, 1]})

    rates = rate_rows(m1)
    _intervals(a, rates, "{:.1f}")
    a.set_xlim(0, _upper(max(r.high for r in rates) * 1.12, 10))
    a.set_title("(a) M1 per condition", loc="left")
    a.set_xlabel("Divergences per 100 narrated turns, 95% interval")

    ratios = ratio_rows(m1)
    top = max(2.0, _upper(max(r.high for r in ratios) * 1.12, 0.5))
    b.axvspan(0, H1_RATIO, color=H1_SHADE, lw=0, zorder=0)
    b.axvline(1, color=REFERENCE, lw=0.9, zorder=1)
    b.axvline(H1_RATIO, color=REFERENCE, lw=0.9, ls=(0, (3, 2)), zorder=1)
    _intervals(b, ratios, "{:.2f}")
    b.set_xlim(0, top)
    # H1's label sits left of its line, inside the shaded region; the other right of its own
    for x, text, dx, ha in (
        (H1_RATIO, f"H1: ≤ {H1_RATIO}", -3, "right"),
        (1, "no difference", 3, "left"),
    ):
        b.annotate(
            text,
            (x, 1),
            xycoords=("data", "axes fraction"),
            xytext=(dx, -2),
            textcoords="offset points",
            ha=ha,
            va="top",
            fontsize=7,
            color=TEXT_2,
        )
    b.set_title(f"(b) Ratio to condition {BASELINE}", loc="left")
    b.set_xlabel(f"Rate over condition {BASELINE}'s rate, 95% interval")
    return fig


def growth_figure(growth: Doc) -> Figure:
    from matplotlib.figure import Figure
    from matplotlib.lines import Line2D

    labels = bin_labels(growth)
    panels = growth_panels(growth)
    xs = list(range(len(labels)))
    values = [v for p in panels for v in p.rates if v is not None]
    fig = Figure(figsize=(7.0, 4.4), layout="constrained")
    axes = fig.subplots(2, 2, sharex=True, sharey=True)
    for ax, panel in zip(axes.flat, panels, strict=True):
        for other in panels:
            if other is not panel:
                ax.plot(xs, other.rates, color=CONTEXT, lw=1, zorder=1)
        ax.plot(xs, panel.rates, color=SERIES, lw=2, marker="o", ms=5, mec=SURFACE, mew=1, zorder=3)
        s = panel.slope
        ax.set_title(f"Condition {panel.condition}", loc="left", fontweight="bold")
        ax.set_title(
            f"slope {signed(s.value)} ({signed(s.low)} to {signed(s.high)})",
            loc="right",
            color=TEXT_2,
            fontsize=7.5,
        )
        ax.grid(axis="y", color=GRID, lw=0.6)
        ax.set_axisbelow(True)
    ax0 = axes.flat[0]
    ax0.set_xticks(xs, labels)
    ax0.set_ylim(0, _upper(max(values) * 1.1, 10))
    fig.supxlabel("Scripted position in the long session, bins of 10", fontsize=8, color=TEXT_2)
    fig.supylabel("Divergences per 100 narrated turns", fontsize=8, color=TEXT_2)
    handles = [
        Line2D([], [], color=SERIES, lw=2, marker="o", ms=5, mec=SURFACE, label="this condition"),
        Line2D([], [], color=CONTEXT, lw=1, label="the other three"),
    ]
    fig.legend(
        handles=handles,
        loc="outside upper right",
        ncols=2,
        frameon=False,
        fontsize=7.5,
        title="Slope: change per 100 turns for every 10 turns played, 95% interval",
        title_fontsize=7.5,
        alignment="right",
    )
    return fig


def taxonomy_figure(m1: Doc) -> Figure:
    from matplotlib.figure import Figure

    groups = taxonomy_rows(m1)
    fig = Figure(figsize=(7.0, 4.8), layout="constrained")
    axes = fig.subplots(len(groups), 1, sharex=True)
    top = _upper(max(r.high for _, rows in groups for r in rows) * 1.12, 5)
    for ax, (k, rows) in zip(axes, groups, strict=True):
        _intervals(ax, rows, "{:.1f}")
        ax.set_title(f"{k}: {CATEGORY_NAMES[k]}", loc="left")
        if ax is not axes[-1]:  # one x-axis, under the last panel
            ax.spines["bottom"].set_visible(False)
            ax.tick_params(axis="x", length=0)
    axes[-1].set_xlim(0, top)
    axes[-1].set_xlabel("Divergences per 100 narrated turns, 95% interval")
    fig.supylabel("Condition (count of divergences)", fontsize=8, color=TEXT_2)
    return fig


def draw(m1: Doc, growth: Doc, out_dir: Path) -> list[Path]:
    """Write the three figures as PNG and SVG; return the paths written."""
    import matplotlib

    check_inputs(m1, growth)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    with matplotlib.rc_context(STYLE):
        makers = {
            "fig_m1_rate": lambda: rate_figure(m1),
            "fig_m1_growth": lambda: growth_figure(growth),
            "fig_m1_taxonomy": lambda: taxonomy_figure(m1),
        }
        for name in NAMES:
            fig = makers[name]()
            for ext in FORMATS:
                path = out_dir / f"{name}.{ext}"
                buffer = io.BytesIO()
                fig.savefig(buffer, format=ext, metadata=METADATA[ext])
                data = buffer.getvalue()
                if ext == "svg":  # LF on every platform, as git stores it
                    data = data.replace(b"\r\n", b"\n")
                path.write_bytes(data)
                paths.append(path)
    return paths


# --- the report ----------------------------------------------------------------


def render(inputs: Sequence[tuple[str, Path]], paths: Sequence[Path], m1: Doc) -> str:
    """The results block of docs/figures.md: inputs, files and their sha256."""
    b = m1["bootstrap"]
    lines = [
        f"Drawn from the 10.1 and 10.2 reports of {m1['runs']} runs and {m1['turns']} "
        f"narrated turns, labels of {m1['dataset']['annotator']}. Intervals as computed "
        f"there: {b['confidence']:.0%} percentile bootstrap over whole runs, "
        f"{b['resamples']:,} resamples, seed {b['seed']}.",
        "",
        "### Inputs",
        "",
        "sha256 with line endings as LF.",
        "",
        "| Input | sha256 |",
        "|---|---|",
        *(f"| `{p.as_posix()}` ({task}) | `{input_sha256(p)}` |" for task, p in inputs),
        "",
        "### Files",
        "",
        "| Figure | Report section | File | sha256 |",
        "|---|---|---|---|",
    ]
    for path in paths:
        name = path.stem
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"| {name} | {SECTIONS[name]} | `{path.as_posix()}` | `{digest}` |")
    return "\n".join(lines)


# --- the command ---------------------------------------------------------------

app = typer.Typer(add_completion=False)


@app.command()
def main(
    m1_path: Annotated[Path, typer.Option("--m1", help="The 10.1 report (m1_rates).")] = Path(
        "results/m1.json"
    ),
    growth_path: Annotated[
        Path, typer.Option("--growth", help="The 10.2 report (m1_growth).")
    ] = Path("results/m1_growth.json"),
    out: Annotated[Path, typer.Option(help="Directory the figures are written to.")] = Path(
        "docs/report/figures"
    ),
    doc: Annotated[
        Path | None, typer.Option(help="Document whose results block is rewritten.")
    ] = None,
) -> None:
    """Draw the M1 figures of the report: rate, growth, taxonomy (WBS 10.6)."""
    try:
        m1, growth = load(m1_path), load(growth_path)
        paths = draw(m1, growth, out)
    except InputError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    block = render([("10.1", m1_path), ("10.2", growth_path)], paths, m1)
    if doc is not None:
        write_results(doc, block)
    typer.echo(block)


if __name__ == "__main__":
    app()
