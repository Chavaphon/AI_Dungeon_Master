# Divergence rubric v0.5

WBS 8.1 · Owner: SD · Status: **draft, for the 8.11 pilot** · CLAUDE.md wins on any conflict.

This is the human annotation rubric for M1, the divergence rate (CLAUDE.md §10). It gives the four categories from §10.1, how to count them, and two positive and two negative worked examples per category. Borderline cases and the hit-point band rules in detail are WBS 8.2. The rubric is frozen as v1.0 at G3 (WBS 8.12).

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
5. **When in doubt, do not record.** As in §10.2, ambiguity is resolved in favour of no divergence. Write the case in the notes column so it can feed the 8.2 conventions.
6. **HP bands** are computed as `current_hp / max_hp`: `healthy` above 0.75, `wounded` above 0.35 up to 0.75, `badly_hurt` above 0 up to 0.35, `unconscious` at 0. A narration with no band phrase is not scored for band accuracy. Adjacent bands are not forgiven (§10.2).

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

## 5. Open points

For 8.2 (borderline conventions):

1. **Scenery.** Is "the damp stone walls" a phantom location if the scenario lists only "the cellar"? Proposal: no. Parts and features of a listed location are in scope, like the rat's teeth in P3.
2. **Negated and figurative band phrases.** "You are far from dying" and "the dying torchlight" both contain a `badly_hurt` word. The checker lexicon will match both. Proposal: annotators score neither.
3. **Hostile creatures with no relationship entry.** The rats are `faction: hostile` but are not in `npc_relationships`. Proposal: `RELATION` applies only to NPCs with a `stance`.

For the team:

4. **CLAUDE.md §6.2 example has the wrong band.** It shows a rat at 4 of 11 HP as `badly_hurt`, but 4/11 = 0.36 is `wounded` under §10.2. This rubric follows §10.2. The fix is already listed for the 2.6 freeze in `docs/tool_contract.md` §7, point 1.
