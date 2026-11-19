# M5: narrative quality per condition, and H2

WBS 11.3 · Owner: SD · Computed 2026-11-19 · CLAUDE.md wins on any conflict.

M5 of CLAUDE.md §10.4 per condition, and H2 of §10.5: "the 95% interval of the D minus A difference in mean M5 score, reported per item". RQ3 is read from the same differences. Computed for the report's Results (`docs/report_outline.md` §5.7, WBS 11.3).

## 1. Definitions

Fixed in `docs/decisions.md` (2026-11-19, "M5 scores and H2, fixed before the figures") and committed before the key was read against the ratings.

| Term | Definition |
|---|---|
| Unit | An excerpt, one per run: 16 scenarios × 4 conditions = 64 (`docs/narrative_quality.md` §1). `results/m5_key.json` maps it to its run. |
| Score | The mean of the two raters' ratings of an excerpt on an item, 1 to 5. A condition's score is the mean over its 16 excerpts, median beside it. |
| **H2 / RQ3** | Per item, the D − A difference in mean score with its 95% interval. B − A and C − A beside it. |
| Reading | D is worse on an item when the interval lies wholly below 0, better when wholly above; otherwise no difference is shown. H2 is contradicted if D is worse on any item. No margin was fixed, so an interval containing 0 does not show that D is no worse. |
| Interval | 95% percentile bootstrap over whole runs (one excerpt each), 10,000 resamples, stratified by condition, seed 20261101 (`bootstrap` in `adm/eval/metrics.py`). |
| Fixed beforehand | Each rater alone; D − A paired by scenario (resampling the 16 scenarios); short scenarios and long sessions apart, no interval. |

## 2. Set-up

| Item | Value |
|---|---|
| Ratings | SD's `results/m5_ratings.jsonl` (sha256 `e4d987f6…c45b`, `docs/m5_rating_sd.md`) and SS's `results/m5_ratings_SS.jsonl` (sha256 `52a7a8b3…2208`, `docs/m5_rating_ss.md`), as in 10.5 |
| Key | `results/m5_key.json`, opened for the first time against the ratings by this command |
| Command | `python -m adm.eval.m5_scores --m5-ratings results/m5_ratings.jsonl --m5-ratings results/m5_ratings_SS.jsonl --doc docs/m5_scores.md` |
| Output | `results/m5_scores.json` (gitignored; for the team Drive under `results/`) and the block in §3, written by the command. |

## 3. Results

<!-- results:start -->
64 excerpts, one per run, 16 scenarios × 4 conditions; raters SS and SD. Score: the mean of the two raters' ratings, 1 to 5. Intervals: 95% percentile bootstrap over whole runs, 10,000 resamples, stratified by condition, seed 20261101.

**H2** (D − A per item, D worse when the interval lies wholly below 0): **not contradicted**: on no item does the D − A interval lie wholly below 0. No margin was fixed, so this does not show that D is no worse.

### Mean score per condition

Mean of the 16 excerpts' scores, median in brackets.

| Item | A | B | C | D |
|---|---|---|---|---|
| coherence | 3.69 (4.0) | 3.72 (3.8) | 3.59 (3.5) | 3.66 (3.5) |
| vividness | 4.28 (4.5) | 4.09 (4.0) | 4.00 (4.0) | 3.94 (4.0) |
| tone | 4.75 (5.0) | 4.66 (4.5) | 4.34 (4.5) | 4.50 (4.5) |
| engagement | 3.25 (3.5) | 3.25 (3.5) | 3.38 (3.5) | 3.41 (3.5) |

### Difference from condition A (H2, RQ3)

| Item | B − A | 95% interval | C − A | 95% interval | **D − A** | 95% interval | Reading |
|---|---|---|---|---|---|---|---|
| coherence | +0.03 | -0.31 to +0.38 | -0.09 | -0.41 to +0.22 | **-0.03** | -0.31 to +0.28 | no difference shown |
| vividness | -0.19 | -0.50 to +0.12 | -0.28 | -0.62 to +0.06 | **-0.34** | -0.69 to +0.00 | no difference shown |
| tone | -0.09 | -0.34 to +0.16 | -0.41 | -0.69 to -0.12 | **-0.25** | -0.53 to +0.03 | no difference shown |
| engagement | +0.00 | -0.34 to +0.34 | +0.12 | -0.19 to +0.44 | **+0.16** | -0.16 to +0.50 | no difference shown |

### D − A for each rater alone, and paired by scenario

