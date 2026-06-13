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

from pydantic import BaseModel, ConfigDict, Field


# --------------------------------------------------------------------------- #
# Fixed vocabularies
# --------------------------------------------------------------------------- #

class Caste(str, Enum):
    DAWN = "Dawn"
    ZENITH = "Zenith"
    TWILIGHT = "Twilight"
    NIGHT = "Night"
    ECLIPSE = "Eclipse"


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


class Charm(BaseModel):
    model_config = ConfigDict(frozen=True)  # rules data is immutable at runtime

    id: str
    name: str
    category: str                          # an AbilityName value, a Martial Arts style, or "sorcery"
    type: CharmType
    min_ability: int = Field(default=0, ge=0)
    min_essence: int = Field(default=1, ge=1)
    # AND-of-ORs: the character must satisfy every inner group; a group is
    # satisfied if ANY of its ids is known. A flat list of single-id groups is
    # the common "all of these required" case.
    prerequisites: list[list[str]] = Field(default_factory=list)
    cost: CharmCost = Field(default_factory=CharmCost)
    duration: str = "Instant"
    keywords: list[str] = Field(default_factory=list)
    # Set on the circle-initiation Charms (Terrestrial/Celestial/Solar Circle Sorcery).
    # Lets engine.validate gate known spells on a known initiation Charm of their circle.
    grants_sorcery_circle: Optional[SpellCircle] = None
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
    model_config = ConfigDict(frozen=True)

    caste: Caste
    caste_abilities: list[AbilityName]     # the five fixed caste abilities
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


class ChargenBudgets(BaseModel):
    # attributes: 8/6/4 across the three prioritized categories; all start at 1.
    # Which category gets which pool is derived from the per-category spend, not stored.
    attribute_pools: tuple[int, int, int] = (8, 6, 4)
    attribute_base: int = 1

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

    essence_start: int = 2
    bonus_points: int = 15

    willpower_start_cap: int = 8           # may not start above this...
    willpower_cap_exception_virtue: int = 4   # ...unless at least
    willpower_cap_exception_count: int = 2    # this many Virtues are >= 4


class RuleSet(BaseModel):
    """The whole rulebook in memory. Charms and spells are indexed by id for
    O(1) prerequisite resolution and load-time link-checking."""
    castes: dict[Caste, CasteDefinition]
    charms: dict[str, Charm]
    spells: dict[str, Spell] = Field(default_factory=dict)
    armor_catalog: dict[str, ArmorType] = Field(default_factory=dict)
    weapon_catalog: dict[str, WeaponType] = Field(default_factory=dict)
    background_catalog: dict[str, BackgroundType] = Field(default_factory=dict)
    bonus_costs: BonusPointCosts = Field(default_factory=BonusPointCosts)
    xp_costs: ExperienceCosts = Field(default_factory=ExperienceCosts)
    budgets: ChargenBudgets = Field(default_factory=ChargenBudgets)
