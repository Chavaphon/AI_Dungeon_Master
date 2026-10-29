"""The state preconditions of the tool-call validator (WBS 5.2, docs/tool_contract.md).

`REJECTS` has a case for every ticked cell of the tool x code matrix in
docs/tool_contract.md section 3, and the coverage tests hold it to the matrix and
to the 19 codes of the schema: every rejection code is reachable by a test. The
order tests check the fixed validation order of section 1, the accept tests the
calls the rules allow, and a property test that every call the validator accepts
executes through the dispatch table without the engine's own guards raising.

The states are the three examples in schemas/examples/, some changed in one place.

Run: pytest tests/engine/test_preconditions.py -v
"""

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from adm.engine.dice import DiceRoller
from adm.engine.npc import NpcCall, take_npc_turn
from adm.engine.state import GameState, load_state, state_hash
from adm.engine.tools import dispatch
from adm.engine.validator import (
    NO_ENCOUNTER_TOOLS,
    Rejection,
    ToolCall,
    tool_arguments,
    tool_names,
    validate,
)

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
CODES = _SCHEMAS[1]["$defs"]["rejection_code"]["enum"]

Edit = Callable[[GameState], None]


# --- states ------------------------------------------------------------------
# exploring:    no encounter yet. Lyra (caster, 2 slots) holds a short sword and
#               2 torches; each rat holds a rat bite. The Keeper is unfriendly and
#               the quest not started.
# mid_combat:   order npc_rat_01, pc_lyra, npc_rat_02; Lyra is active. npc_rat_02
#               is Dodging. The Keeper is neutral and the quest active at 2 of 3.
# after_victory: no encounter; both rats unconscious. Lyra has 1 slot. The
#               Keeper is friendly and the quest completed.

STATES = {
    "exploring": "state_01_exploration.json",
    "mid_combat": "state_02_mid_combat.json",
    "after_victory": "state_03_after_victory.json",
}
COMBATANTS = ["npc_rat_01", "npc_rat_02", "pc_lyra"]
ITEMS = ["item_rat_bite", "item_short_sword", "item_torch"]


def example_state(name: str, *edits: Edit) -> GameState:
    state = load_state(EXAMPLES / STATES[name])
    for edit in edits:
        edit(state)
    return state


def knocked_out(combatant_id: str) -> Edit:
    def edit(state: GameState) -> None:
        state.combatants[combatant_id].current_hp = 0
        state.combatants[combatant_id].status = "unconscious"

    return edit


def slots(n: int) -> Edit:
    def edit(state: GameState) -> None:
        state.combatants["pc_lyra"].spell_slots_1 = n

    return edit


def holding(owner: str, item_id: str, n: int) -> Edit:
    def edit(state: GameState) -> None:
        state.inventory[owner][item_id] = n

    return edit


def stance(value: Any) -> Edit:
    def edit(state: GameState) -> None:
        state.npc_relationships["npc_keeper"].stance = value

    return edit


def quest_stage(n: int) -> Edit:
    def edit(state: GameState) -> None:
        state.quests["quest_missing_ledger"].stage = n

    return edit


# --- calls -------------------------------------------------------------------


def atk(attacker: str = "pc_lyra", target: str = "npc_rat_01", weapon: str = "item_short_sword"):
    return {
        "tool": "attack",
        "arguments": {"attacker_id": attacker, "target_id": target, "weapon_id": weapon},
    }


def cast(caster: str = "pc_lyra", spell: str = "spell_fire_bolt", target: str = "npc_rat_01"):
    return {
        "tool": "cast_spell",
        "arguments": {"caster_id": caster, "spell_id": spell, "target_id": target},
    }


def cure(caster: str = "pc_lyra", target: str = "pc_lyra"):
    return cast(caster, "spell_cure_wounds", target)


def dodge_call(actor: str = "pc_lyra"):
    return {"tool": "dodge", "arguments": {"actor_id": actor}}


def check(actor: str = "pc_lyra", skill: str = "perception", dc: int = 12):
    return {"tool": "skill_check", "arguments": {"actor_id": actor, "skill": skill, "dc": dc}}


