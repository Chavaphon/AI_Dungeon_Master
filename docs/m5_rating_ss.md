# M5 narrative-quality rating, first rater

WBS 9.8 · Owner: SS · Rated 2026-11-13 to 2026-11-15 · CLAUDE.md wins on any conflict.

These are the first rater's M5 ratings, made under the form of WBS 8.13 (`docs/narrative_quality.md`). Done when: "Rater blind to condition" (TASK_CHECKLIST.md, 9.8). This record gives the set-up, the counts and the limits. Agreement with the second rater (9.9, SD, `docs/m5_rating_sd.md`) is WBS 10.5. Condition comparisons belong to 10.x and 11.x, not here, and this record does not read the key.

## 1. Set-up

| Item | Value |
|---|---|
| Copy rated | SS's machine, `runs/A` to `runs/D`. `python -m adm.eval.integrity --checksums experiments/main_grid.sha256` matches all 192 main-grid logs, with no gaps. |
| Selection | §2 of the form: 16 scenarios × 4 conditions = **64 excerpts**, five exchanges each. The §7 fallback was not used. |
| Code | `adm/eval/annotate.py` at `main` (unchanged for `m5` since WBS 8.15) |
| Command | `python -m adm.eval.annotate m5 --rater SS` |
| Sittings | Two: 42 excerpts by 2026-11-13, and the remaining 22 on 2026-11-15. The tool resumes where the rater stopped (`q`). |
| Output | `results/m5_ratings.jsonl` (gitignored; for the team Drive under `results/`, beside SD's). It has 64 lines, sha256 `52a7a8b34e0f3d3f10f2e97fd53d371e478c6c35be2812c2cf9f6ace72a42208`. |
| Key | `results/m5_key.json`, written by the tool on the first run (2026-11-12). Neither the rater nor this record opens it. |
| Checks | 64 lines, one for each of the 64 `excerpt_id`s the selection gives, rater `SS` throughout, and every item an integer from 1 to 5. |

**Blinding.** The tool shows only the excerpt id, the scenario title, the five inputs and the narration (form §3), in SS's own hash order. It shows no condition, run id, seed or turn number. Before rating, SS read the same 64 excerpts in a preview file written with the tool's own selection and rendering (`render_excerpt`, in SS's order). It held nothing the tool does not show. No draft or AI suggestion was shown, so every rating is SS's own.

## 2. Ratings

| Item | 1 | 2 | 3 | 4 | 5 | Mean | Median |
|---|---|---|---|---|---|---|---|
| Coherence | 1 | 6 | 24 | 28 | 5 | 3.47 | 4 |
| Vividness | 0 | 2 | 14 | 18 | 30 | 4.19 | 4 |
| Tone | 0 | 0 | 1 | 5 | 58 | 4.89 | 5 |
| Engagement | 1 | 6 | 22 | 28 | 7 | 3.53 | 4 |

These pool all conditions and say nothing about H2.

## 3. Limitations

- **Tone is at the ceiling.** 58 of the 64 excerpts are rated 5 on tone. An item with almost no spread leaves little room for a D-minus-A difference (H2) to show. It can also give a low or undefined ordinal alpha in 10.5, even when the raters rarely disagree.
- **The raters differ in spread.** SS uses most of the scale on coherence, vividness and engagement. SD gave 4 on coherence and vividness for most excerpts and 3 on engagement for most (`docs/m5_rating_sd.md` §3). 10.5 should report the two raters' ratings separately as well as pooled.
- **Preview.** Reading all 64 excerpts before rating was not in the form. The preview kept the blinding and the rater's order, but SS saw every excerpt before scoring any of them, which may have set a common reference point across excerpts.
- **Notes.** There is one note, on one excerpt, about the mood of its first exchange. No note reports a hint about the condition.
