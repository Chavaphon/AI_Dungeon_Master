"""Display code for interactive `play` only (wp-13, docs/decisions.md WBS 13.1).

It reads the game state and never writes it, and it is never used by the
scripted `run`, `smoke` or `batch` commands. It may import the engine's public
API and `rich`; it must never import `orchestration`, `eval` or `cli`
(tests/test_boundaries.py).
"""
