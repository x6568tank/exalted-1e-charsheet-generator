"""Tests for engine.advancement — post-lock XP transitions, undo, and the XP audit.

A locked Dawn Solar with some XP earned is advanced; the trait change, the log row,
and the running available-XP must all stay consistent, and undo must reverse them.
"""

import pytest

from exalted_builder.engine import advancement, derive, lifecycle
from exalted_builder.models.character import Character
from exalted_builder.models.rules import (
    AbilityName,
    AttributeName,
    CasteDefinition,
    Charm,
    CharmType,
    CharmVariant,
    RuleSet,
    Spell,
    SpellCircle,
    VirtueName,
)

A, AT, V = AbilityName, AttributeName, VirtueName


def _ruleset() -> RuleSet:
    castes = {"dawn": CasteDefinition(
        id="dawn", label="Dawn",
        caste_abilities=[A.ARCHERY, A.BRAWL, A.MARTIAL_ARTS, A.MELEE, A.THROWN])}
    charms = {
        "base": Charm(id="base", name="Base Charm", category="melee",
                      type=CharmType.SIMPLE, min_ability=1, min_essence=1),
        "follow": Charm(id="follow", name="Follow Up", category="melee",
                        type=CharmType.REFLEXIVE, min_ability=2, min_essence=1,
                        prerequisites=[["base"]]),
        "sorcery": Charm(id="sorcery", name="Terrestrial Circle Sorcery", category="occult",
                         type=CharmType.PERMANENT, min_ability=1, min_essence=1,
                         grants_sorcery_circle=SpellCircle.TERRESTRIAL),
        "solar.endurance.ox-body-technique": Charm(
            id="solar.endurance.ox-body-technique", name="Ox-Body Technique",
            category="endurance", type=CharmType.SPECIAL, min_ability=1, min_essence=1,
            repeatable_cap_ability="endurance",
            variants=[
                CharmVariant(key="one-zero", label="One -0", health_levels=[0]),
                CharmVariant(key="two-one", label="Two -1", health_levels=[-1, -1]),
            ]),
    }
    spells = {"frost": Spell(id="frost", name="Frost", circle=SpellCircle.TERRESTRIAL)}
    return RuleSet(castes=castes, charms=charms, spells=spells)


def _locked(xp: int = 50) -> Character:
    c = Character(id="char.xp", caste="dawn")
    c.favored_abilities = [A.OCCULT, A.DODGE, A.ATHLETICS, A.RESISTANCE, A.ENDURANCE]
    c.attributes[AT.DEXTERITY] = 3
    c.abilities[A.MELEE] = 2
    c.abilities[A.OCCULT] = 1                               # so the Sorcery Charm is learnable
    c.virtues.update({V.COMPASSION: 3, V.CONVICTION: 3, V.TEMPERANCE: 2, V.VALOR: 1})
    lifecycle.lock_chargen(c)
    c.xp_earned = xp
    return c


# --------------------------------------------------------------------------- #
# Guards
# --------------------------------------------------------------------------- #

def test_cannot_spend_before_lock():
    rs = _ruleset()
    c = Character(id="char.x", caste="dawn")
    with pytest.raises(advancement.AdvancementError):
        advancement.raise_attribute(rs, c, AT.DEXTERITY)


def test_cannot_overspend():
    rs, c = _ruleset(), _locked(xp=1)
    with pytest.raises(advancement.AdvancementError):
        advancement.raise_attribute(rs, c, AT.DEXTERITY)   # Dex 3 -> 4 costs 12 > 1
    assert c.attributes[AT.DEXTERITY] == 3                 # unchanged on failure
    assert c.xp_log == []


def test_cannot_raise_past_five():
    rs, c = _ruleset(), _locked()
    c.abilities[A.MELEE] = 5
    with pytest.raises(advancement.AdvancementError):
        advancement.raise_ability(rs, c, A.MELEE)


# --------------------------------------------------------------------------- #
# Raises: trait + log + accounting
# --------------------------------------------------------------------------- #

def test_raise_attribute_applies_and_logs():
    rs, c = _ruleset(), _locked()
    entry = advancement.raise_attribute(rs, c, AT.DEXTERITY)
    assert c.attributes[AT.DEXTERITY] == 4
    assert entry.cost == 12 and entry.from_rating == 3 and entry.to_rating == 4
    assert advancement.xp_spent(c) == 12
    assert advancement.xp_available(c) == 38


def test_raise_favored_ability_is_discounted():
    rs, c = _ruleset(), _locked()
    c.abilities[A.OCCULT] = 2                               # Occult is Favoured
    entry = advancement.raise_ability(rs, c, A.OCCULT)
    assert entry.cost == 3                                  # 2 x 2 - 1
    assert c.abilities[A.OCCULT] == 3


