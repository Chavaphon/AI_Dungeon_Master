"""The run integrity check (WBS 9.3): completeness, crashes and seeds.

A grid of all four conditions is played through the real batch runner with a
fake client, so the logs and the attempt ledger are the ones a batch writes.
Then it is damaged one way at a time: a missing log, a log cut short in a copy,
an invalid log, a ledger with no line, a failed last attempt, a tainted or
miscounted complete line, a second model, leftovers in `runs/pending/` and
`runs/aborted/`, a missing seed and a changed log against its checksum. Each is
reported, and only a clean grid passes.

No test calls a model.

Run: pytest tests/eval/test_integrity.py -v
"""

import json
from collections.abc import Sequence
from pathlib import Path

import pytest
from typer.testing import CliRunner

from adm.engine.audit import log_path, read_log
from adm.engine.scenario import load_scenario
from adm.eval import integrity
from adm.orchestration import batch, prompt
from adm.orchestration.client import Message, ModelReply, Phase, load_model_config
from adm.orchestration.narration_only import NarrationOnlyStart
from adm.orchestration.session import Session, new_run_log, run_script

ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = ROOT / "scenarios"
CELLAR_PATH = SCENARIOS / "s01_cellar.json"
CELLAR = load_scenario(CELLAR_PATH)
TEXTS = prompt.load_templates()
CONFIG = load_model_config()
SEED = 3001
CONDITIONS = ("A", "B", "C", "D")
NARRATION = "Water drips down the cellar stairs and pools around the barrels."
INPUTS = len(CELLAR.scripted_inputs)


class FakeClient:
    """Proposes `{"tool": null}`, narrates one fixed line, summarises one line."""

    def chat(self, messages: Sequence[Message], *, phase: Phase, seed: int) -> ModelReply:
        reply = {"toolcall": '{"tool": null}', "narration": NARRATION}.get(
            phase, "Lyra searched the cellar."
        )
        return ModelReply(reply, 3000, 40, 0, 0, "stop", 0)


def _runner(run: batch.PlannedRun, staging: Path) -> int:
    log = new_run_log(staging, run.condition, run.scenario.scenario_id, run.seed)
    condition = run.condition
    start = Session.start if condition == "D" else NarrationOnlyStart(condition.lower())
    run_script(start(FakeClient(), CONFIG, TEXTS, run.scenario, log, seed=run.seed))
    return 0


def _manifest(folder: Path, seeds: Sequence[int] = (SEED,)) -> Path:
    path = folder / "manifest.json"
    doc = {
        "description": "test",
        "scenarios": [str(CELLAR_PATH)],
        "conditions": list(CONDITIONS),
        "seeds": list(seeds),
    }
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def _context(manifest: Path) -> dict:
    return {
        "manifest": manifest.as_posix(),
        "model": CONFIG.model,
        "model_digest": CONFIG.model_digest,
    }


@pytest.fixture(scope="module")
def grid(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """`runs/`, `results/batch/attempts.jsonl` and the manifest of a clean batch."""
    root = tmp_path_factory.mktemp("grid")
    manifest = _manifest(root)
    result = batch.run_batch(
        batch.load_manifest(manifest, CONDITIONS),
        runs_dir=root / "runs",
        runner=_runner,
        ledger=root / "results" / "batch" / "attempts.jsonl",
        context=_context(manifest),
        log=lambda line: None,
    )
    assert result.done
    return root


@pytest.fixture
def root(grid: Path, tmp_path: Path) -> Path:
    """A fresh copy of the clean grid, safe to damage."""
    for path in grid.rglob("*"):
        if path.is_file():
            target = tmp_path / path.relative_to(grid)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())
    return tmp_path


def _check(root: Path) -> integrity.Report:
    return integrity.check(root / "runs", root / "manifest.json", _ledger(root))


def _ledger(root: Path) -> Path:
    return root / "results" / "batch" / "attempts.jsonl"


