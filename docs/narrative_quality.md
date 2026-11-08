# Narrative-quality rating form (M5) v0.9

WBS 8.13 · Owner: SD · Status: **confirmed at the Week 5 checkpoint, 2026-11-08** · CLAUDE.md wins on any conflict.

This is the form and procedure for M5, narrative quality (CLAUDE.md §10.4): two raters, blind to condition, score narration from 1 to 5 on **coherence**, **vividness** and **tone appropriateness**, plus one **engagement** item, "Would you want to keep reading?". The ratings are WBS 9.8 (first rater, SS) and 9.9 (second rater, SD). Agreement is WBS 10.5.

M5 asks how good the narration is to read. It does not ask whether it matches the game state; that is M1 (`docs/rubric.md`). The raters never see the state.

## 1. What is rated

- **The unit is an excerpt:** five consecutive exchanges from one run. Each exchange is a scripted player input and the narration shown for it. Coherence and engagement need more than one reply to judge, and five keeps an excerpt to about three minutes.
- **All four conditions, all sixteen scenarios.** One excerpt per scenario and condition: 12 short scenarios and 4 long sessions, × 4 conditions = **64 excerpts**.
- **Paired across conditions.** For each scenario, the four excerpts come from the same seed and the same five inputs. So the four conditions are rated on identical stimuli (invariant 7), and condition differences can be compared within a scenario.
- **Both raters rate all 64.** Agreement is computed on the full set, which is more than the 20% overlap §10.4 requires.

At about 3.5 minutes an excerpt, 64 take each rater about 3.7 hours, inside the 4 hours of 9.8 and 9.9.

## 2. Choosing the excerpts

The choice is made from the final dataset (D8), with hashes rather than a random number generator, so anyone can reproduce it from the data and it uses no RNG (invariant 3). For each scenario:

1. **Seed.** Take the seeds run in all four conditions, ordered by `sha256("m5-v1/" + scenario_id + "/seed/" + seed)` as lowercase hex.
2. **Window.** Take the window starts `w = 0 … len(scripted_inputs) − 5`, ordered by `sha256("m5-v1/" + scenario_id + "/window/" + w)`.
3. **The first usable pair.** For the first seed, try the windows in that order. Use the first one in which **every one of the four runs has a narrated turn for each of the five inputs**: no record with `turn_failure` set. If no window qualifies, try the next seed.

Rule 3 is what keeps the excerpts blind. Only condition D can fail a turn, and a failed turn shows the player the `REPHRASE` request, so an excerpt with one would give D away. Excluding failed turns from all four conditions at once keeps the excerpts paired.

## 3. Blind presentation

The rater sees an excerpt like this, and nothing else:

```
Excerpt 3f9a1c07 — The Harvest Fair

1. You: I tell Miller Dunn I will catch the boar that broke out of his pen
   DM:  <narration>

2. You: I look for the boar's tracks through the trampled straw
   DM:  <narration>

… (five exchanges)
```

- **The id is opaque.** `excerpt_id` is the first 8 hex digits of `sha256("m5-v1/excerpt/" + run_id + "/" + w)`. It does not encode the condition, the seed or the window.
- **Shown:** the scenario's `display_name`, the five player inputs numbered 1 to 5, and the record's `narration` for each, as the player saw it (after the safety filter, WBS 6.9).
- **Not shown:** the condition, `run_id`, seed, `turn_number`, `input_index`, the state, `narration_facts`, rolls, the raw model output and `narration_filtered`. Turn numbers are hidden because they repeat after a failed turn, which only D has.
- **Order.** Each rater gets all 64 in their own order, sorted by `sha256("m5-v1/order/" + rater + "/" + excerpt_id)`, so the four excerpts of a scenario are not seen side by side, and the two raters do not share order effects.
- **The key.** The mapping from `excerpt_id` to `run_id` and `w` is kept in `results/m5_key.json`. Neither rater opens it until both have finished.

The narration is shown unedited. If the narration itself hints at a condition (for example, a condition C reply that leaks its self-check), the rater still rates it as written and notes it. That is a property of the condition, not a leak in the form.

## 4. The form