def inv(actor: str = "pc_lyra", item: str = "item_torch", delta: int = -1):
    return {
        "tool": "modify_inventory",
        "arguments": {"actor_id": actor, "item_id": item, "delta": delta},
    }


def rel(npc: str = "npc_keeper", direction: str = "up", why: str = "Lyra paid off the debt."):
    return {
        "tool": "update_npc_relationship",
        "arguments": {"npc_id": npc, "direction": direction, "justification": why},
    }


def quest(quest_id: str = "quest_missing_ledger", transition: str = "advance"):
    return {"tool": "update_quest", "arguments": {"quest_id": quest_id, "transition": transition}}


CALLS = {
    "attack": atk,
    "cast_spell": cast,
    "dodge": dodge_call,
    "skill_check": check,
    "modify_inventory": inv,
    "update_npc_relationship": rel,
    "update_quest": quest,
}


def _extra_argument(tool: str) -> dict[str, Any]:
    call = CALLS[tool]()
    call["arguments"]["reason"] = "because"
    return call


# --- the matrix cases --------------------------------------------------------

NO_ENCOUNTER = {"tool": NO_ENCOUNTER_TOOLS, "spell_id": ["spell_cure_wounds"]}

# case id -> (code, state, edits, call, valid_options)
REJECTS: dict[str, tuple[str, str, tuple[Edit, ...], dict[str, Any], dict[str, list[Any]]]] = {
    **{
        f"{tool}_schema_violation": (
            "SCHEMA_VIOLATION",
            "mid_combat",
            (),
            _extra_argument(tool),
            {"arguments": list(tool_arguments(tool)["properties"])},
        )
        for tool in CALLS
    },
    # step 2: existence
    "attack_unknown_target": (
        "UNKNOWN_ENTITY",
        "mid_combat",
        (),
        atk(target="npc_rat_03"),
        {"target_id": COMBATANTS},
    ),
    "attack_unknown_attacker": (
        "UNKNOWN_ENTITY",
        "mid_combat",
        (),
        atk(attacker="pc_bob"),
        {"attacker_id": COMBATANTS},
    ),
    "attack_unknown_weapon": (
        "UNKNOWN_ENTITY",
        "mid_combat",
        (),
        atk(weapon="item_axe"),
        {"weapon_id": ["item_short_sword"]},
    ),
    "cast_spell_unknown_caster": (
        "UNKNOWN_ENTITY",
        "mid_combat",
        (),
        cast(caster="pc_bob"),
        {"caster_id": COMBATANTS},
    ),
    "dodge_unknown_actor": (
        "UNKNOWN_ENTITY",
        "mid_combat",
        (),
        dodge_call("npc_rat_03"),
        {"actor_id": COMBATANTS},
    ),
    "skill_check_unknown_actor": (
        "UNKNOWN_ENTITY",
        "exploring",
        (),
        check("npc_ghost"),
        {"actor_id": COMBATANTS},
    ),
    "modify_inventory_unknown_owner": (
        "UNKNOWN_ENTITY",
        "exploring",
        (),
        inv("npc_ghost"),
        {"actor_id": COMBATANTS},
    ),
    "relationship_unknown_npc": (
        "UNKNOWN_ENTITY",
        "exploring",
        (),
        rel("npc_baker"),
        {"npc_id": ["npc_keeper"]},
    ),
    "item_not_defined": (
        "ITEM_NOT_DEFINED",
        "exploring",
        (),
        inv(item="item_lantern", delta=1),
        {"item_id": ITEMS},
    ),
    "unknown_quest": (
        "UNKNOWN_QUEST",
        "exploring",
        (),
        quest("quest_dragon", "start"),
        {"quest_id": ["quest_missing_ledger"]},
    ),
    "spell_not_supported": (
        "SPELL_NOT_SUPPORTED",
        "mid_combat",
        (),
        cast(spell="spell_fireball"),
        {"spell_id": ["spell_fire_bolt", "spell_cure_wounds"]},
    ),
    # step 3: argument values
    "skill_not_supported": (
        "SKILL_NOT_SUPPORTED",
        "exploring",
        (),
        check(skill="athletics"),
        {"skill": ["strength", "perception", "stealth"]},
    ),
    "dc_above_range": ("DC_OUT_OF_RANGE", "exploring", (), check(dc=40), {"dc": [5, 25]}),
    "dc_below_range": ("DC_OUT_OF_RANGE", "exploring", (), check(dc=4), {"dc": [5, 25]}),
    "dc_just_above_range": ("DC_OUT_OF_RANGE", "exploring", (), check(dc=26), {"dc": [5, 25]}),
    "missing_justification": ("MISSING_JUSTIFICATION", "exploring", (), rel(why="ok"), {}),
    "justification_of_9": ("MISSING_JUSTIFICATION", "exploring", (), rel(why="x" * 9), {}),
    # step 4: encounter
    "attack_before_any_encounter": ("ENCOUNTER_OVER", "exploring", (), atk(), NO_ENCOUNTER),
    "attack_after_victory": (
        "ENCOUNTER_OVER",
        "after_victory",
        (),
        atk(target="pc_lyra"),
        NO_ENCOUNTER,
    ),
    "fire_bolt_outside_encounter": ("ENCOUNTER_OVER", "exploring", (), cast(), NO_ENCOUNTER),
    "dodge_outside_encounter": ("ENCOUNTER_OVER", "after_victory", (), dodge_call(), NO_ENCOUNTER),
    "attack_out_of_turn": (
        "NOT_YOUR_TURN",
        "mid_combat",
        (),
        atk("npc_rat_02", "pc_lyra", "item_rat_bite"),
        {"attacker_id": ["pc_lyra"]},
    ),
    "cast_spell_out_of_turn": (
        "NOT_YOUR_TURN",
        "mid_combat",
        (),
        cure("npc_rat_02", "npc_rat_02"),
        {"caster_id": ["pc_lyra"]},
    ),
    "dodge_out_of_turn": (
        "NOT_YOUR_TURN",
        "mid_combat",
        (),
        dodge_call("npc_rat_01"),
        {"actor_id": ["pc_lyra"]},
    ),
    "skill_check_out_of_turn": (
        "NOT_YOUR_TURN",
        "mid_combat",
        (),
        check("npc_rat_02"),
        {"actor_id": ["pc_lyra"]},
    ),
    "modify_inventory_out_of_turn": (
        "NOT_YOUR_TURN",
        "mid_combat",
        (),
        inv("npc_rat_02", "item_rat_bite", -1),
        {"actor_id": ["pc_lyra"]},
    ),
    # step 5: actor. In play the active combatant is always conscious, so an
    # unconscious attacker or dodger needs a hand-built state.
    "attack_by_unconscious_actor": (
        "ACTOR_UNCONSCIOUS",
        "mid_combat",
        (knocked_out("pc_lyra"),),
        atk(),
        {"attacker_id": ["pc_lyra"]},
    ),
    "dodge_by_unconscious_actor": (
        "ACTOR_UNCONSCIOUS",
        "mid_combat",
        (knocked_out("pc_lyra"),),
        dodge_call(),
        {"actor_id": ["pc_lyra"]},
    ),
    "cure_wounds_by_unconscious_caster": (
        "ACTOR_UNCONSCIOUS",
        "after_victory",
        (),
        cure("npc_rat_01", "npc_rat_01"),
        {"caster_id": ["pc_lyra"]},
    ),
    "skill_check_by_unconscious_actor": (
        "ACTOR_UNCONSCIOUS",
        "after_victory",
        (),
        check("npc_rat_02"),
        {"actor_id": ["pc_lyra"]},
    ),
    "not_a_caster": (
        "NOT_A_CASTER",
        "exploring",
        (),
        cure("npc_rat_01", "npc_rat_01"),
        {"caster_id": ["pc_lyra"]},
    ),
    "no_spell_slot": (
        "NO_SPELL_SLOT",
        "mid_combat",
        (slots(0),),
        cure(),
        {"spell_id": ["spell_fire_bolt"]},
    ),
    "not_a_weapon": (
        "NOT_A_WEAPON",
        "mid_combat",
        (),
        atk(weapon="item_torch"),
        {"weapon_id": ["item_short_sword"]},
    ),
    "weapon_never_held": (
        "WEAPON_NOT_IN_INVENTORY",
        "mid_combat",
        (),
        atk(weapon="item_rat_bite"),
        {"weapon_id": ["item_short_sword"]},
    ),
    "weapon_held_at_zero": (
        "WEAPON_NOT_IN_INVENTORY",
        "mid_combat",
        (holding("pc_lyra", "item_short_sword", 0),),
        atk(),
        {"weapon_id": []},
    ),
    # step 6: target and effect
    "attack_unconscious_target": (
        "TARGET_UNCONSCIOUS",
        "mid_combat",
        (knocked_out("npc_rat_01"),),
        atk(),
        {"target_id": ["npc_rat_02"]},
    ),
    "fire_bolt_unconscious_target": (
        "TARGET_UNCONSCIOUS",
        "mid_combat",
        (knocked_out("npc_rat_01"),),
        cast(),
        {"target_id": ["npc_rat_02"]},
    ),
    "negative_quantity": (
        "NEGATIVE_QUANTITY",
        "exploring",
        (),
        inv(delta=-3),
        {"delta": [-2]},
    ),
    "negative_quantity_of_nothing_held": (
        "NEGATIVE_QUANTITY",
        "exploring",
        (),
        inv(item="item_rat_bite"),
        {},
    ),
    "relationship_up_from_allied": (
        "RELATIONSHIP_STEP_TOO_LARGE",
        "exploring",
        (stance("allied"),),
        rel(direction="up"),
        {"direction": ["down"]},
    ),
    "relationship_down_from_hostile": (
        "RELATIONSHIP_STEP_TOO_LARGE",
        "exploring",
        (stance("hostile"),),
        rel(direction="down"),
        {"direction": ["up"]},
    ),
    "complete_a_quest_not_started": (
        "ILLEGAL_QUEST_TRANSITION",
        "exploring",
        (),
        quest(transition="complete"),
        {"transition": ["start"]},
    ),
    "advance_at_max_stage": (
        "ILLEGAL_QUEST_TRANSITION",
        "mid_combat",
        (quest_stage(3),),
        quest(transition="advance"),
        {"transition": ["complete", "fail"]},
    ),
    "advance_a_completed_quest": (
        "ILLEGAL_QUEST_TRANSITION",
        "after_victory",
        (),
        quest(transition="advance"),
        {"transition": []},
    ),
}


