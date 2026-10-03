# Tool contract v1.0

WBS 2.3 · Owner: CI · Status: **v1.0, frozen at tag `spec-v1.0`** (changes need a `docs/decisions.md` entry) · CLAUDE.md wins on any conflict.

The contract is `schemas/tools.schema.json` (JSON Schema draft 2020-12). It formalises CLAUDE.md §6. Two entry points:

- `#/$defs/proposed_call`: what model call 1 must emit, `{"tool": ..., "arguments": {...}}` or `{"tool": null}`.
- `#/$defs/tool_result`: what the engine returns, an `ok: true` result or an `ok: false` rejection (§6.2).

Examples are in `schemas/examples/` (`toolcall_*.json`, one per tool plus `null`; `result_*.json`, one per tool, both spells, and the §6.2 rejection). `tests/test_tool_contract.py` validates them, has one rejection test per rule, and checks the schema against the tables in CLAUDE.md §6.1 and §6.3 and the matrix in §3 below.

## 1. Validation order

The validator runs these checks in this order and returns the **first** failure. A fixed order makes every rejection deterministic, so the 5.2 tests can name exactly one code per case. Within a step, arguments are checked in signature order.

| Step | Codes | Checked against |
|---|---|---|
| 1. Shape | `SCHEMA_VIOLATION` | `args_<tool>` in the schema: unknown tool, missing, unknown or wrongly typed argument, `direction` or `transition` outside its enum, `delta` of 0 |
| 2. Existence | `UNKNOWN_ENTITY`, `ITEM_NOT_DEFINED`, `UNKNOWN_QUEST`, `SPELL_NOT_SUPPORTED` | Ids in the current state; `spell_id` against the two spells |
| 3. Argument values | `SKILL_NOT_SUPPORTED`, `DC_OUT_OF_RANGE`, `MISSING_JUSTIFICATION` | §4.7, §6.1 |
| 4. Encounter | `ENCOUNTER_OVER`, `NOT_YOUR_TURN` | `encounter_active`, `active_combatant_id` |
| 5. Actor | `ACTOR_UNCONSCIOUS`, `NOT_A_CASTER`, `NO_SPELL_SLOT`, `NOT_A_WEAPON`, `WEAPON_NOT_IN_INVENTORY` | The actor's combatant record and inventory |
| 6. Target and effect | `TARGET_UNCONSCIOUS`, `NEGATIVE_QUANTITY`, `RELATIONSHIP_STEP_TOO_LARGE`, `ILLEGAL_QUEST_TRANSITION` | The target, or the value the change would produce |

The argument schemas check **shape only**. Ids, `spell_id`, `skill`, `dc` and `justification` are plain strings and integers in the schema, so a bad value gets its own code and `valid_options` instead of a generic `SCHEMA_VIOLATION`. A weak model recovers better from "`npc_rat_03` does not exist, try one of these" than from "pattern mismatch".

## 2. The seven tools

"Uses the action" means a successful call ends the actor's turn and the engine advances initiative (§4.4). Turn advance, Dodge expiry and NPC turns are engine steps after the tool. They appear in the turn's audit record (§11), not in the tool's `state_diff`.

### `attack(attacker_id, target_id, weapon_id)`

- **Codes, in order:** `SCHEMA_VIOLATION`, `UNKNOWN_ENTITY` (any of the three ids; `weapon_id` is looked up in `item_definitions`), `ENCOUNTER_OVER`, `NOT_YOUR_TURN`, `ACTOR_UNCONSCIOUS`, `NOT_A_WEAPON`, `WEAPON_NOT_IN_INVENTORY` (quantity 0 counts as not held), `TARGET_UNCONSCIOUS`.
- **Effect:** §4.5. `combatants.<target>.current_hp`, and `.status` if it reaches 0.
- **`narration_facts`:** `attacker`, `target`, `weapon`, `hit`, `critical`, `attack_roll` (the total), `advantage_mode`, `target_ac`, `damage` (0 on a miss), `target_hp_before`, `target_hp_after`, `target_hp_max`, `target_hp_band`, `target_status`.
- **Rolls:** the attack roll, then the damage roll if it hit.
- **Uses the action:** yes.

