"""Text command-line client (WBS 6.10, 6.11, 7.4): a person can play a session
end to end (the done-when of #72). `play` shows the scenario's opening, takes
one input per turn, shows the narration or the request to rephrase, and stops on
`/quit` or end of input with every turn in the audit log. `run` is the one
entry point for every condition (the done-when of #78). `play` is in beginner
mode unless `--mode veteran` is given, and both modes log the same session
(WBS 13.2, #255). Beginner mode shows action hints that leave the session
unchanged (WBS 13.7, #257). The scenario briefing comes first, waits for
Enter and makes no model call and no audit record (WBS 13.4, #252). The status
panel after each turn leaves the session unchanged, and `--no-color` shows no
escape codes or box drawing (WBS 13.5, #253).

No test calls a model: `connect` is replaced by a fake client.

Run: pytest tests/test_cli.py -v
"""

import json
import re
from collections.abc import Sequence
from contextlib import nullcontext
from dataclasses import dataclass, replace
from pathlib import Path

import pytest
from rich.text import Text
from typer.testing import CliRunner

from adm import cli
from adm.engine.audit import AuditLog, log_path, read_log, record_errors
from adm.engine.replay import log_differences
from adm.engine.scenario import Scenario, ScriptedInput, initial_state, load_scenario
from adm.engine.state import GameState
from adm.orchestration.client import Message, ModelReply, ModelUnavailable, Phase
from adm.orchestration.loop import REPHRASE
from adm.play.briefing import AI_LABEL, BEGIN
from adm.play.commands import HINT, UNKNOWN
from adm.play.hints import TITLE
from adm.play.results import result_lines
from adm.play.screen import THINKING
from adm.play.vocabulary import JARGON, Mode

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
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    client: FakeClient,
    keys: str,
    *extra: str,
    begin: str = "\n",
) -> tuple[int, str]:
    """Play `keys` after `begin`, the Enter that starts the session after the
    briefing."""
    monkeypatch.setattr(cli, "connect", lambda config: nullcontext(client))
    args = ["play", "--scenario", str(SCENARIO_PATH), "--seed", str(SEED), "--runs", str(tmp_path)]
    result = CliRunner().invoke(cli.app, [*args, *extra], input=begin + keys)
    # Rich wraps at the terminal width and draws panel borders; compare the words.
    return result.exit_code, " ".join(result.output.replace("│", " ").split())


def _records(tmp_path: Path) -> list[dict]:
    return read_log(log_path(tmp_path, "D", SCENARIO.scenario_id, SEED))


def _initial() -> GameState:
    return initial_state(SCENARIO, SEED)


