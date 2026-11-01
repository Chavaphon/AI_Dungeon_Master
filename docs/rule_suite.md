# Rule suite: Objective 1

WBS 4.17 · Owner: SS · Run 2026-11-01 · CLAUDE.md wins on any conflict.

The evidence for the Objective 1 criterion and deliverable D3: the 60-case rule suite of CLAUDE.md §13 passes 100 per cent, in CI (TASK_CHECKLIST.md, D3). The suite checks the rules engine against the game rules of CLAUDE.md §4; it calls no model.

## 1. Verdict

| Check | Threshold | Result |
|---|---|---|
| Cases per area | The CLAUDE.md §13 table, 60 in all | **60 of 60**, every area at its count (§3). Met. |
| Cases passing | 100% | **60 of 60 cases, 123 of 123 items.** None skipped or expected to fail. Met. |
| In CI | Passes on every push | The `Rule suite` step of the CI `test` job runs `pytest -m rule_suite` before the whole suite, on Python 3.11. |

## 2. What a case is

- A case is one test function marked `@pytest.mark.rule_suite("<area>")`. A parametrized function is one case, and its parameters are the case's examples, run as separate pytest items. That is why 60 cases run as 123 items.
- Cases sit next to the rules they test, in the per-module files under `tests/engine/`. They are not copied into a separate file.
- `tests/engine/test_rule_suite.py` holds the suite to this document. It fails if a case names an area outside §13, if an area has more or fewer cases than §13 gives it, if a case is skipped or marked `xfail` (so a case that counts must pass), or if the table in §4 below is not exactly the marked cases.
- Renaming, adding or removing a case therefore means updating §4 in the same pull request. Changing an area's count means changing CLAUDE.md §13, which needs a `docs/decisions.md` entry.

## 3. Per area

| Area | CLAUDE.md §13 | Built in WBS | Cases | Items |
|---|---|---|---|---|
| `dice` | Dice parsing and seeded reproducibility | 4.2 | 6 | 27 |
| `abilities` | Ability modifiers, including negatives and boundaries | 4.3 | 4 | 12 |
| `initiative` | Initiative, ordering, tie-breaks, round advance | 4.4 | 6 | 6 |
| `attack` | Attack: hit, miss, natural 20, natural 1, critical damage | 4.5 | 8 | 8 |
| `advantage` | Advantage and disadvantage, including mutual cancellation | 4.7 | 5 | 10 |
| `dodge` | Dodge: application and expiry timing | 4.6 | 4 | 4 |
| `spells` | Fire Bolt and Cure Wounds, including the HP cap and slot exhaustion | 4.11–4.13 | 7 | 9 |
| `zero_hp` | Zero HP, unconscious, revival, encounter end | 4.8, 4.12 | 6 | 6 |
| `skill_checks` | Skill checks at, above and below DC | 4.9 | 5 | 18 |
| `inventory` | Inventory and quantity floors | 4.14 | 3 | 5 |
| `relationships` | Relationship ladder, one-step rule, justification | 4.15 | 3 | 6 |
| `quests` | Quest transitions, legal and illegal | 4.16 | 3 | 12 |
| **Total** | | | **60** | **123** |

The revival case (`zero_hp`) is the Cure Wounds test that brings an unconscious combatant back and has it act in its existing initiative slot. WBS 4.10 left that gap open until Cure Wounds was built.

## 4. The cases

Ordered by area as in §3, then by file and line. Each name states the rule it checks.

