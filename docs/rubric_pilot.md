# Rubric pilot

WBS 8.11 · Owner: SD · Status: **done, 2026-11-08**; disagreements resolved at WBS 8.12 (section 4) · CLAUDE.md wins on any conflict.

Before the rubric is frozen at G3 (WBS 8.12), two annotators label the same turns independently by `docs/rubric.md` v0.6, and Krippendorff's alpha measures how far they agree. The disagreements listed in section 2 are the agenda for 8.12.

## 1. Method

| Item | Value |
|---|---|
| Turns | The 30 turns of the 8.10 sample (`docs/checker_validation.md` §1): both dry-run scenarios, `s01_cellar` and `long01_border_road`, under A–D at seed 3001. Both annotators label the same `results/checker_validation/sheet.md`. |
| Annotators | **First:** the 8.10 labels (`results/checker_validation/labels.csv`), drafted by Claude from the blind sheet and accepted by SD (decision log 2026-11-08). **Second:** CI (Chavaphon), `results/checker_validation/labels_CI.csv`, labelled by hand with no AI assistance, as reported by CI. CI was given the sheet, the rubric and a labelling page, and asked not to open the first annotation or `docs/checker_validation.md` §2 (which lists 13 of its labels) until done; this was not otherwise verified. Neither annotation saw the condition or the checker's output. |
| Labels | The 8.10 format: `sample_id,category,phrase,notes`, one row per divergence. Only the four rubric categories count here; `RULE` and `NOTE` rows are ignored. Write `6.4` in `notes` for a one-step stance case left unrecorded under rubric §6.4 rule 3. |
| Unit and value | One turn × one category (120 units). The value is the number of divergences of that category the annotator recorded in that turn (rubric §3 rule 1). |
| Agreement | Krippendorff's alpha, interval metric on the counts, per category and over all four pooled; nominal alpha on whether a turn has any divergence. Target ≥ 0.6 (CLAUDE.md §10.4). Alpha is undefined (`–`) when every value is the same. |
| For 8.12 | Every unit where the counts differ, with both annotators' phrases, and the turns noted `6.4` (rubric §7 point 1, the `RELATION` adjacency allowance). |

Command, once both label files exist:

```bash
python -m adm.eval.rubric_pilot --labels SD=results/checker_validation/labels.csv \
    --labels XX=results/checker_validation/labels_XX.csv     # rewrites section 2 below
```

Counting divergences rather than matching phrases keeps the unit the same as M1's, which counts divergences per turn. Two annotators who record the same number for different phrases agree on the count but not on the reading; the disagreement table shows their phrases side by side so 8.12 can catch those cases.

## 2. Results

<!-- results:start -->
Annotators: SD, CI. Turns: 30. Units: 30 turns × 4 categories. Target: alpha ≥ 0.6 (CLAUDE.md §10.4).

### Agreement

| Units | SD: divergences | CI: divergences | Alpha | Metric | Meets 0.6 |
|---|---|---|---|---|---|
| `PHANTOM` | 10 | 21 | 0.553 | interval | **no** |
| `CONTRADICT` | 7 | 8 | 0.936 | interval | yes |
| `RESOURCE` | 0 | 0 | – | interval | – |
| `RELATION` | 0 | 0 | – | interval | – |
| **All four, pooled** | 17 | 29 | 0.731 | interval | yes |
| Turn has any divergence | 11 | 18 (turns) | 0.541 | nominal | **no** |

Alpha is `–` where it is undefined: every value the same, so there is no disagreement to expect (usually a category nobody recorded).

### Disagreements (10), for 8.12

| Turn | Category | SD | CI |
|---|---|---|---|
| S03 | `PHANTOM` | 0 | 1: “The drovers” |
| S04 | `PHANTOM` | 0 | 2: “a burly man with a thick beard”; “a younger man with a scar above his left eyebrow” |
| S07 | `PHANTOM` | 0 | 1: “our missing ledgers” |
| S13 | `PHANTOM` | 0 | 1: “The drovers” |
| S15 | `PHANTOM` | 0 | 1: “The drovers” |
| S22 | `PHANTOM` | 0 | 1: “The drovers'” |
| S23 | `PHANTOM` | 1: “a handful of coins” | 2: “a handful of coins”; “the border fort's commander” |
| S23 | `CONTRADICT` | 0 | 1: “the reward for escorting the caravan safely to the border fort. Here it is, Edda.” |
| S27 | `PHANTOM` | 0 | 2: “Commander Alderan”; “Orlo's sister” |
| S28 | `PHANTOM` | 0 | 1: “The drovers” |

### One-step stance cases noted `6.4` (rubric §7 point 1)