def test_raise_willpower_increments_purchased_not_virtue_component():
    rs, c = _ruleset(), _locked()
    before = derive.willpower(c)
    entry = advancement.raise_willpower(rs, c)
    assert entry.cost == before * 2
    assert derive.willpower(c) == before + 1
    assert c.willpower_purchased == 1


# --------------------------------------------------------------------------- #
# New traits
# --------------------------------------------------------------------------- #

def test_learn_charm_requires_prerequisites():
    rs, c = _ruleset(), _locked()
    with pytest.raises(advancement.AdvancementError):
        advancement.learn_charm(rs, c, "follow")           # needs 'base' first
    advancement.learn_charm(rs, c, "base")
    advancement.learn_charm(rs, c, "follow")               # now legal
    assert c.charms == ["base", "follow"]
    # base: Melee is Caste -> 8; follow likewise -> 8
    assert advancement.xp_spent(c) == 16


def test_learn_spell_requires_circle_charm():
    rs, c = _ruleset(), _locked()
    with pytest.raises(advancement.AdvancementError):
        advancement.learn_spell(rs, c, "frost")            # no Sorcery Charm yet
    advancement.learn_charm(rs, c, "sorcery")
    entry = advancement.learn_spell(rs, c, "frost")
    assert "frost" in c.spells
    assert entry.cost == 8                                  # Occult favoured -> discounted


def test_add_combo_must_be_legal_and_costs_min_abilities():
    rs, c = _ruleset(), _locked()
    advancement.learn_charm(rs, c, "base")
    advancement.learn_charm(rs, c, "follow")
    entry = advancement.add_combo(rs, c, "Twin", ["base", "follow"])
    assert entry.cost == 1 + 2                              # min_ability 1 + 2
    assert len(c.combos) == 1


# --------------------------------------------------------------------------- #
# Ox-Body Technique (repeatable, variant menu)
# --------------------------------------------------------------------------- #

OX = "solar.endurance.ox-body-technique"


def test_learn_ox_body_adds_purchase_levels_and_costs_charm_xp():
    rs, c = _ruleset(), _locked(xp=20)
    c.abilities[A.ENDURANCE] = 2
    entry = advancement.learn_ox_body(rs, c, "two-one")
    assert entry.cost == 8                                  # Endurance favoured -> new_charm_favored_caste
    assert len(c.ox_body) == 1 and c.ox_body[0].variant == "two-one"
    assert c.ox_body[0].health_levels == [-1, -1]
    # the two -1 levels show up on the derived health track
    assert sum(1 for h in derive.health_track(c) if h.penalty == -1 and h.source) == 2


def test_ox_body_capped_at_endurance_dots():
    rs, c = _ruleset(), _locked(xp=99)
    c.abilities[A.ENDURANCE] = 2
    advancement.learn_ox_body(rs, c, "one-zero")
    advancement.learn_ox_body(rs, c, "one-zero")
    with pytest.raises(advancement.AdvancementError):
        advancement.learn_ox_body(rs, c, "one-zero")       # 3rd exceeds Endurance 2
    assert len(c.ox_body) == 2


def test_ox_body_unknown_variant_raises():
    rs, c = _ruleset(), _locked()
    c.abilities[A.ENDURANCE] = 1
    with pytest.raises(advancement.AdvancementError):
        advancement.learn_ox_body(rs, c, "nope")
    assert c.ox_body == []


def test_undo_ox_body_removes_last_purchase_and_refunds():
    rs, c = _ruleset(), _locked(xp=20)
    c.abilities[A.ENDURANCE] = 2
    advancement.learn_ox_body(rs, c, "one-zero")
    advancement.learn_ox_body(rs, c, "two-one")
    advancement.undo_last(rs, c)
    assert [p.variant for p in c.ox_body] == ["one-zero"]
    assert advancement.xp_available(c) == 12               # 20 - 8 (one purchase left)


def test_ox_body_purchases_pass_the_xp_audit():
    rs, c = _ruleset(), _locked(xp=20)
    c.abilities[A.ENDURANCE] = 1
    advancement.learn_ox_body(rs, c, "one-zero")
    codes = {i.code for i in advancement.validate_xp(rs, c)}
    assert "xp-cost-mismatch" not in codes and "xp-overspent" not in codes


def test_check_ox_body_flags_over_cap_and_bad_variant():
    from exalted_builder.engine import validate
    from exalted_builder.models.character import OxBodyPurchase
    rs, c = _ruleset(), _locked()
    c.abilities[A.ENDURANCE] = 1
    c.ox_body = [OxBodyPurchase(variant="one-zero", health_levels=[0]),
                 OxBodyPurchase(variant="ghost", health_levels=[0])]   # 2 > cap 1, + bad key
    codes = {i.code for i in validate.check_ox_body(rs, c)}
    assert "ox-body-over-cap" in codes and "ox-body-bad-variant" in codes


