# 7. Limitations and threats to validity

<!-- WBS 11.4 · Owner: SD · Reviewer (11.6): CI · Outline: docs/report_outline.md §7 · Draft 2026-11-19 -->

The results of Section 5 hold under the conditions described in this section, and no claim in this report goes beyond them. The first two limits apply to every finding.

## 7.1 The two limits that bound every finding

**One small local model on one machine.** Every turn of every run was produced by a single open-weight model, `llama3.1:8b` (Grattafiori et al., 2024) at Q4_K_M quantisation. It was chosen from a shortlist of models of at most 9.7 billion parameters that fit an 8 GiB laptop GPU, and run through Ollama on one machine (Section 3.8). **The results may not hold for larger models, other model families, or hosted models.** In particular, the central finding, that a correct state in the prompt or in the facts did not make the narration follow it (Section 6.2), may be a property of this model's size rather than of grounding. A model that makes better use of its context could narrate condition D quite differently. The latency figures (Section 5.6) describe this laptop only.

**No player study.** No player took part in the experiment. The 192 runs were played from fixed scripts, not by people. Narrative quality was rated by two members of the team, who also built the system, not by players. **Nothing in this report measures what players experience, enjoy or notice.** The scripted inputs also do not adapt to the state: an attack is still scripted after the last enemy is down. This keeps the conditions comparable, but it inflates some rates relative to real play (Section 6.2). The five Sponsor User sessions were informal, single sessions with friends, and they are not evidence (Section 6.4).

## 7.2 Annotation and rating

**M1 labels are an AI draft accepted unchanged.** The first annotator's labels on all 2,124 turns of the M1 sample were drafted by an AI model from the blind view. SD accepted every one of them without edits (`docs/m1_annotation.md` §3). Every M1 rate, ratio and slope is therefore the drafting model's reading of rubric v1.0, confirmed by one person. The drafter never saw the condition, so the drafts are not expected to favour one condition over another, but this is not an independent human count. The same applies to the confirmed `RULE` breaks in M4 (Table 5.9).

**The M1 alpha is between two reviewed AI drafts.** The overlap labels began from a separate draft by the same model, and SS changed 17 of its 511 turns in a review of about 40 minutes (`docs/m1_overlap.md` §5). The alpha of 0.894 is therefore likely higher than two independent human annotators would reach, and it is not human inter-rater reliability. The Objective 3 rule was also fixed when this alpha was already known (Section 5.8).

**Two inconsistencies within the M1 labels.** About 32 turns name an item that appears only in the player's input, and these were scored inconsistently across the drafting batches. 259 borderline calls were accepted as drafted (`docs/m1_annotation.md` §3). The analysis without `PHANTOM` was fixed beforehand to guard against the first, and it did not change the conclusion (Section 5.1).

**M3 has a single annotator, starting from an AI draft.** CI reviewed the AI-drafted verdicts and changed the reason code on 4 of 242, and no verdict (`docs/m3_annotation.md` §3). As agreed at the Week 5 checkpoint, there is no second annotator, so M3 has no agreement statistic.

**The M5 instrument did not reach agreement.** Ordinal alpha was below zero on every item (Table 5.14), and several things weaken the ratings:

- **SD's ratings were fast and narrow.** The second rater's 64 ratings took about 7 minutes, about 7 seconds per excerpt, against a planned 3.5 minutes each. Most were 3 or 4 (`docs/m5_rating_sd.md` §3).
- **SS's tone ratings were at the ceiling.** The first rater gave tone 5 for 58 of 64 excerpts (`docs/m5_rating_ss.md` §3).
- **The two raters do not agree on direction.** H2 and RQ3 therefore rest on ratings the raters do not share, and their differences may reflect the rater rather than the condition (Section 6.1).

**Builders as raters.** All annotation and rating was done by the team that built the system. Blinding to condition was kept throughout, but the raters knew the hypotheses and the design.

## 7.3 Instruments and design

**The automated checker is weak.** On its validation set, precision was 0.25 and recall 0.35. `PHANTOM` precision was 0.19, and there is no automated `RESOURCE` check at all (`docs/checker_validation.md` §4). The checker was used only to show candidates to a human, and 83% of the confirmed rule breaks were added by hand (Section 5.6). The automated M4 headline is a floor, not an estimate.

**The ground truth for conditions A to C is the replayed script state.** Conditions A to C keep no state, so their narration is scored against the state the script's expected calls produce when replayed with the run's seed (Section 4.1). That state is not necessarily the one the narration implied. If A's narration has an attack miss where the replay has it hit, every later turn is scored against the replay's version. This is a principled choice, since there is no other authoritative state for A to C, but it means A to C are measured against a story they did not tell.

**Deliberate simplifications of the rules.** The game is a small subset of D&D. An unconscious combatant cannot be attacked, and the encounter ends when the last hostile drops, with no death saves (CLAUDE.md §4.8). There are seven tools and no mechanics for movement, romance or summoning. Narration that is correct for tabletop D&D can therefore be a divergence or a rule break here. Attacking a downed foe is the clearest example, and it is common in the data (Section 5.6).

**Sample size and power.** Annotation was by hand, so M1 covers 64 of the 192 runs, one seed per scenario. Each condition has 16 runs, and 4 for RQ2. The intervals are honest about this and wide: a halving of the rate would have shown, but a modest effect would not (Section 5.1). The same holds for M5, with 16 excerpts per condition.

**Analysis rules added after 1 November.** The hypotheses, the latency target and the bootstrap were fixed before any scoring. Several reading rules came later, but each was fixed before the figures it governs were read:

- the sensitivity ratios without `PHANTOM`, 15 November;
- the latency interval rule, 13 November;
- the RQ2 slope definition, 17 November;
- the H2 reading rule, 19 November.

Each is recorded in the decision log with its date (`docs/decisions.md`). The H2 rule was fixed after the M5 agreement figures were known, but before any condition mean was computed.
