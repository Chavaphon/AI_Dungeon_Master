# Task Checklist — AI Dungeon Master

Every task from the Work Breakdown Structure, ordered by due date. Dates are derived from each task's week, its dependencies, and the owner's daily capacity, so a task's date is the day its hours run out, not an arbitrary deadline.

`SS` Shayanis · `CI` Chavaphon · `SD` Sudakarn · `ALL` all three

Owner is who does the task. Several engine tasks sit with `SD` and `CI` so that no week is over capacity; stream accountability is unchanged from the proposal.

Nothing is scheduled during either examination blackout. Work resumes on 21 October and the project ends on 22 November; 2 December is the defence only.

**Proposal version:** v4 (September 24, 2026). The architecture follows the SPECIFY-HARNESS-VERIFY-CONTROL agentic engineering discipline; see CLAUDE.md §1.2 for the mapping. The final report (Week 7) and defence deck must carry this framing explicitly.

**Source:** integrated from `AI_Dungeon_Master_WBS_NEW.xlsx` (sheets WBS, Milestones, Effort, Deliverables, Risks). Where the workbook and CLAUDE.md disagree, CLAUDE.md wins and the task carries a note.

## Work packages

Every GitHub issue carries exactly one of these labels. The WBS ID prefix tells you the package: task `4.5` belongs to `wp-04-rules-engine`.

| WP | Title | Label | Tasks | Count | Hours |
|---|---|---|---|---|---|
| 1.0 | Project Setup and Governance | `wp-01-setup` | 1.1–1.7 | 7 | 7.5 |
| 2.0 | Specification Freeze [G1] | `wp-02-spec-freeze` | 2.1–2.7 | 7 | 15.5 |
| 3.0 | Local Model Selection and Benchmarking [G1] | `wp-03-model-benchmark` | 3.1–3.7 | 7 | 11.5 |
| 4.0 | Rules Engine | `wp-04-rules-engine` | 4.1–4.18 | 18 | 44.5 |
| 5.0 | Validator and State Write Path | `wp-05-validator` | 5.1–5.4 | 4 | 10.0 |
| 6.0 | Orchestration [M1 / G2] | `wp-06-orchestration` | 6.1–6.11 | 11 | 27.0 |
| 7.0 | Condition Harnesses | `wp-07-condition-harnesses` | 7.1–7.7 | 7 | 14.5 |
| 8.0 | Evaluation Instrument [G3] | `wp-08-eval-instrument` | 8.1–8.15, 8.3b | 16 | 44.5 |
| 9.0 | Experimental Execution [M2] | `wp-09-execution` | 9.1–9.10 | 10 | 37.0 |
| 10.0 | Analysis | `wp-10-analysis` | 10.1–10.8 | 8 | 21.0 |
| 11.0 | Reporting and Defence [M3] | `wp-11-reporting` | 11.1–11.12 | 12 | 36.5 |
| 12.0 | Recurring and Handover | `wp-12-recurring` | 12.1–12.9 | 9 | 9.0 |
| | **Total** | | | **116** | **278.5** |

---

## Week 1 — 28 Sep to 4 Oct

**Mon 28 Sep**

- [x] `1.1` **[CI]** Create repository, branch protection, issue and PR templates — *1.5h*
      - Done when: Repo exists, main is protected, one issue label per work package
- [x] `1.2` **[SS]** Python skeleton: pyproject, virtual env, formatter and linter config — *1.5h* · after 1.1
      - Done when: Empty test suite and linter both run clean
- [ ] `1.5` **[SD]** Shared storage for run artefacts and transcripts — *0.5h*
      - Done when: Folder structure created and path recorded in README
- [ ] `1.6` **[SD]** Weekly checkpoint slot and handover-note template — *0.5h*
      - Done when: Recurring slot booked; template committed
- [ ] `12.1` **[ALL]** Weekly checkpoint, Week 1 — *1h*
      - Done when: Notes in the decision log

**Tue 29 Sep**

- [ ] `1.4` **[SS]** Module boundary and coding convention note — *1h*
      - Done when: One page in /docs, agreed by all three members

**Wed 30 Sep**

