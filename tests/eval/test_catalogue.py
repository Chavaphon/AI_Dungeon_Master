"""The catalogue of ten illustrative failures (WBS 10.7): the labels each
turn holds, which turns may fill which slot, the draw, and what an entry shows.

Sampled turns are stand-ins with the attributes the catalogue reads; label
lines are hand-built in the format the annotation tool writes; D records carry
only the fields an entry shows. No test reads the logs or calls a model.

Run: pytest tests/eval/test_catalogue.py -v
"""

import copy
from types import SimpleNamespace

import pytest

from adm.eval import catalogue
from adm.eval.catalogue import SLOTS, CatalogueError, Mark

STATE = {
    "encounter_active": True,
    "round_number": 2,
    "active_combatant_id": "pc_lyra",
    "encounter_outcome": None,
    "combatants": {
        "pc_lyra": {
            "display_name": "Lyra",
            "faction": "party",
            "current_hp": 14,
            "max_hp": 20,
            "status": "active",
            "dodging": True,
            "spell_slots_1": 1,
        },
        "npc_rat_01": {
            "display_name": "giant rat",
            "faction": "hostile",
            "current_hp": 0,
            "max_hp": 11,
            "status": "unconscious",
            "dodging": False,
            "spell_slots_1": None,
        },
    },
    "inventory": {"pc_lyra": {"item_torch": 2, "item_rope": 0}},
    "item_definitions": {
        "item_torch": {"display_name": "torch"},
        "item_rope": {"display_name": "rope"},
    },
    "npc_relationships": {"npc_keeper": {"display_name": "the Keeper", "stance": "neutral"}},
    "quests": {
        "quest_ledger": {
            "display_name": "The Missing Ledger",
            "state": "active",
            "stage": 2,
            "max_stage": 3,
        }
    },
}
NARRATION = "You see a lantern. The rat is unhurt and the Keeper glares at you."


def at(word):
    start = NARRATION.index(word)
    return (start, start + len(word))


LANTERN, UNHURT, GLARES = at("lantern"), at("unhurt"), at("glares")


def candidate(category, check, span, confirmed=True):
    return {"check": check, "category": category, "span": span, "confirmed": confirmed}


def label(turn_id, candidates=(), added=(), annotator="SD"):
    return {
        "turn_id": turn_id,
        "annotator": annotator,
        "candidates": list(candidates),
        "added": [{"category": c, "phrase": "glares", "span": list(GLARES)} for c in added],
        "note": "",
        "draft": {"note": "drafted"},
    }


def record(condition, rid, input_index, **kw):
    return {
        "condition": condition,
        "run_id": rid,
        "scenario_id": "s01_cellar",
        "input_index": input_index,
        "turn_number": input_index + 1,
        "player_input": "I look around",
        "narration": NARRATION,
        "model_calls": [],
        "validation": [],
        "engine_steps": [],
        "turn_failure": None,
        **kw,
    }


def item(turn_id, condition):
    rec = record(condition, f"{condition}_s01_cellar_2001", 0)
    return SimpleNamespace(
        turn_id=turn_id,
        turn=SimpleNamespace(record=rec, narration=NARRATION, state=STATE),
    )


PHANTOM = candidate("PHANTOM", "entity_mention", list(LANTERN))
BAND = candidate("CONTRADICT", "hp_band", list(UNHURT))

# One labelled turn per M1 and M4 slot, in slot order.
TURNS = [
    ("a/1", "A", [PHANTOM], []),
    ("d/1", "D", [], ["PHANTOM"]),
    ("d/2", "D", [BAND], []),
    ("c/1", "C", [], ["CONTRADICT"]),
    ("b/1", "B", [], ["CONTRADICT"]),
    ("d/3", "D", [], ["RESOURCE"]),
    ("d/4", "D", [], ["RELATION"]),
    ("b/2", "B", [], ["RULE"]),
]


def d_logs():
    rid = "D_s02_toll_bridge_2001"
    failed = record(
        "D",
        rid,
        3,
        turn_failure="precondition",
        model_calls=[{"phase": "toolcall", "raw_output": '{"tool":  null}'}],
        validation=[{"ok": False, "rejection_code": "ENCOUNTER_OVER"}],
    )
    return {("D", "s02_toll_bridge", 2001): [record("D", rid, 2), failed]}


def build(turns=TURNS, second=None, logs=None, m3=None):
    items = [item(t, c) for t, c, _, _ in turns]
    lines = [label(t, cands, added) for t, _, cands, added in turns]
    logs = d_logs() if logs is None else logs
    m3 = {catalogue.m3_id("D_s02_toll_bridge_2001", 2): "WRONG_TOOL"} if m3 is None else m3
    return catalogue.build(items, lines, second or {}, logs, lambda key, at: STATE, "SD", m3)


def test_marks_are_confirmed_candidates_and_added_labels_in_narration_order() -> None:
    line = label(
        "t",
        [BAND, candidate("PHANTOM", "entity_mention", list(LANTERN), confirmed=False)],
        ["RELATION"],
    )
    found = catalogue.marks(line, NARRATION)
    assert found == [
        Mark("CONTRADICT", "unhurt", UNHURT, "hp_band"),
        Mark("RELATION", "glares", GLARES, "added"),
    ]


