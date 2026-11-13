"""The annotation tool (WBS 8.15): blind and condition-shuffled.

    python -m adm.eval.annotate m5 --rater SS
    python -m adm.eval.annotate m3 --annotator CI
    python -m adm.eval.annotate m1 --annotator SD

`m5` is the narrative-quality rating (M5, docs/narrative_quality.md). It picks
one excerpt per scenario and condition from the run logs, exactly as section 2
of the form says, writes the key from `excerpt_id` to run and window to
`results/m5_key.json`, and shows each rater the excerpts in their own hash order
(section 3). An excerpt shows the scenario's title, the five player inputs and
the narration the player saw, and nothing else: no condition, run id, seed,
turn number or input index, so the rater cannot tell which condition wrote it.
The four scores and a note go to `results/m5_ratings.jsonl` (section 5).

`m3` is the intent-fidelity annotation (M3, docs/intent_fidelity.md). It draws
the sample of section 2 from the condition D logs and shows each turn as
section 3.2 says: the player's input, the executed call with each id followed by
its display name, and the state the tool-call prompt saw (the state before the
turn, plus the encounter that opened before the call). The population is the
condition D runs the main-grid manifest plans, so smoke logs that share
`runs/D/` are left out, and a planned log that is missing stops the tool. The
verdict, a reason code if unfaithful, and a note go to `results/m3_intent.jsonl`
(section 5). With `--draft`, each turn also shows an AI draft verdict made from
the same view (decision log 2026-11-12, WBS 9.7): Enter accepts it, `e` judges
the turn from scratch, and the line keeps `draft` and `review`.

`m1` is the divergence annotation (M1, docs/rubric.md v1.0, WBS 9.5 and 9.6).
It shows every narrated turn of the 64 sampled runs (`adm/eval/m1.py`), run by
run, with the 9.4 checker candidates numbered. The annotator confirms the true
candidates and adds what no candidate covers; the turn goes to
`results/m1_labels.jsonl`. `--overlap` limits it to the second annotator's 20%.

Every choice and order is a sha256 hash of fixed strings, never an RNG
(invariant 3), so anyone can reproduce them from the logs. A rater who stops
(`q`) resumes where they stopped. `--redo <id>` replaces an earlier rating; a
re-rating needs a note. Nothing here writes to `runs/`.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console

from adm.engine.audit import apply_diff, read_log, step_part
from adm.engine.scenario import Scenario, initial_state, load_scenario
from adm.engine.state import data_hash
from adm.eval import m1 as m1_sample
from adm.eval.checker import LogMismatch as CheckerMismatch
from adm.eval.integrity import load_plan

Doc = dict[str, Any]
RunKey = tuple[str, str, int]  # condition, scenario_id, seed

CONDITIONS = ("A", "B", "C", "D")
WINDOW = 5  # exchanges per M5 excerpt
M3_RATE = 0.15
STOP = "q"

M5_ITEMS: dict[str, tuple[str, dict[int, str]]] = {
    "coherence": (
        "Coherence: does it hang together?",
        {
            1: "Replies ignore the inputs or each other; hard to follow.",
            3: "Mostly follows the inputs and stays consistent, with one or two lapses.",
            5: "Every reply follows from its input and what came before; easy to follow.",
        },
    ),
    "vividness": (
        "Vividness: can you picture it?",
        {
            1: "Generic and flat; no concrete detail.",
            3: "Some specific detail, but much is stock phrasing or repeated.",
            5: "Concrete, specific and varied detail throughout, without padding.",
        },
    ),
    "tone": (
        "Tone appropriateness: does it sound right?",
        {
            1: "The voice does not fit, sounds like an assistant, or acts for the player.",
            3: "Fits most of the time, with a lapse.",
            5: "A consistent Dungeon Master's voice that fits the game and each moment.",
        },
    ),
    "engagement": (
        "Engagement: would you want to keep reading?",
        {
            1: "Definitely not.",
            2: "Probably not.",
            3: "Not sure.",
            4: "Probably yes.",
            5: "Definitely yes.",
        },
    ),
}

REASONS = ("MISSED", "INVENTED", "WRONG_TOOL", "WRONG_TARGET", "WRONG_VALUE", "DROPPED")
SPELLS = {"spell_fire_bolt": "Fire Bolt", "spell_cure_wounds": "Cure Wounds"}


class KeyDrift(RuntimeError):
    """The M5 key on disk is not the selection the logs give now."""


class DraftMismatch(ValueError):
    """An M3 draft that does not fit the sample it is meant for."""


class LogMismatch(ValueError):
    """A run log whose state diffs do not replay to its state hashes."""


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_runs(runs_dir: Path) -> dict[RunKey, list[Doc]]:
    """Every run log under `runs/{condition}/{scenario_id}/{seed}.jsonl`."""
    runs: dict[RunKey, list[Doc]] = {}
    for condition in CONDITIONS:
        for path in sorted((runs_dir / condition).glob("*/*.jsonl")):
            if path.stem.isdigit():
                runs[(condition, path.parent.name, int(path.stem))] = read_log(path)
    return runs


def load_scenarios(scenarios_dir: Path, scenario_ids: set[str]) -> dict[str, Scenario]:
    return {sid: load_scenario(scenarios_dir / f"{sid}.json") for sid in sorted(scenario_ids)}


# --- M5: excerpts ------------------------------------------------------------


@dataclass(frozen=True)
class Excerpt:
    excerpt_id: str
    run_id: str
    w: int
    title: str
    exchanges: tuple[tuple[str, str], ...]


def _narrated(records: Sequence[Doc]) -> dict[int, Doc]:
    """A run's records by `input_index`, with the failed turns left out."""
    by_index: dict[int, list[Doc]] = defaultdict(list)
    for r in records:
        if r["input_index"] is not None:
            by_index[r["input_index"]].append(r)
    return {
        i: rs[0] for i, rs in by_index.items() if len(rs) == 1 and rs[0]["turn_failure"] is None
    }