<!-- cases:start -->
| Area | Case |
|---|---|
| dice | `tests/engine/test_dice.py::test_parse_valid` |
| dice | `tests/engine/test_dice.py::test_parse_rejects` |
| dice | `tests/engine/test_dice.py::test_identical_seed_reproduces_identical_sequence` |
| dice | `tests/engine/test_dice.py::test_golden_sequence_is_pinned` |
| dice | `tests/engine/test_dice.py::test_rollers_with_the_same_seed_are_independent` |
| dice | `tests/engine/test_dice.py::test_roll_is_in_range_and_adds_up` |
| abilities | `tests/engine/test_abilities.py::test_modifier_at_the_score_boundaries` |
| abilities | `tests/engine/test_abilities.py::test_odd_scores_below_10_round_down` |
| abilities | `tests/engine/test_abilities.py::test_modifier_around_10` |
| abilities | `tests/engine/test_abilities.py::test_scores_outside_1_to_20_are_rejected` |
| initiative | `tests/engine/test_combat.py::test_initiative_is_d20_plus_dex_modifier_in_listed_order` |
| initiative | `tests/engine/test_combat.py::test_order_is_highest_total_first` |
| initiative | `tests/engine/test_combat.py::test_tie_breaks_on_higher_dex_score_not_modifier` |
| initiative | `tests/engine/test_combat.py::test_tie_on_total_and_dex_breaks_on_smaller_id` |
| initiative | `tests/engine/test_combat.py::test_wrapping_the_order_increments_the_round` |
| initiative | `tests/engine/test_combat.py::test_advance_skips_an_unconscious_combatant` |
| attack | `tests/engine/test_combat.py::test_attack_reproduces_the_contract_example` |
| attack | `tests/engine/test_combat.py::test_attack_total_equal_to_ac_hits` |
| attack | `tests/engine/test_combat.py::test_attack_below_ac_misses_and_changes_nothing` |
| attack | `tests/engine/test_combat.py::test_natural_20_hits_any_ac_and_is_critical` |
| attack | `tests/engine/test_combat.py::test_natural_1_misses_whatever_the_bonus` |
| attack | `tests/engine/test_combat.py::test_critical_doubles_the_dice_and_not_the_modifier` |
| attack | `tests/engine/test_combat.py::test_damage_is_never_negative` |
| attack | `tests/engine/test_combat.py::test_natural_20_is_judged_after_disadvantage_selection` |
| advantage | `tests/engine/test_dice.py::test_advantage_rolls_two_d20_and_keeps_one` |
| advantage | `tests/engine/test_dice.py::test_advantage_dice_are_recorded_in_the_order_rolled` |
| advantage | `tests/engine/test_dice.py::test_advantage_and_disadvantage_cancel` |
| advantage | `tests/engine/test_dice.py::test_sources_of_one_kind_do_not_stack` |
| advantage | `tests/engine/test_dice.py::test_cancelled_roll_is_a_single_d20` |
| dodge | `tests/engine/test_combat.py::test_attack_on_a_dodging_target_has_disadvantage` |
| dodge | `tests/engine/test_combat.py::test_dodge_sets_the_flag_and_reproduces_the_contract_example` |
| dodge | `tests/engine/test_combat.py::test_dodge_holds_through_other_turns_and_the_round_wrap` |
| dodge | `tests/engine/test_combat.py::test_dodge_clears_at_the_start_of_the_dodgers_next_turn` |
| spells | `tests/engine/test_spells.py::test_fire_bolt_reproduces_the_contract_example` |
| spells | `tests/engine/test_spells.py::test_fire_bolt_critical_rolls_2d10` |
| spells | `tests/engine/test_spells.py::test_fire_bolt_costs_no_slot_and_works_with_none_left` |
| spells | `tests/engine/test_spells.py::test_cure_wounds_reproduces_the_contract_example` |
| spells | `tests/engine/test_spells.py::test_cure_wounds_never_exceeds_max_hp` |
| spells | `tests/engine/test_spells.py::test_cure_wounds_heals_at_least_1` |
| spells | `tests/engine/test_spells.py::test_each_cast_spends_a_slot_and_a_cast_at_zero_is_refused` |
| zero_hp | `tests/engine/test_combat.py::test_damage_beyond_current_hp_stops_at_zero_and_knocks_out` |
| zero_hp | `tests/engine/test_combat.py::test_unconscious_combatant_stays_down_with_no_death_saves` |
| zero_hp | `tests/engine/test_combat.py::test_last_hostile_down_ends_in_victory` |
| zero_hp | `tests/engine/test_combat.py::test_player_character_down_ends_in_defeat` |
| zero_hp | `tests/engine/test_combat.py::test_hp_is_never_negative_and_state_legal_at_every_step` |
| zero_hp | `tests/engine/test_spells.py::test_cure_wounds_revives_and_the_combatant_acts_in_its_slot` |
| skill_checks | `tests/engine/test_checks.py::test_skill_bonus` |
| skill_checks | `tests/engine/test_checks.py::test_check_against_dc` |
| skill_checks | `tests/engine/test_checks.py::test_negative_bonus_can_fail_on_a_roll_that_would_otherwise_pass` |
| skill_checks | `tests/engine/test_checks.py::test_total_is_d20_plus_bonus` |
| skill_checks | `tests/engine/test_checks.py::test_scenario_granted_advantage` |
| inventory | `tests/engine/test_inventory.py::test_remove_reproduces_the_contract_example` |
| inventory | `tests/engine/test_inventory.py::test_removing_everything_leaves_0_and_keeps_the_key` |
| inventory | `tests/engine/test_inventory.py::test_below_0_is_refused_and_changes_nothing` |
| relationships | `tests/engine/test_relationships.py::test_one_step_up_reproduces_the_contract_example` |
| relationships | `tests/engine/test_relationships.py::test_a_step_past_either_end_is_rejected` |
| relationships | `tests/engine/test_relationships.py::test_missing_or_short_justification_is_rejected` |
| quests | `tests/engine/test_quests.py::test_advance_reproduces_the_contract_example` |
| quests | `tests/engine/test_quests.py::test_start_advance_then_finish` |
| quests | `tests/engine/test_quests.py::test_illegal_transition_is_rejected_with_its_code` |
<!-- cases:end -->

## 5. Reproduce

```bash
pytest -m rule_suite -v                       # the 60 cases alone
pytest tests/engine/test_rule_suite.py -v     # the count, the no-skip rule and §4
```

Run on 2026-11-01 from commit `b3276d8` plus this change (Windows, Python 3.14.3 in the local venv): `pytest -m rule_suite -q` gives `123 passed`. CI runs the same command on Python 3.11, the version CLAUDE.md §2 fixes, and that run is the one that counts for D3.

## 6. Not part of the 60

CLAUDE.md §13 asks for three more things "separately". They are evidenced by their own tasks, not by this suite:

| Requirement | Where | Status |
|---|---|---|
| Every rejection code in §6.3 reachable by a test | `tests/engine/test_preconditions.py::test_every_rejection_code_is_reachable` (WBS 5.2) | Passing |
| Replay of one seed gives identical state hashes | WBS 4.18, the replay harness | Not built yet (due 3 Nov) |
| Parser tested against at least 20 recorded malformed outputs | `tests/orchestration/test_parser.py::test_at_least_twenty_recorded_malformed_outputs` (WBS 6.3) | Passing |
