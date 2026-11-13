"""
models/character.py — the save file.

Holds the current trait values of a character, and the audit structures that the
engine uses to validate them:

  * pre-lock  : the engine validates the current traits against ChargenBudgets.
  * lock      : the engine freezes the Virtue component of Willpower and copies the
                traits into a snapshot. The snapshot is the XP baseline.
  * post-lock : each edit adds an append-only XpEntry row. The engine checks the
                current state against snapshot + log, and checks each cost.

This module enforces structural invariants only (non-negative ratings, valid enums,
rating <= 5). Game legality is in engine.validate, which needs the RuleSet. This
module does not import the RuleSet.

Enum-keyed dicts (attributes/abilities/virtues) serialize with the enum string values
as keys, e.g. {"strength": 3}.
"""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from .rules import (AbilityName, AttributeName, Damage, Orientation,
                    VirtueName)


# The capitalized Solar caste names, mapped to the caste ids.
_LEGACY_CASTE_IDS = {
    "Dawn": "dawn", "Zenith": "zenith", "Twilight": "twilight",
    "Night": "night", "Eclipse": "eclipse",
}


# --------------------------------------------------------------------------- #
# Sub-records
# --------------------------------------------------------------------------- #

class Specialty(BaseModel):
    ability: AbilityName
    name: str
    rating: int = Field(ge=1, le=3)        # cap of three per ability enforced in engine


class HearthstoneEntry(BaseModel):
    """One Hearthstone on a Manse Background row.

    Its level is the level of the Manse (core p.338), not a cost in Artifact dots.

    ⚠ Store a stone in this list, with its rating. Do not store it in the `note` of
    the row: the player can edit `note`, and the S&S p.67 total needs the rating.

    `rating` is an inline copy (decision 0007)."""
    name: str
    rating: int = Field(default=1, ge=0, le=5)


class BackgroundEntry(BaseModel):
    name: str                              # open-ended: "Artifact", "Manse", "Resources"...
    # ⚠ A structural bound only: 10 is the highest ceiling of any splat (CH6 p.234-235,
    # human's ruling). The engine (`background_issues`, `background_rating_cap`)
    # applies the real ceilings.
    rating: int = Field(ge=0, le=10)
    note: str = ""                         # the specific descriptor
    # S&S p.67: the cap is per Manse, thus the stones are on the row.
    # `BackgroundType.hearthstone_tiers` and `hearthstone_per_dot` decide if a row
    # can have stones.
    hearthstones: list[HearthstoneEntry] = Field(default_factory=list)
    # The row is a Demesne, not a Manse. A Demesne has no Hearthstones (S&S p.66,
    # human's ruling).
    is_demesne: bool = False


class ArtifactEntry(BaseModel):
    """One rated artifact that the character owns (E:Ab p.131).

    The Artifact budget limits the total rating and the rating of each item.
    Damaged Artifact uses the rating of one item.

    ⚠ Use this list only for an artifact that is not a weapon and not armor. Weapons
    and armor carry `artifact_rating`, and `engine.artifacts.artifact_items` adds
    them. A second entry here counts the item two times.

    `rating` is the dots of the artifact (1-5). An N/A artifact cannot be an entry
    (p.131)."""
    name: str
    rating: int = Field(ge=1, le=5)
    # Copied from `rules.ArtifactType.attunement`. ⚠ 0 can also mean "not transcribed".
    attunement: int = Field(default=0, ge=0)
    # See `Weapon.attuned`.
    # ⚠ Ignored if a gear row has `from_artifact` set to this row. The gear row owns
    # the commitment (human's ruling). `engine.artifacts.artifact_items` selects the
    # row. The editors show no control here when a stat line exists.
    attuned: bool = False
    attuned_pool: Literal["personal", "peripheral"] = "peripheral"
    note: str = ""
    # The acquisition channel (decision 0017): `engine.artifacts.ACQUIRED_BACKGROUND`,
    # `ACQUIRED_PURCHASED` or `ACQUIRED_LEGENDARY`. The Background is the pre-game
    # channel (core p.342, p.345). Cash is the in-play channel (Manacle and Coin
    # pp.122-125, which follows core pp. 324-346). The picker sets
    # `ACQUIRED_LEGENDARY` from `rules.ArtifactType.requires_merit`.
    # Only Background items count against the Artifact budget.
    # ⚠ This field is player-editable. `validate.check_artifacts` refuses a purchase
    # at chargen (human's ruling). The Merit check uses the NAME, not this field.
    acquired: str = "background"


