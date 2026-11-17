# M1 growth against turn index (RQ2)

WBS 10.2 · Owner: SD · CLAUDE.md wins on any conflict.

RQ2 of CLAUDE.md §10.5: the slope of divergences per turn against turn number, per condition, with a bootstrap interval; the long sessions carry it. Done when: "Answers RQ2" (TASK_CHECKLIST.md, 10.2).

## 1. Definitions

Fixed in `docs/decisions.md` (2026-11-17, "M1 growth definitions, fixed before the figures") and committed before the command was run on the labels.

| Term | Definition |
|---|---|
| Data | As in 10.1 (`docs/m1_rates.md` §1): the 9.5 M1 sample, 64 whole runs, SD's labels, the same checks. |
| Divergences of a turn | Confirmed checker candidates plus added labels in `PHANTOM`, `CONTRADICT`, `RESOURCE`, `RELATION` (rubric v1.0). `RULE` is M4. Failed D turns are not in the sample. |
| Turn index | The scripted position, `input_index + 1` (1 to 50 in a long session). It names the same input in every condition, so a failed D turn does not shift D's later turns. |
| **Slope** | Least-squares slope of the per-turn divergence count on the position, pooled over the turns of a condition's runs, reported as the change in divergences per 100 turns for every 10 turns played (1,000 × slope per turn). |
| **RQ2** | Carried by the 4 long sessions, 4 runs per condition. Divergences grow with the session when the slope's 95% interval lies above 0. The difference from A (B−A, C−A, D−A) is given with its interval. |
| Interval | 95% percentile bootstrap over whole runs, 10,000 resamples, stratified by condition, seed 20261101 (`bootstrap` in `adm/eval/metrics.py`). |
| Fixed beforehand | The long-session slopes without `PHANTOM`; the slopes of the 12 short scenarios as context, no interval; the long-session rate in five bins of 10 positions, for the figure (10.6). |

## 2. Set-up

| Item | Value |
|---|---|
| Logs | SD's machine, `runs/`; every sampled log matches `experiments/main_grid.sha256`. |
| Labels | `results/m1_labels.jsonl`, sha256 `53d74b6bd68400064fa83d8da1f60cc90087ece80918aba13f453362bb11138e` (9.5) |
| Command | `python -m adm.eval.m1_growth --checksums experiments/main_grid.sha256 --doc docs/m1_growth.md` |
| Output | `results/m1_growth.json` (gitignored; for the team Drive under `results/`) and the block in §3, written by the command. |

## 3. Results

<!-- results:start -->
Not yet computed.
<!-- results:end -->
