# 4. Experimental method

<!-- WBS 11.2 · Owner: CI · Reviewer (11.6): SD · Outline: docs/report_outline.md §4 · Draft 2026-11-16 -->

This section describes the experiment: the four conditions and what they share (4.1), the scenarios (4.2), the grid of runs and how it was played and checked (4.3), the six metrics (4.4), the divergence rubric and the automated checker (4.5), the three human annotation tasks (4.6 to 4.8) and the analysis (4.9). The results are in Section 5. The figures given here describe the method, the instrument and the size of the dataset; none is a value of M1 to M6 or an answer to a hypothesis.

## 4.1 Conditions

The four conditions add one layer of grounding at a time:

| Condition | State in the prompt | Self-check instruction | Rules engine and tools | Model calls per turn |
|---|---|---|---|---|
| A | no | no | no | 1 (narration) |
| B | yes | no | no | 1 (narration) |
| C | yes | yes | no | 1 (narration) |
| D | yes | no | yes | 2 (tool call, narration), plus up to 2 retries |

**They differ only in the prompt template and in whether tools are wired** (invariant 7). The engine, the scenarios, the seeds, the model and its settings, K, the rolling summary, the history format and the safety filter are the same in all four. The templates are given in full in Appendix B.1, and tests check that they differ line by line only as the table says: B is A plus the state block, C is B plus the four-line self-check, D's tool-call template is B plus the tool list and the tool-call instruction, and D's narration template is A plus the facts block (`docs/prompt_templates.md` §2). The summary and history paragraphs are rendered from the same two block files in every template, and the condition's closing instruction (C's self-check, D's tool-call instruction, D's facts block) comes last, after them, closest to the player's input.

Conditions A to C share one narration-only harness. Each scripted input gets one narration call at temperature 0.7 with the same K, history, rolling summary and safety filter as condition D. There is no tool phase and nothing changes the state: in B and C the state is read-only context.

**Ground truth for A to C.** Narration in A to C cannot be scored against a state the conditions never kept. It is scored against the state the scenario script says should hold at each turn, computed offline by replaying the script through the engine with the run's seed. Each scripted input's expected call (Section 4.2) is played as a scripted condition D turn, so a call the engine rejects is a failed turn that does not advance, and an input with no expected call is narration-only. The state after each input is the ground truth for that turn, and both state hashes in an A to C turn record are taken from this replay. Two replays of one seed are byte-identical. In condition D, narration is scored against the logged state after the turn.

## 4.2 Scenarios

Sixteen scenarios supply the stimuli: twelve short scenarios of 26 to 30 scripted inputs and four long sessions of 52 inputs each.

| Short scenarios | Long sessions |
|---|---|
| `s01_cellar` The Cellar Rats · `s02_toll_bridge` The Bandit Toll · `s03_forest_shrine` The Forest Shrine · `s04_goblin_warren` The Goblin Warren · `s05_wayside_inn` The Wayside Inn · `s06_drowned_lighthouse` The Drowned Lighthouse · `s07_smugglers_cove` The Smugglers' Cove · `s08_old_mine` The Old Mine · `s09_harvest_fair` The Harvest Fair · `s10_watchtower` The Goblin Watchtower · `s11_frozen_pass` The Frozen Pass · `s12_bog_witch` The Bog Witch | `long01_border_road` The Border Road · `long02_hollow_manor` The Hollow Manor · `long03_river_market` The River Market · `long04_mountain_monastery` The Mountain Monastery |

Each scenario is one JSON file, validated against a schema (`docs/scenario_format.md`). It holds:

- **An opening narration and the initial state**: one player character, the other combatants, the inventories, the item definitions, the NPC relationships and the quests.
- **The locations** that narration may name. The state has no locations, so this list is what keeps a mention of "the cellar stairs" from counting as a phantom.
- **The encounters**: before which scripted input each one starts and who is in it, since no tool starts one. Every encounter puts the player character against one to three hostiles (with a neutral bystander in `s05_wayside_inn`); `s08_old_mine` has two encounters and the rest one each.
- **The scripted inputs**, each with its full **expected call**, or none for an input with no mechanical effect. A scripted skill check also carries its DC and any advantage, which are authoritative (Section 3.2).
- **Notes for annotators.**

