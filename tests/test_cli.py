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
from dataclasses import dataclass
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
    assert SCENARIO.display_name in output
    assert SCENARIO.opening_narration in output
    assert NARRATION in output, "narration is printed as written, brackets included"
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
