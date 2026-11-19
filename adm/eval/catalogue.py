"""The qualitative catalogue of ten illustrative failures (WBS 10.7).

    python -m adm.eval.catalogue --checksums experiments/main_grid.sha256 \\
        --doc docs/failure_catalogue.md

**Ten slots**, one failure each, fixed before the draw (docs/decisions.md,
2026-11-19): seven M1 divergences across the rubric categories and the
conditions, one M4 rule break narrated without an engine, one M2 tool call that
ran out of retries, and one M3 call that is valid but not what the player asked
for (CLAUDE.md section 7.2). `SLOTS` lists them.

**Sources.** M1 and M4 come from the first annotator's 9.5 labels on the M1
sample (the data of 10.1, `m1_rates`), M2 from the condition D runs of the main
grid, M3 from the four turns `docs/m3_annotation.md` section 3 names with CI's
final verdicts. With `--checksums`, every log read must match
`experiments/main_grid.sha256` (decision 60).

**The draw.** Within a slot the eligible turns are ordered by
sha256(`10.7-v1/<slot>/<turn>`) and the first is taken. A turn fills one slot
only. A turn of the 9.6 overlap on which the second annotator recorded no
divergence of the slot's category is contested and skipped.

**An entry** is the player input, condition D's tool-call attempts and the
facts its narrator was given, the narration with every labelled divergence in
bold, the labels with the drafter's note, and a state snapshot: the state the
turn is scored against (rubric section 1) for M1 and M4, the state the
tool-call prompt saw for M2 and M3. Ids outside a run are qualified by scenario
(docs/identifiers.md section 3).

The catalogue illustrates; it estimates nothing. The rates are 10.1 to 10.4's.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any

import typer

from adm.engine.audit import log_path, read_log, run_id
from adm.engine.combat import hp_band
from adm.eval import m1
from adm.eval.annotate import state_at_call
from adm.eval.checker import RunKey
from adm.eval.integrity import file_sha256, load_plan, read_checksums
from adm.eval.m1_agreement import read_lines
from adm.eval.m1_rates import LabelError, load_sample_logs, runs_m1
from adm.eval.metrics import DatasetError, write_results

Doc = dict[str, Any]

DRAW = "10.7-v1"
M3_DRAW = "m3-v1"  # adm/eval/annotate.py, the M3 turn id


@dataclass(frozen=True)
class Slot:
    """One place in the catalogue: which failures may fill it."""

    number: int
    layer: str  # M1, M4, M2 or M3
    category: str | None  # the rubric category, or RULE; None for M2 and M3
    conditions: tuple[str, ...]
    source: str  # "any", "added", a checker check, "turn_failure" or "m3"
    title: str


SLOTS = (
    Slot(1, "M1", "PHANTOM", ("A",), "entity_mention", "A phantom entity, found by the checker"),
    Slot(2, "M1", "PHANTOM", ("D",), "any", "A phantom entity in condition D"),
    Slot(
        3,
        "M1",
        "CONTRADICT",
        ("D",),
        "hp_band",
        "A hit-point or status contradiction in D, with the band in the facts",
    ),
    Slot(4, "M1", "CONTRADICT", ("C",), "any", "A state contradiction past C's self-check"),
    Slot(5, "M1", "CONTRADICT", ("B",), "added", "A state contradiction the checker missed, in B"),
    Slot(6, "M1", "RESOURCE", ("D",), "any", "A resource error in D"),
    Slot(7, "M1", "RELATION", ("D",), "any", "A relationship contradiction in D"),
    Slot(8, "M4", "RULE", ("A", "B", "C"), "any", "A rule break narrated with no engine"),
    Slot(9, "M2", None, ("D",), "turn_failure", "A tool call that ran out of retries"),
    Slot(10, "M3", None, ("D",), "m3", "A valid call that is not what the player asked for"),
)

# docs/m3_annotation.md section 3: the M3 turns named with CI's final reason code.
M3_TURNS = {
    "064fcfea": "WRONG_TOOL",
    "1c33f6c8": "WRONG_VALUE",
    "1d18733b": "WRONG_TOOL",
    "1e35416e": "WRONG_TOOL",
}


class CatalogueError(ValueError):
    """A slot cannot be filled from the data as the rule says."""


# --- labels --------------------------------------------------------------------


@dataclass(frozen=True)
class Mark:
    """One labelled divergence in a narration."""

    category: str
    phrase: str
    span: tuple[int, int] | None
    source: str  # the checker check that proposed it, or "added"


def marks(line: Doc, narration: str) -> list[Mark]:
    """The divergences a label line records: confirmed candidates and added
    labels, in narration order."""
    out = []
    for c in line["candidates"]:
        if c.get("confirmed"):
            span = _span(c)
            phrase = narration[span[0] : span[1]] if span else str(c.get("mention", ""))
            out.append(Mark(c["category"], phrase, span, c.get("check", "")))
    for a in line["added"]:
        out.append(Mark(a["category"], a.get("phrase", ""), _span(a), "added"))
    return sorted(out, key=lambda m: m.span[0] if m.span else len(narration))


def _span(label: Doc) -> tuple[int, int] | None:
    span = label.get("span")
    return (int(span[0]), int(span[1])) if span else None


def overlap_categories(lines: Sequence[Doc], annotator: str) -> dict[str, set[str]]:
    """Per turn of the second annotator's overlap, the categories they recorded."""
    out: dict[str, set[str]] = {}
    for line in lines:
        if line.get("annotator") == annotator:
            found = {c["category"] for c in line["candidates"] if c.get("confirmed")}
            out[line["turn_id"]] = found | {a["category"] for a in line["added"]}
    return out


