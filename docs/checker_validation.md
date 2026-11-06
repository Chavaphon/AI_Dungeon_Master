# Checker validation

WBS 8.10 · Owner: SD · Status: **method fixed, labels pending** · CLAUDE.md wins on any conflict.

CLAUDE.md §10.3 asks for the automated checker to be validated against 30 hand-labelled turns before it is used, with precision and recall recorded here, including the cases it is known to miss. This document is that record. The checker is `python -m adm.eval.checker` with every check of WBS 8.6 to 8.9: `entity_mention` (`PHANTOM`), `hp_band` (`CONTRADICT`), `stance` (`RELATION`), and `rule_violation` and `state_audit` (`RULE`, M4).

## 1. Method

| Item | Value |
|---|---|
| Transcripts | The dry run (`docs/dry_run.md`): `s01_cellar` and `long01_border_road` × A–D × seed 3001, 312 turns, in `runs/dry_run/` (team Drive). No main-grid seed, so the labelled turns are never shown to an M1 or M5 annotator again. |
| Sample | 30 narrated turns, stratified by condition: 8 from A, 8 from B, 7 from C, 7 from D. Within a condition, turns are taken in sha256 order of `checker-validation-v1/{run_id}/{input_index}`, so the draw is fixed with no RNG. |
| Labeller | SD, by `docs/rubric.md` v0.6 for the four divergence categories, and by CLAUDE.md §10.3 item 6 (decision 56) for `RULE`. |
| Blinding | The sheet shows each turn's player input, narration, and the state and engine actions it is scored against (rubric §1). It shows no condition, run id or checker output. |
| Labels | `results/checker_validation/labels.csv`, one row per divergence or rule break: `sample_id`, `category`, `phrase` (copied from the narration), `notes`. `NOTE` rows record observations. `5.3` in `notes` marks a rubric §5.3 case. |
| Matching | A candidate matches at most one label of the same turn and category whose phrase overlaps it (spans overlap, or one text contains the other). Matched candidate: true positive. Unmatched candidate: false positive. Unmatched label: miss. |
| Reported | Precision and recall per category, over all candidates and over high-confidence ones; true and false positives per check and kind; every miss and false positive; the number of turns with a rubric §5.3 case (rubric §7 point 2). |

Commands:

```bash
python -m adm.eval.checker_validation sample --runs runs/dry_run   # sheet.md, sample.json, labels.csv
# label results/checker_validation/labels.csv from sheet.md
python -m adm.eval.checker_validation score --runs runs/dry_run    # rewrites section 2 below
```

`RESOURCE` has no automated check (decision log 2026-11-05, WBS 8.7), so its recall is zero by design. Its labels are still counted, so the human pass knows how much it must cover alone.

## 2. Results

<!-- results:start -->
Pending: the labels are not done yet.
<!-- results:end -->

## 3. Known blind spots

Listed by each check's decision-log entry, for this validation to measure. The misses in section 2 show which of these occurred in the sample.

| Check | Blind spots |
|---|---|
| `entity_mention` (8.6) | Lower-case phantom locations ("the crypt below"); too many of a kind ("three rats"); nouns outside the lexicons; a phantom sharing a word with an in-scope name ("a silver key" beside an iron key). |
| `hp_band` (8.7) | Band phrases outside the lexicon ("half dead", "fully restored"); pronoun subjects in a sentence naming several combatants; a wrong phrase that fits a bystander in the same sentence; acting verbs after a pronoun; past and future claims (flagged low); spelled-out HP above twenty. |
| `stance` (8.8) | Markers outside the lexicon (sarcasm, refusals, threats with no marker word); behaviour aimed at someone other than the party; pronoun subjects in a sentence naming several NPCs; every one-step mismatch, forgiven by design. |
| `rule_violation` (8.9) | Attacks after a pronoun; attack verbs outside the list; a second attack by a combatant that did act; slots spent without naming the spell; past-perfect mentions of an earlier attack (may be flagged). |
| `RESOURCE` | Not automated. |

## 4. Conclusion

To be written once section 2 is filled: whether each check is fit for the 9.4 pass, which candidates go to the human pass, and whether any rule should change before the rubric freeze (WBS 8.12).
