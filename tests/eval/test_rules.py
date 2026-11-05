"""Rule violations, M4 (WBS 8.9): runs across all four conditions, the
done-when of #87.

M4 has two parts (CLAUDE.md section 10.3 item 6, docs/decisions.md
2026-11-05). The state audit finds negative or over-maximum hit points, slots
and quantities below zero, out-of-turn actions and combat with no encounter in
a turn's state and engine actions; it is zero on every scenario's ground truth
and fires on a broken state. The narration check finds the same rule breaks
described in prose, given what the turn did.

Run: pytest tests/eval/test_rules.py -v
"""

import copy
from pathlib import Path

import pytest

from adm.engine.replay import replay_script
from adm.engine.scenario import initial_state, load_scenario
from adm.eval.rules import acts, narrated_violations, state_violations

ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = sorted((ROOT / "scenarios").glob("*.json"))
CELLAR = load_scenario(ROOT / "scenarios" / "s01_cellar.json")
SEED = 2001
TRUTH = replay_script(CELLAR, SEED)


def _turn(index: int) -> tuple[dict, dict, dict | None, list]:
    turn = TRUTH[index]
    before = TRUTH[index - 1].state if index else initial_state(CELLAR, SEED).to_dict()
    return turn.state, before, turn.executed_call, turn.engine_steps


def _narrated(index: int, narration: str) -> list[tuple[str, str, str]]:
    found = narrated_violations(narration, *_turn(index))
    return [(c.kind, c.mention, c.confidence) for c in found]


def _attack(attacker: str, target: str = "pc_lyra") -> dict:
    weapon = "item_short_sword" if attacker == "pc_lyra" else "item_rat_bite"
    args = {"attacker_id": attacker, "target_id": target, "weapon_id": weapon}
    return {"tool": "attack", "arguments": args}


def _fight() -> dict:
    """The cellar mid-fight, Lyra active; the second rat renamed so each rat has
    a name of its own."""
    state = copy.deepcopy(CELLAR.initial_state)
    state.update(
        encounter_active=True,
        initiative_order=["pc_lyra", "npc_rat_01", "npc_rat_02"],
        active_combatant_id="pc_lyra",
        round_number=1,
    )
    state["combatants"]["npc_rat_02"]["display_name"] = "cave spider"
    return state


# --- the state audit --------------------------------------------------------------


@pytest.mark.parametrize("path", SCENARIOS, ids=lambda p: p.stem)
def test_the_ground_truth_of_every_scenario_breaks_no_rule(path: Path) -> None:
    scenario = load_scenario(path)
    for seed in (2001, 2002, 2003):
        before = initial_state(scenario, seed).to_dict()
        for turn in replay_script(scenario, seed):
            assert state_violations(turn.state, before, turn.executed_call, turn.engine_steps) == []
            before = turn.state


def test_a_broken_state_is_audited() -> None:
    state = copy.deepcopy(CELLAR.initial_state)
    state["combatants"]["npc_rat_01"]["current_hp"] = -2
    state["combatants"]["npc_rat_02"]["current_hp"] = 99
    state["combatants"]["pc_lyra"]["spell_slots_1"] = -1
    state["inventory"]["pc_lyra"]["item_torch"] = -1
    found = state_violations(state, state, None, [])
    assert [(c.kind, c.subject) for c in found] == [
        ("negative_hp", ("npc_rat_01",)),
        ("hp_above_max", ("npc_rat_02",)),
        ("slot_below_zero", ("pc_lyra",)),
        ("negative_quantity", ("pc_lyra",)),
    ]
    assert {(c.check, c.confidence, c.start, c.end, c.sentence) for c in found} == {
        ("state_audit", "high", 0, 0, "")
    }


def test_an_action_out_of_turn_or_with_no_encounter_is_audited() -> None:
    fight = _fight()
    step = {"step": "npc_action", "when": "after_call", "call": _attack("npc_rat_01")}
    # The rat acts while Lyra is still active: no initiative_advance before it.
    found = state_violations(fight, fight, _attack("pc_lyra", "npc_rat_01"), [step])
    assert [(c.kind, c.subject) for c in found] == [("out_of_turn", ("npc_rat_01",))]

    calm = copy.deepcopy(CELLAR.initial_state)
    found = state_violations(calm, calm, _attack("pc_lyra", "npc_rat_01"), [])
    assert [(c.kind, c.subject) for c in found] == [("after_encounter_end", ("pc_lyra",))]


