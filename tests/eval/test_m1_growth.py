"""M1 growth against turn index (WBS 10.2, RQ2): the pooled slope of
divergences per turn on the scripted position, per condition, the difference
from condition A, and the bins for the growth-curve figure.

The sampled turns are stand-ins with the attributes the count reads (`turn_id`,
`run_id`, `candidates`, `input_index`); the labels are hand-built lines in the
format the annotation tool writes. No test reads the logs or calls a model.

Run: pytest tests/eval/test_m1_growth.py -v
"""

from types import SimpleNamespace

import pytest

from adm.eval import m1_growth
from adm.eval.m1_growth import RunTurns
from adm.eval.m1_rates import LabelError

ZERO = {"PHANTOM": 0, "CONTRADICT": 0, "RESOURCE": 0, "RELATION": 0}


def item(turn_id: str, rid: str, input_index: int) -> SimpleNamespace:
    return SimpleNamespace(turn_id=turn_id, run_id=rid, candidates=(), input_index=input_index)


def line(turn_id: str, rid: str, added=(), annotator="SD") -> dict:
    return {
        "turn_id": turn_id,
        "run_id": rid,
        "annotator": annotator,
        "candidates": [],
        "added": [{"category": c, "phrase": "x", "span": [0, 1]} for c in added],
        "note": "",
    }


def run(condition: str, ys: list[int], scenario="long01_border_road", seed=2001, start=1):
    """A run whose turn at position start+i has ys[i] CONTRADICT divergences."""
    points = tuple((start + i, {**ZERO, "CONTRADICT": y}) for i, y in enumerate(ys))
    return RunTurns((condition, scenario, seed), points)


def test_position_is_input_index_plus_one_and_skipped_inputs_leave_a_gap() -> None:
    key = ("D", "long01_border_road", 2001)
    rid = "D_long01_border_road_2001"
    # input 1 was a failed turn: it is not in the sample, so positions 1, 3
    items = [item("d/1", rid, 0), item("d/2", rid, 2)]
    lines = [
        line("d/1", rid),
        line("d/2", rid, ["PHANTOM", "RULE"]),
        line("d/2", rid, ["CONTRADICT"], annotator="SS"),  # overlap: ignored
    ]
    (r,) = m1_growth.runs_turns([key], items, lines, "SD")
    assert [x for x, _ in r.points] == [1, 3]
    assert dict(r.points[1][1]) == {**ZERO, "PHANTOM": 1}  # RULE is M4


def test_labels_are_checked_as_in_10_1() -> None:
    key = ("A", "long01_border_road", 2001)
    rid = "A_long01_border_road_2001"
    with pytest.raises(LabelError, match="1 sampled turns have no line"):
        m1_growth.runs_turns([key], [item("a/1", rid, 0)], [], "SD")


def test_slope_is_least_squares_scaled_per_100_turns_per_10_turns() -> None:
    # one more divergence every 10 turns: +0.1 per turn, so the rate per 100 turns
    # rises by about 100 every 10 turns (a staircase fits a little under 0.1)
    ys = [i // 10 for i in range(50)]
    flat = run("A", [1] * 50)
    rising = run("D", ys)
    assert m1_growth.slope()([flat]) == 0
    exact = run("D", [0, 1, 2, 3])  # +1 per turn
    assert m1_growth.slope()([exact]) == pytest.approx(1000)
    assert m1_growth.slope()([rising]) == pytest.approx(96.04, abs=0.01)


def test_slope_is_pooled_over_turns_and_undefined_without_spread() -> None:
    a = run("A", [0, 2])
    b = run("A", [0, 0, 0, 0], seed=2002)
    assert m1_growth.slope()([a, b]) == pytest.approx(-2000 / 41)
    # pooled over the six turns; the mean of the two runs' slopes would be +1000
    assert m1_growth.slope()([run("A", [3])]) is None
    assert m1_growth.slope()([]) is None


def test_categories_and_difference_from_a() -> None:
    a = run("A", [0, 1, 2])
    d = run("D", [0, 0, 0])
    assert m1_growth.difference("D")([a, d]) == pytest.approx(-1000)
    phantom_only = RunTurns(
        ("A", "long01_border_road", 2001), ((1, ZERO), (2, {**ZERO, "PHANTOM": 4}))
    )
    assert m1_growth.slope(m1_growth.SENSITIVITY)([phantom_only]) == 0


def test_bins_pool_the_rate_by_position() -> None:
    r = run("A", [1] * 10 + [0] * 40 + [1, 1])  # 52 inputs, as the long sessions
    bins = m1_growth.binned([r])
    assert [b["positions"] for b in bins] == [[1, 10], [11, 20], [21, 30], [31, 40], [41, None]]
    assert bins[0] == {"positions": [1, 10], "turns": 10, "divergences": 10, "rate": 100.0}
    assert bins[1]["rate"] == 0
    assert bins[4]["turns"] == 12 and bins[4]["divergences"] == 2  # 51 and 52 kept
    assert m1_growth.binned([])[0]["rate"] is None


def _grid():
    rising = [i // 10 for i in range(50)]
    runs = []
    for seed in (2001, 2002, 2003, 2004):
        runs.append(run("A", [0] * 50, seed=seed))
        runs.append(run("D", rising, seed=seed))
        runs.append(run("A", [1] * 25, scenario="s01_cellar", seed=seed))
        runs.append(run("D", [1] * 25, scenario="s01_cellar", seed=seed))
    return runs


def test_report_uses_long_sessions_for_rq2_and_is_reproducible() -> None:
    report = m1_growth.growth_report(_grid(), resamples=200)
    a, d = report["conditions"]["A"], report["conditions"]["D"]
    assert a["long_runs"] == d["long_runs"] == 4 and a["short_runs"] == 4
    assert a["slope"]["value"] == 0 and not a["grows"]
    assert d["slope"]["value"] > 0 and d["grows"]  # every run rises: the interval is above 0
    assert d["short_slope"] == 0  # flat short runs do not enter RQ2
    diff = report["differences"]["D"]
    assert diff["all"]["value"] == pytest.approx(d["slope"]["value"])
    assert diff["excludes_zero"]
    assert "A" not in report["differences"]
    assert report == m1_growth.growth_report(_grid(), resamples=200)
    block = m1_growth.render(report)
    assert "| D − A |" in block and "41+" in block
