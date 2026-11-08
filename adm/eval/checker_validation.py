"""Checker validation (WBS 8.10, CLAUDE.md section 10.3): precision and recall of
the automated checker on 30 hand-labelled turns.

    python -m adm.eval.checker_validation sample --runs runs/dry_run
    # label results/checker_validation/labels.csv from sheet.md, then:
    python -m adm.eval.checker_validation score --runs runs/dry_run

**The sample** (`draw_sample`) is 30 narrated turns of the dry run (seed 3001,
`docs/dry_run.md`), stratified by condition, 8 from A and B and 7 from C and D.
Within a condition, turns are taken in the order of a sha256 key of the run id
and input index, so the draw is fixed with no RNG (as in `adm/eval/annotate.py`)
and both scenarios are mixed.

**The sheet** (`sheet.md`) shows each turn as the rubric scores it
(docs/rubric.md section 1): the player input, the narration, and the scored
state and engine actions of the checker's `Turn`, which are condition D's own
or A to C's replayed ground truth. It shows no condition, run id or checker
output, so the labels are blind to both.

**The labels** (`labels.csv`) are one row per divergence or rule break the
labeller finds: `sample_id`, `category` (`PHANTOM`, `CONTRADICT`, `RESOURCE`,
`RELATION`, or `RULE` for M4), `phrase` (the words of the narration, copied) and
`notes`. A row with category `NOTE` records an observation that is not a
divergence. Writing "5.3" in `notes` marks a rubric section 5.3 case (an event,
negation or figurative band phrase), which the rubric's section 7 point 2 asks
8.10 to count.

**Scoring** (`score`) runs every check on the sampled turns and matches each
candidate to at most one label of the same turn and category whose phrase
overlaps it: their spans in the narration overlap, or, if the phrase is not
found verbatim, one text contains the other. A matched candidate is a true
positive, an unmatched candidate a false positive, and an unmatched label a
miss. Precision and recall are reported per category, over all candidates and
over high-confidence ones only. `RESOURCE` has no check (decision log
2026-11-05, WBS 8.7), so its recall is zero by design and reported as such.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any

import typer

from adm.engine.combat import hp_band
from adm.engine.scenario import Scenario, load_scenario
from adm.eval.checker import CHECKS, RunKey, Turn, check_turn, load_runs, turns

Doc = dict[str, Any]

SIZE = 30
PER_CONDITION = {"A": 8, "B": 8, "C": 7, "D": 7}
CATEGORIES = ("PHANTOM", "CONTRADICT", "RESOURCE", "RELATION", "RULE")
LABEL_FIELDS = ("sample_id", "category", "phrase", "notes")
DRAW = "checker-validation-v1"
RESULTS_START = "<!-- results:start -->"
RESULTS_END = "<!-- results:end -->"


def draw_key(run_id: str, input_index: int) -> str:
    return hashlib.sha256(f"{DRAW}/{run_id}/{input_index}".encode()).hexdigest()


@dataclass(frozen=True)
class Sampled:
    """One sampled turn: its id on the sheet, its run and its input."""

    sample_id: str
    key: RunKey
    input_index: int

    def to_dict(self) -> Doc:
        condition, scenario_id, seed = self.key
        return {
            "sample_id": self.sample_id,
            "condition": condition,
            "scenario_id": scenario_id,
            "seed": seed,
            "input_index": self.input_index,
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> Sampled:
        return cls(d["sample_id"], (d["condition"], d["scenario_id"], d["seed"]), d["input_index"])


def narrated_turns(
    runs: Mapping[RunKey, Sequence[Doc]], scenarios: Mapping[str, Scenario]
) -> dict[tuple[RunKey, int], Turn]:
    """Every narrated turn of every run, by run and input index."""
    return {
        (key, t.record["input_index"]): t
        for key in sorted(runs)
        for t in turns(scenarios[key[1]], runs[key])
    }


def draw_sample(
    population: Mapping[tuple[RunKey, int], Turn], per_condition: Mapping[str, int] = PER_CONDITION
) -> list[Sampled]:
    """The sample: per condition, the first turns in draw-key order. Ids are
    S01..S30 in draw-key order across the whole sample, which hides the condition."""
    chosen: list[tuple[str, RunKey, int]] = []
    for condition, size in per_condition.items():
        stratum = sorted(
            (draw_key(t.record["run_id"], index), key, index)
            for (key, index), t in population.items()
            if key[0] == condition
        )
        if len(stratum) < size:
            raise ValueError(f"condition {condition} has {len(stratum)} turns, {size} wanted")
        chosen += stratum[:size]
    chosen.sort()
    return [Sampled(f"S{i:02d}", key, index) for i, (_, key, index) in enumerate(chosen, 1)]


# --- the sheet ------------------------------------------------------------------


def _names(state: Mapping[str, Any]) -> dict[str, str]:
    names = {}
    for table in ("combatants", "item_definitions", "npc_relationships", "quests"):
        for eid, entity in state.get(table, {}).items():
            names[eid] = entity["display_name"]
    return names


def _call(call: Mapping[str, Any] | None, names: Mapping[str, str]) -> str:
    if not call or call.get("tool") is None:
        return "none"
    args = ", ".join(
        f"{k}={names.get(v, v) if isinstance(v, str) else v}"
        for k, v in sorted(call.get("arguments", {}).items())
        if k != "justification"
    )
    return f"{call['tool']}({args})"


def turn_facts(turn: Turn) -> list[str]:
    """What the rubric scores a turn against, as lines of the sheet."""
    s, scenario = turn.state, turn.scenario
    names = _names(scenario.initial_state) | _names(s)
    lines = [
        f"- **Scenario:** {scenario.display_name}. Locations: {', '.join(scenario.locations)}.",
        "- **Combatants (after the turn):** "
        + "; ".join(
            f"{c['display_name']} (`{cid}`) {c['current_hp']}/{c['max_hp']} "
            f"`{hp_band(c['current_hp'], c['max_hp'])}`"
            + (f", slots {c['spell_slots_1']}" if c.get("spell_slots_1") is not None else "")
            for cid, c in sorted(s["combatants"].items())
        ),
        "- **Inventory:** "
        + "; ".join(
            f"{names.get(owner, owner)}: "
            + ", ".join(f"{names.get(i, i)} ×{q}" for i, q in sorted(items.items()))
            for owner, items in sorted(s["inventory"].items())
        ),
    ]
    if s["npc_relationships"]:
        lines.append(
            "- **NPC stances:** "
            + "; ".join(
                f"{n['display_name']} `{n['stance']}`"
                for _, n in sorted(s["npc_relationships"].items())
            )
        )
    if s["quests"]:
        lines.append(
            "- **Quests:** "
            + "; ".join(
                f"{q['display_name']} `{q['state']}`" for _, q in sorted(s["quests"].items())
            )
        )
    before, after = turn.before, s
    encounter = (
        "active"
        if after["encounter_active"]
        else f"over ({after['encounter_outcome']})"
        if after["encounter_outcome"]
        else "not started"
    )
    lines.append(
        f"- **Encounter:** {encounter}"
        + (
            " (started this turn)"
            if after["encounter_active"] and not before["encounter_active"]
            else ""
        )
        + (
            " (ended this turn)"
            if before["encounter_active"] and not after["encounter_active"]
            else ""
        )
    )
    lines.append(f"- **Executed call:** `{_call(turn.call, names)}`")
    npc = [_call(step["call"], names) for step in turn.steps if step.get("step") == "npc_action"]
    lines.append("- **NPC actions:** " + ("; ".join(f"`{c}`" for c in npc) if npc else "none"))
    return lines


def write_sheet(
    path: Path, sample: Sequence[Sampled], population: Mapping[tuple[RunKey, int], Turn]
) -> None:
    out = [
        "# Checker validation: labelling sheet (WBS 8.10)",
        "",
        "Label every divergence (`PHANTOM`, `CONTRADICT`, `RESOURCE`, `RELATION`) by "
        "docs/rubric.md, and every rule break (`RULE`: an attack after the encounter ended or "
        "by a combatant that did not act this turn, Cure Wounds with no slot, negative HP), as "
        "one row of `labels.csv`: `sample_id,category,phrase,notes`. Copy the phrase from the "
        "narration. Write `5.3` in `notes` for a rubric section 5.3 case. The state shown is "
        "the one the rubric scores against.",
        "",
    ]
    for item in sample:
        turn = population[(item.key, item.input_index)]
        out += [
            f"## {item.sample_id}",
            "",
            f"**Player input:** {turn.record['player_input']}",
            "",
            *turn_facts(turn),
            "",
            "**Narration:**",
            "",
            *[f"> {line}" if line else ">" for line in turn.narration.splitlines()],
            "",
        ]
    path.write_text("\n".join(out), encoding="utf-8")


# --- scoring --------------------------------------------------------------------


@dataclass
class Label:
    sample_id: str
    category: str
    phrase: str
    notes: str


def read_labels(path: Path, sample_ids: set[str]) -> list[Label]:
    labels = []
    with path.open(encoding="utf-8", newline="") as f:
        for n, row in enumerate(csv.DictReader(f), 2):
            label = Label(*(str(row.get(k) or "").strip() for k in LABEL_FIELDS))
            label.category = label.category.upper()
            if label.sample_id not in sample_ids:
                raise ValueError(f"labels.csv line {n}: unknown sample_id {label.sample_id!r}")
            if label.category not in (*CATEGORIES, "NOTE"):
                raise ValueError(f"labels.csv line {n}: unknown category {label.category!r}")
            if label.category != "NOTE" and not label.phrase:
                raise ValueError(f"labels.csv line {n}: a {label.category} label needs a phrase")
            labels.append(label)
    return labels


def _overlaps(narration: str, label: Label, candidate: Doc) -> bool:
    start, end = candidate["span"]
    at = narration.lower().find(label.phrase.lower())
    if at >= 0 and end > start:
        return at < end and start < at + len(label.phrase)
    a, b = label.phrase.lower(), str(candidate["mention"]).lower()
    return bool(a and b) and (a in b or b in a)


@dataclass
class Match:
    candidates: list[tuple[str, Doc, Label | None]]  # sample id, candidate, matched label
    missed: list[Label]


def match(
    sample: Sequence[Sampled],
    population: Mapping[tuple[RunKey, int], Turn],
    labels: Sequence[Label],
    checks: Sequence[Any] = CHECKS,
) -> Match:
    by_turn: dict[str, list[Label]] = {}
    for label in labels:
        if label.category != "NOTE":
            by_turn.setdefault(label.sample_id, []).append(label)
    result = Match([], [])
    for item in sample:
        turn = population[(item.key, item.input_index)]
        open_labels = list(by_turn.get(item.sample_id, []))
        for c in check_turn(turn, checks):
            hit = next(
                (
                    label
                    for label in open_labels
                    if label.category == c["category"] and _overlaps(turn.narration, label, c)
                ),
                None,
            )
            if hit is not None:
                open_labels.remove(hit)
            result.candidates.append((item.sample_id, c, hit))
        result.missed += open_labels
    return result


def _ratio(n: int, d: int) -> str:
    return f"{n / d:.2f}" if d else "–"


def report(result: Match, labels: Sequence[Label], sample: Sequence[Sampled]) -> str:
    """The results block of docs/checker_validation.md."""
    rows = [
        "| Category | Labels | Candidates | True positives | Precision | Recall | "
        "High: candidates | High: precision | High: recall |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    totals = Counter()
    for category in CATEGORIES:
        cands = [(c, hit) for _, c, hit in result.candidates if c["category"] == category]
        high = [(c, hit) for c, hit in cands if c["confidence"] == "high"]
        n_labels = sum(1 for lb in labels if lb.category == category)
        tp = sum(1 for _, hit in cands if hit is not None)
        tp_high = sum(1 for _, hit in high if hit is not None)
        totals.update(labels=n_labels, cands=len(cands), tp=tp, high=len(high), tp_high=tp_high)
        note = " (no check)" if category == "RESOURCE" else ""
        rows.append(
            f"| `{category}`{note} | {n_labels} | {len(cands)} | {tp} | {_ratio(tp, len(cands))} | "
            f"{_ratio(tp, n_labels)} | {len(high)} | {_ratio(tp_high, len(high))} | "
            f"{_ratio(tp_high, n_labels)} |"
        )
    t = totals
    rows.append(
        f"| **All** | {t['labels']} | {t['cands']} | {t['tp']} | {_ratio(t['tp'], t['cands'])} | "
        f"{_ratio(t['tp'], t['labels'])} | {t['high']} | {_ratio(t['tp_high'], t['high'])} | "
        f"{_ratio(t['tp_high'], t['labels'])} |"
    )

    by_check = Counter((c["check"], c["kind"], hit is not None) for _, c, hit in result.candidates)
    kinds = sorted({(check, kind) for check, kind, _ in by_check})
    check_rows = ["| Check | Kind | True positives | False positives |", "|---|---|---|---|"]
    check_rows += [
        f"| `{check}` | `{kind}` | {by_check[(check, kind, True)]} | "
        f"{by_check[(check, kind, False)]} |"
        for check, kind in kinds
    ]

    missed = ["| Sample | Category | Phrase | Notes |", "|---|---|---|---|"]
    missed += [
        f"| {m.sample_id} | `{m.category}` | {m.phrase} | {m.notes} |" for m in result.missed
    ]
    false = ["| Sample | Check | Kind | Confidence | Mention |", "|---|---|---|---|---|"]
    false += [
        f"| {sid} | `{c['check']}` | `{c['kind']}` | {c['confidence']} | {c['mention']} |"
        for sid, c, hit in result.candidates
        if hit is None
    ]
    by_condition = Counter(s.key[0] for s in sample)
    s53 = sorted({lb.sample_id for lb in labels if "5.3" in lb.notes})
    return "\n".join(
        [
            f"Sample: {len(sample)} turns ("
            + ", ".join(f"{c} {by_condition[c]}" for c in sorted(by_condition))
            + f"); {sum(1 for lb in labels if lb.category != 'NOTE')} labels.",
            "",
            "### By category",
            "",
            *rows,
            "",
            "### By check",
            "",
            *check_rows,
            "",
            f"### Missed ({len(result.missed)})",
            "",
            *(missed if result.missed else ["None."]),
            "",
            f"### False positives ({len(false) - 2})",
            "",
            *(false if len(false) > 2 else ["None."]),
            "",
            "### Rubric section 5.3 cases (rubric section 7 point 2)",
            "",
            f"{len(s53)} of {len(sample)} turns" + (f": {', '.join(s53)}." if s53 else "."),
        ]
    )


def write_results(doc: Path, block: str) -> None:
    text = doc.read_text(encoding="utf-8")
    start, end = text.index(RESULTS_START), text.index(RESULTS_END)
    doc.write_text(
        text[: start + len(RESULTS_START)] + "\n" + block + "\n" + text[end:], encoding="utf-8"
    )


# --- the command line -------------------------------------------------------------

app = typer.Typer(add_completion=False)
RunsOption = Annotated[Path, typer.Option(help="Directory of the dry-run logs.")]
DirOption = Annotated[Path, typer.Option(help="Where the sample, sheet and labels live.")]
ScenariosOption = Annotated[Path, typer.Option(help="Directory of the scenario files.")]


def _population(runs: Path, scenarios: Path) -> dict[tuple[RunKey, int], Turn]:
    logs = load_runs(runs)
    if not logs:
        raise typer.BadParameter(f"no run logs under {runs}/{{A,B,C,D}}/")
    loaded = {sid: load_scenario(scenarios / f"{sid}.json") for sid in sorted({k[1] for k in logs})}
    return narrated_turns(logs, loaded)


@app.command()
def sample(
    runs: RunsOption = Path("runs/dry_run"),
    out: DirOption = Path("results/checker_validation"),
    scenarios: ScenariosOption = Path("scenarios"),
) -> None:
    """Draw the 30 turns and write sample.json, sheet.md and an empty labels.csv."""
    population = _population(runs, scenarios)
    drawn = draw_sample(population)
    out.mkdir(parents=True, exist_ok=True)
    (out / "sample.json").write_text(
        json.dumps([s.to_dict() for s in drawn], indent=1) + "\n", encoding="utf-8"
    )
    write_sheet(out / "sheet.md", drawn, population)
    labels = out / "labels.csv"
    if not labels.exists():
        labels.write_text(",".join(LABEL_FIELDS) + "\n", encoding="utf-8")
    typer.echo(f"{len(drawn)} turns -> {out / 'sheet.md'}; label them in {labels}")


@app.command()
def score(
    runs: RunsOption = Path("runs/dry_run"),
    out: DirOption = Path("results/checker_validation"),
    scenarios: ScenariosOption = Path("scenarios"),
    doc: Annotated[Path, typer.Option(help="Document whose results block is rewritten.")] = Path(
        "docs/checker_validation.md"
    ),
) -> None:
    """Match the labels against the checker and write precision and recall."""
    population = _population(runs, scenarios)
    drawn = [Sampled.from_dict(d) for d in json.loads((out / "sample.json").read_text("utf-8"))]
    labels = read_labels(out / "labels.csv", {s.sample_id for s in drawn})
    block = report(match(drawn, population, labels), labels, drawn)
    write_results(doc, block)
    typer.echo(block)


if __name__ == "__main__":
    app()