Read all five exchanges once, then rate **the excerpt as a whole** on each item. Use the anchors for 1, 3 and 5. A 2 or 4 is between them. Rate as a reader of the story:

- Do not check the narration against the game rules or the state. M1 does that.
- Do not mark down the player inputs. They are fixed by the script.
- The Dungeon Master is told to narrate in the second person, present tense, 2–4 sentences, and never to speak or act for the player character (§9.1). Count a reply that breaks this under **tone**.

### 4.1 Coherence: does it hang together?

| Score | Anchor |
|---|---|
| 1 | Replies ignore the player's inputs or each other. Events, people or places change from one reply to the next without reason. Hard to follow. |
| 3 | Mostly follows the inputs and stays consistent, with one or two lapses: a forgotten detail, an odd jump, a reply that answers a different input. |
| 5 | Every reply follows from its input and from what came before. Nothing contradicts anything else in the excerpt. Easy to follow. |

### 4.2 Vividness: can you picture it?

| Score | Anchor |
|---|---|
| 1 | Generic and flat ("You attack. It is hurt."). No concrete detail. |
| 3 | Some specific detail of sight, sound or action, but much is stock phrasing or repeated. |
| 5 | Concrete, specific and varied detail throughout. The scene is easy to picture, without padding. |

### 4.3 Tone appropriateness: does it sound right?

| Score | Anchor |
|---|---|
| 1 | The voice does not fit: out of character, modern or assistant-like ("As an AI…", "Sure! Here's…"), wrong mood for the moment, or the narrator acts or speaks for the player. |
| 3 | Fits the fantasy game most of the time, with a lapse: a flat moment, a jarring word, the mood of a fight given to a quiet scene, or one reply that breaks the second-person voice. |
| 5 | A consistent Dungeon Master's voice that fits the game and each moment: tense in a fight, warm or cool with an NPC as the scene calls for. |

### 4.4 Engagement: "Would you want to keep reading?"

| Score | Anchor |
|---|---|
| 1 | Definitely not. |
| 2 | Probably not. |
| 3 | Not sure. |
| 4 | Probably yes. |
| 5 | Definitely yes. |

### 4.5 Note

Optional free text for anything that made a rating hard, or a hint about the condition (§3).

## 5. Recording

The tool (8.15) writes one line per rating to `results/m5_ratings.jsonl` (gitignored, CLAUDE.md §3):

```json
{"excerpt_id": "3f9a1c07", "rater": "SS",
 "coherence": 4, "vividness": 3, "tone": 5, "engagement": 4, "note": ""}
```

Every item is an integer from 1 to 5, and all four are required. An excerpt is rated once per rater; a re-rating replaces the earlier line and is noted.

## 6. Reporting

WBS 10.5 and the results section (11.3) use:

- **Agreement:** Krippendorff's alpha, **ordinal** level, for each of the four items, over all 64 excerpts. The target is `>= 0.6` (§10.4).
- **Scores:** for each condition and item, the median and mean of the two raters' average, over the 16 scenarios. Long sessions are also reported apart from short scenarios.
- **Comparisons** between conditions are paired by scenario (§1), since the four excerpts of a scenario share their seed and inputs.

## 7. Fallback (risk R5)

If rating falls behind, as R5 defines, both raters rate the 48 short-scenario excerpts and drop the long sessions. The choice is made before rating starts, so both raters rate the same set, and it is reported with the results.

## 8. Open points for the Week 5 checkpoint

1. **Five exchanges per excerpt and 64 excerpts** are a proposal, sized to the 4 hours of 9.8 and 9.9. A few can be timed on the 7.7 dry-run transcripts before rating starts, and the window can shrink to four exchanges if 3.5 minutes is optimistic.
2. **The annotation tool (8.15, CI)** shows the excerpts and writes `results/m5_ratings.jsonl`. It needs §3 and §5 from this form. Done: `python -m adm.eval.annotate m5 --rater <initials>` (`docs/decisions.md`, 2026-11-02).

Settled at the Week 5 checkpoint (`docs/decisions.md`, 2026-11-08): five exchanges per excerpt and 64 excerpts, as drafted. The §7 fallback is the only reduction.
