"""Action hints in beginner mode (WBS 13.7, #257): two to four things the player
could type, worked out from the state, in a fixed order, that the validator
would accept at that moment and that never touch the dice or the model.

Run: pytest tests/play/test_hints.py -v
"""

import random
from collections.abc import Iterator
from functools import cache
from pathlib import Path
from typing import Any

import pytest

from adm.engine.dice import DiceRoller
from adm.engine.replay import replay_script
from adm.engine.scenario import Scenario, initial_state, load_scenario
from adm.engine.state import GameState, state_hash
from adm.engine.validator import Rejection, validate
from adm.play.hints import MAX_HINTS, MIN_HINTS, TITLE, hint_block, hints
from adm.play.vocabulary import JARGON

ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = sorted((ROOT / "scenarios").glob("*.json"))
SEEDS = (2001, 2002, 2003)
S01 = load_scenario(ROOT / "scenarios" / "s01_cellar.json")
SEED = 12345


def _states(scenario: Scenario, seed: int) -> Iterator[GameState]:
    """Every state a scripted session shows the player before an input: the
    opening state, then the state after each scripted input (a failed turn
    leaves it as it was)."""
    yield initial_state(scenario, seed)
    for turn in replay_script(scenario, seed):
        yield GameState.from_dict(turn.state)


@cache
def _all_states() -> list[tuple[str, GameState]]:
    """Every scripted session's states, labelled; replayed once per test run."""
    found = []
    for path in SCENARIOS:
        scenario = load_scenario(path)
        for seed in SEEDS:
            for n, state in enumerate(_states(scenario, seed)):
                found.append((f"{scenario.scenario_id}/{seed}/{n}", state))
    return found


def _edit(**changes: Any) -> GameState:
    """s01's opening state with top-level fields and `combatants`/`inventory`
    entries changed."""
    data = initial_state(S01, SEED).to_dict()
    for key, value in changes.items():
        if key in ("combatants", "inventory"):
            for cid, fields in value.items():
                if key == "combatants":
                    data[key][cid].update(fields)
                else:
                    data[key][cid] = fields
        else:
            data[key] = value
    return GameState.from_dict(data)


def _fight(**changes: Any) -> GameState:
    """s01 in its fight, on Lyra's turn."""
    return _edit(
        encounter_active=True,
        round_number=1,
        initiative_order=["npc_rat_01", "pc_lyra", "npc_rat_02"],
        active_combatant_id="pc_lyra",
        **changes,
    )


def _texts(state: GameState) -> list[str]:
    return [h.text for h in hints(state)]


# --- the acceptance criteria ------------------------------------------------------


def test_hints_are_legal_in_every_state_of_every_scripted_session() -> None:
    """The acceptance of #257: across every scripted session (16 scenarios, the
    main grid's three seeds), every hint's call is one the validator accepts in
    the state it was shown in, and the hints are 2 to 4, plain words, and the
    same every time."""
    seen: set[str] = set()
    for where, state in _all_states():
        before = state_hash(state)
        found = hints(state)
        assert state_hash(state) == before, f"{where}: hints changed the state"
        assert hints(state) == found, f"{where}: not deterministic"
        pc = next(c for c in state.combatants.values() if c.is_player_character)
        if pc.status == "active":
            assert MIN_HINTS <= len(found) <= MAX_HINTS, (where, found)
        else:
            assert found == [], f"{where}: a knocked-out player gets no hints"
        for hint in found:
            verdict = validate(state, hint.call)
            assert not isinstance(verdict, Rejection), (where, hint, verdict)
            assert JARGON.search(hint.text) is None, (where, hint.text)
            seen.add(" ".join(hint.text.split()[:2]))
    # The sessions reach every kind of hint, so the check above covers them all.
    assert {
        "look around",
        "talk to",
        "use your",
        "attack the",
        "cast Fire",
        "cast Cure",
        "dodge",
    } <= seen


DICE = ("random", "randint", "randrange", "choice", "shuffle", "seed")


def test_hints_never_touch_the_dice(monkeypatch: pytest.MonkeyPatch) -> None:
    """The acceptance of #257: hints never roll a die or draw a random number."""
    states = [state for _, state in _all_states()]

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("hints touched the dice")

    monkeypatch.setattr(DiceRoller, "_die", forbidden)
    for name in DICE:
        monkeypatch.setattr(random.Random, name, forbidden)
        monkeypatch.setattr(random, name, forbidden)
    assert all(hints(state) is not None for state in states)


# --- what the hints are ---------------------------------------------------------


def test_outside_a_fight_look_talk_and_use() -> None:
    assert _texts(initial_state(S01, SEED)) == [
        "look around",
        "talk to the Keeper",
        "use your torch",
    ]


def test_outside_a_fight_with_nobody_and_nothing_padded_with_sneak() -> None:
    data = initial_state(S01, SEED).to_dict()
    data["npc_relationships"] = {}
    data["inventory"]["pc_lyra"] = {"item_short_sword": 1}
    assert _texts(GameState.from_dict(data)) == ["look around", "sneak ahead quietly"]


def test_a_used_up_item_is_not_suggested() -> None:
    state = _edit(inventory={"pc_lyra": {"item_short_sword": 1, "item_torch": 0}})
    assert "use your torch" not in _texts(state)


def test_in_a_fight_attack_fire_bolt_cure_and_dodge_in_that_order() -> None:
    state = _fight(combatants={"pc_lyra": {"current_hp": 9}})
    assert _texts(state) == [
        "attack the giant rat 1 with your short sword",
        "cast Fire Bolt at the giant rat 1",
        "cast Cure Wounds on yourself",
        "dodge",
    ]
    block = hint_block(state)
    assert block is not None and block.splitlines()[0] == TITLE


def test_a_knocked_out_enemy_is_not_suggested() -> None:
    state = _fight(combatants={"npc_rat_01": {"current_hp": 0, "status": "unconscious"}})
    assert _texts(state)[0] == "attack the giant rat 2 with your short sword"
    assert not any("giant rat 1" in t for t in _texts(state))


def test_no_cure_wounds_when_nobody_is_hurt_or_no_charge_is_left() -> None:
    assert not any("Cure Wounds" in t for t in _texts(_fight()))
    spent = _fight(combatants={"pc_lyra": {"current_hp": 9, "spell_slots_1": 0}})
    assert not any("Cure Wounds" in t for t in _texts(spent))


def test_a_non_caster_without_a_weapon_dodges_or_looks() -> None:
    state = _fight(
        combatants={
            "pc_lyra": {
                "spell_attack_bonus": None,
                "spellcasting_modifier": None,
                "spell_slots_1": None,
            }
        },
        inventory={"pc_lyra": {"item_torch": 2}},
    )
    assert _texts(state) == ["dodge", "look around"]


def test_a_knocked_out_player_gets_no_hints() -> None:
    state = _edit(
        combatants={"pc_lyra": {"current_hp": 0, "status": "unconscious"}},
        encounter_outcome="defeat",
        round_number=2,
    )
    assert hints(state) == [] and hint_block(state) is None
