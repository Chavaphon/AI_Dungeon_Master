# M1 annotation: first annotator

WBS 9.5 · Owner: SD · Done 2026-11-13 · CLAUDE.md wins on any conflict.

The first-annotator divergence labels for M1 (CLAUDE.md §10.4), by rubric v1.0 (`docs/rubric.md`), on the M1 sample. Done when: "Sample annotated under rubric v1.0" (TASK_CHECKLIST.md, 9.5). How the sample, the tool and the draft were chosen is in `docs/decisions.md` (2026-11-12, "M1 sample and annotation tool" and "M1 first-annotator labels start from an AI draft").

## 1. Result

| Item | Value |
|---|---|
| Sample | 64 whole runs: per scenario one seed of 2001–2003 by sha256, all four conditions at it (`adm/eval/m1.py`) |
| Turns | **2,124 of 2,124** narrated turns labelled, one line each, all by SD |
| Labels file | `results/m1_labels.jsonl` (gitignored; team Drive `results/`), sha256 `53d74b6bd68400064fa83d8da1f60cc90087ece80918aba13f453362bb11138e` |
| Draft file | `results/m1_draft_claude.jsonl`, sha256 `ad2a46bf43fe659d13d8eff8c9a01b5a3a9a0da970c182998a1b10d660a5c8c3` |
| Checker candidates shown | 1,507 on 1,015 turns; **430 confirmed** |
| Labels added beyond the candidates | **886**: `CONTRADICT` 394, `PHANTOM` 280, `RULE` 158, `RESOURCE` 39, `RELATION` 15 |
| Turns with at least one label | 841 |
| Review | **2,124 accepted, 0 edited** |

Counts per condition, rates per 100 turns and their intervals are 10.1 and 10.4, after 9.6.

## 2. How it was done

1. Claude drafted every turn from the blind view the tool shows (player input, the scored state, the narration and the 9.4 candidates; no condition, run id or seed), in 16 batches of four runs, with a note on each borderline call. The draft passed the tool's check: every sampled turn once, candidate numbers in range, categories known, every phrase in its narration.
2. SD reviewed the turns in `python -m adm.eval.annotate m1 --annotator SD --draft results/m1_draft_claude.jsonl`. Each turn showed the draft under it; Enter accepted it, `e` relabelled the turn. Each line keeps the draft it was shown and `review`.
3. SD accepted the draft on every turn. **The first-annotator labels are therefore the AI draft, unchanged.**

## 3. Limitations, to be stated in the report

- **No edits.** SD changed no turn, so the first-annotator M1 labels are the AI's, confirmed by SD. The methods section says so: "First-annotator M1 labels were drafted by an AI model from the blind view and accepted turn by turn by SD without change; the 20% overlap was labelled independently by a second annotator." The 9.6 alpha is then agreement between the AI draft and an independent human, and is reported as such.
- **Items named only in a player input are scored inconsistently.** Rubric v1.0 §6.1 rule 6 brings characters, groups and places named in the scripted inputs into scope, not items, so such items are strictly `PHANTOM`. The draft batches split: some scored them (for example the satchel, coins and shield), others left them unrecorded as ambiguous. About 32 turns carry a draft note on this call, and every one was accepted as drafted. Batches were formed from runs in hash order, not by condition, so the split is not expected to favour one condition, but it is not balanced by design either; 10.1 should report `PHANTOM` with this caveat.
- **Borderline calls.** 259 draft notes mark a call as borderline or for SD to check (one combatant phrase covering two downed NPCs counted once, death claims, light fixtures as scenery, and so on). All were accepted as drafted.
- **Scenario notes vs the rubric.** The annotator notes in the Bog Witch and Harvest Fair scenario files call a named villager and the fortune teller `PHANTOM`; rubric §6.1 rule 6 puts them in scope. The draft followed the rubric. The scenario notes are to be corrected so 9.6 is not misled.

## 4. For 9.6 and the analysis

- **9.6 (#99, SS):** `python -m adm.eval.annotate m1 --annotator SS --overlap`, 16 runs, 511 turns, with no draft and without seeing these labels. Use rubric v1.0 as written, including §6.1 rule 6 for input-named items.
- **10.1:** M1 per condition from these labels: confirmed candidates plus added labels, per 100 narrated turns, `RULE` excluded (it is M4).
- **Before reading the logs again,** check the copy: `python -m adm.eval.integrity --checksums experiments/main_grid.sha256`.
