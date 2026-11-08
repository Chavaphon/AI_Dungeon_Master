"""Checker validation (WBS 8.10): the 30-turn sample, the blind labelling sheet,
and precision and recall from the labels.

The sample is fixed with no RNG and stratified 8/8/7/7 by condition; the sheet
shows no condition, run id or checker output; scoring matches each candidate to
at most one overlapping label of its turn and category, and writes the results
block of docs/checker_validation.md.

No test calls a model: the logs are written by the real harnesses with the fake
client of tests/eval/test_checker.py.

Run: pytest tests/eval/test_checker_validation.py -v
"""

import csv
import json
from collections.abc import Sequence
from pathlib import Path

import pytest
from typer.testing import CliRunner

from adm.engine.scenario import load_scenario
from adm.eval import checker_validation as cv
from adm.orchestration import prompt
from adm.orchestration.client import Message, ModelReply, Phase, load_model_config
from adm.orchestration.narration_only import NarrationOnlyStart
from adm.orchestration.session import Session, new_run_log, run_script

ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = ROOT / "scenarios"
CELLAR = load_scenario(SCENARIOS / "s01_cellar.json")
TEXTS = prompt.load_templates()
CONFIG = load_model_config()
SEED = 3001
NULL = json.dumps({"tool": None})

PHANTOM = "You raise your lantern, and a hooded stranger steps out."
WRONG_BAND = "You stagger back, barely standing."
CLEAN = "Water drips down the cellar stairs and pools around the barrels."


class FakeClient:
    """Narrates `narrations` in turn, then CLEAN; proposes `{"tool": null}`."""

    def __init__(self, narrations: Sequence[str]) -> None:
        self.narrations = list(narrations)

    def chat(self, messages: Sequence[Message], *, phase: Phase, seed: int) -> ModelReply:
        if phase == "toolcall":
            reply = NULL
        elif phase == "narration":
            reply = self.narrations.pop(0) if self.narrations else CLEAN
        else:
            reply = "Lyra searched the cellar."
        return ModelReply(reply, 3000, 40, 0, 0, "stop", 0)


def _runs(root: Path) -> Path:
    """One cellar run per condition; every A narration has a phantom lantern
    and stranger, every other turn is clean."""
    runs = root / "runs"
    for condition in "ABC":
        log = new_run_log(runs, condition, CELLAR.scenario_id, SEED)
        narrations = [PHANTOM if condition == "A" else CLEAN] * 30
        start = NarrationOnlyStart(condition.lower())
        run_script(start(FakeClient(narrations), CONFIG, TEXTS, CELLAR, log, seed=SEED))
    log = new_run_log(runs, "D", CELLAR.scenario_id, SEED)
    run_script(Session.start(FakeClient([WRONG_BAND] * 30), CONFIG, TEXTS, CELLAR, log, seed=SEED))
    return runs


