# Main run: the 4 long scenarios under all four conditions

WBS 9.2 · Owner: CI · Run 2026-11-10 · CLAUDE.md wins on any conflict.

The long-session part of the main grid (CLAUDE.md §10.5): `long01` to `long04` × conditions A, B, C, D × seeds 2001, 2002, 2003, 48 runs of 52 scripted inputs, played through the batch runner in one batch. Done when: "Complete, with turn index preserved for RQ2" (TASK_CHECKLIST.md, 9.2). Why one long-only batch is in `docs/decisions.md` (2026-11-10, WBS 9.2). The short scenarios are 9.1 (`docs/main_run.md`); with them, the main grid is complete.

## 1. Verdict

| Check | Threshold | Result |
|---|---|---|
| Runs complete (one record per scripted input) | 48 of 48 | **48 of 48**, each on its first attempt, no transport retry |
| Seeds recorded | every run | 2001, 2002, 2003 in every (scenario, condition) cell, in the ledger and in every record's `seed` |
| Audit-log schema and `record_errors` | every record | **2,496 of 2,496 records valid** (`python -m adm.eval.validate`, exit 0) |
| Same stimuli in every condition (invariant 7) | every input | every `player_input` is its scripted text, every input index present once per run |
| State hashes replay | every record | D replays from its diffs, A–C equal `replay_script`'s ground truth |
| Turn index preserved for RQ2 | every record | `input_index` is 0..51 once each, in order, in all 48 runs; D's `turn_number` rises by one after every narrated turn and repeats only after a failed one; A–C's never falls (§3) |
| Summary regenerations (CLAUDE.md §12) | ≥ 5 per run | 6 in 47 runs, 5 in `D long04 2001` (§4.1) |
| p95 turn latency, condition D (§10.5) | under 10 s | **8.05 s** |
| Whole main grid | 192 of 192 | `python -m adm.eval.validate --manifest experiments/main_grid.json`: none missing, 6,420 records, exit 0 |

## 2. Set-up

| Item | Value |
|---|---|
| Machine | docs/hardware.md §1 (RTX 5060 Laptop, 8 GiB), nothing else on the GPU during the batch |
| Model | `llama3.1:8b`, `sha256:46e0c10c…ca666e`, as pinned in `config/model.json`; the digest is in every ledger line |
| Ollama | 0.35.1, the standalone server of docs/hardware.md §7. Version and digest checked by the batch runner before the first run |
| Code | commit `94dda7d` on `feat/wbs-9.2-long-sessions` |
| Batch | `experiments/main_long.json`: `long01` to `long04`, 48 runs. 10:39:53 to 12:54:48 UTC, 2 h 15 min |
| Commands | `python -m adm.cli batch --manifest experiments/main_long.json`, then `python -m adm.eval.validate --runs runs --manifest experiments/main_long.json --out results/batch/validation_main_long.json`, and the same with `experiments/main_grid.json` and `validation_main_grid.json` |
| Output | logs in `runs/{condition}/{scenario_id}/{seed}.jsonl`; ledger `results/batch/attempts.jsonl` (192 lines, all `complete`, attempt 1) and the validation reports in `results/batch/` (all gitignored) |
| Shared copy | not yet uploaded: `runs/{A,B,C,D}/long*/` seeds 2001 to 2003 and `results/batch/` go to the team Drive folder at the same paths (`README.md`, "Shared storage") |

As in 9.1, the validator lists the logs outside its manifest as "Not in the manifest": the 144 short runs and the ten G2 smoke logs (`runs/D/long01..04`, seeds 1001 to 1010) for `main_long.json`, and the smoke logs alone for `main_grid.json`. Both are expected.

## 3. Turn index for RQ2

RQ2 is the slope of divergences per turn against turn number, per condition (CLAUDE.md §10.5), and the long sessions carry it. Every record already holds the two indexes it needs, so nothing was added:

- `input_index`: the scripted input the record answers, 0 to 51. It is the same stimulus in every condition, so it lines up the four conditions even where D has a failed turn (decision 23). In all 48 runs it is 0..51, once each, in order.
- `turn_number`: the turn being played. In D it rises by one after each narrated turn and repeats after a failed turn (CLAUDE.md §7.1); this holds for every D record. In A–C it is the replayed ground truth's turn for that input (decision 49): it never falls, and it repeats where the replay's expected call was rejected. Final turn numbers are in §4.2.

