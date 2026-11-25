"""The text command-line client (WBS 6.10, 6.11): the composition root of
docs/conventions.md section 1. It reads `config/`, wires the packages and holds
no game logic.

    python -m adm.cli play --scenario scenarios/s01_cellar.json --seed 12345
    python -m adm.cli run --scenario scenarios/s01_cellar.json --condition D --seed 12345
    python -m adm.cli smoke --manifest experiments/smoke_grid.json
    python -m adm.cli batch --manifest experiments/main_grid.json

`play` is an interactive condition D session. The model is checked against
`config/model.json` and freshly loaded first (docs/model_selection.md section 4).
The player sees the scenario's title, labelled "Narrated by AI", its opening
narration and a line pointing to `/help`, then types one input per turn. Each
turn shows one result line per mechanical outcome (the player's executed call
and any NPC actions: dice, hit or miss, damage, hit points), then the
narration; a failed turn shows the request to rephrase. The result lines are
built from the turn's audit record (`adm/play/results.py`) and are display
only: nothing is added to the record or to any prompt.
`play` is in beginner mode by default (WBS 13.2): result lines and commands
use plain words (`adm/play/vocabulary.py`) and show no dice, AC, DC or HP.
`--mode veteran` shows the rolls, AC and DC. The mode is never logged and never
sent to the model, so both modes write the same log. Beginner mode also shows
"You could try:" with two to four hints before the first input and after each
turn (`adm/play/hints.py`, WBS 13.7), worked out from a copy of the state and
checked against the validator, never the dice or the model.
An input that starts with `/` is a slash command (`adm/play/commands.py`,
WBS 13.1): `/help`, `/status`, `/inventory`, `/quests`, `/rules` and
`/glossary` are answered here, from a copy of the state, before the turn loop,
so they make no model call, write no record and do not count toward an
encounter's `before_input`. `/quit` (or `/exit`), end of input or Ctrl+C ends
the session. Every turn is in
`runs/D/<scenario_id>/<seed>.jsonl` (CLAUDE.md section 11) as soon as it is shown.

`guide` prints `HOW_TO_PLAY.md`, the guide for players new to role-playing
games (`adm/play/guide.py`, WBS 13.3); `/help` in `play` is its short version.

`run` plays the scenario's scripted inputs unattended (`session.run_script`),
printing one line per input. It is the one entry point for every condition
(WBS 7.4): `HARNESSES` maps a condition to the `HarnessStart` that builds its
harness, and nothing else differs. Condition D is `Session.start`; A, B and C
are the narration-only harness on templates `a`, `b` and `c` (WBS 7.1 to 7.3,
`NarrationOnlyStart`). A condition with no harness is
refused before its log is created or the model loads. An exception other than
a refused run or a model error is a bug and propagates.

`smoke` plays every run of a smoke manifest that has no log yet, as `run` does,
and reports gate G2 (WBS 6.11, `adm/bench/smoke.py`). An exception ends only
its own run, which is then unrecoverable; the summary goes to
`results/bench/smoke/<UTC time>/summary.json`.

`batch` plays every `(seed, scenario, condition)` run of a batch manifest, one
at a time, each as `run` plays it on a freshly loaded model, and is resumed by
running it again (WBS 7.6, `adm/orchestration/batch.py`). Each run's model
client counts its transport retries, so a run with any is played again. Every
attempt is a line of `results/batch/attempts.jsonl`. It exits 0 only when every
run of the manifest is complete.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.markup import escape

from adm.bench import smoke as smoke_runs
from adm.engine.audit import turn_failure_counts
from adm.engine.scenario import Scenario, load_scenario
from adm.orchestration import batch as batch_runs
from adm.orchestration.client import (
    ModelClient,
    ModelConfig,
    ModelError,
    OllamaClient,
    RetryCountingClient,
    load_model_config,
)
from adm.orchestration.narration_only import NarrationOnlyStart
from adm.orchestration.prompt import load_templates
from adm.orchestration.session import (
    Harness,
    HarnessStart,
    PlayedTurn,
    RunExists,
    Session,
    new_run_log,
    run_script,
)
from adm.play.commands import HINT, is_command, run_command
from adm.play.guide import guide as how_to_play
from adm.play.hints import hint_block
from adm.play.results import result_lines
from adm.play.vocabulary import Mode

# The audit log's conditions (schemas/audit.schema.json), and the harness of
# each one that is wired. Interactive play and the G2 smoke runs are condition D.
CONDITIONS = ("A", "B", "C", "D")
HARNESSES: dict[str, HarnessStart] = {
    "A": NarrationOnlyStart("a"),
    "B": NarrationOnlyStart("b"),
    "C": NarrationOnlyStart("c"),
    "D": Session.start,
}
D = "D"

AI_LABEL = "Narrated by AI"
PROMPT = "> "
RUNS = Path("runs")
SMOKE_RESULTS = Path("results/bench/smoke")
BATCH_LEDGER = Path("results/batch/attempts.jsonl")

app = typer.Typer(add_completion=False, no_args_is_help=True)


@app.callback()
def main() -> None:
    """AI Dungeon Master: a hybrid rule-engine and LLM-based game master."""


def connect(config: ModelConfig) -> AbstractContextManager[ModelClient]:
    """The pinned model on the local Ollama server, freshly loaded."""
    client = OllamaClient(config)
    try:
        client.verify()
        client.fresh_load()
    except BaseException:
        client.close()
        raise
    return client


ScenarioOption = Annotated[
    Path, typer.Option(exists=True, dir_okay=False, help="Scenario JSON file.")
]
SeedOption = Annotated[int, typer.Option(help="Run seed: fixes the dice and the model's sampling.")]
RunsOption = Annotated[Path, typer.Option(help="Directory the audit log is written under.")]
ModeOption = Annotated[
    Mode,
    typer.Option(
        help="beginner: plain words, no dice numbers. veteran: rolls, AC and DC. "
        "Display only: the log and the model are the same in both."
    ),
]


@contextmanager
def open_session(
    console: Console,
    scenario: Scenario,
    seed: int,
    runs: Path,
    condition: str,
    wrap: Callable[[ModelClient], ModelClient] = lambda client: client,
) -> Iterator[Harness]:
    """A new run of `condition` on a freshly loaded model, whose client is
    passed through `wrap`. A run that already has a log is refused before the
    model loads."""
    start = HARNESSES[condition]
    config = load_model_config()
    texts = load_templates()
    log = new_run_log(runs, condition, scenario.scenario_id, seed)
    with console.status(f"Loading {config.model}..."):
        client_cm = connect(config)
    with client_cm as client:
        yield start(wrap(client), config, texts, scenario, log, seed=seed)


@contextmanager
def _exits_on_refusal(console: Console) -> Iterator[None]:
    try:
        yield
    except RunExists as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
    except ModelError as exc:
        console.print(f"[red]Model error: {exc}[/red]")
        raise typer.Exit(1) from exc


@app.command()
def play(
    scenario: ScenarioOption,
    seed: SeedOption,
    runs: RunsOption = RUNS,
    mode: ModeOption = Mode.BEGINNER,
) -> None:
    """Play a scenario interactively under condition D."""
    console = Console(highlight=False)
    loaded = load_scenario(scenario)
    with _exits_on_refusal(console), open_session(console, loaded, seed, runs, D) as session:
        console.print(f"[bold]{escape(loaded.display_name)}[/bold]  [dim]{AI_LABEL}[/dim]\n")
        console.print(loaded.opening_narration, markup=False)
        console.print()
        console.print(HINT, style="dim", markup=False)
        assert isinstance(session, Session), "play is always condition D"
        _loop(console, session, mode)


@app.command()
def guide() -> None:
    """Show the how-to-play guide for players new to role-playing games."""
    Console(highlight=False).print(how_to_play())


@app.command()
def run(
    scenario: ScenarioOption,
    seed: SeedOption,
    condition: Annotated[str, typer.Option(help="Experimental condition: A, B, C or D.")] = D,
    runs: RunsOption = RUNS,
) -> None:
    """Run a scenario's scripted inputs unattended, under any condition."""
    console = Console(highlight=False)
    if condition not in CONDITIONS:
        console.print(f"[red]Unknown condition {condition}; choose one of A, B, C, D.[/red]")
        raise typer.Exit(2)
    if condition not in HARNESSES:
        console.print(f"[red]Condition {condition} is not wired yet.[/red]")
        raise typer.Exit(2)
    loaded = load_scenario(scenario)
    with (
        _exits_on_refusal(console),
        open_session(console, loaded, seed, runs, condition) as session,
    ):
        total = len(loaded.scripted_inputs)

        def report(index: int, turn: PlayedTurn) -> None:
            kind = turn.record["turn_failure"] or "ok"
            console.print(f"input {index + 1}/{total}: {kind}", markup=False)

        run_script(session, on_turn=report)
        _report(console, session)


