"""Core state types and state load/save (WBS 4.1).

`GameState` is the typed form of schemas/state.schema.json (CLAUDE.md section 5).
A legal state passes the JSON Schema and the rules it cannot express
(`cross_field_errors`, docs/state_schema.md section 3). Every load and save
checks both, and the pydantic models add types and attribute access on top.

The post-write invariant assertion (WBS 5.4) is `check_state`: the engine's one
write path (adm/engine/tools.py) runs it after every write, so an illegal state
raises `IllegalState` rather than persisting. The rule on `encounter_outcome` is
the one the state can still show once an encounter is over: `victory` with a
conscious player character, `defeat` with an unconscious one. Which hostiles
were in the encounter is not kept once it ends (docs/decisions.md, WBS 5.4).

`to_dict` gives back exactly the JSON the state was loaded from, so a state file
round-trips without loss and `state_hash` matches docs/conventions.md section 2.
"""

from __future__ import annotations

import hashlib
import json
from functools import cache
from pathlib import Path
from typing import Any, Literal, get_args

from jsonschema import Draft202012Validator
from pydantic import BaseModel, ConfigDict, Field, SerializerFunctionWrapHandler, model_serializer
from pydantic import ValidationError as PydanticValidationError

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "state.schema.json"

Faction = Literal["party", "hostile", "neutral"]
Status = Literal["active", "unconscious"]
Skill = Literal["strength", "perception", "stealth"]
Stance = Literal["hostile", "unfriendly", "neutral", "friendly", "allied"]
QuestState = Literal["not_started", "active", "completed", "failed"]
EncounterOutcome = Literal["victory", "defeat"]


class StateValidationError(ValueError):
    """A state that does not match schemas/state.schema.json."""


class IllegalState(StateValidationError):
    """A state that breaks a rule of docs/state_schema.md, found after a write."""


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, populate_by_name=True)


class Abilities(_Model):
    # `str` and `int` would shadow the builtins, so those two carry an alias.
    str_: int = Field(alias="str")
    dex: int
    con: int
    int_: int = Field(alias="int")
    wis: int
    cha: int


class Combatant(_Model):
    combatant_id: str
    display_name: str
    is_player_character: bool
    faction: Faction
    abilities: Abilities
    proficient_skills: list[Skill]
    armour_class: int
    max_hp: int
    current_hp: int
    status: Status
    dodging: bool
    spell_attack_bonus: int | None
    spellcasting_modifier: int | None
    spell_slots_1: int | None


