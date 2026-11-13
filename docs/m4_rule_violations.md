# M4: rule-violation rate

WBS 10.4 · Owner: CI · Computed 2026-11-13 · CLAUDE.md wins on any conflict.

M4 of CLAUDE.md §10.4: "Rule-violation rate. Automated, all conditions." It measures how often the narration describes a turn that breaks the game's rules (an attack after the fight is over, a combatant acting out of turn, a heal with no spell slot, hit points below zero), and confirms that the state itself never breaks them. Done when: "Reported for all conditions" (TASK_CHECKLIST.md, 10.4). Its companion, M6, is `docs/m6_latency.md`.

## 1. Definitions

Fixed in `docs/decisions.md` (2026-11-13, "M4 and M6 summaries") before the figures below were read. The checks are those of WBS 8.9 (`adm/eval/rules.py`, decision 56), unchanged since their validation in 8.10.

| Term | Definition |
|---|---|
| Narrated turn | An audit record with no `turn_failure`: every A–C record, and the condition D records that were not failed turns. A failed D turn's narration is the engine's request to rephrase, so it is not scored, as in the checker (`docs/automated_pass.md` §2). |
| `state_audit` | A rule broken in the turn's state or engine actions: HP outside `[0, max_hp]`, spell slots or an inventory quantity below zero, an action out of turn order, a combat action with no encounter (Cure Wounds exempt). Always high confidence. Zero by construction; a non-zero count is a harness bug. |
| `rule_violation` | The same rules broken in the narration, judged against the state and what the turn did: D's own executed call and engine steps, A–C's replayed ground truth. High or low confidence (low when the player character is the subject, the spell is only described, or the sentence is hedged). |
| **M4** | (`rule_violation` high + `state_audit`) per 100 narrated turns, per condition (decision 56). |
| Low per 100 turns | `rule_violation` low per 100 narrated turns, given beside M4, not in it. |
| Confirmed per 100 turns | On the 64 runs of the M1 sample (decision 61), the `RULE` candidates one annotator confirmed plus the `RULE` breaks they added, per 100 narrated turns of those runs. The human check on the automated figure. |
| Precision | Confirmed `RULE` candidates / `RULE` candidates shown, by confidence, on the M1 sample. |

Pooled rates are ratios of sums over runs. Every 95% interval is a percentile bootstrap that resamples whole runs, 10,000 resamples, with a fixed seed: within one condition per condition row, stratified by condition in the All row (CLAUDE.md §10.5; `bootstrap` in `adm/eval/metrics.py`).

## 2. Set-up

| Item | Value |
|---|---|
| Dataset | The 192 runs of `experiments/main_grid.json` (16 scenarios × 4 conditions × seeds 2001–2003), the logs pinned by `experiments/main_grid.sha256` (decision 60). The G2 smoke logs in `runs/D/long0*/` are not planned by the manifest and are not read. |
| Copy read | CI's machine, `runs/A` to `runs/D`. The command refuses to run unless every planned log is present and matches its checksum; all 192 do. A–C logs are also checked against the replayed ground truth's state hashes, as in the checker. |
| Command | `python -m adm.eval.metrics m4 --checksums experiments/main_grid.sha256 --doc docs/m4_rule_violations.md`, and `--labels results/m1_labels.jsonl` for the confirmed table |
| Output | `results/m4.json` (gitignored; for the team Drive under `results/`), and the block in §3, written by the command. Two runs give byte-identical output: sha256 `d1cc798624e56a1c14e8452c87a9d4d012d5912ea3522c4e1d869eb869d525e0` (without `--labels`). |
| Cross-check | The candidate counts equal those of the 9.4 pass (`docs/automated_pass.md` §4: A 6 / 36, B 8 / 41, C 6 / 48, D 6 / 34, `state_audit` 0; by rule 121, 54 and 10), which ran the same checker over the Drive copy of the same bytes. |

## 3. Results

<!-- results:start -->
Conditions A, B, C, D, 192 runs, 6366 narrated turns. Intervals: 95% percentile bootstrap over whole runs, 10,000 resamples, seed 20261101; the All row is stratified by condition.

