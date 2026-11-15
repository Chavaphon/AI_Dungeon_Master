# M1: divergence rate per condition

WBS 10.1 · Owner: SD · Computed 2026-11-15 · CLAUDE.md wins on any conflict.

M1 of CLAUDE.md §10.4: confirmed divergences per 100 turns, overall and per category, per condition. It answers RQ1 and tests H1 (§10.5). Done when: "Answers RQ1" (TASK_CHECKLIST.md, 10.1).

## 1. Definitions

Fixed in `docs/decisions.md` (2026-11-15, "M1 rate definitions, fixed before the figures") and committed before the command was run on the labels.

| Term | Definition |
|---|---|
| Sample | The 9.5 M1 sample: per scenario one seed, all four conditions at it, 64 runs, 2,124 narrated turns (`adm/eval/m1.py`). |
| Labels | The first annotator's (SD, 9.5), one line for every sampled turn. The 9.6 overlap labels are for agreement (10.5) only. |
| Divergence | A confirmed checker candidate or an added label in `PHANTOM`, `CONTRADICT`, `RESOURCE` or `RELATION` (rubric v1.0). `RULE` is M4. |
| Turn | A narrated turn. A failed condition D turn shows the engine's request to rephrase and is not in the sample; M2 counts it. |
| **Rate** | 100 × divergences / narrated turns, pooled over a condition's 16 runs. |
| **H1** | D/A ratio of the rates at most 0.5, with its 95% interval excluding 1. |
| Interval | 95% percentile bootstrap over whole runs, 10,000 resamples, stratified by condition, seed 20261101 (`bootstrap` in `adm/eval/metrics.py`). |
| Sensitivity | Every ratio also without `PHANTOM`, fixed beforehand. |

## 2. Set-up

| Item | Value |
|---|---|
| Logs | SD's machine, `runs/`; every sampled log matches `experiments/main_grid.sha256`. |
| Labels | `results/m1_labels.jsonl`, sha256 `53d74b6bd68400064fa83d8da1f60cc90087ece80918aba13f453362bb11138e` (9.5) |
| Command | `python -m adm.eval.m1_rates --checksums experiments/main_grid.sha256 --doc docs/m1_rates.md` |
| Output | `results/m1.json` (gitignored; for the team Drive under `results/`) and the block in §3, written by the command. |

## 3. Results

<!-- results:start -->
64 runs, 2124 narrated turns, labels of the first annotator. Rates are divergences per 100 narrated turns, pooled over runs. Intervals: 95% percentile bootstrap over whole runs, 10,000 resamples, stratified by condition, seed 20261101.

### M1 per condition

| Condition | Runs | Turns | Divergences | Turns with any | Rate | 95% interval |
|---|---|---|---|---|---|---|
| A | 16 | 535 | 299 | 197 | **55.9** | 40.6 to 73.3 |
| B | 16 | 535 | 290 | 202 | **54.2** | 40.1 to 69.1 |
| C | 16 | 535 | 238 | 175 | **44.5** | 32.7 to 58.0 |
| D | 16 | 519 | 298 | 219 | **57.4** | 48.5 to 68.5 |

### Per category

Count, then rate per 100 turns with its 95% interval.

| Condition | `PHANTOM` | `CONTRADICT` | `RESOURCE` | `RELATION` |
|---|---|---|---|---|
| A | 177: 33.1 (23.3 to 43.8) | 112: 20.9 (13.8 to 30.1) | 5: 0.9 (0.4 to 1.5) | 5: 0.9 (0.2 to 2.0) |
| B | 151: 28.2 (19.9 to 36.6) | 127: 23.7 (15.8 to 34.0) | 11: 2.1 (0.2 to 4.3) | 1: 0.2 (0.0 to 0.6) |
| C | 127: 23.7 (14.5 to 35.3) | 99: 18.5 (12.3 to 26.5) | 10: 1.9 (0.7 to 3.1) | 2: 0.4 (0.0 to 0.8) |
| D | 156: 30.1 (21.3 to 39.3) | 118: 22.7 (15.1 to 33.5) | 13: 2.5 (1.3 to 3.7) | 11: 2.1 (0.2 to 4.2) |

### Ratio to condition A

| Ratio | All categories | 95% interval | Without `PHANTOM` | 95% interval |
|---|---|---|---|---|
| B/A | **0.97** | 0.64 to 1.45 | 1.14 | 0.69 to 1.87 |
| C/A | **0.80** | 0.53 to 1.21 | 0.91 | 0.58 to 1.46 |
| D/A | **1.03** | 0.74 to 1.48 | 1.20 | 0.74 to 1.97 |

**H1** (D/A at most 0.5, 95% interval excluding 1): **not supported**. D/A = 1.03, interval 0.74 to 1.48; at most 0.5: no; interval excludes 1: no.

### Short scenarios and long sessions

Rate per 100 turns, no interval; RQ2 (10.2) takes up the long sessions.

| Condition | 12 short scenarios | 4 long sessions |
|---|---|---|
| A | 62.1 | 46.2 |
| B | 56.6 | 50.5 |
| C | 45.3 | 43.3 |
| D | 62.7 | 49.3 |
<!-- results:end -->

The command gives byte-identical `results/m1.json` on a second run: sha256 `35944a49b04d511729d9c784f8b9aa900953e0c7ae17e1cb96e942729f479b04`.

## 4. Reading

- **RQ1: grounding did not lower the divergence rate.** D diverges at 57.4 per 100 narrated turns against A's 55.9: D/A is 1.03, 95% interval 0.74 to 1.48. **H1 is not supported**: the ratio is far above 0.5 and its interval contains 1. Every interval overlaps every other; no condition differs from A at this sample size.
- **Without `PHANTOM` the picture does not change.** The sensitivity ratio D/A is 1.20 (0.74 to 1.97), so the input-named-items inconsistency of 9.5 does not explain the result.
- **C is lowest** (44.5; C/A 0.80, 0.53 to 1.21), but its interval includes 1, so this is not a finding.
- **The rate is not carried by a few runs.** The five runs with most divergences hold 18% of them, and are from A, B and C as well as D. The median per-run rate tells the same story: A 49.0, B 58.1, C 41.5, D 56.2.
- **What D's divergences are.** D's `PHANTOM` (30.1) and `CONTRADICT` (22.7) are close to A's (33.1, 20.9). D has the most `RESOURCE` (2.5) and `RELATION` (2.1), though both are small counts. The narration in D is written after the engine has resolved the turn, and the narrator still invents entities and misstates hit points at about the same rate as with no state at all. 10.7 and 10.8 look at examples.
- **Intervals are wide.** Each condition has 16 runs, one seed per scenario; the run-level bootstrap is honest about that. A 50% reduction would have shown; a small one would not.

## 5. Limitations, for the report

- **The labels are an AI draft accepted unchanged.** SD accepted all 2,124 draft turns (`docs/m1_annotation.md` §3), so these rates are the AI drafter's reading of rubric v1.0, confirmed by one person. The drafter saw no condition, so this is not expected to favour one condition, but the rate is not an independent human count. The 9.6 alpha (0.894) is agreement between two reviewed drafts by the same model (`docs/m1_overlap.md` §5).
- **Condition D has 16 fewer turns** (519 against 535): its failed turns are not narrated by the model and are left out, as fixed in 9.4. M2 reports them.
- **One seed per scenario.** M1 uses a quarter of the main grid's runs (64 of 192) because annotation is by hand; the other seeds are not labelled.