Every scenario exercises at least two of an inventory change, a quest transition and a relationship change, and every long session exercises all three and runs long enough for at least five rolling-summary regenerations. The scripted inputs are fixed, so every condition receives identical stimuli, and they never adapt to how an encounter goes. The expected call serves the offline replay, the checker validation and as guidance for intent-fidelity annotation. **It is not used to grade the model**, because a different but reasonable choice of tool is not a failure.

## 4.3 The grid and how it was run

**The main grid** is 16 scenarios × 4 conditions × 3 seeds (2001, 2002 and 2003, the same in every cell): **192 runs**. The short scenarios hold 327 scripted inputs and the long sessions 208, so the grid holds **6,420 turn records**, one per scripted input per run.

**Gates before the grid.** Two earlier rounds used seeds that no main run uses. Ten 50-turn condition D smoke runs (seeds 1001 to 1010, 30 October) passed gate G2: all ten completed, and 99.0% of first tool-call attempts were schema-valid, so plain prompt mode was kept (`docs/smoke_runs.md`). A dry run of `s01_cellar` and `long01_border_road` under all four conditions at seed 3001 (3 November) passed gate G3: every log passed the audit schema and replayed, and the checker read every log (`docs/dry_run.md`). The 30 turns used to validate the checker and to pilot the rubric were drawn from this dry run, so no main-grid turn was used to tune the instrument.

**Playing the grid.** All runs were played on the machine of Section 3.8 through the batch runner, one run at a time on a freshly loaded model with nothing else on the GPU, with the server version and model digest checked first. The twelve short scenarios ran in two batches of 72 runs on 9 November (`docs/main_run.md`), and the four long sessions in one batch of 48 on 10 November (`docs/long_run.md`). The runner wrote each run to a pending folder and moved it into the dataset only when it covered every scripted input with no transport retry. All 192 runs completed on their first attempt; none was played again.

**Checking the grid.** Every log was validated: each record against the audit schema and its cross-field rules, one record per scripted input with the scripted text, and every state hash replayed (D from its own diffs, A to C against the replayed ground truth). Before annotation, an integrity check ran on the shared copy the annotators read, not on the machine that played the runs (`docs/run_integrity.md`). It confirmed that every planned run was present and valid, that every run's last attempt completed, that all 192 used the same model, and that the three seeds appear in every cell. It found no gap to re-run. The SHA-256 of each of the 192 logs is committed in `experiments/main_grid.sha256`, and every later reader of the logs checks its copy against it.

The grid holds 54 failed turns, all in condition D, where the tool phase exhausted its budget. They are data for M2 and M6. They are not narrated, so they are not scored for divergence; every other turn is a **narrated turn**.

## 4.4 Metrics

| ID | Metric | Definition | Conditions | Data |
|---|---|---|---|---|
| M1 | Divergence rate | Confirmed divergences per 100 narrated turns, overall and per rubric category | A–D | Human labels on 64 whole runs, 2,124 narrated turns (§4.6) |
| M2 | Invalid tool-call rate; recovery rate | Turns with at least one rejected or unparseable attempt / turns; rejected turns with no turn failure / rejected turns. A `{"tool": null}` reply is not a rejection. Rejected attempts / turns is given beside the headline | D | Audit log, all 48 D runs |
| M3 | Intent fidelity | Share of sampled turns whose executed call does what the player asked | D | Human verdicts on a 15% sample, 242 turns (§4.7) |
| M4 | Rule-violation rate | High-confidence `rule_violation` plus `state_audit` candidates per 100 narrated turns (below) | A–D | Automated, all 192 runs; human check on the M1 sample |
| M5 | Narrative quality | Mean 1–5 rating on coherence, vividness, tone appropriateness and engagement | A–D | Two raters, 64 excerpts (§4.8) |
| M6 | Latency and throughput | Mean and p95 seconds per turn (`turn_latency_ms`, every turn including failed ones); tokens per second (`completion_tokens / eval_ms` per model call, then the mean over calls) | A–D | Audit log, all 192 runs |

