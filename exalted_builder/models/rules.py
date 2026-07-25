"""
models/rules.py — the rulebook as data.

These models define the *shape* of static game data: Charms, spells, caste
definitions, and the cost/budget tables. They are loaded once from data/*.json
at startup and treated as immutable at runtime.

Structural validation lives here (an enum is an enum, a coefficient is a
number). Game-legality validation does NOT — it lives in engine.validate,
because legality depends on a *character* and these rules considered together.
This module therefore knows nothing about any Character.
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


# --------------------------------------------------------------------------- #
# Charms & spells
# --------------------------------------------------------------------------- #

class Source(BaseModel):
    book: str = "Exalted 1e Core"
    page: Optional[int] = None


class CharmCost(BaseModel):
    """Activation cost paid in play. Distinct from the XP/BP cost to *learn* the
    Charm, which is character-relative and computed in engine.costs."""
    motes: int = Field(default=0, ge=0)
    willpower: int = Field(default=0, ge=0)
    health: int = Field(default=0, ge=0)   # health levels spent by the Charm
    committed: bool = False                # committed motes reduce the pool until released
    raw: str = ""                          # display string; authoritative for variable costs


class CharmVariant(BaseModel):
    """One selectable package for a repeatable Charm. Ox-Body Technique: each
    purchase picks exactly one variant, `health_levels` are the wound-penalty
    levels it grants (e.g. [0] or [-1, -2, -2]), no prerequisites, `max_purchases`
    is always 1 (repeat purchases just pick a variant again, whether same or
    different). Deadly Beastman Transformation's Gifts (Lunar, p.126-127) are the
    second use of this shape: `health_levels` stays empty, `prerequisites` is an
    AND-of-OR over OTHER variant `key`s of the SAME Charm (mirrors Charm.
    prerequisites but scoped to this Charm's own variant menu, e.g. Glue-Foot
    Climbing needs Spider-Foot Climbing needs Bestial Reflexes-or-Lightning
    Speed), and `max_purchases` is 2 for the handful of Gifts that explicitly
    permit taking them twice (Bestial Reflexes, Enhanced Senses)."""
    model_config = ConfigDict(frozen=True)

    key: str
    label: str
    health_levels: list[int] = Field(default_factory=list)
    prerequisites: list[list[str]] = Field(default_factory=list)
    max_purchases: int = 1
    description: str = ""


class AbilityMinimum(BaseModel):
    """A required minimum in one of a set of Abilities (OR semantics): the character
    must have at least `rating` in AT LEAST ONE of `abilities`. A single-element list
    is a specific-ability floor. Used for the Dragon-Blooded Dynastic schooling
    minimums (p.151) and the Sidereal per-house minimums (p.98) — these are a floor
    spent from the pool, NOT free extra dots."""
    model_config = ConfigDict(frozen=True)
    abilities: list[AbilityName]
    rating: int = Field(ge=1)


class Submodule(BaseModel):
    """One purchasable upgrade to a single Alchemical Charm (p.89). A submodule
    permanently improves its parent Charm; the character has access to it whenever
    that Charm is installed. Dual cost: `bp_cost` bonus points at chargen OR
    `xp_cost` experience post-lock (the page prints both, e.g. "2 bonus points or 6
    experience points"). May carry its own minimum Essence and/or a minimum
    Attribute gate (e.g. the omnidextrous submodule "requires Wits 3+")."""
    model_config = ConfigDict(frozen=True)
    key: str                               # stable within the parent Charm
    name: str
    bp_cost: int = Field(default=0, ge=0)
    xp_cost: int = Field(default=0, ge=0)
    min_essence: int = Field(default=1, ge=1)
    min_attribute: str = ""                # optional extra Attribute gate (AttributeName value)
    min_attribute_rating: int = Field(default=0, ge=0)
    description: str = ""


class Charm(BaseModel):
    model_config = ConfigDict(frozen=True)  # rules data is immutable at runtime

    id: str
    name: str
    category: str                          # an AbilityName value, a Martial Arts style, or "sorcery"
    exalt_type: str = "Solar"              # the splat that can learn it; filters the picker
    # The elemental tree a Charm belongs to, for splats that organise Charms by
    # element (Dragon-Blooded: "Air"/"Earth"/"Fire"/"Water"/"Wood"). "" for splats
    # with no elemental axis (Solar). Authored from the page's element headings; it
    # groups the DB picker and drives the Immaculate "one elemental tree" constraint.
    element: str = ""
    # An Immaculate Order Charm — a Fivefold Dragon Method martial-arts Charm
    # (Dragon-Blooded splatbook, ch.6). These are the Charms a DB may take the
    # *Immaculate* chargen path with (5 from one elemental tree, p.151) instead of
    # the standard 7 Dragon-Blooded Charms; they also cost the Immaculate BP row.
    # False for ordinary ability Charms (all Solar Charms). Set together with
    # `element` on each Immaculate martial-arts Charm.
    immaculate: bool = False
    # A Charm learnable by ANY splat, not just `exalt_type`'s owners. Set on the
    # Terrestrial (Immaculate Dragon) martial-arts styles: nothing in 1e bars a
    # Solar from learning Terrestrial Martial Arts (it just needs a trainer). For a
    # non-DB learner such a Charm is priced/counted as an ordinary Martial Arts
    # Charm — the Immaculate chargen *package* stays Dragon-Blooded-only (see
    # engine.validate._immaculate_path, which also gates on exalt_type).
    open_to_all: bool = False
    # Exalt *tiers* that may learn this Charm on top of `exalt_type` — the middle
    # ground between one splat and `open_to_all`. Matched against
    # ExaltDefinition.tier ("Terrestrial"/"Celestial"). Set ["Celestial"] on the
    # Hungry Ghost Style (Abyssal) and Five-Dragon Style (Dragon-Blooded), which any
    # Celestial Exalt may learn; adding Lunars/Sidereals as Celestial splats grants
    # them these styles with no data or code change. Like `open_to_all`, a Charm
    # learned this way is an ordinary Martial Arts Charm for the learner.
    open_to_tiers: list[str] = Field(default_factory=list)
    type: CharmType
    min_ability: int = Field(default=0, ge=0)
    # For splats whose Charms are Attribute-keyed rather than Ability-keyed (Lunar,
    # p.122): the AttributeName value `min_ability` is the required rating in. ""
    # (default) means the Charm gates on `category`'s Ability as usual. A Charm
    # should set at most one of min_attribute / an Ability-resolving category.
    min_attribute: str = ""
    min_essence: int = Field(default=1, ge=1)
    # ADDITIONAL Ability minimums beyond `min_ability`, for the rare Charm the page
    # gates on more than one Ability. Ascendant Battle Visage (Cult of the Illuminated,
    # p.102) is the first: "Minimum Brawl: 5 / Minimum Endurance: 5".
    #
    # `min_ability` stays the PRIMARY gate — the one derived from `category` — because
    # everything downstream keys off it: the Caste/Favoured and Calling discounts, XP
    # and BP pricing, Combo cost, and the picker's tree layout. These extras are pure
    # REQUIREMENT checks and deliberately feed none of that: a Brawl Charm that also
    # needs Endurance 5 must not become cheaper for a character whose Caste Ability is
    # Endurance.
    #
    # Reuses AbilityMinimum, so each entry is an independent AND whose inner list is an
    # OR ("Brawl 5 AND Endurance 5", or hypothetically "AND (Melee 3 OR Thrown 3)").
    # Empty for all but a handful of Charms.
    extra_min_abilities: list[AbilityMinimum] = Field(default_factory=list)
    # Alchemical Charms only (p.88-91): the Personal Essence committed to *install*
    # the Charm in a Charm Slot (distinct from `cost`, the activation cost paid in
    # play). Committed for as long as the Charm is installed, so the sum over a
    # character's installed Charms is capped by the Personal pool — enforced at
    # chargen for Alchemicals. 0 for every non-Alchemical Charm.
    installation_cost: int = Field(default=0, ge=0)
    # Repeatable Charms (Ox-Body Technique; Deadly Beastman Transformation, Lunar
    # p.124-127): may be bought once per dot of this Ability/Attribute (the cap),
    # each purchase choosing from `variants`. The special value "essence" caps on
    # Character.essence_rating instead (Deadly Beastman Transformation: "no more
    # times than he has points of Essence", p.124 — Essence isn't an Ability or
    # Attribute, so it can't resolve through the normal AbilityName/AttributeName
    # lookup validate.py otherwise uses). None = not repeatable.
    repeatable_cap_ability: Optional[str] = None
    variants: list[CharmVariant] = Field(default_factory=list)
    # How many variants a single purchase selects. Ox-Body: always 1 (the default
    # for both fields below). Deadly Beastman Transformation (p.124): the FIRST
    # purchase grants 2 Gifts, every purchase after grants 1.
    variant_picks_first_purchase: int = 1
    variant_picks_per_purchase: int = 1
    # AND-of-ORs: the character must satisfy every inner group; a group is
    # satisfied if ANY of its ids is known. A flat list of single-id groups is
    # the common "all of these required" case.
    prerequisites: list[list[str]] = Field(default_factory=list)
    cost: CharmCost = Field(default_factory=CharmCost)
    duration: str = "Instant"
    keywords: list[str] = Field(default_factory=list)
    # Set on the circle-initiation Charms (e.g. Terrestrial/Celestial/Solar Circle
    # Sorcery). Lets engine.validate gate known spells on a known initiation Charm of
    # their circle. Track-agnostic: a necromancy initiation Charm sets it the same way.
    grants_circle: Optional[SpellCircle] = None
    # Charms that even the Eclipse/Moonshadow generalist rule (p.127) may NOT reach.
    # The Alchemical Weaving Engines set this: Autochthonians CH4 states outright that
    # "Non-Alchemicals cannot learn weaving Charms", so a foreign learner must never
    # acquire an engine (and thereby its Man-/God-Machine circle). Default False —
    # ordinary foreign-learnable Charms are unaffected.
    no_foreign_learning: bool = False
    # Alchemical Charms only (p.89): the upgrades available for this Charm. Empty
    # for every other splat's Charms and for Alchemical Charms with no listed
    # submodule (most of them, per the book).
    submodules: list[Submodule] = Field(default_factory=list)
    # False bars this Charm from Alchemical Arrays (p.159) — the Auxiliary Essence
    # Storage Unit and the Man-/God-Machine Weaving Engines say so explicitly. True
    # for every ordinary Charm (Arrays otherwise accept any Attribute-based Charm).
    arrayable: bool = True
    # True bars this Charm from ever being uninstalled once worn (CH3 p.141: an
    # Alchemical "cannot ever remove" either Weaving Engine). The vat refit refuses to
    # move it to the Panoply. Default False — an ordinary Charm is freely refittable.
    permanent_install: bool = False
    # Dots of PERMANENT Clarity gained by installing this Charm (CH2 p.69). Six
    # Alchemical Charms grant one each; 0 for every other Charm. Derived, not tracked:
    # removing the Charm removes the dots (p.70), which falls out of reading this off
    # the character's installed Charms.
    permanent_clarity: int = Field(default=0, ge=0)
    description: str = ""
    source: Source = Field(default_factory=Source)


class Spell(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    circle: SpellCircle
    cost: CharmCost = Field(default_factory=CharmCost)
    description: str = ""
    source: Source = Field(default_factory=Source)



class CasteDefinition(BaseModel):
    """One caste (Solar) / aspect (Dragon-Blooded) / etc. `id` is the stable
    lowercase key it is stored under in RuleSet.castes and on Character.caste
    (e.g. "dawn"); `label` is the display name ("Dawn"); `exalt_type` names the
    splat it belongs to, so a caste can be matched to a character's Exalt type."""
    model_config = ConfigDict(frozen=True)

    id: str                                # stable lowercase key, e.g. "dawn"
    exalt_type: str = "Solar"              # the splat this caste belongs to
    label: str                             # display name, e.g. "Dawn"
    caste_abilities: list[AbilityName] = Field(default_factory=list)  # the fixed caste abilities
    # Lunar castes have Caste ATTRIBUTES instead of Caste Abilities (p.90-91): Full
    # Moon = Strength/Dexterity/Stamina, Changing Moon = Charisma/Manipulation/
    # Appearance, No Moon = Perception/Intelligence/Wits — each set is exactly one
    # of engine.validate.ATTRIBUTE_CATEGORIES. Empty for Ability-caste splats
    # (Solar, Dragon-Blooded, Abyssal). A caste sets caste_abilities OR
    # caste_attributes, never both.
    caste_attributes: list[AttributeName] = Field(default_factory=list)
    # Flat XP discount this caste gets on a new spell whose circle is priced via
    # ExperienceCosts.new_spell_by_circle (Lunar No Moon: 2, p.251 — "12/15, minus 2
    # for a No Moon"). 0 (the default) for every caste that gets no such discount,
    # including the other Lunar castes. Ignored entirely by splats that price spells
    # flatly (they use the Occult-Caste/Favoured discount instead).
    spell_cost_discount: int = 0
    # Per-caste ability floors, unioned with the exalt-type-keyed budget minimums.
    # The Sidereal per-house minimums (p.98) differ by caste, unlike the DB Dynastic
    # floor which is the same for every aspect, so they live here rather than on
    # ChargenBudgets. Empty for every caste with no house-specific floor.
    required_min_abilities: list[AbilityMinimum] = Field(default_factory=list)
    # The Eclipse Caste generalist rule (core p.127): with a willing tutor, this
    # caste may learn OTHER splats' Charms, at `foreign_charm_xp_multiplier` times
    # the normal experience. False for every other caste, so the ability is data,
    # not a splat check — the Abyssal Moonshadow parallel is a one-line data change.
    # The chargen half of the rule ("may not start the game knowing" them without
    # Storyteller permission) is Character.st_foreign_charms.
    foreign_charms: bool = False
    # Only meaningful when foreign_charms is True. p.127: "Such Charms cost double
    # the normal experience to learn (usually 20 points) and use." The *use* half
    # (mote costs) is play-time math and deliberately not modelled.
    foreign_charm_xp_multiplier: int = Field(default=2, ge=1)
    # Alchemical crossover (Autochthonians p.90): an Eclipse/Moonshadow learning an
    # Alchemical Charm gains a General Charm Slot with it (the 20-XP path, priced via
    # foreign_charm_xp_multiplier), but may instead add the Charm to their Panoply
    # (no Slot) for this flat rate. None = the caste has no Alchemical-crossover Panoply
    # rate. Only meaningful alongside foreign_charms.
    foreign_panoply_charm_xp: Optional[int] = None
    description: str = ""                   # a quick flavour blurb for the caste
    anima_powers: str = ""


class GrantedCharmChoice(BaseModel):
    """One player choice within a TrainingCamp's free-Charm package.

    The Cult of the Illuminated grants free Charms in two shapes (p.90), so this
    covers both and a camp lists whichever it needs:

    * `from_categories` — "two Charms from ONE of the following four martial arts".
      The player picks a single category from the list, then `pick` Charms inside it.
    * `fixed_sets` — "one of the following pairs of Charms". The player takes exactly
      one whole set, verbatim. `pick` is ignored (a set is all-or-nothing).

    A set may offer alternates for one member where a house rule swaps a Charm
    (Spirit Strengthens the Skin replaces Iron Skin Concentration under Exalted
    Power Combat); those are authored as two separate sets, since the choice is the
    player's, not a rules branch the engine should pick."""
    model_config = ConfigDict(frozen=True)
    label: str = ""                                 # display, e.g. "Martial arts style"
    pick: int = Field(default=0, ge=0)              # how many Charms from the chosen category
    from_categories: list[str] = Field(default_factory=list)
    fixed_sets: list[list[str]] = Field(default_factory=list)


class TrainingCamp(BaseModel):
    """A training camp: an origin-scoped package of chargen requirements attached to
    a character alongside (not instead of) their Caste.

    Introduced for the Cult of the Illuminated (Solar, p.89-93), where an
    Illuminated Solar picks one of two camps — the Sequestered Tabernacle or Kether
    Rock — and that choice sets Ability floors and a free-Charm package. It is a
    THIRD axis beyond splat and caste, which is why it needs its own table rather
    than living on CasteDefinition (any caste may attend either camp) or on
    ChargenBudgets (the budget row is per-origin, and both camps share one origin).

    `origin` scopes the camp to a `Character.origin` value so the camp list a
    character may choose from is data-driven; `exalt_type` scopes it to a splat."""
    model_config = ConfigDict(frozen=True)
    id: str                                         # stable lowercase key
    exalt_type: str = "Solar"
    origin: str = ""                                # Character.origin this camp belongs to
    label: str
    description: str = ""
    # Ability floors this camp's training regimen imposes (p.89). Unioned with the
    # budget's own minimums exactly as CasteDefinition.required_min_abilities is, and
    # AbilityMinimum's OR semantics already express Kether Rock's "either Archery •
    # or Brawl •" with no new machinery.
    required_min_abilities: list[AbilityMinimum] = Field(default_factory=list)
    # Free Charms every graduate of this camp receives, by id. These do NOT come out
    # of the chargen Charm pool and do NOT count toward the Caste/Favored minimum —
    # they are granted, not picked. The character must still meet each Charm's own
    # minimum Ability/Essence ("As usual, the Solar must meet the minimum
    # requirements to gain these Charms", p.90).
    granted_charms: list[str] = Field(default_factory=list)
    # Player choices layered on top of `granted_charms`, resolved onto
    # Character.granted_charms.
    granted_charm_choices: list[GrantedCharmChoice] = Field(default_factory=list)


class Calling(BaseModel):
    """A Calling: the character's role within their organisation, which discounts a
    named set of Abilities and Charms at BOTH chargen and in play.

    Cult of the Illuminated, p.90 and p.102. Each TrainingCamp offers three. The
    discount stacks with the Caste/Favored discount and is a DISCOUNT AXIS, not a
    second Favored list — a Calling Ability is not thereby Favored, so it does not
    count toward the Caste/Favored dot minimum.

    The rates live on BonusPointCosts/ExperienceCosts (per exalt type), not here, so
    a later organisation with a different discount reuses this table unchanged."""
    model_config = ConfigDict(frozen=True)
    id: str                                         # stable lowercase key
    exalt_type: str = "Solar"
    camp: str = ""                                  # TrainingCamp.id that offers it
    label: str
    description: str = ""
    abilities: list[AbilityName] = Field(default_factory=list)
    # Calling Charms, by id. A Charm here is discounted, never granted.
    charms: list[str] = Field(default_factory=list)
    # Calling Abilities named with a parenthetical focus on the page — Paladin's
    # "Craft (War)" — record the focus so the Craft-as-per-focus-Ability machinery
    # can match the right Craft instance. Keyed by AbilityName value.
    ability_focus: dict[str, str] = Field(default_factory=dict)


class College(BaseModel):
    """One Astrological College (Sidereal, p.220-235) — a rated Advantage bought at
    chargen with its own point pool, distinct from Abilities. `house` is the caste id
    of the Maiden that governs it (journeys/serenity/battles/secrets/endings), so the
    "≥4 dots in the Colleges of his Maiden" rule (p.98) matches `house` to
    Character.caste directly; `house_label` is the printed astrological house name
    (e.g. Serenity's colleges sit in the "House of Leisure"). Sidereal-only today;
    other splats simply ship no colleges.json and never reference one."""
    model_config = ConfigDict(frozen=True)
    id: str
    name: str
    house: str                              # caste id of the governing Maiden
    house_label: str = ""                   # printed astrological house name (display)


# --------------------------------------------------------------------------- #
# Equipment catalog
#
# Catalog entries are autofill sources for the corebook gear tables. The
# character stores a *resolved inline copy* (see character.Weapon / .Armor),
# not a reference, because equipment frequently varies per character (artifacts,
# masterwork, enchantment) in a way Charms and spells never do.
# --------------------------------------------------------------------------- #

class ArmorWeight(str, Enum):
    LIGHT = "Light"
    MEDIUM = "Medium"
    HEAVY = "Heavy"
    SUPERHEAVY = "Superheavy"


class ArmorType(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    weight: ArmorWeight
    soak_lethal: int                       # corebook table is Soak (L/B)
    soak_bashing: int
    mobility_penalty: int = 0
    fatigue: int = 0
    resources_cost: int = Field(default=0, ge=0)   # dots of Resources required to buy
    # Artifact armour (0 = mundane). artifact_rating is the dots of Artifact
    # Background needed to start with it; attunement is the motes to commit.
    artifact_rating: int = Field(default=0, ge=0)
    attunement: int = Field(default=0, ge=0)
    tags: list[str] = Field(default_factory=list)


class WeaponType(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    speed: int = 0                         # melee; modifier to initiative
    accuracy: int = 0
    damage: int = 0
    damage_type: str = "L"                 # "L" lethal / "B" bashing
    defense: int = 0                       # melee
    rate: int = 0
    range: int = Field(default=0, ge=0)    # yards; 0 = melee only (thrown/archery)
    max_strength: int = Field(default=0, ge=0)   # bows: the Strength the bow is built for
    # Minimums to wield without penalty (Str / Dex / Martial Arts; 0 = none).
    min_strength: int = Field(default=0, ge=0)
    min_dexterity: int = Field(default=0, ge=0)
    min_martial_arts: int = Field(default=0, ge=0)
    # Artifact weapons (0 = mundane). artifact_rating is the dots of Artifact
    # Background needed to start with it; attunement is the motes to commit.
    artifact_rating: int = Field(default=0, ge=0)
    attunement: int = Field(default=0, ge=0)
    resources_cost: int = Field(default=0, ge=0)
    notes: str = ""                        # special cases (e.g. charge damage)
    tags: list[str] = Field(default_factory=list)


class BackgroundType(BaseModel):
    """A purchasable Background. The catalog of names a character may pick from;
    the per-character rating/descriptor lives on character.BackgroundEntry.

    Availability is a UI autofill hint (backgrounds are free text, never hard-
    validated): `exalt_type`, when set, restricts the Background to that one splat
    (Dragon-Blooded Breeding/Connections); `excluded_exalt_types` lists splats that
    may NOT take an otherwise-universal Background (the DB splatbook, oddly, bars
    Dragon-Blooded from Contacts/Influence/Followers, p.156-157)."""
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    description: str = ""
    exalt_type: str = ""                          # "" = all splats; else only this one
    excluded_exalt_types: list[str] = Field(default_factory=list)


class NatureType(BaseModel):
    """A character Nature (Archetype). Narrative only — no mechanical enforcement;
    this is the catalog the editor's Nature dropdown is populated from. The chosen
    value is stored as free text on Character.nature."""
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    description: str = ""


class MagicalMaterial(BaseModel):
    """One of the five magical materials an artifact weapon/armour can be forged
    from (core p.341). Each material resonates with exactly one Exalt type and
    grants its bonus ONLY in the hands of that type — `exalt_type` matches
    Character.exalt_type ("Solar", "Lunar", "Dragon-Blooded", ...). The weapon_*
    deltas are added to the inline weapon's stats when the wielder matches; the
    armor_* deltas do the same for armour (pending the core armour-material page —
    they default to 0). Values come from page images, never from training data."""
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    exalt_type: str                        # the Exalt the bonus applies for
    weapon_speed: int = 0
    weapon_accuracy: int = 0
    weapon_damage: int = 0
    weapon_defense: int = 0
    # Armour (core p.345-346). Soak deltas are additive; the two negate flags zero
    # out a value rather than add to it (Moonsilver removes mobility penalty,
    # Jade removes fatigue) — these depend on the base, so they can't be a delta.
    armor_soak_lethal: int = 0
    armor_soak_bashing: int = 0
    armor_negate_mobility_penalty: bool = False
    armor_negate_fatigue: bool = False
    notes: str = ""                        # narrative riders (mote drain, damage-roll effects)


# --------------------------------------------------------------------------- #
# Cost tables
# --------------------------------------------------------------------------- #

class LinearCost(BaseModel):
    """cost = current * coeff + offset. The XP increase costs are all of this
    form; the favored/caste ability discount is just offset = -1."""
    coeff: int
    offset: int = 0

    def at(self, current: int) -> int:
        return current * self.coeff + self.offset


class BonusPointCosts(BaseModel):
    """Flat per-purchase BP costs (chargen). background_above_3 applies when the
    dot being bought raises the Background above 3."""
    attribute: int = 4
    # Discount for a Caste ATTRIBUTE (Lunar, p.93 — "4 (3 if a Caste Attribute)").
    # Unused by Ability-caste splats, whose CasteDefinition.caste_attributes is
    # empty so no attribute ever qualifies; defaults equal to `attribute` so it's
    # a no-op until a splat's data row overrides it.
    attribute_caste_favored: int = 4
    ability: int = 2
    ability_favored_caste: int = 1
    background: int = 1
    background_above_3: int = 2
    specialty: int = 1
    # p.105: a specialty dot costs 1 BP, but in a Favoured/Caste Ability you get
    # this many dots per 1 BP ("2 per 1"). Cost is thus dots / this, rounded up.
    specialty_favored_caste_dots_per_point: int = 2
    virtue: int = 3
    willpower: int = 2
    essence: int = 7
    charm: int = 5
    charm_favored_caste: int = 4
    # Immaculate Order Charms (Dragon-Blooded, p.153) cost more than ordinary DB
    # Charms. Unused by splats without an Immaculate package (Solar); the discount
    # applies when the Charm's Ability is Favoured/Caste, same as `charm`.
    immaculate_charm: int = 10
    immaculate_charm_favored_caste: int = 7
    # Sidereal Martial Arts Charms cost a distinct BP rate (8/6, p.101 summary),
    # differing from the ordinary Charm 7/5. Applies to ALL Martial Arts for a
    # Sidereal (there is no Solar-only Martial Arts they cannot learn). None on
    # every other splat, falling back to `charm`/`charm_favored_caste` so their MA
    # Charms are unchanged. Immaculate MA Charms keep the immaculate rate (that
    # branch is checked first).
    martial_arts_charm: Optional[int] = None
    martial_arts_charm_favored_caste: Optional[int] = None
    # Astrological Colleges (Sidereal, p.100-101): 8 BP per dot, 6 if the College is
    # one of the character's own Maiden's. Unused by splats without colleges.
    college: int = 8
    college_own_house: int = 6
    # Calling discounts (Cult of the Illuminated, p.90 and the p.93 table). A Calling
    # is a DISCOUNT AXIS layered on top of Caste/Favoured, not a second Favored list,
    # so these rates replace `ability`/`charm` for a trait named by the character's
    # Calling and STACK with the Caste/Favoured discount. Defaults equal the
    # undiscounted rates, so a splat with no Callings is unaffected.
    calling_ability: int = 2                        # BP/dot: Calling but not Caste/Favoured
    # Calling AND Caste/Favoured: "1 point per 2 dots" (p.90). Expressed as dots-per-
    # point rather than a rate because it is a fractional cost; rounds UP, matching
    # `specialty_favored_caste_dots_per_point` (rules-authority call, 2026-07-24 —
    # the page does not say how an odd dot rounds).
    calling_ability_favored_caste_dots_per_point: int = 1
    calling_charm: int = 5                          # BP: Calling but not Caste/Favoured
    calling_charm_favored_caste: int = 4            # BP: Calling AND Caste/Favoured


class ExperienceCosts(BaseModel):
    # rating-scaled increases
    attribute: LinearCost = Field(default_factory=lambda: LinearCost(coeff=4))
    # Discount for raising a Caste ATTRIBUTE (Lunar, p.251 — "current rating x 4,
    # minus 1 if a Caste Attribute"). Defaults equal to `attribute` so it's a no-op
    # until a splat's data row overrides it; only splats with Caste Attributes
    # (Lunar) ever have an Attribute qualify. Mirrors BonusPointCosts.attribute_caste_favored.
    attribute_caste_favored: LinearCost = Field(default_factory=lambda: LinearCost(coeff=4))
    # Alchemical (Autochthonians p.64): a Caste- or Favored-Attribute costs
    # (current rating x 4) - 1. Only caste_favored-mode splats have Caste/Favored
    # ATTRIBUTES, so this rate is inert for every category-mode splat (their
    # caste-favored attribute SET is empty — validate._caste_favored_attr_names).
    attribute_favored_caste: LinearCost = Field(default_factory=lambda: LinearCost(coeff=4, offset=-1))
    ability: LinearCost = Field(default_factory=lambda: LinearCost(coeff=2))
    ability_favored_caste: LinearCost = Field(default_factory=lambda: LinearCost(coeff=2, offset=-1))
    essence: LinearCost = Field(default_factory=lambda: LinearCost(coeff=8))
    virtue: LinearCost = Field(default_factory=lambda: LinearCost(coeff=3))   # does NOT raise Willpower
    willpower: LinearCost = Field(default_factory=lambda: LinearCost(coeff=2))
    # flat "new trait" costs
    new_ability: int = 3
    new_specialty: int = 3
    # Astrological Colleges (Sidereal, p.265): a new College costs 5; raising one
    # scales at current rating × 3. Unused by splats without colleges.
    new_college: int = 5
    college: LinearCost = Field(default_factory=lambda: LinearCost(coeff=3))
    new_charm: int = 10
    new_charm_favored_caste: int = 8
    # Immaculate Order Charms (Dragon-Blooded, p.292 — "15, 12 if Favored"). Only
    # consulted for a Charm whose `immaculate` flag is set (Dragon-Blooded only);
    # defaults equal to the ordinary new_charm costs so it's a no-op for every splat
    # without an Immaculate package. Mirrors BonusPointCosts.immaculate_charm.
    new_immaculate_charm: int = 10
    new_immaculate_charm_favored_caste: int = 8
    new_spell: int = 10
    new_spell_occult_favored_caste: int = 8
    # Per-circle spell costs (Lunar, p.251 — Terrestrial 12, Celestial 15). When a
    # spell's circle is in this map the map wins and the discount becomes the
    # learner's CASTE discount (CasteDefinition.spell_cost_discount), NOT the
    # Occult-Caste/Favoured discount above — that is the whole point of a splat that
    # prices spells this way (a No Moon Lunar's −2, p.251; Occult-favoured has no
    # effect for such a splat). Empty (every other splat) => the flat new_spell path.
    new_spell_by_circle: dict[SpellCircle, int] = Field(default_factory=dict)
    foreign_charm: int = 20                # spirit Charms / other Exalt types; Eclipse only (gated in engine)
    # Per-circle spell-cost override, keyed by SpellCircle value. When a spell's
    # circle is present, it wins over the flat new_spell rate (and ignores the Occult
    # discount). Alchemical weaving protocols price this way — Man-Machine 12,
    # God-Machine 14 (Autochthonians p.64). Empty for every sorcery/necromancy splat.
    spell_cost_by_circle: dict[str, int] = Field(default_factory=dict)
    # Alchemical Charm-Slot economy (p.64). A bought Slot comes with one free Charm;
    # you pay for the SLOT, not the Charm. `new_charm` here is the flat Panoply
    # (retainer) Charm cost (6) — a Charm bought WITHOUT a Slot.
    new_charm_slot_general: int = 12
    new_charm_slot_dedicated: int = 10
    charm_slot_upgrade: int = 2            # upgrade one Dedicated Slot to General
    # Martial Arts Charm XP rate. Alchemical (11, via Perfected Lotus Matrix) and
    # Sidereal (12/10 — a distinct rate applying to ALL Martial Arts, p.265) set it;
    # None elsewhere, falling back to `new_charm`/`new_charm_favored_caste` so other
    # splats' MA Charms are unchanged.
    new_martial_arts_charm: Optional[int] = None
    new_martial_arts_charm_favored_caste: Optional[int] = None
    # Calling discounts (Cult of the Illuminated, p.102). SUBTRACTED from the computed
    # cost and explicitly stacking with the Caste/Favoured discount: "Any purchase of a
    # Calling Ability after character creation receives a 1 experience point discount.
    # This bonus stacks with the benefit of Favored or Caste Abilities." Deltas rather
    # than rates for exactly that reason. 0 = no Callings, i.e. every other splat.
    calling_ability_discount: int = 0
    calling_charm_discount: int = 0


class BackgroundRule(BaseModel):
    """Mechanical rules attached to ONE Background for ONE splat (see
    `ChargenBudgets.background_rules`).

    Backgrounds are otherwise deliberately soft in this project — free text, an
    autofill catalog, never hard-validated. The Alchemical is the first splat whose
    book gives Backgrounds actual chargen mechanics (CH2 p.65-69), so this is the
    narrow, opt-in exception: a Background with no rule behaves exactly as before.

    `expensive_above`/`expensive_dot_cost` model a Background whose upper dots cost
    more than one dot of the chargen pool each (Alchemical Artifact: "the fourth and
    fifth dot still cost two (2) dots each"). `cap_pre_bp_exempt` lets a Background
    exceed `background_cap_pre_bp` without bonus points ("only Artifact may be higher
    than 3 without bonus points"). `min_rating` is a rating the splat receives
    automatically ("Alchemical Exalted automatically receive Class ••• during
    character creation"). `requires`/`requires_rating` gate one Background on another
    (Backing "requires Class •••+ as a prerequisite")."""
    model_config = ConfigDict(frozen=True)

    cap_pre_bp_exempt: bool = False
    expensive_above: int = 0               # 0 = every dot costs one pool dot
    expensive_dot_cost: int = Field(default=1, ge=1)
    min_rating: int = Field(default=0, ge=0)
    # Dots granted FREE, i.e. on top of the pool rather than out of it. Distinct from
    # min_rating, which is a floor the character must reach by SPENDING pool dots
    # (Alchemical Class •••, CH2 p.61). The Illuminated Solar "begins with
    # Illumination • for free" IN ADDITION to nine Background dots (p.90), so the
    # first dot costs nothing and dots above it cost one each.
    free_rating: int = Field(default=0, ge=0)
    requires: str = ""                     # another Background's NAME, lowercased
    requires_rating: int = Field(default=0, ge=0)


class ChargenBudgets(BaseModel):
    # attributes: 8/6/4 across the three prioritized categories; all start at 1.
    # Which category gets which pool is derived from the per-category spend, not stored.
    attribute_pools: tuple[int, int, int] = (8, 6, 4)
    attribute_base: int = 1
    # How the three attribute_pools are allocated:
    #   "category"      — the default for every prior splat: the pools are matched to
    #                     the three prioritized categories (Physical/Social/Mental) by
    #                     spend, and each category's caste-favoredness (Lunar) only
    #                     affects the over-spend RATE.
    #   "caste_favored" — Alchemical (p.60): the pools are NOT category pools. They are
    #                     assigned in FIXED order to three disjoint attribute SETS —
    #                     the caste's Caste Attributes (pools[0]), the player's chosen
    #                     Favored Attributes (pools[1]), and the remaining attributes
    #                     (pools[2]). Caste and Favored attributes share the discounted
    #                     over-spend rate (bonus_costs.attribute_caste_favored).
    attribute_mode: str = "category"
    # caste_favored mode only: how many Favored Attributes the player selects (3 for
    # Alchemical), and the minimum rating each Caste Attribute must reach ("none may
    # have a rating lower than 2", p.60). 0 = not applicable (every category-mode splat).
    attribute_favored_count: int = 0
    attribute_caste_min: int = 0

    # Required minimum Abilities the character must meet (a floor spent from the
    # pool, not free extras). Dragon-Blooded Dynastic schooling (p.151); empty for
    # splats/origins with no such floor (Solar, DB Outcaste).
    required_min_abilities: list[AbilityMinimum] = Field(default_factory=list)

    # Abilities that MUST be among the character's Favored set (not just dotted) —
    # the Lunar rule that Survival is always Favored (p.90). Empty for splats with
    # no such forced inclusion (Solar, Dragon-Blooded, Abyssal).
    required_favored: list[AbilityName] = Field(default_factory=list)

    ability_dots: int = 25
    ability_min_caste_favored: int = 10    # >= 10 of the 25 on caste/favored abilities
    ability_cap_pre_bp: int = 3
    favored_count: int = 5                 # >= 1 dot required in each favored ability

    background_dots: int = 7
    background_cap_pre_bp: int = 3
    # Per-Background mechanical rules, keyed by the Background's NAME lowercased
    # (character.BackgroundEntry.name is free text, not an id, so this cannot key on
    # BackgroundType.id). Empty for every splat whose Backgrounds are purely narrative
    # — which was ALL of them until the Alchemical (CH2 p.65-69) introduced the first
    # Backgrounds with real mechanics. Per-splat because the rules modify otherwise
    # universal Backgrounds: Artifact is ordinary for a Solar and heavily reworked for
    # an Alchemical, so the mechanics cannot live on the shared BackgroundType.
    background_rules: dict[str, BackgroundRule] = Field(default_factory=dict)
    # Backgrounds this origin may take AT ALL, as lowercased NAMEs (matching
    # background_rules' keying). Empty = unrestricted, which is every splat except the
    # Sidereal ronin, who are "limited to the Backgrounds of Acquaintances, Allies,
    # Artifact, Backing, Connections, Familiar, Manse and Resources" (p.100). This is
    # the ONLY hard Background validation in the project — Backgrounds are otherwise
    # deliberately soft free text — so it is opt-in per origin and checked by name.
    # The same paragraph's "no Backing from or Connections with any of the Sidereal
    # factions or Celestial Bureaus" is narrative and is NOT modelled.
    allowed_backgrounds: list[str] = Field(default_factory=list)
    # Suppress the CASTE's own required_min_abilities for this origin. The ronin
    # "have no minimum required Ability scores" (p.100), but a ronin still HAS a
    # Caste, so the per-house floor on CasteDefinition would otherwise still apply.
    # The budget's own required_min_abilities list is simply empty for such a row.
    ignore_caste_min_abilities: bool = False

    # Astrological Colleges (Sidereal, p.98) — a rated Advantage with its OWN point
    # pool, separate from Abilities and Backgrounds. `college_dots` 0 (the default)
    # means the splat has no colleges (every non-Sidereal). `college_min_own_house`
    # is how many of those dots must be in the character's Maiden's Colleges.
    college_dots: int = 0
    college_min_own_house: int = 0
    college_cap_pre_bp: int = 3

    virtue_dots: int = 5                   # spent over a base of 1 each
    virtue_base: int = 1
    virtue_cap_pre_bp: int = 3

    charm_count: int = 10
    charm_min_caste_favored: int = 5
    # Sidereal, p.101: "no more than 3 [chargen Charms] may be from a Sidereal Martial
    # Arts form; ronin ... none from Sidereal Martial Arts". A "form" is a supernatural
    # SMA style — a martial_arts Charm that is `open_to_tiers` (Celestial-open); the
    # Violet Bier of Sorrows auspicious tree is NOT open_to_tiers and is uncapped. None
    # = no cap (every other splat). 0 = barred (the Sidereal ronin).
    martial_arts_form_charm_cap: Optional[int] = None
    # Charm Slot system (Alchemical, p.88-89): instead of pricing Charms per pick,
    # the character has a fixed number of General Slots (hold any Charm) and
    # Dedicated Slots (hold only a Caste/Favored-Attribute Charm); every Slot comes
    # with one free Charm. These are the FREE (chargen) slot counts. When either is
    # > 0 the splat is slot-based: charm accounting switches from per-pick to
    # per-slot (extra General/Dedicated slots cost bonus_costs.charm/charm_favored_caste),
    # and the caste-favored charm rule becomes "non-Caste/Favored Charms must fit
    # the General Slots". 0/0 (every other splat) keeps the per-pick model.
    charm_slots_general: int = 0
    charm_slots_dedicated: int = 0
    # The alternative Immaculate chargen path (Dragon-Blooded, p.151): a character
    # learning Immaculate martial arts takes this many Charms instead of charm_count,
    # all from a single elemental tree, and the charm_min_caste_favored rule is
    # waived. Only reachable when the character selects Immaculate Order Charms, so it
    # never affects splats without them (Solar).
    immaculate_charm_count: int = 5

    essence_start: int = 2
    # Hard ceiling on Essence at the END of character creation, i.e. after bonus
    # points. Cult of the Illuminated (p.90): an Illuminated Solar starts at Essence
    # 3 and "under no circumstances may begin with an Essence of six (6) or higher",
    # so 5. 0 = no ceiling beyond whatever the BP budget can afford, which is every
    # other splat authored so far.
    essence_start_cap: int = 0
    # This origin requires the character to pick a TrainingCamp / Calling (see
    # rules.TrainingCamp). False for every splat without them, which is all of them
    # except the Illuminated Solar.
    requires_camp: bool = False
    requires_calling: bool = False
    bonus_points: int = 15

    willpower_start_cap: int = 8           # may not start above this...
    willpower_cap_exception_virtue: int = 4   # ...unless at least
    willpower_cap_exception_count: int = 2    # this many Virtues are >= 4

    @field_validator("attribute_mode")
    @classmethod
    def _check_attribute_mode(cls, v: str) -> str:
        if v not in ("category", "caste_favored"):
            raise ValueError(
                f"attribute_mode must be category/caste_favored, got {v!r}")
        return v


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
    are per-rating bonus tables indexed by the Background's rating (0..5). Empty tables
    (Solar) mean no such term. If a splat needs a term none of this can express, STOP
    and ask for the page."""
    model_config = ConfigDict(frozen=True)
    personal_essence_coeff: int
    personal_willpower_coeff: int = 1
    peripheral_essence_coeff: int
    peripheral_willpower_coeff: int = 1
    peripheral_virtue_mode: str = "all"     # "all" | "two_highest" | "highest" | "none"
    peripheral_virtue_coeff: int = 1        # multiplies the selected Virtue term (Lunar: 4)
    # Optional Background-derived additive term (DB Breeding, p.158-159).
    breeding_background: str = ""            # Background name whose rating indexes the tables
    breeding_personal: list[int] = Field(default_factory=list)     # index by rating 0..5
    breeding_peripheral: list[int] = Field(default_factory=list)

    @field_validator("peripheral_virtue_mode")
    @classmethod
    def _check_virtue_mode(cls, v: str) -> str:
        if v not in ("all", "two_highest", "highest", "none"):
            raise ValueError(
                f"peripheral_virtue_mode must be all/two_highest/highest/none, got {v!r}")
        return v


class ExaltDefinition(BaseModel):
    """One Exalt type as data. `id` matches Character.exalt_type ("Solar","Abyssal").
    Holds the splat's essence formula, its magic track (sorcery vs necromancy — see
    SpellCircle), the circle barred at character creation, and the id of its
    repeatable Ox-Body-equivalent Charm. Values come from the page, never memory."""
    model_config = ConfigDict(frozen=True)
    id: str
    label: str
    essence: EssencePoolSpec
    magic_track: str = "sorcery"            # "sorcery" | "necromancy"
    # The circle this splat may NOT begin play knowing — withheld at chargen (Solars:
    # "Solar", core p.100). This is the chargen bar, NOT the splat's reachable ceiling:
    # set it "" (nothing barred) for a splat whose entry circle is also its cap, e.g.
    # Dragon-Blooded (Terrestrial only) — barring their one circle would bar all their
    # sorcery at creation. Read only by validate.chargen_barred_circle.
    highest_magic_circle_id: str = ""       # e.g. "Solar"; "" = nothing barred at chargen
    ox_body_charm_id: str = ""              # the splat's repeatable health-level Charm
    # The splat's repeatable multi-variant-pick Charm, if it has one (Lunar:
    # Deadly Beastman Transformation, p.124-127 — see Charm.variant_picks_*).
    # "" for every splat without one (everyone but Lunar today).
    gift_charm_id: str = ""
    # Does this splat keep a Form Library — a Totem plus the animal shapes it can
    # wear (the "Totem" field on the 1e Lunar sheet)? Purely narrative bookkeeping,
    # never validated or priced; this flag only decides whether the UI offers the
    # page at all. True for Lunar; a later shapeshifting splat can opt in as data.
    form_library: bool = False
    # Does this splat use Clarity in place of Limit (CH2 p.69-71)? True for Alchemical,
    # who took no part in the Great Curse and so have no Limit at all. Decides whether
    # the tracker shows Clarity or Limit; the permanent half is derived in
    # engine.derive.clarity, the temporary half tracked on PlayState.
    clarity: bool = False
    # What this splat calls its Limit track. Sidereals call the Great Curse's meter
    # "Paradox" (p.253) — a pure RENAME, identical 0-10 mechanic, so it is a label and
    # not a second code path. Ignored entirely when `clarity` is True (the Alchemical
    # has no Limit at all to rename). Presentation only.
    limit_label: str = "Limit"
    # What this splat calls its caste slot in the UI: Solars have "Caste", the
    # Dragon-Blooded have "Aspect". Presentation only — the underlying field is
    # still Character.caste keyed to RuleSet.castes.
    caste_noun: str = "Caste"
    # Which tier of Exalt this splat is: "Celestial" (Solar, Lunar, Sidereal,
    # Abyssal) or "Terrestrial" (Dragon-Blooded). Read only by
    # validate.charm_matches_splat, against Charm.open_to_tiers, to open a
    # tier-wide Martial Arts style to splats other than the one that authored it.
    tier: str = "Celestial"


# The canonical Solar definition — the existing hardcoded formula moved into data
# (the values are the verified core-p.104 Solar pools, not new rules). Used as the
# default when no exalts.json is loaded and as the fallback for an unknown exalt_type.
SOLAR_EXALT = ExaltDefinition(
    id="Solar",
    label="Solar Exalted",
    essence=EssencePoolSpec(personal_essence_coeff=3, peripheral_essence_coeff=7,
                            peripheral_virtue_mode="all"),
    magic_track="sorcery",
    highest_magic_circle_id="Solar",
    ox_body_charm_id="solar.endurance.ox-body-technique",
)


# --------------------------------------------------------------------------- #
# Storyteller reference screen
#
# A purely presentational block of rules tables (the tri-fold GM screen, p.2-3 of
# `images/exaltedscreen-20050917.pdf`), rendered read-only in the GM party page.
# It carries NO game logic and is never referenced by id, keyed, or consumed by the
# engine — it is display text, the digital equivalent of a printed screen. Modeled
# as generic tables so any rules table drops in without a bespoke shape.
# --------------------------------------------------------------------------- #

class RefTable(BaseModel):
    """One titled reference table: a header row (`columns`) over `rows`, each row a
    list of cells matching the columns. `note` is an optional footnote below it.
    A `columns`-less table renders as a bare list of rows (e.g. a step sequence)."""
    title: str
    columns: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)
    note: str = ""


class RefGroup(BaseModel):
    """A named panel of related tables (e.g. "Combat")."""
    title: str
    tables: list[RefTable] = Field(default_factory=list)


class StScreen(BaseModel):
    """The whole Storyteller reference screen: named groups of tables."""
    title: str = "Storyteller Reference"
    groups: list[RefGroup] = Field(default_factory=list)


class RuleSet(BaseModel):
    """The whole rulebook in memory. Charms and spells are indexed by id for
    O(1) prerequisite resolution and load-time link-checking.

    The cost/budget tables are keyed by Exalt type so different splats can carry
    different chargen budgets / XP costs. The shared baseline lives under the
    "default" key; a splat that differs adds an entry under its own exalt_type and
    the `*_for(exalt_type)` accessors fall back to "default" otherwise. (This module
    knows nothing about Character, so the accessors take the exalt_type string, not
    a Character.)"""
    exalts: dict[str, ExaltDefinition] = Field(
        default_factory=lambda: {SOLAR_EXALT.id: SOLAR_EXALT})
    castes: dict[str, CasteDefinition]     # keyed by CasteDefinition.id
    charms: dict[str, Charm]
    spells: dict[str, Spell] = Field(default_factory=dict)
    armor_catalog: dict[str, ArmorType] = Field(default_factory=dict)
    weapon_catalog: dict[str, WeaponType] = Field(default_factory=dict)
    background_catalog: dict[str, BackgroundType] = Field(default_factory=dict)
    nature_catalog: dict[str, NatureType] = Field(default_factory=dict)
    material_catalog: dict[str, MagicalMaterial] = Field(default_factory=dict)
    colleges: dict[str, College] = Field(default_factory=dict)   # Astrological Colleges (Sidereal)
    camps: dict[str, TrainingCamp] = Field(default_factory=dict)  # Training camps (Illuminated Solar)
    callings: dict[str, Calling] = Field(default_factory=dict)    # Callings (Illuminated Solar)
    bonus_costs: dict[str, BonusPointCosts] = Field(
        default_factory=lambda: {"default": BonusPointCosts()})
    xp_costs: dict[str, ExperienceCosts] = Field(
        default_factory=lambda: {"default": ExperienceCosts()})
    budgets: dict[str, ChargenBudgets] = Field(
        default_factory=lambda: {"default": ChargenBudgets()})
    # Optional read-only GM reference screen (data/st_screen.json). None when absent.
    st_screen: Optional[StScreen] = None

    def exalt_for(self, exalt_type: str) -> ExaltDefinition:
        """The ExaltDefinition for `exalt_type`, falling back to Solar if the type
        is unknown (engine.validate.check_exalt_type surfaces the bad value as an
        Issue separately, so derivation still produces a number instead of crashing)."""
        return self.exalts.get(exalt_type) or self.exalts.get("Solar") or SOLAR_EXALT

    def bonus_costs_for(self, exalt_type: str) -> BonusPointCosts:
        return self.bonus_costs.get(exalt_type, self.bonus_costs["default"])

    def xp_costs_for(self, exalt_type: str) -> ExperienceCosts:
        return self.xp_costs.get(exalt_type, self.xp_costs["default"])

    def backgrounds_for(self, exalt_type: str) -> list[BackgroundType]:
        """The Backgrounds a character of `exalt_type` may pick from (the editor's
        autofill list). A splat-restricted Background (`exalt_type` set) shows only
        for that splat; a Background listing `exalt_type` in `excluded_exalt_types`
        is hidden from it (DB bar Contacts/Influence/Followers). Universal ones (no
        restriction) show for everyone. Order follows the catalog's insertion order."""
        out: list[BackgroundType] = []
        for bg in self.background_catalog.values():
            if bg.exalt_type and bg.exalt_type != exalt_type:
                continue
            if exalt_type in bg.excluded_exalt_types:
                continue
            out.append(bg)
        return out

    def camps_for(self, exalt_type: str, origin: str = "") -> list[TrainingCamp]:
        """The training camps a character of this splat/origin may attend, in table
        order. Empty for every splat with no camps, which is how the UI decides
        whether to render the picker at all."""
        return [c for c in self.camps.values()
                if c.exalt_type == exalt_type and (not c.origin or c.origin == origin)]

    def callings_for(self, camp_id: str) -> list[Calling]:
        """The Callings offered by one camp, in table order."""
        return [c for c in self.callings.values() if c.camp == camp_id]

    def budgets_for(self, exalt_type: str, origin: str = "") -> ChargenBudgets:
        """The chargen budget for `exalt_type`, optionally specialised by `origin`
        (an intra-splat variant such as Dragon-Blooded Dynastic vs Outcaste). Tries
        the origin-keyed row `"<exalt_type>:<origin>"` first, then the plain
        exalt_type row, then "default". (Character-free: takes strings, not a
        Character, so this module never imports the character model.)"""
        if origin:
            keyed = self.budgets.get(f"{exalt_type}:{origin}")
            if keyed is not None:
                return keyed
        return self.budgets.get(exalt_type, self.budgets["default"])
