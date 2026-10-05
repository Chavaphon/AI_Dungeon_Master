"""Frozen model configuration (WBS 3.6): config/model.json holds the values in
CLAUDE.md section 2.2, and the model name appears nowhere in the code.

No test calls the model.

Run: pytest tests/test_model_config.py -v
"""

import json
import re
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "model.json"

EXPECTED_KEYS = {
    "model",
    "model_digest",
    "quantisation",
    "ollama_version",
    "context_tokens",
    "K_verbatim_turns",
    "temperature",
    "narration_max_tokens",
    "toolcall_max_tokens",
    "seed",
}


@pytest.fixture(scope="module")
def config() -> dict[str, Any]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def test_config_has_exactly_the_specified_keys(config: dict[str, Any]) -> None:
    assert set(config) == EXPECTED_KEYS


def test_no_placeholder_left(config: dict[str, Any]) -> None:
    assert not [key for key, value in config.items() if "TBD" in str(value)]


def test_frozen_values(config: dict[str, Any]) -> None:
    assert config["context_tokens"] == 8192
    assert config["K_verbatim_turns"] == 8
    assert config["temperature"] == 0.7
    assert config["narration_max_tokens"] == 300
    assert config["toolcall_max_tokens"] == 200
    # null means the run's seed is sent to Ollama (docs/decisions.md, WBS 3.6).
    assert config["seed"] is None


def test_model_is_pinned_by_digest(config: dict[str, Any]) -> None:
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", config["model_digest"])
    assert re.fullmatch(r"\d+\.\d+\.\d+", config["ollama_version"])


def test_model_name_is_not_hardcoded(config: dict[str, Any]) -> None:
    """CLAUDE.md section 2.2: the name lives in config/model.json and nowhere else."""
    hits = [
        str(path.relative_to(ROOT))
        for path in sorted((ROOT / "adm").rglob("*.py"))
        if config["model"] in path.read_text(encoding="utf-8")
    ]
    assert hits == []