10.2 can regress on either. `input_index` is the one that compares conditions on the same stimulus.

## 4. Results

Columns as in `docs/main_run.md` §4. "Final turn" for A–C comes from the replayed ground truth (decision 49). "Rejected" counts turns with at least one rejected or unparseable attempt, and "recovered" counts those that still executed a call or ended narration-only. "K reduced" counts turns whose verbatim window was cut to fit `context_tokens`. Latency is `turn_latency_ms`. Tokens per second is `completion_tokens / eval_ms`, averaged over model calls and then over runs.

### 4.1 Per condition

| Cond | Runs | Records | Failed | Narration-only | Recovered / rejected | Filtered | Summaries | K reduced | Max prompt | Mean s | p95 s | tok/s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | 12 | 624 | – | – | – | 0 | 72 | 0 | 1529 | 2.37 | 5.85 | 61.7 |
| B | 12 | 624 | – | – | – | 0 | 72 | 0 | 3304 | 2.85 | 6.28 | 59.1 |
| C | 12 | 624 | – | – | – | 0 | 72 | 0 | 3217 | 2.75 | 6.24 | 59.0 |
| D | 12 | 624 | 14 | 11 | 110 / 124 | 0 | 71 | 0 | 4677 | 4.54 | 8.05 | 58.1 |

No narration was changed by the safety filter and K was never reduced. The largest prompt, 4,677 tokens in D, is 57% of the 8,192-token context. Every run regenerated the summary six times except `D long04 2001`, which did five: its five failed turns are not narrated, and a regeneration comes every K narrated turns (decision 28). Five is the CLAUDE.md §12 minimum.

### 4.2 Per run