Rates pooled over runs are ratios of sums, not means of per-run rates.

**M4** is the automated check of the game's rules, in two parts. `state_audit` checks each narrated turn's state and engine actions: HP outside its range, spell slots or a quantity below zero, an action out of turn, a combat action with no encounter. It is zero by construction; a non-zero count would be a harness bug. `rule_violation` checks the narration against the state and what the turn did (D's own call and engine steps, A to C's replayed ground truth): an attack narrated after the encounter ended, an attack by a combatant that did not act in this encounter turn, Cure Wounds cast with no slot left, and negative HP stated. Its candidates are flagged high or low confidence; only high-confidence ones enter M4, and the low-confidence count is given beside it. The headline is this automated figure on all 192 runs. Because the checker misses many narrated rule breaks, the M1 annotators also labelled rule breaks (category `RULE`) on their sample, and the confirmed rate on those 64 runs is reported beside the headline as its human check.

## 4.5 The divergence rubric and the automated checker

**Rubric.** Divergence is annotated by a written rubric, v1.0, frozen at gate G3 under the git tag `rubric-v1.0` and pinned by its hash (`docs/rubric.md`; condensed in Appendix B.2). A divergence is a phrase in the narration that disagrees with the state. It falls into one of four categories:

| Code | Category | The narration... |
|---|---|---|
| `PHANTOM` | Phantom entity | names an item, character or location that is in neither the state nor the scenario definition |
| `CONTRADICT` | State contradiction | asserts something that conflicts with a recorded value: HP band, status, quest state, where an item is |
| `RESOURCE` | Resource error | describes spending, gaining or using up a resource in a way the state does not show |
| `RELATION` | Relationship contradiction | treats an NPC in a way that does not fit its recorded stance |

Every divergence is counted, several per narration if there are several. A phrase that fits two categories is recorded once, in the first that applies in the order above. A repeat within one narration counts once; in a later turn it counts again. **When in doubt, nothing is recorded**, so the rate is a conservative count. A described HP band is compared with the band of Section 3.4, and adjacent bands are not forgiven: 14 of 20 HP is `wounded`, and "barely standing" is a divergence. The `RELATION` category alone allows one step of the stance ladder either side, because stance markers in prose are coarse. Characters, groups and places named in a scenario's scripted inputs are in scope, since the player's own words put them there.

The rubric was piloted before it was frozen (`docs/rubric_pilot.md`). Two annotations of the same 30 dry-run turns were made independently under v0.6: the first was drafted by an AI model from the blind sheet and accepted by SD (the same labels that validate the checker, below), and the second was made by hand by CI. The unit was one turn and one category, valued by the number of divergences recorded. Pooled interval Krippendorff's alpha was 0.731 (`PHANTOM` 0.553, `CONTRADICT` 0.936; `RESOURCE` and `RELATION` had no labels). Eight of the ten disagreeing units were characters named in the scripted inputs, which led to the scope rule above; the other changes at the freeze are listed in the rubric's §7.

**Automated checker.** The checker (`adm/eval/checker.py`) handles the mechanically decidable part of the rubric and produces **candidates, never scores**. Each candidate carries a category, a confidence (high or low), the phrase and its sentence. It checks:

1. **Entities.** Every display name in the state and the scenario is matched against the narration. An item word, a character word or a capitalised name in mid-sentence that matches nothing in scope is a `PHANTOM` candidate.
2. **HP bands and status**, by a band-phrase lexicon. A phrase is flagged only when it fits none of the combatants it may describe; events, negations and figurative uses are skipped, and hedged or ambiguous phrases are low confidence.
3. **Stance**, by a stance-marker lexicon, for NPCs with a recorded stance, flagged only when more than one step from the stance after the turn.
4. **Rule violations**, the M4 checks of Section 4.4.