- [ ] `1.3` **[CI]** CI pipeline running tests and lint on every push — *2h* · after 1.2
      - Done when: Green check on main; failing test blocks merge
      - Note: Branch protection on `main` (from 1.1) has no required status checks yet. Once the CI workflow has run at least once, add its check name as a required status check, or a failing test will not block merge.
- [ ] `1.7` **[CI]** Decision log created (dated entries, one file) — *0.5h*
      - Done when: File exists with its first entry

**Thu 1 Oct**

- [ ] `2.1` **[SS]** State schema v0.9 written as JSON Schema — *4h* · after 1.4
      - Done when: Validates three hand-written example state files
- [ ] `2.5` **[SD]** Scenario definition file format — *2.5h* · after 2.1
      - Done when: Holds entities, starting state, fixed player inputs and DCs

**Fri 2 Oct**

- [ ] `2.2` **[SS]** Identifier conventions and scenario-scoped namespace — *1h* · after 2.1
      - Done when: Written rule; id collisions across scenarios impossible
- [ ] `2.3` **[CI]** Tool contract v0.9: seven tools, typed parameters, return shapes, rejection codes — *4h* · after 2.1
      - Done when: Every tool has parameters, return shape and enumerated rejection codes (SPECIFY artefact — see CLAUDE.md §6)
- [ ] `2.4` **[SD]** Audit-log turn-record format — *2h* · after 2.3
      - Done when: Example records for one valid turn and one rejected turn
- [ ] `8.1` **[SD]** Divergence rubric v0.5: four categories with worked examples — *3h*
      - Done when: Two positive and two negative examples per category

**Sat 3 Oct**

- [ ] `2.6` **[ALL]** Joint review and freeze of 2.1 to 2.5 — *1.5h* · after 2.1,2.2,2.3,2.4,2.5
      - Done when: All three sign off in the decision log
- [ ] `2.7` **[SS]** Tag specifications v1.0 in the repository — *0.5h* · after 2.6
      - Done when: Tag exists; later changes need a decision-log entry
- [ ] `3.1` **[CI]** Install Ollama; confirm GPU and available VRAM — *1h*
      - Done when: Model serves a test prompt; VRAM figure recorded
- [ ] `3.2` **[CI]** Shortlist three candidate instruct models (7B to 14B) — *1h* · after 3.1
      - Done when: Three named candidates with licences checked

> **GATE G1 — 4 October.** Specifications frozen and tagged. Do not start the engine before this.
> - *Must be true:* State schema, tool contract, audit-log format, scenario format, model version, quantisation and K all frozen and tagged.
> - *If not:* Do not start the engine. A day spent here is cheaper than a week of rework in Week 4.

## Week 2 — 5 Oct to 11 Oct

**Mon 5 Oct**

- [ ] `12.2` **[ALL]** Weekly checkpoint, Week 2 — *1h*
      - Done when: Notes in the decision log

**Tue 6 Oct**

- [ ] `3.3` **[CI]** Build a 20-prompt tool-calling micro-benchmark against the frozen schema — *3h* · after 2.3
      - Done when: Runs unattended and scores schema validity automatically
- [ ] `4.1` **[SS]** Core types and state load/save — *3h* · after 2.7
      - Done when: Round-trips a state file without loss
- [ ] `4.3` **[SD]** Ability scores, modifiers, proficiency bonus, armour class — *2h* · after 4.1
      - Done when: Boundary scores covered by unit tests
- [ ] `4.9` **[SD]** Skill checks: Strength, Perception, Stealth against a DC — *2h* · after 4.3
      - Done when: Each tested at, above and below the DC

**Wed 7 Oct**

- [ ] `3.4` **[CI]** Run the benchmark; record schema-valid rate, latency and tokens per second — *3h* · after 3.2,3.3
      - Done when: Comparison table for all three candidates
- [ ] `4.2` **[SS]** Seeded RNG service and dice parser (XdY+Z) — *2h* · after 4.1
      - Done when: Identical seed reproduces an identical sequence
- [ ] `8.2` **[SD]** Borderline conventions, including hit-point band thresholds — *2h* · after 8.1
      - Done when: 'Badly hurt at 14 of 20' settled by a written rule

**Thu 8 Oct**

