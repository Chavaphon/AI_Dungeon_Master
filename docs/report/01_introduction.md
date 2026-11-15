# 1. Introduction

<!-- WBS 11.5 · Owner: SS · Reviewer (11.6): SD · Outline: docs/report_outline.md §1 · Draft 2026-11-15 -->

## 1.1 The problem

In a tabletop role-playing game such as Dungeons & Dragons, the Dungeon Master (DM) does two jobs at once. They narrate a world and voice its characters, turn after turn, in prose the players want to keep hearing. They also keep that world consistent: who is standing, how badly they are hurt, what is in each backpack, which quests are open and how each non-player character feels about the party. Large language models are good at the first job and unreliable at the second. Over a long session a language-model narrator introduces items and characters that were never established, contradicts recorded hit points and inventory, and resolves checks inconsistently (Ji et al., 2023).

These failures are widely noticed and rarely measured. Most systems that put a language model at the table either keep a human DM in charge of the rules (Zhu, Martin, et al., 2023) or report the quality of the prose, not its agreement with the game. As a result there is little evidence on how much of the drift goes away when the model is grounded more strongly, and which kind of grounding does the work.

## 1.2 The design rule

This project builds an autonomous DM for a deliberately small D&D-style game. A local, open-weight language model writes the narration and dialogue, and a deterministic Python rules engine owns all game state and resolves every mechanic. One rule governs the whole design:

> The language model never writes to game state. It may only propose tool calls. The engine validates them, executes them, and returns the outcome. The model then narrates that outcome.

Every player turn is therefore a loop with two model calls. The first proposes one of seven typed tool calls: attack, cast a spell, dodge, make a skill check, or change an inventory, a relationship or a quest. The engine checks it against a fixed contract, rejects it with a structured reason and a list of valid options if it is illegal, and allows two retries. The second call narrates only the facts the engine returned. Section 3 describes the system in full.

The rule does not remove hallucination. It moves it. Even when the state is exactly right, the narration written from it can still be wrong: it can mention a lantern the player never picked up, describe a character at 14 of 20 hit points as being on the brink of death, or speak to a recorded-neutral innkeeper as if they were hostile. This residual gap between what the engine knows and what the narration says is the thing this project measures. We call it **narration-state divergence**.

## 1.3 Contribution

The contribution is the measurement, not the system. We ask how far the narration drifts from the state under four levels of grounding, each adding one thing to the one before:

| Condition | State in the prompt | Self-check instruction | Rules engine and tools |
|---|---|---|---|
| A | no | no | no |
| B | yes | no | no |
| C | yes | yes | no |
| D | yes | no | yes |

The conditions differ only in the prompt template and in whether the tools are wired. The engine, scenarios, seeds, model and context strategy are the same in all four, so a difference between conditions can be traced to the grounding alone. Comparing only A and D would not show where the benefit comes from; the ladder does. It also guards against a circular result: a system that keeps its state in a validated file will trivially beat one with no state store on state accuracy, so the question is not whether D wins but how much each step contributes and what it costs.

The project delivers three things:

1. **A measured answer.** Divergence rates for each condition over a fixed grid of 16 scripted scenarios (12 short, 4 long sessions of 50 turns) × 4 conditions × 3 seeds: 192 runs and 6,420 logged turn records, every one reproducible from its seed, scenario and condition.
2. **A reusable instrument.** A four-category divergence rubric (phantom entity, state contradiction, resource error, relationship contradiction), a partly automated checker validated against hand-labelled turns, and an audit log in which every state change is traceable to a validated tool call.
3. **Evidence on the cost of grounding.** Blind ratings of narrative quality across the four conditions, the tool-call failure and recovery rates of a small local model, and the latency of the two-call loop on ordinary hardware.

## 1.4 Research questions and hypotheses

The primary question is how much each additional layer of grounding — state supplied in the prompt, model self-checking, and validated tool calling — reduces narration-state divergence, and what that grounding costs in narrative quality and latency. It breaks into three sub-questions:

- **RQ1.** What is the narration-state divergence rate under each of the four conditions, and where along the ladder does the benefit level off?
- **RQ2.** Does divergence grow with session length, and does it grow at different rates under different conditions?
- **RQ3.** Does stricter grounding reduce narrative quality as judged by raters blind to condition, and if so, in what ways?

The hypotheses, the latency target and the analysis were fixed on 1 November 2026, before any main run was scored:

| ID | Statement | Test |
|---|---|---|
| H1 | Condition D has at least 50% fewer confirmed divergences per 100 turns than condition A | The D/A ratio of the divergence rate is at most 0.5 and its 95% interval excludes 1 |
| H2 | Condition D's narrative quality is no worse than condition A's | The 95% interval of the D minus A difference in mean rating, reported per item |
| — | Condition D answers within 10 seconds per turn at the 95th percentile | Turn latency on the main grid |

Every interval is a percentile bootstrap that resamples whole runs, with 10,000 resamples stratified by condition. RQ2 is answered by the slope of divergences against turn number in each condition, which the long sessions carry, and RQ3 by H2's difference for each rating item.

## 1.5 An agentic-engineering framing

The design follows a discipline for building systems around autonomous models, introduced in the course lecture on agentic engineering (17 September 2026) and adopted in the project proposal (v4, §4). As a model gains the ability to act, the engineer's role shifts from writing every instruction to four responsibilities, summed up as *the agent gains autonomy; the engineer keeps responsibility*:

- **SPECIFY** — define the behaviour explicitly, testably and completely: the goal, the edge cases and the acceptance criteria. Here: the tool contract, with its typed parameters and enumerated rejection codes; the failure pipeline, which names every way a tool call can go wrong and what happens next; and a 60-case rule suite and success criteria that can be checked without interpretation.
- **HARNESS** — control what the agent can reach and how its work gets done. Here the rules engine is the harness. The model may read the state but cannot write it; the seven tools are its whole capability; the validator enforces which calls are legal; and a fixed context-assembly procedure tells it exactly what it sees each turn.
- **VERIFY** — check in layers, from deterministic tests through an evaluation set and a critic to human review. Here: the rule suite and the automated checker at the base, the twelve-scenario suite and the four-condition ladder as the evaluation set, an intent-fidelity sample as the critic that looks for valid calls that do not match what the player asked, and human annotation at the top.
- **CONTROL** — least privilege and a spending limit. Here the model has read access and narration, nothing more. A retry budget of two caps the cost of recovering from a bad call, and running out of it ends the turn as a logged failure rather than an open-ended loop.

The framing is not decoration. Each of the four design decisions that the measurement depends on — the tool contract, the rules engine, the four-condition ladder and the retry budget — is one of these responsibilities discharged. Section 3 maps each principle onto the architecture (the proposal's Section 8), and Section 6 returns to the framing to ask what the evidence says about it.

## 1.6 Structure of the report

Section 2 places the work among language-model game masters, grounding by state and by tools, self-checking, and the evaluation of narrative consistency, and sets it explicitly against CALYPSO. Section 3 describes the system, and Section 4 the experiment: conditions, scenarios, metrics, annotation and analysis. Section 5 reports the results for RQ1 to RQ3 and the supporting metrics, Section 6 discusses them, Section 7 states the limitations plainly, and Section 8 gives future work and the conclusion. Appendix A explains how to reproduce every run and analysis, and Appendix B holds the rubric, rating form and protocols.
