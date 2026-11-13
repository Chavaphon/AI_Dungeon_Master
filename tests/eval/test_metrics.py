"""Metrics (WBS 10.3): M2, the invalid tool-call and recovery rates, and the
run-level bootstrap of CLAUDE.md section 10.5.

The records are hand-built: M2 reads only `validation`, `executed_call` and
`turn_failure`, so each test writes the few turns it needs. The loader is given
a manifest over the real `s01_cellar` scenario and logs written to a temporary
runs folder.

No test calls a model.

Run: pytest tests/eval/test_metrics.py -v
"""

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path

import pytest
from typer.testing import CliRunner

from adm.engine.audit import log_path
from adm.eval import metrics

ROOT = Path(__file__).resolve().parents[2]
CELLAR_PATH = ROOT / "scenarios" / "s01_cellar.json"
SCENARIO = "s01_cellar"

CALL = {"tool": "dodge", "arguments": {"actor_id": "pc_lyra"}}
OK = {"ok": True, "tool": "dodge", "narration_facts": {}}
NULL = {"ok": True, "tool": None}
REJECT = {"ok": False, "tool": "attack", "rejection_code": "ENCOUNTER_OVER"}
SCHEMA = {"ok": False, "tool": "attack", "rejection_code": "SCHEMA_VIOLATION"}
UNPARSEABLE = {"ok": False, "failure": "unparseable", "message": "not JSON"}


def turn(validation: Sequence[dict], *, failure: str | None = None) -> dict:
    """One condition D record: its attempts, and how the turn ended."""
    executed = next((CALL for v in validation if v["ok"] and v.get("tool")), None)
    return {
        "validation": list(validation),
        "executed_call": executed if failure is None else None,
        "turn_failure": failure,
        "narration_only": failure is None and executed is None,
    }


def run(records: Sequence[dict], seed: int = 3001, scenario: str = SCENARIO) -> metrics.RunM2:
    return metrics.m2_run(("D", scenario, seed), records)


# --- one run -----------------------------------------------------------------


def test_a_turn_is_rejected_when_any_attempt_fails():
    r = run(
        [
            turn([OK]),
            turn([REJECT, OK]),
            turn([UNPARSEABLE, OK]),
            turn([REJECT, SCHEMA, OK]),
        ]
    )
    assert (r.turns, r.attempts) == (4, 8)
    assert (r.rejected_turns, r.rejected_attempts) == (3, 4)


def test_a_null_reply_is_not_a_rejection():
    r = run([turn([NULL, NULL]), turn([NULL, OK])])
    assert r.rejected_turns == 0
    assert r.rejected_attempts == 0
    assert r.first_attempt_null == 2


def test_a_turn_with_no_tool_phase_counts_as_a_turn_and_nothing_else():
    r = run([turn([])])
    assert (r.turns, r.attempts, r.rejected_turns, r.first_attempt_null) == (1, 0, 0, 0)


def test_recovery_counts_executed_and_narration_only_turns_but_not_failures():
    r = run(
        [
            turn([REJECT, OK]),
            turn([REJECT, SCHEMA, OK]),
            turn([REJECT, NULL]),
            turn([REJECT, REJECT, REJECT], failure="precondition"),
            turn([OK]),
        ]
    )
    assert r.rejected_turns == 4
    assert (r.recovered_executed, r.recovered_narration_only) == (2, 1)
    assert r.recovered_turns == 3
    assert r.recovered_attempts == {2: 2, 3: 1}
    assert r.turn_failures == {"precondition": 1}


def test_attempts_used_by_recovered_turns():
    r = run([turn([REJECT, OK]), turn([REJECT, NULL]), turn([REJECT, SCHEMA, OK])])
    assert r.recovered_attempts == {2: 2, 3: 1}


def test_codes_are_counted_over_every_attempt():
    r = run([turn([REJECT, SCHEMA, UNPARSEABLE], failure="unparseable"), turn([REJECT, OK])])
    assert r.codes == {"ENCOUNTER_OVER": 2, "SCHEMA_VIOLATION": 1, "unparseable": 1}
    assert r.turn_failures == {"unparseable": 1}


