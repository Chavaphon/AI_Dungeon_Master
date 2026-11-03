# Prompt templates v1.0

WBS 7.5 · Owner: CI · Status: **frozen 2026-11-03** · Code: `adm/orchestration/prompt.py` · Tests: `tests/orchestration/test_prompt_freeze.py`, `tests/orchestration/test_prompt.py` · CLAUDE.md wins on any conflict.

This is the freeze record of every file in `config/prompts/`. The text is the text on `main` after the ideation-form alignment (2026-11-01), which added the last preamble line; WBS 7.5 changed no wording. CLAUDE.md §9.1 gives the condition text; this document records the exact files, how the five condition templates differ line by line, and the wording that §9.1 does not hold.

## 1. What is frozen

All eleven files are frozen, not only the four condition templates of §9.1: every one of them reaches the model, and the WBS 6.2, 6.4 and 6.7 entries in `docs/decisions.md` left each one as a draft for 7.5 to freeze. The hash is `sha256` of the file's UTF-8 text with LF line endings, trailing newline included, which is the committed blob. `.gitattributes` checks the files out with LF on every platform.

`tests/orchestration/test_prompt_freeze.py` reads this table. It fails if a file in `config/prompts/` is missing from it, if a listed file is missing, or if a hash differs.

| File | Role | Placeholders | sha256 |
|---|---|---|---|
| `a.txt` | Condition A, the single narration call | `summary`, `history` | `sha256:5363432c1efcce15a2cf03200d3169da7337bb49e799cf0d387b8ce6ea539997` |
| `b.txt` | Condition B, the single narration call | `state_json`, `summary`, `history` | `sha256:74f4e08ad453a9c92c27e8d2624b7f4fcd0ddf06d8eb3355a6c2fe6d05e2ffe6` |
| `c.txt` | Condition C, the single narration call | `state_json`, `summary`, `history` | `sha256:eabd73eba3acf4596dea8f76caf63b0f81e99c622fc5f458daa1403ab4a14e48` |
| `d_toolcall.txt` | Condition D call 1, the tool call | `state_json`, `tools_json`, `summary`, `history` | `sha256:9fdff641299db28d9a20e6a7bf32e60328fc9bda4cc9042928fb5505ed895557` |
| `d_narration.txt` | Condition D call 2, the narration | `narration_facts_json`, `summary`, `history` | `sha256:ca3268f8a4d7e829612ac6911f7ae9e39ff3b3776c9cd8c8cc7930175eb3d100` |
| `summary_block.txt` | The rolling summary block, in every template above and in `summary.txt` | `summary_text` | `sha256:64c838d372d42c17afee16198f55a731f0f0aa353464c922e2ee4dcc50cd00b0` |
| `history_block.txt` | The last K turns as a transcript, in every template above and in `summary.txt` | `transcript` | `sha256:1cf84e244bbd3d617fa367eb38f2aac51cde95ab6c59fa480f0b63b9253dbe23` |
| `summary.txt` | The rolling summary call (§8.1), the same in every condition | `summary`, `history` | `sha256:81094be62cf34a3ce61e987a59784f1a101ba77d39a95692296ab3e788fc1590` |
| `retry_unparseable.txt` | D tool-call retry after an unparseable reply (§7.1) | `pc_id` | `sha256:e7f360014720370353081965ff22c3cb577666656639f310ccda0c262b03adf8` |
| `retry_rejected.txt` | D tool-call retry after a rejection, carrying the full envelope (§7.1) | `rejection_json` | `sha256:dd3d5f3cac3004820db9be72b3d56e4c994b0a4236fa089e73fc15f484943027` |
| `retry_no_tool.txt` | D tool-call re-prompt after the turn's first `{"tool": null}` (§7.1) | none | `sha256:e0494db2a54c46d37a4fc186e66245edb6ecd814c7cb5ca6ff8af17f9dda1a69` |

The placeholder sets are the ones `load_templates` checks (`TEMPLATES`, `BLOCKS` and `RETRIES` in `adm/orchestration/prompt.py`).

## 2. How the condition templates differ, line by line

Each row is one line, or one fixed block of lines, of the union of the five condition templates. The cells give its line numbers in that file; "—" means the file does not hold it. Blank separator lines are left out: every paragraph is separated from the next by exactly one blank line.

