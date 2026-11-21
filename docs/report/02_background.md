# 2. Background and related work

<!-- WBS 11.5 · Owner: SS · Reviewer (11.6): SD · Outline: docs/report_outline.md §2 · Draft 2026-11-15 -->

This section places the project among four lines of work: language models at the D&D table, grounding a model in state and in tools, asking a model to check itself, and measuring whether generated text agrees with an authoritative source. It ends with the rules base and what was cut from it. Section 2.2 sets the project explicitly against CALYPSO, the closest prior system.

## 2.1 Language models at the table

Dungeons & Dragons has become a test bed for dialogue and narrative generation because it joins free-form language to a rule-governed world. Callison-Burch et al. (2022) framed D&D as a dialogue challenge for AI, built a corpus of play from an online community, and showed that adding game-state information helps a model predict and generate the next turn. FIREBALL (Zhu, Aggarwal, et al., 2023) went further: it recorded nearly 25,000 sessions of play on Discord together with the true game state tracked by the Avrae bot. It defined two tasks, *utterance to command* (turning what a player says into an executable game command) and *state to narration* (writing narration from a change in the state). Including the state improved generation on automatic metrics and human judgement, and models could learn to produce executable commands. Zhou et al. (2023) studied the DM's other role, guiding players toward goals, and trained a DM model with a theory-of-mind reward.

Our system's turn loop is close to FIREBALL's two tasks run in sequence and in real time. The first model call turns the player's input into a tool call, and the second narrates the engine's result. The difference lies in who owns the state. FIREBALL takes the state from a game bot that human players drive, and learns from it. Here the engine is the only writer of the state, and the model's command is a proposal that may be refused. That makes it possible to ask how often the narration disagrees with a state the model could not have changed.

## 2.2 CALYPSO: the model as the DM's assistant

CALYPSO (Zhu, Martin, et al., 2023) is the closest prior system, and the project is defined against it. CALYPSO is a set of language-model interfaces that support a human DM during play, deployed to real D&D groups on Discord. A formative study with DMs established where a model is useful at the table. CALYPSO then offered it in three roles: understanding an encounter from its statistics, focused brainstorming, and open-ended chat. DMs reported two useful kinds of output. One was high-fidelity text they could present to players directly, and the other was low-fidelity ideas they could build on while keeping their creative agency.

The two systems answer different questions:

| | CALYPSO | This project |
|---|---|---|
| Who is the DM | A human. The model assists | The system. No human DM in the loop |
| Who owns rules and state | The human DM, with a game bot | A deterministic engine, the only writer of state |
| What the model may do | Suggest text and ideas, which the DM accepts or ignores | Propose a tool call, which the engine validates or rejects, then narrate the result |
| Where correctness comes from | The DM's judgement | The engine's validation and the separation of narration from mechanics |
| What is evaluated | Usefulness to DMs, in a formative study and a field deployment | Narration-state divergence under four grounding conditions, measured on fixed scripts |
| Model | Hosted (GPT-3 and ChatGPT) | One local open-weight 8B model, frozen by digest |

CALYPSO's answer to the model's unreliability is to keep a person in charge. Its output is checked, edited or discarded by a DM who knows the rules and remembers the game. This is a sound choice for an assistant, but it leaves a question open: what happens when no such person is present? We take the opposite route. Mechanical correctness is moved out of the model entirely and into code. The engineering team, not a human at the table, then carries the responsibility CALYPSO leaves with the DM, and we measure how much of the problem that removes. The comparison is not a competition. CALYPSO shows that a model can help a human DM. This project asks how far an autonomous one can be trusted to describe its own world accurately.

## 2.3 Grounding in state and in tools

There are two broad ways to keep a model's output tied to facts it should respect.

**State in the context.** The simplest is to put the facts in the prompt. Conditions B and C do this: the full game state is injected as JSON every turn. Injection helps, but it is not a guarantee. Models use information unevenly across a long context and attend least to the middle (Liu et al., 2024), and a long session pushes the state, the recent turns and a rolling summary into one window. Our context assembly keeps the stable part of the prompt first and a fixed number of recent turns verbatim (K = 8, frozen after benchmarking). It shortens the window by dropping the oldest turns first, never from the middle.

**Tools and actions.** The second way is to let the model act through tools whose results come back as facts. ReAct (Yao et al., 2023) interleaves reasoning with actions in an environment, and Toolformer (Schick et al., 2023) teaches a model when to call an API. AgentBench (Liu et al., 2024) evaluates models as agents across interactive environments and finds a wide gap between hosted and open models. Wang et al. (2024) survey agents built this way. Condition D belongs to this family, but with a stricter boundary than most agent frameworks. The model has no write access to anything. Every proposed call is checked against a typed contract in a fixed order (shape, existence, argument values, encounter, actor, target, effect), and the narration call receives only the facts of the executed result.

