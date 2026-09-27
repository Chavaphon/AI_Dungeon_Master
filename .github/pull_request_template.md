## WBS task

WBS ID: <!-- e.g. 4.5 -->
Closes #

## Summary

<!-- What changed and why. -->

## Checklist

- [ ] `pytest -q` passes
- [ ] `ruff check . && ruff format --check .` passes
- [ ] No bare `random.*`; all dice go through the seeded `DiceRoller` (CLAUDE.md §1.1.3)
- [ ] State is mutated only inside `engine/`, through a validated tool call (CLAUDE.md §1.1.1)
- [ ] No test calls the model; orchestration tests use the recorded-response fake client
- [ ] New dependency, rejection code, prompt-template change or spec deviation has a `docs/decisions.md` entry
- [ ] Task ticked in `TASK_CHECKLIST.md` (or the WBS workbook, not both)
