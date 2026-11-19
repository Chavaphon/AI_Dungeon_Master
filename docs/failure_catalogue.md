# Catalogue of ten illustrative failures

WBS 10.7 · Owner: SS · Drawn 2026-11-19 · CLAUDE.md wins on any conflict.

Ten failures of the system, one per slot, each with its transcript excerpt and a state snapshot. They illustrate the error taxonomy of the report's Results (`docs/report_outline.md` §5.3, `docs/figures.md` figure 5.3) and feed the A-versus-D exhibit (10.8). Done when: "Each with transcript excerpt and state snapshot" (TASK_CHECKLIST.md, 10.7).

## 1. How the ten were chosen

Fixed in `docs/decisions.md` (2026-11-19, "Failure catalogue, fixed before the draw") and committed (5f94ebf) before the command was run on the labels.

| Item | Rule |
|---|---|
| Slots | Ten, one failure each. M1, seven: `PHANTOM` in A found by the checker, `PHANTOM` in D, `CONTRADICT` in D found by the `hp_band` check, `CONTRADICT` in C, `CONTRADICT` in B added by the annotator, `RESOURCE` in D, `RELATION` in D. M4, one: a rule break narrated in A, B or C. M2, one: a D turn whose retry budget ran out. M3, one: a valid call that misreads the request. |
| Sources | M1 and M4: SD's 9.5 labels on the M1 sample, as in 10.1. M2: the 48 condition D runs of the main grid. M3: the four turns named in `docs/m3_annotation.md` §3, with CI's final verdicts. |
| Draw | Within a slot, eligible turns in order of sha256(`10.7-v1/<slot>/<turn>`), the first taken. One slot per turn. A turn of the 9.6 overlap on which SS recorded no divergence of the slot's category is skipped. |
| Entry | Player input; in D, every tool-call attempt with its outcome and the facts given to the narrator; the narration with each labelled divergence in bold; the labels and the drafter's note; a state snapshot. |
| Snapshot | M1 and M4: the state the turn is scored against, after it (rubric §1: D's logged state, A to C's replayed ground truth). M2 and M3: the state the tool-call prompt saw. Ids qualified by scenario (`docs/identifiers.md` §3). |
| Command | `python -m adm.eval.catalogue --checksums experiments/main_grid.sha256 --doc docs/failure_catalogue.md` |

**The catalogue illustrates and estimates nothing.** The rates are those of 10.1 (M1), 10.3 (M2), 9.7 (M3) and 10.4 (M4).

## 2. The ten

<!-- results:start -->
Ten failures drawn by the rule of `docs/decisions.md` (2026-11-19). Labels sha256 `53d74b6bd68400064fa83d8da1f60cc90087ece80918aba13f453362bb11138e`. Bold marks each labelled divergence in a narration.

| # | Layer | Category | Run | Input | Drawn from |
|---|---|---|---|---|---|
| 1 | M1 | `PHANTOM` | `A_s10_watchtower_2002` | 20 | 80 |
| 2 | M1 | `PHANTOM` | `D_long04_mountain_monastery_2002` | 17 | 110 |
| 3 | M1 | `CONTRADICT` | `D_s08_old_mine_2003` | 19 | 13 |
| 4 | M1 | `CONTRADICT` | `C_s04_goblin_warren_2002` | 13 | 87 |
| 5 | M1 | `CONTRADICT` | `B_s10_watchtower_2002` | 8 | 96 |
| 6 | M1 | `RESOURCE` | `D_s05_wayside_inn_2002` | 14 | 11 |
| 7 | M1 | `RELATION` | `D_s06_drowned_lighthouse_2003` | 22 | 11 |
| 8 | M4 | `RULE` | `C_s04_goblin_warren_2002` | 12 | 143 |
| 9 | M2 | – | `D_s11_frozen_pass_2003` | 15 | 54 |
| 10 | M3 | – | `D_s11_frozen_pass_2002` | 17 | 4 |

### 1. A phantom entity, found by the checker

M1, `PHANTOM` · `A_s10_watchtower_2002`, scripted input 20 (turn 17) · drawn from 80 eligible turns

**Player:** "I take the flask of lamp oil from the goblins' stores"

**Narration:**