class FetterEntry(BaseModel):
    """One Fetter of a ghost (Exalted: The Abyssals p.126).

    A Fetter has its own pool, its own costs, and a cap of Willpower + Essence on the
    total dots (p.127, p.283)."""
    name: str                              # "my widowed wife", "the sword I died on"
    rating: int = Field(ge=0, le=5)
    note: str = ""


class PassionEntry(BaseModel):
    """One Passion of a ghost. Each Passion belongs to one Virtue (E:Ab p.126).

    ⚠ A Passion is not bought, before or after the lock (p.283, human's ruling). The
    Passion dots of a Virtue equal its rating. The player distributes them. Thus no
    cost table has a `passion` row. Shift Passion (p.283) moves a dot between two
    Passions of one Virtue.

    `virtue` is the Virtue whose pool this Passion uses."""
    name: str                              # "avenge my murder", "see my son crowned"
    virtue: VirtueName
    rating: int = Field(ge=0, le=5)
    note: str = ""


class MeritFlawPurchase(BaseModel):
    """One Merit or Flaw that the character holds. `merit_id` is a rules.MeritFlaw id.

    `engine.merits.merits_and_flaws_calc` gives the effects (decision 0011).

    `tier`: the option of a variable-cost entry ("minor", "major"). "" otherwise.
    `detail`: free text from the player, for example the words of an oath.
    `arena`: the group of an oath for the stacking rule ("combat", "sex").
    """
    merit_id: str
    tier: str = ""
    detail: str = ""
    arena: str = ""
    # The agreed value of a `variable_cost` entry. Ignored for a printed cost.
    points: int = 0
    # "merit" or "flaw", for a `kind: "either"` entry. ⚠ "" is an error, not a default.
    taken_as: str = ""
    # PG p.24: the number of major stipulations on an Inheritance. engine.merits
    # applies the maximum.
    stipulations: int = Field(default=0, ge=0)
    # The `engine.artifacts` item KEY ("artifact:tattered wings") that a
    # `points_limited_by.per_entry` Flaw modifies.
    # ⚠ "" on Damaged Artifact is an error. Do not select an artifact for the player.
    artifact_key: str = ""
    # The name of a player-authored entry that is in no catalogue. Display only: the
    # engine and validate skip the row. `merit_id` is then not a catalogue id.
    custom_name: str = ""


class CraftRating(BaseModel):
    """One Craft Ability (core p.136). Each focus is a separate rated Ability, not a
    specialty. The engine reads Craft from this list, not from AbilityName.CRAFT."""
    focus: str                             # the specific craft, e.g. "Smithing"
    rating: int = Field(ge=0, le=5)


class CollegeRating(BaseModel):
    """One Astrological College of a character (Sidereal, p.98). `college_id` is a
    RuleSet College id."""
    college_id: str
    rating: int = Field(ge=0, le=5)


class PathRating(BaseModel):
    """One Dragon-King Path of a character (PG pp.175-177). `path_id` is a RuleSet
    Path id. The Essence gate is in the budget (p.177). `rules_db.load_ruleset` adds the Path powers to the Charm catalogue as
    virtual rows, for Combos. The rating here is the source value."""
    path_id: str
    rating: int = Field(ge=0, le=6)


# --------------------------------------------------------------------------- #
# Thaumaturgy holdings (Player's Guide CH3). See models/rules/ for the
# catalogue side and docs/status/thaumaturgy.md for the design.
# --------------------------------------------------------------------------- #

class ArtSpecialty(BaseModel):
    """+1 die in a part of an Art. Two at most apply to one roll.

    ⚠ `art_id` can name an Art that the character does not have (p.116). Do not add
    a prerequisite.

    `name` is free text. The catalogue `specialties` list is for autofill only.

    `narrowed` (p.127): the player limits a Summoning aspect, and its cost is half.
    The engine refuses it on an Art whose `aspect_narrowing` is False."""
    art_id: str
    name: str
    narrowed: bool = False


class ScienceRating(BaseModel):
    """One Science at a rating. engine.validate applies the ceiling
    `ThaumaturgicScience.max_rating`."""
    science_id: str
    rating: int = Field(ge=0)


