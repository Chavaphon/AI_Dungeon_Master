"""The how-to-play guide (WBS 13.3).

`HOW_TO_PLAY.md` at the repository root is the guide for players who have never
played a role-playing game, written in the beginner vocabulary
(`adm/play/vocabulary.py`) with no dice notation and no AC, DC or HP.
`python -m adm.cli guide` prints it with `rich`; `/help` (`adm/play/commands.py`)
shows a short version and points here.
"""

from __future__ import annotations

from pathlib import Path

from rich.markdown import Markdown

GUIDE = Path(__file__).resolve().parents[2] / "HOW_TO_PLAY.md"
GUIDE_COMMAND = "python -m adm.cli guide"
# Where `/help` sends a player for the full guide.
POINTER = f"The full guide: {GUIDE.name}, or run {GUIDE_COMMAND}"


def guide_text(path: Path = GUIDE) -> str:
    return path.read_text(encoding="utf-8")


def guide(path: Path = GUIDE) -> Markdown:
    """The guide, ready for a `rich` console."""
    return Markdown(guide_text(path))
