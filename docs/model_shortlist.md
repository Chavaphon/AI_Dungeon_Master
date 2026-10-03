# Model shortlist

WBS 3.2 · Owner: CI · Checked 2026-10-03 · CLAUDE.md wins on any conflict.

The three models that the Week 2 benchmark (WBS 3.3, 3.4) compares. One of them is frozen in `config/model.json` at WBS 3.6. Until then, no model name appears in code (CLAUDE.md §2.2).

## 1. Candidates

| # | Ollama tag | ID | Family | Parameters | Quantisation | Size on disk | Native context | Capabilities |
|---|---|---|---|---|---|---|---|---|
| 1 | `qwen3.5:9b` | `6488c96fa5fa` | Qwen 3.5 (Alibaba) | 9.7B | Q4_K_M | 6.6 GB | 262144 | completion, tools, thinking, vision |
| 2 | `granite4.2:8b` | `f586c02fdecd` | Granite 4.2 (IBM) | 8.8B | Q4_K_M | 5.3 GB | 131072 | completion, tools, thinking |
| 3 | `llama3.1:8b` | `46e0c10c039e` | Llama 3.1 (Meta) | 8.0B | Q4_K_M | 4.9 GB | 131072 | completion, tools |

All values are from `ollama show <tag>` and `ollama list` on the machine in `docs/hardware.md`, with Ollama 0.35.0.

Why these three:

- **Three model families.** The benchmark compares families, not sizes of one family.
- **Every one has Ollama's `tools` capability.** Condition D lives or dies on producing a valid tool call (risk R1).
- **Qwen 3.5 9B** has the strongest published tool-calling results at this size. It is also the largest of the three and the tightest fit (§3).
- **Granite 4.2 8B** is built for agent use and structured JSON output.
- **Llama 3.1 8B** is the older baseline. It was already smoke-tested in WBS 3.1 and is the only one that fits fully on the GPU in §3.

## 2. Licences checked

Each licence was read from the model itself with `ollama show <tag> --license`, not taken from a web page.

| Model | Licence | What it requires of us |
|---|---|---|
| `qwen3.5:9b` | Apache License 2.0 | Keep the licence and notices if we redistribute the weights. We don't. |
| `granite4.2:8b` | Apache License 2.0 | As above. |
| `llama3.1:8b` | Llama 3.1 Community License Agreement (release date 23 July 2024) | Follow the Llama 3.1 Acceptable Use Policy. If we distribute it or a product using it, display "Built with Llama" and include the licence. The 700-million-user clause doesn't apply to us. |

All three allow research use at no cost, which is all this project needs. **If Llama 3.1 is frozen at 3.6**, the report (WBS 11.x) must say "Built with Llama" and cite the licence.

## 3. Fit on the GPU at an 8192-token context

This is a fit check only, not a benchmark. Each model was loaded with `num_ctx 8192` and `temperature 0`, sent one prompt (`Reply with the JSON object {"tool": null} and nothing else.`), checked with `/api/ps`, and then unloaded. `think: false` was sent to the two thinking models.

| Model | Loaded size (MiB) | On GPU (MiB) | GPU share | Reply |
|---|---|---|---|---|
| `qwen3.5:9b` | 5987 | 5251 | **88%** | `{"tool": null}` |
| `granite4.2:8b` | 6521 | 5971 | **92%** | `{"tool": null}` |
| `llama3.1:8b` | 5543 | 5543 | 100% | `{"tool": null}` |

All three returned bare JSON at temperature 0. With `think: false`, neither thinking model produced any reasoning text.

**Qwen and Granite did not fit fully on the GPU, but only because of the conditions on the day.** At the time of the check, other processes held 1295 MiB of GPU memory, leaving 6605 MiB free. In WBS 3.1, 7899 MiB were free. Both models' loaded sizes are below 7.7 GiB, so they should load at 100% GPU once the other GPU applications are closed. **This must be confirmed at the start of 3.4:** check `nvidia-smi` idle memory and `ollama ps` for each model before any timed run. If either model still splits between CPU and GPU with the GPU otherwise idle, its tokens per second will understate it, so note this next to its M6 figures.

## 4. Considered and excluded

| Model | Why not |
|---|---|
| Any 14B model (e.g. Qwen 3 14B, Phi-4) | About 9 GB of weights at Q4, more than the 7.7 GiB usable (`docs/hardware.md` §5) |
| `qwen3:8b` | Same family as Qwen 3.5; one Qwen is enough |
| Gemma 4 E4B | About 4.5B effective parameters, small for reliable tool calls; also a vision/audio model, so much of its size goes to things we don't use |
| Granite 4.1 8B | Superseded by Granite 4.2 |
| Qwen 2.5, Llama 3.0, Llama 3.2 | Older generations; Llama 3.1 already covers the "older baseline" slot |

## 5. Notes for 3.3 and 3.4

- **Send `num_ctx: 8192` on every request** (`docs/hardware.md` §4).
- **Send `think: false` to Qwen 3.5 and Granite 4.2.** Qwen 3.5 thinks by default. Reasoning text would inflate latency and could break the "reply with one JSON object" rule. Llama 3.1 has no thinking mode, and the field should not be sent to it.
- **Override the sampling defaults.** Qwen 3.5 ships with `temperature 1`, `top_p 0.95`, `top_k 20` and `presence_penalty 1.5`. Granite ships with `temperature 1` and `top_p 0.95`. Our settings are 0.0 for tool calls and 0.7 for narration (CLAUDE.md §2.2). Set every sampling parameter explicitly per request so that model defaults never leak into a run.
- **Qwen 3.5 needs Ollama 0.17.1 or later.** We run 0.35.0.
- **The 3.4 comparison table uses these exact tags and IDs.** If a tag is re-pulled and its ID changes, re-run that model.

## Sources

- [Ollama library: qwen3.5:9b](https://ollama.com/library/qwen3.5:9b)
- [Ollama library: granite4.2:8b](https://ollama.com/library/granite4.2:8b)
- [Ollama library: llama3.1:8b](https://ollama.com/library/llama3.1)
- [Ollama tool-calling models: full list](https://localaimaster.com/blog/best-ollama-models-tool-calling)
- [Best small language models under 10B in 2026](https://www.labellerr.com/blog/best-small-language-models-under-10b-parameters/)