def test_eligibility_follows_condition_source_and_the_overlap() -> None:
    slot3 = SLOTS[2]  # CONTRADICT in D from the hp_band check
    band = [Mark("CONTRADICT", "unhurt", UNHURT, "hp_band")]
    added = [Mark("CONTRADICT", "unhurt", UNHURT, "added")]
    assert catalogue.eligible(slot3, "D", band, None)
    assert not catalogue.eligible(slot3, "A", band, None)
    assert not catalogue.eligible(slot3, "D", added, None)
    # in the overlap: kept only if the second annotator also found a CONTRADICT
    assert catalogue.eligible(slot3, "D", band, {"CONTRADICT"})
    assert not catalogue.eligible(slot3, "D", band, {"PHANTOM"})


def test_pick_takes_the_first_in_draw_order_not_used_before() -> None:
    slot = SLOTS[0]
    units = ["x", "y", "z"]
    order = sorted(units, key=lambda u: catalogue.draw_key(slot, u))
    assert catalogue.pick(slot, units, set()) == order[0]
    assert catalogue.pick(slot, units, {order[0]}) == order[1]
    assert catalogue.pick(slot, [], set()) is None


def test_every_slot_is_filled_by_its_own_turn() -> None:
    entries = build()
    assert [e.slot.number for e in entries] == list(range(1, 11))
    assert [e.run_id[0] for e in entries[:8]] == ["A", "D", "D", "C", "B", "D", "D", "B"]
    assert entries[8].input_index == 3 and entries[8].attempts[0].endswith("ENCOUNTER_OVER")
    assert entries[9].input_index == 2 and entries[9].verdict == "WRONG_TOOL"
    assert entries[0].note == "drafted"
    assert entries[0].snapshot_of.startswith("the state the turn is scored against")
    assert entries[8].snapshot_of == "the state the tool-call prompt saw"


def test_a_slot_with_no_eligible_turn_stops_the_draw() -> None:
    with pytest.raises(CatalogueError, match="slot 7"):
        build(turns=[t for t in TURNS if t[0] != "d/4"])
    # the RELATION turn is in the overlap, where the second annotator found none
    with pytest.raises(CatalogueError, match="slot 7"):
        build(second={"d/4": {"PHANTOM"}})


def test_m3_turns_missing_from_the_logs_stop_the_draw() -> None:
    with pytest.raises(CatalogueError, match="deadbeef"):
        build(m3={"deadbeef": "WRONG_TOOL"})


def test_attempts_and_facts_follow_the_record() -> None:
    rec = record(
        "D",
        "D_s01_cellar_2001",
        4,
        model_calls=[
            {"phase": "toolcall", "raw_output": '{"tool":\n "attack"}'},
            {"phase": "toolcall", "raw_output": "{}"},
            {"phase": "narration", "raw_output": NARRATION},
        ],
        validation=[
            {"ok": False, "rejection_code": "TARGET_UNCONSCIOUS"},
            {"ok": True, "narration_facts": {"who": "call"}},
        ],
        engine_steps=[
            {
                "step": "npc_action",
                "when": "after_call",
                "result": {"ok": True, "narration_facts": {"who": "after"}},
            },
            {"step": "initiative_advance", "when": "after_call"},
            {
                "step": "npc_action",
                "when": "before_call",
                "result": {"ok": True, "narration_facts": {"who": "before"}},
            },
        ],
    )
    assert catalogue.attempts(rec) == ('{"tool": "attack"} -> TARGET_UNCONSCIOUS', "{} -> ok")
    assert [f["who"] for f in catalogue.facts(rec)] == ["before", "call", "after"]


def test_snapshot_has_one_line_per_entity_with_qualified_ids() -> None:
    lines = catalogue.snapshot(STATE, "s01_cellar")
    assert lines[0] == "Encounter: active, round 2, `s01_cellar/pc_lyra` to act"
    assert (
        "`s01_cellar/pc_lyra` Lyra (party): 14/20 HP, wounded, active, dodging, 1 level-1 slots"
        in lines
    )
    assert "`s01_cellar/npc_rat_01` giant rat (hostile): 0/11 HP, unconscious, unconscious" in lines
    assert "Inventory of `s01_cellar/pc_lyra`: torch x2, rope x0" in lines
    assert "`s01_cellar/npc_keeper` the Keeper: neutral" in lines
    assert "`s01_cellar/quest_ledger` The Missing Ledger: active, stage 2 of 3" in lines
    over = {**copy.deepcopy(STATE), "encounter_active": False, "encounter_outcome": "victory"}
    assert (
        catalogue.snapshot(over, "s01_cellar")[0]
        == "Encounter: none active (last ended in victory)"
    )


def test_marked_bolds_each_span_and_skips_an_overlap() -> None:
    found = [
        Mark("PHANTOM", "lantern", LANTERN, "entity_mention"),
        Mark("PHANTOM", "a lantern", at("a lantern"), "added"),
        Mark("CONTRADICT", "unhurt", UNHURT, "hp_band"),
    ]
    assert catalogue.marked(NARRATION, found) == (
        "You see **a lantern**. The rat is **unhurt** and the Keeper glares at you."
    )


def test_render_shows_every_entry_with_its_snapshot() -> None:
    text = catalogue.render(build(), "ab" * 32)
    for slot in SLOTS:
        assert f"### {slot.number}. {slot.title}" in text
    assert "- `s01_cellar/quest_ledger` The Missing Ledger: active, stage 2 of 3" in text
    assert "**M3 verdict**" in text and "`WRONG_TOOL`" in text
    assert "Annotation note (AI draft, accepted by SD): drafted" in text
