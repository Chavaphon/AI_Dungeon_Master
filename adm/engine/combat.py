"""Initiative, turn order, tie-break rule and round advance (WBS 4.4, CLAUDE.md
section 4.4), and attack resolution (WBS 4.5, CLAUDE.md section 4.5).

Initiative is rolled once, when an encounter starts: `1d20 + dex modifier` for
each combatant, in the order the scenario lists them (`encounters[].combatant_ids`).
The order is highest total first. Ties break on, in order:

1. the higher `dex` score (not modifier: 15 beats 14 although both give +2);
2. the lexicographically smaller `combatant_id`.

No two combatants share an id, so the order is total and fixed by the seed alone.

The order holds for the whole encounter. An unconscious combatant keeps its slot
but is skipped. `round_number` is 1 when an encounter starts and goes up by one
each time the turn passes the end of the order.

Each function changes the state in place and returns the `engine_steps` record
of what it did (docs/audit_log.md section 2). Starting an encounter while one is
active, or with an unknown or repeated combatant, is a programmer error: the
scenario loader and the turn loop must not allow it, so it raises.

An attack rolls `1d20 + attack bonus` against the target's armour class, with
disadvantage if the target is Dodging. The kept d20 decides naturals: 20 always
hits and is a critical, 1 always misses. A hit rolls the weapon's damage dice
plus its damage bonus, minimum 0; a critical rolls the dice twice and adds the
bonus once. HP is clamped at 0, and a combatant at 0 becomes unconscious.
`resolve_attack` is the shared path that Fire Bolt (WBS 4.11) reuses.

`attack` changes the state in place and returns the parts of the result envelope
(docs/tool_contract.md section 2). It assumes the validator (WBS 5.2) has
already rejected the call if it breaks a precondition; reaching here with an
unconscious target or a non-weapon raises. Ending the turn, initiative advance
and encounter end are engine steps after the tool, not part of it.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from adm.engine.abilities import combatant_modifier
from adm.engine.dice import AdvantageMode, DiceRoller, RollResult
from adm.engine.state import Combatant, GameState, Status


class StateChange(BaseModel):
    """One `state_diff_entry` (tools.schema.json)."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    path: str
    from_: Any = Field(alias="from")
    to: Any


class EngineStep(BaseModel):
    """A `bookkeeping_step` of the turn record (audit.schema.json)."""

    model_config = ConfigDict(frozen=True)

    step: Literal["encounter_start", "initiative_advance"]
    when: Literal["before_call", "after_call"]
    state_diff: list[StateChange]
    rolls: list[RollResult]

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json", by_alias=True)


class InitiativeEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    combatant_id: str
    dex: int
    roll: RollResult


def _set(state: GameState, field: str, value: Any, diff: list[StateChange]) -> None:
    """Assign a top-level state field and record it, if it changes."""
    before = getattr(state, field)
    if before != value:
        diff.append(StateChange(path=field, from_=before, to=value))
        setattr(state, field, value)


def initiative_sort_key(entry: InitiativeEntry) -> tuple[int, int, str]:
    """Higher total first, then higher dex score, then smaller combatant id."""
    return (-entry.roll.total, -entry.dex, entry.combatant_id)


def roll_initiative(roller: DiceRoller, combatants: Sequence[Combatant]) -> list[InitiativeEntry]:
    """Roll `1d20 + dex modifier` for each combatant, in the order given."""
    return [
        InitiativeEntry(
            combatant_id=c.combatant_id,
            dex=c.abilities.dex,
            roll=roller.roll(f"1d20{combatant_modifier(c, 'dex'):+d}"),
        )
        for c in combatants
    ]


def initiative_order(entries: Sequence[InitiativeEntry]) -> list[str]:
    return [e.combatant_id for e in sorted(entries, key=initiative_sort_key)]


def _is_conscious(state: GameState, combatant_id: str) -> bool:
    return state.combatants[combatant_id].status == "active"


def start_encounter(
    state: GameState, roller: DiceRoller, combatant_ids: Sequence[str]
) -> EngineStep:
    """Roll initiative and open an encounter. The first conscious combatant in the
    order acts first, and the round is 1."""
    if state.encounter_active:
        raise ValueError("an encounter is already active")
    if not combatant_ids:
        raise ValueError("an encounter needs at least one combatant")
    if len(set(combatant_ids)) != len(combatant_ids):
        raise ValueError(f"repeated combatant in {list(combatant_ids)}")
    unknown = [cid for cid in combatant_ids if cid not in state.combatants]
    if unknown:
        raise ValueError(f"unknown combatants {unknown}")

    entries = roll_initiative(roller, [state.combatants[cid] for cid in combatant_ids])
    order = initiative_order(entries)
    first = next((cid for cid in order if _is_conscious(state, cid)), None)
    if first is None:
        raise ValueError("no conscious combatant can take the first turn")

    diff: list[StateChange] = []
    _set(state, "encounter_active", True, diff)
    _set(state, "encounter_outcome", None, diff)
    _set(state, "initiative_order", order, diff)
    _set(state, "round_number", 1, diff)
    _set(state, "active_combatant_id", first, diff)
    return EngineStep(
        step="encounter_start",
        when="before_call",
        state_diff=diff,
        rolls=[e.roll for e in entries],
    )