def _rejected(state: GameState, call: Any) -> Rejection:
    before = state_hash(state)
    result = validate(state, call)
    assert isinstance(result, Rejection), f"accepted {call}"
    assert state_hash(state) == before, "the validator changed the state"
    RESULT_VALIDATOR.validate(result.to_dict())
    return result


def _accepted(state: GameState, call: Any) -> ToolCall:
    before = state_hash(state)
    result = validate(state, call)
    assert isinstance(result, ToolCall), result
    assert state_hash(state) == before, "the validator changed the state"
    return result


@pytest.mark.parametrize("code,name,edits,call,valid_options", REJECTS.values(), ids=REJECTS)
def test_each_precondition_is_rejected_with_its_code(
    code: str, name: str, edits: tuple[Edit, ...], call: dict[str, Any], valid_options: Any
) -> None:
    rejection = _rejected(example_state(name, *edits), call)
    assert rejection.rejection_code == code, rejection.message
    assert rejection.tool == call["tool"]
    assert rejection.valid_options == valid_options


# --- coverage: every code, every matrix cell ---------------------------------


def _matrix() -> set[tuple[str, str]]:
    """The ticked `(tool, code)` cells of docs/tool_contract.md section 3."""
    text = (ROOT / "docs" / "tool_contract.md").read_text(encoding="utf-8")
    section = text.split("## 3.", 1)[1].split("\n## ", 1)[0]
    header = re.search(r"^\| Code \|(.+)\|$", section, flags=re.MULTILINE)
    assert header is not None
    tools = [cell.strip() for cell in header.group(1).split("|")]
    cells = set()
    for code, row in re.findall(r"^\| `([A-Z_]+)` \|(.+)\|$", section, flags=re.MULTILINE):
        marks = [cell.strip() for cell in row.split("|")]
        assert len(marks) == len(tools), code
        cells |= {(tool, code) for tool, mark in zip(tools, marks, strict=True) if mark == "✓"}
    return cells