def select_excerpts(
    runs: Mapping[RunKey, Sequence[Doc]],
    scenarios: Mapping[str, Scenario],
    *,
    short_only: bool = False,
) -> tuple[list[Excerpt], list[str]]:
    """One excerpt per scenario and condition (docs/narrative_quality.md section
    2), and the scenarios that have none."""
    excerpts: list[Excerpt] = []
    skipped: list[str] = []
    for sid in sorted({sid for _, sid, _ in runs}):
        if short_only and sid.startswith("long"):
            continue
        scenario = scenarios[sid]
        seeds = [
            seed
            for seed in {s for _, x, s in runs if x == sid}
            if all((c, sid, seed) in runs for c in CONDITIONS)
        ]
        seeds.sort(key=lambda s: sha(f"m5-v1/{sid}/seed/{s}"))
        windows = sorted(
            range(len(scenario.scripted_inputs) - WINDOW + 1),
            key=lambda w: sha(f"m5-v1/{sid}/window/{w}"),
        )
        chosen = _first_pair(runs, sid, seeds, windows, scenario.display_name)
        if chosen is None:
            skipped.append(sid)
        else:
            excerpts += chosen
    ids = [e.excerpt_id for e in excerpts]
    if len(set(ids)) != len(ids):
        raise ValueError("two excerpts share an excerpt_id")
    return excerpts, skipped


def _first_pair(
    runs: Mapping[RunKey, Sequence[Doc]],
    sid: str,
    seeds: Sequence[int],
    windows: Sequence[int],
    title: str,
) -> list[Excerpt] | None:
    for seed in seeds:
        narrated = {c: _narrated(runs[(c, sid, seed)]) for c in CONDITIONS}
        for w in windows:
            span = range(w, w + WINDOW)
            if all(i in narrated[c] for c in CONDITIONS for i in span):
                return [_excerpt(narrated[c], span, w, title) for c in CONDITIONS]
    return None


def _excerpt(narrated: Mapping[int, Doc], span: range, w: int, title: str) -> Excerpt:
    rid = narrated[span[0]]["run_id"]
    return Excerpt(
        excerpt_id=sha(f"m5-v1/excerpt/{rid}/{w}")[:8],
        run_id=rid,
        w=w,
        title=title,
        exchanges=tuple((narrated[i]["player_input"], narrated[i]["narration"]) for i in span),
    )


def rater_order(excerpts: Sequence[Excerpt], rater: str) -> list[Excerpt]:
    return sorted(excerpts, key=lambda e: sha(f"m5-v1/order/{rater}/{e.excerpt_id}"))


