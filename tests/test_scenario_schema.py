"""Scenario format v1.0 (WBS 2.5): the schema validates the example scenario and
every file in scenarios/, and rejects scenarios that break CLAUDE.md section 12.

`scenario_errors` covers the rules JSON Schema cannot express (see
docs/scenario_format.md). `initial_game_state` is the reference for how the
loader turns a scenario into a turn-0 state; the runtime loader belongs to
WBS 4.1.

Run: pytest tests/test_scenario_schema.py -v
"""

import copy
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from test_state_schema import VALIDATOR as STATE_VALIDATOR
from test_state_schema import cross_field_errors

ROOT = Path(__file__).resolve().parents[1]
STATE_SCHEMA = json.loads((ROOT / "schemas" / "state.schema.json").read_text(encoding="utf-8"))
SCHEMA = json.loads((ROOT / "schemas" / "scenario.schema.json").read_text(encoding="utf-8"))
REGISTRY = Registry().with_resource(STATE_SCHEMA["$id"], Resource.from_contents(STATE_SCHEMA))
VALIDATOR = Draft202012Validator(SCHEMA, registry=REGISTRY)

EXAMPLE = ROOT / "schemas" / "examples" / "scenario_s00_example.json"
SCENARIOS = sorted((ROOT / "scenarios").glob("*.json"))

ACTOR_ARGUMENT = {
    "attack": "attacker_id",
    "cast_spell": "caster_id",
    "dodge": "actor_id",
    "skill_check": "actor_id",
    "modify_inventory": "actor_id",
}
COMBAT_TOOLS = {"attack", "cast_spell", "dodge"}
COVERAGE_TOOLS = {"modify_inventory", "update_quest", "update_npc_relationship"}

Scenario = dict[str, Any]


def _load(path: Path) -> Scenario:
    return json.loads(path.read_text(encoding="utf-8"))


def _example() -> Scenario:
    return _load(EXAMPLE)


def _schema_errors(scenario: Scenario) -> list[str]:
    return [e.message for e in VALIDATOR.iter_errors(scenario)]


def initial_game_state(scenario: Scenario, seed: int) -> dict[str, Any]:
    """The turn-0 GameState a run starts from: no encounter yet, nothing played."""
    return {
        "schema_version": "1.0",
        "scenario_id": scenario["scenario_id"],
        "seed": seed,
        "turn_number": 0,
        "round_number": 0,
        "active_combatant_id": None,
        "initiative_order": [],
        "encounter_active": False,
        "encounter_outcome": None,
        **copy.deepcopy(scenario["initial_state"]),
    }


def scenario_errors(scenario: Scenario) -> list[str]:
    errors: list[str] = []
    state = scenario["initial_state"]
    combatants = state["combatants"]
    pcs = [cid for cid, c in combatants.items() if c["is_player_character"]]
    inputs = scenario["scripted_inputs"]

    game_state = initial_game_state(scenario, seed=0)
    errors += [f"initial_state: {e.message}" for e in STATE_VALIDATOR.iter_errors(game_state)]
    errors += [f"initial_state: {e}" for e in cross_field_errors(game_state)]

    previous = -1
    for n, encounter in enumerate(scenario["encounters"]):
        start = encounter["before_input"]
        if start <= previous:
            errors.append(f"encounters[{n}]: before_input {start} is not after {previous}")
        if start >= len(inputs):
            errors.append(f"encounters[{n}]: before_input {start} is past the last input")
        previous = start
        ids = encounter["combatant_ids"]
        for cid in ids:
            if cid not in combatants:
                errors.append(f"encounters[{n}]: unknown combatant {cid}")
        if not set(pcs) <= set(ids):
            errors.append(f"encounters[{n}]: the player character is not in it")
        if not any(combatants.get(cid, {}).get("faction") == "hostile" for cid in ids):
            errors.append(f"encounters[{n}]: no hostile combatant")

    first_encounter = min((e["before_input"] for e in scenario["encounters"]), default=None)
    used: set[str] = set()
    for i, scripted in enumerate(inputs):
        call = scripted["expected_call"]
        if call is None:
            continue
        tool, args = call["tool"], call["arguments"]
        used.add(tool)
        where = f"scripted_inputs[{i}] {tool}"

        actor = args.get(ACTOR_ARGUMENT.get(tool, ""))
        if actor is not None and actor not in pcs:
            errors.append(f"{where}: actor {actor} is not the player character")
        if "target_id" in args and args["target_id"] not in combatants:
            errors.append(f"{where}: unknown target {args['target_id']}")
        for key in ("weapon_id", "item_id"):
            if key in args and args[key] not in state["item_definitions"]:
                errors.append(f"{where}: undefined item {args[key]}")
        if "npc_id" in args and args["npc_id"] not in state["npc_relationships"]:
            errors.append(f"{where}: unknown npc {args['npc_id']}")
        if "quest_id" in args and args["quest_id"] not in state["quests"]:
            errors.append(f"{where}: unknown quest {args['quest_id']}")
        if tool in COMBAT_TOOLS and (first_encounter is None or i < first_encounter):
            errors.append(f"{where}: combat action before any encounter starts")

    covered = len(used & COVERAGE_TOOLS)
    needed = 3 if scenario["scenario_id"].startswith("long") else 2
    if covered < needed:
        errors.append(
            f"exercises {covered} of inventory, quest and relationship changes; needs {needed}"
        )

    return errors


