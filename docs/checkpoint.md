# Weekly checkpoint

WBS 1.6 · Owner: SD · Covers the recurring tasks 12.1–12.7 · CLAUDE.md wins on any conflict.

## 1. The slot

| | |
|---|---|
| When | Every **Saturday**, **19:00–20:00** (1 hour) |
| Where | Arranged by the team |
| Who | Shayanis (SS), Chavaphon (CI), Sudakarn (SD) |
| Calendar | Recurring slot booked by the team, 3 Oct – 21 Nov |

The slot moved from Monday 20:00 to Saturday 19:00 at the Week 1 checkpoint (`docs/decisions.md`, 2026-10-03). Each checkpoint now falls at the end of its week: it reviews the week just finished and plans the next one.

| Checkpoint | Date | Note |
|---|---|---|
| 12.1 Week 1 | Sat 3 Oct | Held together with the 2.6 review, the day before G1 |
| 12.2 Week 2 | Sat 10 Oct | Day before G1b; checks the 12.8 handover note is ready before 12 Oct |
| — | Sat 17 Oct | Examination blackout, no checkpoint |
| 12.3 Week 3 | Sat 24 Oct | — |
| 12.4 Week 4 | Sat 31 Oct | Day before M1 / G2; decide the Condition C trigger if needed |
| 12.5 Week 5 | Sat 7 Nov | Day before G3 |
| 12.6 Week 6 | Sat 14 Nov | Day before M2 |
| 12.7 Week 7 | Sat 21 Nov | Day before M3; last checkpoint before submission |

If a checkpoint has to move, move it within the same week. A skipped checkpoint is still recorded in the decision log as skipped.

## 2. Agenda (fixed, 60 minutes)

1. **This week** (15 min). Each person: tasks closed, tasks slipped, real hours against the estimate.
2. **Gates and triggers** (10 min). Check the next gate or milestone in `TASK_CHECKLIST.md` and every trigger in the risk register. A fired trigger gets its fallback decided in the meeting, not later.
3. **Decisions** (20 min). Open questions from CLAUDE.md §16, open points in any `docs/` note, and any proposed spec change.
4. **Next week** (10 min). Confirm owners and dates for the coming week's tasks. Rebalance anyone over capacity.
5. **Write-up** (5 min). The note-taker writes the entry below into `docs/decisions.md` before the meeting ends.

Note-taker rotates in the order SD, SS, CI.

## 3. Decision-log entry

Copy this into `docs/decisions.md`. The checkpoint task is done when this entry is committed.

```markdown
## YYYY-MM-DD — Weekly checkpoint, Week N (WBS 12.x)

Attendees: SS, CI, SD · Note-taker: XX

**Closed:** 1.1, 1.2, ...
**Slipped:** <task> — <reason> — new date <date>
**Hours vs. estimate:** SS x/y · CI x/y · SD x/y

**Gates and risks:** <next gate, on track or not> · <any trigger fired, and the fallback chosen>

**Decisions:**
1. <decision> — <reason> — <what changed in CLAUDE.md or docs/, if anything>

**Open, carried to next week:** <question> — <owner>
```

## 4. Handover notes

Before each blackout, the checkpoint also checks that the handover note from `docs/handover_template.md` is on track:

- 12.8, committed before **12 Oct** (CI).
- 12.9, committed before **23 Nov** (CI).