def render_excerpt(excerpt: Excerpt) -> str:
    """The excerpt as the rater sees it (docs/narrative_quality.md section 3)."""
    lines = [f"Excerpt {excerpt.excerpt_id} — {excerpt.title}", ""]
    for n, (said, narration) in enumerate(excerpt.exchanges, start=1):
        lines += [f"{n}. You: {said}", f"   DM:  {narration}", ""]
    return "\n".join(lines).rstrip()


def sync_key(path: Path, excerpts: Sequence[Excerpt]) -> None:
    """Write the key if there is none; otherwise require it to match."""
    key = {e.excerpt_id: {"run_id": e.run_id, "w": e.w} for e in excerpts}
    if path.exists():
        if json.loads(path.read_text(encoding="utf-8")) != key:
            raise KeyDrift(
                f"{path} does not match the excerpts the logs give now; "
                "the logs or the scenario set changed since rating began"
            )
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(key, indent=2, sort_keys=True) + "\n", encoding="utf-8")


# --- M3: the sample and the state at the call ---------------------------------


@dataclass(frozen=True)
class Turn:
    item_id: str
    run_id: str
    scenario_id: str
    seed: int
    input_index: int
    position: int  # the record's position in its log
    record: Doc


def _draw_key(rid: str, input_index: int) -> str:
    return sha(f"m3-v1/{rid}/{input_index}")


def draw_sample(runs: Mapping[RunKey, Sequence[Doc]], rate: float = M3_RATE) -> list[Turn]:
    """The M3 sample (docs/intent_fidelity.md section 2), in draw-key order."""
    strata: dict[str, list[Turn]] = defaultdict(list)
    for (condition, sid, seed), records in runs.items():
        if condition != "D":
            continue
        for position, r in enumerate(records):
            if r["turn_failure"] is None and r["input_index"] is not None:
                key = _draw_key(r["run_id"], r["input_index"])
                turn = Turn(key[:8], r["run_id"], sid, seed, r["input_index"], position, r)
                strata[sid].append(turn)
    sample: list[Turn] = []
    for turns in strata.values():
        turns.sort(key=lambda t: _draw_key(t.run_id, t.input_index))
        sample += turns[: math.ceil(rate * len(turns))]
    return sorted(sample, key=lambda t: _draw_key(t.run_id, t.input_index))


def state_at_call(scenario: Scenario, seed: int, records: Sequence[Doc], position: int) -> Doc:
    """The state the tool-call prompt of `records[position]` saw: the run
    replayed from its initial state, checked against every state hash, plus
    the turn's `before_call` engine steps."""
    data = initial_state(scenario, seed).to_dict()
    for r in records[:position]:
        _check_hash(data, r["state_before_hash"], r)
        data = apply_diff(data, r["state_diff"])
        _check_hash(data, r["state_after_hash"], r)
    record = records[position]
    _check_hash(data, record["state_before_hash"], record)
    for step in record["engine_steps"]:
        if step["when"] == "before_call":
            data = apply_diff(data, step_part(step, "state_diff"))
    return data


def _check_hash(data: Doc, expected: str, record: Doc) -> None:
    if data_hash(data) != expected:
        raise LogMismatch(
            f"{record['run_id']} input {record['input_index']}: the replayed state "
            "does not match the log's state hash"
        )


def _name(state: Doc, entity_id: str) -> str | None:
    for table in ("combatants", "item_definitions", "npc_relationships", "quests"):
        if entity_id in state[table]:
            return state[table][entity_id]["display_name"]
    return SPELLS.get(entity_id)


