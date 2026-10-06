# Decision log

WBS 1.7 · Owner: CI · One file, dated entries · CLAUDE.md wins on any conflict.

This is the record of every decision that changes, overrides or adds to CLAUDE.md, and of every weekly checkpoint. If a choice is not written here, it was not made.

## 1. When an entry is required

- Any change to CLAUDE.md, including overruling a decision in §15 or answering a question in §16.
- A new dependency (§2.1).
- A new or changed rejection code (§6.3).
- Any change to a frozen prompt template in `config/prompts/` (§9.1).
- Any change to a specification after the v1.0 tag (WBS 2.7).
- Freezing `config/model.json` after the benchmark (§2.2).
- A replaced audit log or run (README).
- A change to repository process that affects everyone: CI, branch protection, shared storage.
- Every weekly checkpoint, including one that was skipped (`docs/checkpoint.md` §3 has the template).

## 2. Rules

- Entries are in date order, oldest first. Add new entries at the bottom.
- Never edit or delete a past entry. To reverse a decision, add a new entry that names the one it supersedes.
- Use the date the decision was made, not the date it was written up.
- Say what changed in the repository, with paths, so a reader can check it.

## 3. Entry template

```markdown
## YYYY-MM-DD — <short title> (WBS x.y)

Decided by: <initials> · Supersedes: <entry title, or none>

**Decision:** <what was decided>
**Reason:** <why>
**Changed:** <files, settings or CLAUDE.md sections affected, or "nothing">
```

Checkpoint entries use the template in `docs/checkpoint.md` §3 instead.

---

## 2026-09-30 — CI pipeline and required status check on main (WBS 1.3)

Decided by: CI · Supersedes: none

**Decision:** Every push and every pull request into `main` runs one GitHub Actions job, `test`, on Python 3.11. It runs `ruff check .`, `ruff format --check .` and `pytest -q`, the quality gates in CLAUDE.md §2. `test` is a required status check on `main`, and branches must be up to date with `main` before merging. The existing rules are unchanged: one approval, stale approvals dismissed, conversations resolved, no bypass for administrators.
**Reason:** WBS 1.3 requires a failing test to block merge. Branch protection from WBS 1.1 had no required status checks, so a red run could still be merged.
**Changed:** `.github/workflows/ci.yml` added. Branch protection on `main` now requires `test`. Renaming the job breaks this check; update branch protection in the same change.

## 2026-09-30 — GitHub issues replace TASK_CHECKLIST.md as the task tracker (WBS 12)

Decided by: CI · Supersedes: none

**Decision:** Every WBS task in `TASK_CHECKLIST.md` (116 tasks) is now a GitHub issue titled `[WBS x.y] <task>`. Each issue has its `wp-NN-*` label, its owner as assignee (CI = Chavaphon, SS = b0nusshyn, SD = BelleYalu, ALL = all three), and one of seven weekly milestones, `W1` to `W7`, due on the last day of that week. Task dependencies are recorded as "blocked by" links between issues. Tasks 1.1 to 1.7, already done, were imported and closed with links to their pull requests. From now on, task status lives only in the issues. `TASK_CHECKLIST.md` is a read-only reference for the schedule, gates, deliverables and risk register, and its ticks are frozen as of this date. The WBS workbook is also read-only: its Status column and effort recalculation are no longer maintained.
**Reason:** Issues make it easier to assign, filter and link tasks than a markdown checklist does, and one tracker cannot drift out of sync the way two can.
**Changed:** CLAUDE.md §2.3 added. `TASK_CHECKLIST.md` header and footer now mark it read-only. The last checklist item in `.github/pull_request_template.md` now asks for `Closes #N`. The description in `.github/ISSUE_TEMPLATE/task.yml` now says it is for new or split tasks only.

## 2026-10-01 — State schema v0.9: gaps in CLAUDE.md §5 (WBS 2.1)

Decided by: SS · Supersedes: none

