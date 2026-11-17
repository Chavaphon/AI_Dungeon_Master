# Inter-rater agreement and Objective 3

WBS 10.5 · Owner: SD · Computed 2026-11-17 · CLAUDE.md wins on any conflict.

Krippendorff's alpha for M1 (the 20% double-scored overlap, CLAUDE.md §10.4) and M5 (both raters on all 64 excerpts, `docs/narrative_quality.md` §8), checked against 0.6. Done when: "Objective 3 criterion checked against the 0.6 threshold" (TASK_CHECKLIST.md, 10.5).

## 1. Definitions

Fixed in `docs/decisions.md` (2026-11-17, "Agreement and the Objective 3 rule, fixed before the figures") and committed before the command was run on both raters' files. The M1 figures were already known from 9.6 (`docs/m1_overlap.md` §6) when the Objective 3 rule was fixed; the M5 figures were not.

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
**Objective 3** (pooled M1 alpha at least 0.6): **met**, alpha = 0.894. Both annotators' M1 labels start from AI drafts by the same model (§4).

### M1: the 20% overlap, 511 turns

| Unit | SD | SS | Alpha | Metric | Meets 0.6 |
|---|---|---|---|---|---|
| `PHANTOM` | 137 | 148 | 0.888 | interval | yes |
| `CONTRADICT` | 134 | 136 | 0.888 | interval | yes |
| `RESOURCE` | 11 | 11 | 0.797 | interval | yes |
| `RELATION` | 2 | 2 | 1.000 | interval | yes |
| **All four, pooled** | 284 | 297 | **0.894** | interval | yes |
| Turn has any divergence | 202 | 203 | 0.865 | nominal | yes |

78 of 2044 units differ. Review of the overlap turns: SD: accepted 511, SS: accepted 494, edited 14, relabelled 3.

### M5: narrative quality, 64 excerpts

| Item | Alpha | Metric | Meets 0.6 | Exact agreement | Mean SS | Mean SD |
|---|---|---|---|---|---|---|
| coherence | -0.187 | ordinal | **no** | 39% | 3.47 | 3.86 |
| vividness | -0.013 | ordinal | **no** | 28% | 4.19 | 3.97 |
| tone | -0.266 | ordinal | **no** | 42% | 4.89 | 4.23 |
| engagement | -0.154 | ordinal | **no** | 34% | 3.53 | 3.11 |

Ratings per item, 1 to 5:

- coherence: SS 1:1 2:6 3:24 4:28 5:5 · SD 3:11 4:51 5:2
- vividness: SS 2:2 3:14 4:18 5:30 · SD 3:7 4:52 5:5
- tone: SS 3:1 4:5 5:58 · SD 3:12 4:25 5:27
- engagement: SS 1:1 2:6 3:22 4:28 5:7 · SD 2:4 3:49 4:11
<!-- results:end -->

The command gives byte-identical `results/agreement.json` on a second run: sha256 `25b4703a2f1bd18991e59b7ae0772ded3d4647926685ad744a3f595a25debbdf`. SS's two files matched the checksums in `docs/m1_overlap.md` and `docs/m5_rating_ss.md` before use.

## 4. Reading

- **Objective 3 is met on its pre-set rule**: the pooled M1 alpha is 0.894, above 0.6, and every M1 category meets 0.6 (`RELATION` rests on 2 divergences, so its 1.000 says little). The figures are those of 9.6, recomputed from the checksummed logs.
- **But the M1 alpha is not human inter-rater reliability.** Both sets of labels start from AI drafts by the same model, made separately: SD accepted all 511 overlap turns unchanged, SS accepted 494, edited 14 and relabelled 3. The alpha is mostly the agreement of two drafts with each other, and likely higher than two independent humans would reach (decision log 2026-11-15). The report must state Objective 3 with this caveat.
- **M5 agreement fails on every item.** Ordinal alpha is −0.187 for coherence, −0.013 vividness, −0.266 tone and −0.154 engagement: no better than chance, and slightly worse. Exact agreement is 28% to 42%.
- **Why: the two raters used the scale differently.** SD put almost everything at 3 or 4 (coherence 4 for 51 of 64, engagement 3 for 49); SS spread wider and higher (vividness 5 for 30, tone 5 for 58). Read after the figures, not fixed beforehand: the ratings are within one point of each other for 83% to 91% of excerpts, so the raters rarely disagree by much, but they do not rank the excerpts the same way, which is what alpha measures.
- **This weakens H2 and RQ3.** M5 is the only measure of narrative quality. With raters who do not agree, a D-minus-A difference in mean M5 (H2) cannot be read as a property of the narration: it may reflect rater, not condition. 11.3 should report H2 per rater as well as pooled, and 11.4 should say the M5 instrument did not reach agreement.

## 5. Limitations, for the report

- **M1: two reviewed AI drafts** (above; `docs/m1_overlap.md` §5). The review of the overlap took about 40 minutes, about 5 seconds a turn.
- **M5: SD's ratings were fast.** The 64 excerpts took about 7 minutes, about 7 seconds each (`docs/m5_rating_sd.md` §3), and SS's tone ratings are at the ceiling (58 of 64 at 5, `docs/m5_rating_ss.md`). Both limit what alpha can show, in addition to the different use of the scale.
- **The Objective 3 rule was fixed with the M1 alpha already known** from 9.6; the M5 alphas were not. The rule follows CLAUDE.md §10.4, whose 20% overlap is M1's, and CI and SS are asked to confirm it.
- **No interval for alpha**, as fixed.