- [ ] `3.5` **[CI]** Measure usable context window and choose K, the number of verbatim turns — *2h* · after 3.4
      - Done when: K chosen against measured evidence, not guessed
- [ ] `4.4` **[SS]** Initiative, turn order, tie-break rule, round advance — *3h* · after 4.2
      - Done when: Deterministic order from a seed; tie-break documented

**Fri 9 Oct**

- [ ] `3.6` **[CI]** Freeze model, version, quantisation and K — *0.5h* · after 3.5
      - Done when: Decision-log entry; values live in a config file
- [ ] `3.7` **[CI]** Decide whether grammar-constrained decoding is required — *1h* · after 3.4
      - Done when: Decision recorded with the benchmark number behind it
- [ ] `8.3` **[SD]** Author scenarios 1 to 3 with fixed player inputs — *3h* · after 2.5
      - Done when: Three scenarios complete and loadable

**Sat 10 Oct**

- [ ] `4.5` **[SS]** Attack resolution: to-hit, critical, damage, hit-point reduction — *3h* · after 4.3,4.4
      - Done when: Critical doubles dice and not the modifier; tested
- [ ] `4.7` **[CI]** Advantage and disadvantage, including mutual cancellation — *2h* · after 4.5
      - Done when: Both-apply case has an explicit test

> **GATE G1b — 11 October.** Model, quantisation and K frozen. Handover note written.

**Sun 11 Oct**

- [ ] `4.8` **[SS]** Zero hit points: unconscious state, stabilisation, no death saves — *2h* · after 4.5
      - Done when: Hit points never negative; state legal at every step
- [ ] `12.8` **[CI]** Handover note before the first blackout — *1h*
      - Done when: Written and committed before 12 October

## Monday 12 October

> **BLACKOUT — 12 October.** Examination period begins. No project work until 21 October.
> - *Must be true:* Handover note committed. Engine core and 40 unit tests done.
> - *If not:* Write the handover note anyway. Resuming from memory after nine days is the failure mode.

## Week 3 — 21 Oct to 25 Oct

**Wed 21 Oct**

- [ ] `6.1` **[CI]** Ollama client wrapper with timeouts and retries — *2h* · after 3.6
      - Done when: A stalled generation does not hang the run
- [ ] `12.3` **[ALL]** Weekly checkpoint, Week 3 — *1h*
      - Done when: Notes in the decision log

**Thu 22 Oct**

- [ ] `8.4` **[SD]** Author scenarios 7 to 12 — *4h* · after 8.3
      - Done when: All twelve complete and reviewed by the engine owner

**Fri 23 Oct**

- [ ] `4.10` **[SS]** Unit tests for 4.1 to 4.9 (40 cases) — *5h* · after 4.9
      - Done when: 40 cases passing in CI
- [ ] `6.3` **[CI]** Tool-call parsing, including malformed-JSON recovery — *3h* · after 6.1
      - Done when: Parser tested against 20 recorded bad outputs

**Sat 24 Oct**

- [ ] `4.11` **[SS]** Fire Bolt (cantrip, ranged spell attack, 1d10) — *1.5h* · after 4.5
      - Done when: Shares the attack code path; damage applied correctly
- [ ] `8.5` **[SD]** Author four 50-turn long-session scripts — *4h* · after 8.4
      - Done when: Scripts exercise inventory, quests and relationships

**Sun 25 Oct**

- [ ] `4.12` **[SS]** Cure Wounds with hit-point cap — *2h* · after 4.8
      - Done when: Cannot exceed maximum hit points; tested at the cap
- [ ] `4.13` **[SS]** Spell slot tracking and rest policy — *1.5h* · after 4.12
      - Done when: Slot spent on cast; cast refused at zero slots

## Week 4 — 26 Oct to 1 Nov

**Mon 26 Oct**

- [ ] `4.6` **[SS]** Dodge: disadvantage flag and its expiry — *2h* · after 4.5
      - Done when: Flag clears at the start of the dodger's next turn
- [ ] `4.14` **[SD]** Inventory add and remove with quantity rules — *2h* · after 4.1
      - Done when: Negative quantities unreachable
- [ ] `12.4` **[ALL]** Weekly checkpoint, Week 4 — *1h*
      - Done when: Notes in the decision log

**Tue 27 Oct**

