# Scenario definition format v1.0

WBS 2.5 · Owner: SD · Status: **v1.0, frozen at tag `spec-v1.0`** (changes need a `docs/decisions.md` entry) · CLAUDE.md wins on any conflict.

The schema is `schemas/scenario.schema.json` (JSON Schema draft 2020-12). It formalises CLAUDE.md §12 and reuses the entity definitions in `schemas/state.schema.json`, so a combatant, item, relationship or quest is valid in a scenario exactly when it is valid in a state. `schemas/examples/scenario_s00_example.json` is a worked example. `tests/test_scenario_schema.py` validates it, validates every file in `scenarios/`, and has one rejection test per rule.

## 1. Top-level fields

| Field | Holds |
|---|---|
| `schema_version` | `"1.0"`, as in the state schema |
| `scenario_id` | `s01`–`s12` or `long01`–`long04`, then a name: `s01_cellar`. The pattern, the file name `scenarios/<scenario_id>.json` and the unique series number are the namespace rules in `docs/identifiers.md` §2. |
| `display_name`, `opening_narration` | Shown to the player before turn 1 |
| `locations` | Places the narration may name without being flagged `PHANTOM` (§10.1). Display names only, since there is no location id prefix (§5.1). This answers open point 2 in `docs/identifiers.md` §4. |
| `initial_state` | The **entities** and **starting state**: `combatants`, `inventory`, `item_definitions`, `npc_relationships`, `quests`, each exactly as in the state schema |
| `encounters` | When each encounter starts and who is in it (§2 below) |
| `scripted_inputs` | The **fixed player inputs**, each with its expected call and any **DC** (§3 below) |
| `notes_for_annotators` | Free text for the human pass |

## 2. Starting state and encounters

`initial_state` does not carry run-level fields. When a run starts, the loader adds them: `seed` from the run, `turn_number: 0`, `round_number: 0`, `encounter_active: false`, `initiative_order: []`, `active_combatant_id: null`, `encounter_outcome: null`. The result must be a valid state. `initial_game_state` in the test file is the reference version; the runtime loader belongs to WBS 4.1.

An encounter is `{"before_input": n, "combatant_ids": [...]}`. Initiative (§4.4) is rolled for those combatants just before `scripted_inputs[n]` is processed. There is no tool that starts an encounter, so the scenario has to say when one begins.

## 3. Scripted inputs and DCs

Each input is an object, not a bare string:

```json
{
  "text": "I hold my torch up and check if anything is hidden behind the barrels",
  "expected_call": {
    "tool": "skill_check",
    "arguments": {"actor_id": "pc_lyra", "skill": "perception", "dc": 12}
  },
  "check_advantage": "advantage"
}
```

- `expected_call` is a full tool call with the §6.1 arguments, or `null` for a narration-only input. Conditions A–C are scored against the state reached by replaying the scripted inputs through the engine offline (§9), and a tool name alone cannot be replayed, so the scenario carries the whole call. It is still **not** used to grade the model (§12).
- The **DC** of a skill check is the `dc` argument of its `expected_call`, an integer from 5 to 25.
- `check_advantage` (`"advantage"` or `"disadvantage"`) is how the scenario grants advantage on a skill check (§4.3). It is only allowed on a `skill_check` input. Leaving it out means a normal roll.

## 4. Rules JSON Schema cannot express

These compare values across the file. `scenario_errors` in the test file checks them.

- The turn-0 state built from `initial_state` passes the state schema and its cross-field checks (`cross_field_errors`).
- Encounters are in input order, start before the last input, name existing combatants, include the player character and at least one hostile.
- Every id in an `expected_call` exists in `initial_state`. The acting combatant is the player character, because scripted inputs are what the player types.
- No combat action (`attack`, `cast_spell`, `dodge`) comes before the first encounter starts.
- Coverage (§12): the expected calls include at least two of an inventory change, a quest transition and a relationship change; long scenarios need all three.

The 25- and 50-turn lengths in §12 are targets, so the schema does not enforce them.

## 5. Open points for the 2.6 review

All of these were settled by the 2026-10-03 WBS 2.6 entries in `docs/decisions.md` and are folded into CLAUDE.md at v1.0. They are kept here as the record of what was asked.

1. **Who sets the DC in condition D.** The model proposes `dc` in its `skill_check` call, but A–C are scored against the scenario's DC. If the engine uses the model's DC, condition D can end up in a different state from the ground truth even when the narration is perfect. Proposal: the engine uses the scenario's `dc` and `check_advantage` for that input and logs the model's proposed value. This touches task 2.3.
2. **Encounters that run longer or shorter than the script.** Whether the rats fall after two attacks depends on the seed. Later inputs may then be rejected (`TARGET_UNCONSCIOUS`, `ENCOUNTER_OVER`), or the encounter may still be running when a non-combat input arrives. Proposal: accept this. Every condition receives the same inputs, rejections are logged, and the replay ground truth uses the same seed.
3. **How engine-controlled NPCs choose their actions.** CLAUDE.md §14 says everyone except the PC is engine-controlled, but not how. Offline replay needs that policy. It is not a scenario field. It needs an owner in the engine work package.
4. **CLAUDE.md §12 needs updating at the freeze.** It shows `scripted_inputs` as strings with a separate `expected_tools` list, and `initial_state` as "a complete GameState minus turn/round fields". Both change in this format.