> You rummage through the goblins' scattered belongings, searching for a flask of lamp oil. Your fingers brush against the cold metal of a goblin's dagger, and you push it aside, finally finding the small flask tucked away in a leather **pouch**. The flask is almost full, and you can smell the sweet, pungent scent of lamp oil wafting up from it.

**Labels** (first annotator, rubric v1.0):

1. `PHANTOM` "pouch" (entity_mention candidate, confirmed)

Annotation note (AI draft, accepted by SD): Leather pouch is an invented item. 'a goblin's dagger' may describe a goblin's notched blade; ambiguous, rejected.

**State snapshot**, the state the turn is scored against, after it (rubric section 1):

- Encounter: none active (last ended in victory)
- `s10_watchtower/pc_kael` Kael (party): 28/30 HP, healthy, active
- `s10_watchtower/npc_goblin_01` goblin (hostile): 0/5 HP, unconscious, unconscious
- `s10_watchtower/npc_goblin_02` goblin (hostile): 0/5 HP, unconscious, unconscious
- `s10_watchtower/npc_goblin_03` goblin (hostile): 0/5 HP, unconscious, unconscious
- Inventory of `s10_watchtower/pc_kael`: battleaxe x1, javelin x3, flask of lamp oil x1
- Inventory of `s10_watchtower/npc_goblin_01`: notched blade x1
- Inventory of `s10_watchtower/npc_goblin_02`: notched blade x1
- Inventory of `s10_watchtower/npc_goblin_03`: notched blade x1
- `s10_watchtower/npc_scout_ilsa` Scout Ilsa: friendly
- `s10_watchtower/quest_watchtower` Retake the Watchtower: active, stage 2 of 2
- `s10_watchtower/quest_signal_fire` The Signal Fire: active, stage 1 of 1

### 2. A phantom entity in condition D

M1, `PHANTOM` · `D_long04_mountain_monastery_2002`, scripted input 17 (turn 18) · drawn from 110 eligible turns

**Player:** "I sit with the sick monk through the night"

**Tool-call attempts** (temperature 0.0):

1. `{"tool": null} -> ok`
2. `{"tool": "dodge", "arguments": {"actor_id": "pc_ansa"}} -> ENCOUNTER_OVER`
3. `{"tool": "modify_inventory", "arguments": {"actor_id": "pc_ansa", "item_id": "item_frost_lily", "delta": 1}} -> ok`

**Facts given to the narrator:**

```json
{"actor": "Ansa", "item": "frost-lily", "delta": 1, "quantity_before": 0, "quantity_after": 1}
```

**Narration:**

> You sit beside the young monk's bed, watching as he struggles to catch his breath, his chest rising and falling with a slow, labored rhythm. The infirmarian has given him a small cup of the fever draught, which he sips hesitantly, wincing at the bitter taste. The flames from the **candles** on the bedside table cast flickering shadows on the walls, illuminating the sweat-drenched sheets and the worried look on the young monk's face.

**Labels** (first annotator, rubric v1.0):

1. `PHANTOM` "candles" (entity_mention candidate, confirmed)

Annotation note (AI draft, accepted by SD): candles on bedside table can be picked up; [1] body part; [2] not a band phrase

**State snapshot**, the state the turn is scored against, after it (rubric section 1):

- Encounter: none active
- `long04_mountain_monastery/pc_ansa` Ansa (party): 24/24 HP, healthy, active, 1 level-1 slots
- `long04_mountain_monastery/npc_harpy_01` harpy (hostile): 5/5 HP, healthy, active
- `long04_mountain_monastery/npc_harpy_02` harpy (hostile): 5/5 HP, healthy, active
- Inventory of `long04_mountain_monastery/pc_ansa`: quarterstaff x1, rope x3, frost-lily x1
- Inventory of `long04_mountain_monastery/npc_harpy_01`: claws x1
- Inventory of `long04_mountain_monastery/npc_harpy_02`: claws x1
- `long04_mountain_monastery/npc_abbot` the abbot: hostile
- `long04_mountain_monastery/npc_brother_tam` Brother Tam: friendly
- `long04_mountain_monastery/npc_sorin` Sorin: neutral
- `long04_mountain_monastery/quest_pilgrims_climb` The Pilgrim's Climb: active, stage 2 of 4
- `long04_mountain_monastery/quest_fevered_monk` The Fevered Monk: not_started, stage 0 of 2
- `long04_mountain_monastery/quest_storeroom_thief` The Storeroom Thief: not_started, stage 0 of 2
- `long04_mountain_monastery/quest_high_bell` The High Bell: not_started, stage 0 of 1