def test_the_matrix_has_every_tool() -> None:
    assert {tool for tool, _ in _matrix()} == set(tool_names())


def test_every_rejection_code_is_reachable() -> None:
    assert len(CODES) == 19
    assert {code for code, *_ in REJECTS.values()} == set(CODES)


def test_every_matrix_cell_is_reachable() -> None:
    reached = {(call["tool"], code) for code, _, _, call, _ in REJECTS.values()}
    assert reached == _matrix()


def test_the_example_rejection_is_reproduced() -> None:
    state = example_state("mid_combat", knocked_out("npc_rat_01"))
    expected = json.loads(
        (EXAMPLES / "result_rejected_target_unconscious.json").read_text(encoding="utf-8")
    )
    assert _rejected(state, atk()).to_dict() == expected


# --- messages ----------------------------------------------------------------


MESSAGES = {
    "attack_unknown_target": "target_id npc_rat_03 is not a combatant in the current state.",
    "dc_above_range": "dc 40 is outside 5..25.",
    "missing_justification": "justification must be at least 10 characters, got 2.",
    "attack_after_victory": (
        "No encounter is active, so attack cannot be used. The last encounter ended in victory."
    ),
    "fire_bolt_outside_encounter": "No encounter is active, so spell_fire_bolt cannot be cast.",
    "attack_out_of_turn": "It is pc_lyra's turn, not npc_rat_02's.",
    "no_spell_slot": ("pc_lyra has 0 level-1 spell slots left, and spell_cure_wounds needs one."),
    "negative_quantity": "pc_lyra holds 2 of item_torch; delta -3 would leave -1.",
    "relationship_up_from_allied": (
        "npc_keeper is already allied, the end of the ladder; its stance cannot move up."
    ),
    "advance_at_max_stage": ("quest_missing_ledger is active at stage 3 of 3; it cannot advance."),
}


