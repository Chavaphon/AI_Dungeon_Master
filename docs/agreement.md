# Inter-rater agreement and Objective 3

WBS 10.5 · Owner: SD · CLAUDE.md wins on any conflict.

Krippendorff's alpha for M1 (the 20% double-scored overlap, CLAUDE.md §10.4) and M5 (both raters on all 64 excerpts, `docs/narrative_quality.md` §8), checked against 0.6. Done when: "Objective 3 criterion checked against the 0.6 threshold" (TASK_CHECKLIST.md, 10.5).

## 1. Definitions

Fixed in `docs/decisions.md` (2026-11-17, "Agreement and the Objective 3 rule, fixed before the figures") and committed before the command was run on both raters' files.

| Term | Definition |
|---|---|
| M1 overlap | The 16 overlap runs (511 turns) recomputed from `experiments/main_grid.json` (`m1.overlap_runs`); SD's 9.5 labels against SS's 9.6 labels, paired by `m1_agreement.pair` (one line each per turn, the same checker candidates). |
| M1 unit | One turn and one rubric category, valued by the number of divergences (decision 58). Alpha: interval per category and pooled; nominal on whether a turn has any divergence. `RULE` is M4. |
| M5 | SS (9.8) and SD (9.9), one rating per excerpt of `results/m5_key.json` on each of coherence, vividness, tone and engagement, 1 to 5. Alpha: **ordinal**, per item, over the 64 excerpts. Exact agreement and each rater's mean beside it. |
| **Objective 3** | **Met when the pooled M1 alpha is at least 0.6.** The overlap of §10.4 is M1's (Week 5 checkpoint, decision 1). Every other alpha is checked against 0.6 and reported; none decides the objective. |
| Interval | None for alpha. |

## 2. Set-up

| Item | Value |
|---|---|
| Logs | SD's machine, `runs/`; every sampled log matches `experiments/main_grid.sha256`. |
| M1 labels | `results/m1_labels.jsonl` (SD, sha256 `53d74b6b…1138e`) and `results/m1_labels_SS.jsonl` (SS, sha256 `dd0a2c8d…0285`, `docs/m1_overlap.md`) |
| M5 ratings | SD's `results/m5_ratings.jsonl` (sha256 `e4d987f6…c45b`) and SS's, renamed to `results/m5_ratings_SS.jsonl` (sha256 `52a7a8b3…2208`, `docs/m5_rating_ss.md`): both raters' tools write `m5_ratings.jsonl`. |
| Command | `python -m adm.eval.agreement --m1-labels results/m1_labels.jsonl --m1-labels results/m1_labels_SS.jsonl --m5-ratings results/m5_ratings.jsonl --m5-ratings results/m5_ratings_SS.jsonl --checksums experiments/main_grid.sha256 --doc docs/agreement.md` |
| Output | `results/agreement.json` (gitignored; for the team Drive under `results/`) and the block in §3, written by the command. |

## 3. Results

<!-- results:start -->
Not yet computed: SS's M1 overlap labels and M5 ratings are on the team Drive.
<!-- results:end -->
