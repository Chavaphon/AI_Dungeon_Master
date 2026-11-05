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

## 2026-10-11 — Rubric v0.6: hit-point band rule and borderline conventions (WBS 8.2)

Decided by: SD; the conventions are proposals until the rubric freeze (WBS 8.12) · Supersedes: none

**Decision:**
1. A combatant at 14 of 20 HP is `wounded` (ratio 0.70). Any `badly_hurt` or `healthy` phrase about it is one `CONTRADICT`. Exactly 0.75 and exactly 0.35 fall in the lower band, as `hp_band` in `adm/engine/combat.py` already computes in integers.
2. A band phrase describes how hurt a combatant is now, after every effect of the turn. A damage event ("the bite hurts"), a negated phrase, a figurative phrase about something else, the past and the future, and effort or emotion are not scored for band accuracy. Each combatant is scored separately, with at most one band divergence per combatant per narration.
3. An ambiguous phrase that fits two bands, one of them the actual band, is not a divergence. This is not an adjacency allowance: a clear phrase one band away is still a divergence.
4. The three open points of rubric v0.5 are settled as proposed: features of a listed location are in scope; negated and figurative band phrases are not scored; `RELATION` applies only to NPCs in `npc_relationships`.
5. Proposed for the 8.11 pilot only: `RELATION` behaviour one stance step from the recorded stance is not a divergence.

**Reason:** WBS 8.2 must settle "badly hurt at 14 of 20" with a written rule, and WBS 8.7 must implement it exactly. The other conventions remove the disagreements most likely to lower the agreement measured in the 8.11 pilot. They lean towards no divergence when in doubt, as CLAUDE.md §10.2 requires.

**Changed:** `docs/rubric.md` v0.6: new §5 (hit-point bands, with a lookup table for `max_hp` 4–30), §6 (borderline conventions) and §7 (open points for the pilot). `tests/test_rubric.py` checks the table against `hp_band`. CLAUDE.md is unchanged until the rubric freeze at G3 (WBS 8.12).

## 2026-10-12 — Weekly checkpoint, Week 2 (WBS 12.2)

Attendees: SS, CI, SD · Note-taker: SS

**Closed:** 3.3, 3.4, 3.5, 3.6, 3.7, 4.1, 4.2, 4.3, 4.4, 4.5, 4.7, 4.8, 4.9, 8.2, 8.3, 12.8
**Slipped:** none of the Week 2 tasks. The checkpoint itself was held on 12 Oct instead of Sat 10 Oct, because of exams.
**Hours vs. estimate:** SS 13/13 · CI 12.5/12.5 · SD 9/9. Actual hours equal the `TASK_CHECKLIST.md` estimates.

