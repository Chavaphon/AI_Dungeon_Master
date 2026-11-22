# Defence deck, in talk order

WBS 11.7 · Owner: CI · Built 2026-11-19 · Slide 8 replaced 2026-11-21 (WBS 11.9) · Slide 5 replaced 2026-11-21 (WBS 11.8) · CLAUDE.md wins on any conflict.

The deck for the defence on 2 December (deliverable D11). Done when: "Problem, difficulty, design (framed via SPECIFY / HARNESS / VERIFY / CONTROL), build, evaluation, risks" (TASK_CHECKLIST.md, 11.7). The talk follows that order, not the proposal's, and ends with the live demo.

**File:** `docs/defence/deck.pptx`, 16:9, 15 main slides and 5 backup slides, speaker notes on every slide. From here on it is edited in PowerPoint; 11.8 has replaced slide 5 and 11.9 slide 8 (§4).

## 1. The talk

- **Length:** 15 minutes, then questions. The timings in the speaker notes add up to 14:40, which leaves 20 seconds of slack.
- **The question the talk carries:** *can a correct game state keep an AI narrator honest?* It opens on a real divergence in The Cellar Rats (`s01_cellar`) and closes by playing that same scenario live, so the demo answers the opening slide.
- **How the slides connect:** each content slide has a question above its title (the kicker) and a claim as its title. The kicker is the question the previous slide left open. The last line of each slide's speaker notes, marked `Bridge:`, is the sentence that asks it aloud. Read in order, the titles and bridges form one argument (§2).
- **Where the talk is:** a tracker at the foot of every main slide (Problem, Difficulty, Design, Build, Evaluation, Risks, Takeaway, Demo) highlights the current part.
- **Look:** the palette and fonts of the 15 November progress update (Bookman Old Style headings, Calibri body, Courier New for transcripts and commands). Teal marks the model and orange the engine, throughout.

## 2. Slide order

| # | Part | Kicker (question) | Title (claim) | Time | Bridge to the next slide |
|---|---|---|---|---|---|
| 1 | Opening | — | AI Dungeon Master: *Can a correct game state keep an AI narrator honest?* | 0:20 | "Let me start with what goes wrong when an AI runs the game on its own." |
| 2 | Problem | What goes wrong when an AI runs the game? | AI narrators describe things the game never had | 0:50 | "Why not just tell the model the state?" |
| 3 | Difficulty | Why not just give the model the state? | Three things make this hard | 0:50 | "So the first decision was to take the state away from the model completely." |
| 4 | Design | So who should own the state? | One rule: the model proposes, the engine decides | 0:50 | "How does one turn actually run under that rule?" |
| 5 | Design | How does one turn run under that rule? | Every turn is a loop with two model calls | 1:00 | "Here is the discipline behind them." |
| 6 | Design | Why does each piece exist? | Four design decisions, one discipline each | 1:15 | "Did we build it correctly?" |
| 7 | Build | Did we build it correctly? | The engine is tested, not trusted | 0:50 | "Does that keep the story honest? Here is how we tested it." |
| 8 | Evaluation | Does a correct state keep the story honest? | Four levels of grounding, everything else fixed | 1:00 | "Did it?" |
| 9 | Evaluation | Did D halve the divergences, as we predicted? | No: D diverges as often as the model alone | 1:00 | "What does that look like, turn by turn?" |
| 10 | Evaluation | What does that look like, turn by turn? | The engine fixes the mechanics, not the words | 1:20 | "That split runs through every other metric." |
| 11 | Evaluation | Is it the same story on every other metric? | The state is perfect; the narration is not | 1:00 | "How far can you trust these numbers?" |
| 12 | Risks | How far can you trust these numbers? | What limits every claim here | 1:00 | "Here is what we take away." |
| 13 | Takeaway | So what do we take away? | A correct state is necessary, but not sufficient | 0:40 | "Let us show you the system, in the same cellar we started with." |
| 14 | Demo | Let's see it: the same cellar, live | The Cellar Rats, condition D | 2:45 | "Thank you; we are happy to take questions." |
| 15 | — | Thank you | Questions? | — | — |
| B1 | Backup | RQ2 | Divergence does not grow over a session | — | |
| B2 | Backup | Error taxonomy | PHANTOM and CONTRADICT are nearly all of it | — | |
| B3 | Backup | Ten illustrative failures | Drawn by rule, not picked | — | |
| B4 | Backup | The framing against the evidence | Each discipline held, and showed where it stops | — | |
| B5 | Backup | Reproducibility | Every number replays from a seed and a manifest | — | |

