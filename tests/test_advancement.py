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
    Caste,
    CasteDefinition,
    Charm,
    CharmType,
    RuleSet,
    Spell,
    SpellCircle,
    VirtueName,
)

A, AT, V = AbilityName, AttributeName, VirtueName


def _ruleset() -> RuleSet:
    castes = {Caste.DAWN: CasteDefinition(
        caste=Caste.DAWN,
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
    }
    spells = {"frost": Spell(id="frost", name="Frost", circle=SpellCircle.TERRESTRIAL)}
    return RuleSet(castes=castes, charms=charms, spells=spells)


def _locked(xp: int = 50) -> Character:
    c = Character(id="char.xp", caste=Caste.DAWN)
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
    c = Character(id="char.x", caste=Caste.DAWN)
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
    c = Character(id="char.x", caste=Caste.DAWN)
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
