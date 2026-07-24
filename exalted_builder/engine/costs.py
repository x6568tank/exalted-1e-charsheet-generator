"""
engine/costs.py — experience-point cost of a single post-lock advance (pure).

Every number comes from RuleSet.xp_costs (ExperienceCosts), never hardcoded, so
correcting the table corrects the engine. The scaled traits cost
`current rating × N` — you pay on the rating you are *leaving* (the 1e advancement
table; see CLAUDE.md), so each function takes `from_rating`. New Charms, spells and
specialties are flat; a new Combo costs the sum of its member Charms' minimum
Ability values (core p.213).

These are pure `(RuleSet, …) -> int` functions: the advancement transitions in
engine.advancement call them, and the UI shows them as a price before buying.
"""

from __future__ import annotations

from ..models.character import Character
from ..models.rules import AbilityName, AttributeName, Charm, RuleSet
from . import validate

# A trait's first dot (an Ability bought from 0) has no `from_rating` to scale; it
# is the flat new_ability cost. Attributes/Virtues never start below 1, so they are
# always scaled.


def attribute_step(ruleset: RuleSet, character: Character, from_rating: int,
                   attr: AttributeName | None = None) -> int:
    """XP to raise an Attribute one dot. Two independent discount axes, checked in
    order because a caste_favored-mode splat also has `caste_attributes` populated:

    * caste_favored mode (Alchemical, p.64) — a Caste- or Favored-Attribute takes the
      `attribute_favored_caste` rate, matching a SPECIFIC Attribute.
    * Caste Attributes (Lunar, p.251 — `(x4)-1`) — the `attribute_caste_favored` rate.

    Every other splat (and every non-favored Attribute) pays the flat rate. `attr` is
    optional so call sites that don't pass it keep the flat rate — correct for them,
    since only these two splats override the Attribute rate at all."""
    xp = ruleset.xp_costs_for(character.exalt_type)
    if attr is not None:
        if attr in validate._caste_favored_attr_names(ruleset, character):
            return xp.attribute_favored_caste.at(from_rating)
        if attr in validate.caste_attributes(ruleset, character):
            return xp.attribute_caste_favored.at(from_rating)
    return xp.attribute.at(from_rating)


def ability_step(ruleset: RuleSet, character: Character, ability: AbilityName,
                 from_rating: int) -> int:
    """XP to raise an Ability one dot. Going 0 -> 1 is the flat 'new ability' cost;
    above that it scales, with the Caste/Favoured discount when applicable."""
    xp = ruleset.xp_costs_for(character.exalt_type)
    if from_rating <= 0:
        return xp.new_ability
    favored = ability in validate.caste_favored_abilities(ruleset, character)
    cost = xp.ability_favored_caste if favored else xp.ability
    return cost.at(from_rating)


def virtue_step(ruleset: RuleSet, character: Character, from_rating: int) -> int:
    """XP to raise a Virtue one dot. (Does not raise Willpower — that is pinned at
    lock; see derive.willpower.)"""
    return ruleset.xp_costs_for(character.exalt_type).virtue.at(from_rating)


def willpower_step(ruleset: RuleSet, character: Character, from_rating: int) -> int:
    """XP to raise permanent Willpower one dot, scaled on the current rating."""
    return ruleset.xp_costs_for(character.exalt_type).willpower.at(from_rating)


def essence_step(ruleset: RuleSet, character: Character, from_rating: int) -> int:
    """XP to raise Essence one dot, scaled on the current rating."""
    return ruleset.xp_costs_for(character.exalt_type).essence.at(from_rating)


def specialty_cost(ruleset: RuleSet, character: Character) -> int:
    """XP for one new specialty dot (flat)."""
    return ruleset.xp_costs_for(character.exalt_type).new_specialty


def college_new_cost(ruleset: RuleSet, character: Character) -> int:
    """XP for a new Astrological College (Sidereal, p.265): flat new_college (5)."""
    return ruleset.xp_costs_for(character.exalt_type).new_college


