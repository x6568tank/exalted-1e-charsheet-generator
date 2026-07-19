"""Tier-gated cross-splat Martial Arts.

Two styles are open wider than their authoring splat, but NOT to everyone:

* **Hungry Ghost Style** (Abyssal) — any *Celestial* Exalt may learn it (Solar,
  Abyssal, and later Lunar/Sidereal), but not the Terrestrial Dragon-Blooded.
* **Five-Dragon Style** (Dragon-Blooded) — its own splat plus any Celestial.

This is the middle ground between `Charm.exalt_type` (one splat) and
`Charm.open_to_all` (every splat): `Charm.open_to_tiers` names Exalt *tiers*, and
`ExaltDefinition.tier` says which tier a splat sits in. Adding Lunars/Sidereals as
`tier: "Celestial"` grants them these styles with no code change.
"""

from pathlib import Path

import pytest

import exalted_builder
from exalted_builder import rules_db
from exalted_builder.engine import validate
from exalted_builder.models.character import Character
from exalted_builder.models.rules import AbilityName

DATA_DIR = Path(exalted_builder.__file__).parent / "data"

_HUNGRY_GHOST = "abyssal.martial-arts.essence-discerning-glance"
_FIVE_DRAGON = "dragonblooded.martial-arts.five-dragon-fortitude"
_ENLIGHTENMENT = "dragonblooded.martial-arts.spirit-sight"


@pytest.fixture(scope="module")
def rs():
    return rules_db.load_ruleset(DATA_DIR)


def _char(splat: str, caste: str) -> Character:
    c = Character(id="x", exalt_type=splat, caste=caste, essence_rating=3)
    c.abilities = {AbilityName.MARTIAL_ARTS: 5}
    return c


# --- the tier data itself ---------------------------------------------------- #

def test_exalt_tiers_authored(rs):
    assert rs.exalt_for("Solar").tier == "Celestial"
    assert rs.exalt_for("Abyssal").tier == "Celestial"
    assert rs.exalt_for("Dragon-Blooded").tier == "Terrestrial"


def test_styles_flagged_celestial(rs):
    for cid in (_HUNGRY_GHOST, _FIVE_DRAGON):
        assert rs.charms[cid].open_to_tiers == ["Celestial"]
        # tier-opening is narrower than open_to_all — these stay splat-limited
        assert rs.charms[cid].open_to_all is False


def test_whole_style_trees_are_open_not_just_the_roots(rs):
    for cat in ("martial_arts:hungry-ghost", "martial_arts:five-dragon"):
        style = [c for c in rs.charms.values() if c.category == cat]
        assert style, cat
        assert all(c.open_to_tiers == ["Celestial"] for c in style), cat


# --- visibility -------------------------------------------------------------- #

def test_solar_may_learn_hungry_ghost(rs):
    charm = rs.charms[_HUNGRY_GHOST]
    assert validate.charm_matches_splat(_char("Solar", "dawn"), charm, rs) is True


def test_solar_may_learn_five_dragon(rs):
    charm = rs.charms[_FIVE_DRAGON]
    assert validate.charm_matches_splat(_char("Solar", "dawn"), charm, rs) is True


def test_abyssal_may_learn_five_dragon(rs):
    charm = rs.charms[_FIVE_DRAGON]
    assert validate.charm_matches_splat(_char("Abyssal", "dusk"), charm, rs) is True


def test_dragon_blooded_barred_from_hungry_ghost(rs):
    # Terrestrial tier: the Celestial-only style stays out of reach
    charm = rs.charms[_HUNGRY_GHOST]
    assert validate.charm_matches_splat(_char("Dragon-Blooded", "air"), charm, rs) is False


def test_dragon_blooded_keep_their_own_five_dragon(rs):
    charm = rs.charms[_FIVE_DRAGON]
    assert validate.charm_matches_splat(_char("Dragon-Blooded", "earth"), charm, rs) is True


def test_enlightenment_charms_stay_dragon_blooded_only(rs):
    # the Dragon-Path initiation gate is not a style and is not opened up
    charm = rs.charms[_ENLIGHTENMENT]
    assert validate.charm_matches_splat(_char("Solar", "dawn"), charm, rs) is False


def test_tier_opening_needs_the_ruleset(rs):
    # without a RuleSet there is no tier table; the call degrades to splat/open_to_all
    charm = rs.charms[_HUNGRY_GHOST]
    assert validate.charm_matches_splat(_char("Solar", "dawn"), charm) is False


# --- validation -------------------------------------------------------------- #

def test_solar_holding_hungry_ghost_gets_no_wrong_splat_error(rs):
    c = _char("Solar", "dawn")
    c.charms = [_HUNGRY_GHOST]
    codes = {i.code for i in validate.check_splat_consistency(rs, c)}
    assert "charm-wrong-splat" not in codes


def test_db_holding_hungry_ghost_is_flagged(rs):
    c = _char("Dragon-Blooded", "air")
    c.charms = [_HUNGRY_GHOST]
    codes = {i.code for i in validate.check_splat_consistency(rs, c)}
    assert "charm-wrong-splat" in codes


def test_celestial_five_dragon_is_not_the_immaculate_path(rs):
    # Five-Dragon is not an Immaculate Charm, and a Solar is never on the DB package
    c = _char("Solar", "dawn")
    c.charms = [_FIVE_DRAGON]
    assert rs.charms[_FIVE_DRAGON].immaculate is False
    assert validate.immaculate_martial_artist(rs, c) is False
