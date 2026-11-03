"""Text command-line client (WBS 6.10, 6.11, 7.4): a person can play a session
end to end (the done-when of #72). `play` shows the scenario's opening, takes
one input per turn, shows the narration or the request to rephrase, and stops on
`/quit` or end of input with every turn in the audit log. `run` is the one
entry point for every condition (the done-when of #78).

No test calls a model: `connect` is replaced by a fake client.

Run: pytest tests/test_cli.py -v
"""

import json
from collections.abc import Sequence
from contextlib import nullcontext
from dataclasses import dataclass, replace
from pathlib import Path

import pytest
from typer.testing import CliRunner

from adm import cli
from adm.engine.audit import AuditLog, log_path, read_log
from adm.engine.scenario import Scenario, ScriptedInput, load_scenario
from adm.orchestration.client import Message, ModelReply, ModelUnavailable, Phase
from adm.orchestration.loop import REPHRASE

ROOT = Path(__file__).resolve().parents[1]
SCENARIO_PATH = ROOT / "scenarios" / "s01_cellar.json"
SCENARIO = load_scenario(SCENARIO_PATH)
SEED = 12345

LOOK = json.dumps(
    {"tool": "skill_check", "arguments": {"actor_id": "pc_lyra", "skill": "perception", "dc": 12}}
)
NARRATION = "Water laps at the barrels as you peer into [the dark]."


class FakeClient:
    """Answers toolcalls from `toolcalls` in order and every narration with NARRATION."""

    def __init__(self, *toolcalls: str) -> None:
        self.toolcalls = list(toolcalls)

    def chat(self, messages: Sequence[Message], *, phase: Phase, seed: int) -> ModelReply:
        reply = NARRATION if phase == "narration" else self.toolcalls.pop(0)
        return ModelReply(reply, 3000, 40, 0, 0, "stop", 0)


def _play(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, client: FakeClient, keys: str
) -> tuple[int, str]:
    monkeypatch.setattr(cli, "connect", lambda config: nullcontext(client))
    args = ["play", "--scenario", str(SCENARIO_PATH), "--seed", str(SEED), "--runs", str(tmp_path)]
    result = CliRunner().invoke(cli.app, args, input=keys)
    # Rich wraps at the terminal width; compare the words.
    return result.exit_code, " ".join(result.output.split())


def _records(tmp_path: Path) -> list[dict]:
    return read_log(log_path(tmp_path, "D", SCENARIO.scenario_id, SEED))


