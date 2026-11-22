# Appendix A. Reproduction and release

<!-- WBS 11.11 · Owner: SS · Reviewer (11.6): CI · Outline: docs/report_outline.md, Appendices · Draft 2026-11-20 -->

This appendix says where the code and data are, under which licences, and how to check the dataset, replay it and recompute every result in Section 5. Each command runs from the root of the repository. How the release is built and published is in `docs/release.md`.

## A.1 Repository and licence

| Item | Where | Licence |
|---|---|---|
| Code, scenarios, prompts, schemas and documentation | https://github.com/Chavaphon/AI_Dungeon_Master, git tag `release-v1.0` | MIT (`LICENSE`) |
| Dataset | `adm-dataset-v1.0.zip`, attached to the `release-v1.0` GitHub release; sha256 in `docs/release.md` §4 | MIT (`LICENSE`) |
| Game rules | a small, simplified subset adapted from the System Reference Document 5.1 by Wizards of the Coast LLC | CC-BY-4.0, attributed in `NOTICE` |
| Language model | `llama3.1:8b`, Q4_K_M, digest in `config/model.json`; not redistributed | Llama 3.1 Community License (`NOTICE`). Built with Llama. |

The rules are not compatible with Dungeons & Dragons 5th edition, and are not described as such. `NOTICE` gives the SRD 5.1 attribution in the wording CC-BY-4.0 asks for. `tests/eval/test_release.py` checks on every commit that `LICENSE` and `NOTICE` hold the licence and both notices.

## A.2 The dataset

| Files | What they are | Pinned by |
|---|---|---|
| `runs/{A,B,C,D}/{scenario_id}/{2001,2002,2003}.jsonl` | The 192 main-grid audit logs, 6,420 turn records (Section 4.3) | `experiments/main_grid.sha256`, in the repository |
| `results/batch/attempts.jsonl` | The batch runner's attempt ledger, one line per run | `docs/decisions.md`, 2026-11-20 |
| `results/m1_labels.jsonl`, `results/m1_labels_SS.jsonl` | M1 labels: SD on the 64-run sample, SS on the 16-run overlap | `docs/m1_annotation.md`, `docs/m1_overlap.md` |
| `results/m3_intent.jsonl` | M3 verdicts, CI, 242 turns | `docs/m3_annotation.md` |
| `results/m5_ratings.jsonl`, `results/m5_ratings_SS.jsonl`, `results/m5_key.json` | M5 ratings by SD and SS, and the key from excerpt to run | `docs/m5_rating_sd.md`, `docs/m5_rating_ss.md`, `docs/decisions.md` |
| `results/m1_draft_claude.jsonl`, `results/m1_overlap_draft_claude.jsonl`, `results/m3_draft_claude.jsonl` | The AI drafts the annotators reviewed (Sections 4.6 and 4.7) | the same documents |
| `dataset/README.md`, `dataset/LICENSE`, `dataset/NOTICE` | The archive's notes (also the release notes), the MIT licence and the SRD 5.1 and Llama 3.1 notices | `dataset/SHA256SUMS` |
| `dataset/SHA256SUMS` | The sha256 of every other file in the archive | the archive's sha256 |

Annotators are named by initials. There is no player data: the player inputs are the scenarios' scripted inputs. The logs end their lines in CRLF, as written, and their checksums are of those bytes, so the archive must be unpacked as binary files.

## A.3 Setting up

Python 3.11. The analysis needs the `analysis` extra; replaying the state needs nothing else; playing a run again also needs the model (A.6).

```bash
git clone https://github.com/Chavaphon/AI_Dungeon_Master && cd AI_Dungeon_Master
git checkout release-v1.0
python -m venv .venv && source .venv/bin/activate   # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -e ".[dev,analysis]"
pytest -q                                            # the test suite, the 60-case rule suite included
unzip adm-dataset-v1.0.zip                           # the release asset, into the repository root
```

## A.4 Checking the dataset

```bash
sha256sum -c dataset/SHA256SUMS
python -m adm.eval.integrity --manifest experiments/main_grid.json --checksums experiments/main_grid.sha256
```

The second command (Section 4.3, `docs/run_integrity.md`) exits 0 only when all 192 planned runs are present and valid, the ledger shows each one completed with no transport retry, every cell has the three seeds, and every log has the checked bytes.

## A.5 Replaying the state without the model

Every turn record holds the state's hash before and after the turn, and its state diff. The run-log validator replays condition D's logs from their diffs and A to C's from the scripted replay, checking every hash on the way, together with the audit-log schema and script coverage:

```bash
python -m adm.eval.validate --runs runs --manifest experiments/main_grid.json
```