def eligible(slot: Slot, condition: str, found: Sequence[Mark], second: set[str] | None) -> bool:
    """Whether a labelled turn may fill an M1 or M4 slot. `second` is the second
    annotator's categories when the turn is in the overlap."""
    if condition not in slot.conditions:
        return False
    ms = [m for m in found if m.category == slot.category]
    if slot.source != "any":
        ms = [m for m in ms if m.source == slot.source]
    if not ms:
        return False
    return second is None or slot.category in second


def draw_key(slot: Slot, unit: str) -> str:
    return hashlib.sha256(f"{DRAW}/{slot.number}/{unit}".encode()).hexdigest()


def pick(slot: Slot, units: Sequence[str], used: set[str]) -> str | None:
    """The first unit of the slot's draw order not used by an earlier slot."""
    for unit in sorted(units, key=lambda u: draw_key(slot, u)):
        if unit not in used:
            return unit
    return None


def m3_id(rid: str, input_index: int) -> str:
    return hashlib.sha256(f"{M3_DRAW}/{rid}/{input_index}".encode()).hexdigest()[:8]


# --- the entry -----------------------------------------------------------------


@dataclass(frozen=True)
class Entry:
    """One catalogued failure, as the doc shows it."""

    slot: Slot
    pool: int
    run_id: str
    scenario_id: str
    input_index: int
    turn_number: int
    player_input: str
    narration: str
    marks: tuple[Mark, ...]
    note: str
    attempts: tuple[str, ...]
    facts: tuple[Doc, ...]
    verdict: str | None
    snapshot: tuple[str, ...]
    snapshot_of: str


def attempts(record: Doc) -> tuple[str, ...]:
    """Each tool-call attempt as `raw output -> outcome`."""
    raws = [c["raw_output"] for c in record["model_calls"] if c["phase"] == "toolcall"]
    out = []
    for raw, v in zip(raws, record["validation"], strict=False):
        outcome = "ok" if v.get("ok") else v.get("rejection_code") or "unparseable"
        out.append(f"{' '.join(raw.split())} -> {outcome}")
    return tuple(out)


def facts(record: Doc) -> tuple[Doc, ...]:
    """The facts condition D's narrator was given, in play order: NPC actions
    before the call, the call, NPC actions after it (CLAUDE.md section 9.1)."""

    def npc(when: str) -> list[Doc]:
        return [
            s["result"]["narration_facts"]
            for s in record["engine_steps"]
            if s["step"] == "npc_action" and s["when"] == when and s["result"].get("ok")
        ]

    call = [v["narration_facts"] for v in record["validation"] if v.get("ok") is True]
    return tuple(npc("before_call") + call[-1:] + npc("after_call"))


