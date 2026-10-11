# Divergence rubric v0.6

WBS 8.1, 8.2 · Owner: SD · Status: **draft, for the 8.11 pilot** · CLAUDE.md wins on any conflict.

This is the human annotation rubric for M1, the divergence rate (CLAUDE.md §10). It gives the four categories from §10.1, how to count them, and two positive and two negative worked examples per category. Sections 5 and 6, the hit-point band rules in detail and the borderline conventions, are WBS 8.2. The rubric is frozen as v1.0 at G3 (WBS 8.12).

## 1. What a divergence is

A divergence is a phrase in the narration that **disagrees with the state**. Annotators score the narration of one turn against:

- **Condition D:** the state after that turn, plus the turn's `narration_facts` and `state_diff` in the audit log.
- **Conditions A–C:** the ground-truth state for that turn, from replaying the scenario's scripted inputs through the engine (§9).
- **All conditions:** the scenario definition. Its `display_name`s and `locations` are in scope even when they are not in the state (`docs/scenario_format.md`).

Only disagreement with the state counts. Weak prose, a wrong tone, or narration that acts for the player character are M5 (narrative quality), not divergences.

## 2. The four categories

| Code | Category | The narration... |
|---|---|---|
| `PHANTOM` | Phantom entity | names an item, character or location that is in neither the state nor the scenario definition |
| `CONTRADICT` | State contradiction | asserts something that conflicts with a recorded value: HP band, status, quest state, where an item is |
| `RESOURCE` | Resource error | describes spending, gaining or using up a resource in a way the state does not show: spell slots, inventory quantities |
| `RELATION` | Relationship contradiction | treats an NPC in a way that does not fit its recorded `stance` |

## 3. Counting rules

1. **Count every divergence.** One narration can contain several, including several in the same category. Two phantom items in one sentence are two `PHANTOM`s.
2. **One phrase, one divergence.** If a single phrase fits more than one category, record it once, in the first that applies in this order: `PHANTOM`, `CONTRADICT`, `RESOURCE`, `RELATION`. A phantom has no recorded value to contradict, so it is checked first.
3. **Repeats within one narration count once.** "The stranger smiles. The stranger draws a knife." is one phantom stranger (and one phantom knife).
4. **Each turn is scored on its own.** A phantom that appears again in a later turn is counted again in that turn.
5. **When in doubt, do not record.** As in §10.2, ambiguity is resolved in favour of no divergence. Write the case in the notes column so it can feed the pilot (WBS 8.11).
6. **HP bands** are computed as `current_hp / max_hp`: `healthy` above 0.75, `wounded` above 0.35 up to 0.75, `badly_hurt` above 0 up to 0.35, `unconscious` at 0. A narration with no band phrase is not scored for band accuracy. Adjacent bands are not forgiven (§10.2). The full rule is §5.

## 4. Worked examples

All examples use the cellar setting from `schemas/examples/scenario_s00_example.json`. Lyra has `max_hp` 20, a short sword, two torches, two level-1 spell slots and no lantern. The two giant rats have `max_hp` 11. The Keeper is an NPC in `npc_relationships`. The scenario's locations are "the cellar", "the cellar stairs" and "the barrels". Each example states only the facts that matter for it.

### 4.1 `PHANTOM`

**P1 — positive.** Lyra's inventory: short sword 1, torch 2.
> You raise your lantern, and its light catches two pairs of red eyes behind the barrels.

**1 × `PHANTOM`.** No lantern exists in the state or the scenario. It is a phantom item even though nothing is spent: the narration invents an object.

**P2 — positive.** Combatants: Lyra and two giant rats. No other characters.
> A hooded stranger steps out from behind the barrels and draws a curved dagger.

**2 × `PHANTOM`.** The stranger is a phantom character and the dagger a phantom item. Rule 1: count both.

**P3 — negative.** Lyra attacks `npc_rat_01` and hits.
> Your sword bites into the rat's flank, and its yellow teeth snap at your ankle as it twists away.

**No divergence.** A flank and teeth are parts of an entity that is in scope, not new entities. The rat's weapon is called "bite" in the state, and describing its teeth does not invent anything.

**P4 — negative.** Narration-only turn, "I look around the cellar".
> Water drips down the cellar stairs and pools around the barrels.

**No divergence.** "The cellar stairs" and "the barrels" are in the scenario's `locations`, so they are in scope even though the state has no location field.

### 4.2 `CONTRADICT`

**C1 — positive.** Lyra: `current_hp` 14 of 20. Ratio 0.70, band `wounded`.
> You stagger back, barely standing, your vision swimming.

**1 × `CONTRADICT`.** "Barely standing" is a `badly_hurt` phrase, and the recorded band is `wounded`. This is the §10.2 example: adjacent bands are still a divergence.