@pytest.mark.parametrize("case,message", MESSAGES.items(), ids=MESSAGES)
def test_messages_name_the_state_values(case: str, message: str) -> None:
    _, name, edits, call, _ = REJECTS[case]
    assert _rejected(example_state(name, *edits), call).message == message


# --- the validation order ----------------------------------------------------


def test_the_shape_is_checked_before_the_state() -> None:
    call = atk(target="npc_rat_03")
    call["arguments"]["weapon_id"] = 5
    assert _rejected(example_state("exploring"), call).rejection_code == "SCHEMA_VIOLATION"


def test_existence_comes_before_the_turn() -> None:
    call = atk("npc_rat_02", "npc_rat_03", "item_rat_bite")
    rejection = _rejected(example_state("mid_combat"), call)
    assert rejection.rejection_code == "UNKNOWN_ENTITY"
    assert "target_id" in rejection.valid_options


def test_arguments_in_a_step_go_in_signature_order() -> None:
    state = example_state("mid_combat")
    rejection = _rejected(state, cast("pc_bob", "spell_fireball", "npc_ghost"))
    assert rejection.valid_options == {"caster_id": COMBATANTS}
    rejection = _rejected(state, cast("pc_lyra", "spell_fireball", "npc_ghost"))
    assert rejection.rejection_code == "SPELL_NOT_SUPPORTED"


def test_argument_values_come_before_the_turn() -> None:
    rejection = _rejected(example_state("mid_combat"), check("npc_rat_02", "athletics", 40))
    assert rejection.rejection_code == "SKILL_NOT_SUPPORTED"
    rejection = _rejected(example_state("mid_combat"), check("npc_rat_02", "stealth", 40))
    assert rejection.rejection_code == "DC_OUT_OF_RANGE"


