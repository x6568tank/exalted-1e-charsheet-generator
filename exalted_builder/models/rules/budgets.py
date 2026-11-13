"""
models/rules/budgets.py — the cost tables and the chargen budgets: bonus point
costs, XP costs, Background rules, Essence pool formulas, and the Exalt definitions.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ._base import (AbilityGroupMinimum, AbilityMinimum, AbilityName,
                    BackgroundBudgetTier, EssencePoolSpec, SpellCircle, VirtueName)


# --------------------------------------------------------------------------- #
# Cost tables
# --------------------------------------------------------------------------- #

class LinearCost(BaseModel):
    """cost = current * coeff + offset. The favored or caste discount is offset -1."""
    coeff: int
    offset: int = 0

    def at(self, current: int) -> int:
        return current * self.coeff + self.offset


class BonusPointCosts(BaseModel):
    """Flat bonus point costs for one purchase at chargen.

    `background_above_3` applies when the dot raises the Background above 3."""
    attribute: int = 4
    # Lunar p.93: a Caste Attribute.
    attribute_caste_favored: int = 4
    ability: int = 2
    ability_favored_caste: int = 1
    background: int = 1
    background_above_3: int = 2
    specialty: int = 1
    # p.105: dots for 1 BP in a Favored or Caste Ability. The cost rounds up.
    specialty_favored_caste_dots_per_point: int = 2
    # --- Thaumaturgy (Player's Guide BP table, p.116) ------------------------ #
    # An Art Specialty and a printed Art aspect are the same purchase.
    thaum_art: int = 5
    thaum_art_specialty: int = 2
    # Ritual: base + per_level x level.
    thaum_ritual_base: int = 2
    thaum_ritual_per_level: int = 1
    thaum_formula: int = 1
    # p.124: each additional regional version of a known ritual or formula.
    thaum_extra_orientation: int = 1
    # ⚠ Human's ruling. No page gives the Science costs: the printed tables omit
    # them. This is a known exception. Do not "correct" it. A printed source wins.
    thaum_science_first_dot: int = 5
    thaum_science_additional_dot: int = 7
    virtue: int = 3
    # E:Ab p.127. The Passions have no row: they derive from the Virtues.
    fetter: int = 3
    willpower: int = 2
    essence: int = 7
    # God-Blooded p.50: the cost of a step, keyed by the target rating. It overrides
    # `essence` for the listed steps. The starred prerequisites are in validate.
    essence_by_rating: dict[int, int] = Field(default_factory=dict)
    charm: int = 5
    charm_favored_caste: int = 4
    # Mountain Folk CH6 p.233: the surcharge for a Charm of another caste's Pattern.
    charm_cross_pattern: int = 0
    # God-Blooded p.50: a Charm with `grants_circle` set. 0 = use `charm`.
    magic_charm: int = 0
    # Dragon-Blooded p.153. The favored or caste discount applies as for `charm`.
    immaculate_charm: int = 10
    immaculate_charm_favored_caste: int = 7
    # Sidereal p.101: all Martial Arts Charms. None = use `charm`. ⚠ The engine
    # checks the Immaculate rate first.
    martial_arts_charm: Optional[int] = None
    martial_arts_charm_favored_caste: Optional[int] = None
    # Sidereal p.100-101. `college_own_house`: a College of the character's Maiden.
    college: int = 8
    college_own_house: int = 6
    # Dragon-King PG p.176. `path_breed`: a Breed Path, or the chosen Favored Path.
    path: int = 0
    path_breed: int = 0
    path_above_3: int = 0
    path_breed_above_3: int = 0
    # Cult of the Illuminated p.90 and p.93. A Calling is a discount axis, not a
    # second Favored list. These rates replace `ability` and `charm` for a Calling
    # trait, and stack with the Caste or Favored discount.
    calling_ability: int = 2                        # Calling, not Caste/Favored
    # p.90: "1 point per 2 dots". The cost rounds up (human's ruling).
    calling_ability_favored_caste_dots_per_point: int = 1
    calling_charm: int = 5                          # Calling, not Caste/Favored
    calling_charm_favored_caste: int = 4            # Calling and Caste/Favored


class ExperienceCosts(BaseModel):
    attribute: LinearCost = Field(default_factory=lambda: LinearCost(coeff=4))
    # Lunar p.251: a Caste Attribute.
    attribute_caste_favored: LinearCost = Field(default_factory=lambda: LinearCost(coeff=4))
    # Autochthonians p.64: a Caste or Favored Attribute of a `caste_favored` splat.
    attribute_favored_caste: LinearCost = Field(default_factory=lambda: LinearCost(coeff=4, offset=-1))
    ability: LinearCost = Field(default_factory=lambda: LinearCost(coeff=2))
    ability_favored_caste: LinearCost = Field(default_factory=lambda: LinearCost(coeff=2, offset=-1))
    essence: LinearCost = Field(default_factory=lambda: LinearCost(coeff=8))
    # Mortal PG p.115: the cost of a step, keyed by the target rating. It overrides
    # `essence` for the listed steps. The starred prerequisites are not costs.
    essence_by_rating: dict[int, int] = Field(default_factory=dict)
    virtue: LinearCost = Field(default_factory=lambda: LinearCost(coeff=3))   # does NOT raise Willpower
    # --- Fetters and Passions (ghosts, E:Ab p.283) --------------------------- #
    fetter: LinearCost = Field(default_factory=lambda: LinearCost(coeff=3))
    new_fetter: int = 20
    # The discount for a character who knows the Arcanos `new_fetter_discount_charm_id`.
    # "" disables the discount.
    new_fetter_discounted: int = 0
    new_fetter_discount_charm_id: str = ""
    # p.283: move the focus of a Passion or a Fetter. ⚠ A shift is a transfer: the
    # total does not change.
    shift_passion: int = 20
    shift_fetter: int = 10
    willpower: LinearCost = Field(default_factory=lambda: LinearCost(coeff=2))
    new_ability: int = 3
    new_specialty: int = 3
    # Mountain Folk CH6 p.237: a Craft Ability and a Craft specialty. These replace
    # the Favored discount. None and 0 = the ordinary rates.
    craft: Optional[LinearCost] = None
    craft_specialty: int = 0
    # --- Thaumaturgy (Player's Guide XP table, p.115) ------------------------ #
    # ⚠ An Art Specialty is 2 BP and 3 XP. The tables differ. Do not make them agree.
    # A mystical Merit costs its BP value x this.
    new_merit_bp_multiplier: int = 2
    thaum_new_art: int = 5
    thaum_new_art_specialty: int = 3
    # Ritual: base + per_level x level.
    thaum_ritual_base: int = 3
    thaum_ritual_per_level: int = 1
    thaum_formula: int = 1
    thaum_extra_orientation: int = 1
    # ⚠ Human's ruling, as for the BP Science costs. No page gives these values.
    thaum_new_science: int = 7
    thaum_science: LinearCost = Field(default_factory=lambda: LinearCost(coeff=6))
    # Sidereal p.265.
    new_college: int = 5
    college: LinearCost = Field(default_factory=lambda: LinearCost(coeff=3))
    # Dragon-King PG p.176.
    new_path: int = 0
    new_path_breed: int = 0
    path: LinearCost = Field(default_factory=lambda: LinearCost(coeff=0))
    path_breed: LinearCost = Field(default_factory=lambda: LinearCost(coeff=0))
    new_charm: int = 10
    new_charm_favored_caste: int = 8
    # Mountain Folk CH6 p.233: the surcharge for a Charm of another caste's Pattern.
    new_charm_cross_pattern: int = 0
    # Dragon-Blooded p.292. Applies to a Charm with `immaculate` set.
    new_immaculate_charm: int = 10
    new_immaculate_charm_favored_caste: int = 8
    new_spell: int = 10
    new_spell_occult_favored_caste: int = 8
    # God-Blooded p.49: a Charm with `grants_circle` set. 0 = use `new_charm`.
    new_magic_charm: int = 0
    # Lunar p.251: the cost by circle. A listed circle overrides `new_spell`. The
    # discount is then CasteDefinition.spell_cost_discount, not the Occult discount.
    new_spell_by_circle: dict[SpellCircle, int] = Field(default_factory=dict)
    foreign_charm: int = 20                # spirit Charms / other Exalt types; Eclipse only (gated in engine)
    # Autochthonians p.64: the cost of a weaving protocol by circle. A listed circle
    # overrides `new_spell`, and the Occult discount does not apply.
    spell_cost_by_circle: dict[str, int] = Field(default_factory=dict)
    # Alchemical Charm Slots (p.64). A bought Slot includes one free Charm.
    # `new_charm` is then the cost of a Charm without a Slot.
    new_charm_slot_general: int = 12
    new_charm_slot_dedicated: int = 10
    charm_slot_upgrade: int = 2            # one Dedicated Slot to General
    # Sidereal p.265: all Martial Arts Charms. None = use `new_charm`.
    new_martial_arts_charm: Optional[int] = None
    new_martial_arts_charm_favored_caste: Optional[int] = None
    # Cult of the Illuminated p.102. Subtracted from the cost. It stacks with the
    # Caste or Favored discount.
    calling_ability_discount: int = 0
    calling_charm_discount: int = 0


class BackgroundRule(BaseModel):
    """The mechanical rules of one Background for one splat.

    `ChargenBudgets.background_rules` holds these rules. A Background with no rule is
    free text with no mechanics. Alchemical CH2 p.65-69 is the first source."""
    model_config = ConfigDict(frozen=True)

    # This Background can go above `background_cap_pre_bp` without bonus points.
    cap_pre_bp_exempt: bool = False
    # Pool dots for each dot of this Background. E:Ab p.151: Whispers.
    # ⚠ `expensive_above: 0` means "no expensive dots", thus that pair cannot express
    # a cost on all dots. The two fields compose.
    dot_cost: int = Field(default=1, ge=1)
    expensive_above: int = 0               # 0 = no threshold; see dot_cost
    expensive_dot_cost: int = Field(default=1, ge=1)
    # A rating that the character must buy with pool dots (Alchemical Class, CH2 p.61).
    min_rating: int = Field(default=0, ge=0)
    # Dots that the character gets in addition to the pool (Illuminated, p.90).
    free_rating: int = Field(default=0, ge=0)
    # p.66 (Lookshy Breeding): extra bonus points for each dot above
    # `background_cap_pre_bp`, added to `background_above_3`.
    bp_surcharge_per_dot: int = Field(default=0, ge=0)
    requires: str = ""                     # another Background's NAME, lowercased
    requires_rating: int = Field(default=0, ge=0)
    # E:Ab p.126: a ceiling that bonus points cannot buy past. 0 = no ceiling.
    max_rating: int = Field(default=0, ge=0)
    # The budget table of a Background that buys rated items. ⚠ `Abyssal:fugitive`
    # must not carry these: it uses the core Artifact Background (p.131).
    budget_tiers: tuple[BackgroundBudgetTier, ...] = ()
    # Artifact rating for each dot bought. Read by `engine.artifacts.acquisition_cost`.
    # The tiers win if both shapes are set.
    rating_per_dot: int = Field(default=1, ge=1)
    # True: the rule applies after the lock too (Sidereals p.106; Mountain Folk CH6
    # p.234-235 and human's ruling). `background_issues` applies only these post-lock.
    bind_post_lock: bool = False
    # Mountain Folk CH6: effective rating = stored rating + `effective_bonus`. At zero
    # dots the effective rating is `effective_floor`; the bonus does not apply.
    # ⚠ `validate.effective_background_rating` is the one read site. A raw
    # `BackgroundEntry.rating` is the stored rating.
    effective_bonus: int = Field(default=0, ge=0)
    effective_floor: int = Field(default=0, ge=0)
    # Sidereals pp.106-108: the rating cannot exceed the sum of the Attributes.
    # `background_issues` skips this check if it gets no character. Chargen only.
    max_rating_is_attribute_sum: bool = False
    # Core p.103: the rating must be 0 unless `st_toggle` is set. Chargen only.
    barred: bool = False
    # The name of the PER-CHARACTER `HouseRules` field that lifts this rule. Read
    # through `validate.background_st_permitted` only. "" = no toggle.
    st_toggle: str = ""
    # Mountain Folk CH6 p.234-235: each dot above this rating costs one bonus point,
    # not a pool dot. 0 = no threshold.
    bp_above_rating: int = Field(default=0, ge=0)


class ChargenBudgets(BaseModel):
    # The engine matches the pools to the categories by spend.
    attribute_pools: tuple[int, int, int] = (8, 6, 4)
    attribute_base: int = 1
    # Mountain Folk CH6 p.230: a floor for each Attribute.
    attribute_min: int = 0
    # Mountain Folk CH6 p.230: an Attribute ceiling on both sides of the lock.
    # 0 = the normal ceiling.
    attribute_cap: int = 0
    # Mountain Folk CH6 p.230: ceilings by AttributeName value. An absent Attribute
    # uses `attribute_cap`.
    attribute_caps: dict[str, int] = Field(default_factory=dict)
    # Mountain Folk CH6 p.230: an Ability ceiling on both sides of the lock.
    # 0 = the normal ceiling.
    ability_cap: int = 0
    # "category": the pools match the three categories by spend.
    # "caste_favored" (Alchemical, p.60): the pools go in order to the Caste
    # Attributes, the Favored Attributes, and the other Attributes.
    attribute_mode: str = "category"
    # caste_favored mode only (p.60).
    attribute_favored_count: int = 0
    attribute_caste_min: int = 0

    # Dragon-Blooded p.151: floors spent from the pool.
    required_min_abilities: list[AbilityMinimum] = Field(default_factory=list)
    # Mountain Folk CH6 p.230: floors on the sum of a group of Abilities.
    required_min_ability_groups: list[AbilityGroupMinimum] = Field(default_factory=list)

    # Lunar p.90: Abilities that must be Favored.
    required_favored: list[AbilityName] = Field(default_factory=list)

    ability_dots: int = 25
    ability_min_caste_favored: int = 10    # >= 10 of the 25 on caste/favored abilities
    # Mountain Folk CH6 p.230: a separate pool for the Favored Abilities. When it is
    # set, `ability_dots` is the pool for any Ability. 0 = one pool.
    ability_favored_dots: int = 0
    ability_cap_pre_bp: int = 3
    favored_count: int = 5                 # >= 1 dot required in each favored ability
    # Core p.103: this origin can take the optional Favored Ability. ⚠ The PER-CHARACTER
    # `HouseRules.mortal_favored_ability` must also be set.
    optional_favored_ability: bool = False

    background_dots: int = 7
    background_cap_pre_bp: int = 3
    # Mountain Folk CH6 p.230: dots by CasteDefinition.id. An absent caste uses
    # `background_dots`.
    background_dots_by_caste: dict[str, int] = Field(default_factory=dict)
    # Rules by the lowercased Background NAME (CH2 p.65-69).
    background_rules: dict[str, BackgroundRule] = Field(default_factory=dict)
    # Sidereal p.100: the only Backgrounds this origin can take, as lowercased NAMEs.
    # Empty = no restriction.
    allowed_backgrounds: list[str] = Field(default_factory=list)
    # The Backgrounds that the dropdown shows. Read through
    # `RuleSet.catalogue_backgrounds_for`. Empty = use the `exalt_type` tag.
    # An entry is a lowercased NAME, or an id ("background.whispers"). Use an id for a
    # name that exists twice, or for a Background tagged for a different splat (PG p.50).
    #
    # ⚠ Not the same as `allowed_backgrounds`:
    #
    #   allowed_backgrounds     HARD VALIDATION. A name outside it is an ERROR
    #                           (`background-not-allowed`).
    #   catalogue_backgrounds   OFFERED LIST. A name outside it is legal but not in
    #                           the dropdown.
    #
    # A list in the incorrect field makes all free-text Backgrounds illegal.
    catalogue_backgrounds: list[str] = Field(default_factory=list)
    # Mountain Folk CH6 p.234: Backgrounds this origin cannot take, as lowercased NAMEs.
    banned_backgrounds: list[str] = Field(default_factory=list)
    # p.100: ignore the caste's `required_min_abilities` for this origin.
    ignore_caste_min_abilities: bool = False

    # Sidereal p.98: the College pool. 0 = no Colleges. `college_min_own_house` is the
    # minimum in the Colleges of the character's Maiden.
    college_dots: int = 0
    college_min_own_house: int = 0
    college_cap_pre_bp: int = 3

    # Dragon-King PG p.175-177: the Path pool. 0 = no Paths.
    # `path_max_by_essence` (p.177) uses the CURRENT Essence, not `essence_start`.
    path_dots: int = 0
    path_min_breed_favored: int = 0
    path_cap_pre_bp: int = 3
    path_max_by_essence: dict[int, int] = Field(default_factory=dict)
    # p.177: ceilings by current Essence. `elder.trait_ceiling` gives the Ability
    # ceiling, thus there is no Ability field.
    intelligence_max_by_essence: dict[int, int] = Field(default_factory=dict)
    virtue_max_by_essence: dict[int, int] = Field(default_factory=dict)
    # p.175: Virtue floors spent from `virtue_dots`.
    required_virtue_dots: dict[VirtueName, int] = Field(default_factory=dict)

    virtue_dots: int = 5                   # spent over a base of 1 each
    virtue_base: int = 1
    virtue_cap_pre_bp: int = 3

    # E:Ab p.126: the Fetter pool. 0 = no Fetter panel. The Passions have no pool:
    # they derive from the Virtues (p.283).
    fetter_dots: int = 0
    fetter_cap_pre_bp: int = 3

    charm_count: int = 10
    charm_min_caste_favored: int = 5
    # Sidereal p.101: the maximum chargen Charms from Martial Arts Charms with
    # `open_to_tiers` set. None = no cap. 0 = barred.
    martial_arts_form_charm_cap: Optional[int] = None
    # Alchemical p.88-89: the free Slots. If one is > 0, the engine counts Slots,
    # not Charms. A General Slot holds any Charm. A Dedicated Slot holds a
    # Caste or Favored Attribute Charm.
    charm_slots_general: int = 0
    charm_slots_dedicated: int = 0
    # Dragon-Blooded p.151: the Charm count if the character takes Immaculate Charms.
    immaculate_charm_count: int = 5
    # p.68: Charm ids that this origin gets free at creation.
    granted_charms: list[str] = Field(default_factory=list)
    # p.68: this origin cannot take Immaculate Charms at chargen.
    bar_immaculate_charms_at_chargen: bool = False

    essence_start: int = 2
    # Cult of the Illuminated p.90: the Essence ceiling at the end of chargen.
    # 0 = no ceiling.
    essence_start_cap: int = 0
    # Mountain Folk CH6 p.230: overrides ExaltDefinition.essence_cap for this origin.
    # 0 = use the splat value.
    essence_cap: int = 0
    # The origin needs a TrainingCamp, or a Calling.
    requires_camp: bool = False
    requires_calling: bool = False
    bonus_points: int = 15
    # Player's Guide p.61: bonus points added, by the Inheritance rating (0..5).
    # Read by validate.bonus_point_breakdown.
    inheritance_bonus_points: list[int] = Field(default_factory=list)
    # p.61: the Flaw-point cap, by the Inheritance rating. Read by
    # engine.merits.merits_and_flaws_calc. Index 0 is 0 (human's ruling).
    inheritance_flaw_cap: list[int] = Field(default_factory=list)

    willpower_start_cap: int = 8           # may not start above this...
    willpower_cap_exception_virtue: int = 4   # ...unless at least
    willpower_cap_exception_count: int = 2    # this many Virtues are >= 4
    # Mountain Folk CH6 p.230: a Willpower ceiling on both sides of the lock.
    # 0 = no ceiling.
    willpower_hard_cap: int = 0

    @field_validator("attribute_mode")
    @classmethod
    def _check_attribute_mode(cls, v: str) -> str:
        if v not in ("category", "caste_favored"):
            raise ValueError(
                f"attribute_mode must be category/caste_favored, got {v!r}")
        return v


class ExaltDefinition(BaseModel):
    """One Exalt type. `id` matches Character.exalt_type ("Solar", "Abyssal")."""
    model_config = ConfigDict(frozen=True)
    id: str
    label: str
    essence: EssencePoolSpec
    magic_track: str = "sorcery"            # "sorcery" | "necromancy"
    # The circle that is barred at chargen (core p.100). It is not the highest
    # reachable circle. Read only by validate.chargen_barred_circle.
    # ⚠ Set "" for a splat whose only circle is its entry circle (Dragon-Blooded).
    # Else the splat has no sorcery at chargen.
    highest_magic_circle_id: str = ""       # e.g. "Solar"; "" = nothing barred at chargen
    ox_body_charm_id: str = ""              # the splat's repeatable health-level Charm
    # Lunar p.124-127: the repeatable Charm with variant picks.
    gift_charm_id: str = ""
    # The UI shows the Form Library page. Not validated.
    form_library: bool = False
    # CH2 p.69-71: Clarity replaces Limit. engine.derive.clarity gives the permanent
    # value.
    clarity: bool = False
    # p.253: the name of the Limit track. Display only. Ignored if `clarity` is True.
    limit_label: str = "Limit"
    # Core p.103: the splat has a Virtue Flaw. False for Dragon-Blooded, Sidereal and
    # Alchemical (human's ruling). Independent of `limit_label` and `clarity`.
    has_virtue_flaw: bool = True
    # Core p.103: False bars all Charms. ⚠ A `charm_count` of 0 does not: bonus points
    # can still buy an `open_to_all` Charm. ⚠ Merits can lift the bar. Read it through
    # `engine.merits.merits_and_flaws_calc` (decision 0011).
    charms_available: bool = True
    # The Essence ceiling after the lock. ChargenBudgets.essence_start_cap is the
    # ceiling before the lock. ⚠ 0 gives 9 (p.258) in engine.elder. Write the value
    # for each new splat. engine.elder holds a Terrestrial at 7.
    # Mortals: 1 (Player's Guide p.11). Essence Mastery (PG p.121) gives 3 (human's
    # ruling). ⚠ `merits_and_flaws_calc` RAISES this 1 to 3 rather than removing it.
    essence_cap: int = 0
    # PG p.114: the Essence formula after a Merit unlocks the pool. One pool.
    # Selected by engine.derive.essence_pools through engine.merits.
    unlocked_essence: Optional[EssencePoolSpec] = None
    # The UI name of the caste slot. Display only.
    caste_noun: str = "Caste"
    # E:Ab p.126: the plural name of the Charm pool. Display only.
    charm_noun: str = "Charms"
    # Read only by validate.charm_matches_splat, against Charm.open_to_tiers.
    tier: str = "Celestial"
    # Player's Guide p.114: the splat can use its thaumaturgy. ⚠ False bars use only.
    # The character keeps and can teach the thaumaturgy.
    thaumaturgy_usable: bool = True
    # p.114: multiplier on the cost of an Art, Science, ritual or formula.
    thaumaturgy_cost_multiplier: int = Field(default=1, ge=1)
    # E:Ab p.126: one Essence pool, not Personal and Peripheral.
    # ⚠ The Beacon of Power Merit is the second source. `derive.essence_pool_is_merged`
    # is the one read site for both. Do not add a second read site.
    single_essence_pool: bool = False
    # E:Ab p.126: bars all Charms of other splats, `open_to_all` Charms included.
    # ⚠ `charms_available` bars all Charms. This bars only Charms of other splats.
    foreign_charms_barred: bool = False
    # PG p.234: Terrestrial Martial Arts are open, at the cost `new_martial_arts_charm`.
    # The one exception to `foreign_charms_barred`. ⚠ It does not need a Merit.
    terrestrial_martial_arts: bool = False
    # Charm ids that the splat can never hold (human's ruling).
    # ⚠ charm_matches_splat checks this list first. No grant can override it.
    barred_charm_ids: list[str] = Field(default_factory=list)
    # PG p.48: spell ids that the splat can never learn.
    # ⚠ Check both meets_spell_requirements and check_spell_access.
    barred_spell_ids: list[str] = Field(default_factory=list)
    # E:Ab p.234: False bars all Combos.
    combos_available: bool = True
    # PG p.165: Stamina // 2 adds to lethal soak. Read by derive.soak.
    stamina_adds_to_lethal_soak: bool = True


def _keyed_row(table: dict, exalt_type: str, origin: str, upbringing: str, default):
    """Return the row of `table` for the most specific key.

    Keys in order: `"E:o:u"`, `"E:o"`, `"E"`. Return `default` if none exists.
    `budgets_for` and `bonus_costs_for` both use this function.
    """
    if origin and upbringing:
        row = table.get(f"{exalt_type}:{origin}:{upbringing}")
        if row is not None:
            return row
    if origin:
        row = table.get(f"{exalt_type}:{origin}")
        if row is not None:
            return row
    return table.get(exalt_type, default)


# The Solar definition (core-p.104). The default if exalts.json is not loaded, and
# the fallback for an unknown exalt_type.
SOLAR_EXALT = ExaltDefinition(
    id="Solar",
    label="Solar Exalted",
    essence=EssencePoolSpec(personal_essence_coeff=3, peripheral_essence_coeff=7,
                            peripheral_virtue_mode="all"),
    magic_track="sorcery",
    highest_magic_circle_id="Solar",
    ox_body_charm_id="solar.endurance.ox-body-technique",
)