For conditions A to C, the state the narration is scored against is the scripted replay of Section 4.1: each input's `expected_call` played through the engine with the run's seed. `replay_script(scenario, seed)` in `adm/engine/replay.py` computes it, and two replays of one seed are byte-identical. Every analysis command below recomputes it rather than reading it from a file.

## A.6 Playing a run again with the model

A run is fixed by its scenario, condition and seed (invariant 4). To play one again, install Ollama 0.35.1 (`docs/hardware.md` §7) and the pinned model, start the model fresh, let nothing else use the server, and play into a separate folder:

```bash
ollama pull llama3.1:8b
python -m adm.cli run --scenario scenarios/s01_cellar.json --condition D --seed 2001 --runs replay_runs
python -c "import json, sys; from adm.engine.replay import log_differences; r = lambda p: [json.loads(l) for l in open(p, encoding='utf-8')]; print(log_differences(r(sys.argv[1]), r(sys.argv[2])) or 'identical')" runs/D/s01_cellar/2001.jsonl replay_runs/D/s01_cellar/2001.jsonl
```

`log_differences` compares every field except the timings (`timestamp`, `latency_ms`, `eval_ms`, `turn_latency_ms`). The client refuses any other Ollama version or model digest. Repeatability was checked on the machine that played the grid (`docs/model_selection.md` §3, `docs/hardware.md` §1). A different GPU or driver may give different model replies; that was not tested. The engine's part of a run does not depend on the machine.

## A.7 Recomputing the results

Each command with `--checksums` reads the logs and checks them against `experiments/main_grid.sha256` first; `m5_scores` reads the ratings and `figures` the M1 outputs, not the logs. Each command with `--doc` rewrites the results block of that document; the checker writes only its JSON Lines file, and M3 has no command. The bootstrap is seeded (20261101, 10,000 resamples), so a rerun gives the same values.

| Result (Section 5) | Command | Writes |
|---|---|---|
| Automated checker candidates | `python -m adm.eval.checker --runs runs/ --out results/automated.jsonl` | `results/automated.jsonl` |
| M1 per condition, H1 | `python -m adm.eval.m1_rates --checksums experiments/main_grid.sha256 --doc docs/m1_rates.md` | `docs/m1_rates.md`, `results/m1.json` |
| M1 growth, RQ2 | `python -m adm.eval.m1_growth --checksums experiments/main_grid.sha256 --doc docs/m1_growth.md` | `docs/m1_growth.md`, `results/m1_growth.json` |
| M2 | `python -m adm.eval.metrics m2 --checksums experiments/main_grid.sha256 --doc docs/m2_tool_calls.md` | `docs/m2_tool_calls.md` |
| M3 | counted from `results/m3_intent.jsonl`: x = 170 faithful of n = 242. The 95% Wilson interval is (p + z²/2n ± z·√(p(1−p)/n + z²/4n²)) / (1 + z²/n), with p = x/n and z = 1.96 | `docs/m3_annotation.md` §2 |
| M4 | `python -m adm.eval.metrics m4 --checksums experiments/main_grid.sha256 --doc docs/m4_rule_violations.md --labels results/m1_labels.jsonl` | `docs/m4_rule_violations.md` |
| M5, H2, RQ3 | `python -m adm.eval.m5_scores --m5-ratings results/m5_ratings.jsonl --m5-ratings results/m5_ratings_SS.jsonl --doc docs/m5_scores.md` | `docs/m5_scores.md` |
| M6, the latency target | `python -m adm.eval.metrics m6 --checksums experiments/main_grid.sha256 --doc docs/m6_latency.md` | `docs/m6_latency.md` |
| Agreement, Objective 3 | `python -m adm.eval.agreement --m1-labels results/m1_labels.jsonl --m1-labels results/m1_labels_SS.jsonl --m5-ratings results/m5_ratings.jsonl --m5-ratings results/m5_ratings_SS.jsonl --checksums experiments/main_grid.sha256 --doc docs/agreement.md` | `docs/agreement.md` |
| Figures 5.1 to 5.3 | `python -m adm.eval.figures --doc docs/figures.md` (after M1 and growth) | `docs/report/figures/` |
| Failure catalogue | `python -m adm.eval.catalogue --checksums experiments/main_grid.sha256 --doc docs/failure_catalogue.md` | `docs/failure_catalogue.md` |
| A versus D exhibit | `python -m adm.eval.exhibit --checksums experiments/main_grid.sha256 --doc docs/exhibit_a_vs_d.md` (after M1) | `docs/exhibit_a_vs_d.md`, `docs/report/figures/fig_a_vs_d.*` |

Values are what to compare. A document rewritten on another operating system can differ in its line endings, and a JSON output in its bytes, while every value matches.
