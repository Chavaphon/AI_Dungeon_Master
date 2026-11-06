# Rubric pilot

WBS 8.11 · Owner: SD · Status: **method fixed, labels pending** · CLAUDE.md wins on any conflict.

Before the rubric is frozen at G3 (WBS 8.12), two annotators label the same turns independently by `docs/rubric.md` v0.6, and Krippendorff's alpha measures how far they agree. The disagreements listed in section 2 are the agenda for 8.12.

## 1. Method

| Item | Value |
|---|---|
| Turns | The 30 turns of the 8.10 sample (`docs/checker_validation.md` §1): both dry-run scenarios, `s01_cellar` and `long01_border_road`, under A–D at seed 3001. Both annotators label the same `results/checker_validation/sheet.md`. |
| Annotators | The 8.10 labels (`results/checker_validation/labels.csv`, drafted by Claude from the blind sheet and accepted by SD, decision log 2026-11-08) are the first annotation, and one second team member, labelling unaided,, who labels into `results/checker_validation/labels_<initials>.csv`. Neither sees the other's labels, the condition or the checker's output. |
| Labels | The 8.10 format: `sample_id,category,phrase,notes`, one row per divergence. Only the four rubric categories count here; `RULE` and `NOTE` rows are ignored. Write `6.4` in `notes` for a one-step stance case left unrecorded under rubric §6.4 rule 3. |
| Unit and value | One turn × one category (120 units). The value is the number of divergences of that category the annotator recorded in that turn (rubric §3 rule 1). |
| Agreement | Krippendorff's alpha, interval metric on the counts, per category and over all four pooled; nominal alpha on whether a turn has any divergence. Target ≥ 0.6 (CLAUDE.md §10.4). Alpha is undefined (`–`) when every value is the same. |
| For 8.12 | Every unit where the counts differ, with both annotators' phrases, and the turns noted `6.4` (rubric §7 point 1, the `RELATION` adjacency allowance). |

Command, once both label files exist:

```bash
python -m adm.eval.rubric_pilot --labels SD=results/checker_validation/labels.csv \
    --labels XX=results/checker_validation/labels_XX.csv     # rewrites section 2 below
```

Counting divergences rather than matching phrases keeps the unit the same as M1's, which counts divergences per turn. Two annotators who record the same number for different phrases agree on the count but not on the reading; the disagreement table shows their phrases side by side so 8.12 can catch those cases.

## 2. Results

<!-- results:start -->
Pending: the second annotation is not done yet.
<!-- results:end -->

## 3. For the rubric freeze (WBS 8.12)

To be written once section 2 is filled: which rules caused the disagreements, what changes in rubric v1.0, and whether the `RELATION` adjacency allowance stays (rubric §7 point 1). If alpha is below 0.6, the freeze goes ahead regardless and the weaker pilot is noted (`TASK_CHECKLIST.md`, G3).
