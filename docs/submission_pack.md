# Final submission pack

WBS 11.12 · Owner: SD · Checked 2026-11-21, re-checked 2026-11-22 after 11.6 to 11.10 merged, release published 2026-11-22 · Milestone 3 is due 22 Nov 2026.

This page lists everything in the submission pack, where each item lives, and whether it passed the checks. Done when: "MILESTONE 3; nothing carried into December" (TASK_CHECKLIST.md, 11.12). **Status: complete.** Every task in 11.0 is closed, the `release-v1.0` release and the `rubric-v1.0` tag are published, and the published archive was checked (Section 3). Two items are left with their owners (Section 4).

## 1. Contents

| Item | Where | Deliverable | State |
|---|---|---|---|
| Final report, in reading order | `docs/report/`: `00_abstract.md`, `01_introduction.md` to `08_future_work_conclusion.md`, `references.md`, `appendix_a_release.md`, `appendix_b_protocols.md` | D10 | All sections written and signed off in the review pass (11.6, `docs/report_review.md` §2) |
| Report figures | `docs/report/figures/` (PNG and SVG) | D10 | 3.1 (11.8) and 5.1 to 5.4 present |
| Defence deck | `docs/defence/deck.pptx`, described in `docs/defence_deck.md` | D11 | Built (11.7), slides 5 and 8 replaced (11.8, 11.9); its sha256 matches `docs/defence_deck.md` §6 |
| Rehearsals and questions | `docs/defence_questions.md`; rehearsals tracked by the team outside the repository | D11 | Top ten questions answered (11.10). One deck fix still open (Section 3) |
| Code release | public repository, `LICENSE` (MIT), `NOTICE` (SRD 5.1 and Llama 3.1) | D12 | Present |
| Data release | [`release-v1.0`](https://github.com/Chavaphon/AI_Dungeon_Master/releases/tag/release-v1.0) GitHub release, `adm-dataset-v1.0.zip` (`docs/release.md` §4) | D12 | Published; the downloaded asset's sha256 matches §4 |
| Specifications v1.0 | tag `spec-v1.0` | D1 | Present |
| Rubric v1.0 | tag `rubric-v1.0` (decision log, 8.12) | D7 | Present, on the freeze commit `0ab8124`, whose `docs/rubric.md` has the sha256 pinned in `tests/test_rubric.py` |
| D2 to D9 | model freeze, rule suite, scenarios, condition D, harnesses, dataset, agreement | D2 to D9 | Issues closed: 3.6, 4.17, 8.5, 6.11, 7.7, 9.10, 10.5 |

## 2. Checks on the report

Re-run over every report file on 2026-11-22, on `main` after 11.6 (#247) and 11.10 (#248).

| Check | Result |
|---|---|
| Every section in the outline exists, with its owner and reviewer in its header | Pass, 12 files, about 26,700 words |
| Every in-text citation has an entry in `references.md`, and every entry is cited | Pass, 22 references, after restoring the Ollama entry (below) |
| Every image link resolves to a file in `figures/` | Pass, 5 images |
| Every repository path in backticks exists | Pass. Paths under `results/` and `dataset/` in Appendix A are gitignored and ship in the release archive; Appendix B's prompt files are in `config/prompts/` |
| Every "Section x.y" reference points to an existing heading | Pass |
| Every "Table x.y" is defined | Pass, 14 tables |
| Every figure referenced has a caption | Pass, Figures 3.1 and 5.1 to 5.4 |
| No `TODO`, `TBD`, `FIXME`, `??` or placeholder left | Pass |
| `LICENSE` is MIT and `NOTICE` names SRD 5.1 and Llama 3.1 | Pass |

**Ollama reference restored.** The 11.6 review cited Ollama in Section 3.8 and added its entry to `references.md` (R3-3, `4e4b2a0`). The merge of `main` into the review branch (`9e25dbb`) dropped the entry, so `main` cited "(Ollama, n.d.)" with no reference. This pull request puts the entry back, as 11.6 wrote it. Nothing else was lost in that merge: the merge differs from the branch tip only in that line.

## 3. Release and tags

Published on 2026-11-22, by `docs/release.md` §3, from SD's machine:

1. The four files that were on the Drive only, the main-grid ledger and SS's `results/m5_key.json` were put in place. SD's local key had the same content as the pinned file with LF line endings; the pinned bytes (CRLF) were used.
2. The build wrote `dist/adm-dataset-v1.0.zip`: 206 members, 2,351,815 bytes, sha256 `0a2450fa02f2cc01f3d2d7649ef415dcc2237db836664147d29ad745956fa040`. A second build gave identical bytes.
3. §4 was committed through #261.
4. `release-v1.0` was tagged on `main` after #249 and #261 (`ecc3523`), and the GitHub release was created with the archive and the archive's `dataset/README.md` as its notes. `rubric-v1.0` was tagged on `0ab8124`.
5. The asset was downloaded into an empty folder: its sha256 matches §4, and `sha256sum -c dataset/SHA256SUMS` passes for all 205 files.

`docs/release.md` §3 says a team member publishes and not an agent. Steps 1 to 5 were run by Claude Code on SD's explicit instruction, in SD's session and with SD's GitHub account.

## 4. Left with their owners

Neither blocks a deliverable's existence; both are edits to what is already submitted.

| Item | Owner | Task |
|---|---|---|
| Slide 14's speaker notes still name "the demo video (WBS 12.12)", which was dropped (#245). Delete the phrase in PowerPoint and update the sha256 in `docs/defence_deck.md` §6 (`docs/defence_questions.md` §4) | CI | #119 (11.7) |
| The `owner` findings of the review pass (`docs/report_review.md` §3): gaps, wording and questions left to each section's owner | each owner | #118 (11.6) |