### `cast_spell(caster_id, spell_id, target_id)`

- **Codes:** `SCHEMA_VIOLATION`, `UNKNOWN_ENTITY` (caster, target), `SPELL_NOT_SUPPORTED`, `ENCOUNTER_OVER` (Fire Bolt only), `NOT_YOUR_TURN`, `ACTOR_UNCONSCIOUS`, `NOT_A_CASTER`, `NO_SPELL_SLOT` (Cure Wounds only), `TARGET_UNCONSCIOUS` (Fire Bolt only).
- **Effect:** §4.6. Fire Bolt: as `attack`. Cure Wounds: `current_hp`, `status` on revival, and the caster's `spell_slots_1`.
- **`narration_facts`:** `caster`, `target`, `spell` (`"fire bolt"` or `"cure wounds"`), then:
  - Fire Bolt: the same roll and HP fields as `attack`.
  - Cure Wounds: `healed_rolled`, `healed_applied`, `target_hp_before`, `target_hp_after`, `target_hp_max`, `target_hp_band`, `target_status`, `revived`, `slots_remaining`.
- **Uses the action:** yes. Cure Wounds is legal outside an encounter, to heal between fights.

### `dodge(actor_id)`

- **Codes:** `SCHEMA_VIOLATION`, `UNKNOWN_ENTITY`, `ENCOUNTER_OVER`, `NOT_YOUR_TURN`, `ACTOR_UNCONSCIOUS`.
- **Effect:** `combatants.<actor>.dodging` to `true` (§4.5).
- **`narration_facts`:** `actor`.
- **Uses the action:** yes.

### `skill_check(actor_id, skill, dc)`

- **Codes:** `SCHEMA_VIOLATION`, `UNKNOWN_ENTITY`, `SKILL_NOT_SUPPORTED`, `DC_OUT_OF_RANGE`, `NOT_YOUR_TURN`, `ACTOR_UNCONSCIOUS`.
- **Effect:** none. A roll only (§4.7). Advantage or disadvantage comes from the scenario (`check_advantage`, WBS 2.5), not from an argument.
- **`narration_facts`:** `actor`, `skill`, `dc`, `check_total`, `advantage_mode`, `success`.
- **Uses the action:** no (§4.7). Legal outside an encounter.

### `modify_inventory(actor_id, item_id, delta)`

- **Codes:** `SCHEMA_VIOLATION`, `UNKNOWN_ENTITY` (actor), `ITEM_NOT_DEFINED`, `NOT_YOUR_TURN`, `NEGATIVE_QUANTITY`.
- **Effect:** `inventory.<actor>.<item>`. A quantity that reaches 0 keeps its key (WBS 2.2). A new key is added at `delta`.
- **`narration_facts`:** `actor`, `item`, `delta`, `quantity_before`, `quantity_after`.
- **Uses the action:** no. Legal outside an encounter. Here `actor_id` is the inventory's **owner**, not someone acting, so `ACTOR_UNCONSCIOUS` does not apply. Otherwise the PC could not loot an unconscious rat after a victory.

### `update_npc_relationship(npc_id, direction, justification)`

- **Codes:** `SCHEMA_VIOLATION`, `UNKNOWN_ENTITY` (`npc_id` not in `npc_relationships`), `MISSING_JUSTIFICATION`, `RELATIONSHIP_STEP_TOO_LARGE` (moving past either end of the ladder).
- **Effect:** `npc_relationships.<npc>.stance`, plus a new `history` entry `{turn, from, to, justification}` with `turn = turn_number`.
- **`narration_facts`:** `npc`, `stance_before`, `stance_after`, `justification`.
- **Uses the action:** no. No turn check: there is no actor.

### `update_quest(quest_id, transition)`

