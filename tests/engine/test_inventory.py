"""Inventory add and remove with quantity rules (WBS 4.14): quantities never go
below 0, a quantity of 0 keeps its key, a new item is added at `delta`, and the
owner may be unconscious. The result matches `facts_modify_inventory` and the
contract example.

Run: pytest tests/engine/test_inventory.py -v
"""

import json
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from adm.engine.inventory import InventoryOutcome, held, modify_inventory, most_negative_delta
from adm.engine.state import GameState, load_state

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "schemas" / "examples"

_SCHEMAS = [
    json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))
    for name in ("state.schema.json", "tools.schema.json")
]
_REGISTRY = Registry().with_resources((s["$id"], Resource.from_contents(s)) for s in _SCHEMAS)
RESULT_VALIDATOR = Draft202012Validator(
    {"$ref": _SCHEMAS[1]["$id"] + "#/$defs/tool_result"}, registry=_REGISTRY
)


@pytest.fixture
def exploration() -> GameState:
    # Lyra holds a short sword and 2 torches; each rat holds its bite.
    return load_state(EXAMPLES / "state_01_exploration.json")


def _result(outcome: InventoryOutcome) -> dict:
    return {"ok": True, "tool": "modify_inventory", **outcome.to_dict()}


def _assert_valid(state: GameState) -> None:
    GameState.from_dict(state.to_dict())


# --- rule suite: inventory and quantity floors (CLAUDE.md section 13) --------


@pytest.mark.rule_suite("inventory")
def test_remove_reproduces_the_contract_example(exploration: GameState) -> None:
    outcome = modify_inventory(exploration, "pc_lyra", "item_torch", -1)
    example = json.loads((EXAMPLES / "result_modify_inventory.json").read_text(encoding="utf-8"))
    assert _result(outcome) == example
    RESULT_VALIDATOR.validate(_result(outcome))
    assert exploration.inventory["pc_lyra"]["item_torch"] == 1
    _assert_valid(exploration)


@pytest.mark.rule_suite("inventory")
def test_removing_everything_leaves_0_and_keeps_the_key(exploration: GameState) -> None:
    outcome = modify_inventory(exploration, "pc_lyra", "item_torch", -2)
    assert exploration.inventory["pc_lyra"]["item_torch"] == 0
    assert (outcome.facts.quantity_before, outcome.facts.quantity_after) == (2, 0)
    assert [c.path for c in outcome.state_diff] == ["inventory.pc_lyra.item_torch"]
    RESULT_VALIDATOR.validate(_result(outcome))
    _assert_valid(exploration)
    # an item at 0 can be held again
    modify_inventory(exploration, "pc_lyra", "item_torch", 1)
    assert exploration.inventory["pc_lyra"]["item_torch"] == 1


@pytest.mark.rule_suite("inventory")
@pytest.mark.parametrize(
    ("item_id", "delta"),
    [
        ("item_torch", -3),  # holds 2: one too many
        ("item_torch", -100),
        ("item_rat_bite", -1),  # defined but never held: 0
    ],
)
def test_below_0_is_refused_and_changes_nothing(
    exploration: GameState, item_id: str, delta: int
) -> None:
    before = exploration.to_dict()
    with pytest.raises(ValueError, match="cannot apply"):
        modify_inventory(exploration, "pc_lyra", item_id, delta)
    assert exploration.to_dict() == before
    assert most_negative_delta(exploration, "pc_lyra", item_id) == -held(
        exploration, "pc_lyra", item_id
    )


# --- other rules -------------------------------------------------------------


def test_new_item_is_added_at_delta_from_null(exploration: GameState) -> None:
    outcome = modify_inventory(exploration, "pc_lyra", "item_rat_bite", 2)
    assert exploration.inventory["pc_lyra"]["item_rat_bite"] == 2
    assert outcome.facts.quantity_before == 0
    change = outcome.state_diff[0].model_dump(mode="json", by_alias=True)
    assert change == {"path": "inventory.pc_lyra.item_rat_bite", "from": None, "to": 2}
    RESULT_VALIDATOR.validate(_result(outcome))
    _assert_valid(exploration)


def test_owner_with_no_inventory_gets_one(exploration: GameState) -> None:
    del exploration.inventory["npc_rat_02"]
    outcome = modify_inventory(exploration, "npc_rat_02", "item_torch", 1)
    assert exploration.inventory["npc_rat_02"] == {"item_torch": 1}
    change = outcome.state_diff[0].model_dump(mode="json", by_alias=True)
    assert change == {"path": "inventory.npc_rat_02", "from": None, "to": {"item_torch": 1}}
    _assert_valid(exploration)


def test_unconscious_owner_can_be_looted() -> None:
    state = load_state(EXAMPLES / "state_03_after_victory.json")
    rat = state.combatants["npc_rat_01"]
    assert rat.status == "unconscious"
    held_before = held(state, "npc_rat_01", "item_rat_bite")
    outcome = modify_inventory(state, "npc_rat_01", "item_rat_bite", -held_before)
    assert outcome.facts.actor == rat.display_name
    assert state.inventory["npc_rat_01"]["item_rat_bite"] == 0


def test_facts_use_display_names(exploration: GameState) -> None:
    facts = modify_inventory(exploration, "pc_lyra", "item_short_sword", 1).facts
    assert (facts.actor, facts.item, facts.delta) == ("Lyra", "short sword", 1)


@pytest.mark.parametrize(
    ("actor_id", "item_id", "delta", "message"),
    [
        ("pc_lyra", "item_torch", 0, "delta is 0"),
        ("npc_ghost", "item_torch", 1, "not a combatant"),
        ("pc_lyra", "item_lantern", 1, "not defined"),
    ],
)
def test_calls_the_validator_rejects_raise(
    exploration: GameState, actor_id: str, item_id: str, delta: int, message: str
) -> None:
    before = exploration.to_dict()
    with pytest.raises(ValueError, match=message):
        modify_inventory(exploration, actor_id, item_id, delta)
    assert exploration.to_dict() == before


@given(deltas=st.lists(st.integers(min_value=-5, max_value=5).filter(bool), max_size=30))
def test_no_sequence_of_calls_reaches_a_negative_quantity(deltas: list[int]) -> None:
    state = load_state(EXAMPLES / "state_01_exploration.json")
    expected = 2
    for delta in deltas:
        if expected + delta < 0:
            with pytest.raises(ValueError):
                modify_inventory(state, "pc_lyra", "item_torch", delta)
        else:
            modify_inventory(state, "pc_lyra", "item_torch", delta)
            expected += delta
        assert state.inventory["pc_lyra"]["item_torch"] == expected >= 0
    _assert_valid(state)
