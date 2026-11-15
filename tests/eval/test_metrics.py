"""Metrics (WBS 10.3, 10.4): M2, the invalid tool-call and recovery rates; M4,
the rule-violation rate; M6, latency and throughput; and the run-level bootstrap
of CLAUDE.md section 10.5.

The records are hand-built: M2 reads only `validation`, `executed_call` and
`turn_failure`, M6 only `turn_latency_ms` and `model_calls`, so each test writes
the few turns it needs. M4's candidates come from the checker, tested in
test_checker.py and test_rules.py; here they are recorded. The loader is given
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

from adm.engine.audit import log_path, run_id
from adm.eval import metrics
from adm.eval.checker import Turn

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


def _manifest(folder: Path, seeds: Sequence[int] = (3001, 3002), conditions: str = "AD") -> Path:
    path = folder / "manifest.json"
    doc = {
        "description": "test",
        "scenarios": [str(CELLAR_PATH)],
        "conditions": list(conditions),
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
    logs = metrics.load_planned_runs(
        runs, _manifest(tmp_path), _checksums(tmp_path, runs, [*paths, a_log])
    )
    assert sorted(logs) == [("D", SCENARIO, 3001), ("D", SCENARIO, 3002)]
    assert len(logs[("D", SCENARIO, 3001)]) == 2


def test_loader_refuses_a_missing_planned_log(tmp_path):
    runs = tmp_path / "runs"
    _write_logs(runs, seeds=(3001,))
    with pytest.raises(metrics.DatasetError, match="3002"):
        metrics.load_planned_runs(runs, _manifest(tmp_path), None)


def test_loader_refuses_a_log_that_differs_from_its_checksum(tmp_path):
    runs = tmp_path / "runs"
    paths = _write_logs(runs)
    sums = _checksums(tmp_path, runs, paths)
    with paths[1].open("a", encoding="utf-8") as log:
        log.write(json.dumps(turn([OK])) + "\n")
    with pytest.raises(metrics.DatasetError, match="sha256"):
        metrics.load_planned_runs(runs, _manifest(tmp_path), sums)


def test_loader_refuses_a_log_absent_from_the_checksum_file(tmp_path):
    runs = tmp_path / "runs"
    paths = _write_logs(runs)
    sums = _checksums(tmp_path, runs, paths[:1])
    with pytest.raises(metrics.DatasetError, match="checksum file"):
        metrics.load_planned_runs(runs, _manifest(tmp_path), sums)


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


def test_loader_reads_the_planned_runs_of_the_conditions_asked_for(tmp_path):
    runs = tmp_path / "runs"
    paths = _write_timed_logs(runs)
    sums = _checksums(tmp_path, runs, paths)
    logs = metrics.load_planned_runs(runs, _manifest(tmp_path), sums, ("A", "D"))
    assert sorted(logs) == [
        ("A", SCENARIO, 3001),
        ("A", SCENARIO, 3002),
        ("D", SCENARIO, 3001),
        ("D", SCENARIO, 3002),
    ]


# --- M4 (WBS 10.4) --------------------------------------------------------------
#
# `check_turn` is replaced by recorded candidates, so these tests are about
# counting. A Turn needs only its record here.


def _turn(run: str, index: int) -> Turn:
    record = {"run_id": run, "input_index": index}
    return Turn(record, None, {}, {}, None, ())  # type: ignore[arg-type]


def _candidate(kind: str, confidence: str = "high", check: str = "rule_violation") -> dict:
    return {"check": check, "category": "RULE", "kind": kind, "confidence": confidence}


@pytest.fixture
def recorded(monkeypatch):
    """Candidates by (run id, input index), served in place of the checker."""
    found: dict[tuple[str, int], list[dict]] = {}

    def check_turn(turn, checks):
        assert checks == metrics.M4_CHECKS
        return found.get((turn.record["run_id"], turn.record["input_index"]), [])

    monkeypatch.setattr(metrics, "check_turn", check_turn)
    return found


def test_m4_run_counts_high_low_and_state_audit_by_rule(recorded):
    recorded[("D_x_1", 0)] = [_candidate("out_of_turn"), _candidate("after_encounter_end", "low")]
    recorded[("D_x_1", 2)] = [_candidate("negative_hp", check="state_audit")]
    r = metrics.m4_run(("D", "x", 1), [_turn("D_x_1", i) for i in range(4)])
    assert (r.narrated, r.high, r.low, r.state_audit, r.m4) == (4, 1, 1, 1, 2)
    assert r.kinds == {
        "after_encounter_end": {"low": 1},
        "negative_hp": {"state_audit": 1},
        "out_of_turn": {"high": 1},
    }


def _m4(condition: str, seed: int, narrated: int, high: int, low: int = 0) -> metrics.RunM4:
    kinds = {"out_of_turn": {"high": high, "low": low}}
    return metrics.RunM4((condition, "x", seed), narrated, high, low, 0, kinds)


def test_m4_is_high_and_state_audit_per_100_narrated_turns_with_low_apart():
    runs = [_m4("A", 1, 100, 1, 4), _m4("A", 2, 100, 3), _m4("D", 1, 50, 0, 2)]
    report = metrics.m4(runs, resamples=200)
    a, d, pooled = (report["conditions"][c] for c in ("A", "D", "all"))
    assert a["m4"]["value"] == pytest.approx(2.0)
    assert (a["m4"]["numerator"], a["m4"]["denominator"]) == (4, 200)
    assert a["low_per_100"] == pytest.approx(2.0)
    low, high = a["m4"]["interval"]
    assert low <= 2.0 <= high
    assert d["m4"]["value"] == 0
    assert d["m4"]["interval"] == [0, 0]
    assert pooled["m4"]["value"] == pytest.approx(100 * 4 / 250)
    assert report["kinds"]["out_of_turn"] == {
        "A": {"high": 4, "low": 4},
        "D": {"high": 0, "low": 2},
    }
    assert report["labels"] is None
    text = metrics.render_m4(report)
    assert "**2.00**" in text
    assert "Not computed" in text


def _label_line(run: str, index: int, candidates=(), added=(), annotator: str = "SD") -> dict:
    return {
        "run_id": run,
        "input_index": index,
        "annotator": annotator,
        "candidates": [
            {"category": cat, "confidence": conf, "confirmed": ok} for cat, conf, ok in candidates
        ],
        "added": [{"category": cat} for cat in added],
    }


def _write_labels(path: Path, lines: Sequence[dict]) -> Path:
    path.write_text("".join(json.dumps(line) + "\n" for line in lines), encoding="utf-8")
    return path


def test_labels_count_confirmed_rule_candidates_and_added_breaks(tmp_path):
    lines = [
        _label_line("A_x_1", 0, [("RULE", "high", True), ("RULE", "low", False)], ["RULE"]),
        _label_line("A_x_1", 1, [("PHANTOM", "high", True), ("RULE", "low", True)], ["PHANTOM"]),
        _label_line("A_x_1", 0, [("RULE", "high", False)], annotator="SS"),
    ]
    labels = metrics.read_labels(_write_labels(tmp_path / "l.jsonl", lines), "SD")
    [r] = metrics.label_runs({("A", "x", 1): [_turn("A_x_1", 0), _turn("A_x_1", 1)]}, labels)
    counts = (r.shown_high, r.shown_low, r.confirmed_high, r.confirmed_low, r.added)
    assert counts == (1, 2, 1, 1, 1)
    assert r.confirmed == 3
    report = metrics.m4([_m4("A", 1, 2, 0)], [r], annotator="SD", resamples=50)
    row = report["labels"]["conditions"]["A"]
    assert row["rate"]["value"] == pytest.approx(150.0)
    assert (row["precision_high"], row["precision_low"]) == (1.0, 0.5)
    assert "Annotator SD" in metrics.render_m4(report)


def test_labels_refuse_a_sample_turn_with_no_line(tmp_path):
    path = _write_labels(tmp_path / "l.jsonl", [_label_line("A_x_1", 0)])
    labels = metrics.read_labels(path, "SD")
    with pytest.raises(
        metrics.DatasetError, match="1 sample turns have no label line: A_x_1 input 1"
    ):
        metrics.label_runs({("A", "x", 1): [_turn("A_x_1", 0), _turn("A_x_1", 1)]}, labels)


def test_labels_refuse_two_lines_for_one_turn(tmp_path):
    path = _write_labels(tmp_path / "l.jsonl", [_label_line("A_x_1", 0)] * 2)
    with pytest.raises(metrics.DatasetError, match="two lines"):
        metrics.read_labels(path, "SD")


# --- M6 (WBS 10.4) --------------------------------------------------------------


def _timed(latency_ms: int, *calls: tuple[str, int, int]) -> dict:
    """A record's turn latency and its (phase, completion_tokens, eval_ms) calls."""
    return {
        "turn_latency_ms": latency_ms,
        "model_calls": [{"phase": p, "completion_tokens": n, "eval_ms": ms} for p, n, ms in calls],
    }


