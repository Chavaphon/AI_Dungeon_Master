# M1 growth against turn index (RQ2)

WBS 10.2 · Owner: SD · Computed 2026-11-17 · CLAUDE.md wins on any conflict.

RQ2 of CLAUDE.md §10.5: the slope of divergences per turn against turn number, per condition, with a bootstrap interval; the long sessions carry it. Done when: "Answers RQ2" (TASK_CHECKLIST.md, 10.2).

## 1. Definitions

Fixed in `docs/decisions.md` (2026-11-17, "M1 growth definitions, fixed before the figures") and committed before the command was run on the labels.

| Term | Definition |
|---|---|
| Data | As in 10.1 (`docs/m1_rates.md` §1): the 9.5 M1 sample, 64 whole runs, SD's labels, the same checks. |
| Divergences of a turn | Confirmed checker candidates plus added labels in `PHANTOM`, `CONTRADICT`, `RESOURCE`, `RELATION` (rubric v1.0). `RULE` is M4. Failed D turns are not in the sample. |
| Turn index | The scripted position, `input_index + 1` (1 to 52 in a long session). It names the same input in every condition, so a failed D turn does not shift D's later turns. |
| **Slope** | Least-squares slope of the per-turn divergence count on the position, pooled over the turns of a condition's runs, reported as the change in divergences per 100 turns for every 10 turns played (1,000 × slope per turn). |
| **RQ2** | Carried by the 4 long sessions, 4 runs per condition. Divergences grow with the session when the slope's 95% interval lies above 0. The difference from A (B−A, C−A, D−A) is given with its interval. |
| Interval | 95% percentile bootstrap over whole runs, 10,000 resamples, stratified by condition, seed 20261101 (`bootstrap` in `adm/eval/metrics.py`). |
| Fixed beforehand | The long-session slopes without `PHANTOM`; the slopes of the 12 short scenarios as context, no interval; the long-session rate in bins of 10 positions, the last from 41 to the end, for the figure (10.6). |

## 2. Set-up

| Item | Value |
|---|---|
| Logs | SD's machine, `runs/`; every sampled log matches `experiments/main_grid.sha256`. |
| Labels | `results/m1_labels.jsonl`, sha256 `53d74b6bd68400064fa83d8da1f60cc90087ece80918aba13f453362bb11138e` (9.5) |
| Command | `python -m adm.eval.m1_growth --checksums experiments/main_grid.sha256 --doc docs/m1_growth.md` |
| Output | `results/m1_growth.json` (gitignored; for the team Drive under `results/`) and the block in §3, written by the command. |

## 3. Results

<!-- results:start -->
Turn index: scripted position (input_index + 1). Slope: change in divergences per 100 turns per 10 turns played, least squares pooled over a condition's runs. Intervals: 95% percentile bootstrap over whole runs, 10,000 resamples, stratified by condition, seed 20261101.

### Long sessions: slope per condition (RQ2)

| Condition | Runs | Turns | Slope | 95% interval | Grows | Without `PHANTOM` | 95% interval |
|---|---|---|---|---|---|---|---|
| A | 4 | 208 | **-3.3** | -15.4 to +8.2 | no | -1.3 | -10.3 to +4.8 |
| B | 4 | 208 | **+1.2** | -9.1 to +13.9 | no | +2.5 | -2.8 to +7.7 |
| C | 4 | 208 | **+1.5** | -5.8 to +7.4 | no | -0.3 | -8.3 to +6.5 |
| D | 4 | 205 | **+5.7** | -2.3 to +15.4 | no | +4.4 | -2.6 to +11.0 |

### Difference from condition A

| Difference | Slope | 95% interval | Excludes 0 | Without `PHANTOM` | 95% interval |
|---|---|---|---|---|---|
| B − A | **+4.5** | -11.3 to +21.4 | no | +3.7 | -4.9 to +13.8 |
| C − A | **+4.8** | -8.8 to +18.6 | no | +0.9 | -9.5 to +12.7 |
| D − A | **+9.0** | -5.7 to +24.4 | no | +5.7 | -4.7 to +17.0 |