class RitualEntry(BaseModel):
    """A ritual that the character knows, in one or more regional versions.

    `ritual_id` is a RuleSet ritual id. If it is "", the inline fields describe a
    custom ritual.

    `orientations`: each extra regional version costs 1 point (p.124). ⚠ The cost
    function needs the set, and the XP log must tell a ritual from an orientation."""
    ritual_id: str = ""                    # "" => custom, described inline below
    name: str = ""                         # custom only; catalogue entries read the RuleSet
    level: int = Field(default=1, ge=1, le=5)   # custom only
    description: str = ""                  # custom only
    orientations: list[Orientation] = Field(default_factory=lambda: [Orientation.REALM])

    @field_validator("orientations")
    @classmethod
    def _at_least_one_orientation(cls, v: list[Orientation]) -> list[Orientation]:
        # An empty list gives [REALM]. Duplicates are removed.
        if not v:
            return [Orientation.REALM]
        return list(dict.fromkeys(v))


class FormulaEntry(BaseModel):
    """A formula or procedure that the character knows. The orientation rule of
    RitualEntry applies.

    `level` has no upper bound here. The ceiling is rules data for each Science."""
    formula_id: str = ""                   # "" => custom, described inline below
    name: str = ""                         # custom only
    science_id: str = ""                   # custom only
    level: int = Field(default=1, ge=1)    # custom only
    description: str = ""                  # custom only
    orientations: list[Orientation] = Field(default_factory=lambda: [Orientation.REALM])

    @field_validator("orientations")
    @classmethod
    def _at_least_one_orientation(cls, v: list[Orientation]) -> list[Orientation]:
        if not v:
            return [Orientation.REALM]
        return list(dict.fromkeys(v))


class ThaumaturgyState(BaseModel):
    """All the thaumaturgy that a character knows. Not keyed to a splat (p.114).

    ExaltDefinition.thaumaturgy_usable decides if the character can use it."""
    arts: list[str] = Field(default_factory=list)              # trained Art ids: +2 dice
    art_specialties: list[ArtSpecialty] = Field(default_factory=list)
    sciences: list[ScienceRating] = Field(default_factory=list)
    rituals: list[RitualEntry] = Field(default_factory=list)
    formulas: list[FormulaEntry] = Field(default_factory=list)


class Combo(BaseModel):
    name: str
    charm_ids: list[str] = Field(default_factory=list)
    willpower_cost: int = Field(default=1, ge=0)


class Array(BaseModel):
    """An Alchemical Array (p.89). It links Attribute-based Charms.

    Cost: 1 bonus point per Charm at chargen. XP: the sum of the minimum Attribute
    ratings of the Charms. Ability-based martial arts Charms cannot join. The Array
    reduces the installation cost of its Charms to 3/4, rounded up (engine.validate).
    It grants each legal integrated Combo of its Charms for 1 Willpower. Only Charm
    Slot splats build Arrays (p.90)."""
    name: str
    charm_ids: list[str] = Field(default_factory=list)
    willpower_cost: int = Field(default=1, ge=0)


class Weapon(BaseModel):
    """Inline copy of a weapon that the character owns (rules.WeaponType)."""
    name: str
    speed: int = 0
    accuracy: int = 0
    damage: int = 0
    damage_type: str = "L"                 # "L" lethal / "B" bashing
    defense: int = 0
    rate: int = 0
    range: int = Field(default=0, ge=0)    # yards; 0 = melee only
    max_strength: int = Field(default=0, ge=0)
    min_strength: int = Field(default=0, ge=0)
    min_dexterity: int = Field(default=0, ge=0)
    min_martial_arts: int = Field(default=0, ge=0)
    # ⚠ A catalogue row can have a Resources cost and an Artifact rating. The player
    # sets 0 for the one not paid (human's ruling). 0 = mundane.
    artifact_rating: int = Field(default=0, ge=0)
    attunement: int = Field(default=0, ge=0)
    # The character commits `attunement` motes now, from `attuned_pool`. Ownership
    # does not imply attunement: nothing sets `attuned` on purchase, equip or load
    # (human's ruling). The player selects the pool (core pp.147-148, p.344).
    # `attuned_pool` is ignored on a merged pool.
    #
    # ⚠ This field is player-editable by design. Do not make it like `from_artifact`.
    #
    # ⚠ No module under `engine/validate/` may read either field (decision 0006). A
    # test finds violations.
    attuned: bool = False
    attuned_pool: Literal["personal", "peripheral"] = "peripheral"
    resources_cost: int = Field(default=0, ge=0)
    # rules.MagicalMaterial id; "" = mundane. engine.derive applies the bonus only if
    # the Exalt type matches.
    material: str = ""
    notes: str = ""
    # For ammunition (human's ruling). ⚠ A count, not a multiplier. The engine does not
    # read it (decision 0008).
    quantity: int = Field(default=1, ge=1)
    # `engine.artifacts.item_key` of the `Character.artifacts` entry whose stat line
    # this row is. "" = ordinary gear. Without the link, one item counts two times
    # against the p.131 budget.
    #
    # ⚠ Set once, when the artifact grants the row. No screen control can edit it: it
    # is a discriminator. A soft reference: if the key does not resolve,
    # `artifact_items` counts this row as its own item.
    from_artifact: str = ""
    acquired: str = "background"           # see ArtifactEntry.acquired


