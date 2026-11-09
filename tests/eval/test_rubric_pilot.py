"""Rubric pilot (WBS 8.11): Krippendorff's alpha between two annotators.

Alpha is checked against the published worked example (Krippendorff 2011,
"Computing Krippendorff's alpha-reliability", 4 coders x 12 units with missing
values) and against the `krippendorff` package when it is installed. The report
counts divergences per turn and category, lists disagreements, and rewrites the
results block of docs/rubric_pilot.md.

Run: pytest tests/eval/test_rubric_pilot.py -v
"""

import json
import random
from pathlib import Path

import pytest
from typer.testing import CliRunner

from adm.eval import rubric_pilot as rp
from adm.eval.checker_validation import Label

N = None
# Krippendorff (2011), section C: coders as rows, units as columns.
EXAMPLE = [
    [1, 2, 3, 3, 2, 1, 4, 1, 2, N, N, N],
    [1, 2, 3, 3, 2, 2, 4, 1, 2, 5, N, 3],
    [N, 3, 3, 3, 2, 3, 4, 2, 2, 5, 1, N],
    [1, 2, 3, 3, 2, 4, 4, 1, 2, 5, 1, N],
]
UNITS = [list(col) for col in zip(*EXAMPLE, strict=True)]


def test_alpha_matches_the_published_nominal_value():
    assert rp.alpha(UNITS, "nominal") == pytest.approx(0.743, abs=5e-4)


def test_alpha_matches_the_published_interval_value():
    assert rp.alpha(UNITS, "interval") == pytest.approx(0.849, abs=5e-4)


def test_perfect_agreement_is_one():
    assert rp.alpha([[0, 0], [1, 1], [2, 2]]) == pytest.approx(1.0)


def test_alpha_is_undefined_with_no_variation_or_no_pairs():
    assert rp.alpha([[0, 0], [0, 0]]) is None
    assert rp.alpha([[1, None], [None, 2]]) is None


def test_alpha_matches_the_krippendorff_package():
    kd = pytest.importorskip("krippendorff")
    rng = random.Random(8011)
    for metric in ("nominal", "interval"):
        coders = [[rng.choice([0, 0, 0, 1, 2]) for _ in range(40)] for _ in range(2)]
        coders[1] = [v if rng.random() < 0.7 else rng.choice([0, 1, 2]) for v in coders[0]]
        units = [list(c) for c in zip(*coders, strict=True)]
        expected = kd.alpha(reliability_data=coders, level_of_measurement=metric)
        assert rp.alpha(units, metric) == pytest.approx(expected)


def L(sid, category, phrase="x", notes=""):  # noqa: N802
    return Label(sid, category, phrase, notes)


IDS = ["S01", "S02", "S03", "S04"]


def test_counts_ignore_rule_and_note_rows():
    c = rp.counts([L("S01", "PHANTOM"), L("S01", "PHANTOM"), L("S01", "RULE"), L("S02", "NOTE")])
    assert c == {("S01", "PHANTOM"): 2}


def test_report_lists_disagreements_with_both_phrases_and_adjacency_notes():
    sd = [L("S01", "PHANTOM", "lantern"), L("S02", "CONTRADICT", "barely standing")]
    xx = [
        L("S01", "PHANTOM", "lantern"),
        L("S01", "PHANTOM", "stranger"),
        L("S03", "NOTE", "", "6.4 the Keeper scowls"),
    ]
    block = rp.report(IDS, {"SD": sd, "XX": xx})
    assert "### Disagreements (2), for 8.12" in block
    assert "| S01 | `PHANTOM` | 1: “lantern” | 2: “lantern”; “stranger” |" in block
    assert "| S02 | `CONTRADICT` | 1: “barely standing” | 0 |" in block
    assert "- SD: none" in block and "- XX: S03" in block
    # RESOURCE: nobody recorded one, so alpha is undefined
    assert "| `RESOURCE` | 0 | 0 | – | interval | – |" in block


def test_identical_annotations_meet_the_target():
    same = [L("S01", "PHANTOM"), L("S02", "RELATION"), L("S04", "CONTRADICT")]
    block = rp.report(IDS, {"SD": same, "XX": list(same)})
    assert "| **All four, pooled** | 3 | 3 | 1.000 | interval | yes |" in block
    assert "### Disagreements (0), for 8.12\n\nNone." in block


def test_cli_writes_the_results_block(tmp_path: Path):
    (tmp_path / "sample.json").write_text(json.dumps([{"sample_id": s} for s in IDS]))
    header = "sample_id,category,phrase,notes\n"
    (tmp_path / "a.csv").write_text(header + "S01,PHANTOM,lantern,\nS02,CONTRADICT,dying,\n")
    (tmp_path / "b.csv").write_text(header + "S01,phantom,lantern,\n")
    doc = tmp_path / "pilot.md"
    doc.write_text(f"# x\n\n{rp.RESULTS_START}\nPending.\n{rp.RESULTS_END}\n\n## 3\n")
    result = CliRunner().invoke(
        rp.app,
        [
            "--labels", f"SD={tmp_path / 'a.csv'}",
            "--labels", f"XX={tmp_path / 'b.csv'}",
            "--sample", str(tmp_path / "sample.json"),
            "--doc", str(doc),
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    text = doc.read_text(encoding="utf-8")
    assert "Pending." not in text and "Annotators: SD, XX. Turns: 4." in text
    assert text.endswith("\n## 3\n")


def test_cli_needs_two_distinct_annotators(tmp_path: Path):
    (tmp_path / "sample.json").write_text("[]")
    one = CliRunner().invoke(
        rp.app, ["--labels", "SD=a.csv", "--sample", str(tmp_path / "sample.json")]
    )
    assert one.exit_code != 0
    bad = CliRunner().invoke(rp.app, ["--labels", "a.csv", "--labels", "b.csv"])
    assert bad.exit_code != 0
