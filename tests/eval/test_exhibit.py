"""The side-by-side A versus D exhibit (WBS 10.8): which inputs pair up, the
two rows' rules, the draw, and what each side shows.

Sampled turns are stand-ins with the attributes the exhibit reads; label lines
are hand-built in the format the annotation tool writes. No test reads the
logs or calls a model. The slide test needs matplotlib (the `analysis` extra)
and is skipped without it.

Run: pytest tests/eval/test_exhibit.py -v
"""

from types import SimpleNamespace

import pytest

from adm.eval import exhibit
from adm.eval.catalogue import Mark
from adm.eval.exhibit import ROWS, ExhibitError

NARRATION = "The rat falls dead at your feet."
DEAD = (NARRATION.index("falls dead"), NARRATION.index("falls dead") + len("falls dead"))
ATTACK = {
    "tool": "attack",
    "arguments": {"attacker_id": "pc_lyra", "target_id": "npc_rat_01", "weapon_id": "item_sword"},
}
FACTS = {
    "attacker": "Lyra",
    "weapon": "short sword",
    "target": "giant rat",
    "hit": True,
    "critical": False,
    "attack_roll": 17,
    "target_ac": 12,
    "target_hp_before": 11,
    "target_hp_after": 4,
    "target_hp_max": 11,
    "target_hp_band": "wounded",
    "target_status": "active",
}
STATE = {
    "combatants": {
        "npc_rat_01": {
            "display_name": "giant rat",
            "current_hp": 4,
            "max_hp": 11,
            "status": "active",
        },
        "pc_lyra": {"display_name": "Lyra", "current_hp": 20, "max_hp": 20, "status": "active"},
    }
}
M1_REPORT = {
    "conditions": {
        "A": {"turns": 535, "rate": {"value": 55.9}},
        "D": {"turns": 519, "rate": {"value": 57.4}},
    },
    "h1": {"ratio": 1.03, "interval": [0.74, 1.48]},
}


def scenario(tools):
    return SimpleNamespace(
        scripted_inputs=[SimpleNamespace(expected_call={"tool": t} if t else None) for t in tools]
    )


def turn(condition, index, call=ATTACK, seed=2001, sid="s01_cellar"):
    record = {
        "condition": condition,
        "run_id": f"{condition}_{sid}_{seed}",
        "scenario_id": sid,
        "seed": seed,
        "input_index": index,
        "player_input": f"input {index}",
        "model_calls": [{"phase": "toolcall", "raw_output": "{}"}],
        "validation": [{"ok": True, "narration_facts": FACTS}],
        "engine_steps": [],
    }
    return SimpleNamespace(
        turn_id=f"{condition}/{index}",
        turn=SimpleNamespace(record=record, narration=NARRATION, state=STATE, call=call),
    )


def line(turn_id, added=()):
    return {
        "turn_id": turn_id,
        "annotator": "SD",
        "candidates": [],
        "added": [{"category": c, "phrase": "falls dead", "span": list(DEAD)} for c in added],
    }


def build(labels, tools=("attack", "attack", "attack"), d_calls=None):
    """Turns for A and D at each input, labelled from `labels[(cond, index)]`."""
    items, lines = [], []
    for i in range(len(tools)):
        for c in ("A", "D"):
            call = (d_calls or {}).get(i, ATTACK) if c == "D" else ATTACK
            items.append(turn(c, i, call))
            lines.append(line(f"{c}/{i}", labels.get((c, i), ())))
    return exhibit.pairs(items, lines, "SD", {"s01_cellar": scenario(tools)})


def test_only_combat_inputs_where_d_used_the_same_tool_pair_up() -> None:
    dodge = {"tool": "dodge", "arguments": {"actor_id": "pc_lyra"}}
    got = build({}, tools=("attack", None, "skill_check", "attack"), d_calls={3: dodge})
    assert [p.input_index for p in got] == [0]
    assert got[0].player_input == "input 0" and got[0].a.run_id.startswith("A_")


