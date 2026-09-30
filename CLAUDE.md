# CLAUDE.md — AI Dungeon Master

Working specification for the KMUTT IS&A project *AI Dungeon Master: A Hybrid Rule-Engine and LLM-Based Game Master System*.

This file is the single source of truth for implementation. If something here contradicts the proposal PDF, **this file wins** and the contradiction should be raised with the team. If something is genuinely not specified here, stop and ask rather than inventing it — the evaluation depends on details being fixed, not reasonable.

---

## 1. What this project is

A text-based Dungeon Master for a stripped-down D&D-style game. A local language model produces narration and dialogue. A deterministic Python rules engine owns all game state and resolves all mechanics.

**The one rule that governs the whole design:**

> The language model never writes to game state. It may only propose tool calls. The engine validates them, executes them, and returns the outcome. The model then narrates that outcome.

The project's research contribution is not the system, it is the measurement: how far the *narration* drifts from the *state*, under four levels of grounding. So anything that makes runs non-reproducible or makes the audit log incomplete is a correctness bug, not a nice-to-have.

### 1.1 Non-negotiable invariants

Violating any of these breaks the experiment. Each should have at least one test.

1. State is mutated only inside `engine/`, only through a validated tool call.
2. Every state mutation appends a record to the audit log, with a before/after diff.
3. Every dice roll comes from the single seeded RNG instance. No bare `random.*` anywhere.
4. The same `(seed, scenario_id, condition)` triple reproduces a byte-identical run.
5. `0 <= current_hp <= max_hp` holds after every write.
6. The model's raw output is never parsed into state directly. It is parsed into a *proposed tool call*, which is then validated.
7. Conditions A, B, C and D differ only in the prompt template and whether tools are wired. The engine, scenario, seed and context strategy are identical across them.

### 1.2 Agentic engineering design principles

This project follows the **SPECIFY-HARNESS-VERIFY-CONTROL** discipline for agentic system engineering (introduced in proposal v4, Section 8.0). Each principle maps directly onto decisions already fixed in this document. When in doubt about why a design decision exists, trace it to its principle here.

| Principle | What it means | Where it appears in this design |
|---|---|---|
| **SPECIFY** | Define explicit, testable, complete behaviour — goal, edge cases, acceptance criteria | Tool contract (section 6): seven tools with typed parameters, return shapes and enumerated rejection codes. Failure pipeline (section 7.1): every failure mode named and handled. The 60-case rule suite (section 13) and the success criteria table in the proposal are the acceptance criteria. Behaviour is explicit, testable and complete. |
| **HARNESS** | What the agent can access: tools (capability), connections, execution guidelines | The rules engine is the harness. The model can read state (injected in prompts B, C, D) but **cannot write** — all writes go through validated tool calls. The tool set (section 6) defines capability; the validator (section 6.3) enforces which tool calls are legal; the context assembly procedure (section 8) is the execution guideline that tells the model exactly how its work gets done. |
| **VERIFY** | Layered checking: deterministic tests → evaluation set → critic → human review | The four-condition experimental ladder maps directly onto the verification pyramid. The 60-case rule suite and automated checker (section 10.3) are the deterministic test base. The twelve scenario suite is the evaluation set. The M3 intent-fidelity sample (section 10.4) is the critic — an active search for failures invisible to the automated checker. Human rubric annotation (M1, M5) is the top layer. |
| **CONTROL** | Least privilege, spending limits, kill switch | The model has read access to state and narration capability — nothing more. All writes are mediated by the engine. The retry budget of 2 (section 7.1) is the spending limit; budget exhaustion routes to a safe, logged turn-failure rather than an uncontrolled loop. The `turn_failure` record is the kill switch: the turn does not advance, initiative does not move, and the failure is counted, not hidden. |

---

## 2. Environment and commands

