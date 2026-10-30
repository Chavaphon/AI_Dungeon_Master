"""The scenario loader and the encounter schedule (WBS 6.10, docs/scenario_format.md).

`load_scenario` reads `scenarios/<scenario_id>.json` and checks it against
schemas/scenario.schema.json. `initial_state` builds the turn-0 state a run
starts from: the scenario's entity maps plus the run-level fields of
docs/scenario_format.md section 2 (`seed` from the run, turn and round 0, no
encounter). The result passes the state schema and its cross-field rules, or
raises.

No tool starts an encounter, so the scenario says when each one does:
`{"before_input": n, "combatant_ids": [...]}` starts just before input `n`.
`due_encounter` decides which, if any, starts before an input:

- A scripted run counts `input_index`. Interactive play counts the player's
  inputs from 0, failed turns included, as a scripted run does, since a failed
  turn still uses up its input (docs/decisions.md, WBS 6.10).
- Encounters start in scenario order, one at a time. One that is due while the
  one before it is still active waits, and starts before the first input after
  that one ends. No encounter is skipped (docs/decisions.md, WBS 6.10).

The schedule reads the state and never writes it; `tools.open_encounter`
starts the encounter.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Sequence
from functools import cache
from pathlib import Path
from typing import Any, Literal

from jsonschema import Draft202012Validator
from pydantic import BaseModel, ConfigDict
from referencing import Registry, Resource

from adm.engine.state import GameState

SCHEMAS = Path(__file__).resolve().parents[2] / "schemas"


class ScenarioValidationError(ValueError):
    pass


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Encounter(_Model):
    before_input: int
    combatant_ids: list[str]


class ScriptedInput(_Model):
    text: str
    expected_call: dict[str, Any] | None
    check_advantage: Literal["advantage", "disadvantage"] | None = None


class Scenario(_Model):
    schema_version: Literal["1.0"]
    scenario_id: str
    display_name: str
    opening_narration: str
    locations: list[str]
    initial_state: dict[str, Any]
    encounters: list[Encounter]
    scripted_inputs: list[ScriptedInput]
    notes_for_annotators: str


@cache
def _validator() -> Draft202012Validator:
    schemas = {
        name: json.loads((SCHEMAS / name).read_text(encoding="utf-8"))
        for name in ("scenario.schema.json", "state.schema.json")
    }
    registry = Registry().with_resources(
        (s["$id"], Resource.from_contents(s)) for s in schemas.values()
    )
    return Draft202012Validator(schemas["scenario.schema.json"], registry=registry)


def load_scenario(path: Path) -> Scenario:
    """Read a scenario file and check it against the scenario schema."""
    data = json.loads(path.read_text(encoding="utf-8"))
    errors = sorted(_validator().iter_errors(data), key=lambda e: list(e.absolute_path))
    if errors:
        lines = [f"{e.json_path}: {e.message}" for e in errors]
        raise ScenarioValidationError(f"{path} does not match the schema:\n" + "\n".join(lines))
    return Scenario.model_validate(data)


def initial_state(scenario: Scenario, seed: int) -> GameState:
    """The turn-0 state of a run: no encounter yet, nothing played."""
    return GameState.from_dict(
        {
            "schema_version": "1.0",
            "scenario_id": scenario.scenario_id,
            "seed": seed,
            "turn_number": 0,
            "round_number": 0,
            "active_combatant_id": None,
            "initiative_order": [],
            "encounter_active": False,
            "encounter_outcome": None,
            **copy.deepcopy(scenario.initial_state),
        }
    )


def due_encounter(
    encounters: Sequence[Encounter], started: int, input_index: int, state: GameState
) -> Encounter | None:
    """The encounter to start before input `input_index`, given that the first
    `started` encounters have started, or None."""
    if started >= len(encounters) or state.encounter_active:
        return None
    upcoming = encounters[started]
    return upcoming if upcoming.before_input <= input_index else None
