"""The automated checker's runner (WBS 8.6): run logs in, `PHANTOM` candidates out.

The checker reads condition A and D logs written by the real harnesses with a
fake client, scores each narrated turn against the state of docs/rubric.md
section 1 (D: the logged state after the turn; A-C: the replayed ground truth),
skips failed turns, refuses a log whose state does not match its hashes, and
writes one candidate per line, the same bytes on every run.

No test calls a model.

Run: pytest tests/eval/test_checker.py -v
"""

import json
from collections.abc import Sequence
from pathlib import Path

import pytest
from typer.testing import CliRunner

from adm.engine.audit import read_log
from adm.engine.replay import replay_script
from adm.engine.scenario import load_scenario
from adm.engine.state import data_hash
from adm.eval import checker
from adm.orchestration import prompt
from adm.orchestration.client import Message, ModelReply, Phase, load_model_config
from adm.orchestration.narration_only import NarrationOnlyStart
from adm.orchestration.session import Session, new_run_log, run_script

ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = ROOT / "scenarios"
CELLAR = load_scenario(SCENARIOS / "s01_cellar.json")
TEXTS = prompt.load_templates()
CONFIG = load_model_config()
SEED = 2001

PHANTOM = "You raise your lantern, and a hooded stranger steps out behind the barrels."
CLEAN = "Water drips down the cellar stairs and pools around the barrels."
NULL = json.dumps({"tool": None})
GARBLED = "I think Lyra should look around."


class FakeClient:
    """Narrates `narrations` in turn, then CLEAN; proposes `toolcalls` in turn,
    then `{"tool": null}`; summarises with a fixed line."""

    def __init__(self, narrations: Sequence[str] = (), toolcalls: Sequence[str] = ()) -> None:
        self.narrations = list(narrations)
        self.toolcalls = list(toolcalls)

    def chat(self, messages: Sequence[Message], *, phase: Phase, seed: int) -> ModelReply:
        if phase == "toolcall":
            reply = self.toolcalls.pop(0) if self.toolcalls else NULL
        elif phase == "narration":
            reply = self.narrations.pop(0) if self.narrations else CLEAN
        else:
            reply = "Lyra searched the cellar."
        return ModelReply(reply, 3000, 40, 0, 0, "stop", 0)


def _a_run(runs: Path, narrations: Sequence[str] = (PHANTOM,)) -> Path:
    log = new_run_log(runs, "A", CELLAR.scenario_id, SEED)
    harness = NarrationOnlyStart("a")(FakeClient(narrations), CONFIG, TEXTS, CELLAR, log, seed=SEED)
    run_script(harness)
    return log.path


def _d_run(runs: Path) -> Path:
    """Input 0 fails (three garbled replies); input 1 narrates the phantom."""
    client = FakeClient([PHANTOM], [GARBLED, GARBLED, GARBLED])
    log = new_run_log(runs, "D", CELLAR.scenario_id, SEED)
    run_script(Session.start(client, CONFIG, TEXTS, CELLAR, log, seed=SEED))
    return log.path


def _check(runs: Path) -> list[dict]:
    logs = checker.load_runs(runs)
    return checker.check_runs(logs, {CELLAR.scenario_id: CELLAR})


def test_a_phantom_in_condition_a_is_a_candidate_with_its_run_and_turn(tmp_path: Path) -> None:
    path = _a_run(tmp_path)
    candidates = _check(tmp_path)

    record = read_log(path)[0]
    assert [(c["kind"], c["mention"]) for c in candidates] == [
        ("item", "lantern"),
        ("character", "stranger"),
    ]
    for c in candidates:
        assert {k: c[k] for k in checker.RUN_FIELDS} == {k: record[k] for k in checker.RUN_FIELDS}
        assert c["check"] == "entity_mention" and c["category"] == "PHANTOM"
        assert c["status"] == "candidate" and c["confidence"] == "high"
        start, end = c["span"]
        assert record["narration"][start:end] == c["mention"]


def test_a_failed_turn_is_skipped_and_d_is_scored_on_its_logged_state(tmp_path: Path) -> None:
    path = _d_run(tmp_path)
    records = read_log(path)
    assert records[0]["turn_failure"] == "unparseable"
    assert records[0]["narration"] not in (PHANTOM, CLEAN)

    candidates = _check(tmp_path)
    assert {c["input_index"] for c in candidates} == {1}
    assert {c["mention"] for c in candidates} == {"lantern", "stranger"}
    states = checker.scored_states(CELLAR, records)
    assert [data_hash(s) for s in states] == [r["state_after_hash"] for r in records]


def test_conditions_a_to_c_are_scored_on_the_replayed_ground_truth(tmp_path: Path) -> None:
    records = read_log(_a_run(tmp_path))
    truth = replay_script(CELLAR, SEED)
    assert checker.scored_states(CELLAR, records) == [t.state for t in truth]


@pytest.mark.parametrize("condition", ["A", "D"])
def test_a_log_that_does_not_match_its_state_is_refused(tmp_path: Path, condition: str) -> None:
    path = _a_run(tmp_path) if condition == "A" else _d_run(tmp_path)
    records = read_log(path)
    records[-1]["state_after_hash"] = "sha256:" + "0" * 64
    with pytest.raises(checker.LogMismatch, match="state_after_hash"):
        checker.scored_states(CELLAR, records)


def test_the_command_line_writes_one_candidate_per_line_the_same_every_time(
    tmp_path: Path,
) -> None:
    runs = tmp_path / "runs"
    _a_run(runs)
    _d_run(runs)
    out = tmp_path / "results" / "automated.jsonl"
    args = ["--runs", str(runs), "--out", str(out), "--scenarios", str(SCENARIOS)]

    first = CliRunner().invoke(checker.app, args)
    assert first.exit_code == 0, first.output
    written = out.read_bytes()
    lines = [json.loads(line) for line in written.decode("utf-8").splitlines()]
    assert [(c["condition"], c["mention"]) for c in lines] == [
        ("A", "lantern"),
        ("A", "stranger"),
        ("D", "lantern"),
        ("D", "stranger"),
    ]
    assert "2 runs, 4 candidates (4 high confidence)" in first.output

    second = CliRunner().invoke(checker.app, args)
    assert second.exit_code == 0 and out.read_bytes() == written


def test_a_clean_run_has_no_candidates(tmp_path: Path) -> None:
    _a_run(tmp_path, narrations=())
    assert _check(tmp_path) == []
