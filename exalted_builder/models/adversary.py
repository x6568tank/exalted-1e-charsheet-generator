"""
models/adversary.py — the Storyteller's throwaway opposition.

An `Adversary` is one extra, beast or NPC on the Storyteller's party page. It is
not validated, not bought, and not locked.

⚠ An Adversary is NOT a `Character` and must never become one — a test asserts
it.

## One model, five printed templates

The templates nest:

  * Extra          (p.241)      init, pool, Valor, Willpower, 3 fixed health levels
  * Beast          (p.316-317)  + Str/Dex/Sta, attacks, Abilities, dodge/soak
  * NPC            (p.276-279)  + all 9 Attributes, 4 Virtues, Essence, notes
  * Spirit         (p.292-295)  + Nature, Backgrounds, Charms, Cost To Materialize
  * Exalt/Deathlord(p.302-315)  + Caste/Aspect, Spells, Personal/Peripheral Essence

Thus each field except `name` is optional.

## Three shapes

1. ⚠ `charms` and `spells` are PROSE, never catalogue ids. The book prints text
   such as "All listed Charms". engine.adversaries asserts this.
2. ⚠ `dodge` is NULLABLE, not 0. None = the creature does not dodge (p.316, p.307).
3. Mote pools: a spirit has `essence_pool`. An Exalt has personal and peripheral.
   An entry uses one shape, never both.

`health_levels` is a flat list of wound penalties, as `OxBodyPurchase.health_levels`.
The repeat notation (`-0/-1 x 7/-2 x 12/-4/Incap`) is expanded at authoring, not at
runtime (engine.adversaries.expand_health).

## Play-state

`damage` aligns by position with `health_levels`, as `PlayState.health`. A manual
tracker (decision 0006).
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from .rules import Damage


# The two sides of a roster entry (p3-tables.md section 15.1, R6).
ENEMY = "enemy"
ALLY = "ally"
Side = Literal["enemy", "ally"]


class AdversaryAttack(BaseModel):
    """One printed attack line: `Bite: 6/7/1L` (beast) or `Fist: Speed 4 Accuracy 3
    Damage 2B Defense 3` (NPC).

    `defense` is Optional: a beast uses its Atk value to parry (p.317).
    `damage_type`: the printed suffix, or "". `note`: a printed footnote."""
    name: str
    speed: Optional[int] = None
    accuracy: Optional[int] = None
    damage: Optional[int] = None
    damage_type: str = ""
    defense: Optional[int] = None
    note: str = ""


class AdversaryTrait(BaseModel):
    """One rated Ability or Background, with the printed specialties:
    `Survival 3 (Tracking +3)`. The specialties are text, not Specialty instances."""
    name: str
    rating: int = 0
    specialties: str = ""


class Adversary(BaseModel):
    """One extra, beast or NPC on the Storyteller's roster.

    `template_id` is the catalogue row of the copy. Display only. The copy is
    independent, and the catalogue row is never changed."""

    id: str
    name: str = ""
    template_id: str = ""
    # Free-text identity. `categories`: the roster labels ("Extra", "Beast").
    # `caste` holds the `Caste:` line or the `Aspect:` line.
    # ⚠ `categories` is a list with no primary entry (human's ruling).
    categories: list[str] = Field(default_factory=list)
    # The side at a campaign table (R6). Each roster in a `.party.json` loads as
    # enemies.
    # ⚠ An enemy never reaches the page of a player. An ally reaches it as a name
    # and a health track only (`view.ally_view`, R7).
    side: Side = ENEMY
    nature: str = ""
    caste: str = ""

    # Attributes as a name->rating map. ⚠ An absent Attribute is not 0: a beast
    # prints three of nine (p.316).
    attributes: dict[str, int] = Field(default_factory=dict)
    virtues: dict[str, int] = Field(default_factory=dict)
    abilities: list[AdversaryTrait] = Field(default_factory=list)
    backgrounds: list[AdversaryTrait] = Field(default_factory=list)

    # Combat. `dodge` absent = does not dodge (see the module docstring).
    base_initiative: Optional[int] = None
    # The one dice pool of an extra (p.241). None on the other templates.
    combat_pool: Optional[int] = None
    attacks: list[AdversaryAttack] = Field(default_factory=list)
    dodge: Optional[int] = None
    soak_lethal: int = 0
    soak_bashing: int = 0
    # Mundane armor, by ArmorType id. The picker hides artifact armor (human's
    # ruling). The two soak fields above hold natural soak only.
    armor_id: str = ""
    # Shield, by ArmorType id. An Adversary has one armor, and a shield adds to it
    # (p.335).
    shield_id: str = ""

    willpower: int = 0
    essence: int = 0
    # Mote pools. See the module docstring.
    essence_pool: int = 0
    personal_essence: int = 0
    peripheral_essence: int = 0
    cost_to_materialize: int = 0
    # The elemental label (p.295, p.298). Two fields, not a flag: the GM reads the
    # label on the card.
    cost_to_dematerialize: int = 0

    # Wound penalties, one per box, deepest last. Expanded at authoring time.
    health_levels: list[int] = Field(default_factory=list)

    # Prose, never ids. See the module docstring.
    charms: str = ""
    spells: str = ""
    # The printed `Powers:` line. Prose.
    powers: str = ""
    notes: str = ""

    # ---- play-state ------------------------------------------------------- #
    # Aligned by position with health_levels. Normalized at render.
    damage: list[Optional[Damage]] = Field(default_factory=list)
    willpower_spent: int = Field(default=0, ge=0)
    motes_spent: int = Field(default=0, ge=0)