class Armor(BaseModel):
    """Inline copy of armor that the character owns (rules.ArmorType)."""
    name: str
    soak_lethal: int = 0                   # soak is computed per damage type in engine.derive
    soak_bashing: int = 0
    mobility_penalty: int = 0
    fatigue: int = 0
    artifact_rating: int = Field(default=0, ge=0)
    attunement: int = Field(default=0, ge=0)
    attuned: bool = False                  # see Weapon.attuned — same contract
    attuned_pool: Literal["personal", "peripheral"] = "peripheral"
    resources_cost: int = Field(default=0, ge=0)
    material: str = ""                     # magical material id; "" = mundane
    from_artifact: str = ""                # see Weapon.from_artifact — same contract
    acquired: str = "background"           # see ArtifactEntry.acquired


class GearEntry(BaseModel):
    """One item of mundane goods that the character owns (M&C p.123). An inline copy
    (decision 0007).

    ⚠ Only `goods` rows go here. A `service` row is never owned (human's ruling).
    See `rules.GearType`.
    """
    name: str
    resources_cost: int = Field(default=0, ge=0)
    quantity: int = Field(default=1, ge=1)
    note: str = ""


class VirtueFlaw(BaseModel):
    virtue: VirtueName
    description: str = ""


class OxBodyPurchase(BaseModel):
    """One purchase of Ox-Body Technique. `variant` is a rules.CharmVariant.key.
    `health_levels` is an inline copy of its levels, thus engine.derive needs no
    RuleSet."""
    variant: str
    health_levels: list[int] = Field(default_factory=list)


class VariantPurchase(BaseModel):
    """One purchase of a repeatable variant-menu Charm. Ox-Body and Deadly Beastman
    Transformation have their own lists.

    `charm_id` names the Charm. `variants` are the `rules.CharmVariant.key`s of this
    purchase. Example: Environmental Hazard-Resisting Meditation (Caste Book: Zenith
    p.72-73). See `rules.Charm.variants_unique`.
    """
    charm_id: str
    variants: list[str] = Field(default_factory=list)


class BeastmanGiftPurchase(BaseModel):
    """One purchase of Deadly Beastman Transformation (Lunar, p.124-127).

    `gifts` are the Gift variant keys of this purchase (rules.Charm.
    variant_picks_first_purchase / variant_picks_per_purchase).
    ⚠ The Attribute bonus of each purchase is not tracked: it applies only in hybrid
    form, which is play state."""
    gifts: list[str] = Field(default_factory=list)


class SubmodulePurchase(BaseModel):
    """One Alchemical submodule (p.89): the `key` of a rules.Submodule on the Charm
    `charm_id`. The character must know the Charm. A submodule has no rating."""
    charm_id: str
    key: str


class AnimalForm(BaseModel):
    """One shape in the Form Library of a Lunar. Free text. Not validated, not priced,
    and not in the XP audit."""
    name: str = ""
    notes: str = ""       # habitat, stats the ST assigned, when/where it was taken


class HealthLevel(BaseModel):
    """An adjustment to the health track. Usually a bonus level from a Charm. With
    `removed=True` it removes a level of that penalty (a curse). The base track is a
    rules constant. Damage is play state."""
    penalty: int                           # 0, -1, -2, -4 ...
    source_charm: str = ""
    removed: bool = False                  # True = a curse removing a level of this penalty


