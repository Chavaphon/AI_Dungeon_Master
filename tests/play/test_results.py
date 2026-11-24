"""Result lines (CLAUDE.md section 15, item 42; WBS 13.2): one line per
mechanical outcome, read from the audit record, shown before the narration.
Veteran mode shows the rolls, AC and DC; beginner mode says the same outcome in
plain words, with no jargon.

Run: pytest tests/play/test_results.py -v
"""

import json
from pathlib import Path

import pytest

from adm.engine.scenario import initial_state, load_scenario
from adm.engine.state import GameState
from adm.play.results import result_lines
from adm.play.vocabulary import JARGON, Mode

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "schemas" / "examples"
SCENARIO = load_scenario(ROOT / "scenarios" / "s01_cellar.json")


def _state() -> GameState:
    return initial_state(SCENARIO, 12345)


def _example(name: str) -> dict:
    return json.loads((EXAMPLES / f"{name}.json").read_text(encoding="utf-8"))


# The call each example result answers, in s01_cellar's ids.
ARGUMENTS = {
    "attack": {
        "attacker_id": "pc_lyra",
        "target_id": "npc_rat_01",
        "weapon_id": "item_short_sword",
    },
    "fire_bolt": {"caster_id": "pc_lyra", "spell_id": "spell_fire_bolt", "target_id": "npc_rat_01"},
    "cure_wounds": {
        "caster_id": "pc_lyra",
        "spell_id": "spell_cure_wounds",
        "target_id": "pc_lyra",
    },
    "dodge": {"actor_id": "pc_lyra"},
    "skill_check": {"actor_id": "pc_lyra", "skill": "perception", "dc": 12},
    "modify_inventory": {"actor_id": "pc_lyra", "item_id": "item_torch", "delta": -1},
    "update_npc_relationship": {
        "npc_id": "npc_keeper",
        "direction": "up",
        "justification": "Lyra paid off the debt.",
    },
    "update_quest": {"quest_id": "quest_missing_ledger", "transition": "advance"},
}

# example -> (its arguments, veteran line, beginner line)
LINES = {
    "result_attack": (
        "attack",
        "Lyra -> giant rat (short sword): 17 vs AC 12, hit, 7 damage; giant rat 4/11 HP",
        "You hit giant rat 1 with your short sword. Giant rat 1 is wounded.",
    ),
    "result_cast_spell_fire_bolt": (
        "fire_bolt",
        "Lyra -> giant rat (Fire Bolt): 13 vs AC 12, disadvantage, hit, 7 damage; "
        "giant rat 4/11 HP",
        "The odds are against you. You hit giant rat 1 with Fire Bolt. Giant rat 1 is wounded.",
    ),
    "result_cast_spell_cure_wounds": (
        "cure_wounds",
        "Lyra -> Lyra (Cure Wounds): +6 HP; Lyra 20/20 HP; 1 slot(s) left",
        "You cast Cure Wounds on yourself. You are healthy. 1 spell charge left.",
    ),
    "result_dodge": (
        "dodge",
        "Lyra dodges",
        "You dodge: attacks against you are harder until your next turn.",
    ),
    "result_skill_check": (
        "skill_check",
        "Lyra perception check: 12 vs DC 12, success",
        "Your perception check: success.",
    ),
    "result_modify_inventory": (
        "modify_inventory",
        "Lyra -1 torch (now 1)",
        "You lose 1 torch (1 left).",
    ),
    "result_update_npc_relationship": (
        "update_npc_relationship",
        "the Keeper: neutral -> friendly",
        "The Keeper now feels friendly towards you (was neutral).",
    ),
    "result_update_quest": (
        "update_quest",
        "Quest The Missing Ledger: active -> active (stage 3/3)",
        "Quest The Missing Ledger: in progress, stage 3 of 3.",
    ),
}


def _record(example: str, **facts: object) -> dict:
    result = _example(example)
    result["narration_facts"].update(facts)
    call = {"tool": result["tool"], "arguments": ARGUMENTS[LINES[example][0]]}
    return {"engine_steps": [], "validation": [result], "executed_call": call}


@pytest.mark.parametrize("example", LINES)
def test_every_tool_has_a_veteran_result_line(example: str) -> None:
    assert result_lines(_record(example), _state(), Mode.VETERAN) == [LINES[example][1]]


@pytest.mark.parametrize("example", LINES)
def test_every_tool_has_a_beginner_result_line(example: str) -> None:
    (line,) = result_lines(_record(example), _state(), Mode.BEGINNER)
    assert line == LINES[example][2]
    assert JARGON.search(line) is None


def test_result_lines_follow_the_order_of_the_turn() -> None:
    record = _example("audit_turn_valid")
    lines = result_lines(record, _state(), Mode.VETERAN)
    assert len(lines) == 3, "the player's attack, then the two NPC attacks after it"
    assert lines[0].startswith("Lyra -> giant rat (short sword)")
    assert all(line.startswith("giant rat -> Lyra (bite)") for line in lines[1:])


def test_beginner_lines_number_shared_names_and_call_the_player_you() -> None:
    lines = result_lines(_example("audit_turn_valid"), _state(), Mode.BEGINNER)
    assert lines == [
        "The odds are against you. You hit giant rat 2 with your short sword. "
        "Giant rat 2 is badly hurt.",
        "Giant rat 2 hits you with its bite. You are wounded.",
        "Giant rat 1 misses you.",
    ]


@pytest.mark.parametrize("mode", list(Mode))
def test_a_failed_turn_has_no_player_result_line(mode: Mode) -> None:
    assert result_lines(_example("audit_turn_rejected"), _state(), mode) == []


@pytest.mark.parametrize(
    ("example", "facts", "line"),
    [
        (
            "result_attack",
            {"hit": False, "damage": 0},
            "You miss giant rat 1.",
        ),
        (
            "result_attack",
            {"critical": True, "target_hp_after": 0, "target_hp_band": "unconscious"},
            "You hit giant rat 1 with your short sword. A critical hit! "
            "Giant rat 1 is knocked out.",
        ),
        (
            "result_cast_spell_cure_wounds",
            {"revived": True, "slots_remaining": 0, "target_hp_band": "badly_hurt"},
            "You cast Cure Wounds on yourself. You wake up. You are badly hurt. "
            "No spell charges left.",
        ),
        (
            "result_skill_check",
            {"advantage_mode": "advantage", "success": False},
            "You have the upper hand. Your perception check: failure.",
        ),
        (
            "result_modify_inventory",
            {"delta": 2, "quantity_before": 1, "quantity_after": 3},
            "You gain torch x2 (3 now).",
        ),
        (
            "result_update_quest",
            {"transition": "complete", "state_after": "completed"},
            "Quest The Missing Ledger: completed.",
        ),
    ],
)
def test_beginner_lines_for_other_outcomes(example: str, facts: dict, line: str) -> None:
    assert result_lines(_record(example, **facts), _state(), Mode.BEGINNER) == [line]
    assert JARGON.search(line) is None
