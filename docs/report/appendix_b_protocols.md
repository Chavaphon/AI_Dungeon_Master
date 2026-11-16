# Appendix B. Rubric, rating form and protocols

<!-- WBS 11.2 · Owner: CI · Reviewer (11.6): SS · Outline: docs/report_outline.md, Appendices · Draft 2026-11-16 -->

This appendix holds the texts the experiment was run and annotated with. The prompt templates (B.1) and the M5 rating form (B.3) are given verbatim. The divergence rubric (B.2) and the M3 protocol (B.4) are condensed; the frozen files in the repository are authoritative where the two differ.

| Text | Authoritative file | Frozen |
|---|---|---|
| Prompt templates | `config/prompts/`, hashes in `docs/prompt_templates.md` | v1.0, 2026-11-03, checked by `tests/orchestration/test_prompt_freeze.py` |
| Divergence rubric | `docs/rubric.md` | v1.0, 2026-11-08, git tag `rubric-v1.0`, hash in `tests/test_rubric.py` |
| M5 rating form | `docs/narrative_quality.md` | v0.9, confirmed 2026-11-08 |
| M3 protocol | `docs/intent_fidelity.md` | v0.9, confirmed 2026-11-08 |

## B.1 Prompt templates

Eleven files reach the model. The five condition templates fill the system message; `{summary}` and `{history}` are replaced by the two shared blocks, or dropped with their blank line when there is nothing to put in them; the player's input is the user message. The retry texts are sent as user messages after the model's rejected reply (Section 3.5). Each hash is the SHA-256 of the file as committed, UTF-8 with LF line endings and a trailing newline.

How the condition templates differ (`docs/prompt_templates.md` §2):

| From | To | Difference |
|---|---|---|
| A | B | B adds the state lead-in and state block after the preamble |
| B | C | C adds the four-line self-check after the history |
| B | D tool call | D adds the tools lead-in and tools block after the state block, and the tool-call instruction after the history |
| A | D narration | D narration adds the facts lead-in and facts block after the history; it holds no state and no tools |

<!-- templates:start -->

### B.1.1 `a.txt`

Condition A, the single narration call. `sha256:5363432c1efcce15a2cf03200d3169da7337bb49e799cf0d387b8ce6ea539997`

```text
You are the Dungeon Master for a text-based fantasy role-playing game.
Narrate in the second person, present tense. Keep each reply to 2-4 sentences.
Describe only what the player character could perceive.
Do not speak or act for the player character.
Do not use headings, lists, or dice notation in narration.
Keep violence non-graphic and suitable for players aged 8 and up.

{summary}

{history}
```

### B.1.2 `b.txt`

Condition B, the single narration call. `sha256:74f4e08ad453a9c92c27e8d2624b7f4fcd0ddf06d8eb3355a6c2fe6d05e2ffe6`

```text
You are the Dungeon Master for a text-based fantasy role-playing game.
Narrate in the second person, present tense. Keep each reply to 2-4 sentences.
Describe only what the player character could perceive.
Do not speak or act for the player character.
Do not use headings, lists, or dice notation in narration.
Keep violence non-graphic and suitable for players aged 8 and up.

The authoritative game state is given below as JSON. It is correct.
Your narration must be consistent with it.

<state>
{state_json}
</state>

{summary}

{history}
```

### B.1.3 `c.txt`

Condition C, the single narration call. `sha256:eabd73eba3acf4596dea8f76caf63b0f81e99c622fc5f458daa1403ab4a14e48`

```text
You are the Dungeon Master for a text-based fantasy role-playing game.
Narrate in the second person, present tense. Keep each reply to 2-4 sentences.
Describe only what the player character could perceive.
Do not speak or act for the player character.
Do not use headings, lists, or dice notation in narration.
Keep violence non-graphic and suitable for players aged 8 and up.

The authoritative game state is given below as JSON. It is correct.
Your narration must be consistent with it.

<state>
{state_json}
</state>

{summary}

{history}

Before you reply, check your narration against the state above:
every item you mention must be in the inventory, every character must
appear in the state, and any description of health must match the
recorded hit points. Revise silently, then give only the final narration.
```

### B.1.4 `d_toolcall.txt`

Condition D call 1, the tool call. `sha256:9fdff641299db28d9a20e6a7bf32e60328fc9bda4cc9042928fb5505ed895557`

```text
You are the Dungeon Master for a text-based fantasy role-playing game.
Narrate in the second person, present tense. Keep each reply to 2-4 sentences.
Describe only what the player character could perceive.
Do not speak or act for the player character.
Do not use headings, lists, or dice notation in narration.
Keep violence non-graphic and suitable for players aged 8 and up.

The authoritative game state is given below as JSON. It is correct.
Your narration must be consistent with it.

<state>
{state_json}
</state>

The tools you can call are defined below as JSON.

<tools>
{tools_json}
</tools>

{summary}

{history}

Decide the single game action that the player's input represents.
Reply with one JSON object and nothing else:
{"tool": "<tool name>", "arguments": { ... }}
If the input is pure conversation with no mechanical effect, reply
with exactly: {"tool": null}
```

