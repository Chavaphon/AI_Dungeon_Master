# Automated checker pass over the main grid

WBS 9.4 · Owner: SD · Run 2026-11-12 · CLAUDE.md wins on any conflict.

The automated checker of CLAUDE.md §10.3 run over every transcript of the main grid: 16 scenarios × 4 conditions × seeds 2001–2003, 192 runs (`docs/main_run.md`, `docs/long_run.md`), checked whole in 9.3 (`docs/run_integrity.md`). Done when: "Automated M1 subset and M4 produced" (TASK_CHECKLIST.md, 9.4). The output is the input of the human pass: 9.5 confirms or rejects each candidate, and 10.1 and 10.4 compute M1 and M4 from it.

**Everything below is candidates, not divergences.** The checker reports candidates with a confidence flag and never a final score (CLAUDE.md §10.3). On the 30 validation turns its precision was 0.19 for `PHANTOM`, 0.67 for `CONTRADICT`, 0.00 for `RELATION` and 0.33 for `RULE` (`docs/checker_validation.md` §2). The counts here measure how much the annotators must read, not how often each condition diverges. No comparison between conditions, and so nothing about H1, may be drawn from them.

## 1. Set-up

| Item | Value |
|---|---|
| Copy scored | The team Drive folder (`README.md`, "Shared storage"): `runs/A` to `runs/D`, downloaded 2026-11-12 to SD's machine |
| Integrity | `python -m adm.eval.integrity --checksums experiments/main_grid.sha256`: **all 192 logs match their checksums**, 6,420 records valid, seeds 2001–2003 in every cell. The ledger (`results/batch/attempts.jsonl`) was not downloaded, so the ledger checks report every run as "no ledger line"; 9.3 already passed them on the same bytes. |
| Code | `adm/eval/checker.py` at `main` 85d13b2, checks `entity_mention`, `hp_band`, `stance`, `rule_violation`, `state_audit` (WBS 8.6–8.9), unchanged since the validation of 8.10 |
| Command | `python -m adm.eval.checker --runs runs/ --out results/automated_all.jsonl`, then the main-grid lines kept (§1.1) |
| Output | `results/automated.jsonl` (gitignored; on the team Drive under `results/`): 4,457 candidates, sha256 `0bd623dffa8741562038de655fec81fbd6f0e8852a19736e5f0bc41cd58d701e` |
| Time | 18 s for 202 logs |
| Reproducible | A second run gave the same bytes. |

### 1.1 Only the main grid

`runs/D/long0*/` also holds the ten 50-turn smoke logs of gate G2 (seeds 1001–1010), and the checker scores every `{seed}.jsonl` it finds: 202 runs and 4,799 candidates. The 342 candidates of the smoke logs are dropped by seed, keeping the main grid's seeds:

```bash
python -m adm.eval.checker --runs runs/ --out results/automated_all.jsonl
python -c "import json; src = open('results/automated_all.jsonl', encoding='utf-8'); open('results/automated.jsonl', 'w', encoding='utf-8', newline='\n').writelines(l for l in src if json.loads(l)['seed'] in (2001, 2002, 2003))"
```

Each run is scored on its own, and the output is sorted by run, so this gives the same lines as scoring the 192 logs alone.

## 2. Turns

| Condition | Records | Failed turns (not scored) | Narrated turns scored |
|---|---|---|---|
| A | 1,605 | 0 | 1,605 |
| B | 1,605 | 0 | 1,605 |
| C | 1,605 | 0 | 1,605 |
| D | 1,605 | 54 | 1,551 |
| **All** | 6,420 | 54 | 6,366 |

A failed condition D turn is skipped, because its narration is the engine's request to rephrase, not the model's (`adm/eval/checker.py`). The 54 are those of 9.3: precondition 47, schema 6, unknown entity 1. M2 counts them; M1 does not.

## 3. Candidates: the automated M1 subset

Candidates per 100 narrated turns, all and high confidence only. `RESOURCE` has no automated check (decision log 2026-11-05, WBS 8.7) and is left wholly to the human pass.

| Category | Check | Condition | High | Low | Per 100 turns | High per 100 turns |
|---|---|---|---|---|---|---|
| `PHANTOM` | `entity_mention` | A | 561 | 521 | 67.4 | 35.0 |
| | | B | 494 | 511 | 62.6 | 30.8 |
| | | C | 388 | 470 | 53.5 | 24.2 |
| | | D | 444 | 468 | 58.8 | 28.6 |
| `CONTRADICT` | `hp_band` | A | 22 | 31 | 3.3 | 1.4 |
| | | B | 44 | 50 | 5.9 | 2.7 |
| | | C | 57 | 45 | 6.4 | 3.6 |
| | | D | 38 | 39 | 5.0 | 2.5 |
| `RESOURCE` | none | all | – | – | – | – |
| `RELATION` | `stance` | A | 2 | 13 | 0.9 | 0.1 |
| | | B | 2 | 22 | 1.5 | 0.1 |
| | | C | 1 | 22 | 1.4 | 0.1 |
| | | D | 5 | 22 | 1.7 | 0.3 |

By kind, over all conditions:

| Check | Kind | High | Low |
|---|---|---|---|
| `entity_mention` | `item` | 1,545 | 707 |
| | `character` | 342 | 844 |
| | `proper_noun` | 0 | 419 |
| `hp_band` | `band` | 117 | 164 |
| | `status` | 44 | 1 |
| `stance` | `stance` | 10 | 79 |

3,024 of the 6,366 narrated turns have at least one candidate, and every one of the 192 runs has some.

## 4. M4: rule violations

| Condition | `rule_violation` high | `rule_violation` low | Per 100 turns | `state_audit` |
|---|---|---|---|---|
| A | 6 | 36 | 2.6 | 0 |
| B | 8 | 41 | 3.1 | 0 |
| C | 6 | 48 | 3.4 | 0 |
| D | 6 | 34 | 2.6 | 0 |

By kind: action after encounter end 121 (high 18), action out of turn order 54 (high 8), spell slot spent below zero 10 (all low).

`state_audit` finds nothing in any condition. The engine makes rule breaks in the state zero by construction, and for A to C the state scored is the replayed ground truth (CLAUDE.md §15 item 56). So M4 rests wholly on `rule_violation`, the breaks the narration describes, and like the M1 candidates these need the human pass before they are counted. Its precision on the validation sample was 0.33 over three candidates.

## 5. For the human pass and the analysis

- **9.5 (#98), 9.6 (#99):** the M1 sample is annotated by rubric v1.0. The candidates are a starting list, not the answer. The checker's recall on validation was 0.35 overall and zero for `RESOURCE`, so annotators read whole narrations, not only flagged spans.
- **The volume is `PHANTOM`.** 87 per cent of the candidates are `entity_mention`, Of its kinds, `character` and `proper_noun` (1,605 candidates here) had no true positive on validation: 0 of 7 and 0 of 3, against 4 of 11 for `item` (`docs/checker_validation.md` §2, "By check"). Expect most of them to be rejected.
- **9.7 (#100):** reads the same logs, unblocked by this pass.
- **10.1 and 10.4:** compute M1 and M4 from confirmed labels, with the bootstrap of CLAUDE.md §10.5, not from these counts.
- **Before reading the logs again,** check the copy: `python -m adm.eval.integrity --checksums experiments/main_grid.sha256`.