**C2 — positive.** `quest_missing_ledger` is `completed`. The Keeper has the ledger.
> "That ledger is still out there somewhere," the Keeper mutters. "Bring it back and we'll talk."

**1 × `CONTRADICT`.** The narration treats a completed quest as unfinished and the ledger as lost. Both statements come from one phrase about one fact, so rule 2 records it once. The Keeper's tone is not the issue here, so this is not `RELATION`.

**C3 — negative.** Lyra: `current_hp` 18 of 20. Ratio 0.90, band `healthy`.
> You shake the water from your boots, unhurt, and turn toward the second rat.

**No divergence.** "Unhurt" is a `healthy` phrase, and the recorded band is `healthy`.

**C4 — negative.** Lyra: `current_hp` 14 of 20, band `wounded`.
> You grit your teeth and lift your sword again.

**No divergence.** No band phrase appears, so the narration is not scored for band accuracy (rule 6). Gritted teeth suggest effort, not a health level.

### 4.3 `RESOURCE`

**R1 — positive.** Lyra casts `spell_fire_bolt`. `state_diff` has no change to `spell_slots_1`, which stays at 2.
> You pour the last of your magic into a bolt of fire that hurls the rat against the wall.

**1 × `RESOURCE`.** Fire Bolt is a cantrip and costs nothing (§4.6). "The last of your magic" claims a resource was used up, and Lyra still has two slots.

**R2 — positive.** Lyra's inventory: torch 2. This turn's `state_diff` is empty.
> You light your last torch and hold it high.

**1 × `RESOURCE`.** "Your last torch" asserts a quantity of 1 and the inventory holds 2.

**R3 — negative.** Lyra casts `spell_cure_wounds` on herself. `state_diff`: `spell_slots_1` 2 → 1.
> Warm light knits the cut on your arm closed, and you feel some of your magic ebb away with it.

**No divergence.** The narration describes spending magic, and the state shows one slot spent.

**R4 — negative.** `modify_inventory(item_ledger, -1)`. `state_diff`: `item_ledger` 1 → 0.
> You climb the stairs and press the ledger into the Keeper's hands.

**No divergence.** Lyra gives the ledger away, and the state shows her quantity drop to 0. An item at quantity 0 keeps its definition, so later mentions of the ledger are not `PHANTOM`.

### 4.4 `RELATION`

**L1 — positive.** The Keeper: `stance` `unfriendly`.
> The Keeper beams and pulls you into a hug like an old friend.

**1 × `RELATION`.** Warmth like this fits `friendly` or `allied`, not `unfriendly`.

**L2 — positive.** The Keeper: `stance` `friendly`, after `update_npc_relationship(up)` two turns ago. Nothing this turn changes it.
> The Keeper spits at your feet and orders you out of the cellar.

**1 × `RELATION`.** Open hostility toward a `friendly` NPC. If the player had just insulted the Keeper, a stance change should have gone through a tool call. Narration that runs ahead of the state is still a divergence.

**L3 — negative.** The Keeper: `stance` `unfriendly`.
> The Keeper eyes you coldly and answers with a single grunt.

**No divergence.** Coldness fits `unfriendly`.

**L4 — negative.** The Keeper: `stance` `neutral`.
> The Keeper nods and points you toward the stairs without a word.

**No divergence.** Businesslike and neither warm nor hostile, which fits `neutral`.

## 5. Hit-point bands in detail

This section is the rule for band accuracy. The automated checker (WBS 8.7) implements it exactly, and human annotators apply it in the same way.

### 5.1 The thresholds

The band is computed by `hp_band(current_hp, max_hp)` in `adm/engine/combat.py`, the one definition that the engine and the checker share (`docs/conventions.md` §1):

| Band | Ratio `current_hp / max_hp` | In integers |
|---|---|---|
| `healthy` | `> 0.75` | `100 × current_hp > 75 × max_hp` |
| `wounded` | `> 0.35` and `<= 0.75` | `100 × current_hp > 35 × max_hp`, and not `healthy` |
| `badly_hurt` | `> 0` and `<= 0.35` | `current_hp >= 1`, and neither of the above |
| `unconscious` | `== 0` | `current_hp == 0` |

A ratio of exactly 0.75 or exactly 0.35 is in the **lower** band: 15 of 20 is `wounded`, and 7 of 20 is `badly_hurt`. The comparison is done in integers, so there is no rounding. Annotators never compute the ratio by hand. In condition D they read `target_hp_band` from `narration_facts`. In conditions A–C, which have no `narration_facts`, they look up the replayed `current_hp` in the table in §5.6.

### 5.2 The settled rule: 14 of 20

