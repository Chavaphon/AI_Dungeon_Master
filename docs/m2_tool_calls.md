# M2: invalid tool-call and recovery rates

WBS 10.3 · Owner: CI · Computed 2026-11-13 · CLAUDE.md wins on any conflict.

M2 of CLAUDE.md §10.4: "From the audit log. Condition D only. Rejected calls / total turns; recovered within budget / rejected." It measures how often `llama3.1:8b` proposes a call the engine refuses or cannot parse, and how often the retry budget of 2 (§7.1) saves the turn. It is the CONTROL principle's spending limit, measured (§1.2), and the reported form of risk R1. Done when: "Condition D only" (TASK_CHECKLIST.md, 10.3).

## 1. Definitions

Fixed in `docs/decisions.md` (2026-11-13, "M2 definitions and the bootstrap helper") before the figures below were read. The unit is a turn, one audit record, failed turns included.

| Term | Definition |
|---|---|
| Attempt | One toolcall model call: one entry of the record's `validation`. At most 3 per turn. |
| Rejected attempt | A `validation` entry with `ok: false`: a rejection envelope (`rejection_code`) or an unparseable reply (`failure: "unparseable"`). |
| `{"tool": null}` reply | Valid (`ok: true`), so not a rejection. The first one of a turn is always re-prompted (decision 32), which uses an attempt; that is counted separately, as context. |
| Rejected turn | A turn with at least one rejected attempt. |
| Recovered turn | A rejected turn with no `turn_failure`: the budget did not run out. It executed a call, or ended narration-only after a `{"tool": null}` reply. Both count; they are shown apart. |
| **Invalid tool-call rate** | Rejected turns / turns. The headline, as in the smoke runs (`docs/smoke_runs.md` §3). |
| Rejected-attempt rate | Rejected attempts / turns: the literal reading of "rejected calls / total turns". Given beside the headline; it can exceed 1. |
| **Recovery rate** | Recovered turns / rejected turns. |

Pooled rates are ratios of sums over the 48 runs, not means of per-run rates. Every 95% interval is a percentile bootstrap that resamples whole runs, 10,000 resamples, stratified by condition (one stratum here), with a fixed seed (CLAUDE.md §10.5; `bootstrap` in `adm/eval/metrics.py`).

## 2. Set-up

| Item | Value |
|---|---|
| Dataset | The 48 condition D runs of `experiments/main_grid.json` (16 scenarios × seeds 2001–2003), the logs pinned by `experiments/main_grid.sha256` (decision 60). The G2 smoke logs in `runs/D/long0*/` are not planned by the manifest and are not read. |
| Copy read | CI's machine, `runs/D`. The command refuses to run unless every planned log is present and matches its checksum; all 48 do. |
| Command | `python -m adm.eval.metrics m2 --checksums experiments/main_grid.sha256 --doc docs/m2_tool_calls.md` |
| Output | `results/m2.json` (gitignored; for the team Drive under `results/`), and the block in §3, written by the command. Two runs of the command give byte-identical output: sha256 `b8582c2991c7a495a3a9c2a2788708b1f74d27b15ad6defaf051f03929e48aea`. |

## 3. Results

<!-- results:start -->
Condition D, 48 runs, 1605 turns, 2594 toolcall attempts. Intervals: 95% percentile bootstrap over whole runs, 10,000 resamples, seed 20261101.

### Rates

| Rate | Count | Value | 95% interval |
|---|---|---|---|
| **Invalid tool-call rate** (rejected turns / turns) | 402 / 1605 | 25.0% | 22.1% to 28.2% |
| Rejected attempts / turns | 573 / 1605 | 35.7% | 30.4% to 41.7% |
| **Recovery rate** (recovered / rejected turns) | 348 / 402 | 86.6% | 81.1% to 91.6% |

### How rejected turns ended

| Ending | Turns |
|---|---|
| Recovered, a call executed | 301 |
| Recovered, narration-only after a `{"tool": null}` reply | 47 |
| Failed: retry budget exhausted | 54 |
| **Rejected turns** | **402** |

Attempts used by recovered turns: 2 attempts 192, 3 attempts 156. Turns whose first reply was `{"tool": null}` (re-prompted, not a rejection): 468.

### Rejections by code, over all attempts

| Code | Attempts |
|---|---|
| `ENCOUNTER_OVER` | 268 |
| `SCHEMA_VIOLATION` | 54 |
| `NO_SPELL_SLOT` | 50 |
| `NOT_A_CASTER` | 42 |
| `RELATIONSHIP_STEP_TOO_LARGE` | 34 |
| `NEGATIVE_QUANTITY` | 27 |
| `ILLEGAL_QUEST_TRANSITION` | 22 |
| `TARGET_UNCONSCIOUS` | 19 |
| `ACTOR_UNCONSCIOUS` | 16 |
| `UNKNOWN_ENTITY` | 11 |
| `ITEM_NOT_DEFINED` | 10 |
| `unparseable` | 9 |
| `WEAPON_NOT_IN_INVENTORY` | 6 |
| `SKILL_NOT_SUPPORTED` | 5 |