def test_m6_run_takes_every_turn_and_skips_calls_with_no_eval_ms():
    records = [
        _timed(4000, ("toolcall", 30, 500), ("narration", 120, 2000)),
        _timed(2500, ("toolcall", 20, 0)),  # a failed turn: still a turn the player waited for
    ]
    r = metrics.m6_run(("D", "x", 1), records)
    assert r.seconds == (4.0, 2.5)
    assert r.rates == (("toolcall", 60.0), ("narration", 60.0))
    assert r.zero_eval == 1


def _m6(condition: str, seed: int, seconds: Sequence[float]) -> metrics.RunM6:
    return metrics.RunM6((condition, "x", seed), tuple(seconds), (("narration", 50.0),), 0)


def test_m6_reports_mean_p95_max_and_tokens_per_second_by_phase():
    seconds = [1.0 + 0.1 * i for i in range(20)]
    report = metrics.m6([_m6("D", s, seconds) for s in range(3)], resamples=200)
    s = report["conditions"]["D"]["seconds"]
    assert s["mean"] == pytest.approx(1.95)
    assert s["p95"] == pytest.approx(metrics.percentile(seconds, 0.95))
    assert s["max"] == pytest.approx(2.9)
    assert report["conditions"]["D"]["tokens_per_second"]["phases"] == {
        "narration": {"calls": 3, "mean": 50.0}
    }
    assert report["target"]["met"] is True
    assert ": met." in metrics.render_m6(report)


