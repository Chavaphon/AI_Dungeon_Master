# Final report outline

WBS 11.1 · Owner: SD · Drafted 2026-11-15 · Status: **agreed by SD, CI and SS, 2026-11-15** · CLAUDE.md wins on any conflict.

The section list of the final report (deliverable D10, due 22 Nov), with a named owner for each section. Done when: "Section list with a named owner each" (TASK_CHECKLIST.md, 11.1). Owners follow the writing tasks of the WBS. Each section lists what it must contain, the tasks and docs it draws on, and who reviews it in 11.6, so that every section is read by someone who did not write it (D10 acceptance).

## Sections at a glance

| # | Section | Owner | WBS | Due | Reviewer (11.6) |
|---|---|---|---|---|---|
| — | Abstract | SD | 11.12 | Sat 21 Nov | CI |
| 1 | Introduction | SS | 11.5 | Sun 15 Nov | SD |
| 2 | Background and related work | SS | 11.5 | Sun 15 Nov | SD |
| 3 | System design | CI | 11.2 | Wed 18 Nov | SS |
| 4 | Experimental method | CI | 11.2 | Wed 18 Nov | SD |
| 5 | Results | SD | 11.3 | Thu 19 Nov | CI |
| 6 | Discussion | SD | 11.4 | Fri 20 Nov | SS |
| 7 | Limitations and threats to validity | SD | 11.4 | Fri 20 Nov | CI |
| 8 | Future work and conclusion | SD | 11.4 | Fri 20 Nov | SS |
| — | References | each section's owner; merged by SD | 11.12 | Sat 21 Nov | — |
| A | Appendix: reproduction and release | SS | 11.11 | Sat 21 Nov | CI |
| B | Appendix: rubric, rating form and protocols | CI | 11.2 | Wed 18 Nov | SS |

The final pack is assembled and checked by SD in 11.12.

## 1. Introduction (SS)

- The problem: language-model DMs narrate things the game state does not support, and the drift is rarely measured.
- The one design rule (CLAUDE.md §1): the model never writes to state. It proposes tool calls, and a deterministic engine validates and executes them.
- The contribution is the measurement, not the system: how far narration drifts from state under four levels of grounding.
- RQ1 to RQ3 and H1, H2 and the latency target, as fixed before scoring (CLAUDE.md §10.5).
- The agentic-engineering framing SPECIFY / HARNESS / VERIFY / CONTROL (proposal §4), introduced here and taken up again in §3 and §6.
- Sources: proposal v4, CLAUDE.md §1, §10.5.

## 2. Background and related work (SS)

- Positions the work against CALYPSO explicitly (11.5 done-when).
- LLM game masters and interactive fiction; grounding by state injection and by tool use; self-check prompting.
- Evaluation of narrative quality and factual consistency; Krippendorff's alpha.
- SRD 5.1 as the rules base, and what was simplified.

## 3. System design (CI)

- Architecture, with the loop-corrected diagram from 11.8: **two model calls per turn, drawn as a loop** (CLAUDE.md §7).
- Rules engine (§4), state schema (§5), tool contract with its seven tools and rejection codes (§6), the turn loop and failure pipeline with the retry budget of 2 (§7, §7.1), context assembly and the rolling summary (§8).
- A subsection mapping SPECIFY / HARNESS / VERIFY / CONTROL to the four design decisions: tool contract, rules engine, the four-condition ladder, the retry budget (11.2 done-when; CLAUDE.md §1.2).
- Model choice and hardware (`docs/model_selection.md`, `docs/hardware.md`).
- Detailed enough that the system can be rebuilt from the text alone (11.2 done-when).
- Sources: CLAUDE.md §4 to §8, `docs/tool_contract.md`, `docs/state_schema.md`, `docs/prompt_templates.md`.

## 4. Experimental method (CI)