> **A combatant at 14 of 20 HP is `wounded`.** 14 / 20 = 0.70, which is above 0.35 and at most 0.75. Any narration that describes that combatant with a `badly_hurt` phrase ("barely standing", "near death", "on the brink", "gravely wounded") is **one `CONTRADICT`**. So is a `healthy` phrase ("unhurt", "barely a scratch"). Only a `wounded` phrase, or no band phrase at all, is free of divergence.

Adjacent bands are not forgiven (CLAUDE.md §10.2). "It was only one band off" is never a reason to drop a divergence. The model was handed the band in condition D, and in conditions A–C the band is the measurement.

### 5.3 What a band phrase is

A **band phrase** is a word or phrase that describes **how hurt a combatant is now**. The checker uses only the lexicon in CLAUDE.md §10.2. Annotators judge by meaning, so "fully restored" is a `healthy` phrase although it is not in the lexicon. The following are **not** band phrases and are not scored for band accuracy:

1. **Events, not conditions.** Words that describe a blow landing this turn, not the state it leaves behind: "the bite hurts", "the blade wounds your arm", "you are struck". On its own a hit claims no band, because it can leave a combatant in any of them. "The bite leaves you badly wounded" describes the result and **is** a band phrase (`badly_hurt`).
2. **Negated phrases.** "You are far from dying", "not yet beaten", "no longer bleeding". Not scored either way. (Settles rubric v0.5 open point 2.)
3. **Figurative phrases about something else.** "The dying torchlight", "the barrels collapse", "a wounded silence". The phrase must be about a combatant. (Settles open point 2.)
4. **The past and the future.** "Earlier, you were nearly killed" and "one more hit and you'll fall" make no claim about the band now.
5. **Effort and emotion.** "You grit your teeth", "panting", "furious". As in example C4, these describe effort, not a health level.

Intensity words decide the band of a phrase: "badly / gravely / seriously / terribly wounded" is `badly_hurt`; "wounded", "hurt" and "bleeding" alone are `wounded`; "a scratch", "barely hurt" and "a graze" are `healthy`. If a phrase could honestly be read as either of two bands, and the actual band is one of them, record no divergence (rubric §3 rule 5). This is not an adjacency allowance. It applies only when the **phrase** is ambiguous, never when the phrase is clear and the band is one step away.

### 5.4 Which hit points are compared

1. **The state after the turn.** A band phrase is scored against the combatant's HP after every effect of the turn, including engine-controlled NPC steps (`target_hp_after` in condition D). "You are bleeding" after Cure Wounds brought Lyra from 6 to 16 of 20 is scored against 16 (`healthy`): one `CONTRADICT`.
2. **The combatant the phrase is about.** Each combatant is scored separately. A narration that gets two combatants' bands wrong has two `CONTRADICT`s (rule 1). If the phrase does not make clear which combatant it describes ("someone is badly hurt"), it is not scored.
3. **One combatant, one band divergence per narration.** If a narration describes the same combatant with several band phrases, and any of them disagrees with the actual band, record one `CONTRADICT` for that combatant (rule 3). Phrases that agree do not cancel one that does not.
4. **Every combatant, inside an encounter or not.** Hostile creatures are scored the same way as the player character. A combatant that is not in any encounter yet still has `current_hp` and is scored.

### 5.5 Unconscious: band and status

The `unconscious` band and the `unconscious` status always go together (CLAUDE.md §4.8): `current_hp` is 0 exactly when `status` is `unconscious`.

1. "Falls", "collapses" and "crumples" are `unconscious` phrases only when they mean losing consciousness. "The rat falls back, hissing" is not a band phrase.
2. Narrating a combatant at 0 HP as acting (attacking, speaking, fleeing), or a combatant above 0 HP as down, is **one `CONTRADICT`**, even if it also uses a band phrase. One phrase, one divergence (rule 2).
3. "Dying" or "near death" for a combatant at 0 HP is a `badly_hurt` phrase scored against the `unconscious` band: one `CONTRADICT`. There is no death in this game, so the phrase is not scored a second time as a claim of death.

### 5.6 Lookup table

HP values in each band for the `max_hp` values a scenario is likely to use. This table is generated from `hp_band`, and `tests/test_rubric.py` fails if the two disagree.

