"""M1 rates (WBS 10.1): divergences per 100 narrated turns per condition, the
ratio to condition A, and H1.

The sampled turns are stand-ins with the three attributes the count reads
(`turn_id`, `run_id`, `candidates`); the labels are hand-built lines in the
format the annotation tool writes. No test reads the logs or calls a model.

Run: pytest tests/eval/test_m1_rates.py -v
"""

from types import SimpleNamespace

import pytest

from adm.eval import m1_rates
from adm.eval.m1_rates import RunM1

CANDIDATE = {
    "check": "entity_mention",
    "category": "PHANTOM",
    "kind": "item",
    "confidence": "high",
    "mention": "lantern",
    "span": [0, 7],
}
KEYS = [("A", "s01_cellar", 2001), ("D", "s01_cellar", 2001)]


def item(turn_id: str, rid: str, candidates: tuple = ()) -> SimpleNamespace:
    return SimpleNamespace(turn_id=turn_id, run_id=rid, candidates=candidates)


def line(turn_id: str, rid: str, confirmed=(), added=(), candidates=(), annotator="SD") -> dict:
    return {
        "turn_id": turn_id,
        "run_id": rid,
        "annotator": annotator,
        "candidates": [{**c, "confirmed": c in confirmed} for c in candidates],
        "added": [{"category": c, "phrase": "x", "span": [0, 1]} for c in added],
        "note": "",
    }


def _sample():
    items = [
        item("a/1", "A_s01_cellar_2001", (CANDIDATE,)),
        item("a/2", "A_s01_cellar_2001"),
        item("d/1", "D_s01_cellar_2001"),
    ]
    lines = [
        line("a/1", "A_s01_cellar_2001", [CANDIDATE], ["CONTRADICT", "RULE"], [CANDIDATE]),
        line("a/2", "A_s01_cellar_2001"),
        line("d/1", "D_s01_cellar_2001", added=["RESOURCE"]),
        line("d/1", "D_s01_cellar_2001", added=["PHANTOM"], annotator="SS"),  # overlap: ignored
    ]
    return items, lines


def test_counts_are_per_run_rubric_categories_only_first_annotator() -> None:
    items, lines = _sample()
    a, d = m1_rates.runs_m1(KEYS, items, lines, "SD")
    assert a.key == KEYS[0] and a.turns == 2 and a.turns_with_any == 1
    assert dict(a.counts) == {"PHANTOM": 1, "CONTRADICT": 1, "RESOURCE": 0, "RELATION": 0}
    assert d.divergences() == 1 and d.counts["PHANTOM"] == 0  # SS's line is not read


@pytest.mark.parametrize(
    ("drop", "extra", "problem"),
    [
        (2, None, "1 sampled turns have no line"),
        (None, line("a/2", "A_s01_cellar_2001"), "1 turns labelled twice"),
        (None, line("z/9", "A_s01_cellar_2001"), "1 lines are not sampled turns"),
        (0, line("a/1", "A_s01_cellar_2001"), "1 turns differ from the sample"),
    ],
)
def test_labels_that_do_not_cover_the_sample_are_refused(drop, extra, problem) -> None:
    items, lines = _sample()
    if drop is not None:
        lines.pop(drop)
    if extra is not None:
        lines.append(extra)
    with pytest.raises(m1_rates.LabelError, match=problem):
        m1_rates.runs_m1(KEYS, items, lines, "SD")


def run(condition: str, seed: int, turns: int, phantom: int, contradict: int = 0) -> RunM1:
    counts = {"PHANTOM": phantom, "CONTRADICT": contradict, "RESOURCE": 0, "RELATION": 0}
    return RunM1((condition, f"s{seed:02d}", 2001), turns, counts, min(turns, phantom))


def test_rates_are_pooled_ratios_of_sums_per_100_turns() -> None:
    runs = [run("A", 1, 10, 4), run("A", 2, 30, 4, 2)]
    assert m1_rates.rate()(runs) == pytest.approx(100 * 10 / 40)
    assert m1_rates.rate(["CONTRADICT"])(runs) == pytest.approx(5.0)
    assert m1_rates.rate()([]) is None


def test_the_ratio_and_h1_follow_the_pooled_rates() -> None:
    runs = [run("A", s, 20, 10) for s in range(1, 6)] + [run("D", s, 20, 2) for s in range(1, 6)]
    report = m1_rates.m1_report(runs, resamples=200)
    assert report["conditions"]["A"]["rate"]["value"] == pytest.approx(50.0)
    assert report["conditions"]["D"]["rate"]["value"] == pytest.approx(10.0)
    d = report["ratios"]["D"]
    assert d["all"]["value"] == pytest.approx(0.2)
    assert d["without_phantom"]["value"] is None  # nothing left in A to divide by
    assert d["without_phantom"]["interval"] is None
    assert report["h1"] == {
        "ratio": pytest.approx(0.2),
        "interval": d["all"]["interval"],
        "at_most_half": True,
        "excludes_one": True,
        "supported": True,
    }
    # The same seed gives the same intervals.
    assert m1_rates.m1_report(runs, resamples=200)["ratios"] == report["ratios"]


def test_h1_fails_when_the_ratio_is_above_half_or_the_interval_reaches_one() -> None:
    runs = [run("A", s, 20, 10) for s in range(1, 6)] + [run("D", s, 20, 8) for s in range(1, 6)]
    h1 = m1_rates.m1_report(runs, resamples=200)["h1"]
    assert h1["ratio"] == pytest.approx(0.8)
    assert not h1["at_most_half"] and not h1["supported"]


def test_the_report_block_has_every_condition_and_the_h1_line() -> None:
    runs = [run(c, s, 20, n) for c, n in zip("ABCD", (10, 8, 6, 2), strict=True) for s in (1, 2)]
    runs.append(RunM1(("A", "long01_border_road", 2001), 50, {k: 0 for k in m1_rates.RUBRIC}, 0))
    block = m1_rates.render(m1_rates.m1_report(runs, resamples=100))
    for c in "ABCD":
        assert f"\n| {c} | " in block
    for c in "BCD":
        assert f"| {c}/A | " in block
    assert "**H1**" in block and "supported" in block
    assert "| A | 50.0 | 0.0 |" in block  # short vs long