def advance_initiative(state: GameState) -> EngineStep:
    """Pass the turn to the next conscious combatant in the order. Passing the end
    of the order wraps to the start and increments `round_number` once."""
    if not state.encounter_active:
        raise ValueError("no active encounter")
    order = state.initiative_order
    index = order.index(state.active_combatant_id)
    round_number = state.round_number
    for _ in order:
        index += 1
        if index == len(order):
            index = 0
            round_number += 1
        if _is_conscious(state, order[index]):
            break
    else:
        raise ValueError("no conscious combatant in the initiative order")

    diff: list[StateChange] = []
    _set(state, "active_combatant_id", order[index], diff)
    _set(state, "round_number", round_number, diff)
    return EngineStep(step="initiative_advance", when="after_call", state_diff=diff, rolls=[])


# --- attack resolution -------------------------------------------------------

HpBand = Literal["healthy", "wounded", "badly_hurt", "unconscious"]


def hp_band(current_hp: int, max_hp: int) -> HpBand:
    """The band of CLAUDE.md section 10.2, the one definition the checker imports.
    Compared in integers so 0.75 and 0.35 exactly fall in the lower band."""
    if max_hp < 1 or not 0 <= current_hp <= max_hp:
        raise ValueError(f"hit points {current_hp} of {max_hp} are out of range")
    if current_hp == 0:
        return "unconscious"
    if 100 * current_hp > 75 * max_hp:
        return "healthy"
    if 100 * current_hp > 35 * max_hp:
        return "wounded"
    return "badly_hurt"


class AttackRollFacts(BaseModel):
    """`attack_roll_facts` in tools.schema.json, shared by attack and Fire Bolt."""

    model_config = ConfigDict(frozen=True)

    hit: bool
    critical: bool
    attack_roll: int
    advantage_mode: AdvantageMode
    target_ac: int
    damage: int
    target_hp_before: int
    target_hp_after: int
    target_hp_max: int
    target_hp_band: HpBand
    target_status: Status


class AttackFacts(AttackRollFacts):
    """`facts_attack` in tools.schema.json."""

    attacker: str
    target: str
    weapon: str


class AttackOutcome(BaseModel):
    """The `narration_facts`, `state_diff` and `rolls` of an attack's result envelope."""

    model_config = ConfigDict(frozen=True)

    facts: AttackFacts
    state_diff: list[StateChange]
    rolls: list[RollResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "narration_facts": self.facts.model_dump(mode="json"),
            "state_diff": [c.model_dump(mode="json", by_alias=True) for c in self.state_diff],
            "rolls": [r.to_dict() for r in self.rolls],
        }


def resolve_attack(
    state: GameState,
    roller: DiceRoller,
    target_id: str,
    attack_bonus: int,
    damage_dice: str,
    damage_bonus: int,
) -> tuple[AttackRollFacts, list[StateChange], list[RollResult]]:
    """Roll to hit `target_id` and apply any damage. Rolls are the attack roll,
    then the damage roll if it hit."""
    target = state.combatants[target_id]
    if target.status != "active":
        raise ValueError(f"{target_id} is unconscious and cannot be attacked")

    mode: AdvantageMode = "disadvantage" if target.dodging else "normal"
    attack_roll = roller.roll(f"1d20{attack_bonus:+d}", mode)
    natural = attack_roll.total - attack_roll.modifier
    critical = natural == 20
    hit = critical or (natural != 1 and attack_roll.total >= target.armour_class)
    rolls = [attack_roll]

    damage = 0
    if hit:
        notation = f"{damage_dice}{damage_bonus:+d}"
        damage_roll = roller.roll_critical(notation) if critical else roller.roll(notation)
        rolls.append(damage_roll)
        damage = max(0, damage_roll.total)

    hp_before = target.current_hp
    hp_after = max(0, hp_before - damage)
    diff: list[StateChange] = []
    path = f"combatants.{target_id}"
    if hp_after != hp_before:
        diff.append(StateChange(path=f"{path}.current_hp", from_=hp_before, to=hp_after))
        target.current_hp = hp_after
    if hp_after == 0:
        diff.append(StateChange(path=f"{path}.status", from_=target.status, to="unconscious"))
        target.status = "unconscious"

    facts = AttackRollFacts(
        hit=hit,
        critical=critical,
        attack_roll=attack_roll.total,
        advantage_mode=mode,
        target_ac=target.armour_class,
        damage=damage,
        target_hp_before=hp_before,
        target_hp_after=hp_after,
        target_hp_max=target.max_hp,
        target_hp_band=hp_band(hp_after, target.max_hp),
        target_status=target.status,
    )
    return facts, diff, rolls


def attack(
    state: GameState, roller: DiceRoller, attacker_id: str, target_id: str, weapon_id: str
) -> AttackOutcome:
    """Resolve a weapon attack (section 4.5) and apply it to `state`."""
    weapon = state.item_definitions[weapon_id]
    if not weapon.is_weapon:
        raise ValueError(f"{weapon_id} is not a weapon")
    assert weapon.attack_bonus is not None
    assert weapon.damage_dice is not None and weapon.damage_bonus is not None
    roll_facts, diff, rolls = resolve_attack(
        state, roller, target_id, weapon.attack_bonus, weapon.damage_dice, weapon.damage_bonus
    )
    facts = AttackFacts(
        attacker=state.combatants[attacker_id].display_name,
        target=state.combatants[target_id].display_name,
        weapon=weapon.display_name,
        **roll_facts.model_dump(),
    )
    return AttackOutcome(facts=facts, state_diff=diff, rolls=rolls)
