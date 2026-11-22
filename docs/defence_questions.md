# Defence questions, with prepared answers

WBS 11.10 · Owner: ALL · Drafted 2026-11-22 · CLAUDE.md wins on any conflict.

The ten questions the examiners are most likely to ask at the defence on 2 December, with an answer for each, then seven reserve questions. Done when: "Within time; answers prepared for the top ten questions" (TASK_CHECKLIST.md, 11.10). This page covers the second half. The two timed rehearsals are tracked by the team outside the repository.

Nothing here computes anything. Every number is copied from the report (`docs/report/`) or the record it cites, as in `docs/defence_deck.md` §3. If 11.6 or a later change alters a figure, update the answer that quotes it.

## 1. How to use this page

- **Length.** Each answer is meant to be said aloud in 30 to 45 seconds. Lead with the first sentence; the rest is there if the examiner follows up.
- **Who answers.** The lead below is a suggestion by area: CI for the tool loop and M3, SD for M1 and the results, SS for the architecture, M5 and the overlap. Anyone may answer.
- **What to show.** The slide named is the one to put on screen, usually a backup (B1 to B5, `docs/defence_deck.md` §2).
- **The disclosure.** Any answer that rests on an M1 number says that the labels began as an AI draft that one annotator accepted. Slides 9 and 12 already say this; do not drop it under pressure.
- **When you do not know.** Say so, and say where the report would hold it. A wrong number on the day costs more than "I would need to check Table 5.x".

## 2. The top ten

### Q1. "H1 failed. So was building the engine pointless?"

**Lead:** CI · **Show:** slide 11, then B4 · **Source:** report §6.2; Tables 5.7, 5.9, 5.10

No. The engine did the job it was given, and the measurement shows it. The state audit found zero rule breaks: no hit points out of range, no slot below zero, nobody acting out of turn. Of the turns with a rejected call, 86.6% were saved within the retry budget, and the rest failed safely and were logged. The 95th-percentile turn took 7.89 seconds, under the 10-second target. What H1 measured is the narration, and there the engine did not help. So the finding is not "the engine failed". It is that a correct state is necessary for a trustworthy narrator but not sufficient.

### Q2. "Why did D not reduce divergence?"

**Lead:** SD · **Show:** B2 · **Source:** report §6.2; Table 5.5

Three mechanisms in the design and the data help explain it:

1. D's narrator sees only the facts of the turn, never the scene, so nothing stops it inventing scenery.
2. B and C had the full state, and C was also told to check against it, yet neither improved reliably on A. For this 8-billion-parameter model, putting the truth in the prompt does not make it act on the truth.
3. The script kept attacking after fights ended, which drives many `CONTRADICT` labels in every condition.

The two big categories barely move: `PHANTOM` is 30.1 per 100 turns in D against 33.1 in A, and `CONTRADICT` is 22.7 against 20.9. These are explanations, not tested findings.

### Q3. "Your M1 labels were drafted by an AI. Why should we trust them?"

**Lead:** SD · **Show:** slide 12 · **Source:** report §5.1, §5.8, §7.2

The caution is fair, and we say it wherever the numbers appear: one annotator accepted the AI draft without edits on all 2,124 turns, so every M1 figure is that model's reading of rubric v1.0, confirmed by one person. Two things limit the damage. First, the drafter never saw the condition, so it has no reason to favour one condition over another. Second, the analysis without `PHANTOM`, the category with a known scoring inconsistency, was fixed in advance, and it makes D look worse, not better: a ratio of 1.20. The alpha of 0.894 is between two reviewed AI drafts, not two independent people, and we do not present it as human inter-rater reliability.

### Q4. "Isn't this just a weak 8B model? Would a bigger model fix it?"

**Lead:** SS · **Show:** slide 12 · **Source:** report §7.1, §8.1

Possibly. That is the first limit we state. We used one open-weight model, `llama3.1:8b` at Q4_K_M, because it had to run locally on an 8 GiB laptop GPU with no paid API, and it is pinned by digest. The central finding, that a correct state does not make the narration follow it, may be a property of this model's size rather than of grounding, and the report says so. The useful thing is that the whole grid replays from a seed and a manifest, so a larger model is one more run of the same ladder, not a new study.

### Q5. "Sixteen runs per condition: is the study powered to find anything?"

**Lead:** SD · **Show:** slide 9 · **Source:** report §5.1, §6.1, §7.3; Table 5.3

It was powered for the effect we predicted, not for a small one. H1 predicted a halving, a D/A ratio of at most 0.5. The observed ratio is 1.03, and even the lower end of its interval, 0.74, is well above 0.5. So a halving would have shown, and it did not. A modest effect would not show at this size. That is why C, the lowest at a C/A of 0.80, is not a finding: its interval of 0.53 to 1.21 contains 1. The sample was limited by hand annotation: 64 of the 192 runs, about 530 narrated turns per condition.

### Q6. "How is a divergence decided? Isn't it subjective?"

**Lead:** SD · **Show:** B2 · **Source:** CLAUDE.md §10; `docs/rubric.md`; report §4.5, §7.3

As little as we could make it. Rubric v1.0 was frozen at gate G3, after a pilot and before any main run was scored, and it is pinned by its hash. It has four categories (`PHANTOM`, `CONTRADICT`, `RESOURCE`, `RELATION`) and fixed rules, for example hit-point bands at 0.75 and 0.35 of maximum with no forgiveness for an adjacent band, because the band is handed to D's narrator explicitly. An automated checker proposes candidates, and a human confirms or rejects each one. The checker alone is weak, with precision 0.25 and recall 0.35 on its validation set, which is why every M1 number comes from the human-confirmed labels, not from the checker.

