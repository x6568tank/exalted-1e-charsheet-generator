"""
models/party.py — a Storyteller's party bundle.

A `Party` holds a copy of each player's Character, the GM's notes, and the
adversaries. It has no rules and no derived values.

⚠ Members are COPIES, not references to .character.json files.
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
    beasts and NPCs being run against them."""
    id: str
    name: str = ""
    session_notes: str = ""
    members: list[PartyMember] = Field(default_factory=list)
    adversaries: list[Adversary] = Field(default_factory=list)