**Decision:** Three points that CLAUDE.md §5 leaves open are fixed for the v0.9 state schema. (1) Every combatant has `spell_attack_bonus`, `spellcasting_modifier` and `spell_slots_1`. A non-caster has all three as `null`, which means it cannot cast. (2) Outside an encounter, `initiative_order` is `[]` and `active_combatant_id` is `null`. `round_number` is 0 until the first encounter starts, and `turn_number` starts at 0. (3) A `not_started` quest is at stage 0, `start` moves it to stage 1, and every other quest state has `stage >= 1`.
**Reason:** The schema has to say what these fields hold, and CLAUDE.md does not. Null spell fields make "cannot cast" explicit instead of overloading 0.
**Changed:** `schemas/state.schema.json`, `schemas/examples/`, `tests/test_state_schema.py` and `docs/state_schema.md` added. CLAUDE.md is unchanged until the 2.6 freeze. Open point for task 2.3: there is no rejection code yet for a non-caster that tries to cast.

## 2026-10-02 — Tool contract v0.9: gaps in CLAUDE.md §6 (WBS 2.3)

Decided by: CI · Supersedes: none

**Decision:** Seven points that CLAUDE.md §6 leaves open are fixed for the v0.9 tool contract. (1) A new rejection code, `NOT_A_CASTER`, for `cast_spell` by a combatant whose spell fields are `null`. There are now 19 codes. (2) `ENCOUNTER_OVER` now means "combat action with no active encounter", so it also covers the time before the first encounter starts. Cure Wounds is exempt and can heal between fights. (3) Only `attack`, `cast_spell` and `dodge` use the turn's action and advance initiative. `skill_check`, `modify_inventory`, `update_npc_relationship` and `update_quest` do not. (4) `schemas/tools.schema.json` is the single source for the validator's shape check and the model-facing tool definitions. (5) The validator checks in a fixed order and returns the first failure: shape, existence, argument values, encounter, actor, target and effect. The argument schemas check shape only, so a bad id or value gets its own code and `valid_options` rather than `SCHEMA_VIOLATION`. (6) `narration_facts` is defined for all seven tools. The §6.2 attack example gains `weapon` and `advantage_mode`. (7) In `modify_inventory`, `actor_id` is the inventory's owner, so `ACTOR_UNCONSCIOUS` does not apply and the PC can loot an unconscious enemy. `delta` of 0 is a `SCHEMA_VIOLATION`, `advance` at `max_stage` is illegal, and `retry_allowed` is always `true`.
**Reason:** (1) 2.1 made "cannot cast" explicit with `null` spell fields, and no existing code describes it. (2) No tool starts an encounter (2.5), so the engine needs a code for combat before one starts. Reusing `ENCOUNTER_OVER` avoids a near-duplicate. (3) §4.5 allows one action per turn and §4.7 frees skill checks; the other three are bookkeeping, not actions. (4) CLAUDE.md §6 requires one source, and no engine code is written before G1. (5) One fixed order makes each rejection deterministic and testable (5.2). (6) The narration call sees only `narration_facts` (§9.1), so a missing weapon name invites a `PHANTOM`.
**Changed:** `schemas/tools.schema.json`, `schemas/examples/toolcall_*.json`, `schemas/examples/result_*.json`, `tests/test_tool_contract.py` and `docs/tool_contract.md` added. CLAUDE.md is unchanged until the 2.6 freeze; the edits it needs are listed in `docs/tool_contract.md` §7. That list includes an error in the §6.2 example, which gives 4 of 11 HP as `badly_hurt` when §10.2 makes it `wounded`.
## 2026-10-02 — Identifier conventions and scenario-scoped namespace (WBS 2.2)

Decided by: SS · Supersedes: none