def render_turn(record: Doc, state: Doc, item_id: str = "") -> str:
    """The turn as the M3 annotator sees it (docs/intent_fidelity.md section 3.2)."""
    lines = [f"Turn {item_id}".rstrip(), "", f"Player: {record['player_input']}", ""]
    call = record["executed_call"]
    if call is None:
        lines.append('Call: no call ({"tool": null})')
    else:
        lines.append(f"Call: {call['tool']}")
        for arg, value in call["arguments"].items():
            name = _name(state, value) if isinstance(value, str) else None
            lines.append(f"  {arg}: {value} ({name})" if name else f"  {arg}: {value}")
    lines += ["", "State when the call was made"]
    lines.append(f"  Encounter: {'active' if state['encounter_active'] else 'none'}")
    lines.append("  Combatants:")
    for cid, c in state["combatants"].items():
        lines.append(f"    {c['display_name']} ({cid}): {c['status']}")
    for cid, c in state["combatants"].items():
        if c["is_player_character"]:
            held = state["inventory"].get(cid, {})
            items = ", ".join(
                f"{state['item_definitions'][i]['display_name']} ({i}) x{n}"
                for i, n in held.items()
                if n > 0
            )
            lines.append(f"  Inventory of {c['display_name']}: {items or 'nothing'}")
    lines.append("  NPC stances:")
    for nid, n in state["npc_relationships"].items():
        lines.append(f"    {n['display_name']} ({nid}): {n['stance']}")
    lines.append("  Quests:")
    for qid, q in state["quests"].items():
        lines.append(
            f"    {q['display_name']} ({qid}): {q['state']}, stage {q['stage']} of {q['max_stage']}"
        )
    return "\n".join(lines)


def load_draft(lines: Sequence[Doc], sample: Sequence[Turn]) -> dict[str, Doc]:
    """The M3 draft by item id, checked against the sample: every sampled turn
    once, `faithful` a boolean, and `reason` one of the codes exactly when the
    verdict is unfaithful."""
    ids = {t.item_id for t in sample}
    draft: dict[str, Doc] = {}
    errors: list[str] = []
    for n, line in enumerate(lines, 1):
        item_id, faithful, reason = line.get("item_id"), line.get("faithful"), line.get("reason")
        note = line.get("note", "")
        if item_id not in ids:
            errors.append(f"line {n}: {item_id!r} is not a sampled turn")
        elif item_id in draft:
            errors.append(f"line {n}: {item_id} is drafted twice")
        elif not isinstance(faithful, bool):
            errors.append(f"line {n}: faithful must be true or false")
        elif faithful and reason is not None:
            errors.append(f"line {n}: a faithful verdict has no reason")
        elif not faithful and reason not in REASONS:
            errors.append(f"line {n}: an unfaithful verdict needs a reason from {REASONS}")
        elif not isinstance(note, str):
            errors.append(f"line {n}: note must be text")
        else:
            draft[item_id] = {"faithful": faithful, "reason": reason, "note": note}
    missing = sorted(ids - draft.keys())
    if missing and not errors:
        errors.append(f"{len(missing)} sampled turns have no draft line, e.g. {missing[:3]}")
    if errors:
        raise DraftMismatch("; ".join(errors[:5]))
    return draft


def render_draft(draft: Doc) -> str:
    """The draft verdict of one turn, under the turn."""
    verdict = "faithful" if draft["faithful"] else f"unfaithful, {draft['reason']}"
    lines = ["", "Draft (AI, from this view)", f"  verdict: {verdict}"]
    if draft["note"]:
        lines.append(f"  note:    {draft['note']}")
    return "\n".join(lines)


# --- ratings files -----------------------------------------------------------


def read_lines(path: Path) -> list[Doc]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def append_line(path: Path, doc: Doc) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n")
        f.flush()
        os.fsync(f.fileno())


def replace_line(path: Path, same: Callable[[Doc], bool], doc: Doc) -> None:
    """Rewrite `path` with the line that is `same` as `doc` replaced by it."""
    lines = [doc if same(old) else old for old in read_lines(path)]
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        "".join(json.dumps(d, ensure_ascii=False, separators=(",", ":")) + "\n" for d in lines),
        encoding="utf-8",
        newline="\n",
    )
    os.replace(tmp, path)


# --- the command line --------------------------------------------------------

app = typer.Typer(add_completion=False, no_args_is_help=True)

RunsOption = Annotated[Path, typer.Option(help="Directory of the run logs.")]
ScenariosOption = Annotated[Path, typer.Option(help="Directory of the scenario files.")]
ResultsOption = Annotated[Path, typer.Option(help="Directory the ratings are written to.")]
RedoOption = Annotated[str | None, typer.Option(help="Re-rate this id; needs a note.")]


class _Stop(Exception):
    """The rater typed `q`."""


def _ask(console: Console, question: str, parse: Callable[[str], Any]) -> Any:
    """Ask until `parse` accepts the answer; `q` stops."""
    while True:
        answer = console.input(question).strip()
        if answer.lower() == STOP:
            raise _Stop
        try:
            return parse(answer)
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")


