# Dry run: all four harnesses, gate G3

WBS 7.7 · Owner: CI · Run 2026-11-03 · CLAUDE.md wins on any conflict.

The evidence for deliverable D6 and the gate G3 item "all four harnesses dry-run": two scenarios played under conditions A, B, C and D through the batch runner, every log checked against the audit-log schema (TASK_CHECKLIST.md, done-when of 7.7). The choice of scenarios, seed and folder is in `docs/decisions.md` (2026-11-03, WBS 7.7).

## 1. Verdict

| Check | Threshold | Result |
|---|---|---|
| Runs complete (one record per scripted input) | 8 of 8 | **8 of 8**, each on its first attempt, no transport retry |
| Audit-log schema and `record_errors` (done-when) | every record | **312 of 312 records valid** (`python -m adm.eval.validate`, exit 0) |
| Same stimuli in every condition (invariant 7) | every input | every `player_input` is its scripted text |
| State hashes replay | every record | D replays from its diffs, A–C equal `replay_script`'s ground truth |
| Downstream tools read the logs | no error | the checker read all 8 runs: 189 `PHANTOM` candidates, no `LogMismatch` |

## 2. Set-up

| Item | Value |
|---|---|
| Machine | docs/hardware.md §1 (RTX 5060 Laptop, 8 GiB) |
| Model | `llama3.1:8b`, `sha256:46e0c10c…ca666e`, as pinned in `config/model.json`; 100% GPU throughout (`ollama ps`) |
| Ollama | 0.35.1, the standalone server of docs/hardware.md §7, version and digest checked before the batch |
| Grid | `experiments/dry_run.json`: `s01_cellar` (26 inputs) and `long01_border_road` (52 inputs) × A, B, C, D × seed 3001; 8 runs, 312 inputs |
| Commands | `python -m adm.cli batch --manifest experiments/dry_run.json --runs runs/dry_run --ledger results/dry_run/attempts.jsonl`, then `python -m adm.eval.validate --runs runs/dry_run --manifest experiments/dry_run.json --out results/dry_run/validation.json` and `python -m adm.eval.checker --runs runs/dry_run --out results/dry_run/automated.jsonl` |
| Output | logs in `runs/dry_run/{condition}/{scenario_id}/3001.jsonl`; ledger, validation report and checker output in `results/dry_run/` (all gitignored). 13:05 to 13:34 UTC, 29 minutes. |
| Shared copy | `runs/dry_run/` and `results/dry_run/`, uploaded 2026-11-03 to the team Drive folder at the same paths (`README.md`, "Shared storage") |

## 3. Per run

"Final turn" is the last record's `turn_number`; for A–C it comes from the replayed ground truth, so it repeats where an expected call is rejected (decision 49). "Rejected" is turns with at least one rejected or unparseable attempt; "recovered" is those that still executed a call or ended narration-only. Latency is `turn_latency_ms`; tokens per second is `completion_tokens / eval_ms`, mean over model calls.

| Run | Records | Final turn | Failed turns | Narration-only | Schema-valid 1st | Recovered / rejected | Summaries | K reduced | Max prompt tokens | Mean s | p95 s | tok/s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A s01 | 26/26 | 20 | – | – | – | – | 3 | 0 | 1249 | 3.46 | 8.66 | 38.1 |
| B s01 | 26/26 | 20 | – | – | – | – | 3 | 0 | 2516 | 4.21 | 9.18 | 36.5 |
| C s01 | 26/26 | 20 | – | – | – | – | 3 | 0 | 2499 | 4.78 | 9.21 | 33.6 |
| D s01 | 26/26 | 22 | 4 | 1 | 26 | 8 / 12 | 2 | 0 | 3786 | 5.19 | 8.24 | 42.0 |
| A long01 | 52/52 | 49 | – | – | – | – | 6 | 0 | 1278 | 3.25 | 8.09 | 42.2 |
| B long01 | 52/52 | 49 | – | – | – | – | 6 | 0 | 2914 | 4.50 | 10.54 | 38.4 |
| C long01 | 52/52 | 49 | – | – | – | – | 6 | 0 | 3027 | 8.08 | 17.82 | 19.6 |
| D long01 | 52/52 | 52 | 0 | 0 | 52 | 8 / 8 | 6 | 0 | 4549 | 6.50 | 12.24 | 41.1 |

No narration was changed by the safety filter. Every run of long01 regenerated the summary six times (CLAUDE.md §12 asks for five). No prompt came near the 8192-token context.

## 4. What it shows

**Turn failures (4, all D s01, all `precondition`).** Inputs 8 to 11 ("I slash at the second rat" and the three after it) came after the rats were down. Each turn went `ENCOUNTER_OVER`, `NO_SPELL_SLOT`, `ENCOUNTER_OVER`: the model swaps to Cure Wounds with no slot left and then back to the attack, the pattern of the G2 smoke runs (`docs/smoke_runs.md` §4). The script outrunning the fight is expected (decision 23). The replay of A–C has the same shape, which is why their final turn is below the input count.

**Rejections by code**, over all D attempts: `ENCOUNTER_OVER` 17, `NO_SPELL_SLOT` 5, `RELATIONSHIP_STEP_TOO_LARGE` 5, `ILLEGAL_QUEST_TRANSITION` 2, `SCHEMA_VIOLATION` 1. Every first attempt in both D runs was schema-valid.

**Timings are not representative.** A video game was running on the same GPU during the later runs. The model stayed at 100% GPU, so the replies are those of an idle machine, but C long01 (19.6 tok/s, p95 17.8 s) and D long01 (p95 12.2 s) are slowed by it. These figures are not M6 evidence; M6 comes from the main grid, which must run with nothing else on the GPU.

**Checker.** The 189 candidates (89 high confidence) by condition: A 52, B 51, C 35, D 51. They are unconfirmed and only show that the logs feed the checker; they are not a divergence result.

## 5. Follow-ups

- The eight logs are the transcripts for the 8.11 rubric pilot, and for timing a few M5 excerpts (`docs/narrative_quality.md` §7 point 1). Seed 3001 is in no main-grid cell, so pilot annotators see no transcript they will later rate.
- Run `python -m adm.eval.validate --runs runs --manifest experiments/main_grid.json` after each main-grid batch (WBS 9.1, 9.2).
