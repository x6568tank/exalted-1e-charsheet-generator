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
from ..models.rules import AbilityName, Charm, RuleSet
from . import validate

# A trait's first dot (an Ability bought from 0) has no `from_rating` to scale; it
# is the flat new_ability cost. Attributes/Virtues never start below 1, so they are
# always scaled.


def attribute_step(ruleset: RuleSet, from_rating: int) -> int:
    """XP to raise an Attribute from `from_rating` to the next dot."""
    return ruleset.xp_costs.attribute.at(from_rating)


def ability_step(ruleset: RuleSet, character: Character, ability: AbilityName,
                 from_rating: int) -> int:
    """XP to raise an Ability one dot. Going 0 -> 1 is the flat 'new ability' cost;
    above that it scales, with the Caste/Favoured discount when applicable."""
    if from_rating <= 0:
        return ruleset.xp_costs.new_ability
    favored = ability in validate.caste_favored_abilities(ruleset, character)
    cost = ruleset.xp_costs.ability_favored_caste if favored else ruleset.xp_costs.ability
    return cost.at(from_rating)


def virtue_step(ruleset: RuleSet, from_rating: int) -> int:
    """XP to raise a Virtue one dot. (Does not raise Willpower — that is pinned at
    lock; see derive.willpower.)"""
    return ruleset.xp_costs.virtue.at(from_rating)


def willpower_step(ruleset: RuleSet, from_rating: int) -> int:
    """XP to raise permanent Willpower one dot, scaled on the current rating."""
    return ruleset.xp_costs.willpower.at(from_rating)


def essence_step(ruleset: RuleSet, from_rating: int) -> int:
    """XP to raise Essence one dot, scaled on the current rating."""
    return ruleset.xp_costs.essence.at(from_rating)


def specialty_cost(ruleset: RuleSet) -> int:
    """XP for one new specialty dot (flat)."""
    return ruleset.xp_costs.new_specialty


def charm_cost(ruleset: RuleSet, character: Character, charm: Charm) -> int:
    """XP to learn a Charm: discounted when its gating Ability is Caste/Favoured."""
    ability = validate._category_ability(charm.category)
    favored = ability is not None and ability in validate.caste_favored_abilities(ruleset, character)
    return ruleset.xp_costs.new_charm_favored_caste if favored else ruleset.xp_costs.new_charm


def spell_cost(ruleset: RuleSet, character: Character) -> int:
    """XP to learn a spell: discounted when Occult is Caste/Favoured (core p.100/191)."""
    favored = AbilityName.OCCULT in validate.caste_favored_abilities(ruleset, character)
    return ruleset.xp_costs.new_spell_occult_favored_caste if favored else ruleset.xp_costs.new_spell


def combo_cost(ruleset: RuleSet, charm_ids: list[str]) -> int:
    """XP for a new Combo: the sum of its member Charms' minimum Ability values
    (core p.213). Unknown ids contribute nothing (reference checks flag them)."""
    return sum(ruleset.charms[cid].min_ability for cid in charm_ids if cid in ruleset.charms)