def test_the_encounter_comes_before_the_actor_and_target() -> None:
    state = example_state("after_victory")
    rejection = _rejected(state, atk("npc_rat_01", "npc_rat_02", "item_torch"))
    assert rejection.rejection_code == "ENCOUNTER_OVER"


def test_the_turn_comes_before_the_actor() -> None:
    state = example_state("mid_combat", knocked_out("npc_rat_02"))
    rejection = _rejected(state, dodge_call("npc_rat_02"))
    assert rejection.rejection_code == "NOT_YOUR_TURN"


def test_the_actor_comes_before_the_target() -> None:
    state = example_state("mid_combat", knocked_out("npc_rat_01"))
    assert _rejected(state, atk(weapon="item_torch")).rejection_code == "NOT_A_WEAPON"
    state = example_state("mid_combat", knocked_out("npc_rat_01"))
    state.combatants["pc_lyra"].spell_attack_bonus = None
    state.combatants["pc_lyra"].spellcasting_modifier = None
    state.combatants["pc_lyra"].spell_slots_1 = None
    assert _rejected(state, cast()).rejection_code == "NOT_A_CASTER"


def test_a_non_weapon_is_named_before_it_is_looked_for() -> None:
    state = example_state("mid_combat", holding("pc_lyra", "item_torch", 0))
    assert _rejected(state, atk(weapon="item_torch")).rejection_code == "NOT_A_WEAPON"


# --- calls the rules allow ---------------------------------------------------


@pytest.mark.parametrize("tool", tool_names())
def test_the_example_calls_pass_mid_combat(tool: str) -> None:
    call = json.loads((EXAMPLES / f"toolcall_{tool}.json").read_text(encoding="utf-8"))
    assert _accepted(example_state("mid_combat"), call) == ToolCall(**call)


def test_the_null_tool_passes() -> None:
    accepted = _accepted(example_state("mid_combat"), {"tool": None})
    assert accepted == ToolCall(tool=None, arguments={})


@pytest.mark.parametrize(
    "name,edits,call",
    [
        ("after_victory", (), cure()),  # Cure Wounds needs no encounter
        ("after_victory", (), cure(target="npc_rat_01")),  # and revives
        ("mid_combat", (knocked_out("npc_rat_01"),), cure(target="npc_rat_01")),
        ("exploring", (), cure()),  # at full HP: the slot is still spent
        ("mid_combat", (), atk(target="pc_lyra")),  # attacking yourself
        ("mid_combat", (), cast(target="pc_lyra")),
        ("mid_combat", (), atk(target="npc_rat_02")),  # Dodging is no bar
        ("exploring", (), check(dc=5)),
        ("exploring", (), check(dc=25)),
        ("after_victory", (), check()),
        ("after_victory", (), inv("npc_rat_01", "item_rat_bite", -1)),  # an unconscious owner
        ("exploring", (), inv(item="item_rat_bite", delta=1)),  # a new item
        ("exploring", (), inv(delta=-2)),  # down to exactly 0
        ("exploring", (), rel(why="x" * 10)),
        ("mid_combat", (), rel(direction="down")),  # no turn check
        ("mid_combat", (), quest(transition="fail")),
        ("mid_combat", (quest_stage(3),), quest(transition="complete")),
        ("exploring", (), quest(transition="start")),
    ],
)
def test_legal_calls_pass(name: str, edits: tuple[Edit, ...], call: dict[str, Any]) -> None:
    _accepted(example_state(name, *edits), call)


def test_an_ally_can_be_attacked() -> None:
    state = example_state("mid_combat")
    state.combatants["npc_rat_02"].faction = "party"
    _accepted(state, atk(target="npc_rat_02"))


def test_relationship_and_quest_changes_ignore_the_turn() -> None:
    state = example_state("mid_combat")
    state.active_combatant_id = "npc_rat_02"
    _accepted(state, rel())
    _accepted(state, quest())
    assert _rejected(state, check()).rejection_code == "NOT_YOUR_TURN"


