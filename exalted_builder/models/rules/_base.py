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
    ENCHANTMENT = "Enchantment"   # Mountain Folk only (CH6 p.244): a simple Charm whose
    # effect outlasts the instant but needs no committed Essence to sustain — "the new
    # 'enchantment' type ... treated as simple Charms with a duration longer than
    # instant. However, characters need not commit Essence to sustain these ongoing
    # effects." Roughly half the Mountain Folk Charms are enchantments.
    SIMPLE_ENCHANTMENT = "Simple/Enchantment"   # Living Earth Meditation (CH6 p.264),
    # the one Charm the book prints with a dual Type — usable as either a Simple or an
    # Enchantment. One entry; kept as a distinct value rather than collapsed, because
    # the page prints it and the picker should too.


class SpellCircle(str, Enum):
    # Sorcery circles — ascend earth->Heaven (core p.191).
    TERRESTRIAL = "Terrestrial"
    CELESTIAL = "Celestial"
    SOLAR = "Solar"
    # Necromancy circles — the death-magic mirror of sorcery (Abyssal p.223). They
    # DESCEND in the fiction (toward Oblivion) but grow in power Shadowlands->
    # Labyrinth->Void, so they are ordered low-to-high power like the sorcery ones.
    SHADOWLANDS = "Shadowlands"
    LABYRINTH = "Labyrinth"
    VOID = "Void"
    # Alchemical weaving protocols — the Machine God's sorcery-analogue (Autochthonians
    # CH4). Man-Machine ~ Terrestrial Circle, God-Machine ~ Celestial Circle in power.
    # Gated ONLY by which Weaving Engine Charm is installed, exactly as the sorcery/
    # necromancy circles are gated by their initiation Charms.
    MAN_MACHINE = "Man-Machine"
    GOD_MACHINE = "God-Machine"


class CircleKind(str, Enum):
    """Which of the magic disciplines a circle belongs to. Matches
    ExaltDefinition.magic_track. The tracks never cross-grant: a known Sorcery Charm
    unlocks only sorcery circles, a Weaving Engine only weaving circles, etc.
    (Abyssal p.223; Autochthonians CH4 — "Non-Alchemicals cannot learn weaving")."""
    SORCERY = "sorcery"
    NECROMANCY = "necromancy"
    WEAVING = "weaving"


# The three circles of each magic track, ordered ascending in power. Keyed by the
# magic_track string on ExaltDefinition, so a splat's picker shows the right columns
# (Solars: Sorcery; Abyssals: Necromancy). The engine's circle-access logic is
# track-agnostic (exact-match + the initiation-Charm prerequisite chain) — this table
# is for presentation and track membership, not access.
TRACK_CIRCLES: dict[str, tuple["SpellCircle", ...]] = {
    CircleKind.SORCERY.value: (SpellCircle.TERRESTRIAL, SpellCircle.CELESTIAL, SpellCircle.SOLAR),
    CircleKind.NECROMANCY.value: (SpellCircle.SHADOWLANDS, SpellCircle.LABYRINTH, SpellCircle.VOID),
    CircleKind.WEAVING.value: (SpellCircle.MAN_MACHINE, SpellCircle.GOD_MACHINE),
}


def circle_kind(circle: "SpellCircle") -> str:
    """The magic track ('sorcery' | 'necromancy') a circle belongs to."""
    for kind, circles in TRACK_CIRCLES.items():
        if circle in circles:
            return kind
    return CircleKind.SORCERY.value


class Source(BaseModel):
    book: str = "Core"
    page: Optional[int] = None
class Damage(str, Enum):
    """A mark in a health-track box. The 1e shorthand: '/' bashing, 'x' lethal,
    '*' aggravated. (Empty boxes are None.)

    Shared vocabulary: the character marks damage in its health track, and a Charm
    cost may name which KIND of health level it spends. It lives here, with the other
    enums character.py already imports, rather than in a module of its own.
    """
    BASHING = "/"
    LETHAL = "x"
    AGGRAVATED = "*"