There is no automated `RESOURCE` check. Before use, the checker was validated against 30 hand-labelled dry-run turns, drawn in hash order, 8, 8, 7 and 7 from A to D, and labelled blind to condition and checker output, by the AI-drafted labels accepted by SD described above (`docs/checker_validation.md`). Over all categories its precision was 0.25 and its recall 0.35 (0.50 and 0.25 for high-confidence candidates alone). `PHANTOM` precision was 0.19. The checker therefore cannot measure M1 by itself, and is used only to show candidates to a human, who confirms or rejects each one and reads the whole narration for what it missed. The automated pass over all 192 runs scored 6,366 narrated turns and wrote 4,457 candidates (`docs/automated_pass.md`).

## 4.6 M1 annotation

**Sample.** M1 is annotated on whole runs, so that the run-level bootstrap has whole units and the long sessions keep every turn for RQ2. For each scenario, one seed of the three is chosen by SHA-256 order, and all four conditions are taken at that seed: **64 runs, 2,124 narrated turns** (`adm/eval/m1.py`). Pairing by seed means the four conditions of a scenario share their dice and inputs.

**Procedure.** The annotation tool shows each turn blind to condition, run and seed: the player's input, the state the narration is scored against (Section 4.1), the narration, and the checker's candidates for the turn, numbered. The annotator confirms the true candidates and adds any divergence none of them covers, by rubric v1.0. Rule breaks are labelled too, as `RULE`, for the M4 check; they are not part of M1. M1 per condition is the first annotator's confirmed candidates plus added labels in the four rubric categories, per 100 narrated turns.

**AI drafting.** The labels were not made from scratch. A model drafted labels for every turn from the same blind view, with a note on each borderline call, and a team member then reviewed each turn in the tool, accepting the draft or relabelling the turn; each label line keeps the draft it was shown and whether it was accepted or edited. In the words fixed in the decision log:

> M1 labels were drafted by an AI model from the blind view, for the full sample and, separately, for the 20% overlap. SD reviewed the first and SS the second, turn by turn. Agreement on the overlap is therefore between two reviewed AI drafts and is reported as such.

SD accepted the draft on all 2,124 turns of the full sample without change (`docs/m1_annotation.md`). The overlap is 16 runs, 4 of each condition's 16 (a fifth, rounded up), holding 511 turns; its draft was made separately, by drafting agents that could not see the first draft or SD's labels, and SS changed 17 of the 511 turns (14 edited, 3 relabelled) (`docs/m1_overlap.md`). Section 7 discusses what this does to the agreement figure.

## 4.7 M3 intent fidelity

M3 is the critic layer of Section 3.9: it looks for the failure no validator can see, a valid call for the wrong action (`docs/intent_fidelity.md`, condensed in Appendix B.4).

**Population and sample.** Every condition D turn of the main grid whose tool phase did not fail, including turns that ended with no call, since choosing no call can also be wrong: 1,551 turns. The sample is drawn per scenario, so that each scenario's share of the sample matches its share of the turns. In each stratum the turns are ordered by the SHA-256 of a fixed prefix, the run and the input index, and the first `ceil(0.15 × n)` are taken: **242 turns**, 148 from short scenarios and 94 from long sessions (`docs/m3_annotation.md`). The draw uses no random number generator and is reproducible from the dataset alone.

**Decision rule.** The annotator sees the player's input, the executed call with each identifier followed by its display name, and the state before the turn. They do not see the narration, the expected call, the condition or the earlier attempts. They answer one question, "does the executed call do what the player asked, as far as one call in this game can?", as faithful or unfaithful, working down six ordered rules: no mechanical request needs no call; a mechanical request needs one; the tool must be one a reasonable reading leads to; the arguments the request determines must match it (the DC and the wording of a justification are not judged); in a multi-part request the call must do the part the request is for; and when in doubt, faithful. Each unfaithful verdict takes one reason code: `MISSED`, `INVENTED`, `WRONG_TOOL`, `WRONG_TARGET`, `WRONG_VALUE` or `DROPPED`. M3 is the faithful share. Its 95% interval is a Wilson interval (Wilson, 1927) on the sampled turns, as the protocol fixes (`docs/intent_fidelity.md` §5); it is the one interval in the report that is not a run-level bootstrap.

