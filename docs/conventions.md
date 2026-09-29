# Module boundaries and coding conventions

WBS 1.4 · Owner: SS · Status: **draft, awaiting sign-off** · CLAUDE.md wins on any conflict.

## 1. Module boundaries

Dependencies point one way: `cli → orchestration → engine`, and `eval → engine`. Nothing imports `cli`.

| Package | Owns | May import | Must never |
|---|---|---|---|
| `adm/engine/` | `GameState` and every mutation of it; dice; rules; tool dispatch; validator; audit records | stdlib, `pydantic`, `jsonschema` | import `orchestration`, `eval`, `cli` or `httpx`; do network I/O; read the clock or env inside rule code |
| `adm/orchestration/` | Ollama client, prompt assembly, parser, rolling summary, safety filter, turn loop | `engine` public API | assign to a state field; parse model output into anything but a *proposed* tool call; import `eval` |
| `adm/eval/` | checker, HP-band lexicon, metrics, annotation CLI | `engine` (offline replay for A–C ground truth; band thresholds) | import `orchestration` (the checker must not depend on how a run was produced); call the model |
| `adm/cli.py` | composition root: reads `config/`, wires the packages, typer commands | everything | contain game logic |

The rules behind this table:

- **One write path.** The only path to change state is `engine.tools.dispatch(state, proposed_call)`. It validates, executes, appends the audit record and returns the result envelope. Orchestration gets back a result, never a mutable state. (Invariants 1, 2, 6.)
- **One RNG.** `random` is imported only in `engine/dice.py`, and the `DiceRoller` is created once per run from the seed and passed in explicitly. There are no module-level RNGs. (Invariant 3.)
- **One model name.** It is read from `config/model.json` by a single loader in `orchestration/client.py` and appears nowhere else. (§2.2.)
- **One band threshold.** `hp_band(current, maximum)` is defined once in `engine` so the engine can put it in `narration_facts`. `eval/bands.py` imports it and adds only the phrase lexicon, so the engine and the checker cannot disagree. (§10.2.)
- **Condition differences live in `config/prompts/` and one flag for tool wiring.** No `if condition == "C"` anywhere else. (Invariant 7.)

`tests/test_boundaries.py` enforces the import rules and the RNG rule automatically. The other rules are checked in review.

## 2. Coding conventions

- **Python 3.11.** `ruff format` and `ruff check` are configured in `pyproject.toml` (line length 100). Both must pass before a commit.
- **Types.** Every public function has type hints. State and results are pydantic v2 models, and tool arguments are validated through them, not with hand-written `dict` checks.
- **Identifiers.** Use the kind-prefixed `snake_case` ids of §5.1 (`pc_`, `npc_`, `item_`, `quest_`, `spell_`). Never parse meaning from an id beyond its prefix.
- **Rejections are values, bugs are exceptions.** An illegal tool call returns an `ok: false` envelope with a §6.3 code. Exceptions are only for programmer errors and broken invariants, and they are never caught to hide a bad state. Adding a rejection code needs a `docs/decisions.md` entry.
- **Determinism.** JSON written for hashing uses `json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`. Iterate over sorted keys wherever order affects output. The wall-clock time (`timestamp`, `latency_ms`) is taken only in orchestration and passed into the audit record.
- **Tests.** Tests live in `tests/`, mirroring the package layout (`tests/engine/test_combat.py`). No test calls the model; use the recorded-response fake client. Use `hypothesis` for property checks such as the HP clamp. Construct RNGs from a literal seed in the test.
- **Git.** One WBS task per branch and PR. Name branches `<type>/wbs-<id>-<slug>`, e.g. `feat/wbs-4.5-attack`. Use conventional commit prefixes (`feat:`, `fix:`, `docs:`, `chore:`, `test:`) and fill in the PR template.

## 3. Open points to settle at sign-off

1. **"Byte-identical run" (invariant 4) versus timestamps.** `timestamp` and `latency_ms` differ on every run. Proposal: replay compares the state-hash sequence and every audit field except those two.
2. **Where `hp_band` lives** (§1 above). CLAUDE.md §3 puts band *classification* in `eval/bands.py`, but the engine also needs the thresholds. Proposal: thresholds go in `engine`, and the lexicon stays in `eval`.

## Sign-off

| Member | Agreed | Date |
|---|---|---|
| Shayanis (SS) | Yes | 2026-09-29 |
| Chavaphon (CI) | | |
| Sudakarn (SD) | | |