### Q7. "Your script keeps attacking after the fight is over. Doesn't that bias the results?"

**Lead:** CI · **Show:** slide 12 · **Source:** report §5.4, §6.2, §7.1

It inflates the absolute rates, but not the comparison. The scripted inputs are fixed so that every condition receives exactly the same stimuli, and they never adapt to how an encounter goes. The cost is real: `ENCOUNTER_OVER` accounts for 268 of the 573 rejected tool-call attempts and 121 of the 185 automated M4 candidates. Every condition faced the same late attacks, though, so the difference between conditions still holds. A human player adapts to the state, so the rates describe play against a script, not play by a person.

### Q8. "Why does D's narrator get only the facts, and not the whole state?"

**Lead:** SS · **Show:** slide 5, then B2 · **Source:** CLAUDE.md §9.1, §15 item 12; report §6.2, §8.1

It was a design decision, made deliberately: the narrator should describe what the engine resolved, not reinterpret the whole state. The cost showed up in the data. The facts say nothing about scenery, about NPCs the turn did not touch, or about what is in scope, and D has the highest `RELATION` rate, 2.1 per 100 turns against 0.2 to 0.9 elsewhere, although that rests on only 11 divergences. This is a plausible reason, not a tested finding. The obvious next step is to give D's narrator the in-scope entities and NPC stances as well as the facts, as a new condition on the same ladder.

### Q9. "About 30% of executed calls don't do what the player asked. Is the tool loop making things worse?"

**Lead:** CI · **Show:** B4 · **Source:** report §5.5, §6.2, §6.3; Table 5.8

It adds a failure of its own, and the measurement found it. In M3, 70.2% of executed calls were faithful to the player's request. The commonest miss is an invented inventory change while the player rests, looks or talks. It comes from the control loop: after a rejection, or after the forced re-prompt that follows a first "no tool" reply, the model reaches for a call the validator will accept rather than the one the player meant. The validator, working as specified, cannot see that. Our reading is that a spending limit is not neutral: it shapes what the agent spends on. A retry that allows "no call" as a legitimate outcome is in the future work.

### Q10. "Your two raters disagreed on narrative quality. What can you claim about H2?"

**Lead:** SS · **Show:** slide 11 · **Source:** report §5.7, §6.1, §7.2; Tables 5.12, 5.14

Very little, and we say so. H2 is not contradicted: no item's D minus A interval lies wholly below 0. But no margin for "no worse" was fixed, so H2 could only ever be refuted, never confirmed. Vividness sits on the boundary, with an upper bound of exactly 0.00. And the two raters do not agree: ordinal alpha is between −0.27 and −0.01 on every item, and they disagree even on the direction of D minus A for some items. The honest summary is that we did not detect a cost to narrative quality, and our instrument was not well placed to detect one.

## 3. Reserve questions

Shorter answers, for questions that are likely but less central.

| Question | Answer | Source |
|---|---|---|
| "Did you pick these examples?" (slide 10) | No. The two rows were fixed in the decision log and committed (0dc03b0) before the draw, and each is the first qualifying pair in hash order, from 14 and 31 candidates. The line under the rows, D/A 1.03, is the result. | `docs/exhibit_a_vs_d.md` §2; slide 10's notes |
| "How can sampling at temperature 0.7 be reproducible?" | The run's seed is sent to Ollama on every call, and every run starts from a freshly loaded model with nothing else on the server. The same seed, scenario and condition replay to identical state hashes; only the timings differ. | B5; CLAUDE.md §1.1 invariant 4, §2.2 |
| "Why no player study?" | It was withdrawn for time. Quality was rated by two team members, blind to condition. The five Sponsor User sessions were informal and are not evidence. | report §6.4, §7.1 |
| "Why not JSON mode or constrained decoding?" | Prompt mode was already 100% schema-valid for this model in benchmarking. A grammar cannot stop a valid call for the wrong action, which is the real failure, and it would hide the parse failures that M2 counts. | `docs/decisions.md` 2026-10-06 (WBS 3.7); CLAUDE.md §15 item 26 |
| "How is this different from CALYPSO?" | CALYPSO supports a human DM, who stays in charge of the facts. Here the narrator is autonomous, and we measure how far its narration drifts from a state it cannot write. | report §2.2 |
| "Why is C the lowest? Does the self-check work?" | C is lowest at 44.5, but its ratio to A has an interval of 0.53 to 1.21, which contains 1, so it is not a finding. C also has a lower tone score than A, consistent with the self-check instruction leaking into the prose, but that was not a hypothesis. | report §5.1, §6.1; Table 5.3 |
| "Did you change the analysis after seeing the data?" | H1, H2, the latency target, the three seeds and the bootstrap were fixed on 1 November, before any scoring. Four reading rules came later, each dated in the decision log and each fixed before the figures it governs were read. | report §7.3; CLAUDE.md §10.5 |

## 4. Fix before rehearsing

- **Slide 14's speaker notes** still end with "or the demo video (WBS 12.12)". The demo video was dropped (#245), so the only fallback is the recorded run of `docs/live_demo.md` §2 step 9. Delete the phrase in PowerPoint and update the deck's sha256 in `docs/defence_deck.md` §6, as 11.8 did.