- [ ] `4.15` **[SD]** NPC relationship ladder: one step per event, justification required — *2.5h* · after 4.1
      - Done when: Two-step change rejected; missing justification rejected
- [ ] `6.2` **[CI]** Prompt assembly: system prompt, tool definitions, state, summary, last K turns — *3h* · after 3.5,2.3
      - Done when: Worst-case assembled prompt still fits the context window

**Wed 28 Oct**

- [ ] `4.16` **[SD]** Quest log transitions — *2.5h* · after 4.1
      - Done when: Illegal transitions rejected with a named code
- [ ] `4.17` **[SS]** Complete the 60-case rule suite to 100 per cent pass — *4h* · after 4.10,4.16
      - Done when: Objective 1 success criterion evidenced

**Thu 29 Oct**

- [ ] `5.1` **[SS]** Schema validation for every tool call — *2.5h* · after 2.3,4.1
      - Done when: Malformed call rejected naming field and expected type

**Fri 30 Oct**

- [ ] `5.2` **[SS]** State precondition checks and rejection codes — *3h* · after 5.1
      - Done when: Every rejection code in 2.3 reachable by a test
- [ ] `6.4` **[CI]** Failure pipeline: five modes, structured errors, retry budget of two — *4h* · after 6.3,5.2
      - Done when: Each mode in the CLAUDE.md §7.1 table has a test (CONTROL artefact — budget exhaustion must route to a logged turn-failure, never an uncontrolled loop)
      - Note: WBS and proposal §8.3 say *four* modes; CLAUDE.md §7.1 lists five (adds unparseable output). CLAUDE.md wins — raise at the Week 1 checkpoint.
- [ ] `6.5` **[CI]** Exhausted-budget fallback and turn-failure logging — *1.5h* · after 6.4
      - Done when: Turn does not advance; failure is counted
- [ ] `6.6` **[CI]** Narration call conditioned on the validated outcome — *2.5h* · after 6.4
      - Done when: Model receives the numbers and describes them
- [ ] `6.9` **[SD]** Output safety filter and filtered-turn logging — *2h* · after 6.6
      - Done when: Filtered turns counted, never silently dropped
- [ ] `8.3b` **[SD]** Author scenarios 4 to 6 — *3h* · after 8.3
      - Done when: Six scenarios complete and reviewed

**Sat 31 Oct**

- [ ] `5.3` **[SS]** State diff writer and audit-log append — *2.5h* · after 2.4,5.2
      - Done when: Every write produces a diff record
- [ ] `6.7` **[CI]** Rolling summary regenerated every K turns — *2.5h* · after 6.2
      - Done when: Summary length bounded; regeneration logged
- [ ] `8.14` **[SD]** Intent-fidelity annotation protocol (M3) — *1.5h* · after 8.1
      - Done when: Sampling rule and decision rule written down

> **MILESTONE 1 / GATE G2 — 1 November.** Playable 50-turn session. TRIGGER: if not met, drop Condition C today.
> - *Must be true:* Ten smoke runs attempted, at least nine complete without unrecoverable failure. Objective 2 criterion met.
> - *If not:* Drop Condition C and run a three-condition ladder (A, B, D). Decide on the day, do not defer.

**Sun 1 Nov**

- [ ] `5.4` **[SS]** Post-write invariant assertion — *2h* · after 5.3
      - Done when: An illegal state raises rather than persists
- [ ] `6.10` **[CI]** Text command-line client — *2h* · after 6.6
      - Done when: A person can play a session end to end
- [ ] `6.11` **[CI]** Ten 50-turn smoke runs; at least nine complete — *3h* · after 6.10
      - Done when: MILESTONE 1 evidence and Objective 2 criterion

## Week 5 — 2 Nov to 8 Nov

**Mon 2 Nov**

- [ ] `6.8` **[CI]** Latency and throughput instrumentation (M6) — *1.5h* · after 6.1
      - Done when: Seconds per turn and tokens per second in the log
- [ ] `12.5` **[ALL]** Weekly checkpoint, Week 5 — *1h*
      - Done when: Notes in the decision log

**Tue 3 Nov**

