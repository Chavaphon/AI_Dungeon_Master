# AI_Dungeon_Master

A text-based Dungeon Master for a small D&D-style game, played alone in a terminal. A local language model narrates; a deterministic rules engine owns the game state and resolves every roll, so the story cannot invent items or forget damage. It is for people who want to play D&D alone or do not know how to start. Built with Llama.

## Playing the game

You need Python 3.11, [Ollama](https://ollama.com) 0.35.1 and a GPU with about 8 GB of memory (the model is `llama3.1:8b` at Q4_K_M; `config/model.json` pins the exact version). Nothing is sent to the internet while you play.

```bash
ollama pull llama3.1:8b
python -m venv .venv
source .venv/bin/activate        # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -e .
python -m adm.cli play
```

With no options, `play` shows a numbered menu of the scenarios (name, short or long, number of turns) and draws a random seed, which it prints at the start and the end with the command that replays the same game: `python -m adm.cli play --scenario scenarios/s01_cellar.json --seed 123456`. Giving `--scenario` and `--seed` skips the menu and the draw.

The title is labelled **Narrated by AI**. Type what your character does in plain English, for example `I draw my sword and attack the nearest rat`. Each turn first shows a result line for every outcome the engine resolved, then the narration. The game starts in beginner mode, which says what happened in plain words ("You hit giant rat 2 with your short sword. Giant rat 2 is wounded.") with no dice numbers, and before each input suggests two to four things you could type ("You could try: attack the giant rat 1 with your short sword"); `--mode veteran` shows the rolls, AC, DC and hit points ("Lyra -> giant rat (short sword): 17 vs AC 12, hit, 7 damage; giant rat 4/11 HP"). Both modes play and log the same game. Commands starting with `/` are for you, not the Dungeon Master (the game reminds you under the opening): `/help`, `/status`, `/inventory`, `/quests`, `/rules` and `/glossary` show information without using a turn, and `/quit`, Ctrl+C or end of input ends the session. The sixteen scenarios are in `scenarios/`; any seed works, but each `(scenario, seed)` can be played once per log folder.

### Sponsor User sessions

Friends who try development builds play into their own folder, so their sessions never mix with the experiment data in `runs/`:

```bash
python -m adm.cli play --scenario scenarios/s01_cellar.json --seed 12345 --runs sponsor_runs
```

`sponsor_runs/` is gitignored and is never uploaded or scored. This is informal feedback, not a study (CLAUDE.md §14).

## Licence

Code, scenarios and released data are under the MIT License (`LICENSE`). The rules are adapted from the System Reference Document 5.1 under CC-BY-4.0, and the model is used under the Llama 3.1 Community License; see `NOTICE`.

The code and the main-grid dataset are released at the git tag `release-v1.0`: the dataset is one archive attached to that GitHub release, checked against its sha256 in `docs/release.md`. How to check it, replay it and recompute every result is in `docs/report/appendix_a_release.md`.

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
| `tests/play/test_commands.py` | Each slash command of `adm/play/commands.py` shows what the state holds (the player's own items, quests, health and the fight's turn order, with shared names numbered), ignores case and arguments, names an unknown command, and leaves the state hash unchanged; in beginner mode no command shows dice notation or AC, DC or HP |
| `tests/play/test_hints.py` | Across every scripted session (16 scenarios, seeds 2001–2003), every beginner hint is a call the validator accepts in that state, there are 2 to 4 of them (none for a knocked-out player), they are plain words, fixed in order, leave the state unchanged and never roll a die |
| `tests/play/test_picker.py` | The menu lists every scenario with its name, length and turns, the tutorial first and marked "Start here", then short, then long; a menu number names one row; a drawn seed is six digits and never an experiment seed |
| `tests/play/test_results.py` | Every tool has a veteran result line (rolls, AC, DC) and a beginner one in plain words with no jargon; lines follow the order of the turn, call the player "you" and number shared names; a failed turn has no player line |
| `tests/play/test_vocabulary.py` | The beginner vocabulary is #255's table, and the jargon pattern finds dice notation, modifiers and AC, DC, HP but not plain words |
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
| `tests/eval/test_integrity.py` | `python -m adm.eval.integrity` passes a clean batch played through the real batch runner, and reports as a gap a planned run with no log, a log cut short, a log the validator rejects, a run with no ledger line or whose last attempt did not complete, and a complete line with a transport retry, another record count or another seed; it lists earlier failed attempts, pending and aborted logs, stray files and empty narrations without failing, fails runs played with two models or a cell missing a seed, keeps the main grid's seeds out of the other experiments, and writes checksums a later copy is checked against |
| `tests/eval/test_m1.py` | The M1 sample is one seed per scenario with all four conditions at it, fixed by hash with no RNG, 64 runs on the main grid; a seed missing a condition, and smoke logs, are never drawn; the overlap is a fifth of each condition, 16 runs; each annotator has their own run order; a turn shows its checker candidates and nothing that names the condition, run or seed; `annotate m1` records confirmations and additions with their spans, asks again on a bad answer, resumes, and replaces a line on `--redo` with a note; an AI draft is checked against the sample (every turn once, candidate numbers, categories, phrases in the narration), shown under each turn, accepted with Enter or edited, kept on the line with its review status, and refused for the overlap |
| `tests/eval/test_m1_rates.py` | M1 counts confirmed candidates plus added labels in the four rubric categories, from the first annotator only; labels that miss a sampled turn, repeat one, add one or were shown other candidates are refused; rates are pooled per 100 narrated turns; the D/A ratio and H1 follow the pooled rates with a reproducible bootstrap, and H1 fails when the ratio is above 0.5 or its interval reaches 1 |
| `tests/eval/test_agreement.py` | M1 agreement counts rubric categories only and reports each annotator's review counts; identical labels give alpha 1; Objective 3 is the pooled M1 alpha against 0.6; M5 ratings must pair one per excerpt of the key, within 1 to 5; M5 alpha is ordinal per item with exact agreement and means, undefined with no spread |
| `tests/eval/test_m5_scores.py` | The M5 key gives one excerpt per scenario and condition at one seed; an excerpt's score is the mean of the two raters; D − A per item with the run-level bootstrap and its reading rule (worse only when the interval lies below 0); each rater alone, paired by scenario, short against long |
| `tests/eval/test_m1_growth.py` | RQ2 positions are `input_index + 1`, so a failed turn leaves a gap; labels are checked as in 10.1; the slope is least squares pooled over turns, scaled per 100 turns per 10 turns, undefined without spread; the difference from A, the `PHANTOM`-free slope and the position bins, the last open-ended, follow; RQ2 uses only the long sessions, and the report is reproducible |
| `tests/eval/test_figures.py` | The figures draw the 10.1 rates and ratios to A, the 10.2 bins and slopes and the per-category rates with counts, in condition order; reports of different labels or bootstraps, or missing a condition, interval or bin, are refused; input hashes ignore line endings; with matplotlib, the six files are written and a second run gives the same bytes |
| `tests/eval/test_catalogue.py` | A turn's labels are its confirmed candidates and added labels; a slot takes only its condition, category and source, and skips a turn the 9.6 overlap contests; the draw takes the first unused turn in hash order, and stops when a slot or an M3 turn cannot be found; each slot is filled by its own turn; attempts, facts in play order, the qualified state snapshot and the bolded narration follow the record |
| `tests/eval/test_exhibit.py` | Only combat inputs where D executed the expected tool pair up, and only when both A and D narrated; row 1 needs a `CONTRADICT` or `RULE` label in A and none in D, row 2 a `CONTRADICT` in D; the draw takes the first in hash order on different inputs and stops when a row is empty; each side shows its named combatants' truth and D its facts; the measured 10.1 result is on the slide; with matplotlib the slide's bytes repeat |
| `tests/eval/test_release.py` | `LICENSE` and `NOTICE` carry the MIT licence, the SRD 5.1 attribution and the Llama 3.1 notice, and a notice without them is refused; every annotation has its own full pin; the logs come from the checksum file; a missing or changed file is named, and one under another file's name is pointed out; the archive is refused with every problem, holds its files byte for byte with `SHA256SUMS` and repeats byte for byte |
| `tests/engine/test_dice.py` | `adm/engine/dice.py` parses only the `XdY+Z` of CLAUDE.md §4.2, reproduces a pinned sequence from a seed, keeps the right die under advantage and disadvantage, and returns rolls that match `roll_result` in the tool contract |