class XpEntry(BaseModel):
    """One post-lock purchase. The engine checks `cost` against the XP table, and
    checks that the current state shows the change."""
    target: str                            # "abilities.melee", "essence", "charms", ...
    detail: str = ""                       # charm/spell id for 'new' purchases
    from_rating: Optional[int] = None
    to_rating: Optional[int] = None
    cost: int
    training_complete: bool = True         # dormant hook for the parked training-time rule
    # On a `drop_merit` row only: a deep copy of the removed purchase. `undo_last`
    # adds it again.
    removed_purchase: Optional[MeritFlawPurchase] = None


class HouseRules(BaseModel):
    """Optional rules that the Storyteller switches on. Stored on the Character, thus
    they travel with the save.

    ⚠ A field that changes chargen accounting must also freeze into the
    ChargenSnapshot. Else a change after the lock re-prices the character.

    ⚠ Each field is TABLE-WIDE or PER-CHARACTER. A control that applies a value to
    all characters can change TABLE-WIDE fields only. `TABLE_WIDE_HOUSE_RULES` lists
    them.
    """
    # TABLE-WIDE. Player's Guide p.115: one free ritual, formula or aspect per two dots
    # of Occult.
    magic_for_everyone: bool = False

    # TABLE-WIDE. Player's Guide p.113: two independent chargen caps ("and/or"). They
    # do not apply after chargen.
    restrict_chargen_ritual_level: bool = False
    restrict_chargen_science_rating: bool = False

    # PER-CHARACTER. Core p.127: the character can start with Charms of other splats.
    # Chargen only. Has no effect unless the caste sets CasteDefinition.foreign_charms.
    st_foreign_charms: bool = False

    # PER-CHARACTER. Core p.103: a heroic mortal takes one Favored Ability. No other
    # Ability can be higher than it (mortal-favored-not-highest).
    mortal_favored_ability: bool = False

    # PER-CHARACTER. Sidereals p.106: a Celestial Manse above 3. Read through
    # `validate.background_st_permitted`.
    st_celestial_manse_over_three: bool = False

    # PER-CHARACTER. Core p.103: a mortal can hold the Artifact or Manse Background.
    # Chargen only. Read through `validate.background_st_permitted`.
    st_mortal_artifact_manse: bool = False

    # PER-CHARACTER. PG p.120: committed motes reduce the free third of the pool. No
    # page decides this. OFF: one third of the printed pool. ON: one third of the
    # remainder.
    # ⚠ The play tracker only (`build_play_view`). The sheet prints the full pool.
    # ⚠ Has no effect unless `derive.essence_freely_accessible` returns a number.
    committed_motes_reduce_free_essence: bool = False

    # TABLE-WIDE. p.66: all Backgrounds are available to all splats.
    # ⚠ Read only through `validate.background_catalogue_for`. It must not lift
    # `banned_backgrounds`.
    # Not frozen into the ChargenSnapshot: it changes the dropdown, not the costs.
    all_backgrounds_available: bool = False

    # TABLE-WIDE. Player's Guide p.17: how Merits and Flaws change after chargen.
    #
    #   "experience" (DEFAULT) — a change costs or pays 2x the bonus-point value in XP.
    #       A charge that the character cannot pay is a debt on later XP. Flaws above
    #       10 points pay nothing.
    #   "backgrounds" — changes with the plot. No XP.
    #   "swap" — a lost Trait is replaced by one of equal value. No XP.
    #
    # ⚠ "backgrounds" and "swap" are identical in the engine. Do not merge them: the
    # sheet records which one the table uses.
    mf_change_method: str = "experience"

    # PER-CHARACTER. Player's Guide p.258: a Terrestrial can go above Essence 7.
    # Ignored unless ExaltDefinition.tier is "Terrestrial".
    terrestrial_essence_transcendence: bool = False

    # TABLE-WIDE. Player's Guide p.61: the free dots of the Inheritance Background
    # (1-5). It does not set the rating. The character gets the bonus points of the
    # rating on the sheet (human's ruling). None = use the budget `free_rating`.
    godblooded_inheritance_rating: Optional[int] = Field(default=None, ge=1, le=5)

    @field_validator("mf_change_method")
    @classmethod
    def _check_mf_method(cls, v: str) -> str:
        if v not in ("experience", "backgrounds", "swap"):
            raise ValueError(
                f"mf_change_method must be experience/backgrounds/swap, got {v!r}")
        return v


