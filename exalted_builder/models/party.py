"""
models/party.py — a Storyteller's party bundle.

Character-data domain, like character.py: a `Party` holds a full copy of each
player's Character, the GM's notes, and the adversaries being run against them.
It carries no rules and no derived values — legality lives in engine.validate,
which never looks at a Party, and the cards that render one read capacities from
the engine the way the Play tab does.

⚠ Members are COPIES, not references to .character.json files. The GM's copy is
the table copy and may drift from the player's own.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .adversary import Adversary
from .character import Character


class PartyMember(BaseModel):
    """One character at the table, plus whatever the GM wants to remember about
    them. `notes` is free text and has no mechanical meaning."""
    notes: str = ""
    character: Character


class Party(BaseModel):
    """A named group of characters, the GM's session notes, and the extras,
    beasts and NPCs being run against them. `adversaries` defaults empty, so
    bundles written before it existed still load."""
    id: str
    name: str = ""
    session_notes: str = ""
    members: list[PartyMember] = Field(default_factory=list)
    adversaries: list[Adversary] = Field(default_factory=list)
