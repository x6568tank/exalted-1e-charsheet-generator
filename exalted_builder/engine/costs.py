"""
engine/costs.py — experience-point cost of a single post-lock advance (pure).

Each number comes from RuleSet.xp_costs (ExperienceCosts). A scaled trait costs
`current rating × N`, on the rating that the character leaves, thus each function
takes `from_rating`. New Charms, spells and specialties are flat. A new Combo costs
the sum of the minimum Ability values of its Charms (core p.213).

Pure `(RuleSet, …) -> int` functions. engine.advancement calls them, and the UI shows
them as a price.
"""

from __future__ import annotations

from typing import Optional

from ..models.character import Character, MeritFlawPurchase
from ..models.rules import AbilityName, AttributeName, Charm, RuleSet, VirtueName
from . import merits, paths, validate

# The first dot of an Ability (from 0) costs the flat new_ability. Attributes and
# Virtues never start below 1.


def attribute_step(ruleset: RuleSet, character: Character, from_rating: int,
                   attr: AttributeName | None = None) -> int:
    """Return the XP to raise an Attribute one dot. Two discounts, in this order (a
    caste_favored splat also has `caste_attributes`):

    * caste_favored mode (Alchemical, p.64) — a Caste or Favored Attribute takes
      `attribute_favored_caste`.
    * Caste Attributes (Lunar, p.251 — `(x4)-1`) — `attribute_caste_favored`.

    Else the flat rate. Without `attr` the flat rate applies."""
    xp = ruleset.xp_costs_for(character.exalt_type)
    if attr is not None:
        if attr in validate._caste_favored_attr_names(ruleset, character):
            return xp.attribute_favored_caste.at(from_rating)
        if attr in validate.caste_attributes(ruleset, character):
            return xp.attribute_caste_favored.at(from_rating)
    return xp.attribute.at(from_rating)


