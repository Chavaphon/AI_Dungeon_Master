"""Quest log transitions (WBS 4.16): the four legal transitions of CLAUDE.md
section 5.2, and every other transition rejected with `ILLEGAL_QUEST_TRANSITION`
and the transitions that are legal instead. The result matches
`facts_update_quest` and the contract example.

Run: pytest tests/engine/test_quests.py -v
"""

import json
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from adm.engine.quests import (
    ILLEGAL_QUEST_TRANSITION,
    TRANSITIONS,
    IllegalQuestTransition,
    QuestOutcome,
    legal_transitions,
    update_quest,
)
from adm.engine.state import GameState, load_state

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "schemas" / "examples"
LEDGER = "quest_missing_ledger"  # max_stage 3 in every example state

_SCHEMAS = [
    json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))
    for name in ("state.schema.json", "tools.schema.json")
]
_REGISTRY = Registry().with_resources((s["$id"], Resource.from_contents(s)) for s in _SCHEMAS)
RESULT_VALIDATOR = Draft202012Validator(
    {"$ref": _SCHEMAS[1]["$id"] + "#/$defs/tool_result"}, registry=_REGISTRY
)


@pytest.fixture
def state() -> GameState:
    # The ledger quest is not_started, stage 0 of 3.
    return load_state(EXAMPLES / "state_01_exploration.json")


def _result(outcome: QuestOutcome) -> dict:
    return {"ok": True, "tool": "update_quest", **outcome.to_dict()}


def _assert_valid(state: GameState) -> None:
    GameState.from_dict(state.to_dict())


def _set(state: GameState, quest_state: str, stage: int) -> None:
    quest = state.quests[LEDGER]
    quest.state, quest.stage = quest_state, stage


# --- rule suite: quest transitions, legal and illegal ------------------------


@pytest.mark.rule_suite("quests")
def test_advance_reproduces_the_contract_example() -> None:
    state = load_state(EXAMPLES / "state_02_mid_combat.json")  # active, stage 2 of 3
    outcome = update_quest(state, LEDGER, "advance")
    example = json.loads((EXAMPLES / "result_update_quest.json").read_text(encoding="utf-8"))
    assert _result(outcome) == example
    RESULT_VALIDATOR.validate(_result(outcome))
    _assert_valid(state)


@pytest.mark.rule_suite("quests")
@pytest.mark.parametrize(
    ("transition", "final", "diff_paths"),
    [
        ("complete", ("completed", 3), ["state"]),
        ("fail", ("failed", 3), ["state"]),
    ],
)
def test_start_advance_then_finish(
    state: GameState, transition: str, final: tuple[str, int], diff_paths: list[str]
) -> None:
    start = update_quest(state, LEDGER, "start")
    assert [c.path.rsplit(".", 1)[1] for c in start.state_diff] == ["state", "stage"]
    assert (start.facts.state_after, start.facts.stage_after) == ("active", 1)
    for stage in (2, 3):
        assert update_quest(state, LEDGER, "advance").facts.stage_after == stage
    outcome = update_quest(state, LEDGER, transition)
    quest = state.quests[LEDGER]
    assert (quest.state, quest.stage) == final
    assert [c.path.rsplit(".", 1)[1] for c in outcome.state_diff] == diff_paths
    RESULT_VALIDATOR.validate(_result(outcome))
    _assert_valid(state)


@pytest.mark.rule_suite("quests")
@pytest.mark.parametrize(
    ("quest_state", "stage", "transition", "legal"),
    [
        ("not_started", 0, "advance", ["start"]),
        ("not_started", 0, "complete", ["start"]),
        ("not_started", 0, "fail", ["start"]),
        ("active", 1, "start", ["advance", "complete", "fail"]),
        ("active", 3, "advance", ["complete", "fail"]),  # at max_stage
        ("completed", 3, "start", []),
        ("completed", 3, "fail", []),  # finished quests are final
        ("failed", 2, "advance", []),
        ("failed", 2, "complete", []),
    ],
)
def test_illegal_transition_is_rejected_with_its_code(
    state: GameState, quest_state: str, stage: int, transition: str, legal: list[str]
) -> None:
    _set(state, quest_state, stage)
    before = state.to_dict()
    with pytest.raises(IllegalQuestTransition) as raised:
        update_quest(state, LEDGER, transition)
    assert raised.value.code == ILLEGAL_QUEST_TRANSITION
    assert str(raised.value).startswith(ILLEGAL_QUEST_TRANSITION)
    assert raised.value.valid_options == {"transition": legal}
    assert state.to_dict() == before


# --- other rules -------------------------------------------------------------


def test_complete_does_not_need_max_stage(state: GameState) -> None:
    _set(state, "active", 1)
    outcome = update_quest(state, LEDGER, "complete")
    assert (outcome.facts.stage_before, outcome.facts.stage_after) == (1, 1)
    assert outcome.facts.max_stage == 3
    assert state.quests[LEDGER].state == "completed"


def test_facts_use_display_names(state: GameState) -> None:
    facts = update_quest(state, LEDGER, "start").facts
    assert (facts.quest, facts.transition) == ("The Missing Ledger", "start")


def test_unknown_quest_raises(state: GameState) -> None:
    with pytest.raises(ValueError, match="not a quest"):
        update_quest(state, "quest_rats", "start")


@pytest.mark.parametrize(
    ("quest_state", "stage", "legal"),
    [
        ("not_started", 0, ["start"]),
        ("active", 2, ["advance", "complete", "fail"]),
        ("active", 3, ["complete", "fail"]),
        ("completed", 3, []),
        ("failed", 1, []),
    ],
)
def test_legal_transitions(
    state: GameState, quest_state: str, stage: int, legal: list[str]
) -> None:
    _set(state, quest_state, stage)
    assert legal_transitions(state.quests[LEDGER]) == legal


@given(transitions=st.lists(st.sampled_from(TRANSITIONS), max_size=15))
def test_stage_only_rises_and_stays_in_range(transitions: list[str]) -> None:
    state = load_state(EXAMPLES / "state_01_exploration.json")
    quest = state.quests[LEDGER]
    for transition in transitions:
        stage, legal = quest.stage, legal_transitions(quest)
        if transition in legal:
            update_quest(state, LEDGER, transition)
        else:
            with pytest.raises(IllegalQuestTransition):
                update_quest(state, LEDGER, transition)
        assert stage <= quest.stage <= quest.max_stage
        assert (quest.state == "not_started") == (quest.stage == 0)
    _assert_valid(state)
