# M1 annotation: the second-annotator overlap

WBS 9.6 · Owner: SS · Reviewed 2026-11-15 · CLAUDE.md wins on any conflict.

The second annotator's divergence labels for M1 (CLAUDE.md §10.4) on the 20% overlap, by rubric v1.0 (`docs/rubric.md`), so that Krippendorff's alpha against the first annotator (9.5, `docs/m1_annotation.md`) can be computed. Done when: "Agreement is computable" (TASK_CHECKLIST.md, 9.6). Why the overlap starts from an AI draft is in `docs/decisions.md` (2026-11-15).

## 1. Status

| Item | Value |
|---|---|
| Overlap | 16 runs, a fifth of each condition's sampled runs (`m1.overlap_runs`): **511** narrated turns |
| Draft file | `results/m1_overlap_draft_claude.jsonl` (gitignored; for the team Drive `results/`), sha256 `6b7999245f753db1f1e6d979784f4c951830f3ef17c089bc5f02504387669d84` |
| Draft checks | every overlap turn once, candidate numbers in range, categories known, every phrase in its narration (`m1.load_draft`) |
| Checker candidates shown | 313 on 227 turns; the draft **confirms 91** |
| Labels added beyond the candidates | **268**: `CONTRADICT` 120, `PHANTOM` 90, `RULE` 46, `RESOURCE` 11, `RELATION` 1 |
| Turns with at least one label | 225 |
| Turns with a draft note | 310 |
| Review by SS | **511 of 511** turns: **494 accepted**, **14 edited**, **3 relabelled** with `--redo` without the draft shown |
| Labels file | `results/m1_labels_SS.jsonl` (gitignored; for the team Drive `results/`), sha256 `dd0a2c8dd263710abe7cf1db249d1b3c05927142283694765de032230dd90285` |
| Final labels | **86** candidates confirmed, **260** labels added: `CONTRADICT` 113, `PHANTOM` 89, `RULE` 46, `RESOURCE` 11, `RELATION` 1; 219 turns with at least one label; 17 notes by SS |
| SS's side of the pairing | every overlap turn once, each shown with the checker candidates the sample gives now |
| Agreement | computable once SD's `m1_labels.jsonl` is beside it: §3 step 3 |

Counts per condition are left to 10.1 and 10.5.

## 2. How the draft was made

1. The 16 overlap runs were rendered in SS's run order with `m1.render`, the view the tool shows: the player input, the state the rubric scores against, the narration and the numbered 9.4 checker candidates. Each run's file also gave the scenario's title, locations and opening narration (all in scope by rubric §1). Nothing named the condition, run id or seed.
2. Eight agents drafted the runs, two runs each, each in a fresh context, by rubric v1.0 and CLAUDE.md §10 and §15 items 54–56 and 59. They were told not to read `results/`, any label or draft file, `docs/m1_annotation.md`, `docs/checker_validation.md`, `docs/rubric_pilot.md` or the run logs. SD's labels and the 9.5 draft were not on the machine.
3. Each line is `{"turn_id", "confirmed", "added", "note"}`, the 9.5 format. The note gives the other reading on every borderline call and often says why a candidate was rejected.

## 3. To finish 9.6

1. **Review.** SS reviews every turn:
   ```
   python -m adm.eval.annotate m1 --annotator SS --overlap --draft results/m1_overlap_draft_claude.jsonl
   ```
   Enter accepts the draft and `e` relabels the turn from scratch. `q` stops; the same command resumes.
2. **Rename** the output before fetching SD's labels, since both are written as `results/m1_labels.jsonl`: rename SS's to `results/m1_labels_SS.jsonl`, then download SD's `m1_labels.jsonl` from the Drive.
3. **Check agreement is computable:**
   ```
   python -m adm.eval.m1_agreement --labels results/m1_labels.jsonl --labels results/m1_labels_SS.jsonl
   ```
   It exits 0 only when both annotators have one line for each of the 511 overlap turns and were shown the same checker candidates. It prints alpha on the unit of decision 58. 10.5 reports it.
4. Upload `results/m1_overlap_draft_claude.jsonl` and `results/m1_labels_SS.jsonl` to the team Drive `results/`, then fill in §1 here: the review counts (`accepted`/`edited`) and the labels file's sha256.

## 4. Calls for SS to settle in review

- **Items named only in a player input.** Rubric §6.1 rule 6 brings characters, groups and places named in the scripted inputs into scope, not items, so such items are strictly `PHANTOM`. The batches split on this, as the 9.5 draft did (batch 5 left a player-input rope as scenery, batch 6 scored ropes as `PHANTOM`). Apply one rule. These 22 turns carry a draft note on it: 56b630f6/18, 56b630f6/24, 56b630f6/25, fe945621/26, 39294198/8, 39294198/24, 0eb795be/2, 0eb795be/18, 0eb795be/21, 3f005890/22, 3f005890/27, 15508b71/27, a3874016/16, 0ab9524e/15, 0ab9524e/18, d09fe624/24, 894cb22a/13, 894cb22a/17, 894cb22a/26, 60ec7d10/3, aebbbbe2/17, fba02043/8.
- **Scenery objects.** Candles, lanterns, jars, furnishings and shelf contents were mostly treated as part of a location; only objects handled or used were scored.
- **Downed combatants narrated as acting.** Each later turn in which an unconscious combatant acts explicitly gets one `CONTRADICT` (rubric §5.5). One run has the PC acting at 0 HP for many turns, which accounts for most of the `CONTRADICT` labels.
- **Off-screen groups and places in dialogue** (guilds, capitals, offices) were scored `PHANTOM`.
- **One phrase, two labels.** One turn has a phrase labelled both `CONTRADICT` (an unconscious PC acting, M1) and `RULE` (an attack after the encounter ended, M4). These are different metrics, so the double label stands unless SS decides otherwise.

## 5. Limitations, to be stated in the report

- **The alpha is between two reviewed AI drafts.** The first-annotator labels are the 9.5 AI draft, accepted by SD without change. The overlap labels start from a separate draft by the same model. The alpha therefore measures agreement between two reviewed drafts, likely higher than two independent humans would reach, and is not human inter-rater reliability (decision log 2026-11-15, point 4).
- **Review share.** SS changed 17 of 511 turns (14 edited, 3 relabelled), 3.3%; the other 494 are the draft unchanged. The report gives this, as it gives SD's 0 of 2,124.
- **Review time.** The draft file was written at 12:41 and the labels file last at 13:20 on 2026-11-15, so the review of 511 turns took at most about 40 minutes, about 5 seconds a turn. The report should say the review was quick, so that the labels are read as close to the draft.
