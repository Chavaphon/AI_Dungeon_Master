# Intent-fidelity annotation protocol (M3) v0.9

WBS 8.14 · Owner: SD · Status: **confirmed at the Week 5 checkpoint, 2026-11-08** · CLAUDE.md wins on any conflict.

This is the protocol for M3, intent fidelity (CLAUDE.md §10.4): on a 15% random sample of turns, a human judges, yes or no, whether the executed call represents what the player asked for. It is the critic layer of the VERIFY pyramid (§1.2). It looks for the failure the validator cannot see: a valid call for the wrong action (§7.2). The annotation itself is WBS 9.7 (CI, Week 6), on the annotation tool of WBS 8.15.

Section 2 is the **sampling rule** and section 3 the **decision rule**, the two things 8.14 must fix.

## 1. What is scored

- **Condition D only.** M3 judges the executed call. Conditions A–C have no tool phase and no `executed_call` (`docs/audit_log.md` §3), so they have nothing to judge.
- **The unit is one turn record** of a scripted run: `run_id` plus `input_index`. Short scenarios and long sessions are both in the population (9.1 and 9.2).
- **Failed turns are excluded.** A turn with `turn_failure` set ran no call. It is counted by M2, not M3.
- **A `{"tool": null}` reply is included** (`narration_only: true`, `executed_call: null`). Choosing no call is a decision about the player's request and can be wrong, as when "I pick up the key" changes nothing.
- **Only the final call is judged.** After a rejection and a successful retry, the annotator judges the call that ran, not the attempts before it. Retries are M2.

## 2. Sampling rule

1. **Population.** Every condition D turn record of the final dataset (D8, after the 9.10 re-runs) whose `turn_failure` is `null`. The dataset is the condition D runs `experiments/main_grid.json` plans (48 runs, seeds 2001–2003). The G2 smoke logs that share `runs/D/long0*/` (seeds 1001–1010) are not in it, and the tool stops if a planned log is missing (`docs/decisions.md`, 2026-11-12, WBS 9.7).
2. **Strata.** One stratum per `scenario_id`: twelve short scenarios and four long sessions. This keeps each scenario's share of the sample equal to its share of the turns, so long sessions are not under-sampled by chance.
3. **Draw.** In each stratum, sort the records by the key `sha256("m3-v1/" + run_id + "/" + input_index)`, as lowercase hex, and take the first `ceil(0.15 × n)`, where `n` is the stratum's size.
4. **Fallback (risk R5).** If annotation falls behind, as R5 defines, the rate drops from 15% to 10%. Because the draw is an ordering, the 10% sample is the first `ceil(0.10 × n)` of the same order, a subset of the 15% one. Turns already scored stay valid. The rate used is reported with the result.

The draw uses a hash, not a random number generator. It is reproducible from the dataset alone, it does not depend on the order runs finished, and it adds nothing to any seeded RNG stream (invariant 3). A run replaced in 9.10 keeps its `run_id`, so its turns keep their place in the order.

`expected_call` plays no part in the draw. Sampling only turns where the model's call differs from it would over-represent failures and bias the rate (§12).

## 3. Decision rule

### 3.1 The question

> **Does the executed call do what the player asked, as far as one call in this game can?**

Answer `faithful` or `unfaithful`. There is no third value. A judgement that is hard to make gets `faithful` with a note (rule 3.3.6).

### 3.2 What the annotator sees

| Shown | Not shown |
|---|---|
| `player_input` | the narration, and anything else written after the call ran |
| `executed_call`, with each id followed by its display name | `expected_call` |
| The state before the turn: the player character's inventory, the NPC stances, the quest states and stages, the combatants and their status, and whether an encounter is active | the condition, the seed, and the earlier attempts and rejections |

Narration is hidden because M3 judges the call, not how it was described. `expected_call` is hidden because a different but reasonable call is not a failure (§12), and seeing the script's answer would anchor the annotator. Reasonable is judged from the request alone.

### 3.3 Rules, in order

Work down the list. The first rule that settles the turn decides it.