@app.command()
def smoke(
    manifest: Annotated[
        Path, typer.Option(exists=True, dir_okay=False, help="Smoke manifest JSON file.")
    ] = Path("experiments/smoke_grid.json"),
    runs: RunsOption = RUNS,
    out: Annotated[Path, typer.Option(help="Directory the summary is written under.")] = (
        SMOKE_RESULTS
    ),
) -> None:
    """Play the smoke runs of a manifest and report gate G2 (WBS 6.11)."""
    console = Console(highlight=False)
    config = load_model_config()

    def runner(scenario: Scenario, seed: int, runs_dir: Path) -> None:
        with open_session(console, scenario, seed, runs_dir, D) as session:
            total = len(scenario.scripted_inputs)

            def report(index: int, turn: PlayedTurn) -> None:
                kind = turn.record["turn_failure"] or "ok"
                console.print(f"  input {index + 1}/{total}: {kind}", markup=False)

            run_script(session, on_turn=report)

    started = datetime.now(UTC)
    summary = smoke_runs.smoke(
        smoke_runs.load_manifest(manifest),
        runs_dir=runs,
        runner=runner,
        k=config.K_verbatim_turns,
        log=lambda line: console.print(line, markup=False),
    )
    summary = {
        "started": started.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "finished": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "manifest": manifest.as_posix(),
        "model": config.model,
        "model_digest": config.model_digest,
        **summary,
    }
    path = smoke_runs.write_summary(summary, out / started.strftime("%Y%m%dT%H%M%SZ"))
    smoke_runs.report(console, summary)
    console.print(f"Summary: {path}", markup=False)


