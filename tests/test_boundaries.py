"""Static checks for the module boundaries in docs/conventions.md.

These parse source files; they import nothing from adm, so they hold even
while the packages are empty.
"""

import ast
from pathlib import Path

import pytest

ADM = Path(__file__).resolve().parents[1] / "adm"

# The one module allowed to import random (CLAUDE.md invariant 3).
DICE_MODULE = ADM / "engine" / "dice.py"

# package -> top-level modules it must never import
FORBIDDEN = {
    "engine": {"adm.orchestration", "adm.eval", "adm.cli", "httpx"},
    "orchestration": {"adm.eval", "adm.cli"},
    "eval": {"adm.orchestration", "adm.cli", "httpx"},
}


def _source_files(package: str | None = None) -> list[Path]:
    root = ADM / package if package else ADM
    return sorted(root.rglob("*.py"))


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.add(node.module)
    return modules


def _matches(module: str, banned: str) -> bool:
    return module == banned or module.startswith(banned + ".")


def test_package_layout_exists() -> None:
    for package in ("engine", "orchestration", "eval"):
        assert (ADM / package / "__init__.py").is_file()


@pytest.mark.parametrize("package", sorted(FORBIDDEN))
def test_package_respects_import_boundaries(package: str) -> None:
    violations = [
        f"{path.relative_to(ADM.parent)} imports {module}"
        for path in _source_files(package)
        for module in _imported_modules(path)
        for banned in FORBIDDEN[package]
        if _matches(module, banned)
    ]
    assert not violations, "\n".join(violations)


def test_random_only_imported_by_dice_module() -> None:
    violations = [
        f"{path.relative_to(ADM.parent)} imports {module}"
        for path in _source_files()
        if path != DICE_MODULE
        for module in _imported_modules(path)
        if _matches(module, "random") or _matches(module, "numpy.random")
    ]
    assert not violations, "\n".join(violations)