| Run | Records | Final turn | Failed turns | Narration-only | Schema-valid 1st | Recovered / rejected | Summaries | K reduced | Max prompt tokens | Mean s | p95 s | tok/s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A long01 2001 | 52/52 | 50 | – | – | – | – | 6 | 0 | 1324 | 2.38 | 5.79 | 61.2 |
| B long01 2001 | 52/52 | 50 | – | – | – | – | 6 | 0 | 3038 | 2.89 | 6.47 | 59.2 |
| C long01 2001 | 52/52 | 50 | – | – | – | – | 6 | 0 | 2895 | 2.87 | 6.17 | 58.9 |
| D long01 2001 | 52/52 | 51 | 1 | 0 | 51 | 6 / 7 | 6 | 0 | 4677 | 4.72 | 8.41 | 57.8 |
| A long02 2001 | 52/52 | 49 | – | – | – | – | 6 | 0 | 1343 | 2.43 | 5.87 | 61.4 |
| B long02 2001 | 52/52 | 49 | – | – | – | – | 6 | 0 | 2702 | 2.76 | 6.26 | 59.4 |
| C long02 2001 | 52/52 | 49 | – | – | – | – | 6 | 0 | 2520 | 2.37 | 6.12 | 59.6 |
| D long02 2001 | 52/52 | 52 | 0 | 0 | 50 | 8 / 8 | 6 | 0 | 4258 | 4.62 | 8.12 | 58.1 |
| A long03 2001 | 52/52 | 48 | – | – | – | – | 6 | 0 | 1379 | 2.40 | 5.91 | 61.8 |
| B long03 2001 | 52/52 | 48 | – | – | – | – | 6 | 0 | 2928 | 2.78 | 6.04 | 59.1 |
| C long03 2001 | 52/52 | 48 | – | – | – | – | 6 | 0 | 2774 | 2.43 | 5.94 | 59.4 |
| D long03 2001 | 52/52 | 51 | 1 | 1 | 52 | 9 / 10 | 6 | 0 | 4303 | 4.47 | 7.62 | 58.1 |
| A long04 2001 | 52/52 | 50 | – | – | – | – | 6 | 0 | 1390 | 2.32 | 5.93 | 61.9 |
| B long04 2001 | 52/52 | 50 | – | – | – | – | 6 | 0 | 3037 | 2.66 | 6.11 | 59.0 |
| C long04 2001 | 52/52 | 50 | – | – | – | – | 6 | 0 | 3217 | 2.87 | 6.35 | 58.6 |
| D long04 2001 | 52/52 | 47 | 5 | 1 | 51 | 14 / 19 | 5 | 0 | 4456 | 4.38 | 8.29 | 58.2 |
| A long01 2002 | 52/52 | 50 | – | – | – | – | 6 | 0 | 1124 | 2.02 | 4.85 | 62.7 |
| B long01 2002 | 52/52 | 50 | – | – | – | – | 6 | 0 | 2986 | 3.13 | 6.28 | 58.8 |
| C long01 2002 | 52/52 | 50 | – | – | – | – | 6 | 0 | 2999 | 2.74 | 5.87 | 59.0 |
| D long01 2002 | 52/52 | 50 | 2 | 0 | 52 | 7 / 9 | 6 | 0 | 4368 | 4.47 | 8.14 | 58.0 |
| A long02 2002 | 52/52 | 49 | – | – | – | – | 6 | 0 | 1340 | 2.37 | 5.66 | 61.6 |
| B long02 2002 | 52/52 | 49 | – | – | – | – | 6 | 0 | 2701 | 2.80 | 6.69 | 59.3 |
| C long02 2002 | 52/52 | 49 | – | – | – | – | 6 | 0 | 2659 | 2.53 | 6.16 | 59.4 |
| D long02 2002 | 52/52 | 52 | 0 | 0 | 51 | 5 / 5 | 6 | 0 | 4081 | 4.53 | 8.05 | 57.9 |
| A long03 2002 | 52/52 | 48 | – | – | – | – | 6 | 0 | 1370 | 2.33 | 5.75 | 61.8 |
| B long03 2002 | 52/52 | 48 | – | – | – | – | 6 | 0 | 2849 | 2.65 | 6.08 | 59.5 |
| C long03 2002 | 52/52 | 48 | – | – | – | – | 6 | 0 | 3109 | 2.70 | 6.37 | 59.2 |
| D long03 2002 | 52/52 | 52 | 0 | 2 | 52 | 14 / 14 | 6 | 0 | 4400 | 4.59 | 7.87 | 58.2 |
| A long04 2002 | 52/52 | 50 | – | – | – | – | 6 | 0 | 1410 | 2.38 | 6.08 | 61.8 |
| B long04 2002 | 52/52 | 50 | – | – | – | – | 6 | 0 | 3105 | 2.71 | 6.20 | 58.8 |
| C long04 2002 | 52/52 | 50 | – | – | – | – | 6 | 0 | 3140 | 2.83 | 6.33 | 58.6 |
| D long04 2002 | 52/52 | 51 | 1 | 2 | 52 | 14 / 15 | 6 | 0 | 4387 | 4.48 | 8.15 | 58.4 |
| A long01 2003 | 52/52 | 50 | – | – | – | – | 6 | 0 | 1311 | 2.40 | 5.80 | 61.6 |
| B long01 2003 | 52/52 | 50 | – | – | – | – | 6 | 0 | 2965 | 2.98 | 6.69 | 59.0 |
| C long01 2003 | 52/52 | 50 | – | – | – | – | 6 | 0 | 3023 | 2.99 | 6.72 | 58.7 |
| D long01 2003 | 52/52 | 52 | 0 | 2 | 52 | 6 / 6 | 6 | 0 | 4521 | 4.50 | 7.95 | 58.1 |
| A long02 2003 | 52/52 | 52 | – | – | – | – | 6 | 0 | 1365 | 2.45 | 5.97 | 61.4 |
| B long02 2003 | 52/52 | 52 | – | – | – | – | 6 | 0 | 2670 | 2.86 | 6.37 | 59.3 |
| C long02 2003 | 52/52 | 52 | – | – | – | – | 6 | 0 | 2710 | 2.83 | 6.40 | 59.0 |
| D long02 2003 | 52/52 | 51 | 1 | 0 | 50 | 5 / 6 | 6 | 0 | 4163 | 4.52 | 7.95 | 58.3 |
| A long03 2003 | 52/52 | 48 | – | – | – | – | 6 | 0 | 1529 | 2.54 | 6.05 | 61.6 |
| B long03 2003 | 52/52 | 48 | – | – | – | – | 6 | 0 | 2921 | 2.99 | 6.42 | 59.1 |
| C long03 2003 | 52/52 | 48 | – | – | – | – | 6 | 0 | 3067 | 2.93 | 6.62 | 58.9 |
| D long03 2003 | 52/52 | 52 | 0 | 2 | 52 | 11 / 11 | 6 | 0 | 4410 | 4.58 | 8.26 | 58.2 |
| A long04 2003 | 52/52 | 50 | – | – | – | – | 6 | 0 | 1326 | 2.38 | 5.85 | 61.9 |
| B long04 2003 | 52/52 | 50 | – | – | – | – | 6 | 0 | 3304 | 3.00 | 6.68 | 58.9 |
| C long04 2003 | 52/52 | 50 | – | – | – | – | 6 | 0 | 3039 | 2.89 | 6.31 | 58.7 |
| D long04 2003 | 52/52 | 49 | 3 | 1 | 51 | 11 / 14 | 6 | 0 | 4419 | 4.55 | 8.27 | 58.1 |