def snapshot(state: Doc, scenario_id: str) -> tuple[str, ...]:
    """The state as one line per encounter, combatant, inventory, NPC and quest,
    every id qualified by its scenario."""

    def q(entity: str) -> str:
        return f"`{scenario_id}/{entity}`"

    if state.get("encounter_active"):
        lines = [
            f"Encounter: active, round {state['round_number']}, "
            f"{q(state['active_combatant_id'])} to act"
        ]
    else:
        outcome = state.get("encounter_outcome")
        lines = [f"Encounter: none active{f' (last ended in {outcome})' if outcome else ''}"]
    for cid, c in state["combatants"].items():
        extra = ", dodging" if c.get("dodging") else ""
        if c.get("spell_slots_1") is not None:
            extra += f", {c['spell_slots_1']} level-1 slots"
        lines.append(
            f"{q(cid)} {c['display_name']} ({c['faction']}): {c['current_hp']}/{c['max_hp']} HP, "
            f"{hp_band(c['current_hp'], c['max_hp'])}, {c['status']}{extra}"
        )
    names = {i: d["display_name"] for i, d in state["item_definitions"].items()}
    for holder, items in state["inventory"].items():
        held = ", ".join(f"{names.get(i, i)} x{n}" for i, n in items.items()) or "nothing"
        lines.append(f"Inventory of {q(holder)}: {held}")
    for nid, n in state["npc_relationships"].items():
        lines.append(f"{q(nid)} {n['display_name']}: {n['stance']}")
    for qid, quest in state["quests"].items():
        lines.append(
            f"{q(qid)} {quest['display_name']}: {quest['state']}, "
            f"stage {quest['stage']} of {quest['max_stage']}"
        )
    return tuple(lines)


def marked(narration: str, found: Sequence[Mark]) -> str:
    """The narration on one line with each labelled span in bold; a span that
    overlaps an earlier one is left unmarked."""
    out, at = [], 0
    for span in sorted(m.span for m in found if m.span):
        start, end = span
        if start < at or end > len(narration):
            continue
        out += [narration[at:start], "**", narration[start:end], "**"]
        at = end
    out.append(narration[at:])
    return " ".join("".join(out).split())


# --- the draw ------------------------------------------------------------------


def _read_checked(runs_dir: Path, keys: Sequence[RunKey], checksums: Path | None) -> dict:
    expected = read_checksums(checksums) if checksums else None
    logs = {}
    for key in keys:
        path = log_path(runs_dir, *key)
        if not path.is_file():
            raise DatasetError(f"No log for {run_id(*key)}")
        if expected is not None:
            name = path.relative_to(runs_dir).as_posix()
            if expected.get(name) != file_sha256(path):
                raise DatasetError(f"{path.as_posix()}: does not match the checksum file")
        logs[key] = read_log(path)
    return logs


