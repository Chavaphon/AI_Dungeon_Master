"""The how-to-play guide (WBS 13.3, #256): `HOW_TO_PLAY.md` covers #256's
eight topics in order, in the beginner vocabulary with no jargon left
unexplained, never calls the game 5e, and stays in step with the game's
commands and its request to rephrase. `python -m adm.cli guide` prints it, and
`/help` is its short version and points to it.

Run: pytest tests/play/test_guide.py -v
"""

import io
import re

import pytest
from rich.console import Console
from typer.testing import CliRunner

from adm import cli
from adm.orchestration.loop import REPHRASE
from adm.play.commands import COMMANDS, QUIT, run_command
from adm.play.guide import GUIDE, POINTER, guide, guide_text
from adm.play.vocabulary import JARGON, TERMS, Mode

TEXT = guide_text()

# #256's scope, in its order.
SECTIONS = [
    "What is this game?",
    "How to play",
    "Fights",
    "Health",
    "The three skills",
    "The two spells",
    "When the game asks you to rephrase",
    "Commands",
]


def _headings() -> list[str]:
    return re.findall(r"^## \d+\. (.+)$", TEXT, flags=re.MULTILINE)


def _section(title: str) -> str:
    start = TEXT.index(f". {title}\n")
    end = TEXT.find("\n## ", start)
    return TEXT[start : end if end != -1 else None]


def _render(renderable: object) -> str:
    console = Console(width=100, record=True, file=io.StringIO())
    console.print(renderable)
    return " ".join(console.export_text().split())


def test_the_guide_is_at_the_repository_root() -> None:
    assert GUIDE.name == "HOW_TO_PLAY.md" and GUIDE.parent == cli.RUNS.resolve().parent


def test_the_sections_follow_the_issue_in_order() -> None:
    assert _headings() == SECTIONS


def test_how_to_play_has_eight_to_ten_example_phrases_covering_every_kind() -> None:
    examples = re.findall(r"^- `(I [^`]+)`$", _section("How to play"), flags=re.MULTILINE)
    assert 8 <= len(examples) <= 10
    joined = " | ".join(examples).lower()
    kinds = {
        "looking around": "look around",
        "attacking": "attack",
        "Fire Bolt": "fire bolt",
        "Cure Wounds": "cure wounds",
        "dodging": "dodge",
        "sneaking": "sneak",
        "lifting something": "roll the heavy barrel",
        "picking up an item": "pick up",
        "talking to someone": "tell the keeper",
    }
    missing = [kind for kind, words in kinds.items() if words not in joined]
    assert not missing, missing


def test_the_guide_has_no_jargon() -> None:
    """Every term is a beginner word (WBS 13.2): no dice notation, signed
    modifier or AC, DC or HP anywhere, so nothing is left unexplained."""
    assert not JARGON.findall(TEXT)
    for term in ("initiative", "cantrip", "spell slot", "NPC", "hit points"):
        assert term.lower() not in TEXT.lower(), term


@pytest.mark.parametrize("word", ["role-playing game", "Dungeon Master", "skill check"])
def test_a_game_word_is_explained_in_the_first_section_that_uses_it(word: str) -> None:
    """Past the opening lines, the first section to use a game word defines
    it, in bold."""
    body = TEXT[TEXT.index("\n## 1. ") :]
    first = body.index(word)
    section = body[body.rfind("\n## ", 0, first) : body.find("\n## ", first)]
    assert f"**{word}**" in section


def test_the_beginner_words_are_the_vocabulary_s() -> None:
    for term in ("HP", "unconscious", "spell slot", "DC", "initiative"):
        assert TERMS[term] in TEXT, TERMS[term]


def test_the_game_is_inspired_by_never_5e() -> None:
    assert "inspired by" in TEXT
    assert not re.search(r"5e|5th edition|fifth edition|compatible", TEXT, flags=re.IGNORECASE)


def test_the_rephrase_section_quotes_the_game() -> None:
    assert f"> {REPHRASE}" in _section("When the game asks you to rephrase")


def test_every_command_is_in_the_guide() -> None:
    section = _section("Commands")
    for name in [*COMMANDS, *QUIT]:
        assert f"`{name}`" in section, name


def test_the_guide_renders_with_rich() -> None:
    out = _render(guide())
    assert "How to Play" in out and "##" not in out


def test_guide_prints_the_guide_without_a_model(monkeypatch: pytest.MonkeyPatch) -> None:
    def never(config: object) -> None:
        raise AssertionError("the guide needs no model")

    monkeypatch.setattr(cli, "connect", never)
    result = CliRunner().invoke(cli.app, ["guide"])
    assert result.exit_code == 0, result.output
    out = " ".join(result.output.split())
    assert all(title in out for title in SECTIONS)


@pytest.mark.parametrize("mode", list(Mode))
def test_help_is_the_short_version_and_points_to_the_guide(mode: Mode) -> None:
    from adm.engine.scenario import initial_state, load_scenario

    state = initial_state(load_scenario(GUIDE.parent / "scenarios" / "s01_cellar.json"), 1)
    out = _render(run_command("/help", state, mode).renderable)
    assert POINTER in out
    assert not JARGON.findall(out)
    assert len(out) < len(" ".join(TEXT.split())) / 3, "a short version"
