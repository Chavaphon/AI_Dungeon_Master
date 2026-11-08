"""Divergence rubric (WBS 8.1, 8.2, 8.12): the hit-point band table in docs/rubric.md
section 5.6 agrees with `hp_band`, the one definition the engine and the checker
share, the settled 14-of-20 rule is written down, and the rubric is still the
v1.0 frozen at gate G3 (git tag `rubric-v1.0`).

A failure of `test_rubric_v1_0_is_frozen` means the frozen rubric changed. That
needs a docs/decisions.md entry and the new hash here, in the same pull request.

Run: pytest tests/test_rubric.py -v
"""

import hashlib
import re
from pathlib import Path

import pytest

from adm.engine.combat import hp_band

ROOT = Path(__file__).resolve().parents[1]
RUBRIC = (ROOT / "docs" / "rubric.md").read_text(encoding="utf-8")
BANDS = ("healthy", "wounded", "badly_hurt", "unconscious")

# sha256 of docs/rubric.md v1.0 with LF line endings (WBS 8.12, decision log 2026-11-08).
RUBRIC_V1_0_SHA256 = "f447eab3fefc5912894c8a8e9927c23069d322c81bd792d036e97d2254d6af0d"


def _table_rows() -> dict[int, list[str]]:
    block = RUBRIC.split("<!-- band-table:start -->")[1].split("<!-- band-table:end -->")[0]
    rows = {}
    for line in block.strip().splitlines()[2:]:
        cells = [c.strip() for c in line.strip("|").split("|")]
        rows[int(cells[0])] = cells[1:]
    return rows


def _expand(cell: str) -> list[int]:
    low, _, high = cell.partition("–")
    return list(range(int(low), int(high or low) + 1))


ROWS = _table_rows()


def test_table_covers_4_to_30() -> None:
    assert sorted(ROWS) == list(range(4, 31))


@pytest.mark.parametrize("max_hp", sorted(ROWS))
def test_table_row_matches_hp_band(max_hp: int) -> None:
    from_table = {
        hp: band for band, cell in zip(BANDS, ROWS[max_hp], strict=True) for hp in _expand(cell)
    }
    assert from_table == {hp: hp_band(hp, max_hp) for hp in range(max_hp + 1)}


def test_14_of_20_is_settled_as_wounded() -> None:
    assert hp_band(14, 20) == "wounded"
    assert re.search(r"14 of 20 HP is `wounded`", RUBRIC)


def test_rubric_v1_0_is_frozen() -> None:
    assert RUBRIC.startswith("# Divergence rubric v1.0\n")
    assert hashlib.sha256(RUBRIC.encode("utf-8")).hexdigest() == RUBRIC_V1_0_SHA256
