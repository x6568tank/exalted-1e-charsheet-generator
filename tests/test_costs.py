"""Tests for engine.costs — the XP price of a single advance. Values come from the
default ExperienceCosts table (current rating x N for scaled traits)."""

from exalted_builder.engine import costs
from exalted_builder.models.character import Character, MeritFlaw
from exalted_builder.models.rules import (
    AbilityName,
    Caste,
    CasteDefinition,
    Charm,
    CharmType,
    MeritFlawEffect,
    MeritFlawType,
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
    brigid = MeritFlawType(
        id="merit.brigids-heir", name="Brigid's Heir", points=5,
        effects=[
            MeritFlawEffect(kind="cost_multiplier", target="charms", factor_num=2, factor_den=1,
                            except_charm_types=["Special"], except_sorcery_initiation=True),
            MeritFlawEffect(kind="cost_multiplier", target="spells", factor_num=1, factor_den=2),
        ])
    return RuleSet(castes=castes, charms=charms, merit_flaw_catalog={brigid.id: brigid})


def _char() -> Character:
    c = Character(id="char.cost", caste=Caste.DAWN)
    c.favored_abilities = [A.OCCULT, A.DODGE, A.ATHLETICS, A.RESISTANCE, A.ENDURANCE]
    return c


def test_attribute_scales_on_current_rating():
    assert costs.attribute_step(_ruleset(), 3) == 12      # 3 x 4


def test_ability_uses_caste_favored_discount():
    rs, c = _ruleset(), _char()
    assert costs.ability_step(rs, c, A.LORE, 2) == 4       # non-caste/favoured: 2 x 2
    assert costs.ability_step(rs, c, A.MELEE, 2) == 3      # caste: 2 x 2 - 1
    assert costs.ability_step(rs, c, A.OCCULT, 2) == 3     # favoured: 2 x 2 - 1


def test_new_ability_from_zero_is_flat():
    rs, c = _ruleset(), _char()
    assert costs.ability_step(rs, c, A.LORE, 0) == 3       # new_ability flat, no scaling


def test_virtue_willpower_essence_scale():
    rs = _ruleset()
    assert costs.virtue_step(rs, 3) == 9                   # 3 x 3
    assert costs.willpower_step(rs, 5) == 10               # 5 x 2
    assert costs.essence_step(rs, 2) == 16                 # 2 x 8


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
    assert costs.specialty_cost(_ruleset()) == 3


def test_combo_cost_sums_member_minimum_abilities():
    rs = _ruleset()
    assert costs.combo_cost(rs, ["melee-charm", "occult-charm"]) == 5    # 3 + 2
    assert costs.combo_cost(rs, ["melee-charm", "missing"]) == 3         # unknown id ignored


# --------------------------------------------------------------------------- #
# Brigid's Heir cost multiplier (Charms x2 except Ox-Body/sorcery; spells x1/2)
# --------------------------------------------------------------------------- #

def _brigid_char() -> Character:
    c = _char()
    c.merits_flaws = [MeritFlaw(name="Brigid's Heir", points=5)]
    return c


def test_brigids_heir_doubles_charm_cost():
    rs, c = _ruleset(), _brigid_char()
    assert costs.charm_cost(rs, c, rs.charms["melee-charm"]) == 16       # Caste base 8 x2
    rs.charms["lore-charm"] = Charm(id="lore-charm", name="L", category="lore",
                                    type=CharmType.SIMPLE, min_ability=1, min_essence=1)
    assert costs.charm_cost(rs, c, rs.charms["lore-charm"]) == 20        # non-c/f base 10 x2


def test_brigids_heir_exempts_ox_body_and_sorcery_initiation():
    rs, c = _ruleset(), _brigid_char()
    assert costs.charm_cost(rs, c, rs.charms["ox-body"]) == 8            # Special, favoured base 8, not doubled
    assert costs.charm_cost(rs, c, rs.charms["sorcery"]) == 8            # grants a Circle, not doubled


def test_brigids_heir_halves_spell_cost():
    rs, c = _ruleset(), _brigid_char()
    assert costs.spell_cost(rs, c) == 4                                  # Occult favoured base 8, halved
    c.favored_abilities = [A.LORE, A.DODGE, A.ATHLETICS, A.RESISTANCE, A.ENDURANCE]
    assert costs.spell_cost(rs, c) == 5                                  # base 10, halved (round up)


def test_no_multiplier_without_the_merit():
    rs, c = _ruleset(), _char()
    assert costs.charm_cost(rs, c, rs.charms["melee-charm"]) == 8        # plain Caste cost
    assert costs.spell_cost(rs, c) == 8
