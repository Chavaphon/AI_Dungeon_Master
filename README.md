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
