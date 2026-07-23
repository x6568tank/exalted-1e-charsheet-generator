"""Tests for engine.costs — the XP price of a single advance. Values come from the
default ExperienceCosts table (current rating x N for scaled traits)."""

from exalted_builder.engine import costs
from exalted_builder.models.character import Character
from exalted_builder.models.rules import (
    AbilityName,
    AttributeName,
    CasteDefinition,
    Charm,
    CharmType,
    ExperienceCosts,
    LinearCost,
    RuleSet,
    SpellCircle,
)

A = AbilityName
AT = AttributeName


def _ruleset() -> RuleSet:
    castes = {"dawn": CasteDefinition(
        id="dawn", label="Dawn",
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
                         grants_circle=SpellCircle.TERRESTRIAL),
    }
    return RuleSet(castes=castes, charms=charms)


def _char() -> Character:
    c = Character(id="char.cost", caste="dawn")
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


def _spell(cid: str, circle: SpellCircle):
    from exalted_builder.models.rules import Spell
    return Spell(id=cid, name=cid, circle=circle, description="")


def test_spell_cost_per_circle_uses_caste_discount_not_occult():
    """A splat with new_spell_by_circle prices by circle and applies the CASTE
    discount; the Occult-favoured path is bypassed for it."""
    castes = {"disc": CasteDefinition(id="disc", label="Disc", spell_cost_discount=2),
              "plain": CasteDefinition(id="plain", label="Plain")}
    xp = {"default": ExperienceCosts(),
          "Lunar": ExperienceCosts(new_spell_by_circle={SpellCircle.TERRESTRIAL: 12,
                                                        SpellCircle.CELESTIAL: 15})}
    rs = RuleSet(castes=castes, charms={}, xp_costs=xp)
    terr, cel = _spell("t", SpellCircle.TERRESTRIAL), _spell("c", SpellCircle.CELESTIAL)
    disc = Character(id="c.disc", exalt_type="Lunar", caste="disc")
    disc.favored_abilities = [A.OCCULT]                    # Occult favoured must NOT matter
    assert costs.spell_cost(rs, disc, terr) == 10          # 12 − 2
    assert costs.spell_cost(rs, disc, cel) == 13           # 15 − 2
    plain = Character(id="c.plain", exalt_type="Lunar", caste="plain")
    assert costs.spell_cost(rs, plain, terr) == 12         # no caste discount
    # No spell passed => can't read a circle => flat new_spell fallback.
    assert costs.spell_cost(rs, plain) == 10


def test_specialty_is_flat():
    assert costs.specialty_cost(_ruleset(), _char()) == 3


def test_combo_cost_sums_member_minimum_abilities():
    rs = _ruleset()
    assert costs.combo_cost(rs, ["melee-charm", "occult-charm"]) == 5    # 3 + 2
    assert costs.combo_cost(rs, ["melee-charm", "missing"]) == 3         # unknown id ignored


def test_combo_cost_counts_attribute_keyed_charms_by_min_rating():
    """A Lunar Attribute-keyed Charm stores its required rating in `min_ability`
    (min_attribute only names WHICH Attribute), so summing min_ability already
    yields the p.251 'sum of minimum Ability and minimum Attribute values' figure."""
    rs = _ruleset()
    rs.charms["lunar-charm"] = Charm(
        id="lunar-charm", name="Lunar", category="melee", exalt_type="Lunar",
        type=CharmType.SIMPLE, min_attribute="dexterity", min_ability=4, min_essence=1)
    assert costs.combo_cost(rs, ["lunar-charm", "occult-charm"]) == 6    # 4 (Dex) + 2 (Occult)


def _caste_attr_ruleset() -> RuleSet:
    """A splat with Caste Attributes (Physical) and a Lunar-style attribute
    Caste-favored XP discount ((x4)-1), used to exercise the discount branch."""
    castes = {"full-moon": CasteDefinition(
        id="full-moon", label="Full Moon",
        caste_attributes=[AT.STRENGTH, AT.DEXTERITY, AT.STAMINA])}
    xp = {"default": ExperienceCosts(),
          "Lunar": ExperienceCosts(essence=LinearCost(coeff=9),
                                   attribute_caste_favored=LinearCost(coeff=4, offset=-1),
                                   new_charm=15, new_charm_favored_caste=12)}
    return RuleSet(castes=castes, charms={}, xp_costs=xp)


def test_attribute_caste_favored_discount():
    rs = _caste_attr_ruleset()
    c = Character(id="c.lunar", exalt_type="Lunar", caste="full-moon")
    assert costs.attribute_step(rs, c, 3, AT.STRENGTH) == 11    # Caste Attribute: 3 x 4 - 1
    assert costs.attribute_step(rs, c, 3, AT.CHARISMA) == 12    # non-Caste: 3 x 4
    assert costs.attribute_step(rs, c, 3) == 12                 # no attr passed: flat rate


def test_essence_uses_splat_override():
    rs = _caste_attr_ruleset()
    c = Character(id="c.lunar", exalt_type="Lunar", caste="full-moon")
    assert costs.essence_step(rs, c, 2) == 18                   # Lunar 2 x 9 (not the x8 default)


def test_immaculate_charm_uses_its_own_rate():
    """A Charm flagged `immaculate` prices off new_immaculate_charm, not new_charm."""
    xp = {"default": ExperienceCosts(new_charm=12, new_charm_favored_caste=10,
                                     new_immaculate_charm=15,
                                     new_immaculate_charm_favored_caste=12)}
    castes = {"dawn": CasteDefinition(id="dawn", label="Dawn",
                                      caste_abilities=[A.ARCHERY])}
    rs = RuleSet(castes=castes, charms={}, xp_costs=xp)
    c = Character(id="c.db", exalt_type="Dragon-Blooded", caste="dawn")
    ordinary = Charm(id="ord", name="Ordinary", category="melee",
                     type=CharmType.SIMPLE, min_ability=1, min_essence=1)
    imm = Charm(id="imm", name="Immaculate", category="martial_arts:fire-dragon",
                type=CharmType.SIMPLE, min_ability=1, min_essence=1, immaculate=True)
    c.favored_abilities = []
    assert costs.charm_cost(rs, c, ordinary) == 12             # new_charm (Melee not favored)
    assert costs.charm_cost(rs, c, imm) == 15                  # immaculate full rate (MA not favored)
    c.favored_abilities = [A.MARTIAL_ARTS]
    assert costs.charm_cost(rs, c, imm) == 12                  # immaculate, MA favored -> discounted