- [ ] `4.18` **[SS]** Replay harness: seed plus scenario reproduces a session — *2.5h* · after 4.2
      - Done when: Two runs of one seed are byte-identical
- [ ] `7.1` **[SS]** Condition A harness: no state given to the model — *1.5h* · after 6.10
      - Done when: Runs a scenario end to end
- [ ] `7.4` **[CI]** Condition D wired into the common runner — *1h* · after 6.11
      - Done when: Same entry point as A to C

**Wed 4 Nov**

- [ ] `7.2` **[SS]** Condition B harness: state in prompt, no rules engine — *2h* · after 7.1
      - Done when: State injected identically to Condition D

**Thu 5 Nov**

- [ ] `7.3` **[SS]** Condition C harness: state plus self-check instruction — *2h* · after 7.2
      - Done when: Differs from B only in the instruction text
- [ ] `7.5` **[CI]** Freeze the four prompt templates verbatim — *2h* · after 7.3,7.4
      - Done when: Templates committed; differences documented line by line
- [ ] `7.6` **[CI]** Batch runner: scenario x condition x seed, resumable, unattended — *4h* · after 7.5
      - Done when: Survives interruption and resumes without duplicating work

**Fri 6 Nov**

- [ ] `7.7` **[CI]** Dry run on two scenarios across four conditions — *2h* · after 7.6
      - Done when: Output validates against the audit-log schema

**Sat 7 Nov**

- [ ] `8.6` **[SS]** Automated checker: entity-mention extraction — *4h* · after 2.4
      - Done when: Flags items and NPCs absent from state
- [ ] `8.7` **[SD]** Automated checker: numeric and hit-point band comparison — *3h* · after 8.2,8.6
      - Done when: Implements the 8.2 rule exactly
- [ ] `8.8` **[SD]** Automated checker: relationship-stance contradiction — *2.5h* · after 8.6
      - Done when: Detects hostile narration of a recorded-neutral NPC
- [ ] `8.9` **[SD]** Rule-violation checker (M4) — *2h* · after 8.6
      - Done when: Runs across all four conditions
- [ ] `8.10` **[SD]** Validate the checker against 30 hand-labelled turns — *3h* · after 8.9
      - Done when: Precision and recall recorded; blind spots listed
- [ ] `8.11` **[SD]** Rubric pilot on two scenarios with two annotators — *3h* · after 8.10,7.7
      - Done when: Krippendorff alpha computed on the pilot

> **GATE G3 — 8 November.** Rubric v1.0 frozen and hard feature cutoff.
> - *Must be true:* Rubric v1.0 tagged, pilot agreement computed, all four harnesses dry-run, no further features accepted.
> - *If not:* Freeze the rubric regardless and note the weaker pilot. An unfrozen rubric invalidates the annotation.

**Sun 8 Nov**

- [ ] `8.12` **[ALL]** Resolve disagreements and freeze rubric v1.0 — *2h* · after 8.11
      - Done when: GATE G3; rubric tagged in the repository
- [ ] `8.13` **[SD]** Narrative-quality rating form plus engagement item (M5) — *1.5h* · after 8.1
      - Done when: Five-point scales, blind presentation
- [ ] `8.15` **[CI]** Annotation tool: blind and condition-shuffled — *3h* · after 8.13
      - Done when: Annotator cannot infer condition from the interface

## Week 6 — 9 Nov to 15 Nov

**Mon 9 Nov**

- [ ] `12.6` **[ALL]** Weekly checkpoint, Week 6 — *1h*
      - Done when: Notes in the decision log

**Tue 10 Nov**

- [ ] `9.1` **[CI]** Main run: 12 scenarios x 4 conditions — *3h* · after 7.7,8.12
      - Done when: All runs complete with seeds recorded

**Wed 11 Nov**

- [ ] `9.2` **[CI]** Long sessions: 4 x 50 turns x 4 conditions — *3h* · after 9.1
      - Done when: Complete, with turn index preserved for RQ2
- [ ] `9.3` **[SS]** Run integrity check: completeness, crashes, seeds — *2h* · after 9.2
      - Done when: Any gap re-run before annotation begins
- [ ] `9.4` **[SD]** Automated checker pass over every transcript — *2h* · after 9.3
      - Done when: Automated M1 subset and M4 produced

