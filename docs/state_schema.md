# State schema v0.9

WBS 2.1 · Owner: SS · Status: **draft, for the 2.6 joint review** · CLAUDE.md wins on any conflict.

The schema is `schemas/state.schema.json` (JSON Schema draft 2020-12). It formalises CLAUDE.md §5, with three hand-written examples in `schemas/examples/`. `tests/test_state_schema.py` validates the examples and has one rejection test per rule.

| Example | Shows |
|---|---|
| `state_01_exploration.json` | Scenario start: no encounter, quest not started, empty relationship history |
| `state_02_mid_combat.json` | The CLAUDE.md §5 example, plus a hostile rat that is dodging |
| `state_03_after_victory.json` | Encounter resolved: both hostiles unconscious, slot spent, quest completed, item at quantity 0 |

## 1. What the schema enforces

- Every required key from §5, and no others (`additionalProperties: false` throughout; §4 says "implement exactly this, no more").
- The §5.2 enumerations and the §5.1 id prefixes, on both map keys and id fields. A player character must have a `pc_` id, everyone else `npc_`. The exact id and `scenario_id` patterns are in `docs/identifiers.md`.
- Ability scores 1–20, `max_hp >= 1`, `current_hp >= 0`, spell slots and inventory quantities `>= 0`, justification of at least 10 characters (§4.1, §6.1).
- `status` is `unconscious` exactly when `current_hp` is 0 (§4.8).
- Weapons carry `attack_bonus`, `damage_dice` and `damage_bonus`; non-weapons carry none of them. `damage_dice` is `XdY` from §4.2 *without* `+Z`, because the modifier is `damage_bonus` and a critical doubles only the dice (§4.5).
- During an encounter: an `active_combatant_id`, a non-empty `initiative_order`, `round_number >= 1` and no outcome. Outside one: `active_combatant_id` is null.
- A set `encounter_outcome` means the encounter is no longer active (§4.8).

## 2. Gaps in CLAUDE.md filled here

Decided by SS on 2026-10-01; see `docs/decisions.md`.

- **Non-casters.** `spell_attack_bonus`, `spellcasting_modifier` and `spell_slots_1` are required on every combatant. A non-caster has all three `null`; a caster has all three as integers. Mixing is rejected.
- **Outside an encounter.** `encounter_active: false`, `initiative_order: []`, `active_combatant_id: null`, `round_number: 0` until the first encounter starts. `turn_number` starts at 0.
- **Quest stages.** A `not_started` quest is at stage 0. `start` moves it to stage 1, and every other state has `stage >= 1`.

## 3. Rules JSON Schema cannot express

These rules involve comparing two values, so JSON Schema can't express them. `cross_field_errors` in the test file checks them for the examples. The runtime check belongs to WBS 5.4, the post-write invariant assertion.

- `current_hp <= max_hp` (invariant 5).
- Each map key equals the entity's own id field.
- An NPC in both `combatants` and `npc_relationships` has the same `display_name` in both (`docs/identifiers.md` §1, rule 5).
- Exactly one player character (§14).
- `initiative_order` names existing combatants; `active_combatant_id` is in it.
- Inventory owners are combatants; inventory items are in `item_definitions`.
- Relationship history is a chain of one-step changes ending at the current `stance` (§5.2).
- `stage <= max_stage`.
- `victory` means every hostile is unconscious; `defeat` means the player character is (§4.8).

## 4. Open points for the 2.6 review

1. **A non-caster casting Fire Bolt.** §6.3 has no rejection code for "this combatant cannot cast". Raise with task 2.3.
2. **State after an encounter ends.** Example 3 clears `initiative_order` and keeps the last `round_number`. CLAUDE.md does not say which. The schema allows either.
3. **`schema_version`.** It is `"1.0"`, as in CLAUDE.md §5, even though this draft of the schema is v0.9. The draft becomes v1.0 at the 2.7 tag.