**Gates and risks:** G1b (11 Oct) is met: model, quantisation and K are frozen in `config/model.json` (3.6), and the handover note is committed (12.8, #44). The 3.6 and 3.7 confirmations it waited on are given below. No risk-register trigger has fired. 4.6 and 4.10–4.13 are scheduled for Weeks 3 and 4, and the team continues as scheduled after the blackout. R2 is checked again at the Week 3 checkpoint (#46).

**Decisions:**
1. The model freeze (2026-10-05 entry, WBS 3.6) is confirmed as written: `llama3.1:8b`, Q4_K_M, Ollama 0.35.1, K = 8.
2. No grammar-constrained decoding and no JSON mode (2026-10-06 entry, WBS 3.7) is confirmed as written.

**Open, carried to next week:** sign-off of `docs/conventions.md` (1.4) — CI, SD · the engine's NPC action policy rules — SS (4.19, #136) · whether the minimal FastAPI interface is built (CLAUDE.md §16) — all

## 2026-10-13 — Ollama client: timeouts, transport retries, summary cap (WBS 6.1)

Decided by: CI · Supersedes: none

**Decision:**
1. `adm/orchestration/client.py` is the single loader of `config/model.json`. Every request sends `num_ctx` and every sampling option with the values the 3.4–3.6 evidence used, no `think` field and no `format` field. Replies are not streamed, so the read timeout bounds the whole generation: a stalled server raises instead of hanging the run.
2. Timeouts are module constants, not `config/model.json` keys, because that file's key set is frozen: connect 5 s, chat 60 s, load 120 s. The chat bound is about five times the worst case at 8192 tokens; the load bound covers the 35 s first load after a reboot (`docs/hardware.md` §3).
3. Connection errors, timeouts and 5xx replies are retried at most twice, after 1 s and 2 s. A 4xx reply or a body that is not a chat reply is not retried. Exhausted retries raise `ModelUnavailable`, which aborts the run; it is not a `turn_failure`. These transport retries are separate from the turn loop's retry budget of two (CLAUDE.md §7.1).
4. Every reply carries `transport_retries`. A retry reaches a server that may already have seen the request, and earlier requests can change a reply (`docs/model_selection.md` §3.2), so **a run with any transport retry is not guaranteed to replay byte-identically**. The batch runner (7.6, #82) must re-run such a run from a fresh load. The audit schema is unchanged.
5. The rolling summary call (6.7) runs at temperature 0.0 with `num_predict` 200, the §8.1 cap. The client returns Ollama's `done_reason`, so a summary that hits the cap shows `"length"` and 6.7 truncates it at a sentence boundary.
6. The seed sent to Ollama must be in 0 to 2³² − 2. llama.cpp reads the seed as an unsigned 32-bit integer and treats `0xFFFFFFFF`, which is what −1 becomes, as "pick a random seed". Run seeds outside that range raise `ValueError` rather than silently break invariant 4.
7. `fresh_load()` unloads the model (`keep_alive: 0`), polls `/api/ps` until it is gone (at most 30 s), and loads it with `num_ctx` and no prompt. Loads and chats send `keep_alive: -1`, so an idle interactive session never reloads the model part-way through a run. `verify()` refuses a server whose version, or a model whose digest, differs from `config/model.json`.

**Reason:** WBS 6.1 must stop a stalled generation from hanging an unattended batch, while keeping invariant 4 checkable. Point 4 makes the one case where a retry could change a reply visible instead of silent. Points 6 and 7 close two ways a run could stop being reproducible without anyone noticing.

**Changed:** `adm/orchestration/client.py` added. `tests/orchestration/test_client.py` added; it makes no model calls, uses an `httpx.MockTransport` fake Ollama, and tests the stall against a local socket that never answers. No new dependencies; CLAUDE.md and the schemas are unchanged.

## 2026-10-14 — Tool-call parser: extraction and safe repairs (WBS 6.3)

Decided by: CI · Supersedes: none

**Decision:**
1. `adm/orchestration/parser.py` turns the condition D tool-call reply into a proposed call or a parse failure. It reads no state and does not check the tool contract. An unknown tool, a missing argument, or the string `"null"` in place of `null` is a parsed call, which the validator rejects with `SCHEMA_VIOLATION` (`docs/tool_contract.md` §1). The parser does not normalise `"null"`.
2. The call is the first JSON object with a `tool` key. It may be inside the first code fence, or have prose or tags such as `</think>` around it. Objects without `tool`, such as an echoed `<state>` block, are skipped. A later object with `tool` is ignored and flagged.
3. If nothing decodes as written, three repairs are tried, each of which cannot change what the model meant: trailing commas are removed, Python's `None`, `True` and `False` become JSON literals, and brackets missing at the end of a cut-off reply are closed. Text inside JSON strings is never edited. A reply cut off inside a string stays a failure, because closing it would invent content. Single quotes and unquoted keys are not rewritten: rewriting them could corrupt a justification that contains an apostrophe.
4. Every extraction and repair is listed on the result (`code_fence`, `surrounding_text`, `multiple_objects`, `trailing_comma`, `python_literal`, `closed_truncation`). A recovered parse is therefore visible rather than hidden from M2, which the 2026-10-06 entry (WBS 3.7) asked for.
5. A failure is a value with reason `no_json` or `no_tool_key`. Its message is the logged one from `schemas/examples/audit_turn_rejected.json`. The retry prompt with one example belongs to the failure pipeline (6.4, #63).
6. The 31 recorded replies the tests use are copied from the gitignored `results/bench/` into `tests/orchestration/fixtures/recorded_toolcall_outputs.jsonl`, with each line naming its run file and line. All 31 broke the tool contract. They are:
   - 20 Qwen prose replies
   - 2 schema-invalid Granite replies
   - 3 Granite replies with trailing tags
   - 1 echoed state block
   - 5 Llama prose replies

   The benchmark had no fenced, broken or cut-off JSON, so those cases are hand-written in the tests and are not counted as recorded.

**Reason:** WBS 6.3 must recover from malformed output without hiding the failures M2 counts, and without making the parser a second validator. The Week 2 data shows that what `llama3.1:8b` gets wrong is prose instead of JSON, not broken JSON. The repairs are therefore kept to the ones that cannot change a call's meaning.

**Changed:** `adm/orchestration/parser.py` added. `tests/orchestration/test_parser.py` and `tests/orchestration/fixtures/recorded_toolcall_outputs.jsonl` added. No new dependencies; CLAUDE.md and the schemas are unchanged.

## 2026-10-24 — Weekly checkpoint, Week 3 (WBS 12.3)

Attendees: SS, CI, SD · Note-taker: CI

**Closed:** 4.10, 4.11, 4.12, 4.13, 6.1, 6.3, 8.4, 8.5
**Slipped:** none.
**Hours vs. estimate:** SS 11/11 · CI 6/6 · SD 9/9. Actual hours equal the `TASK_CHECKLIST.md` estimates.

**Gates and risks:** G2 / Milestone 1 (1 Nov) is on track: a playable 50-turn session, shown by 6.11 (#73). No risk-register trigger has fired. R2 is checked again at the Week 4 checkpoint (#56), the day before G2; R3 is checked at 6.2 (#58).

**Decisions:**
1. `docs/conventions.md` (1.4) is signed off by CI and SD. Its two open points are settled as proposed: replay compares every audit field except `timestamp` and `latency_ms`, as CLAUDE.md §11 already says, and the band thresholds live in the engine (`hp_band` in `adm/engine/combat.py`) with the lexicon in `eval`. Its status is changed to signed off.
2. The minimal FastAPI interface is not built. This answers the last open question in CLAUDE.md §16. The only client is the text CLI (6.10, #72). CLAUDE.md §14, §15 (item 27) and §16 are updated.
3. The engine's NPC action policy (4.19, #136) is agreed. On its turn, an NPC that holds a weapon attacks. Its target is the conscious combatant of the opposing faction (hostile against party, party against hostile) with the lowest `current_hp`, ties broken by the smaller `combatant_id`. Its weapon is the first weapon id in its sorted inventory. An NPC with no weapon dodges. The policy rolls no dice of its own, so it adds nothing to the seeded RNG stream. SS writes the rules into `docs/` in the 4.19 pull request.

**Open, carried to next week:** none.

## 2026-10-24 — Prompt assembly, block order and K reduction (WBS 6.2)

Decided by: CI · Supersedes: none

**Decision:**
1. **State comes before tools** in the D tool-call prompt. CLAUDE.md §8 listed tool definitions as item 2 and state as item 3, while §9.1 gives `d_toolcall.txt` as "preamble, state block, tool definitions". §8 is corrected to match §9.1, and so is the "§8 step 2" reference in `docs/tool_contract.md` §5.
2. **Where the summary and history go.** Each template's fixed blocks (preamble, state, tools or facts) come first. Then the rolling summary, then the last K turns. The condition's instruction comes last, closest to the input: C's self-check, D's tool-call instruction, and D narration's facts block. The prompt is one system message and one user message holding the player input. The history is a `Player:` / `DM:` transcript, never `assistant` messages (2026-10-05 entry, point 3).
3. **Templates in `config/prompts/` now, as drafts.** The five condition templates hold the §9.1 text verbatim, with `{summary}` and `{history}` paragraphs. A paragraph with nothing to fill it is dropped. Two shared block files are added: `summary_block.txt` and `history_block.txt`, worded as the 3.5 drafts. WBS 7.5 (#81) freezes all seven files. No module branches on the condition; a template uses only the placeholders it holds (invariant 7).
4. **Tokens are estimated, not counted:** `ceil(characters / 3.5) + 5` per message. It is deterministic, so a replay reduces K at the same turns. It over-counts every one of the nine `llama3.1:8b` prompts recorded in 3.5, by 3.5–10.9% (`docs/context_budget.md` §9.1). The budget is `context_tokens` less the phase's reply cap: 7992 for a tool call, 7892 for narration.
5. **K reduction.** The assembler tries K, K−1, … 0 and uses the first prompt that fits. It drops the oldest turns and never cuts the middle. The turn record's `k_used` logs the reduction. A turn has one K: the loop assembles the turn's largest prompt first (the D tool call, or the single A–C call) and passes its `k_used` on. If even K = 0 does not fit, `PromptTooLarge` is raised. That is a state beyond the authoring ceiling, so it is a bug, not a turn failure.
6. **R3 is not triggered.** The §2 worst case at K = 8 is estimated at 7765 of 7992 tokens for the D tool call, with no reduction (`docs/context_budget.md` §9.2).

**Reason:** §8 and §9.1 disagreed about the order. K = 8 was validated on the §9.1 order (3.3, 3.5), so that order is kept, and swapping it would need a new benchmark. The instruction-last rule is the layout 3.5 validated for D, applied the same way to every template. No tokeniser runs offline. Counting through Ollama would add a model call per turn, and earlier requests can change a reply (`docs/model_selection.md` §3). An estimate that over-counts can only reduce K early, never let a prompt overflow.

**Changed:** `adm/orchestration/prompt.py`, `config/prompts/` (seven files) and `tests/orchestration/test_prompt.py` added. CLAUDE.md: §3 lists the two block files; §8 swaps items 2 and 3 and states the message layout, the reduction rule and the estimate. `docs/tool_contract.md` §5: step 3. `docs/context_budget.md` §9 added. No new dependencies.

## 2026-10-24 — Rolling summary: coverage, trigger, prompt and cap (WBS 6.7)

Decided by: CI · Supersedes: none

**Decision:**
1. **Coverage: overlap, no gap.** CLAUDE.md §8.1 says the summary covers "turns older than K" and is regenerated every K turns; both cannot hold exactly. After turn n with n % K == 0, the new summary is the model's fold of the previous summary and the K turns played since the last regeneration. Those turns are still in the verbatim window, so a turn can be in both for up to K turns, but no turn is ever in neither. CLAUDE.md §8.1 states the rule.
2. **Trigger.** A turn here is a narrated turn: a failed turn has no narration and is not counted. K is `K_verbatim_turns` from `config/model.json`, never a turn's reduced `k_used`. At K = 8 a 50-turn session regenerates 6 times, so the long scenarios meet the §12 minimum of five.
3. **Prompt.** `config/prompts/summary.txt` is added as a draft that WBS 7.5 (#81) freezes with the other seven files. It is the same in every condition (invariant 7). It has no narration preamble and no state, so the summary has no numbers to restate, and it reuses `summary_block.txt` and `history_block.txt`. The instruction comes last, as in every other template; the user message is the fixed line "Write the summary.". The summary must see every turn it folds in, so a prompt that would need K reduced raises `PromptTooLarge`; the worst case is about 3000 of 7992 tokens.
4. **Cap.** The call runs at temperature 0.0 with `num_predict` 200 (2026-10-13 entry, point 5), so a reply cannot pass the cap; one that reaches it ends with `done_reason` "length". That reply is cut after its last complete sentence (`.`, `!` or `?`, with any closing quotes or brackets, before a space or the end) and logged with `truncated: true`. If it has no complete sentence it is kept whole. The uncut reply stays in the model call's `raw_output`.

**Reason:** With the strict reading, up to K − 1 turns would leave the prompt entirely between regenerations, which loses context for no gain; repeating a few turns costs little and loses nothing. Folding only the new turns into the previous summary keeps the summary prompt bounded however long the session runs.

**Changed:** `adm/orchestration/summary.py`, `config/prompts/summary.txt` and `tests/orchestration/test_summary.py` added. `adm/orchestration/prompt.py` lists the summary template in `TEMPLATES`. `tests/orchestration/test_prompt.py` checks the shared preamble only in the five condition templates. CLAUDE.md: §3 lists `summary.txt`, §8.1 states the coverage rule, and §15 adds item 28. No new dependencies; the schemas are unchanged.

## 2026-10-27 — Dodge: expiry step, and every Dodge cleared at encounter end (WBS 4.6)

Decided by: SS · Supersedes: none

**Decision:**
1. **Expiry is its own engine step.** `expire_dodge` in `adm/engine/combat.py` is the `dodge_expiry` step of `docs/audit_log.md` §2. The turn loop runs it right after each `initiative_advance`, the order used in `audit_turn_valid.json`. It clears `dodging` on the combatant whose turn is starting, and records nothing if that combatant is not dodging. So a Dodge holds through everyone else's turns and across the round wrap, and expires at the start of the dodger's next turn (CLAUDE.md §4.5, §15 item 6).
2. **An unconscious dodger keeps the flag** while it is skipped. It cannot be attacked (§4.8), so the flag has no effect, and it clears when the combatant is revived and its turn comes.
3. **Encounter end clears every Dodge.** CLAUDE.md §4.5 does not say what happens to a Dodge whose next turn never comes because the encounter ended first. The `encounter_end` step now resets every `dodging: true` to false, in combatant id order, as part of its diff.

**Reason:** (3) Under the strict reading, a combatant would still be dodging during exploration and would carry disadvantage into a later encounter until its first turn there. That is a stale advantage, and the state injected in B, C and D would show a dodging rat outside any fight, which is a divergence source of our own making. `state_03_after_victory.json` already shows the dodging rat of `state_02_mid_combat.json` with `dodging: false` after the victory, so the examples assumed this rule.

**Changed:** `adm/engine/combat.py`: `dodge`, `expire_dodge`, and the reset in `end_encounter_if_over`. `tests/engine/test_combat.py`: the four dodge rule-suite cases, and the victory test's diff now includes the reset. `tests/engine/test_rule_suite.py`: dodge leaves `NOT_YET_BUILT`. CLAUDE.md: the §4.5 Dodge bullets, and §15 adds item 29. `docs/audit_log.md` §2: the `encounter_end` row. No new dependencies; the schemas are unchanged.

## 2026-10-27 — NPC turns: before-call turns at encounter start, neutral NPCs dodge (WBS 4.19)

Decided by: SS · Supersedes: none

**Decision:**
1. **The policy agreed at the Week 3 checkpoint** (2026-10-24, decision 3) is written down in `docs/npc_policy.md` and built in `adm/engine/npc.py`.
2. **NPCs who win initiative act at encounter start.** When an encounter starts and NPCs come before the PC in the initiative order, their turns run right after `encounter_start`, before the player's call. They are recorded as `before_call` steps: `npc_action`, `initiative_advance`, `dodge_expiry` and, if the PC falls, `encounter_end`. `schemas/audit.schema.json` widens `npc_action.when` from `"after_call"` to either value. CLAUDE.md §9.1 now orders the narration facts as they happened: the before-call NPC actions, then the player's call, then the after-call NPC actions.
3. **A neutral NPC, or one with no conscious opponent, dodges.** The agreed rule names opponents only for `hostile` and `party`, and gives "no weapon → dodge" as the fallback. The fallback now also covers "no opponent".
4. **NPC turns run only after an action-using call.** That means `attack`, `cast_spell` and `dodge` (CLAUDE.md §4.5). They stop when the turn reaches the PC or the encounter ends. `take_npc_turn` is the one place an NPC call is executed, and where the 5.2 validator will check it. The policy only proposes legal calls, so a rejected NPC call is a bug and raises.

**Reason:** (2) CLAUDE.md §4.4 says initiative fixes the order and `active_combatant_id` names whose turn it is. If the encounter started on an NPC's turn and the engine waited for the player's call, that call would be rejected with `NOT_YOUR_TURN`. Making the PC always act first would override the initiative rolls. The audit schema already allowed `before_call` for the bookkeeping steps; only `npc_action` was fixed to `after_call`. (3) No scenario puts a neutral combatant in an encounter, but the policy must be total, and dodging is the agreed fallback.

**Changed:**
- `adm/engine/npc.py`, `docs/npc_policy.md` and `tests/engine/test_npc.py` are added.
- `adm/engine/combat.py`: `advance_initiative`, `expire_dodge` and `end_encounter_if_over` take a `when` keyword, defaulting to `after_call`.
- `schemas/audit.schema.json`: `npc_action.when`.
- `tests/test_audit_log.py`: the reject case `npc_action_before_call` becomes an accept test.
- `adm/orchestration/prompt.py`: the `facts_json` docstring.
- CLAUDE.md: §3 lists `npc.py`, §4.8 states the policy, §9.1 the fact order, and §15 adds item 30.
- `docs/audit_log.md` §2 and `docs/tool_contract.md` §2: before-call NPC turns.

No new dependencies.

## 2026-10-29 — Latency and throughput fields in the audit log (WBS 6.8)

Decided by: CI · Supersedes: none

**Decision:**
1. **`eval_ms` per model call.** Each `model_calls` entry gains `eval_ms`: Ollama's `eval_duration` in milliseconds, the generation time alone. Tokens per second (M6) is `completion_tokens / eval_ms`, the measure the 3.4 benchmark used (`docs/model_benchmark.md` §2). `latency_ms` stays as the call's wall time. A reply without `eval_duration` logs 0, like the token counts.
2. **`turn_latency_ms` per turn.** The turn record gains `turn_latency_ms`: wall time from receiving the player input to writing the record, covering every model call (retries included) and the engine. Seconds per turn (M6) is `turn_latency_ms / 1000`. The turn loop (WBS 6.4, 6.6) measures it.
3. **Both are timings, so neither is replayed.** A byte-identical replay compares every audit field except `timestamp`, `latency_ms`, `eval_ms` and `turn_latency_ms`.
4. **Two cross-field rules.** `turn_latency_ms` is at least the sum of the turn's call latencies, and each call's `eval_ms` is at most its `latency_ms`.
5. **One builder for `model_calls` entries.** `ModelReply.model_call(phase, attempt)` in `adm/orchestration/client.py` returns the entry. The summary uses it, and the turn loop is to use it for the toolcall and narration calls.

**Reason:** Wall time includes evaluating a prompt of about 3000 tokens, so tokens per second from `latency_ms` would understate generation speed and could not be compared with the 3.4 figures. Summing the call latencies would leave out the engine and anything between calls, so seconds per turn gets its own field. The mean and p95 summaries stay in WBS 10.4.

**Changed:** `adm/orchestration/client.py`: `ModelReply.eval_ms` and `ModelReply.model_call`. `adm/orchestration/summary.py`: `Summary.model_call` uses it. `schemas/audit.schema.json`: `model_call.eval_ms` and `turn_latency_ms`, both required. The three `schemas/examples/audit_turn_*.json`. `tests/orchestration/test_client.py`, `tests/orchestration/test_summary.py` and `tests/test_audit_log.py`. CLAUDE.md: §10.4 M6 row, §11 bullet, example and replay sentence, and §15 adds item 31. `docs/audit_log.md` §1, §3 and §4.5. `docs/conventions.md` §2. No new dependencies.

## 2026-10-29 — State precondition checks (WBS 5.2)

Decided by: SS · Supersedes: none

**Decision:**
1. **One entry point.** `validate(state, call)` in `adm/engine/validator.py` runs the shape check (WBS 5.1) and then steps 2 to 6 of `docs/tool_contract.md` §1, and returns the validated call or the first rejection. It never changes the state. The engine functions keep their own guards, so a call that skips the validator still cannot write an illegal value.
2. **`NEGATIVE_QUANTITY` with none held.** `valid_options` is `{}`, not `{"delta": [0]}`: the most negative legal delta is `-held`, but a delta of 0 is itself a `SCHEMA_VIOLATION`, so offering it would waste a retry. `docs/tool_contract.md` §4 says so.
3. **`ACTOR_UNCONSCIOUS` for `attack` and `dodge` cannot arise in play.** Both need an encounter, during one `NOT_YOUR_TURN` is checked first, and the active combatant is always conscious, because an unconscious one is skipped. The check stays for every tool in the matrix as a guard, and its tests use a hand-built state. In play the code comes from a skill check or a Cure Wounds by an unconscious combatant outside an encounter.
4. **NPC calls are validated.** `take_npc_turn` passes the policy's call through `validate` before executing it (2026-10-27, WBS 4.19, point 4). A rejection is a bug in the policy and raises `ValueError` naming the code.

**Reason:** CLAUDE.md §6.3 and `docs/tool_contract.md` fix the codes, their order and their `valid_options`. These four points are where that text left a choice.

**Changed:** `adm/engine/validator.py`: `check_preconditions` and `validate`. `adm/engine/npc.py`: `take_npc_turn`. `tests/engine/test_preconditions.py` is added: a case for every ticked cell of the tool × code matrix, checked against the matrix and the 19 codes, plus tests for the order, the legal calls and the reproduced `result_rejected_target_unconscious.json`, and a property test that every accepted call executes. `docs/tool_contract.md` §4: the `NEGATIVE_QUANTITY` row. CLAUDE.md is unchanged. No new dependencies; the schemas are unchanged.

## 2026-10-29 — Failure pipeline: retry messages and the null re-prompt (WBS 6.4)

Decided by: CI · Supersedes: none

**Decision:**
1. **Every first `{"tool": null}` is re-prompted.** CLAUDE.md §7.1 re-prompts "when the input clearly needs" a tool, but the loop cannot tell such input from conversation without reading the script, and `expected_call` is not used to drive or grade the model (§12). So the first null reply of a turn is always re-prompted once, if an attempt is left. A second null, or a null on the third attempt, ends the tool phase as `narration_only`, never as a `turn_failure`. A pure-conversation turn therefore costs one extra call; any tool it is pushed into is visible to M3.
2. **A retry is an extra chat turn.** The first call's two messages are sent unchanged, then each earlier reply as an `assistant` message and its structured error as a `user` message, so the third attempt sees both earlier exchanges. This is the only prompt with more than two messages. The `context_budget.md` §5 finding, that models stopped calling tools when history came as chat turns, concerned the K verbatim turns, which stay a transcript in the system message.
3. **Three retry templates** in `config/prompts/`, loaded and checked like the others: `retry_unparseable.txt` gives the parser's expected format and one example, a perception check by the state's player character, so the example never names an unknown id; `retry_rejected.txt` carries the full rejection envelope, whose `message` names the field and type or the state values behind the rejection and whose `valid_options` lists what would pass, so one template serves `SCHEMA_VIOLATION`, `UNKNOWN_ENTITY` and every precondition code; `retry_no_tool.txt` asks the model to select the tool for the input, and to reply null again only if the input has no mechanical effect.
4. **A retry may reduce K.** It is assembled from the previous attempt's `k_used` with its extra messages counted, so a retry that would overflow drops the oldest verbatim turns. The tool phase's last `k_used` is the turn's, and the narration call reuses it.
5. **`turn_failure` follows the last attempt**, as `docs/audit_log.md` §3 says: unparseable, `SCHEMA_VIOLATION`, `UNKNOWN_ENTITY`, or any other code as `precondition`.
6. **Execution is a callback.** There is no seven-tool dispatch in the engine yet, so `run_tool_phase` takes `execute`, called at most once and only with a validated call; its `result_ok` is the last `validation` entry. What a failed turn does next, and writing the record, are WBS 6.5.

**Reason:** CLAUDE.md §7.1 fixes the modes and the budget, but not what the retry says, where it goes in the prompt, or when a null reply "clearly needs" a tool. Points 1 and 2 were chosen with the owner; the rest follow from them and from the audit-log rules.

**Changed:** `adm/orchestration/loop.py` is added: `run_tool_phase`, `ToolPhase`, `RETRY_BUDGET`. `adm/orchestration/prompt.py`: `RETRIES`, `retry_feedback`, and `assemble(followups=...)`. `config/prompts/retry_unparseable.txt`, `retry_rejected.txt`, `retry_no_tool.txt`. `tests/orchestration/test_loop.py` is added, with a recovery and an exhaustion test for each §7.1 mode and a property test that any reply sequence stops within three calls; `tests/orchestration/test_prompt.py` covers `followups` and the retry templates. CLAUDE.md: §3 lists the retry templates, §7.1 and §8 say how a retry is sent, §15 adds item 32. No new dependencies; the schemas are unchanged.
## 2026-10-29 — State diff writer and audit-log append (WBS 5.3)

Decided by: SS · Supersedes: none

**Decision:**
1. **The write path.** `dispatch(state, roller, call, *, check_advantage)` in the new `adm/engine/tools.py` validates a call (WBS 5.1, 5.2), runs the engine function for its tool from the dispatch table, and returns the turn record's validation entry: the rejection, `{"ok": true, "tool": null}`, or the full `result_ok`. It does not append the audit record, as `docs/conventions.md` §1 said it would. A turn record also holds the model calls, the narration and the timings, which only the turn loop has. The loop builds the record and appends it (point 4). `docs/conventions.md` §1 is updated.
2. **Every write is checked against its diff.** `check_write` replays a write's diff on the state from before it and requires the state after it. It runs on every tool call in `dispatch`, on the engine's own writes (`open_encounter`, `after_call` and `increment_turn`), and once more over the whole turn in `engine_fields`. A change with no diff entry, or an entry that does not match a change, raises `UnrecordedWrite`. That is a broken invariant, not a rejection (`docs/conventions.md` §2). This is how "every write produces a diff record" is enforced at run time, not only in tests.
3. **`turn_increment` is built** as `increment_turn`, an `EngineStep` with `step: "turn_increment"` (`docs/audit_log.md` §2).
4. **The writer refuses bad records.** `record_errors`, the §3 rules of `docs/audit_log.md`, moves from `tests/test_audit_log.py` to `adm/engine/audit.py`. `AuditLog.append` writes nothing for a record that fails the schema, fails `record_errors` or belongs to another run, and raises `InvalidRecord`. Each record is one compact JSON line, flushed and synced to disk before `append` returns, so a run that dies keeps every turn it wrote.
5. **`skill_check` advantage** comes from the scenario (§4.7, decision 20), so `dispatch` takes it as the keyword `check_advantage`, not as a call argument.

**Reason:** (1, 4) The audit log is the dataset (CLAUDE.md §11), so an incomplete record should fail when it is written, not when the run is scored. (2) Invariant 2 needs every mutation to be in the log. Checking each write against its own diff catches an engine function that forgets an entry at the write that caused it.

**Open for WBS 6.4 (not decided here):**
- **Narration-only turns.** Does a turn whose reply is `{"tool": null}` advance `turn_number`? The narration-only case in `tests/test_audit_log.py` records no state change, so it does not.
- **Encounter start on a failed turn.** An encounter starts before its scripted input (§12). If that input's turn then fails, its record has `encounter_start` steps, but §3 says a failed turn changes no state.
- **Scenario DC.** For a scripted skill check, does the loop substitute the scenario's `dc` before validation (decision 20)?

**Changed:** `adm/engine/tools.py` and `adm/engine/audit.py` are added. `adm/engine/combat.py`: `EngineStep` allows `turn_increment`. `adm/engine/state.py`: `data_hash`. `tests/engine/test_audit.py` is added. `tests/test_audit_log.py` imports `record_errors`, `apply_diff` and `step_part` from the engine. `tests/engine/test_preconditions.py`: its property test runs through `dispatch`. `docs/conventions.md` §1 and `docs/audit_log.md`. CLAUDE.md is unchanged: §3 already lists `tools.py` and `audit.py`. No new dependencies; the schemas are unchanged.

## 2026-10-29 — Post-write invariant assertion (WBS 5.4)

Decided by: SS · Supersedes: none

**Decision:**
1. **One check, after every write.** `check_state` in `adm/engine/state.py` checks the state schema and the cross-field rules of `docs/state_schema.md` §3, and raises `IllegalState` (a `StateValidationError`). The write path in `adm/engine/tools.py` runs it after every write: `dispatch`, `open_encounter`, `after_call` and `increment_turn`. It runs after the diff check of WBS 5.3. CLAUDE.md §5's "validate after every write" now holds at run time, and so does invariant 5 (`0 <= current_hp <= max_hp`).
2. **A failed write is undone.** If the diff check or the state check fails, or the engine function itself raises, the state is put back as it was before the write, and the exception propagates. So an illegal state raises rather than persists, and the caller's state is left legal. It is a bug, not a rejection: the dice roller has moved on, so the run stops.
3. **Load and save check the cross-field rules too.** `cross_field_errors` moves from `tests/test_state_schema.py` to `adm/engine/state.py`. `GameState.from_dict` (so `load_state`) and `save_state` run it after the schema, so an illegal state file neither loads nor is written.
4. **The `encounter_outcome` rule is narrowed.** `docs/state_schema.md` §3 said "`victory` means every hostile is unconscious". The engine decides victory over the hostiles in the encounter's initiative order (WBS 4.8), and `s08_old_mine` keeps a giant spider for its second encounter. So after the first victory the state is `victory` with an active hostile, which is legal. Once an encounter ends, the state no longer records who was in it. The rule is now what the state can show: `victory` needs a conscious player character and `defeat` an unconscious one. Victory over the encounter's hostiles is decided, and tested, where the encounter ends (`encounter_outcome`).

**Reason:** (2) "An illegal state raises rather than persists" (WBS 5.4). Raising after the in-place write would leave the caller holding the illegal state. (4) Enforcing the rule as written would stop s08 on a legal state. Scoping it to the encounter needs data the state does not keep. Agreed with SS on 2026-10-29.

**Changed:** `adm/engine/state.py`: `cross_field_errors`, `check_state` and `IllegalState`; `from_dict` and `save_state` run the cross-field rules. `adm/engine/tools.py`: every write goes through `_write`, which checks and undoes. `tests/engine/test_invariants.py` is added. `tests/test_state_schema.py` imports `cross_field_errors` from the engine and tests the narrowed outcome rule. `docs/state_schema.md` §3 and `docs/conventions.md` §1. CLAUDE.md is unchanged. No new dependencies; the schemas are unchanged.

## 2026-10-30 — Exhausted-budget fallback and failed-turn records (WBS 6.5)

Decided by: CI · Supersedes: none

**Decision:**
1. **A failed turn is logged and does not advance.** `fail_turn` in `adm/orchestration/loop.py` writes the record of a turn whose tool phase exhausted the retry budget: no narration call, no step after the call and no `turn_increment`, so `turn_number` and initiative stay where they were. The record's `narration`, and what the player sees, is `REPHRASE`, the text of `schemas/examples/audit_turn_rejected.json`. Interactive play asks for new input and a scripted run takes its next one, so both just play the next turn (2.6 decision 3). `turn_record` builds the condition D record and is reused for narrated turns (WBS 6.6), with a `TurnTimer` for `timestamp` and `turn_latency_ms`.
2. **Encounter start on a failed turn** (5.3 open point). The failed record keeps the `before_call` steps of an encounter that started before it: `encounter_start` and the turns of NPCs who won initiative. `docs/audit_log.md` §3 now says a failed turn has no `after_call` step, instead of no state change. The `narration_facts` of those NPC actions are returned as `FailedTurn.carried_facts` and go first in the next narrated turn's `{narration_facts_json}`, so they are narrated once.
3. **Narration-only turns advance** (5.3 open point). A turn that ends on `{"tool": null}` is played and narrated, so it ends with a `turn_increment` like any other turn that does not fail. `record_errors` now requires every condition D turn that does not fail to end with exactly one `turn_increment`.
4. **Failures are counted** from the log: `turn_failure_counts(records)` in `adm/engine/audit.py` counts failed turns by kind, so `eval` can report them without importing orchestration.

**Reason:** CLAUDE.md §7.1 says a failed turn does not advance but is logged and counted; it does not say what happens to an encounter that started before it, and the 5.3 rule that a failed turn changes no state cannot hold then. Rolling the encounter back would drop logged rolls (invariants 2 and 3). Narration-only turns advancing keeps `turn_number` close to `input_index` and matches the A–C replay, where an input with no `expected_call` is still a turn. Points 2 and 3 were chosen with the owner. The scenario-DC point of the 5.3 entry stays open.

**Changed:** `adm/orchestration/loop.py`: `REPHRASE`, `TurnTimer`, `turn_record`, `FailedTurn`, `fail_turn`. `adm/engine/audit.py`: the two `record_errors` rules and `turn_failure_counts`. `tests/orchestration/test_loop.py`, `tests/engine/test_audit.py` and `tests/test_audit_log.py`: a failed turn of each kind, consecutive failed scripted turns, a failed turn after an encounter start, the narration-only `turn_increment`, and the new rejections. `docs/audit_log.md` §3. CLAUDE.md: §7.1, §9.1 and §15 items 33–34. No new dependencies; the schemas are unchanged.

## 2026-10-30 — Narration call and narrated-turn records (WBS 6.6)

Decided by: CI · Supersedes: none

**Decision:**
1. **The facts array.** `turn_facts` in `adm/orchestration/loop.py` builds `{narration_facts_json}` in the order things happened: facts carried from a failed turn (WBS 6.5), the NPC actions before the call, the player's executed call, then the NPC actions after it (2.6 decision 10, CLAUDE.md §9.1). It reads only the `narration_facts` of the result and of each `npc_action` step, so the narration call never sees the state, the diff or the rolls.
2. **A narration-only turn has no player facts.** No call ran, so its array holds only NPC and carried facts, and is `[]` when there are none. The frozen `d_narration.txt` is sent unchanged.
3. **One K per turn.** The narration call reuses the tool phase's `k_used`. The narration prompt holds no state or tools, so it is far smaller than the tool-call prompt (`docs/context_budget.md`: 3832 of 7892 tokens at the worst case, K = 8). One that would still need K reduced is a bug and raises `PromptTooLarge`, as the summary call does.
4. **The narration is the stripped reply.** `narration` is the reply with surrounding whitespace removed, and the raw reply stays in the model call's `raw_output`. `narration_filtered` is false until the safety filter (WBS 6.9).
5. **`narrate_turn` writes the record.** Like `fail_turn`, it takes the turn's engine steps, which must end with `turn_increment`, narrates, and appends the record. When the caller passes `fold` (the turns since the last regeneration, decided with `summary.is_due`), the rolling summary is regenerated with this turn's narration before the record is written, so its call and `summary` field are in the same record. The driver that runs a whole turn, from encounter start to the log, is the CLI's (WBS 6.10).

**Reason:** CLAUDE.md §9.1 fixes the template and the facts order but not what a narration-only turn sends, which K the second call uses, or where the summary call goes in the turn. The scope (narration and record here, the driver in 6.10) was chosen with the owner. "The model describes the numbers" is checked by tests that every value of the facts reaches the prompt; no test calls the model (§13), so how well it describes them is measured by the smoke runs (6.11) and the checker.

**Changed:** `adm/orchestration/loop.py`: `turn_facts`, `Narration`, `narrate`, `NarratedTurn`, `narrate_turn`; `fail_turn` shares the NPC-facts helper. `tests/orchestration/test_loop.py`: the facts and every number in the prompt with no state, the record, the facts order around an NPC-first encounter, carried facts, a narration-only turn, the turn's K, the K overflow, the summary fold, and the refused failed phase. CLAUDE.md: §15 item 35. No new dependencies; the schemas and templates are unchanged.

## 2026-10-30 — Text command-line client and the encounter schedule (WBS 6.10)

Decided by: CI · Supersedes: none

**Decision:**
1. **When an encounter starts in interactive play.** `before_input` indexes `scripted_inputs`, and interactive play has no `input_index`. The encounter with `before_input: n` starts just before the player's n-th input of the session, counted from 0, failed turns included, as a scripted run counts them (a failed turn still uses up its input, 2.6 decision 3). `input_index` stays `null` in the record.
2. **An encounter that is due while one is active waits.** Encounters start in scenario order, one at a time. One whose input has come while the encounter before it is still running starts before the first input after that one ends, so no encounter is skipped. Only `s08_old_mine` has two, and whether the first is over by input 15 depends on the seed. `due_encounter` in the new `adm/engine/scenario.py` holds this rule, in the engine, so the scripted runner and the A–C replay can apply the same one.
3. **The scenario loader.** `load_scenario` checks a scenario against `schemas/scenario.schema.json`, and `initial_state` builds the turn-0 state of docs/scenario_format.md §2 (the reference `initial_game_state` in `tests/test_scenario_schema.py`), checked by `GameState.from_dict`.
4. **The session driver.** `Session` in `adm/orchestration/session.py` plays one turn per input: the due encounter, the tool phase with `tools.dispatch` as `execute`, then `fail_turn`, or `after_call`, `turn_increment` and `narrate_turn`. It keeps the verbatim history (narrated turns only), the rolling summary and the facts carried from failed turns.
5. **One log per run.** A session whose `runs/D/<scenario_id>/<seed>.jsonl` already exists is refused before the model loads, so two sessions never append under one `run_id`.
6. **The client.** `python -m adm.cli play --scenario … --seed … [--runs runs]` checks the model against `config/model.json` and loads it fresh (docs/model_selection.md §4), shows the scenario's title and opening narration, and then one narration, or the request to rephrase, per input. `/quit`, `/exit`, end of input or Ctrl+C ends the session. A Ctrl+C during a turn ends the session without logging that turn.

**Reason:** CLAUDE.md §12 ties encounters to scripted inputs only, and nothing said what happens when one is due while another runs; `start_encounter` raises then. Points 1 and 2 were chosen with the owner. Counting inputs rather than narrated turns keeps interactive play and scripted runs on one rule.

**Changed:** `adm/engine/scenario.py`, `adm/orchestration/session.py` and `adm/cli.py` are added, with `tests/engine/test_scenario.py`, `tests/orchestration/test_session.py` and `tests/test_cli.py`. CLAUDE.md: §12 and §15 items 36–37. No new dependencies; the schemas and templates are unchanged.

## 2026-10-30 — Scripted condition D runs, the scenario DC, and the smoke runs (WBS 6.11)

Decided by: CI · Supersedes: none

**Decision:**
1. **The scenario DC is substituted at execution** (the 5.3 open point). For a scripted input whose `expected_call` is a `skill_check`, a `skill_check` from the model is validated as proposed, so `DC_OUT_OF_RANGE` stays reachable, and then executed with the scenario's `dc` and `check_advantage` (CLAUDE.md §4.7, decision 20). `proposed_calls` and `executed_call` keep the model's call, so its `dc` is the one logged and `record_errors`' rule that the executed call is the last proposal still holds. The result's `narration_facts` carry the DC that was rolled against. If the input expects any other call, or none, the model's `dc` is used with no advantage. The substitution is in `Session._execute` (`adm/orchestration/session.py`); the engine is unchanged.
2. **Scripted runs.** `Session.play` takes the scripted input and its `input_index`, which reaches the record of a narrated or failed turn. `run_script` plays every input in order and moves on after a failed turn (decision 23). `python -m adm.cli run --scenario … --condition D --seed …` is the unattended entry point. Only `D` is accepted for now; A to C join the same command with WBS 7.1 to 7.4.
3. **The smoke grid.** `experiments/smoke_grid.json`: the four long scenarios, the only ones with 50 or more inputs (52 each), long01 and long02 three seeds each and long03 and long04 two each, seeds 1001 to 1010. `python -m adm.cli smoke --manifest experiments/smoke_grid.json` plays them with a freshly loaded model per run and writes `results/bench/smoke/<UTC time>/summary.json`.
4. **Complete and unrecoverable.** A run is complete when nothing raised and its log holds exactly one record per scripted input, in order. Any exception (a model error after the client's retries, an illegal state, a refused record) or a missing input makes it unrecoverable. A failed turn does not: the pipeline recovers from it by design (§7.1), so it is counted. Gate G2 needs ten runs attempted and at least nine complete; that is also the Objective 2 criterion, that condition D sustains a 50-turn session.
5. **The R1 figure.** The tool-call schema-valid rate of the 3.7 revisit trigger is the share of turns whose first toolcall attempt parses and passes the schema (neither unparseable nor `SCHEMA_VIOLATION`). Below 80% fires R1.
6. **Resuming.** A run whose log exists is read, not played again: a complete log counts as it is, and an incomplete one counts as unrecoverable, so evidence is never overwritten.

**Reason:** (1) Validating the model's own `dc` keeps D's rejection data honest, and substituting after validation needs no change to the audit-log rules; the state still follows the scenario's ground truth, as decision 20 requires. Chosen with the owner. (3, 4) TASK_CHECKLIST.md defines G2 as "ten smoke runs attempted, at least nine complete without unrecoverable failure" but not what complete means; §7.1 makes turn failures a reported metric, not a crash. The grid was chosen with the owner. (2, 3) The smoke driver lives in the CLI because `adm/bench` may not import orchestration (docs/conventions.md §1); `adm/bench/smoke.py` only schedules runs and reads logs.

**Changed:** `adm/orchestration/session.py`: `Session.play(…, input_index=, scripted=)`, the DC substitution, `run_script`. `adm/cli.py`: `run` and `smoke`, sharing `open_session` with `play`. `adm/bench/smoke.py` and `experiments/smoke_grid.json` are added, with `tests/bench/test_smoke.py`; `tests/orchestration/test_session.py` and `tests/test_cli.py` gain the scripted cases. `docs/smoke_runs.md` holds the results. CLAUDE.md: §2 the `smoke` command, §4.7, §15 items 38–39. No new dependencies; the schemas and templates are unchanged.

## 2026-11-01 — No approving review required to merge into main (WBS 1.1)

Decided by: CI · Supersedes: 2026-09-30 — CI pipeline and required status check on main (the "one approval" rule only)

**Decision:** Pull requests into `main` no longer need an approving review to merge. Branch protection still requires a pull request, the `test` status check with the branch up to date with `main`, and resolved conversations, and administrators are not exempt.
**Reason:** Requested by the repository owner, so that a pull request can merge as soon as `test` passes.
**Changed:** Branch protection on `main`: `required_approving_review_count` from 1 to 0. No files other than this log.

## 2026-11-01 — Intent-fidelity protocol v0.9: sampling and decision rules (WBS 8.14)

Decided by: SD · Supersedes: none

**Decision:** CLAUDE.md §10.4 defines M3 as a binary, human-annotated judgement on a 15% random sample. `docs/intent_fidelity.md` fixes what that leaves open. (1) **Scope.** Condition D only, since A–C execute no call. Turns with `turn_failure` set are excluded, since they ran no call and are counted by M2. A `{"tool": null}` reply is included, and only the final executed call is judged. (2) **Sampling rule.** Stratified by `scenario_id`. Each stratum is ordered by `sha256("m3-v1/" + run_id + "/" + input_index)` and its first `ceil(0.15 × n)` records are taken. The R5 fallback to 10% is a prefix of the same order. `expected_call` plays no part in the draw. (3) **Decision rule.** Six ordered rules, ending in "when in doubt, faithful". Each unfaithful turn gets one reason code: `MISSED`, `INVENTED`, `WRONG_TOOL`, `WRONG_TARGET`, `WRONG_VALUE` or `DROPPED`. `dc` and the wording of `justification` are not judged. (4) **Blinding.** The annotator sees the input, the executed call and the state before the turn, but not the narration, `expected_call` or the condition.
**Reason:** A hash order is reproducible from the dataset alone, does not depend on the order runs finish, survives the 9.10 re-runs, and uses no RNG (invariant 3). It also makes the 10% fallback a subset, so no scored turn is wasted. Stratifying keeps the long sessions at their real share. Hiding `expected_call` follows §12: a different but reasonable call is not a failure. Resolving doubt towards faithful matches the rubric (§3, rule 5) and makes M3 a lower bound.
**Changed:** `docs/intent_fidelity.md` added. CLAUDE.md is unchanged. Two points are left for the Week 5 checkpoint (#75): whether M3 gets a second annotator for Krippendorff's alpha, and who annotates (9.7).

## 2026-11-01 — Narrative-quality form v0.9: excerpts, sampling and blinding (WBS 8.13)

Decided by: SD · Supersedes: none

**Decision:** CLAUDE.md §10.4 defines M5 as two blind raters scoring 1–5 on coherence, vividness and tone appropriateness, plus an engagement item. `docs/narrative_quality.md` fixes what that leaves open. (1) **Unit.** An excerpt of five consecutive exchanges (player input and the narration shown) from one run, rated as a whole. (2) **Sample.** One excerpt per scenario and condition, 16 × 4 = 64, paired: the four excerpts of a scenario share one seed and one window of inputs. Both raters rate all 64. (3) **Choice.** By hash order, not an RNG: the first seed in `sha256("m5-v1/" + scenario_id + "/seed/" + seed)` order, and the first window in `sha256("m5-v1/" + scenario_id + "/window/" + w)` order in which all four runs narrated all five inputs. (4) **Blinding.** An opaque `excerpt_id`, only the title, inputs and `narration` shown, no turn numbers, a per-rater shuffled order, and the key held back until both raters finish. (5) **Scales.** Anchored descriptors at 1, 3 and 5 for the three quality items. Engagement is a five-point "definitely not" to "definitely yes". (6) **Agreement.** Ordinal Krippendorff's alpha per item over all 64. (7) **R5 fallback.** The 48 short-scenario excerpts, chosen before rating starts.
**Reason:** Coherence and engagement cannot be judged on a single 2–4 sentence reply. Pairing removes scenario and stimulus differences from the condition comparison. A window with a failed turn would reveal condition D, since only D fails and a failed turn shows `REPHRASE`, so such windows are skipped in all four conditions at once. 64 excerpts at about 3.5 minutes fit the 4 hours of 9.8 and 9.9.
**Changed:** `docs/narrative_quality.md` added. CLAUDE.md is unchanged. Open for the Week 5 checkpoint (#75): the excerpt length and count, and what the annotation tool (8.15) needs from the form.

## 2026-11-01 — Weekly checkpoint, Week 4 (WBS 12.4)

Attendees: SS, CI, SD · Note-taker: SD

**Closed:** 4.6, 4.14, 4.15, 4.16, 4.17, 4.19, 5.1, 5.2, 5.3, 5.4, 6.2, 6.4, 6.5, 6.6, 6.7, 6.9, 6.10, 6.11, 8.3b, 8.14. Two Week 5 tasks also closed early: 6.8 and 8.13.
**Slipped:** none past Week 4. 4.14, 4.15 and 4.16 merged on 29 Oct, one to three days after their dates, and 4.17, which follows 4.16, closed on 1 Nov; 6.9 and 8.14 closed on 1 Nov. None held up G2. The checkpoint itself was held on Sun 1 Nov instead of Sat 31 Oct.
**Hours vs. estimate:** SS 21/21 · CI 21/21 · SD 16/16. Actual hours equal the `TASK_CHECKLIST.md` estimates, plus 4.19 (SS, 4 h), 6.8 (CI, 1.5 h) and 8.13 (SD, 1.5 h).

**Gates and risks:** G2 / Milestone 1 (1 Nov) is met: ten 50-turn smoke runs attempted, ten complete (`docs/smoke_runs.md`, 6.11). The Objective 2 criterion is met. R2 has not fired, so Condition C stays and the ladder keeps four conditions. R1 has not fired: the first-attempt schema-valid rate is 99.0% (515 of 520 turns). R3 did not fire at 6.2. R4 has not fired: condition D averaged 4.83 s per turn, so the 9.1 and 9.2 grid, about 2,000 turns per seed, projects to about 3 hours per seed, far below 40 hours. R7 and R8: no new mechanic proposed and no absence. R5 and R6 are not yet due.

**Decisions:**
1. G2 is confirmed as met on the 6.11 evidence, and the four-condition ladder (A, B, C, D) stands. — The fallback in R2 is not needed. — Nothing changed.
2. The G2 evidence (the ten logs, the aborted 1009 log and `results/bench/smoke/`) is uploaded to the shared Drive folder by CI before the Week 5 checkpoint (Sat 7 Nov). — Until then it exists on one laptop only, and under the README's rules the Drive copy is the dataset (`docs/smoke_runs.md` §5). — Nothing changed.
3. The Ollama tray app's auto-update is turned off, or batches run from a bare `ollama serve`, by CI before the 7.7 dry run (#83). — The client refuses any version other than 0.35.1, so an auto-update would stop a run (`docs/smoke_runs.md` §2, §5). — Nothing changed.
4. Issues are closed by their pull request. #55, #57, #59 and #67 were closed by hand because #170, #172, #173 and #174 did not say `Closes #N`. Every pull request for a WBS task names its issue that way (CLAUDE.md §2.3). — Closing by PR links the issue to the work. — Nothing changed; the rule is already in CLAUDE.md.

**Open, carried to next week:** from 8.14, whether M3 gets a second annotator for Krippendorff's alpha, and who annotates (9.7) — SD, CI · from 8.13, the M5 excerpt length and count, and what the annotation tool (8.15) needs from the form — SD, CI

## 2026-11-01 — Condition D wired into the common runner (WBS 7.4)

Decided by: CI · Supersedes: none

**Decision:** `python -m adm.cli run --condition X` is the one entry point for all four conditions. (1) **Harness contract.** `adm/orchestration/session.py` defines `Harness`: a `scenario`, the run's `log`, and `play(player_input, *, input_index, scripted)`, which logs a turn and returns it as a `PlayedTurn` (`record` and `message`). `HarnessStart` builds one with the same arguments as `Session.start`, which is condition D's. `run_script` plays any harness, with each scripted input and its `input_index` passed the same way in every condition. (2) **Registry.** The composition root, `adm/cli.py`, maps each condition to its `HarnessStart` in `HARNESSES`. Only `D` is registered. WBS 7.1 to 7.3 add A, B and C there, one line each, with no other CLI or runner change. (3) **Refusal order.** An unknown condition, or one with no harness yet, exits with code 2 before its log is created or the model loads. (4) **Run logs.** `new_run_log` takes the condition, so a run is refused only when the same `(condition, scenario_id, seed)` already has a log. `play` (interactive) and `smoke` (gate G2) stay condition D and use the same `open_session`.
**Reason:** `docs/conventions.md` §1 says no `if condition == ...` outside the templates and the tool-wiring flag. Choosing a harness in one table keeps that rule, and invariant 7 holds because every condition gets the same scenario, seed, model load and scripted inputs from one code path. Fixing the contract now lets the A to C harnesses (SS) land in parallel without touching the runner. The 7.6 batch runner can then call the same `open_session` and `run_script`.
**Changed:** `adm/orchestration/session.py`: `PlayedTurn`, `Harness`, `HarnessStart`, `new_run_log(condition=...)`, and `run_script` takes any harness. `adm/cli.py`: `CONDITIONS`, `HARNESSES`, `open_session(condition=...)`, and `run`'s refusals. `tests/test_cli.py`: A to C are refused before a log or model load, an unknown condition is refused, and a fake harness registered for A runs through `run` unchanged. `tests/orchestration/test_session.py`: `run_script` runs any harness, and log names follow the condition. `tests/bench/test_smoke.py` passes the condition. CLAUDE.md is unchanged. No new dependencies; the schemas are unchanged.

## 2026-11-01 — Alignment with the project canvas and project form (ideation form)

Decided by: CI · Supersedes: none

**Decision:** The course's project canvas and project form (CSC493/691, filled in on 1 Nov) commit the project to six things the repository did not yet do. (1) **AI label and result line.** `play` shows "Narrated by AI" beside the scenario's title and, before each narration, one result line per mechanical outcome, in the order it happened: NPC actions before the call, the player's executed call, NPC actions after it (e.g. "Lyra -> giant rat (short sword): 17 vs AC 12, hit, 7 damage; giant rat 4/11 HP"). `result_lines` in `adm/cli.py` builds them from the turn's audit record only. They are not logged and not sent to the model, so the experiment, the audit log and replay are unchanged; `run` and `smoke` do not show them. (2) **Non-graphic violence.** The form names an audience of 8 and up, and proposal v4 §14 promised a system-prompt restriction to non-graphic fantasy violence that was never added. One line is added to the end of the shared preamble in all five templates: "Keep violence non-graphic and suitable for players aged 8 and up." It is identical in every condition (invariant 7). The safety filter (6.9) is unchanged. (3) **Sponsor User sessions.** Five friends play development builds and give informal feedback. They play with `--runs sponsor_runs/`, which is gitignored, so a sponsor session can never clash with or be mistaken for a main-run log. It is not a study (CLAUDE.md §14). (4) **Licence.** MIT for the code, scenarios and released data (`LICENSE`); `NOTICE` holds the SRD 5.1 attribution and the Llama 3.1 Community License notice ("Built with Llama"). (5) **Targets and analysis, fixed before scoring.** H1: D has at least 50% fewer confirmed divergences per 100 turns than A, tested by a D/A ratio of at most 0.5 whose 95% interval excludes 1. H2: D's narrative quality is no worse than A's, as the 95% interval of the D minus A difference per M5 item. p95 under 10 s per turn in D. Every interval is a percentile bootstrap over whole runs, 10,000 resamples, stratified by condition. RQ2 is the per-condition slope of divergence over turn number. (6) **Main grid.** 16 scenarios × 4 conditions × 3 seeds, 2001, 2002 and 2003 in every cell: 192 runs, about 6,100 turns, about 6–9 hours on the 6.11 machine. The manifest itself is written by WBS 7.6 in its own format.
**Reason:** (1) The form's human-AI interaction answers (section 3.vi) say users are told the narrator is an AI and can see why it did what it did; the record already holds every fact, so showing it costs nothing and changes no measured output. (2) The preamble is frozen at 7.5, which has not happened, so this is the last cheap moment; adding the line to the shared block keeps the conditions identical. The ten 6.11 smoke runs used the old preamble; they remain the G2 evidence, but they are not comparable to main-grid runs, which no analysis does. The worst-case prompt grows by about 15 tokens, well inside K_fit = 10. (3) `play` logs every turn (invariant 2), so a separate folder, not a no-log mode, is the way to keep sponsor sessions out of the dataset. (5, 6) Fixing hypotheses and tests before the data exist keeps the analysis honest; three seeds give the bootstrap repeats per cell without exceeding the annotation budget (R5), and the time is far below the R4 trigger of 40 hours.
**Changed:** `adm/cli.py` (`AI_LABEL`, `result_lines`, `_result_line`, the title and the turn display), `tests/test_cli.py` (label, result line per tool, order, failed turn, display only). `config/prompts/a.txt`, `b.txt`, `c.txt`, `d_narration.txt`, `d_toolcall.txt` and `tests/orchestration/test_prompt.py` (the preamble). `LICENSE`, `NOTICE` added. `README.md`: how to play, Sponsor User sessions, licence. `.gitignore`: `sponsor_runs/`, `ideationForm/`, `Claude outputs/`. CLAUDE.md: §9.1 preamble, new §10.5, §14 Sponsor Users, §15 items 42–46. `adm/bench/toolcall.py` keeps the old preamble on purpose: it is the frozen Week 2 benchmark. No new dependencies; the schemas are unchanged.

## 2026-11-02 — Annotation tool: blind and condition-shuffled (WBS 8.15)

Decided by: CI · Supersedes: none

**Decision:** `python -m adm.eval.annotate` (`adm/eval/annotate.py`) is the tool for M5 and M3. M1 annotation is not in it: the rubric has no sampling rule or record format yet, and is frozen at 8.12. (1) **M5** follows `docs/narrative_quality.md` as written: the excerpt choice of §2, `excerpt_id` and the per-rater order of §3, the items and anchors of §4, the record of §5. The rater sees the title, the five inputs and the narration, nothing else. `--short-only` is the §7 fallback. (2) **The M5 key.** `results/m5_key.json` is written on the first run. Every later run recomputes the selection and refuses to start if it differs, so a rater never rates against a key that no longer matches the logs. (3) **M3 state.** `docs/intent_fidelity.md` §3.2 shows "the state before the turn". The tool shows the state the tool-call prompt saw: the state before the turn, plus the turn's `before_call` engine steps. On the input an encounter opens, that is the encounter as active with the NPC actions that went first, which is what the model was asked to act on. The state is rebuilt by replaying each earlier record's `state_diff` from the scenario's initial state; every `state_before_hash` and `state_after_hash` is checked on the way, and a log that does not replay is refused. (4) **M3 order.** The sample is shown in draw-key order (`sha256("m3-v1/" + run_id + "/" + input_index)`) across all strata, so scenarios and seeds are interleaved. The turn is labelled by the first 8 hex digits of that key. `--rate 0.10` is the §2 rule 4 fallback. (5) **Re-rating.** `--redo <id>` rewrites the earlier line in place, and needs a non-empty note. Without it, an item already rated by that rater is skipped, so a rater who stops with `q` resumes where they stopped.
**Reason:** (3) M3 judges whether the call matches the request given what the model could see; the encounter state at the call is that, and §3.2's list of what is shown is unchanged. Checking the hashes makes a corrupt or hand-edited log fail loudly instead of showing a wrong state. (2, 4) Hash orders keep everything reproducible from the logs and use no RNG (invariant 3). (5) §5 of the form says a re-rating replaces the earlier line and is noted; the note is where it is noted. The tool was checked on the ten G2 smoke logs: all 520 turns replay to their hashes.
**Changed:** `adm/eval/annotate.py` and `tests/eval/test_annotate.py` added. CLAUDE.md: §2 commands, §15 item 47. `docs/narrative_quality.md` §8 and `docs/intent_fidelity.md` §5 point to the command. No new dependencies; the schemas are unchanged.

## 2026-11-03 — Replay harness and the A–C ground truth (WBS 4.18)

Decided by: SS · Supersedes: none

**Decision:** (1) **What is replayed.** `replay_script(scenario, seed)` in `adm/engine/replay.py` plays the scenario's scripted inputs through the engine with no model. Each input proposes exactly its `expected_call`, or `{"tool": null}` when that is null. It then runs as a scripted condition D turn does, using the same engine functions in the same order: the due encounter opens, the call goes through the write path, then `after_call` and `turn_increment` run. (2) **Rejections.** A rejected expected call is a failed turn, with `turn_failure` named as in §7.1: nothing runs after it, and `turn_number` does not advance. This is what condition D gives when its retry budget runs out on the same call. A null call is a narration-only turn and advances (decision 34). Rejections such as `ENCOUNTER_OVER` stay in the replay as data (decision 23). (3) **Ground truth.** The replay is the A–C ground truth of §9: the state after each input, and both A–C state hashes, come from it. Each `ReplayTurn` uses the audit record's field names and adds `state`. (4) **One scripted-DC rule.** The scenario-DC substitution of decision 38 moves from `Session._execute` into the engine as `tools.dispatch_scripted`, and both the session and the replay call it. (5) **Comparing runs.** `log_differences(first, second)` lists every record path where two audit logs differ, leaving out `timestamp`, `latency_ms`, `eval_ms` and `turn_latency_ms` (§11, decision 31). An empty list means the second run replays the first.
**Reason:** §9 says the ground truth is computed "by replaying the scripted inputs through the engine", but not what happens when an expected call is rejected. This is common: at seed 12345, 15 of the 16 scenarios have at least one, because decision 23 keeps the script fixed when a fight ends early. Playing each input as condition D would play it, with a model that always proposes the expected call, gives one rule with no new cases. It keeps the ground truth and condition D in one code path, so the two cannot drift apart (invariant 7). A test checks this for all 16 scenarios: every replayed field of an oracle condition D run equals the replay. Moving the DC rule into the engine is part of keeping that one code path. `adm/eval` may import the engine but not orchestration (`docs/conventions.md` §1), so the checker can build the ground truth itself.
**Changed:** `adm/engine/replay.py` and `tests/engine/test_replay.py` added. `adm/engine/tools.py`: `dispatch_scripted`. `adm/orchestration/session.py`: `_execute` calls it. `adm/engine/audit.py`: `_failure_kind` is now public as `failure_kind`. `tests/orchestration/test_session.py`: an oracle D run equals the replay for every scenario, and two runs of one seed differ only in the timings (invariant 4). CLAUDE.md: §9 (one sentence), §15 item 48. `docs/rule_suite.md` §6: the replay row is passing. `README.md`: test table. No new dependencies, and the schemas are unchanged.

## 2026-11-03 — Condition A harness and the narration-only runner (WBS 7.1)

Decided by: SS · Supersedes: none

**Decision:** (1) **One harness for A to C.** `NarrationOnlySession` in `adm/orchestration/narration_only.py` plays conditions A, B and C, keyed only by its template. `NarrationOnlyStart("a")` is registered for A in `adm/cli.py`'s `HARNESSES`. WBS 7.2 and 7.3 each register theirs in one line. (2) **The turn.** One `narration` call per input, at temperature 0.7 with the narration reply cap, on the assembled template with the rolling summary, the last K turns and the input. K is reduced and logged in `k_used` as in condition D. The reply goes through the same safety filter. The rolling summary is regenerated after every K-th turn, as in D. Every turn is narrated and joins the history. (3) **Which state.** The ground truth for an input is the state after that input in `replay_script` (WBS 4.18). Both state hashes are that state, and it is the state handed to the template; template `a` uses none of it. `turn_number` is the replay turn's, so it repeats where the expected call is rejected, just as an oracle condition D run would. (4) **Scripted only.** A turn without an `input_index` is refused with `NotScripted`, since only scripted inputs have a ground truth. Interactive `play` stays condition D.
**Reason:** (1, 2) Invariant 7 lets A to D differ only in the template and the tool wiring, so the context strategy, sampling and filter must be D's. One harness keyed by its template keeps the rule in `docs/conventions.md` §1: no `if condition == ...`. (3) `docs/audit_log.md` §4.4 (decision 4 of the 2.6 review) makes the hashed state, the injected state and the scored state one and the same. `docs/rubric.md` §1 scores condition D against the state after the turn. Using the after-state for A to C keeps the two comparable. B and C (7.2, 7.3) inherit this: the state they inject is the after-state. (4) §9 defines A–C's state only by replaying the script.
**Changed:** `adm/orchestration/narration_only.py` and `tests/orchestration/test_narration_only.py` added. `adm/cli.py`: `HARNESSES` registers A. `tests/test_cli.py`: `run --condition A` plays a scenario end to end. CLAUDE.md §15 item 49. `README.md`: test table. No new dependencies; the schemas and prompt templates are unchanged.

## 2026-11-03 — Condition B harness: what "injected identically" means (WBS 7.2)

Decided by: SS · Supersedes: none

**Decision:** Condition B is `NarrationOnlyStart("b")` in `adm/cli.py`'s `HARNESSES`, the narration-only harness of WBS 7.1 on template `b`. No code beyond that registration was needed. The done-when "state injected identically to Condition D" is read as: given the same state, B's system message and D's tool-call system message are byte-identical from the first byte to `</state>`. That covers the same preamble, the same lead-in ("The authoritative game state…"), the same serialisation (`prompt.state_json`: sorted keys, indent 2) and the same place, right after the preamble. The state B injects for an input is that input's ground truth: the replay's state after it, as fixed for A–C at WBS 7.1. B differs from A only by that block.
**Reason:** One call in B has to stand in for D's two. D's tool call sees the state before the call, and its narration call sees the facts of the outcome. The ground truth after the input is what B's narration is scored against (`docs/rubric.md` §1, `docs/audit_log.md` §4.4). Injecting a different state from the one it is scored against would count the engine's dice as the model's divergences. So "identically" constrains the injection's form, which is what invariant 7 controls, while its content is the ground truth.
**Changed:** `adm/cli.py`: `HARNESSES` registers B. `tests/orchestration/test_narration_only.py`: B runs every scenario end to end; it injects each input's ground-truth state; its prompt matches D's tool-call prompt byte for byte up to `</state>`; it differs from A only by the state block. `tests/test_cli.py`: `run --condition B`. `README.md`: test table. CLAUDE.md, the templates and the schemas are unchanged.

## 2026-11-03 — Prompt templates v1.0 frozen (WBS 7.5)

Decided by: CI · Supersedes: none

**Decision:** (1) **What is frozen.** All eleven files in `config/prompts/`, not only the four condition templates of CLAUDE.md §9.1: `a`, `b`, `c`, `d_toolcall`, `d_narration`, the shared `summary_block` and `history_block`, the rolling summary's `summary`, and the three `retry_*` messages. The text is the text on `main` after the ideation-form alignment (2026-11-01), as the issue's owner asked; no wording changes. (2) **The record.** `docs/prompt_templates.md` §1 lists each file with its role, placeholders and the sha256 of its LF text, which is the committed blob. §2 gives every line of the five condition templates with its line number in each file, and the four pairwise differences: B is A plus the state block, C is B plus the self-check, D's tool call is B plus the tools block and the instruction, and D's narration is A plus the facts block. §3 lists the frozen wording that §9.1 does not hold and the task that fixed each. (3) **Enforcement.** `tests/orchestration/test_prompt_freeze.py` reads the §1 table and fails if a file is added, removed or changed without the table changing, and it checks each §2 difference paragraph by paragraph. (4) **Line endings.** `.gitattributes` checks `config/prompts/*.txt` out with LF on every platform. The blobs were already LF; on Windows with `core.autocrlf` three working copies were CRLF. `load_templates` reads in universal-newline mode, so prompts were never affected. (5) No git tag: the record and the test are the freeze.
**Reason:** The WBS 6.2, 6.4 and 6.7 entries each left their templates as drafts for 7.5, and every one of the eleven reaches the model, so freezing four would leave the summary and retry prompts free to drift between runs, which invariant 7 and the replay comparison cannot see. Until now a template edit passed CI silently; a hash in a table that a test reads makes the decision-log rule of §9.1 checkable. Documenting the differences as whole paragraphs shows that the conditions differ only in their own blocks, with the preamble, summary and history identical, which is the claim invariant 7 makes about the prompts.
**Changed:** `docs/prompt_templates.md`, `tests/orchestration/test_prompt_freeze.py` and `.gitattributes` added. CLAUDE.md: §3 lists the new doc, §9.1 names the freeze record, §15 adds item 50. `adm/bench/toolcall.py`: a comment points to the record. `config/prompts/` is unchanged. No new dependencies; the schemas are unchanged.

## 2026-11-03 — Automated checker: entity-mention extraction and the candidate record (WBS 8.6)

Decided by: SS · Supersedes: none

**Decision:** (1) **Layout.** `python -m adm.eval.checker --runs runs/ --out results/automated.jsonl` (`adm/eval/checker.py`) reads every run log and runs each check in `CHECKS` on every narrated turn. WBS 8.6 adds the first check, `entity_mention`, whose extraction lives in `adm/eval/entities.py`. WBS 8.7 to 8.9 add their checks to the same list. (2) **The candidate record.** One JSON line per candidate: `run_id`, `condition`, `scenario_id`, `seed`, `input_index`, `turn_number`, `check`, `category`, `status` (always `candidate`), `confidence` (`high` or `low`), `kind`, `mention`, `span` (character offsets into `narration`) and `sentence`. Lines are sorted by run, then turn, then position, so a rerun writes the same bytes. (3) **The scored state.** Condition D is checked against the state after the turn, rebuilt from the logged diffs. A–C are checked against `replay_script`'s state after the input. Both are verified against the record's hashes, and a log that does not match raises `LogMismatch`. Failed turns are skipped, since their narration is the engine's rephrase request. (4) **Scope.** A narration may use any word of a `display_name` in the state or the scenario, of a location, of the scenario's title, or of a spell. An item at quantity 0 keeps its definition (rubric R-neg). (5) **Candidates.** There are three kinds, each reported once per narration at its first mention (rubric §3 rule 3). `item` is a word from a lexicon of things that can be picked up, used, given or spent. `character` is a word from a lexicon of people and creatures. `proper_noun` is a run of capitalised words in mid-sentence. In each case, the mention counts only if none of its words is in scope. Plurals and possessives are matched in the singular by a small rule, with no lemmatiser. (6) **Confidence.** `high` is a lexicon word in a plain sentence. `low` is every proper noun, every word in `AMBIGUOUS_WORDS` ("guard", "ring", "figure") and any mention in a sentence with a negation or hypothetical ("no", "not", "if", "would", …).
**Reason:** CLAUDE.md §10.3 defines entity extraction as display names matched against the narration, with any capitalised noun phrase or known item-type word that matches nothing flagged as a candidate. It does not fix the lexicon, the output format or the scored state. (3) follows `docs/rubric.md` §1 and the 7.1 decision. (4) keeps the rubric's examples P3 and P4 and its §6.1 conventions free of false positives. The words are matched loosely, so "the rat" is in scope for "giant rat"; the rubric resolves ambiguity in favour of no divergence (§10.2), and the checker under-reports. The lexicons leave out generic words that can name an in-scope item ("blade", "weapon"), worn things that are part of a character ("cloak", "boot"; rubric §6.1 rule 5), fixtures, and words that are mostly verbs ("note", "lock"). (2) is the format 8.7–8.9 write and 8.10 validates. Known blind spots, for 8.10 to measure: lower-case phantom locations ("the crypt below"); too many of a kind ("three rats"); nouns missing from a lexicon; a phantom sharing a word with an in-scope name ("a silver key" beside an iron key).
**Changed:** `adm/eval/entities.py`, `adm/eval/checker.py`, `tests/eval/test_entities.py` and `tests/eval/test_checker.py` added. CLAUDE.md: §3 layout (`entities.py`), §15 item 51. `README.md`: test table. No new dependencies; the schemas are unchanged.

## 2026-11-03 — Batch runner: resume, re-runs and the main-grid manifest (WBS 7.6)

Decided by: CI · Supersedes: none

**Decision:** (1) **Manifest.** `experiments/main_grid.json` is `{"description", "scenarios": [path], "conditions": [str], "seeds": [int]}`, and every combination is one run: 16 scenarios × A–D × 2001, 2002, 2003, 192 runs, 6,420 scripted inputs. `load_manifest` refuses a duplicate in any list, a condition with no harness, a seed outside Ollama's 0 to 2³² − 2 and two scenarios with one id. Runs go seed by seed, then scenario, then condition, so a batch that stops early leaves whole `(scenario, seed)` cells played under all four conditions. (2) **One run** is played exactly as `adm.cli run` plays it (`open_session`, `run_script`), on its own fresh load (decision 25), with the client wrapped in `RetryCountingClient`, which adds up `transport_retries`. (3) **Staging.** The log is written to `runs/pending/{condition}/{scenario_id}/{seed}.jsonl` and moved into `runs/` with `os.replace` only when it covers every scripted input (decision 39's test, now `engine.audit.covers_script`) and had no transport retry. So a log in its place is a whole, clean run. (4) **Resume** is running the same command again. A log in place that covers the script is skipped without loading the model. A log left in `runs/pending/`, or an incomplete log in place (an interrupted `adm.cli run`), is moved to `runs/aborted/{condition}/{scenario_id}/{seed}.{UTC}.jsonl` and the run is played again from the start; it is never continued, because a reply depends on every request the model served since it was loaded (`docs/model_selection.md` §3). Aborted logs are never deleted or overwritten. (5) **Attempts.** At most 3 per run per invocation (`--max-attempts`). A transport retry or a `ModelError` aborts the attempt and the run is played again. A `ModelError` on the last attempt, or a `ModelConfigMismatch` at once, stops the batch. Any other exception is a bug, so it is not retried: the run is aborted and the batch goes on. Ctrl+C aborts the run in progress and exits 130. A run that does not finish stays pending for the next invocation (WBS 9.10). (6) **Ledger.** Every attempt and every discarded log appends a line to `results/batch/attempts.jsonl`: run id, outcome (`complete`, `tainted`, `model_error`, `error`, `interrupted`), attempt, times, transport retries, record count, error, aborted log, manifest, model and digest. Resuming reads the logs, not the ledger. (7) `batch` exits 0 only when every run of the manifest is complete.
**Reason:** The done-when is resuming after an interruption without duplicating work. A partial run cannot be resumed part-way without breaking invariant 4, so the unit of work is the whole run, and staging makes "in place" mean "done" even if the process is killed between the last turn and the retry check. `transport_retries` is not in the audit log (the 2026-10-13 entry left the schema unchanged), so it has to be counted while the run plays; point 4 of that entry asked the batch runner to re-run such a run. The attempt cap and stopping on a dead server keep an unattended batch from looping on a sick server, as the owner chose; a deterministic bug would fail the same way on every attempt, so retrying it only costs time. The seed-first order keeps the conditions balanced in a partial grid, so an early stop does not leave one condition ahead of the others.
**Changed:** `adm/orchestration/batch.py`, `experiments/main_grid.json` and `tests/orchestration/test_batch.py` added. `adm/orchestration/client.py`: `RetryCountingClient`. `adm/engine/audit.py`: `covers_script`, now also used by `adm/bench/smoke.py`. `adm/cli.py`: the `batch` command, and `open_session` takes a client wrapper. `tests/test_cli.py`, `tests/orchestration/test_client.py`: batch and counting-client tests. `docs/hardware.md` §7: setting up the pinned Ollama for runs. CLAUDE.md: §3 layout (`batch.py`), §15 item 52. `README.md`: `runs/aborted/` in the shared-storage tree, test table. No new dependencies; the schemas are unchanged.

## 2026-11-03 — Dry run: grid, seed and the run-log validator (WBS 7.7)

Decided by: CI · Supersedes: none

**Decision:** (1) **Grid.** `experiments/dry_run.json`, in the batch runner's format: `s01_cellar` and `long01_border_road` × A, B, C, D × seed 3001, 8 runs and 312 scripted inputs. It is played by the batch runner like the main grid. (2) **Seed and folder.** Seed 3001 is in no main-grid cell (2001–2003) and no smoke run (1001–1010). The logs go to `runs/dry_run/` (`--runs runs/dry_run --ledger results/dry_run/attempts.jsonl`), so the checker and the annotation tool, which read `runs/{A..D}/`, never mix them with main-grid logs. (3) **Validator.** `python -m adm.eval.validate` (`adm/eval/validate.py`) checks the logs on disk. Every record must pass `schemas/audit.schema.json` and `record_errors`, and carry its own path's condition, scenario, seed and run id. The log must hold one record per scripted input, in order, and each `player_input` must be its scripted text. The state hashes must replay: D from its diffs, A–C against `replay_script` (`checker.scored_states`). With `--manifest`, a planned run with no log is an error and an unplanned log is only listed. It exits 0 only when there is no error, and `--out` writes the report as JSON. (4) **Result.** 8 of 8 runs complete on the first attempt, and all 312 records valid (`docs/dry_run.md`).
**Reason:** (1) One short and one long scenario cover every harness path, including the long-session summary regeneration (six per long01 run), in 29 minutes. (2) The same transcripts feed the 8.11 rubric pilot. A main-grid seed would show pilot annotators the exact narrations they later rate blind, so a seed of its own keeps M1 and M5 annotation clean. (3) The audit-log writer refuses a bad record, but the done-when is about the output, and a log can be truncated, moved or edited after it is written. The same check is reusable after every main-grid batch (9.1, 9.2). `adm/eval` may not import orchestration (`docs/conventions.md` §1), so it reads the manifest's three lists itself.
**Changed:** `experiments/dry_run.json`, `adm/eval/validate.py`, `tests/eval/test_validate.py` and `docs/dry_run.md` added. CLAUDE.md: §2 commands, §3 layout (`validate.py`), §15 item 53. `README.md`: `runs/dry_run/` in the shared-storage tree, test table. No new dependencies; the schemas and prompt templates are unchanged.

## 2026-11-05 — Automated checker: hit-point band, status and HP-number comparison (WBS 8.7)

Decided by: SD · Supersedes: none

**Decision:** (1) **The check.** `hp_band` joins `CHECKS` in `adm/eval/checker.py`; its rules live in `adm/eval/bands.py`. It writes `CONTRADICT` candidates of three kinds: `band` (a band phrase whose bands exclude the actual band), `status` (a combatant at 0 HP named directly before an attack, speech or flight verb; rubric §5.5 rule 2) and `hp_number` ("3 hit points left" when no subject has that `current_hp`). The actual band is always `engine.combat.hp_band`; `bands.py` adds only the CLAUDE.md §10.2 lexicon. (2) **Matching.** No lemmatiser: each lexicon entry lists its inflections ("collapses", "fell"), and the longest phrase wins ("close to collapse" is `badly_hurt`). (3) **Rubric §5.3.** An intensity word before "wounded", "hurt", "injured" or "bleeding" sets the band ("badly" → `badly_hurt`, "barely" → `healthy`, "slightly" → `healthy` or `wounded`). A phrase implies a set of bands and is flagged only when the actual band is outside it, so an ambiguous phrase is never flagged and an adjacent band always is (§5.2). Skipped as not band phrases: a phrase followed by its object ("hurt you"), negation in the three words before ("no longer bleeding"), an adjective directly before a non-combatant noun ("the dying torchlight"), a verb whose subject is not a combatant ("the barrels collapse") and "falls back / silent / away" (§5.5 rule 1). (4) **Subject.** "You", "your" and the player character's name are the player character; an NPC is named by any word of its `display_name` but size and colour words. A phrase goes to the combatant named next to it, else to every combatant named in its sentence, else to those of the sentence before, and is flagged only if it fits none of them. (5) **Confidence.** `high` needs a single named subject, a lexicon word that is not in `AMBIGUOUS` ("fine", "fresh", "sore", "failing", the fall, collapse and crumple forms) and no hedge word ("if", "would", "will", "'ll", "earlier", "almost", "nearly", …) in the sentence. Everything else is `low`. (6) **One per combatant.** At most one candidate per subject per narration, the first high-confidence one or else the first (rubric §3 rule 2, §5.4 rule 3). (7) **Record.** The 8.6 record plus `subject` (combatant ids), `implied` and `actual`, so an annotator sees the claim and the state side by side.
**Reason:** The done-when is "implements the 8.2 rule exactly", and the 8.2 rule is `docs/rubric.md` §5. The lexicon cannot see meaning, so every rule in (3) and (4) removes a false positive the rubric names, and anything it cannot settle is skipped or marked `low`, as CLAUDE.md §10.2 requires the checker to under-report. This answers rubric §7 open point 2. Known blind spots, for 8.10 to measure: band phrases outside the lexicon ("half dead", "fully restored"); pronoun subjects in a sentence naming several combatants; a wrong phrase that happens to fit a bystander in the same sentence; acting verbs after a pronoun ("it lunges"); past and future claims (flagged, low); HP numbers spelled out above twenty. Resource quantities ("your last torch", rubric §6.3) are CLAUDE.md §10.3 item 4 and are not part of this check.
**Changed:** `adm/eval/bands.py` and `tests/eval/test_bands.py` added. `adm/eval/checker.py`: the `hp_band` check. `adm/eval/entities.py`: `sentences` made public for `bands.py`. `tests/eval/test_checker.py`: a band candidate end to end. `docs/rubric.md` §7: open point 2 answered. CLAUDE.md: §15 item 54. `README.md`: test table. No new dependencies; the schemas are unchanged.