**Fri 13 Nov**

- [ ] `9.5` **[SD]** Human annotation of the M1 sample, first annotator — *8h* · after 9.4
      - Done when: Sample annotated under rubric v1.0
- [ ] `9.6` **[SS]** Second-annotator pass on the 20 per cent overlap — *5h* · after 9.5
      - Done when: Agreement is computable
- [ ] `9.7` **[CI]** Intent-fidelity annotation on the 15 per cent sample (M3) — *4h* · after 9.4
      - Done when: Sample scored under the 8.14 protocol (critic layer — active search for intent failures invisible to the automated checker)
- [ ] `9.8` **[SS]** Narrative-quality rating, first rater — *4h* · after 9.3
      - Done when: Rater blind to condition

**Sat 14 Nov**

- [ ] `9.10` **[CI]** Re-run any failed or incomplete batches — *2h* · after 9.3
      - Done when: Dataset complete; MILESTONE 2 evidenced

> **MILESTONE 2 — 15 November.** Audit-log dataset complete.
> - *Must be true:* All 12 scenarios x 4 conditions plus long sessions run, integrity-checked, seeds recorded.
> - *If not:* Cut long sessions from 50 to 30 turns and re-run only those. Do not extend into Week 7.

**Sun 15 Nov**

- [ ] `9.9` **[SD]** Narrative-quality rating, second rater — *4h* · after 9.3
      - Done when: Rater blind to condition
- [ ] `11.1` **[SD]** Report outline agreed with section owners — *1h* · after 9.4
      - Done when: Section list with a named owner each
- [ ] `11.5` **[SS]** Write introduction and background — *3h* · after 11.1
      - Done when: Positions the work against CALYPSO explicitly; introduces the agentic-engineering framing (proposal Section 4) that recurs in Section 8

## Week 7 — 16 Nov to 22 Nov

**Mon 16 Nov**

- [ ] `10.1` **[SD]** Divergence rate per condition with confidence intervals (M1) — *3h* · after 9.6
      - Done when: Answers RQ1
- [ ] `10.3` **[CI]** Invalid tool-call and recovery rates (M2) — *2h* · after 9.10
      - Done when: Condition D only
- [ ] `12.7` **[ALL]** Weekly checkpoint, Week 7 — *1h*
      - Done when: Notes in the decision log

**Tue 17 Nov**

- [ ] `10.2` **[SD]** Divergence growth against turn index — *3h* · after 10.1
      - Done when: Answers RQ2
- [ ] `10.4` **[CI]** Rule-violation and throughput summaries (M4, M6) — *2h* · after 9.4
      - Done when: Reported for all conditions
- [ ] `10.6` **[SS]** Figures: rate by condition, growth curves, error taxonomy — *4h* · after 10.2
      - Done when: Three finished figures

**Wed 18 Nov**

- [ ] `10.5` **[SD]** Inter-rater agreement (Krippendorff alpha) — *2h* · after 9.6,9.9
      - Done when: Objective 3 criterion checked against the 0.6 threshold
- [ ] `10.7` **[SS]** Qualitative catalogue of ten illustrative failures — *3h* · after 9.6
      - Done when: Each with transcript excerpt and state snapshot
- [ ] `10.8` **[SS]** Side-by-side Condition A versus D transcript exhibit — *2h* · after 10.7
      - Done when: The single strongest defence slide
- [ ] `11.2` **[CI]** Write methods and system description — *5h* · after 11.1
      - Done when: System reproducible from the text alone; system architecture explained through the SPECIFY / HARNESS / VERIFY / CONTROL agentic-engineering framing (proposal Section 8.0), including a subsection mapping the principles to the four design decisions (tool contract, rules engine, 4-condition ladder, retry budget)

**Thu 19 Nov**

- [ ] `11.3` **[SD]** Write results — *5h* · after 10.6
      - Done when: Every claim traceable to a figure or table

> **CUT-OFF — 20 November.** Analysis cut-off. TRIGGER: write up against partial results rather than slipping.
> - *Must be true:* All annotation complete and figures produced.
> - *If not:* Write the report against partial results with the gap stated. Nothing can be fixed after 22 November.

**Fri 20 Nov**

