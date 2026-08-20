"""
models/adversary.py — the Storyteller's throwaway opposition.

Character-data domain, like character.py and party.py: an `Adversary` is one
extra, beast or NPC the GM keeps on the party page. Nothing here is validated
against a budget, nothing is bought, nothing locks.

⚠ An Adversary is NOT a `Character` and must never become one — a test asserts
it. Reusing Character would drag chargen, the lock and the XP ledger onto a
bandit.

## One model, five printed templates

The corebook prints adversaries at five levels of detail, and they nest — an
extra fills four fields, a beast seven, an NPC/spirit/Exalt all of them:

  * Extra          (p.241)      init, pool, Valor, Willpower, 3 fixed health levels
  * Beast          (p.316-317)  + Str/Dex/Sta, attacks, Abilities, dodge/soak
  * NPC            (p.276-279)  + all 9 Attributes, 4 Virtues, Essence, notes
  * Spirit         (p.292-295)  + Nature, Backgrounds, Charms, Cost To Materialize
  * Exalt/Deathlord(p.302-315)  + Caste/Aspect, Spells, Personal/Peripheral Essence

So every field below except `name` is optional, and "bare minimum" is what an
extra actually stores.

## Three shapes the pages forced

1. ⚠ `charms` and `spells` are PROSE, never catalogue ids — the book prints "All
   listed Charms" (Fakharu), "All Solar Charms the Storyteller cares to give him"
   (the Mask of Winters) and, for Sesus Nagezzer, a paragraph naming no Charm at
   all. The loader's link-checking would reject ids. Asserted in
   engine.adversaries.
2. ⚠ `dodge` is NULLABLE, not zero-defaulted. A bear has no dodge value printed at
   all (p.316) and Nagezzer prints the literal "Does not dodge" (p.307): absent
   means the creature does not dodge, which is not the same as dodging with 0.
3. Mote pools come in two shapes: spirits print one `Essence Pool: 112`,
   Terrestrials print `Personal Essence: 11  Peripheral Essence: 27`. Two
   optional fields, never both — a spirit's single pool is not a Personal pool.

`health_levels` is a flat list of wound penalties, the same shape
`OxBodyPurchase.health_levels` uses. The book's repeat notation
(`-0/-1 x 7/-2 x 12/-4/Incap`) is expanded when the data is authored, never at
runtime — see engine.adversaries.expand_health.

## Play-state

`damage` is the tracker, aligned positionally to `health_levels` exactly as
`PlayState.health` aligns to engine.derive.health_track. Decision 0006 applies:
a dumb manual tracker — nothing auto-wraps, auto-heals or auto-accounts.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from .rules import Damage


class AdversaryAttack(BaseModel):
    """One printed attack line.

    Beasts print `Bite: 6/7/1L` (Spd/Atk/Dmg) and NPCs print `Fist: Speed 4
    Accuracy 3 Damage 2B Defense 3` — the same record, except that beasts have no
    Defense column because p.317 says to "use the provided Atk value for both
    attacks and parries". `defense` is therefore Optional rather than 0.

    `damage_type` is the printed suffix ("B", "L", or "" where the book omits it,
    as on a Clinch). `note` carries the asterisked footnotes the book hangs off
    individual lines ("Frigid Razor drains 8 motes…", "+venom", "+egg")."""
    name: str
    speed: Optional[int] = None
    accuracy: Optional[int] = None
    damage: Optional[int] = None
    damage_type: str = ""
    defense: Optional[int] = None
    note: str = ""


class AdversaryTrait(BaseModel):
    """One rated Ability or Background, with the parenthetical specialties the
    book prints inline: `Survival 3 (Tracking +3)`, `Melee 6 (Daiklaves +3)`.

    Specialties are printed text, not the Character model's Specialty instances:
    an adversary's are descriptive, never bought, and the 3-per-Ability cap does
    not apply."""
    name: str
    rating: int = 0
    specialties: str = ""


class Adversary(BaseModel):
    """One extra, beast or NPC on the Storyteller's roster.

    Every field but `name` is optional; which ones are filled is what makes an
    entry an extra rather than a Deathlord. `template_id` records the catalogue
    row this was instantiated from, for display only — the copy is independent
    the moment it is made, and the catalogue row is never written back to."""

    id: str
    name: str = ""
    template_id: str = ""
    # Free-text identity. `category` is the roster's own grouping label
    # ("Extra", "Beast", "Spirit"…); the rest are printed fields that only some
    # templates carry. `caste` serves both the Sidereal/Abyssal `Caste:` line and
    # the Dragon-Blooded `Aspect:` — one field, since no block prints both.
    category: str = ""
    nature: str = ""
    caste: str = ""

    # Traits. Attributes are a plain name->rating map rather than the Character
    # model's typed blocks: a beast prints three of the nine (p.316 notes the
    # rest default to Intelligence 1, Perception 2, Wits 3) and storing absences
    # as zeroes would claim the book printed a zero.
    attributes: dict[str, int] = Field(default_factory=dict)
    virtues: dict[str, int] = Field(default_factory=dict)
    abilities: list[AdversaryTrait] = Field(default_factory=list)
    backgrounds: list[AdversaryTrait] = Field(default_factory=list)

    # Combat. `dodge` absent = does not dodge (see the module docstring).
    base_initiative: Optional[int] = None
    # An extra's ONE dice pool. p.241 gives "4 dice in any relevant combat dice
    # pool" instead of Attributes and Abilities, so an extra needs no traits at
    # all — this single number stands in for every roll it makes. Absent on every
    # other template, which rolls Attribute + Ability like a character.
    combat_pool: Optional[int] = None
    attacks: list[AdversaryAttack] = Field(default_factory=list)
    dodge: Optional[int] = None
    soak_lethal: int = 0
    soak_bashing: int = 0
    # Mundane armour worn, by ArmorType id. Artifact armour is filtered out of the
    # picker (human's ruling): an extra does not carry a daiklave's worth of gear.
    # Soak and the dodge mobility penalty follow from this the way they do for a
    # character; the two soak fields above hold natural soak (a beast's hide, a
    # Deathlord's "Skin") that no armour explains.
    armor_id: str = ""
    # Shield carried, by ArmorType id (shields are armour rows tagged "shield").
    # ⚠ A slot of its own because an Adversary holds ONE armour, not a list, and a
    # shield STACKS with armour — p.335 has a target shield "adds 1 to the
    # mobility penalty of her armor". A Character's armour is already a list and
    # needs no such field.
    shield_id: str = ""

    willpower: int = 0
    essence: int = 0
    # Mote pools. `essence_pool` is a spirit's single pool; personal/peripheral
    # are the Exalted split. An entry uses one shape or the other, never both.
    essence_pool: int = 0
    personal_essence: int = 0
    peripheral_essence: int = 0
    cost_to_materialize: int = 0
    # The inverse, for elementals: p.295 makes the physical state their natural
    # one, so their blocks print "Cost To Dematerialize" (the Zephyr, p.298) where
    # a spirit prints "Cost To Materialize". Two fields, not one plus a flag —
    # the label is what a GM reads off the card.
    cost_to_dematerialize: int = 0

    # Wound penalties, one per box, deepest last. Expanded at authoring time.
    health_levels: list[int] = Field(default_factory=list)

    # Prose, never ids. See the module docstring.
    charms: str = ""
    spells: str = ""
    # The separate `Powers:` line ghosts and elementals print (the War Ghost's
    # "Materialize, Measure the Wind", the Zephyr's "Elemental Powers: Dragon's
    # Suspire, Element's Domain…"). Apart from `charms` because the book keeps it
    # apart; prose for the same reason nothing else here resolves.
    powers: str = ""
    notes: str = ""

    # ---- play-state ------------------------------------------------------- #
    # Aligned positionally to health_levels. Normalised at render time, exactly
    # as PlayState.health is, so editing the track later does not corrupt marks.
    damage: list[Optional[Damage]] = Field(default_factory=list)
    willpower_spent: int = Field(default=0, ge=0)
    motes_spent: int = Field(default=0, ge=0)