<!-- band-table:start -->
| `max_hp` | `healthy` | `wounded` | `badly_hurt` | `unconscious` |
|---|---|---|---|---|
| 4 | 4 | 2–3 | 1 | 0 |
| 5 | 4–5 | 2–3 | 1 | 0 |
| 6 | 5–6 | 3–4 | 1–2 | 0 |
| 7 | 6–7 | 3–5 | 1–2 | 0 |
| 8 | 7–8 | 3–6 | 1–2 | 0 |
| 9 | 7–9 | 4–6 | 1–3 | 0 |
| 10 | 8–10 | 4–7 | 1–3 | 0 |
| 11 | 9–11 | 4–8 | 1–3 | 0 |
| 12 | 10–12 | 5–9 | 1–4 | 0 |
| 13 | 10–13 | 5–9 | 1–4 | 0 |
| 14 | 11–14 | 5–10 | 1–4 | 0 |
| 15 | 12–15 | 6–11 | 1–5 | 0 |
| 16 | 13–16 | 6–12 | 1–5 | 0 |
| 17 | 13–17 | 6–12 | 1–5 | 0 |
| 18 | 14–18 | 7–13 | 1–6 | 0 |
| 19 | 15–19 | 7–14 | 1–6 | 0 |
| 20 | 16–20 | 8–15 | 1–7 | 0 |
| 21 | 16–21 | 8–15 | 1–7 | 0 |
| 22 | 17–22 | 8–16 | 1–7 | 0 |
| 23 | 18–23 | 9–17 | 1–8 | 0 |
| 24 | 19–24 | 9–18 | 1–8 | 0 |
| 25 | 19–25 | 9–18 | 1–8 | 0 |
| 26 | 20–26 | 10–19 | 1–9 | 0 |
| 27 | 21–27 | 10–20 | 1–9 | 0 |
| 28 | 22–28 | 10–21 | 1–9 | 0 |
| 29 | 22–29 | 11–21 | 1–10 | 0 |
| 30 | 23–30 | 11–22 | 1–10 | 0 |
<!-- band-table:end -->

For a `max_hp` above 30, use the integer rule in §5.1.

## 6. Other borderline conventions

These settle the open points of rubric v0.5 and the cases that come up most often in the worked examples. Each one leans towards **no divergence** when in doubt (rule 5).

### 6.1 `PHANTOM`

1. **Parts and features of a listed location are in scope.** "The damp stone walls", "the floor" and "a crack in the ceiling" belong to "the cellar". A separate place that is not listed ("the crypt below", "the next room") is a `PHANTOM`. (Settles open point 1.)
2. **Scenery is not an item.** Dust, cobwebs, puddles, shadows and smells are not phantom items. Something is an item when the narration lets it be picked up, used, given or spent. "A rusty key glints in the dust" is a `PHANTOM` item; "dust drifts in the torchlight" is not.
3. **Unnamed and unseen presences are not entities.** "A noise from somewhere above" or "you feel watched" asserts no character. "A guard shouts from the stairs" does.
4. **Too many of a kind is a phantom.** "Three rats" when the state has two is one `PHANTOM` (the third rat), not a `CONTRADICT`.
5. **Parts of an in-scope entity are in scope.** As in P3, the rat's teeth and tail and Lyra's armour or cloak are not phantoms. A distinct object that a character carries ("the rat's golden collar") is.

### 6.2 `CONTRADICT`

1. **Dialogue counts.** What an NPC says is part of the narration, as in C2. An NPC who lies is not an exception: this game has no deception mechanic, so a false statement is still a divergence.
2. **Quest state is scored by meaning.** Narration that treats a `completed` or `failed` quest as open, or a `not_started` quest as already under way, is a `CONTRADICT`. Hints and rumours about a `not_started` quest are not.

### 6.3 `RESOURCE`

1. **Quantity words are claims.** "Your last torch", "your only potion" and "your final spell" assert a quantity and are scored against the state. "A torch" or "your torches" asserts none.
2. **Fire Bolt costs nothing.** Any narration of Fire Bolt draining or using up magic is a `RESOURCE` divergence (example R1). Tiredness after casting ("you lower your hand, breathing hard") is not.

### 6.4 `RELATION`

1. **Only NPCs with a stance.** `RELATION` applies only to entries in `npc_relationships`. A `hostile` faction creature with no stance, such as the giant rats, cannot have a `RELATION` divergence. (Settles open point 3.)
2. **The stance after the turn.** If `update_npc_relationship` ran this turn, the narration is scored against the new stance. A change described in the narration without the tool call is a divergence (example L2).
3. **Two steps away, or a different direction.** Behaviour that fits the recorded stance or one step either side of it is not a divergence: the stance markers are coarse and the stance ladder has five steps. Behaviour two or more steps away (warmth towards `unfriendly`, hostility towards `friendly`) is. The adjacency allowance is for `RELATION` only. HP bands have none.

## 7. Open points for the 8.11 pilot

1. **RELATION adjacency (§6.4 rule 3).** This is a proposal. If the pilot shows that annotators disagree mostly on one-step stance cases, keep it. If they agree on them, drop it, and treat any stance mismatch as a divergence, as HP bands are treated.
2. **Checker coverage of §5.3.** The lexicon cannot tell an event ("the bite hurts") from a condition ("you are hurt"), or a negated phrase from a plain one. WBS 8.7 must either skip those cases or flag them as low confidence, so that the checker under-reports as CLAUDE.md §10.2 requires. WBS 8.10 should report how many of the 30 hand-labelled turns these cases account for.