**Annotator and AI drafting.** M3 is single-annotated, as agreed at the Week 5 checkpoint, so no agreement statistic exists for it. As with M1, a model drafted each verdict from the annotator's view, and the annotator reviewed each turn:

> M3 verdicts were drafted by an AI model from the annotator's view and reviewed turn by turn by one annotator (CI), who changed 4 of 242 drafts, all in their reason code.

## 4.8 M5 narrative quality

**Unit and sample.** M5 rates an excerpt of five consecutive exchanges, each a scripted player input and the narration shown for it, because coherence and engagement need more than one reply to judge. There is one excerpt per scenario and condition: **64 excerpts**. The four excerpts of a scenario come from the same seed and the same five inputs, so conditions are rated on identical stimuli and compared within a scenario. The seed and window are chosen by SHA-256 order as the first in which none of the four runs has a failed turn: a failed turn shows the player a request to rephrase, which only D can produce, and would reveal the condition.

**Blinding.** The rater sees an opaque excerpt identifier, the scenario's title, the five inputs and the five narrations as the player saw them, and nothing else: no condition, run, seed, turn number, state, facts or rolls. Each rater has their own SHA-256 order over all 64 excerpts, so the four excerpts of a scenario are not seen side by side and the raters do not share order effects. The key from excerpt to run was not opened until both had finished.

**Form.** Each excerpt is rated as a whole from 1 to 5 on coherence, vividness and tone appropriateness, with anchors at 1, 3 and 5, and on engagement, "Would you want to keep reading?", with an anchor at every point (Appendix B.3). Raters judge the narration as readers of the story: they do not check it against the state, which is M1's job. A reply that acts for the player character or breaks the second-person voice is marked down under tone.

**Raters.** Both raters, SS and SD, rated all 64 excerpts, which is more than the 20% overlap required, so agreement is computed on the full set. No AI draft was used for M5.

## 4.9 Analysis

The hypotheses, the latency target and the bootstrap analysis were fixed on 1 November 2026, before any main run was scored, and recorded in the decision log. Later refinements were fixed after the automated checker had run, each marked below with its date. All but the Objective 3 rule were fixed before the figures they govern were read.

- **H1** is supported if the D/A ratio of the M1 rate is at most 0.5 and its 95% interval excludes 1. The B/A and C/A ratios, and every ratio without `PHANTOM`, are given beside it (added 15 November, WBS 10.1).
- **H2** is reported as the 95% interval of the D minus A difference in mean M5 score, for each item. RQ3 is read from the same differences. An item's score in a condition is the mean over its 16 excerpts of the two raters' mean rating; D is worse on an item when the interval lies wholly below 0, and H2 is contradicted if D is worse on any item (added 19 November, WBS 11.3).
- **Latency.** The target is p95 under 10 s per turn in D. It counts as met only if the upper bound of the p95's 95% interval is also under 10 s (added 13 November, WBS 10.4).
- **RQ2** is the pooled least-squares slope of per-turn divergences on the scripted position (`input_index + 1`) in each condition, on the four long sessions, reported as the change in divergences per 100 turns per 10 turns played, with a bootstrap interval and the difference from A (added 17 November, WBS 10.2).

**Intervals.** Every 95% interval in the report, except M3's (Section 4.7), is a percentile bootstrap (Efron & Tibshirani, 1993) that resamples whole runs, never single turns, because turns within a run share their history and are not independent. Each uses 10,000 resamples. Across conditions the resampling is stratified by condition, and a ratio between two conditions resamples each condition's runs separately. All metrics use one shared function (`bootstrap` in `adm/eval/metrics.py`) with its own fixed seed, 20261101, the date the analysis was fixed. It is the only random number generator outside the game's dice, and it never touches a run.

**Agreement.** Krippendorff's alpha is reported against a target of at least 0.6. Objective 3 is met when the pooled M1 alpha reaches it; this rule was fixed on 17 November (WBS 10.5), after the M1 alpha was known (Section 7.2). For M1 it is computed on the overlap, at the interval level on the number of divergences per turn and category, per category and pooled, and at the nominal level on whether a turn has any divergence. For M5 it is computed at the ordinal level on each item over all 64 excerpts.