# --- the NPC policy goes through the validator -------------------------------


def test_an_illegal_npc_call_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    state = example_state("mid_combat", knocked_out("pc_lyra"))
    state.active_combatant_id = "npc_rat_02"
    bad = NpcCall(
        tool="attack",
        arguments={
            "attacker_id": "npc_rat_02",
            "target_id": "pc_lyra",
            "weapon_id": "item_rat_bite",
        },
    )
    monkeypatch.setattr("adm.engine.npc.choose_action", lambda state, npc_id: bad)
    before = state_hash(state)
    with pytest.raises(ValueError, match="TARGET_UNCONSCIOUS"):
        take_npc_turn(state, DiceRoller(1), "after_call")
    assert state_hash(state) == before


# --- agreement with the engine -----------------------------------------------

VARIANTS: list[tuple[str, tuple[Edit, ...]]] = [
    ("exploring", ()),
    ("exploring", (stance("allied"),)),
    ("exploring", (stance("hostile"),)),
    ("mid_combat", ()),
    ("mid_combat", (knocked_out("npc_rat_01"),)),
    ("mid_combat", (slots(0), quest_stage(3))),
    ("mid_combat", (holding("pc_lyra", "item_short_sword", 0),)),
    ("after_victory", ()),
]


_ids = st.sampled_from([*COMBATANTS, "npc_ghost"])
_items = st.sampled_from([*ITEMS, "item_ledger", "item_lantern"])
_arguments = {
    "attack": {"attacker_id": _ids, "target_id": _ids, "weapon_id": _items},
    "cast_spell": {
        "caster_id": _ids,
        "spell_id": st.sampled_from(["spell_fire_bolt", "spell_cure_wounds", "spell_fireball"]),
        "target_id": _ids,
    },
    "dodge": {"actor_id": _ids},
    "skill_check": {
        "actor_id": _ids,
        "skill": st.sampled_from(["strength", "perception", "stealth", "athletics"]),
        "dc": st.integers(0, 30),
    },
    "modify_inventory": {
        "actor_id": _ids,
        "item_id": _items,
        "delta": st.integers(-4, 4).filter(bool),
    },
    "update_npc_relationship": {
        "npc_id": st.sampled_from(["npc_keeper", "npc_baker"]),
        "direction": st.sampled_from(["up", "down"]),
        "justification": st.sampled_from(["", "x" * 9, "x" * 10, "She paid the debt."]),
    },
    "update_quest": {
        "quest_id": st.sampled_from(["quest_missing_ledger", "quest_dragon"]),
        "transition": st.sampled_from(["start", "advance", "complete", "fail"]),
    },
}
any_call = st.sampled_from(sorted(_arguments)).flatmap(
    lambda tool: st.fixed_dictionaries(
        {"tool": st.just(tool), "arguments": st.fixed_dictionaries(_arguments[tool])}
    )
)


@settings(max_examples=600, deadline=None)
@given(variant=st.sampled_from(VARIANTS), call=any_call)
def test_every_accepted_call_executes(
    variant: tuple[str, tuple[Edit, ...]], call: dict[str, Any]
) -> None:
    """A call the validator accepts never trips the engine's own guards, and
    leaves a state the schema accepts with HP in range (invariant 5). It runs
    through the dispatch table of adm/engine/tools.py."""
    state = example_state(variant[0], *variant[1])
    result = validate(state, call)
    if isinstance(result, Rejection):
        RESULT_VALIDATOR.validate(result.to_dict())
        return
    entry = dispatch(state, DiceRoller(state.seed), call)
    assert entry["ok"] and entry["tool"] == call["tool"]
    GameState.from_dict(state.to_dict())
    for c in state.combatants.values():
        assert 0 <= c.current_hp <= c.max_hp
        assert (c.status == "unconscious") == (c.current_hp == 0)
    assert all(n >= 0 for items in state.inventory.values() for n in items.values())
