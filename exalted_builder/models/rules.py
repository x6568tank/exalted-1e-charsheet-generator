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
    TERRESTRIAL = "Terrestrial"
    CELESTIAL = "Celestial"
    SOLAR = "Solar"


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
    """One selectable package for a repeatable Charm (currently only Ox-Body
    Technique). Each purchase of the Charm picks one variant; `health_levels` are
    the wound-penalty levels it grants (e.g. [0] or [-1, -2, -2])."""
    model_config = ConfigDict(frozen=True)

    key: str
    label: str
    health_levels: list[int] = Field(default_factory=list)
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
    type: CharmType
    min_ability: int = Field(default=0, ge=0)
    min_essence: int = Field(default=1, ge=1)
    # Repeatable Charms (Ox-Body Technique): may be bought once per dot of this
    # Ability (the cap), each purchase choosing one of `variants`. None = not repeatable.
    repeatable_cap_ability: Optional[str] = None
    variants: list[CharmVariant] = Field(default_factory=list)
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
    caste_abilities: list[AbilityName]     # the five fixed caste abilities
    description: str = ""                   # a quick flavour blurb for the caste
    anima_powers: str = ""


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
    the per-character rating/descriptor lives on character.BackgroundEntry."""
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    description: str = ""


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


class ExperienceCosts(BaseModel):
    # rating-scaled increases
    attribute: LinearCost = Field(default_factory=lambda: LinearCost(coeff=4))
    ability: LinearCost = Field(default_factory=lambda: LinearCost(coeff=2))
    ability_favored_caste: LinearCost = Field(default_factory=lambda: LinearCost(coeff=2, offset=-1))
    essence: LinearCost = Field(default_factory=lambda: LinearCost(coeff=8))
    virtue: LinearCost = Field(default_factory=lambda: LinearCost(coeff=3))   # does NOT raise Willpower
    willpower: LinearCost = Field(default_factory=lambda: LinearCost(coeff=2))
    # flat "new trait" costs
    new_ability: int = 3
    new_specialty: int = 3
    new_charm: int = 10
    new_charm_favored_caste: int = 8
    new_spell: int = 10
    new_spell_occult_favored_caste: int = 8
    foreign_charm: int = 20                # spirit Charms / other Exalt types; Eclipse only (gated in engine)


class AbilityMinimum(BaseModel):
    """A required minimum in one of a set of Abilities (OR semantics): the character
    must have at least `rating` in AT LEAST ONE of `abilities`. A single-element list
    is a specific-ability floor. Used for the Dragon-Blooded Dynastic schooling
    minimums (p.151) — these are a floor spent from the pool, NOT free extra dots."""
    model_config = ConfigDict(frozen=True)
    abilities: list[AbilityName]
    rating: int = Field(ge=1)


class ChargenBudgets(BaseModel):
    # attributes: 8/6/4 across the three prioritized categories; all start at 1.
    # Which category gets which pool is derived from the per-category spend, not stored.
    attribute_pools: tuple[int, int, int] = (8, 6, 4)
    attribute_base: int = 1

    # Required minimum Abilities the character must meet (a floor spent from the
    # pool, not free extras). Dragon-Blooded Dynastic schooling (p.151); empty for
    # splats/origins with no such floor (Solar, DB Outcaste).
    required_min_abilities: list[AbilityMinimum] = Field(default_factory=list)

    ability_dots: int = 25
    ability_min_caste_favored: int = 10    # >= 10 of the 25 on caste/favored abilities
    ability_cap_pre_bp: int = 3
    favored_count: int = 5                 # >= 1 dot required in each favored ability

    background_dots: int = 7
    background_cap_pre_bp: int = 3

    virtue_dots: int = 5                   # spent over a base of 1 each
    virtue_base: int = 1
    virtue_cap_pre_bp: int = 3

    charm_count: int = 10
    charm_min_caste_favored: int = 5
    # The alternative Immaculate chargen path (Dragon-Blooded, p.151): a character
    # learning Immaculate martial arts takes this many Charms instead of charm_count,
    # all from a single elemental tree, and the charm_min_caste_favored rule is
    # waived. Only reachable when the character selects Immaculate Order Charms, so it
    # never affects splats without them (Solar).
    immaculate_charm_count: int = 5

    essence_start: int = 2
    bonus_points: int = 15

    willpower_start_cap: int = 8           # may not start above this...
    willpower_cap_exception_virtue: int = 4   # ...unless at least
    willpower_cap_exception_count: int = 2    # this many Virtues are >= 4


class EssencePoolSpec(BaseModel):
    """Per-splat motes formula as data, so derive.essence_pools is a lookup, not a
    branch. personal = essence*personal_essence_coeff + willpower*personal_willpower_coeff;
    peripheral = essence*peripheral_essence_coeff + willpower*peripheral_willpower_coeff
    + the Virtue term selected by `peripheral_virtue_mode`.

      * Solar (core p.104):      3 / 7, virtue_mode "all"          (Ess×3+WP; Ess×7+WP+ΣVirtues)
      * Dragon-Blooded (p.150-152): 1 / 4, virtue_mode "two_highest",
        plus a Breeding-Background term added to BOTH pools (see below).

    `peripheral_virtue_mode`: "all" adds ΣVirtues (all four), "two_highest" adds only
    the sum of the two highest Virtues (the DB rule), "none" adds nothing.

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
    peripheral_virtue_mode: str = "all"     # "all" | "two_highest" | "none"
    # Optional Background-derived additive term (DB Breeding, p.158-159).
    breeding_background: str = ""            # Background name whose rating indexes the tables
    breeding_personal: list[int] = Field(default_factory=list)     # index by rating 0..5
    breeding_peripheral: list[int] = Field(default_factory=list)

    @field_validator("peripheral_virtue_mode")
    @classmethod
    def _check_virtue_mode(cls, v: str) -> str:
        if v not in ("all", "two_highest", "none"):
            raise ValueError(f"peripheral_virtue_mode must be all/two_highest/none, got {v!r}")
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
    highest_magic_circle_id: str = ""       # circle barred at creation (e.g. "Solar")
    ox_body_charm_id: str = ""              # the splat's repeatable health-level Charm


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
    bonus_costs: dict[str, BonusPointCosts] = Field(
        default_factory=lambda: {"default": BonusPointCosts()})
    xp_costs: dict[str, ExperienceCosts] = Field(
        default_factory=lambda: {"default": ExperienceCosts()})
    budgets: dict[str, ChargenBudgets] = Field(
        default_factory=lambda: {"default": ChargenBudgets()})

    def exalt_for(self, exalt_type: str) -> ExaltDefinition:
        """The ExaltDefinition for `exalt_type`, falling back to Solar if the type
        is unknown (engine.validate.check_exalt_type surfaces the bad value as an
        Issue separately, so derivation still produces a number instead of crashing)."""
        return self.exalts.get(exalt_type) or self.exalts.get("Solar") or SOLAR_EXALT

    def bonus_costs_for(self, exalt_type: str) -> BonusPointCosts:
        return self.bonus_costs.get(exalt_type, self.bonus_costs["default"])

    def xp_costs_for(self, exalt_type: str) -> ExperienceCosts:
        return self.xp_costs.get(exalt_type, self.xp_costs["default"])

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