### 3. A hit-point or status contradiction in D, with the band in the facts

M1, `CONTRADICT` · `D_s08_old_mine_2003`, scripted input 19 (turn 17) · drawn from 13 eligible turns

**Player:** "I send another bolt of fire into the spider"

**Tool-call attempts** (temperature 0.0):

1. `{"tool": "cast_spell", "arguments": {"caster_id": "pc_oren", "spell_id": "spell_fire_bolt", "target_id": "npc_giant_spider"}} -> ok`

**Facts given to the narrator:**

```json
{"hit": false, "critical": false, "attack_roll": 11, "advantage_mode": "normal", "target_ac": 13, "damage": 0, "target_hp_before": 4, "target_hp_after": 4, "target_hp_max": 12, "target_hp_band": "badly_hurt", "target_status": "active", "caster": "Oren", "target": "giant spider", "spell": "fire bolt"}
{"hit": false, "critical": false, "attack_roll": 13, "advantage_mode": "normal", "target_ac": 16, "damage": 0, "target_hp_before": 18, "target_hp_after": 18, "target_hp_max": 24, "target_hp_band": "wounded", "target_status": "active", "attacker": "giant spider", "target": "Oren", "weapon": "fangs"}
```

**Narration:**

> Your bolt of fire hurtles towards the giant spider, which lies motionless on the mine floor, its body badly injured from your previous attack. The flame from the fire bolt illuminates the dark mine, casting eerie shadows on the walls as it hurtles towards the spider. The spider's body is still twitching weakly, its eight legs splayed out in all directions, and it doesn't seem to be reacting to the incoming fire. The flame from the fire bolt engulfs the spider's body, casting a brief, intense blaze over its injured form. The spider's body convulses with a sudden, intense spasm, and then it lies still, its chest no longer rising and **falling** with a faint, labored breath.

**Labels** (first annotator, rubric v1.0):

1. `CONTRADICT` "falling" (hp_band candidate, confirmed)

Annotation note (AI draft, accepted by SD): Spider at 4/12 narrated as dead/down ('lies still, its chest no longer rising and falling'); confirming [2] for that phrase. 'chest' body part

**State snapshot**, the state the turn is scored against, after it (rubric section 1):

- Encounter: active, round 6, `s08_old_mine/pc_oren` to act
- `s08_old_mine/pc_oren` Oren (party): 18/24 HP, wounded, active, 0 level-1 slots
- `s08_old_mine/npc_kobold_01` kobold (hostile): 0/4 HP, unconscious, unconscious
- `s08_old_mine/npc_kobold_02` kobold (hostile): 3/4 HP, wounded, active
- `s08_old_mine/npc_giant_spider` giant spider (hostile): 4/12 HP, badly_hurt, active
- Inventory of `s08_old_mine/pc_oren`: warhammer x2, torch x2
- Inventory of `s08_old_mine/npc_kobold_01`: spear x1
- Inventory of `s08_old_mine/npc_kobold_02`: spear x1
- Inventory of `s08_old_mine/npc_giant_spider`: fangs x1
- `s08_old_mine/npc_foreman` the foreman: unfriendly
- `s08_old_mine/quest_lost_miners` The Lost Miners: active, stage 1 of 2

### 4. A state contradiction past C's self-check

M1, `CONTRADICT` · `C_s04_goblin_warren_2002`, scripted input 13 (turn 12) · drawn from 87 eligible turns

**Player:** "I take one more swing at the little goblin if it is still dodging"

**Narration:**

> Your handaxe slices through the air, biting deep into the little goblin's leg. The goblin's high-pitched yelp grows louder as **it tries to scramble away** from **your attack**. **The goblin's torch** casts an erratic light on the walls as it falls to the ground, clutching at its wounded leg.

**Labels** (first annotator, rubric v1.0):

1. `CONTRADICT` "it tries to scramble away" (added by the annotator)
2. `RULE` "your attack" (rule_violation candidate, confirmed)
3. `PHANTOM` "The goblin's torch" (added by the annotator)

Annotation note (AI draft, accepted by SD): runt at 0/3 unconscious narrated as scrambling away

