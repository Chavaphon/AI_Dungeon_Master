# 8. Future work and conclusion

<!-- WBS 11.4 · Owner: SD · Reviewer (11.6): SS · Outline: docs/report_outline.md §8 · Draft 2026-11-19 -->

## 8.1 Future work

Each item below follows from a result or a limitation in this report.

- **Larger and hosted models.** The first open question is whether a model that makes better use of its context would narrate D's facts and B's and C's state faithfully (Sections 6.2 and 7.1). The grid, the scenarios, the rubric and the analysis are all reproducible from a seed and a manifest (Appendix A), so swapping the model and re-running is the cheapest way to separate the effect of grounding from the effect of model size.
- **A player study.** Real players would test what this study could not: whether they notice divergence, whether it matters to their enjoyment, and whether the result line helps them catch it (Sections 6.4 and 7.1). Players also adapt to the state, which would remove the attacks that scripts send after the fight is over.
- **Harnessing the narration itself.** The divergence sits at the edge of the harness (Section 6.3), so the next design step is to constrain or check the narration, not only the calls. Three options suggest themselves:
  - give D's narrator the in-scope entities and the stances of the NPCs present, as well as the turn's facts;
  - check each narration against the state before showing it, with the checker as a gate and a retry;
  - restrict the narrator to describing only the entities the facts name.

  Each can be added as a new condition on the same ladder.
- **Automated `RESOURCE` checks, and a better checker.** The checker's weak recall, and its lack of any `RESOURCE` check, are why every M1 figure needed hand labels (Section 7.3). Better checks would let M1 cover the whole grid rather than a third of it.
- **Independent human annotators.** Both M1 annotators started from AI drafts. Second annotators for M1 and M3 who label from scratch would turn the agreement figures into genuine human inter-rater reliability (Section 7.2).
- **A better M5 instrument.** Rater training on anchor excerpts, and enough time per excerpt, would help M5 reach agreement. So might a paired comparison of the four conditions' excerpts, which would ask raters to rank rather than score.
- **Intent-aware retries.** The forced re-prompt, and the pressure to return a valid call, produced invented inventory changes (Sections 5.5 and 6.2). A retry that allows "no call" as a legitimate end, or that checks a call's effect against the request, would test whether CONTROL can be tightened without costing intent fidelity.

## 8.2 Conclusion

This project built an autonomous Dungeon Master in which a local language model never writes to game state: it proposes tool calls, a deterministic engine validates and executes them, and the model narrates the outcome. It then measured how far the narration drifts from that state under four levels of grounding, over 192 runs, 6,420 turn records, and 2,124 hand-labelled turns.

**RQ1.** Grounding did not reduce narration-state divergence. Condition D, with the full engine, diverged at 57.4 per 100 narrated turns against 55.9 for condition A, which had no state at all. The ratio was 1.03 (0.74 to 1.48), so H1, a halving, is not supported. No step on the ladder showed a benefit. The state in the prompt (B) and a self-check instruction (C) did not reliably lower the rate either, so there was no point at which a benefit levelled off. The engine kept the state correct by construction, with zero state-audit violations, but the narration written from that state invented entities and misstated conditions as often as narration written with no state.

**RQ2.** Divergence did not grow over a session. Over the four 52-turn long sessions, no condition's slope differed from zero, and D did not drift more slowly than A. The rate rose and fell with what the script asked for, not with how long the session had run.

**RQ3.** No cost of grounding to narrative quality was detected. No item's D − A difference was wholly below zero, so H2 is not contradicted. Vividness came closest to showing D worse. The two raters did not agree on any item, however, and no margin for "no worse" was fixed, so this study cannot claim that grounding is free.

Within the limits of one 8-billion-parameter local model and no player study, the evidence supports a narrower claim than the one the project set out to test. A validated rules engine makes an autonomous Dungeon Master's mechanics trustworthy: every outcome is legal, logged and reproducible, and the cost is about two seconds a turn. It does not make the Dungeon Master's words trustworthy. The design rule moved the hallucination out of the state and left it in the prose, and closing that gap is the work this study points to next.
