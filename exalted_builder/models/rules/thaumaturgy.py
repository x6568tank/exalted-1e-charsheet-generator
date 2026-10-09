"""
models/rules/thaumaturgy.py — the Thaumaturgy models (Player's Guide CH3): the
Arts, the Sciences, the Rituals, and the Formulas.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from ._base import Source


# --------------------------------------------------------------------------- #
# Thaumaturgy (Player's Guide CH3)
#
# Thaumaturgy is NOT a splat and NOT an origin: it is an orthogonal capability
# layer. p.114 — the Exalted learn it "without any difficulty", the Wyld-tainted
# "with no restraint", Dragon Kings can, spirits pay double, the Fair Folk not at
# all, and the dead retain what they learned but may never use it (see
# ExaltDefinition.thaumaturgy_usable). It therefore keys off nothing; any
# character may hold it.
#
# Four branches, four different mechanical shapes (p.113):
#   Arts       - BINARY. Trained = +2 dice. Specialties +1 die each, max two
#                applied to a roll. Buyable WITHOUT the parent Art.
#   Sciences   - RATED, with printed per-dot descriptions.
#   Rituals    - LEVELLED 1-5, gated only on Occult >= level.
#   Formulas   - rote recipes for a Science, cheapest of all.
#
# Everything the chapter says about RESOLVING these (ward Strength/Durability,
# the banishment table, summoning difficulties, internal-alchemy failure, the
# four ways to pay a cost) is dice resolution and deliberately OUT OF SCOPE, the
# same call as combat derivation. `roll`/`cost`/`time` below are display strings
# the engine never parses.
# --------------------------------------------------------------------------- #

class Orientation(str, Enum):
    """The regional version of a ritual or formula (p.124). Every ritual and
    formula has one. Casting one from a foreign orientation costs +1 difficulty at
    one region away and +2 at two, with prep time x2/x5 — all of which is dice
    resolution and out of scope. What IS in scope is that a thaumaturge may learn
    several versions of the same spell, each extra costing a flat 1 point, so a
    character's holding is (id, {orientations}) and never a bare id."""
    NORTH = "North"
    SOUTH = "South"
    EAST = "East"
    WEST = "West"
    REALM = "Realm"


class ThaumaturgicAspect(BaseModel):
    """One sub-field of an Art — Summoning's "ghosts", Warding's "the Wyld".

    **An aspect IS a printed general specialty.** The source uses both words for
    one thing: the stat block heads the list "Aspects:", while the prose (p.126)
    says "each field of study is further subdivided into a number of specialties"
    and "Each art lists a number of specialties". The worked example settles it by
    using a printed aspect as its middle term — "mastering the Art (Warding, +2),
    a general specialty in the Art (Fair Folk, +1) and a relevant specialty (Local
    Fair Folk, +1)" — and "Fair Folk" is an item on Warding's Aspects line.

    So: buying an aspect is buying a specialty, at the Art Specialty rate, and a
    player-invented narrower specialty stacks on top for another +1. At most TWO
    specialties apply to any one roll, so the ceiling is +4 (Art +2, general +1,
    narrow +1).

    **No Art is required to buy one** (p.126, and the BP-table footnote): "A
    thaumaturge does not need to buy a field of study in order to purchase a
    specialty in that field, and many do not." Never add a prerequisite.

    `min_occult` is 0 for most: only Summoning gates its aspects individually
    (Beasts/Mortals •, Demons/Elementals ••, Ghosts/Spirits •••, p.126-129).
    Warding, Exorcism and Astrology print aspect lists with no per-aspect gate, so
    0 means "no gate beyond the parent Art's own min_occult"."""
    model_config = ConfigDict(frozen=True)
    id: str
    name: str
    min_occult: int = Field(default=0, ge=0)
    description: str = ""


class ThaumaturgicArt(BaseModel):
    """One Art (p.126-135). Binary, not rated: training grants a flat +2 dice.

    `aspects` is the printed general-specialty menu — see ThaumaturgicAspect; an
    aspect and a specialty are the same purchase. `specialties` is a spare slot for
    any Art that ever prints a specialty list SEPARATE from its Aspects line; none
    of the four do, so it is empty everywhere today. Player-invented specialties
    are free text on the character (the Backgrounds precedent), because the book
    explicitly invites them: "a character could choose to buy a specialty of 'Local
    Fair Folk' for the Art of Warding" (p.126)."""
    model_config = ConfigDict(frozen=True)
    id: str
    name: str
    min_occult: int = Field(default=1, ge=0)
    roll: str = ""                          # display, e.g. "Charisma + Occult"
    cost: str = ""                          # display, e.g. "3 motes per attempt"
    aspects: list[ThaumaturgicAspect] = Field(default_factory=list)
    specialties: list[str] = Field(default_factory=list)   # suggested, not exhaustive
    # Summoning only (p.127): further limiting an aspect ("Summoning (War Gods)")
    # halves that aspect's cost. No other Art prints the option.
    aspect_narrowing: bool = False
    description: str = ""
    source: Source = Field(default_factory=Source)


