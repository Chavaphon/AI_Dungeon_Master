# Audit-log turn-record format v0.9

WBS 2.4 · Owner: SD · Status: **draft, for the 2.6 joint review** · CLAUDE.md wins on any conflict.

The schema is `schemas/audit.schema.json` (JSON Schema draft 2020-12). It formalises CLAUDE.md §11. Tool calls, results, rolls and diff entries reuse `schemas/tools.schema.json` (WBS 2.3), so the audit log and the tool contract cannot disagree. `tests/test_audit_log.py` validates the examples, has one rejection test per rule, and replays the valid example: its `state_diff`, applied to `state_02_mid_combat.json`, reproduces `state_after_hash` exactly.

| Example | Shows |
|---|---|
| `audit_turn_valid.json` | Condition D. Lyra attacks the dodging rat (disadvantage) and hits. Then the rat's Dodge expires, both rats act, the round wraps and the turn comes back to Lyra. |
| `audit_turn_rejected.json` | Condition D. "I bash the rat with my torch": `NOT_A_WEAPON`, then unparseable output, then `NOT_A_WEAPON` again. The budget is exhausted, so `turn_failure: "precondition"`, and the state is unchanged. |
| `audit_turn_condition_b.json` | Condition B. One narration call, no tool phase, no state change. The narration diverges from the state on purpose (a rat "collapses" at 11 HP), as material for the rubric. |

A run's log is `runs/{condition}/{scenario_id}/{seed}.jsonl`, one record per line, in the order the turns were played. Upload it to shared storage when the run ends (README).

## 1. Fields

Everything from §11 is kept with the same name and meaning. Three fields are added (marked **new**), and `validation` holds more than the §11 example shows.

| Field | Holds |
|---|---|
| `run_id` | `{condition}_{scenario_id}_{seed}` (`docs/identifiers.md` §3) |
| `condition`, `scenario_id`, `seed` | The run's triple (invariant 4) |
| `turn_number` | The turn being played: the state's `turn_number` before the turn, plus 1. A failed turn does not advance (§7.1), so the next record has the same number. |
| `input_index` **new** | Which scripted input this turn answers, an index into the scenario's `scripted_inputs`. `null` in interactive play. This is what lines up the same stimulus across conditions, because `turn_number` stops matching after a failed turn. |
| `timestamp` | UTC, `YYYY-MM-DDTHH:MM:SSZ` |
| `player_input` | The raw text, unchanged (§7.2) |
| `model_calls` | Every model call of the turn: `phase` (`toolcall`, `narration` or `summary`), `attempt`, token counts, `latency_ms` and the raw output. M6 is computed from these. |
| `proposed_calls` | One entry per toolcall attempt: what the parser extracted, or `null` if the output could not be parsed |
| `validation` | One entry per toolcall attempt. A rejection is the full `result_rejected` envelope with its code and `valid_options`. A success is the full `result_ok` result, so the turn's `narration_facts` are in the log (the rubric scores against them). `{"ok": true, "tool": null}` is a `{"tool": null}` reply. `{"ok": false, "failure": "unparseable", "message": ...}` is a parse failure. |
| `executed_call` | The call that passed validation and ran, or `null` |
| `engine_steps` **new** | What the engine did outside the player's call, in order (§2 below) |
| `rolls` | Every roll of the turn, in the order rolled |
| `state_before_hash`, `state_after_hash` | `sha256:` of the state serialised as in `docs/conventions.md` §2 |
| `state_diff` | Every change of the turn, in the order applied (invariant 2) |
| `narration`, `narration_filtered` | The text shown to the player, and whether the safety filter changed it. The unfiltered text is the narration call's `raw_output`. |
| `turn_failure` | `null`, or `unparseable`, `schema`, `unknown_entity` or `precondition` (§7.1) |
| `narration_only` | The §7.1 fallback in condition D: the final reply was `{"tool": null}` |
| `k_used` | The number of verbatim turns in the prompt, after any reduction (§8) |
| `summary_regenerated`, `summary` **new** | Whether the rolling summary was regenerated this turn, and if so `{text, truncated}` (§8.1) |

## 2. Engine steps

2.3 says that turn advance, Dodge expiry and NPC turns are engine steps after the tool, recorded in the turn record rather than the tool's `state_diff`. `engine_steps` is where they go. Each step has a `when`, `before_call` or `after_call`:

| Step | When | Records |
|---|---|---|
| `encounter_start` | before | Initiative rolls; `encounter_active`, `initiative_order`, `round_number`, `active_combatant_id` (scenario `encounters`, WBS 2.5) |
| `dodge_expiry` | after | `dodging` cleared at the start of that combatant's turn (§4.5) |
| `npc_action` | after | The engine's call for an NPC and its full `result_ok`, with its own diff and rolls |
| `initiative_advance` | after | `active_combatant_id`, and `round_number` when the order wraps (§4.4) |
| `encounter_end` | after | `encounter_active`, `encounter_outcome` (§4.8) |
| `turn_increment` | after | `turn_number` |

The top-level `state_diff` is the `before_call` steps, then the executed result's diff, then the `after_call` steps, concatenated in that order. `rolls` follows the same rule. So the top level is the whole turn, and the parts say where each change came from.

## 3. Rules JSON Schema cannot express

`record_errors` in the test file checks these.

- `run_id` equals `{condition}_{scenario_id}_{seed}`.
- Conditions A–C have no tool phase: no toolcall calls, empty `proposed_calls`, `validation` and `engine_steps`, no `executed_call`, no state change, no `turn_failure`.
- Toolcall attempts are numbered 1, 2, 3, at most `1 + retry budget`, and are aligned one-to-one with `proposed_calls` and `validation`. A `null` proposed call is a parse failure, and a `{"tool": null}` call is validated as `no_tool`.
- The loop stops at the first success. Only the last attempt can be a successful call. At most one `{"tool": null}` reply is followed by a re-prompt (§7.1).
- `executed_call` is the last proposed call if and only if that attempt succeeded.
- `turn_failure` is set if and only if all three attempts failed. Its kind follows the last attempt (`SCHEMA_VIOLATION` → `schema`, `UNKNOWN_ENTITY` → `unknown_entity`, unparseable → `unparseable`, any other code → `precondition`). A failed turn changes no state and has no narration call.
- `narration_only` is true exactly when a condition D turn ends on `{"tool": null}`.
- `state_diff` and `rolls` are the steps and the result in order (§2). The hashes are equal exactly when `state_diff` is empty.
- One narration call per turn, none on a failed turn. `summary_regenerated` matches the summary call and the `summary` field.

## 4. Open points for the 2.6 review

1. **NPC actions are not narrated.** The D narration call sees only the player's `narration_facts` (§9.1). In the valid example, a rat bites Lyra for 5 HP and the narration cannot mention it. Options: pass the NPC actions' facts to the narration call as well, or narrate them in a separate call. Either changes the frozen `d_narration.txt` input.
2. **How NPCs choose their actions** (also 2.5 open point 3). The example's rat attacks are illustrative. The audit log can record any policy, but replay needs one fixed policy.
3. **Scripted runs after a failed turn.** A scripted run cannot "ask the player to rephrase". Proposal: move on to the next input. The failed record keeps its `input_index`, and the next record has `input_index + 1` and the same `turn_number`.
4. **What A–C hash.** The proposal here: `state_before_hash` and `state_after_hash` are both the ground-truth state for that input from the offline replay (§9). It's the state injected in B and C, and the one the narration is scored against.
5. **Byte-identical replay** (`docs/conventions.md` §3, point 1). `timestamp` and `latency_ms` differ on every run. The replay test compares everything else.
