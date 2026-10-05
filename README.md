# AI_Dungeon_Master

## Shared storage

Run artefacts and transcripts do not go in git: `runs/` and `results/` are gitignored (CLAUDE.md §3). The team copy lives in one Google Drive folder on the KMUTT account (WBS 1.5):

**https://drive.google.com/drive/folders/1fIteuSKqAyhTU3uR6mfV6SzHdxLqoO9H**

Access is limited to the three team members. Sign in with your `@kmutt.ac.th` account; if you are asked to request access, ask Sudakarn.

```
AI_Dungeon_Master/
  runs/
    A/  B/  C/  D/     audit logs, runs/{condition}/{scenario_id}/{seed}.jsonl (CLAUDE.md §11)
  results/             checker output and scored metrics, e.g. results/automated.jsonl
  benchmarks/          Week 2 model benchmark output (WBS 3.4, 3.5)
  annotations/         human annotation sheets for M1, M3 and M5
```

Rules:

- **The Drive copy is the dataset.** A run counts once its `.jsonl` is uploaded to `runs/`. A run that exists only on one laptop does not exist.
- **Keep the same paths.** Upload `runs/` and `results/` with the same layout the code writes locally, so a download can be dropped back into the repository root and re-scored.
- **Never edit an audit log by hand.** Re-run it instead. If a run is replaced, upload the new file and note why in `docs/decisions.md`.
- **Scenario subfolders are created by the batch runner**, not by hand.

## Running the tests

One-time setup from the repository root (Python 3.11):

```bash
python -m venv .venv
source .venv/bin/activate        # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

Then:

```bash
pytest -q                                   # whole suite
pytest tests/test_state_schema.py -q        # one file
pytest tests/test_state_schema.py::test_three_examples_exist   # one test
pytest -k boundaries -q                     # tests whose name matches
pytest --cov=adm --cov-report=term-missing  # with coverage
```

Both quality gates must pass before any commit (CLAUDE.md §2):

```bash
pytest -q
ruff check . && ruff format --check .
```

No test calls the model or needs Ollama running; orchestration tests use a recorded-response fake client (CLAUDE.md §13).

| Test file | What it checks |
|---|---|
| `tests/test_boundaries.py` | Package import boundaries from `docs/conventions.md`, and that only `adm/engine/dice.py` imports `random` |
| `tests/test_state_schema.py` | `schemas/state.schema.json` accepts the examples in `schemas/examples/` and rejects states that break CLAUDE.md §4–5 |
| `tests/test_identifiers.py` | Id patterns in `schemas/state.schema.json` follow `docs/identifiers.md`, and every file in `scenarios/` is named after its id and stays in its own namespace |
| `tests/test_tool_contract.py` | `schemas/tools.schema.json` accepts the example calls and results, rejects ones that break CLAUDE.md §6, and matches the §6.1 and §6.3 tables and the matrix in `docs/tool_contract.md` |
| `tests/test_scenario_schema.py` | `schemas/scenario.schema.json` accepts the example scenario and every file in `scenarios/`, and rejects scenarios that break CLAUDE.md §12 |
| `tests/test_audit_log.py` | `schemas/audit.schema.json` accepts the example turn records and rejects records that break CLAUDE.md §7 and §11; the valid example replays to its after-hash |
| `tests/engine/test_state.py` | `adm/engine/state.py` loads and saves every example state without loss, validates against the schema on both, and hashes as `docs/conventions.md` §2 |
| `tests/engine/test_dice.py` | `adm/engine/dice.py` parses only the `XdY+Z` of CLAUDE.md §4.2, reproduces a pinned sequence from a seed, keeps the right die under advantage and disadvantage, and returns rolls that match `roll_result` in the tool contract |