- The four conditions and invariant 7: they differ only in prompt template and tool wiring (CLAUDE.md §9). The replayed ground truth for A to C.
- Scenarios: 12 short and 4 long sessions (`docs/scenario_format.md`). Grid: 16 × 4 × seeds 2001 to 2003, 192 runs, 6,420 records (`docs/main_run.md`, `docs/long_run.md`, `docs/run_integrity.md`).
- Metrics M1 to M6 (CLAUDE.md §10.4), with the evaluation slide's table of conditions × metrics × sample size (11.9).
- Annotation: the rubric v1.0 and its pilot (`docs/rubric.md`, `docs/rubric_pilot.md`); the automated checker and its validation (`docs/checker_validation.md`, `docs/automated_pass.md`); the M1 sample and procedure, **with the AI-draft disclosure sentence of `docs/m1_annotation.md` §3 verbatim**; M3 (`docs/intent_fidelity.md`, `docs/m3_annotation.md`, including its AI-draft disclosure); M5 (`docs/narrative_quality.md`).
- Analysis: run-level percentile bootstrap, 10,000 resamples, stratified by condition, using the shared `bootstrap()` (CLAUDE.md §10.5).

## 5. Results (SD)

Every claim traceable to a figure or table (11.3 done-when).

- 5.1 **RQ1 / H1:** M1 per condition per 100 narrated turns, overall and per category, with the D/A ratio and its interval (10.1). Figure: rate by condition (10.6).
- 5.2 **RQ2:** divergence against turn index per condition, carried by the long sessions (10.2). Figure: growth curves (10.6).
- 5.3 **Error taxonomy:** divergences by category and condition. Figure (10.6), with the catalogue of ten illustrative failures (10.7) and the side-by-side A-versus-D exhibit (10.8).
- 5.4 **M2:** invalid tool-call and recovery rates, condition D only (10.3, `docs/m2_tool_calls.md`).
- 5.5 **M3:** intent fidelity with its Wilson interval (`docs/m3_annotation.md`).
- 5.6 **M4 and M6:** rule violations in all conditions; latency mean and p95 against the 10 s target, and tokens per second (10.4).
- 5.7 **RQ3 / H2:** the D minus A difference per M5 item (9.8, 9.9).
- 5.8 **Agreement:** Krippendorff's alpha for M1 (9.6 overlap) and M5 (all 64), checked against 0.6 (10.5).

## 6. Discussion (SD)

- What the results say about each hypothesis, including any that fail.
- What the engine changes and what it does not: divergences that remain in D, and what kind.
- The SPECIFY / HARNESS / VERIFY / CONTROL framing revisited against the evidence.
- Observations from the sponsor sessions, as colour only, never as results (`docs/sponsor_feedback.md`).

## 7. Limitations and threats to validity (SD)

States the local-model and no-player-study limits plainly (11.4 done-when). At least:

- One local model of at most 9.7B parameters on one machine; results may not hold for larger or hosted models.
- No player study: quality is rated by the team, not by players.
- **M1:** first-annotator labels are an AI draft accepted by SD without edits, so the 9.6 alpha is agreement between the draft and one human. Input-named items scored inconsistently (about 32 turns). 259 borderline calls accepted as drafted (`docs/m1_annotation.md` §3).
- **M3:** single annotator, starting from an AI draft (`docs/m3_annotation.md`).
- **M5:** the second rater's 64 ratings took about 7 minutes and have little spread (`docs/m5_rating_sd.md` §3).
- The checker's low precision on `PHANTOM` and no automated check for `RESOURCE` (`docs/checker_validation.md`).
- The A to C ground truth is the replayed script state, not the state the narration implied.
- Deliberate rule simplifications: for example, an unconscious combatant cannot be attacked (CLAUDE.md §4.8).
- Team members were both the system's builders and its raters.

## 8. Future work and conclusion (SD)

- Future work: larger and hosted models, a player study, automated `RESOURCE` checks, second annotators for M3.
- Conclusion: the answers to RQ1 to RQ3 in one paragraph each.

## Appendices

- **A. Reproduction and release (SS, 11.11):** repository, licence (MIT) and `NOTICE` with the SRD 5.1 attribution and Llama 3.1 notice; the commands that reproduce a run and the analysis; data checksums (`experiments/main_grid.sha256`).
- **B. Rubric, rating form and protocols (CI, 11.2):** rubric v1.0, the M5 form, the M3 protocol, the prompt templates.

## Agreement

Agreed in the team chat on 2026-11-15, as reported by SD.

| Member | Sections owned | Agreed |
|---|---|---|
| SD | Abstract, 5, 6, 7, 8 | yes |
| CI | 3, 4, Appendix B | yes (team chat) |
| SS | 1, 2, Appendix A | yes (team chat) |
