"""The scenario picker and the random seed (WBS 13.6).

`play` with no `--scenario` shows a numbered menu of the scenarios in
`scenarios/`: each one's name, whether it is short or long, and its number of
scripted turns. A tutorial (`tut` prefix, WBS 13.9) is listed first and marked
"Start here"; then the short scenarios, then the long ones, each in id order.

`play` with no `--seed` draws a seed here, in the CLI layer, from the operating
system (`secrets`), never from `random` and never in `engine/` or
`orchestration/`. The game's dice still come from the one `DiceRoller`, which
the session seeds with it (CLAUDE.md invariant 3). The seed is printed at the
start and the end of the session with the command that replays it.

Drawn seeds are six digits, `SEED_MIN` to `SEED_MAX`, so they are easy to type
and never one of the experiment seeds (1001-1010, 2001-2003, 3001): a play
session can never take the path of an experiment log.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from pathlib import Path

from rich.markup import escape
from rich.table import Table

from adm.engine.scenario import load_scenario

SCENARIOS = Path(__file__).resolve().parents[2] / "scenarios"

SEED_MIN = 100_000
SEED_MAX = 999_999

START_HERE = "Start here"
CHOOSE = "Choose a scenario by number"
INVALID = "Type a number from the list."

# Scenario id prefix -> its length word and place in the menu.
KINDS = ("tut", "s", "long")
LENGTHS = {"tut": "tutorial", "s": "short", "long": "long"}


@dataclass(frozen=True)
class Choice:
    """One row of the menu."""

    path: Path
    scenario_id: str
    display_name: str
    length: str
    turns: int

    @property
    def tutorial(self) -> bool:
        return self.length == LENGTHS["tut"]


def _kind(scenario_id: str) -> str:
    return scenario_id.split("_", 1)[0].rstrip("0123456789")


def choices(directory: Path = SCENARIOS) -> list[Choice]:
    """Every scenario in `directory`, in menu order: tutorial, short, long."""
    found = []
    for path in directory.glob("*.json"):
        scenario = load_scenario(path)
        kind = _kind(scenario.scenario_id)
        found.append(
            Choice(
                path=path,
                scenario_id=scenario.scenario_id,
                display_name=scenario.display_name,
                length=LENGTHS[kind],
                turns=len(scenario.scripted_inputs),
            )
        )
    return sorted(found, key=lambda c: (KINDS.index(_kind(c.scenario_id)), c.scenario_id))


def menu(rows: list[Choice]) -> Table:
    """The numbered menu, from 1."""
    table = Table(title="Choose a scenario", title_justify="left", box=None, pad_edge=False)
    table.add_column("#", justify="right")
    table.add_column("Scenario")
    table.add_column("Length")
    table.add_column("Turns", justify="right")
    for number, row in enumerate(rows, start=1):
        name = escape(row.display_name)
        if row.tutorial:
            name = f"{name}  [bold]{START_HERE}[/bold]"
        table.add_row(str(number), name, row.length, f"about {row.turns}")
    return table


def parse_choice(text: str, count: int) -> int | None:
    """The 0-based index a typed menu number names, or None if it names none."""
    text = text.strip()
    if not text.isdigit():
        return None
    number = int(text)
    return number - 1 if 1 <= number <= count else None


def draw_seed() -> int:
    """A fresh six-digit seed from the operating system, never from `random`."""
    return SEED_MIN + secrets.randbelow(SEED_MAX - SEED_MIN + 1)


def replay_command(scenario: Path, seed: int) -> str:
    """The command that plays the same scenario with the same seed."""
    try:
        shown = scenario.resolve().relative_to(Path.cwd())
    except ValueError:
        shown = scenario
    return f"python -m adm.cli play --scenario {shown} --seed {seed}"