**State snapshot**, the state the turn is scored against, after it (rubric section 1):

- Encounter: none active (last ended in victory)
- `s04_goblin_warren/pc_mara` Mara (party): 16/24 HP, wounded, active
- `s04_goblin_warren/npc_goblin_boss` goblin boss (hostile): 0/9 HP, unconscious, unconscious
- `s04_goblin_warren/npc_goblin_runt` little goblin (hostile): 0/3 HP, unconscious, unconscious
- Inventory of `s04_goblin_warren/pc_mara`: handaxe x1, torch x1
- Inventory of `s04_goblin_warren/npc_goblin_boss`: scimitar x1
- Inventory of `s04_goblin_warren/npc_goblin_runt`: silver spoon x1
- `s04_goblin_warren/npc_garrick` Garrick: neutral
- `s04_goblin_warren/npc_garricks_wife` Garrick's wife: neutral
- `s04_goblin_warren/quest_rescue_garrick` Rescue Garrick: active, stage 1 of 2
- `s04_goblin_warren/quest_lost_sheep` The Lost Sheep: not_started, stage 0 of 1

### 5. A state contradiction the checker missed, in B

M1, `CONTRADICT` · `B_s10_watchtower_2002`, scripted input 8 (turn 8) · drawn from 96 eligible turns

**Player:** "I put my back to the wall and fend them off"

**Narration:**

> You stand with your back against the wall of the watchtower, your battleaxe at the ready. The **wounded** goblin, its shoulder bloody, takes a tentative step forward, its crude **club** raised. **The second goblin, clutching its wounded shoulder, hesitates**, its beady eyes fixed on you with a mixture of fear and anger. The third goblin, still clutching its wounded side, looks at its companions uncertainly, its eyes flicking between you and the broken door of the watchtower.

**Labels** (first annotator, rubric v1.0):

1. `CONTRADICT` "wounded" (hp_band candidate, confirmed)
2. `PHANTOM` "club" (entity_mention candidate, confirmed)
3. `CONTRADICT` "The second goblin, clutching its wounded shoulder, hesitates" (added by the annotator)

Annotation note (AI draft, accepted by SD): [1] taken as the third goblin's 'wounded side' (goblin_03 is 5/5 healthy); second goblin is 0/5 but narrated acting. 'The wounded goblin' unidentifiable, not scored

**State snapshot**, the state the turn is scored against, after it (rubric section 1):

- Encounter: active, round 5, `s10_watchtower/pc_kael` to act
- `s10_watchtower/pc_kael` Kael (party): 28/30 HP, healthy, active
- `s10_watchtower/npc_goblin_01` goblin (hostile): 0/5 HP, unconscious, unconscious
- `s10_watchtower/npc_goblin_02` goblin (hostile): 0/5 HP, unconscious, unconscious
- `s10_watchtower/npc_goblin_03` goblin (hostile): 5/5 HP, healthy, active
- Inventory of `s10_watchtower/pc_kael`: battleaxe x1, javelin x3
- Inventory of `s10_watchtower/npc_goblin_01`: notched blade x1
- Inventory of `s10_watchtower/npc_goblin_02`: notched blade x1
- Inventory of `s10_watchtower/npc_goblin_03`: notched blade x1
- `s10_watchtower/npc_scout_ilsa` Scout Ilsa: neutral
- `s10_watchtower/quest_watchtower` Retake the Watchtower: active, stage 1 of 2
- `s10_watchtower/quest_signal_fire` The Signal Fire: not_started, stage 0 of 1

### 6. A resource error in D

M1, `RESOURCE` · `D_s05_wayside_inn_2002`, scripted input 14 (turn 15) · drawn from 11 eligible turns

**Player:** "I heal the merchant who was caught in the middle of the brawl"

**Tool-call attempts** (temperature 0.0):

1. `{"tool": "cast_spell", "arguments": {"caster_id": "pc_hollis", "spell_id": "spell_cure_wounds", "target_id": "npc_merchant"}} -> NO_SPELL_SLOT`
2. `{"tool": "cast_spell", "arguments": {"caster_id": "pc_hollis", "spell_id": "spell_fire_bolt", "target_id": "npc_merchant"}} -> ENCOUNTER_OVER`
3. `{"tool": "modify_inventory", "arguments": {"actor_id": "pc_hollis", "item_id": "item_staff", "delta": 1}} -> ok`

