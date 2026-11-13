# Run integrity check: the main grid before annotation

WBS 9.3 · Owner: SS · Run 2026-11-11 · CLAUDE.md wins on any conflict.

The check that the dataset of 9.1 (`docs/main_run.md`) and 9.2 (`docs/long_run.md`) is whole before 9.4 and the annotation read it: every planned run is complete, nothing crashed, and every run carries the right seed. Done when: "Any gap re-run before annotation begins" (TASK_CHECKLIST.md, 9.3). It was run on the team Drive copy, the one the annotators read, not on the machine that played the runs. Why it was built this way is in `docs/decisions.md` (2026-11-11, WBS 9.3).

## 1. Verdict

| Check | Threshold | Result |
|---|---|---|
| Completeness: a log for every planned run | 192 of 192 | **180 of 192 in the Drive copy as downloaded**; 192 of 192 once 12 misplaced logs were moved into place (§3) |
| Completeness: every log valid (`adm.eval.validate`) | every record | **6,420 of 6,420 records valid**: schema, `record_errors`, one record per scripted input with the scripted text, state hashes replay |
| Crashes: last ledger attempt `complete` | every run | **192 of 192**, all on attempt 1, no transport retry, record count equal to the log's |
| Crashes: earlier failed attempts, `runs/pending/`, `runs/aborted/` | listed | **none** |
| Seeds | 2001, 2002, 2003 in every cell | **all 64 (scenario, condition) cells**; every record's and every ledger line's `seed` is its run's |
| One model for every run | one | `llama3.1:8b`, `sha256:46e0c10c…ca666e`, all 192 runs |
| Empty narration in a narrated turn | listed | **none** |
| Gaps to re-run | none before annotation | **none**. The 12 missing logs were a folder misplaced in the Drive copy, not missing runs, so nothing needed playing again (§3) |

## 2. Set-up

| Item | Value |
|---|---|
| Copy checked | The team Drive folder (`README.md`, "Shared storage"): `runs/A` to `runs/D` and `results/batch/attempts.jsonl`, downloaded 2026-11-11 to SS's machine |
| Code | `adm/eval/integrity.py` on `feat/wbs-9.3-run-integrity` |
| Command | `python -m adm.eval.integrity --manifest experiments/main_grid.json --out results/integrity/main_grid.json --write-checksums experiments/main_grid.sha256` |
| Output | report `results/integrity/main_grid.json` (gitignored); checksums `experiments/main_grid.sha256` (committed, §4) |
| Time | 32 s for the 192 runs |

### 2.1 What is checked

| Part | Check | A failure is |
|---|---|---|
| Completeness | every planned run has a log in its place, `runs/{condition}/{scenario_id}/{seed}.jsonl` | a gap |
| | every line of the log is a JSON object (a copy cut short is caught here) | a gap |
| | the log passes the run-log validator of 7.7 (`docs/dry_run.md`), state-hash replay included | a gap |
| Crashes | the run has a ledger line, and its last one is `complete` | a gap |
| | that line has no transport retry, the log's record count and the run's seed | a gap |
| | earlier attempts that failed, logs left in `runs/pending/` or `runs/aborted/` | listed |
| | every run was played with the same model and digest | an error |
| Seeds | every cell holds a log for each of the manifest's seeds | an error |
| | the main grid's seeds are used by no other experiment (smoke 1001–1010, dry run 3001) | a test (`tests/eval/test_integrity.py`) |
| Data, not gaps | turn failures and empty narrations, counted for the annotators | listed |
| Copy | logs outside the manifest, and files under `runs/{condition}/` that are not a log in its place | listed |

A re-run of a complete run reproduces it byte for byte (invariant 4), so it cannot fix anything in the run itself: a failed turn or an odd narration is data. Only a run that is missing, cut short, tainted by a transport retry or crashed can be fixed by playing it again.

`eval` may not read `config/model.json` (docs/conventions.md §1), so the model check asks that every run used one model and digest. The batch runner already refuses a model that does not match the config before it plays anything (decision 52).

## 3. The gap found

In the Drive copy as downloaded, the condition D logs of the four long scenarios at seeds 2001 to 2003 were not in their place. They were under `runs/D/s07_smugglers_cove/`, as if the four `long0*` folders had been dropped into the `s07_smugglers_cove` folder:

```
runs/D/s07_smugglers_cove/long01_border_road/{1001,1002,1003,2001,2002,2003}.jsonl
runs/D/s07_smugglers_cove/long02_hollow_manor/{1004,1005,1006,2001,2002,2003}.jsonl
runs/D/s07_smugglers_cove/long03_river_market/{1007,1008,2001,2002,2003}.jsonl
runs/D/s07_smugglers_cove/long04_mountain_monastery/{1009,1010,2001,2002,2003}.jsonl
```

The ten smoke logs in those folders are byte-identical to the ones in place (`runs/D/long0*/100*.jsonl`). `s07_smugglers_cove`'s own D logs were in place.

**Effect.** Every tool finds a log by its path, so 9.4's checker, the annotation tool and the analysis would have skipped all 12 runs without an error: condition D's long sessions, the ones RQ2 rests on.