### B.1.5 `d_narration.txt`

Condition D call 2, the narration. `sha256:ca3268f8a4d7e829612ac6911f7ae9e39ff3b3776c9cd8c8cc7930175eb3d100`

```text
You are the Dungeon Master for a text-based fantasy role-playing game.
Narrate in the second person, present tense. Keep each reply to 2-4 sentences.
Describe only what the player character could perceive.
Do not speak or act for the player character.
Do not use headings, lists, or dice notation in narration.
Keep violence non-graphic and suitable for players aged 8 and up.

{summary}

{history}

The rules engine has resolved the action. These facts are authoritative
and complete. Narrate them. Do not add mechanical outcomes that are not
listed, and do not contradict any value here.

<facts>
{narration_facts_json}
</facts>
```

### B.1.6 `summary_block.txt`

The rolling summary block, in every template above and in `summary.txt`. `sha256:64c838d372d42c17afee16198f55a731f0f0aa353464c922e2ee4dcc50cd00b0`

```text
Summary of earlier turns:

<summary>
{summary_text}
</summary>
```

### B.1.7 `history_block.txt`

The last K turns as a transcript, in every template above and in `summary.txt`. `sha256:1cf84e244bbd3d617fa367eb38f2aac51cde95ab6c59fa480f0b63b9253dbe23`

```text
The most recent turns of the game, oldest first:

<history>
{transcript}
</history>
```

### B.1.8 `summary.txt`

The rolling summary call (Section 3.6), the same in every condition. `sha256:81094be62cf34a3ce61e987a59784f1a101ba77d39a95692296ab3e788fc1590`

```text
You keep the running record of a text-based fantasy role-playing game.

{summary}

{history}

Write a new summary of the whole game so far, combining the earlier summary,
if there is one, with the turns above. Write one plain paragraph of under 150
words. Include only events, decisions the player made, and unresolved threads.
Do not state any numbers: no hit points, spell slots, item counts, dice,
difficulty or turn numbers. Do not add anything that is not in the summary or
the turns.
```

### B.1.9 `retry_unparseable.txt`

D tool-call retry after an unparseable reply (Section 3.5). `sha256:e7f360014720370353081965ff22c3cb577666656639f310ccda0c262b03adf8`

```text
Your reply could not be read as a tool call.
Expected one JSON object of the form {"tool": ..., "arguments": {...}}.
For example:
{"tool": "skill_check", "arguments": {"actor_id": "{pc_id}", "skill": "perception", "dc": 12}}
Reply with one JSON object for the player's input and nothing else.
```

### B.1.10 `retry_rejected.txt`

D tool-call retry after a rejection, carrying the full envelope (Section 3.5). `sha256:dd3d5f3cac3004820db9be72b3d56e4c994b0a4236fa089e73fc15f484943027`

```text
The rules engine rejected that call:
{rejection_json}
Fix the call using the message and valid_options above.
Reply with one corrected JSON object and nothing else.
```

### B.1.11 `retry_no_tool.txt`

D tool-call re-prompt after the turn's first `{"tool": null}` (Section 3.5). `sha256:e0494db2a54c46d37a4fc186e66245edb6ecd814c7cb5ca6ff8af17f9dda1a69`

```text
You replied {"tool": null}. Read the player's input again and select the tool
for the game action it describes. Reply with one JSON object and nothing else:
{"tool": "<tool name>", "arguments": { ... }}
Reply with exactly {"tool": null} again only if the input has no mechanical
effect at all.
```

<!-- templates:end -->

## B.2 Divergence rubric v1.0 (condensed)

**What is scored.** A divergence is a phrase in the narration that disagrees with the state. Condition D is scored against the state after the turn, with its narration facts and state diff; conditions A to C against the replayed ground truth for that turn (Section 4.1). In every condition the scenario definition is in scope: its display names, its locations, and the characters, groups and places that the text of its scripted inputs names. Weak prose, wrong tone and narration that acts for the player character are M5, not divergences.

**Categories.**

| Code | The narration... | Example (Lyra: 14 of 20 HP, short sword, two torches, two slots, no lantern) |
|---|---|---|
| `PHANTOM` | names an item, character or location in neither the state nor the scenario | "You raise your lantern…": 1 `PHANTOM` |
| `CONTRADICT` | conflicts with a recorded value: HP band, status, quest state, where an item is | "You stagger back, barely standing…": 1 `CONTRADICT` (`badly_hurt` phrase, band `wounded`) |
| `RESOURCE` | describes spending, gaining or using up a resource the state does not show | "You light your last torch…" with two torches: 1 `RESOURCE` |
| `RELATION` | treats an NPC in a way that does not fit its recorded stance | The `unfriendly` Keeper "beams and pulls you into a hug": 1 `RELATION` |

