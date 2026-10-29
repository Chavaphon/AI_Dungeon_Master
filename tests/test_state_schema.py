"""State schema v1.0 (WBS 2.1): the schema validates the hand-written examples
and rejects states that break the rules in CLAUDE.md sections 4 and 5.

`cross_field_errors` covers the rules JSON Schema cannot express (see
docs/state_schema.md). It lives in adm/engine/state.py since WBS 5.4, where the
post-write invariant assertion (`check_state`) runs it after every write.

Run: pytest tests/test_state_schema.py -v
"""

import copy
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from adm.engine.state import cross_field_errors

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schemas" / "state.schema.json").read_text(encoding="utf-8"))
EXAMPLES = sorted((ROOT / "schemas" / "examples").glob("state_*.json"))
VALIDATOR = Draft202012Validator(SCHEMA)

State = dict[str, Any]


def _load(path: Path) -> State:
    return json.loads(path.read_text(encoding="utf-8"))


def _mid_combat() -> State:
    return _load(ROOT / "schemas" / "examples" / "state_02_mid_combat.json")


def _schema_errors(state: State) -> list[str]:
    return [e.message for e in VALIDATOR.iter_errors(state)]


def test_schema_is_valid_draft_2020_12() -> None:
    Draft202012Validator.check_schema(SCHEMA)


def test_three_examples_exist() -> None:
    assert len(EXAMPLES) == 3


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.stem)
def test_example_validates(path: Path) -> None:
    state = _load(path)
    assert _schema_errors(state) == []
    assert cross_field_errors(state) == []


def _set(path: str, value: Any) -> Callable[[State], None]:
    *parents, leaf = path.split(".")

    def mutate(state: State) -> None:
        node = state
        for key in parents:
            node = node[key]
        node[leaf] = value

    return mutate


def _delete(path: str) -> Callable[[State], None]:
    *parents, leaf = path.split(".")

    def mutate(state: State) -> None:
        node = state
        for key in parents:
            node = node[key]
        del node[leaf]

    return mutate


def _rename_combatant(state: State) -> None:
    state["combatants"]["rat_03"] = state["combatants"].pop("npc_rat_02")


SCHEMA_REJECTS = {
    "unknown_top_level_key": _set("location", "cellar"),
    "unknown_combatant_key": _set("combatants.pc_lyra.level", 3),
    "missing_required_key": _delete("quests"),
    "wrong_schema_version": _set("schema_version", "0.9"),
    "bad_id_prefix": _rename_combatant,
    "pc_with_npc_prefix": _set("combatants.npc_rat_01.is_player_character", True),
    "ability_above_20": _set("combatants.pc_lyra.abilities.dex", 21),
    "ability_below_1": _set("combatants.pc_lyra.abilities.str", 0),
    "unsupported_skill": _set("combatants.pc_lyra.proficient_skills", ["arcana"]),
    "negative_hp": _set("combatants.pc_lyra.current_hp", -1),
    "unconscious_with_hp": _set("combatants.npc_rat_01.status", "unconscious"),
    "active_at_zero_hp": _set("combatants.npc_rat_01.current_hp", 0),
    "unknown_status": _set("combatants.pc_lyra.status", "dead"),
    "unknown_faction": _set("combatants.pc_lyra.faction", "ally"),
    "partial_spell_fields": _set("combatants.npc_rat_01.spell_slots_1", 0),
    "negative_spell_slots": _set("combatants.pc_lyra.spell_slots_1", -1),
    "negative_inventory": _set("inventory.pc_lyra.item_torch", -1),
    "weapon_without_damage": _delete("item_definitions.item_short_sword.damage_dice"),
    "damage_dice_with_modifier": _set("item_definitions.item_short_sword.damage_dice", "1d6+3"),
    "unsupported_die": _set("item_definitions.item_short_sword.damage_dice", "1d7"),
    "non_weapon_with_attack": _set("item_definitions.item_torch.attack_bonus", 1),
    "unknown_stance": _set("npc_relationships.npc_keeper.stance", "loyal"),
    "short_justification": _set(
        "npc_relationships.npc_keeper.history",
        [{"turn": 4, "from": "unfriendly", "to": "neutral", "justification": "helped"}],
    ),
    "unknown_quest_state": _set("quests.quest_missing_ledger.state", "abandoned"),
    "not_started_past_stage_0": _set("quests.quest_missing_ledger.state", "not_started"),
    "active_at_stage_0": _set("quests.quest_missing_ledger.stage", 0),
    "encounter_without_active_combatant": _set("active_combatant_id", None),
    "encounter_with_empty_order": _set("initiative_order", []),
    "encounter_round_0": _set("round_number", 0),
    "outcome_while_active": _set("encounter_outcome", "victory"),
    "duplicate_in_initiative": _set("initiative_order", ["pc_lyra", "pc_lyra"]),
    "active_combatant_outside_encounter": _set("encounter_active", False),
}


