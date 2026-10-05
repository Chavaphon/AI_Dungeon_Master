# Context budget and the choice of K

WBS 3.5 · Owner: CI · Run 2026-10-05 · CLAUDE.md wins on any conflict.

K is the number of past turns kept verbatim in the prompt (CLAUDE.md §8). This document measures how many turns fit in the 8192-token context and whether the model still calls tools correctly with them present. It sets the rule for choosing K before reading the numbers, then applies it. **Result: K = 8, and the history must be sent as a transcript block, not as chat turns (§5).** WBS 3.6 (#38) freezes K into `config/model.json`.

## 1. Setup

| Item | Value |
|---|---|
| Machine | `docs/hardware.md` §1 (RTX 5060 Laptop, 8151 MiB) |
| Ollama | 0.35.1 |
| GPU before the runs | **0 MiB used**, no other GPU processes (`nvidia-smi`) |
| Models | `qwen3.5:9b` 6488c96fa5fa, `granite4.2:8b` f586c02fdecd, `llama3.1:8b` 46e0c10c039e, the same digests as in 3.4 |
| GPU share when loaded | Qwen 88%, Granite 92%, Llama 100% |
| Tool | `python -m adm.bench.context` (`adm/bench/context.py`) |
| Options | As in 3.4 (`docs/model_benchmark.md` §1). Token counting uses `num_predict 1`. Narration uses temperature 0.7 and `num_predict 300` (§2.2). |

The GPU was empty this time, and Qwen and Granite still loaded at 88% and 92%. So the split seen in 3.4 is a property of these two models on this 8 GB card, not of other applications holding memory. Their latency figures understate what they would do fully on the GPU. Token counts and accuracy are unaffected.

### 1.1 What a turn is

A verbatim turn is **the player's input and the DM's narration**. Invariant 7 requires the same context strategy in every condition, and conditions A–C have no tool calls to keep, so tool calls and results are not part of the history. The current state is injected separately (§8, item 3).

### 1.2 Fixtures

- **`adm/bench/context_ceiling_state.json`** is a worst-case state: 1 PC, 6 hostiles (4 giant rats and 2 smugglers, one a caster), 3 NPC relationships with history, 12 item definitions, 4 quests (one in each state), and an active encounter. It is 9.2 KB of pretty-printed JSON, about three times the 3.3 example states. A test validates it against the schema and the cross-field rules.
- **`adm/bench/context_history.json`** holds:
  - 32 hand-written turns in the s01 cellar world, 2–4 sentences each, with no digits;
  - a rolling summary of about 205 tokens, in the §8.1 style with no numeric state;
  - 8 narration probes, one per successful result example.

### 1.3 Runs

| Run | What | Folder in `results/bench/context/` |
|---|---|---|
| 1 | All three phases, history as chat turns, prompt mode | `20261005T052846Z` |
| 2 | Qwen, accuracy, chat turns, JSON mode, K = 0 and 8 | `20261005T053742Z` |
| 3 | Tokens and accuracy, history as a transcript, prompt mode | `20261005T054107Z` |
| 4 | Qwen, tokens and accuracy, transcript, JSON mode | `20261005T054529Z` |

Runs 3 and 4 were added after run 1 showed the chat-turn collapse (§5). No request failed in any run.

## 2. The rule for choosing K (fixed before the runs)

1. **K_fit** is the largest K that satisfies `worst prefix + K × worst turn + 200-token reply ≤ 8192` for **every** candidate's tokeniser. The model is not frozen yet, so K must suit all three.
   - **Worst prefix** is the D tool-call prompt with the ceiling state, a summary budgeted at its 200-token cap, the longest player input, and any fixed history heading.
   - **Worst turn** is the per-turn template, plus the longest input, plus a narration at its 300-token cap.

   Sizing against the caps means the per-turn reduction in §8 never fires for a scenario within the ceiling.
2. **Chosen K** is the largest K ≤ K_fit at which no model's schema-valid or tool-match rate falls more than 1 case in 20 below its own K = 0 rate.
3. If the chosen K is below 8, risk R3 is triggered.

The D tool-call prompt is the largest prompt in any condition. It is the only one with the state *and* the tools. Condition C, the largest narration-only prompt, is 1200–1500 tokens smaller (§3).

## 3. Token budget

Transcript format (runs 3 and 4), which is the format §5 recommends.

| Model | Base prefix | Summary | Longest input | History heading | Per-turn template | Typical turn | Worst prefix | Worst turn | **K_fit** | K_fit, typical turns | K_fit, condition C |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `qwen3.5:9b` | 4840 | 205 | 23 | 20 | 6 | 73.7 | 5082 | 329 | **8** | 39 | 12 |
| `granite4.2:8b` | 5045 | 207 | 23 | 21 | 7 | 74.8 | 5288 | 330 | **8** | 36 | 12 |
| `llama3.1:8b` | 4205 | 201 | 23 | 17 | 4 | 71.8 | 4444 | 327 | **10** | 49 | 14 |

- **Base prefix** is preamble, ceiling state and tools, with a one-token input. The ceiling state alone adds about 2400 tokens over the 3.4 example states.
- **Typical turn** is the slope of prompt tokens against K over the 32 fixture turns. Prompt tokens rose steadily all the way to K = 32 (Granite peaked at 7674), so **no prompt was truncated**.
- **K_fit, typical turns** shows how much room is left when narrations are as long as they really are (§4), not at their cap.
- With history as chat turns (run 1), the per-turn template costs 10–12 tokens instead of 4–7, and the K_fit values are the same: 8, 8 and 10.

At K = 8, Granite's worst-case tool-call prompt is 5288 + 8 × 330 = 7928 tokens. With the 200-token reply that is 8128, inside 8192 with 64 to spare.

## 4. Narration length

The draft `d_narration` prompt was given each of the 8 result examples, with 5 seeds at temperature 0.7, so n = 40 per model.

| Model | Mean | p95 | Max | Hit the 300 cap |
|---|---|---|---|---|
| `qwen3.5:9b` | 65 | 81 | 92 | 0 |
| `granite4.2:8b` | 67 | 92 | 104 | 0 |
| `llama3.1:8b` | 64 | 84 | 89 | 0 |

Real narrations are about a third of the cap, and none reached it. Budgeting every turn at 300 tokens is therefore very conservative: in a typical session, a K = 8 prompt uses about 5900 of the 8192 tokens. The rule keeps the cap anyway, so that a long narration can never push a prompt over the limit.

## 5. Accuracy against K: the history format matters more than its length

### 5.1 History as chat turns: collapse

In run 1, each past turn was sent as a `user` message followed by an `assistant` message, the usual chat layout.

| Model | K = 0 valid / tool | K = 8 valid / tool | K = 16 valid / tool |
|---|---|---|---|
| `qwen3.5:9b` | 20% / 20% | 0% / 0% | 0% / 0% |
| `granite4.2:8b` | 90% / 90% | 5% / 15% | 0% / 5% |
| `llama3.1:8b` | 100% / 80% | 0% / 0% | 0% / 0% |
| `qwen3.5:9b`, JSON mode (run 2) | 100% / 95% | 100% / 85% | — |

With any history at all, all three models stop calling tools and write narration. For example, Llama at K = 8 answers tc01 ("I hum a tune") with "The sound of your humming hangs in the air…". The previous `assistant` messages are all narration, and the models continue that pattern instead of following the JSON instruction in the system prompt. JSON mode forces Qwen's reply to be JSON, but it still loses 2 cases of tool match. The prompts were nowhere near the context limit (3200–4300 tokens), so this is a formatting problem, not a capacity one.

### 5.2 History as a transcript: stable

In runs 3 and 4, the same turns are written into the system prompt as a block after the summary, and the only messages are the system prompt and the current input:

```
The most recent turns of the game, oldest first:

<history>
Player: <input>
DM: <narration>

Player: ...
</history>
```

| Model | K | Schema-valid | Tool match | Args match | Mean s | p95 s |
|---|---|---|---|---|---|---|
| `qwen3.5:9b` | 0 | 25% | 25% | 25% | 1.30 | 1.73 |
| | 8 | 20% | 20% | 20% | 1.60 | 2.27 |
| | 16 | 15% | 15% | 15% | 1.77 | 2.73 |
| `qwen3.5:9b`, JSON | 0 | 100% | 95% | 95% | 1.29 | 2.62 |
| | 8 | 100% | 90% | 90% | 1.20 | 1.87 |
| | 16 | 100% | 95% | 95% | 1.26 | 2.26 |
| `granite4.2:8b` | 0 | 85% | 90% | 85% | 1.16 | 2.81 |
| | 8 | 95% | 85% | 80% | 1.13 | 2.07 |
| | 16 | 95% | 85% | 80% | 1.20 | 2.30 |
| `llama3.1:8b` | 0 | 100% | 80% | 80% | 0.66 | 1.75 |
| | 8 | 100% | 75% | 75% | 0.56 | 1.26 |
| | 10 | 100% | 75% | 75% | 0.56 | 1.21 |
| | 16 | 100% | 75% | 75% | 0.60 | 1.45 |

Every model in every mode stays within 1 case of its K = 0 rates up to K = 16. Latency barely moves with K, because prompt evaluation is fast next to generation.

**Which cases change.** tc03 ("I put my shoulder to the stuck cellar door…") is lost by every model once history is present. Granite and Llama call `attack` on a rat instead. tc03's state is the calm exploration example, but the history fixture ends in the middle of a fight with rats and smugglers, so the models act on the history. This is a contradiction between the fixture and that case's state, not a context limit. In real play, history and state agree. The other changes are single cases that move in both directions: for Llama, tc07 is lost and tc11 is gained.

## 6. Decision

| | Qwen | Granite | Llama |
|---|---|---|---|
| K_fit (worst case) | 8 | 8 | 10 |
| Largest stable K ≤ K_fit (transcript) | 8 | 8 | 10 |
| Largest stable K ≤ K_fit (chat turns) | 0 | 0 | 0 |

**K = 8**, the smallest K_fit across the three tokenisers. It holds whichever model 3.6 freezes, and it equals the CLAUDE.md §2.2 placeholder. Risk R3 is not triggered.

This choice depends on two conditions:

1. **The history is sent as a transcript block in the system prompt, never as `assistant` chat turns.** The exact heading and block wording are drafts for 6.2 (#58) to settle and 7.5 to freeze. Under invariant 7, the same format is used in every condition's calls, including A–C and the D narration call.
2. **Scenario states stay within the ceiling** in §1.2 (1 PC, 6 combatant NPCs, 3 relationships, 12 items, 4 quests, short display names and justifications). A larger state makes the worst-case prompt exceed 8192 at K = 8, and then the per-turn reduction in §8 applies and is logged. Scenario authors (8.3 onward) should treat the ceiling as a limit.

## 7. For the next tasks

- **3.6 (#38):** freeze `K_verbatim_turns: 8`. **Repeatability:** the same K = 0 request gave different replies in run 1 and run 3 for Llama on tc16 (`{"tool": null}`, then a perception check) and for Granite on tc16 (`null`, then `"null"`). Qwen differed on 5 cases, as in 3.4. In 3.4, Llama and Granite were identical across 3 repeats within one run. Across separate runs they are not, and the cause is not established. Invariant 4 needs a byte-identical replay, so 3.6 should test repeat runs of the frozen model in separate processes.
- **3.7 (#39):** JSON mode made Qwen robust in both history formats (100% schema-valid at every K).
- **6.2 (#58):** use the transcript format (§5.2). If prompts are assembled with chat turns, condition D collapses.
- **8.3:** keep scenario states within the ceiling (§6).

## 8. Raw data

`results/` is gitignored. All four run folders hold `summary.json` and per-model jsonl files with every request and raw reply. They go in the team Drive folder under `bench/context/`, next to `bench/toolcall/`.