- [ ] `11.4` **[SD]** Write discussion, limitations and future work — *3h* · after 11.3
      - Done when: States the local-model and no-player-study limits plainly
- [ ] `11.6` **[ALL]** Internal review pass across all sections — *3h* · after 11.2,11.4,11.5
      - Done when: Each section read by someone who did not write it
- [ ] `11.7` **[CI]** Defence deck built in talk order, not proposal order — *5h* · after 11.3
      - Done when: Problem, difficulty, design (framed via SPECIFY / HARNESS / VERIFY / CONTROL), build, evaluation, risks
- [ ] `11.8` **[SS]** Loop-corrected architecture diagram — *2h* · after 11.7
      - Done when: Shows two model calls per turn
- [ ] `11.9` **[CI]** Evaluation slide: conditions x metrics x sample size — *1.5h* · after 11.7
      - Done when: Design readable in ten seconds
- [ ] `11.10` **[ALL]** Two timed rehearsals with anticipated questions — *3h* · after 11.8,11.9
      - Done when: Within time; answers prepared for the top ten questions

**Sat 21 Nov**

- [ ] `11.11` **[SS]** Code and data release with SRD 5.1 attribution — *3h* · after 11.3
      - Done when: Licence file and attribution present
- [ ] `11.12` **[SD]** Assemble and check the final submission pack — *2h* · after 11.10,11.11
      - Done when: MILESTONE 3; nothing carried into December

> **MILESTONE 3 — 22 November.** Submission pack complete. Nothing can be fixed after today.
> - *Must be true:* Report finished, deck rehearsed twice, code and data released. Nothing outstanding.
> - *If not:* There is no recovery window. Whatever is unfinished on this date is unfinished at the defence.

**Sun 22 Nov**

- [ ] `12.9` **[CI]** Handover note before the second blackout — *1h*
      - Done when: Written and committed before 23 November

## Monday 23 November

> **BLACKOUT — 23 November.** Examination period. No project work until 2 December.

## Wednesday 2 December

> **DEFENCE — 2 December.** Final report submitted and project defended.

---

## Summary