@pytest.mark.parametrize("mutate", SCHEMA_REJECTS.values(), ids=SCHEMA_REJECTS.keys())
def test_schema_rejects(mutate: Callable[[State], None]) -> None:
    state = _mid_combat()
    mutate(state)
    assert _schema_errors(state), "schema accepted an invalid state"


def _add_second_pc(state: State) -> None:
    pc = copy.deepcopy(state["combatants"]["pc_lyra"])
    pc["combatant_id"] = "pc_bram"
    state["combatants"]["pc_bram"] = pc


def _add_keeper_combatant(display_name: str) -> Callable[[State], None]:
    def mutate(state: State) -> None:
        keeper = copy.deepcopy(state["combatants"]["npc_rat_02"])
        keeper.update(combatant_id="npc_keeper", display_name=display_name, faction="neutral")
        state["combatants"]["npc_keeper"] = keeper

    return mutate


CROSS_FIELD_REJECTS = {
    "hp_above_max": _set("combatants.pc_lyra.current_hp", 21),
    "key_id_mismatch": _set("combatants.pc_lyra.combatant_id", "pc_other"),
    "two_player_characters": _add_second_pc,
    "initiative_unknown_combatant": _set("initiative_order", ["pc_lyra", "npc_ghost"]),
    "active_not_in_initiative": _set("initiative_order", ["npc_rat_01", "npc_rat_02"]),
    "inventory_undefined_item": _set("inventory.pc_lyra.item_lantern", 1),
    "inventory_unknown_owner": _set("inventory.npc_ghost", {}),
    "two_step_relationship": _set(
        "npc_relationships.npc_keeper.history",
        [{"turn": 4, "from": "hostile", "to": "neutral", "justification": "Lyra paid the debt."}],
    ),
    "stance_disagrees_with_history": _set("npc_relationships.npc_keeper.stance", "friendly"),
    "stage_beyond_max": _set("quests.quest_missing_ledger.stage", 4),
    "one_id_two_names": _add_keeper_combatant("Keeper Alis"),
}


@pytest.mark.parametrize("mutate", CROSS_FIELD_REJECTS.values(), ids=CROSS_FIELD_REJECTS.keys())
def test_cross_field_rejects(mutate: Callable[[State], None]) -> None:
    state = _mid_combat()
    mutate(state)
    assert _schema_errors(state) == [], "case should pass the schema and fail only in Python"
    assert cross_field_errors(state)


def test_victory_needs_a_conscious_player_character() -> None:
    state = _load(ROOT / "schemas" / "examples" / "state_03_after_victory.json")
    state["combatants"]["pc_lyra"].update(current_hp=0, status="unconscious")
    assert _schema_errors(state) == []
    assert cross_field_errors(state) == ["victory with an unconscious player character"]


def test_defeat_needs_an_unconscious_player_character() -> None:
    state = _load(ROOT / "schemas" / "examples" / "state_03_after_victory.json")
    state["encounter_outcome"] = "defeat"
    assert _schema_errors(state) == []
    assert cross_field_errors(state) == ["defeat with an active player character"]


def test_victory_allows_a_hostile_kept_for_a_later_encounter() -> None:
    # s08_old_mine: the spider is still active after the kobolds are beaten.
    # Who was in the encounter is not kept once it ends (docs/decisions.md, WBS 5.4).
    state = _load(ROOT / "schemas" / "examples" / "state_03_after_victory.json")
    state["combatants"]["npc_rat_02"].update(current_hp=3, status="active")
    assert _schema_errors(state) == []
    assert cross_field_errors(state) == []
