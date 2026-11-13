"""
models/rules/_base.py — the fixed vocabularies (the trait names, the Charm types,
the spell circles) and the small models that more than one rules module uses.

This module is the bottom of the package. It imports no sibling module.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# --------------------------------------------------------------------------- #
# Fixed vocabularies
# --------------------------------------------------------------------------- #

class AttributeName(str, Enum):
    STRENGTH = "strength"
    DEXTERITY = "dexterity"
    STAMINA = "stamina"
    CHARISMA = "charisma"
    MANIPULATION = "manipulation"
    APPEARANCE = "appearance"
    PERCEPTION = "perception"
    INTELLIGENCE = "intelligence"
    WITS = "wits"


class AbilityName(str, Enum):
    # Dawn
    ARCHERY = "archery"
    BRAWL = "brawl"
    MARTIAL_ARTS = "martial_arts"
    MELEE = "melee"
    THROWN = "thrown"
    # Zenith
    ENDURANCE = "endurance"
    PERFORMANCE = "performance"
    PRESENCE = "presence"
    RESISTANCE = "resistance"
    SURVIVAL = "survival"
    # Twilight
    CRAFT = "craft"
    INVESTIGATION = "investigation"
    LORE = "lore"
    MEDICINE = "medicine"
    OCCULT = "occult"
    # Night
    ATHLETICS = "athletics"
    AWARENESS = "awareness"
    DODGE = "dodge"
    LARCENY = "larceny"
    STEALTH = "stealth"
    # Eclipse
    BUREAUCRACY = "bureaucracy"
    LINGUISTICS = "linguistics"
    RIDE = "ride"
    SAIL = "sail"
    SOCIALIZE = "socialize"


class VirtueName(str, Enum):
    COMPASSION = "compassion"
    CONVICTION = "conviction"
    TEMPERANCE = "temperance"
    VALOR = "valor"


class CharmType(str, Enum):
    REFLEXIVE = "Reflexive"
    SUPPLEMENTAL = "Supplemental"
    SIMPLE = "Simple"
    EXTRA_ACTION = "Extra Action"
    PERMANENT = "Permanent"
    SPECIAL = "Special"        # e.g. Ox-Body Technique (repeatable, permanent effect)
    ENCHANTMENT = "Enchantment"   # Mountain Folk only (CH6 p.244): a simple Charm with
    # a duration longer than instant, and no committed Essence.
    SIMPLE_ENCHANTMENT = "Simple/Enchantment"   # Living Earth Meditation (CH6 p.264):
    # the one Charm with a dual Type.


class SpellCircle(str, Enum):
    # Sorcery circles, in ascending order (core p.191).
    TERRESTRIAL = "Terrestrial"
    CELESTIAL = "Celestial"
    SOLAR = "Solar"
    # Necromancy circles, in ascending order of power (Abyssal p.223).
    SHADOWLANDS = "Shadowlands"
    LABYRINTH = "Labyrinth"
    VOID = "Void"
    # Alchemical weaving protocols (Autochthonians CH4). The installed Weaving Engine
    # Charm gates each circle.
    MAN_MACHINE = "Man-Machine"
    GOD_MACHINE = "God-Machine"


class CircleKind(str, Enum):
    """The magic discipline of a circle. Matches ExaltDefinition.magic_track. A
    Charm of one track never opens a circle of a different track (Abyssal p.223;
    Autochthonians CH4)."""
    SORCERY = "sorcery"
    NECROMANCY = "necromancy"
    WEAVING = "weaving"


# The three circles of each magic track, in ascending order, keyed by
# ExaltDefinition.magic_track. For display and track membership only. The engine
# access logic does not use it.
TRACK_CIRCLES: dict[str, tuple["SpellCircle", ...]] = {
    CircleKind.SORCERY.value: (SpellCircle.TERRESTRIAL, SpellCircle.CELESTIAL, SpellCircle.SOLAR),
    CircleKind.NECROMANCY.value: (SpellCircle.SHADOWLANDS, SpellCircle.LABYRINTH, SpellCircle.VOID),
    CircleKind.WEAVING.value: (SpellCircle.MAN_MACHINE, SpellCircle.GOD_MACHINE),
}


def circle_kind(circle: "SpellCircle") -> str:
    """Return the magic track ('sorcery' | 'necromancy') of `circle`."""
    for kind, circles in TRACK_CIRCLES.items():
        if circle in circles:
            return kind
    return CircleKind.SORCERY.value


class Source(BaseModel):
    book: str = "Core"
    page: Optional[int] = None
class Damage(str, Enum):
    """A mark in a health-track box: '/' bashing, 'x' lethal, '*' aggravated.
    An empty box is None. A Charm cost can also name the kind of health level.
    """
    BASHING = "/"
    LETHAL = "x"
    AGGRAVATED = "*"
# Display names for the glyphs.
DAMAGE_LABELS = {
    Damage.BASHING: "bashing",
    Damage.LETHAL: "lethal",
    Damage.AGGRAVATED: "aggravated",
}
class AbilityMinimum(BaseModel):
    """An Ability floor with OR semantics: the character must have `rating` in at
    least one of `abilities`. Dragon-Blooded p.151, Sidereal p.98. ⚠ Spent from the
    pool, not free dots."""
    model_config = ConfigDict(frozen=True)
    abilities: list[AbilityName]
    rating: int = Field(ge=1)
class AbilityGroupMinimum(BaseModel):
    """An Ability floor on a SUM: the total of `abilities` must be at least `rating`
    (CH6 p.230). ⚠ Spent from the pool, not free dots."""
    model_config = ConfigDict(frozen=True)
    abilities: list[AbilityName]
    rating: int = Field(ge=1)
class AttributeMinimum(BaseModel):
    """An Attribute floor with OR semantics: the character must have `rating` in at
    least one of `attributes`.

    ⚠ Not an AbilityMinimum: the chargen schooling code reads AbilityMinimum as
    Ability dots. Not `Charm.min_attribute` (Lunar, p.122), which sets the primary
    gate and the price. This is a requirement only.
    """
    model_config = ConfigDict(frozen=True)
    attributes: list[AttributeName]
    rating: int = Field(ge=1)
class BackgroundBudgetTier(BaseModel):
    """One row of a Background that buys a budget (`BackgroundRule.budget_tiers`,
    `BackgroundType.hearthstone_tiers`).

    E:Ab p.131, the Abyssal Artifact Background:

        •     Trinkets            combined ≤ 3
        ••    Sound Gear          combined ≤ 5,  none individually above 3
        •••   Well-Equipped       combined ≤ 7,  none individually above 4
        ••••  Supremely Appointed combined ≤ 10, no individual ceiling
        ••••• Divine Regalia      combined ≤ 13, no individual ceiling

    `individual_max` 0 = no ceiling for one item. The engine reports a limit as an
    ordinary chargen issue: the Storyteller can override it."""
    model_config = ConfigDict(frozen=True)

    rating: int = Field(ge=0, le=5)        # dots of the owning Background
    name: str = ""                         # the printed label ("Well-Equipped")
    combined_max: int = Field(default=0, ge=0)
    individual_max: int = Field(default=0, ge=0)   # 0 = no per-item ceiling
    # The printed number of items. 0 = no count (the Manse ladders print one).
    max_items: int = Field(default=0, ge=0)
class EssencePoolSpec(BaseModel):
    """The mote formula of a splat. derive.essence_pools reads it.

    personal = essence*personal_essence_coeff + willpower*personal_willpower_coeff
    peripheral = essence*peripheral_essence_coeff
                 + willpower*peripheral_willpower_coeff + the Virtue term

      * Solar (core p.104):      3 / 7, virtue_mode "all"
      * Dragon-Blooded (p.150-152): 1 / 4, virtue_mode "two_highest", plus Breeding.
      * Lunar (p.91):            1 / 4, personal_willpower_coeff 2, virtue_mode
        "highest", peripheral_virtue_coeff 4.

    `peripheral_virtue_mode`: "all" (sum of the Virtues), "two_highest", "highest"
    (times `peripheral_virtue_coeff`), "none".

    `breeding_background` (p.158-159): the Background whose rating indexes
    `breeding_personal` and `breeding_peripheral` (0..5, plus 6 from a Merit: see
    engine.merits.LEGENDARY_BREEDING). These add to both pools. Empty = no term.
    If a splat needs a term that this spec cannot express, stop and ask for the page."""
    model_config = ConfigDict(frozen=True)
    personal_essence_coeff: int
    personal_willpower_coeff: int = 1
    peripheral_essence_coeff: int
    peripheral_willpower_coeff: int = 1
    peripheral_virtue_mode: str = "all"     # "all" | "two_highest" | "highest" | "none"
    peripheral_virtue_coeff: int = 1        # multiplies the selected Virtue term (Lunar: 4)
    # Breeding term (p.158-159).
    breeding_background: str = ""            # Background name whose rating indexes the tables
    breeding_personal: list[int] = Field(default_factory=list)     # index by rating 0..6
    breeding_peripheral: list[int] = Field(default_factory=list)
    # A Virtue term on the personal pool (PG p.114, the unlocked mortal).
    # `personal_named_virtue` is a VirtueName value; "" adds nothing.
    personal_virtue_mode: str = "none"       # same vocabulary as peripheral_virtue_mode
    personal_virtue_coeff: int = 1
    personal_named_virtue: str = ""
    personal_named_virtue_coeff: int = 1
    # More named Virtues, added flat (PG p.177). `_named_virtue_term` sums
    # `personal_named_virtue` and this list.
    personal_named_virtues: list[str] = Field(default_factory=list)

    @field_validator("peripheral_virtue_mode", "personal_virtue_mode")
    @classmethod
    def _check_virtue_mode(cls, v: str) -> str:
        if v not in ("all", "two_highest", "highest", "none"):
            raise ValueError(
                f"peripheral_virtue_mode must be all/two_highest/highest/none, got {v!r}")
        return v
