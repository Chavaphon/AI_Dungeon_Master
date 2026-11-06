# AI_Dungeon_Master

A text-based Dungeon Master for a small D&D-style game, played alone in a terminal. A local language model narrates; a deterministic rules engine owns the game state and resolves every roll, so the story cannot invent items or forget damage. It is for people who want to play D&D alone or do not know how to start. Built with Llama.

## Playing the game

You need Python 3.11, [Ollama](https://ollama.com) 0.35.1 and a GPU with about 8 GB of memory (the model is `llama3.1:8b` at Q4_K_M; `config/model.json` pins the exact version). Nothing is sent to the internet while you play.

```bash
ollama pull llama3.1:8b
python -m venv .venv
source .venv/bin/activate        # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -e .
python -m adm.cli play --scenario scenarios/s01_cellar.json --seed 12345
```

The title is labelled **Narrated by AI**. Type what your character does in plain English, for example `I draw my sword and attack the nearest rat`. Each turn first shows a result line for every roll the engine made (hit or miss, damage, hit points), then the narration. `/quit`, Ctrl+C or end of input ends the session. The sixteen scenarios are in `scenarios/`; any seed works, but each `(scenario, seed)` can be played once per log folder.

### Sponsor User sessions

Friends who try development builds play into their own folder, so their sessions never mix with the experiment data in `runs/`:

```bash
python -m adm.cli play --scenario scenarios/s01_cellar.json --seed 12345 --runs sponsor_runs
```

`sponsor_runs/` is gitignored and is never uploaded or scored. This is informal feedback, not a study (CLAUDE.md §14).

## Licence

Code, scenarios and released data are under the MIT License (`LICENSE`). The rules are adapted from the System Reference Document 5.1 under CC-BY-4.0, and the model is used under the Llama 3.1 Community License; see `NOTICE`.

## Shared storage

Run artefacts and transcripts do not go in git: `runs/` and `results/` are gitignored (CLAUDE.md §3). The team copy lives in one Google Drive folder on the KMUTT account (WBS 1.5):

**https://drive.google.com/drive/folders/1fIteuSKqAyhTU3uR6mfV6SzHdxLqoO9H**

Access is limited to the three team members. Sign in with your `@kmutt.ac.th` account; if you are asked to request access, ask Sudakarn.

```
AI_Dungeon_Master/
  runs/
    A/  B/  C/  D/     audit logs, runs/{condition}/{scenario_id}/{seed}.jsonl (CLAUDE.md §11)
    aborted/           partial or tainted attempts the batch runner played again (WBS 7.6)
    dry_run/           the WBS 7.7 dry run, same layout; kept out of the main grid's runs/{A..D}
  results/             checker output and scored metrics, e.g. results/automated.jsonl
  benchmarks/          Week 2 model benchmark output (WBS 3.4, 3.5)
  annotations/         human annotation sheets for M1, M3 and M5
```

Rules:

- **The Drive copy is the dataset.** A run counts once its `.jsonl` is uploaded to `runs/`. A run that exists only on one laptop does not exist.
- **Keep the same paths.** Upload `runs/` and `results/` with the same layout the code writes locally, so a download can be dropped back into the repository root and re-scored.
- **Never edit an audit log by hand.** Re-run it instead. If a run is replaced, upload the new file and note why in `docs/decisions.md`.
- **Scenario subfolders are created by the batch runner**, not by hand.

## Running the tests

One-time setup from the repository root (Python 3.11):

```bash
python -m venv .venv
source .venv/bin/activate        # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

Then:

```bash
pytest -q                                   # whole suite
pytest tests/test_state_schema.py -q        # one file
pytest tests/test_state_schema.py::test_three_examples_exist   # one test
pytest -k boundaries -q                     # tests whose name matches
pytest -m rule_suite -v                     # the 60-case rule suite of CLAUDE.md §13
pytest --cov=adm --cov-report=term-missing  # with coverage
```

Both quality gates must pass before any commit (CLAUDE.md §2):

```bash
pytest -q
ruff check . && ruff format --check .
```

No test calls the model or needs Ollama running; orchestration tests use a recorded-response fake client (CLAUDE.md §13).

| Test file | What it checks |
|---|---|
| `tests/test_boundaries.py` | Package import boundaries from `docs/conventions.md`, and that only `adm/engine/dice.py` imports `random` |
| `tests/test_state_schema.py` | `schemas/state.schema.json` accepts the examples in `schemas/examples/` and rejects states that break CLAUDE.md §4–5 |
| `tests/test_identifiers.py` | Id patterns in `schemas/state.schema.json` follow `docs/identifiers.md`, and every file in `scenarios/` is named after its id and stays in its own namespace |
| `tests/test_tool_contract.py` | `schemas/tools.schema.json` accepts the example calls and results, rejects ones that break CLAUDE.md §6, and matches the §6.1 and §6.3 tables and the matrix in `docs/tool_contract.md` |
| `tests/test_scenario_schema.py` | `schemas/scenario.schema.json` accepts the example scenario and every file in `scenarios/`, and rejects scenarios that break CLAUDE.md §12 |
| `tests/test_audit_log.py` | `schemas/audit.schema.json` accepts the example turn records and rejects records that break CLAUDE.md §7 and §11; the valid example replays to its after-hash |
| `tests/engine/test_state.py` | `adm/engine/state.py` loads and saves every example state without loss, validates against the schema on both, and hashes as `docs/conventions.md` §2 |
| `tests/engine/test_rule_suite.py` | The `rule_suite` markers give every CLAUDE.md §13 area its case count, 60 in all; no case is skipped or `xfail`; `docs/rule_suite.md` lists exactly the marked cases |
| `tests/engine/test_replay.py` | `adm/engine/replay.py` replays every scenario byte-identically from its seed, chains the state hashes from turn 0, and plays rejected and null expected calls as a scripted condition D turn does; `log_differences` ignores only the timings |
| `tests/orchestration/test_narration_only.py` | The condition A, B and C harnesses run every scenario end to end with one narration call per input; A's prompt has no state or tools, B injects each input's ground-truth state byte for byte as condition D's tool call does, differing from A only by that block, and C differs from B only by the self-check instruction; their hashes and turn numbers are the replay's; K, history, summary and safety filter follow condition D; two runs of one seed differ only in the timings |
| `tests/orchestration/test_batch.py` | `adm/orchestration/batch.py` expands a manifest seed by seed, then scenario, then condition, and refuses a bad one; an interrupted batch resumes without playing a finished run again; a partial or tainted log is moved to `runs/aborted/` and the run played again; a model error on the last attempt or a config mismatch stops the batch; a bug ends only its own run |
| `tests/eval/test_entities.py` | `adm/eval/entities.py` finds exactly the `PHANTOM`s of the rubric's worked examples, counts a repeat once, skips scenery, parts and worn things, keeps an item at quantity 0 in scope, never flags an in-scope name in any scenario, and marks negated, ambiguous and proper-noun mentions low confidence |
| `tests/eval/test_bands.py` | `adm/eval/bands.py` implements the rubric §5 band rule: the C1, C3 and C4 examples, 14 of 20 is `wounded` with no adjacency allowance, intensity words, events, negations and figurative phrases skipped, each combatant scored once on its own HP, an unconscious combatant acting flagged, and stated HP numbers compared |
| `tests/eval/test_stance.py` | `adm/eval/stance.py` flags hostile narration of a neutral NPC and the rubric's L1 and L2 examples but not L3 and L4, scores only NPCs with a stance, forgives one step either side, skips negated markers, the party's own behaviour and mixed tones, and can name every stance NPC in every scenario |
| `tests/eval/test_rules.py` | `adm/eval/rules.py` finds no rule break in any scenario's ground truth, audits a broken state and out-of-turn or encounter-less actions, and flags narrated attacks after the encounter ended or by a combatant that did not act, Cure Wounds with no slot, and negative hit points |
| `tests/eval/test_checker_validation.py` | `adm/eval/checker_validation.py` draws a fixed 30-turn sample stratified 8/8/7/7 by condition, writes a labelling sheet with no condition, run id or checker output, matches each candidate to at most one overlapping label, and writes precision and recall into `docs/checker_validation.md` |
| `tests/eval/test_rubric_pilot.py` | `adm/eval/rubric_pilot.py` computes Krippendorff's alpha (checked against the published worked example and the `krippendorff` package), counts divergences per turn and category from two annotators' labels, lists their disagreements, and writes the results into `docs/rubric_pilot.md` |
| `tests/eval/test_checker.py` | `python -m adm.eval.checker` scores A–C turns on the replayed ground truth and D turns on the logged state, skips failed turns, refuses a log whose state does not match its hashes, and writes one candidate per line, the same bytes every run |
| `tests/eval/test_validate.py` | `python -m adm.eval.validate` passes a clean A–D grid and reports a record that breaks the schema or a rule it cannot express, a missing record, an input that is not the scripted text, a hash that does not replay, a log in another run's place, an empty log and a planned run with no log; it exits 0 only on a valid grid |
| `tests/engine/test_dice.py` | `adm/engine/dice.py` parses only the `XdY+Z` of CLAUDE.md §4.2, reproduces a pinned sequence from a seed, keeps the right die under advantage and disadvantage, and returns rolls that match `roll_result` in the tool contract |