**Facts given to the narrator:**

```json
{"actor": "Hollis", "item": "staff", "delta": 1, "quantity_before": 1, "quantity_after": 2}
```

**Narration:**

> You rush over to the merchant who was caught in the middle of the brawl, and **use your magic to heal his burns**. The flames have been extinguished, but his clothes are singed and he's shaken. As you lay a hand on his shoulder, you feel a surge of energy flow through him, and **his wounds begin to close**. His eyes, which had been wide with fear, slowly relax as he feels the pain begin to subside.

**Labels** (first annotator, rubric v1.0):

1. `RESOURCE` "use your magic to heal his burns" (added by the annotator)
2. `RULE` "his wounds begin to close" (added by the annotator)

Annotation note (AI draft, accepted by SD): Healing magic is narrated with slots at 0 and no slot change (the executed call is staff +1). The healing magic is a RESOURCE divergence, and Cure Wounds with no slot is a RULE break. SD should check whether both are wanted.

**State snapshot**, the state the turn is scored against, after it (rubric section 1):

- Encounter: none active (last ended in victory)
- `s05_wayside_inn/pc_hollis` Hollis (party): 15/20 HP, wounded, active, 0 level-1 slots
- `s05_wayside_inn/npc_drunk_01` big drunk (hostile): 5/5 HP, healthy, active
- `s05_wayside_inn/npc_drunk_02` drunk (hostile): 5/5 HP, healthy, active
- `s05_wayside_inn/npc_merchant` merchant (neutral): 9/9 HP, healthy, active
- Inventory of `s05_wayside_inn/pc_hollis`: staff x2, room key x2
- Inventory of `s05_wayside_inn/npc_drunk_01`: fists x1
- Inventory of `s05_wayside_inn/npc_drunk_02`: fists x1
- Inventory of `s05_wayside_inn/npc_merchant`: bolt of cloth x1
- `s05_wayside_inn/npc_bess` Bess: neutral
- `s05_wayside_inn/npc_stranger` the cloaked stranger: unfriendly
- `s05_wayside_inn/quest_missing_ledger` The Missing Ledger: active, stage 1 of 2

### 7. A relationship contradiction in D

M1, `RELATION` · `D_s06_drowned_lighthouse_2003`, scripted input 22 (turn 23) · drawn from 11 eligible turns

**Player:** "I pour oil into the great lamp and light it"

**Tool-call attempts** (temperature 0.0):

1. `{"tool": "modify_inventory", "arguments": {"actor_id": "pc_vesna", "item_id": "item_lamp_oil", "delta": -8}} -> ok`

**Facts given to the narrator:**

```json
{"actor": "Vesna", "item": "flask of lamp oil", "delta": -8, "quantity_before": 8, "quantity_after": 0}
```

**Narration:**

> You carefully pour the oil from the flask into the great lamp's reservoir, watching as the liquid flows into the glass container. Once the oil is filled, you carefully light the wick, and the lamp begins to glow with a warm, golden light. The light spills out of the lantern room and into the surrounding darkness, casting an eerie glow over the lighthouse's exterior. **The keeper's eyes light up with a mixture of relief and gratitude** as he watches the lamp come to life.

**Labels** (first annotator, rubric v1.0):

1. `RELATION` "The keeper's eyes light up with a mixture of relief and gratitude" (added by the annotator)

Annotation note (AI draft, accepted by SD): keeper hostile; gratitude two+ steps away. 'lantern room' = lamp room. Lamp lit while quest still active read as progress, not completion

**State snapshot**, the state the turn is scored against, after it (rubric section 1):

- Encounter: none active (last ended in victory)
- `s06_drowned_lighthouse/pc_vesna` Vesna (party): 22/22 HP, healthy, active
- `s06_drowned_lighthouse/npc_giant_crab` giant crab (hostile): 0/11 HP, unconscious, unconscious
- Inventory of `s06_drowned_lighthouse/pc_vesna`: spear x1, flask of lamp oil x0, spyglass x1
- Inventory of `s06_drowned_lighthouse/npc_giant_crab`: claw x1
- `s06_drowned_lighthouse/npc_keeper` the keeper: hostile
- `s06_drowned_lighthouse/npc_ilse` Ilse: friendly
- `s06_drowned_lighthouse/quest_relight_lamp` Relight the Lamp: active, stage 1 of 3