def test_cure_wounds_with_no_encounter_is_legal() -> None:
    calm = copy.deepcopy(CELLAR.initial_state)
    args = {"caster_id": "pc_lyra", "spell_id": "spell_cure_wounds", "target_id": "pc_lyra"}
    assert state_violations(calm, calm, {"tool": "cast_spell", "arguments": args}, []) == []


def test_acts_follow_initiative_through_the_engine_steps() -> None:
    # The first attack: the encounter starts, the second rat goes first, Lyra
    # drops the first rat, and its turn is skipped back round to the second.
    state, before, call, steps = _turn(3)
    assert [(a.actor, a.active, a.encounter) for a in acts(before, call, steps)] == [
        ("npc_rat_02", "npc_rat_02", True),
        ("pc_lyra", "pc_lyra", True),
        ("npc_rat_02", "npc_rat_02", True),
    ]


# --- the narration ----------------------------------------------------------------


def test_an_attack_narrated_after_the_encounter_ended_is_a_violation() -> None:
    assert TRUTH[9].state["encounter_outcome"] == "victory"
    assert _narrated(10, "The giant rat lunges at you from the shadows.") == [
        ("after_encounter_end", "rat lunges", "high")
    ]
    # The player character may be doing what the input asked: low.
    assert _narrated(10, "You swing your sword at the rat.") == [
        ("after_encounter_end", "You swing", "low")
    ]
    assert _narrated(10, "The rat does not attack.") == []


def test_an_attack_before_the_first_encounter_is_not_scored() -> None:
    assert _narrated(2, "The rat attacks you.") == []


def test_a_combatant_narrated_attacking_when_it_did_not_act_is_out_of_turn() -> None:
    fight = _fight()
    steps = [{"step": "npc_action", "when": "after_call", "call": _attack("npc_rat_01")}]
    call = _attack("pc_lyra", "npc_rat_01")
    narration = "You strike the rat. The rat bites back, and the cave spider lunges."
    found = narrated_violations(narration, fight, fight, call, steps)
    assert [(c.kind, c.mention, c.subject) for c in found] == [
        ("out_of_turn", "spider lunges", ("npc_rat_02",))
    ]


def test_a_rejected_turn_has_no_attacks_at_all() -> None:
    assert TRUTH[5].turn_failure == "precondition"
    assert _narrated(5, "The giant rat lunges, but you strike it.") == [
        ("out_of_turn", "rat lunges", "high"),
        ("out_of_turn", "you strike", "low"),
    ]


def test_cure_wounds_with_no_slot_left_is_a_violation() -> None:
    state = copy.deepcopy(CELLAR.initial_state)
    empty = copy.deepcopy(state)
    empty["combatants"]["pc_lyra"]["spell_slots_1"] = 0

    def found(narration: str, before: dict) -> list[tuple[str, str]]:
        return [
            (c.mention, c.confidence)
            for c in narrated_violations(narration, before, before, None, [])
        ]

    assert found("You cast Cure Wounds and the cut closes.", empty) == [("Cure Wounds", "high")]
    assert found("A healing spell knits your wounds.", empty) == [("healing spell", "low")]
    assert found("You cannot cast Cure Wounds again.", empty) == []
    assert found("You cast Cure Wounds and the cut closes.", state) == []


@pytest.mark.parametrize(
    ("narration", "flagged"),
    [
        ("You have -3 hit points.", True),
        ("The rat is at negative hit points.", True),
        ("You sink below zero hp.", True),
        ("You have 3 hit points.", False),
        ("The rat loses 3 hit points.", False),
    ],
)
def test_narrated_negative_hit_points(narration: str, flagged: bool) -> None:
    kinds = [k for k, _, _ in _narrated(12, narration)]
    assert kinds == (["negative_hp"] if flagged else [])
