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

**Still to do on the Drive** (§5): the same moves in the shared folder, so the next download is right.

## 4. Checksums

`experiments/main_grid.sha256` holds the sha256 of each of the 192 logs, in `sha256sum` format and the batch runner's order. It pins the dataset that was checked here; its own sha256 is `5655b4adbe788e5d5a83162f73157fc261872656b708c31fc49ababec880d56a`.

Anyone who reads the logs later (9.4 to 9.10, the analysis) checks their copy first, from the repository root:

```
python -m adm.eval.integrity --checksums experiments/main_grid.sha256
```

It exits 0 only when the copy has no gap and every log has the checked bytes. `sha256sum -c experiments/main_grid.sha256` checks the bytes alone.

The logs were written on Windows and end their lines with CRLF; the checksums are of those bytes. Copy them as binary files: a tool that changes line endings changes every checksum, though not the records.

## 5. Follow-ups

- **Drive layout (SS or CI, before 9.4 reads the Drive).** In the shared folder, move `runs/D/s07_smugglers_cove/long0*/{2001,2002,2003}.jsonl` into `runs/D/long0*/`, then delete the four `long0*` folders left inside `runs/D/s07_smugglers_cove/`; their smoke logs are duplicates. Then download again and run the checksum command of §4.
- **CI.** Run the same command against the logs on the machine that played them. If they match, the Drive copy is byte for byte what was played.
- **9.4 (#97) onwards.** Run the §4 command before scoring or annotating. 9.10 (#102) has no failed or incomplete batch to re-run.