def _log(root: Path, condition: str, seed: int = SEED) -> Path:
    return log_path(root / "runs", condition, CELLAR.scenario_id, seed)


def _run(report: integrity.Report, condition: str) -> integrity.RunIntegrity:
    return next(r for r in report.runs if r.key[0] == condition)


def _ledger_lines(root: Path) -> list[dict]:
    return [json.loads(line) for line in _ledger(root).read_text(encoding="utf-8").splitlines()]


def _write_ledger(root: Path, lines: Sequence[dict]) -> None:
    _ledger(root).write_text("".join(json.dumps(x) + "\n" for x in lines), encoding="utf-8")


def _rid(condition: str, seed: int = SEED) -> str:
    return f"{condition}_s01_cellar_{seed}"


# --- a clean grid ------------------------------------------------------------


def test_the_ledger_outcome_is_the_batch_runners() -> None:
    assert integrity.COMPLETE == batch.COMPLETE
    assert (integrity.PENDING, integrity.ABORTED) == (batch.PENDING, batch.ABORTED)


def test_a_clean_batch_has_no_gap(root: Path) -> None:
    report = _check(root)

    assert report.ok and report.gaps == []
    assert [r.run_id for r in report.runs] == [_rid(c) for c in CONDITIONS]
    assert {r.records for r in report.runs} == {INPUTS}
    assert report.record_count == 4 * INPUTS
    assert report.seeds == [SEED] and report.seed_errors == []
    assert report.models == {f"{CONFIG.model}@{CONFIG.model_digest}": 4}
    assert report.pending == report.aborted == report.unplanned == []
    assert all(r.history == [] for r in report.runs)
    assert report.empty_narrations == []


def test_each_run_carries_the_sha256_of_its_log(root: Path) -> None:
    import hashlib

    report = _check(root)
    for run in report.runs:
        assert run.sha256 == hashlib.sha256(_log(root, run.key[0]).read_bytes()).hexdigest()


# --- completeness ------------------------------------------------------------


def test_a_planned_run_with_no_log_is_a_gap(root: Path) -> None:
    _log(root, "C").unlink()
    report = _check(root)

    assert report.gaps == [_rid("C")] and not report.ok
    assert "no log" in _run(report, "C").errors
    assert report.seed_errors == [f"C s01_cellar: no log for seeds [{SEED}]"]


def test_a_log_cut_short_in_a_copy_is_a_gap_not_a_crash(root: Path) -> None:
    path = _log(root, "B")
    data = path.read_bytes()
    path.write_bytes(data[: len(data) - 40])

    report = _check(root)
    assert report.gaps == [_rid("B")]
    assert f"line {INPUTS} is not JSON" in _run(report, "B").errors


def test_a_log_the_validator_rejects_is_a_gap(root: Path) -> None:
    path = _log(root, "A")
    records = read_log(path)
    records[4]["player_input"] = "I attack the Keeper"
    path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")

    report = _check(root)
    assert report.gaps == [_rid("A")]
    assert "input 4: player_input is not the scripted input's text" in _run(report, "A").errors


def test_a_log_outside_the_manifest_is_listed_and_not_checked(root: Path) -> None:
    stray = _log(root, "D", seed=1001)
    stray.parent.mkdir(parents=True, exist_ok=True)
    stray.write_text("not json\n", encoding="utf-8")

    report = _check(root)
    assert report.ok
    assert report.unplanned == [_rid("D", 1001)]
    assert report.strays == []


def test_a_file_copied_into_the_wrong_folder_is_listed_as_a_stray(root: Path) -> None:
    misplaced = root / "runs" / "D" / "s01_cellar" / "long01_border_road" / "1001.jsonl"
    misplaced.parent.mkdir(parents=True)
    misplaced.write_bytes(_log(root, "D").read_bytes())

    report = _check(root)
    assert report.ok
    assert report.strays == [misplaced.as_posix()]


# --- crashes -----------------------------------------------------------------