# The TABLE-WIDE fields of `HouseRules`. A campaign copies these fields onto each
# copy (`engine.house_rule_actions.apply_table_rules`). ⚠ `ui.view._HOUSE_RULES`
# gives each field a scope too. A test asserts that its "table" rows are this set.
TABLE_WIDE_HOUSE_RULES = frozenset({
    "magic_for_everyone", "restrict_chargen_ritual_level",
    "restrict_chargen_science_rating", "all_backgrounds_available", "mf_change_method",
    "godblooded_inheritance_rating",
})


class ChargenSnapshot(BaseModel):
    """The traits at the lock. The baseline of the XP log."""
    attributes: dict[AttributeName, int]
    abilities: dict[AbilityName, int]
    crafts: list[CraftRating] = Field(default_factory=list)
    colleges: list[CollegeRating] = Field(default_factory=list)
    paths: list[PathRating] = Field(default_factory=list)
    favored_path: str = ""
    virtues: dict[VirtueName, int]
    specialties: list[Specialty]
    backgrounds: list[BackgroundEntry]
    # ⚠ Artifacts are not frozen: XP can raise the Artifact Background, thus the p.131
    # budget changes. engine.validate.check_artifacts checks them on both sides.
    # ⚠ Passions are not frozen: they derive from the Virtues on both sides (p.283).
    fetters: list[FetterEntry] = Field(default_factory=list)
    merits_flaws: list[MeritFlawPurchase] = Field(default_factory=list)
    charms: list[str]
    elemental_powers: list[str] = Field(default_factory=list)
    spells: list[str]
    combos: list[Combo] = Field(default_factory=list)
    arrays: list[Array] = Field(default_factory=list)
    submodules: list[SubmodulePurchase] = Field(default_factory=list)
    ox_body: list[OxBodyPurchase] = Field(default_factory=list)
    beastman_gifts: list[BeastmanGiftPurchase] = Field(default_factory=list)
    variant_purchases: list[VariantPurchase] = Field(default_factory=list)
    # ⚠ None, not an empty state, if the character bought no thaumaturgy. The XP
    # audit uses the difference.
    thaumaturgy: Optional[ThaumaturgyState] = None
    house_rules: Optional[HouseRules] = None
    essence_rating: int
    willpower_purchased: int
    wp_virtue_component: int               # two highest Virtues AT LOCK; never recomputed


class PlayState(BaseModel):
    """Play state: spent motes and Willpower, health damage, and Limit.

    ⚠ Chargen validation, the XP audit and the permanent derivations do not read this
    layer (decision 0006). It is a manual tracker for the Storyteller.

    `health` aligns by position with engine.derive.health_track. The render
    normalizes its length. `willpower_spent` counts spent boxes. `limit` is 0..10.

    `renown` (Lunar, p.112-115): four 0-100 scores that the Storyteller sets. `face`
    (0-10): a rank that the Storyteller sets (p.113). Not enforced for a Casteless
    Lunar (p.108)."""
    health: list[Optional[Damage]] = Field(default_factory=list)
    motes_personal_spent: int = Field(default=0, ge=0)
    motes_peripheral_spent: int = Field(default=0, ge=0)
    willpower_spent: int = Field(default=0, ge=0)
    limit: int = Field(default=0, ge=0, le=10)
    # Alchemical (CH2 p.69-71): temporary Clarity. engine.derive.clarity gives the
    # permanent value.
    clarity_temporary: int = Field(default=0, ge=0, le=10)
    # Core p.332: the armor fatigue penalty. A manual counter: it is a roll result
    # (decision 0009). Stored positive. It subtracts from a pool.
    fatigue: int = Field(default=0, ge=0)
    # The name of the weapon in hand. "" = unarmed. Read through `view.wielded_index`.
    # A name that no weapon has gives unarmed.
    in_hand: str = ""
    renown: dict[str, int] = Field(
        default_factory=lambda: {"succor": 0, "mettle": 0, "cunning": 0, "glory": 0})
    face: int = Field(default=0, ge=0, le=10)

    @field_validator("renown")
    @classmethod
    def _check_renown_range(cls, v: dict[str, int]) -> dict[str, int]:
        for k, rating in v.items():
            if not (0 <= rating <= 100):
                raise ValueError(f"renown[{k!r}] = {rating}; must be 0-100.")
        return v


