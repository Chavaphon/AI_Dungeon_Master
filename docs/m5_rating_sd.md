# M5 narrative-quality rating, second rater

WBS 9.9 · Owner: SD · Rated 2026-11-15 · CLAUDE.md wins on any conflict.

The second rater's M5 ratings under the form of WBS 8.13 (`docs/narrative_quality.md`). Done when: "Rater blind to condition" (TASK_CHECKLIST.md, 9.9). This record gives the set-up, the counts and the limits. Agreement with the first rater (9.8, SS) is WBS 10.5. Condition comparisons are 10.x and 11.x, not here: the key was not opened.

## 1. Set-up

| Item | Value |
|---|---|
| Copy rated | SD's machine, `runs/A` to `runs/D`. `python -m adm.eval.integrity --checksums experiments/main_grid.sha256`: checksums match for all 192 main-grid logs. |
| Selection | §2 of the form: 16 scenarios × 4 conditions = **64 excerpts**, five exchanges each. The §7 fallback was not used. |
| Code | `adm/eval/annotate.py` at `main` 2772f20 |
| Command | `python -m adm.eval.annotate m5 --rater SD` |
| Output | `results/m5_ratings.jsonl` (gitignored; for the team Drive under `results/`): 64 lines, sha256 `e4d987f6ca49539323c479dd54446d5f6ef0be03baa3613c0593c61127dfc45b` |
| Key | `results/m5_key.json`, written by the tool on the first run. It was not opened, and it is not read for this record. |
| Checks | One line per excerpt, 64 distinct `excerpt_id`, rater `SD` throughout, every item an integer from 1 to 5. |

**Blinding.** The tool shows only the excerpt id, the scenario title, the five inputs and the narration (form §3), in SD's own hash order. No condition, run id, seed or turn number. No draft or AI suggestion was shown: every rating is SD's.

## 2. Ratings

| Item | 1 | 2 | 3 | 4 | 5 | Mean | Median |
|---|---|---|---|---|---|---|---|
| Coherence | 0 | 0 | 11 | 51 | 2 | 3.86 | 4 |
| Vividness | 0 | 0 | 7 | 52 | 5 | 3.97 | 4 |
| Tone | 0 | 0 | 12 | 25 | 27 | 4.23 | 4 |
| Engagement | 0 | 4 | 49 | 11 | 0 | 3.11 | 3 |

These pool all conditions and say nothing about H2.

## 3. Limitations

- **Time.** The tool wrote the key at 12:00 and the last rating at 12:07: about 7 minutes for 64 excerpts, some 7 seconds each, against about 3.5 minutes each in the form (§1). The excerpts cannot all have been read in full at that pace. The ratings are kept as made, at SD's decision, and are reported with this limitation.
- **Little spread.** Coherence and vividness are 4 for 51 and 52 of 64 excerpts, and engagement is 3 for 49. With so little spread, ordinal alpha in 10.5 may be low, and a D-minus-A difference in 11.x has little room to show in SD's ratings.
- **Notes.** The five notes are single digits ("4", "4", "4", "3", "4"), most likely scores typed at the note prompt. They carry no comment.
- **10.5 and the report** should state this alongside the agreement figure, and report the first rater's ratings on their own as well as pooled.