def test_m6_target_is_not_met_when_the_upper_bound_reaches_it():
    runs = [_m6("D", 1, [1.0] * 15 + [30.0] * 5), _m6("D", 2, [1.0] * 20)]
    target = metrics.m6(runs, resamples=200)["target"]
    assert target["p95"] > 10
    assert target["met"] is False
    # 4 slow turns in 100 keep the p95 fast; a resample drawing run 1 twice does not
    runs = [_m6("D", 1, [1.0] * 16 + [30.0] * 4)] + [_m6("D", s, [1.0] * 20) for s in range(2, 6)]
    target = metrics.m6(runs, resamples=200)["target"]
    assert target["p95"] < 10 < target["p95_upper"]
    assert target["met"] is False


def test_m6_has_no_target_without_condition_d():
    assert metrics.m6([_m6("A", 1, [1.0])], resamples=10)["target"] is None


# --- the M4 and M6 commands -----------------------------------------------------


def _write_timed_logs(
    runs: Path, seeds: Sequence[int] = (3001, 3002), conditions: str = "AD"
) -> list[Path]:
    """Three-turn logs, 3, 4 and 5 s per turn, 60 tok/s."""
    paths = []
    for condition in conditions:
        for seed in seeds:
            path = log_path(runs, condition, SCENARIO, seed)
            path.parent.mkdir(parents=True, exist_ok=True)
            records = [
                {
                    **turn([OK]),
                    **_timed(3000 + 1000 * i, ("narration", 60, 1000)),
                    "run_id": run_id(condition, SCENARIO, seed),
                    "input_index": i,
                }
                for i in range(3)
            ]
            path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
            paths.append(path)
    return paths