def build(
    items: Sequence[m1.M1Turn],
    lines: Sequence[Doc],
    second: Mapping[str, set[str]],
    d_logs: Mapping[RunKey, Sequence[Doc]],
    state_of: Callable[[RunKey, int], Doc],
    annotator: str,
    m3_turns: Mapping[str, str] = M3_TURNS,
) -> list[Entry]:
    """Fill every slot by the draw rule. `state_of(key, position)` is the state
    the tool-call prompt of that D record saw."""
    mine = {line["turn_id"]: line for line in lines if line.get("annotator") == annotator}
    labelled = []
    for item in items:
        line = mine[item.turn_id]
        labelled.append((item, line, marks(line, item.turn.narration)))

    d_turns: dict[str, tuple[RunKey, int]] = {}
    failed: list[str] = []
    for key, records in d_logs.items():
        for position, r in enumerate(records):
            unit = f"{r['run_id']}/{r['input_index']}"
            d_turns[unit] = (key, position)
            if r["turn_failure"] is not None:
                failed.append(unit)
    m3_units = {
        m3_id(r["run_id"], r["input_index"]): f"{r['run_id']}/{r['input_index']}"
        for records in d_logs.values()
        for r in records
        if r["turn_failure"] is None and r["input_index"] is not None
    }
    missing = [t for t in m3_turns if t not in m3_units]
    if missing:
        raise CatalogueError(f"M3 turns not in the D logs: {', '.join(missing)}")

    used: set[str] = set()
    entries = []
    for slot in SLOTS:
        if slot.layer in ("M1", "M4"):
            pool = {
                item.turn_id: (item, line, found)
                for item, line, found in labelled
                if eligible(slot, item.turn.record["condition"], found, second.get(item.turn_id))
            }
            unit = pick(slot, list(pool), used)
            if unit is None:
                raise CatalogueError(f"slot {slot.number}: no eligible turn")
            used.add(unit)
            item, line, found = pool[unit]
            entries.append(_m1_entry(slot, len(pool), item, line, found))
            continue
        units = failed if slot.layer == "M2" else [m3_units[t] for t in m3_turns]
        unit = pick(slot, units, used)
        if unit is None:
            raise CatalogueError(f"slot {slot.number}: no eligible turn")
        used.add(unit)
        key, position = d_turns[unit]
        verdict = None
        if slot.layer == "M3":
            verdict = m3_turns[next(t for t, u in m3_units.items() if u == unit)]
        record = d_logs[key][position]
        entries.append(_d_entry(slot, len(units), key, record, state_of(key, position), verdict))
    return entries


def _m1_entry(slot: Slot, pool: int, item: m1.M1Turn, line: Doc, found: Sequence[Mark]) -> Entry:
    record = item.turn.record
    d = record["condition"] == "D"
    return Entry(
        slot=slot,
        pool=pool,
        run_id=record["run_id"],
        scenario_id=record["scenario_id"],
        input_index=record["input_index"],
        turn_number=record["turn_number"],
        player_input=record["player_input"],
        narration=item.turn.narration,
        marks=tuple(found),
        note=line.get("note") or line.get("draft", {}).get("note", ""),
        attempts=attempts(record) if d else (),
        facts=facts(record) if d else (),
        verdict=None,
        snapshot=snapshot(item.turn.state, record["scenario_id"]),
        snapshot_of="the state the turn is scored against, after it (rubric section 1)",
    )


def _d_entry(
    slot: Slot, pool: int, key: RunKey, record: Doc, state: Doc, verdict: str | None
) -> Entry:
    return Entry(
        slot=slot,
        pool=pool,
        run_id=record["run_id"],
        scenario_id=key[1],
        input_index=record["input_index"],
        turn_number=record["turn_number"],
        player_input=record["player_input"],
        narration=record["narration"],
        marks=(),
        note="",
        attempts=attempts(record),
        facts=facts(record),
        verdict=verdict,
        snapshot=snapshot(state, key[1]),
        snapshot_of="the state the tool-call prompt saw",
    )


# --- the report ----------------------------------------------------------------


def _quote(text: str) -> str:
    return " ".join(text.split()).replace("|", "\\|")


def _origin(m: Mark) -> str:
    return "added by the annotator" if m.source == "added" else f"{m.source} candidate, confirmed"


