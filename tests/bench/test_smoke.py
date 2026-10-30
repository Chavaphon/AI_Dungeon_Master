"""Smoke runs (WBS 6.11): the manifest is the agreed grid of ten long runs, a
run is complete only when every scripted input is in its log and nothing
raised, the figures are read back from the audit log, and the gate G2 and
risk R1 verdicts follow TASK_CHECKLIST.md and docs/decisions.md.

No test calls a model: the runner plays a real session on a fake client.

Run: pytest tests/bench/test_smoke.py -v
"""

import json
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from adm.bench import smoke
from adm.engine.audit import log_path, read_log
from adm.engine.scenario import Scenario, load_scenario
from adm.orchestration import prompt
from adm.orchestration.client import (
    Message,
    ModelReply,
    ModelUnavailable,
    Phase,
    load_model_config,
)
from adm.orchestration.session import Session, new_run_log, run_script

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "experiments" / "smoke_grid.json"
CELLAR = "scenarios/s01_cellar.json"
CONFIG = load_model_config()
TEXTS = prompt.load_templates()
K = CONFIG.K_verbatim_turns

Doc = dict[str, Any]

LOOK = json.dumps(
    {"tool": "skill_check", "arguments": {"actor_id": "pc_lyra", "skill": "perception", "dc": 12}}
)
BAD_DC = json.dumps(
    {"tool": "skill_check", "arguments": {"actor_id": "pc_lyra", "skill": "perception", "dc": 40}}
)
GARBLED = "Lyra looks around."


class FakeClient:
    """Answers toolcalls from `script`, then always LOOK. Raises after
    `fail_after` toolcalls, if set."""

    def __init__(self, *script: str, fail_after: int | None = None) -> None:
        self.script = list(script)
        self.fail_after = fail_after
        self.toolcalls = 0

    def chat(self, messages: Sequence[Message], *, phase: Phase, seed: int) -> ModelReply:
        if phase == "toolcall":
            self.toolcalls += 1
            if self.fail_after is not None and self.toolcalls > self.fail_after:
                raise ModelUnavailable("Ollama stopped answering")
            reply = self.script.pop(0) if self.script else LOOK
        else:
            reply = "The water stirs." if phase == "narration" else "Lyra searched."
        # Zero latency: the real turn_latency_ms must not be shorter than its calls.
        return ModelReply(reply, 3000, 40, 0, 0, "stop", 0)


def _runner(clients: dict[int, FakeClient]) -> smoke.Runner:
    def run(scenario: Scenario, seed: int, runs_dir: Path) -> None:
        log = new_run_log(runs_dir, scenario.scenario_id, seed)
        session = Session.start(clients[seed], CONFIG, TEXTS, scenario, log, seed=seed)
        run_script(session)

    return run


def _smoke(tmp_path: Path, manifest: list[Doc], runner: smoke.Runner) -> Doc:
    return smoke.smoke(manifest, runs_dir=tmp_path, runner=runner, k=K, log=lambda line: None)


@pytest.fixture(autouse=True)
def _at_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(ROOT)  # manifest scenario paths are relative to the repository


# --- the grid ----------------------------------------------------------------


def test_the_manifest_is_ten_fifty_turn_runs_over_the_long_scenarios() -> None:
    runs = smoke.load_manifest(MANIFEST)
    assert len(runs) == 10
    by_scenario = Counter(Path(r["scenario"]).stem for r in runs)
    assert by_scenario == {
        "long01_border_road": 3,
        "long02_hollow_manor": 3,
        "long03_river_market": 2,
        "long04_mountain_monastery": 2,
    }
    assert len({r["seed"] for r in runs}) == 10
    for r in runs:
        assert len(load_scenario(ROOT / r["scenario"]).scripted_inputs) >= 50


def test_a_manifest_that_lists_a_run_twice_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "grid.json"
    entry = {"scenario": CELLAR, "seed": 1}
    path.write_text(json.dumps({"runs": [entry, entry]}), encoding="utf-8")
    with pytest.raises(ValueError, match="twice"):
        smoke.load_manifest(path)


# --- complete and unrecoverable ----------------------------------------------


def test_a_run_with_failed_turns_is_still_complete(tmp_path: Path) -> None:
    client = FakeClient(GARBLED, GARBLED, GARBLED, BAD_DC, LOOK)
    summary = _smoke(tmp_path, [{"scenario": CELLAR, "seed": 1}], _runner({1: client}))

    (run,) = summary["runs"]
    inputs = len(load_scenario(ROOT / CELLAR).scripted_inputs)
    assert run["complete"] and run["error"] is None
    assert run["turns"] == run["inputs"] == inputs
    assert run["turn_failures"] == {"unparseable": 1}
    assert run["narrated"] == inputs - 1
    # Turn 1 fails three times; turn 2 is rejected once (DC 40) and recovers.
    assert run["schema_valid_first"] == inputs - 1
    assert (run["rejected_turns"], run["recovered_turns"]) == (2, 1)
    assert run["summaries"] == (inputs - 1) // K
    assert run["encounters"] == 1
    assert run["k_reduced"] == 0, "a short history is not a reduced K"
    assert run["tokens_per_s_mean"] is None, "no call reports a generation time"