def test_a_log_with_no_ledger_line_is_a_gap(root: Path) -> None:
    _write_ledger(root, [x for x in _ledger_lines(root) if x["run_id"] != _rid("D")])

    report = _check(root)
    assert report.gaps == [_rid("D")]
    [error] = _run(report, "D").errors
    assert error.startswith("no ledger line")


def test_a_missing_ledger_makes_every_run_a_gap(root: Path) -> None:
    _ledger(root).unlink()
    assert _check(root).gaps == [_rid(c) for c in CONDITIONS]


def test_a_last_attempt_that_did_not_complete_is_a_gap(root: Path) -> None:
    lines = _ledger_lines(root)
    crash = {**lines[1], "outcome": "error", "error": "KeyError: 'hp'\nTraceback ..."}
    _write_ledger(root, [*lines, crash])

    report = _check(root)
    assert report.gaps == [lines[1]["run_id"]]
    run = next(r for r in report.runs if r.run_id == lines[1]["run_id"])
    assert "last ledger attempt is error: KeyError: 'hp'" in run.errors


def test_failed_attempts_before_a_complete_one_are_history_not_gaps(root: Path) -> None:
    lines = _ledger_lines(root)
    first = {**lines[2], "outcome": "tainted", "attempt": 1, "transport_retries": 1}
    model = {**lines[2], "outcome": "model_error", "attempt": 2, "error": "ModelTimeout: 120 s"}
    complete = {**lines[2], "attempt": 3}
    _write_ledger(root, [*lines[:2], first, model, complete, *lines[3:]])

    report = _check(root)
    assert report.ok
    run = next(r for r in report.runs if r.run_id == lines[2]["run_id"])
    assert run.history == ["attempt 1 tainted", "attempt 2 model_error: ModelTimeout: 120 s"]


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        ({"transport_retries": 2}, "the complete attempt had 2 transport retries"),
        ({"records": 3}, f"the ledger counts 3 records, the log holds {INPUTS}"),
        ({"seed": 2001}, "the ledger's complete line has seed 2001"),
    ],
)
def test_a_complete_line_that_does_not_match_the_log_is_a_gap(
    root: Path, change: dict, expected: str
) -> None:
    lines = _ledger_lines(root)
    lines[0] = {**lines[0], **change}
    _write_ledger(root, lines)

    report = _check(root)
    assert report.gaps == [lines[0]["run_id"]]
    assert expected in report.runs[0].errors


def test_runs_played_with_two_models_fail_the_check(root: Path) -> None:
    lines = _ledger_lines(root)
    lines[3] = {**lines[3], "model_digest": "sha256:" + "0" * 64}
    _write_ledger(root, lines)

    report = _check(root)
    assert report.gaps == [] and not report.ok
    assert len(report.models) == 2
    assert report.model_errors[0].startswith("runs were played with more than one model")


def test_leftovers_in_pending_and_aborted_are_listed(root: Path) -> None:
    pending = log_path(root / "runs" / "pending", "C", CELLAR.scenario_id, SEED)
    aborted = log_path(root / "runs" / "aborted", "D", CELLAR.scenario_id, SEED)
    aborted = aborted.with_name(f"{SEED}.20261109T101500Z.jsonl")
    for path in (pending, aborted):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")

    report = _check(root)
    assert report.pending == [pending.as_posix()]
    assert report.aborted == [aborted.as_posix()]
    assert report.ok


def test_empty_narrations_are_listed_as_data_not_gaps(root: Path) -> None:
    path = _log(root, "D")
    records = read_log(path)
    records[3]["narration"] = ""
    for call in records[3]["model_calls"]:
        if call["phase"] == "narration":
            call["raw_output"] = ""
    path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")

    report = _check(root)
    assert report.ok
    assert report.empty_narrations == [f"{_rid('D')} input 3"]


# --- seeds -------------------------------------------------------------------