def render_entry(e: Entry) -> str:
    s = e.slot
    what = f"{s.layer}, `{s.category}`" if s.category else s.layer
    lines = [
        f"### {s.number}. {s.title}",
        "",
        f"{what} · `{e.run_id}`, scripted input {e.input_index} (turn {e.turn_number}) · "
        f"drawn from {e.pool} eligible turns",
        "",
        f'**Player:** "{_quote(e.player_input)}"',
        "",
    ]
    if e.attempts:
        lines += ["**Tool-call attempts** (temperature 0.0):", ""]
        lines += [f"{i}. `{a}`" for i, a in enumerate(e.attempts, 1)]
        lines.append("")
    if e.facts:
        lines += ["**Facts given to the narrator:**", "", "```json"]
        lines += [json.dumps(f, ensure_ascii=False) for f in e.facts]
        lines += ["```", ""]
    elif e.attempts:
        lines += ["**Facts given to the narrator:** none.", ""]
    lines += ["**Narration:**", "", f"> {marked(e.narration, e.marks)}", ""]
    if e.marks:
        lines += ["**Labels** (first annotator, rubric v1.0):", ""]
        lines += [
            f'{i}. `{m.category}` "{_quote(m.phrase)}" ({_origin(m)})'
            for i, m in enumerate(e.marks, 1)
        ]
        lines.append("")
        if e.note:
            lines += [f"Annotation note (AI draft, accepted by SD): {_quote(e.note)}", ""]
    if e.verdict:
        lines += [f"**M3 verdict** (CI, `docs/m3_annotation.md` section 3): `{e.verdict}`.", ""]
    lines += [f"**State snapshot**, {e.snapshot_of}:", ""]
    lines += [f"- {x}" for x in e.snapshot]
    return "\n".join(lines)


def render(entries: Sequence[Entry], labels_sha256: str) -> str:
    head = [
        f"Ten failures drawn by the rule of `docs/decisions.md` (2026-11-19). Labels "
        f"sha256 `{labels_sha256}`. Bold marks each labelled divergence in a narration.",
        "",
        "| # | Layer | Category | Run | Input | Drawn from |",
        "|---|---|---|---|---|---|",
    ]
    head += [
        f"| {e.slot.number} | {e.slot.layer} | {f'`{e.slot.category}`' if e.slot.category else '–'}"
        f" | `{e.run_id}` | {e.input_index} | {e.pool} |"
        for e in entries
    ]
    return "\n\n".join(["\n".join(head), *(render_entry(e) for e in entries)])


# --- the command ---------------------------------------------------------------

app = typer.Typer(add_completion=False)


@app.command()
def main(
    labels: Annotated[Path, typer.Option(help="The first annotator's m1_labels.jsonl.")] = Path(
        "results/m1_labels.jsonl"
    ),
    overlap: Annotated[Path, typer.Option(help="The second annotator's 9.6 labels.")] = Path(
        "results/m1_labels_SS.jsonl"
    ),
    annotator: Annotated[str, typer.Option(help="The first annotator (9.5).")] = "SD",
    second: Annotated[str, typer.Option(help="The second annotator (9.6).")] = "SS",
    runs: Annotated[Path, typer.Option(help="The runs directory.")] = Path("runs"),
    manifest: Annotated[Path, typer.Option(help="The batch manifest of the dataset.")] = Path(
        "experiments/main_grid.json"
    ),
    checksums: Annotated[
        Path | None, typer.Option(help="sha256sum file the logs must match (decision 60).")
    ] = None,
    doc: Annotated[
        Path | None, typer.Option(help="Document whose results block is rewritten.")
    ] = None,
) -> None:
    """Draw the ten illustrative failures of the catalogue (WBS 10.7)."""
    try:
        planned, scenarios, _ = load_plan(manifest)
        logs = load_sample_logs(runs, manifest, checksums)
        sample = sorted(logs)
        items = list(m1.sample_turns(sample, logs, scenarios))
        lines = read_lines([labels])
        runs_m1(sample, items, lines, annotator)  # the labels are checked as in 10.1
        d_logs = _read_checked(runs, [k for k in planned if k[0] == "D"], checksums)
        entries = build(
            items,
            lines,
            overlap_categories(read_lines([overlap]), second),
            d_logs,
            lambda key, at: state_at_call(scenarios[key[1]], key[2], d_logs[key], at),
            annotator,
        )
    except (DatasetError, LabelError, CatalogueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    block = render(entries, file_sha256(labels))
    if doc is not None:
        write_results(doc, block)
    for e in entries:  # ASCII only: the Windows console cannot print the narration
        typer.echo(f"{e.slot.number:>2} {e.slot.layer} {e.run_id} input {e.input_index}")


if __name__ == "__main__":
    app()
