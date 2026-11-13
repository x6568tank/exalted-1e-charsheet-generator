"""
models/rules/castes.py — the caste and the origin models: castes, Godblooded
heritages, Lunar breeds, granted Charm choices, Cult camps and Callings, Sidereal
Colleges, martial-arts styles, and Dragon-King Paths.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from ._base import (AbilityGroupMinimum, AbilityMinimum, AbilityName, AttributeName,
                    CharmType, EssencePoolSpec, Source)
from .charms import CharmCost


class GodbloodedHeritage(BaseModel):
    """The mechanics of one God-Blooded heritage (Player's Guide CH2, pp.45-60).
    `CasteDefinition.heritage_traits` holds it: a heritage is the God-Blooded caste.

    * `unlocked_essence` — the Awakened-Essence pool formula (p.66).
    * `charm_access` — the Charm catalogues of other splats that the heritage learns
      (p.47).
    * `magic_track` / `magic_track_by_parent` — the one magic track that the heritage
      can learn (p.48). "" = no restriction except Charm access.
    * `attribute_pools` — the Half-Caste override (p.47; the prose wins over the p.50
      summary). None = the splat pools.
    * `allowed_backgrounds` — the heritage Backgrounds (p.50), as lowercased NAMEs.
    * `heritage_power` — the perception power (p.51-60). Display only."""
    model_config = ConfigDict(frozen=True)

    unlocked_essence: Optional[EssencePoolSpec] = None
    charm_access: list[str] = Field(default_factory=list)
    # p.47: True = ignore `charm_access` and use the catalogue of the parent Exalt
    # type, from `Character.origin`.
    charm_access_parent: bool = False
    magic_track: str = ""
    # p.48: `magic_track` by parent Exalt type. It overrides `magic_track` for a
    # listed parent.
    magic_track_by_parent: dict[str, str] = Field(default_factory=dict)
    attribute_pools: Optional[tuple[int, int, int]] = None
    allowed_backgrounds: list[str] = Field(default_factory=list)
    heritage_power: str = ""
    # The choices of the Origin dropdown for this heritage (p.47; p.73-79, human's
    # ruling). Empty = the heritage does not use `Character.origin`.
    origin_options: list[str] = Field(default_factory=list)
    # p.47: Charm ids that the heritage can never hold. ⚠ Both Charm gates check
    # this list first.
    barred_charm_ids: list[str] = Field(default_factory=list)
    # p.47: False closes the native Charm catalogue of the splat. The explicit grants
    # stay (p.234 martial arts, `charm_access`). Checked in charm_matches_splat.
    # ⚠ A flag, not a deny-list: a deny-list does not cover a Charm added later.
    charms_available: bool = True
    # p.47: the Gift Charm and its purchase cap, by parent Exalt type
    # (`Character.origin`).
    gift_charm_ids: dict[str, str] = Field(default_factory=dict)
    gift_caps: dict[str, int] = Field(default_factory=dict)
    # p.47: the Ox-Body Charm, by parent Exalt type (`Character.origin`).
    ox_body_charm_ids: dict[str, str] = Field(default_factory=dict)
    # PG p.83: the Ox-Body Charm of the heritage (human's ruling). Checked after
    # `ox_body_charm_ids` and before the splat value.
    ox_body_charm_id: str = ""


class InnateWeapon(BaseModel):
    """One natural weapon of a Dragon-King breed (PG pp.167-174). Display only
    (decision 0008)."""
    model_config = ConfigDict(frozen=True)

    name: str
    speed: int = 0
    accuracy: int = 0
    damage: int = 0
    damage_type: str = "L"                 # "L" lethal / "B" bashing
    defense: int = 0


class BreedTraits(BaseModel):
    """The mechanics of one Dragon-King breed (PG pp.167-174).
    `CasteDefinition.breed_traits` holds it: a breed is the Dragon-King caste.

    * `element` — the two Paths with this `Path.element` are the Breed Paths.
    * `attribute_bonuses` — free dots added to the pools (p.167). Each effective dot
      above 5 costs bonus points (p.175).
      ⚠ Read against the EFFECTIVE value, not the pool spend; charged in
      bonus_point_breakdown.
    * `innate_soak_bashing` / `innate_soak_lethal` — innate armor, added in
      derive.soak (p.165).
    * `bonus_health_levels` — extra health levels (p.171/174).
    * `innate_weapons` — display only (decision 0008).
    """
    model_config = ConfigDict(frozen=True)

    element: str = ""
    attribute_bonuses: dict[AttributeName, int] = Field(default_factory=dict)
    innate_soak_bashing: int = Field(default=0, ge=0)
    innate_soak_lethal: int = Field(default=0, ge=0)
    bonus_health_levels: list[int] = Field(default_factory=list)
    innate_weapons: list[InnateWeapon] = Field(default_factory=list)


class CasteDefinition(BaseModel):
    """One caste, aspect, heritage or breed. `id` is the key in RuleSet.castes and
    on Character.caste ("dawn"). `exalt_type` is the splat."""
    model_config = ConfigDict(frozen=True)

    id: str                                # stable lowercase key, e.g. "dawn"
    exalt_type: str = "Solar"              # the splat this caste belongs to
    label: str                             # display name, e.g. "Dawn"
    caste_abilities: list[AbilityName] = Field(default_factory=list)  # the fixed caste abilities
    # Lunar p.90-91: Caste Attributes. Each set is one of
    # engine.validate.ATTRIBUTE_CATEGORIES. A caste sets caste_abilities OR
    # caste_attributes, never both.
    caste_attributes: list[AttributeName] = Field(default_factory=list)
    # Lunar p.251: the XP discount on a spell priced by
    # ExperienceCosts.new_spell_by_circle.
    spell_cost_discount: int = 0
    # Sidereal p.98: Ability floors of the caste, added to the budget floors.
    required_min_abilities: list[AbilityMinimum] = Field(default_factory=list)
    # Mountain Folk CH6 p.230: floors on the sum of a group of Abilities.
    required_min_ability_groups: list[AbilityGroupMinimum] = Field(default_factory=list)
    # Core p.127: the caste can learn Charms of other splats, at
    # `foreign_charm_xp_multiplier` x the XP. The chargen permission is
    # Character.house_rules.st_foreign_charms.
    foreign_charms: bool = False
    # p.127. The mote cost of use is not modelled.
    foreign_charm_xp_multiplier: int = Field(default=2, ge=1)
    # Autochthonians p.90: the XP to add an Alchemical Charm to the Panoply, with no
    # Slot. None = no such rate.
    foreign_panoply_charm_xp: Optional[int] = None
    description: str = ""                   # a quick flavour blurb for the caste
    anima_powers: str = ""
    # God-Blooded only. See GodbloodedHeritage.
    heritage_traits: Optional[GodbloodedHeritage] = None
    # Dragon-Kings only. See BreedTraits.
    breed_traits: Optional[BreedTraits] = None


class GrantedCharmChoice(BaseModel):
    """One player choice in the free-Charm package of a TrainingCamp.

    * `from_categories` — p.90: the player selects ONE category, then `pick` Charms
      in it.
    * `fixed_sets` — p.90: the player takes one complete set. `pick` is ignored.
    * `pool_categories` + `pool_charms` — p.96: `pick` Charms from one flat pool.
      The pool is all Charms of `pool_categories` plus the ids in `pool_charms`.

    ⚠ Do not merge the pool shape with `from_categories`. The pool can mix styles
    with a named Ability Charm.

    An alternate Charm under a house rule is a separate set."""
    model_config = ConfigDict(frozen=True)
    label: str = ""                                 # display, e.g. "Martial arts style"
    pick: int = Field(default=0, ge=0)              # how many Charms from the chosen category
    from_categories: list[str] = Field(default_factory=list)
    fixed_sets: list[list[str]] = Field(default_factory=list)
    pool_categories: list[str] = Field(default_factory=list)
    pool_charms: list[str] = Field(default_factory=list)

    def pool_charm_ids(self, charms: dict) -> list[str]:
        """Return the Charm ids of the flat pool, from the catalogue `charms`.
        Return [] for the other two shapes."""
        if not (self.pool_categories or self.pool_charms):
            return []
        out = [cid for cid, charm in charms.items()
               if charm.category in self.pool_categories]
        out += [cid for cid in self.pool_charms if cid not in out]
        return out


class TrainingCamp(BaseModel):
    """A training camp: chargen requirements for a character, in addition to the
    Caste (Cult of the Illuminated, Solar, p.89-93).

    `origin` scopes the camp to a `Character.origin` value. `exalt_type` scopes it to
    a splat."""
    model_config = ConfigDict(frozen=True)
    id: str                                         # stable lowercase key
    exalt_type: str = "Solar"
    origin: str = ""                                # Character.origin this camp belongs to
    label: str
    description: str = ""
    # p.89: Ability floors, added to the budget floors.
    required_min_abilities: list[AbilityMinimum] = Field(default_factory=list)
    # p.90: free Charm ids. ⚠ Not from the Charm pool, and not counted toward the
    # Caste/Favored minimum. The minimums of each Charm still apply.
    granted_charms: list[str] = Field(default_factory=list)
    # Player choices. Resolved onto Character.granted_charms.
    granted_charm_choices: list[GrantedCharmChoice] = Field(default_factory=list)
    # The page that prints this row. None when no page is known. ⚠ None, not
    # `Source()`, which names "Core". Read site: the public wiki (`ui/wiki_view`).
    source: Optional[Source] = None


class Calling(BaseModel):
    """A Calling: the role of the character, which discounts a set of Abilities and
    Charms, at chargen and in play (Cult of the Illuminated, p.90 and p.102).

    ⚠ A discount only. A Calling Ability is not Favored and does not count toward
    the Caste/Favored minimum. The rates are on BonusPointCosts and ExperienceCosts."""
    model_config = ConfigDict(frozen=True)
    id: str                                         # stable lowercase key
    exalt_type: str = "Solar"
    camp: str = ""                                  # TrainingCamp.id that offers it
    label: str
    description: str = ""
    abilities: list[AbilityName] = Field(default_factory=list)
    # Calling Charms, by id. A Charm here is discounted, never granted.
    charms: list[str] = Field(default_factory=list)
    # The Craft focus of a Calling Ability ("Craft (War)"), by AbilityName value.
    ability_focus: dict[str, str] = Field(default_factory=dict)
    # The page that prints this row. None when no page is known. ⚠ None, not
    # `Source()`, which names "Core". Read site: the public wiki (`ui/wiki_view`).
    source: Optional[Source] = None


class College(BaseModel):
    """One Astrological College (Sidereal, p.220-235). `house` is the caste id of the
    governing Maiden, which the p.98 rule matches to Character.caste. `house_label`
    is the printed house name."""
    model_config = ConfigDict(frozen=True)
    id: str
    name: str
    house: str                              # caste id of the governing Maiden
    house_label: str = ""                   # printed astrological house name (display)


class MartialArtsStyle(BaseModel):
    """One martial-arts style: the `Type:` line, the prose and the style rules of the
    page, for the category `martial_arts:<slug>`.

    ⚠ **`tier` is DISPLAY ONLY. Nothing in engine/ may read it** (a test enforces
    this). The Charm fields `open_to_tiers` / `open_to_all` decide access (decision
    0011).
    """
    model_config = ConfigDict(frozen=True)
    id: str                                 # "style.righteous-devil"
    name: str                               # "Righteous Devil Style", as printed
    category: str                           # "martial_arts:righteous-devil"
    # The printed `Type:` word. ⚠ A str, not an enum (decision 0001).
    tier: str = ""
    preamble: str = ""                      # the style's prose, as printed
    # Style rules, one entry for each printed rule.
    mechanics: list[str] = Field(default_factory=list)
    source: Source = Field(default_factory=Source)


class PathPower(BaseModel):
    """One power of a Dragon-King Path (PG pp.177-191). The dot is the Path rating
    that gives the power (p.177). `cost` is the activation cost: use `raw` for a
    variable cost. `text` is the printed text."""
    model_config = ConfigDict(frozen=True)

    dot: int = Field(ge=1, le=6)
    name: str
    type: CharmType
    cost: CharmCost = Field(default_factory=CharmCost)
    duration: str = "Instant"
    keywords: list[str] = Field(default_factory=list)
    text: str = ""


class Path(BaseModel):
    """One Dragon-King Path (PG pp.177-191): a rated trait (1-6) with its own pool,
    costs and Essence gate. `element`: the two Paths whose element matches
    `BreedTraits.element` are the Breed Paths. `powers`: the six powers in order."""
    model_config = ConfigDict(frozen=True)

    id: str                                  # stable lowercase key, e.g. "dk.celestial-air"
    name: str                                # e.g. "Celestial Air"
    element: str = ""                        # "air" | "wood" | "fire" | "water" | "earth"
    element_label: str = ""                  # display, e.g. "Air"
    description: str = ""
    powers: list[PathPower] = Field(default_factory=list)