## 5. What it shows

**Turn failures: 14, all in D**, out of 624 D turns (2.2%), against 4.1% in the short scenarios and 1.0% in the G2 smoke runs. All 14 follow patterns already seen:

- **The script outruns the fight (6).** `long04_mountain_monastery`'s harpy fight ends before its scripted Fire Bolts do (inputs 42 to 44; "I burn the second harpy if it is still in the air" failed in all three seeds), and the retries go `ENCOUNTER_OVER`, `NO_SPELL_SLOT`, `ENCOUNTER_OVER`. Seed 2001 also failed the heal at input 45, with no slot left. The same input failed in the smoke runs (`docs/smoke_runs.md` §4); the script keeps going by design (decision 23).
- **Movement and rest inputs (6).** "I ride on the tailboard of the last wagon and rest my legs" (`long01` input 36, seeds 2001 and 2002), "I climb down the side of the ravine to look for the mule" (`long01` input 12, 2002), "I sit with the sick monk through the night" (`long04` input 17, 2001 and 2003) and "As night falls I go back inside and climb to the long gallery" (`long02` input 11, 2003). The model's first reply is `{"tool": null}` or an invented `move` tool, and its retries break the schema or reach for a combat action outside an encounter. This is the movement pattern of 9.1 (`docs/main_run.md` §5).
- **Quest out of order (1).** "I tell the abbot the high bell has rung" (`long04` input 48, 2003): three `update_quest` attempts, rejected `ILLEGAL_QUEST_TRANSITION`, `SCHEMA_VIOLATION`, `ILLEGAL_QUEST_TRANSITION`.
- **Item from an NPC (1).** "I haul the net off his rack while his men watch" (`long03` input 25, 2001), which also failed in smoke run 1007. There is no transfer between inventories (decision 22), and the model reached for an unknown id, a combat action and a spell.

**Rejections by code**, over all D attempts: `ENCOUNTER_OVER` 77, `SCHEMA_VIOLATION` 19, `RELATIONSHIP_STEP_TOO_LARGE` 14, `ILLEGAL_QUEST_TRANSITION` 12, `NO_SPELL_SLOT` 9, `NOT_A_CASTER` 7, `ITEM_NOT_DEFINED` 6, `NEGATIVE_QUANTITY` 5, `TARGET_UNCONSCIOUS` 5, `UNKNOWN_ENTITY` 5, `SKILL_NOT_SUPPORTED` 1, and no unparseable reply. 110 of the 124 turns with a rejection recovered within the budget (89%). 11 turns ended narration-only.

**Timings are M6 evidence.** Throughput was about 58 to 62 tokens per second in every condition, as in 9.1. Turns are a little slower than in the short scenarios (D mean 4.54 s against 4.30 s, p95 8.05 s against 7.68 s), in line with the longer prompts of a 52-turn session. D's p95 is under the 10 s target.

## 6. Follow-ups

- Upload `runs/{A,B,C,D}/long*/` (seeds 2001 to 2003) and `results/batch/` to the team Drive folder, then record it in §2.
- 9.3 (#96) onwards: the checker (9.4) and annotation run over these logs and those of 9.1, 192 runs in all. Nothing here has been scored.
- 10.2: RQ2 from `input_index` or `turn_number` (§3).