def test_schema_is_valid_draft_2020_12() -> None:
    Draft202012Validator.check_schema(SCHEMA)


def test_example_validates() -> None:
    scenario = _example()
    assert _schema_errors(scenario) == []
    assert scenario_errors(scenario) == []


def test_initial_game_state_is_a_valid_turn_0_state() -> None:
    state = initial_game_state(_example(), seed=12345)
    assert list(STATE_VALIDATOR.iter_errors(state)) == []
    assert cross_field_errors(state) == []
    assert state["seed"] == 12345
    assert state["turn_number"] == 0 and not state["encounter_active"]


@pytest.mark.parametrize("path", SCENARIOS, ids=lambda p: p.stem)
def test_scenario_file_validates(path: Path) -> None:
    scenario = _load(path)
    assert scenario["scenario_id"] == path.stem, "file name must be <scenario_id>.json"
    assert _schema_errors(scenario) == []
    assert scenario_errors(scenario) == []


def _set(path: str, value: Any) -> Callable[[Scenario], None]:
    *parents, leaf = path.split(".")

    def mutate(scenario: Scenario) -> None:
        node: Any = scenario
        for key in parents:
            node = node[int(key)] if isinstance(node, list) else node[key]
        if isinstance(node, list):
            node[int(leaf)] = value
        else:
            node[leaf] = value

    return mutate


def _delete(path: str) -> Callable[[Scenario], None]:
    *parents, leaf = path.split(".")

    def mutate(scenario: Scenario) -> None:
        node: Any = scenario
        for key in parents:
            node = node[int(key)] if isinstance(node, list) else node[key]
        del node[leaf]

    return mutate


SKILL_CHECK = "scripted_inputs.4.expected_call"

SCHEMA_REJECTS = {
    "unknown_top_level_key": _set("difficulty", "easy"),
    "missing_required_key": _delete("scripted_inputs"),
    "wrong_schema_version": _set("schema_version", "0.9"),
    "bad_scenario_id": _set("scenario_id", "cellar_rats"),
    "scenario_id_without_name": _set("scenario_id", "long01"),
    "no_locations": _set("locations", []),
    "duplicate_location": _set("locations", ["the cellar", "the cellar"]),
    "run_field_in_initial_state": _set("initial_state.seed", 12345),
    "invalid_combatant_in_initial_state": _set("initial_state.combatants.pc_lyra.current_hp", -1),
    "no_inputs": _set("scripted_inputs", []),
    "empty_input_text": _set("scripted_inputs.0.text", ""),
    "plain_string_input": _set("scripted_inputs.0", "I look around the cellar"),
    "missing_expected_call": _delete("scripted_inputs.0.expected_call"),
    "unknown_tool": _set(
        "scripted_inputs.0.expected_call", {"tool": "dash", "arguments": {"actor_id": "pc_lyra"}}
    ),
    "missing_argument": _delete("scripted_inputs.2.expected_call.arguments.weapon_id"),
    "unknown_argument": _set("scripted_inputs.2.expected_call.arguments.range", 30),
    "unsupported_spell": _set("scripted_inputs.3.expected_call.arguments.spell_id", "spell_sleep"),
    "unsupported_skill": _set(f"{SKILL_CHECK}.arguments.skill", "arcana"),
    "dc_below_5": _set(f"{SKILL_CHECK}.arguments.dc", 4),
    "dc_above_25": _set(f"{SKILL_CHECK}.arguments.dc", 26),
    "dc_not_integer": _set(f"{SKILL_CHECK}.arguments.dc", "12"),
    "zero_inventory_delta": _set("scripted_inputs.5.expected_call.arguments.delta", 0),
    "unknown_direction": _set("scripted_inputs.7.expected_call.arguments.direction", "sideways"),
    "short_justification": _set("scripted_inputs.7.expected_call.arguments.justification", "nice"),
    "unknown_transition": _set("scripted_inputs.1.expected_call.arguments.transition", "reset"),
    "advantage_on_non_check": _set("scripted_inputs.2.check_advantage", "advantage"),
    "advantage_without_call": _set("scripted_inputs.0.check_advantage", "advantage"),
    "unknown_advantage_mode": _set("scripted_inputs.4.check_advantage", "double"),
    "encounter_with_one_combatant": _set("encounters.0.combatant_ids", ["pc_lyra"]),
    "encounter_negative_start": _set("encounters.0.before_input", -1),
}