**Decision:** Entity ids are `<prefix>_<name>`, using only the five §5.1 prefixes. `<name>` is lowercase `[a-z0-9]` words joined by single underscores, and repeated entities of one kind get a two-digit suffix from `01`. Ids are unique within a scenario and fixed when it loads. An NPC in both `combatants` and `npc_relationships` is one entity with one `display_name`. Spell ids belong to the engine. The scenario id is the namespace: it matches `^(s|long)[0-9]{2}_...$`, its series number is unique across the suite, and it equals the scenario's file stem. Inside a run, ids are bare and resolved only against that run's state. Any artefact that combines scenarios writes `<scenario_id>/<entity_id>`.
**Reason:** WBS 2.2 requires that ids cannot collide across scenarios. CLAUDE.md §5.1 gives the prefixes and within-scenario uniqueness, but not the exact format or how scenarios are kept apart.
**Changed:** `docs/identifiers.md` and `tests/test_identifiers.py` added. In `schemas/state.schema.json`, the id patterns no longer allow double or trailing underscores, and `scenario_id` has its own pattern. `tests/test_state_schema.py` gains the display-name consistency check. `docs/state_schema.md` cross-references the new doc. CLAUDE.md is unchanged until the 2.6 freeze.

## 2026-10-02 — Scenario format v0.9: gaps in CLAUDE.md §12 (WBS 2.5)

Decided by: SD · Supersedes: none

**Decision:** Five points that CLAUDE.md §12 leaves open are fixed for the v0.9 scenario format. (1) `initial_state` holds only the five entity maps (`combatants`, `inventory`, `item_definitions`, `npc_relationships`, `quests`). The loader adds `seed` from the run, `turn_number` and `round_number` 0, and no active encounter. (2) Each scripted input is an object `{text, expected_call, check_advantage?}`. `expected_call` is the full tool call, or `null`, and it replaces the separate `expected_tools` list. (3) The DC of a skill check is the `dc` argument of that input's `expected_call`. (4) An `encounters` list says before which input each encounter starts and which combatants are in it. (5) A `locations` list names the places the narration may mention without a `PHANTOM` divergence. `scenario_id` reuses the pattern from the 2.2 identifier entry above.
**Reason:** (1) The seed is a run parameter: one scenario is run under several seeds. (2) Conditions A–C are scored by replaying the scripted inputs offline (§9), which needs the whole call, not only the tool name. One object per input also keeps the text and its call from drifting apart. (3) WBS 2.5 requires the format to hold DCs. (4) No tool starts an encounter. (5) §10.1 counts a location as a phantom only if it is in neither the state nor the scenario, and the state has no locations. This also answers open point 2 in `docs/identifiers.md` §4: names outside the state are listed explicitly.
**Changed:** `schemas/scenario.schema.json`, `schemas/examples/scenario_s00_example.json`, `tests/test_scenario_schema.py` and `docs/scenario_format.md` added. CLAUDE.md §12 is unchanged until the 2.6 freeze. Open points for 2.6, listed in `docs/scenario_format.md` §5: who sets the DC in condition D, scripted inputs when an encounter runs longer or shorter than the script, and how engine-controlled NPCs choose actions.

## 2026-10-02 — Divergence rubric v0.5: counting rules (WBS 8.1)

Decided by: SD · Supersedes: none

**Decision:** Two counting rules are added to CLAUDE.md §10.1 for the v0.5 rubric. (1) A phrase that fits more than one category is recorded once, in the first that applies in the order `PHANTOM`, `CONTRADICT`, `RESOURCE`, `RELATION`. (2) The same divergence repeated within one narration counts once; in a later turn it counts again.
**Reason:** §10.1 says to count every divergence but not how to handle one phrase that fits two categories, or a phantom mentioned twice in one reply. Without a rule, two annotators can score the same turn differently, which lowers the agreement the 8.11 pilot measures.
**Changed:** `docs/rubric.md` added. CLAUDE.md is unchanged until the rubric freeze at G3 (WBS 8.12). The rubric's worked examples use the bands in §10.2, as `docs/tool_contract.md` §7 does.

## 2026-10-03 — Model shortlist for the benchmark (WBS 3.2)

Decided by: CI · Supersedes: none