def _command(
    tmp_path: Path, name: str, *extra: str, conditions: str = "AD"
) -> tuple[Path, Path, list[str]]:
    runs = tmp_path / "runs"
    paths = _write_timed_logs(runs, conditions=conditions)
    doc = tmp_path / f"{name}.md"
    doc.write_text(
        f"# {name}\n\n{metrics.RESULTS_START}\nold\n{metrics.RESULTS_END}\n", encoding="utf-8"
    )
    out = tmp_path / f"{name}.json"
    args = [
        name,
        "--runs",
        str(runs),
        "--manifest",
        str(_manifest(tmp_path, conditions=conditions)),
        "--checksums",
        str(_checksums(tmp_path, runs, paths)),
        "--out",
        str(out),
        "--doc",
        str(doc),
        "--resamples",
        "50",
        *extra,
    ]
    return out, doc, args


@pytest.fixture
def recorded_turns(monkeypatch):
    """Every record a narrated turn, in place of the checker's replay."""
    monkeypatch.setattr(
        metrics,
        "turns",
        lambda scenario, records: (_turn(r["run_id"], r["input_index"]) for r in records),
    )


def test_m4_command_scores_every_condition_and_rewrites_the_doc(tmp_path, recorded, recorded_turns):
    recorded[(run_id("D", SCENARIO, 3001), 1)] = [_candidate("out_of_turn")]
    out, doc, args = _command(tmp_path, "m4")
    result = CliRunner().invoke(metrics.app, args)
    assert result.exit_code == 0, result.output
    report = json.loads(out.read_text(encoding="utf-8"))
    assert list(report["conditions"]) == ["A", "D", "all"]
    assert report["conditions"]["D"]["m4"]["value"] == pytest.approx(100 / 6)
    assert "old" not in doc.read_text(encoding="utf-8")
    assert CliRunner().invoke(metrics.app, args).exit_code == 0
    assert json.loads(out.read_text(encoding="utf-8")) == report


def test_m4_command_counts_the_labels_of_the_m1_sample(tmp_path, recorded, recorded_turns):
    # one seed per scenario and all four conditions at it: 4 runs of 3 turns
    lines = [
        _label_line(run_id(c, SCENARIO, seed), i, added=["RULE"] if c == "A" else [])
        for c in "ABCD"
        for seed in (3001, 3002)
        for i in range(3)
    ]
    labels = _write_labels(tmp_path / "labels.jsonl", lines)
    out, doc, args = _command(tmp_path, "m4", "--labels", str(labels), conditions="ABCD")
    result = CliRunner().invoke(metrics.app, args)
    assert result.exit_code == 0, result.output
    report = json.loads(out.read_text(encoding="utf-8"))["labels"]
    assert (report["annotator"], report["runs"]) == ("SD", 4)
    assert report["conditions"]["A"]["rate"]["value"] == pytest.approx(100.0)
    assert report["conditions"]["D"]["confirmed"] == 0


def test_m4_command_exits_1_on_incomplete_labels(tmp_path, recorded, recorded_turns):
    labels = _write_labels(tmp_path / "labels.jsonl", [])
    _, _, args = _command(tmp_path, "m4", "--labels", str(labels), conditions="ABCD")
    result = CliRunner().invoke(metrics.app, args)
    assert result.exit_code == 1
    assert "no label line" in result.output


def test_m4_command_exits_1_when_no_m1_sample_run_is_planned(tmp_path, recorded, recorded_turns):
    labels = _write_labels(tmp_path / "labels.jsonl", [])
    _, _, args = _command(tmp_path, "m4", "--labels", str(labels))
    result = CliRunner().invoke(metrics.app, args)
    assert result.exit_code == 1
    assert "M1 sample" in result.output


def test_m6_command_reports_every_condition(tmp_path):
    out, doc, args = _command(tmp_path, "m6")
    result = CliRunner().invoke(metrics.app, args)
    assert result.exit_code == 0, result.output
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["conditions"]["A"]["seconds"]["mean"] == pytest.approx(4.0)
    assert report["conditions"]["D"]["tokens_per_second"]["mean"] == pytest.approx(60.0)
    assert report["target"]["met"] is True
    assert "Seconds per turn" in doc.read_text(encoding="utf-8")