def _score(answer: str) -> int:
    if not re.fullmatch(r"[1-5]", answer):
        raise ValueError("Type a whole number from 1 to 5.")
    return int(answer)


def _note(required: bool) -> Callable[[str], str]:
    def parse(answer: str) -> str:
        if required and not answer:
            raise ValueError("A re-rating needs a note saying why.")
        return answer

    return parse


def _yes_no(answer: str) -> bool:
    if answer.lower() not in {"y", "n"}:
        raise ValueError("Type y (faithful) or n (unfaithful).")
    return answer.lower() == "y"


def _reason(answer: str) -> str:
    code = answer.upper()
    if code not in REASONS:
        raise ValueError(f"Type one of {', '.join(REASONS)}.")
    return code


def _accept(answer: str) -> bool:
    """Enter accepts the draft; `e` edits the turn."""
    if answer.lower() not in {"", "e"}:
        raise ValueError("Press Enter to accept the draft, or type e to edit.")
    return answer == ""


def _name_option(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z]+", value):
        raise typer.BadParameter("use your initials, letters only")
    return value


@app.callback()
def main() -> None:
    """Blind, condition-shuffled annotation for M5, M3 and M1 (WBS 8.15, 9.5)."""


@app.command()
def m5(
    rater: Annotated[str, typer.Option(help="Your initials.", callback=_name_option)],
    runs: RunsOption = Path("runs"),
    scenarios: ScenariosOption = Path("scenarios"),
    results: ResultsOption = Path("results"),
    short_only: Annotated[
        bool, typer.Option(help="R5 fallback: the 48 short-scenario excerpts only.")
    ] = False,
    redo: RedoOption = None,
) -> None:
    """Rate narrative quality (M5), blind to condition."""
    console = Console(highlight=False)
    logs = load_runs(runs)
    found = load_scenarios(scenarios, {sid for _, sid, _ in logs})
    excerpts, skipped = select_excerpts(logs, found, short_only=short_only)
    if skipped:
        console.print(f"No usable excerpt for: {', '.join(skipped)}", markup=False)
    if not excerpts:
        console.print("[red]Nothing to rate.[/red]")
        raise typer.Exit(1)
    try:
        sync_key(results / "m5_key.json", excerpts)
    except KeyDrift as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc

    path = results / "m5_ratings.jsonl"
    done = {r["excerpt_id"] for r in read_lines(path) if r["rater"] == rater}
    ordered = rater_order(excerpts, rater)
    if redo is not None:
        if redo not in done:
            console.print(f"[red]You have not rated {redo}.[/red]")
            raise typer.Exit(1)
        todo = [e for e in ordered if e.excerpt_id == redo]
    else:
        todo = [e for e in ordered if e.excerpt_id not in done]

    try:
        for excerpt in todo:
            console.print(f"\n[{len(done) + 1}/{len(ordered)}]", markup=False)
            console.print(render_excerpt(excerpt), markup=False)
            rating: Doc = {"excerpt_id": excerpt.excerpt_id, "rater": rater}
            for item, (question, anchors) in M5_ITEMS.items():
                console.print(f"\n{question}", markup=False)
                for score, anchor in anchors.items():
                    console.print(f"  {score}  {anchor}", markup=False)
                rating[item] = _ask(console, "Score 1-5 (q to stop): ", _score)
            rating["note"] = _ask(console, "Note (optional): ", _note(redo is not None))
            if redo is not None:
                replace_line(path, lambda r: (r["excerpt_id"], r["rater"]) == (redo, rater), rating)
            else:
                append_line(path, rating)
                done.add(excerpt.excerpt_id)
    except _Stop:
        pass
    console.print(f"\n{len(done)}/{len(ordered)} rated. Ratings: {path}", markup=False)


