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
