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
| Ollama | 0.35.0, serving at `http://localhost:11434` when measured; runs use the 0.35.1 that `config/model.json` pins (§7) |

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

## 7. Setting up Ollama for experiment runs

Added 2026-11-03 (WBS 7.6). Every run must be served by the Ollama version that `config/model.json` pins (`ollama_version`, now 0.35.1): `OllamaClient.verify()` refuses any other, so a batch on the wrong version stops before its first run. The Windows tray app auto-updates (it had moved this machine to 0.40.13 before the smoke runs, and to 0.40.14 by 3 November, `docs/smoke_runs.md` §2), so experiment runs use a standalone server with no tray app and no updater.

**Install (Windows, once per machine).** Use the release's standalone zip, not `OllamaSetup.exe`. It installs nothing, leaves any existing installation alone, and cannot update itself.

1. Download `ollama-windows-amd64.zip` and `sha256sum.txt` from the [v0.35.1 release](https://github.com/ollama/ollama/releases/tag/v0.35.1), for example with `gh release download v0.35.1 --repo ollama/ollama --pattern ollama-windows-amd64.zip --pattern sha256sum.txt`.
2. Check the zip against `sha256sum.txt`: `sha256sum ollama-windows-amd64.zip` must print `dc50b9ca7f9023c86525012632cd1615b093d0407987444a7f62ecab617e8e93`, which is also the digest GitHub shows for the asset.
3. Unpack it to a folder of its own. On this machine that is `C:\Users\USER\ollama-0.35.1\` (`ollama.exe` and `lib\`). `ollama.exe --version` prints `client version is 0.35.1`.

The standalone server reads models from the same place as the tray app (`%USERPROFILE%\.ollama\models`), so a model pulled earlier does not need pulling again. On a new machine, run `ollama.exe pull llama3.1:8b` once with the server below running. `verify()` then checks the digest against `config/model.json`.

**Before every batch, smoke run or benchmark:**

1. Quit the tray app (tray icon, Quit Ollama), and turn off its start at login. Nothing may be listening on port 11434 except the server below.
2. In a terminal of its own, which stays open for the whole batch, start the server:

   ```
   C:\Users\USER\ollama-0.35.1\ollama.exe serve
   ```

   It should log `Listening on 127.0.0.1:11434 (version 0.35.1)`.
3. Check the version and the model digest from the repository root:

   ```
   .venv/Scripts/python.exe -c "from adm.orchestration.client import OllamaClient, load_model_config; OllamaClient(load_model_config()).verify(); print('ok')"
   ```

4. Start the batch (`python -m adm.cli batch --manifest experiments/main_grid.json`). Nothing else may use the server while it runs (`docs/model_selection.md` §3.3). If the batch stops or the machine restarts, start the server again and run the same command; finished runs are not played again (`adm/orchestration/batch.py`).

**Checked 2026-11-03** on this machine: a batch of `s01_cellar` under A and D, seed 4242, was killed part-way through D and run again. The finished A run was skipped, D's partial log went to `runs/aborted/`, and the replayed D run matched the aborted one's six records in every field but the timings.
