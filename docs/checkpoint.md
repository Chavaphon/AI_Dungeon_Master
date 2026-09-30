# Weekly checkpoint

WBS 1.6 · Owner: SD · Covers the recurring tasks 12.1–12.7 · CLAUDE.md wins on any conflict.

## 1. The slot

| | |
|---|---|
| When | Every **Monday**, **20:00–21:00** (1 hour) |
| Where | Arranged by the team |
| Who | Shayanis (SS), Chavaphon (CI), Sudakarn (SD) |
| Calendar | Recurring slot booked by the team, 28 Sep – 16 Nov |

Exceptions to the Monday slot:

| Checkpoint | Date | Note |
|---|---|---|
| 12.1 Week 1 | Mon 28 Sep | Slot was booked after this date; the team agrees a catch-up time before G1 (4 Oct) |
| 12.2 Week 2 | Mon 5 Oct | Checks the 12.8 handover note is on track |
| — | Mon 12 Oct, Mon 19 Oct | Examination blackout, no checkpoint |
| 12.3 Week 3 | **Wed 21 Oct**, 20:00 | First day back after the blackout |
| 12.4 Week 4 | Mon 26 Oct | — |
| 12.5 Week 5 | Mon 2 Nov | — |
| 12.6 Week 6 | Mon 9 Nov | — |
| 12.7 Week 7 | Mon 16 Nov | Last checkpoint before the 22 Nov submission |

If a checkpoint has to move, move it within the same week. A skipped checkpoint is still recorded in the decision log as skipped.

## 2. Agenda (fixed, 60 minutes)

1. **Last week** (15 min). Each person: tasks closed, tasks slipped, real hours against the estimate.
2. **Gates and triggers** (10 min). Check the next gate or milestone in `TASK_CHECKLIST.md` and every trigger in the risk register. A fired trigger gets its fallback decided in the meeting, not later.
3. **Decisions** (20 min). Open questions from CLAUDE.md §16, open points in any `docs/` note, and any proposed spec change.
4. **This week** (10 min). Confirm owners and dates for the week's tasks. Rebalance anyone over capacity.
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
