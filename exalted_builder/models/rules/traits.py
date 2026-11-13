"""
models/rules/traits.py — the Merits and Flaws, the Natures, the trait reference
text, the Virtue Flaws, the roll definitions, and the magical materials.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ._base import AbilityName, AttributeName, Source, VirtueName
from .backgrounds import BackgroundPointLimit, TraitRequirement


class MeritFlaw(BaseModel):
    """One Merit or Flaw.

    ⚠ Inert (decision 0011): the printed text, the cost and the prerequisites only.
    `engine.merits.merits_and_flaws_calc` gives the effects, by id. The catalogue
    includes the Thaumaturgy Merits (Player's Guide pp.120-122).

      * `cost` is the printed value. 0 if `cost_options` is used. A purchase then
        names its tier.
      * `kind`: the calc decides the sign. A Flaw grants bonus points.
      * `repeatable_by`: the axis of a repeatable Merit ("attribute group"). "" = once.
      * `prerequisites` are MeritFlaw ids. A prerequisite that the build cannot check
        goes in `prerequisite_note` as printed text.
    """
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    # "merit" | "flaw" | "either". For "either" the player selects the side
    # (`MeritFlawPurchase.taken_as`).
    kind: str = "merit"
    category: str = ""                     # "Supernatural" / "Social" / ... as printed
    cost: int = 0                          # printed point value; 0 when cost_options is used
    cost_options: dict[str, int] = Field(default_factory=dict)   # named tier -> points
    # Splat prices, {exalt_type: {tier: points}}. Inner key "" = one fixed price.
    cost_options_by_exalt_type: dict[str, dict[str, int]] = Field(default_factory=dict)
    # Caste prices, the same shape. They override the splat prices (p.30).
    cost_options_by_caste: dict[str, dict[str, int]] = Field(default_factory=dict)
    # The price of each side of a `kind: "either"` entry (p.30).
    cost_by_kind: dict[str, int] = Field(default_factory=dict)
    # The page gives no price. The purchase stores the agreed value.
    variable_cost: bool = False
    # The printed cost line. The UI shows it, thus a price that the engine cannot
    # model is still visible.
    cost_note: str = ""
    # The only splats that can take it. Empty = all.
    exalt_types: list[str] = Field(default_factory=list)
    # Splats that cannot take it (p.21).
    barred_exalt_types: list[str] = Field(default_factory=list)
    # CasteDefinition ids that cannot take it (p.41). Caste ids are unique across
    # splats.
    barred_castes: list[str] = Field(default_factory=list)
    # The only origins that can take it (human's ruling). Empty = all. ⚠ Validation
    # and the picker both apply it.
    required_origins: list[str] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)       # other MeritFlaw ids
    # p.41: the splat must start at this Essence or higher
    # (`ChargenBudgets.essence_start`). 0 = no floor.
    min_starting_essence: int = 0
    # Splat bars for one tier, {tier: [exalt_type, ...]} (p.20-21). A splat barred at
    # every tier is barred from the entry.
    tier_barred_exalt_types: dict[str, list[str]] = Field(default_factory=dict)
    prerequisite_note: str = ""            # printed prereq this build cannot check
    # Trait requirements by tier. "" = all tiers. A named tier adds to it.
    # AND-of-OR, as `Charm.prerequisites` (p.25).
    trait_prerequisites: dict[str, list[list[TraitRequirement]]] = Field(default_factory=dict)
    # PG p.24: the trait whose rating caps the number of purchases. "" = no cap except
    # `repeatable_by`.
    max_purchases_from_trait: str = ""
    # PG p.74: the maximum purchases, by origin. An absent origin has no cap.
    # Validate and the post-lock buy path both apply it.
    max_purchases_by_origin: dict[str, int] = Field(default_factory=dict)
    # Point limits from a Background rating.
    #
    # ⚠ A list: Damaged Artifact has two limits (PG p.38), one on the item and one on
    # the sum of the Background. One summed check is incorrect.
    points_limits: tuple[BackgroundPointLimit, ...] = ()
    repeatable_by: str = ""                # "" = once only
    # The purchase can record stipulations (p.24). The UI reads it.
    takes_stipulations: bool = False
    # Only a character with thaumaturgy can take it.
    thaumaturges_only: bool = False
    description: str = ""
    source: Source = Field(default_factory=Source)

    @field_validator("kind")
    @classmethod
    def _check_kind(cls, v: str) -> str:
        if v not in ("merit", "flaw", "either"):
            raise ValueError(f"kind must be merit/flaw/either, got {v!r}")
        return v


class NatureType(BaseModel):
    """A Nature. The catalogue of the Nature dropdown. Character.nature is free
    text."""
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    description: str = ""


class AttributeDescription(BaseModel):
    """The reference text of one Attribute (core pp.127-128): the prose, and the
    1-5 ladder by rating. A ladder value includes the printed label. Display only."""
    model_config = ConfigDict(frozen=True)

    id: AttributeName
    name: str
    category: str = ""                 # "Physical" / "Social" / "Mental"
    description: str = ""
    ladder: dict[int, str] = Field(default_factory=dict)


class AbilityDescription(BaseModel):
    """The reference text of one Ability (core pp.133-140): the prose, the sample
    specialties and the three example feats.

    ⚠ 1e has no ladder for each Ability (`TraitDescriptions.ability_ladder`). The
    feats are `standard` (1 success), `challenging` (3) and `legendary` (5) (p.132).
    `specialties_note`: the Linguistics paragraph."""
    model_config = ConfigDict(frozen=True)

    id: AbilityName
    name: str
    description: str = ""
    specialties: list[str] = Field(default_factory=list)
    specialties_note: str = ""
    standard: str = ""
    challenging: str = ""
    legendary: str = ""


class VirtueDescription(BaseModel):
    """The reference text of one Virtue (core pp.129-130): the prose, the 1-5
    ladder, what the Virtue aids, and what needs a failed Virtue check. The ladder
    has no labels."""
    model_config = ConfigDict(frozen=True)

    id: VirtueName
    name: str
    description: str = ""
    ladder: dict[int, str] = Field(default_factory=dict)
    aids_in: str = ""
    must_fail_check_to: str = ""


class TraitDescriptions(BaseModel):
    """The Chapter Four reference text of the three trait families. `ability_ladder`
    is the common Ability ladder (p.132). Display only."""
    model_config = ConfigDict(frozen=True)

    source: Source = Field(default_factory=Source)
    # By rating, from 0: "Unskilled" is a printed rung.
    ability_ladder: dict[int, str] = Field(default_factory=dict)
    attributes: list[AttributeDescription] = Field(default_factory=list)
    virtues: list[VirtueDescription] = Field(default_factory=list)
    abilities: list[AbilityDescription] = Field(default_factory=list)

    def attribute(self, name: AttributeName) -> AttributeDescription | None:
        """Return the row for `name`. Return None if the file does not have it."""
        return next((a for a in self.attributes if a.id == name), None)

    def ability(self, name: AbilityName) -> AbilityDescription | None:
        """Return the row for `name`. Return None if the file does not have it."""
        return next((a for a in self.abilities if a.id == name), None)

    def virtue(self, name: VirtueName) -> VirtueDescription | None:
        """Return the row for `name`. Return None if the file does not have it."""
        return next((v for v in self.virtues if v.id == name), None)


class VirtueFlawType(BaseModel):
    """One sample Virtue Flaw (core pp.131-133).

    A catalogue for the dropdown only. `Character.virtue_flaw.description` is free
    text. `virtue` filters the dropdown: the Virtue must be 3 or more (p.131).
    """
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    virtue: VirtueName
    description: str = ""
    limit_break: str = ""                   # the printed Limit Break Condition
    source: str = ""
    notes: str = ""                         # transcription oddities, printed as-is


class PoolKind(str, Enum):
    """What arithmetic a RollDefinition's base term is made of."""
    ATTRIBUTE_ABILITY = "attribute_ability"   # Dexterity + Melee, Wits + Awareness…
    VIRTUE = "virtue"                         # a Virtue check: the Virtue's rating alone
    WILLPOWER = "willpower"                   # a Willpower check: permanent Willpower


class WeaponStat(str, Enum):
    """The weapon stat that joins the pool, if any (core p.327)."""
    NONE = "none"
    ACCURACY = "accuracy"
    DEFENSE = "defense"


class RollDefinition(BaseModel):
    """One named roll whose BASE dice pool is trait arithmetic (decision 0016).
    The roster is data/dice_pools.json. The engine adds the traits of the row.

    ⚠ The BASE pool only. Stunts, difficulty, range, split actions and Charm dice
    are out of scope (0016). The surface shows `excludes` with the number.
    """
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    kind: PoolKind = PoolKind.ATTRIBUTE_ABILITY
    category: str = ""                     # UI grouping only: "Combat", "Social"…
    attribute: Optional[AttributeName] = None   # required for ATTRIBUTE_ABILITY
    ability: Optional[AbilityName] = None       # required for ATTRIBUTE_ABILITY
    weapon_stat: WeaponStat = WeaponStat.NONE
    # Core p.326: the armor mobility penalty applies to this roll. Per roll, not on
    # all rolls. Attack rolls do not carry it.
    mobility_applies: bool = False
    # Wound penalties apply (p.229, human's ruling). Set False only where a page says
    # so (p.233).
    # ⚠ Do not clear it without a page. An incorrect exemption gives a larger pool.
    wound_applies: bool = True
    notes: str = ""
    source: Source = Field(default_factory=Source)

    @model_validator(mode="after")
    def _check_traits(self) -> "RollDefinition":
        if self.kind is PoolKind.ATTRIBUTE_ABILITY:
            if self.attribute is None or self.ability is None:
                raise ValueError(
                    f"roll {self.id!r}: kind 'attribute_ability' needs both "
                    f"`attribute` and `ability`.")
        elif self.attribute is not None or self.ability is not None:
            raise ValueError(
                f"roll {self.id!r}: kind {self.kind.value!r} takes no attribute/ability.")
        if self.weapon_stat is not WeaponStat.NONE and self.kind is not PoolKind.ATTRIBUTE_ABILITY:
            raise ValueError(f"roll {self.id!r}: a weapon stat needs an Attribute + Ability pool.")
        return self


class MagicalMaterial(BaseModel):
    """One magical material (core p.341). The bonus applies only if the wielder's
    Character.exalt_type equals `exalt_type`. The weapon_* values add to the weapon.
    The armor_* values add to the armor."""
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    exalt_type: str                        # the Exalt the bonus applies for
    weapon_speed: int = 0
    weapon_accuracy: int = 0
    weapon_damage: int = 0
    weapon_defense: int = 0
    # Armor (core p.345-346). The soak values add. A negate flag sets the value to 0
    # (Moonsilver: mobility; Jade: fatigue).
    armor_soak_lethal: int = 0
    armor_soak_bashing: int = 0
    armor_negate_mobility_penalty: bool = False
    armor_negate_fatigue: bool = False
    notes: str = ""                        # narrative riders (mote drain, damage-roll effects)
