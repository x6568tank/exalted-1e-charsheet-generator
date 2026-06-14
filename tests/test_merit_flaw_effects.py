"""Tests for Merit/Flaw mechanical effects — currently trait-rating caps applied
in both chargen (validate_chargen) and post-lock XP (advancement).

Covers True Paragon (raises a Virtue's max to 6) and Disfigured (lowers Appearance
to 1 at 3pt / 0 at 4pt), per the Player's Guide pages in images/.
"""

import pytest

from exalted_builder.engine import advancement, lifecycle, validate
from exalted_builder.models.character import Character, MeritFlaw
from exalted_builder.models.rules import (
    AbilityName,
    AttributeName,
    Caste,
    CasteDefinition,
    MeritFlawEffect,
    MeritFlawType,
    RuleSet,
    VirtueName,
)

A, AT, V = AbilityName, AttributeName, VirtueName


def _ruleset() -> RuleSet:
    castes = {Caste.DAWN: CasteDefinition(
        caste=Caste.DAWN,
        caste_abilities=[A.ARCHERY, A.BRAWL, A.MARTIAL_ARTS, A.MELEE, A.THROWN])}
    catalog = {
        "merit.true-paragon": MeritFlawType(
            id="merit.true-paragon", name="True Paragon", points=3,
            effects=[MeritFlawEffect(kind="trait_cap", target="virtues", max=6)]),
        "flaw.disfigured": MeritFlawType(
            id="flaw.disfigured", name="Disfigured", points=3, is_flaw=True,
            effects=[MeritFlawEffect(kind="trait_cap", target="attributes.appearance",
                                     max_by_points={3: 1, 4: 0})]),
    }
    return RuleSet(castes=castes, charms={}, merit_flaw_catalog=catalog)


# --------------------------------------------------------------------------- #
# trait_max
# --------------------------------------------------------------------------- #

def test_trait_max_default_without_effects():
    rs, c = _ruleset(), Character(id="c")
    assert validate.trait_max(rs, c, "virtues.compassion", 5) == 5
    assert validate.trait_max(rs, c, "attributes.appearance", 5) == 5


def test_true_paragon_raises_virtue_cap_only():
    rs, c = _ruleset(), Character(id="c")
    c.merits_flaws = [MeritFlaw(name="True Paragon", points=3)]
    assert validate.trait_max(rs, c, "virtues.valor", 5) == 6
    assert validate.trait_max(rs, c, "attributes.strength", 5) == 5   # other traits untouched


def test_disfigured_lowers_appearance_by_severity():
    rs = _ruleset()
    c3 = Character(id="c", merits_flaws=[MeritFlaw(name="Disfigured", points=3, is_flaw=True)])
    c4 = Character(id="c", merits_flaws=[MeritFlaw(name="Disfigured", points=4, is_flaw=True)])
    assert validate.trait_max(rs, c3, "attributes.appearance", 5) == 1
    assert validate.trait_max(rs, c4, "attributes.appearance", 5) == 0
    assert validate.trait_max(rs, c4, "attributes.strength", 5) == 5


# --------------------------------------------------------------------------- #
# Chargen
# --------------------------------------------------------------------------- #

def test_chargen_allows_virtue_six_only_with_true_paragon():
    rs = _ruleset()
    c = Character(id="c", caste=Caste.DAWN)
    c.virtues[V.COMPASSION] = 6
    assert "virtue-range" in {i.code for i in validate.validate_chargen(rs, c)}
    c.merits_flaws = [MeritFlaw(name="True Paragon", points=3)]
    assert "virtue-range" not in {i.code for i in validate.validate_chargen(rs, c)}


def test_chargen_caps_appearance_with_disfigured():
    rs = _ruleset()
    c = Character(id="c", caste=Caste.DAWN)
    c.attributes[AT.APPEARANCE] = 2
    assert "attribute-range" not in {i.code for i in validate.validate_chargen(rs, c)}
    c.merits_flaws = [MeritFlaw(name="Disfigured", points=3, is_flaw=True)]   # max 1
    assert "attribute-range" in {i.code for i in validate.validate_chargen(rs, c)}


def test_chargen_disfigured_4pt_requires_appearance_zero():
    rs = _ruleset()
    c = Character(id="c", caste=Caste.DAWN)
    c.merits_flaws = [MeritFlaw(name="Disfigured", points=4, is_flaw=True)]    # max 0
    c.attributes[AT.APPEARANCE] = 1
    assert "attribute-range" in {i.code for i in validate.validate_chargen(rs, c)}
    c.attributes[AT.APPEARANCE] = 0                                           # 0 is now legal
    assert "attribute-range" not in {i.code for i in validate.validate_chargen(rs, c)}


# --------------------------------------------------------------------------- #
# Post-lock XP
# --------------------------------------------------------------------------- #

def _locked(c: Character) -> Character:
    lifecycle.lock_chargen(c)
    c.xp_earned = 100
    return c


def test_xp_virtue_to_six_needs_true_paragon():
    rs = _ruleset()
    c = Character(id="c", caste=Caste.DAWN)
    c.virtues[V.COMPASSION] = 5
    _locked(c)
    with pytest.raises(advancement.AdvancementError):
        advancement.raise_virtue(rs, c, V.COMPASSION)        # capped at 5
    c.merits_flaws = [MeritFlaw(name="True Paragon", points=3)]
    advancement.raise_virtue(rs, c, V.COMPASSION)
    assert c.virtues[V.COMPASSION] == 6


def test_xp_appearance_blocked_by_disfigured():
    rs = _ruleset()
    c = Character(id="c", caste=Caste.DAWN)
    c.attributes[AT.APPEARANCE] = 1
    c.merits_flaws = [MeritFlaw(name="Disfigured", points=3, is_flaw=True)]   # max 1
    _locked(c)
    with pytest.raises(advancement.AdvancementError):
        advancement.raise_attribute(rs, c, AT.APPEARANCE)