def college_step(ruleset: RuleSet, character: Character, from_rating: int) -> int:
    """XP to raise a College one dot, scaled on the current rating (p.265: ×3)."""
    return ruleset.xp_costs_for(character.exalt_type).college.at(from_rating)


def charm_cost(ruleset: RuleSet, character: Character, charm: Charm) -> int:
    """XP to learn a Charm: discounted when its gating Ability is Caste/Favoured
    (Ability-keyed Charms), or when its gating Attribute's category matches the
    caste's favored Attribute category (Lunar's Attribute-keyed Charms, p.122 —
    the same collision `validate._min_trait_rating` warns about: 'melee' is both
    a category string and a valid AbilityName, so a Lunar Melee Charm's discount
    must come from `min_attribute`, never from category-as-Ability).

    A Charm belonging to ANOTHER splat — reachable only through the Eclipse-style
    caste privilege (p.127) — then costs double ("usually 20 points"). The Caste/
    Favoured discount is applied FIRST and the multiplier last, per the rules
    authority's call: a foreign Charm gets full C/F treatment, then doubles."""
    xp = ruleset.xp_costs_for(character.exalt_type)
    if charm.min_attribute:
        caste_attr_category = validate._caste_favored_attribute_category(ruleset, character)
        favored = validate._charm_attribute_caste_favored(charm, caste_attr_category)
    else:
        ability = validate._category_ability(charm.category)
        favored = ability is not None and ability in validate.caste_favored_abilities(ruleset, character)
    # Immaculate Order Charms (Dragon-Blooded) have their own, higher rate (p.292).
    if validate.is_immaculate_charm(charm):
        cost = xp.new_immaculate_charm_favored_caste if favored else xp.new_immaculate_charm
    elif charm.category.startswith("martial_arts"):
        # Sidereal Martial Arts is a distinct rate (12/10, p.265); other splats leave
        # both MA fields None and fall back to the ordinary new_charm rate.
        if favored:
            cost = xp.new_martial_arts_charm_favored_caste
            if cost is None:
                cost = xp.new_charm_favored_caste
        else:
            cost = xp.new_martial_arts_charm if xp.new_martial_arts_charm is not None else xp.new_charm
    else:
        cost = xp.new_charm_favored_caste if favored else xp.new_charm
    # An Eclipse/Moonshadow learning another splat's Charm pays a multiple (p.90).
    caste = validate.foreign_charms_caste(ruleset, character)
    if caste is not None and validate.is_foreign_charm(ruleset, character, charm):
        cost *= caste.foreign_charm_xp_multiplier
    return cost


def spell_cost(ruleset: RuleSet, character: Character, spell=None) -> int:
    """XP to learn a spell. Three pricing policies, chosen by the splat's data:

    - **Flat per-circle** (Alchemical, p.64): a circle listed in `spell_cost_by_circle`
      prices at that rate — Man-Machine 12, God-Machine 14 — with no Occult discount.
    - **Discounted per-circle** (Lunar, p.251): when the splat's `new_spell_by_circle`
      maps the spell's circle, that base applies, reduced by the learner's *caste*
      discount (`CasteDefinition.spell_cost_discount` — a No Moon's −2). The
      Occult-Caste/Favoured discount does NOT apply to such a splat.
    - **Flat** (Solar/DB/Abyssal, core p.100/191): the flat `new_spell`, discounted to
      `new_spell_occult_favored_caste` when Occult is Caste/Favoured.

    `spell` is optional only so a caller with no spell in hand still gets the flat
    price; both per-circle policies need the spell to read its circle."""
    xp = ruleset.xp_costs_for(character.exalt_type)
    if spell is not None:
        by_circle = xp.spell_cost_by_circle.get(spell.circle.value)
        if by_circle is not None:
            return by_circle
        if spell.circle in xp.new_spell_by_circle:
            base = xp.new_spell_by_circle[spell.circle]
            caste_def = ruleset.castes.get(character.caste)
            discount = caste_def.spell_cost_discount if caste_def else 0
            return base - discount
    favored = AbilityName.OCCULT in validate.caste_favored_abilities(ruleset, character)
    return xp.new_spell_occult_favored_caste if favored else xp.new_spell


