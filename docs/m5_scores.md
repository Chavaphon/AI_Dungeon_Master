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
<!-- results:end -->
