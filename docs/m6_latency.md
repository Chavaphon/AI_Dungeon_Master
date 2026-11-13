# M6: latency and throughput

WBS 10.4 · Owner: CI · Computed 2026-11-13 · CLAUDE.md wins on any conflict.

M6 of CLAUDE.md §10.4: "Mean and p95 seconds per turn (`turn_latency_ms`), tokens per second (`completion_tokens / eval_ms` per model call)." The target fixed before scoring is a p95 under 10 s per turn in condition D (§10.5). Done when: "Reported for all conditions" (TASK_CHECKLIST.md, 10.4). Its companion, M4, is `docs/m4_rule_violations.md`.

## 1. Definitions

Fixed in `docs/decisions.md` (2026-11-13, "M4 and M6 summaries") before the figures below were read. The fields are those of WBS 6.8 (decision 31).

| Term | Definition |
|---|---|
| Seconds per turn | `turn_latency_ms / 1000`: wall time from the player's input to the record being written, every model call (retries and summary regenerations included) and the engine. |
| Turns counted | Every audit record, failed condition D turns included: the player waited for them too. |
| Mean, p50, p95, max | Over the pooled turns of a condition. Percentiles interpolate linearly between order statistics (numpy's default; `percentile` in `adm/eval/metrics.py`). |
| Tokens per second | `completion_tokens / eval_ms` × 1000 per model call, then the mean over calls, as in the smoke runs (`docs/smoke_runs.md` §3); per condition and per phase (`toolcall`, `narration`, `summary`). `eval_ms` is Ollama's generation time alone, so prompt evaluation does not dilute it. A call with no `eval_ms` is left out and counted. |
| **Target** | p95 seconds per turn in D under 10 s. Met only when the p95 and the upper bound of its 95% interval are both under 10 s. |

Every 95% interval is a percentile bootstrap that resamples whole runs within a condition, 10,000 resamples, with a fixed seed (CLAUDE.md §10.5; `bootstrap` in `adm/eval/metrics.py`). For the p95, each resample's turns are pooled and their p95 taken.

## 2. Set-up

| Item | Value |
|---|---|
| Dataset | The 192 runs of `experiments/main_grid.json`, the logs pinned by `experiments/main_grid.sha256` (decision 60), as for M4. |
| Machine | All 192 runs were played on one machine, `docs/hardware.md` §1 (RTX 5060 Laptop, 8 GiB), `llama3.1:8b` Q4_K_M on Ollama 0.35.1, with nothing else on the GPU (`docs/main_run.md` §2, `docs/long_run.md` §2). The figures hold for that machine only (`docs/hardware.md` §6). |
| Command | `python -m adm.eval.metrics m6 --checksums experiments/main_grid.sha256 --doc docs/m6_latency.md` |
| Output | `results/m6.json` (gitignored; for the team Drive under `results/`), and the block in §3, written by the command. Two runs give byte-identical output: sha256 `1ee13e3e7916e9472702cbb221b0fdebad50b7d3085f4624426a8585d6d9f138`. |

## 3. Results

<!-- results:start -->
Conditions A, B, C, D, 192 runs, 6420 turns (failed turns included). Intervals: 95% percentile bootstrap over whole runs, 10,000 resamples, seed 20261101.

**Target: p95 under 10 s per turn in condition D. p95 = 7.89 s, upper 95% bound 7.98 s: met.**

### Seconds per turn

| Condition | Runs | Turns | Mean | 95% interval | p50 | **p95** | 95% interval | Max |
|---|---|---|---|---|---|---|---|---|
| A | 48 | 1605 | 2.24 | 2.18 to 2.28 | 1.92 | **5.67** | 5.53 to 5.76 | 16.34 |
| B | 48 | 1605 | 2.70 | 2.63 to 2.76 | 2.35 | **6.19** | 6.13 to 6.28 | 8.39 |
| C | 48 | 1605 | 2.57 | 2.50 to 2.64 | 2.23 | **6.05** | 5.90 to 6.17 | 7.96 |
| D | 48 | 1605 | 4.39 | 4.32 to 4.45 | 4.17 | **7.89** | 7.74 to 7.98 | 9.67 |

### Tokens per second

Mean over model calls of `completion_tokens / eval_ms`; calls per cell in brackets.

| Condition | Calls | Mean | Toolcall | Narration | Summary |
|---|---|---|---|---|---|
| A | 1,785 | **62.2** | – | 62.3 (1,605) | 61.8 (180) |
| B | 1,785 | **59.7** | – | 59.5 (1,605) | 61.4 (180) |
| C | 1,785 | **59.6** | – | 59.4 (1,605) | 61.6 (180) |
| D | 4,320 | **58.7** | 57.1 (2,594) | 61.2 (1,551) | 61.9 (175) |

Calls with no `eval_ms` logged, left out: 0.
<!-- results:end -->

## 4. Reading

**The target is met with room to spare.** D's p95 is 7.89 s per turn (7.74 to 7.98 s); even the slowest of its 1,605 turns, 9.67 s, is under 10 s. The long sessions are slightly slower than the short ones, as their prompts are longer (`docs/long_run.md` §5: p95 8.05 s against 7.68 s), and both are under the target.

**D costs about 2 s a turn more than A–C, and that is the second model call.** D's mean is 4.39 s against 2.24 to 2.70 s. A–C make one narration call per turn; D makes a tool call (at least one, up to three) and then the narration. B and C are a little slower than A because their narration prompts carry the state: a mean of about 2,330 prompt tokens against 1,010 for A, for replies of much the same length (93 to 100 completion tokens against 91). D's tool-call prompt, with the state and the tool definitions, averages 3,600 tokens for a reply of 31.

**Throughput is the same in every condition.** About 60 tokens per second for every phase and condition, as in the main batches (`docs/main_run.md` §5). D's tool calls are a little lower, 57.1, probably because their replies are short (31 tokens on average), so the fixed start of generation weighs more. Since generation speed does not differ, latency differences between conditions come from the number of calls and prompt length, not from the model running slower.

**The slow tail is summary regenerations and retries.** A turn that regenerates the rolling summary (every K = 8 narrated turns) adds a call of up to 200 tokens: the 715 such turns average 6.3 s against 2.6 s for the rest. D's slowest turns combine a summary with a retried tool call. A's maximum, 16.3 s (`s02_toll_bridge` 2001, input 23), is one summary call that took 14.0 s of wall time for 200 tokens, a one-off: B's and C's maxima are 8.4 s and 8.0 s.

**The figures belong to one laptop.** They are comparable across conditions because all 192 runs were played on the same machine with an idle GPU. They say nothing about other hardware (`docs/hardware.md` §6), and the dry run's timings, slowed by a game sharing the GPU, are not M6 (`docs/dry_run.md`).
