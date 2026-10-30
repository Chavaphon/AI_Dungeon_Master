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