class Item(_Model):
    item_id: str
    display_name: str
    is_weapon: bool
    attack_bonus: int | None = None
    damage_dice: str | None = None
    damage_bonus: int | None = None

    @model_serializer(mode="wrap")
    def _omit_absent_weapon_fields(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        # A non-weapon has no weapon keys at all in the file, rather than nulls.
        data = handler(self)
        for key in ("attack_bonus", "damage_dice", "damage_bonus"):
            if data[key] is None:
                del data[key]
        return data


class RelationshipChange(_Model):
    turn: int
    from_: Stance = Field(alias="from")
    to: Stance
    justification: str


class NPCRelationship(_Model):
    npc_id: str
    display_name: str
    stance: Stance
    history: list[RelationshipChange]


class Quest(_Model):
    quest_id: str
    display_name: str
    state: QuestState
    stage: int
    max_stage: int


class GameState(_Model):
    schema_version: Literal["1.0"]
    scenario_id: str
    seed: int
    turn_number: int
    round_number: int
    active_combatant_id: str | None
    initiative_order: list[str]
    encounter_active: bool
    encounter_outcome: EncounterOutcome | None
    combatants: dict[str, Combatant]
    inventory: dict[str, dict[str, int]]
    item_definitions: dict[str, Item]
    npc_relationships: dict[str, NPCRelationship]
    quests: dict[str, Quest]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GameState:
        """Check `data` against the state schema and its cross-field rules, then
        build the typed state."""
        _check_schema(data)
        _check_cross_field(data)
        try:
            return cls.model_validate(data)
        except PydanticValidationError as exc:
            raise StateValidationError(str(exc)) from exc

    def to_dict(self) -> dict[str, Any]:
        """The state as plain JSON data, with the keys and nulls of the schema."""
        return self.model_dump(mode="json", by_alias=True)


@cache
def _validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


def _check_schema(data: Any) -> None:
    errors = sorted(_validator().iter_errors(data), key=lambda e: list(e.absolute_path))
    if errors:
        lines = [f"{e.json_path}: {e.message}" for e in errors]
        raise StateValidationError("state does not match the schema:\n" + "\n".join(lines))


STANCES: tuple[str, ...] = get_args(Stance)  # the ladder, hostile to allied


def cross_field_errors(data: dict[str, Any]) -> list[str]:
    """Where a state that passes the schema breaks the rules of docs/state_schema.md
    section 3, which JSON Schema cannot express."""
    errors: list[str] = []
    combatants = data["combatants"]

    keyed = (
        ("combatants", "combatant_id"),
        ("item_definitions", "item_id"),
        ("npc_relationships", "npc_id"),
        ("quests", "quest_id"),
    )
    for section, id_field in keyed:
        for key, entity in data[section].items():
            if entity[id_field] != key:
                errors.append(f"{section}.{key}: {id_field} is {entity[id_field]!r}")

    pcs = [cid for cid, c in combatants.items() if c["is_player_character"]]
    if len(pcs) != 1:
        errors.append(f"expected exactly one player character, found {pcs}")

    for cid, c in combatants.items():
        if not 0 <= c["current_hp"] <= c["max_hp"]:
            errors.append(f"{cid}: current_hp {c['current_hp']} outside [0, {c['max_hp']}]")

    for cid in data["initiative_order"]:
        if cid not in combatants:
            errors.append(f"initiative_order: unknown combatant {cid}")
    active = data["active_combatant_id"]
    if active is not None and active not in data["initiative_order"]:
        errors.append(f"active_combatant_id {active} is not in initiative_order")

    for owner, items in data["inventory"].items():
        if owner not in combatants:
            errors.append(f"inventory: unknown combatant {owner}")
        for item_id in items:
            if item_id not in data["item_definitions"]:
                errors.append(f"inventory.{owner}: undefined item {item_id}")

    for npc_id, rel in data["npc_relationships"].items():
        if npc_id in combatants and combatants[npc_id]["display_name"] != rel["display_name"]:
            errors.append(f"{npc_id}: display_name differs between combatants and relationships")
        stance = rel["history"][0]["from"] if rel["history"] else rel["stance"]
        for entry in rel["history"]:
            if entry["from"] != stance:
                errors.append(f"{npc_id}: history breaks at turn {entry['turn']}")
            if abs(STANCES.index(entry["to"]) - STANCES.index(entry["from"])) != 1:
                errors.append(f"{npc_id}: turn {entry['turn']} is not a one-step change")
            stance = entry["to"]
        if stance != rel["stance"]:
            errors.append(f"{npc_id}: stance {rel['stance']} does not match history")

    for qid, quest in data["quests"].items():
        if quest["stage"] > quest["max_stage"]:
            errors.append(f"{qid}: stage {quest['stage']} beyond max_stage")

    outcome = data["encounter_outcome"]
    conscious_pcs = [pc for pc in pcs if combatants[pc]["status"] == "active"]
    if outcome == "victory" and len(conscious_pcs) != len(pcs):
        errors.append("victory with an unconscious player character")
    if outcome == "defeat" and conscious_pcs:
        errors.append("defeat with an active player character")

    return errors


def _check_cross_field(data: dict[str, Any]) -> None:
    errors = cross_field_errors(data)
    if errors:
        raise StateValidationError("state breaks a cross-field rule:\n" + "\n".join(errors))


def check_state(state: GameState) -> None:
    """The post-write invariant assertion: raise `IllegalState` unless `state`
    passes the schema and every cross-field rule."""
    data = state.to_dict()
    try:
        _check_schema(data)
        _check_cross_field(data)
    except StateValidationError as exc:
        raise IllegalState(f"illegal state after a write: {exc}") from exc


def canonical_json(state: GameState) -> str:
    """The serialisation used for hashing (docs/conventions.md section 2)."""
    return _canonical(state.to_dict())


def _canonical(data: dict[str, Any]) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def state_hash(state: GameState) -> str:
    return data_hash(state.to_dict())


def data_hash(data: dict[str, Any]) -> str:
    """`state_hash` of a state already in its JSON form, as `to_dict` gives it."""
    return "sha256:" + hashlib.sha256(_canonical(data).encode("utf-8")).hexdigest()


def load_state(path: Path) -> GameState:
    """Read a state file and check it against the schema and its cross-field rules."""
    return GameState.from_dict(json.loads(path.read_text(encoding="utf-8")))


def save_state(state: GameState, path: Path) -> None:
    """Check `state` against the schema and its cross-field rules and write it;
    nothing is written if it is illegal."""
    data = state.to_dict()
    _check_schema(data)
    _check_cross_field(data)
    text = json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    path.write_text(text, encoding="utf-8")
