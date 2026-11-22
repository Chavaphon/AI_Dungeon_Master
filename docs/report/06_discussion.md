# 6. Discussion

<!-- WBS 11.4 · Owner: SD · Reviewer (11.6): SS · Outline: docs/report_outline.md §6 · Draft 2026-11-19 -->

This section interprets the results of Section 5. Section 6.1 takes each hypothesis and research question in turn. Section 6.2 asks what the rules engine changed and what it did not, and why D's narration diverged as often as A's. Section 6.3 returns to the SPECIFY / HARNESS / VERIFY / CONTROL framing of Section 1.5, and Section 6.4 adds observations from the Sponsor User sessions as colour. The limits on every claim here are set out in Section 7.

## 6.1 The hypotheses and research questions

**H1 failed, and clearly.** The project expected the full grounding of condition D to halve the divergence rate. Instead D diverged at 57.4 per 100 narrated turns against A's 55.9, a ratio of 1.03 (0.74 to 1.48) (Table 5.3). The interval is wide, because each condition has only 16 runs, but its lower bound of 0.74 is still far above the threshold of 0.5. A reduction of the size H1 predicted would have shown up, and it did not. Removing `PHANTOM`, the category with the known scoring inconsistency, makes the ratio larger, not smaller (1.20).

**RQ1: no layer of the ladder shows a benefit, so there is no point where the benefit levels off.** RQ1 asked where along the ladder the benefit levels off. The ladder was built to show which layer does the work, and the answer at this sample size is that none does. B, with the state in its prompt, is at 54.2. C, which adds the self-check, is the lowest at 44.5, but its ratio to A, 0.80 (0.53 to 1.21), has an interval that contains 1. If C's advantage is real it is smaller than this design can detect, and it is not a finding. Section 1.3 worried that the ladder might produce a circular result, with D trivially beating A on state accuracy. That worry is answered, though not in the expected direction: D does win on state accuracy (Section 6.2), but that win does not carry over to the narration, which is what M1 measures.

**RQ2: divergence did not grow over a session in any condition.** Every long-session slope's interval contains 0, and so does D − A (Table 5.4). What moved the rate was the script. Stretches with combat and many named characters drew more divergences in every condition, and the per-run slopes followed the scenario rather than the condition (Section 5.2). The narration does not drift further from the state as the session lengthens, at least over 52 turns with a rolling summary every eight. Its error rate is high from the first turn.

**RQ3 and H2: no cost to narrative quality was shown, but the instrument cannot carry the claim.** No item's D − A interval lies wholly below 0, so H2 is not contradicted (Table 5.12). Three things stop this from becoming "grounding costs nothing":

- **No margin was fixed for "no worse".** So H2 could be refuted but never confirmed.
- **Vividness lies on the boundary.** Its upper bound is exactly 0.00, and the paired interval, a secondary view, excludes 0. D is the lowest condition on vividness, and both raters, taken alone, put it below A. A plausible reason is that D's narrator writes from a short list of facts rather than the open-ended context the other conditions see. That is a hypothesis for future work, not a result.
- **The two raters do not agree** on any M5 item (alpha −0.27 to −0.01, Table 5.14), and they disagree even on the direction of D − A for two of the four items, coherence and tone.

The honest reading is that this study did not detect a cost to narrative quality and was not well placed to detect one. C's lower tone (C − A −0.41, −0.69 to −0.12) is the one M5 difference whose interval excludes 0. It is consistent with a self-check instruction leaking into the prose, but it was not a hypothesis and it rests mostly on one rater.

**The latency target was met, with room to spare.** D's p95 was 7.89 s, and its slowest turn 9.67 s (Table 5.10). The two-call loop costs about two seconds a turn over a single narration call on an 8 GiB laptop GPU, so latency is not what limits the approach.

**Objective 3 was met on its rule, but not in its spirit.** The pooled M1 alpha of 0.894 clears 0.6. Both label sets, however, began as drafts from the same AI model, and both reviewers accepted almost all of the draft (Section 5.8). The figure shows that the rubric can be applied consistently from the same starting point. It does not show that two people reading independently would agree, which is what an inter-rater target is meant to establish.

## 6.2 What the engine changes, and what it does not

**The engine changed the state completely.** In condition D every mechanical outcome came from dice and rules. No hit point went out of range, no slot or quantity went below zero, and no combatant acted out of turn: the state audit is zero on all 1,551 narrated D turns, as it is on the replayed ground truth of A to C (Section 5.6). The engine refused 573 tool-call attempts and logged all 54 turns it could not save (Section 5.4). The failure catalogue shows the same thing turn by turn: in every condition D entry the state stayed legal, even when the model's call or narration did not (Section 5.3). For the job it was given, keeping the game's state correct, the HARNESS works.

**It did not change the narration.** D's `PHANTOM` and `CONTRADICT` rates (30.1 and 22.7) are close to A's (33.1 and 20.9) (Table 5.5). D's narration still describes 7.5 rule breaks per 100 turns that the engine never executed (Table 5.9). Three mechanisms in the design and data help explain why a correct state did not produce correct prose.

