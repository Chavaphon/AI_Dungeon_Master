# Model selection and frozen configuration

WBS 3.6 · Owner: CI · Run 2026-10-05 · CLAUDE.md wins on any conflict.

This is deliverable D2. It chooses one of the three shortlisted models (`docs/model_shortlist.md`) using the 3.4 and 3.5 evidence (`docs/model_benchmark.md`, `docs/context_budget.md`). It tests whether the chosen model replies identically across separate runs, and freezes the result in `config/model.json`. **Result: `llama3.1:8b`, Q4_K_M, K = 8.** Replies are byte-identical across processes and days when the model is freshly loaded. Earlier requests to an already-loaded model can change a reply (§3.2), so every run must start from a fresh load.

## 1. Evidence

All figures come from earlier documents except the repeatability rows, which are §3 here.

| | `qwen3.5:9b` | `granite4.2:8b` | `llama3.1:8b` |
|---|---|---|---|
| Schema-valid, prompt mode (3.4 §2) | 23% | 85% | **100%** |
| Schema-valid, JSON mode (3.4 §3) | 100% | 85% | **100%** |
| Tool match, prompt / JSON (3.4) | 23% / 95% | 90% / 90% | 80% / 80% |
| Risk R1, prompt mode (3.4 §6) | triggered | clear | clear |
| Identical across repeats in one run (3.4 §5) | no, 5 of 20 cases | yes | yes |
| Identical across fresh processes (§3) | not tested | not tested | **yes** |
| GPU share at 8192 context, GPU idle (3.5 §1) | 88% | 92% | **100%** |
| Mean / p95 s per tool call (3.4 §2) | 1.35 / 1.73 | 1.02 / 1.56 | **0.57 / 0.89** |
| Generation tok/s (3.4 §2) | 46.4 | 40.5 | **63.4** |
| K_fit, worst case (3.5 §3) | 8 | 8 | 10 |
| Stable up to K = 16, transcript history (3.5 §5.2) | yes | yes | yes |
| Licence (shortlist §2) | Apache 2.0 | Apache 2.0 | Llama 3.1 Community |

## 2. Choice

**`llama3.1:8b`**, for four reasons, in order of weight:

