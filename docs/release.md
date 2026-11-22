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
| Archive | Size | Members | sha256 |
|---|---|---|---|
| `dist/adm-dataset-v1.0.zip` | 2,351,815 bytes | 206 | `0a2450fa02f2cc01f3d2d7649ef415dcc2237db836664147d29ad745956fa040` |

The 192 logs match `experiments/main_grid.sha256`; the other files match their pins:

| File | What it is | sha256 | Pinned in |
|---|---|---|---|
| `results/batch/attempts.jsonl` | Batch runner's attempt ledger, one line per main-grid run (7.6, 9.3) | `b0340b8f8ceda0563ab61d5d38234a87a89ec48392dc578257f1a54dee189f03` | decision log, 2026-11-20 |
| `results/m1_labels.jsonl` | M1 divergence labels, SD, 64 runs (9.5) | `53d74b6bd68400064fa83d8da1f60cc90087ece80918aba13f453362bb11138e` | docs/m1_annotation.md |
| `results/m1_draft_claude.jsonl` | AI draft SD reviewed for the M1 labels | `ad2a46bf43fe659d13d8eff8c9a01b5a3a9a0da970c182998a1b10d660a5c8c3` | docs/m1_annotation.md |
| `results/m1_labels_SS.jsonl` | M1 overlap labels, SS, 16 runs (9.6) | `dd0a2c8dd263710abe7cf1db249d1b3c05927142283694765de032230dd90285` | docs/m1_overlap.md |
| `results/m1_overlap_draft_claude.jsonl` | AI draft SS reviewed for the overlap labels | `6b7999245f753db1f1e6d979784f4c951830f3ef17c089bc5f02504387669d84` | docs/m1_overlap.md |
| `results/m3_intent.jsonl` | M3 intent-fidelity verdicts, CI, 242 turns (9.7) | `3561a33dd9b474372bc28bc6ef7b83d288b44d593d1d2389c1ec310c1c2ee8f5` | docs/m3_annotation.md |
| `results/m3_draft_claude.jsonl` | AI draft CI reviewed for the M3 verdicts | `8ab5e81b72e4c1d50cbce3d8365d93e78b04096a9e933f0f0970e46f64e51c52` | docs/m3_annotation.md |
| `results/m5_key.json` | M5 key: each excerpt's run and window (8.15) | `2323457f4989117e1c1949eb80b362a1d424a39b4a8b0387845b345775676e34` | decision log, 2026-11-20 |
| `results/m5_ratings.jsonl` | M5 ratings, SD, 64 excerpts (9.9) | `e4d987f6ca49539323c479dd54446d5f6ef0be03baa3613c0593c61127dfc45b` | docs/m5_rating_sd.md |
| `results/m5_ratings_SS.jsonl` | M5 ratings, SS, 64 excerpts (9.8) | `52a7a8b34e0f3d3f10f2e97fd53d371e478c6c35be2812c2cf9f6ace72a42208` | docs/m5_rating_ss.md |

Every member's sha256 is in `dataset/SHA256SUMS` inside the archive.
<!-- results:end -->
