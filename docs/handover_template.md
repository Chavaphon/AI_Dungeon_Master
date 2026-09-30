# Handover note template

WBS 1.6 · Owner: SD · Used by 12.8 (before 12 Oct) and 12.9 (before 23 Nov) · CLAUDE.md wins on any conflict.

Copy this file to `docs/handover_YYYY-MM-DD.md`, fill in every section, and commit it before the blackout begins. Write it for someone who has forgotten everything: after nine days away, resuming from memory is the failure mode (TASK_CHECKLIST.md, 12 Oct blackout).

Leave no section blank. If a section has nothing in it, write "none".

---

```markdown
# Handover note — YYYY-MM-DD

Written by: XX · Reviewed by: XX, XX · Blackout: <start> to <end> · Resume date: <date>

## 1. Where we are

- Last completed gate or milestone: <G1 / G1b / M1 / ...>
- Next gate or milestone: <name> on <date> — <on track / at risk / missed>
- `main` at commit: <short sha> · Latest tag: <tag>
- Test suite: <n> passing, <n> failing (`pytest -q`) · Lint: <clean / not clean>

## 2. Task status by owner

| Owner | Done since last handover | In progress (and % left) | Not started, due next |
|---|---|---|---|
| SS | | | |
| CI | | | |
| SD | | | |

## 3. Work in flight

Every branch or PR that is not merged:

| Branch / PR | Owner | State | What is left | Safe to merge as is? |
|---|---|---|---|---|
| | | | | |

## 4. Frozen things

What is fixed and must not change without a `docs/decisions.md` entry:

- Specifications: <tag, e.g. spec-v1.0>
- Model, version, quantisation, K: <values from config/model.json>
- Prompt templates: <frozen / not yet>
- Rubric: <version, frozen / not yet>

## 5. Open decisions and questions

| Question | Options on the table | Owner | Must be decided by |
|---|---|---|---|
| | | | |

## 6. Risks

Risk-register triggers that have fired or are close to firing (TASK_CHECKLIST.md, risk register):

| Risk | Status | Fallback agreed |
|---|---|---|
| | | |

## 7. Where things live

- Repository: https://github.com/Chavaphon/AI_Dungeon_Master
- Shared storage for runs and results: <path, see README>
- Run artefacts present so far: <e.g. none / runs/D/s01_cellar/12345.jsonl ...>
- Anything that lives only on one person's machine: <list it, or move it before the blackout>

## 8. First steps on the resume day

A numbered list someone can follow without asking anyone:

1. `git pull` and run `pytest -q && ruff check . && ruff format --check .`
2. <first task, owner, and the file or issue to open>
3. <...>

## 9. Environment gotchas

Commands, setup steps or machine quirks that will be forgotten (Ollama version, GPU, venv, anything that broke once):

- <...>
```
