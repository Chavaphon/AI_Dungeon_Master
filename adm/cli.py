"""The text command-line client (WBS 6.10): the composition root of
docs/conventions.md section 1. It reads `config/`, wires the packages and holds
no game logic.

    python -m adm.cli play --scenario scenarios/s01_cellar.json --seed 12345

`play` is an interactive condition D session. The model is checked against
`config/model.json` and freshly loaded first (docs/model_selection.md section 4).
The player sees the scenario's title and opening narration, then types one
input per turn and reads the narration; a failed turn shows the request to
rephrase. `/quit`, end of input or Ctrl+C ends the session. Every turn is in
`runs/D/<scenario_id>/<seed>.jsonl` (CLAUDE.md section 11) as soon as it is shown.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from adm.engine.audit import turn_failure_counts
from adm.engine.scenario import load_scenario
from adm.orchestration.client import (
    ModelClient,
    ModelConfig,
    ModelError,
    OllamaClient,
    load_model_config,
)
from adm.orchestration.prompt import load_templates
from adm.orchestration.session import RunExists, Session, new_run_log

QUIT = {"/quit", "/exit"}
PROMPT = "> "
RUNS = Path("runs")

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


@app.command()
def play(
    scenario: Annotated[
        Path, typer.Option(exists=True, dir_okay=False, help="Scenario JSON file.")
    ],
    seed: Annotated[int, typer.Option(help="Run seed: fixes the dice and the model's sampling.")],
    runs: Annotated[Path, typer.Option(help="Directory the audit log is written under.")] = RUNS,
) -> None:
    """Play a scenario interactively under condition D."""
    console = Console(highlight=False)
    config = load_model_config()
    texts = load_templates()
    loaded = load_scenario(scenario)

    try:
        log = new_run_log(runs, loaded.scenario_id, seed)
        with console.status(f"Loading {config.model}..."):
            client_cm = connect(config)
        with client_cm as client:
            session = Session.start(client, config, texts, loaded, log, seed=seed)
            console.print(f"[bold]{loaded.display_name}[/bold]\n")
            console.print(loaded.opening_narration, markup=False)
            _loop(console, session)
    except RunExists as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
    except ModelError as exc:
        console.print(f"[red]Model error: {exc}[/red]")
        raise typer.Exit(1) from exc


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

    records = session.log.records()
    failures = sum(turn_failure_counts(records).values())
    console.print(
        f"\n{len(records)} turns ({failures} failed) logged to {session.log.path}",
        markup=False,
    )


if __name__ == "__main__":
    app()
