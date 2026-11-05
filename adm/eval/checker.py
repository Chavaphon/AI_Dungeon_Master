"""The automated checker (CLAUDE.md section 10.3): candidate divergences from the run logs.

    python -m adm.eval.checker --runs runs/ --out results/automated.jsonl

It reads every run log under `runs/{condition}/{scenario_id}/{seed}.jsonl` and
writes one JSON line per candidate. It never calls the model and never imports
orchestration: it must not depend on how a run was produced (docs/conventions.md
section 1).

**The turn.** `turns` yields a `Turn` for each narrated record of a run. A failed
condition D turn is skipped: its `narration` is the engine's request to
rephrase, not the model's. Each turn carries the state it is scored against
(docs/rubric.md section 1):

- Condition D: the state after the turn, rebuilt by replaying each record's
  `state_diff` from the scenario's turn-0 state.
- Conditions A to C: the ground truth for the input, `replay_script`'s state
  after it (CLAUDE.md section 9).

Each state is checked against the record's `state_after_hash`, and a log that
does not match is refused with `LogMismatch`, so a corrupt log fails loudly
instead of being scored against the wrong state.

**The checks.** `CHECKS` lists each check, a function from a `Turn` to its
candidates. WBS 8.6 adds `entity_mention` (`PHANTOM`, `adm/eval/entities.py`).
WBS 8.7 adds `hp_band` (`CONTRADICT`, `adm/eval/bands.py`): band phrases, an
unconscious combatant acting, and stated HP numbers, against the scored state.
WBS 8.8 adds `stance` (`RELATION`, `adm/eval/stance.py`): stance markers too far
from an NPC's recorded stance. WBS 8.9 adds the M4 checks (`RULE`,
`adm/eval/rules.py`): `rule_violation`, rule breaks the narration describes
given what the turn did, and `state_audit`, rule breaks in the state and engine
actions themselves, which the engine makes zero by construction. `RULE` is M4,
not one of the four M1 divergence categories.

**The record**, one line per candidate, sorted by run, then turn, then position:

    {"run_id", "condition", "scenario_id", "seed", "input_index", "turn_number",
     "check", "category", "status": "candidate", "confidence": "high" | "low",
     "kind", "mention", "span": [start, end], "sentence"}

`hp_band`, `stance` and the M4 candidates add `subject` (the combatant or NPC
ids the phrase may describe); `hp_band` and `stance` also add `implied` (what
the narration claims) and `actual` (what the state records). A `state_audit`
candidate has no narration: its `span` is `[0, 0]`, its `sentence` empty and
its `mention` the offending field or action.

`span` indexes the record's `narration`. `status` is always `candidate`: a human
confirms or rejects each one, and the checker never reports a final score for
`PHANTOM` (CLAUDE.md section 10.3). The output is a pure function of the logs
and scenarios, so a rerun gives the same bytes.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any

import typer

from adm.engine.audit import apply_diff, read_log
from adm.engine.replay import replay_script
from adm.engine.scenario import Scenario, initial_state, load_scenario
from adm.engine.state import data_hash
from adm.eval.bands import band_candidates
from adm.eval.entities import Scope, phantom_candidates
from adm.eval.rules import narrated_violations, state_violations
from adm.eval.stance import stance_candidates

Doc = dict[str, Any]
RunKey = tuple[str, str, int]  # condition, scenario_id, seed

CONDITIONS = ("A", "B", "C", "D")
RUN_FIELDS = ("run_id", "condition", "scenario_id", "seed", "input_index", "turn_number")


class LogMismatch(ValueError):
    """A run log whose records do not match the state they are scored against."""


@dataclass(frozen=True)
class Turn:
    """One narrated turn and what it is scored against: the state after it, the
    state before it, and what the engine did in it (the executed call and the
    engine steps; for A to C, the replayed ground truth's)."""

    record: Doc
    scenario: Scenario
    state: Doc
    before: Doc
    call: Doc | None
    steps: Sequence[Doc]

    @property
    def narration(self) -> str:
        return str(self.record["narration"])


# --- runs and turns ----------------------------------------------------------


def load_runs(runs_dir: Path) -> dict[RunKey, list[Doc]]:
    """Every run log under `runs/{condition}/{scenario_id}/{seed}.jsonl`, by key."""
    runs: dict[RunKey, list[Doc]] = {}
    for condition in CONDITIONS:
        for path in sorted((runs_dir / condition).glob("*/*.jsonl")):
            if path.stem.isdigit():
                runs[(condition, path.parent.name, int(path.stem))] = read_log(path)
    return runs


def _check_hash(state: Doc, record: Doc, field: str) -> None:
    if data_hash(state) != record[field]:
        raise LogMismatch(
            f"{record['run_id']} input {record['input_index']}: the state it is scored "
            f"against does not match its {field}"
        )


@dataclass(frozen=True)
class Scored:
    """What one record is scored against (docs/rubric.md section 1)."""

    before: Doc
    state: Doc
    call: Doc | None
    steps: Sequence[Doc]


def scored_turns(scenario: Scenario, records: Sequence[Doc]) -> list[Scored]:
    """The states and engine actions each record is scored against, checked
    against its hashes: condition D's own, A to C's replayed ground truth."""
    if not records:
        return []
    condition, seed = records[0]["condition"], records[0]["seed"]
    scored: list[Scored] = []
    if condition == "D":
        state = initial_state(scenario, seed).to_dict()
        for record in records:
            _check_hash(state, record, "state_before_hash")
            after = apply_diff(state, record["state_diff"])
            _check_hash(after, record, "state_after_hash")
            scored.append(Scored(state, after, record["executed_call"], record["engine_steps"]))
            state = after
        return scored
    truth = replay_script(scenario, seed)
    start = initial_state(scenario, seed).to_dict()
    for record in records:
        index = record["input_index"]
        if index is None or not 0 <= index < len(truth):
            raise LogMismatch(f"{record['run_id']}: input_index {index} is not a scripted input")
        turn = truth[index]
        _check_hash(turn.state, record, "state_after_hash")
        # A-C records carry the state after the input in both hashes (CLAUDE.md
        # section 15 item 49), so the state before is the replay's, unchecked.
        before = truth[index - 1].state if index else start
        scored.append(Scored(before, turn.state, turn.executed_call, turn.engine_steps))
    return scored


def scored_states(scenario: Scenario, records: Sequence[Doc]) -> list[Doc]:
    """The state each record is scored against, checked against its hashes."""
    return [s.state for s in scored_turns(scenario, records)]


def turns(scenario: Scenario, records: Sequence[Doc]) -> Iterator[Turn]:
    """The narrated turns of one run, in order, each with what it is scored against."""
    for record, s in zip(records, scored_turns(scenario, records), strict=True):
        if record["turn_failure"] is None:
            yield Turn(record, scenario, s.state, s.before, s.call, s.steps)


# --- the checks --------------------------------------------------------------

Check = Callable[[Turn], list[Doc]]


def entity_mention(turn: Turn) -> list[Doc]:
    """`PHANTOM` candidates: mentions that match nothing in scope (WBS 8.6)."""
    scope = Scope.of(turn.scenario, turn.state)
    return [
        {"check": "entity_mention", "category": "PHANTOM", **c.to_dict()}
        for c in phantom_candidates(turn.narration, scope)
    ]


def hp_band(turn: Turn) -> list[Doc]:
    """`CONTRADICT` candidates: HP bands, status and HP numbers (WBS 8.7)."""
    return [
        {"check": "hp_band", "category": "CONTRADICT", **c.to_dict()}
        for c in band_candidates(turn.narration, turn.state)
    ]


def stance(turn: Turn) -> list[Doc]:
    """`RELATION` candidates: treatment that does not fit an NPC's stance (WBS 8.8)."""
    return [
        {"check": "stance", "category": "RELATION", **c.to_dict()}
        for c in stance_candidates(turn.narration, turn.state)
    ]


def rule_violation(turn: Turn) -> list[Doc]:
    """M4: rule breaks the narration describes, given what the turn did (WBS 8.9)."""
    found = narrated_violations(turn.narration, turn.state, turn.before, turn.call, turn.steps)
    return [{"check": c.check, "category": "RULE", **c.to_dict()} for c in found]


def state_audit(turn: Turn) -> list[Doc]:
    """M4: rule breaks in the turn's state and engine actions; zero by construction."""
    found = state_violations(turn.state, turn.before, turn.call, turn.steps)
    return [{"check": c.check, "category": "RULE", **c.to_dict()} for c in found]


CHECKS: tuple[Check, ...] = (entity_mention, hp_band, stance, rule_violation, state_audit)


def check_turn(turn: Turn, checks: Sequence[Check] = CHECKS) -> list[Doc]:
    """Every candidate of one turn, as output records, in narration order."""
    run = {field: turn.record[field] for field in RUN_FIELDS}
    found = [
        {**run, "check": c["check"], "category": c["category"], "status": "candidate", **c}
        for check in checks
        for c in check(turn)
    ]
    return sorted(found, key=lambda c: (c["span"][0], c["check"]))


def check_runs(
    runs: dict[RunKey, list[Doc]], scenarios: dict[str, Scenario], checks: Sequence[Check] = CHECKS
) -> list[Doc]:
    """Every candidate of every run, sorted by run key and then turn."""
    return [
        candidate
        for key in sorted(runs)
        for turn in turns(scenarios[key[1]], runs[key])
        for candidate in check_turn(turn, checks)
    ]


def write_jsonl(path: Path, lines: Sequence[Doc]) -> None:
    """Write `lines` atomically, one compact JSON object each."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        "".join(json.dumps(d, ensure_ascii=False, separators=(",", ":")) + "\n" for d in lines),
        encoding="utf-8",
        newline="\n",
    )
    os.replace(tmp, path)


# --- the command line --------------------------------------------------------

app = typer.Typer(add_completion=False)


@app.command()
def main(
    runs: Annotated[Path, typer.Option(help="Directory of the run logs.")] = Path("runs"),
    out: Annotated[Path, typer.Option(help="JSONL file the candidates are written to.")] = Path(
        "results/automated.jsonl"
    ),
    scenarios: Annotated[Path, typer.Option(help="Directory of the scenario files.")] = Path(
        "scenarios"
    ),
) -> None:
    """Write every candidate divergence in the run logs (CLAUDE.md section 10.3)."""
    logs = load_runs(runs)
    loaded = {sid: load_scenario(scenarios / f"{sid}.json") for sid in sorted({k[1] for k in logs})}
    candidates = check_runs(logs, loaded)
    write_jsonl(out, candidates)
    high = sum(1 for c in candidates if c["confidence"] == "high")
    typer.echo(f"{len(logs)} runs, {len(candidates)} candidates ({high} high confidence) -> {out}")


if __name__ == "__main__":
    app()