@pytest.fixture(scope="module")
def runs(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return _runs(tmp_path_factory.mktemp("cv"))


def _population(runs: Path) -> dict:
    return cv._population(runs, SCENARIOS)


def test_the_sample_is_30_turns_stratified_by_condition_and_fixed(runs: Path) -> None:
    population = _population(runs)
    first = cv.draw_sample(population)
    assert len(first) == cv.SIZE == sum(cv.PER_CONDITION.values())
    assert {c: sum(1 for s in first if s.key[0] == c) for c in "ABCD"} == cv.PER_CONDITION
    assert [s.sample_id for s in first] == [f"S{i:02d}" for i in range(1, 31)]
    assert len({(s.key, s.input_index) for s in first}) == 30
    assert cv.draw_sample(population) == first
    # Ids follow the draw key, so conditions are interleaved.
    assert [s.key[0] for s in first] != sorted(s.key[0] for s in first)


def test_a_condition_too_small_for_its_stratum_is_refused(runs: Path) -> None:
    with pytest.raises(ValueError, match="condition A"):
        cv.draw_sample(_population(runs), {"A": 1000})


def test_the_sheet_is_blind_and_shows_what_the_rubric_scores(tmp_path: Path, runs: Path) -> None:
    out = tmp_path / "cv"
    result = CliRunner().invoke(
        cv.app, ["sample", "--runs", str(runs), "--out", str(out), "--scenarios", str(SCENARIOS)]
    )
    assert result.exit_code == 0, result.output
    sheet = (out / "sheet.md").read_text(encoding="utf-8")
    assert sheet.count("\n## S") == 30
    for hidden in ("_s01_cellar_", "Condition", "entity_mention", "hp_band", "confidence"):
        assert hidden not in sheet
    for shown in (
        "**Player input:**",
        "Lyra (`pc_lyra`) 20/20 `healthy`",
        "the Keeper `unfriendly`",
        "**Executed call:**",
        "**Encounter:**",
    ):
        assert shown in sheet
    assert (out / "labels.csv").read_text(encoding="utf-8") == "sample_id,category,phrase,notes\n"
    assert len(json.loads((out / "sample.json").read_text(encoding="utf-8"))) == 30


def _write_labels(path: Path, rows: list[tuple[str, str, str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(cv.LABEL_FIELDS)
        writer.writerows(rows)


def test_scoring_matches_labels_and_writes_the_results_block(tmp_path: Path, runs: Path) -> None:
    out = tmp_path / "cv"
    args = ["--runs", str(runs), "--out", str(out), "--scenarios", str(SCENARIOS)]
    assert CliRunner().invoke(cv.app, ["sample", *args]).exit_code == 0
    drawn = [cv.Sampled.from_dict(d) for d in json.loads((out / "sample.json").read_text("utf-8"))]
    a_turn = next(s.sample_id for s in drawn if s.key[0] == "A")
    clean = next(s.sample_id for s in drawn if s.key[0] == "B")
    _write_labels(
        out / "labels.csv",
        [
            (a_turn, "PHANTOM", "lantern", ""),  # found by the checker
            (clean, "RESOURCE", "the barrels", "no check"),  # a miss by design
            (clean, "NOTE", "", "5.3: an event"),
        ],
    )
    doc = tmp_path / "checker_validation.md"
    doc.write_text(f"# x\n\n{cv.RESULTS_START}\nPending.\n{cv.RESULTS_END}\n\nend\n", "utf-8")

    result = CliRunner().invoke(cv.app, ["score", *args, "--doc", str(doc)])
    assert result.exit_code == 0, result.output
    text = doc.read_text(encoding="utf-8")
    assert "Pending." not in text and text.endswith("end\n")
    phantom = next(line for line in text.splitlines() if line.startswith("| `PHANTOM`"))
    cells = [c.strip() for c in phantom.strip("|").split("|")]
    # 1 label; the 8 A turns each give a lantern and a stranger, one lantern matches.
    assert cells[1:6] == ["1", "16", "1", "0.06", "1.00"]
    assert f"| {clean} | `RESOURCE` | the barrels | no check |" in text
    assert "| `entity_mention` | `character` | 0 | 8 |" in text
    assert f"1 of 30 turns: {clean}." in text


def test_a_candidate_matches_at_most_one_label_and_only_its_category() -> None:
    label = cv.Label("S01", "PHANTOM", "your lantern", "")
    candidate = {"category": "PHANTOM", "span": [14, 21], "mention": "lantern"}
    narration = "You raise your lantern high."
    assert cv._overlaps(narration, label, candidate)
    assert not cv._overlaps(narration, cv.Label("S01", "PHANTOM", "high", ""), candidate)
    # Not found verbatim: fall back to containment.
    loose = {**candidate, "span": [0, 0]}
    assert cv._overlaps(narration, cv.Label("S01", "PHANTOM", "Lantern!", ""), loose)
    assert not cv._overlaps(narration, cv.Label("S01", "PHANTOM", "torch", ""), loose)


@pytest.mark.parametrize(
    ("row", "message"),
    [
        (("S99", "PHANTOM", "x", ""), "unknown sample_id"),
        (("S01", "PHANTASM", "x", ""), "unknown category"),
        (("S01", "PHANTOM", "", ""), "a PHANTOM label needs a phrase"),
    ],
)
def test_bad_labels_are_refused_with_their_line(tmp_path: Path, row: tuple, message: str) -> None:
    path = tmp_path / "labels.csv"
    _write_labels(path, [row])
    with pytest.raises(ValueError, match=f"line 2: {message}"):
        cv.read_labels(path, {"S01"})