### Long sessions: rate per 100 turns by position

Pooled over the condition's long-session runs; for the growth-curve figure (10.6).

| Condition | 1–10 | 11–20 | 21–30 | 31–40 | 41+ |
|---|---|---|---|---|---|
| A | 67.5 | 30.0 | 52.5 | 27.5 | 52.1 |
| B | 42.5 | 45.0 | 72.5 | 42.5 | 50.0 |
| C | 47.5 | 40.0 | 30.0 | 40.0 | 56.2 |
| D | 40.0 | 38.5 | 55.0 | 38.5 | 70.2 |

### Short scenarios, for context

Slope over the 12 short scenarios, no interval: their scripts differ by position.

| Condition | Runs | Slope |
|---|---|---|
| A | 12 | +0.1 |
| B | 12 | -2.8 |
| C | 12 | +6.8 |
| D | 12 | +10.2 |
<!-- results:end -->

The command gives byte-identical `results/m1_growth.json` on a second run: sha256 `ec9207b837f8da0af98f9f2273bcc0d3aa2c71ec5f63fa486bc637b23cef8652`.

## 4. Reading

- **RQ2: no condition's divergences grow measurably over a 52-turn session.** Every slope's 95% interval contains 0. D has the steepest point estimate, +5.7 per 100 turns for every 10 turns played (−2.3 to +15.4), and A the flattest, −3.3 (−15.4 to +8.2).
- **D does not drift more slowly than A.** The prediction behind grounding was that state in the prompt, and the engine in D, would hold the narration steady as the session grows. The difference D − A is +9.0 (−5.7 to +24.4): if anything D's point estimate rises faster, but the interval contains 0, so this is not a finding. B − A (+4.5) and C − A (+4.8) are the same: no difference from A.
- **Without `PHANTOM` the picture does not change.** D's slope is +4.4 (−2.6 to +11.0) and D − A +5.7 (−4.7 to +17.0).
- **The script, not the session length, moves the rate.** The per-bin rates go up and down together across conditions (A, for example, is 67.5 in turns 1–10 and 27.5 in turns 31–40), and per-run slopes follow the scenario more than the condition: all four `long03_river_market` runs fall (−20.8 to −4.5), and all four `long01_border_road` runs rise (+0.9 to +20.7). Busy stretches of a script (combat, many named characters) produce more divergences in every condition.
- **The last stretch is highest in C and D** (56.2 and 70.2 per 100 turns in positions 41 onwards, against A's 52.1), the pattern a growth effect would show, but one bin of four runs is not evidence. 10.6 plots the bins; 10.7 can look at those turns.
- **Short scenarios agree in direction only.** Their slopes (A +0.1, B −2.8, C +6.8, D +10.2) have no interval and differ in script by position, so they are context, not a test.

## 5. Limitations, for the report

- **Four runs per condition.** Each long session is played once per condition in the M1 sample (one seed), so the bootstrap draws from 4 runs per stratum and the intervals are wide and coarse. A moderate growth effect would not show.
- **Position is confounded with the script.** Every condition gets the same input at the same position, so the differences between conditions are fair, but each condition's own slope also reflects what the script asks for at each point, not only how long the session has run.
- **Labels as in 10.1.** The labels are an AI draft accepted unchanged by SD (`docs/m1_annotation.md` §3; `docs/m1_rates.md` §5).
- **D has 3 fewer long-session turns** (205 against 208): its failed turns are not narrated by the model and leave gaps at their positions.
- **A correction after the first run.** The bins were first written as 1–10 to 41–50, and the long sessions have 52 inputs, so positions 51 and 52 were dropped from the last bin. It now runs to the end (decision log, 2026-11-17). The slopes and differences were unchanged by the correction.