def ability_step(ruleset: RuleSet, character: Character, ability: AbilityName,
                 from_rating: int) -> int:
    """Return the XP to raise an Ability one dot. 0 -> 1 is the flat new-ability
    cost. Above that it scales, with the Caste/Favoured discount if applicable."""
    xp = ruleset.xp_costs_for(character.exalt_type)
    if ability == AbilityName.CRAFT and xp.craft is not None:
        # Superior Craftsmanship (Mountain Folk, CH6 p.237): half the XP, rounded up.
        # It replaces the Favored discount. The first dot is half of 3: 2.
        if from_rating <= 0:
            return max(1, (xp.new_ability + 1) // 2)
        total = xp.craft.at(from_rating)
    elif from_rating <= 0:
        return xp.new_ability
    else:
        favored = ability in validate.caste_favored_abilities(ruleset, character)
        cost = xp.ability_favored_caste if favored else xp.ability
        total = cost.at(from_rating)
    # A Calling Ability costs 1 XP less and stacks with Caste/Favored (p.102): a
    # subtraction after the rate.
    if ability in validate.calling_abilities(ruleset, character):
        total -= xp.calling_ability_discount
    # Prodigy: "(current rating x 2) - 2". A subtraction after the rate, read from a
    # MeritEffects field.
    total -= merits.merits_and_flaws_calc(ruleset, character).ability_xp_discount.get(
        ability.value, 0)
    return max(0, total)


def virtue_step(ruleset: RuleSet, character: Character, from_rating: int,
                virtue: Optional[VirtueName] = None) -> int:
    """Return the XP to raise a Virtue one dot. It does not raise Willpower
    (derive.willpower).

    An ATTUNED Virtue (PG p.74; `MeritEffects.favored_virtues`) costs
    (current rating x 2), not the splat (current x 3)."""
    if (virtue is not None
            and virtue.value in merits.merits_and_flaws_calc(
                ruleset, character).favored_virtues):
        return from_rating * 2
    return ruleset.xp_costs_for(character.exalt_type).virtue.at(from_rating)


def willpower_step(ruleset: RuleSet, character: Character, from_rating: int) -> int:
    """Return the XP to raise permanent Willpower one dot."""
    return ruleset.xp_costs_for(character.exalt_type).willpower.at(from_rating)


def essence_step(ruleset: RuleSet, character: Character, from_rating: int) -> int:
    """Return the XP to raise Essence one dot. A step in
    `ExperienceCosts.essence_by_rating` (PG p.115) wins over the scaled rate."""
    xp = ruleset.xp_costs_for(character.exalt_type)
    flat = xp.essence_by_rating.get(from_rating + 1)
    return flat if flat is not None else xp.essence.at(from_rating)


def merit_cost(ruleset: RuleSet, character: Character, merit, tier: str = "",
               *, taken_as: str = "", points: int = 0) -> int:
    """Return the XP to buy a Merit after creation: its bonus-point value x2 (PG
    p.115).

    The value comes from `validate.merit_points`, thus the XP and chargen prices
    agree for each shape: a tier menu, a splat or caste rate, an agreed variable cost
    (`points`), and a two-sided entry (`taken_as`)."""
    bp = validate.merit_points(
        merit, MeritFlawPurchase(merit_id=merit.id, tier=tier, taken_as=taken_as,
                                 points=points),
        character.exalt_type, character.caste)
    return bp * ruleset.xp_costs_for(character.exalt_type).new_merit_bp_multiplier


def elemental_power_xp(ruleset: RuleSet, character: Character, power) -> int:
    """Return the XP to learn an elemental power: its bonus-point value x2 (PG p.68),
    through `new_merit_bp_multiplier`. ⚠ Not the God-Blooded new-Charm rate: 14, not
    15."""
    return power.bp_cost * ruleset.xp_costs_for(character.exalt_type).new_merit_bp_multiplier


def specialty_cost(ruleset: RuleSet, character: Character,
                   ability: AbilityName | None = None) -> int:
    """Return the XP for one new specialty. A Mountain Folk Craft specialty costs 2
    (CH6 p.233, p.237). `ability` None gives the ordinary rate."""
    xp = ruleset.xp_costs_for(character.exalt_type)
    if ability == AbilityName.CRAFT and xp.craft_specialty:
        return xp.craft_specialty
    return xp.new_specialty


def college_new_cost(ruleset: RuleSet, character: Character) -> int:
    """Return the XP for a new Astrological College (Sidereal, p.265)."""
    return ruleset.xp_costs_for(character.exalt_type).new_college


def college_step(ruleset: RuleSet, character: Character, from_rating: int) -> int:
    """Return the XP to raise a College one dot (p.265: ×3)."""
    return ruleset.xp_costs_for(character.exalt_type).college.at(from_rating)


def path_new_cost(ruleset: RuleSet, character: Character, path_id: str) -> int:
    """Return the XP for a new Dragon-King Path at rating 1 (PG p.176): new_path, or
    new_path_breed for a Breed or Favoured Path."""
    xp = ruleset.xp_costs_for(character.exalt_type)
    return xp.new_path_breed if paths.path_is_favored(ruleset, character, path_id) \
        else xp.new_path


def path_step(ruleset: RuleSet, character: Character, path_id: str,
              from_rating: int) -> int:
    """Return the XP to raise a Path one dot (p.176: ×5, or ×4 for a Breed/Favoured
    Path)."""
    xp = ruleset.xp_costs_for(character.exalt_type)
    rate = xp.path_breed if paths.path_is_favored(ruleset, character, path_id) \
        else xp.path
    return rate.at(from_rating)


def _fighter_in_life_covers(ruleset: RuleSet, character: Character,
                            charm: Charm) -> bool:
    """Return True if this Terrestrial Martial Arts Charm is inside the Fighter in
    Life allowance (PG p.234).

    The Merit gives a COUNT. It covers the first N such Charms. A Charm held already
    counts. The count is a `MeritEffects` field (decision 0011). Charms are counted
    through `validate.charm_picks`.
    """
    picks = merits.merits_and_flaws_calc(ruleset, character).terrestrial_ma_picks
    if not picks:
        return False
    held = sum(1 for pick in validate.charm_picks(ruleset, character)
               if (c := ruleset.charms.get(pick.charm_id)) is not None
               and validate.is_terrestrial_martial_arts(c)
               and pick.charm_id != charm.id)
    return held < picks


def charm_cost(ruleset: RuleSet, character: Character, charm: Charm) -> int:
    """Return the XP to learn a Charm. The Caste/Favoured discount uses the gating
    Ability, or for an Attribute-keyed Charm (Lunar, p.122) the category of
    `min_attribute` (⚠ 'melee' is also an AbilityName; see
    `validate._min_trait_rating`).

    A Charm of a different splat (p.127) costs double. The discount applies FIRST,
    the multiplier last (human's ruling)."""
    xp = ruleset.xp_costs_for(character.exalt_type)
    if charm.min_attribute:
        caste_attr_category = validate._caste_favored_attribute_category(ruleset, character)
        favored = validate._charm_attribute_caste_favored(charm, caste_attr_category)
    else:
        ability = validate._category_ability(charm.category)
        favored = ability is not None and ability in validate.caste_favored_abilities(ruleset, character)
    # PG p.234 (ghosts): this branch comes first, before the Immaculate rate (p.292).
    # ⚠ The ORDER is the rule: reversed, a ghost pays a DB rate.
    if (ruleset.exalt_for(character.exalt_type).terrestrial_martial_arts
            and validate.is_terrestrial_martial_arts(charm)):
        if _fighter_in_life_covers(ruleset, character, charm):
            # The cost of a regular Arcanos.
            cost = xp.new_charm_favored_caste if favored else xp.new_charm
        else:
            # The cost of a new Arcanos: the penalty rate.
            cost = (xp.new_martial_arts_charm
                    if xp.new_martial_arts_charm is not None else xp.new_charm)
    # Immaculate Order Charms (Dragon-Blooded) have their own, higher rate (p.292).
    elif validate.is_immaculate_charm(charm):
        cost = xp.new_immaculate_charm_favored_caste if favored else xp.new_immaculate_charm
    elif charm.category.startswith("martial_arts"):
        # Sidereal Martial Arts (p.265). None on other splats: the new_charm rate.
        # Ghosts: the p.234 penalty rate.
        if favored:
            cost = xp.new_martial_arts_charm_favored_caste
            if cost is None:
                cost = xp.new_charm_favored_caste
        else:
            cost = xp.new_martial_arts_charm if xp.new_martial_arts_charm is not None else xp.new_charm
    elif charm.grants_circle is not None and xp.new_magic_charm:
        # God-Blooded p.49: initiation Charms. Flat. 0 = the ordinary rate.
        cost = xp.new_magic_charm
    elif xp.new_charm_cross_pattern and validate.mountain_folk_cross_pattern(
            ruleset, character, charm):
        # CH6 p.233: a Charm of another caste's Pattern. No Favoured discount applies.
        cost = xp.new_charm_cross_pattern
    else:
        cost = xp.new_charm_favored_caste if favored else xp.new_charm
    # A Calling Charm costs 2 XP less, and stacks with Caste/Favoured (p.102). Before
    # the foreign multiplier.
    if validate.is_calling_charm(ruleset, character, charm):
        cost = max(0, cost - xp.calling_charm_discount)
    # Eclipse/Moonshadow: a Charm of another splat costs a multiple (p.90).
    caste = validate.foreign_charms_caste(ruleset, character)
    if caste is not None and validate.is_foreign_charm(ruleset, character, charm):
        cost *= caste.foreign_charm_xp_multiplier
    # A Merit reprice (Brigid's Heir). LAST.
    return merits.adjust_charm_cost(ruleset, character, charm, cost)


def spell_cost(ruleset: RuleSet, character: Character, spell=None) -> int:
    """Return the XP to learn a spell. Three policies, by the splat data:

    - **Flat per-circle** (Alchemical, p.64): `spell_cost_by_circle`. No Occult
      discount.
    - **Discounted per-circle** (Lunar, p.251): `new_spell_by_circle`, less the caste
      discount (`CasteDefinition.spell_cost_discount`). No Occult discount.
    - **Flat** (Solar/DB/Abyssal, core p.100/191): `new_spell`, or
      `new_spell_occult_favored_caste` if Occult is Caste/Favoured.

    Without `spell` the flat price applies: the per-circle policies need the circle."""
    xp = ruleset.xp_costs_for(character.exalt_type)

    def _adjust(cost: int) -> int:
        # A Merit reprice (Brigid's Heir). Each policy goes through here.
        return merits.adjust_spell_cost(ruleset, character, cost)

    if spell is not None:
        by_circle = xp.spell_cost_by_circle.get(spell.circle.value)
        if by_circle is not None:
            return _adjust(by_circle)
        if spell.circle in xp.new_spell_by_circle:
            base = xp.new_spell_by_circle[spell.circle]
            caste_def = ruleset.castes.get(character.caste)
            discount = caste_def.spell_cost_discount if caste_def else 0
            return _adjust(base - discount)
    favored = AbilityName.OCCULT in validate.caste_favored_abilities(ruleset, character)
    return _adjust(xp.new_spell_occult_favored_caste if favored else xp.new_spell)


def charm_slot_cost(ruleset: RuleSet, character: Character, *, dedicated: bool) -> int:
    """Return the XP for one more Alchemical Charm Slot (p.64). The Slot includes one
    free Charm."""
    xp = ruleset.xp_costs_for(character.exalt_type)
    return xp.new_charm_slot_dedicated if dedicated else xp.new_charm_slot_general


def charm_slot_upgrade_cost(ruleset: RuleSet, character: Character) -> int:
    """Return the XP to upgrade one Dedicated Slot to General (p.64)."""
    return ruleset.xp_costs_for(character.exalt_type).charm_slot_upgrade


def retainer_charm_cost(ruleset: RuleSet, character: Character) -> int:
    """Return the XP for one Panoply Charm with no Slot: the table rate (p.64), or the
    crossover caste rate (p.90). No Caste/Favored discount."""
    if validate.uses_charm_slots(ruleset, character):
        return ruleset.xp_costs_for(character.exalt_type).new_charm
    crossover = validate.crossover_panoply_xp(ruleset, character)
    if crossover is not None:
        return crossover
    return ruleset.xp_costs_for(character.exalt_type).new_charm


def martial_arts_charm_cost(ruleset: RuleSet, character: Character) -> int:
    """Return the XP for one Martial Arts Charm through Perfected Lotus Matrix (p.100).
    It uses no Slot."""
    xp = ruleset.xp_costs_for(character.exalt_type)
    return xp.new_martial_arts_charm if xp.new_martial_arts_charm is not None else xp.new_charm


def ox_body_cost(ruleset: RuleSet, character: Character) -> int:
    """Return the XP for one more Ox-Body purchase: a new Charm. 0 if absent."""
    charm = validate.ox_body_charm(ruleset, character)
    return charm_cost(ruleset, character, charm) if charm else 0


def gift_cost(ruleset: RuleSet, character: Character) -> int:
    """Return the XP for one more purchase of the Gift Charm: a new Charm, for any
    number of Gifts (p.124). 0 if absent."""
    charm = validate.gift_charm(ruleset, character)
    return charm_cost(ruleset, character, charm) if charm else 0


def variant_purchase_cost(ruleset: RuleSet, character: Character, charm) -> int:
    """Return the XP for one more purchase of a variant-menu Charm: a new Charm. 0 if
    absent."""
    return charm_cost(ruleset, character, charm) if charm else 0


def combo_cost(ruleset: RuleSet, charm_ids: list[str]) -> int:
    """Return the XP for a new Combo: the sum of the minimum Ability values of its
    Charms (core p.213). An unknown id adds 0."""
    return sum(ruleset.charms[cid].min_ability for cid in charm_ids if cid in ruleset.charms)


def array_cost(ruleset: RuleSet, charm_ids: list[str]) -> int:
    """Return the XP for a new Alchemical Array: the sum of the minimum Attribute
    ratings of its Charms (p.89). `Charm.min_ability` holds the rating for both
    keyings. A separate rule, thus a separate function."""
    return combo_cost(ruleset, charm_ids)


# --------------------------------------------------------------------------- #
# Thaumaturgy (Player's Guide CH3)
#
# One ladder, two currencies. ⚠ The BP and XP tables (p.116 / p.115) differ on Art
# Specialty (2 BP vs 3 XP) and Ritual base (2 vs 3). Do not merge the rows.
#
# `multiplier` is ExaltDefinition.thaumaturgy_cost_multiplier (spirits: 2, p.114).
# --------------------------------------------------------------------------- #

def _thaum_multiplier(ruleset: RuleSet, character: Character) -> int:
    return ruleset.exalt_for(character.exalt_type).thaumaturgy_cost_multiplier


def thaum_art_bp(ruleset: RuleSet, character: Character) -> int:
    """Return the BP for an Art (+2 dice, p.126)."""
    costs = ruleset.bonus_costs_for(character.exalt_type, character.origin,
                                    character.upbringing)
    return costs.thaum_art * _thaum_multiplier(ruleset, character)


def thaum_art_xp(ruleset: RuleSet, character: Character) -> int:
    return (ruleset.xp_costs_for(character.exalt_type).thaum_new_art
            * _thaum_multiplier(ruleset, character))


def thaum_specialty_bp(ruleset: RuleSet, character: Character, *,
                       narrowed: bool = False) -> int:
    """Return the BP for one Art specialty, or one printed aspect (see
    models.rules.ThaumaturgicAspect).

    `narrowed` (Summoning only, p.127) halves the cost, rounded UP: 2 becomes 1.
    """
    costs = ruleset.bonus_costs_for(character.exalt_type, character.origin,
                                    character.upbringing)
    base = costs.thaum_art_specialty
    if narrowed:
        base = -(-base // 2)
    return base * _thaum_multiplier(ruleset, character)


def thaum_specialty_xp(ruleset: RuleSet, character: Character, *,
                       narrowed: bool = False) -> int:
    base = ruleset.xp_costs_for(character.exalt_type).thaum_new_art_specialty
    if narrowed:
        base = -(-base // 2)
    return base * _thaum_multiplier(ruleset, character)


def thaum_ritual_bp(ruleset: RuleSet, character: Character, level: int,
                    orientations: int = 1) -> int:
    """Return the BP for a ritual: 2 + level (p.116), plus 1 for each extra regional
    version (p.124)."""
    costs = ruleset.bonus_costs_for(character.exalt_type, character.origin,
                                    character.upbringing)
    base = costs.thaum_ritual_base + costs.thaum_ritual_per_level * level
    extra = costs.thaum_extra_orientation * max(0, orientations - 1)
    return (base + extra) * _thaum_multiplier(ruleset, character)


def thaum_ritual_xp(ruleset: RuleSet, character: Character, level: int,
                    orientations: int = 1) -> int:
    """Return the XP for a ritual: 3 + level (p.115)."""
    costs = ruleset.xp_costs_for(character.exalt_type)
    base = costs.thaum_ritual_base + costs.thaum_ritual_per_level * level
    extra = costs.thaum_extra_orientation * max(0, orientations - 1)
    return (base + extra) * _thaum_multiplier(ruleset, character)


def thaum_formula_bp(ruleset: RuleSet, character: Character,
                     orientations: int = 1) -> int:
    """Return the BP for a formula: 1, plus 1 for each extra regional version."""
    costs = ruleset.bonus_costs_for(character.exalt_type, character.origin,
                                    character.upbringing)
    total = costs.thaum_formula + costs.thaum_extra_orientation * max(0, orientations - 1)
    return total * _thaum_multiplier(ruleset, character)


def thaum_formula_xp(ruleset: RuleSet, character: Character,
                     orientations: int = 1) -> int:
    costs = ruleset.xp_costs_for(character.exalt_type)
    total = costs.thaum_formula + costs.thaum_extra_orientation * max(0, orientations - 1)
    return total * _thaum_multiplier(ruleset, character)


def thaum_orientation_bp(ruleset: RuleSet, character: Character) -> int:
    """Return the BP for ONE more regional version of a known ritual or formula
    (p.124).

    ⚠ A separate purchase: each XP log row means "learned it" or "learned another
    version", never both.
    """
    costs = ruleset.bonus_costs_for(character.exalt_type, character.origin,
                                    character.upbringing)
    return costs.thaum_extra_orientation * _thaum_multiplier(ruleset, character)


def thaum_orientation_xp(ruleset: RuleSet, character: Character) -> int:
    return (ruleset.xp_costs_for(character.exalt_type).thaum_extra_orientation
            * _thaum_multiplier(ruleset, character))


def thaum_science_step_bp(ruleset: RuleSet, character: Character, from_rating: int) -> int:
    """BP to raise a Science by ONE dot from `from_rating`: 5 for the first, 7 after.

    ⚠ Human's ruling: no page gives these costs. See
    models.rules.BonusPointCosts.thaum_science_first_dot.
    """
    costs = ruleset.bonus_costs_for(character.exalt_type, character.origin,
                                    character.upbringing)
    rate = (costs.thaum_science_first_dot if from_rating <= 0
            else costs.thaum_science_additional_dot)
    return rate * _thaum_multiplier(ruleset, character)


def thaum_science_bp(ruleset: RuleSet, character: Character, rating: int) -> int:
    """Return the total BP for a Science at `rating` from 0: the chargen figure."""
    return sum(thaum_science_step_bp(ruleset, character, r) for r in range(max(0, rating)))


def thaum_science_step_xp(ruleset: RuleSet, character: Character, from_rating: int) -> int:
    """Return the XP to raise a Science one dot: 7 for the first, then current × 6
    (human's ruling, as `thaum_science_step_bp`)."""
    costs = ruleset.xp_costs_for(character.exalt_type)
    step = (costs.thaum_new_science if from_rating <= 0
            else costs.thaum_science.at(from_rating))
    return step * _thaum_multiplier(ruleset, character)


def fetter_step(ruleset: RuleSet, character: Character, from_rating: int) -> int:
    """Return the XP to raise one Fetter a dot (E:Ab p.283: current x 3)."""
    return ruleset.xp_costs_for(character.exalt_type).fetter.at(from_rating)


def new_fetter_cost(ruleset: RuleSet, character: Character) -> int:
    """Return the XP for a new Fetter: 20, or 15 for a character who knows the Arcanos
    in `ExperienceCosts.new_fetter_discount_charm_id` (p.283). The Charm is data.
    Asked through `validate.charm_picks`.
    """
    xp = ruleset.xp_costs_for(character.exalt_type)
    cid = xp.new_fetter_discount_charm_id
    if cid and xp.new_fetter_discounted:
        if any(pick.charm_id == cid for pick in validate.charm_picks(ruleset, character)):
            return xp.new_fetter_discounted
    return xp.new_fetter
