# Report review pass

WBS 11.6 · Owner: ALL · Drafted 2026-11-22 · Status: **every section read by its reviewer, 2026-11-22; owner findings applied 2026-11-22 (WBS 12.9, §5)** · CLAUDE.md wins on any conflict.

The final report (deliverable D10) is accepted when every section has been read by someone who did not write it (`TASK_CHECKLIST.md`, D10; issue #118). The reviewer of each section is fixed in `docs/report_outline.md` and repeated in each section's header. This page is the record of that pass: who read what, what they found, and what was changed.

## 1. How the review was done

The review read the report as it will be submitted: `main` with the Abstract, the merged `references.md` and the small §2, §5 and §7 edits of PR #243 (WBS 11.12).

Each section was checked for:

1. **Numbers.** Every rate, interval, count and ratio against the doc it comes from (`docs/m1_rates.md`, `docs/m1_growth.md`, `docs/m2_tool_calls.md`, `docs/m3_annotation.md`, `docs/m4_rule_violations.md`, `docs/m6_latency.md`, `docs/m5_scores.md`, `docs/agreement.md`, `docs/run_integrity.md` and the rest) and against the Section 5 tables.
2. **Spec fidelity.** Statements about the system and method against CLAUDE.md and the spec docs.
3. **Outline.** Every bullet of `docs/report_outline.md` for the section is covered.
4. **Cross-references.** Every Section, Table and Figure number, repository path, image link and citation resolves.
5. **Consistency.** A number is stated the same way in the Abstract, Section 5, Sections 6 to 8 and the defence deck's slide table (`docs/defence_deck.md` §3).
6. **Readability.** Unclear sentences and terms used before they are defined.

**AI drafting.** The findings below were drafted by an AI model reading each section against its sources, and every `error` and `gap` was checked again against the cited line and source before it was recorded. A drafted finding is not a review: the named reviewer reads the section, confirms or rejects each finding, adds their own, and signs in Section 2. Only that read meets the done-when.

**Classes.** `error`: a wrong number, fact or reference with one correct value. `gap`: an outline item missing. `wording` and `question`: for the section's owner to decide.

**What was changed.** Only `error`s with one unambiguous correct value were fixed in the report, in the same pull request as this page. Every `gap`, `wording` and `question` is left to the section's owner. No fix changes a number or claim used on a slide, so `docs/defence_deck.md` is unchanged (slide 11's "86.6% recovered" is already per turn).

## 2. Sign-off

A reviewer fills in the date after reading the whole section and marking each finding below `confirmed` or `rejected`. #118 closes when every row has a date.

All eleven rows were signed off on 2026-11-22, as reported by CI for all three reviewers (SD, SS and CI). No finding was marked `rejected`, so the findings in Section 3 stand as drafted; each `owner` item is still for its section's owner.

| Section | File | Owner | Reviewer | Read by reviewer | Findings | Fixed here | For owner |
|---|---|---|---|---|---|---|---|
| Abstract | `00_abstract.md` | SD | CI | 2026-11-22 | 5 | 1 | 4 |
| 1 Introduction | `01_introduction.md` | SS | SD | 2026-11-22 | 9 | 1 | 8 |
| 2 Background | `02_background.md` | SS | SD | 2026-11-22 | 5 | 1 | 4 |
| 3 System design | `03_system_design.md` | CI | SS | 2026-11-22 | 6 | 2 | 4 |
| 4 Experimental method | `04_experimental_method.md` | CI | SD | 2026-11-22 | 10 | 3 | 7 |
| 5 Results | `05_results.md` | SD | CI | 2026-11-22 | 7 | 2 | 5 |
| 6 Discussion | `06_discussion.md` | SD | SS | 2026-11-22 | 5 | 4 | 1 |
| 7 Limitations | `07_limitations.md` | SD | CI | 2026-11-22 | 7 | 2 | 5 |
| 8 Future work, conclusion | `08_future_work_conclusion.md` | SD | SS | 2026-11-22 | 1 | 1 | 0 |
| A Reproduction and release | `appendix_a_release.md` | SS | CI | 2026-11-22 | 6 | 1 | 5 |
| B Rubric and protocols | `appendix_b_protocols.md` | CI | SS | 2026-11-22 | 2 | 0 | 2 |

