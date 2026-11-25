"""The scenario picker and the random seed (WBS 13.6, #254): the menu lists
every scenario, the tutorial first and marked "Start here", then short, then
long; a drawn seed is six digits from the operating system and is never an
experiment seed.

Run: pytest tests/play/test_picker.py -v
"""

import io
import json
import shutil
from pathlib import Path

import pytest
from rich.console import Console

from adm.engine.scenario import load_scenario
from adm.play import picker

ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = ROOT / "scenarios"
EXPERIMENTS = ROOT / "experiments"


def _render(rows: list[picker.Choice]) -> str:
    console = Console(width=120, record=True, file=io.StringIO())
    console.print(picker.menu(rows))
    return " ".join(console.export_text().split())


def test_every_scenario_is_listed_short_before_long() -> None:
    rows = picker.choices()
    ids = [row.scenario_id for row in rows]
    files = sorted(load_scenario(p).scenario_id for p in SCENARIOS.glob("*.json"))
    assert sorted(ids) == files
    lengths = [row.length for row in rows]
    assert lengths == sorted(lengths, key=["tutorial", "short", "long"].index)


def test_a_row_shows_name_length_and_turns() -> None:
    row = next(r for r in picker.choices() if r.scenario_id == "long01_border_road")
    scenario = load_scenario(row.path)
    assert (row.display_name, row.length, row.turns) == (
        scenario.display_name,
        "long",
        len(scenario.scripted_inputs),
    )
    text = _render([row])
    assert f"1 {scenario.display_name} long about {row.turns}" in text
    assert picker.START_HERE not in text


def test_the_tutorial_is_first_and_marked_start_here(tmp_path: Path) -> None:
    for name in ("s01_cellar", "long01_border_road"):
        shutil.copy(SCENARIOS / f"{name}.json", tmp_path)
    tutorial = json.loads((SCENARIOS / "s01_cellar.json").read_text(encoding="utf-8"))
    tutorial.update(scenario_id="tut01_first_steps", display_name="First Steps")
    (tmp_path / "tut01_first_steps.json").write_text(json.dumps(tutorial), encoding="utf-8")

    rows = picker.choices(tmp_path)
    assert [r.scenario_id for r in rows] == [
        "tut01_first_steps",
        "s01_cellar",
        "long01_border_road",
    ]
    assert rows[0].tutorial and rows[0].length == "tutorial"
    assert f"1 First Steps {picker.START_HERE} tutorial" in _render(rows)


@pytest.mark.parametrize(
    ("text", "index"),
    [("1", 0), (" 3 ", 2), ("16", 15), ("0", None), ("17", None), ("", None), ("two", None)],
    ids=repr,
)
def test_a_menu_number_names_one_row(text: str, index: int | None) -> None:
    assert picker.parse_choice(text, 16) == index


def test_drawn_seeds_are_six_digits() -> None:
    seeds = {picker.draw_seed() for _ in range(200)}
    assert all(picker.SEED_MIN <= s <= picker.SEED_MAX for s in seeds)
    assert len(seeds) > 1, "seeds are drawn, not fixed"


def test_no_experiment_seed_can_be_drawn() -> None:
    """A play session never takes the log path of an experiment run."""
    seeds: set[int] = set()
    for path in EXPERIMENTS.glob("*.json"):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        seeds.update(manifest.get("seeds", []))
        seeds.update(run["seed"] for run in manifest.get("runs", []))
    assert seeds, "the manifests name their seeds"
    assert not [s for s in seeds if picker.SEED_MIN <= s <= picker.SEED_MAX]


def test_the_replay_command_names_the_scenario_and_seed() -> None:
    command = picker.replay_command(SCENARIOS / "s01_cellar.json", 123456)
    assert command.startswith("python -m adm.cli play --scenario ")
    assert command.endswith("s01_cellar.json --seed 123456")
