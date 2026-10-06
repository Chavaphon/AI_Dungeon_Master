"""Seeded RNG service and dice parser (WBS 4.2): an identical seed reproduces an
identical sequence, and only the XdY+Z notation of CLAUDE.md section 4.2 parses.

Run: pytest tests/engine/test_dice.py -v
"""

import json
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from adm.engine.dice import DiceExpression, DiceRoller, InvalidDiceNotation, parse_notation

ROOT = Path(__file__).resolve().parents[2]
SIDES = (4, 6, 8, 10, 12, 20, 100)

_SCHEMAS = [
    json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))
    for name in ("state.schema.json", "tools.schema.json")
]
_REGISTRY = Registry().with_resources((s["$id"], Resource.from_contents(s)) for s in _SCHEMAS)
ROLL_VALIDATOR = Draft202012Validator(
    {"$ref": _SCHEMAS[1]["$id"] + "#/$defs/roll_result"}, registry=_REGISTRY
)


# --- parser ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("notation", "expected"),
    [
        ("1d20", DiceExpression(count=1, sides=20, modifier=0)),
        ("1d6+3", DiceExpression(count=1, sides=6, modifier=3)),
        ("2d8-1", DiceExpression(count=2, sides=8, modifier=-1)),
        ("20d100+0", DiceExpression(count=20, sides=100, modifier=0)),
        ("1d4-12", DiceExpression(count=1, sides=4, modifier=-12)),
    ],
)
def test_parse_valid(notation: str, expected: DiceExpression) -> None:
    assert parse_notation(notation) == expected


@pytest.mark.parametrize(
    "notation",
    [
        "",
        "d20",  # X is required
        "0d6",  # X below 1
        "21d6",  # X above 20
        "01d6",  # leading zero
        "1d7",  # unsupported die
        "1d0",
        "1d2",
        "1D20",  # uppercase
        "1d20+",  # sign without a number
        "1d20+-3",
        "1d20 + 3",  # whitespace
        " 1d20",
        "1d20\n",
        "1d20+3+2",
        "1d20*2",
        "2x6",
        "1d٢0",  # non-ASCII digit
    ],
)
def test_parse_rejects(notation: str) -> None:
    with pytest.raises(InvalidDiceNotation):
        parse_notation(notation)


@pytest.mark.parametrize("notation", ["1d20+0", "1d20-0"])
def test_zero_modifier_writes_without_sign(notation: str) -> None:
    assert parse_notation(notation).notation == "1d20"


def test_negative_modifier_writes_with_minus() -> None:
    assert parse_notation("2d8-1").notation == "2d8-1"


# --- reproducibility -------------------------------------------------------


def _sequence(seed: int) -> list[int]:
    roller = DiceRoller(seed)
    return [roller.roll(f"1d{sides}").total for sides in SIDES * 20]


def test_identical_seed_reproduces_identical_sequence() -> None:
    assert _sequence(12345) == _sequence(12345)


def test_different_seeds_differ() -> None:
    assert _sequence(12345) != _sequence(12346)


def test_golden_sequence_is_pinned() -> None:
    # Pins the seed -> dice mapping, so a change in how dice are drawn (or a
    # Python version that draws them differently) fails here instead of
    # silently breaking replays of runs already recorded.
    roller = DiceRoller(12345)
    assert [roller.roll("1d20").total for _ in range(10)] == GOLDEN_D20_12345


GOLDEN_D20_12345 = [9, 1, 17, 6, 8, 4, 12, 4, 3, 9]


def test_rollers_with_the_same_seed_are_independent() -> None:
    first, second = DiceRoller(7), DiceRoller(7)
    a = first.roll("1d20")
    first.roll("1d20")
    assert second.roll("1d20") == a


def test_seed_must_be_an_int() -> None:
    with pytest.raises(TypeError):
        DiceRoller("12345")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        DiceRoller(True)


# --- roll results ----------------------------------------------------------


@given(
    seed=st.integers(),
    count=st.integers(min_value=1, max_value=20),
    sides=st.sampled_from(SIDES),
    modifier=st.integers(min_value=-50, max_value=50),
)
def test_roll_is_in_range_and_adds_up(seed: int, count: int, sides: int, modifier: int) -> None:
    notation = f"{count}d{sides}{modifier:+d}"
    result = DiceRoller(seed).roll(notation)
    assert len(result.individual_dice) == count
    assert all(1 <= die <= sides for die in result.individual_dice)
    assert result.modifier == modifier
    assert result.total == sum(result.individual_dice) + modifier
    assert result.advantage_mode == "normal"


def test_every_face_comes_up() -> None:
    roller = DiceRoller(1)
    for sides in SIDES:
        faces = {roller.roll(f"1d{sides}").total for _ in range(sides * 60)}
        assert faces == set(range(1, sides + 1)), sides


def test_result_records_canonical_notation() -> None:
    assert DiceRoller(1).roll("1d6+0").notation == "1d6"


@pytest.mark.parametrize(("mode", "pick"), [("advantage", max), ("disadvantage", min)])
def test_advantage_rolls_two_d20_and_keeps_one(mode: str, pick: object) -> None:
    roller = DiceRoller(99)
    for _ in range(200):
        result = roller.roll("1d20+5", advantage_mode=mode)
        assert len(result.individual_dice) == 2
        assert result.total == pick(result.individual_dice) + 5  # type: ignore[operator]
        assert result.notation == "1d20+5"
        assert result.advantage_mode == mode


def test_advantage_dice_are_recorded_in_the_order_rolled() -> None:
    plain, advantaged = DiceRoller(3), DiceRoller(3)
    first, second = plain.roll("1d20").total, plain.roll("1d20").total
    assert advantaged.roll("1d20", advantage_mode="advantage").individual_dice == [first, second]


@pytest.mark.parametrize("notation", ["2d20", "1d6", "1d8+3"])
def test_advantage_only_applies_to_a_single_d20(notation: str) -> None:
    with pytest.raises(ValueError, match="1d20"):
        DiceRoller(1).roll(notation, advantage_mode="advantage")


def test_unknown_advantage_mode_is_an_error() -> None:
    with pytest.raises(ValueError):
        DiceRoller(1).roll("1d20", advantage_mode="both")  # type: ignore[arg-type]


def test_invalid_notation_raises_from_roll() -> None:
    with pytest.raises(InvalidDiceNotation):
        DiceRoller(1).roll("1d7")


@pytest.mark.parametrize(
    ("notation", "mode"),
    [("1d20+5", "normal"), ("1d20-1", "advantage"), ("1d20", "disadvantage"), ("20d100", "normal")],
)
def test_result_matches_the_tool_contract_schema(notation: str, mode: str) -> None:
    result = DiceRoller(5).roll(notation, advantage_mode=mode)  # type: ignore[arg-type]
    errors = [e.message for e in ROLL_VALIDATOR.iter_errors(result.to_dict())]
    assert errors == []
