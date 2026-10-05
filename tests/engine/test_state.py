"""Core state types and load/save (WBS 4.1): a state file round-trips without loss.

The examples in schemas/examples/ are the fixtures. The audit-log example's
state_before_hash was computed from the raw mid-combat example, so matching it
proves the typed model loses nothing that the hash covers.

Run: pytest tests/engine/test_state.py -v
"""

import json
from pathlib import Path
from typing import Any

import pytest

from adm.engine.state import (
    GameState,
    StateValidationError,
    canonical_json,
    load_state,
    save_state,
    state_hash,
)

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES_DIR = ROOT / "schemas" / "examples"
EXAMPLES = sorted(EXAMPLES_DIR.glob("state_*.json"))
MID_COMBAT = EXAMPLES_DIR / "state_02_mid_combat.json"


def _raw(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.stem)
def test_load_then_dump_equals_the_file(path: Path) -> None:
    assert load_state(path).to_dict() == _raw(path)


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.stem)
def test_save_then_load_round_trips(path: Path, tmp_path: Path) -> None:
    state = load_state(path)
    out = tmp_path / "state.json"
    save_state(state, out)
    assert load_state(out) == state
    assert _raw(out) == _raw(path)


def test_save_is_byte_stable(tmp_path: Path) -> None:
    first, second = tmp_path / "a.json", tmp_path / "b.json"
    save_state(load_state(MID_COMBAT), first)
    save_state(load_state(first), second)
    assert first.read_bytes() == second.read_bytes()


def test_hash_matches_the_audit_log_example() -> None:
    record = _raw(EXAMPLES_DIR / "audit_turn_valid.json")
    assert state_hash(load_state(MID_COMBAT)) == record["state_before_hash"]


def test_canonical_json_is_the_conventions_serialisation() -> None:
    state = load_state(MID_COMBAT)
    expected = json.dumps(
        _raw(MID_COMBAT), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    assert canonical_json(state) == expected


def test_typed_access() -> None:
    state = load_state(MID_COMBAT)
    lyra = state.combatants["pc_lyra"]
    assert lyra.abilities.str_ == 12
    assert lyra.abilities.int_ == 10
    assert state.combatants["npc_rat_01"].spell_slots_1 is None
    assert state.item_definitions["item_torch"].attack_bonus is None
    assert state.npc_relationships["npc_keeper"].history[0].from_ == "unfriendly"


def test_load_rejects_a_schema_invalid_file(tmp_path: Path) -> None:
    raw = _raw(MID_COMBAT)
    raw["combatants"]["pc_lyra"]["current_hp"] = -1
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(StateValidationError, match="current_hp"):
        load_state(bad)


def test_load_rejects_an_unknown_key(tmp_path: Path) -> None:
    raw = _raw(MID_COMBAT)
    raw["location"] = "cellar"
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(StateValidationError):
        load_state(bad)


def test_save_refuses_an_invalid_state_and_writes_nothing(tmp_path: Path) -> None:
    state = load_state(MID_COMBAT)
    state.combatants["pc_lyra"].status = "unconscious"  # still at 14 HP
    out = tmp_path / "state.json"
    with pytest.raises(StateValidationError):
        save_state(state, out)
    assert not out.exists()


def test_from_dict_does_not_coerce_types() -> None:
    raw = _raw(MID_COMBAT)
    raw["combatants"]["pc_lyra"]["current_hp"] = "14"
    with pytest.raises(StateValidationError):
        GameState.from_dict(raw)
