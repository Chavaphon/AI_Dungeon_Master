# Inference hardware

WBS 3.1 · Owner: CI · Measured 2026-10-01 · CLAUDE.md wins on any conflict.

The machine that serves the model, and how much of the model fits on its GPU. Tasks 3.2 to 3.6 build on these figures.

## 1. Machine

| Item | Value |
|---|---|
| Owner | CI (Chavaphon) |
| OS | Windows 11 Home Single Language |
| CPU | Intel Core Ultra 7 255H |
| System RAM | 23.4 GiB usable |
| GPU | NVIDIA GeForce RTX 5060 Laptop GPU (compute capability 12.0, Blackwell) |
| NVIDIA driver | 610.88 |
| Ollama | 0.35.0, serving at `http://localhost:11434` |

## 2. VRAM

| Measurement | MiB |
|---|---|
| Total | 8151 |
| Free when idle (no model loaded) | 7899 |
| Used with the smoke-test model loaded at an 8192-token context | 5652 |
| Headroom left with that model loaded | about 2250 |

**Usable VRAM for the model is about 7.7 GiB.** That figure has to cover the weights plus the KV cache for the context window.

## 3. Smoke test

Model `llama3.1:8b` (Q4, 4.9 GB on disk), chosen only because it was already pulled. It is **not** a shortlist candidate, and its name appears nowhere in code (CLAUDE.md §2.2).

Prompt: `Describe a dark dungeon cellar in about 150 words.` at `temperature 0` and `num_ctx 8192`, through `/api/generate`.

| Run | Load time | Prompt eval | Generation |
|---|---|---|---|
| Cold (model not loaded) | 6.6 s | 141 tok/s | 68 tok/s |
| Warm (model already loaded) | 0 s | 1328 tok/s | 66 tok/s |

`ollama ps` reported `100% GPU` at an 8192-token context. The very first load after a reboot took 35 s, because the model was read from disk.

## 4. Context size changes what fits

With no `num_ctx` set, Ollama 0.35.0 loads this model at a **16384-token** context. The model plus its KV cache then takes 7.3 GB, `ollama ps` shows a `16%/84% CPU/GPU` split, and generation slows to 6 tok/s, about ten times slower than at 8192. Our spec value is `context_tokens: 8192` (CLAUDE.md §2.2), and at that value the model fits entirely on the GPU.

So `orchestration/client.py` (WBS 6.1) must send `num_ctx` from `config/model.json` with every request and must not rely on Ollama's default. Otherwise latency (M6) depends on whatever version of Ollama happens to be installed.

## 5. What this means for task 3.2 (shortlist)

- 7B to 8B models at Q4 fit fully on the GPU at an 8192-token context, with about 2 GiB to spare.
- A 14B model at Q4 needs about 9 GB for the weights alone, more than the 7.7 GiB usable. It would run partly on the CPU at a fraction of the speed, which would show up in M6 and stretch the batch runs (WBS 9.1, 9.2). Shortlist 14B candidates only if someone can run the batches on a larger GPU, or if we accept a lower quantisation for them.

## 6. Open point

These figures are valid only for this machine. If another team member runs benchmarks or batches on different hardware, add a section for that machine here. M6 latency is only comparable between runs made on the same machine.
