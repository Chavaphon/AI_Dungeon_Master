# Sponsor User play sessions

How the five Sponsor Users play the game and how their feedback is gathered and summarised (WBS 12.11). Section 6 is the summary. Fill it in once the sessions are over.

This is informal feedback, not a study (CLAUDE.md §14). Sponsor sessions are not data: they are never scored, never uploaded to the shared Drive and never cited as results.

## 1. Limits

- **Logs stay local.** Every session is played with `--runs sponsor_runs` (CLAUDE.md §15 item 44). `sponsor_runs/` is gitignored and stays on the machine it was played on. Nothing reads it: no checker, metric or annotation tool, and nothing goes in `runs/`.
- **No personal data.** Sponsors are recorded only as `P1` to `P5`. Do not write down names, ages, contact details, or anything else that identifies a person, here or on the feedback sheets. Quote what a sponsor said only when the quote cannot identify them.
- **Informal.** There are no questionnaires, scores or recordings. Feedback is a short conversation after the session, or the sponsor's own notes.

## 2. Consent

Before a sponsor's first session, read this out and ask whether they agree:

> This is a text adventure game we built for a university project. The storyteller is an AI, a language model running on this computer; the game's rules and dice are ordinary code. Your game is saved on this machine only, and we won't upload it or use it as research data. After each session we'll chat about what worked and what didn't. We'll write up the feedback without your name. You can stop at any time, and you don't have to give a reason.

Verbal agreement is enough. Record only the sponsor code and "consented: yes" on their first feedback sheet. If a sponsor stops, delete their `sponsor_runs/` folder if they ask, and leave their feedback out of the summary if they ask.

## 3. Build and setup

1. **The build.** Sponsors play `main` as it stands when the sessions start. Write its short commit hash on every feedback sheet (`git rev-parse --short HEAD`). If `main` changes during the sessions, note the new hash from the day it is pulled.
2. **Install.** Follow README "Playing the game". For pinned Ollama 0.35.1 and the model pull on Windows, follow `docs/live_demo.md` §1. `play` refuses any Ollama version or model other than the ones `config/model.json` pins.
3. **Play.** Always pass `--runs sponsor_runs`:

   ```bash
   python -m adm.cli play --scenario scenarios/s01_cellar.json --seed 101 --runs sponsor_runs
   ```

4. **Seeds.** Each `(scenario, seed)` can be played only once per log folder, so use a new seed every session. A simple rule is day then sponsor number: day 1 for P1 is `101`, day 3 for P5 is `305`. Do not use the experiment seeds 2001, 2002, 2003 or 3001, so a sponsor log can never be mistaken for a run.
5. **Scenarios.** Start with the short scenarios (`s01_cellar` to `s12_bog_witch`, about 25 turns each). Sponsors who come back on later days can try a long one (`long01_border_road` to `long04_mountain_monastery`). Any scenario may be played in any order.

## 4. Schedule

One session a day for 3 to 5 days per sponsor, about 20 to 30 minutes each. `/quit`, Ctrl+C or end of input ends a session at any point. There is no need to finish a scenario.

## 5. Feedback sheet

Fill in one sheet per session, straight after it. A team member can fill it in from a short chat, or the sponsor can write it. The sheets are working notes. Keep them with the team, not in git; only the summary in section 6 is committed.

```text
Sponsor:        P_            Day: _ of _        Date: ____-__-__
Build:          main @ _______
Scenario:       ______________                   Seed: ___
Turns played:   about __      Finished the scenario: yes / no
Consented:      yes           (first session only)

1. Where did the story break? Narration that contradicted what had happened,
   forgot something, or invented people, items or places.

2. Where did the rules feel wrong or confusing? Rolls, damage, hit points,
   turn order, spells, skill checks, inventory, quests, NPC attitudes.

3. The "Narrated by AI" label: noticed it? What did it make them think?

4. The result line shown before each narration: useful, ignored, confusing?
   Did it ever disagree with the narration?

5. Anything else: what was fun, what was boring, what they wanted to do
   but could not.
```

## 6. Summary

*To be filled in after the sessions. Until then this section is empty on purpose.*

The observations are anecdotal. They can guide fixes and give colour in the report's discussion, but they are not results and they never go into M1 to M6.

### 6.1 Sessions

| Sponsor | Days played | Scenarios tried | Build(s) |
|---|---|---|---|
| P1 | | | |
| P2 | | | |
| P3 | | | |
| P4 | | | |
| P5 | | | |

### 6.2 Where the story broke

### 6.3 Where the rules felt wrong

### 6.4 Reactions to the AI label

### 6.5 Reactions to the result line

### 6.6 Follow-ups

Any problem found becomes a GitHub issue, linked here, or the summary says "none". A fix to the engine, prompts or scenarios after the main run does not change the experiment's frozen specifications. Such a fix needs a `docs/decisions.md` entry like any other change.
