"""The run-log validator (WBS 7.7): every log on disk is a whole, valid run.

Logs are written by the real harnesses with a fake client, for all four
conditions, then damaged one way at a time: a record that breaks the schema, a
missing record, a changed input, a wrong hash, a log in another run's place, a
planned run with no log. Each is reported, and only a clean grid passes.

No test calls a model.

Run: pytest tests/eval/test_validate.py -v
"""

import json
from collections.abc import Sequence
from pathlib import Path

import pytest
from typer.testing import CliRunner

from adm.engine.audit import log_path, read_log
from adm.engine.scenario import load_scenario
from adm.eval import validate
from adm.eval.checker import load_runs
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
CONDITIONS = ("A", "B", "C", "D")
NARRATION = "Water drips down the cellar stairs and pools around the barrels."


class FakeClient:
    """Proposes `{"tool": null}`, narrates one fixed line, summarises one line."""

    def chat(self, messages: Sequence[Message], *, phase: Phase, seed: int) -> ModelReply:
        reply = {"toolcall": '{"tool": null}', "narration": NARRATION}.get(
            phase, "Lyra searched the cellar."
        )
        return ModelReply(reply, 3000, 40, 0, 0, "stop", 0)


def _play(runs: Path, condition: str) -> Path:
    log = new_run_log(runs, condition, CELLAR.scenario_id, SEED)
    start = Session.start if condition == "D" else NarrationOnlyStart(condition.lower())
    run_script(start(FakeClient(), CONFIG, TEXTS, CELLAR, log, seed=SEED))
    return log.path


@pytest.fixture(scope="module")
def grid(tmp_path_factory: pytest.TempPathFactory) -> Path:
    runs = tmp_path_factory.mktemp("runs")
    for condition in CONDITIONS:
        _play(runs, condition)
    return runs


@pytest.fixture
def runs(grid: Path, tmp_path: Path) -> Path:
    """A fresh copy of the clean grid, safe to damage."""
    copy = tmp_path / "runs"
    for path in grid.rglob("*.jsonl"):
        target = copy / path.relative_to(grid)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
    return copy


def _manifest(tmp_path: Path, conditions: Sequence[str] = CONDITIONS) -> Path:
    path = tmp_path / "manifest.json"
    doc = {
        "description": "test",
        "scenarios": [str(SCENARIOS / "s01_cellar.json")],
        "conditions": list(conditions),
        "seeds": [SEED],
    }
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def _log(runs: Path, condition: str) -> Path:
    return log_path(runs, condition, CELLAR.scenario_id, SEED)


def _rewrite(path: Path, records: Sequence[dict]) -> None:
    path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")


def _errors(runs: Path, condition: str) -> list[str]:
    report = validate.validate_runs(load_runs(runs), {CELLAR.scenario_id: CELLAR})
    return next(r.errors for r in report.runs if r.key[0] == condition)


def test_a_clean_grid_of_all_four_conditions_is_valid(runs: Path, tmp_path: Path) -> None:
    planned = validate.planned_runs(_manifest(tmp_path))
    report = validate.validate_runs(load_runs(runs), {CELLAR.scenario_id: CELLAR}, planned)

    assert report.ok and report.error_count == 0
    assert [r.run_id for r in report.runs] == [f"{c}_s01_cellar_{SEED}" for c in CONDITIONS]
    assert {r.records for r in report.runs} == {len(CELLAR.scripted_inputs)}
    assert report.missing == [] and report.unplanned == []


def test_a_record_that_breaks_the_schema_is_reported(runs: Path) -> None:
    path = _log(runs, "B")
    records = read_log(path)
    del records[3]["narration"]
    _rewrite(path, records)

    errors = _errors(runs, "B")
    assert errors and all(e.startswith("record 3: ") for e in errors)
    assert any("narration" in e for e in errors)


def test_a_record_that_breaks_a_rule_the_schema_cannot_express_is_reported(runs: Path) -> None:
    path = _log(runs, "D")
    records = read_log(path)
    records[2]["narration_only"] = not records[2]["narration_only"]
    _rewrite(path, records)

    assert "record 2: narration_only does not match the toolcall outcome" in _errors(runs, "D")


def test_a_missing_record_is_reported(runs: Path) -> None:
    path = _log(runs, "A")
    _rewrite(path, read_log(path)[:-1])

    [error] = _errors(runs, "A")
    assert "input_index" in error and f"not 0..{len(CELLAR.scripted_inputs) - 1}" in error


def test_an_input_that_is_not_the_scripted_text_is_reported(runs: Path) -> None:
    path = _log(runs, "C")
    records = read_log(path)
    records[5]["player_input"] = "I attack the Keeper"
    _rewrite(path, records)

    assert _errors(runs, "C") == ["input 5: player_input is not the scripted input's text"]


@pytest.mark.parametrize("condition", ["A", "D"])
def test_a_state_hash_that_does_not_replay_is_reported(runs: Path, condition: str) -> None:
    path = _log(runs, condition)
    records = read_log(path)
    record = records[-1]
    zero = "sha256:" + "0" * 64
    # A turn with no diff has equal hashes; keep them equal so the record still
    # passes its own rules and only the replay can tell.
    if record["state_before_hash"] == record["state_after_hash"]:
        record["state_before_hash"] = zero
    record["state_after_hash"] = zero
    _rewrite(path, records)

    [error] = _errors(runs, condition)
    assert error.startswith(f"{record['run_id']} input {record['input_index']}: ")
    assert "_hash" in error


def test_a_log_in_another_runs_place_is_reported(runs: Path) -> None:
    _log(runs, "B").write_bytes(_log(runs, "A").read_bytes())

    errors = _errors(runs, "B")
    assert "record 0: condition is 'A', the log is 'B'" in errors
    assert f"record 0: run_id is 'A_s01_cellar_{SEED}', the log is 'B_s01_cellar_{SEED}'" in errors


def test_an_empty_log_is_reported(runs: Path) -> None:
    _log(runs, "A").write_text("", encoding="utf-8")
    assert _errors(runs, "A") == ["the log is empty"]


def test_a_planned_run_with_no_log_is_an_error_and_an_unplanned_log_is_not(
    runs: Path, tmp_path: Path
) -> None:
    _log(runs, "C").unlink()
    planned = validate.planned_runs(_manifest(tmp_path, ("B", "C", "D")))
    report = validate.validate_runs(load_runs(runs), {CELLAR.scenario_id: CELLAR}, planned)

    assert report.missing == [f"C_s01_cellar_{SEED}"]
    assert report.unplanned == [f"A_s01_cellar_{SEED}"]
    assert report.error_count == 1 and not report.ok


def test_the_command_line_exits_0_only_on_a_valid_grid_and_writes_the_report(
    runs: Path, tmp_path: Path
) -> None:
    out = tmp_path / "results" / "validation.json"
    args = ["--runs", str(runs), "--manifest", str(_manifest(tmp_path))]
    args += ["--scenarios", str(SCENARIOS), "--out", str(out)]

    clean = CliRunner().invoke(validate.app, args)
    assert clean.exit_code == 0, clean.output
    inputs = len(CELLAR.scripted_inputs)
    assert f"4 runs, {4 * inputs} records: valid" in clean.output
    assert json.loads(out.read_text(encoding="utf-8"))["ok"] is True

    path = _log(runs, "D")
    _rewrite(path, read_log(path)[:-1])
    broken = CliRunner().invoke(validate.app, args)
    assert broken.exit_code == 1
    assert f"D_s01_cellar_{SEED}: {inputs - 1} records, 1 errors" in broken.output
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["ok"] is False and report["errors"] == 1
