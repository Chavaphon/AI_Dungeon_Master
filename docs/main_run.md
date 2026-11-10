# Main run: the 12 short scenarios under all four conditions

WBS 9.1 · Owner: CI · Run 2026-11-09 · CLAUDE.md wins on any conflict.

The short-scenario part of the main grid (CLAUDE.md §10.5): `s01` to `s12` × conditions A, B, C, D × seeds 2001, 2002, 2003, 144 runs, played through the batch runner in two batches. Done when: "All runs complete with seeds recorded" (TASK_CHECKLIST.md, 9.1). Why two batches and not one `main_grid.json` batch is in `docs/decisions.md` (2026-11-09, WBS 9.1). The long scenarios are 9.2 (#95).

## 1. Verdict

| Check | Threshold | Result |
|---|---|---|
| Runs complete (one record per scripted input) | 144 of 144 | **144 of 144**, each on its first attempt, no transport retry |
| Seeds recorded | every run | 2001, 2002, 2003 in every (scenario, condition) cell, in the ledger and in every record's `seed` (§3) |
| Audit-log schema and `record_errors` | every record | **3,924 of 3,924 records valid** (`python -m adm.eval.validate`, exit 0 for both manifests) |
| Same stimuli in every condition (invariant 7) | every input | every `player_input` is its scripted text, every input index present once per run |
| State hashes replay | every record | D replays from its diffs, A–C equal `replay_script`'s ground truth |
| p95 turn latency, condition D (§10.5) | under 10 s | **7.68 s** |

## 2. Set-up

| Item | Value |
|---|---|
| Machine | docs/hardware.md §1 (RTX 5060 Laptop, 8 GiB), nothing else on the GPU during either batch |
| Model | `llama3.1:8b`, `sha256:46e0c10c…ca666e`, as pinned in `config/model.json`; the digest is in every ledger line |
| Ollama | 0.35.1, the standalone server of docs/hardware.md §7. Version and digest checked before each batch. The tray app had updated itself to 0.40.15 and was quit first |
| Code | commit `e35b4d0` on `feat/wbs-9.1-main-run` for both batches |
| Batch 1 | `experiments/main_short_1.json`: `s01` to `s06`, 72 runs. 10:47:39 to 12:28:36 UTC, 1 h 41 min |
| Batch 2 | `experiments/main_short_2.json`: `s07` to `s12`, 72 runs. 12:30:04 to 14:10:32 UTC, 1 h 40 min |
| Commands | `python -m adm.cli batch --manifest experiments/main_short_N.json`, then `python -m adm.eval.validate --runs runs --manifest experiments/main_short_N.json --out results/batch/validation_main_short_N.json` |
| Output | logs in `runs/{condition}/{scenario_id}/{seed}.jsonl`; ledger `results/batch/attempts.jsonl` (144 lines, all `complete`, attempt 1) and the two validation reports in `results/batch/` (all gitignored) |
| Shared copy | `runs/{A,B,C,D}/s*/` and `results/batch/`, uploaded 2026-11-09 to the team Drive folder at the same paths (`README.md`, "Shared storage") |

The smoke logs of G2 (`runs/D/long01..04`, seeds 1001 to 1010) share the `runs/` folder and are listed by the validator as "Not in the manifest". So are batch 1's logs when batch 2 is validated. Both are expected.

## 3. Seeds recorded

Each of the 48 (scenario, condition) cells has exactly the three seeds 2001, 2002 and 2003, the same in every cell. Every ledger line carries its run's `seed`, `model` and `model_digest`, and every record's `seed` equals its file name. The 144 run ids in the ledger are exactly the short-scenario runs of `experiments/main_grid.json` (`test_main_short_batches_are_the_short_part_of_the_main_grid`), so a later `main_grid.json` batch skips them as complete.

## 4. Results

Columns as in `docs/dry_run.md` §3. "Final turn" for A–C comes from the replayed ground truth (decision 49). "Rejected" counts turns with at least one rejected or unparseable attempt, and "recovered" counts those that still executed a call or ended narration-only. "K reduced" counts turns whose verbatim window was cut to fit `context_tokens`. Latency is `turn_latency_ms`. Tokens per second is `completion_tokens / eval_ms`, averaged over model calls and then over runs.

### 4.1 Per condition

| Cond | Runs | Records | Failed | Narration-only | Recovered / rejected | Filtered | Summaries | K reduced | Max prompt | Mean s | p95 s | tok/s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | 36 | 981 | – | – | – | 0 | 108 | 0 | 1373 | 2.15 | 5.51 | 62.6 |
| B | 36 | 981 | – | – | – | 0 | 108 | 0 | 2856 | 2.60 | 6.16 | 60.0 |
| C | 36 | 981 | – | – | – | 0 | 108 | 0 | 2971 | 2.46 | 5.85 | 60.1 |
| D | 36 | 981 | 40 | 39 | 238 / 278 | 0 | 104 | 0 | 4178 | 4.30 | 7.68 | 59.1 |

No narration was changed by the safety filter, no prompt came near the 8,192-token context, and K was never reduced. Every run regenerated the summary two or three times.

### 4.2 Per run

| Run | Records | Final turn | Failed turns | Narration-only | Schema-valid 1st | Recovered / rejected | Summaries | K reduced | Max prompt tokens | Mean s | p95 s | tok/s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A s01 2001 | 26/26 | 22 | – | – | – | – | 3 | 0 | 1125 | 1.98 | 4.50 | 61.8 |
| B s01 2001 | 26/26 | 22 | – | – | – | – | 3 | 0 | 2487 | 2.66 | 5.22 | 60.0 |
| C s01 2001 | 26/26 | 22 | – | – | – | – | 3 | 0 | 2293 | 2.23 | 4.41 | 60.6 |
| D s01 2001 | 26/26 | 24 | 2 | 1 | 26 | 7 / 9 | 3 | 0 | 3932 | 4.26 | 6.85 | 59.4 |
| A s02 2001 | 27/27 | 23 | – | – | – | – | 3 | 0 | 1356 | 2.59 | 4.12 | 62.8 |
| B s02 2001 | 27/27 | 23 | – | – | – | – | 3 | 0 | 2552 | 2.69 | 5.11 | 60.1 |
| C s02 2001 | 27/27 | 23 | – | – | – | – | 3 | 0 | 2474 | 2.50 | 5.11 | 60.1 |
| D s02 2001 | 27/27 | 27 | 0 | 1 | 27 | 5 / 5 | 3 | 0 | 3975 | 4.53 | 6.97 | 58.7 |
| A s03 2001 | 27/27 | 20 | – | – | – | – | 3 | 0 | 1373 | 2.34 | 5.46 | 61.9 |
| B s03 2001 | 27/27 | 20 | – | – | – | – | 3 | 0 | 2473 | 2.59 | 5.99 | 60.2 |
| C s03 2001 | 27/27 | 20 | – | – | – | – | 3 | 0 | 2420 | 2.34 | 5.03 | 60.4 |
| D s03 2001 | 27/27 | 25 | 2 | 0 | 27 | 5 / 7 | 3 | 0 | 3894 | 4.25 | 7.17 | 59.3 |
| A s04 2001 | 28/28 | 24 | – | – | – | – | 3 | 0 | 1166 | 1.98 | 4.12 | 63.1 |
| B s04 2001 | 28/28 | 24 | – | – | – | – | 3 | 0 | 2519 | 2.50 | 5.77 | 59.8 |
| C s04 2001 | 28/28 | 24 | – | – | – | – | 3 | 0 | 2575 | 2.34 | 4.86 | 59.9 |
| D s04 2001 | 28/28 | 28 | 0 | 4 | 27 | 7 / 7 | 3 | 0 | 3965 | 4.44 | 7.30 | 58.8 |
| A s05 2001 | 27/27 | 25 | – | – | – | – | 3 | 0 | 1349 | 2.38 | 5.03 | 62.2 |
| B s05 2001 | 27/27 | 25 | – | – | – | – | 3 | 0 | 2822 | 2.70 | 5.25 | 59.8 |
| C s05 2001 | 27/27 | 25 | – | – | – | – | 3 | 0 | 2801 | 2.69 | 5.34 | 59.1 |
| D s05 2001 | 27/27 | 27 | 0 | 0 | 27 | 4 / 4 | 3 | 0 | 4147 | 4.56 | 7.87 | 58.8 |
| A s06 2001 | 28/28 | 28 | – | – | – | – | 3 | 0 | 1250 | 2.10 | 4.41 | 62.8 |
| B s06 2001 | 28/28 | 28 | – | – | – | – | 3 | 0 | 2299 | 2.51 | 5.16 | 60.1 |
| C s06 2001 | 28/28 | 28 | – | – | – | – | 3 | 0 | 2301 | 2.41 | 5.02 | 60.0 |
| D s06 2001 | 28/28 | 28 | 0 | 1 | 25 | 7 / 7 | 3 | 0 | 3555 | 4.18 | 5.78 | 59.4 |
| A s01 2002 | 26/26 | 24 | – | – | – | – | 3 | 0 | 1190 | 1.98 | 3.81 | 63.0 |
| B s01 2002 | 26/26 | 24 | – | – | – | – | 3 | 0 | 2312 | 2.40 | 4.87 | 60.2 |
| C s01 2002 | 26/26 | 24 | – | – | – | – | 3 | 0 | 2232 | 2.22 | 5.47 | 60.2 |
| D s01 2002 | 26/26 | 26 | 0 | 0 | 26 | 6 / 6 | 3 | 0 | 3772 | 3.98 | 5.75 | 59.4 |
| A s02 2002 | 27/27 | 23 | – | – | – | – | 3 | 0 | 1305 | 2.17 | 4.50 | 62.6 |
| B s02 2002 | 27/27 | 23 | – | – | – | – | 3 | 0 | 2623 | 2.95 | 6.45 | 59.7 |
| C s02 2002 | 27/27 | 23 | – | – | – | – | 3 | 0 | 2515 | 2.68 | 5.85 | 59.8 |
| D s02 2002 | 27/27 | 27 | 0 | 2 | 27 | 9 / 9 | 3 | 0 | 3938 | 4.28 | 6.75 | 59.3 |
| A s03 2002 | 27/27 | 24 | – | – | – | – | 3 | 0 | 1259 | 2.13 | 5.42 | 62.9 |
| B s03 2002 | 27/27 | 24 | – | – | – | – | 3 | 0 | 2490 | 2.47 | 5.25 | 60.2 |
| C s03 2002 | 27/27 | 24 | – | – | – | – | 3 | 0 | 2380 | 2.40 | 5.58 | 60.0 |
| D s03 2002 | 27/27 | 27 | 0 | 0 | 25 | 9 / 9 | 3 | 0 | 3898 | 4.79 | 8.18 | 58.7 |
| A s04 2002 | 28/28 | 25 | – | – | – | – | 3 | 0 | 1159 | 2.01 | 4.52 | 62.9 |
| B s04 2002 | 28/28 | 25 | – | – | – | – | 3 | 0 | 2491 | 2.42 | 5.50 | 60.3 |
| C s04 2002 | 28/28 | 25 | – | – | – | – | 3 | 0 | 2631 | 2.31 | 4.90 | 60.2 |
| D s04 2002 | 28/28 | 28 | 0 | 4 | 28 | 12 / 12 | 3 | 0 | 3893 | 4.42 | 6.94 | 59.4 |
| A s05 2002 | 27/27 | 23 | – | – | – | – | 3 | 0 | 1240 | 2.12 | 5.05 | 63.0 |
| B s05 2002 | 27/27 | 23 | – | – | – | – | 3 | 0 | 2842 | 2.82 | 5.22 | 59.7 |
| C s05 2002 | 27/27 | 23 | – | – | – | – | 3 | 0 | 2867 | 2.88 | 5.72 | 59.5 |
| D s05 2002 | 27/27 | 27 | 0 | 0 | 27 | 7 / 7 | 3 | 0 | 4047 | 4.66 | 6.92 | 58.5 |
| A s06 2002 | 28/28 | 28 | – | – | – | – | 3 | 0 | 1268 | 2.12 | 4.24 | 63.0 |
| B s06 2002 | 28/28 | 28 | – | – | – | – | 3 | 0 | 2223 | 2.27 | 4.40 | 60.6 |
| C s06 2002 | 28/28 | 28 | – | – | – | – | 3 | 0 | 2216 | 2.19 | 4.08 | 60.0 |
| D s06 2002 | 28/28 | 26 | 2 | 1 | 26 | 5 / 7 | 3 | 0 | 3573 | 3.91 | 6.25 | 59.6 |
| A s01 2003 | 26/26 | 22 | – | – | – | – | 3 | 0 | 1259 | 2.17 | 4.43 | 62.3 |
| B s01 2003 | 26/26 | 22 | – | – | – | – | 3 | 0 | 2423 | 2.64 | 5.52 | 60.2 |
| C s01 2003 | 26/26 | 22 | – | – | – | – | 3 | 0 | 2437 | 2.44 | 5.27 | 60.4 |
| D s01 2003 | 26/26 | 25 | 1 | 0 | 26 | 6 / 7 | 3 | 0 | 3825 | 4.33 | 5.94 | 58.8 |
| A s02 2003 | 27/27 | 22 | – | – | – | – | 3 | 0 | 1292 | 2.27 | 4.69 | 62.3 |
| B s02 2003 | 27/27 | 22 | – | – | – | – | 3 | 0 | 2582 | 2.72 | 4.45 | 60.1 |
| C s02 2003 | 27/27 | 22 | – | – | – | – | 3 | 0 | 2546 | 2.32 | 4.40 | 60.4 |
| D s02 2003 | 27/27 | 27 | 0 | 1 | 27 | 7 / 7 | 3 | 0 | 3805 | 3.94 | 6.64 | 59.3 |
| A s03 2003 | 27/27 | 25 | – | – | – | – | 3 | 0 | 1165 | 1.98 | 4.30 | 62.9 |
| B s03 2003 | 27/27 | 25 | – | – | – | – | 3 | 0 | 2671 | 2.83 | 5.50 | 60.1 |
| C s03 2003 | 27/27 | 25 | – | – | – | – | 3 | 0 | 2537 | 2.68 | 5.79 | 59.4 |
| D s03 2003 | 27/27 | 27 | 0 | 0 | 26 | 8 / 8 | 3 | 0 | 3912 | 4.75 | 7.33 | 58.7 |
| A s04 2003 | 28/28 | 24 | – | – | – | – | 3 | 0 | 1296 | 2.13 | 4.24 | 62.6 |
| B s04 2003 | 28/28 | 24 | – | – | – | – | 3 | 0 | 2487 | 2.42 | 5.28 | 60.1 |
| C s04 2003 | 28/28 | 24 | – | – | – | – | 3 | 0 | 2507 | 2.29 | 5.58 | 60.5 |
| D s04 2003 | 28/28 | 28 | 0 | 2 | 27 | 6 / 6 | 3 | 0 | 3988 | 4.31 | 6.74 | 59.0 |
| A s05 2003 | 27/27 | 23 | – | – | – | – | 3 | 0 | 1338 | 2.36 | 5.04 | 62.4 |
| B s05 2003 | 27/27 | 23 | – | – | – | – | 3 | 0 | 2856 | 2.83 | 5.27 | 59.6 |
| C s05 2003 | 27/27 | 23 | – | – | – | – | 3 | 0 | 2971 | 2.86 | 5.58 | 59.3 |
| D s05 2003 | 27/27 | 27 | 0 | 0 | 27 | 0 / 0 | 3 | 0 | 3962 | 4.27 | 6.67 | 58.5 |
| A s06 2003 | 28/28 | 26 | – | – | – | – | 3 | 0 | 1246 | 2.18 | 4.75 | 62.4 |
| B s06 2003 | 28/28 | 26 | – | – | – | – | 3 | 0 | 2411 | 2.65 | 5.58 | 60.1 |
| C s06 2003 | 28/28 | 26 | – | – | – | – | 3 | 0 | 2299 | 2.32 | 4.67 | 60.5 |
| D s06 2003 | 28/28 | 28 | 0 | 2 | 27 | 6 / 6 | 3 | 0 | 3781 | 4.39 | 6.71 | 59.0 |
| A s07 2001 | 27/27 | 24 | – | – | – | – | 3 | 0 | 1255 | 2.21 | 4.69 | 61.7 |
| B s07 2001 | 27/27 | 24 | – | – | – | – | 3 | 0 | 2409 | 2.54 | 5.46 | 60.0 |
| C s07 2001 | 27/27 | 24 | – | – | – | – | 3 | 0 | 2385 | 2.31 | 4.77 | 60.1 |
| D s07 2001 | 27/27 | 27 | 0 | 2 | 27 | 7 / 7 | 3 | 0 | 3953 | 4.63 | 7.78 | 59.1 |
| A s08 2001 | 30/30 | 23 | – | – | – | – | 3 | 0 | 1338 | 2.15 | 3.74 | 62.4 |
| B s08 2001 | 30/30 | 23 | – | – | – | – | 3 | 0 | 2712 | 2.55 | 4.72 | 59.8 |
| C s08 2001 | 30/30 | 23 | – | – | – | – | 3 | 0 | 2717 | 2.47 | 5.28 | 59.9 |
| D s08 2001 | 30/30 | 27 | 3 | 0 | 28 | 9 / 12 | 3 | 0 | 4056 | 4.23 | 6.68 | 59.1 |
| A s09 2001 | 26/26 | 24 | – | – | – | – | 3 | 0 | 1229 | 2.22 | 4.42 | 62.5 |
| B s09 2001 | 26/26 | 24 | – | – | – | – | 3 | 0 | 2354 | 2.62 | 5.10 | 60.3 |
| C s09 2001 | 26/26 | 24 | – | – | – | – | 3 | 0 | 2227 | 2.34 | 5.07 | 60.5 |
| D s09 2001 | 26/26 | 26 | 0 | 1 | 26 | 4 / 4 | 3 | 0 | 3673 | 4.20 | 6.64 | 59.2 |
| A s10 2001 | 27/27 | 22 | – | – | – | – | 3 | 0 | 1130 | 2.02 | 4.23 | 63.0 |
| B s10 2001 | 27/27 | 22 | – | – | – | – | 3 | 0 | 2652 | 2.51 | 5.32 | 59.8 |
| C s10 2001 | 27/27 | 22 | – | – | – | – | 3 | 0 | 2602 | 2.32 | 5.27 | 60.1 |
| D s10 2001 | 27/27 | 27 | 0 | 2 | 26 | 8 / 8 | 3 | 0 | 4052 | 4.40 | 6.87 | 59.0 |
| A s11 2001 | 27/27 | 22 | – | – | – | – | 3 | 0 | 1273 | 2.21 | 4.21 | 62.4 |
| B s11 2001 | 27/27 | 22 | – | – | – | – | 3 | 0 | 2325 | 2.37 | 5.41 | 60.4 |
| C s11 2001 | 27/27 | 22 | – | – | – | – | 3 | 0 | 2534 | 2.78 | 6.33 | 59.9 |
| D s11 2001 | 27/27 | 23 | 4 | 0 | 27 | 5 / 9 | 2 | 0 | 3945 | 4.12 | 5.65 | 59.4 |
| A s12 2001 | 27/27 | 24 | – | – | – | – | 3 | 0 | 1231 | 2.14 | 4.15 | 62.7 |
| B s12 2001 | 27/27 | 24 | – | – | – | – | 3 | 0 | 2442 | 2.51 | 6.05 | 59.9 |
| C s12 2001 | 27/27 | 24 | – | – | – | – | 3 | 0 | 2613 | 2.73 | 5.30 | 60.0 |
| D s12 2001 | 27/27 | 25 | 2 | 0 | 26 | 8 / 10 | 3 | 0 | 4025 | 4.39 | 7.18 | 59.1 |
| A s07 2002 | 27/27 | 25 | – | – | – | – | 3 | 0 | 1155 | 1.99 | 4.69 | 62.9 |
| B s07 2002 | 27/27 | 25 | – | – | – | – | 3 | 0 | 2431 | 2.35 | 4.22 | 60.3 |
| C s07 2002 | 27/27 | 25 | – | – | – | – | 3 | 0 | 2549 | 2.49 | 5.56 | 60.2 |
| D s07 2002 | 27/27 | 27 | 0 | 0 | 27 | 9 / 9 | 3 | 0 | 3821 | 4.20 | 6.72 | 59.2 |
| A s08 2002 | 30/30 | 23 | – | – | – | – | 3 | 0 | 1265 | 2.20 | 4.49 | 62.1 |
| B s08 2002 | 30/30 | 23 | – | – | – | – | 3 | 0 | 2771 | 2.73 | 5.71 | 59.6 |
| C s08 2002 | 30/30 | 23 | – | – | – | – | 3 | 0 | 2744 | 2.44 | 5.30 | 60.1 |
| D s08 2002 | 30/30 | 21 | 9 | 0 | 28 | 7 / 16 | 2 | 0 | 4000 | 3.61 | 4.72 | 59.2 |
| A s09 2002 | 26/26 | 24 | – | – | – | – | 3 | 0 | 1098 | 1.98 | 4.37 | 63.0 |
| B s09 2002 | 26/26 | 24 | – | – | – | – | 3 | 0 | 2238 | 2.44 | 5.28 | 60.1 |
| C s09 2002 | 26/26 | 24 | – | – | – | – | 3 | 0 | 2380 | 2.40 | 4.99 | 60.5 |
| D s09 2002 | 26/26 | 26 | 0 | 2 | 26 | 3 / 3 | 3 | 0 | 3566 | 3.85 | 6.09 | 59.6 |
| A s10 2002 | 27/27 | 23 | – | – | – | – | 3 | 0 | 1125 | 1.96 | 4.01 | 63.2 |
| B s10 2002 | 27/27 | 23 | – | – | – | – | 3 | 0 | 2639 | 2.44 | 5.59 | 60.1 |
| C s10 2002 | 27/27 | 23 | – | – | – | – | 3 | 0 | 2661 | 2.18 | 4.86 | 60.4 |
| D s10 2002 | 27/27 | 27 | 1 | 3 | 27 | 7 / 8 | 3 | 0 | 4102 | 4.44 | 6.86 | 59.0 |
| A s11 2002 | 27/27 | 22 | – | – | – | – | 3 | 0 | 1258 | 2.16 | 3.76 | 62.6 |
| B s11 2002 | 27/27 | 22 | – | – | – | – | 3 | 0 | 2369 | 2.41 | 5.17 | 60.4 |
| C s11 2002 | 27/27 | 22 | – | – | – | – | 3 | 0 | 2379 | 2.27 | 4.69 | 60.6 |
| D s11 2002 | 27/27 | 23 | 4 | 0 | 27 | 6 / 10 | 2 | 0 | 3973 | 4.09 | 6.01 | 59.3 |
| A s12 2002 | 27/27 | 21 | – | – | – | – | 3 | 0 | 1290 | 2.16 | 4.44 | 62.3 |
| B s12 2002 | 27/27 | 21 | – | – | – | – | 3 | 0 | 2649 | 2.64 | 5.98 | 59.6 |
| C s12 2002 | 27/27 | 21 | – | – | – | – | 3 | 0 | 2612 | 2.61 | 5.57 | 59.7 |
| D s12 2002 | 27/27 | 26 | 1 | 0 | 27 | 8 / 9 | 3 | 0 | 4001 | 4.50 | 6.64 | 59.1 |
| A s07 2003 | 27/27 | 25 | – | – | – | – | 3 | 0 | 1333 | 2.17 | 4.00 | 62.8 |
| B s07 2003 | 27/27 | 25 | – | – | – | – | 3 | 0 | 2408 | 2.32 | 4.97 | 60.7 |
| C s07 2003 | 27/27 | 25 | – | – | – | – | 3 | 0 | 2452 | 2.49 | 5.08 | 60.0 |
| D s07 2003 | 27/27 | 27 | 0 | 5 | 27 | 10 / 10 | 3 | 0 | 4011 | 4.75 | 7.75 | 59.2 |
| A s08 2003 | 30/30 | 24 | – | – | – | – | 3 | 0 | 1232 | 2.06 | 3.85 | 62.7 |
| B s08 2003 | 30/30 | 24 | – | – | – | – | 3 | 0 | 2723 | 2.81 | 5.54 | 59.6 |
| C s08 2003 | 30/30 | 24 | – | – | – | – | 3 | 0 | 2768 | 2.53 | 4.59 | 59.9 |
| D s08 2003 | 30/30 | 26 | 4 | 0 | 29 | 7 / 11 | 3 | 0 | 4178 | 4.38 | 6.23 | 58.7 |
| A s09 2003 | 26/26 | 25 | – | – | – | – | 3 | 0 | 1226 | 2.07 | 4.09 | 62.6 |
| B s09 2003 | 26/26 | 25 | – | – | – | – | 3 | 0 | 2445 | 2.76 | 5.27 | 60.2 |
| C s09 2003 | 26/26 | 25 | – | – | – | – | 3 | 0 | 2300 | 2.46 | 5.28 | 60.2 |
| D s09 2003 | 26/26 | 26 | 0 | 1 | 25 | 4 / 4 | 3 | 0 | 3666 | 4.14 | 6.97 | 59.1 |
| A s10 2003 | 27/27 | 23 | – | – | – | – | 3 | 0 | 1273 | 2.22 | 4.48 | 62.6 |
| B s10 2003 | 27/27 | 23 | – | – | – | – | 3 | 0 | 2748 | 2.63 | 5.97 | 59.6 |
| C s10 2003 | 27/27 | 23 | – | – | – | – | 3 | 0 | 2758 | 2.61 | 5.05 | 59.6 |
| D s10 2003 | 27/27 | 26 | 1 | 4 | 25 | 10 / 11 | 3 | 0 | 3987 | 4.08 | 6.80 | 59.6 |
| A s11 2003 | 27/27 | 23 | – | – | – | – | 3 | 0 | 1295 | 2.34 | 4.42 | 61.8 |
| B s11 2003 | 27/27 | 23 | – | – | – | – | 3 | 0 | 2544 | 3.01 | 6.53 | 59.9 |
| C s11 2003 | 27/27 | 23 | – | – | – | – | 3 | 0 | 2557 | 2.54 | 5.50 | 60.3 |
| D s11 2003 | 27/27 | 23 | 4 | 0 | 26 | 6 / 10 | 2 | 0 | 3873 | 3.94 | 6.04 | 59.5 |
| A s12 2003 | 27/27 | 23 | – | – | – | – | 3 | 0 | 1282 | 2.21 | 4.55 | 62.5 |
| B s12 2003 | 27/27 | 23 | – | – | – | – | 3 | 0 | 2682 | 2.95 | 6.28 | 59.7 |
| C s12 2003 | 27/27 | 23 | – | – | – | – | 3 | 0 | 2543 | 2.62 | 6.04 | 59.7 |
| D s12 2003 | 27/27 | 27 | 0 | 0 | 27 | 4 / 4 | 3 | 0 | 4015 | 4.61 | 7.12 | 58.5 |

## 5. What it shows

**Turn failures: 40, all in D**, 7 in batch 1 and 33 in batch 2, out of 981 D turns (4.1%). All 40 follow known patterns:

- **The script outruns the fight (24).** An attack or Fire Bolt comes after the encounter has ended, and the model's retries go `ENCOUNTER_OVER`, `NO_SPELL_SLOT`, `ENCOUNTER_OVER`, or the reverse for a heal with no slot left. This is the pattern of the G2 smoke runs and the dry run (`docs/dry_run.md` §4), and the script keeps going by design (decision 23). `s08_old_mine` seed 2002 has 7 of them: its fights ended early, and the scripted attacks and heals kept coming.
- **Movement inputs (8).** "I climb down the old ladder into the shaft" (`s08`, all three seeds), "I push through the waist-deep snowdrift" (`s11`, all three) and two inputs on the `s06` lighthouse stair. Each one's `expected_call` is a `strength` check. In all eight the model's first reply is not a parseable tool call, and its retries reach for a schema-breaking call or a combat action outside an encounter. There is no movement tool, and the model does not map climbing or wading to a strength check.
- **The PC is down (3).** In `s11_frozen_pass` seed 2003 the PC reached 0 HP at input 13, so the encounter ended in defeat. Its later fire and healing calls were `ACTOR_UNCONSCIOUS`, as there is no death and no revival without a healer (CLAUDE.md §4.8). Its input 19 executed a valid skill check *by the conscious wolf*. That is a misparsed intent for M3 (§7.2), not an engine error.
- **Other (5).** `SKILL_NOT_SUPPORTED` three times on "I check how badly I am hurt" (`s01` 2003), `ITEM_NOT_DEFINED` on asking the foreman for pay (`s08` 2002), and one mixed retry chain each in `s10` 2002, `s10` 2003 and `s12` 2001.

**Rejections by code**, over all D attempts: `ENCOUNTER_OVER` 191, `NO_SPELL_SLOT` 41, `SCHEMA_VIOLATION` 35, `NOT_A_CASTER` 35, `NEGATIVE_QUANTITY` 22, `RELATIONSHIP_STEP_TOO_LARGE` 20, `ACTOR_UNCONSCIOUS` 16, `TARGET_UNCONSCIOUS` 14, `ILLEGAL_QUEST_TRANSITION` 10, `WEAPON_NOT_IN_INVENTORY` 6, `UNKNOWN_ENTITY` 6, `SKILL_NOT_SUPPORTED` 4, `ITEM_NOT_DEFINED` 4, and 9 unparseable replies. 238 of the 278 turns with a rejection recovered within the budget (86%). 39 turns ended narration-only.

**Timings are M6 evidence.** The GPU was idle in both batches. Throughput was about 60 tokens per second in every condition, against 19.6 to 42.2 in the dry run, where a game was sharing the GPU. D is slower than A–C (mean 4.3 s against 2.2 to 2.6 s) because it makes two model calls per turn.

## 6. Follow-ups

- 9.2 (#95): the four long scenarios, `long01` to `long04` × A–D × the same seeds, played 2026-11-10: `docs/long_run.md`.
- 9.3 (#96) onwards: the checker (9.4) and annotation run over these logs. Nothing here has been scored.
- The logs are on the Drive (§2); 9.4 onwards reads them from there or from `runs/`.