**Decision:** The Week 2 benchmark compares three models, all at Q4_K_M: `qwen3.5:9b` (Apache 2.0), `granite4.2:8b` (Apache 2.0) and `llama3.1:8b` (Llama 3.1 Community License). There are no 14B candidates. Requests to the two thinking models send `think: false`, and every request sets `num_ctx` and every sampling parameter explicitly.
**Reason:** Three families, each with Ollama's `tools` capability, each at or below 9.7B so that it fits the 7.7 GiB of usable VRAM measured in WBS 3.1. A 14B model at Q4 does not fit. Licences were read from `ollama show --license`. The Llama licence requires "Built with Llama" in the report if Llama is frozen. In the fit check, Qwen 3.5 and Granite 4.2 loaded at 88% and 92% GPU, because other processes held 1.3 GiB of GPU memory at the time. WBS 3.4 must confirm each model loads at 100% GPU on an otherwise idle GPU before timing it.
**Changed:** `docs/model_shortlist.md` added. `qwen3.5:9b` and `granite4.2:8b` pulled on the benchmark machine. `config/model.json` is not created until WBS 3.6.

## 2026-10-03 — Audit-log turn record v0.9: gaps in CLAUDE.md §11 (WBS 2.4)

Decided by: SD · Supersedes: none

**Decision:** The v0.9 turn record keeps every §11 field and fills five gaps. (1) `validation` has one entry per toolcall attempt, aligned with `proposed_calls`. A rejected attempt holds the full rejection envelope, and a successful one the full `result_ok`, including its `narration_facts`. There are two extra entry shapes: `{"ok": true, "tool": null}` for a `{"tool": null}` reply, and a parse-failure entry, with a `null` proposed call, for unparseable output. (2) A new `engine_steps` list records the engine's work outside the player's call: `encounter_start`, `dodge_expiry`, `npc_action`, `initiative_advance`, `encounter_end` and `turn_increment`. The top-level `state_diff` and `rolls` are the before-call steps, the executed result and the after-call steps, concatenated in order. (3) A new `input_index` names the scripted input the turn answers. (4) A new `summary` field holds `{text, truncated}` when the rolling summary is regenerated. (5) `turn_number` is the turn being played, so it repeats after a failed turn. State hashes are `sha256:` of the `docs/conventions.md` §2 serialisation.
**Reason:** (1) M2 needs every rejection with its code, and the rubric scores narration against `narration_facts`, which §11 does not store. (2) `docs/tool_contract.md` §2 puts turn advance, Dodge expiry and NPC turns in the turn record, and §11 has no field for them; invariant 2 needs every mutation diffed. (3) After a failed turn, `turn_number` no longer lines up the same input across conditions. (4) §8.1 requires every regeneration to be logged, and a boolean alone loses the text.
**Changed:** `schemas/audit.schema.json`, `schemas/examples/audit_turn_*.json`, `tests/test_audit_log.py` and `docs/audit_log.md` added. CLAUDE.md §11 is unchanged until the 2.6 freeze. Open points for 2.6, listed in `docs/audit_log.md` §4: NPC actions are not narrated, the NPC action policy, scripted runs after a failed turn, and what conditions A–C hash.

## 2026-10-03 — Specifications v0.9 reviewed and signed off (WBS 2.6)

Decided by: SS, CI, SD · Supersedes: none

**Decision:** All three members sign off the v0.9 specifications for the G1 freeze: the state schema (2.1), identifier conventions (2.2), tool contract (2.3), audit-log turn record (2.4) and scenario format (2.5), as merged on `main`. The open points in those specs are settled as follows.

Proposals accepted as written:
1. The DC and `check_advantage` for a skill check come from the scenario's scripted input. In condition D the engine uses them and logs the model's proposed `dc` (`docs/scenario_format.md` §5.1).
2. When an encounter runs longer or shorter than the script, the inputs are not changed. Rejections such as `TARGET_UNCONSCIOUS` or `ENCOUNTER_OVER` are logged and count as data (`docs/scenario_format.md` §5.2).
3. After a failed turn, a scripted run moves on to the next input. The failed record keeps its `input_index`, and the next record has `input_index + 1` and the same `turn_number` (`docs/audit_log.md` §4.3).
4. In conditions A–C, both state hashes are the replayed ground-truth state for that input (`docs/audit_log.md` §4.4).
5. A byte-identical replay compares every audit field except `timestamp` and `latency_ms` (`docs/conventions.md` §3.1, `docs/audit_log.md` §4.5).
6. The CLAUDE.md §6.2 example is corrected: 4 of 11 HP is `wounded`, as §10.2 says (`docs/tool_contract.md` §7.1).
7. The failure pipeline has five modes, as in CLAUDE.md §7.1. The WBS and proposal §8.3 say four; CLAUDE.md wins (`TASK_CHECKLIST.md`, task 6.4 note).
8. Every other proposal in the open-point lists of `docs/state_schema.md`, `docs/identifiers.md`, `docs/tool_contract.md`, `docs/scenario_format.md` and `docs/audit_log.md` is accepted as written.