### Failed turns by kind

| `turn_failure` | Turns |
|---|---|
| `precondition` | 47 |
| `schema` | 6 |
| `unknown_entity` | 1 |

### Per scenario

| Scenario | Runs | Turns | Rejected | Rate | Recovered | Recovery | Failed |
|---|---|---|---|---|---|---|---|
| s01_cellar | 3 | 78 | 22 | 28.2% | 19 | 86.4% | 3 |
| s02_toll_bridge | 3 | 81 | 21 | 25.9% | 21 | 100.0% | 0 |
| s03_forest_shrine | 3 | 81 | 24 | 29.6% | 22 | 91.7% | 2 |
| s04_goblin_warren | 3 | 84 | 25 | 29.8% | 25 | 100.0% | 0 |
| s05_wayside_inn | 3 | 81 | 11 | 13.6% | 11 | 100.0% | 0 |
| s06_drowned_lighthouse | 3 | 84 | 20 | 23.8% | 18 | 90.0% | 2 |
| s07_smugglers_cove | 3 | 81 | 26 | 32.1% | 26 | 100.0% | 0 |
| s08_old_mine | 3 | 90 | 39 | 43.3% | 23 | 59.0% | 16 |
| s09_harvest_fair | 3 | 78 | 11 | 14.1% | 11 | 100.0% | 0 |
| s10_watchtower | 3 | 81 | 27 | 33.3% | 25 | 92.6% | 2 |
| s11_frozen_pass | 3 | 81 | 29 | 35.8% | 17 | 58.6% | 12 |
| s12_bog_witch | 3 | 81 | 23 | 28.4% | 20 | 87.0% | 3 |
| long01_border_road | 3 | 156 | 22 | 14.1% | 19 | 86.4% | 3 |
| long02_hollow_manor | 3 | 156 | 19 | 12.2% | 18 | 94.7% | 1 |
| long03_river_market | 3 | 156 | 35 | 22.4% | 34 | 97.1% | 1 |
| long04_mountain_monastery | 3 | 156 | 48 | 30.8% | 39 | 81.2% | 9 |
<!-- results:end -->

## 4. Reading

**One in four turns needs a retry, and seven in eight of those are saved.** The invalid tool-call rate is 25.0% (22.1% to 28.2%) and the recovery rate 86.6% (81.1% to 91.6%). The 54 turns the budget did not save are 3.4% of all turns; they are the failed turns that M1 skips and M3 leaves out (`docs/automated_pass.md`, `docs/intent_fidelity.md`).

**The model rarely gets the format wrong.** Unparseable replies and `SCHEMA_VIOLATION` are 63 of 573 rejected attempts (11%). Nearly every rejection is a well-formed call the state does not allow, which is the engine doing the job the design gives it (§1: the model proposes, the engine validates). The first attempt parses and passes the schema in 1,575 of 1,605 turns (98.1%, as defined in `adm/bench/smoke.py`), far from risk R1's trigger of 80%.

**Most rejections come from the script outrunning the fight.** `ENCOUNTER_OVER` is 268 of 573 rejected attempts and appears in 242 of the 402 rejected turns. Scripted inputs do not adapt to how an encounter goes (decision 23), so an input such as "I hurl fire at the second wolf" arrives after the wolf is down and the encounter has ended. The commonest failed turn, 26 of 54, is the one the smoke runs found (`docs/smoke_runs.md` §4): the attack is refused with `ENCOUNTER_OVER`, the model swaps to Cure Wounds with no slot left (`NO_SPELL_SLOT`), then goes back to the attack. This is data, not a fault (§7.1): the rejection is logged and counted.

**The forced re-prompt has a cost.** A strength check outside combat ("I climb down the old ladder into the shaft", s08 input 3; "I push through the waist-deep snowdrift", s11 input 4) failed in all three seeds of both scenarios the same way: a `{"tool": null}` reply, re-prompted by decision 32; then `dodge` with no arguments (`SCHEMA_VIOLATION`); then `dodge` with the actor, refused with `ENCOUNTER_OVER`. The re-prompt pushes the model to pick some tool, and it picks the wrong one rather than `skill_check`. These six, with 15 of the 26 above, are 21 of the 28 failed turns of s08 and s11, the two scenarios with the lowest recovery rates (59%). They are candidates for the qualitative failure catalogue (WBS 10.7).

**Smoke runs are not comparable.** The ten G2 smoke runs gave 20.6% and 95.3% (`docs/smoke_runs.md` §3), on the long scenarios only and with the preamble before the 2026-11-01 alignment. M2 is the main-grid figure above.