@app.command()
def batch(
    manifest: Annotated[
        Path, typer.Option(exists=True, dir_okay=False, help="Batch manifest JSON file.")
    ] = Path("experiments/main_grid.json"),
    runs: RunsOption = RUNS,
    ledger: Annotated[Path, typer.Option(help="Attempt ledger, appended to.")] = BATCH_LEDGER,
    max_attempts: Annotated[
        int, typer.Option(min=1, help="Attempts per run before it is left pending.")
    ] = batch_runs.MAX_ATTEMPTS,
) -> None:
    """Play every run of a batch manifest that is not complete yet (WBS 7.6)."""
    console = Console(highlight=False)
    config = load_model_config()
    try:
        plan = batch_runs.load_manifest(manifest, HARNESSES)
    except batch_runs.ManifestError as exc:
        console.print(f"[red]{escape(str(exc))}[/red]")
        raise typer.Exit(2) from exc

    def runner(planned: batch_runs.PlannedRun, staging: Path) -> int:
        counter: list[RetryCountingClient] = []

        def wrap(client: ModelClient) -> ModelClient:
            counter.append(RetryCountingClient(client))
            return counter[0]

        with open_session(
            console, planned.scenario, planned.seed, staging, planned.condition, wrap
        ) as session:
            run_script(session)
        return counter[0].transport_retries

    context = {
        "manifest": manifest.as_posix(),
        "model": config.model,
        "model_digest": config.model_digest,
    }
    try:
        result = batch_runs.run_batch(
            plan,
            runs_dir=runs,
            runner=runner,
            ledger=ledger,
            max_attempts=max_attempts,
            context=context,
            log=lambda line: console.print(line, markup=False),
        )
    except KeyboardInterrupt:
        console.print("Interrupted. Run the same command again to resume.", markup=False)
        raise typer.Exit(130) from None
    _batch_report(console, plan, result)
    if not result.done:
        raise typer.Exit(1)


def _batch_report(
    console: Console, plan: list[batch_runs.PlannedRun], result: batch_runs.BatchResult
) -> None:
    complete = set(result.complete)
    for condition in dict.fromkeys(r.condition for r in plan):
        ids = [r.run_id for r in plan if r.condition == condition]
        done = sum(1 for i in ids if i in complete)
        console.print(f"{condition}: {done}/{len(ids)} complete", markup=False)
    console.print(
        f"{len(complete)}/{result.planned} runs complete, {result.played} attempts played.",
        markup=False,
    )
    for label, ids in (("Errors", result.errors), ("Pending", result.pending)):
        if ids:
            console.print(f"{label}: {', '.join(ids)}", markup=False)
    if result.stopped is not None:
        console.print(f"Stopped: {result.stopped}", markup=False)


def _loop(console: Console, session: Session, mode: Mode) -> None:
    # Ctrl+C mid-turn ends the session too: that turn is not logged. The mode
    # only reaches display code, never the session (CLAUDE.md item 75).
    # Hints are shown when the state may have changed: at the start and after
    # each turn, not again after a command or a blank line.
    fresh = True
    try:
        while True:
            if fresh and mode is Mode.BEGINNER:
                block = hint_block(session.state.model_copy(deep=True))
                if block is not None:
                    console.print(f"\n{block}", style="dim", markup=False)
            fresh = False
            try:
                text = console.input(f"\n{PROMPT}").strip()
            except EOFError:
                break
            if not text:
                continue
            if is_command(text):
                # A copy: display code never touches the game state (invariant 1).
                command = run_command(text, session.state.model_copy(deep=True), mode)
                console.print(command.renderable)
                if command.quit:
                    break
                continue
            with console.status("The Dungeon Master is thinking..."):
                turn = session.play(text)
            console.print()
            state = session.state.model_copy(deep=True)
            for line in result_lines(turn.record, state, mode):
                console.print(line, style="dim", markup=False)
            console.print(turn.message, markup=False)
            fresh = True
    except KeyboardInterrupt:
        pass
    _report(console, session)


def _report(console: Console, session: Harness) -> None:
    records = session.log.records()
    failures = sum(turn_failure_counts(records).values())
    console.print(
        f"\n{len(records)} turns ({failures} failed) logged to {session.log.path}",
        markup=False,
    )


if __name__ == "__main__":
    app()