1. **Reproducibility (invariant 4).** Qwen gave different replies to identical requests within one run (3.4 §5), and a byte-identical replay cannot rest on that. Llama is identical within a run and across fresh processes (§3).
2. **Schema-valid rate (R1).** Llama reaches 100% without JSON mode or a grammar. Granite has schema errors that would need one: the string `"null"` instead of JSON `null`, and missing `arguments`. Qwen is at 23% without JSON mode.
3. **GPU fit and speed (R4).** Llama is the only candidate fully on the 8 GB GPU, and it is about twice as fast per tool call. The Week 6 batches (9.1, 9.2) run 16 scenarios × 4 conditions × several seeds unattended, so throughput matters.
4. **No change of plan.** K = 8 already holds for Llama with room to spare (K_fit 10). Prompt mode and JSON mode give the same Llama replies, so 3.7 (#39) is not forced to adopt JSON mode.

**The known cost is tool match: 80%.** Llama's 4 misses in 20 are valid calls for the wrong action (3.4 §4):
- tc06 and tc19: relationship changes dropped as `{"tool": null}`;
- tc11: Fire Bolt sent as a sword attack;
- tc16: a quest advance sent as a perception check.

The validator cannot see these (CLAUDE.md §7.2). They are measured by M3, and the report should name relationship and quest updates as the weak tools. Qwen with JSON mode matches more often (95%), but not repeatably, and point 1 outweighs it.

## 3. Repeatability across processes

3.5 §7 found that one Llama case (tc16, K = 0) replied `{"tool": null}` in 3.5 run 1 and a perception check in 3.5 run 3. Both runs used Ollama's default options with `seed 0`. This section tests whether that difference was random.

### 3.1 Fresh load, same sequence: identical

Each run below is a new Python process, started after `ollama stop llama3.1:8b`, with the GPU idle (0 MiB used before loading) and the model at 100% GPU. The model digest is `sha256:46e0c10c…ca666e` (full value in `config/model.json`), and Ollama is 0.35.1.

| Comparison | Records | Differing raw replies |
|---|---|---|
| Tool calls, 3.4 run `20261004T095239Z` vs `20261005T090326Z` vs `20261005T090416Z`, 3 repeats each | 60 per run | **0** |
| Tool calls, repeats within each of those runs | 20 cases × 3 | **0** |
| Narration at temperature 0.7, seeds 0–4, 3.5 run `20261005T052846Z` vs `20261005T090501Z` vs `20261005T090548Z` | 40 per run | **0** |
| All three context phases in run-1 order, 3.5 run `20261005T052846Z` vs `20261005T090731Z`, accuracy replies at K = 0, 8, 10, 16 | 80 | **0** |

The last row reproduces 3.5 run 1 exactly, including tc16 = `{"tool": null}`. The narration result also shows that a fixed seed makes temperature-0.7 sampling repeatable.

### 3.2 Earlier requests can change a reply

The tc16 K = 0 request body is byte-identical in the 3.3 tool-call bench and in both 3.5 history formats (checked with `==` on the built request dicts). The reply still differs, so the difference comes from the server's state, not from the request. The same tc16 request was sent to a loaded model after various other requests:

| Requests the loaded model had served before tc16 | tc16 reply |
|---|---|
| None (fresh load), or tc16 itself, or tc01 | perception check |
| One K = 16 chat-history request with `num_predict 1` | perception check |
| The full narration phase (`--phase narration`) | perception check |
| The full token phase, either history format (`--phase tokens`) | perception check |
| The 20 accuracy cases at K = 0 only (`--phase accuracy --k 0`) | perception check |
| **The narration phase and then the token phase (`--phase narration --phase tokens`)** | **`{"tool": null}`** |

So the reply depends on the history of requests the model has served since it was loaded. The mechanism is not established. Ollama's prompt cache reuses earlier work, and the arithmetic then differs slightly, which is enough to flip a close greedy choice. tc16 is a close choice: every model misses it (3.4 §4).

### 3.3 What this requires of every run

Invariant 4 holds if, and only if, a run sends the same request sequence to a freshly loaded model, with nothing else using the Ollama server during the run. In practice:

- **6.1 (#45), Ollama client:** at the start of a run, unload the model (a request with `keep_alive: 0`, or `ollama stop`) and load it again. Never share the loaded model across runs.
- **7.6 (#82), batch runner:** do the above before every `(seed, scenario, condition)` run, and run one at a time. Do not run benchmarks or interactive play on the same server during a batch.
- **4.18 (#76), replay harness:** a replay compares against an original run that also started from a fresh load.

## 4. Frozen values

`config/model.json`:

| Key | Value | Source |
|---|---|---|
| `model` | `llama3.1:8b` | §2 |
| `model_digest` | `sha256:46e0c10c039e…ca666e` | `/api/tags`; a re-pull that changes it is a new model |
| `quantisation` | `Q4_K_M` | `/api/tags` |
| `ollama_version` | `0.35.1` | `/api/version`; the version all evidence was gathered on |
| `context_tokens` | 8192 | CLAUDE.md §2.2, sent as `num_ctx` (`docs/hardware.md` §4) |
| `K_verbatim_turns` | 8 | 3.5 §6 |
| `temperature` | 0.7 | narration; tool calls are 0.0 (CLAUDE.md §2.2) |
| `narration_max_tokens` | 300 | CLAUDE.md §2.2 |
| `toolcall_max_tokens` | 200 | CLAUDE.md §2.2 |
| `seed` | `null` | see below |

**`seed: null` means that the run's seed is sent to Ollama** as the `seed` option on every call. The triple `(seed, scenario, condition)` then fixes the dice and the sampling together, and different seeds give different narrations, as they give different rolls. An integer here would override the run's seed for every run.

For the 6.1 client, as the benchmarks did:
- send `num_ctx` and every sampling option explicitly on every request (`docs/model_benchmark.md` §1), so that model defaults never leak in;
- send no `think` field, because Llama 3.1 has no thinking capability (`docs/model_shortlist.md` §5).

The two added keys pin the version. `model_digest` identifies the weights exactly. `ollama_version` matters because §3.2 shows that the server's behaviour affects replies. Upgrading either one means re-running §3 before any run that counts.

## 5. Licence

Llama 3.1 is under the Llama 3.1 Community License Agreement (`docs/model_shortlist.md` §2). The report (11.x) and the code and data release (11.11, #123) must display "Built with Llama" and cite the licence. The Acceptable Use Policy applies, and nothing in this project conflicts with it.

## 6. Raw data

`results/` is gitignored. These new folders are in the team Drive folder under `bench/repeat/`, keeping the `toolcall/` and `context/` split:
- `bench/repeat/toolcall/`: `20261005T090326Z`, `20261005T090416Z`;
- `bench/repeat/context/`: `20261005T090501Z`, `20261005T090548Z`, `20261005T090731Z`, and the bisection runs `20261005T091056Z` to `20261005T091252Z`.

The §3.2 probe replies were printed, not saved. Re-run them by running the listed `adm.bench.context` phases and then sending the tc16 request built by `adm.bench.toolcall.build_chat_request`.