# --------------------------------------------------------------------------- #
# Undo (LIFO)
# --------------------------------------------------------------------------- #

def test_undo_reverses_trait_and_refunds():
    rs, c = _ruleset(), _locked()
    advancement.raise_attribute(rs, c, AT.DEXTERITY)
    assert advancement.xp_spent(c) == 12
    undone = advancement.undo_last(rs, c)
    assert undone.target == "attributes.dexterity"
    assert c.attributes[AT.DEXTERITY] == 3                 # reverted
    assert c.xp_log == [] and advancement.xp_spent(c) == 0


def test_undo_charm_removes_it():
    rs, c = _ruleset(), _locked()
    advancement.learn_charm(rs, c, "base")
    advancement.undo_last(rs, c)
    assert c.charms == []


def test_undo_on_empty_log_raises():
    rs, c = _ruleset(), _locked()
    with pytest.raises(advancement.AdvancementError):
        advancement.undo_last(rs, c)


# --------------------------------------------------------------------------- #
# Audit
# --------------------------------------------------------------------------- #

def test_validate_xp_is_silent_before_lock():
    rs = _ruleset()
    c = Character(id="char.x", caste="dawn")
    assert advancement.validate_xp(rs, c) == []


def test_validate_xp_flags_overspend():
    rs, c = _ruleset(), _locked(xp=10)
    advancement.add_xp(c, 5)                                # 15 earned
    advancement.raise_attribute(rs, c, AT.DEXTERITY)       # 12 spent, ok
    c.xp_earned = 5                                         # hand-edit below the spend
    codes = {i.code for i in advancement.validate_xp(rs, c)}
    assert "xp-overspent" in codes


def test_validate_xp_flags_cost_tampering():
    rs, c = _ruleset(), _locked()
    advancement.raise_attribute(rs, c, AT.DEXTERITY)
    c.xp_log[-1].cost = 1                                   # tampered row
    codes = {i.code for i in advancement.validate_xp(rs, c)}
    assert "xp-cost-mismatch" in codes


def test_validate_xp_summary_reports_available():
    rs, c = _ruleset(), _locked(xp=20)
    advancement.raise_attribute(rs, c, AT.DEXTERITY)       # 12
    summary = next(i for i in advancement.validate_xp(rs, c) if i.code == "xp-summary")
    assert "12 of 20" in summary.message and "8 available" in summary.message


# --------------------------------------------------------------------------- #
# Permanent reductions (curses / Charm costs) — free, logged, undoable
# --------------------------------------------------------------------------- #

def test_lower_attribute_is_free_and_logged():
    rs, c = _ruleset(), _locked(xp=10)
    advancement.lower_attribute(c, AT.DEXTERITY, "wasting curse")
    assert c.attributes[AT.DEXTERITY] == 2                  # 3 -> 2
    row = c.xp_log[-1]
    assert (row.from_rating, row.to_rating, row.cost) == (3, 2, 0)
    assert row.detail == "wasting curse"
    assert advancement.xp_available(c) == 10               # no XP spent or refunded


def test_reduction_passes_the_xp_audit():
    rs, c = _ruleset(), _locked(xp=10)
    advancement.lower_attribute(c, AT.DEXTERITY, "curse")
    codes = {i.code for i in advancement.validate_xp(rs, c)}
    assert "xp-cost-mismatch" not in codes                 # a 0-cost reduction is expected at 0


def test_lower_floors_guard_the_minimum():
    rs, c = _ruleset(), _locked()
    c.attributes[AT.STRENGTH] = 1
    with pytest.raises(advancement.AdvancementError):
        advancement.lower_attribute(c, AT.STRENGTH)        # already at 1


def test_lower_willpower_can_drop_below_virtue_component():
    rs, c = _ruleset(), _locked()
    start = derive.willpower(c)                             # = two highest Virtues (3+3 = 6)
    for _ in range(start - 1):                              # curse it all the way down to 1
        advancement.lower_willpower(c, "soul-eroding curse")
    assert derive.willpower(c) == 1
    assert c.willpower_purchased < 0                        # net-negative below the Virtue floor
    with pytest.raises(advancement.AdvancementError):
        advancement.lower_willpower(c)                      # floored at 1


def test_undo_reverses_a_willpower_reduction():
    rs, c = _ruleset(), _locked()
    start = derive.willpower(c)
    advancement.lower_willpower(c, "curse")
    assert derive.willpower(c) == start - 1
    advancement.undo_last(rs, c)
    assert derive.willpower(c) == start                    # restored exactly
    assert c.xp_log == []


def test_undo_reverses_an_attribute_reduction():
    rs, c = _ruleset(), _locked()
    advancement.lower_attribute(c, AT.DEXTERITY, "curse")   # 3 -> 2
    advancement.undo_last(rs, c)
    assert c.attributes[AT.DEXTERITY] == 3
    assert c.xp_log == []