- 116 tasks (the workbook's "of 128" counter also counts its 12 work-package header rows)
- 278.5 task-hours; 311.5 person-hours once the 16h of joint tasks are counted for each member
- 7 working weeks, 28 September to 22 November 2026
- 3 milestones, 3 gates, 2 blackouts, 1 defence

## Weekly totals

| Week | Dates | Tasks | Hours |
|---|---|---|---|
| W1 | 28 Sep – 4 Oct | 18 | 29.0 |
| W2 | 5 Oct – 11 Oct | 17 | 35.5 |
| W3 | 21 Oct – 25 Oct | 9 | 24.0 |
| W4 | 26 Oct – 1 Nov | 20 | 49.0 |
| W5 | 2 Nov – 8 Nov | 19 | 43.5 |
| W6 | 9 Nov – 15 Nov | 13 | 42.0 |
| W7 | 16 Nov – 22 Nov | 20 | 55.5 |

## Effort by person and week (hours)

Load pulled from the WBS sheet; capacity is the workbook's input. Negative variance is overload.

| Person | W1 | W2 | W3 | W4 | W5 | W6 | W7 | Total |
|---|---|---|---|---|---|---|---|---|
| Shayanis (SS) | 10.5 | 14 | 11 | 17 | 15 | 15 | 21 | 103.5 |
| Chavaphon (CI) | 12.5 | 13.5 | 6 | 19.5 | 16.5 | 13 | 23.5 | 104.5 |
| Sudakarn (SD) | 11 | 10 | 9 | 14.5 | 18 | 16 | 25 | 103.5 |
| *Capacity per person* | 12 | 14 | 10 | 18 | 16 | 16 | 24 | 110 |
| Variance SS | 1.5 | 0 | **−1** | 1 | 1 | 1 | 3 | 6.5 |
| Variance CI | **−0.5** | 0.5 | 4 | **−1.5** | **−0.5** | 3 | 0.5 | 5.5 |
| Variance SD | 1 | 4 | 1 | 3.5 | **−2** | 0 | **−1** | 6.5 |

311.5 person-hours against 330 capacity: about 6 per cent headroom. Any task that doubles in size costs someone a weekend. Revise estimates after Week 1 with real data.

## Deliverables register

| ID | Deliverable | Owner | Due | From WBS | Acceptance |
|---|---|---|---|---|---|
| D1 | Specifications v1.0 (schema, tools, audit log, scenarios) | SS | 4 Oct | 2.7 | Tagged in the repository and referenced by the decision log |
| D2 | Model selection report and frozen config | CI | 4 Oct | 3.6 | Benchmark table for three candidates plus the chosen K |
| D3 | Rules engine with 60-case test suite | SS | 25 Oct | 4.17 | 100 per cent pass in CI; Objective 1 evidenced |
| D4 | Scenario suite: 12 scenarios and 4 long sessions | SD | 25 Oct | 8.5 | All load and run without manual intervention |
| D5 | Working hybrid system (Condition D) | CI | 1 Nov | 6.11 | Nine of ten 50-turn runs complete; Objective 2 evidenced |
| D6 | Four condition harnesses and batch runner | CI | 8 Nov | 7.7 | Dry run validates against the audit-log schema |
| D7 | Divergence rubric v1.0 and automated checker | SD | 8 Nov | 8.12 | Pilot agreement computed; checker validated on 30 turns |
| D8 | Complete audit-log dataset | CI | 15 Nov | 9.10 | All runs present, seeds recorded, integrity checked |
| D9 | Annotated corpus and agreement statistics | SD | 20 Nov | 10.5 | Krippendorff alpha at or above 0.6, or the shortfall explained |
| D10 | Final report | SD | 22 Nov | 11.6 | Reviewed by someone other than each section's author |
| D11 | Defence deck, rehearsed twice | CI | 22 Nov | 11.10 | Within time; top ten questions prepared |
| D12 | Code and data release with SRD 5.1 attribution | SS | 22 Nov | 11.11 | Public repository, licence file, replay instructions |

Note: the workbook dates D2 at 4 October (G1) while tasks 3.3–3.6 run in Week 2 and G1b is 11 October. Treat 11 October as the real D2 date.

## Risk register

Carried from proposal Section 13. Check triggers at each weekly checkpoint.

| ID | Risk | L | I | Owner | Mitigation and fallback | Trigger |
|---|---|---|---|---|---|---|
| R1 | Local model calls tools unreliably | H | H | CI | Benchmark in Week 1 before the engine is finished; few-shot examples; one tool call per turn; grammar-constrained decoding. Reported as M2 rather than hidden. | Schema-valid rate below 80 per cent at task 3.4 |
| R2 | Milestone 1 slips | M | H | CI | Orchestration benchmarked Week 1, built Week 4 on a tested engine. Fallback: drop Condition C, run A, B, D. | No 50-turn session on 1 November |
| R3 | Context window too small for state plus history | M | H | CI | K benchmarked and frozen in Week 1. Fallback: reduce K, then inject only the fields a turn can touch, identically across conditions. | Worst-case prompt exceeds context at task 6.2 |
| R4 | Inference too slow for the Week 6 batches | M | M | CI | Throughput measured as M6 from Week 4; runs are unattended batches. Fallback: smaller quantisation, then 50-turn sessions cut to 30. | Projected batch time above 40 hours |
| R5 | Annotation workload exceeds available time | H | H | SD | Automate the checkable subset; rubric drafted Week 1 and piloted Week 5; annotation starts on completed runs in Week 6. Fallback: intent sample 15 to 10 per cent, overlap 20 to 15 per cent. | Less than half the M1 sample done by 15 November |
| R6 | Work unfinished before the second blackout | M | H | SD | Week 7 ends with a complete pack. Nothing scheduled into the blackout. Handover notes before each one. | Analysis incomplete on 20 November |
| R7 | Scope creep back toward full 5e | M | H | SS | Action set and spell list frozen Week 1; any addition requires a removal. Hard feature cutoff end of Week 5. | Any new mechanic proposed after 8 November |
| R8 | Key member unavailable | L | H | ALL | Named reviewer per stream; shared repository with documented interfaces from Week 1. | Absence longer than three days |

---

Tick items here or in the WBS workbook, not both. The workbook recalculates effort from its Status column; this file is the flat, date-ordered view for day-to-day use.
