# Checker validation

WBS 8.10 · Owner: SD · Status: **done, 2026-11-08** · CLAUDE.md wins on any conflict.

CLAUDE.md §10.3 asks for the automated checker to be validated against 30 hand-labelled turns before it is used, with precision and recall recorded here, including the cases it is known to miss. This document is that record. The checker is `python -m adm.eval.checker` with every check of WBS 8.6 to 8.9: `entity_mention` (`PHANTOM`), `hp_band` (`CONTRADICT`), `stance` (`RELATION`), and `rule_violation` and `state_audit` (`RULE`, M4).

## 1. Method

| Item | Value |
|---|---|
| Transcripts | The dry run (`docs/dry_run.md`): `s01_cellar` and `long01_border_road` × A–D × seed 3001, 312 turns, in `runs/dry_run/` (team Drive). No main-grid seed, so the labelled turns are never shown to an M1 or M5 annotator again. |
| Sample | 30 narrated turns, stratified by condition: 8 from A, 8 from B, 7 from C, 7 from D. Within a condition, turns are taken in sha256 order of `checker-validation-v1/{run_id}/{input_index}`, so the draw is fixed with no RNG. |
| Labeller | SD, by `docs/rubric.md` v0.6 for the four divergence categories, and by CLAUDE.md §10.3 item 6 (decision 56) for `RULE`. **Provenance:** Claude drafted a label for every divergence it found from the same blind sheet (no checker output seen), with a list of borderline cases it left out; SD reviewed the draft and accepted all 20 labels and 3 notes. The labels are therefore Claude's reading, approved by SD, not an independent hand labelling (decision log 2026-11-08). |
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
Sample: 30 turns (A 8, B 8, C 7, D 7); 20 labels.

### By category

| Category | Labels | Candidates | True positives | Precision | Recall | High: candidates | High: precision | High: recall |
|---|---|---|---|---|---|---|---|---|
| `PHANTOM` | 10 | 21 | 4 | 0.19 | 0.40 | 7 | 0.57 | 0.40 |
| `CONTRADICT` | 7 | 3 | 2 | 0.67 | 0.29 | 2 | 0.50 | 0.14 |
| `RESOURCE` (no check) | 0 | 0 | 0 | – | – | 0 | – | – |
| `RELATION` | 0 | 1 | 0 | 0.00 | – | 0 | – | – |
| `RULE` | 3 | 3 | 1 | 0.33 | 0.33 | 1 | 0.00 | 0.00 |
| **All** | 20 | 28 | 7 | 0.25 | 0.35 | 10 | 0.50 | 0.25 |

### By check

| Check | Kind | True positives | False positives |
|---|---|---|---|
| `entity_mention` | `character` | 0 | 7 |
| `entity_mention` | `item` | 4 | 7 |
| `entity_mention` | `proper_noun` | 0 | 3 |
| `hp_band` | `band` | 2 | 0 |
| `hp_band` | `status` | 0 | 1 |
| `rule_violation` | `after_encounter_end` | 0 | 1 |
| `rule_violation` | `out_of_turn` | 1 | 0 |
| `rule_violation` | `slot_below_zero` | 0 | 1 |
| `stance` | `stance` | 0 | 1 |

### Missed (13)

| Sample | Category | Phrase | Notes |
|---|---|---|---|
| S06 | `RULE` | striking the enraged rat with a swift thrust | attack narrated after the encounter was already over (victory); no call executed |
| S11 | `CONTRADICT` | still clutching his injured arm, takes a step back | first bandit is 0/7 unconscious but narrated as acting |
| S11 | `PHANTOM` | its men ready to intervene | the toll captain's men are not in state or scenario |
| S12 | `PHANTOM` | its men busy | the toll captain's men again |
| S12 | `PHANTOM` | the toll bridge | separate place not in the scenario's locations (rubric 6.1.1) |
| S15 | `CONTRADICT` | We thought you said it was gone over the edge | The Missing Mule is not_started but treated as already given up (rubric 6.2.2) |
| S18 | `PHANTOM` | the river's edge | the river is not a scenario location |
| S20 | `PHANTOM` | The toll captain's men | not in state or scenario |
| S20 | `PHANTOM` | the river rushing over the rocks | the river is not a scenario location |
| S21 | `CONTRADICT` | before launching himself at you once more | first bandit is 0/7 unconscious but narrated attacking |
| S21 | `RULE` | before launching himself at you once more | attack by a combatant that did not act (bandit 01 is down; the NPC attack was bandit 02) |
| S25 | `CONTRADICT` | it manages to rise to its paws | second rat is 0/7 unconscious but narrated getting up |
| S29 | `CONTRADICT` | the sealed letter, which is still unopened | sealed letter x0 and The Sealed Letter is completed: she no longer has it |

