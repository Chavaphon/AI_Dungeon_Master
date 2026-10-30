# Smoke runs: Milestone 1 / gate G2

WBS 6.11 · Owner: CI · Run 2026-10-30 · CLAUDE.md wins on any conflict.

The evidence for Milestone 1 / gate G2 and the Objective 2 criterion: ten scripted condition D runs of 50 or more turns, of which at least nine must complete without an unrecoverable failure (TASK_CHECKLIST.md). What "complete" means, the grid and the scenario-DC rule are in `docs/decisions.md` (2026-10-30, WBS 6.11).

## 1. Verdict

| Check | Threshold | Result |
|---|---|---|
| Gate G2 / Objective 2: runs complete | ≥ 9 of 10 | **10 of 10. Met.** Condition C stays in the ladder. |
| Risk R1: first-attempt schema-valid rate | ≥ 80% | **99.0%** (515 of 520 turns). Not fired; the WBS 3.7 prompt-mode decision stands. |
| Long scenarios: summary regenerations (CLAUDE.md §12) | ≥ 5 per run | 6 in every run |
| Invariant 4 (replay) | identical | Seed 1009 was played twice (§4); the 51 records the two attempts share are identical apart from the timings. |

## 2. Set-up

| Item | Value |
|---|---|
| Machine | docs/hardware.md §1 (RTX 5060 Laptop, 8 GiB) |
| Model | `llama3.1:8b`, `sha256:46e0c10c…ca666e`, as pinned in `config/model.json` |
| Ollama | 0.35.1, reinstalled for these runs from the GitHub release (installer SHA-256 checked). 0.40.13 had been installed by the tray app's auto-update, and the client refuses it. The runs used a bare `ollama serve`, with no tray app and so no auto-update. |
| Grid | `experiments/smoke_grid.json`: long01 and long02 × 3 seeds, long03 and long04 × 2, seeds 1001–1010, 52 scripted inputs each |
| Command | `python -m adm.cli smoke --manifest experiments/smoke_grid.json` |
| Summary | `results/bench/smoke/20261030T120009Z/summary.json` (gitignored); logs in `runs/D/<scenario_id>/<seed>.jsonl` (gitignored) |

## 3. Per run

"Rejected" is turns with at least one rejected or unparseable attempt; "recovered" is those that still executed a call or ended narration-only. Latency is `turn_latency_ms`; tokens per second is `completion_tokens / eval_ms`, mean over model calls (M6).

| Run | Complete | Records | Final turn | Failed turns | Narration-only | Schema-valid 1st | Recovered / rejected | Mean s | p95 s | tok/s |
|---|---|---|---|---|---|---|---|---|---|---|
| long01 1001 | yes | 52/52 | 52 | 0 | 3 | 51 | 12 / 12 | 5.89 | 9.13 | 46.7 |
| long01 1002 | yes | 52/52 | 52 | 0 | 3 | 51 | 12 / 12 | 5.14 | 8.74 | 55.0 |
| long01 1003 | yes | 52/52 | 52 | 0 | 1 | 52 | 7 / 7 | 4.75 | 8.34 | 57.9 |
| long02 1004 | yes | 52/52 | 52 | 0 | 0 | 52 | 8 / 8 | 4.55 | 7.76 | 58.1 |
| long02 1005 | yes | 52/52 | 52 | 0 | 0 | 51 | 5 / 5 | 4.69 | 8.51 | 58.1 |
| long02 1006 | yes | 52/52 | 50 | 2 | 0 | 51 | 9 / 11 | 4.55 | 8.62 | 58.4 |
| long03 1007 | yes | 52/52 | 51 | 1 | 4 | 52 | 12 / 13 | 4.79 | 8.14 | 58.4 |
| long03 1008 | yes | 52/52 | 52 | 0 | 0 | 51 | 10 / 10 | 4.65 | 8.01 | 58.1 |
| long04 1009 | yes | 52/52 | 51 | 1 | 1 | 52 | 17 / 18 | 4.78 | 8.05 | 58.4 |
| long04 1010 | yes | 52/52 | 51 | 1 | 2 | 52 | 10 / 11 | 4.55 | 8.29 | 58.5 |
| **Total** | **10/10** | 520 | | **5** (1.0%) | 14 | **99.0%** | **102 / 107** (95.3%) | 4.83 | max 9.13 | |

No turn needed K reduced (CLAUDE.md §8). Each run started one encounter. Rejected turns were 20.6% of all turns (M2's shape; not the M2 figure, which comes from the main grid).

## 4. What went wrong, and what it means

**Turn failures (5).** All are `precondition`, and all come from the script outrunning the fight. That is expected: decision 23 keeps scripted inputs fixed however long an encounter lasts.

| Run | Input | Attempts | Player input |
|---|---|---|---|
| long02 1006 | 35 | `ENCOUNTER_OVER`, `NO_SPELL_SLOT`, `ENCOUNTER_OVER` | I cast fire bolt at the armour again |
| long02 1006 | 37 | null re-prompted, `NO_SPELL_SLOT`, `ENCOUNTER_OVER` | I say a prayer over my own wounds |
| long03 1007 | 25 | `ENCOUNTER_OVER`, `ITEM_NOT_DEFINED`, `ITEM_NOT_DEFINED` | I haul the net off his rack while his men watch |
| long04 1009 | 44 | `ENCOUNTER_OVER`, `NO_SPELL_SLOT`, `ENCOUNTER_OVER` | I burn the second harpy if it is still in the air |
| long04 1010 | 44 | `ENCOUNTER_OVER`, `NO_SPELL_SLOT`, `ENCOUNTER_OVER` | I burn the second harpy if it is still in the air |

The model does not give up on an attack once the encounter is over. It swaps to Cure Wounds with no slot left, then goes back to the attack. In 1007 it tried to give the player an item the scenario does not define. These are candidates for the M3 sample and for the report's failure discussion. They are not engine faults.

**Rejections by code**, over all attempts: `ENCOUNTER_OVER` 69, `RELATIONSHIP_STEP_TOO_LARGE` 14, `NOT_A_CASTER` 10, `NO_SPELL_SLOT` 8, `ILLEGAL_QUEST_TRANSITION` 7, `NEGATIVE_QUANTITY` 7, `SCHEMA_VIOLATION` 5, `TARGET_UNCONSCIOUS` 5, `ITEM_NOT_DEFINED` 5, unparseable 2, `SKILL_NOT_SUPPORTED` 1. Format errors (unparseable plus `SCHEMA_VIOLATION`) are 7 of 133.

**An interrupted attempt.** The first attempt at long04 seed 1009 was stopped at 51 of 52 inputs when Claude Code's memory-pressure guard ended the background shell. The Ollama server and the driver were both stopped; the system under test raised nothing. The partial log was moved to `runs/aborted/D/long04_mountain_monastery/1009.jsonl`, and the run was played again from the start on a freshly loaded model. Its first 51 records match the aborted ones in every field except `timestamp`, `latency_ms`, `eval_ms` and `turn_latency_ms`, raw model output included. That is a cross-process check of invariant 4 and decision 25.

**Throughput.** Run 1001 was the slowest (46.7 tok/s, mean 5.9 s per turn); runs from 1003 on settled at about 58 tok/s. The cause, probably the first load after reinstalling Ollama, was not investigated. M6 is measured on the main grid.

## 5. Follow-ups

- The Ollama tray app is set to start at login and auto-updates. Before the Week 6 batches, turn that off or run a bare `ollama serve`. Otherwise the pinned-version check will stop the batch.
- Nothing here blocks WBS 7.x. Condition D is ready to join the common runner (7.4).