# Display names, for anywhere the shorthand glyph alone would not read.
DAMAGE_LABELS = {
    Damage.BASHING: "bashing",
    Damage.LETHAL: "lethal",
    Damage.AGGRAVATED: "aggravated",
}
class AbilityMinimum(BaseModel):
    """A required minimum in one of a set of Abilities (OR semantics): the character
    must have at least `rating` in AT LEAST ONE of `abilities`. A single-element list
    is a specific-ability floor. Used for the Dragon-Blooded Dynastic schooling
    minimums (p.151) and the Sidereal per-house minimums (p.98) — these are a floor
    spent from the pool, NOT free extra dots."""
    model_config = ConfigDict(frozen=True)
    abilities: list[AbilityName]
    rating: int = Field(ge=1)
class AbilityGroupMinimum(BaseModel):
    """A required minimum SUM across a GROUP of Abilities: the character's combined
    rating across all of `abilities` must be at least `rating`. AbilityMinimum is
    OR semantics (one of a set); this is sum-over-set, a different shape the
    Mountain Folk Artisan's College of Divine Enlightenment schooling demands —
    "an absolute minimum of ... •• divided among Craft Abilities" (CH6 p.230). A
    single-element group is the same as an AbilityMinimum, so groups are only used
    where the printed floor is explicitly "divided among" several Abilities. The
    floor is spent from the pool, NOT free extra dots, like AbilityMinimum."""
    model_config = ConfigDict(frozen=True)
    abilities: list[AbilityName]
    rating: int = Field(ge=1)
class AttributeMinimum(BaseModel):
    """The Attribute mirror of AbilityMinimum: the character must have at least
    `rating` in AT LEAST ONE of `attributes` (OR semantics; a single-element list is a
    specific-Attribute floor).

    Its own type rather than a widened AbilityMinimum, because AbilityMinimum is also
    the Dragon-Blooded/Sidereal chargen schooling minimum — those consumers budget
    ABILITY dots and must not be handed an Attribute.

    Distinct from `Charm.min_attribute`, which RETARGETS the primary `min_ability`
    gate at an Attribute for the Attribute-keyed splats (Lunar, p.122) and therefore
    feeds pricing and the Caste/Favoured discount. These are pure additional
    requirements and feed neither, exactly like `extra_min_abilities`.
    """
    model_config = ConfigDict(frozen=True)
    attributes: list[AttributeName]
    rating: int = Field(ge=1)
class BackgroundBudgetTier(BaseModel):
    """One row of a Background that BUYS A BUDGET rather than rating a trait directly
    (`BackgroundRule.budget_tiers`, `BackgroundType.hearthstone_tiers`).

    The Abyssal Artifact Background (E:Ab p.131) is the first of these and the reason
    the shape exists: its dots do not describe how good your artifact is, they buy a
    pool of combined artifact rating plus a ceiling on any single item —

        •     Trinkets            combined ≤ 3
        ••    Sound Gear          combined ≤ 5,  none individually above 3
        •••   Well-Equipped       combined ≤ 7,  none individually above 4
        ••••  Supremely Appointed combined ≤ 10, no individual ceiling
        ••••• Divine Regalia      combined ≤ 13, no individual ceiling

    `individual_max` is 0 for "no ceiling" — the two top rows print no limit "other
    than it cannot be N/A", and an N/A artifact has no rating to record in the first
    place (see character.ArtifactEntry). The one-dot row prints no individual cap
    either, because a combined maximum of 3 already is one.

    The per-item ceilings are ST-overridable in the text ("without Storyteller
    permission"); they are reported as ordinary chargen issues, which is how every
    other soft printed limit in this build behaves."""
    model_config = ConfigDict(frozen=True)

    rating: int = Field(ge=0, le=5)        # dots of the owning Background
    name: str = ""                         # the printed label ("Well-Equipped")
    combined_max: int = Field(default=0, ge=0)
    individual_max: int = Field(default=0, ge=0)   # 0 = no per-item ceiling
    # How many ITEMS the row permits, where the page states a count rather than
    # leaving it implied by the two maxima. 0 = uncounted, which is every Artifact row
    # and every Hearthstone row but one: the Dragon-Blooded and Abyssal Manse ladders
    # both print "She may have ONE Hearthstone of level 1 or 2" at a single dot, and
    # the maxima alone would permit two level-1 stones instead.
    max_items: int = Field(default=0, ge=0)