# --------------------------------------------------------------------------- #
# The character
# --------------------------------------------------------------------------- #

def new_character_id() -> str:
    """Return a new unique character id.

    ⚠ Do not use a constant id. Data keyed by `character.id` merges two characters
    that share an id.
    """
    return f"char.{uuid.uuid4().hex[:12]}"


class Character(BaseModel):
    # --- identity / concept ---
    id: str
    name: str = ""
    player: str = ""
    edition: str = "1e"
    exalt_type: str = "Solar"
    caste: str = "dawn"                     # CasteDefinition.id into ruleset.castes
    # The origin variant of the splat, which selects the chargen budget
    # (Dragon-Blooded p.150-151). "" = the default budget. Lunar "casteless" must
    # agree with `caste` (engine.validate.check_lunar_casteless_consistency).
    origin: str = ""
    # The upbringing under `origin`. It changes the budget only (p.68, p.159, p.133).
    # "" = the default upbringing of the origin.
    upbringing: str = ""
    # Cult of the Illuminated (Solar, p.89-93). `camp`: a rules.TrainingCamp id.
    # `calling`: a rules.Calling id. "" unless ChargenBudgets.requires_camp or
    # .requires_calling is set.
    camp: str = ""
    calling: str = ""
    # p.90: the free Charms of the camp, resolved.
    # ⚠ Not in `charms`: they do not count against the Charm pool or the minimum.
    granted_charms: list[str] = Field(default_factory=list)
    concept: str = ""
    nature: str = ""
    anima: str = ""
    # --- biography: free text. The engine does not read these fields. ---
    sex: str = ""
    age: str = ""
    eye_color: str = ""
    hair_color: str = ""
    skin_color: str = ""
    height: str = ""
    weight: str = ""
    description: str = ""
    backstory: str = ""
    notes: str = ""
    # Lunar Form Library. Free text. See AnimalForm.
    totem: str = ""
    animal_forms: list[AnimalForm] = Field(default_factory=list)

    # --- current, canonical traits ---
    essence_rating: int = Field(default=2, ge=1)
    # PG p.41: permanent Resonance of a character with Death's Taint. A permanent
    # trait, not play state (decision 0006). The temporary value is PlayState.limit.
    # ⚠ After the lock, change it through engine.advancement only, thus the ledger
    # records it.
    limit_permanent: int = Field(default=0, ge=0)
    attributes: dict[AttributeName, int] = Field(
        default_factory=lambda: {a: 1 for a in AttributeName}
    )
    abilities: dict[AbilityName, int] = Field(
        default_factory=lambda: {a: 0 for a in AbilityName}
    )
    # Core p.136. ⚠ The AbilityName.CRAFT key in `abilities` is unused.
    crafts: list[CraftRating] = Field(default_factory=list)
    # Sidereal p.98.
    colleges: list[CollegeRating] = Field(default_factory=list)
    # PG p.175-177. `favored_path`: the one Favored Path that the player selects
    # (human's ruling). The two Breed Paths are Favored by element.
    paths: list[PathRating] = Field(default_factory=list)
    favored_path: str = ""
    favored_abilities: list[AbilityName] = Field(default_factory=list)
    # Alchemical p.60: the Favored Attributes. Read only by a `caste_favored` splat.
    favored_attributes: list[AttributeName] = Field(default_factory=list)
    specialties: list[Specialty] = Field(default_factory=list)

    virtues: dict[VirtueName, int] = Field(
        default_factory=lambda: {v: 1 for v in VirtueName}
    )
    virtue_flaw: Optional[VirtueFlaw] = None

    # Purchased Willpower dots, net of permanent penalties. Permanent WP = component +
    # purchased. ⚠ A curse can make it negative after the lock
    # (engine.advancement.lower_willpower). The engine floors permanent WP at 1.
    willpower_purchased: int = 0
    # Frozen at lock (decision 0005). None before the lock.
    wp_virtue_component: Optional[int] = None

    backgrounds: list[BackgroundEntry] = Field(default_factory=list)
    # E:Ab p.131. Paid with Artifact Background dots. See ArtifactEntry.
    artifacts: list[ArtifactEntry] = Field(default_factory=list)
    # M&C p.123. `view.inventory_rows` shows this list with the weapons and armor.
    gear: list[GearEntry] = Field(default_factory=list)
    # Ghosts (E:Ab p.126-127). See FetterEntry and PassionEntry.
    fetters: list[FetterEntry] = Field(default_factory=list)
    passions: list[PassionEntry] = Field(default_factory=list)
    # Decision 0011. engine.merits calculates the effects.
    merits_flaws: list[MeritFlawPurchase] = Field(default_factory=list)
    charms: list[str] = Field(default_factory=list)           # Charm ids into the RuleSet
    # Core p.296, GoD p.56, PG p.68: Elemental God-Blooded. Cost: bp_cost bonus
    # points, or bp_cost * 2 XP.
    elemental_powers: list[str] = Field(default_factory=list)
    # Alchemical Panoply (p.89): owned Charms that are not in a Slot.
    # ⚠ Not in `charms`, which is the installed set that the Slot rules count.
    retainer_charms: list[str] = Field(default_factory=list)
    combos: list[Combo] = Field(default_factory=list)
    # Alchemical (p.89). See Array.
    arrays: list[Array] = Field(default_factory=list)
    # Alchemical (p.89).
    submodules: list[SubmodulePurchase] = Field(default_factory=list)
    spells: list[str] = Field(default_factory=list)           # Spell ids into the RuleSet
    # One record per purchase. ⚠ Not in `charms`.
    ox_body: list[OxBodyPurchase] = Field(default_factory=list)
    # Alchemical (p.88-89): the total Slots, free and bought. None = the free base
    # from ChargenBudgets.
    general_charm_slots: Optional[int] = None
    dedicated_charm_slots: Optional[int] = None
    # Lunar p.124-127. One record per purchase. ⚠ Not in `charms`.
    beastman_gifts: list[BeastmanGiftPurchase] = Field(default_factory=list)
    # See VariantPurchase. ⚠ Not in `charms`.
    variant_purchases: list[VariantPurchase] = Field(default_factory=list)

    # Player's Guide CH3. Not keyed to a splat.
    thaumaturgy: Optional[ThaumaturgyState] = None

    weapons: list[Weapon] = Field(default_factory=list)
    armor: list[Armor] = Field(default_factory=list)
    health_bonus_levels: list[HealthLevel] = Field(default_factory=list)

    # --- lifecycle / accounting ---
    chargen_locked: bool = False
    chargen_snapshot: Optional[ChargenSnapshot] = None
    xp_earned: int = Field(default=0, ge=0)
    xp_log: list[XpEntry] = Field(default_factory=list)

    # --- Storyteller options (see HouseRules; frozen into the snapshot at lock) ---
    house_rules: Optional[HouseRules] = None

    # --- play-state (separate layer; never enters chargen/XP validation) ---
    play: Optional[PlayState] = None

    # --- homebrew this character depends on (see custom_content.py) ------------
    # Copies of the custom definitions that the character uses by id, keyed
    # "charms"/"spells"/"rituals" (decision 0012). Gear needs no entry: the save has
    # inline copies (decision 0007).
    #
    # ⚠ Opaque dicts, not Charm/Spell models: this module does not import the rules
    # catalogue. custom_content writes them and rules_db loads them. A bad row is
    # reported, not fatal.
    #
    # The engine does not read this field. An id that is here but not in the RuleSet
    # is an `unknown-charm` error.
    custom_definitions: dict[str, list[dict]] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_st_foreign_charms(cls, data: object) -> object:
        """Move a top-level `st_foreign_charms` into `house_rules`.

        Input: the raw payload. Output: the payload without the top-level key. The
        value goes into `house_rules` unless `house_rules` already has the key.
        """
        if not isinstance(data, dict) or "st_foreign_charms" not in data:
            return data
        data = dict(data)
        legacy = data.pop("st_foreign_charms")
        existing = data.get("house_rules")
        if isinstance(existing, HouseRules):
            existing = existing.model_dump()
        if existing is None:
            existing = {}
        if isinstance(existing, dict):
            existing.setdefault("st_foreign_charms", legacy)
            data["house_rules"] = existing
        return data

    @field_validator("caste", mode="before")
    @classmethod
    def _migrate_legacy_caste(cls, v: object) -> object:
        """Map a capitalized Solar caste ("Dawn") to its id ("dawn"). Return any
        other value unchanged."""
        return _LEGACY_CASTE_IDS.get(v, v) if isinstance(v, str) else v