1. **D's narrator sees less than B's and C's.** By design, D's narration call receives the facts of the turn: what the engine resolved, and the bands of the combatants it touched. It does not receive the whole state (Sections 3.4 and 3.5). The facts say nothing about scenery, nothing about NPCs the turn did not touch, and nothing about what is in scope, so they cannot stop the narrator inventing candles or misjudging a hostile keeper's mood (catalogue entries 2 and 7). D has the highest `RELATION` rate (2.1 per 100 turns, against 0.2 to 0.9), although it rests on 11 divergences. The decision to narrate from the facts was meant to keep the narration tied to what happened. It also cut the narrator off from the context it needed for the parts of the story the turn did not touch.
2. **More information did not help the narrator use it.** B and C were given the full state, every HP value and status, and C was also told to check its narration against it. Neither improved reliably on A (Table 5.3). The catalogue shows narrators in B, C and D describing combatants in the wrong condition, and unconscious combatants as acting, with the truth in their prompt (entries 3, 4, 5 and 8). For an 8-billion-parameter local model, putting the truth in the prompt does not make the model act on it. The bottleneck is the model's use of the information, not its availability. Whether a larger model would close this gap is the first question this study leaves open (Section 8).
3. **The script outran the fights.** Scripted inputs do not adapt to how an encounter goes, so attacks arrive after the last enemy is down. This one pattern produces most of the rejections in M2 (`ENCOUNTER_OVER`, 268 of 573), most of the automated M4 candidates (121 of 185), and many `CONTRADICT` labels in every condition. Fixed stimuli are what make the conditions comparable, so this is not a flaw in the comparison. But it means the absolute rates describe play against a script that ignores the state, which a human player would not do.

**The loop added a failure of its own: valid calls for the wrong action.** M3 found that about 30% of executed calls in D do not do what the player asked (70.2% faithful, Table 5.8). The commonest reason is an invented inventory change while the player rested, looked or talked. The catalogue shows how this happens (entries 2, 6 and 10). After a rejection, or after the forced re-prompt that follows a `{"tool": null}` reply, the model reaches for a call the validator will accept rather than the one the player meant. The validator, working as specified, accepts it. And once a wrong call is accepted, its result stays in the state: in entry 10 a misread at input 2 caused an invented call fifteen inputs later. So the engine keeps the state legal, but not necessarily true to the story.

**What remains in D, then, is narration-state divergence of exactly the kind Section 1.2 predicted:** "the rule does not remove hallucination. It moves it." The results put a figure on how far it moved. All of the mechanical error left the state, but none of the descriptive error left the narration.

## 6.3 The framing revisited

Section 1.5 claimed that each of the four design decisions discharges one responsibility of the agentic-engineering framing. The evidence supports that claim, and it also shows where each responsibility stops.

**SPECIFY held.** Every failure the system produced has a name and a count: nineteen rejection codes, a failure kind for every failed turn, and a reason code for every unfaithful call (Sections 5.4 and 5.5). This is what made the error taxonomy possible at all. The specification covered the calls, though, and not the prose. Nothing in the contract says what a narration may claim, so the narration's failures had to be found afterwards by people.

**HARNESS held for everything it covered, and it covered the state.** The model could not write the state, and it did not. But the narration call is unharnessed text. The facts block constrains what the narrator is told; nothing constrains what it writes. The divergence the project measures sits exactly at the edge of the harness, and the results show that edge clearly.

**VERIFY earned its layers, but its top layer was thinner than planned.** Each layer caught something the one below missed:

- The automated checker alone would have put M4 at about 0.4 per 100 turns. The human pass found 9.0 (Table 5.9).
- The validator passed every call that M3 found unfaithful. Only the critic layer saw that 30% of valid calls misread the request.

The human layer, though, began from AI drafts that were accepted almost without change, for M1 on all 2,124 turns and for M3 on 238 of 242. So human review here was closer to confirming a model's labels than to an independent check (Section 7). Layered verification is only as strong as its least independent layer.

**CONTROL bounded the cost, and the spending limit interacts with intent.** The budget of two retries saved 86.6% of rejected turns. It ended the rest as logged failures, with no open-ended loop, and kept the p95 under 8 s (Sections 5.4 and 5.6). The forced re-prompt after a first `{"tool": null}`, however, is pressure to return some call. It produced the out-of-combat `dodge` and the invented items of catalogue entries 2 and 10. A control meant to stop the model from giving up too easily also pushes it towards calls that are legal but wrong. A spending limit is not neutral: it shapes what the agent spends on.

**"The agent gains autonomy; the engineer keeps responsibility."** In this system the engineering kept responsibility for the state and discharged it fully. It did not, and by design could not, keep responsibility for the words. The main lesson of the study is that a state that is correct by construction is necessary for a trustworthy autonomous narrator but is not sufficient for one. Making the narration follow that state needs its own specification, harness and verification.

## 6.4 Observations from the Sponsor User sessions

Five friends each played one informal session of a development build (`docs/sponsor_feedback.md`). They were not a study and none of what they said is a result. Their remarks are included here only because they echo the measured findings in a player's words.

- Players found the edges of the harness at once. One meditated into "wind bending power", one became a demi-god, and one "was able to destroy the landscape". None of these has a tool, so the model most likely proposed no call and the narration ran with nothing from the engine to hold it back (the sponsor logs were not read). This is the unharnessed narration of Section 6.3, met in play.
- Two players said the result line, which is built from the audit record, sometimes disagreed with the story. Since the line comes from the state, the narration was the part in the wrong. The line made the divergence visible to the player.
- Valid calls for the wrong action appeared too. "Kill myself" became the loss of the character's sword, and running downstairs gained a torch. These are the misread intents that M3 samples.
- Three of the five found the result line useful, and two called the game "very fun". One player said the story "make sense and follow what I input".