class EssencePoolSpec(BaseModel):
    """Per-splat motes formula as data, so derive.essence_pools is a lookup, not a
    branch. personal = essence*personal_essence_coeff + willpower*personal_willpower_coeff;
    peripheral = essence*peripheral_essence_coeff + willpower*peripheral_willpower_coeff
    + the Virtue term selected by `peripheral_virtue_mode`.

      * Solar (core p.104):      3 / 7, virtue_mode "all"          (Ess×3+WP; Ess×7+WP+ΣVirtues)
      * Dragon-Blooded (p.150-152): 1 / 4, virtue_mode "two_highest",
        plus a Breeding-Background term added to BOTH pools (see below).
      * Lunar (p.91):            1 / 4, personal_willpower_coeff 2, virtue_mode
        "highest" with peripheral_virtue_coeff 4 (Ess+WP×2; Ess×4+WP×2+highestVirtue×4).

    `peripheral_virtue_mode`: "all" adds ΣVirtues (all four, Solar), "two_highest"
    adds the sum of the two highest Virtues (Dragon-Blooded), "highest" adds only
    the single highest Virtue (Lunar — scaled by `peripheral_virtue_coeff`, since
    Lunar's term is ×4 rather than the ×1 every other splat uses), "none" adds
    nothing.

    Some splats add a flat, Background-derived bonus to both pools that plain
    coefficients can't express — the Dragon-Blooded Breeding Background (p.158-159).
    `breeding_background` names that Background; `breeding_personal`/`breeding_peripheral`
    are per-rating bonus tables indexed by the Background's rating (0..5, plus a
    rating-6 row a Merit can reach — see engine.merits.LEGENDARY_BREEDING). Empty
    tables (Solar) mean no such term. If a splat needs a term none of this can express,
    STOP and ask for the page."""
    model_config = ConfigDict(frozen=True)
    personal_essence_coeff: int
    personal_willpower_coeff: int = 1
    peripheral_essence_coeff: int
    peripheral_willpower_coeff: int = 1
    peripheral_virtue_mode: str = "all"     # "all" | "two_highest" | "highest" | "none"
    peripheral_virtue_coeff: int = 1        # multiplies the selected Virtue term (Lunar: 4)
    # Optional Background-derived additive term (DB Breeding, p.158-159).
    breeding_background: str = ""            # Background name whose rating indexes the tables
    breeding_personal: list[int] = Field(default_factory=list)     # index by rating 0..6
    breeding_peripheral: list[int] = Field(default_factory=list)
    # A Virtue term on the PERSONAL pool. Every Exalt splat's personal pool is
    # Essence/Willpower only, so these default to inert. They exist for the unlocked
    # mortal (PG p.114), whose single pool is
    #   Essence + Willpower + Conviction + (highest Virtue x 2)
    # — a NAMED Virtue added flat alongside a scaled highest-Virtue term, which
    # nothing else in this spec could express. `personal_named_virtue` is a
    # VirtueName value ("conviction"); "" adds nothing.
    personal_virtue_mode: str = "none"       # same vocabulary as peripheral_virtue_mode
    personal_virtue_coeff: int = 1
    personal_named_virtue: str = ""
    personal_named_virtue_coeff: int = 1
    # Additional named Virtues added flat, the same shape as the single
    # `personal_named_virtue`. The Dragon-Kings (PG p.177) are the first consumer:
    # their single pool is Essence x 4 + Willpower x 2 + Conviction + Valor — TWO
    # specific named Virtues, which no virtue_mode can express ("two_highest" is the
    # two highest, not Conviction+Valor specifically). `_named_virtue_term` sums the
    # single + the list, so the mortal's existing single-named-virtue formula is
    # unchanged (the list defaults empty).
    personal_named_virtues: list[str] = Field(default_factory=list)

    @field_validator("peripheral_virtue_mode", "personal_virtue_mode")
    @classmethod
    def _check_virtue_mode(cls, v: str) -> str:
        if v not in ("all", "two_highest", "highest", "none"):
            raise ValueError(
                f"peripheral_virtue_mode must be all/two_highest/highest/none, got {v!r}")
        return v
