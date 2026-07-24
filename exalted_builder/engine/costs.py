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
    """XP to raise an Attribute from `from_rating` to the next dot. Discounted when
    `attr` is one of the character's Caste Attributes (Lunar, p.251 — `(x4)-1`); the
    default cost equals the ordinary rate for every splat without Caste Attributes.
    `attr` is optional so pre-Lunar call sites that didn't pass it keep the flat rate
    (correct for them, since only Lunar has an attribute_caste_favored override)."""
    xp = ruleset.xp_costs_for(character.exalt_type)
    if attr is not None and attr in validate.caste_attributes(ruleset, character):
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
    must come from `min_attribute`, never from category-as-Ability)."""
    xp = ruleset.xp_costs_for(character.exalt_type)
    if charm.min_attribute:
        caste_attr_category = validate._caste_favored_attribute_category(ruleset, character)
        favored = validate._charm_attribute_caste_favored(charm, caste_attr_category)
    else:
        ability = validate._category_ability(charm.category)
        favored = ability is not None and ability in validate.caste_favored_abilities(ruleset, character)
    # Immaculate Order Charms (Dragon-Blooded) have their own, higher rate (p.292).
    if validate.is_immaculate_charm(charm):
        return xp.new_immaculate_charm_favored_caste if favored else xp.new_immaculate_charm
    return xp.new_charm_favored_caste if favored else xp.new_charm


def spell_cost(ruleset: RuleSet, character: Character, spell=None) -> int:
    """XP to learn a spell. Two pricing policies, chosen by the splat's data:

    - **Per-circle** (Lunar, p.251): when the splat's `new_spell_by_circle` maps the
      spell's circle, that base applies, discounted by the learner's *caste* discount
      (`CasteDefinition.spell_cost_discount` — a No Moon's −2). The Occult-Caste/
      Favoured discount does NOT apply to such a splat.
    - **Flat** (Solar/DB/Abyssal, core p.100/191): the flat `new_spell`, discounted to
      `new_spell_occult_favored_caste` when Occult is Caste/Favoured.

    `spell` is optional only so a caller with no spell in hand still gets the flat
    price; per-circle pricing needs the spell to read its circle."""
    xp = ruleset.xp_costs_for(character.exalt_type)
    if xp.new_spell_by_circle and spell is not None and spell.circle in xp.new_spell_by_circle:
        base = xp.new_spell_by_circle[spell.circle]
        caste_def = ruleset.castes.get(character.caste)
        discount = caste_def.spell_cost_discount if caste_def else 0
        return base - discount
    favored = AbilityName.OCCULT in validate.caste_favored_abilities(ruleset, character)
    return xp.new_spell_occult_favored_caste if favored else xp.new_spell


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
