"""Seeded RNG service and dice parser (WBS 4.2, CLAUDE.md section 4.2).

This is the only module that imports `random` (invariant 3). A run creates one
`DiceRoller` from its seed and passes it in explicitly; there is no module-level
RNG.

Each die is drawn from `random.random()` alone. Python guarantees that output
for a given seed across versions, but not that of `randint` or `randrange`.
CI runs Python 3.11 and members run newer versions, and a recorded run must
replay identically on all of them (invariant 4).
"""

from __future__ import annotations

import random
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict

AdvantageMode = Literal["normal", "advantage", "disadvantage"]

SUPPORTED_SIDES = frozenset({4, 6, 8, 10, 12, 20, 100})
MAX_DICE = 20

# ASCII digits only: `\d` would also match other scripts' digits.
_NOTATION = re.compile(r"([1-9][0-9]?)d([1-9][0-9]*)(?:([+-])([0-9]+))?")


class InvalidDiceNotation(ValueError):
    """Notation outside `XdY+Z` with X in 1..20 and Y a supported die."""


class DiceExpression(BaseModel):
    model_config = ConfigDict(frozen=True)

    count: int
    sides: int
    modifier: int

    @property
    def notation(self) -> str:
        """Canonical form: a zero modifier is omitted, a negative one written with `-`."""
        base = f"{self.count}d{self.sides}"
        return f"{base}{self.modifier:+d}" if self.modifier else base


def parse_notation(notation: str) -> DiceExpression:
    match = _NOTATION.fullmatch(notation)
    if match is None:
        raise InvalidDiceNotation(f"{notation!r} is not XdY+Z")
    count, sides = int(match[1]), int(match[2])
    if not 1 <= count <= MAX_DICE:
        raise InvalidDiceNotation(f"{notation!r}: X must be 1..{MAX_DICE}")
    if sides not in SUPPORTED_SIDES:
        raise InvalidDiceNotation(f"{notation!r}: Y must be one of {sorted(SUPPORTED_SIDES)}")
    modifier = int(match[4]) if match[4] else 0
    if match[3] == "-":
        modifier = -modifier
    return DiceExpression(count=count, sides=sides, modifier=modifier)


class RollResult(BaseModel):
    """One roll, as attached to the turn's audit record (`roll_result` in tools.schema.json)."""

    model_config = ConfigDict(frozen=True)

    notation: str
    individual_dice: list[int]
    modifier: int
    total: int
    advantage_mode: AdvantageMode

    def to_dict(self) -> dict[str, object]:
        return self.model_dump(mode="json")


class DiceRoller:
    """Wraps exactly one `random.Random(seed)`."""

    def __init__(self, seed: int) -> None:
        if type(seed) is not int:
            raise TypeError(f"seed must be an int, not {type(seed).__name__}")
        self._rng = random.Random(seed)

    def _die(self, sides: int) -> int:
        return int(self._rng.random() * sides) + 1

    def roll(self, notation: str, advantage_mode: AdvantageMode = "normal") -> RollResult:
        """Roll `notation`. Advantage and disadvantage apply only to `1d20+Z` (section 4.3):
        two d20 are rolled and both recorded, in order, and the higher or lower is kept."""
        expr = parse_notation(notation)
        if advantage_mode == "normal":
            dice = [self._die(expr.sides) for _ in range(expr.count)]
            kept = sum(dice)
        elif advantage_mode in ("advantage", "disadvantage"):
            if (expr.count, expr.sides) != (1, 20):
                raise ValueError(f"{advantage_mode} applies only to 1d20, not {notation!r}")
            dice = [self._die(20), self._die(20)]
            kept = max(dice) if advantage_mode == "advantage" else min(dice)
        else:
            raise ValueError(f"unknown advantage_mode {advantage_mode!r}")
        return RollResult(
            notation=expr.notation,
            individual_dice=dice,
            modifier=expr.modifier,
            total=kept + expr.modifier,
            advantage_mode=advantage_mode,
        )

    def roll_critical(self, notation: str) -> RollResult:
        """Roll critical damage (section 4.5): the dice twice, the modifier once.
        `1d8+3` is rolled and recorded as `2d8+3`. The doubled count may exceed 20."""
        expr = parse_notation(notation)
        doubled = DiceExpression(count=2 * expr.count, sides=expr.sides, modifier=expr.modifier)
        dice = [self._die(doubled.sides) for _ in range(doubled.count)]
        return RollResult(
            notation=doubled.notation,
            individual_dice=dice,
            modifier=doubled.modifier,
            total=sum(dice) + doubled.modifier,
            advantage_mode="normal",
        )
