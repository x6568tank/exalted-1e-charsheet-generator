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
# Thaumaturgy is not a splat and not an origin. It is a layer that any character can
# hold (p.114; see ExaltDefinition.thaumaturgy_usable).
#
# Four branches (p.113):
#   Arts       - BINARY. Trained = +2 dice. Specialties +1 die each, max two
#                applied to a roll. Buyable WITHOUT the parent Art.
#   Sciences   - RATED, with printed per-dot descriptions.
#   Rituals    - LEVELLED 1-5, gated only on Occult >= level.
#   Formulas   - rote recipes for a Science, cheapest of all.
#
# Resolution is out of scope (decision 0016). `roll`/`cost`/`time` are display
# strings. The engine does not parse them.
# --------------------------------------------------------------------------- #

class Orientation(str, Enum):
    """The regional version of a ritual or formula (p.124). Each extra version costs
    1 point, thus a holding is (id, {orientations}), not an id. The casting penalties
    are out of scope."""
    NORTH = "North"
    SOUTH = "South"
    EAST = "East"
    WEST = "West"
    REALM = "Realm"


class ThaumaturgicAspect(BaseModel):
    """One field of an Art: Summoning "ghosts", Warding "the Wyld".

    An aspect is a printed general specialty (p.126). It costs the Art Specialty
    rate. A narrower player specialty adds +1 more. Two specialties at most apply to
    a roll: the maximum is +4.

    ⚠ **No Art is required to buy one** (p.126). Do not add a prerequisite.

    `min_occult`: only Summoning gates each aspect (p.126-129). 0 = no gate except
    the `min_occult` of the Art."""
    model_config = ConfigDict(frozen=True)
    id: str
    name: str
    min_occult: int = Field(default=0, ge=0)
    description: str = ""


class ThaumaturgicArt(BaseModel):
    """One Art (p.126-135). Not rated: training gives +2 dice.

    `aspects`: the general-specialty menu (see ThaumaturgicAspect). `specialties`:
    a printed specialty list separate from the aspects. Empty for all four Arts.
    A player specialty is free text on the character (p.126)."""
    model_config = ConfigDict(frozen=True)
    id: str
    name: str
    min_occult: int = Field(default=1, ge=0)
    roll: str = ""                          # display, e.g. "Charisma + Occult"
    cost: str = ""                          # display, e.g. "3 motes per attempt"
    aspects: list[ThaumaturgicAspect] = Field(default_factory=list)
    specialties: list[str] = Field(default_factory=list)   # suggested, not exhaustive
    # Summoning only (p.127): a narrowed aspect costs half.
    aspect_narrowing: bool = False
    description: str = ""
    source: Source = Field(default_factory=Source)


class ScienceLevel(BaseModel):
    """One printed rung of a Science, keyed by `rating`.

    ⚠ The ladder has gaps: Alchemy has no five-dot rung, but rating 5 is legal
    (p.143). Do not renumber the six-dot entry."""
    model_config = ConfigDict(frozen=True)
    rating: int = Field(ge=1)
    description: str = ""


class ThaumaturgicScience(BaseModel):
    """One Science (p.136-148). The only rated branch.

    `max_rating` is 6 for Alchemy (see ScienceLevel). ⚠ The usual <=5 bound does not
    apply."""
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
        """Return the printed rung at `rating`. Return None if the book has none
        (Alchemy 5). A missing rung is legal."""
        return next((lv for lv in self.levels if lv.rating == rating), None)


class ThaumaturgicRitual(BaseModel):
    """One ritual (p.148-150). Level 1-5. The character needs Occult >= level.

    The character can also carry a custom ritual inline (p.148).

    The source has no stat block. `cost`/`roll`/`difficulty` are taken from the
    prose. `description` is the reference."""
    model_config = ConfigDict(frozen=True)
    id: str
    name: str
    level: int = Field(ge=1, le=5)
    cost: str = ""                          # display, e.g. "1 mote or one Willpower"
    roll: str = ""                          # display; many rituals print none
    resources: str = ""                     # display, e.g. "Resources 2" for components
    description: str = ""
    source: Source = Field(default_factory=Source)
    # Set by the loader on a row from the custom library, as `Charm.custom`.
    # ⚠ A ritual for one character is an inline `RitualEntry` with no `ritual_id`,
    # not a row here.
    custom: bool = False


class ThaumaturgicFormula(BaseModel):
    """One formula or procedure of a Science (p.138-142).

    `materials_raw` overrides the Resources cost when set."""
    model_config = ConfigDict(frozen=True)
    id: str
    name: str
    science_id: str                         # the Science it belongs to, e.g. "alchemy"
    # ⚠ Not bounded at 5: Alchemy reaches 6.
    level: int = Field(ge=1)
    roll: str = ""                          # display, normally "Intelligence + Occult"
    difficulty: Optional[int] = None
    materials_resources: Optional[int] = None
    materials_raw: str = ""                 # authoritative when set
    effects: str = ""
    addiction: str = ""
    source: Source = Field(default_factory=Source)