**Fix.** Nothing was played again. In the downloaded copy, the 12 main-grid logs were moved into `runs/D/long0*/` and the nested duplicates removed. Checked again, all 192 runs are whole and valid, with 6,420 records. Every log's record count equals the one in CI's validation report for the main grid (`results/batch/validation_main_grid.json`, 9.2), and the 54 failed turns (precondition 47, schema 6, unknown entity 1) are the 40 of 9.1 and the 14 of 9.2.

**On the Drive.** SS made the same moves in the shared folder on 2026-11-11. A fresh download of `runs/` into `results/drive_check/runs/`, checked with `python -m adm.eval.integrity --runs results/drive_check/runs --checksums experiments/main_grid.sha256`, has no gap, no stray file, and every one of the 192 logs matches its checksum. The Drive copy is now the checked dataset.

## 4. Checksums

`experiments/main_grid.sha256` holds the sha256 of each of the 192 logs, in `sha256sum` format and the batch runner's order. It pins the dataset that was checked here; its own sha256 is `5655b4adbe788e5d5a83162f73157fc261872656b708c31fc49ababec880d56a`.

Anyone who reads the logs later (9.4 to 9.10, the analysis) checks their copy first, from the repository root:

```
python -m adm.eval.integrity --checksums experiments/main_grid.sha256
```

It exits 0 only when the copy has no gap and every log has the checked bytes. A copy in another folder is checked with `--runs`, for example a fresh Drive download into `results/drive_check/runs/` (gitignored): `python -m adm.eval.integrity --runs results/drive_check/runs --checksums experiments/main_grid.sha256`. Files are matched by `{condition}/{scenario_id}/{seed}.jsonl`. `sha256sum -c experiments/main_grid.sha256` checks the bytes alone, from the repository root.

The logs were written on Windows and end their lines with CRLF; the checksums are of those bytes. Copy them as binary files: a tool that changes line endings changes every checksum, though not the records.

## 5. Follow-ups

- **Drive layout: done.** Fixed by SS on 2026-11-11 and confirmed on a fresh download (§3).
- **CI: done.** Run by CI on 2026-11-13 against the logs on the machine that played them: every one of the 192 logs matches its checksum, so the Drive copy is byte for byte what was played (§6).
- **9.4 (#97) onwards.** Run the §4 command before scoring or annotating. 9.10 (#102) has no failed or incomplete batch to re-run (§6).

## 6. Re-runs and Milestone 2 (WBS 9.10)

WBS 9.10 · Owner: CI · Run 2026-11-13. Done when: "Dataset complete; MILESTONE 2 evidenced" (TASK_CHECKLIST.md, 9.10).

### 6.1 The copy that was played

The same check, against the logs on CI's machine, the one that played all 192 runs, with the committed checksums:

```
python -m adm.eval.integrity --manifest experiments/main_grid.json --checksums experiments/main_grid.sha256 --out results/integrity/main_grid_ci.json
```

| Check | Result |
|---|---|
| Completeness | 192 of 192 planned runs whole and valid, 6,420 records |
| Crashes | 0 runs with an earlier failed attempt, 0 pending logs, 0 aborted logs; the ledger (`results/batch/attempts.jsonl`) has 192 lines, every one `complete` |
| Seeds | 2001, 2002, 2003 in every cell |
| Model | `llama3.1:8b`, `sha256:46e0c10c…ca666e`, all 192 runs |
| Turn failures (data) | precondition 47, schema 6, unknown entity 1, as in §3 |
| Empty narrations | none |
| Checksums against `experiments/main_grid.sha256` | **match**, all 192 |
| Gaps | **none**; exit 0 |

The ten logs not in the manifest are the G2 smoke runs (seeds 1001–1010, `docs/smoke_runs.md`). `runs/aborted/D/long04_mountain_monastery/1009.jsonl` (30 October) is a smoke attempt from before the main grid and is not part of it; `runs/pending/` holds no log.

### 6.2 Nothing re-run

No planned run is missing, cut short, crashed or tainted by a transport retry, on either copy, so the batch runner was not run again. A re-run of a complete run reproduces it byte for byte (invariant 4), so it could not change the 54 failed turns or any narration: they are data. The dataset is the 192 logs pinned by `experiments/main_grid.sha256` (sha256 `5655b4adbe788e5d5a83162f73157fc261872656b708c31fc49ababec880d56a`), and both the Drive copy and the copy that was played match it.

### 6.3 Milestone 2 and deliverable D8

Milestone 2 (15 November): "Audit-log dataset complete." D8: "All runs present, seeds recorded, integrity checked."

| Must be true | Evidence |
|---|---|
| All 12 scenarios × 4 conditions run | 144 of 144 short runs (`docs/main_run.md`), whole and valid here |
| Long sessions run | 48 of 48 long runs at 50 turns (`docs/long_run.md`), whole and valid here |
| Integrity-checked | §1 on the Drive copy (SS, 2026-11-11) and §6.1 on the copy that was played (CI, 2026-11-13): no gap, checksums match |
| Seeds recorded | 2001, 2002, 2003 in all 64 (scenario, condition) cells; every record's and every ledger line's `seed` is its run's (§1) |

Milestone 2 is met. The fallback, cutting the long sessions to 30 turns, was not needed.
