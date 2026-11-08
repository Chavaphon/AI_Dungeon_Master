# Live demo setup

How to set up and run a live demo of interactive play (`python -m adm.cli play`, condition D). The commands are for Windows PowerShell on the team laptop, run from the repository root. The Ollama setup is the one in `docs/hardware.md` §7.

A demo is not data. Its log must never go to `runs/` (CLAUDE.md §11, §14), so every command below passes `--runs` with a folder outside the repository.

## 1. Once per machine (at least a day before)

1. **Python 3.11 and the package.**

   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   pip install -e .
   ```

   If `python` opens the Microsoft Store, call `.venv\Scripts\python.exe` directly.

2. **Pinned Ollama 0.35.1, standalone.** Download `ollama-windows-amd64.zip` from the v0.35.1 release, check its sha256 (`dc50b9ca7f9023c86525012632cd1615b093d0407987444a7f62ecab617e8e93`) and unpack it to `C:\Users\USER\ollama-0.35.1\` (`docs/hardware.md` §7). Do not use `OllamaSetup.exe`: the tray app updates itself, and `play` refuses any version other than the one `config/model.json` pins.

3. **The model.** With the server from §2 step 3 running, pull it once:

   ```powershell
   C:\Users\USER\ollama-0.35.1\ollama.exe pull llama3.1:8b
   ```

   If the digest check in §2 fails, the pulled model is not the pinned one.

4. **Rehearse.** Do the whole of §2 and §3 once, on the machine and display you will demo on, and time the turns.

## 2. On the day, before the audience arrives

1. **Free the GPU.** Close games, browsers with video, and anything else that uses the GPU. A game running alongside pushed p95 latency from about 9 s to 12–18 s in the dry run (`docs/dry_run.md` §4).
2. **Quit the Ollama tray app** (tray icon, Quit Ollama). Nothing else may be listening on port 11434.
3. **Start the server** in its own terminal, and leave that terminal open for the whole demo:

   ```powershell
   C:\Users\USER\ollama-0.35.1\ollama.exe serve
   ```

   It should log `Listening on 127.0.0.1:11434 (version 0.35.1)`.

4. **Check the version and digest** in a second terminal:

   ```powershell
   .venv\Scripts\python.exe -c "from adm.orchestration.client import OllamaClient, load_model_config; OllamaClient(load_model_config()).verify(); print('ok')"
   ```

   It must print `ok`.

5. **Make a demo log folder** outside the repository, so nothing lands in `runs/` or in git:

   ```powershell
   mkdir $env:USERPROFILE\adm_demo_runs
   ```

6. **Warm-up run.** Play two or three turns with a throwaway seed, then `/quit`, to confirm that the model loads and replies:

   ```powershell
   .venv\Scripts\python.exe -m adm.cli play --scenario scenarios/s01_cellar.json --seed 9001 --runs $env:USERPROFILE\adm_demo_runs
   ```

7. **Pick unused seeds.** Each `(scenario, seed)` pair can be played once per log folder; a second try is refused with `RunExists`. Write down a few fresh seeds (9101, 9102, ...) so a restart on stage needs no thinking.
8. **Set up the terminal.** Use a large font, a dark theme, and a window wide enough that the result lines do not wrap.
9. **Prepare a fallback** in case the model fails on the day. Play the scripted run in advance and keep its log and terminal output to show instead:

   ```powershell
   .venv\Scripts\python.exe -m adm.cli run --scenario scenarios/s01_cellar.json --condition D --seed 9002 --runs $env:USERPROFILE\adm_demo_runs
   ```

## 3. During the demo

Start the session:

```powershell
.venv\Scripts\python.exe -m adm.cli play --scenario scenarios/s01_cellar.json --seed 9101 --runs $env:USERPROFILE\adm_demo_runs
```

Loading the model takes a few seconds. The title is labelled "Narrated by AI". Each turn shows one dim result line per mechanical outcome, then the narration. Each turn takes about 4–9 s.

### Suggested script (s01, Lyra: a caster with a short sword, a torch and 2 spell slots)

The rats attack before the **4th input**, whatever it says (CLAUDE.md §12; failed turns count toward it). Use the first three inputs for the non-combat features.

| # | Input | Shows |
|---|---|---|
| 1 | `I tell the Keeper I will find the missing ledger` | Quest start; possibly a stance change |
| 2 | `I hold up my torch and search behind the barrels` | Perception skill check, with a roll line |
| 3 | `I stand still and listen for the scratching` | Another check, or pure narration |
| 4 | `I draw my sword and attack the nearest rat` | Encounter starts; the rats act; attack and HP lines |
| 5 | `I hurl a bolt of fire at the other rat` | Fire Bolt |
| 6 | `I cast Fireball at the rats` | Rejection (`SPELL_NOT_SUPPORTED`), then retry: the engine owns the rules |
| 7 | `I heal my wounds` | Cure Wounds; the result line shows the slots left |
| 8 | Keep attacking until both rats are down | Victory |
| 9 | `I pick up the ledger` (if found) | Inventory change; quest advance or complete |

End with `/quit`. The session reports the number of turns and failed turns and where the log is.

### What to avoid

- **Attacking after the last rat is down.** The engine rejects it (`ENCOUNTER_OVER`), and the model tends to swap to Cure Wounds with no slot left and fail the turn. If it happens, explain it as the retry budget and turn failure at work (CLAUDE.md §7.1).
- **Things outside the ruleset**, unless you mean to show a rejection: movement or maps, items the scenario does not define, taking items from NPCs, skills other than strength, perception and stealth, or any spell other than Fire Bolt and Cure Wounds (CLAUDE.md §4, §14).
- **Expecting the scenario to end.** Nothing ends a scenario; `/quit` when you are done.

## 4. If something goes wrong

| Symptom | Fix |
|---|---|
| `Ollama is X, but config/model.json pins 0.35.1` | The tray app is serving. Quit it and start the standalone server (§2 steps 2–3). |
| `llama3.1:8b has digest ...` or `is not installed` | Pull the model with the standalone server (§1 step 3). |
| `RunExists` | That seed has already been used in the folder. Use the next fresh seed. |
| Connection refused / model error | The server terminal was closed or crashed. Start it again (§2 step 3) and restart with a new seed. |
| Very slow turns (>15 s) | Something else is using the GPU (§2 step 1). |
| "Please rephrase" | A failed turn (retry budget used up). Rephrase more plainly, naming the target and the weapon or spell. |
| Model fails completely | Switch to the fallback output (§2 step 9). |

## 5. Afterwards

1. `/quit` the session, then stop the server with Ctrl+C in its terminal.
2. Leave the demo logs in `%USERPROFILE%\adm_demo_runs`. Never copy them into `runs/`, never upload them to the team Drive, and never score them.