- SD: S30
- CI: S30
<!-- results:end -->

## 3. For the rubric freeze (WBS 8.12)

**Verdict.** Pooled alpha is **0.731**, above the 0.6 target, and `CONTRADICT` agreement is high (0.936). `PHANTOM` (0.553) and whether a turn has any divergence (0.541) fall short. `RESOURCE` and `RELATION` were recorded by neither annotator, so their agreement is untested by this pilot.

**Almost all disagreement is one rule.** 8 of the 10 disagreeing units are characters the narration describes that appear in the player's scripted input but have no `display_name`: the drovers (S03, S13, S15, S22, S28), the two gate guards (S04), the fort's commander (S23) and Orlo's sister and Commander Alderan (S27). The first annotation treated them as in scope; CI recorded them as `PHANTOM`. Rubric §1 says only the scenario's `display_name`s and `locations` are in scope, so CI's reading is the literal one. Without these 8 units the two annotations differ on 2.

**Proposed changes for rubric v1.0**, for the team to decide at 8.12:

1. **Characters named in a scripted input** (§6.1, new rule): decide whether a character, group or place that the scenario's own `scripted_inputs` text names is in scope. Recommended: **in scope**, the same as a `display_name`, because the stimulus put it there and the model is answering the player; an invented personal name for one (Commander Alderan) is still not a new entity. Either way, write it down: it is the cause of the `PHANTOM` shortfall.
2. **Invented plural of a single item** (S07, "our missing ledgers"): CI read it as rule 6.1.4 (too many of a kind). Confirm whether a plural in dialogue counts.
3. **A reward paid while its quest is still active** (S23): CI recorded `CONTRADICT`. §6.2.2 lists closed-as-open and not-started-as-underway, but not active-as-completed. Add it, or say it is not scored.
4. **`RULE` for an attack with no executed call** (S06, S14) and an NPC attack whose attacker is ambiguous (S21): the annotations differ. `RULE` is M4, not a rubric category, so it is outside alpha, but the sheet should show which bandit acted.
5. **`RELATION` adjacency (rubric §7 point 1):** both annotators had the one one-step case (S30) and both left it unrecorded. No evidence against the allowance: **keep it**.

If the team adopts change 1, the main-grid annotation should use the rule as written; the pilot does not need to be re-run, since it has identified the gap the freeze is meant to close.

## 4. Resolved at the rubric freeze (WBS 8.12)

Decided by the team on 2026-11-08 (`docs/decisions.md`, WBS 8.12) and written into `docs/rubric.md` v1.0, tag `rubric-v1.0`. Changes 1, 3 and 5 were adopted as proposed. On change 2, an invented plural of an item that exists once is a `PHANTOM` (rubric §6.1 rule 4). Change 4 is outside the rubric (`RULE` is M4). The pilot is not re-run: section 2 stays the agreement measured under v0.6, and the table below is the reading under v1.0.

| Turn | Category | SD | CI | v1.0 | Rule |
|---|---|---|---|---|---|
| S03 | `PHANTOM` | 0 | 1 | 0 | §6.1 rule 6: the drovers are named in a scripted input |
| S04 | `PHANTOM` | 0 | 2 | 0 | §6.1 rule 6: the two men are the gate guards of a scripted input, described |
| S07 | `PHANTOM` | 0 | 1 | 1 | §6.1 rule 4: "our missing ledgers", a plural of the one ledger |
| S13 | `PHANTOM` | 0 | 1 | 0 | §6.1 rule 6: the drovers |
| S15 | `PHANTOM` | 0 | 1 | 0 | §6.1 rule 6: the drovers |
| S22 | `PHANTOM` | 0 | 1 | 0 | §6.1 rule 6: the drovers |
| S23 | `PHANTOM` | 1 | 2 | 1 | "a handful of coins" stands; §6.1 rule 6: the fort's commander is named in a scripted input |
| S23 | `CONTRADICT` | 0 | 1 | 1 | §6.2 rule 2: the reward is handed over while the quest is still `active` |
| S27 | `PHANTOM` | 0 | 2 | 0 | §6.1 rule 6: Orlo's sister is named in a scripted input, and "Commander Alderan" is an invented name for the fort's commander |
| S28 | `PHANTOM` | 0 | 1 | 0 | §6.1 rule 6: the drovers |

Under v1.0, SD's reading matches 8 of the 10 units and CI's matches 2 (S07, S23 `CONTRADICT`). Both point to a gap in v0.6, not a lapse by either annotator. The one-step stance case (S30) stays unrecorded by both, and the `RELATION` allowance is kept (rubric §6.4 rule 3).
