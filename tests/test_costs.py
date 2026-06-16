"""Tests for engine.costs — the XP price of a single advance. Values come from the
default ExperienceCosts table (current rating x N for scaled traits)."""

from exalted_builder.engine import costs
from exalted_builder.models.character import Character
from exalted_builder.models.rules import (
    AbilityName,
    Caste,
    CasteDefinition,
    Charm,
    CharmType,
    RuleSet,
    SpellCircle,
)

A = AbilityName


def _ruleset() -> RuleSet:
    castes = {Caste.DAWN: CasteDefinition(
        caste=Caste.DAWN,
        caste_abilities=[A.ARCHERY, A.BRAWL, A.MARTIAL_ARTS, A.MELEE, A.THROWN])}
    charms = {
        "melee-charm": Charm(id="melee-charm", name="Melee Charm", category="melee",
                             type=CharmType.SIMPLE, min_ability=3, min_essence=2),
        "occult-charm": Charm(id="occult-charm", name="Occult Charm", category="occult",
                              type=CharmType.SIMPLE, min_ability=2, min_essence=1),
        "ox-body": Charm(id="ox-body", name="Ox-Body", category="endurance",
                         type=CharmType.SPECIAL, min_ability=1, min_essence=1),
        "sorcery": Charm(id="sorcery", name="Terrestrial Circle Sorcery", category="occult",
                         type=CharmType.SIMPLE, min_ability=1, min_essence=1,
                         grants_sorcery_circle=SpellCircle.TERRESTRIAL),
    }
    return RuleSet(castes=castes, charms=charms)


def _char() -> Character:
    c = Character(id="char.cost", caste=Caste.DAWN)
    c.favored_abilities = [A.OCCULT, A.DODGE, A.ATHLETICS, A.RESISTANCE, A.ENDURANCE]
    return c


def test_attribute_scales_on_current_rating():
    assert costs.attribute_step(_ruleset(), _char(), 3) == 12      # 3 x 4


def test_ability_uses_caste_favored_discount():
    rs, c = _ruleset(), _char()
    assert costs.ability_step(rs, c, A.LORE, 2) == 4       # non-caste/favoured: 2 x 2
    assert costs.ability_step(rs, c, A.MELEE, 2) == 3      # caste: 2 x 2 - 1
    assert costs.ability_step(rs, c, A.OCCULT, 2) == 3     # favoured: 2 x 2 - 1


def test_new_ability_from_zero_is_flat():
    rs, c = _ruleset(), _char()
    assert costs.ability_step(rs, c, A.LORE, 0) == 3       # new_ability flat, no scaling


def test_virtue_willpower_essence_scale():
    rs, c = _ruleset(), _char()
    assert costs.virtue_step(rs, c, 3) == 9                # 3 x 3
    assert costs.willpower_step(rs, c, 5) == 10            # 5 x 2
    assert costs.essence_step(rs, c, 2) == 16              # 2 x 8


def test_charm_cost_discounts_caste_favored_ability():
    rs, c = _ruleset(), _char()
    assert costs.charm_cost(rs, c, rs.charms["melee-charm"]) == 8     # Melee is Caste
    # A non-caste/favoured Charm pays full price.
    rs.charms["lore-charm"] = Charm(id="lore-charm", name="Lore", category="lore",
                                    type=CharmType.SIMPLE, min_ability=1, min_essence=1)
    assert costs.charm_cost(rs, c, rs.charms["lore-charm"]) == 10


def test_spell_cost_discounts_when_occult_caste_favored():
    rs, c = _ruleset(), _char()
    assert costs.spell_cost(rs, c) == 8                    # Occult favoured here
    c.favored_abilities = [A.LORE, A.DODGE, A.ATHLETICS, A.RESISTANCE, A.ENDURANCE]
    assert costs.spell_cost(rs, c) == 10                   # Occult neither caste nor favoured


def test_specialty_is_flat():
    assert costs.specialty_cost(_ruleset(), _char()) == 3


def test_combo_cost_sums_member_minimum_abilities():
    rs = _ruleset()
    assert costs.combo_cost(rs, ["melee-charm", "occult-charm"]) == 5    # 3 + 2
    assert costs.combo_cost(rs, ["melee-charm", "missing"]) == 3         # unknown id ignored