@pytest.mark.parametrize("mutate", SCHEMA_REJECTS.values(), ids=SCHEMA_REJECTS.keys())
def test_schema_rejects(mutate: Callable[[Scenario], None]) -> None:
    scenario = _example()
    mutate(scenario)
    assert _schema_errors(scenario), "schema accepted an invalid scenario"


def _second_encounter(start: int) -> Callable[[Scenario], None]:
    def mutate(scenario: Scenario) -> None:
        scenario["encounters"].append(
            {"before_input": start, "combatant_ids": ["pc_lyra", "npc_rat_02"]}
        )

    return mutate


def _drop_calls(*tools: str) -> Callable[[Scenario], None]:
    def mutate(scenario: Scenario) -> None:
        for scripted in scenario["scripted_inputs"]:
            if scripted["expected_call"] and scripted["expected_call"]["tool"] in tools:
                scripted["expected_call"] = None

    return mutate


def _no_hostiles(scenario: Scenario) -> None:
    for combatant in scenario["initial_state"]["combatants"].values():
        if combatant["faction"] == "hostile":
            combatant["faction"] = "neutral"


def _as_long(scenario: Scenario) -> None:
    scenario["scenario_id"] = "long01_border_road"
    _drop_calls("update_npc_relationship")(scenario)


CROSS_FIELD_REJECTS = {
    "initial_hp_above_max": _set("initial_state.combatants.pc_lyra.current_hp", 21),
    "initial_two_step_history": _set(
        "initial_state.npc_relationships.npc_keeper.history",
        [{"turn": 0, "from": "hostile", "to": "neutral", "justification": "Paid off an old debt."}],
    ),
    "encounter_unknown_combatant": _set("encounters.0.combatant_ids", ["pc_lyra", "npc_ghost"]),
    "encounter_without_pc": _set("encounters.0.combatant_ids", ["npc_rat_01", "npc_rat_02"]),
    "encounter_without_hostile": _no_hostiles,
    "encounter_past_last_input": _set("encounters.0.before_input", 9),
    "encounters_out_of_order": _second_encounter(1),
    "actor_is_not_pc": _set("scripted_inputs.2.expected_call.arguments.attacker_id", "npc_rat_01"),
    "unknown_target": _set("scripted_inputs.2.expected_call.arguments.target_id", "npc_rat_03"),
    "undefined_weapon": _set("scripted_inputs.2.expected_call.arguments.weapon_id", "item_axe"),
    "undefined_item": _set("scripted_inputs.5.expected_call.arguments.item_id", "item_lantern"),
    "unknown_npc": _set("scripted_inputs.7.expected_call.arguments.npc_id", "npc_mayor"),
    "unknown_quest": _set("scripted_inputs.1.expected_call.arguments.quest_id", "quest_rats"),
    "combat_before_encounter": _set("encounters.0.before_input", 3),
    "covers_only_one_change": _drop_calls("modify_inventory", "update_npc_relationship"),
    "long_covers_only_two_changes": _as_long,
}


@pytest.mark.parametrize("mutate", CROSS_FIELD_REJECTS.values(), ids=CROSS_FIELD_REJECTS.keys())
def test_cross_field_rejects(mutate: Callable[[Scenario], None]) -> None:
    scenario = _example()
    mutate(scenario)
    assert _schema_errors(scenario) == [], "case should pass the schema and fail only in Python"
    assert scenario_errors(scenario)