def test_a_cell_missing_one_of_the_manifest_seeds_is_reported(root: Path) -> None:
    manifest = _manifest(root, seeds=(SEED, SEED + 1))

    report = integrity.check(root / "runs", manifest, _ledger(root))
    assert report.seeds == [SEED, SEED + 1]
    assert report.seed_errors == [
        f"{c} s01_cellar: no log for seeds [{SEED + 1}]" for c in CONDITIONS
    ]
    assert report.gaps == [_rid(c, SEED + 1) for c in CONDITIONS]


def test_the_main_grid_seeds_are_used_by_no_other_experiment() -> None:
    def seeds(name: str) -> set[int]:
        doc = json.loads((ROOT / "experiments" / name).read_text(encoding="utf-8"))
        return set(doc["seeds"]) if "seeds" in doc else {r["seed"] for r in doc["runs"]}

    main = seeds("main_grid.json")
    assert main == {2001, 2002, 2003}
    assert main.isdisjoint(seeds("smoke_grid.json"))
    assert main.isdisjoint(seeds("dry_run.json"))


# --- checksums and the command line ------------------------------------------


def _cli(root: Path, *extra: str) -> list[str]:
    args = ["--runs", str(root / "runs"), "--manifest", str(root / "manifest.json")]
    return [*args, "--ledger", str(_ledger(root)), *extra]


def test_the_command_line_writes_checksums_a_copy_can_be_checked_against(root: Path) -> None:
    sums = root / "main_grid.sha256"
    out = root / "results" / "integrity.json"
    first = CliRunner().invoke(
        integrity.app, _cli(root, "--write-checksums", str(sums), "--out", str(out))
    )
    assert first.exit_code == 0, first.output
    assert "Gaps: none" in first.output
    lines = sums.read_bytes().decode("utf-8").split("\n")
    assert lines[-1] == "" and len(lines) == 5 and b"\r" not in sums.read_bytes()
    assert lines[0].endswith(_log(root, "A").as_posix())
    assert json.loads(out.read_text(encoding="utf-8"))["ok"] is True

    same = CliRunner().invoke(integrity.app, _cli(root, "--checksums", str(sums)))
    assert same.exit_code == 0, same.output
    assert "match" in same.output

    path = _log(root, "C")
    # The same records, written with other separators: still a valid log, but
    # not the bytes that were checked.
    records = read_log(path)
    path.write_text(
        "".join(json.dumps(r, indent=1).replace("\n", "") + "\n" for r in records), encoding="utf-8"
    )
    assert _check(root).ok
    changed = CliRunner().invoke(integrity.app, _cli(root, "--checksums", str(sums)))
    assert changed.exit_code == 1
    assert f"{path.as_posix()}: sha256 differs from the checksum file" in changed.output


def test_the_command_line_exits_1_and_names_the_gaps(root: Path) -> None:
    _log(root, "B").unlink()
    result = CliRunner().invoke(integrity.app, _cli(root))
    assert result.exit_code == 1
    assert f"Gaps: {_rid('B')}" in result.output


def test_a_copy_in_another_folder_is_checked_against_the_same_checksums(
    root: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    sums = root / "main_grid.sha256"
    written = CliRunner().invoke(integrity.app, _cli(root, "--write-checksums", str(sums)))
    assert written.exit_code == 0, written.output

    copy = tmp_path_factory.mktemp("download") / "drive_check" / "runs"
    for path in (root / "runs").rglob("*.jsonl"):
        target = copy / path.relative_to(root / "runs")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
    args = ["--runs", str(copy), "--manifest", str(root / "manifest.json")]
    args += ["--ledger", str(_ledger(root)), "--checksums", str(sums)]

    checked = CliRunner().invoke(integrity.app, args)
    assert checked.exit_code == 0, checked.output
    assert "match" in checked.output

    _log(root, "A").unlink()  # the original is gone; the copy is checked on its own
    (copy / "B" / "s01_cellar" / f"{SEED}.jsonl").unlink()
    missing = CliRunner().invoke(integrity.app, args)
    assert missing.exit_code == 1
    assert f"{(copy / 'B' / 's01_cellar').as_posix()}/{SEED}.jsonl: no such log" in missing.output