1. **No mechanical request, no call.** If the request asks for nothing the seven tools do (looking around, talking, asking a question, waiting), then `{"tool": null}` is faithful. A call that changes state is unfaithful (`INVENTED`). A skill check on an observation request ("I look around the cellar") is also faithful.
2. **A mechanical request needs a call.** If the request asks for something a tool does (attack, cast, dodge, a check, picking up or using up an item, changing an NPC's mind, taking on or settling a quest), then `{"tool": null}` is unfaithful (`MISSED`).
3. **The right tool.** The tool must be one a reasonable reading of the request leads to. "I raise my shield" may be `dodge` or no call. "I attack the rat" must be `attack` or, for a caster, `cast_spell` with Fire Bolt. Otherwise `WRONG_TOOL`.
4. **The right arguments.** Every argument the request determines must match it:
    - the target, weapon, item, NPC and quest named or clearly meant (otherwise `WRONG_TARGET`);
    - the spell, the skill, the direction of a stance change, the quest transition, and the sign and size of an inventory change (otherwise `WRONG_VALUE`).

    Not judged: `dc` (the scenario's DC is authoritative, §15 item 20) and the wording of `justification`, as long as it is about this event.
5. **Several actions in one request.** One call per turn can do one thing. The call must do **the action the request is for**: its last stated goal, unless the request makes that goal depend on an earlier step that the game rolls for. "I sneak past the guard and grab his keys": the request is for the keys, so `skill_check(stealth)` alone is unfaithful (`DROPPED`), the case in §7.2. "I try to sneak past the guard": a stealth check is faithful. When the goal is something no tool can do (taking an item from an NPC's inventory, §15 item 22), a call that does the part a tool can do is faithful.
6. **When in doubt, faithful.** If two readings of the request are both reasonable and the call fits one of them, the call is faithful. Write the other reading in the note. As in the rubric (§3, rule 5), ambiguity is resolved in favour of no failure, so M3 is a lower bound on misparsed intent, not an estimate inflated by guesses.

### 3.4 Reason codes

Every `unfaithful` turn gets exactly one code, the first in this list that applies.

| Code | The call... | Rule |
|---|---|---|
| `MISSED` | is `{"tool": null}`, but the request asked for something a tool does | 2 |
| `INVENTED` | changes state that the request did not ask to change | 1 |
| `WRONG_TOOL` | uses a tool no reasonable reading leads to | 3 |
| `WRONG_TARGET` | names the wrong combatant, weapon, item, NPC or quest | 4 |
| `WRONG_VALUE` | has the wrong spell, skill, direction, transition or quantity | 4 |
| `DROPPED` | does one part of a multi-part request but not the part the request is for | 5 |

The codes do not change M3, which is binary. They let the report say which tools the model misreads. The 3.4 benchmark already points at relationship and quest updates (`docs/model_selection.md`).

## 4. Worked examples

Each is condition D, using the long sessions and short scenarios in `scenarios/`.

| Player input | Executed call | Verdict | Why |
|---|---|---|---|
| "I accept the bottle of cider the stallholder presses into my hands" (s09, input 1) | `modify_inventory(pc_nia, item_cider, +1)` | faithful | Rules 3 and 4: right tool, item and quantity |
| same | `{"tool": null}` | unfaithful, `MISSED` | Rule 2: an item was asked to change hands |
| "I tell Master Orlo I will guard his wagons as far as the border fort" (long01, input 1) | `update_quest(quest_border_caravan, advance)` | unfaithful, `WRONG_VALUE` | Rule 4: taking on a quest is `start` |
| "I tell the harbour master he is a thief" (long03, input 24) | `update_npc_relationship(npc_harbour_master, up, ...)` | unfaithful, `WRONG_VALUE` | Rule 4: an insult moves the stance down |
| "I wander between the stalls and take in the fair" (s09, input 0) | `skill_check(pc_nia, perception, 12)` | faithful | Rule 1: an observation may be a check |
| same | `modify_inventory(pc_nia, item_cider, +1)` | unfaithful, `INVENTED` | Rule 1: nothing was picked up |
| "I take the brass badge from the first bandit's coat" (long01, input 31) | `modify_inventory(pc_edda, item_bandit_badge, +1)` | faithful | Rule 5: a tool cannot take it from the bandit's inventory, so adding it to Edda's is the part a tool can do |
| "I sneak up on the boar while it is busy rooting in the turnips" (s09, input 5) | `attack(pc_nia, npc_boar, item_spear)` | unfaithful, `WRONG_TOOL` | Rule 3: the request is to sneak up, not to strike |
| "I raise my guard as both bandits rush me" (long01, input 26) | `{"tool": null}` | faithful | Rule 6: "raise my guard" may be Dodge or flavour; note the other reading |

## 5. Recording and reporting

The tool (8.15, `python -m adm.eval.annotate m3 --annotator <initials>`) writes one line per scored turn to `results/m3_intent.jsonl` (gitignored, §3):

```json
{"run_id": "D_s09_harvest_fair_12345", "input_index": 5, "annotator": "CI",
 "faithful": false, "reason": "WRONG_TOOL", "note": ""}
```

`reason` is `null` when `faithful` is `true`.

The results section (WBS 11.3) gives:

- **M3** as faithful turns over scored turns, with a 95% Wilson interval, and the sampling rate used (§2, rule 4).
- The same split by the tool of the executed call (and "no call"), and by short scenarios versus long sessions.
- The count of each reason code.

## 6. Open points for the Week 5 checkpoint

1. **A second annotator.** CLAUDE.md §10.4 asks for Krippendorff's alpha on a 20% double-scored overlap but does not say whether M3 is included. The WBS has a second-annotator pass only for M1 (9.6). Proposal: no second pass for M3 within the 9.7 budget. Rule 3.3.6 and the reason codes make the judgement narrow. If the team wants alpha for M3 too, 20% of the M3 sample is about 1 extra hour for SS, and 9.6 grows by that much.
2. **Who annotates.** 9.7 is CI's, and CI also wrote the orchestration that produces the calls. If the team prefers an annotator who did not build the tool phase, SD or SS could take it. This changes owners, not the protocol.

Settled at the Week 5 checkpoint (`docs/decisions.md`, 2026-11-08): no second annotator for M3, and the report states that M3 is single-annotated; 9.7 stays with CI.
