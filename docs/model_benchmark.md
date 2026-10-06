# Tool-call benchmark results

WBS 3.4 · Owner: CI · Run 2026-10-04 · CLAUDE.md wins on any conflict.

The three shortlisted models (`docs/model_shortlist.md`) were run through the 20-case tool-call micro-benchmark (WBS 3.3, `adm/bench/`). This document records the comparison table and what it shows. It does **not** choose a model. The freeze is WBS 3.6 (#38), after K is chosen in 3.5 (#36). Whether to use Ollama's JSON mode is WBS 3.7 (#39).

## 1. Setup

| Item | Value |
|---|---|
| Machine | `docs/hardware.md` §1 (RTX 5060 Laptop, 8151 MiB) |
| Ollama | **0.35.1** (hardware.md records 0.35.0, the version installed at WBS 3.1) |
| Free VRAM before the runs | 7404 MiB (492 MiB held by desktop applications) |
| Cases | 20 (`adm/bench/toolcall_cases.json`), covering all seven tools and `{"tool": null}` |
| Prompt | Draft `d_toolcall` prompt, as described in the 2026-10-04 WBS 3.3 entry in `docs/decisions.md` |
| Options on every request | `num_ctx 8192`, `num_predict 200`, `temperature 0.0`, `top_p 1.0`, `top_k 0`, `min_p 0.0`, `seed 0`, `repeat_penalty 1.0`, `presence_penalty 0.0`, `frequency_penalty 0.0` |
| `think: false` sent to | `qwen3.5:9b`, `granite4.2:8b` (they list the `thinking` capability). Not sent to `llama3.1:8b` |
| Prompt-mode run | 3 repeats, so n = 60 per model · `results/bench/toolcall/20261004T095239Z/` |
| JSON-mode run | `--format json`, 1 repeat, so n = 20 per model · `results/bench/toolcall/20261004T095558Z/` |

The command for the prompt-mode run:

```bash
python -m adm.bench.toolcall --model qwen3.5:9b --model granite4.2:8b --model llama3.1:8b --repeats 3
```

The JSON-mode run is the same command with `--format json` instead of `--repeats 3`.

Model digests (`ollama list`) match the shortlist §1 exactly: `qwen3.5:9b` 6488c96fa5fa, `granite4.2:8b` f586c02fdecd, `llama3.1:8b` 46e0c10c039e.

No request failed in either run (0 errors in all 240).

## 2. Comparison table (prompt mode, the R1 figure)

| Model | n | Schema-valid | Lenient | Tool match | Args match | Mean s | p95 s | tok/s | Prompt tokens | GPU share |
|---|---|---|---|---|---|---|---|---|---|---|
| `qwen3.5:9b` | 60 | **23%** | 23% | 23% | 23% | 1.35 | 1.73 | 46.4 | 2792 | 88%* |
| `granite4.2:8b` | 60 | **85%** | 85% | 90% | 85% | 1.02 | 1.56 | 40.5 | 2898 | 92%* |
| `llama3.1:8b` | 60 | **100%** | 100% | 80% | 80% | 0.57 | 0.89 | 63.4 | 2420 | 100% |

- **Schema-valid** is the primary score: the raw reply parsed unchanged as one JSON object and validated against `proposed_call`. **Lenient** is the same check after stripping code fences and prose. **Tool** and **Args** are whether the reply names the expected tool and arguments; a skill check's `dc` and a relationship change's `justification` are not compared.
- **Latency** is wall-clock seconds per tool-call request with the model already loaded; it covers the tool-call phase only, not narration. **tok/s** is generation speed (`eval_count / eval_duration`). Prompt tokens differ between models only because their tokenisers differ; every model got the same prompt.
- \* **Qwen and Granite were not fully on the GPU.** Even with 7404 MiB free, Ollama placed 88% and 92% of them on the GPU, the same split the shortlist fit check saw with less memory free (shortlist §3). So the expectation in shortlist §3, that they would load at 100% once other applications were closed, does not hold on this machine. **Their latency and tok/s understate what they would do fully on the GPU**, so read their M6 figures with that in mind. Schema-valid and match rates are unaffected.

## 3. JSON mode (input to 3.7, no decision taken)

The same cases, with Ollama's `format: "json"` field set.

| Model | n | Schema-valid | Lenient | Tool match | Args match | Mean s | p95 s | tok/s | GPU share |
|---|---|---|---|---|---|---|---|---|---|
| `qwen3.5:9b` | 20 | **100%** | 100% | 95% | 95% | 1.29 | 2.61 | 45.7 | 88% |
| `granite4.2:8b` | 20 | **85%** | 85% | 90% | 85% | 1.14 | 2.80 | 40.4 | 92% |
| `llama3.1:8b` | 20 | **100%** | 100% | 80% | 80% | 0.64 | 1.70 | 63.8 | 100% |

JSON mode turns Qwen from the worst candidate into the most accurate one. It changes nothing for Granite and Llama: their replies are the same as in prompt mode. The p95 figures here come from 20 samples, not 60, so they are noisier than the prompt-mode ones.

## 4. What fails, per model

Failures are the same in every repeat unless §5 says otherwise.

**`qwen3.5:9b`, prompt mode: it narrates instead of calling a tool.** In 15 or 16 of the 20 cases per repeat, Qwen ignores the JSON instruction and writes a narration reply in the second person. For example, tc08 "I attack the second rat with my short sword" gets "You swing your short sword at the second giant rat, the steel glinting in the torchlight…". The prompt's shared preamble ("Narrate in the second person, present tense…") comes before the JSON instruction, and Qwen follows the preamble. The only cases it always answers with valid JSON are tc06, tc07, tc18 and tc20. With JSON mode on, its single miss is tc16 (quest advance), where it calls `skill_check` (perception).

**`granite4.2:8b`: right idea, wrong shape (3 cases).**
- tc06 (apologise to the Keeper) and tc16 (spot a quest clue): it replies `{"tool": "null"}`. That is the string `"null"`, not JSON `null`, and has no `arguments`. It is a schema error, and also the wrong decision, since both cases expect a tool.
- tc15 (dodge, phrased indirectly): it replies `{"tool": "dodge"}`, the right tool but with `arguments` missing. It is a schema error.

**`llama3.1:8b`: always valid, sometimes the wrong action (4 cases).** These are the cases the validator cannot catch (CLAUDE.md §7.2). They would show up only in M3.
- tc06 (apologise to the Keeper) and tc19 (swear an oath to the Keeper): `{"tool": null}`, so the relationship change is dropped.
- tc11 (hurl a bolt of fire at the wounded rat): `attack` with the short sword instead of `cast_spell` with `spell_fire_bolt`.
- tc16 (spot a quest clue): `skill_check` (perception) instead of `update_quest` (advance).

**Common to all three:** tc16, the quest advance, is missed by every model in both modes. Relationship changes (tc06, tc19) are the next weakest.

**Lenient equals strict for every model.** No reply was wrapped in a code fence or in prose around valid JSON. A recovering parser (WBS 6.3) gains nothing on this set. The failures are either no JSON at all (Qwen) or JSON with the wrong content (Granite).

## 5. Repeatability

Temperature 0 and a fixed seed should give byte-identical replies on every repeat.

- `granite4.2:8b` and `llama3.1:8b`: **identical** in all 20 cases across the 3 repeats.
- `qwen3.5:9b`: **not identical.** In 5 cases (tc01, tc02, tc03, tc08, tc09), repeat 0 differs from repeats 1 and 2, which match each other. In tc03 this also flips validity: prose in repeat 0, a valid call in repeats 1 and 2. That is why its per-repeat schema-valid rates are 20%, 25% and 25%. The cause is not established. Two possibilities are its CPU/GPU split, and different caching state on the first request after the untimed warm-up.

This matters for 3.6. Invariant 4 needs a byte-identical replay, and that holds only if the frozen model answers repeat requests identically. If Qwen is a candidate at 3.6, its repeatability should be re-checked with JSON mode on.

## 6. Risk R1

R1's trigger is a schema-valid rate below 80% at task 3.4 (`TASK_CHECKLIST.md` risk register).

| Model | Prompt mode | JSON mode | R1 |
|---|---|---|---|
| `qwen3.5:9b` | 23% | 100% | **Triggered in prompt mode.** Clears with JSON mode. |
| `granite4.2:8b` | 85% | 85% | Clear. |
| `llama3.1:8b` | 100% | 100% | Clear. |

R1 is triggered only for Qwen without JSON mode. Two candidates clear the 80% line without mitigation, so condition D is viable. Schema-valid is not the same as correct: Llama's tool-match rate is 80%, and its misses are valid calls for the wrong action (§4).

## 7. Malformed outputs for the parser tests

CLAUDE.md §13 asks for at least 20 malformed model outputs recorded during Week 2, for the parser tests (WBS 6.3). The prompt-mode run has **22 distinct schema-invalid replies**: 20 from Qwen (all prose narration, no JSON) and 2 from Granite (`{"tool": "null"}` and `{"tool": "dodge"}`). They are in the jsonl files of the prompt-mode run, where `schema_valid` is false.

That meets the count but not the variety. The set has no fenced JSON, no truncated JSON and no JSON with trailing prose. 6.3 should add such cases by hand, or collect them in later runs.

## 8. Inputs to the next tasks

- **3.5 (K):** mean prompt tokens per case, using the example states with no history, are 2420–2898. That leaves about 5300 of the 8192-token context for summary and turn history, before the 200-token reply.
- **3.6 (freeze):** weigh correct calls (tool match), repeatability (§5), GPU fit (§2) and the M6 figures together.
- **3.7 (grammar-constrained decoding):** JSON mode is decisive for Qwen and makes no difference for Granite or Llama. Granite's `"null"` string and missing `arguments` are what a schema-constrained grammar (as opposed to plain JSON mode) would prevent. Decided in `docs/decisions.md` 2026-10-06: with `llama3.1:8b` frozen, neither JSON mode nor a grammar is used.

## 9. Raw data

`results/` is gitignored. Both run folders, `results/bench/toolcall/20261004T095239Z/` and `results/bench/toolcall/20261004T095558Z/`, each hold `summary.json` and one `<model>.jsonl` per model, with every raw reply. Both folders go in the team Drive folder (README, "Shared storage") under `bench/toolcall/`, so the numbers here can be checked without re-running.