## 3. Where every number comes from

No slide computes anything. Every figure is copied from the report's Results (`docs/report/05_results.md`) or the record it cites, and the three figures are the committed PNGs in `docs/report/figures/`.

| Slide | Value on the slide | Source |
|---|---|---|
| 1 | 192 runs, 6,420 turn records | `docs/run_integrity.md`; report §4 |
| 2 | Condition A turns: the lantern and the ledger | `runs/dry_run/A/s01_cellar/3001.jsonl` (seed 3001, not a main-grid run), as quoted in the progress update; inventory and quest from `scenarios/s01_cellar.json` |
| 4 | 7 tools, 19 rejection codes | CLAUDE.md §6.1, §6.3 |
| 5 | Two calls, temperatures 0.0 and 0.7, retry budget 2, K = 8; the failure, no-tool, read and write paths | CLAUDE.md §2.2, §7, §7.1, §8; `docs/architecture_diagram.md` §1 |
| 6 | The four decisions | report §3.9, Table |
| 7 | 60 of 60 rule-suite cases | `docs/rule_suite.md` |
| 7 | Every rejection code reached by a test; parser tested on recorded malformed output | CLAUDE.md §13 |
| 7 | 0 state rule breaks in 6,366 narrated turns | report §5.6, Table 5.9 |
| 7 | 192 runs, 6,420 records, all valid, checksummed | `docs/run_integrity.md` |
| 8 | Conditions A to D, as the grid's columns | CLAUDE.md §9 |
| 8 | 48 runs per condition, 192 runs, 6,420 turn records | CLAUDE.md §10.5; `docs/run_integrity.md` |
| 8 | M1 narrated turns: A, B, C 535, D 519 (16 runs each) | report Table 5.2 |
| 8 | M2: D 1,605 turns | report Table 5.7 |
| 8 | M3: D 242 sampled turns (15%) | report Table 5.8 |
| 8 | M4 narrated turns: A, B, C 1,605, D 1,551 | report Table 5.9 (automated, all 192 runs) |
| 8 | M5: 16 excerpts per condition | report §5.7; `docs/m5_scores.md` |
| 8 | M6 turns: 1,605 per condition | report Table 5.10 |
| 8 | H1 | CLAUDE.md §10.5 |
| 9 | A 55.9, D 57.4, D/A 1.03 (0.74 to 1.48); C 44.5, C/A 0.80; D/A without `PHANTOM` 1.20 | report Tables 5.2 and 5.3; Figure 5.1 |
| 10 | The two A-versus-D rows and the measured line | `docs/exhibit_a_vs_d.md` §2; Figure 5.4, with the figure's own heading cropped off (the slide title replaces it) |
| 11 | 86.6% recovered, 25.0% of turns rejected | report Table 5.7 |
| 11 | p95 7.89 s (interval to 7.98 s) | report Table 5.10 |
| 11 | 9.0 narrated rule breaks per 100 turns (8.99) | report Table 5.9 |
| 11 | 70.2% faithful calls | report Table 5.8 |
| 11 | No growth (RQ2); H2 not contradicted, vividness on the boundary | report §5.2, §5.7 |
| 12 | M1 alpha 0.894 between two reviewed drafts; M5 alpha −0.27 to −0.01 | report §5.8, Tables 5.13 and 5.14 |
| 12 | 268 of 573 rejected attempts `ENCOUNTER_OVER` | report §5.4 |
| 13 | Takeaway and next steps | report §6.2, §6.3, §8.1 (draft, PR #240) |
| 14 | Demo inputs, seed and fallback | `docs/live_demo.md` §2–§4 |
| B1 | Slopes per condition and D − A | report Table 5.4; Figure 5.2 |
| B2 | Category rates; 92% to 97% | report Table 5.5; Figure 5.3 |
| B3 | Ten failures | report Table 5.6; `docs/failure_catalogue.md` |
| B4 | The framing revisited | report §6.3 (draft, PR #240) |

**Disclosures carried on the slides.** Slide 9 states that the M1 labels are an AI draft accepted by one annotator, and slide 12 states that the M1 alpha is between two reviewed AI drafts and that M5 did not reach agreement. Slide 2 and slide 10 say that their examples are examples, not results; slide 10 carries the measured D/A line under its two rows, as `docs/exhibit_a_vs_d.md` §3.3 asks.

**If the report changes.** Slides 13 and B4 paraphrase the draft discussion in PR #240 (WBS 11.4), which was not merged when the deck was built. If 11.4 or the 11.6 review changes a figure or a claim, the matching row above names the slide to update.

## 4. Slots for the follow-on tasks

| Slide | Now | Replaced by |
|---|---|---|
| 5 | **Done in 11.8** (SS, 2026-11-21): the loop-corrected architecture diagram, `docs/report/figures/fig_turn_loop.svg`, the same file as report Figure 3.1. It adds the failed-turn path to the audit log, the no-tool path, and the state with its one writer (`docs/architecture_diagram.md` §2). Title, kicker, caption line and colours unchanged; the speaker notes walk the new paths. | — |
| 8 | **Done in 11.9** (CI, 2026-11-21): one grid, the four conditions as columns and the six metrics as rows, each cell the sample that metric was measured on in that condition; D's column is orange, M1's row is tinted as the headline, and a merged grey cell marks M2 and M3 as D-only. Below it, the shared design (48 runs per condition) and H1. Kicker and title unchanged. | — |

11.10 (two timed rehearsals) checks the 15 minutes against a stopwatch and prepares answers to the top ten questions. The questions and answers are in `docs/defence_questions.md`, with "Did you pick these?" (slide 10's notes) among the reserves; the rehearsal timings are kept by the team outside the repository.

## 5. The demo, at the end

The demo is the last part of the talk, after the takeaway, so that the talk's argument is complete before anything can go wrong on stage. It plays the scenario of slide 2.

- **Before the audience arrives:** `docs/live_demo.md` §2 in full: GPU freed, the pinned Ollama 0.35.1 serving, the version and digest checked, a warm-up run, fresh seeds written down, and the fallback run recorded.
- **On the slide:** what to watch (the engine's result line, the result line against the narration, a refused Fireball) and the command, with seed 9101.
- **In the notes:** the input script of `docs/live_demo.md` §3, cut to six inputs to fit 2:45, and what to avoid.
- **If it fails:** switch to the fallback run recorded in §2 step 9. It keeps the talk inside 15 minutes.

## 6. Files

| File | sha256 |
|---|---|
| `docs/defence/deck.pptx` | `e5e4e1a264dee9000ecbdaec4e1dc8e3736cc460d63b881b79e435e312a1cc4a` |

The deck was generated with pptxgenjs and checked by rendering every slide in PowerPoint. It is not regenerated from code: later changes are made in PowerPoint, and this hash is updated with them. The one exception is 11.9: no PowerPoint edits had been made yet, so slide 8 was replaced by rebuilding from the 11.7 build script with only slide 8's block changed. The text, shapes and speaker notes of the other 19 slides were compared against the 11.7 deck and are identical, and slide 8 was rendered in PowerPoint and inspected.

11.8 is the first PowerPoint edit. On slide 5 the draft diagram's 21 shapes were deleted, the SVG was inserted in their place (820 pt wide, with alt text), the caption line was moved below it, and the speaker notes were rewritten; the slide was then rendered and inspected. Saving from PowerPoint re-serialises the file, so the other 19 slides were compared against the 11.9 deck: their text and speaker notes are identical apart from XML escaping (`&apos;` written as `'`), and slide 8, whose merged cells gained empty paragraphs, was rendered and looks unchanged.

12.9 (2026-11-22) removed "or the demo video (WBS 12.12)" from the end of slide 14's speaker notes, which now end "…switch to the recorded fallback run (live_demo.md §2 step 9)." (`docs/defence_questions.md` §4). The edit was made in `ppt/notesSlides/notesSlide14.xml` with Python's `zipfile`, not in PowerPoint, so nothing was re-serialised: every other member of the file is byte-identical to the 11.8 deck, in the same order and with the same compression. Speaker notes are not shown on the slide, so nothing visible changed. The deck's 11.8 sha256 was `e1d6afbf…642889`.