| Item | SS alone | 95% interval | Reading | SD alone | 95% interval | Reading | Paired by scenario | 95% interval |
|---|---|---|---|---|---|---|---|---|
| coherence | +0.12 | -0.44 to +0.75 | no difference shown | -0.19 | -0.50 to +0.12 | no difference shown | -0.03 | -0.28 to +0.25 |
| vividness | -0.38 | -1.00 to +0.25 | no difference shown | -0.31 | -0.69 to +0.06 | no difference shown | -0.34 | -0.59 to -0.06 |
| tone | +0.06 | +0.00 to +0.19 | no difference shown | -0.56 | -1.06 to +0.00 | no difference shown | -0.25 | -0.56 to +0.09 |
| engagement | +0.25 | -0.38 to +0.94 | no difference shown | +0.06 | -0.19 to +0.31 | no difference shown | +0.16 | -0.12 to +0.50 |

### Each rater's mean, and short scenarios against long sessions

Means per condition: SS / SD, then the pooled score over the 12 short scenarios / the 4 long sessions, no interval.

| Item | Condition | SS / SD | Short / long |
|---|---|---|---|
| coherence | A | 3.50 / 3.88 | 3.79 / 3.38 |
| coherence | B | 3.56 / 3.88 | 3.79 / 3.50 |
| coherence | C | 3.19 / 4.00 | 3.50 / 3.88 |
| coherence | D | 3.62 / 3.69 | 3.67 / 3.62 |
| vividness | A | 4.50 / 4.06 | 4.21 / 4.50 |
| vividness | B | 4.12 / 4.06 | 4.04 / 4.25 |
| vividness | C | 4.00 / 4.00 | 3.83 / 4.50 |
| vividness | D | 4.12 / 3.75 | 3.92 / 4.00 |
| tone | A | 4.94 / 4.56 | 4.75 / 4.75 |
| tone | B | 4.88 / 4.44 | 4.58 / 4.88 |
| tone | C | 4.75 / 3.94 | 4.25 / 4.62 |
| tone | D | 5.00 / 4.00 | 4.50 / 4.50 |
| engagement | A | 3.50 / 3.00 | 3.33 / 3.00 |
| engagement | B | 3.31 / 3.19 | 3.33 / 3.00 |
| engagement | C | 3.56 / 3.19 | 3.38 / 3.38 |
| engagement | D | 3.75 / 3.06 | 3.33 / 3.62 |
<!-- results:end -->

The command gives byte-identical `results/m5_scores.json` on a second run: sha256 `a803b223d2385fcf2ced5e1cd2c699265d50c4f7d80fdc0626eebd5be4ecff77`.

## 4. Reading

- **H2 is not contradicted, and not shown either.** On no item does the D − A interval lie wholly below 0. But every interval contains 0, and no margin was fixed on 1 November, so the data do not show that D's narration is no worse than A's: they show no difference at this sample size.
- **Vividness is on the boundary.** D − A is −0.34, interval −0.69 to 0.00: the upper bound is exactly 0, so by the pre-set rule (wholly below 0) D is not worse. The paired-by-scenario interval, fixed beforehand as a secondary view, is −0.59 to −0.06 and does exclude 0. D is the lowest condition on vividness (3.94 against A's 4.28), and both raters rate D lower alone (SS −0.38, SD −0.31). This is the closest the data come to D reading worse. It is reported as a pointer, not as a contradiction of H2.
- **Tone: C is below A.** C − A is −0.41 (−0.69 to −0.12), the one difference whose headline interval excludes 0. It is not a hypothesis test (H2 is about D), and it rests mostly on SD's ratings (C 3.94 against A 4.56; SS rates every condition near 5). D − A on tone is −0.25 (−0.53 to +0.03).
- **Coherence and engagement do not move.** D − A is −0.03 and +0.16; every condition is within 0.09 of A on coherence and within 0.16 on engagement.
- **The two raters do not agree on direction.** SS has D above A on coherence, tone and engagement; SD has D below A on coherence, vividness and tone. Only vividness has both below. With ordinal alpha below 0 on every item (`docs/agreement.md`), the pooled differences cannot be read as properties of the narration alone.
- **Short and long sessions** show no consistent pattern by condition; four long sessions per condition are too few to read.

## 5. Limitations, for the report

- **The M5 instrument did not reach agreement** (alpha −0.27 to −0.01, `docs/agreement.md`), so H2 and RQ3 rest on ratings that two raters do not share. SD's 64 ratings took about 7 minutes (`docs/m5_rating_sd.md` §3), and SS's tone ratings are at the ceiling (58 of 64 at 5), which leaves little room for a difference on tone in SS's ratings.
- **16 excerpts per condition**, one per scenario. A difference of half a point would likely show; a difference of a quarter would not.
- **No margin for "no worse"** was fixed, so H2 can be contradicted but not confirmed.
- **The raters are team members** who built the system, rating blind to condition.