# --- the pooled figures -------------------------------------------------------


def test_pooled_rates_are_ratios_of_sums_not_means_of_run_rates():
    one = run([turn([REJECT, OK])], seed=1)  # 1 of 1 rejected, recovered
    many = run([turn([OK])] * 9, seed=2)  # 0 of 9
    report = metrics.m2([one, many], resamples=50)
    assert report["totals"]["turns"] == 10
    assert report["rates"]["rejected_turn_rate"]["value"] == pytest.approx(0.1)
    assert report["rates"]["recovery_rate"]["value"] == pytest.approx(1.0)


def test_report_holds_intervals_codes_failures_and_scenarios():
    runs = [
        run([turn([REJECT, OK]), turn([OK])], seed=1),
        run([turn([REJECT, REJECT, REJECT], failure="precondition"), turn([OK])], seed=2),
        run([turn([OK]), turn([UNPARSEABLE, OK])], seed=3, scenario="s02_toll_bridge"),
    ]
    report = metrics.m2(runs, resamples=200)
    rates = report["rates"]
    assert set(rates) == {"rejected_turn_rate", "rejected_attempt_rate", "recovery_rate"}
    for rate in rates.values():
        low, high = rate["interval"]
        assert low <= rate["value"] <= high
    assert rates["rejected_attempt_rate"]["value"] == pytest.approx(5 / 6)
    assert report["codes"] == {"ENCOUNTER_OVER": 4, "unparseable": 1}
    assert report["turn_failures"] == {"precondition": 1}
    assert [s["scenario_id"] for s in report["scenarios"]] == [SCENARIO, "s02_toll_bridge"]
    assert report["scenarios"][0]["rejected_turns"] == 2
    assert report["bootstrap"] == {
        "resamples": 200,
        "seed": metrics.BOOTSTRAP_SEED,
        "confidence": 0.95,
        "unit": "run",
    }


# --- the bootstrap ------------------------------------------------------------


def _mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs)


def test_bootstrap_is_reproducible_from_its_seed():
    units = [0.1, 0.4, 0.2, 0.9, 0.5, 0.3]
    first = metrics.bootstrap(units, _mean, resamples=500, seed=7)
    assert first == metrics.bootstrap(units, _mean, resamples=500, seed=7)
    assert first != metrics.bootstrap(units, _mean, resamples=500, seed=8)


def test_bootstrap_of_identical_units_has_zero_width():
    assert metrics.bootstrap([0.25] * 5, _mean, resamples=100) == (0.25, 0.25)


def test_bootstrap_interval_contains_the_estimate():
    units = [float(i % 7) for i in range(40)]
    low, high = metrics.bootstrap(units, _mean, resamples=1000)
    assert low < _mean(units) < high


def test_stratified_bootstrap_keeps_each_stratum_size():
    units = [("A", 0.0)] * 3 + [("D", 1.0)] * 2
    sizes = set()

    def share_of_d(sample: Sequence[tuple[str, float]]) -> float:
        sizes.add(sum(1 for c, _ in sample if c == "D"))
        return _mean([v for _, v in sample])

    low, high = metrics.bootstrap(units, share_of_d, strata=lambda u: u[0], resamples=100)
    assert sizes == {2}
    assert low == high == pytest.approx(0.4)


def test_bootstrap_skips_resamples_where_the_statistic_is_undefined():
    units = [0, 0, 1]

    def only_with_one(sample: Sequence[int]) -> float | None:
        return 1.0 if 1 in sample else None

    assert metrics.bootstrap(units, only_with_one, resamples=100) == (1.0, 1.0)
    assert metrics.bootstrap([0, 0], only_with_one, resamples=10) is None


def test_percentile_interpolates_linearly():
    assert metrics.percentile([1.0, 2.0, 3.0, 4.0, 5.0], 0.5) == 3.0
    assert metrics.percentile([0.0, 10.0], 0.025) == pytest.approx(0.25)


# --- the dataset --------------------------------------------------------------