Tool calls from a small model are often malformed. Grammar-constrained decoding (Willard & Louf, 2023) can force the output into a schema. We benchmarked the frozen model before deciding, and generate tool calls in plain prompt mode, with no grammar constraint and no JSON mode. Malformed output is handled by the retry budget and reported as a metric (M2), not suppressed.

## 2.4 Asking the model to check itself

Condition C asks whether a cheap prompt can stand in for the architecture: the same state as B, plus an instruction to check the narration against it and revise silently before answering. Self-refinement can improve outputs when a model critiques and revises its own work (Madaan et al., 2023). Chain-of-Verification reduces hallucination by having the model plan and answer separate verification questions before writing its final response (Dhuliawala et al., 2024). Without external feedback, however, models often fail to correct their own reasoning and sometimes make it worse (Huang et al., 2024). Our self-check is the weakest form of this idea. It is a single instruction with no separate verification call and no external signal, kept deliberately minimal so that C differs from B in one block of text only. If it closes much of the gap between B and D, the architecture is hard to justify. If it does not, the result says something about how far self-checking can go at this model size.

## 2.5 Hallucination and consistency with a source

Ji et al. (2023) separate *intrinsic* hallucination, which contradicts the source, from *extrinsic* hallucination, which cannot be verified from it. Narration-state divergence is a special case in which the source is a structured, authoritative game state, and both kinds appear. Our four categories cover them:
- **Phantom entities** are extrinsic: an item, character or place named in the narration that is neither in the state nor in the scenario.
- **State contradictions** are intrinsic: a hit-point band, a status, a quest state or an item's location that conflicts with the record.
- **Resource errors** are intrinsic: spending or gaining what the state does not show.
- **Relationship contradictions** are intrinsic: treating a non-player character against its recorded stance.

Because the source is a state file rather than prose, part of the check can be automated: entity names, hit-point bands, statuses, stances and rule breaks. The rest needs a human. Two choices make the measurement fair to the model:
- **Bands are given.** The engine hands the model the hit-point band ("wounded") with every result, so a band error in the narration is the model's mistake and not an inference problem.
- **Ambiguity counts as no divergence.** An unclear case is resolved in the model's favour, so the measured rate is a conservative count.

## 2.6 Rating narrative quality and agreement

Consistency is only half of what a DM is for. If grounding made the prose flat, a lower divergence rate would be a poor trade. The proposal planned a player study, using instruments such as the Player Experience Inventory (Abeele et al., 2020) or the Game Experience Questionnaire (IJsselsteijn et al., 2013), but it was withdrawn: the examination blackouts left no time to run one properly. Narrative quality is instead rated from transcripts, blind to condition, on coherence, vividness and tone, plus one engagement item ("would you want to keep reading?"). This is not player experience, and the report makes no claim about enjoyment or immersion in actual play.

Ratings and annotations from more than one person are only meaningful if the people agree. We report Krippendorff's alpha, which handles any number of coders, ordinal and interval data, and missing values, and has been argued for as a standard reliability measure for coding data (Hayes & Krippendorff, 2007). The target is alpha ≥ 0.6. Section 4 describes how the annotation was done, including where an AI model drafted labels that a team member then reviewed, and Section 7 states what that does to the agreement figures.

## 2.7 Rules base

The mechanics are derived from the System Reference Document 5.1 (Wizards of the Coast, 2023), released under the Creative Commons Attribution 4.0 licence. The game is inspired by it but is deliberately not compatible with it, and is not described as fifth edition. The cuts were made so that every rule could be tested and every state change validated:
- **Combat:** no map, movement, range or positioning, and three actions only (attack, cast a spell, dodge).
- **Spells and skills:** two spells only (Fire Bolt and Cure Wounds) and three skills (strength, perception, stealth).
- **Stored numbers:** attack bonuses and armour class are stored, not derived, and the proficiency bonus is a flat +2.
- **Hit points and death:** no death and no death saving throws. A combatant at 0 hit points is unconscious and cannot be attacked, which departs from tabletop convention.
- **Resting:** no rests, so spell slots do not recover within a session.
- **Party size:** one player character, with every other combatant run by the engine on a fixed policy.

Section 3 gives the full ruleset. Several of these cuts matter for the measurement. For example, because an unconscious combatant cannot be attacked, a narration of a second blow against a fallen enemy is an error the checker can see.

The works cited in this section are listed in the References at the end of the report (`references.md`).