### False positives (21)

| Sample | Check | Kind | Confidence | Mention |
|---|---|---|---|---|
| S01 | `entity_mention` | `character` | low | man |
| S01 | `entity_mention` | `proper_noun` | low | I've |
| S03 | `entity_mention` | `character` | low | man |
| S04 | `entity_mention` | `character` | low | guards |
| S04 | `entity_mention` | `character` | low | man |
| S05 | `rule_violation` | `slot_below_zero` | low | healing spell |
| S10 | `entity_mention` | `item` | low | chest |
| S11 | `entity_mention` | `item` | high | sword |
| S14 | `entity_mention` | `item` | low | chest |
| S16 | `entity_mention` | `character` | low | guard |
| S16 | `entity_mention` | `item` | low | cart |
| S18 | `entity_mention` | `proper_noun` | low | I'm |
| S18 | `stance` | `stance` | low | glare |
| S21 | `entity_mention` | `item` | low | chest |
| S23 | `entity_mention` | `item` | high | pouch |
| S27 | `entity_mention` | `proper_noun` | low | Commander Alderan |
| S27 | `entity_mention` | `character` | low | sister's |
| S28 | `entity_mention` | `character` | low | shape |
| S28 | `hp_band` | `status` | high | bandits attacked |
| S28 | `rule_violation` | `after_encounter_end` | high | bandits attacked |
| S30 | `entity_mention` | `item` | high | pouch |

### Rubric section 5.3 cases (rubric section 7 point 2)

2 of 30 turns: S10, S21.
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

**Overall.** On 30 turns with 20 labelled divergences and rule breaks, the checker raised 28 candidates: precision 0.25 and recall 0.35 over all, 0.50 and 0.25 over high confidence. It under-reports, as CLAUDE.md §10.2 asks, but not cleanly: most of its output is noise from `entity_mention`, and most real divergences are missed. It is a triage aid for 9.4, not a measurement. M1 must come from the human pass.

**Per check, for the 9.4 pass:**

| Check | Verdict | Reason |
|---|---|---|
| `entity_mention` (`PHANTOM`) | Keep as a candidate list only; every candidate goes to the human pass | 4 of 21 right (0.19); the `character` and `proper_noun` kinds were never right (0 of 10), mostly generic words ("man", "guards", "shape") and contractions ("I've", "I'm"). Missed all phantom places (the river, the toll bridge) and unnamed groups (the toll captain's men), as section 3 predicted. |
| `hp_band`, kind `band` | Fit for use | 2 of 2 right. |
| `hp_band`, kind `status` | Human confirmation needed | 0 of 1. Of the 4 labelled "unconscious combatant narrated acting" cases, the commonest `CONTRADICT` in the sample, it caught none as `status`; one (S11, bandit 2) was caught as a band phrase, and three (S11 bandit 1, S21, S25) were missed. |
| `stance` (`RELATION`) | Human confirmation needed | 1 low-confidence false positive; no `RELATION` divergence was labelled, so recall is untested. |
| `rule_violation` (`RULE`, M4) | Report high-confidence and low separately, as decision 56 says | 1 of 3 right; its one high-confidence `after_encounter_end` (S28, "bandits attacked") was a past-tense mention. |
| `RESOURCE` | Not automated | No `RESOURCE` divergence was labelled in this sample. |

**Missed most often:** unconscious combatants narrated as acting (3 of 4), phantom places and groups (6), and a quest or item treated against its recorded state (S15, S29).

**For the rubric freeze (8.12):** (1) the scenario's scripted inputs mention characters with no `display_name` (the drovers, the gate guards, the fort's commander); this validation treated them as in scope, and the rubric should say so, or not, explicitly. (2) A hit narrated against a target that took no damage (S21) is a §5.3 event and is not scored; 8.12 should confirm that is intended. (3) Rubric section 5.3 cases were 2 of 30 turns (S10, S21), as rubric section 7 point 2 asked.