def _manifest(folder: Path, seeds: Sequence[int] = (3001, 3002)) -> Path:
    path = folder / "manifest.json"
    doc = {
        "description": "test",
        "scenarios": [str(CELLAR_PATH)],
        "conditions": ["A", "D"],
        "seeds": list(seeds),
    }
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def _write_logs(runs: Path, seeds: Sequence[int] = (3001, 3002)) -> list[Path]:
    paths = []
    for seed in seeds:
        path = log_path(runs, "D", SCENARIO, seed)
        path.parent.mkdir(parents=True, exist_ok=True)
        records = [turn([REJECT, OK]), turn([OK])]
        path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
        paths.append(path)
    return paths


def _checksums(folder: Path, runs: Path, paths: Sequence[Path]) -> Path:
    out = folder / "grid.sha256"
    lines = [
        f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(runs.parent).as_posix()}"
        for p in paths
    ]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def test_loader_reads_only_the_planned_condition_d_runs(tmp_path):
    runs = tmp_path / "runs"
    paths = _write_logs(runs)
    a_log = log_path(runs, "A", SCENARIO, 3001)
    a_log.parent.mkdir(parents=True)
    a_log.write_text("", encoding="utf-8")
    logs = metrics.load_d_runs(
        runs, _manifest(tmp_path), _checksums(tmp_path, runs, [*paths, a_log])
    )
    assert sorted(logs) == [("D", SCENARIO, 3001), ("D", SCENARIO, 3002)]
    assert len(logs[("D", SCENARIO, 3001)]) == 2


def test_loader_refuses_a_missing_planned_log(tmp_path):
    runs = tmp_path / "runs"
    _write_logs(runs, seeds=(3001,))
    with pytest.raises(metrics.DatasetError, match="3002"):
        metrics.load_d_runs(runs, _manifest(tmp_path), None)


def test_loader_refuses_a_log_that_differs_from_its_checksum(tmp_path):
    runs = tmp_path / "runs"
    paths = _write_logs(runs)
    sums = _checksums(tmp_path, runs, paths)
    with paths[1].open("a", encoding="utf-8") as log:
        log.write(json.dumps(turn([OK])) + "\n")
    with pytest.raises(metrics.DatasetError, match="sha256"):
        metrics.load_d_runs(runs, _manifest(tmp_path), sums)


def test_loader_refuses_a_log_absent_from_the_checksum_file(tmp_path):
    runs = tmp_path / "runs"
    paths = _write_logs(runs)
    sums = _checksums(tmp_path, runs, paths[:1])
    with pytest.raises(metrics.DatasetError, match="checksum file"):
        metrics.load_d_runs(runs, _manifest(tmp_path), sums)


def test_cli_writes_the_report_and_the_doc_block(tmp_path):
    runs = tmp_path / "runs"
    paths = _write_logs(runs)
    doc = tmp_path / "m2.md"
    doc.write_text(
        f"# M2\n\n{metrics.RESULTS_START}\nold\n{metrics.RESULTS_END}\n\nAfter.\n",
        encoding="utf-8",
    )
    out = tmp_path / "m2.json"
    args = [
        "m2",
        "--runs",
        str(runs),
        "--manifest",
        str(_manifest(tmp_path)),
        "--checksums",
        str(_checksums(tmp_path, runs, paths)),
        "--out",
        str(out),
        "--doc",
        str(doc),
        "--resamples",
        "100",
    ]
    result = CliRunner().invoke(metrics.app, args)
    assert result.exit_code == 0, result.output
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["totals"]["rejected_turns"] == 2
    text = doc.read_text(encoding="utf-8")
    assert "old" not in text
    assert "50.0%" in text
    assert text.endswith("After.\n")
    assert CliRunner().invoke(metrics.app, args).exit_code == 0
    assert json.loads(out.read_text(encoding="utf-8")) == report


def test_cli_exits_1_on_a_dataset_error(tmp_path):
    result = CliRunner().invoke(
        metrics.app,
        ["m2", "--runs", str(tmp_path / "runs"), "--manifest", str(_manifest(tmp_path))],
    )
    assert result.exit_code == 1
    assert "No log" in result.output
