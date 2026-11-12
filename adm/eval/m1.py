"""The M1 annotation sample and its turns (WBS 9.5, 9.6; CLAUDE.md section 10.4).

    python -m adm.eval.annotate m1 --annotator SD
    python -m adm.eval.annotate m1 --annotator SS --overlap

**The sample** (`draw_runs`) is whole runs, because the M1 bootstrap resamples
whole runs and RQ2 needs every turn of the long sessions (CLAUDE.md section
10.5). For each scenario, one seed is chosen: of the seeds that have a log in
all four conditions, the first in the order of `sha256("m1-v1/{scenario_id}/{seed}")`.
All four conditions are taken at that seed, so the conditions of a scenario
share their dice and scripted inputs. On the main grid that is 16 scenarios x 4
conditions = 64 runs. The draw is fixed with no RNG, as in `adm/eval/annotate.py`.

**The overlap** (`overlap_runs`) is the part a second annotator scores for
Krippendorff's alpha (9.6): per condition, the first `ceil(0.2 * n)` of the
sampled runs in the order of `sha256("m1-v1/overlap/{run_id}")`. On the main
grid that is 4 runs per condition, 16 in all.

**The order** (`annotator_order`) is per annotator: runs in the order of
`sha256("m1-v1/{annotator}/{run_id}")`, so conditions are interleaved and two
annotators do not see the runs in the same order. Within a run, turns are shown
in play order, since a run is read as a story. A failed condition D turn is not
shown, as in the checker: its narration is the engine's, not the model's.

**Blinding.** A run is shown by its label, the first 8 hex digits of
`sha256("m1-v1/{run_id}")`, and a turn by `{label}/{k}`, where k counts the
run's narrated turns, so a skipped failed turn leaves no gap. The annotator sees
the player input, the state the rubric scores against (the sheet facts of WBS
8.10, `checker_validation.turn_facts`), the narration, and the 9.4 candidates of
the turn, numbered. No condition, run id or seed.

**The record**, one JSON line per turn in `results/m1_labels.jsonl`:

    {"turn_id", "run_id", "input_index", "annotator",
     "candidates": [{"check", "category", "kind", "confidence", "mention",
                     "span", "confirmed"}],
     "added": [{"category", "phrase", "span"}],
     "note"}

`candidates` are the checker's candidates of the turn, each confirmed or not;
`added` are the divergences and rule breaks the annotator found that no
candidate covers, with the phrase copied from the narration and its span.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from adm.engine.scenario import Scenario
from adm.eval.checker import RunKey, Turn, check_turn, turns
from adm.eval.checker_validation import turn_facts

Doc = dict[str, Any]

DRAW = "m1-v1"
CONDITIONS = ("A", "B", "C", "D")
OVERLAP_RATE = 0.2
CATEGORIES = {
    "P": "PHANTOM",
    "C": "CONTRADICT",
    "R": "RESOURCE",
    "L": "RELATION",
    "U": "RULE",
}
CANDIDATE_FIELDS = ("check", "category", "kind", "confidence", "mention", "span")


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def run_label(rid: str) -> str:
    return sha(f"{DRAW}/{rid}")[:8]


def _run_id(key: RunKey) -> str:
    condition, scenario_id, seed = key
    return f"{condition}_{scenario_id}_{seed}"


def draw_runs(keys: Sequence[RunKey]) -> list[RunKey]:
    """The M1 sample: per scenario, the first seed in draw-key order that has a
    log in all four conditions, and its four runs. Sorted by run key."""
    by_scenario: dict[str, dict[int, set[str]]] = {}
    for condition, scenario_id, seed in keys:
        by_scenario.setdefault(scenario_id, {}).setdefault(seed, set()).add(condition)
    chosen: list[RunKey] = []
    for scenario_id, seeds in sorted(by_scenario.items()):
        whole = [s for s, conditions in seeds.items() if conditions >= set(CONDITIONS)]
        if not whole:
            continue
        seed = min(whole, key=lambda s: sha(f"{DRAW}/{scenario_id}/{s}"))
        chosen += [(c, scenario_id, seed) for c in CONDITIONS]
    return sorted(chosen)


def overlap_runs(sample: Sequence[RunKey], rate: float = OVERLAP_RATE) -> list[RunKey]:
    """The second annotator's runs: per condition, ceil(rate * n) in draw-key order."""
    chosen: list[RunKey] = []
    for condition in CONDITIONS:
        stratum = sorted(
            (k for k in sample if k[0] == condition),
            key=lambda k: sha(f"{DRAW}/overlap/{_run_id(k)}"),
        )
        chosen += stratum[: math.ceil(rate * len(stratum))]
    return sorted(chosen)