### 8. A rule break narrated with no engine

M4, `RULE` · `C_s04_goblin_warren_2002`, scripted input 12 (turn 12) · drawn from 143 eligible turns

**Player:** "I corner the little goblin and strike at it"

**Narration:**

> You raise your handaxe, swinging it at the little goblin as it tries to scramble away from **your attack**. The blade bites deep into the goblin's leg, and it lets out a high-pitched yelp as **it tries to crawl towards** the pile of treasure. **The goblin's torch** casts a wild, erratic light on the walls as it clutches at its wounded leg, unable to escape your grasp.

**Labels** (first annotator, rubric v1.0):

1. `RULE` "your attack" (rule_violation candidate, confirmed)
2. `CONTRADICT` "it tries to crawl towards" (added by the annotator)
3. `PHANTOM` "The goblin's torch" (added by the annotator)

Annotation note (AI draft, accepted by SD): runt at 0/3 unconscious narrated as crawling/yelping

**State snapshot**, the state the turn is scored against, after it (rubric section 1):

- Encounter: none active (last ended in victory)
- `s04_goblin_warren/pc_mara` Mara (party): 16/24 HP, wounded, active
- `s04_goblin_warren/npc_goblin_boss` goblin boss (hostile): 0/9 HP, unconscious, unconscious
- `s04_goblin_warren/npc_goblin_runt` little goblin (hostile): 0/3 HP, unconscious, unconscious
- Inventory of `s04_goblin_warren/pc_mara`: handaxe x1, torch x1
- Inventory of `s04_goblin_warren/npc_goblin_boss`: scimitar x1
- Inventory of `s04_goblin_warren/npc_goblin_runt`: silver spoon x1
- `s04_goblin_warren/npc_garrick` Garrick: neutral
- `s04_goblin_warren/npc_garricks_wife` Garrick's wife: neutral
- `s04_goblin_warren/quest_rescue_garrick` Rescue Garrick: active, stage 1 of 2
- `s04_goblin_warren/quest_lost_sheep` The Lost Sheep: not_started, stage 0 of 1

### 9. A tool call that ran out of retries

M2 · `D_s11_frozen_pass_2003`, scripted input 15 (turn 14) · drawn from 54 eligible turns

**Player:** "I send one more bolt at the first wolf if it is still standing"

**Tool-call attempts** (temperature 0.0):

1. `{"tool": "cast_spell", "arguments": {"caster_id": "pc_ysolde", "spell_id": "spell_fire_bolt", "target_id": "npc_wolf_01"}} -> ENCOUNTER_OVER`
2. `{"tool": "cast_spell", "arguments": {"caster_id": "pc_ysolde", "spell_id": "spell_cure_wounds", "target_id": "pc_ysolde"}} -> ACTOR_UNCONSCIOUS`
3. `{"tool": "skill_check", "arguments": {"actor_id": "pc_ysolde", "skill": "perception", "dc": 15}} -> ACTOR_UNCONSCIOUS`

**Facts given to the narrator:** none.

**Narration:**

> I couldn't turn that into an action. Could you rephrase it?

**State snapshot**, the state the tool-call prompt saw:

- Encounter: none active (last ended in defeat)
- `s11_frozen_pass/pc_ysolde` Ysolde (party): 0/20 HP, unconscious, unconscious, 1 level-1 slots
- `s11_frozen_pass/npc_wolf_01` wolf (hostile): 2/4 HP, wounded, active
- `s11_frozen_pass/npc_wolf_02` wolf (hostile): 2/4 HP, wounded, active
- Inventory of `s11_frozen_pass/pc_ysolde`: quarterstaff x1, ration x1, blanket x0
- Inventory of `s11_frozen_pass/npc_wolf_01`: bite x1
- Inventory of `s11_frozen_pass/npc_wolf_02`: bite x1
- `s11_frozen_pass/npc_old_tobin` Old Tobin: unfriendly
- `s11_frozen_pass/quest_cross_pass` Over the Pass: not_started, stage 0 of 3

### 10. A valid call that is not what the player asked for

M3 · `D_s11_frozen_pass_2002`, scripted input 17 (turn 14) · drawn from 4 eligible turns

