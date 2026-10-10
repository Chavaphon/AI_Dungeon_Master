"""Initiative, turn order, tie-break rule and round advance (WBS 4.4, CLAUDE.md
section 4.4).

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
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from adm.engine.abilities import combatant_modifier
from adm.engine.dice import DiceRoller, RollResult
from adm.engine.state import Combatant, GameState


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