class ScienceLevel(BaseModel):
    """One printed dot-rung of a Science. Keyed by `rating` rather than held in a
    positional list BECAUSE THE LADDER IS SPARSE: Alchemy prints • •• ••• •••• and
    then ••••••, with no five-dot rung, yet two printed formulas require Alchemy
    ••••• and the stated rule is that a formula's required level equals its
    difficulty (p.143). Rating 5 is thus reachable and purchasable with no
    description. Never renumber the six-dot entry down to close the gap."""
    model_config = ConfigDict(frozen=True)
    rating: int = Field(ge=1)
    description: str = ""


class ThaumaturgicScience(BaseModel):
    """One Science: Alchemy, Enchantment, Geomancy or Weather Working (p.136-148).
    The only rated branch of thaumaturgy.

    `max_rating` is per-Science and is 6 for Alchemy — see ScienceLevel. Do not
    assume the project's usual <=5 rating bound applies here; that bound is a
    convention that holds because chargen rarely exceeds 5, not an invariant."""
    model_config = ConfigDict(frozen=True)
    id: str
    name: str
    roll: str = ""                          # display, e.g. "Dexterity + Occult"
    cost: str = ""                          # display, e.g. "3 motes per level of effect"
    time: str = ""                          # display, e.g. "one day per dot of effect"
    duration: str = ""                      # display
    max_rating: int = Field(default=5, ge=1)
    levels: list[ScienceLevel] = Field(default_factory=list)   # sparse; keyed by rating
    description: str = ""
    source: Source = Field(default_factory=Source)

    def level(self, rating: int) -> Optional[ScienceLevel]:
        """The printed rung at `rating`, or None where the book prints none
        (Alchemy 5). A missing rung is legal, not a data error."""
        return next((lv for lv in self.levels if lv.rating == rating), None)


class ThaumaturgicRitual(BaseModel):
    """One ritual (p.148-150). Levelled 1-5; "the only normal restriction on
    purchasing a ritual is that a thaumaturge must have an Occult score equal to
    or higher than the ritual's level".

    The chapter prints exactly five, and the book expects more to be written
    (p.148: "there are few constant rules, but there are guidelines"), so the
    catalogue is a seed and the character may also carry custom rituals inline —
    the editable-custom-weapons precedent.

    Rituals have NO stat block in the source: the heading is the name with its dot
    rating inline and everything else is prose. `cost`/`roll`/`difficulty` are
    therefore best-effort display strings pulled out of that prose, and
    `description` remains authoritative."""
    model_config = ConfigDict(frozen=True)
    id: str
    name: str
    level: int = Field(ge=1, le=5)
    cost: str = ""                          # display, e.g. "1 mote or one Willpower"
    roll: str = ""                          # display; many rituals print none
    resources: str = ""                     # display, e.g. "Resources 2" for components
    description: str = ""
    source: Source = Field(default_factory=Source)
    # Stamped by the loader on a row that came from the user's library, exactly as
    # `Charm.custom` and `Spell.custom` are. ⚠ Rituals are the ONE catalogue with a
    # second custom shape beside this one: a ritual authored for a single character
    # is an inline `RitualEntry` with no `ritual_id`, and never becomes a row here.
    custom: bool = False


class ThaumaturgicFormula(BaseModel):
    """One formula or procedure — a rote recipe belonging to a Science (p.138-142).
    Unlike rituals these DO have a labelled stat block: Name / Alchemy / Roll /
    Difficulty / Cost of Materials / Effects / Addiction.

    `materials_raw` wins when set, because one printed formula costs "Equal to
    poison cost" rather than a number of Resources dots."""
    model_config = ConfigDict(frozen=True)
    id: str
    name: str
    science_id: str                         # the Science it belongs to, e.g. "alchemy"
    # The Science rating required. NOT bounded at 5: Alchemy reaches 6.
    level: int = Field(ge=1)
    roll: str = ""                          # display, normally "Intelligence + Occult"
    difficulty: Optional[int] = None
    materials_resources: Optional[int] = None
    materials_raw: str = ""                 # authoritative when set
    effects: str = ""
    addiction: str = ""
    source: Source = Field(default_factory=Source)