`references.md` has no reviewer in the outline; its changes are listed in Section 4.

## 3. Findings

Line numbers are those before the fixes. Status: `fixed` (in this pull request) or `owner` (left to the section's owner). The reviewer adds `confirmed` or `rejected`.

### Abstract (SD; reviewer CI)

| ID | Line | Class | Finding | Source | Status |
|---|---|---|---|---|---|
| A-01 | 7 | error | "recovered 86.6% of rejected tool calls": 86.6% is of rejected *turns* (348 of 402), not calls (573 rejected attempts), and the retry loop saves them | `docs/m2_tool_calls.md` §3, Table 5.7 | fixed: "saved 86.6% of the turns with a rejected tool call within the retry budget" |
| A-02 | 5 | wording | "a deterministic rules engine based on SRD 5.1"; the spec says *inspired by*, not compatible | CLAUDE.md §4 | owner: "inspired by SRD 5.1"; fixed in 12.9 |
| A-03 | 7 | wording | "Yet 70.2% of its executed calls" reads as a positive and hides that it is a 15% sample | `docs/m3_annotation.md` §2 | owner: "Yet only 70.2% of a 15% sample of its executed calls"; fixed in 12.9 |
| A-04 | 7 | wording | "Divergence did not grow over a session" is stronger than the test (no slope interval excludes 0, 4 runs per condition); §5.2 says "measurably". Same in §6.1 and §8.2 | `docs/m1_growth.md` §4 | owner: "did not grow measurably"; fixed in 12.9 |
| A-05 | — | question | The outline has no bullets for the Abstract; it was checked against Sections 5 to 8 instead | `docs/report_outline.md` | owner; no change needed (12.9): the Abstract was checked against Sections 5 to 8 |

### 1 Introduction (SS; reviewer SD)

| ID | Line | Class | Finding | Source | Status |
|---|---|---|---|---|---|
| R1-1 | 60, 67 | question | The framing is cited to "proposal (v4, §4)" at line 60 and to "the proposal's Section 8" at line 67. CLAUDE.md §1.2 says Section 8.0; the outline says §4. The proposal PDF is not in the repository | CLAUDE.md §1.2 | owner: check the PDF, use one; **open** (12.9): needs the proposal PDF |
| R1-2 | 60 | question | The lecture date "17 September 2026" appears nowhere else in the repository | — | owner: confirm or drop; **open** (12.9): needs the lecture record |
| R1-3 | 36 | wording | Long sessions "of 50 turns"; §4.2, §5.2 and §8.2 say 52 scripted inputs | `docs/long_run.md` | owner: "of 52 scripted inputs"; fixed in 12.9 |
| R1-4 | 56 | error | "Every interval is a percentile bootstrap", but M3 uses a Wilson interval (§4.7); RQ2 is the slope against the scripted position, not turn number | CLAUDE.md §15 item 66; `docs/intent_fidelity.md` §5 | fixed |
| R1-5 | 54 | wording | "answers within 10 seconds per turn at the 95th percentile"; the target is fixed as p95 turn latency under 10 s | CLAUDE.md §10.5 | owner; fixed in 12.9 |
| R1-6 | 64 | question | "the twelve-scenario suite" (copied from CLAUDE.md §1.2); the evaluation set is 16 scenarios | CLAUDE.md §10.5, §4.2 | owner: "sixteen-scenario"; fixed in 12.9 |
| R1-7 | 67 | wording | "Section 3 maps each principle onto the architecture (the proposal's Section 8)" reads as if Section 3 were the proposal's | — | owner: "Section 3.9 maps …, as the proposal's Section 8.0 did"; fixed in 12.9 |
| R1-8 | 7 | question | Ji et al. (2023) is a general hallucination survey, not evidence about a DM narrator; "over a long session" suggests growth, which RQ2 did not find | Table 5.1 | owner; fixed in 12.9 |
| R1-9 | 37 | wording | "validated against hand-labelled turns"; the labels were AI-drafted and reviewed. Same at §4 lines 58 and 91 and §8.2 line 24 ("2,124 hand-labelled turns") | `docs/m1_annotation.md`, `docs/checker_validation.md` | owner: "AI-drafted, human-reviewed labels"; fixed in 12.9 |

### 2 Background and related work (SS; reviewer SD)

| ID | Line | Class | Finding | Source | Status |
|---|---|---|---|---|---|
| R2-1 | 34, 36 | error | Two different works cited as "(Liu et al., 2024)"; APA tells them apart by initials | `references.md` (Liu, N. F.; Liu, X.) | fixed: "N. F. Liu et al." and "X. Liu et al." |
| R2-2 | — | question | The Player Experience Inventory's first author's surname is Vanden Abeele; the entry and citation give "Abeele, V. V." | `references.md` | owner; fixed in 12.9 |
| R2-3 | — | question | The stated reason the player study was withdrawn ("examination blackouts") and the plan to use PEI or GEQ are not in the repository | CLAUDE.md §14 | owner: confirm against the proposal; **open** (12.9): needs the proposal |
| R2-4 | §2.1 | gap | The outline asks for "LLM game masters and interactive fiction"; no interactive-fiction or text-adventure work is discussed | `docs/report_outline.md` §2 | owner; **open** (12.9): needs new literature; no citation added without a source read |
| R2-5 | 64 | wording | "The mechanics are derived from" SRD 5.1 sits beside "not compatible" | CLAUDE.md §4 | owner: "inspired by"; fixed in 12.9 |

PR #243 also moved §2's reference list to `references.md`; SS to check the move.

### 3 System design (CI; reviewer SS)

| ID | Line | Class | Finding | Source | Status |
|---|---|---|---|---|---|
| R3-1 | 202 | error | "K and both temperatures are frozen in one configuration file"; `config/model.json` holds only the narration temperature, and 0.0 is a constant in the client | `config/model.json`; `adm/orchestration/client.py` (`TOOLCALL_TEMPERATURE`, `SUMMARY_TEMPERATURE`) | fixed |
| R3-3 | 27, 202 | error | No citations in §3: SRD 5.1, Llama 3.1 and Ollama are named without one, and Ollama had no reference entry | `references.md`; PR #243 | fixed: SRD 5.1, Grattafiori et al. (2024) and Ollama cited; Ollama entry added |
| R3-2 | 161 | wording | Context item 2 gives the state to "conditions B, C and D", but D's narration call gets no state (line 150) | CLAUDE.md §9.1 | owner: "conditions B and C, and condition D's tool call"; fixed in 12.9 |
| R3-4 | 89 | question | "so that the player can loot a defeated creature" (from `docs/tool_contract.md`); CLAUDE.md §6.1 says no transfer between inventories and no taking an item from an NPC | CLAUDE.md §6.1 | owner: drop, or "so that an unconscious owner's inventory can still change"; fixed in 12.9 |
| R3-5 | 213 | wording | "Nothing else used the GPU during the experiment"; the source states a rule, not an observation | `docs/hardware.md` | owner: "Nothing else was allowed to use the Ollama server during a batch"; fixed in 12.9 |
| R3-6 | — | wording | Six tables without captions, while §5 numbers every table; optionally cite Willard & Louf (2023) at grammar-constrained decoding (line 132) | — | owner; declined (12.9): optional; adding captions would renumber the tables of `docs/submission_pack.md` §2 |

### 4 Experimental method (CI; reviewer SD)

| ID | Line | Class | Finding | Source | Status |
|---|---|---|---|---|---|
| R4-1 | 129–138 | error | §4.9 says "Two refinements were fixed later … before the figures they govern were read". The log has five (13, 15, 17, 17 and 19 November), and the Objective 3 rule was fixed after the M1 alpha was known. RQ2 is given as the slope against turn number, but decision 66 fixes the scripted position; §5.2 cites §4.9 for it. The H2 reading rule used in Table 5.1 is not stated | CLAUDE.md §15 items 66, 67, 71; `docs/decisions.md` 2026-11-17, 2026-11-19 | fixed: RQ2 bullet, H2 rule and Objective 3 rule added with their dates |
| R4-2 | 103 | error | "16 runs, a fifth of each condition's sample"; it is `ceil(0.2 × 16)` = 4 of each condition's 16 | `adm/eval/m1.py` (`overlap_runs`) | fixed: "4 of each condition's 16 (a fifth, rounded up)" |
| R4-4 | 111, 136 | gap | Wilson interval and bootstrap used without a citation (first cited in §5) | `references.md` | fixed: Wilson (1927), Efron & Tibshirani (1993) |
| R4-3 | 101 | question | The outline asks for the `docs/m1_annotation.md` §3 sentence verbatim; that sentence was superseded on 15 November, and §4 quotes the superseding decision word for word, which is right. The outline's pointer is stale | `docs/decisions.md` 2026-11-15 | owner (SD, outline); fixed in 12.9 |
| R4-5 | 113–115 | gap | CI's first M3 pass, set aside and done again, is not disclosed in §4.7 or §7; the decision log lists it among the limitations carried into the report | `docs/m3_annotation.md` §3; `docs/decisions.md` 2026-11-15 checkpoint | owner; fixed in 12.9 |
| R4-6 | 71 | question | The `rubric-v1.0` tag does not exist locally or on the remote; the sha256 pin in `tests/test_rubric.py` does | `docs/submission_pack.md` §3 | owner (#90); resolved (12.9): `rubric-v1.0` is now tagged on `0ab8124`; no text change |
| R4-7 | 56–63 | gap | The table of metrics has a pooled data column only; the 11.9 grid gives the sample per condition | `docs/defence_deck.md` slide 8 | owner; fixed in 12.9 |
| R4-8 | 95 | wording | "share their dice and inputs"; D's rolls follow its own calls, so the conditions share the seed and inputs | — | owner; fixed in 12.9 |
| R4-9 | 50 | wording | "found no gap to re-run" omits that 12 logs were misplaced in the Drive copy and found on checking | `docs/run_integrity.md` | owner (optional); fixed in 12.9 |
| R4-10 | 58–62 | wording | The table uses "§4.6", the text "Section 4.6" | — | owner; fixed in 12.9 |

### 5 Results (SD; reviewer CI)

| ID | Line | Class | Finding | Source | Status |
|---|---|---|---|---|---|
| R5-01 | 223 | error | "The two agree only on vividness"; both raters also put D above A on engagement (SS +0.25, SD +0.06). They disagree on coherence and tone only. Repeated in §6 line 19 and §7 line 27 | `docs/m5_scores.md` §3; Table 5.12 | fixed in §5, §6 and §7 |
| R5-02 | 98 | error | The catalogue draw is cited to "Section 4", which never mentions the catalogue | grep of `04_experimental_method.md` | fixed: reference to Section 4 removed |
| R5-03 | 98 | wording | "The labels it quotes are the AI draft that SD accepted" holds for entries 1 to 8; entry 10 carries CI's edited M3 verdict, entry 9 a logged fact | `docs/failure_catalogue.md` entry 10 | owner: "The M1 and M4 labels it quotes are the AI draft that SD accepted; the M3 verdict is CI's"; fixed in 12.9 |
| R5-04 | 193 | wording | The slow tail is put down to summary regenerations only; the source names retries too | `docs/m6_latency.md` §3 | owner; fixed in 12.9 |
| R5-05 | 223, 251 | wording | M5 agreement "below chance" at 223, "no better than chance" at 251; vividness alpha is −0.013 | `docs/agreement.md` §4 | owner: "no better than chance"; fixed in 12.9 |
| R5-06 | 148 | wording | "15% of the 1,551 D turns" gives 233, not 242; the sample is 15% per scenario, rounded up | `docs/m3_annotation.md` §1 | owner; fixed in 12.9 |
| R5-07 | 48 | wording | "(Section 7)" for the input-named-items inconsistency; it is §7.2 | — | owner; fixed in 12.9 |

### 6 Discussion (SD; reviewer SS)

| ID | Line | Class | Finding | Source | Status |
|---|---|---|---|---|---|
| R6-1 | 19 | error | "disagree even on the direction of D − A for three of the four items"; it is two, coherence and tone (see R5-01) | `docs/m5_scores.md` §3 | fixed |
| R6-2 | 29 | error | "In condition D … the state audit is zero on all 6,366 narrated turns"; 6,366 is all four conditions, D has 1,551 | Table 5.9 | fixed |
| R6-3 | 56 | error | The forced re-prompt after a first `{"tool": null}` is in catalogue entries 2 and 10; entry 6 starts with a `NO_SPELL_SLOT` rejection | `docs/failure_catalogue.md` entries 2, 6, 10 | fixed |
| R6-4 | 33 | error | D's narrator getting facts, not state, is cited to Sections 3.4 and 3.6; it is in 3.5 (line 150), and 3.6 does not say it | `03_system_design.md` §3.5 | fixed: "Sections 3.4 and 3.5" |
| R6-5 | 64 | wording | The sponsor doc says the null-call path "most likely" happened (the logs were not read); the report states it as fact. Also line 29, "refused 573 illegal proposals", counts unparseable replies, which are not proposals | `docs/sponsor_feedback.md`; `docs/m2_tool_calls.md` | owner: "most likely"; "refused 573 tool-call attempts"; fixed in 12.9 |

### 7 Limitations and threats to validity (SD; reviewer CI)

| ID | Line | Class | Finding | Source | Status |
|---|---|---|---|---|---|
| R7-01 | 39 | error | "a halving of the rate would have shown, but a modest effect would not (Section 5.1)"; the argument is made in §6.1 | `06_discussion.md` §6.1 | fixed: "Sections 5.1 and 6.1" |
| R7-03 | 27 | error | "The two raters do not agree on direction"; they agree on two items (see R5-01) | `docs/m5_scores.md` §3 | fixed: "disagree on direction for two of the four items" |
| R7-02 | 41–48 | wording | The list of later rules says each was fixed before its figures were read; the Objective 3 rule (17 November) was fixed after the M1 alpha was known, as line 17 admits, and is not listed | `docs/agreement.md`; `docs/decisions.md` 2026-11-17 | owner: add it, qualify "each"; fixed in 12.9 |
| R7-04 | 37 | wording | "Attacking a downed foe … is common in the data (Section 5.6)"; §5.6 counts attacks narrated after the encounter ended (121 of 185) | `05_results.md` §5.6 | owner; fixed in 12.9 |
| R7-05 | 17 | wording | "a review of about 40 minutes"; the source says at most about 40 minutes | `docs/m1_overlap.md` §5 | owner; fixed in 12.9 |
| R7-06 | 19 | wording | The heading says "Two inconsistencies", but the 259 borderline calls are not an inconsistency | — | owner: "Two weaknesses"; fixed in 12.9 |
| R7-07 | 21 | wording | "changed the reason code on 4 of 242, and no verdict" reads awkwardly | — | owner: "changed no verdict, and changed the reason code on 4 of the 242 drafts"; fixed in 12.9 |

### 8 Future work and conclusion (SD; reviewer SS)

| ID | Line | Class | Finding | Source | Status |
|---|---|---|---|---|---|
| R8-1 | 17 | error | "rather than a quarter of it"; M1 covers 64 of 192 runs, a third (§7.3 says "64 of the 192 runs") | Table 5.1; `docs/m1_rates.md` | fixed: "a third" |

A-04 and R1-9 also touch §8.2.

### Appendix A: reproduction and release (SS; reviewer CI)

| ID | Line | Class | Finding | Source | Status |
|---|---|---|---|---|---|
| RA-01 | 56 | error | The validator "replays each log's diffs from the scenario's initial state"; that holds for D only, A to C replay `replay_script` | `adm/eval/validate.py` docstring, check 5 | fixed |
| RA-02 | 93 | wording | The exhibit reads `results/m1.json` by default, so it runs after M1; only the figures row says when to run | `adm/eval/exhibit.py` (`--m1`) | owner: "(after M1)"; fixed in 12.9 |
| RA-03 | 78 | wording | "Each command reads the logs … and rewrites the results block of its document" does not hold for every row: the checker takes no `--doc`, `m5_scores` and `figures` do not read the logs | the CLI options | owner; fixed in 12.9 |
| RA-04 | 20–28 | wording | The archive table leaves out `dataset/README.md`, `dataset/LICENSE` and `dataset/NOTICE` | `docs/release.md`; `adm/eval/release.py` | owner; fixed in 12.9 |
| RA-05 | 12, 38 | question | `release-v1.0` is neither built nor tagged, so the appendix points at an archive that does not exist yet | `docs/release.md` §4 | owner (#123); resolved (12.9): `release-v1.0` is published; no text change |
| RA-06 | 86 | question | M3 has no command; its Wilson interval was computed by hand. Give the counts (170 of 242) and the formula so a reader can check it? | — | owner; fixed in 12.9 |

### Appendix B: rubric, rating form and protocols (CI; reviewer SS)

| ID | Line | Class | Finding | Source | Status |
|---|---|---|---|---|---|
| RB-1 | 16 | wording | Retry messages are "sent as user messages after the model's rejected reply"; `retry_unparseable` and `retry_no_tool` do not follow a rejection | CLAUDE.md §7.1 | owner; fixed in 12.9 |
| RB-2 | 304 | wording | The quoted M5 form says "(§9.1)", meaning CLAUDE.md §9.1; a report reader will look for a Section 9.1 | — | owner: keep the quote, add "[CLAUDE.md §9.1; Appendix B.1]"; fixed in 12.9 |

Checked and found correct, among other things: all eleven prompt templates in B.1 byte-identical to `config/prompts/` with matching sha256; B.2 against `docs/rubric.md` v1.0; B.3 and B.4 against their protocols; every Wilson interval in Table 5.8 recomputed from its counts.

## 4. Outside the report sections

- **`references.md`**: Ollama entry added for R3-3 (fixed). R2-1 and R2-2 concern its Liu and Vanden Abeele entries.
- **`docs/submission_pack.md`** (PR #243) still lists Figure 3.1 as a placeholder and 11.8 as open; #246 merged the diagram. For SD in 11.12; not changed here.
- **`docs/report_outline.md`** gives the framing as "proposal §4" (R1-1) and points §4's disclosure at the superseded `docs/m1_annotation.md` §3 sentence (R4-3). For SD; not changed here. R4-3 was fixed in 12.9 (§5).

## 5. Owner pass (WBS 12.9)

The Week 7 checkpoint left the `owner` findings to be done before the blackout (`docs/decisions.md`, 2026-11-22, decision 1). On 2026-11-22 CI applied them to the report in one pull request (#125), drafted with an AI model and checked against each finding's source. Each section's owner approves the changes to their sections in that pull request's review: SD for the Abstract, Sections 5 to 8; SS for Sections 1 and 2 and Appendix A; CI for Sections 3 and 4 and Appendix B.

| Outcome | Findings |
|---|---|
| Fixed in 12.9 | 37: every `wording` finding but R3-6 (29), the questions R1-6, R1-8, R2-2, R3-4, R4-3 and RA-06, and the gaps R4-5 and R4-7 |
| Resolved by events, no text change | 2: R4-6 (`rubric-v1.0` tagged), RA-05 (`release-v1.0` published) |
| No change needed | 1: A-05 |
| Declined | 1: R3-6, optional; table captions would renumber the 14 tables counted in `docs/submission_pack.md` §2 |
| Still open | 4: R1-1 and R1-2 (the proposal PDF and the lecture record, which are not in the repository), R2-3 (the proposal's reason for withdrawing the player study), R2-4 (interactive-fiction literature; no citation is added without a source read) |

R2-2 was checked against the publisher's record: the first author is Vero Vanden Abeele, so the entry moved from A to V in `references.md`. No change alters a number or a claim on a slide (`docs/defence_deck.md` §3). The four open findings leave the submitted report correct as it stands; they are for SS after the blackout.

