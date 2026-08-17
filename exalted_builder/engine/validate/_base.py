"""
engine/validate/_base.py — the primitives every validation domain shares.

This module exists so the domain modules (`charms`, `backgrounds`, `artifacts`, …)
can be imported by `validate/__init__.py` without importing it back. Everything
here is depended on from several domains at once and belongs to none of them:

  * `Issue` — the return type of every check in the package (35 dependents, by far
    the most-shared name in the old single file).
  * `ATTRIBUTE_CATEGORIES` and `_attribute_category` — the Physical/Social/Mental
    grouping and its reverse lookup.
  * `craft_rating` / `ability_rating` — reading an Ability rating correctly, i.e.
    resolving Craft from its per-focus instances rather than the unused CRAFT dot.
  * `thaum_state` / `_chargen_source` — which traits chargen accounting reads,
    snapshot vs. live. Decision 0004's two shapes hinge on this one function.

⚠ **Nothing here may import a sibling domain module.** This is the bottom of the
package's import graph and must stay there; a domain-specific rule that drifts in
turns the graph cyclic and the cycle will surface as an import error at startup,
not as a test failure.
"""

from __future__ import annotations

from pydantic import BaseModel

from ...models.character import Character, ThaumaturgyState
from ...models.rules import AbilityName, AttributeName

# Attribute categories and the order Strength/Dexterity/Stamina etc. (core p.104).
# Which category receives which of the 8/6/4 pools is the player's priority and is
# inferred from the spend, not stored — so this is just the membership grouping.
ATTRIBUTE_CATEGORIES: dict[str, tuple[AttributeName, ...]] = {
    "Physical": (AttributeName.STRENGTH, AttributeName.DEXTERITY, AttributeName.STAMINA),
    "Social": (AttributeName.CHARISMA, AttributeName.MANIPULATION, AttributeName.APPEARANCE),
    "Mental": (AttributeName.PERCEPTION, AttributeName.INTELLIGENCE, AttributeName.WITS),
}


def thaum_state(character: Character) -> ThaumaturgyState:
    """The character's thaumaturgy, or an empty state. `Character.thaumaturgy` is
    Optional so old saves load with None; every consumer wants the same empty
    answer, so it is centralised here rather than None-checked at each site."""
    return character.thaumaturgy or ThaumaturgyState()


class Issue(BaseModel):
    """One legality finding. `code` is a stable machine tag; `where` locates the
    offending trait (a Charm/Spell id, an ability name, etc.)."""
    code: str
    message: str
    where: str = ""
    severity: str = "error"        # "error" | "warning"


def craft_rating(character: Character) -> int:
    """The effective Craft Ability rating: the highest of the character's per-focus
    Craft instances (core p.136), or 0 if they have none. A Craft Charm's minimum
    Ability is met by the best craft a character possesses."""
    return max((c.rating for c in character.crafts), default=0)


def ability_rating(character: Character, ability: AbilityName) -> int:
    """A character's rating in `ability`, reading Craft from its per-focus instances
    rather than the (unused) AbilityName.CRAFT dot."""
    if ability == AbilityName.CRAFT:
        return craft_rating(character)
    return character.abilities.get(ability, 0)


def _attribute_category(attr: AttributeName) -> str | None:
    """Which of Physical/Social/Mental `attr` belongs to (the reverse lookup of
    ATTRIBUTE_CATEGORIES)."""
    for cat, attrs in ATTRIBUTE_CATEGORIES.items():
        if attr in attrs:
            return cat
    return None


def _chargen_source(character: Character):
    """The traits chargen accounting reads: the frozen snapshot once locked, else
    the current (pre-lock) traits. Returned as a flat tuple in a fixed order."""
    snap = character.chargen_snapshot
    return (
        snap.attributes if snap else character.attributes,
        snap.abilities if snap else character.abilities,
        snap.crafts if snap else character.crafts,
        snap.virtues if snap else character.virtues,
        snap.backgrounds if snap else character.backgrounds,
        snap.specialties if snap else character.specialties,
        snap.charms if snap else character.charms,
        snap.spells if snap else character.spells,
        snap.combos if snap else character.combos,
        snap.ox_body if snap else character.ox_body,
        snap.essence_rating if snap else character.essence_rating,
        snap.willpower_purchased if snap else character.willpower_purchased,
        snap.beastman_gifts if snap else character.beastman_gifts,
        snap.arrays if snap else character.arrays,
        snap.submodules if snap else character.submodules,
        snap.colleges if snap else character.colleges,
        (snap.thaumaturgy or ThaumaturgyState()) if snap else thaum_state(character),
        snap.paths if snap else character.paths,
        snap.favored_path if snap else character.favored_path,
        snap.elemental_powers if snap else character.elemental_powers,
    )
