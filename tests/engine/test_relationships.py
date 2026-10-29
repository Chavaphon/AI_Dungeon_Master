"""NPC relationship ladder (WBS 4.15): a change moves one step only, needs a
justification of at least 10 characters, and is recorded in `history`. A
two-step change and a missing justification are rejected. The result matches
`facts_update_npc_relationship` and the contract example.

Run: pytest tests/engine/test_relationships.py -v
"""

import json
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from adm.engine.relationships import (
    LADDER,
    RelationshipOutcome,
    other_direction,
    step,
    update_npc_relationship,
)
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

WHY = "Lyra paid off the Keeper's debt to the guild."


@pytest.fixture
def mid_combat() -> GameState:
    # Turn 7. The Keeper is neutral, with one history entry from turn 4.
    return load_state(EXAMPLES / "state_02_mid_combat.json")


def _result(outcome: RelationshipOutcome) -> dict:
    return {"ok": True, "tool": "update_npc_relationship", **outcome.to_dict()}


def _assert_valid(state: GameState) -> None:
    GameState.from_dict(state.to_dict())


# --- rule suite: relationship ladder, one-step rule, justification -----------


@pytest.mark.rule_suite("relationships")
def test_one_step_up_reproduces_the_contract_example(mid_combat: GameState) -> None:
    outcome = update_npc_relationship(mid_combat, "npc_keeper", "up", WHY)
    example = json.loads(
        (EXAMPLES / "result_update_npc_relationship.json").read_text(encoding="utf-8")
    )
    assert _result(outcome) == example
    RESULT_VALIDATOR.validate(_result(outcome))
    keeper = mid_combat.npc_relationships["npc_keeper"]
    assert keeper.stance == "friendly"
    assert [(h.turn, h.from_, h.to) for h in keeper.history] == [
        (4, "unfriendly", "neutral"),
        (7, "neutral", "friendly"),
    ]
    _assert_valid(mid_combat)


@pytest.mark.rule_suite("relationships")
@pytest.mark.parametrize(
    ("start", "direction"),
    [
        ("allied", "up"),  # already at the top: up would be a step off the ladder
        ("hostile", "down"),  # already at the bottom
    ],
)
def test_a_step_past_either_end_is_rejected(
    mid_combat: GameState, start: str, direction: str
) -> None:
    mid_combat.npc_relationships["npc_keeper"].stance = start
    before = mid_combat.to_dict()
    with pytest.raises(ValueError, match="cannot move"):
        update_npc_relationship(mid_combat, "npc_keeper", direction, WHY)
    assert mid_combat.to_dict() == before
    assert step(start, other_direction(direction)) is not None  # the valid option works


@pytest.mark.rule_suite("relationships")
@pytest.mark.parametrize(
    "justification",
    [
        "",
        "nice",
        "123456789",  # 9 characters: one short
    ],
)
def test_missing_or_short_justification_is_rejected(
    mid_combat: GameState, justification: str
) -> None:
    before = mid_combat.to_dict()
    with pytest.raises(ValueError, match="justification"):
        update_npc_relationship(mid_combat, "npc_keeper", "up", justification)
    assert mid_combat.to_dict() == before


# --- other rules -------------------------------------------------------------


def test_ten_characters_is_enough(mid_combat: GameState) -> None:
    outcome = update_npc_relationship(mid_combat, "npc_keeper", "down", "1234567890")
    assert (outcome.facts.stance_before, outcome.facts.stance_after) == ("neutral", "unfriendly")
    assert outcome.facts.justification == "1234567890"
    RESULT_VALIDATOR.validate(_result(outcome))


def test_two_steps_take_two_calls_and_two_history_entries(mid_combat: GameState) -> None:
    update_npc_relationship(mid_combat, "npc_keeper", "up", WHY)
    mid_combat.turn_number = 9
    outcome = update_npc_relationship(
        mid_combat, "npc_keeper", "up", "Lyra saved the Keeper's son."
    )
    keeper = mid_combat.npc_relationships["npc_keeper"]
    assert keeper.stance == "allied"
    assert [(h.turn, h.from_, h.to) for h in keeper.history][1:] == [
        (7, "neutral", "friendly"),
        (9, "friendly", "allied"),
    ]
    assert [c.path for c in outcome.state_diff] == [
        "npc_relationships.npc_keeper.stance",
        "npc_relationships.npc_keeper.history.2",
    ]
    _assert_valid(mid_combat)


def test_ladder_order_and_steps() -> None:
    assert LADDER == ("hostile", "unfriendly", "neutral", "friendly", "allied")
    assert [step(s, "up") for s in LADDER] == [*LADDER[1:], None]
    assert [step(s, "down") for s in LADDER] == [None, *LADDER[:-1]]
    assert (other_direction("up"), other_direction("down")) == ("down", "up")


@pytest.mark.parametrize(
    ("npc_id", "direction", "message"),
    [
        ("npc_mayor", "up", "has no relationship"),
        ("npc_keeper", "sideways", "not up or down"),
    ],
)
def test_calls_the_validator_rejects_raise(
    mid_combat: GameState, npc_id: str, direction: str, message: str
) -> None:
    before = mid_combat.to_dict()
    with pytest.raises(ValueError, match=message):
        update_npc_relationship(mid_combat, npc_id, direction, WHY)
    assert mid_combat.to_dict() == before


@given(directions=st.lists(st.sampled_from(["up", "down"]), max_size=20))
def test_every_recorded_change_is_one_step_and_justified(directions: list[str]) -> None:
    state = load_state(EXAMPLES / "state_02_mid_combat.json")
    for direction in directions:
        keeper = state.npc_relationships["npc_keeper"]
        if step(keeper.stance, direction) is None:
            with pytest.raises(ValueError):
                update_npc_relationship(state, "npc_keeper", direction, WHY)
        else:
            update_npc_relationship(state, "npc_keeper", direction, WHY)
    for change in state.npc_relationships["npc_keeper"].history:
        assert abs(LADDER.index(change.to) - LADDER.index(change.from_)) == 1
        assert len(change.justification) >= 10
    _assert_valid(state)
