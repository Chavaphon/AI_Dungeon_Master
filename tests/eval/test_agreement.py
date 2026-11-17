"""Inter-rater agreement (WBS 10.5): M1 alpha on the paired overlap, M5 ordinal
alpha per item over the 64 excerpts, and Objective 3.

Labels and ratings are hand-built lines in the format the annotation tool
writes. No test reads the logs or calls a model.

Run: pytest tests/eval/test_agreement.py -v
"""

import pytest

from adm.eval import agreement
from adm.eval.agreement import RatingError


def m1_line(turn_id: str, added=(), annotator="SD", review="accepted") -> dict:
    return {
        "turn_id": turn_id,
        "run_id": "A_s01_cellar_2001",
        "annotator": annotator,
        "candidates": [],
        "added": [{"category": c, "phrase": "x", "span": [0, 1]} for c in added],
        "note": "",
        "review": review,
    }


def rating(excerpt_id: str, rater: str, c=4, v=4, t=5, e=3) -> dict:
    return {
        "excerpt_id": excerpt_id,
        "rater": rater,
        "coherence": c,
        "vividness": v,
        "tone": t,
        "engagement": e,
        "note": "",
    }


def _m1_pairs():
    sd = [
        m1_line("t/1", ["PHANTOM"]),
        m1_line("t/2", ["CONTRADICT", "CONTRADICT", "RULE"]),
        m1_line("t/3"),
        m1_line("t/4", ["RESOURCE"]),
    ]
    ss = [
        m1_line("t/1", ["PHANTOM"], "SS"),
        m1_line("t/2", ["CONTRADICT"], "SS", review="edited"),
        m1_line("t/3", annotator="SS"),
        m1_line("t/4", ["RESOURCE"], "SS"),
    ]
    return list(zip(sd, ss, strict=True))


def test_m1_counts_rubric_categories_and_reports_review() -> None:
    part = agreement.m1_agreement(_m1_pairs())
    assert part["turns"] == 4 and part["units"] == 16
    assert part["pooled"]["totals"] == [4, 3]  # RULE is M4
    assert part["units_differ"] == 1
    assert part["any"]["totals"] == [3, 3] and part["any"]["alpha"] == 1
    assert part["review"] == [{"accepted": 4}, {"accepted": 3, "edited": 1}]
    assert part["per_category"]["RELATION"]["alpha"] is None  # nobody used it


def test_identical_m1_labels_give_alpha_one_and_meet_objective_3() -> None:
    pairs = [(a, {**a, "annotator": "SS"}) for a, _ in _m1_pairs()]
    part = agreement.m1_agreement(pairs)
    assert part["pooled"]["alpha"] == pytest.approx(1)
    assert agreement.objective_3(part) == {"alpha": pytest.approx(1), "target": 0.6, "met": True}


def test_objective_3_is_the_pooled_m1_alpha_against_0_6() -> None:
    assert not agreement.objective_3({"pooled": {"alpha": 0.59}})["met"]
    assert agreement.objective_3({"pooled": {"alpha": 0.6}})["met"]
    assert not agreement.objective_3({"pooled": {"alpha": None}})["met"]


def test_m5_ratings_must_pair_over_the_key() -> None:
    ids = ["e1", "e2"]
    good = [rating("e1", "SS"), rating("e2", "SS"), rating("e1", "SD"), rating("e2", "SD")]
    assert len(agreement.pair_ratings(good, "SS", "SD", ids)) == 2
    cases = [
        (good[:3], "SD has no rating for 1 excerpts"),
        ([*good, rating("e1", "SD")], "SD rated 1 excerpts twice"),
        ([*good, rating("e9", "SS")], "SS rated 1 unknown excerpts"),
        ([*good[:3], rating("e2", "SD", t=6)], "SD has 1 ratings outside 1 to 5"),
    ]
    for lines, problem in cases:
        with pytest.raises(RatingError, match=problem):
            agreement.pair_ratings(lines, "SS", "SD", ids)


def test_m5_alpha_is_ordinal_per_item_with_exact_share_and_means() -> None:
    pairs = [
        (rating("e1", "SS", c=5), rating("e1", "SD", c=4)),
        (rating("e2", "SS", c=3), rating("e2", "SD", c=3)),
        (rating("e3", "SS", c=1), rating("e3", "SD", c=2)),
        (rating("e4", "SS", c=4), rating("e4", "SD", c=4)),
    ]
    part = agreement.m5_agreement(pairs)
    c = part["items"]["coherence"]
    assert c["metric"] == "ordinal" and 0 < c["alpha"] < 1
    assert c["exact"] == 0.5 and c["means"] == [3.25, 3.25]
    # tone is 5 everywhere: no expected disagreement, alpha undefined
    assert part["items"]["tone"]["alpha"] is None and part["items"]["tone"]["exact"] == 1


def test_render_states_objective_3_and_both_tables() -> None:
    pairs = [(a, {**a, "annotator": "SS"}) for a, _ in _m1_pairs()]
    m1_part = agreement.m1_agreement(pairs)
    m5_part = agreement.m5_agreement(
        [
            (rating("e1", "SS", c=5), rating("e1", "SD", c=4)),
            (rating("e2", "SS"), rating("e2", "SD")),
        ]
    )
    block = agreement.render(
        {
            "m1_annotators": ["SD", "SS"],
            "m5_raters": ["SS", "SD"],
            "m1": m1_part,
            "m5": m5_part,
            "objective_3": agreement.objective_3(m1_part),
        }
    )
    assert "**Objective 3**" in block and "**met**" in block
    assert "| **All four, pooled** |" in block and "| engagement |" in block