def test_an_exception_makes_the_run_unrecoverable_and_the_next_run_goes_on(
    tmp_path: Path,
) -> None:
    clients = {1: FakeClient(fail_after=5), 2: FakeClient()}
    manifest = [{"scenario": CELLAR, "seed": 1}, {"scenario": CELLAR, "seed": 2}]
    summary = _smoke(tmp_path, manifest, _runner(clients))

    broken, whole = summary["runs"]
    assert not broken["complete"]
    assert broken["error"] == "ModelUnavailable: Ollama stopped answering"
    assert broken["turns"] == 5, "the turns before the error stay in the log"
    assert whole["complete"]
    assert summary["totals"]["complete"] == 1


def test_an_existing_log_is_read_not_played_again(tmp_path: Path) -> None:
    manifest = [{"scenario": CELLAR, "seed": 1}]
    first = _smoke(tmp_path, manifest, _runner({1: FakeClient()}))

    def never(scenario: Scenario, seed: int, runs_dir: Path) -> None:
        raise AssertionError("a run with a log must not be played again")

    again = _smoke(tmp_path, manifest, never)
    assert again["runs"] == first["runs"]


def test_a_truncated_log_is_incomplete(tmp_path: Path) -> None:
    manifest = [{"scenario": CELLAR, "seed": 1}]
    _smoke(tmp_path, manifest, _runner({1: FakeClient()}))
    path = log_path(tmp_path, "D", "s01_cellar", 1)
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    path.write_text("".join(lines[:-1]), encoding="utf-8")

    (run,) = _smoke(tmp_path, manifest, _runner({}))["runs"]
    assert not run["complete"] and run["error"] is None
    assert len(read_log(path)) == run["turns"] == run["inputs"] - 1


def test_tokens_per_second_is_completion_tokens_over_eval_time() -> None:
    call = {"completion_tokens": 40, "eval_ms": 500}
    record = {
        "input_index": 0,
        "validation": [{"ok": True, "tool": None}],
        "model_calls": [call, {**call, "eval_ms": 0}],
        "turn_latency_ms": 2000,
        "turn_failure": None,
        "turn_number": 1,
        "narration_only": True,
        "summary_regenerated": False,
        "k_used": K,
        "engine_steps": [],
    }
    run = smoke.summarise_run([record], inputs=1, k=K, error=None)
    assert run["complete"]
    assert run["tokens_per_s_mean"] == pytest.approx(80.0), "a call with no eval time is left out"
    assert run["latency_mean_s"] == 2.0


def test_k_reduced_counts_only_turns_cut_below_the_history() -> None:
    def record(k_used: int, failure: str | None = None) -> Doc:
        return {"k_used": k_used, "turn_failure": failure}

    # Histories 0, 1, 2, 2 (after a failure), 3: only the last turn was cut.
    records = [record(0), record(1), record(2, "schema"), record(2), record(1)]
    assert smoke._k_reduced(records, k=8) == 1
    assert smoke._k_reduced([record(8)] * 3, k=2) == 0


# --- the verdicts ------------------------------------------------------------


def _run(complete: bool, turns: int = 50, schema_valid: int = 50) -> Doc:
    return {
        "complete": complete,
        "turns": turns,
        "turn_failures": {},
        "narration_only": 0,
        "schema_valid_first": schema_valid,
        "rejected_turns": 0,
        "recovered_turns": 0,
        "latency_mean_s": 5.0,
        "latency_p95_s": 9.0,
    }


@pytest.mark.parametrize(
    ("complete", "attempted", "met"),
    [(10, 10, True), (9, 10, True), (8, 10, False), (9, 9, False)],
)
def test_gate_g2_needs_nine_of_ten(complete: int, attempted: int, met: bool) -> None:
    runs = [_run(i < complete) for i in range(attempted)]
    assert smoke.summarise(runs)["gate_g2_met"] is met


@pytest.mark.parametrize(("valid", "fired"), [(40, False), (39, True)])
def test_r1_fires_below_eighty_per_cent_schema_valid(valid: int, fired: bool) -> None:
    totals = smoke.summarise([_run(True, turns=50, schema_valid=valid)])
    assert totals["r1_fired"] is fired
