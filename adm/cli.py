"""The text command-line client (WBS 6.10, 6.11): the composition root of
docs/conventions.md section 1. It reads `config/`, wires the packages and holds
no game logic.

    python -m adm.cli play --scenario scenarios/s01_cellar.json --seed 12345
    python -m adm.cli run --scenario scenarios/s01_cellar.json --condition D --seed 12345
    python -m adm.cli smoke --manifest experiments/smoke_grid.json

`play` is an interactive condition D session. The model is checked against
`config/model.json` and freshly loaded first (docs/model_selection.md section 4).
The player sees the scenario's title and opening narration, then types one
input per turn and reads the narration; a failed turn shows the request to
rephrase. `/quit`, end of input or Ctrl+C ends the session. Every turn is in
`runs/D/<scenario_id>/<seed>.jsonl` (CLAUDE.md section 11) as soon as it is shown.

`run` plays the scenario's scripted inputs unattended (`session.run_script`),
printing one line per input. Only condition D exists so far; A to C join the
same command with their harnesses (WBS 7.1 to 7.4). An exception other than a
refused run or a model error is a bug and propagates.

`smoke` plays every run of a smoke manifest that has no log yet, as `run` does,
and reports gate G2 (WBS 6.11, `adm/bench/smoke.py`). An exception ends only
its own run, which is then unrecoverable; the summary goes to
`results/bench/smoke/<UTC time>/summary.json`.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from adm.bench import smoke as smoke_runs
from adm.engine.audit import turn_failure_counts
from adm.engine.scenario import Scenario, load_scenario
from adm.orchestration.client import (
    ModelClient,
    ModelConfig,
    ModelError,
    OllamaClient,
    load_model_config,
)
from adm.orchestration.loop import CONDITION, FailedTurn, NarratedTurn
from adm.orchestration.prompt import load_templates
from adm.orchestration.session import RunExists, Session, new_run_log, run_script

QUIT = {"/quit", "/exit"}
PROMPT = "> "
RUNS = Path("runs")
SMOKE_RESULTS = Path("results/bench/smoke")

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


@contextmanager
def open_session(console: Console, scenario: Scenario, seed: int, runs: Path) -> Iterator[Session]:
    """A new condition D session on a freshly loaded model. A run that already
    has a log is refused before the model loads."""
    config = load_model_config()
    texts = load_templates()
    log = new_run_log(runs, scenario.scenario_id, seed)
    with console.status(f"Loading {config.model}..."):
        client_cm = connect(config)
    with client_cm as client:
        yield Session.start(client, config, texts, scenario, log, seed=seed)


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
def play(scenario: ScenarioOption, seed: SeedOption, runs: RunsOption = RUNS) -> None:
    """Play a scenario interactively under condition D."""
    console = Console(highlight=False)
    loaded = load_scenario(scenario)
    with _exits_on_refusal(console), open_session(console, loaded, seed, runs) as session:
        console.print(f"[bold]{loaded.display_name}[/bold]\n")
        console.print(loaded.opening_narration, markup=False)
        _loop(console, session)


@app.command()
def run(
    scenario: ScenarioOption,
    seed: SeedOption,
    condition: Annotated[str, typer.Option(help="Experimental condition.")] = CONDITION,
    runs: RunsOption = RUNS,
) -> None:
    """Run a scenario's scripted inputs unattended."""
    console = Console(highlight=False)
    if condition != CONDITION:
        console.print(f"[red]Condition {condition} is not wired yet (WBS 7.1 to 7.4).[/red]")
        raise typer.Exit(2)
    loaded = load_scenario(scenario)
    with _exits_on_refusal(console), open_session(console, loaded, seed, runs) as session:
        total = len(loaded.scripted_inputs)

        def report(index: int, turn: NarratedTurn | FailedTurn) -> None:
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
        with open_session(console, scenario, seed, runs_dir) as session:
            total = len(scenario.scripted_inputs)

            def report(index: int, turn: NarratedTurn | FailedTurn) -> None:
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


def _loop(console: Console, session: Session) -> None:
    # Ctrl+C mid-turn ends the session too: that turn is not logged.
    try:
        while True:
            try:
                text = console.input(f"\n{PROMPT}").strip()
            except EOFError:
                break
            if text in QUIT:
                break
            if not text:
                continue
            with console.status("The Dungeon Master is thinking..."):
                turn = session.play(text)
            console.print(f"\n{turn.message}", markup=False)
    except KeyboardInterrupt:
        pass
    _report(console, session)


def _report(console: Console, session: Session) -> None:
    records = session.log.records()
    failures = sum(turn_failure_counts(records).values())
    console.print(
        f"\n{len(records)} turns ({failures} failed) logged to {session.log.path}",
        markup=False,
    )


if __name__ == "__main__":
    app()