### M4 per condition

M4 = (`rule_violation` high + `state_audit`) per 100 narrated turns (decision 56).

| Condition | Runs | Narrated turns | `rule_violation` high | `state_audit` | **M4 per 100 turns** | 95% interval | `rule_violation` low | Low per 100 turns |
|---|---|---|---|---|---|---|---|---|
| A | 48 | 1605 | 6 | 0 | **0.37** | 0.12 to 0.69 | 36 | 2.24 |
| B | 48 | 1605 | 8 | 0 | **0.50** | 0.13 to 0.95 | 41 | 2.55 |
| C | 48 | 1605 | 6 | 0 | **0.37** | 0.07 to 0.75 | 48 | 2.99 |
| D | 48 | 1551 | 6 | 0 | **0.39** | 0.06 to 0.87 | 34 | 2.19 |
| **All** | 192 | 6366 | 26 | 0 | **0.41** | 0.24 to 0.61 | 159 | 2.50 |

### Candidates by rule

Each cell is `rule_violation` high / `rule_violation` low / `state_audit`.

| Rule | A | B | C | D |
|---|---|---|---|---|
| `slot_below_zero` | 0 / 2 / 0 | 0 / 2 / 0 | 0 / 2 / 0 | 0 / 4 / 0 |
| `out_of_turn` | 1 / 8 / 0 | 4 / 17 / 0 | 2 / 21 / 0 | 1 / 0 / 0 |
| `after_encounter_end` | 5 / 26 / 0 | 4 / 22 / 0 | 4 / 25 / 0 | 5 / 30 / 0 |

### Confirmed by the human pass (M1 sample)

Not computed: run with `--labels results/m1_labels.jsonl` once the 9.5 labels are on this machine.
<!-- results:end -->

## 4. Reading

**The state never breaks a rule, in any condition.** `state_audit` is zero on all 6,366 narrated turns: no HP outside its range, no slot or quantity below zero, no action out of turn and no combat with no encounter, in D's own state and in A–C's replayed ground truth. This is invariant 5 and the validator's preconditions holding on the whole main grid, and it is why M4 rests wholly on what the narration says.

**Narrated rule breaks are rare and about equally rare in every condition.** M4 is 0.37 to 0.50 per 100 narrated turns, 26 high-confidence candidates over 6,366 turns, and the four intervals overlap almost wholly. Counts this small cannot separate the conditions, and no test of a difference was fixed before scoring (CLAUDE.md §10.5 tests H1 on M1, not M4), so none is drawn here.

**These are candidates, not confirmed breaks.** On the 30 validation turns, 1 of the checker's 3 `RULE` candidates was right, and its one high-confidence `after_encounter_end` was a past-tense mention (`docs/checker_validation.md` §2). The confirmed table above, from the M1 sample's labels, is the check on how many of the 26 are real; until it is computed, read M4 as an upper bound for the high-confidence kinds it covers, and not a bound at all for breaks the checker cannot see (its recall on validation was 0.35 over all categories).

**Fights that end before the script does produce most of them.** `after_encounter_end` is 121 of the 185 candidates, 18 of the 26 high-confidence ones. Scripted inputs do not adapt to how an encounter goes (decision 23), so an attack can arrive after the last hostile is down; A–C narrate the attack the input asks for with nothing to stop them, and D's narration still gives 35 candidates (5 high), attacks described in turns that began after the encounter ended, when the engine refuses any combat action. This is the pattern behind most of M2's rejections (`docs/m2_tool_calls.md` §4).

**D narrates NPC turns from the facts, and its low-confidence `out_of_turn` count shows it.** It has 1 `out_of_turn` candidate against 9 to 23 in A–C. D's narration call is given the NPC actions of the turn (decision 21), while A–C narrate the fight with no record of who acted and attribute attacks freely. These are mostly low-confidence and unconfirmed, so it is a pointer for the qualitative catalogue (WBS 10.7), not a result.
