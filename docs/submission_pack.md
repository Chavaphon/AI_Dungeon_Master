# Final submission pack

WBS 11.12 · Owner: SD · Checked 2026-11-21 · Milestone 3 is due 22 Nov 2026.

This page lists everything in the submission pack, where each item lives, and whether it passed the checks. Done when: "MILESTONE 3; nothing carried into December" (TASK_CHECKLIST.md, 11.12). **Status: not complete.** Section 3 lists the open items.

## 1. Contents

| Item | Where | Deliverable | State |
|---|---|---|---|
| Final report, in reading order | `docs/report/`: `00_abstract.md`, `01_introduction.md` to `08_future_work_conclusion.md`, `references.md`, `appendix_a_release.md`, `appendix_b_protocols.md` | D10 | All sections written. Review pass (11.6) open; Figure 3.1 is a text placeholder |
| Report figures | `docs/report/figures/` (PNG and SVG) | D10 | 5.1 to 5.4 present; 3.1 waits on 11.8 |
| Defence deck, rehearsed twice | not in the repository yet | D11 | **Open:** 11.7, 11.8, 11.9 and 11.10 |
| Code release | public repository, `LICENSE` (MIT), `NOTICE` (SRD 5.1 and Llama 3.1) | D12 | Present |
| Data release | `release-v1.0` GitHub release, one archive (`docs/release.md`) | D12 | **Not published:** no `release-v1.0` tag or release exists |
| Specifications v1.0 | tag `spec-v1.0` | D1 | Present |
| Rubric v1.0 | tag `rubric-v1.0` (decision log, 8.12) | D7 | **Tag missing** on the remote; the file is pinned by sha256 in `tests/test_rubric.py` |
| D2 to D9 | model freeze, rule suite, scenarios, condition D, harnesses, dataset, agreement | D2 to D9 | Issues closed: 3.6, 4.17, 8.5, 6.11, 7.7, 9.10, 10.5 |

## 2. Checks on the report

Run over every report file on 2026-11-21, after merging 11.4 (#240).

| Check | Result |
|---|---|
| Every section in the outline exists, with its owner and reviewer in its header | Pass, 12 files, about 26,500 words |
| Every in-text citation has an entry in `references.md`, and every entry is cited | Pass, 21 references |
| Every image link resolves to a file in `figures/` | Pass, 4 images |
| Every repository path in backticks exists | Pass |
| Every "Section x.y" reference points to an existing heading | Pass |
| Every "Table x.y" is defined | Pass, 14 tables |
| Every figure referenced has a caption | Pass; Figure 3.1's is marked as a placeholder for 11.8 |
| No `TODO`, `TBD`, `FIXME` or `??` left | Pass |
| Numbers in sections 6 to 8 and the Abstract match Section 5 or the docs it cites | Pass |
| `LICENSE` is MIT and `NOTICE` names SRD 5.1 and Llama 3.1 | Pass |

**References.** Sections 1 and 2 cite all the related work, so the list that closed Section 2 is now `references.md`, at the end of the report. Three methods sources were added where the report relies on them: the bootstrap (Efron & Tibshirani, 1993) and Krippendorff's alpha (Hayes & Krippendorff, 2007) in Section 5, the Wilson (1927) interval in Section 5.5, and Llama 3 (Grattafiori et al., 2024) in Section 7.1. Sections 3 and 4 use the bootstrap, the Wilson interval and Ollama without a citation; CI may add them in 11.6.

## 3. Open before Milestone 3

Each is owned by a WBS task, so this list carries no new task.

| Open item | Owner | Task | Blocks |
|---|---|---|---|
| Review pass: each section read by someone who did not write it | ALL | #118 (11.6) | D10 |
| Loop-corrected architecture diagram, which replaces Figure 3.1's text version | SS | #120 (11.8) | D10, D11 |
| Defence deck, in talk order | CI | #119 (11.7) | D11 |
| Evaluation slide | CI | #121 (11.9) | D11 |
| Two timed rehearsals and the top ten questions | ALL | #122 (11.10) | D11, this task |
| Publish the `release-v1.0` data release; `docs/release.md` §4 says four files are still on the Drive only. A team member publishes it, by `docs/release.md` §3 | SS | #123 (11.11) | D12 |
| Push the `rubric-v1.0` tag that the 8.12 decision records | SS, CI or SD | #90 (8.12) | D7 |

When all of these are done, SD re-runs the checks in Section 2, updates this page and closes #124.