- Python 3.11
- Local inference: [Ollama](https://ollama.com) serving one open-weight instruct model
- No paid API. No network calls to any model provider.

```bash
# setup
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# quality gates (must both pass before any commit)
pytest -q
ruff check . && ruff format --check .

# play a session interactively
python -m adm.cli play --scenario scenarios/s01_cellar.json --seed 12345

# run one scripted scenario under one condition
python -m adm.cli run --scenario scenarios/s01_cellar.json --condition D --seed 12345

# run the full experiment grid (unattended, resumable)
python -m adm.cli batch --manifest experiments/main_grid.json

# score transcripts
python -m adm.eval.checker --runs runs/ --out results/automated.jsonl
```

### 2.1 Dependencies

Runtime: `pydantic>=2`, `jsonschema`, `httpx`, `typer`, `rich`.
Dev: `pytest`, `pytest-cov`, `ruff`, `hypothesis`.
Analysis: `pandas`, `numpy`, `scipy`, `matplotlib`, `krippendorff`.

Do not add dependencies without a note in `docs/decisions.md`.

### 2.2 Model configuration

Model choice is frozen in `config/model.json` after the Week 2 benchmark. Until then use the placeholder below and **never hardcode a model name anywhere else**.

```json
{
  "model": "TBD_AFTER_BENCHMARK",
  "quantisation": "TBD",
  "context_tokens": 8192,
  "K_verbatim_turns": 8,
  "temperature": 0.7,
  "narration_max_tokens": 300,
  "toolcall_max_tokens": 200,
  "seed": null
}
```

`temperature` is 0.7 for narration and **0.0 for tool-call generation**. Two different sampling settings, one model. This is deliberate: narration wants variety, tool selection does not.

### 2.3 Task tracking

GitHub issues are the only place task status lives. There is one issue per WBS task, titled `[WBS x.y] <task>`, with its `wp-NN-*` label, its owner as assignee, and a weekly milestone (`W1` to `W7`). Dependencies are recorded as "blocked by" links on the issue.

- Before starting a task, check that every issue blocking it is closed.
- Close an issue through its pull request (`Closes #N`), not by hand.
- `TASK_CHECKLIST.md` and the WBS workbook (`AI_Dungeon_Master_WBS_NEW.xlsx`) are **read-only references** for the schedule, gates, deliverables and risk register. Do not tick boxes or update the workbook's Status column to record progress. The workbook's effort recalculation is retired.
- A new, split or re-scoped task needs a new issue and a `docs/decisions.md` entry.

---

## 3. Repository layout

```
adm/
  engine/
    state.py          # GameState, Combatant, Item, Quest, NPCRelationship models
    dice.py           # DiceRoller, seeded; XdY+Z parser
    combat.py         # initiative, attack, dodge, turn advance
    spells.py         # fire_bolt, cure_wounds, slot accounting
    checks.py         # skill checks
    inventory.py
    quests.py
    relationships.py
    tools.py          # tool definitions, dispatch table
    validator.py      # schema + precondition checks, rejection codes
    audit.py          # turn records, state diffs, JSONL writer
  orchestration/
    client.py         # Ollama HTTP wrapper, timeouts, retries
    prompt.py         # context assembly, the four condition templates
    parser.py         # model output -> proposed tool call
    summary.py        # rolling summary
    safety.py         # output filter
    loop.py           # the turn loop, failure pipeline, retry budget
  eval/
    checker.py        # automated divergence + rule violation detection
    bands.py          # HP band lexicon and classification
    metrics.py        # M1-M6 computation
    annotate.py       # blind, condition-shuffled annotation CLI
  cli.py
config/
  model.json
  prompts/            # a.txt b.txt c.txt d_toolcall.txt d_narration.txt
scenarios/            # s01..s12 + long01..long04
experiments/          # run manifests
runs/                 # audit logs, gitignored
results/              # scored output, gitignored
tests/
docs/
  decisions.md        # dated decision log; every deviation goes here
```

---

## 4. Game rules specification

This is a deliberately small ruleset. Implement exactly this, no more. It is *inspired by* the D&D 5e SRD 5.1 (CC-BY-4.0) but is not compatible with it and should not be described as 5e.

### 4.1 Characters and derived values

| Quantity | Rule |
|---|---|
| Ability scores | Integers 1–20. Six scores: `str`, `dex`, `con`, `int`, `wis`, `cha`. Stored in the scenario, never rolled at runtime. |
| Ability modifier | `floor((score - 10) / 2)`. Use `math.floor`, not integer division, so negatives round correctly: score 7 → −2. |
| Proficiency bonus | Fixed `+2` for every combatant. No levels in this game. |
| Armour class | Stored directly per combatant as an integer, typically 10–18. **Not** derived from armour or dexterity. |
| Hit points | `max_hp` from scenario; `current_hp` clamped to `[0, max_hp]` after every write. |
| Attack bonus | Stored per weapon as `attack_bonus`, already including ability and proficiency. Do not recompute it. |
| Spell attack bonus | Stored per combatant as `spell_attack_bonus`. |
| Spellcasting modifier | Stored per combatant as `spellcasting_modifier`. Used only by Cure Wounds. |

Storing bonuses rather than deriving them is intentional. It removes a whole class of arithmetic bugs from the engine and keeps scenario authoring explicit.

### 4.2 Dice

`DiceRoller` wraps exactly one `random.Random(seed)`. Notation `XdY+Z`:

- `X` in 1..20, `Y` in {4, 6, 8, 10, 12, 20, 100}, `Z` any integer, `+Z` optional.
- Anything else raises `InvalidDiceNotation`.
- Every roll returns a `RollResult`: `{notation, individual_dice: [int], modifier: int, total: int, advantage_mode: "normal"|"advantage"|"disadvantage"}`.
- Every `RollResult` produced during a turn is attached to that turn's audit record.

### 4.3 Advantage and disadvantage

- Advantage: roll `2d20`, take the higher.
- Disadvantage: roll `2d20`, take the lower.
- **If both apply, they cancel and you roll a single `d20`.** They do not stack; two sources of advantage are still just advantage.
- Both dice are recorded in `individual_dice`, in the order rolled.

Sources in this game: the target is Dodging (disadvantage for the attacker), or the scenario explicitly grants advantage/disadvantage on a skill check.

### 4.4 Initiative and turn order

- Rolled once at encounter start: `d20 + dex_modifier` per combatant.
- Ties broken by, in order: higher `dex` score, then lexicographically smaller `combatant_id`. This makes order fully deterministic from the seed.
- Order is fixed for the whole encounter. Combatants who fall unconscious keep their slot but are skipped.
- `round_number` starts at 1 and increments when the order wraps.
- `active_combatant_id` names whose turn it is. A tool call from anyone else is rejected with `NOT_YOUR_TURN`.

### 4.5 Actions

Exactly three. One action per turn. There is **no movement, no positioning, no range and no map** — every combatant is assumed to be within reach of every other. This is why Dash does not exist in this game.

**Attack**

1. Roll `d20 + weapon.attack_bonus` against `target.armour_class`, with disadvantage if the target is Dodging.
2. Natural 20 on the d20 (after advantage/disadvantage selection): automatic hit and a critical.
3. Natural 1: automatic miss, regardless of bonuses.
4. On hit, damage = `weapon.damage_dice + weapon.damage_bonus`, minimum 0.
5. On a critical, roll the damage dice **twice** and add the modifier **once**. `1d8+3` critical = `2d8+3`.
6. Subtract from `target.current_hp`, clamped at 0.
7. If `current_hp` reaches 0, set `status = "unconscious"` (see 4.8).

**Cast Spell** — see 4.6. Only two spells exist.

**Dodge**

- Sets `dodging = true` on the actor.
- Cleared at the **start of that actor's next turn**, not at the end of the round. A combatant who dodges keeps the benefit through everyone else's turns.
- Attacks against a dodging combatant are made with disadvantage.

### 4.6 Spells

Exactly two spells are supported. A `cast_spell` call naming anything else is rejected with `SPELL_NOT_SUPPORTED`.

**`spell_fire_bolt`** — cantrip
- Ranged spell attack: `d20 + caster.spell_attack_bonus` vs `target.armour_class`.
- Damage `1d10` fire on hit. Critical doubles to `2d10`.
- Costs no resource. Usable every turn.
- Same natural 20 / natural 1 rules as a weapon attack.

**`spell_cure_wounds`** — level 1
- No attack roll. Always succeeds if it passes validation.
- Heals `1d8 + caster.spellcasting_modifier`, minimum 1.
- Consumes one level-1 slot: `caster.spell_slots_1 -= 1`. Rejected with `NO_SPELL_SLOT` if zero.
- `target.current_hp = min(current_hp + healed, max_hp)`. Record both the rolled amount and the amount actually applied; they differ at the cap and the checker cares about the difference.
- May target an unconscious combatant. Doing so sets `status = "active"` (see 4.8).
- May target a combatant already at full HP; the heal applies 0 and the slot is still spent.

**Spell slots** do not recover during a session. There is no short or long rest. Sessions are single encounters or short chains of encounters within one scenario.

### 4.7 Skill checks

Three skills only: `strength`, `perception`, `stealth`. Anything else is rejected with `SKILL_NOT_SUPPORTED`.

- `strength` uses the `str` modifier, `perception` uses `wis`, `stealth` uses `dex`.
- Roll `d20 + ability_modifier + (proficiency_bonus if the combatant is proficient in that skill else 0)`.
- Success if `total >= dc`. `dc` must be in 5..25 or the call is rejected with `DC_OUT_OF_RANGE`.
- Skill checks do not consume the turn action and may be called outside combat.

### 4.8 Zero hit points, unconsciousness, encounter end

There are **no death saving throws** and no death.

- At 0 HP: `status = "unconscious"`. The combatant is skipped in turn order and cannot act.
- An unconscious combatant **cannot be attacked**. `attack` and `cast_spell` with a damaging spell targeting them are rejected with `TARGET_UNCONSCIOUS`. This is a simplification, chosen to avoid needing death rules; it is a deliberate deviation from tabletop convention and should be stated in the report.
- Cure Wounds on an unconscious combatant restores HP and sets `status = "active"`. They act on their next turn in the existing initiative order.
- The encounter ends when either every hostile is unconscious (`outcome: "victory"`) or the player character is unconscious (`outcome: "defeat"`).
- When an encounter ends, further combat tool calls are rejected with `ENCOUNTER_OVER`.

---

## 5. State schema

One JSON file per run, versioned. Validate against `schemas/state.schema.json` on load and after every write.

```json
{
  "schema_version": "1.0",
  "scenario_id": "s01_cellar",
  "seed": 12345,
  "turn_number": 7,
  "round_number": 3,
  "active_combatant_id": "pc_lyra",
  "initiative_order": ["npc_rat_01", "pc_lyra", "npc_rat_02"],
  "encounter_active": true,
  "encounter_outcome": null,

  "combatants": {
    "pc_lyra": {
      "combatant_id": "pc_lyra",
      "display_name": "Lyra",
      "is_player_character": true,
      "faction": "party",
      "abilities": {"str": 12, "dex": 16, "con": 14, "int": 10, "wis": 13, "cha": 11},
      "proficient_skills": ["stealth"],
      "armour_class": 14,
      "max_hp": 20,
      "current_hp": 14,
      "status": "active",
      "dodging": false,
      "spell_attack_bonus": 5,
      "spellcasting_modifier": 3,
      "spell_slots_1": 2
    }
  },

  "inventory": {
    "pc_lyra": {"item_short_sword": 1, "item_torch": 2}
  },

  "item_definitions": {
    "item_short_sword": {
      "item_id": "item_short_sword",
      "display_name": "short sword",
      "is_weapon": true,
      "attack_bonus": 5,
      "damage_dice": "1d6",
      "damage_bonus": 3
    },
    "item_torch": {
      "item_id": "item_torch",
      "display_name": "torch",
      "is_weapon": false
    }
  },

  "npc_relationships": {
    "npc_keeper": {
      "npc_id": "npc_keeper",
      "display_name": "the Keeper",
      "stance": "neutral",
      "history": [
        {"turn": 4, "from": "unfriendly", "to": "neutral",
         "justification": "Lyra returned the stolen ledger."}
      ]
    }
  },

  "quests": {
    "quest_missing_ledger": {
      "quest_id": "quest_missing_ledger",
      "display_name": "The Missing Ledger",
      "state": "active",
      "stage": 2,
      "max_stage": 3
    }
  }
}
```

### 5.1 Identifier convention

`snake_case`, prefixed by kind, unique within a scenario:
`pc_*`, `npc_*`, `item_*`, `quest_*`, `spell_*`.

The prefix is load-bearing: the divergence checker uses it to decide what kind of entity a narration mention should be matched against. Do not invent other prefixes.

### 5.2 Enumerations

| Field | Allowed values |
|---|---|
| `status` | `active`, `unconscious` |
| `faction` | `party`, `hostile`, `neutral` |
| `stance` | `hostile`, `unfriendly`, `neutral`, `friendly`, `allied` |
| `quest.state` | `not_started`, `active`, `completed`, `failed` |
| `encounter_outcome` | `null`, `victory`, `defeat` |

The stance ladder is ordered as written. A single change may move **one step only**.

Legal quest transitions: `not_started → active`, `active → active` (stage increment), `active → completed`, `active → failed`. Everything else is rejected with `ILLEGAL_QUEST_TRANSITION`. `stage` may only increase, and never beyond `max_stage`.

---

## 6. Tool contract

Seven tools. These definitions are the contract given to the model and enforced by the validator. Keep the two in sync by generating the model-facing JSON schema from the same source.

*(SPECIFY artefact — this section, together with section 7.1 and the success criteria table in the proposal, constitutes the complete specification required under the SPECIFY principle.)*

### 6.1 Signatures

| Tool | Parameters | Returns |
|---|---|---|
| `attack` | `attacker_id: str`, `target_id: str`, `weapon_id: str` | `AttackResult` |
| `cast_spell` | `caster_id: str`, `spell_id: str`, `target_id: str` | `SpellResult` |
| `dodge` | `actor_id: str` | `DodgeResult` |
| `skill_check` | `actor_id: str`, `skill: str`, `dc: int` | `CheckResult` |
| `modify_inventory` | `actor_id: str`, `item_id: str`, `delta: int` | `InventoryResult` |
| `update_npc_relationship` | `npc_id: str`, `direction: str`, `justification: str` | `RelationshipResult` |
| `update_quest` | `quest_id: str`, `transition: str` | `QuestResult` |

`direction` is `"up"` or `"down"`. `transition` is `"start"`, `"advance"`, `"complete"` or `"fail"`. `justification` must be a non-empty string of at least 10 characters.

### 6.2 Result envelopes

Every tool returns the same outer shape. The narration prompt receives `narration_facts` and nothing else from the result — this is what forces the model to describe rather than invent.

```json
{
  "ok": true,
  "tool": "attack",
  "narration_facts": {
    "attacker": "Lyra",
    "target": "giant rat",
    "hit": true,
    "critical": false,
    "attack_roll": 17,
    "target_ac": 12,
    "damage": 7,
    "target_hp_before": 11,
    "target_hp_after": 4,
    "target_hp_max": 11,
    "target_hp_band": "badly_hurt",
    "target_status": "active"
  },
  "state_diff": [
    {"path": "combatants.npc_rat_01.current_hp", "from": 11, "to": 4}
  ],
  "rolls": [
    {"notation": "1d20+5", "individual_dice": [12], "modifier": 5, "total": 17,
     "advantage_mode": "normal"},
    {"notation": "1d6+3", "individual_dice": [4], "modifier": 3, "total": 7,
     "advantage_mode": "normal"}
  ]
}
```

`target_hp_band` is computed by the engine and handed to the model deliberately, so that a band error in the narration is the model's fault and not an inference problem. See section 9.2.

Rejection:

```json
{
  "ok": false,
  "tool": "attack",
  "rejection_code": "TARGET_UNCONSCIOUS",
  "message": "npc_rat_01 is unconscious and cannot be attacked.",
  "valid_options": {"target_id": ["npc_rat_02"]},
  "retry_allowed": true
}
```

`valid_options` is populated wherever the engine can cheaply enumerate what *would* have been legal. It matters: it is the main thing that lets a weak local model recover on its second attempt.

### 6.3 Rejection codes

Complete list. Do not add one without updating this table and `docs/decisions.md`.

| Code | Raised when |
|---|---|
| `SCHEMA_VIOLATION` | Missing parameter, wrong type, unknown parameter |
| `UNKNOWN_ENTITY` | Any id not present in the current state |
| `NOT_YOUR_TURN` | `actor_id != active_combatant_id` during an active encounter |
| `ACTOR_UNCONSCIOUS` | The acting combatant is unconscious |
| `TARGET_UNCONSCIOUS` | Damaging action against an unconscious target |
| `WEAPON_NOT_IN_INVENTORY` | `weapon_id` not held by the attacker |
| `NOT_A_WEAPON` | `weapon_id` exists but `is_weapon` is false |
| `SPELL_NOT_SUPPORTED` | `spell_id` is not one of the two supported spells |
| `NO_SPELL_SLOT` | Cure Wounds with `spell_slots_1 == 0` |
| `SKILL_NOT_SUPPORTED` | Skill outside the three supported |
| `DC_OUT_OF_RANGE` | `dc < 5` or `dc > 25` |
| `ITEM_NOT_DEFINED` | `item_id` absent from `item_definitions` |
| `NEGATIVE_QUANTITY` | Inventory change would drop below zero |
| `RELATIONSHIP_STEP_TOO_LARGE` | Change of more than one step, or beyond the ends of the ladder |
| `MISSING_JUSTIFICATION` | Justification absent or under 10 characters |
| `UNKNOWN_QUEST` | `quest_id` absent from state |
| `ILLEGAL_QUEST_TRANSITION` | Transition not permitted from the current quest state |
| `ENCOUNTER_OVER` | Combat action after the encounter has resolved |

---

## 7. The turn loop

Two model calls per player turn. This is a loop, not a pipeline — the architecture diagram in the report must show it as one.

```
receive player free-text input
  |
  v
assemble context  (section 8)
  |
  v
MODEL CALL 1  (temperature 0.0)  -> proposed tool call
  |
  v
parse  -> validate  -> execute
  |            |
  |            +--> rejected: structured error back to the model, retry
  |                 (budget: 2 retries, then fallback)
  v
MODEL CALL 2  (temperature 0.7)  -> narration, given narration_facts only
  |
  v
safety filter -> render -> append turn record to audit log
```

### 7.1 Failure pipeline

Retry budget is **2** attempts after the first, so 3 model calls maximum for the tool phase.

*(CONTROL artefact — the budget is the spending limit; exhaustion routes to a safe logged state, not an uncontrolled loop. The `turn_failure` record is the kill switch.)*

| Failure | Response | On budget exhaustion |
|---|---|---|
| Output is not parseable as a tool call | Return the expected format with one example; retry | Turn does not advance. Ask the player to rephrase. Log `turn_failure: unparseable`. |
| `SCHEMA_VIOLATION` | Return the offending field and expected type; retry | As above, `turn_failure: schema`. |
| `UNKNOWN_ENTITY` | Return the error plus `valid_options`; retry | As above, `turn_failure: unknown_entity`. |
| Any state-precondition rejection | Return the reason, the relevant current state values, and `valid_options`; retry | As above, `turn_failure: precondition`. |
| No tool call produced when the input clearly needs one | Re-prompt **once** with an explicit instruction to select a tool | Treat as a narration-only turn. Log `narration_only: true`. |

A turn that fails does **not** increment `turn_number` and does **not** advance initiative. It is still written to the audit log. Turn failures are a reported metric, not an embarrassment to hide.

### 7.2 Silently misparsed intent

The dangerous failure is not a rejected call, it is a *valid* call that does not match what the player asked for. Player writes "I sneak past the guard and grab his keys", model emits a clean `skill_check(stealth)` and drops the keys. The validator sees nothing wrong.

This cannot be detected automatically. Do not try. Record enough in the turn record (raw player input, raw model output, executed call) for a human to judge it later, and leave it to the M3 intent-fidelity annotation.

---

## 8. Context assembly

Order matters — the stable prefix goes first so it stays identical across turns.

1. System prompt (condition-specific, from `config/prompts/`)
2. Tool definitions (conditions D only)
3. Current state, injected as JSON (conditions B, C, D)
4. Rolling summary of turns older than K
5. Last `K` turns verbatim, oldest first
6. Current player input

*(HARNESS artefact — this procedure is the execution guideline: it defines exactly what context the model receives and in what order.)*

`K` defaults to 8 and is frozen in `config/model.json` after benchmarking. **If the assembled prompt would exceed `context_tokens`, reduce K for that turn and log it.** Never silently truncate from the middle.

### 8.1 Rolling summary

- Regenerated every `K` turns by a separate model call at temperature 0.0.
- Hard cap 200 tokens. If the model exceeds it, truncate at a sentence boundary and log.
- The summary prompt asks only for events, decisions and unresolved threads. It must not restate numeric state, because the state file is injected separately and a stale number in the summary is a divergence source of our own making.
- Every regeneration is written to the audit log.

---

## 9. Experimental conditions

Four conditions. They must differ **only** as described. Any other difference is a confound and invalidates the comparison.

*(VERIFY artefact — the four conditions constitute the evaluation set layer of the verification pyramid. Together with the rule suite at the base and the M3 critic above, they form the complete VERIFY strategy.)*

| Condition | State in prompt | Self-check instruction | Tools and engine |
|---|---|---|---|
| A | no | no | no |
| B | yes | no | no |
| C | yes | yes | no |
| D | yes | no | yes |

Conditions A–C produce narration only, in a single model call. There is no tool phase and no state mutation; the state file, where present, is read-only context. Condition D is the full two-call loop.

For A–C, the "state" used for scoring is the state the *scenario script* says should hold at that turn, computed by replaying the scripted inputs through the engine offline. This is the ground truth the narration is compared against.

### 9.1 Prompt templates

These are frozen. Store them verbatim in `config/prompts/` and change them only with a decision-log entry. The shared block is identical in all four.

**Shared preamble (all conditions)**

```
You are the Dungeon Master for a text-based fantasy role-playing game.
Narrate in the second person, present tense. Keep each reply to 2-4 sentences.
Describe only what the player character could perceive.
Do not speak or act for the player character.
Do not use headings, lists, or dice notation in narration.
```

**A — `a.txt`** — preamble only, then the conversation.

**B — `b.txt`** — preamble, then:

```
The authoritative game state is given below as JSON. It is correct.
Your narration must be consistent with it.

<state>
{state_json}
</state>
```

**C — `c.txt`** — preamble, then the B state block, then:

```
Before you reply, check your narration against the state above:
every item you mention must be in the inventory, every character must
appear in the state, and any description of health must match the
recorded hit points. Revise silently, then give only the final narration.
```

**D — `d_toolcall.txt`** (call 1, temperature 0.0) — preamble, state block, tool definitions, then:

```
Decide the single game action that the player's input represents.
Reply with one JSON object and nothing else:
{"tool": "<tool name>", "arguments": { ... }}
If the input is pure conversation with no mechanical effect, reply
with exactly: {"tool": null}
```

**D — `d_narration.txt`** (call 2, temperature 0.7) — preamble, then:

```
The rules engine has resolved the action. These facts are authoritative
and complete. Narrate them. Do not add mechanical outcomes that are not
listed, and do not contradict any value here.

<facts>
{narration_facts_json}
</facts>
```

Note that D's narration call does **not** receive the full state, only the facts. This is the architecture, not an oversight.

---

## 10. Divergence rubric and the automated checker

This is the measurement instrument. Its thresholds must be fixed before any scoring begins, and frozen once the pilot is done.

### 10.1 The four categories

| Code | Category | Definition |
|---|---|---|
| `PHANTOM` | Phantom entity | Narration names an item, character or location that is not in state or in the scenario definition |
| `CONTRADICT` | State contradiction | Narration asserts something that conflicts with a recorded value (HP band, status, quest state, location of an item) |
| `RESOURCE` | Resource error | Narration describes spending, gaining or consuming a resource inconsistently with state (spell slots, inventory quantities) |
| `RELATION` | Relationship contradiction | Narration treats an NPC in a manner inconsistent with its recorded stance |

One narration may contain several divergences, including several of the same category. Count each. The unit of M1 is **divergences per 100 turns**.

### 10.2 Hit-point bands — the threshold that decides everything

Bands are computed as `ratio = current_hp / max_hp`:

| Band | Ratio |
|---|---|
| `healthy` | `> 0.75` |
| `wounded` | `> 0.35` and `<= 0.75` |
| `badly_hurt` | `> 0` and `<= 0.35` |
| `unconscious` | `== 0` |

**A `CONTRADICT` divergence is recorded when the band implied by the narration differs from the actual band.** 14 of 20 is 0.70, which is `wounded`; narrating "on the brink of death" implies `badly_hurt` and is therefore a divergence. Adjacent bands are not forgiven — the whole point is that the model has been handed the band explicitly in `narration_facts`.

Band lexicon used by the automated checker, in `eval/bands.py`. Phrases are matched case-insensitively on the lemmatised narration:

- `healthy`: unhurt, unharmed, unscathed, fresh, barely a scratch, fine, uninjured
- `wounded`: hurt, wounded, bleeding, bruised, battered, injured, sore
- `badly_hurt`: barely standing, near death, dying, at death's door, close to collapse, gravely wounded, on the brink, failing
- `unconscious`: unconscious, collapses, falls, out cold, senseless, crumples

A narration containing no band phrase is not scored for band accuracy. Ambiguity is resolved in favour of no divergence; the checker should under-report rather than over-report, and the human pass catches the rest.

### 10.3 What the checker automates

`eval/checker.py` handles the mechanically decidable subset:

1. **Entity extraction.** Every `display_name` in state and in the scenario is matched against the narration. A capitalised noun phrase or a known item-type word that matches nothing in scope is flagged `PHANTOM` (candidate).
2. **Band comparison** per 10.2.
3. **Status contradiction.** Narration implies an unconscious combatant is acting, or an active one is down.
4. **Resource comparison.** Narration mentions casting or spending when `state_diff` shows no corresponding change, or vice versa.
5. **Stance comparison** against the stance lexicon (hostile/warm/neutral speech markers).
6. **Rule violations (M4)**, which are checked against the *state*, not the narration: negative HP, slot spent below zero, action out of turn order, action after encounter end.

Everything else is human-annotated. The checker must report **candidates with a confidence flag**, never final scores, for `PHANTOM`. A human confirms or rejects each candidate.

Validate the checker against 30 hand-labelled turns before using it. Record precision and recall in `docs/checker_validation.md`, including the cases it is known to miss.

### 10.4 Metrics

| ID | Metric | Computation |
|---|---|---|
| M1 | Divergence rate | Confirmed divergences per 100 turns, overall and per category, per condition |
| M2 | Invalid tool-call rate and recovery rate | From the audit log. Condition D only. Rejected calls / total turns; recovered within budget / rejected |
| M3 | Intent fidelity | Human-annotated on a 15% random sample. Binary per turn: does the executed call represent the player's request? *(This is the critic layer in the VERIFY pyramid — an active search for failures invisible to the automated checker.)* |
| M4 | Rule-violation rate | Automated, all conditions |
| M5 | Narrative quality | Two raters, blind to condition, 1–5 on coherence, vividness, tone appropriateness, plus one engagement item ("would you want to keep reading?") |
| M6 | Latency and throughput | Mean and p95 seconds per turn, tokens per second |

Inter-rater agreement: Krippendorff's alpha on a 20% double-scored overlap. Target `>= 0.6`.

---

## 11. Audit log

JSON Lines, one record per turn, at `runs/{condition}/{scenario_id}/{seed}.jsonl`. This file *is* the dataset. If it is incomplete, the run is worthless.

```json
{
  "run_id": "D_s01_cellar_12345",
  "condition": "D",
  "scenario_id": "s01_cellar",
  "seed": 12345,
  "turn_number": 7,
  "timestamp": "2026-11-09T14:22:31Z",
  "player_input": "I swing my sword at the bigger rat",
  "model_calls": [
    {"phase": "toolcall", "attempt": 1, "prompt_tokens": 3120,
     "completion_tokens": 41, "latency_ms": 2210,
     "raw_output": "{\"tool\": \"attack\", \"arguments\": {...}}"}
  ],
  "proposed_calls": [{"tool": "attack", "arguments": {"attacker_id": "pc_lyra", "target_id": "npc_rat_01", "weapon_id": "item_short_sword"}}],
  "validation": [{"ok": true}],
  "executed_call": {"tool": "attack", "arguments": {}},
  "rolls": [],
  "state_before_hash": "sha256:...",
  "state_after_hash": "sha256:...",
  "state_diff": [],
  "narration": "Your blade bites into the rat's flank...",
  "narration_filtered": false,
  "turn_failure": null,
  "narration_only": false,
  "k_used": 8,
  "summary_regenerated": false
}
```

State hashes are how invariant 4 is tested: replay a seed, compare the hash sequence.

---

## 12. Scenario definition

One JSON file per scenario in `scenarios/`. Twelve short scenarios of about 25 turns, four long ones of 50 turns.

```json
{
  "scenario_id": "s01_cellar",
  "display_name": "The Cellar Rats",
  "opening_narration": "The cellar stairs end in ankle-deep water...",
  "initial_state": { "...": "a complete GameState minus turn/round fields" },
  "scripted_inputs": [
    "I look around the cellar",
    "I draw my sword and attack the nearest rat",
    "I check if anything is hidden behind the barrels"
  ],
  "expected_tools": [null, "attack", "skill_check"],
  "notes_for_annotators": "Turn 12 deliberately references a lantern that is not in inventory, to test PHANTOM detection."
}
```

`scripted_inputs` are fixed so that every condition receives identical stimuli. `expected_tools` is used only for checker validation and M3 sampling guidance; it is **not** used to grade the model, because a different but reasonable tool choice is not a failure.

Every scenario must exercise at least two of: inventory change, quest transition, relationship change. Long scenarios must exercise all three and must run long enough for at least five summary regenerations.

---

## 13. Testing requirements

The 60-case rule suite is an objective success criterion. Distribution:

| Area | Cases |
|---|---|
| Dice parsing and seeded reproducibility | 6 |
| Ability modifiers, including negatives and boundaries | 4 |
| Initiative, ordering, tie-breaks, round advance | 6 |
| Attack: hit, miss, natural 20, natural 1, critical damage | 8 |
| Advantage and disadvantage, including mutual cancellation | 5 |
| Dodge: application and expiry timing | 4 |
| Fire Bolt and Cure Wounds, including the HP cap and slot exhaustion | 7 |
| Zero HP, unconscious, revival, encounter end | 6 |
| Skill checks at, above and below DC | 5 |
| Inventory and quantity floors | 3 |
| Relationship ladder, one-step rule, justification | 3 |
| Quest transitions, legal and illegal | 3 |
| **Total** | **60** |

Plus, separately: every rejection code in 6.3 must be reachable by at least one test; the replay test must confirm identical state hashes across two runs of one seed; the parser must be tested against at least 20 recorded malformed model outputs collected during Week 2 benchmarking.

No test may call the model. Orchestration tests use a recorded-response fake client.

---

## 14. Out of scope — do not build

Building any of these is scope creep and costs someone else their week.

- Any spatial model: maps, grids, movement, range, cover, area effects. There is no Dash.
- Any spell beyond the two named. No concentration, saving throws, components or durations.
- Death, death saving throws, resurrection.
- Multiplayer or a party of more than one player character. One PC; everyone else is engine-controlled.
- Rests, levelling, experience points, currency.
- A database or vector store. JSON files only.
- Retrieval-augmented generation over lore documents.
- Fine-tuning, LoRA, quantisation experiments.
- A graphical client. Text CLI only; a minimal FastAPI page is optional and last.
- Human-participant studies. The player study was withdrawn.

---

## 15. Decisions made in this document

The proposal left these open. They are settled here so that nothing has to be guessed, but the team may overrule any of them — change this file and add a dated entry to `docs/decisions.md`.

1. Attack bonuses, damage bonuses, spell attack bonus and AC are **stored, not derived**.
2. Proficiency bonus is a flat +2 for everyone.
3. Initiative ties break on dex score, then combatant id.
4. Natural 1 is an automatic miss.
5. Criticals double the dice only, not the modifier.
6. Dodge expires at the start of the dodger's next turn.
7. Advantage and disadvantage cancel exactly, and do not stack.
8. Unconscious combatants cannot be attacked. This is a simplification and a deviation from tabletop convention.
9. No rests; spell slots do not recover within a session.
10. HP band thresholds are 0.75 / 0.35 / 0, and a band mismatch is a divergence with no tolerance for adjacency.
11. `narration_facts` includes the band, so the model is never asked to infer it.
12. Condition D's narration call receives facts only, not the full state.
13. Tool-call generation runs at temperature 0.0, narration at 0.7.
14. Retry budget is 2, and a failed turn does not advance the game.
15. Skill checks do not consume the turn action.
16. The rolling summary is forbidden from restating numeric state.

## 16. Open questions for the team

Do not resolve these alone.

- The model name, version and quantisation. Placeholder until the Week 2 benchmark completes.
- Whether grammar-constrained decoding is needed, which depends on the benchmarked schema-valid rate.
- Whether the minimal FastAPI interface is built at all. It is optional and has no reserved time.
