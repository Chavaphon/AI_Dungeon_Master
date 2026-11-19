"""M5 per condition and H2 (WBS 11.3): the excerpt key joined to both raters'
ratings, the mean score per condition, the D minus A difference per item with
the run-level bootstrap, each rater alone, and the paired-by-scenario interval.

Ratings and keys are hand-built in the format the annotation tool writes. No
test reads the logs or the real ratings.

Run: pytest tests/eval/test_m5_scores.py -v
"""

import pytest

from adm.eval import m5_scores
from adm.eval.m5_scores import CONDITIONS, Excerpt, ExcerptKeyError

SCENARIOS = [f"s{i:02d}_x" for i in range(1, 13)] + [f"long0{i}_x" for i in range(1, 5)]


def rating(eid: str, rater: str, score: int) -> dict:
    return {
        "excerpt_id": eid,
        "rater": rater,
        "coherence": score,
        "vividness": score,
        "tone": score,
        "engagement": score,
        "note": "",
    }


def grid(first=lambda c, s: 3, second=lambda c, s: 3):
    """A full key and paired ratings; `first(condition, scenario_index)` gives a score."""
    key, pairs = {}, []
    for i, scen in enumerate(SCENARIOS):
        for c in CONDITIONS:
            key[f"{c}{i:02d}"] = {"run_id": f"{c}_{scen}_2001", "w": 0}
    for eid in sorted(key):
        c, i = eid[0], int(eid[1:])
        pairs.append((rating(eid, "SS", first(c, i)), rating(eid, "SD", second(c, i))))
    return key, pairs


def test_run_id_parses_into_condition_scenario_and_seed() -> None:
    assert m5_scores.parse_run_id("C_long04_mountain_monastery_2003") == (
        "C",
        "long04_mountain_monastery",
        2003,
    )


def test_key_must_give_one_excerpt_per_scenario_and_condition_at_one_seed() -> None:
    key, pairs = grid()
    units = m5_scores.excerpts(key, pairs)
    assert len(units) == 64 and sum(e.long for e in units) == 16
    bad = dict(key)
    bad["D00"] = {"run_id": "D_s01_x_2002", "w": 0}
    with pytest.raises(ExcerptKeyError, match="s01_x mixes seeds"):
        m5_scores.excerpts(bad, pairs)
    bad = dict(key)
    bad["D00"] = {"run_id": "C_s01_x_2001", "w": 0}
    with pytest.raises(ExcerptKeyError, match="condition D has 15 excerpts"):
        m5_scores.excerpts(bad, pairs)


def test_score_is_the_mean_of_the_two_raters() -> None:
    e = Excerpt("e", "A", "s01_x", 2001, (rating("e", "SS", 5), rating("e", "SD", 2)))
    assert e.score("tone") == 3.5
    assert e.score("tone", 0) == 5 and e.score("tone", 1) == 2


def test_reading_rule() -> None:
    assert m5_scores.reading([-0.5, -0.1]) == "worse"
    assert m5_scores.reading([0.1, 0.5]) == "better"
    assert m5_scores.reading([-0.1, 0.5]) == "no difference shown"
    assert m5_scores.reading([-0.5, 0.0]) == "no difference shown"
    assert m5_scores.reading(None) == "undefined"


def test_no_difference_gives_zero_and_h2_not_contradicted() -> None:
    key, pairs = grid()
    report = m5_scores.scores_report(m5_scores.excerpts(key, pairs), ["SS", "SD"], resamples=200)
    d = report["items"]["tone"]["differences"]["D-A"]
    assert d["value"] == 0 and d["interval"] == [0, 0]
    assert not report["h2"]["contradicted"]


def test_d_lower_everywhere_is_worse_and_contradicts_h2() -> None:
    def score(c, i):
        return 2 + i % 2 if c == "D" else 4 + i % 2  # D two points lower, some spread

    key, pairs = grid(score, score)
    report = m5_scores.scores_report(m5_scores.excerpts(key, pairs), ["SS", "SD"], resamples=200)
    item = report["items"]["coherence"]
    assert item["differences"]["D-A"]["value"] == pytest.approx(-2)
    assert item["differences"]["D-A"]["reading"] == "worse"
    assert item["differences"]["B-A"]["value"] == 0
    assert item["paired"]["value"] == pytest.approx(-2) and item["paired"]["reading"] == "worse"
    assert report["h2"] == {"worse_items": list(m5_scores.M5_ITEMS), "contradicted": True}


def test_each_rater_alone_and_short_against_long() -> None:
    # only SS rates D lower, and only on the long sessions
    key, pairs = grid(first=lambda c, i: 1 if c == "D" and i >= 12 else 4, second=lambda c, i: 4)
    report = m5_scores.scores_report(m5_scores.excerpts(key, pairs), ["SS", "SD"], resamples=200)
    item = report["items"]["vividness"]
    ss, sd = item["per_rater"]
    assert ss["value"] == pytest.approx(-3 * 4 / 16) and sd["value"] == 0
    d = item["conditions"]["D"]
    assert d["short_mean"] == 4 and d["long_mean"] == 2.5
    assert d["rater_means"] == [pytest.approx(4 - 0.75), 4]
    assert report == m5_scores.scores_report(
        m5_scores.excerpts(key, pairs), ["SS", "SD"], resamples=200
    )
    block = m5_scores.render(report)
    assert "**H2**" in block and "| vividness |" in block and "Paired by scenario" in block