def charm_slot_cost(ruleset: RuleSet, character: Character, *, dedicated: bool) -> int:
    """XP to buy one more Alchemical Charm Slot (p.64) — Dedicated is cheaper (10)
    than General (12). The Slot comes with one free Charm; you pay only for the Slot."""
    xp = ruleset.xp_costs_for(character.exalt_type)
    return xp.new_charm_slot_dedicated if dedicated else xp.new_charm_slot_general


def charm_slot_upgrade_cost(ruleset: RuleSet, character: Character) -> int:
    """XP to upgrade one Dedicated Charm Slot to a General one (p.64)."""
    return ruleset.xp_costs_for(character.exalt_type).charm_slot_upgrade


def retainer_charm_cost(ruleset: RuleSet, character: Character) -> int:
    """XP for one Panoply (retainer) Charm bought WITHOUT a Slot. A native Alchemical
    pays the flat table rate (p.64, 6); an Eclipse/Moonshadow adding an Alchemical Charm
    to their Panoply through the crossover pays their caste's flat rate (p.90, 8). No
    Caste/Favored discount applies either way."""
    if validate.uses_charm_slots(ruleset, character):
        return ruleset.xp_costs_for(character.exalt_type).new_charm
    crossover = validate.crossover_panoply_xp(ruleset, character)
    if crossover is not None:
        return crossover
    return ruleset.xp_costs_for(character.exalt_type).new_charm


def martial_arts_charm_cost(ruleset: RuleSet, character: Character) -> int:
    """XP for one Martial Arts Charm learned through Perfected Lotus Matrix (p.100,
    flat 11). MA Charms are stored inside the Matrix and use no Charm Slot."""
    xp = ruleset.xp_costs_for(character.exalt_type)
    return xp.new_martial_arts_charm if xp.new_martial_arts_charm is not None else xp.new_charm


def ox_body_cost(ruleset: RuleSet, character: Character) -> int:
    """XP to buy one more Ox-Body Technique: priced as a normal new Charm (the
    variant chosen does not change the cost). 0 if the Charm is absent."""
    charm = validate.ox_body_charm(ruleset, character)
    return charm_cost(ruleset, character, charm) if charm else 0


def gift_cost(ruleset: RuleSet, character: Character) -> int:
    """XP to buy one more purchase of the Gift-granting Charm (Deadly Beastman
    Transformation): priced as a normal new Charm, regardless of how many Gifts
    this purchase grants — they come bundled with the purchase, not priced
    individually (p.124). 0 if the Charm is absent."""
    charm = validate.gift_charm(ruleset, character)
    return charm_cost(ruleset, character, charm) if charm else 0


def combo_cost(ruleset: RuleSet, charm_ids: list[str]) -> int:
    """XP for a new Combo: the sum of its member Charms' minimum Ability values
    (core p.213). Unknown ids contribute nothing (reference checks flag them)."""
    return sum(ruleset.charms[cid].min_ability for cid in charm_ids if cid in ruleset.charms)


def array_cost(ruleset: RuleSet, charm_ids: list[str]) -> int:
    """XP for a new Alchemical Array: the sum of its member Charms' minimum
    Attribute ratings (p.89). Arithmetically identical to `combo_cost` because
    `Charm.min_ability` stores the required *rating* for both keyings — the
    Attribute a Charm gates on is named by `min_attribute`, not rated by it — but
    it is a different rule on a different page, so it gets its own name rather
    than callers reaching for the Combo function."""
    return combo_cost(ruleset, charm_ids)
