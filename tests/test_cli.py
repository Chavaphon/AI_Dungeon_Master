"""Text command-line client (WBS 6.10): a person can play a session end to end
(the done-when of #72). `play` shows the scenario's opening, takes one input
per turn, shows the narration or the request to rephrase, and stops on `/quit`
or end of input with every turn in the audit log.

No test calls a model: `connect` is replaced by a fake client.

Run: pytest tests/test_cli.py -v
"""

import json
from collections.abc import Sequence
from contextlib import nullcontext
from pathlib import Path

import pytest
from typer.testing import CliRunner

from adm import cli
from adm.engine.audit import log_path, read_log
from adm.engine.scenario import load_scenario
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


def test_run_refuses_a_condition_that_is_not_wired(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    code, output = _run(monkeypatch, tmp_path, LookingClient(), "--condition", "A")
    assert code == 2
    assert "not wired yet" in output
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
