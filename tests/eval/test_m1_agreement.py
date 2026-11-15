"""M1 agreement check (WBS 9.6): the second annotator's overlap pairs with the first.

The check needs no model and no logs for its pairing and counting: the lines are
written here as the annotation tool writes them (`adm.eval.m1.record`).

Run: pytest tests/eval/test_m1_agreement.py -v
"""

from collections.abc import Sequence
from typing import Any

import pytest

from adm.eval import m1_agreement

Doc = dict[str, Any]

CANDIDATE = {
    "check": "entities",
    "category": "PHANTOM",
    "kind": "item",
    "confidence": "high",
    "mention": "lantern",
    "span": [9, 16],
}


def line(
    turn_id: str,
    annotator: str,
    confirmed: Sequence[bool] = (),
    added: Sequence[str] = (),
) -> Doc:
    return {
        "turn_id": turn_id,
        "run_id": "D_s01_cellar_2001",
        "input_index": 0,
        "annotator": annotator,
        "candidates": [{**CANDIDATE, "confirmed": c} for c in confirmed],
        "added": [{"category": cat, "phrase": "x", "span": [0, 1]} for cat in added],
        "note": "",
    }


def test_counts_are_confirmed_candidates_plus_added_labels_rubric_categories_only() -> None:
    counts = m1_agreement.label_counts(
        line("aa/1", "SD", confirmed=(True, False), added=("PHANTOM", "CONTRADICT", "RULE"))
    )
    assert counts == {"PHANTOM": 2, "CONTRADICT": 1}


def test_complete_overlap_pairs_in_sample_order() -> None:
    lines = [
        line("aa/2", "SS"),
        line("aa/1", "SS"),
        line("aa/1", "SD"),
        line("aa/2", "SD"),
        line("bb/1", "SD"),
    ]
    pairs = m1_agreement.pair(lines, "SD", "SS", ["aa/1", "aa/2"])
    assert [first["turn_id"] for first, _ in pairs] == ["aa/1", "aa/2"]
    assert all(second["annotator"] == "SS" for _, second in pairs)


@pytest.mark.parametrize(
    ("lines", "problem"),
    [
        ([line("aa/1", "SD"), line("aa/2", "SD"), line("aa/1", "SS")], "SS has no line for 1"),
        ([line("aa/1", "SD"), line("aa/1", "SS"), line("aa/2", "SS")], "SD has no line for 1"),
        (
            [line(t, a) for t in ("aa/1", "aa/2") for a in ("SD", "SS")] + [line("bb/1", "SS")],
            "SS has 1 line outside the overlap",
        ),
        (
            [line(t, a) for t in ("aa/1", "aa/2") for a in ("SD", "SS")] + [line("aa/1", "SS")],
            "SS has 1 duplicate",
        ),
        (
            [
                line("aa/1", "SD", confirmed=(True,)),
                line("aa/1", "SS"),
                line("aa/2", "SD"),
                line("aa/2", "SS"),
            ],
            "1 turn shown with different checker candidates",
        ),
    ],
)
def test_an_overlap_that_does_not_pair_is_refused(lines: list[Doc], problem: str) -> None:
    with pytest.raises(m1_agreement.OverlapError, match=problem):
        m1_agreement.pair(lines, "SD", "SS", ["aa/1", "aa/2"])


def test_the_report_gives_alpha_per_category_pooled_and_any_divergence() -> None:
    pairs = [
        (line("aa/1", "SD", added=("PHANTOM",)), line("aa/1", "SS", added=("PHANTOM",))),
        (line("aa/2", "SD"), line("aa/2", "SS")),
        (line("aa/3", "SD", added=("CONTRADICT",)), line("aa/3", "SS", added=("CONTRADICT",))),
        (line("aa/4", "SD"), line("aa/4", "SS", added=("CONTRADICT",))),
    ]
    block = m1_agreement.report(pairs, "SD", "SS")
    assert "| 4 turns | SD | SS |" in block
    assert "| `PHANTOM` | 1 | 1 | 1.000 | interval |" in block
    assert "| `RESOURCE` | 0 | 0 | – | interval |" in block
    assert "| **All four, pooled** | 2 | 3 |" in block
    assert "| Turn has any divergence | 2 | 3 |" in block
    assert "| Units that differ | 1 |" in block
