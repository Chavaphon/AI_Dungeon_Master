"""The rule suite of CLAUDE.md section 13 (WBS 4.10, completed by WBS 4.17).

A rule-suite case is one test function marked `@pytest.mark.rule_suite("<area>")`,
written exactly so. A parametrized function is one case; its parameters are the
case's examples. The cases stay next to the rules they test, in the per-module
test files, and this module counts them per area against the section 13 table.

`NOT_YET_BUILT` names the areas whose rules are not written yet; they must have no
cases. WBS 4.10 covers the areas of WBS 4.1 to 4.9 that are built: 40 cases.
Dodge (4.6) and the areas of 4.11 to 4.16 add the other 20, and WBS 4.17 empties
`NOT_YET_BUILT`.

Run the suite alone: pytest -m rule_suite -v

These parse source files, as tests/test_boundaries.py does, so the count holds
whichever tests a run selects.
"""

import ast
from collections import Counter
from pathlib import Path

TESTS = Path(__file__).resolve().parents[1]
MARKER = "pytest.mark.rule_suite"

# CLAUDE.md section 13, in table order.
SECTION_13 = {
    "dice": 6,  # dice parsing and seeded reproducibility
    "abilities": 4,  # ability modifiers, including negatives and boundaries
    "initiative": 6,  # initiative, ordering, tie-breaks, round advance
    "attack": 8,  # hit, miss, natural 20, natural 1, critical damage
    "advantage": 5,  # advantage and disadvantage, including mutual cancellation
    "dodge": 4,  # application and expiry timing
    "spells": 7,  # Fire Bolt and Cure Wounds, the HP cap and slot exhaustion
    "zero_hp": 6,  # zero HP, unconscious, revival, encounter end
    "skill_checks": 5,  # at, above and below the DC
    "inventory": 3,  # inventory and quantity floors
    "relationships": 3,  # relationship ladder, one-step rule, justification
    "quests": 3,  # quest transitions, legal and illegal
}

# area -> the WBS task that builds its rules
NOT_YET_BUILT = {
    "dodge": "4.6",
    "spells": "4.11 to 4.13",
    "inventory": "4.14",
    "relationships": "4.15",
    "quests": "4.16",
}


def _cases() -> list[tuple[str, str]]:
    """Every `(area, "file::function")` marked as a rule-suite case under tests/."""
    cases = []
    for path in sorted(TESTS.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Call) and ast.unparse(decorator.func) == MARKER:
                    where = f"{path.relative_to(TESTS).as_posix()}::{node.name}"
                    args = decorator.args
                    assert len(args) == 1 and not decorator.keywords, f"{where}: one area"
                    assert isinstance(args[0], ast.Constant), f"{where}: area must be a literal"
                    cases.append((args[0].value, where))
    return cases


def test_section_13_table_has_60_cases() -> None:
    assert sum(SECTION_13.values()) == 60
    assert set(NOT_YET_BUILT) <= set(SECTION_13)


def test_every_case_names_a_section_13_area() -> None:
    unknown = [f"{where}: {area!r}" for area, where in _cases() if area not in SECTION_13]
    assert not unknown, "\n".join(unknown)


def test_every_case_is_a_test_function() -> None:
    bad = [where for _, where in _cases() if not where.split("::")[1].startswith("test_")]
    assert not bad, "\n".join(bad)


def test_each_built_area_has_its_section_13_count() -> None:
    counts = Counter(area for area, _ in _cases())
    expected = {area: 0 if area in NOT_YET_BUILT else n for area, n in SECTION_13.items()}
    actual = {area: counts[area] for area in SECTION_13}
    listing = "\n".join(f"{area}: {where}" for area, where in sorted(_cases()))
    assert actual == expected, listing