| Row | Text | A `a` | B `b` | C `c` | D `d_toolcall` | D `d_narration` |
|---|---|---|---|---|---|---|
| 1 | Preamble: "You are the Dungeon Master for a text-based fantasy role-playing game." | 1 | 1 | 1 | 1 | 1 |
| 2 | Preamble: "Narrate in the second person, present tense. Keep each reply to 2-4 sentences." | 2 | 2 | 2 | 2 | 2 |
| 3 | Preamble: "Describe only what the player character could perceive." | 3 | 3 | 3 | 3 | 3 |
| 4 | Preamble: "Do not speak or act for the player character." | 4 | 4 | 4 | 4 | 4 |
| 5 | Preamble: "Do not use headings, lists, or dice notation in narration." | 5 | 5 | 5 | 5 | 5 |
| 6 | Preamble: "Keep violence non-graphic and suitable for players aged 8 and up." | 6 | 6 | 6 | 6 | 6 |
| 7 | State lead-in: "The authoritative game state is given below as JSON. It is correct." / "Your narration must be consistent with it." | — | 8–9 | 8–9 | 8–9 | — |
| 8 | State block: `<state>` / `{state_json}` / `</state>` | — | 11–13 | 11–13 | 11–13 | — |
| 9 | Tools lead-in: "The tools you can call are defined below as JSON." | — | — | — | 15 | — |
| 10 | Tools block: `<tools>` / `{tools_json}` / `</tools>` | — | — | — | 17–19 | — |
| 11 | `{summary}` paragraph | 8 | 15 | 15 | 21 | 8 |
| 12 | `{history}` paragraph | 10 | 17 | 17 | 23 | 10 |
| 13 | Self-check: "Before you reply, check your narration against the state above:" … "Revise silently, then give only the final narration." (4 lines) | — | — | 19–22 | — | — |
| 14 | Tool-call instruction: "Decide the single game action that the player's input represents." … `with exactly: {"tool": null}` (5 lines) | — | — | — | 25–29 | — |
| 15 | Facts lead-in: "The rules engine has resolved the action. These facts are authoritative" … "listed, and do not contradict any value here." (3 lines) | — | — | — | — | 12–14 |
| 16 | Facts block: `<facts>` / `{narration_facts_json}` / `</facts>` | — | — | — | — | 16–18 |
| | **Lines in file** | 10 | 17 | 22 | 29 | 18 |

The differences, pairwise. Each is checked by a test.

| From | To | Difference | Test |
|---|---|---|---|
| A | B | B inserts rows 7–8, the state lead-in and block, between the preamble and the summary. Nothing else. | `test_b_is_a_plus_the_state_block` |
| B | C | C appends row 13, the self-check, after the history. Nothing else. | `test_b_and_c_differ_only_by_the_self_check` (`test_prompt.py`) |
| B | D tool call | D inserts rows 9–10, the tools lead-in and block, after the state block, and appends row 14, the tool-call instruction, after the history. Nothing else. | `test_d_toolcall_is_b_plus_tools_and_instruction` |
| A | D narration | D narration appends rows 15–16, the facts lead-in and block, after the history. It holds no state and no tools. | `test_d_narration_is_a_plus_the_facts_block` |

So rows 1–6, 11 and 12 are identical in all five, and the condition-specific text is always last, closest to the player's input (decision 2 of the WBS 6.2 entry). The summary and history paragraphs come from the same two block files in every template, so a turn with the same summary and history gives them byte for byte in every condition (`test_conditions_share_summary_and_history_byte_for_byte`).

## 3. Wording not given in CLAUDE.md §9.1

§9.1 gives the preamble, the state block, the self-check, the tool-call instruction and the facts block, and those are verbatim (`tests/orchestration/test_prompt.py`). The rest was fixed by earlier tasks and is frozen here unchanged.

| Text | Where | Fixed by |
|---|---|---|
| Preamble line 6, the non-graphic violence line | All five, row 6 | Ideation-form alignment, 2026-11-01 (decision 43). §9.1 holds it. |
| "The tools you can call are defined below as JSON." and the `<tools>` tags | `d_toolcall.txt`, rows 9–10 | WBS 3.3 draft heading, kept at 6.2; the block's content is `docs/tool_contract.md` §5 |
| The `{summary}` and `{history}` paragraphs, and their place after the fixed blocks | All five, rows 11–12 | WBS 6.2, decisions 2 and 3 |
| `summary_block.txt`, `history_block.txt` | Shared blocks | WBS 3.5 drafts, adopted at 6.2 |
| `summary.txt` | Rolling summary call | WBS 6.7, decision 3 |
| `retry_unparseable.txt`, `retry_rejected.txt`, `retry_no_tool.txt` | Tool-call retries | WBS 6.4, decision 3 |

## 4. From template to prompt bytes

The prompt is built by `assemble` in `adm/orchestration/prompt.py`; its module docstring and CLAUDE.md §8 are the reference. Four rules decide the bytes and are frozen with the text:

1. A file is read as UTF-8 in universal-newline mode, and one trailing newline is removed.
2. Placeholders are replaced with `str.replace`, since the tool-call instruction holds literal braces.
3. A `{summary}` or `{history}` paragraph with nothing to put in it is dropped with its separator, so an empty block leaves no blank gap.
4. The template fills the system message; the player's input is the user message. A retry appends the earlier replies as `assistant` messages and each `retry_*` text as a `user` message.

## 5. Changing a frozen template

A change to any file in §1 needs a `docs/decisions.md` entry that says why and which runs it makes incomparable, and, in the same pull request, the new hash in §1. The freeze test fails until both files agree. A change to one condition's template that is not mirrored in the others breaks invariant 7, unless it is in that condition's own rows (7–10 and 13–16).

Two earlier prompts are deliberately not the frozen text:

- The ten WBS 6.11 smoke runs used the preamble without line 6. They remain the gate G2 evidence and are not compared with main-grid runs (ideation-form entry, 2026-11-01).
- `adm/bench/toolcall.py` keeps the Week 2 draft of `d_toolcall.txt`, so the 3.3–3.7 benchmark stays reproducible. Nothing in a run uses it.