def annotator_order(runs: Sequence[RunKey], annotator: str) -> list[RunKey]:
    return sorted(runs, key=lambda k: sha(f"{DRAW}/{annotator}/{_run_id(k)}"))


@dataclass(frozen=True)
class M1Turn:
    """One narrated turn of the sample, as the annotator sees it."""

    turn_id: str
    turn: Turn
    candidates: tuple[Doc, ...]

    @property
    def run_id(self) -> str:
        return str(self.turn.record["run_id"])

    @property
    def input_index(self) -> int:
        return int(self.turn.record["input_index"])


def sample_turns(
    order: Sequence[RunKey],
    runs: Mapping[RunKey, Sequence[Doc]],
    scenarios: Mapping[str, Scenario],
) -> Iterator[M1Turn]:
    """The narrated turns of `order`'s runs, run by run, in play order, each
    with its checker candidates."""
    for key in order:
        label = run_label(_run_id(key))
        for k, turn in enumerate(turns(scenarios[key[1]], runs[key]), 1):
            found = tuple(
                {field: c.get(field) for field in CANDIDATE_FIELDS} for c in check_turn(turn)
            )
            yield M1Turn(f"{label}/{k}", turn, found)


def render(item: M1Turn) -> str:
    """The turn as the annotator sees it: nothing that names the condition."""
    lines = [
        f"Turn {item.turn_id}",
        f"Player input: {item.turn.record['player_input']}",
        *(line.replace("**", "").replace("`", "") for line in turn_facts(item.turn)),
        "",
        "Narration:",
        *(f"  {line}" for line in item.turn.narration.splitlines()),
        "",
    ]
    if item.candidates:
        lines.append("Checker candidates:")
        for n, c in enumerate(item.candidates, 1):
            lines.append(
                f"  [{n}] {c['category']:<10} {c['confidence']:<4} {c['mention']!r} ({c['kind']})"
            )
    else:
        lines.append("Checker candidates: none")
    return "\n".join(lines)


def parse_confirmed(answer: str, count: int) -> set[int]:
    """The candidate numbers confirmed: `a` is all, empty is none."""
    answer = answer.strip().lower()
    if not answer:
        return set()
    if answer == "a":
        return set(range(1, count + 1))
    numbers = answer.replace(",", " ").split()
    if not all(n.isdigit() and 1 <= int(n) <= count for n in numbers):
        raise ValueError(f"Type candidate numbers from 1 to {count}, a for all, or Enter for none.")
    return {int(n) for n in numbers}


def parse_category(answer: str) -> str | None:
    """A category letter, or None for no more."""
    code = answer.strip().upper()
    if not code:
        return None
    if code not in CATEGORIES:
        letters = ", ".join(f"{k} {v}" for k, v in CATEGORIES.items())
        raise ValueError(f"Type one of: {letters}; or Enter to finish.")
    return CATEGORIES[code]


def find_phrase(narration: str, phrase: str) -> list[int]:
    """The span of `phrase` in the narration, case-insensitive; it must be there."""
    phrase = phrase.strip()
    at = narration.lower().find(phrase.lower()) if phrase else -1
    if at < 0:
        raise ValueError("Copy the phrase exactly from the narration.")
    return [at, at + len(phrase)]


def record(
    item: M1Turn, annotator: str, confirmed: set[int], added: Sequence[Doc], note: str
) -> Doc:
    return {
        "turn_id": item.turn_id,
        "run_id": item.run_id,
        "input_index": item.input_index,
        "annotator": annotator,
        "candidates": [
            {**c, "confirmed": n in confirmed} for n, c in enumerate(item.candidates, 1)
        ],
        "added": list(added),
        "note": note,
    }
