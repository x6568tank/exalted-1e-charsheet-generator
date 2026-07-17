"""Craft as separate per-focus Abilities (core p.136).

"Characters who wish to master multiple crafts must take this Ability multiple
times" — so each craft is its own rated Ability, budgeted/capped/discounted like
the separate Ability it is, NOT a specialty. The single AbilityName.CRAFT dot in
`abilities` is unused; the engine reads craft from Character.crafts.
"""

import pytest

from exalted_builder.engine import advancement, costs, lifecycle, validate
from exalted_builder.models.character import Character, CraftRating
from exalted_builder.models.rules import (
    AbilityName, CasteDefinition, Charm, CharmType, RuleSet,
)

A = AbilityName


def _ruleset(craft_is_caste: bool = False) -> RuleSet:
    caste_abilities = (
        [A.CRAFT, A.LORE, A.MEDICINE, A.OCCULT, A.INVESTIGATION] if craft_is_caste
        else [A.MELEE, A.ARCHERY, A.BRAWL, A.MARTIAL_ARTS, A.THROWN]
    )
    castes = {"dawn": CasteDefinition(id="dawn", label="Dawn", caste_abilities=caste_abilities)}
    charms = {
        "c-craft": Charm(id="c-craft", name="Crafty", category="craft",
                         type=CharmType.SIMPLE, min_ability=3, min_essence=1),
    }
    return RuleSet(castes=castes, charms=charms)


# --------------------------------------------------------------------------- #
# Effective rating helpers
# --------------------------------------------------------------------------- #

def test_craft_rating_is_the_highest_instance():
    c = Character(id="c")
    c.crafts = [CraftRating(focus="Smithing", rating=2), CraftRating(focus="Genesis", rating=4)]
    assert validate.craft_rating(c) == 4
    assert validate.ability_rating(c, A.CRAFT) == 4
    assert validate.ability_rating(c, A.MELEE) == 0


def test_no_crafts_is_zero():
    assert validate.craft_rating(Character(id="c")) == 0


# --------------------------------------------------------------------------- #
# Charm minimum-ability gate uses the best craft
# --------------------------------------------------------------------------- #

def test_craft_charm_needs_a_craft_at_its_minimum():
    rs = _ruleset()
    charm = rs.charms["c-craft"]            # needs Craft 3
    c = Character(id="c")
    c.crafts = [CraftRating(focus="Smithing", rating=2)]
    assert not validate.meets_charm_requirements(rs, c, charm)
    c.crafts.append(CraftRating(focus="Genesis", rating=3))
    assert validate.meets_charm_requirements(rs, c, charm)


# --------------------------------------------------------------------------- #
# Chargen accounting: craft dots are Ability dots
# --------------------------------------------------------------------------- #

def _base_solar(rs: RuleSet) -> Character:
    """A Dawn Solar with all non-craft chargen requirements satisfied and exactly
    25 free Ability dots used, BEFORE any craft. Favoured = five non-caste."""
    c = Character(id="c", caste="dawn")
    c.favored_abilities = [A.AWARENESS, A.DODGE, A.ATHLETICS, A.RESISTANCE, A.ENDURANCE]
    from exalted_builder.models.rules import AttributeName as AT, VirtueName as V
    c.attributes.update({AT.STRENGTH: 5, AT.DEXTERITY: 4, AT.STAMINA: 2,
                         AT.CHARISMA: 4, AT.MANIPULATION: 3, AT.APPEARANCE: 2,
                         AT.PERCEPTION: 3, AT.INTELLIGENCE: 2, AT.WITS: 2})
    c.abilities.update({A.MELEE: 3, A.ARCHERY: 3, A.BRAWL: 1, A.MARTIAL_ARTS: 1, A.THROWN: 1,
                        A.AWARENESS: 3, A.DODGE: 3, A.ATHLETICS: 1, A.RESISTANCE: 1, A.ENDURANCE: 1,
                        A.LORE: 3, A.OCCULT: 2, A.SURVIVAL: 2})
    c.virtues.update({V.COMPASSION: 3, V.CONVICTION: 3, V.TEMPERANCE: 2, V.VALOR: 1})
    c.essence_rating = 2
    return c


