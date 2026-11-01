"""The rule suite of CLAUDE.md section 13 (WBS 4.10, completed by WBS 4.17).

A rule-suite case is one test function marked `@pytest.mark.rule_suite("<area>")`,
written exactly so. A parametrized function is one case; its parameters are the
case's examples. The cases stay next to the rules they test, in the per-module
test files, and this module counts them per area against the section 13 table.

The suite is complete: every area has its section 13 count, 60 in all. A case may
not be skipped or expected to fail, so that 60 cases counted are 60 cases passed.
docs/rule_suite.md, the Objective 1 evidence, lists the 60 and must agree with the
markers.

Run the suite alone: pytest -m rule_suite -v

These parse source files, as tests/test_boundaries.py does, so the count holds
whichever tests a run selects.
"""

import ast
import re
from collections import Counter
from pathlib import Path

TESTS = Path(__file__).resolve().parents[1]
EVIDENCE = TESTS.parent / "docs" / "rule_suite.md"
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

# What would let a case count without passing.
NOT_PASSING = re.compile(r"pytest\.(mark\.)?(skip|skipif|xfail|importorskip)\b")


def _case_nodes() -> list[tuple[str, str, ast.Module, ast.FunctionDef]]:
    """Every `(area, "file::function", module, function)` marked as a rule-suite case."""
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
                    cases.append((args[0].value, where, tree, node))
    return cases


def _cases() -> list[tuple[str, str]]:
    """Every `(area, "file::function")` marked as a rule-suite case under tests/."""
    return [(area, where) for area, where, _, _ in _case_nodes()]


def _evidence_rows() -> list[tuple[str, str]]:
    """The `(area, "file::function")` rows of the case table in docs/rule_suite.md."""
    text = EVIDENCE.read_text(encoding="utf-8")
    block = text.split("<!-- cases:start -->")[1].split("<!-- cases:end -->")[0]
    rows = []
    for line in block.strip().splitlines()[2:]:
        area, case = (cell.strip().strip("`") for cell in line.strip().strip("|").split("|")[:2])
        rows.append((area, case.removeprefix("tests/")))
    return rows


def test_section_13_table_has_60_cases() -> None:
    assert sum(SECTION_13.values()) == 60


def test_every_case_names_a_section_13_area() -> None:
    unknown = [f"{where}: {area!r}" for area, where in _cases() if area not in SECTION_13]
    assert not unknown, "\n".join(unknown)


def test_every_case_is_a_test_function() -> None:
    bad = [where for _, where in _cases() if not where.split("::")[1].startswith("test_")]
    assert not bad, "\n".join(bad)


def test_each_area_has_its_section_13_count() -> None:
    counts = Counter(area for area, _ in _cases())
    actual = {area: counts[area] for area in SECTION_13}
    listing = "\n".join(f"{area}: {where}" for area, where in sorted(_cases()))
    assert actual == SECTION_13, listing


def test_no_case_is_skipped_or_expected_to_fail() -> None:
    bad = []
    for _, where, tree, node in _case_nodes():
        module_marks = [
            ast.unparse(statement)
            for statement in tree.body
            if isinstance(statement, ast.Assign)
            and any(ast.unparse(target) == "pytestmark" for target in statement.targets)
        ]
        if NOT_PASSING.search(ast.unparse(node)) or any(map(NOT_PASSING.search, module_marks)):
            bad.append(where)
    assert not bad, "\n".join(bad)


def test_evidence_lists_exactly_the_marked_cases() -> None:
    assert sorted(_evidence_rows()) == sorted(_cases())
