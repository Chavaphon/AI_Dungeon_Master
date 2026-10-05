"""Core state types and state load/save (WBS 4.1).

`GameState` is the typed form of schemas/state.schema.json (CLAUDE.md section 5).
The JSON Schema is the authority on what a legal state is: every load and save
validates against it, and the pydantic models add types and attribute access on
top. The rules JSON Schema cannot express are checked by the post-write
invariant assertion, WBS 5.4.

`to_dict` gives back exactly the JSON the state was loaded from, so a state file
round-trips without loss and `state_hash` matches docs/conventions.md section 2.
"""

from __future__ import annotations

import hashlib
import json
from functools import cache
from pathlib import Path
from typing import Any, Literal

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
        """Validate `data` against the state schema, then build the typed state."""
        _check_schema(data)
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


def canonical_json(state: GameState) -> str:
    """The serialisation used for hashing (docs/conventions.md section 2)."""
    return json.dumps(state.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def state_hash(state: GameState) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(state).encode("utf-8")).hexdigest()


def load_state(path: Path) -> GameState:
    """Read a state file and validate it against the schema."""
    return GameState.from_dict(json.loads(path.read_text(encoding="utf-8")))


def save_state(state: GameState, path: Path) -> None:
    """Validate `state` against the schema and write it; nothing is written if it is invalid."""
    data = state.to_dict()
    _check_schema(data)
    text = json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    path.write_text(text, encoding="utf-8")
