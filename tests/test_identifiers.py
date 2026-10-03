"""Identifier conventions and the scenario-scoped namespace (WBS 2.2).

The id patterns live in schemas/state.schema.json; the rules are written down
in docs/identifiers.md. The scenario checks run over every file in scenarios/
and pass trivially until the first scenario is committed (WBS 2.5, 8.3).

Run: pytest tests/test_identifiers.py -v
"""

import copy
import json
import re
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schemas" / "state.schema.json").read_text(encoding="utf-8"))
SCENARIOS = sorted((ROOT / "scenarios").glob("*.json"))
ENGINE_SPELLS = ("spell_fire_bolt", "spell_cure_wounds")
SPELL_ID = re.compile(r"^spell_[a-z0-9]+(_[a-z0-9]+)*$")

ENTITY_KINDS = ("pc_id", "npc_id", "item_id", "quest_id")


def _matches(definition: str, value: str) -> bool:
    validator = Draft202012Validator({"$defs": SCHEMA["$defs"], "$ref": f"#/$defs/{definition}"})
    return validator.is_valid(value)


VALID = {
    "pc_id": ["pc_lyra", "pc_x", "pc_lyra_2"],
    "npc_id": ["npc_keeper", "npc_rat_01", "npc_rat_02", "npc_old_man_of_the_hill"],
    "item_id": ["item_torch", "item_short_sword", "item_rat_bite"],
    "quest_id": ["quest_missing_ledger"],
    "scenario_id": ["s01_cellar", "s12_last_stand", "long04_border_road"],
}

INVALID = {
    "pc_id": ["pc_", "pc_Lyra", "pc_lyra_", "pc__lyra", "pc_ly-ra", "lyra", "npc_lyra"],
    "npc_id": ["npc_rat__01", "npc_rat_", "npc_Rat", "rat_01", "pc_rat_01", "npc_rät"],
    "item_id": ["item_", "item_Short_sword", "item_short sword", "spell_fire_bolt"],
    "quest_id": ["quest_", "quest_missing__ledger", "q_missing_ledger"],
    "scenario_id": ["cellar", "s1_cellar", "s001_cellar", "s01_", "S01_cellar", "long1_road"],
}


@pytest.mark.parametrize(
    ("definition", "value"), [(d, v) for d, vs in VALID.items() for v in vs], ids=str
)
def test_valid_id_accepted(definition: str, value: str) -> None:
    assert _matches(definition, value)


@pytest.mark.parametrize(
    ("definition", "value"), [(d, v) for d, vs in INVALID.items() for v in vs], ids=str
)
def test_invalid_id_rejected(definition: str, value: str) -> None:
    assert not _matches(definition, value)


@pytest.mark.parametrize("value", [v for k in ENTITY_KINDS for v in VALID[k]])
def test_prefixes_are_disjoint(value: str) -> None:
    assert sum(_matches(kind, value) for kind in ENTITY_KINDS) == 1


def test_engine_spells_follow_the_convention() -> None:
    assert all(SPELL_ID.match(spell) for spell in ENGINE_SPELLS)


def _mid_combat() -> dict[str, Any]:
    path = ROOT / "schemas" / "examples" / "state_02_mid_combat.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_state_rejects_scenario_id_outside_namespace() -> None:
    state = _mid_combat()
    state["scenario_id"] = "cellar"
    assert not Draft202012Validator(SCHEMA).is_valid(state)


def test_npc_may_be_both_combatant_and_relationship() -> None:
    # The mismatched-name case is CROSS_FIELD_REJECTS["one_id_two_names"] in test_state_schema.
    state = _mid_combat()
    keeper = copy.deepcopy(state["combatants"]["npc_rat_02"])
    keeper.update(combatant_id="npc_keeper", display_name="the Keeper", faction="neutral")
    state["combatants"]["npc_keeper"] = keeper
    assert Draft202012Validator(SCHEMA).is_valid(state)


def _scenario(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("path", SCENARIOS, ids=lambda p: p.stem)
def test_scenario_file_is_named_after_its_id(path: Path) -> None:
    scenario = _scenario(path)
    assert _matches("scenario_id", scenario["scenario_id"])
    assert path.stem == scenario["scenario_id"]


@pytest.mark.parametrize("path", SCENARIOS, ids=lambda p: p.stem)
def test_scenario_state_carries_its_scenario_id(path: Path) -> None:
    scenario = _scenario(path)
    state_id = scenario.get("initial_state", {}).get("scenario_id", scenario["scenario_id"])
    assert state_id == scenario["scenario_id"]


def test_scenario_series_numbers_are_unique() -> None:
    numbers = [_scenario(p)["scenario_id"].split("_", 1)[0] for p in SCENARIOS]
    assert len(numbers) == len(set(numbers)), f"duplicate series numbers: {numbers}"