def test_an_input_whose_d_turn_was_not_narrated_has_no_pair() -> None:
    items = [turn("A", 0)]
    lines = [line("A/0")]
    assert exhibit.pairs(items, lines, "SD", {"s01_cellar": scenario(["attack"])}) == []


def test_the_rows_follow_their_rules() -> None:
    fixes, does_not = ROWS
    got = build({("A", 0): ["CONTRADICT"], ("D", 1): ["CONTRADICT"], ("A", 2): ["PHANTOM"]})
    assert [fixes.test(p) for p in got] == [True, False, False]
    assert [does_not.test(p) for p in got] == [False, True, False]
    rule_only = build({("A", 0): ["RULE"]})[0]
    assert fixes.test(rule_only)
    d_phantom = build({("A", 0): ["RULE"], ("D", 0): ["PHANTOM"]})[0]
    assert not fixes.test(d_phantom)  # D must have no label at all


def test_the_draw_takes_the_first_in_hash_order_on_different_inputs() -> None:
    got = build({(c, i): ["CONTRADICT"] for c in ("A", "D") for i in range(3)})
    with pytest.raises(ExhibitError, match="row 1"):
        exhibit.draw(got)  # D has a label everywhere, so row 1 has no pair
    got = build({("A", i): ["CONTRADICT"] for i in range(3)} | {("D", 0): ["CONTRADICT"]})
    rows = exhibit.draw(got)
    fixes_pool = [p for p in got if ROWS[0].test(p)]
    first = sorted(fixes_pool, key=lambda p: exhibit.draw_key(ROWS[0], p))[0]
    assert rows[0][1] is first and rows[0][2] == 2
    assert rows[1][1].input_index == 0 and rows[1][1].unit != rows[0][1].unit


def test_each_side_shows_its_truth_and_d_its_facts() -> None:
    p = build({})[0]
    assert exhibit.named(p) == ["npc_rat_01", "pc_lyra"]
    assert exhibit.brief(STATE, ["npc_rat_01"]) == ["giant rat: 4/11 HP, wounded, active"]
    assert exhibit.fact_line(FACTS) == (
        "Lyra's short sword hits giant rat (roll 17 vs AC 12): 11 to 4 of 11 HP, wounded, active"
    )
    miss = {**FACTS, "hit": False, "weapon": None, "spell": "fire bolt", "caster": "Lyra"}
    assert exhibit.fact_line(miss).startswith("Lyra's fire bolt misses giant rat")


def test_segments_bold_each_labelled_span() -> None:
    marks = (Mark("CONTRADICT", "falls dead", DEAD, "added"),)
    assert exhibit.segments(NARRATION, marks) == [
        ("The rat ", False),
        ("falls dead", True),
        (" at your feet.", False),
    ]


def test_the_measured_result_is_on_the_slide_text() -> None:
    text = exhibit.measured(M1_REPORT)
    assert "A 55.9 and D 57.4" in text and "D/A 1.03, 95% interval 0.74 to 1.48" in text
    assert "H1 (D/A at most 0.5) is not supported" in text


def test_the_slide_is_written_and_a_second_run_gives_the_same_bytes(tmp_path) -> None:
    pytest.importorskip("matplotlib")
    got = build({("A", 0): ["CONTRADICT"], ("D", 1): ["CONTRADICT"]})
    rows = exhibit.draw(got)
    one = exhibit.write_slide(rows, M1_REPORT, tmp_path / "one")
    two = exhibit.write_slide(rows, M1_REPORT, tmp_path / "two")
    assert [p.name for p in one] == ["fig_a_vs_d.png", "fig_a_vs_d.svg"]
    for a, b in zip(one, two, strict=True):
        assert a.read_bytes() == b.read_bytes()
    assert b"\r\n" not in one[1].read_bytes()
    block = exhibit.render(rows, M1_REPORT, one)
    assert "### Row 1. What the engine fixes" in block and "**falls dead**" in block