def test_a_session_is_played_end_to_end(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    garbled = "Lyra looks."
    client = FakeClient(LOOK, garbled, garbled, garbled)
    keys = "I look around the cellar\n\n  \nmumble\n/quit\nnever sent\n"
    code, output = _play(monkeypatch, tmp_path, client, keys)

    assert code == 0, output
    assert f"{SCENARIO.display_name} {cli.AI_LABEL}" in output, "the title carries the AI label"
    assert SCENARIO.opening_narration in output
    assert NARRATION in output, "narration is printed as written, brackets included"
    line = cli.result_lines(_records(tmp_path)[0])[0]
    assert line.startswith("Lyra perception check:") and "vs DC 12" in line
    assert output.index(line) < output.index(NARRATION), "the result line comes first"
    assert REPHRASE in output
    records = _records(tmp_path)
    assert [r["player_input"] for r in records] == ["I look around the cellar", "mumble"]
    assert [r["turn_failure"] for r in records] == [None, "unparseable"]
    assert "2 turns (1 failed)" in output
    assert client.toolcalls == [], "blank lines are not sent; nothing after /quit is"


def test_end_of_input_ends_the_session(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, output = _play(monkeypatch, tmp_path, FakeClient(LOOK), "I look around\n")
    assert code == 0, output
    assert len(_records(tmp_path)) == 1


def test_an_existing_run_is_refused_before_the_model_loads(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = log_path(tmp_path, "D", SCENARIO.scenario_id, SEED)
    path.parent.mkdir(parents=True)
    path.write_text("", encoding="utf-8")

    def connect(config: object) -> None:
        raise AssertionError("the model must not be loaded for a run that exists")

    monkeypatch.setattr(cli, "connect", connect)
    args = ["play", "--scenario", str(SCENARIO_PATH), "--seed", str(SEED), "--runs", str(tmp_path)]
    result = CliRunner().invoke(cli.app, args, input="I look around\n")
    assert result.exit_code == 1
    assert "already exists" in result.output
    assert path.read_text(encoding="utf-8") == ""


def test_an_unavailable_model_ends_the_session(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def connect(config: object) -> None:
        raise ModelUnavailable("Ollama is not running")

    monkeypatch.setattr(cli, "connect", connect)
    args = ["play", "--scenario", str(SCENARIO_PATH), "--seed", str(SEED), "--runs", str(tmp_path)]
    result = CliRunner().invoke(cli.app, args, input="I look around\n")
    assert result.exit_code == 1
    assert "Ollama is not running" in result.output


# --- run: scripted inputs, unattended (WBS 6.11) ------------------------------


class LookingClient(FakeClient):
    """Always looks around: every scripted input gets a valid call. A 26-input
    run also regenerates the rolling summary."""

    def chat(self, messages: Sequence[Message], *, phase: Phase, seed: int) -> ModelReply:
        if phase == "summary":
            return ModelReply("Lyra searched the cellar.", 3000, 40, 0, 0, "stop", 0)
        if phase == "toolcall" and not self.toolcalls:
            self.toolcalls.append(LOOK)
        return super().chat(messages, phase=phase, seed=seed)


def _run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, client: FakeClient, *extra: str
) -> tuple[int, str]:
    monkeypatch.setattr(cli, "connect", lambda config: nullcontext(client))
    args = ["run", "--scenario", str(SCENARIO_PATH), "--seed", str(SEED), "--runs", str(tmp_path)]
    result = CliRunner().invoke(cli.app, [*args, *extra])
    return result.exit_code, " ".join(result.output.split())


def test_run_plays_every_scripted_input(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, output = _run(monkeypatch, tmp_path, LookingClient(), "--condition", "D")
    assert code == 0, output
    records = _records(tmp_path)
    total = len(SCENARIO.scripted_inputs)
    assert [r["input_index"] for r in records] == list(range(total))
    assert [r["player_input"] for r in records] == [i.text for i in SCENARIO.scripted_inputs]
    assert f"input {total}/{total}" in output
    assert f"{total} turns" in output


def _never_connect(config: object) -> None:
    raise AssertionError("the model must not be loaded for a refused condition")


@pytest.mark.parametrize("condition", ["A", "B", "C"])
def test_run_refuses_a_condition_that_is_not_wired(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, condition: str
) -> None:
    monkeypatch.setattr(cli, "HARNESSES", {"D": cli.HARNESSES["D"]})
    monkeypatch.setattr(cli, "connect", _never_connect)
    args = ["run", "--scenario", str(SCENARIO_PATH), "--seed", str(SEED), "--runs", str(tmp_path)]
    result = CliRunner().invoke(cli.app, [*args, "--condition", condition])
    assert result.exit_code == 2
    assert "not wired yet" in " ".join(result.output.split())
    assert not any(tmp_path.iterdir()), "no log is created for a refused condition"


def test_run_refuses_an_unknown_condition(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cli, "connect", _never_connect)
    args = ["run", "--scenario", str(SCENARIO_PATH), "--seed", str(SEED), "--runs", str(tmp_path)]
    result = CliRunner().invoke(cli.app, [*args, "--condition", "E"])
    assert result.exit_code == 2
    assert "Unknown condition E" in " ".join(result.output.split())
    assert not any(tmp_path.iterdir())


# --- the common runner (WBS 7.4) ----------------------------------------------


@dataclass(frozen=True)
class _Turn:
    record: dict
    message: str


class FakeHarness:
    """Another condition's harness, registered as A to C will be (WBS 7.1 to
    7.3). It logs nothing; it records what the runner gave it."""

    started: list["FakeHarness"] = []

    def __init__(
        self,
        client: object,
        config: object,
        texts: object,
        scenario: Scenario,
        log: AuditLog,
        *,
        seed: int,
    ) -> None:
        self.client, self.scenario, self.log, self.seed = client, scenario, log, seed
        self.played: list[tuple[str, int | None, ScriptedInput | None]] = []
        FakeHarness.started.append(self)

    def play(
        self,
        player_input: str,
        *,
        input_index: int | None = None,
        scripted: ScriptedInput | None = None,
    ) -> _Turn:
        self.played.append((player_input, input_index, scripted))
        return _Turn({"turn_failure": None}, player_input)


def test_another_condition_runs_through_the_same_entry_point(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The done-when of #78: a harness registered for A is run by `run` exactly
    as condition D is, with no other change to the CLI."""
    FakeHarness.started.clear()
    client = LookingClient()
    monkeypatch.setattr(cli, "HARNESSES", {**cli.HARNESSES, "A": FakeHarness})
    code, output = _run(monkeypatch, tmp_path, client, "--condition", "A")

    assert code == 0, output
    (harness,) = FakeHarness.started
    assert harness.client is client and harness.seed == SEED
    assert harness.log.path == log_path(tmp_path, "A", SCENARIO.scenario_id, SEED)
    inputs = SCENARIO.scripted_inputs
    assert harness.played == [(s.text, i, s) for i, s in enumerate(inputs)]
    total = len(inputs)
    assert f"input {total}/{total}: ok" in output
    assert not log_path(tmp_path, "D", SCENARIO.scenario_id, SEED).exists()


@pytest.mark.parametrize("condition", ["A", "B", "C"])
def test_run_plays_a_narration_only_condition_end_to_end(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, condition: str
) -> None:
    """The done-whens of #77, #79 and #80: conditions A, B and C run a scenario
    end to end through `run`."""
    code, output = _run(monkeypatch, tmp_path, LookingClient(), "--condition", condition)

    assert code == 0, output
    records = read_log(log_path(tmp_path, condition, SCENARIO.scenario_id, SEED))
    total = len(SCENARIO.scripted_inputs)
    assert [r["input_index"] for r in records] == list(range(total))
    assert all(r["condition"] == condition and r["executed_call"] is None for r in records)
    phases = {c["phase"] for r in records for c in r["model_calls"]}
    assert phases == {"narration", "summary"}
    assert f"input {total}/{total}: ok" in output
    assert f"{total} turns (0 failed)" in output
    assert not log_path(tmp_path, "D", SCENARIO.scenario_id, SEED).exists()


def test_run_refuses_an_existing_run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = log_path(tmp_path, "D", SCENARIO.scenario_id, SEED)
    path.parent.mkdir(parents=True)
    path.write_text("", encoding="utf-8")
    code, output = _run(monkeypatch, tmp_path, LookingClient())
    assert code == 1
    assert "already exists" in output


def test_smoke_plays_a_manifest_and_writes_the_summary(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    clients = iter([LookingClient(), LookingClient()])
    monkeypatch.setattr(cli, "connect", lambda config: nullcontext(next(clients)))
    manifest = tmp_path / "grid.json"
    runs = [{"scenario": str(SCENARIO_PATH), "seed": s} for s in (1, 2)]
    manifest.write_text(json.dumps({"runs": runs}), encoding="utf-8")
    out = tmp_path / "results"
    args = ["smoke", "--manifest", str(manifest), "--runs", str(tmp_path), "--out", str(out)]
    result = CliRunner().invoke(cli.app, args)

    output = " ".join(result.output.split())
    assert result.exit_code == 0, output
    assert "2/2 complete: gate G2 NOT met" in output, "the gate needs ten runs"
    (path,) = out.glob("*/summary.json")
    summary = json.loads(path.read_text(encoding="utf-8"))
    assert [r["seed"] for r in summary["runs"]] == [1, 2]
    assert all(r["complete"] for r in summary["runs"])
    assert summary["model_digest"]


# ---------------------------------------------------------------------------
# Result lines (ideation form section 3.vi): one line per mechanical outcome,
# read from the audit record, shown before the narration.
# ---------------------------------------------------------------------------

EXAMPLES = ROOT / "schemas" / "examples"


def _example(name: str) -> dict:
    return json.loads((EXAMPLES / f"{name}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("example", "line"),
    [
        (
            "result_attack",
            "Lyra -> giant rat (short sword): 17 vs AC 12, hit, 7 damage; giant rat 4/11 HP",
        ),
        (
            "result_cast_spell_fire_bolt",
            "Lyra -> giant rat (Fire Bolt): 13 vs AC 12, disadvantage, hit, 7 damage; "
            "giant rat 4/11 HP",
        ),
        (
            "result_cast_spell_cure_wounds",
            "Lyra -> Lyra (Cure Wounds): +6 HP; Lyra 20/20 HP; 1 slot(s) left",
        ),
        ("result_dodge", "Lyra dodges"),
        ("result_skill_check", "Lyra perception check: 12 vs DC 12, success"),
        ("result_modify_inventory", "Lyra -1 torch (now 1)"),
        ("result_update_npc_relationship", "the Keeper: neutral -> friendly"),
        ("result_update_quest", "Quest The Missing Ledger: active -> active (stage 3/3)"),
    ],
)
def test_every_tool_has_a_result_line(example: str, line: str) -> None:
    result = _example(example)
    record = {"engine_steps": [], "validation": [result], "executed_call": {"tool": result["tool"]}}
    assert cli.result_lines(record) == [line]


def test_result_lines_follow_the_order_of_the_turn() -> None:
    record = _example("audit_turn_valid")
    lines = cli.result_lines(record)
    assert len(lines) == 3, "the player's attack, then the two NPC attacks after it"
    assert lines[0].startswith("Lyra -> giant rat (short sword)")
    assert all(line.startswith("giant rat -> Lyra (bite)") for line in lines[1:])


def test_a_failed_turn_has_no_player_result_line() -> None:
    assert cli.result_lines(_example("audit_turn_rejected")) == []


def test_result_lines_are_display_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _play(monkeypatch, tmp_path, FakeClient(LOOK), "I look around\n")
    line = cli.result_lines(_records(tmp_path)[0])[0]
    assert line not in log_path(tmp_path, "D", SCENARIO.scenario_id, SEED).read_text("utf-8")


# --- batch: the main grid, resumable (WBS 7.6) ---------------------------------


class RetryingClient(LookingClient):
    """A LookingClient whose first reply took one transport retry."""

    retried = False

    def chat(self, messages: Sequence[Message], *, phase: Phase, seed: int) -> ModelReply:
        reply = super().chat(messages, phase=phase, seed=seed)
        retries, self.retried = (0 if self.retried else 1), True
        return replace(reply, transport_retries=retries)


def _batch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, clients: Sequence[FakeClient]
) -> tuple[int, str, list[FakeClient]]:
    supply = iter(clients)
    used: list[FakeClient] = []

    def connect(config: object) -> nullcontext:
        used.append(next(supply))
        return nullcontext(used[-1])

    monkeypatch.setattr(cli, "connect", connect)
    manifest = tmp_path / "grid.json"
    doc = {"scenarios": [str(SCENARIO_PATH)], "conditions": ["A", "D"], "seeds": [SEED]}
    manifest.write_text(json.dumps(doc), encoding="utf-8")
    args = ["batch", "--manifest", str(manifest), "--runs", str(tmp_path / "runs")]
    args += ["--ledger", str(tmp_path / "attempts.jsonl")]
    result = CliRunner().invoke(cli.app, args)
    return result.exit_code, " ".join(result.output.split()), used


def test_batch_plays_every_run_and_resumes_with_nothing_to_do(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    code, output, used = _batch(monkeypatch, tmp_path, [LookingClient(), LookingClient()])
    assert code == 0, output
    assert len(used) == 2, "one fresh load per run"
    for condition in ("A", "D"):
        records = read_log(log_path(tmp_path / "runs", condition, SCENARIO.scenario_id, SEED))
        assert [r["input_index"] for r in records] == list(range(len(SCENARIO.scripted_inputs)))
        assert {r["condition"] for r in records} == {condition}
    assert "2/2 runs complete" in output

    code, output, used = _batch(monkeypatch, tmp_path, [])
    assert code == 0, output
    assert used == [], "a complete run is not played again"
    assert "0 attempts played" in output


def test_batch_plays_a_run_again_after_a_transport_retry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    clients = [RetryingClient(), LookingClient(), LookingClient()]
    code, output, used = _batch(monkeypatch, tmp_path, clients)
    assert code == 0, output
    assert len(used) == 3
    ledger = read_log(tmp_path / "attempts.jsonl")
    assert [e["outcome"] for e in ledger] == ["tainted", "complete", "complete"]
    assert ledger[0]["transport_retries"] == 1
    assert ledger[0]["model_digest"]


def test_batch_stops_when_the_server_is_down(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def connect(config: object) -> None:
        raise ModelUnavailable("connection refused")

    monkeypatch.setattr(cli, "connect", connect)
    manifest = tmp_path / "grid.json"
    doc = {"scenarios": [str(SCENARIO_PATH)], "conditions": ["D"], "seeds": [SEED]}
    manifest.write_text(json.dumps(doc), encoding="utf-8")
    args = ["batch", "--manifest", str(manifest), "--runs", str(tmp_path / "runs")]
    result = CliRunner().invoke(cli.app, [*args, "--ledger", str(tmp_path / "l.jsonl")])
    output = " ".join(result.output.split())
    assert result.exit_code == 1, output
    assert "Stopped: ModelUnavailable: connection refused" in output
    assert "0/1 runs complete" in output