Points with no proposal, decided here:

9. **NPC actions are chosen by a separate AI agent** rather than a fixed engine rule. The agent only proposes calls; they go through the same validator and are recorded as `npc_action` steps (2.4). Its design is open and must satisfy three constraints: CLAUDE.md §14 says NPCs are engine-controlled and must be updated; a run must still replay identically from its seed (invariant 4); and conditions A–C are scored by an offline replay that cannot call the model (§9, §13). It must also be identical across the four conditions (invariant 7).
10. **NPC actions must be narrated.** The condition D narration call receives the `narration_facts` of the NPC actions in the turn as well as the player's, in the order they happened. This changes the input of the frozen `d_narration.txt` template (§9.1).
11. **No taking items from other characters.** There is no transfer between inventories and no stealing. `modify_inventory` changes one inventory per call. Scenarios must not script an input that takes an item from an NPC.
12. **Attacking yourself or an ally is allowed.** `attack` and Fire Bolt may target any conscious combatant, and no rejection code is added.

**Reason:** Gate G1 (4 Oct) requires the specifications to be frozen before the engine is started. Every open point is now either decided or has a stated constraint.
**Changed:** Nothing in the schemas. CLAUDE.md is updated at the v1.0 tag (2.7) with the edits listed in each spec doc, plus: §14 and §9.1 for decisions 9 and 10, the §6.2 band, and §12 for the scenario format.

## 2026-10-03 — Weekly checkpoint, Week 1 (WBS 12.1)

Attendees: SS, CI, SD · Note-taker: SD

**Closed:** 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 3.1, 3.2, 8.1
**Slipped:** none. The checkpoint itself was held on 3 Oct instead of 28 Sep, because the slot was booked after that date.
**Hours vs. estimate:** not tracked this week. Task work was drafted with Claude Code.

**Gates and risks:** G1 (4 Oct) is on track. 2.6 is signed off above, and 2.7 (SS) tags v1.0. No risk-register trigger has fired. R1 is checked at 3.4.

**Decisions:**
1. The 2.6 sign-off above, including NPC actions chosen by an AI agent and narrated, no item transfers, and self- or ally-targeting allowed.
2. The failure pipeline has five modes (2.6 decision 7).
3. The weekly checkpoint moves from Monday 20:00–21:00 to **Saturday 19:00–20:00**, from Week 2 (Sat 10 Oct) to Week 7 (Sat 21 Nov). `docs/checkpoint.md` updated with the new dates.

**Open, carried to next week:** design of the NPC action agent (2.6 decision 9), which needs an owner and must fit the engine work in Week 2 — all · CLAUDE.md edits at the v1.0 tag — SS (2.7)

## 2026-10-03 — NPC actions are engine-controlled (WBS 2.6)

Decided by: CI · Supersedes: Specifications v0.9 reviewed and signed off (WBS 2.6), decision 9

