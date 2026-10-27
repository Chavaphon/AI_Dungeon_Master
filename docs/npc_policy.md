# NPC action policy

WBS 4.19 · Owner: SS · Status: **agreed at the Week 3 checkpoint, 2026-10-24** (`docs/decisions.md`, decision 3), with two additions from the 4.19 entry of 2026-10-27 · Code: `adm/engine/npc.py` · Tests: `tests/engine/test_npc.py`

Every combatant except the player character is played by the engine (CLAUDE.md §4.8, §14). The engine follows fixed rules over the current state. It makes no model call, so the policy is the same in all four conditions (invariant 7), and the offline replay for A–C ground truth plays NPCs exactly as a condition D run does.

## 1. The rules

On its turn, an NPC chooses one call.

1. **Opponents.** An NPC's opponents are the combatants in the encounter's initiative order who are of the opposing faction and conscious. `hostile` is opposed by `party`, and `party` by `hostile`. A `neutral` NPC has no opponents (addition, 2026-10-27).
2. **Target.** The opponent with the lowest `current_hp`. Ties are broken by the smaller `combatant_id`.
3. **Weapon.** The first item id, in sorted order, in the NPC's inventory that it holds (quantity above 0) and that is a weapon (`is_weapon`). Quantity 0 counts as not held, as for `WEAPON_NOT_IN_INVENTORY` (`docs/tool_contract.md` §2).
4. **Action.** With a weapon and a target, it calls `attack(npc, target, weapon)`. Otherwise it calls `dodge(npc)`. That covers an NPC with no weapon (agreed) and one with no opponent (addition, 2026-10-27).

It never casts a spell, uses a skill or changes an inventory. The rules use only the current state, so the same state always gives the same call.

The policy rolls no dice of its own. The only rolls in an NPC turn are its attack's, from the run's single seeded `DiceRoller` (invariant 3). The NPC actions therefore follow from `(seed, scenario_id)` and the player's calls, and nothing else.

In the twelve short and four long scenarios, every encounter is one PC against hostiles that each hold one weapon. So in practice each hostile attacks the PC with its weapon.

## 2. When NPC turns run

| When | What the engine does | `when` |
|---|---|---|
| After the PC's action-using call (`attack`, `cast_spell`, `dodge`) | `encounter_end` if the fight is over. Otherwise `initiative_advance`, `dodge_expiry` if one applies, then the NPC turns (`after_player_action`) | `after_call` |
| When an encounter starts and NPCs win initiative | Right after `encounter_start`, the turns of the NPCs ahead of the PC (`run_npc_turns`) | `before_call` (addition, 2026-10-27) |

Each NPC turn is an `npc_action` step holding the call and its full `result_ok`. If the fight is over, `encounter_end` follows and the run stops. Otherwise `initiative_advance` and `dodge_expiry` follow. The run stops when the turn reaches the PC, whose Dodge has already expired by then, or when the encounter ends. Skill checks and the other calls that do not use the action do not pass the turn, so no NPC acts after them. A failed turn does not advance initiative either (CLAUDE.md §7.1).

The condition D narration call receives the facts of every NPC action in the turn and of the player's call, in the order they happened (CLAUDE.md §9.1).

## 3. Validation

The engine executes an NPC call in one place: `take_npc_turn`. When the validator (WBS 5.2) is built, it checks the call there, like a player's call (CLAUDE.md §4.8). The policy only proposes calls that pass every precondition in `docs/tool_contract.md`. A rejected NPC call would therefore be a bug in the policy, so it raises and is not retried. Until 5.2 lands, `tests/engine/test_npc.py` checks that the calls are legal.
