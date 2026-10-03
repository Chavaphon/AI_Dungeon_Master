# Identifier conventions and scenario-scoped namespace

WBS 2.2 · Owner: SS · Status: **v1.0, frozen at tag `spec-v1.0`** (changes need a `docs/decisions.md` entry) · CLAUDE.md wins on any conflict.

This formalises CLAUDE.md §5.1. The patterns are enforced by `schemas/state.schema.json`, and `tests/test_identifiers.py` tests them along with the scenario-level rules.

## 1. Entity ids

An entity id is `<kind>_<name>`:

| Kind | Prefix | Names | Example |
|---|---|---|---|
| Player character | `pc_` | `combatants` key with `is_player_character: true` | `pc_lyra` |
| Non-player character | `npc_` | every other `combatants` key, and every `npc_relationships` key | `npc_rat_01`, `npc_keeper` |
| Item | `item_` | `item_definitions` key, `inventory` inner key, `weapon_id` | `item_short_sword` |
| Quest | `quest_` | `quests` key | `quest_missing_ledger` |
| Spell | `spell_` | `spell_id` in `cast_spell` only | `spell_fire_bolt` |

Rules:

1. **Format.** `<name>` is one or more lowercase ASCII words of `[a-z0-9]`, joined by single underscores. The full pattern is `^<prefix>_[a-z0-9]+(_[a-z0-9]+)*$`. No uppercase, hyphens, double underscores, or a trailing underscore. `npc_rat__01`, `npc_rat_` and `npc_Rat` are all rejected.
2. **These five prefixes only** (§5.1). The divergence checker reads the prefix to decide what kind of entity a mention is. Apart from the prefix, an id has no meaning (`docs/conventions.md` §2).
3. **Several of the same kind** get a two-digit suffix starting at `01`: `npc_rat_01`, `npc_rat_02`. A unique entity has no suffix: `npc_keeper`.
4. **Unique within a scenario.** Each kind has its own map in the state, so a map key cannot repeat. The prefixes don't overlap, so an id of one kind can never equal an id of another kind.
5. **One id, one entity.** If an NPC appears in both `combatants` and `npc_relationships`, both entries use the same `npc_` id and the same `display_name`.
6. **Ids are fixed when the scenario loads.** No tool creates, renames or deletes an entity. `modify_inventory` only changes a quantity, and an item at quantity 0 keeps its key. So the set of ids in a run is exactly the set in the scenario's `initial_state`, and a run cannot create a collision partway through.
7. **Spell ids belong to the engine, not to scenarios.** Exactly two exist: `spell_fire_bolt` and `spell_cure_wounds` (§4.6). The state has no spell map, so a scenario cannot define a `spell_` id.
8. **Display names don't have to be unique.** Two rats can both be "giant rat". The id tells them apart, and the checker matches display names only to decide whether a mention is in scope.

## 2. Scenario ids: the namespace

An entity id is only unique **inside its scenario**. Two scenarios can both contain `npc_rat_01`, and these are different entities. The scenario id is the namespace that keeps them apart.

1. **Format.** `^(s|long)[0-9]{2}_[a-z0-9]+(_[a-z0-9]+)*$`. Short scenarios use `s01` to `s12`, and long sessions use `long01` to `long04` (CLAUDE.md §3, §12). Example: `s01_cellar`.
2. **The series number is unique across the suite.** `s01_cellar` and `s01_crypt` cannot both exist, so a scenario can be referred to unambiguously by its number alone.
3. **The file is named after its id.** The scenario with `scenario_id: "s01_cellar"` lives at `scenarios/s01_cellar.json`. Two files can't share a path, so two scenarios can't share an id.
4. **The state carries its scenario.** `scenario_id` in the state must equal the `scenario_id` of the scenario it was loaded from.

## 3. Resolving and qualifying ids

- **Inside a run, ids are always local.** Prompts, tool calls, `narration_facts`, `state_diff` paths and the validator use bare ids such as `npc_rat_01`. An id is looked up only in the current run's state. Anything not found there is `UNKNOWN_ENTITY`, even if another scenario defines it.
- **Outside a run, ids are always qualified.** Any artefact that combines several scenarios (checker output in `results/`, annotation sheets, analysis tables, the failure catalogue) writes an entity as `<scenario_id>/<entity_id>`, for example `s01_cellar/npc_rat_01`. It never uses the bare id as a key.
- **Runs are already qualified by their path.** An audit log is at `runs/{condition}/{scenario_id}/{seed}.jsonl`, and its `run_id` is `{condition}_{scenario_id}_{seed}`. The condition is one letter, and the scenario id contains no uppercase, so a `run_id` splits back into its parts in only one way.

These rules make a collision across scenarios impossible. Inside a run only one scenario is in scope (§3). Outside a run every id carries its scenario (§3). Scenario ids are unique across the suite (§2).

## 4. Open points for the 2.6 review

All of these were settled by the 2026-10-03 WBS 2.6 entries in `docs/decisions.md` and are folded into CLAUDE.md at v1.0. They are kept here as the record of what was asked.

1. **Scenario file format (WBS 2.5).** The rules in §2 assume a top-level `scenario_id` and a `scenarios/<scenario_id>.json` file name, as in CLAUDE.md §12. `tests/test_identifiers.py` checks every file in `scenarios/` against them. It passes trivially until the first scenario is committed.
2. **Ids outside the state.** A scenario can name locations or entities that are not state entities, for example in `opening_narration`. These have no id and no prefix, and the PHANTOM check treats them as in scope only through the scenario definition. Task 2.5 should say whether such names are listed explicitly.
