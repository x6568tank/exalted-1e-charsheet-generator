"""
models/rules/charms.py — the Charm and spell models: the cost, the variants, the
prerequisites, Submodules, and Elemental Powers.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from ._base import (AbilityMinimum, AttributeMinimum, CharmType, Damage, Source,
                    SpellCircle)


# --------------------------------------------------------------------------- #
# Charms & spells
# --------------------------------------------------------------------------- #


class CharmCost(BaseModel):
    """The activation cost in play. engine.costs calculates the XP/BP cost to learn
    the Charm."""
    motes: int = Field(default=0, ge=0)
    willpower: int = Field(default=0, ge=0)
    health: int = Field(default=0, ge=0)   # health levels spent by the Charm
    # The type of health level that `health` spends. None = the page does not say.
    # ⚠ Not homebrew-only: Stolen Wax Discipline (E:Ab p.237) sets it. Do not remove
    # it.
    health_type: Optional[Damage] = None
    committed: bool = False                # committed motes reduce the pool until released
    raw: str = ""                          # display string; authoritative for variable costs


class CharmVariant(BaseModel):
    """One package of a repeatable Charm.

    Ox-Body Technique: each purchase selects one variant. `health_levels` are the
    levels it grants ([0] or [-1, -2, -2]). `max_purchases` is 1.

    Deadly Beastman Transformation Gifts (Lunar, p.126-127): `health_levels` is
    empty. `prerequisites` is an AND-of-OR over other variant `key`s of the same
    Charm. `max_purchases` is 2 for a Gift that the page lets the character take
    two times."""
    model_config = ConfigDict(frozen=True)

    key: str
    label: str
    health_levels: list[int] = Field(default_factory=list)
    prerequisites: list[list[str]] = Field(default_factory=list)
    max_purchases: int = 1
    description: str = ""


class Submodule(BaseModel):
    """One upgrade of one Alchemical Charm (p.89). It applies when the Charm is
    installed. Cost: `bp_cost` bonus points at chargen, or `xp_cost` XP after the
    lock. It can have a minimum Essence and a minimum Attribute."""
    model_config = ConfigDict(frozen=True)
    key: str                               # stable within the parent Charm
    name: str
    bp_cost: int = Field(default=0, ge=0)
    xp_cost: int = Field(default=0, ge=0)
    min_essence: int = Field(default=1, ge=1)
    min_attribute: str = ""                # optional extra Attribute gate (AttributeName value)
    min_attribute_rating: int = Field(default=0, ge=0)
    description: str = ""


class ElementalPower(BaseModel):
    """One of the nine elemental powers (PG p.68; core p.296; Games of Divinity p.56).
    For Elemental God-Blooded only. Cost: `bp_cost` bonus points, or `bp_cost * 2`
    XP. `required_merits` are Merit ids (`mf.elemental-dominion`).

    `activation` and `description` are text only (decision 0008). Training time
    (p.68) is out of scope."""
    model_config = ConfigDict(frozen=True)
    id: str                                  # namespaced `elemental.<slug>`
    name: str
    bp_cost: int = Field(default=7, ge=0)
    min_essence: int = Field(default=2, ge=1)
    required_merits: list[str] = Field(default_factory=list)
    activation: str = ""
    description: str = ""
    source: Source = Field(default_factory=Source)


class CharmCountRequirement(BaseModel):
    """A count prerequisite: "any three Lore Charms" (`Charm.prerequisite_counts`).

    The Charm that has the requirement does not count toward it. `label` overrides
    the category noun in the display. Empty = use the category.
    """
    model_config = ConfigDict(frozen=True)

    category: str
    count: int = Field(default=1, ge=1)
    label: str = ""


class Charm(BaseModel):
    model_config = ConfigDict(frozen=True)  # rules data is immutable at runtime

    id: str
    name: str
    category: str                          # an AbilityName value, a Martial Arts style, or "sorcery"
    exalt_type: str = "Solar"              # the splat that can learn it; filters the picker
    # Dragon-Blooded: the element tree. It groups the picker and gives the Immaculate
    # "one elemental tree" rule.
    element: str = ""
    # Dragon-Blooded ch.6: an Immaculate Order Charm. These Charms give the Immaculate
    # chargen path (p.151) and use the Immaculate cost row. Set with `element`.
    immaculate: bool = False
    # All splats can learn the Charm. A learner of another splat pays the ordinary
    # Martial Arts cost. ⚠ The Immaculate chargen package stays Dragon-Blooded only
    # (engine.validate._immaculate_path).
    open_to_all: bool = False
    # Exalt tiers that can learn the Charm, in addition to `exalt_type`. Matched
    # against ExaltDefinition.tier. A learner of another splat pays the ordinary
    # Martial Arts cost.
    open_to_tiers: list[str] = Field(default_factory=list)
    # The martial-arts tier of the style ("Terrestrial" / "Celestial" / "Sidereal").
    # "" = not martial arts, or no printed tier.
    #
    # ⚠ NOT AUTHORED IN THE CHARM FILES. `rules_db` copies it from
    # `MartialArtsStyle.tier` at load. The loader overwrites a value in a charms JSON.
    #
    # ⚠ `ma_tier` gives the kind of style. `open_to_tiers` gives who can learn it. Do
    # not use `open_to_tiers` for the p.101 Sidereal chargen cap.
    ma_tier: str = ""
    # PG p.249: the only learners, "<Splat>" or "<Splat>:<caste>". The character must
    # match one entry. It narrows access only: the splat/tier test still applies.
    restricted_to: list[str] = Field(default_factory=list)
    # PG p.246: no Virtue of the learner can be above this. 0 = no cap.
    max_virtue: int = Field(default=0, ge=0)
    type: CharmType
    min_ability: int = Field(default=0, ge=0)
    # Lunar p.122: the AttributeName value that `min_ability` rates. "" = the Ability
    # of `category`.
    min_attribute: str = ""
    # E:Ab p.234-253: the VirtueName value that `min_ability` rates.
    #
    # ⚠ `min_ability` holds the RATING here, as it does for `min_attribute`.
    #
    # A Charm sets AT MOST ONE of min_virtue / min_attribute / an Ability-resolving
    # category. `validate._min_trait_rating` resolves them in that order.
    min_virtue: str = ""
    min_essence: int = Field(default=1, ge=1)
    # Cult of the Illuminated p.102: Ability minimums in addition to `min_ability`.
    # Each entry is an AND. Its inner list is an OR.
    # ⚠ Requirement checks only. Pricing, discounts and Combo cost use `min_ability`.
    extra_min_abilities: list[AbilityMinimum] = Field(default_factory=list)
    # Attribute minimums, the same shape. For homebrew: no printed Charm uses it.
    extra_min_attributes: list[AttributeMinimum] = Field(default_factory=list)
    # Alchemical (p.88-91): the Personal Essence committed to install the Charm in a
    # Slot. The installed total is capped by the Personal pool at chargen.
    installation_cost: int = Field(default=0, ge=0)
    # p.124-127: the Charm can be bought once per dot of this Ability or Attribute.
    # "essence" = once per dot of Character.essence_rating. None = not repeatable.
    repeatable_cap_ability: Optional[str] = None
    # PG p.83: the VirtueName value that caps the purchases. None = no Virtue cap.
    repeatable_cap_virtue: Optional[str] = None
    # CH6 p.245: the highest Virtue caps the purchases.
    repeatable_cap_highest_virtue: bool = False
    # CH6 pp.245-246: a flat cap on the purchases. validate._repeatable_purchase_cap
    # uses `min(trait_cap, repeatable_cap_max)`. 0 = no flat cap.
    repeatable_cap_max: int = Field(default=0, ge=0)
    variants: list[CharmVariant] = Field(default_factory=list)
    # Variants for each purchase (p.124).
    variant_picks_first_purchase: int = 1
    variant_picks_per_purchase: int = 1
    # Caste Book: Zenith p.72-73: each variant only one time.
    variants_unique: bool = False
    # AND-of-ORs: the character must satisfy every inner group. A group is
    # satisfied if the character knows ANY of its ids.
    prerequisites: list[list[str]] = Field(default_factory=list)
    # Count prerequisites (Aspect Book: Air/Earth). Each entry is an AND.
    prerequisite_counts: list[CharmCountRequirement] = Field(default_factory=list)
    cost: CharmCost = Field(default_factory=CharmCost)
    duration: str = "Instant"
    keywords: list[str] = Field(default_factory=list)
    # The spell circle that this initiation Charm opens. engine.validate needs it to
    # gate spells. Sorcery and necromancy both use it.
    grants_circle: Optional[SpellCircle] = None
    # Autochthonians CH4: the p.127 Eclipse rule cannot reach this Charm.
    no_foreign_learning: bool = False
    # Alchemical (p.89): the upgrades of this Charm.
    submodules: list[Submodule] = Field(default_factory=list)
    # p.159: False bars the Charm from Alchemical Arrays.
    arrayable: bool = True
    # CH3 p.141: True = the Charm can never be uninstalled. The vat refit refuses it.
    permanent_install: bool = False
    # CH2 p.69: permanent Clarity from this installed Charm. Derived: removal removes
    # it (p.70).
    permanent_clarity: int = Field(default=0, ge=0)
    description: str = ""
    source: Source = Field(default_factory=Source)
    # Set by the loader on rows from the custom library (custom_content.py). The
    # engine ignores it. The UI marks the row as homebrew (human's ruling), and the
    # authoring page edits only these rows.
    custom: bool = False
    # Set by the loader on rows generated from `Path.powers`, for Combos and the
    # sheet. The picker hides these rows. ⚠ Each other read site must decide if it
    # skips or includes them.
    virtual: bool = False


class Spell(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    circle: SpellCircle
    cost: CharmCost = Field(default_factory=CharmCost)
    description: str = ""
    source: Source = Field(default_factory=Source)
    # Set by the loader. See Charm.custom.
    custom: bool = False