- **Codes:** `SCHEMA_VIOLATION`, `UNKNOWN_QUEST`, `ILLEGAL_QUEST_TRANSITION`.
- **Effect** (§5.2):

  | Transition | From | To |
  |---|---|---|
  | `start` | `not_started`, stage 0 | `active`, stage 1 |
  | `advance` | `active`, `stage < max_stage` | `active`, stage + 1 |
  | `complete` | `active` | `completed`, stage unchanged |
  | `fail` | `active` | `failed`, stage unchanged |

  Anything else, including `advance` at `max_stage`, is `ILLEGAL_QUEST_TRANSITION`.
- **`narration_facts`:** `quest`, `transition`, `state_before`, `state_after`, `stage_before`, `stage_after`, `max_stage`.
- **Uses the action:** no. No turn check.

`narration_facts` always uses `display_name`s, never ids, because it is the only thing the narration call sees (§9.1). Every fact that touches HP carries the engine-computed `target_hp_band` (§10.2) and `target_status`.

## 3. Tool × code matrix

Rows are in validation order. Every code is raised by at least one tool, which is what makes 5.2's "every code reachable by a test" possible.

| Code | attack | cast_spell | dodge | skill_check | modify_inventory | update_npc_relationship | update_quest |
|---|---|---|---|---|---|---|---|
| `SCHEMA_VIOLATION` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `UNKNOWN_ENTITY` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | |
| `ITEM_NOT_DEFINED` | | | | | ✓ | | |
| `UNKNOWN_QUEST` | | | | | | | ✓ |
| `SPELL_NOT_SUPPORTED` | | ✓ | | | | | |
| `SKILL_NOT_SUPPORTED` | | | | ✓ | | | |
| `DC_OUT_OF_RANGE` | | | | ✓ | | | |
| `MISSING_JUSTIFICATION` | | | | | | ✓ | |
| `ENCOUNTER_OVER` | ✓ | ✓ | ✓ | | | | |
| `NOT_YOUR_TURN` | ✓ | ✓ | ✓ | ✓ | ✓ | | |
| `ACTOR_UNCONSCIOUS` | ✓ | ✓ | ✓ | ✓ | | | |
| `NOT_A_CASTER` | | ✓ | | | | | |
| `NO_SPELL_SLOT` | | ✓ | | | | | |
| `NOT_A_WEAPON` | ✓ | | | | | | |
| `WEAPON_NOT_IN_INVENTORY` | ✓ | | | | | | |
| `TARGET_UNCONSCIOUS` | ✓ | ✓ | | | | | |
| `NEGATIVE_QUANTITY` | | | | | ✓ | | |
| `RELATIONSHIP_STEP_TOO_LARGE` | | | | | | ✓ | |
| `ILLEGAL_QUEST_TRANSITION` | | | | | | | ✓ |

## 4. Rejections and `valid_options`

Every rejection is `{ok: false, tool, rejection_code, message, valid_options, retry_allowed}`. `tool` echoes the proposed name, even an unknown one. `retry_allowed` is always `true`: the retry budget belongs to the turn loop (§7.1), not to the engine. `valid_options` maps an argument name to a list of values that would have passed this check. It is `{}` when no list helps.