**Counting rules.**

1. Count every divergence, several per narration if there are several.
2. One phrase, one divergence: a phrase that fits several categories is recorded in the first that applies, in the order `PHANTOM`, `CONTRADICT`, `RESOURCE`, `RELATION`.
3. A repeat within one narration counts once.
4. Each turn is scored on its own; a repeat in a later turn counts again.
5. When in doubt, do not record.

**Hit-point bands.**

| Band | `current_hp / max_hp` | Lexicon used by the checker |
|---|---|---|
| `healthy` | above 0.75 | unhurt, unharmed, unscathed, fresh, barely a scratch, fine, uninjured |
| `wounded` | above 0.35, up to 0.75 | hurt, wounded, bleeding, bruised, battered, injured, sore |
| `badly_hurt` | above 0, up to 0.35 | barely standing, near death, dying, at death's door, close to collapse, gravely wounded, on the brink, failing |
| `unconscious` | 0 | unconscious, collapses, falls, out cold, senseless, crumples |

- A ratio of exactly 0.75 or 0.35 is in the lower band.
- Adjacent bands are not forgiven.
- A narration with no band phrase is not scored for band accuracy. Annotators judge band phrases by meaning; the checker uses only the lexicon.
- Not band phrases: events ("the blade wounds your arm"), negations ("far from dying"), figurative uses about something else ("the dying torchlight"), the past and the future, and effort or emotion ("panting").
- Intensity words decide the band: "badly wounded" is `badly_hurt`, "wounded" alone is `wounded`. A phrase that honestly fits two bands, one of them the actual band, is not a divergence; this applies to an ambiguous phrase, never to a clear phrase one band away.
- A phrase is scored against the HP after every effect of the turn, for the combatant it is about, and each combatant gets at most one band divergence per narration.
- Narrating a combatant at 0 HP as acting, or one above 0 HP as down, is one `CONTRADICT`.

**Borderline conventions.**

- **`PHANTOM`.**
  - Parts and features of a listed location, and parts of an in-scope entity, are in scope.
  - Scenery (dust, shadows, smells) is not an item. Something is an item when the narration lets it be picked up, used, given or spent.
  - An unseen presence ("a noise from somewhere above") is not an entity; "a guard shouts" is.
  - Too many of a kind is one `PHANTOM`: "three rats" when there are two, or "our missing ledgers" when there is one.
  - A character named in a scripted input may be described or given an invented personal name without a divergence.
- **`CONTRADICT`.**
  - Dialogue counts, and an NPC's false statement is still a divergence, since the game has no deception mechanic.
  - Quest state is scored by meaning: treating a completed or failed quest as open, a `not_started` quest as under way, or an `active` quest as completed or failed is a divergence. Progress towards an active quest's end is not.
- **`RESOURCE`.**
  - Quantity words ("your last torch") are claims; "a torch" is not.
  - Any narration of Fire Bolt draining magic is a divergence, since it costs nothing.
- **`RELATION`.**
  - Applies only to NPCs with a recorded stance, scored against the stance after the turn.
  - Behaviour that fits the stance or one step either side of it is not a divergence. Two or more steps away is.
  - A stance change narrated without the tool call is a divergence.

## B.3 M5 rating form

Verbatim from `docs/narrative_quality.md` §4. The rater sees an excerpt of five exchanges, identified by an opaque code and the scenario's title, and rates it once on each item.

> Read all five exchanges once, then rate **the excerpt as a whole** on each item. Use the anchors for 1, 3 and 5. A 2 or 4 is between them. Rate as a reader of the story:
>
> - Do not check the narration against the game rules or the state. M1 does that.
> - Do not mark down the player inputs. They are fixed by the script.
> - The Dungeon Master is told to narrate in the second person, present tense, 2–4 sentences, and never to speak or act for the player character (§9.1). Count a reply that breaks this under **tone**.

**Coherence: does it hang together?**

| Score | Anchor |
|---|---|
| 1 | Replies ignore the player's inputs or each other. Events, people or places change from one reply to the next without reason. Hard to follow. |
| 3 | Mostly follows the inputs and stays consistent, with one or two lapses: a forgotten detail, an odd jump, a reply that answers a different input. |
| 5 | Every reply follows from its input and from what came before. Nothing contradicts anything else in the excerpt. Easy to follow. |

**Vividness: can you picture it?**

