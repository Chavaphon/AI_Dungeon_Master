# M3 intent-fidelity annotation

WBS 9.7 · Owner: CI · Annotated 2026-11-13 · CLAUDE.md wins on any conflict.

The M3 annotation of CLAUDE.md §10.4 under the 8.14 protocol (`docs/intent_fidelity.md`). For each turn in a 15% sample of condition D turns, the question is: does the executed call do what the player asked, as far as one call in this game can? Done when: "Sample scored under the 8.14 protocol" (TASK_CHECKLIST.md, 9.7). This record gives the counts. The rate with its 95% Wilson interval and the write-up are WBS 11.3 (`docs/intent_fidelity.md` §5).

## 1. Set-up

| Item | Value |
|---|---|
| Copy annotated | CI's machine, `runs/D`. `python -m adm.eval.integrity --manifest experiments/main_grid.json --checksums experiments/main_grid.sha256`: 192 of 192 runs whole and valid, checksums match. |
| Population | The 48 condition D runs of `experiments/main_grid.json` (seeds 2001–2003). The G2 smoke logs in `runs/D/long0*/` are left out (decision log 2026-11-12, "M3 population is the main grid"). 1,551 turns with no `turn_failure`. |
| Sample | §2 of the protocol at the full rate of 15%: `ceil(0.15 n)` per scenario in the order of `sha256("m3-v1/{run_id}/{input_index}")`. **242 turns**: 148 short, 94 long. The R5 fallback of 10% was not needed. |
| Draft | `results/m3_draft_claude.jsonl`: an AI draft of all 242 verdicts, made from the annotator's view only. sha256 `8ab5e81b72e4c1d50cbce3d8365d93e78b04096a9e933f0f0970e46f64e51c52` (decision log 2026-11-12, "M3 verdicts start from an AI draft reviewed by CI"). |
| Code | `adm/eval/annotate.py` at 17cd7cd (PR #219): `m3 --manifest`, `m3 --draft` |
| Command | `python -m adm.eval.annotate m3 --annotator CI --draft results/m3_draft_claude.jsonl` |
| Output | `results/m3_intent.jsonl` (gitignored; for the team Drive under `results/`): 242 lines, sha256 `3561a33dd9b474372bc28bc6ef7b83d288b44d593d1d2389c1ec310c1c2ee8f5` |
| Checks | One line for every sampled turn and none for any other. Annotator `CI` throughout. `reason` is null exactly when `faithful` is true, and every reason is a protocol code. Every line keeps `draft` and `review`. |

An earlier pass, made on 2026-11-12, accepted every draft in about three minutes. It was set aside and done again, and it is not used. It is kept at `results/m3_set_aside/`, together with a 30-turn check that was meant to be blind but was run with the draft on screen.

## 2. Verdicts

**170 of 242 turns faithful, 72 unfaithful.**

| Executed call | Faithful | Turns |
|---|---|---|
| `skill_check` | 58 | 64 |
| `modify_inventory` | 28 | 66 |
| `update_npc_relationship` | 19 | 33 |
| `attack` | 29 | 32 |
| `cast_spell` | 13 | 22 |
| `update_quest` | 9 | 11 |
| no call (`{"tool": null}`) | 9 | 9 |
| `dodge` | 5 | 5 |

| Sessions | Faithful | Turns |
|---|---|---|
| Short scenarios (s01–s12) | 106 | 148 |
| Long sessions (long01–long04) | 64 | 94 |

| Reason (unfaithful turns) | Count |
|---|---|
| `INVENTED` | 28 |
| `WRONG_TOOL` | 22 |
| `WRONG_VALUE` | 16 |
| `WRONG_TARGET` | 6 |
| `MISSED` | 0 |
| `DROPPED` | 0 |

The model misreads inventory most of all. Of the 38 unfaithful `modify_inventory` turns, 25 are `INVENTED`, 21 of them an item added while the player rested, looked or talked; 5 are `WRONG_VALUE`, mostly a +1 where the player gave the item away; 7 are `WRONG_TOOL`. Relationship updates come next: 14 of 33 are unfaithful, 6 of them in the wrong direction and 11 of the 14 moving the stance down. The 3.4 benchmark pointed at the same two tools (`docs/model_selection.md`).

## 3. Review of the draft

| | Turns |
|---|---|
| Draft accepted unchanged | 238 |
| Edited | 4 |
| of which the verdict changed | 0 |
| of which only the reason code changed | 4 |

Each edit kept the draft's verdict (unfaithful) and changed its reason code:

| Turn | Player input | Draft | CI |
|---|---|---|---|
| `064fcfea` | "I swing at the second kobold if it is still standing" (Cure Wounds on the downed kobold) | `INVENTED` | `WRONG_TOOL` |
| `1c33f6c8` | "I hand the ledger back to Bess" (room key −1) | `WRONG_TARGET` | `WRONG_VALUE` |
| `1d18733b` | "We reach the village at the foot of the pass" (stance down) | `INVENTED` | `WRONG_TOOL` |
| `1e35416e` | "I wrap my blanket around Tobin's shoulders and tell him to keep it" (blanket +1) | `WRONG_VALUE` | `WRONG_TOOL` |

So M3 itself, the faithful share, is the draft's: CI changed no verdict. Because acceptance was so high, the anchoring risk named in the decision log applies, and the report states it. Suggested methods wording: "M3 verdicts were drafted by an AI model from the annotator's view and reviewed turn by turn by one annotator (CI), who changed 4 of 242 drafts, all in their reason code." M3 is single-annotated (Week 5 checkpoint), so no agreement statistic is available.

The two kinds of call the draft settled one way throughout (decision log 2026-11-12, point 4) were accepted as drafted:
- an attack on a combatant already down, with no encounter running: no call is faithful, and a perception check in its place is `WRONG_TOOL`;
- Fire Bolt aimed at a downed, named target that hits a different creature: `WRONG_TARGET`.

## 4. Follow-up

- [ ] Upload `results/m3_intent.jsonl` and `results/m3_draft_claude.jsonl` to the team Drive under `results/` (CI).
- [ ] SD and SS confirm the AI-draft method (decision log 2026-11-12), as they did for the M1 draft.
- WBS 11.3: M3 as 170/242 with a 95% Wilson interval, split by tool and by short versus long, with the reason counts and the review figures of §3.
