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

In the event, each sponsor played one session, and the summary was written after the fifth (`docs/decisions.md`, 2026-11-17).

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

Written on 2026-11-17 from the five feedback sheets, after one session per sponsor.

The observations are anecdotal. They can guide fixes and give colour in the report's discussion, but they are not results and they never go into M1 to M6.

### 6.1 Sessions

| Sponsor | Days played | Scenarios tried | Turns (log records) | Finished | Build(s) |
|---|---|---|---|---|---|
| P1 | 1 (12 Nov) | `s01_cellar`, seed 101 | about 10 | no | `main` @ `dab6ff4` |
| P2 | 1 (13 Nov) | `s02_toll_bridge`, seed 102 | 21 | no | `main` @ `24c896f` |
| P3 | 1 (13 Nov) | `s03_forest_shrine`, seed 103 | 13 | no | `main` @ `174b076` |
| P4 | 1 (13 Nov) | `s04_goblin_warren`, seed 104 | 54 | no | `main` @ `174b076` |
| P5 | 1 (17 Nov) | `s05_wayside_inn`, seed 105 | 17 | no | `main` @ `1603d16` |

All five consented. The builds differ only in `adm/eval`, docs and tests, so every sponsor played the same engine, orchestration, CLI, prompts, model configuration and scenarios. Turn counts include failed turns. P1's log was read once, for debugging only, to explain P1's two reports; the other logs were not read beyond their line counts, so their notes below rest on the scenario files and the rules and are marked "likely" where they guess at what the model did. Nobody finished a scenario, and nobody tried a long one.

### 6.2 Where the story broke

- **Powers and people the rules do not have.** P2 meditated and gained "wind bending power"; P3 talked to a god and became a demi-god; P4 handed an invented "Elara" to the goblins and "was able to destroy the landscape". None of these has a tool, so the model most likely proposed `{"tool": null}` and the narration call ran with no facts from the player's action to hold it back (CLAUDE.md §9.1: D's narration sees the facts only). This is the condition D weakness the experiment measures: its facts constrain what the engine resolved and nothing else.
- **Narration that ignored the facts.** In P1's log the rats' bites were in the narration facts and never narrated, a missed attack (10 against AC 12) was narrated as the rat exploding, and a dragon invented at turn 2 was repeated from then on. P2 and P4 also said the result line and the story disagreed at times (§6.5).
- **No break.** P5 said the story "make sense and follow what I input".

These reports match the M1 finding that condition D does not narrate fewer divergences than condition A (`docs/m1_rates.md`). They illustrate it; they are not evidence for it.

### 6.3 Where the rules felt wrong

- **Silently misparsed intent** (CLAUDE.md §7.2). In P1's log, "kill myself" became `modify_inventory` of Lyra's short sword by −1, which left Lyra with no weapon and every later attack rejected, and "Run downstair" became a torch `+1`. P2's "Tornado" became a longsword attack, the only legal action of a non-caster. P2's negotiation with "Griselda", who is not in `s02_toll_bridge`, likely became a one-step `down` for Hessa, the only NPC with a relationship. Each call was valid, so the validator could not stop it; this is what M3 samples.
- **Items from nowhere.** P4 reported an "infinite wedding ring + spoon glitch", and P1 gained a torch. `modify_inventory` with a positive `delta` is legal for any defined item any number of times: the "no transfer, no stealing" rule of CLAUDE.md §6.1 binds scenario authors, and the engine has no rule on where an item comes from. Likely repeated `+1` calls in P4's case; the log was not read.
- **Things the game cannot do, by design.** P5 could not flirt with Bess: there is no romance mechanic, and an NPC's attitude moves one stance step per call with a justification (CLAUDE.md §5.2). P4 could not summon another creature: no tool creates a combatant (CLAUDE.md §4.8). P2's wind power and Tornado need spells a non-caster cannot cast (CLAUDE.md §4.6).
- **A quest that could not be found.** P3 looked for a quest. `s03_forest_shrine`'s one quest starts only when the player agrees to fetch the relic for the hermit, and `play` has no quest or inventory command: a quest appears only in the result line when `update_quest` runs.

### 6.4 Reactions to the AI label

Nobody learned anything from it. P1 did not notice it, and P2, P3 and P4 said they already knew the narrator was an AI, P2 "from the way the dungeon master responded". P5 had no comment. Nobody found it off-putting.

### 6.5 Reactions to the result line

Three of the five found it useful: P2, P3 ("very helpful") and P5 ("very useful"). P1 ignored it. P4 found it not useful. P2 and P4 said it sometimes disagreed with the story. The line is built from the turn's audit record (CLAUDE.md §15 item 42), so when the two disagree it is the narration that is wrong; the line made the divergence visible to the player, which is what it is for.

### 6.6 Anything else

P1 called it "very fun imaginative game for imaginative people", and P4 "very fun, not boring". P2 wanted a picture of the scene and P3 "can not picture the current scene"; images, maps and any graphical client are out of scope (CLAUDE.md §14), so the only sense of place is the opening narration and 2-4 sentence replies.

### 6.7 Follow-ups

Any problem found becomes a GitHub issue, linked here, or the summary says "none". A fix to the engine, prompts or scenarios after the main run does not change the experiment's frozen specifications. Such a fix needs a `docs/decisions.md` entry like any other change.

None. The engine behaved as specified in every report checked (P1's log). Invented powers and narration that ignores the facts are model behaviour that M1 already measures, misparsed intent is what M3 samples, and the missing mechanics and pictures are out of scope by design. Items from nowhere follow from `modify_inventory` as specified; a provenance rule would change the frozen tool contract after the main run, so the team chose no issue. The report's discussion (WBS 11.4) may use §6.2 and §6.3 as colour.
