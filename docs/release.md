# Code and data release

WBS 11.11 · Owner: SS · 2026-11-20 · CLAUDE.md wins on any conflict.

How the code and the main-grid dataset are released (deliverable D12: "Public repository, licence file, replay instructions"). Done when: "Licence file and attribution present" (TASK_CHECKLIST.md, 11.11). The decision is in `docs/decisions.md` (2026-11-20, "Code and data release"). The replay instructions are Appendix A of the report, `docs/report/appendix_a_release.md`.

## 1. What is released

| Item | Where | Licence |
|---|---|---|
| Code, scenarios, prompts, schemas, docs | https://github.com/Chavaphon/AI_Dungeon_Master (public) at the git tag `release-v1.0` | MIT (`LICENSE`) |
| Dataset | `adm-dataset-v1.0.zip`, attached to the `release-v1.0` GitHub release | MIT (`LICENSE`) |
| Rules | adapted from the SRD 5.1 | CC-BY-4.0, attributed in `NOTICE` |
| Model | not redistributed; `ollama pull llama3.1:8b` | Llama 3.1 Community License, noticed in `NOTICE`; "Built with Llama" in `README.md` and `NOTICE` |

The archive holds:

- the 192 main-grid audit logs, `runs/{condition}/{scenario_id}/{seed}.jsonl`, checked against `experiments/main_grid.sha256`;
- the batch attempt ledger, `results/batch/attempts.jsonl`;
- SD's and SS's M1 labels, CI's M3 verdicts, SD's and SS's M5 ratings, the M5 key, and the three AI drafts the annotators reviewed;
- `dataset/README.md`, `dataset/LICENSE`, `dataset/NOTICE` and `dataset/SHA256SUMS` (the sha256 of every other member).

It is laid out as the repository is, so it unpacks into a checkout of the tag. Outputs the code computes from these files (`results/m1.json`, `results/automated.jsonl` and the others) are not in it; Appendix A recomputes them. The dry run, the smoke runs, aborted attempts and Sponsor User sessions are not the dataset and are not released.

## 2. Checks before it is built

`python -m adm.eval.release` builds nothing unless:

- every log is present with the bytes `experiments/main_grid.sha256` pins;
- every other file is present with the sha256 its own record gives (`ANNOTATIONS` in `adm/eval/release.py`, which says where each pin comes from). A file found under another file's name is named; this matters because both M5 raters' tools write `results/m5_ratings.jsonl`;
- `LICENSE` holds the MIT licence, and `NOTICE` the SRD 5.1 attribution in the wording CC-BY-4.0 asks for, the Llama 3.1 licence notice and "Built with Llama". `tests/eval/test_release.py` checks the repository's two files on every commit.

The members are copied byte for byte (the logs keep the CRLF line endings their checksums are of), in sorted order with one fixed date and mode, so the same files give the same archive.

## 3. Steps to publish

Only a team member publishes; nothing is published by an agent.

1. **Fetch the files from the Drive.** On SS's machine on 2026-11-20 the logs, ledger, the two M1 label files, the overlap draft and the M5 key are in place. These four are not: download them from the team Drive's `results/` as binary files:
   - `results/m1_draft_claude.jsonl`
   - `results/m3_intent.jsonl`
   - `results/m3_draft_claude.jsonl`
   - SD's `results/m5_ratings.jsonl`. First rename the local `results/m5_ratings.jsonl`, which is SS's, to `results/m5_ratings_SS.jsonl`.
2. **Build.** From the repository root, on `main` with the report final:

   ```bash
   python -m adm.eval.release --checksums experiments/main_grid.sha256 --doc docs/release.md
   ```

   It writes `dist/adm-dataset-v1.0.zip` (gitignored) and the block in §4, or lists every problem and exits 1.
3. **Commit §4** through a pull request, so that the tag holds the archive's sha256.
4. **Tag and release**, once that pull request is merged:

   ```bash
   git tag -a release-v1.0 -m "Code and data release (WBS 11.11)" && git push origin release-v1.0
   gh release create release-v1.0 dist/adm-dataset-v1.0.zip --title "AI Dungeon Master v1.0: code and dataset" --notes-file dataset-notes.md
   ```

   The notes are the archive's `dataset/README.md` (`unzip -p dist/adm-dataset-v1.0.zip dataset/README.md > dataset-notes.md`).
5. **Check the published copy:** download the asset into an empty folder, compare its sha256 with §4, unpack it there and run `sha256sum -c dataset/SHA256SUMS`.

## 4. The archive

<!-- results:start -->
Not built yet: four files are on the Drive only (§3, step 1). This block is rewritten by the build.
<!-- results:end -->