**Player:** "I wrap my blanket around Tobin's shoulders and tell him to keep it"

**Tool-call attempts** (temperature 0.0):

1. `{"tool": null} -> ok`
2. `{"tool": "modify_inventory", "arguments": {"actor_id": "pc_ysolde", "item_id": "item_blanket", "delta": -1}} -> NEGATIVE_QUANTITY`
3. `{"tool": "modify_inventory", "arguments": {"actor_id": "pc_ysolde", "item_id": "item_blanket", "delta": 1}} -> ok`

**Facts given to the narrator:**

```json
{"actor": "Ysolde", "item": "blanket", "delta": 1, "quantity_before": 0, "quantity_after": 1}
```

**Narration:**

> You wrap the worn blanket around Tobin's shoulders, trying to keep the chill from seeping in. He nods his thanks, his eyes still fixed on the path ahead, but his hands remain in his cloak, his fingers curled over the worn leather pouch that hangs from his belt. The wind whips his grey hair into a frenzy, and his bushy eyebrows are bent against the gusts, but he seems undeterred.

**M3 verdict** (CI, `docs/m3_annotation.md` section 3): `WRONG_TOOL`.

**State snapshot**, the state the tool-call prompt saw:

- Encounter: none active (last ended in victory)
- `s11_frozen_pass/pc_ysolde` Ysolde (party): 17/20 HP, healthy, active, 0 level-1 slots
- `s11_frozen_pass/npc_wolf_01` wolf (hostile): 0/4 HP, unconscious, unconscious
- `s11_frozen_pass/npc_wolf_02` wolf (hostile): 0/4 HP, unconscious, unconscious
- Inventory of `s11_frozen_pass/pc_ysolde`: quarterstaff x1, ration x1, blanket x0
- Inventory of `s11_frozen_pass/npc_wolf_01`: bite x1
- Inventory of `s11_frozen_pass/npc_wolf_02`: bite x1
- `s11_frozen_pass/npc_old_tobin` Old Tobin: unfriendly
- `s11_frozen_pass/quest_cross_pass` Over the Pass: not_started, stage 0 of 3
<!-- results:end -->

## 3. Reading

Read after the draw. Each point names the entries it rests on. The catalogue shows how failures happen, not how often; every count below is cited from the doc that computed it.

### 3.1 Per entry

1. **A, an invented container.** Asked to take the lamp oil, the narrator finds it "in a leather pouch" that exists nowhere. A small, typical `PHANTOM`: scenery invented to make the action vivid. The checker found it.
2. **D, an invented call and an invented candle.** "I sit with the sick monk through the night" needs no tool. The model said so (`{"tool": null}`). The forced re-prompt (decision 32) produced a `dodge` outside combat, and the last attempt added a frost-lily the player never picked. The narrator then ignored that fact and invented candles. The facts constrained neither the call nor the narration.
3. **D, the band in the facts and the spider dead anyway.** The facts say the fire bolt missed and the spider is `badly_hurt` and `active` at 4 of 12. The narration has it "lies still, its chest no longer rising and falling". This is the case §10.2 was written for: the model was handed the band and contradicted it.
4. **C, an unconscious goblin scrambling away.** The state in C's prompt has the little goblin at 0 of 3, `unconscious`, and the self-check instruction asks for health to match. The narration has it yelping and scrambling, and adds a torch it does not hold.
5. **B, a downed goblin hesitating, which only a person caught.** Two of the three goblins are at 0 of 5. The narration has "the second goblin, clutching its wounded shoulder" still in the fight. The checker flagged a band word nearby but not this status contradiction; the annotator added it. This is why M1 counts added labels as well as confirmed candidates.
6. **D, healing with no slot, after a call that changed nothing related.** Cure Wounds was rejected (`NO_SPELL_SLOT`), and the retries ended in `modify_inventory` adding a second staff. The facts given to the narrator say only "staff +1". It narrates healing magic closing the merchant's wounds anyway, a `RESOURCE` error and an M4 rule break in one sentence. The engine kept the state right; the narration did not follow it.
7. **D, a hostile keeper grateful.** The keeper is `hostile`. The narration gives him "relief and gratitude", more than one stance step away. D's narration call receives the facts only, not the state (CLAUDE.md §9.1, decision 12), and this turn's facts are about lamp oil. The narrator had no way to know the keeper's stance.
8. **C, an attack on a combatant already down (M4).** The turn before entry 4 in the same run: the encounter is over and the goblin unconscious, yet the narration has the player strike it. The draw allows one slot per turn, not per run, so entries 4 and 8 are neighbours. Read together, the narrator kept a fight going for two turns after the state ended it, with the state in its prompt and an instruction to check against it.
9. **D, a request no tool can honour (M2).** Ysolde fell to 0 HP two inputs earlier (encounter lost), and the script still says "one more bolt at the first wolf", since scripted inputs never adapt (decision 23). The model tried the fire bolt (`ENCOUNTER_OVER`), then healing herself and a perception check (`ACTOR_UNCONSCIOUS`). After the third rejection the turn failed: not advanced, logged and counted. This is the CONTROL path of CLAUDE.md §1.2 working as designed: the budget stopped the loop and nothing illegal reached the state. Some of the turn failures M2 counts are of this kind, the engine refusing a request the state makes impossible.
10. **D, a misreading that propagated (M3).** The player gives Tobin the blanket. The PC holds none, because at input 2 of this run "I bind the gash with a strip torn from my cloak" was executed as blanket −1. The correct call this time (blanket −1) was rejected with `NEGATIVE_QUANTITY`, and the retry made the call valid by adding a blanket instead. The narration follows the player and the state follows the model: the story has Tobin wrapped in the blanket, and the state has it back in Ysolde's pack. The same `modify_inventory(item_blanket, -1)` at input 2 appears in seed 2003 as well. CI's verdict is `WRONG_TOOL`; the draft said `WRONG_VALUE`.