**Decision:** NPC actions are chosen by the engine, not by a separate AI agent. This restores CLAUDE.md §14 as written: one PC, and everyone else is engine-controlled. The engine's call for an NPC still goes through the validator and is recorded as an `npc_action` step (`docs/audit_log.md` §2). Decision 10 of the 2.6 sign-off is unchanged: NPC actions are narrated, and the condition D narration call receives their `narration_facts` in order. The policy that picks an NPC's action and target is a simple rule-based system: fixed rules over the current state, with no model call. Its exact rules are open (`docs/scenario_format.md` §5, point 3) and are a new task, WBS 4.19 (#136, owner SS, Week 4). It may choose `attack` or `dodge`, so it depends on Dodge (4.6). Any randomness in it must come from the seeded `DiceRoller` (invariant 3).
**Reason:** An agent that calls the model breaks the offline replay that produces the A–C ground truth (§9), since no replay or test may call the model (§13). It also makes a run depend on more than its seed (invariant 4), and it needs its own frozen prompt, failure fallback and audit fields. Enemy behaviour is not what the experiment measures, so that cost buys nothing for the research question.
**Changed:** Nothing in the schemas or specs. CLAUDE.md §14 already says NPCs are engine-controlled, so the §14 edit planned for the v1.0 tag (2.7) is dropped. The §9.1 edit for decision 10 still applies. The checkpoint item "design of the NPC action agent" becomes "the engine's NPC action policy". New issue #136 (WBS 4.19) blocks #73 (6.11) and #76 (4.18). #65 (6.6) has a comment adding NPC facts to the narration call.

## 2026-10-03 — Specifications v1.0 tagged (WBS 2.7)

Decided by: SS · Supersedes: none

**Decision:** The specifications signed off at 2.6 are frozen as v1.0 under the git tag `spec-v1.0`, on the `main` merge commit of this change. v1.0 is CLAUDE.md plus `schemas/state.schema.json`, `schemas/tools.schema.json`, `schemas/audit.schema.json` and `schemas/scenario.schema.json`, with their examples and their specs `docs/state_schema.md`, `docs/identifiers.md`, `docs/tool_contract.md`, `docs/audit_log.md` and `docs/scenario_format.md`. From the tag on, any change to them needs an entry here (§1). No schema rule changes in this step.
**Reason:** Gate G1 (4 Oct) requires the specifications frozen and tagged before the engine starts (WBS 4.1 is blocked by 2.7). The 2.6 sign-off deferred the CLAUDE.md edits to the tag so that the frozen CLAUDE.md does not contradict the frozen schemas.
**Changed:** CLAUDE.md: a v1.0 note at the top; §4.1 non-casters; §4.5 which tools use the action, and self- or ally-targeting; §4.7 scenario DC and `check_advantage`; §4.8 widened `ENCOUNTER_OVER`, encounter start and the rule-based NPC policy; §5 and §5.1 the 2.1 and 2.2 rules; §6 single source, no transfers, `retry_allowed`, validation order; §6.2 example gains `weapon` and `advantage_mode`, and its band is corrected to `wounded`; §6.3 adds `NOT_A_CASTER` (19 codes) and widens `ENCOUNTER_OVER`; §7.1 scripted runs after a failed turn; §9 A–C hashes; §9.1 NPC facts in `{narration_facts_json}`, with the template text unchanged; §11 the 2.4 fields and the replay comparison; §12 the 2.5 format; §15 decisions 17–23. The five spec docs and four schema descriptions are marked v1.0, and their open-point sections are marked settled. `tests/test_tool_contract.py`: `ADDED_CODES` and `test_claude_md_attack_example_band_is_wrong` are removed, as the docs asked, since CLAUDE.md now matches. `docs/conventions.md` (1.4) is not part of v1.0; it still needs CI's and SD's sign-off.

## 2026-10-04 — Tool-calling micro-benchmark (WBS 3.3)

Decided by: CI · Supersedes: none

**Decision:** The 3.3 micro-benchmark lives in a new package, `adm/bench/`, which is not in the CLAUDE.md §3 layout. 3.4, 3.5 and 3.7 reuse it. It holds 20 cases (`adm/bench/toolcall_cases.json`). Each case pairs a state fixture from `schemas/examples/` with one player input and the expected call, and together they cover all seven tools and `{"tool": null}`. The prompt is a draft of `d_toolcall.txt`. Its preamble, state block and instruction are verbatim from §9.1. The tool-definition block is derived from `schemas/tools.schema.json` exactly as `docs/tool_contract.md` §5 says, and its one-line heading is draft wording. WBS 7.5 freezes the real template, so nothing is written to `config/prompts/`. Model tags are passed on the command line (`--model`) and appear nowhere in code (§2.2). `think: false` is sent only to models whose `/api/show` lists the `thinking` capability. Every sampling option is set on every request (`docs/model_shortlist.md` §5). The primary score, `schema_valid`, is the raw reply parsed unchanged as one JSON object and validated against `proposed_call`. It is the figure for risk R1's 80 per cent trigger. Reported alongside it: `schema_valid_lenient` (after stripping code fences and prose), plus tool and argument match. Argument match ignores a skill check's `dc` and a relationship change's `justification`. `--format json` sends Ollama's JSON mode so that 3.7 has a comparison number.
**Reason:** 3.3's done-when is "runs unattended and scores schema validity automatically". Keeping the benchmark inside `adm` puts it under ruff, pytest and the import-boundary test. Taking model tags from arguments keeps §2.2 intact before the 3.6 freeze. The strict figure is what condition D gets with no recovering parser; the lenient figure shows how much a recovering parser (6.3) would add.
**Changed:** `adm/bench/` added (`toolcall.py`, `toolcall_cases.json`). `tests/bench/test_toolcall.py` added; it makes no model calls and uses an `httpx.MockTransport` fake Ollama. `tests/test_boundaries.py` now forbids `adm/bench` from importing `orchestration`, `eval` and `cli`. `pyproject.toml` ships `adm/bench/*.json` as package data. Output goes to `results/bench/toolcall/<UTC timestamp>/` (gitignored). No new dependencies.

## 2026-10-05 — K = 8, and history as a transcript block (WBS 3.5)

Decided by: CI · Supersedes: none

**Decision:**
1. K, the number of verbatim turns, is **8**. 3.6 (#38) writes it to `config/model.json`.
2. A verbatim turn is the player's input and the DM's narration, the same in every condition. Tool calls and results are not part of it.
3. The last K turns are sent as a transcript block (`Player:` / `DM:` lines) in the system prompt, after the summary. They are never sent as `assistant` chat messages. Under invariant 7, the same format is used in every call of every condition. The block's wording is a draft for 6.2 (#58) to settle and 7.5 to freeze.
4. `adm/bench/context_ceiling_state.json` is the scenario authoring ceiling: 1 PC, 6 combatant NPCs, 3 relationships, 12 item definitions and 4 quests. A larger state can make the worst-case prompt exceed 8192 tokens at K = 8, and then the per-turn reduction in §8 applies.

**Reason:** The rule was fixed before the runs (`docs/context_budget.md` §2): the largest K that fits 8192 tokens for every candidate's tokeniser, with the ceiling state, the summary at its 200-token cap and every narration at its 300-token cap, and that keeps schema-valid and tool-match rates within 1 case in 20 of K = 0. K_fit is 8 for Qwen and Granite and 10 for Llama (§3). Every model is stable at its K_fit when history is a transcript (§5.2). When history is sent as chat turns, all three stop calling tools and write narration from K = 8 (Llama falls from 100% to 0% schema-valid, Granite from 90% to 5%). The models continue the pattern of the earlier `assistant` messages (§5.1). Real narrations average 65 tokens and never reached the cap (§4), so K = 8 leaves a large margin in practice.
**Changed:** `adm/bench/context.py`, `context_ceiling_state.json` and `context_history.json` added, with `tests/bench/test_context.py` (no model calls; `httpx.MockTransport`). In `adm/bench/toolcall.py`, `chat_body`, `preflight`, `summarise`, `mean` and `safe_name` lose their leading underscore so that `context.py` can import them, and `chat_body` takes an optional `options`; the 3.3 behaviour is unchanged. `docs/context_budget.md` added. No new dependencies. `config/model.json` is still not created (3.6).

## 2026-10-05 — Model frozen: llama3.1:8b, K = 8 (WBS 3.6)

Decided by: CI, answering CLAUDE.md §16 for the team; to be confirmed at the Week 2 checkpoint (#28) · Supersedes: none

**Decision:**
1. The model is **`llama3.1:8b`**: digest `sha256:46e0c10c039e019119339687c3c1757cc81b9da49709a3b3924863ba87ca666e`, Q4_K_M, served by Ollama 0.35.1. K is 8. All values are in `config/model.json`.
2. `config/model.json` gains two keys, `model_digest` and `ollama_version`, so that the "version" is pinned. A re-pull that changes the digest, or an Ollama upgrade, means re-running `docs/model_selection.md` §3 before any run that counts.
3. `seed: null` means that the run's seed is sent to Ollama as the `seed` option on every call.
4. Every run starts from a freshly loaded model, and nothing else uses the Ollama server during a run. 6.1 (#45) and 7.6 (#82) implement this.

**Reason:** `docs/model_selection.md` §2.
- Llama is the only candidate that is 100% schema-valid without JSON mode, identical across repeats, and fully on the GPU, and it is the fastest.
- Qwen replies differently to identical requests (3.4 §5), which a byte-identical replay (invariant 4) cannot rest on.
- Granite produces schema errors.
- The cost is Llama's 80% tool match: wrong-action calls that only M3 can catch.

Llama's replies are byte-identical across fresh processes and days: 0 of 60 tool calls, 0 of 40 temperature-0.7 narrations, and 0 of 80 replies when 3.5 run 1 is replayed. The 3.5 tc16 difference is deterministic. It appears only after the model has served the narration phase and then the token phase, while the request bytes stay identical (§3.2). So a reply depends on the requests served since the model was loaded, which is why point 4 is needed.
**Changed:**
- `config/model.json` added.
- `tests/test_model_config.py` added: key set, no placeholder, frozen values, and the model name absent from `adm/`.
- `docs/model_selection.md` added (deliverable D2).
- CLAUDE.md §2.2: placeholder replaced, and seed and fresh-load rule added.
- CLAUDE.md §15: items 24 and 25 added.
- CLAUDE.md §16: the model question removed.
- No new dependencies.

## 2026-10-06 — No grammar-constrained decoding and no JSON mode (WBS 3.7)

Decided by: CI, answering CLAUDE.md §16 for the team; to be confirmed at the Week 2 checkpoint (#28) · Supersedes: none

**Decision:**
1. Condition D's tool calls are generated in plain prompt mode, with no grammar-constrained decoding and no Ollama JSON mode. The 6.1 client (#45) sends no `format` field on any request, tool call or narration.
2. Nothing is added to the parser for format reasons. 6.3 (#49) still handles malformed output as CLAUDE.md §7.1 says.
3. Revisit trigger: if the 6.11 smoke runs (#73) show a tool-call schema-valid rate below 80% (risk R1's trigger), a new entry here decides again before the Week 6 batches.

**Reason:** `docs/model_benchmark.md` §2–4 and `docs/model_selection.md` §1–2, for the frozen `llama3.1:8b`.

| | Prompt mode | JSON mode |
|---|---|---|
| Schema-valid | **100%** (n = 60) | 100% (n = 20) |
| Tool match | 80% | 80% |
| Mean / p95 s per tool call | 0.57 / 0.89 | 0.64 / 1.70 |

- JSON mode changes none of Llama's replies, and lenient equals strict: no reply has code fences or extra prose. So JSON mode gains nothing measured.
- 3.5 §5.2: Llama stays schema-valid up to K = 16 when history is a transcript, which is the format 6.2 uses.
- Llama's misses are valid calls for the wrong action (3.4 §4). A grammar cannot prevent them; M3 measures them.
- A constraint would hide parse failures that M2 is meant to count. It would also make the model's raw output depend on a decoding setting outside the frozen prompt templates.

**Changed:**
- CLAUDE.md §15: item 26 added.
- CLAUDE.md §16: the grammar-constrained decoding question removed.
- `docs/model_selection.md` §2 point 4 and §4: the decision and the "no `format` field" rule for the 6.1 client.
- `docs/model_benchmark.md` §8: points to this entry.
- `config/model.json` unchanged. No new dependencies.
