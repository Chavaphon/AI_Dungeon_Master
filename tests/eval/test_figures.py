"""The three M1 figures of the report (WBS 10.6): rate by condition, growth
curves and error taxonomy, drawn from the 10.1 and 10.2 reports.

The reports are built by `m1_rates.m1_report` and `m1_growth.growth_report`
from hand-made runs, so the figures are tested against the shape those
commands write, after a JSON round trip. No test reads the logs or calls a
model. The drawing tests need matplotlib (the `analysis` extra) and are
skipped without it.

Run: pytest tests/eval/test_figures.py -v
"""

import json
from pathlib import Path

import pytest

from adm.eval import figures, m1_growth, m1_rates
from adm.eval.figures import InputError
from adm.eval.m1_growth import RunTurns
from adm.eval.m1_rates import RunM1
from adm.eval.rubric_pilot import RUBRIC

DATASET = {
    "manifest": "experiments/main_grid.json",
    "checksums": "experiments/main_grid.sha256",
    "labels": "results/m1_labels.jsonl",
    "labels_sha256": "ab" * 32,
    "annotator": "SD",
}
ZERO = dict.fromkeys(RUBRIC, 0)


def _roundtrip(report: dict) -> dict:
    return json.loads(json.dumps({"dataset": dict(DATASET), **report}))


@pytest.fixture
def m1() -> dict:
    runs = []
    for i, c in enumerate("ABCD"):
        for seed, extra in ((2001, 0), (2002, 3)):
            counts = {**ZERO, "PHANTOM": 4 + i + extra, "CONTRADICT": 2 + extra, "RELATION": i}
            runs.append(RunM1((c, "s01_cellar", seed), 20, counts, 5))
    return _roundtrip(m1_rates.m1_report(runs, resamples=200))


@pytest.fixture
def growth() -> dict:
    runs = []
    for i, c in enumerate("ABCD"):
        for seed in (2001, 2002):
            points = tuple(
                (x, {**ZERO, "CONTRADICT": int((x + seed + i) % (3 + i) == 0)})
                for x in range(1, 53)
            )
            runs.append(RunTurns((c, "long01_border_road", seed), points))
    return _roundtrip(m1_growth.growth_report(runs, resamples=200))


def test_rate_rows_are_the_10_1_rates_in_condition_order(m1: dict) -> None:
    rows = figures.rate_rows(m1)
    assert [r.label for r in rows] == ["A", "B", "C", "D"]
    for r in rows:
        rate = m1["conditions"][r.label]["rate"]
        assert (r.value, [r.low, r.high]) == (rate["value"], rate["interval"])
        assert r.low <= r.value <= r.high


def test_ratio_rows_are_to_condition_a_and_leave_it_out(m1: dict) -> None:
    rows = figures.ratio_rows(m1)
    assert [r.label for r in rows] == ["B/A", "C/A", "D/A"]
    assert rows[-1].value == m1["ratios"]["D"]["all"]["value"] == m1["h1"]["ratio"]


def test_taxonomy_has_each_rubric_category_with_counts_beside_conditions(m1: dict) -> None:
    groups = figures.taxonomy_rows(m1)
    assert [k for k, _ in groups] == list(RUBRIC)
    phantom = dict(groups)["PHANTOM"]
    assert [r.label for r in phantom] == ["A (11)", "B (13)", "C (15)", "D (17)"]
    assert phantom[0].value == m1["conditions"]["A"]["by_category"]["PHANTOM"]["value"]


def test_growth_panels_take_the_10_2_bins_and_slopes(growth: dict) -> None:
    assert figures.bin_labels(growth) == ["1–10", "11–20", "21–30", "31–40", "41+"]
    panels = figures.growth_panels(growth)
    assert [p.condition for p in panels] == ["A", "B", "C", "D"]
    d = growth["conditions"]["D"]
    assert panels[-1].rates == tuple(b["rate"] for b in d["bins"])
    assert (panels[-1].slope.value, [panels[-1].slope.low, panels[-1].slope.high]) == (
        d["slope"]["value"],
        d["slope"]["interval"],
    )
    assert figures.signed(-3.25) == "−3.2" and figures.signed(5.7) == "+5.7"


def test_reports_of_different_labels_or_bootstraps_are_refused(m1: dict, growth: dict) -> None:
    figures.check_inputs(m1, growth)
    other = {**growth, "dataset": {**growth["dataset"], "labels_sha256": "cd" * 32}}
    with pytest.raises(InputError, match="labels_sha256"):
        figures.check_inputs(m1, other)
    with pytest.raises(InputError, match="bootstraps"):
        figures.check_inputs(m1, {**growth, "bootstrap": {**growth["bootstrap"], "seed": 1}})


def test_a_missing_condition_interval_or_bin_is_refused(m1: dict, growth: dict) -> None:
    del m1["conditions"]["C"]
    with pytest.raises(InputError, match="condition C"):
        figures.rate_rows(m1)
    growth["conditions"]["B"]["slope"]["interval"] = None
    with pytest.raises(InputError, match="slope of B"):
        figures.growth_panels(growth)
    growth["conditions"]["A"]["bins"][-1]["positions"] = [41, 50]
    with pytest.raises(InputError, match="bins of A"):
        figures.bin_labels(growth)


def test_input_hash_is_the_same_with_crlf_and_lf(tmp_path: Path) -> None:
    lf, crlf = tmp_path / "lf.json", tmp_path / "crlf.json"
    lf.write_bytes(b'{\n  "a": 1\n}\n')
    crlf.write_bytes(b'{\r\n  "a": 1\r\n}\r\n')
    assert figures.input_sha256(lf) == figures.input_sha256(crlf)


def test_figures_are_written_and_a_second_run_gives_the_same_bytes(
    m1: dict, growth: dict, tmp_path: Path
) -> None:
    pytest.importorskip("matplotlib")
    first = figures.draw(m1, growth, tmp_path / "one")
    second = figures.draw(m1, growth, tmp_path / "two")
    assert [p.name for p in first] == [
        f"{name}.{ext}" for name in figures.NAMES for ext in figures.FORMATS
    ]
    for a, b in zip(first, second, strict=True):
        assert a.read_bytes() == b.read_bytes(), a.name
    assert first[0].read_bytes().startswith(b"\x89PNG")
    assert all(b"\r\n" not in p.read_bytes() for p in first if p.suffix == ".svg")


def test_results_block_names_inputs_and_every_file(m1: dict, growth: dict, tmp_path: Path) -> None:
    pytest.importorskip("matplotlib")
    m1_path, growth_path = tmp_path / "m1.json", tmp_path / "m1_growth.json"
    m1_path.write_text(json.dumps(m1), encoding="utf-8")
    growth_path.write_text(json.dumps(growth), encoding="utf-8")
    paths = figures.draw(m1, growth, tmp_path / "out")
    block = figures.render([("10.1", m1_path), ("10.2", growth_path)], paths, m1)
    assert figures.input_sha256(m1_path) in block
    assert all(p.as_posix() in block for p in paths)
    assert block.isascii()  # the Windows console cannot print a true minus