@app.command()
def m3(
    annotator: Annotated[str, typer.Option(help="Your initials.", callback=_name_option)],
    runs: RunsOption = Path("runs"),
    scenarios: ScenariosOption = Path("scenarios"),
    results: ResultsOption = Path("results"),
    rate: Annotated[
        float, typer.Option(help="Sampling rate; 0.10 is the R5 fallback.", min=0.0, max=1.0)
    ] = M3_RATE,
    manifest: Annotated[
        Path, typer.Option(help="The batch manifest whose condition D runs are the population.")
    ] = Path("experiments/main_grid.json"),
    draft: Annotated[
        Path | None, typer.Option(help="An AI draft to review (decision log 2026-11-12).")
    ] = None,
    redo: RedoOption = None,
) -> None:
    """Annotate intent fidelity (M3) on the condition D sample."""
    console = Console(highlight=False)
    planned = {key for key in load_plan(manifest)[0] if key[0] == "D"}
    logs = {key: records for key, records in load_runs(runs).items() if key in planned}
    missing = sorted(planned - logs.keys())
    if missing:
        names = ", ".join(f"{c}_{sid}_{seed}" for c, sid, seed in missing)
        console.print(f"No log for planned runs: {names}", markup=False, style="red")
        raise typer.Exit(1)
    sample = draw_sample(logs, rate=rate)
    if not sample:
        console.print("[red]No condition D turns to annotate.[/red]")
        raise typer.Exit(1)
    drafts: dict[str, Doc] = {}
    if draft is not None:
        try:
            drafts = load_draft(read_lines(draft), sample)
        except DraftMismatch as exc:
            console.print(f"The draft does not fit the sample: {exc}", markup=False, style="red")
            raise typer.Exit(1) from exc
    found = load_scenarios(scenarios, {t.scenario_id for t in sample})

    path = results / "m3_intent.jsonl"
    done = {
        (r["run_id"], r["input_index"]) for r in read_lines(path) if r["annotator"] == annotator
    }
    if redo is not None:
        todo = [t for t in sample if t.item_id == redo and (t.run_id, t.input_index) in done]
        if not todo:
            console.print(f"[red]You have not annotated {redo}.[/red]")
            raise typer.Exit(1)
    else:
        todo = [t for t in sample if (t.run_id, t.input_index) not in done]

    try:
        for turn in todo:
            records = logs[("D", turn.scenario_id, turn.seed)]
            try:
                state = state_at_call(found[turn.scenario_id], turn.seed, records, turn.position)
            except LogMismatch as exc:
                console.print(f"[red]{exc}[/red]")
                raise typer.Exit(1) from exc
            console.print(f"\n[{len(done) + 1}/{len(sample)}]", markup=False)
            console.print(render_turn(turn.record, state, turn.item_id), markup=False)
            console.print(
                "\nDoes the executed call do what the player asked, "
                "as far as one call in this game can?",
                markup=False,
            )
            shown = drafts.get(turn.item_id)
            accepted = False
            if shown is not None:
                console.print(render_draft(shown), markup=False)
                if redo is None:
                    question = "Accept draft? Enter = accept, e = edit (q to stop): "
                    accepted = _ask(console, question, _accept)
            if accepted:
                faithful, reason, note = shown["faithful"], shown["reason"], ""
            else:
                faithful = _ask(console, "Faithful? y/n (q to stop): ", _yes_no)
                reason = None
                if not faithful:
                    console.print(f"Reason: {', '.join(REASONS)}", markup=False)
                    reason = _ask(console, "Reason code: ", _reason)
                note = _ask(console, "Note (optional): ", _note(redo is not None))
            verdict = {
                "run_id": turn.run_id,
                "input_index": turn.input_index,
                "annotator": annotator,
                "faithful": faithful,
                "reason": reason,
                "note": note,
            }
            if shown is not None:
                verdict["draft"] = shown
                verdict["review"] = "accepted" if accepted else "edited"
            if redo is not None:
                key = (turn.run_id, turn.input_index, annotator)
                replace_line(
                    path,
                    lambda r, key=key: (r["run_id"], r["input_index"], r["annotator"]) == key,
                    verdict,
                )
            else:
                append_line(path, verdict)
                done.add((turn.run_id, turn.input_index))
    except _Stop:
        pass
    console.print(f"\n{len(done)}/{len(sample)} annotated. Annotations: {path}", markup=False)


