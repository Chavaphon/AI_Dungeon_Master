"""The batch runner (WBS 7.6): every run of a manifest, resumable and unattended.
Done when it survives an interruption and resumes without duplicating work.

The runner is a fake that writes `{"input_index": i}` lines where the real one
plays the run, so no test loads or calls a model.

Run: pytest tests/orchestration/test_batch.py -v
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from adm.engine.audit import log_path, read_log
from adm.engine.scenario import load_scenario
from adm.orchestration import batch as b
from adm.orchestration.client import ModelConfigMismatch, ModelUnavailable

ROOT = Path(__file__).resolve().parents[2]
CELLAR = ROOT / "scenarios" / "s01_cellar.json"
BRIDGE = ROOT / "scenarios" / "s02_toll_bridge.json"
SCENARIO = load_scenario(CELLAR)
INPUTS = len(SCENARIO.scripted_inputs)


class Clock:
    """A clock one second further on at every reading."""

    def __init__(self) -> None:
        self.now = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        self.now += timedelta(seconds=1)
        return self.now


Behaviour = Callable[[b.PlannedRun, int], int]


class FakeRunner:
    """Writes the run's log under the staging directory. `behave(run, attempt)`
    may raise or write fewer records, and returns the transport retries."""

    def __init__(self, behave: Behaviour | None = None) -> None:
        self.behave = behave
        self.calls: list[tuple[str, int]] = []

    def __call__(self, run: b.PlannedRun, staging: Path) -> int:
        attempt = sum(1 for rid, _ in self.calls if rid == run.run_id) + 1
        self.calls.append((run.run_id, attempt))
        if self.behave is not None:
            return self.behave(run, attempt)
        write_log(run.log(staging), INPUTS)
        return 0


def write_log(path: Path, records: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as log:
        for i in range(records):
            log.write(json.dumps({"input_index": i}) + "\n")


def plan(*conditions: str, seeds: tuple[int, ...] = (7,)) -> list[b.PlannedRun]:
    return [b.PlannedRun(c, SCENARIO, s) for s in seeds for c in conditions or ("D",)]


def go(
    tmp_path: Path, runs: list[b.PlannedRun], runner: FakeRunner, **kwargs: object
) -> b.BatchResult:
    return b.run_batch(
        runs,
        runs_dir=tmp_path / "runs",
        runner=runner,
        ledger=tmp_path / "attempts.jsonl",
        log=lambda line: None,
        clock=Clock(),
        **kwargs,  # type: ignore[arg-type]
    )


def ledger(tmp_path: Path) -> list[dict]:
    path = tmp_path / "attempts.jsonl"
    return read_log(path) if path.exists() else []


def final(tmp_path: Path, run: b.PlannedRun) -> Path:
    return log_path(tmp_path / "runs", run.condition, run.scenario.scenario_id, run.seed)


def aborted(tmp_path: Path) -> list[Path]:
    return sorted((tmp_path / "runs" / b.ABORTED).rglob("*.jsonl"))


# --- manifest -----------------------------------------------------------------


def write_manifest(tmp_path: Path, **overrides: object) -> Path:
    doc = {
        "description": "test",
        "scenarios": [str(CELLAR), str(BRIDGE)],
        "conditions": ["A", "B", "C", "D"],
        "seeds": [2001, 2002],
        **overrides,
    }
    path = tmp_path / "grid.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def test_manifest_runs_seed_by_seed_then_scenario_then_condition(tmp_path: Path) -> None:
    runs = b.load_manifest(write_manifest(tmp_path), "ABCD")
    assert [r.run_id for r in runs[:5]] == [
        "A_s01_cellar_2001",
        "B_s01_cellar_2001",
        "C_s01_cellar_2001",
        "D_s01_cellar_2001",
        "A_s02_toll_bridge_2001",
    ]
    assert len(runs) == 16
    assert len({r.run_id for r in runs}) == 16


def test_main_grid_is_the_section_10_5_grid() -> None:
    runs = b.load_manifest(ROOT / "experiments" / "main_grid.json", "ABCD")
    assert len(runs) == 192
    assert {r.seed for r in runs} == {2001, 2002, 2003}
    assert len({r.scenario.scenario_id for r in runs}) == 16
    assert {r.condition for r in runs} == {"A", "B", "C", "D"}


@pytest.mark.parametrize(
    "overrides",
    [
        {"conditions": ["A", "A"]},
        {"seeds": [1, 1]},
        {"scenarios": [str(CELLAR), str(CELLAR)]},
        {"conditions": ["E"]},
        {"seeds": [-1]},
        {"seeds": [2**32 - 1]},
        {"seeds": [True]},
        {"seeds": []},
    ],
)
def test_a_bad_manifest_is_refused(tmp_path: Path, overrides: dict) -> None:
    with pytest.raises(b.ManifestError):
        b.load_manifest(write_manifest(tmp_path, **overrides), "ABCD")


def test_a_condition_without_a_harness_is_refused(tmp_path: Path) -> None:
    with pytest.raises(b.ManifestError, match="condition A has no harness"):
        b.load_manifest(write_manifest(tmp_path), "D")


# --- playing and resuming -------------------------------------------------------


def test_every_run_is_played_once_and_moved_into_place(tmp_path: Path) -> None:
    runs = plan("A", "B", "C", "D")
    runner = FakeRunner()
    result = go(tmp_path, runs, runner)
    assert result.done
    assert runner.calls == [(r.run_id, 1) for r in runs]
    for run in runs:
        assert len(read_log(final(tmp_path, run))) == INPUTS
    assert not list((tmp_path / "runs" / b.PENDING).rglob("*.jsonl"))
    assert [e["outcome"] for e in ledger(tmp_path)] == [b.COMPLETE] * 4


def test_a_second_invocation_plays_nothing(tmp_path: Path) -> None:
    runs = plan("A", "D")
    go(tmp_path, runs, FakeRunner())
    runner = FakeRunner()
    result = go(tmp_path, runs, runner)
    assert result.done and result.played == 0
    assert runner.calls == []


def test_an_interrupted_batch_resumes_without_duplicating_work(tmp_path: Path) -> None:
    """The done-when of #82: Ctrl+C part-way through the second run. The first
    run is not played again; the second is played again from the start, and
    its partial log is kept under runs/aborted/."""
    runs = plan("A", "B", "C")

    def interrupt_b(run: b.PlannedRun, attempt: int) -> int:
        write_log(run.log(tmp_path / "runs" / b.PENDING), INPUTS if run.condition != "B" else 3)
        if run.condition == "B":
            raise KeyboardInterrupt
        return 0

    with pytest.raises(KeyboardInterrupt):
        go(tmp_path, runs, FakeRunner(interrupt_b))
    assert final(tmp_path, runs[0]).exists()
    assert not final(tmp_path, runs[1]).exists()
    (partial,) = aborted(tmp_path)
    assert len(read_log(partial)) == 3

    runner = FakeRunner()
    result = go(tmp_path, runs, runner)
    assert result.done
    assert runner.calls == [(runs[1].run_id, 1), (runs[2].run_id, 1)]
    assert [len(read_log(final(tmp_path, r))) for r in runs] == [INPUTS] * 3
    outcomes = [(e["run_id"], e["outcome"]) for e in ledger(tmp_path)]
    assert (runs[1].run_id, b.INTERRUPTED) in outcomes


def test_a_log_left_in_staging_by_a_killed_batch_is_aborted(tmp_path: Path) -> None:
    (run,) = plan()
    write_log(run.log(tmp_path / "runs" / b.PENDING), 5)
    runner = FakeRunner()
    assert go(tmp_path, [run], runner).done
    assert runner.calls == [(run.run_id, 1)]
    (partial,) = aborted(tmp_path)
    assert len(read_log(partial)) == 5
    assert ledger(tmp_path)[0]["outcome"] == b.INTERRUPTED
    assert ledger(tmp_path)[0]["records"] == 5


def test_an_incomplete_log_in_place_is_aborted_and_played_again(tmp_path: Path) -> None:
    (run,) = plan()
    write_log(final(tmp_path, run), 4)
    runner = FakeRunner()
    assert go(tmp_path, [run], runner).done
    assert len(read_log(final(tmp_path, run))) == INPUTS
    (partial,) = aborted(tmp_path)
    assert len(read_log(partial)) == 4


def test_aborted_logs_never_overwrite_each_other(tmp_path: Path) -> None:
    (run,) = plan()
    clock_reading = datetime(2026, 11, 3, tzinfo=UTC)

    def fail(run: b.PlannedRun, attempt: int) -> int:
        write_log(run.log(tmp_path / "runs" / b.PENDING), 1)
        return 1

    b.run_batch(
        [run],
        runs_dir=tmp_path / "runs",
        runner=FakeRunner(fail),
        ledger=tmp_path / "attempts.jsonl",
        log=lambda line: None,
        clock=lambda: clock_reading,
    )
    assert len(aborted(tmp_path)) == 3


# --- failures -------------------------------------------------------------------


def test_a_run_with_a_transport_retry_is_played_again(tmp_path: Path) -> None:
    (run,) = plan()

    def tainted_once(run: b.PlannedRun, attempt: int) -> int:
        write_log(run.log(tmp_path / "runs" / b.PENDING), INPUTS)
        return 1 if attempt == 1 else 0

    runner = FakeRunner(tainted_once)
    assert go(tmp_path, [run], runner).done
    assert runner.calls == [(run.run_id, 1), (run.run_id, 2)]
    assert [e["outcome"] for e in ledger(tmp_path)] == [b.TAINTED, b.COMPLETE]
    assert ledger(tmp_path)[0]["transport_retries"] == 1
    assert len(aborted(tmp_path)) == 1


def test_a_run_tainted_on_every_attempt_stays_pending(tmp_path: Path) -> None:
    first, second = plan("C", "D")

    def always_tainted(run: b.PlannedRun, attempt: int) -> int:
        write_log(run.log(tmp_path / "runs" / b.PENDING), INPUTS)
        return 2 if run.condition == "C" else 0

    runner = FakeRunner(always_tainted)
    result = go(tmp_path, [first, second], runner)
    assert not result.done
    assert result.pending == [first.run_id]
    assert result.complete == [second.run_id]
    assert not final(tmp_path, first).exists(), "a tainted log is never put in place"
    assert [c for c in runner.calls if c[0] == first.run_id] == [
        (first.run_id, n) for n in (1, 2, 3)
    ]


def test_max_attempts_is_respected(tmp_path: Path) -> None:
    (run,) = plan()
    runner = FakeRunner(lambda run, attempt: 1)
    go(tmp_path, [run], runner, max_attempts=1)
    assert runner.calls == [(run.run_id, 1)]


def test_a_model_error_is_retried(tmp_path: Path) -> None:
    (run,) = plan()

    def flaky(run: b.PlannedRun, attempt: int) -> int:
        write_log(run.log(tmp_path / "runs" / b.PENDING), 2 if attempt == 1 else INPUTS)
        if attempt == 1:
            raise ModelUnavailable("server stalled")
        return 0

    assert go(tmp_path, [run], FakeRunner(flaky)).done
    assert [e["outcome"] for e in ledger(tmp_path)] == [b.MODEL_ERROR, b.COMPLETE]


def test_a_model_error_on_the_last_attempt_stops_the_batch(tmp_path: Path) -> None:
    first, second = plan("C", "D")

    def down(run: b.PlannedRun, attempt: int) -> int:
        raise ModelUnavailable("connection refused")

    runner = FakeRunner(down)
    result = go(tmp_path, [first, second], runner)
    assert result.stopped is not None and "connection refused" in result.stopped
    assert runner.calls == [(first.run_id, n) for n in (1, 2, 3)]
    assert result.pending == [first.run_id, second.run_id]


def test_a_config_mismatch_stops_the_batch_at_once(tmp_path: Path) -> None:
    first, second = plan("C", "D")

    def wrong_version(run: b.PlannedRun, attempt: int) -> int:
        raise ModelConfigMismatch("Ollama is 0.40.13")

    runner = FakeRunner(wrong_version)
    result = go(tmp_path, [first, second], runner)
    assert runner.calls == [(first.run_id, 1)]
    assert result.stopped == "Ollama is 0.40.13"


def test_a_bug_ends_only_its_own_run_and_is_not_retried(tmp_path: Path) -> None:
    first, second = plan("C", "D")

    def bug_in_c(run: b.PlannedRun, attempt: int) -> int:
        write_log(run.log(tmp_path / "runs" / b.PENDING), 2 if run.condition == "C" else INPUTS)
        if run.condition == "C":
            raise ValueError("refused record")
        return 0

    runner = FakeRunner(bug_in_c)
    result = go(tmp_path, [first, second], runner)
    assert runner.calls == [(first.run_id, 1), (second.run_id, 1)]
    assert result.errors == [first.run_id]
    assert result.complete == [second.run_id]
    assert not result.done
    entry = ledger(tmp_path)[0]
    assert entry["outcome"] == b.ERROR and "refused record" in entry["error"]
    assert entry["aborted_log"]


def test_a_run_that_returns_with_an_incomplete_log_is_an_error(tmp_path: Path) -> None:
    (run,) = plan()

    def short(run: b.PlannedRun, attempt: int) -> int:
        write_log(run.log(tmp_path / "runs" / b.PENDING), INPUTS - 1)
        return 0

    result = go(tmp_path, [run], FakeRunner(short))
    assert result.errors == [run.run_id]
    assert not final(tmp_path, run).exists()


def test_ledger_lines_carry_the_context(tmp_path: Path) -> None:
    (run,) = plan()
    go(tmp_path, [run], FakeRunner(), context={"model_digest": "sha256:x"})
    (entry,) = ledger(tmp_path)
    assert entry["model_digest"] == "sha256:x"
    assert entry["run_id"] == run.run_id
    assert entry["attempt"] == 1
    assert entry["records"] == INPUTS