| Score | Anchor |
|---|---|
| 1 | Generic and flat ("You attack. It is hurt."). No concrete detail. |
| 3 | Some specific detail of sight, sound or action, but much is stock phrasing or repeated. |
| 5 | Concrete, specific and varied detail throughout. The scene is easy to picture, without padding. |

**Tone appropriateness: does it sound right?**

| Score | Anchor |
|---|---|
| 1 | The voice does not fit: out of character, modern or assistant-like ("As an AI…", "Sure! Here's…"), wrong mood for the moment, or the narrator acts or speaks for the player. |
| 3 | Fits the fantasy game most of the time, with a lapse: a flat moment, a jarring word, the mood of a fight given to a quiet scene, or one reply that breaks the second-person voice. |
| 5 | A consistent Dungeon Master's voice that fits the game and each moment: tense in a fight, warm or cool with an NPC as the scene calls for. |

**Engagement: "Would you want to keep reading?"**

| Score | Anchor |
|---|---|
| 1 | Definitely not. |
| 2 | Probably not. |
| 3 | Not sure. |
| 4 | Probably yes. |
| 5 | Definitely yes. |

**Note.** Optional free text for anything that made a rating hard, or a hint about the condition.

## B.4 M3 intent-fidelity protocol (condensed)

**Scope.**

- Condition D turns of the main grid, excluding failed turns.
- Turns that ended with no call are included.
- Only the call that finally ran is judged; earlier attempts are M2.

**Sample.**

- One stratum per scenario.
- In each stratum, turns are ordered by `sha256("m3-v1/" + run_id + "/" + input_index)` as lowercase hex, and the first `ceil(0.15 × n)` are taken.
- If annotation had fallen behind, the first `ceil(0.10 × n)` of the same order would have been used; it did not.

**What the annotator sees.**

| Shown | Not shown |
|---|---|
| The player's input | The narration |
| The executed call, each identifier followed by its display name | The expected call |
| The state before the turn: the player character's inventory, NPC stances, quest states and stages, combatants and their status, and whether an encounter is active | The condition, the seed, earlier attempts and rejections |

**The question.** Does the executed call do what the player asked, as far as one call in this game can? The answer is `faithful` or `unfaithful`; there is no third value.

**Rules, in order.** The first rule that settles the turn decides it.

1. **No mechanical request, no call.** If the request asks for nothing the seven tools do (looking around, talking, asking, waiting), no call is faithful, and so is a skill check on an observation request. A call that changes state is unfaithful.
2. **A mechanical request needs a call.** If the request asks for something a tool does, no call is unfaithful.
3. **The right tool.** The tool must be one a reasonable reading of the request leads to. "I raise my shield" may be Dodge or no call; "I attack the rat" must be an attack or, for a caster, Fire Bolt.
4. **The right arguments.** The target, weapon, item, NPC and quest named or clearly meant, and the spell, skill, stance direction, quest transition and the sign and size of an inventory change, must match. The DC and the wording of a justification are not judged.
5. **Several actions in one request.** The call must do the action the request is for: its last stated goal, unless that goal depends on an earlier step the game rolls for. "I sneak past the guard and grab his keys" with only a stealth check is unfaithful; "I try to sneak past the guard" with a stealth check is faithful. When the goal is something no tool can do, a call that does the part a tool can do is faithful.
6. **When in doubt, faithful.** If two readings are reasonable and the call fits one, it is faithful; the other reading goes in the note.

**Reason codes.** Each unfaithful verdict takes the first that applies:

| Code | The call... | Rule |
|---|---|---|
| `MISSED` | is no call, but the request asked for something a tool does | 2 |
| `INVENTED` | changes state the request did not ask to change | 1 |
| `WRONG_TOOL` | uses a tool no reasonable reading leads to | 3 |
| `WRONG_TARGET` | names the wrong combatant, weapon, item, NPC or quest | 4 |
| `WRONG_VALUE` | has the wrong spell, skill, direction, transition or quantity | 4 |
| `DROPPED` | does one part of a multi-part request but not the part it is for | 5 |

**Worked examples.**

| Player input | Executed call | Verdict |
|---|---|---|
| "I accept the bottle of cider the stallholder presses into my hands" | `modify_inventory(pc_nia, item_cider, +1)` | faithful |
| same | no call | unfaithful, `MISSED` |
| "I tell Master Orlo I will guard his wagons as far as the border fort" | `update_quest(quest_border_caravan, advance)` | unfaithful, `WRONG_VALUE` (taking on a quest is `start`) |
| "I tell the harbour master he is a thief" | `update_npc_relationship(npc_harbour_master, up, …)` | unfaithful, `WRONG_VALUE` |
| "I sneak up on the boar while it is busy rooting in the turnips" | `attack(pc_nia, npc_boar, item_spear)` | unfaithful, `WRONG_TOOL` |
| "I raise my guard as both bandits rush me" | no call | faithful (rule 6) |