@app.command()
def m1(
    annotator: Annotated[str, typer.Option(help="Your initials.", callback=_name_option)],
    runs: RunsOption = Path("runs"),
    scenarios: ScenariosOption = Path("scenarios"),
    results: ResultsOption = Path("results"),
    overlap: Annotated[
        bool, typer.Option(help="Second annotator: the 20% overlap runs only (WBS 9.6).")
    ] = False,
    redo: RedoOption = None,
    draft: Annotated[
        Path | None,
        typer.Option(help="AI pre-label file to review (decision log 2026-11-12)."),
    ] = None,
) -> None:
    """Annotate divergences (M1) by rubric v1.0, whole runs, blind to condition."""
    console = Console(highlight=False)
    logs = load_runs(runs)
    sample = m1_sample.draw_runs(sorted(logs))
    if overlap:
        sample = m1_sample.overlap_runs(sample)
    if not sample:
        console.print("[red]No scenario has a run in all four conditions at one seed.[/red]")
        raise typer.Exit(1)
    found = load_scenarios(scenarios, {sid for _, sid, _ in sample})
    order = m1_sample.annotator_order(sample, annotator)
    try:
        items = list(m1_sample.sample_turns(order, logs, found))
    except CheckerMismatch as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
    drafts: dict[str, Doc] = {}
    if draft is not None:
        if overlap:
            console.print("[red]The overlap is annotated without a draft (WBS 9.6).[/red]")
            raise typer.Exit(1)
        try:
            drafts = m1_sample.load_draft(read_lines(draft), items)
        except m1_sample.DraftError as exc:
            console.print(f"[red]The draft does not fit the sample: {exc}[/red]", markup=False)
            raise typer.Exit(1) from exc

    path = results / "m1_labels.jsonl"
    done = {r["turn_id"] for r in read_lines(path) if r["annotator"] == annotator}
    if redo is not None:
        todo = [t for t in items if t.turn_id == redo and t.turn_id in done]
        if not todo:
            console.print(f"[red]You have not annotated {redo}.[/red]")
            raise typer.Exit(1)
    else:
        todo = [t for t in items if t.turn_id not in done]
    console.print(
        f"{len(order)} runs, {len(items)} turns. Categories: "
        + ", ".join(f"{k} {v}" for k, v in m1_sample.CATEGORIES.items()),
        markup=False,
    )

    try:
        for item in todo:
            console.print(f"\n[{len(done) + 1}/{len(items)}]", markup=False)
            console.print(m1_sample.render(item), markup=False)
            shown = drafts.get(item.turn_id)
            if shown is not None:
                console.print(m1_sample.render_draft(item, shown), markup=False)
                accepted = _ask(
                    console,
                    "Accept draft? Enter = accept, e = edit (q to stop): ",
                    m1_sample.parse_accept,
                )
                if accepted and redo is None:
                    line = m1_sample.record(
                        item,
                        annotator,
                        set(shown["confirmed"]),
                        shown["added"],
                        "",
                        draft=shown,
                        review="accepted",
                    )
                    append_line(path, line)
                    done.add(item.turn_id)
                    continue
            confirmed: set[int] = set()
            if shown is not None and accepted:
                confirmed = set(shown["confirmed"])
            elif item.candidates:
                count = len(item.candidates)
                confirmed = _ask(
                    console,
                    "Confirm which? numbers, a = all, Enter = none (q to stop): ",
                    lambda a, count=count: m1_sample.parse_confirmed(a, count),
                )
            added: list[Doc] = list(shown["added"]) if shown is not None and accepted else []
            while shown is None or not accepted:
                category = _ask(
                    console,
                    "Missed divergence? category letter, Enter = done: ",
                    m1_sample.parse_category,
                )
                if category is None:
                    break
                narration = item.turn.narration
                span = _ask(
                    console,
                    "Phrase (copy from the narration): ",
                    lambda a, n=narration: (a.strip(), m1_sample.find_phrase(n, a)),
                )
                added.append({"category": category, "phrase": span[0], "span": span[1]})
            note = _ask(console, "Note (optional): ", _note(redo is not None))
            review = None if shown is None else ("accepted" if accepted else "edited")
            line = m1_sample.record(item, annotator, confirmed, added, note, shown, review)
            if redo is not None:
                key = (item.turn_id, annotator)
                replace_line(path, lambda r, key=key: (r["turn_id"], r["annotator"]) == key, line)
            else:
                append_line(path, line)
                done.add(item.turn_id)
    except _Stop:
        pass
    console.print(f"\n{len(done)}/{len(items)} annotated. Labels: {path}", markup=False)


if __name__ == "__main__":
    app()