def test_a_session_is_played_end_to_end(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    garbled = "Lyra looks."
    client = FakeClient(LOOK, garbled, garbled, garbled)
    keys = "I look around the cellar\n\n  \nmumble\n/quit\nnever sent\n"
    code, output = _play(monkeypatch, tmp_path, client, keys)

    assert code == 0, output
    assert f"{SCENARIO.display_name} {AI_LABEL}" in output, "the title carries the AI label"
    assert SCENARIO.opening_narration in output
    assert output.index(SCENARIO.opening_narration) < output.index(HINT), "/help is pointed to"
    assert NARRATION in output, "narration is printed as written, brackets included"
    line = result_lines(_records(tmp_path)[0], _initial(), Mode.BEGINNER)[0]
    assert line.startswith("Your perception check:"), "beginner mode by default"
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


# --- the briefing (WBS 13.4) -------------------------------------------------------


def test_the_briefing_comes_first_and_waits_for_enter(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The acceptance of #252: the briefing makes no model call and no audit
    record, and what is typed at its prompt is not an input."""
    client = RecordingClient(LOOK)
    code, output = _play(monkeypatch, tmp_path, client, "/quit\n", begin="I attack the rats\n")
    assert code == 0, output

    assert client.calls == [], "no model call"
    assert not log_path(tmp_path, "D", SCENARIO.scenario_id, SEED).exists(), "no audit record"
    for shown in ("You are...", "You carry...", "Your quests", "People you know", "Places"):
        assert shown in output
    assert "The Keeper: unfriendly towards you" in output
    assert "giant rat" not in output, "the rats are not named before the fight"
    assert output.index(SCENARIO.opening_narration) < output.index("You are...")
    assert output.index("Places") < output.index(BEGIN.strip()) < output.index(HINT)
    assert "0 turns (0 failed)" in output


def test_end_of_input_at_the_briefing_ends_the_session(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    client = RecordingClient(LOOK)
    code, output = _play(monkeypatch, tmp_path, client, "", begin="")
    assert code == 0, output
    assert client.calls == [] and HINT not in output
    assert "0 turns (0 failed)" in output


def test_veteran_mode_briefs_with_the_numbers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    code, output = _play(monkeypatch, tmp_path, FakeClient(), "/quit\n", "--mode", "veteran")
    assert code == 0, output
    assert "Armour class: 14" in output and "(damage 1d6+3)" in output


# --- the play screen (WBS 13.5) ------------------------------------------------------

GARBLED = "Lyra looks."


def _calls() -> tuple[str, ...]:
    """The model replies to `_screen_keys`: four calls, then three garbled."""
    return (LOOK, LOOK, LOOK, ATTACK, GARBLED, GARBLED, GARBLED)


COMMANDS = ["/help", "/status", "/inventory", "/quests", "/rules", "/glossary", "/bogus"]
# Box drawing (U+2500-U+257F) and block elements (U+2580-U+259F), the health bar's.
BOXES = re.compile("[─-▟]")


def _screen_keys() -> str:
    """Four scripted inputs through the start of s01's fight, a failed turn,
    and every command."""
    inputs = [i.text for i in SCENARIO.scripted_inputs[:4]]
    return "\n".join([*inputs, "mumble", *COMMANDS]) + "\n"


def test_the_status_panel_leaves_the_session_unchanged(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The acceptance of #253: the same session with the status panel on and
    off makes the same model calls and a log identical but for timings."""
    on, off = RecordingClient(*_calls()), RecordingClient(*_calls())
    code, shown = _play(monkeypatch, tmp_path / "on", on, _screen_keys())
    assert code == 0, shown
    monkeypatch.setattr(cli, "status_panel", lambda state, mode, bar: Text())
    code, hidden = _play(monkeypatch, tmp_path / "off", off, _screen_keys())
    assert code == 0, hidden

    assert "Fight, round " in shown and "Fight, round " not in hidden
    assert on.calls == off.calls, "the panel never reaches the model"
    first, second = _records(tmp_path / "on"), _records(tmp_path / "off")
    assert len(first) == len(second) == 5
    assert log_differences(first, second) == []


def test_the_status_panel_follows_each_turn(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    keys = "\n".join(i.text for i in SCENARIO.scripted_inputs[:2]) + "\n"
    code, output = _play(monkeypatch, tmp_path, FakeClient(LOOK, LOOK), keys)
    assert code == 0, output
    assert output.count("Lyra: healthy") == 2, "once after each turn"
    assert output.index(NARRATION) < output.index("Lyra: healthy")


def _raw_play(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, client: FakeClient, *extra: str
) -> str:
    """The session's output as the terminal gets it, on a forced terminal so
    that any style is an escape code."""
    monkeypatch.setenv("FORCE_COLOR", "1")
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setattr(cli, "connect", lambda config: nullcontext(client))
    args = ["play", "--scenario", str(SCENARIO_PATH), "--seed", str(SEED), "--runs", str(tmp_path)]
    result = CliRunner().invoke(cli.app, [*args, *extra], input="\n" + _screen_keys())
    assert result.exit_code == 0, result.output
    return result.output


def test_no_color_has_no_escape_codes_and_no_box_drawing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The acceptance of #253: a whole session, the briefing, a fight, a
    failed turn and every command, in both modes."""
    styled = _raw_play(monkeypatch, tmp_path / "styled", FakeClient(*_calls()))
    assert "\x1b" in styled and BOXES.search(styled), "the check would catch them"
    for mode in Mode:
        plain = _raw_play(
            monkeypatch,
            tmp_path / mode.value,
            FakeClient(*_calls()),
            "--no-color",
            "--mode",
            mode.value,
        )
        assert "\x1b" not in plain
        assert BOXES.search(plain) is None, BOXES.search(plain)
        for shown in ("You are...", "Fight, round ", "Glossary", REPHRASE, THINKING):
            assert shown in plain
    first = _records(tmp_path / "styled")
    assert log_differences(first, _records(tmp_path / "beginner")) == [], "the same log"


# --- slash commands (WBS 13.1) ---------------------------------------------------

ATTACK = json.dumps(
    {
        "tool": "attack",
        "arguments": {
            "attacker_id": "pc_lyra",
            "target_id": "npc_rat_01",
            "weapon_id": "item_short_sword",
        },
    }
)


class RecordingClient(FakeClient):
    """A FakeClient that keeps every request it was sent."""

    def __init__(self, *toolcalls: str) -> None:
        super().__init__(*toolcalls)
        self.calls: list[tuple[Phase, list[Message], int]] = []

    def chat(self, messages: Sequence[Message], *, phase: Phase, seed: int) -> ModelReply:
        self.calls.append((phase, list(messages), seed))
        return super().chat(messages, phase=phase, seed=seed)


def test_slash_commands_never_reach_the_model_or_the_log(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The acceptance of #251: commands mixed into a session leave its model
    calls and its audit log exactly as without them, timings aside, and do not
    count toward the encounter's `before_input`."""
    inputs = [i.text for i in SCENARIO.scripted_inputs[:4]]
    assert SCENARIO.encounters[0].before_input == 3, "the fight starts on the 4th input"
    toolcalls = (LOOK, LOOK, LOOK, ATTACK)
    commands = ["/help", "/status", "/inventory", "/quests", "/rules", "/glossary", "/bogus"]
    mixed = [*commands[:3], inputs[0], inputs[1], *commands[3:], inputs[2], "/STATUS", inputs[3]]

    plain, with_commands = RecordingClient(*toolcalls), RecordingClient(*toolcalls)
    code, _ = _play(monkeypatch, tmp_path / "plain", plain, "\n".join(inputs) + "\n")
    assert code == 0
    keys = "\n".join([*mixed, "/status", "/quit", "never sent"]) + "\n"
    code, output = _play(monkeypatch, tmp_path / "mixed", with_commands, keys)
    assert code == 0, output

    assert with_commands.calls == plain.calls, "the same model calls, in the same order"
    first, second = _records(tmp_path / "plain"), _records(tmp_path / "mixed")
    assert len(first) == len(second) == 4
    assert log_differences(first, second) == []
    starts = [[s["step"] for s in r["engine_steps"]].count("encounter_start") for r in second]
    assert starts == [0, 0, 0, 1], "commands do not count toward before_input"
    assert UNKNOWN in output
    assert "Turn order:" in output, "/status after the fight starts shows it"
    assert with_commands.toolcalls == [], "nothing after /quit is sent"


# --- beginner and veteran modes (WBS 13.2) ----------------------------------------


def test_beginner_and_veteran_log_the_same_session(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The acceptance of #255: one session played in each mode makes the same
    model calls and a log identical but for timings; the mode is never logged."""
    inputs = [i.text for i in SCENARIO.scripted_inputs[:4]]
    toolcalls = (LOOK, LOOK, LOOK, ATTACK)
    keys = "\n".join([*inputs, "/status", "/rules", "/glossary"]) + "\n"
    beginner, veteran = RecordingClient(*toolcalls), RecordingClient(*toolcalls)
    code, plain = _play(monkeypatch, tmp_path / "beginner", beginner, keys)
    assert code == 0, plain
    code, numbers = _play(monkeypatch, tmp_path / "veteran", veteran, keys, "--mode", "veteran")
    assert code == 0, numbers

    assert beginner.calls == veteran.calls, "the model never sees the mode"
    first, second = _records(tmp_path / "beginner"), _records(tmp_path / "veteran")
    assert len(first) == len(second) == 4
    assert log_differences(first, second) == []
    for folder in ("beginner", "veteran"):
        text = log_path(tmp_path / folder, "D", SCENARIO.scenario_id, SEED).read_text("utf-8")
        assert "beginner" not in text and "veteran" not in text
    assert "vs AC" in numbers and "vs DC 12" in numbers, "veteran shows the rolls"
    assert plain != numbers


def test_beginner_output_has_no_jargon(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The acceptance of #255: a beginner session, through the start of a fight
    and every command, shows no dice notation and no AC, DC or HP."""
    inputs = [i.text for i in SCENARIO.scripted_inputs[:4]]
    commands = ["/help", "/status", "/inventory", "/quests", "/rules", "/glossary", "/bogus"]
    keys = "\n".join([*commands, *inputs, *commands]) + "\n"
    code, output = _play(monkeypatch, tmp_path, FakeClient(LOOK, LOOK, LOOK, ATTACK), keys)
    assert code == 0, output
    assert "Turn order:" in output, "the fight started"
    assert JARGON.search(output) is None, JARGON.search(output)


# --- action hints (WBS 13.7) ------------------------------------------------------


def test_hints_leave_the_session_unchanged(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The acceptance of #257: a beginner session with hints on and the same
    session with hints off make the same model calls and a log identical but
    for timings, so its state hashes and rolls are the same."""
    inputs = [i.text for i in SCENARIO.scripted_inputs[:4]]
    toolcalls = (LOOK, LOOK, LOOK, ATTACK)
    keys = "\n".join([*inputs, "/status"]) + "\n"
    on, off = RecordingClient(*toolcalls), RecordingClient(*toolcalls)
    code, shown = _play(monkeypatch, tmp_path / "on", on, keys)
    assert code == 0, shown
    monkeypatch.setattr(cli, "hint_block", lambda state: None)
    code, hidden = _play(monkeypatch, tmp_path / "off", off, keys)
    assert code == 0, hidden

    assert TITLE in shown and TITLE not in hidden
    assert on.calls == off.calls, "hints never reach the model"
    first, second = _records(tmp_path / "on"), _records(tmp_path / "off")
    assert len(first) == len(second) == 4
    assert log_differences(first, second) == []
    assert [r["state_after_hash"] for r in first] == [r["state_after_hash"] for r in second]
    assert [r["rolls"] for r in first] == [r["rolls"] for r in second]


def test_beginner_mode_shows_hints_before_each_input(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    inputs = [i.text for i in SCENARIO.scripted_inputs[:4]]
    keys = "\n".join([inputs[0], "/status", *inputs[1:]]) + "\n"
    code, output = _play(monkeypatch, tmp_path, FakeClient(LOOK, LOOK, LOOK, ATTACK), keys)
    assert code == 0, output

    assert output.index(HINT) < output.index(TITLE), "the first hints come before input 1"
    assert output.count(TITLE) == 5, "at the start and after each of the 4 turns, not /status"
    assert "with your short sword" in output, "a fight hint once the fight is on"


def test_veteran_mode_shows_no_hints(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    keys = SCENARIO.scripted_inputs[0].text + "\n"
    code, output = _play(monkeypatch, tmp_path, FakeClient(LOOK), keys, "--mode", "veteran")
    assert code == 0, output
    assert TITLE not in output


def test_an_unknown_mode_is_refused(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cli, "connect", _never_connect)
    code, output = _play(monkeypatch, tmp_path, FakeClient(), "", "--mode", "expert")
    assert code == 2 and "expert" in output
    assert not any(tmp_path.iterdir())


def test_ctrl_c_at_the_prompt_ends_the_session_cleanly(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    typed = iter(["", "I look around the cellar"])

    def keyboard(self: object, prompt: str = "", **kwargs: object) -> str:
        try:
            return next(typed)
        except StopIteration:
            raise KeyboardInterrupt from None

    monkeypatch.setattr(cli.Console, "input", keyboard)
    code, output = _play(monkeypatch, tmp_path, FakeClient(LOOK), "")
    assert code == 0, output
    assert "Traceback" not in output
    records = _records(tmp_path)
    assert len(records) == 1 and all(record_errors(r) == [] for r in records)
    assert "1 turns (0 failed)" in output


class InterruptedClient(FakeClient):
    """Ctrl+C arrives during the second narration call."""

    narrations = 0

    def chat(self, messages: Sequence[Message], *, phase: Phase, seed: int) -> ModelReply:
        if phase == "narration":
            self.narrations += 1
            if self.narrations == 2:
                raise KeyboardInterrupt
        return super().chat(messages, phase=phase, seed=seed)


def test_ctrl_c_mid_turn_keeps_a_valid_log_of_the_finished_turns(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    keys = "I look around the cellar\nI look again\nnever played\n"
    code, output = _play(monkeypatch, tmp_path, InterruptedClient(LOOK, LOOK, LOOK), keys)
    assert code == 0, output
    assert "Traceback" not in output
    records = _records(tmp_path)
    assert [r["player_input"] for r in records] == ["I look around the cellar"]
    assert all(record_errors(r) == [] for r in records)


def test_exit_still_ends_the_session(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client = FakeClient(LOOK)
    code, output = _play(monkeypatch, tmp_path, client, "/exit\nI look around\n")
    assert code == 0, output
    assert (
        client.toolcalls == [LOOK]
        and not log_path(tmp_path, "D", SCENARIO.scenario_id, SEED).exists()
    )


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


def test_result_lines_are_display_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _play(monkeypatch, tmp_path, FakeClient(LOOK), "I look around\n")
    text = log_path(tmp_path, "D", SCENARIO.scenario_id, SEED).read_text("utf-8")
    for mode in Mode:
        line = result_lines(_records(tmp_path)[0], _initial(), mode)[0]
        assert line not in text


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