### 3.2 What the ten show together

- **Grounding does not stop the narrator inventing** (1, 2, 4, 5). Every condition invents scenery, items or creatures. 10.1 measures it: `PHANTOM` is 23.7 to 33.1 per 100 turns in every condition (`docs/m1_rates.md` §3).
- **Telling the model the truth is not the same as being believed** (3, 4, 5, 8). D's narrator was handed the band, and B and C had the state with every HP and status. Each still narrated a combatant in the wrong condition. Unconscious combatants narrated as acting recur across entries 3, 4, 5 and 8.
- **D's narrator sees less than B's and C's** (2, 7). By design it receives the facts of the turn, not the state (decision 12). So it cannot know an NPC's stance or what is in scope unless the turn's facts mention it. Entry 7 is a `RELATION` error the narrator had no information to avoid, and D has the highest `RELATION` rate (2.1 per 100 turns against 0.2 to 0.9, `docs/m1_rates.md` §3). This is a reading for the discussion (11.4) to weigh, not a tested finding.
- **The retry loop can turn a refusal into an invented call** (2, 6, 10). In each, a rejection or the forced re-prompt is followed by a valid `modify_inventory` that adds an item the player never asked for. The validator accepts it, because it is legal. M3 finds the same pattern at scale: `INVENTED` is the most common unfaithful reason, 28 of 72, and 21 of the 25 invented `modify_inventory` turns added an item while the player rested, looked or talked (`docs/m3_annotation.md` §2). This is CLAUDE.md §7.2's silently misparsed intent, produced in part by the pressure to return a call.
- **A wrong call stays in the state** (10). A misread at input 2 caused a rejection and an invented call fifteen inputs later. The engine keeps the state legal, not true to the story.
- **The engine side held** (3, 6, 9). In every D entry the state stayed legal: no slot spent below zero, no action by an unconscious combatant, a failed turn counted rather than hidden. What went wrong in D went wrong in the model's two calls, the misread call and the unfaithful narration, which is what M2, M3 and M1 measure.

### 3.3 For 10.8 and the report

- Entries 3, 6 and 7 are the strongest condition D examples for the A-versus-D exhibit (10.8): each puts the facts the narrator was given next to what it wrote.
- Entry 6's annotation note asked SD to check whether the `RESOURCE` and `RULE` labels should both stand; SD accepted the draft unchanged. The labels are an AI draft accepted by SD (`docs/m1_annotation.md` §3), and the M3 verdict is CI's review of an AI draft (`docs/m3_annotation.md` §3). The report says so wherever it quotes an entry.
- The M3 slot was drawn from the four turns `docs/m3_annotation.md` §3 names, all of whose reason codes CI edited. It shows one real misread, not a typical one.
