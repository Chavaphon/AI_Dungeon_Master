# Final submission pack

WBS 11.12 · Owner: SD · Checked 2026-11-21, re-checked 2026-11-22 after 11.6 to 11.10 merged · Milestone 3 is due 22 Nov 2026.

This page lists everything in the submission pack, where each item lives, and whether it passed the checks. Done when: "MILESTONE 3; nothing carried into December" (TASK_CHECKLIST.md, 11.12). **Status: not complete.** Every task in 11.0 is closed, but the release and one tag are not published (Section 3). Publishing is for a team member, not an agent (`docs/release.md` §3).

## 1. Contents

| Item | Where | Deliverable | State |
|---|---|---|---|
| Final report, in reading order | `docs/report/`: `00_abstract.md`, `01_introduction.md` to `08_future_work_conclusion.md`, `references.md`, `appendix_a_release.md`, `appendix_b_protocols.md` | D10 | All sections written and signed off in the review pass (11.6, `docs/report_review.md` §2) |
| Report figures | `docs/report/figures/` (PNG and SVG) | D10 | 3.1 (11.8) and 5.1 to 5.4 present |
| Defence deck | `docs/defence/deck.pptx`, described in `docs/defence_deck.md` | D11 | Built (11.7), slides 5 and 8 replaced (11.8, 11.9); its sha256 matches `docs/defence_deck.md` §6 |
| Rehearsals and questions | `docs/defence_questions.md`; rehearsals tracked by the team outside the repository | D11 | Top ten questions answered (11.10). One deck fix still open (Section 3) |
| Code release | public repository, `LICENSE` (MIT), `NOTICE` (SRD 5.1 and Llama 3.1) | D12 | Present |
| Data release | `release-v1.0` GitHub release, one archive (`docs/release.md`) | D12 | **Not published:** no `release-v1.0` tag or release exists, and `docs/release.md` §4 is still "Not built yet" |
| Specifications v1.0 | tag `spec-v1.0` | D1 | Present |
| Rubric v1.0 | tag `rubric-v1.0` (decision log, 8.12) | D7 | **Tag missing** on the remote. The freeze commit is `0ab8124`; its `docs/rubric.md` has the sha256 pinned in `tests/test_rubric.py` |
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

## 3. Open before Milestone 3

| Open item | Owner | Task | Blocks |
|---|---|---|---|
| Publish the `release-v1.0` data release by `docs/release.md` §3: fetch the four Drive files, build, commit §4 through a pull request, then tag and release | SS | #123 (11.11) | D12, this task |
| Push the `rubric-v1.0` tag on `0ab8124`, the 8.12 freeze commit | SS, CI or SD | #90 (8.12) | D7, this task |
| Slide 14's speaker notes still name "the demo video (WBS 12.12)", which was dropped (#245). Delete the phrase in PowerPoint and update the sha256 in `docs/defence_deck.md` §6 (`docs/defence_questions.md` §4) | CI | #119 (11.7) | D11 |
| The `owner` findings of the review pass (`docs/report_review.md` §3): gaps, wording and questions left to each section's owner | each owner | #118 (11.6) | D10 |

The first two are outward-facing and are done by a team member. When they are done, SD re-runs the checks in Section 2, updates this page and closes #124.