def test_craft_dot_costs_bonus_points_when_over_the_25():
    rs = _ruleset()                        # craft is NOT caste/favoured here
    c = _base_solar(rs)                    # already spends all 25 free Ability dots
    bd0 = validate.bonus_point_breakdown(rs, c)
    assert bd0.lines and dict((l.domain, l.points) for l in bd0.lines)["Abilities"] == 0

    c.crafts = [CraftRating(focus="Smithing", rating=2)]   # 2 Ability dots over the 25
    bd = validate.bonus_point_breakdown(rs, c)
    # The free pool absorbs the dearest dots, so the 2-dot overflow bills at the
    # cheapest (Caste/Favoured) rate of 1 BP each — the player-favourable accounting.
    assert dict((l.domain, l.points) for l in bd.lines)["Abilities"] == 2


def test_craft_dots_count_toward_caste_favoured_minimum():
    rs = _ruleset(craft_is_caste=True)     # Craft is a Caste ability
    c = Character(id="c", caste="dawn")
    c.favored_abilities = [A.MELEE, A.ARCHERY, A.BRAWL, A.THROWN, A.DODGE]
    # Only 4 caste/favoured ability dots in the dict; the craft adds the rest.
    from exalted_builder.models.rules import VirtueName as V
    c.abilities.update({A.MELEE: 1, A.ARCHERY: 1, A.BRAWL: 1, A.THROWN: 1})
    c.crafts = [CraftRating(focus="Smithing", rating=3), CraftRating(focus="Genesis", rating=3)]
    # 4 + 6 craft = 10 caste/favoured dots -> the minimum is met (no such error).
    codes = {i.code for i in validate.validate_chargen(rs, c) if i.severity == "error"}
    assert "ability-caste-favored-min" not in codes


# --------------------------------------------------------------------------- #
# Post-lock advancement
# --------------------------------------------------------------------------- #

def _locked() -> tuple[RuleSet, Character]:
    rs = _ruleset(craft_is_caste=True)
    c = Character(id="c", caste="dawn")
    lifecycle.lock_chargen(c)
    c.xp_earned = 100
    return rs, c


def test_learn_then_raise_a_craft():
    rs, c = _locked()
    e1 = advancement.learn_craft(rs, c, "Smithing")
    assert e1.cost == costs.ability_step(rs, c, A.CRAFT, 0)      # new-ability flat cost
    assert [(x.focus, x.rating) for x in c.crafts] == [("Smithing", 1)]
    e2 = advancement.raise_craft(rs, c, "Smithing")
    assert e2.cost == costs.ability_step(rs, c, A.CRAFT, 1)
    assert c.crafts[0].rating == 2


def test_duplicate_focus_is_rejected():
    rs, c = _locked()
    advancement.learn_craft(rs, c, "Smithing")
    with pytest.raises(advancement.AdvancementError):
        advancement.learn_craft(rs, c, "smithing")              # case-insensitive clash


def test_undo_reverts_then_removes():
    rs, c = _locked()
    advancement.learn_craft(rs, c, "Smithing")
    advancement.raise_craft(rs, c, "Smithing")
    advancement.undo_last(rs, c)            # undo the raise
    assert c.crafts[0].rating == 1
    advancement.undo_last(rs, c)            # undo the learn -> instance gone
    assert c.crafts == []
    assert c.xp_log == []


def test_xp_audit_is_clean_for_craft_purchases():
    rs, c = _locked()
    advancement.learn_craft(rs, c, "Smithing")
    advancement.raise_craft(rs, c, "Smithing")
    codes = {i.code for i in advancement.validate_xp(rs, c)}
    assert "xp-cost-mismatch" not in codes and "xp-overspent" not in codes