| Code | `valid_options` |
|---|---|
| `SCHEMA_VIOLATION` | Unknown tool: `{"tool": [the seven]}`. Bad enum: `{"<arg>": [allowed values]}`. Missing, extra or wrongly typed argument: `{"arguments": [expected names]}` |
| `UNKNOWN_ENTITY` | `{"<arg>": [ids of that kind in state]}`; for `weapon_id`, the weapons the attacker holds |
| `ITEM_NOT_DEFINED` | `{"item_id": [item_definitions keys]}` |
| `UNKNOWN_QUEST` | `{"quest_id": [quest keys]}` |
| `SPELL_NOT_SUPPORTED` | `{"spell_id": ["spell_fire_bolt", "spell_cure_wounds"]}` |
| `SKILL_NOT_SUPPORTED` | `{"skill": ["strength", "perception", "stealth"]}` |
| `DC_OUT_OF_RANGE` | `{"dc": [5, 25]}`, the bounds |
| `MISSING_JUSTIFICATION` | `{}` |
| `ENCOUNTER_OVER` | `{"tool": ["cast_spell", "skill_check", "modify_inventory", "update_npc_relationship", "update_quest"], "spell_id": ["spell_cure_wounds"]}` |
| `NOT_YOUR_TURN` | `{"<actor arg>": [active_combatant_id]}` |
| `ACTOR_UNCONSCIOUS` | `{"<actor arg>": [conscious combatants]}`; during an encounter, just the active one |
| `NOT_A_CASTER` | `{"caster_id": [conscious combatants with spell fields]}` |
| `NO_SPELL_SLOT` | `{"spell_id": ["spell_fire_bolt"]}` |
| `NOT_A_WEAPON`, `WEAPON_NOT_IN_INVENTORY` | `{"weapon_id": [weapons the attacker holds]}` |
| `TARGET_UNCONSCIOUS` | `{"target_id": [conscious combatants of another faction than the attacker]}` |
| `NEGATIVE_QUANTITY` | `{"delta": [-held]}`, the most negative legal delta |
| `RELATIONSHIP_STEP_TOO_LARGE` | `{"direction": [the other direction]}` |
| `ILLEGAL_QUEST_TRANSITION` | `{"transition": [transitions legal from the current state]}` |

## 5. Model-facing tool definitions

The tool list in the condition D prompt (§8 step 2, WBS 6.2) is derived from the schema, never written by hand: one `{name, description, parameters}` per tool, where `parameters` is `args_<tool>` without its top-level `description`. `model_tool_definitions()` in the test file is the reference derivation. The 3.3 micro-benchmark uses the same list.

## 6. Gaps in CLAUDE.md filled here

Decided by CI on 2026-10-02; see `docs/decisions.md`.

1. **`NOT_A_CASTER`**, a new code: `cast_spell` by a combatant whose spell fields are `null` (raised by 2.1). The code count is now 19.
2. **`ENCOUNTER_OVER` widened** to "combat action with no active encounter", whether the first one has not started or the last one has resolved. Cure Wounds is exempt.
3. **The turn action.** Only `attack`, `cast_spell` and `dodge` use it. The other four do not end the turn. `NOT_YOUR_TURN` still applies to `skill_check` and `modify_inventory` during an encounter.
4. **The single source** is `schemas/tools.schema.json`. The 5.1 validator and the 6.2 prompt both load it.
5. **Validation order** as in §1, and argument schemas that check shape only.
6. **`narration_facts` for all seven tools** (§2). Two fields are added to the §6.2 attack example: `weapon`, so the narration does not invent one, and `advantage_mode`, so it can describe a dodging target.
7. **Small cases:** `delta` of 0 is a `SCHEMA_VIOLATION`. `advance` at `max_stage` is illegal. For `modify_inventory`, `actor_id` is the owner and `ACTOR_UNCONSCIOUS` does not apply. `retry_allowed` is always `true`.

## 7. Open points for the 2.6 review

All of these were settled by the 2026-10-03 WBS 2.6 entries in `docs/decisions.md` and are folded into CLAUDE.md at v1.0. They are kept here as the record of what was asked.

1. **CLAUDE.md §6.2 example band is wrong.** It gives 4 of 11 HP as `badly_hurt`, but 4/11 = 0.36 > 0.35 is `wounded` under §10.2. `result_attack.json` uses `wounded`. Fix §6.2 at the freeze; a test marks the spot.
2. **Self-targeting.** Nothing stops an attack or Fire Bolt on yourself or an ally. There is no code for it, so it is legal for now.
3. **Transfers.** Taking the guard's keys is two inventory changes, but a turn has one tool call. Either allow a second call, or add a `from_id` to `modify_inventory`.
4. **Who sets the DC in condition D.** §6.1 makes `dc` the model's argument; the scenario also holds one (2.5 open point).
5. **CLAUDE.md text at the freeze:** add `NOT_A_CASTER` to §6.3, widen `ENCOUNTER_OVER` in §6.3 and §4.8, add `weapon` and `advantage_mode` to the §6.2 example, and say in §4.5 which tools use the action.
