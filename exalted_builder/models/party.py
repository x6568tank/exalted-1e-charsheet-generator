"""
models/party.py — a Storyteller's party bundle.

Character-data domain, like character.py: a `Party` is a container the GM keeps
at the table, holding a full *copy* of each player's Character plus notes. It
imports nothing game-specific — game legality still lives in engine.validate,
which never looks at a Party at all.

Why copies rather than references to .character.json files: the shipped build
runs in the browser, where loading is an upload and there are no filesystem
paths to reference. One bundle file loads and saves in one action. The
consequence is deliberate — the GM's copy is the table copy and may drift from
the player's own file.

A Party carries no rules and no derived values; the cards that render it read
capacities from the engine the same way the Play tab does.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .character import Character


class PartyMember(BaseModel):
    """One character at the table, plus whatever the GM wants to remember about
    them. `notes` is free text and has no mechanical meaning."""
    notes: str = ""
    character: Character


class Party(BaseModel):
    """A named group of characters and the GM's session notes."""
    id: str
    name: str = ""
    session_notes: str = ""
    members: list[PartyMember] = Field(default_factory=list)
