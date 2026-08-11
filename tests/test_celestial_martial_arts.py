"""Tier-gated cross-splat Martial Arts.

Two styles are open wider than their authoring splat, but NOT to everyone:

* **Hungry Ghost Style** (Abyssal) — any *Celestial* Exalt may learn it (Solar,
  Abyssal, and later Lunar/Sidereal), but not the Terrestrial Dragon-Blooded.
* ~~**Five-Dragon Style**~~ — **corrected 2026-08-01**: Five-Dragon Style is
  TERRESTRIAL (human, rules authority), so it is `open_to_all` and belongs with the
  cross-splat styles, not here. The five Immaculate Dragon Paths are the Celestial
  ones, and the data had both backwards.

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
_AIR_DRAGON = "dragonblooded.air-dragon.air-dragons-sight"
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
    """The hierarchy, low to high: Terrestrial < Celestial < Solar (human, rules
    authority, 2026-08-11). Terrestrial is the Dragon-Blooded alone; Celestial holds
    Lunars, Sidereals, Abyssals and Alchemicals; the Solar Exalted stand above all.

    Solar was previously authored `Celestial` — not a taxonomy but a workaround, since
    the tier test was exact string equality and there was no way to say "Celestial or
    below". `validate.tier_reaches` now ranks them, so the label can be honest."""
    assert rs.exalt_for("Solar").tier == "Solar"
    assert rs.exalt_for("Abyssal").tier == "Celestial"
    assert rs.exalt_for("Lunar").tier == "Celestial"
    assert rs.exalt_for("Sidereal").tier == "Celestial"
    assert rs.exalt_for("Alchemical").tier == "Celestial"
    assert rs.exalt_for("Dragon-Blooded").tier == "Terrestrial"


def test_a_splat_reaches_its_own_tier_and_every_tier_below(rs):
    """Downward only. A Solar reaches Celestial and Terrestrial styles; a Celestial
    reaches Terrestrial; nothing reaches UP — Lunars and Sidereals cannot touch
    Solar-tier material."""
    assert validate.tier_reaches("Solar", ["Celestial"])
    assert validate.tier_reaches("Solar", ["Terrestrial"])
    assert validate.tier_reaches("Celestial", ["Terrestrial"])
    assert validate.tier_reaches("Celestial", ["Celestial"])
    assert not validate.tier_reaches("Celestial", ["Solar"])
    assert not validate.tier_reaches("Terrestrial", ["Celestial"])
    assert not validate.tier_reaches("Terrestrial", ["Solar"])
    # Splats outside the hierarchy reach nothing by rank; they are gated elsewhere.
    assert not validate.tier_reaches("Mortal", ["Terrestrial"])
    assert not validate.tier_reaches("Ghost", ["Terrestrial"])


def test_an_alchemical_reaches_no_martial_arts_at_all_without_the_matrix(rs):
    """CH3 p.100 — the tier says what she COULD reach, PLM says whether she may, and
    it gates EVERY tier: no Terrestrial style either (human, 2026-08-11).

    The bar has to sit above `open_to_all`, because the Terrestrial styles are
    open_to_all and would otherwise be granted before any tier reasoning ran. Testing
    only the Celestial style would pass with the bar in the wrong place."""
    bare = _char("Alchemical", "orichalcum")
    for cid in (_HUNGRY_GHOST, _FIVE_DRAGON):
        assert not validate.charm_matches_splat(bare, rs.charms[cid], rs), cid
    installed = _char("Alchemical", "orichalcum")
    installed.charms = [validate.PERFECTED_LOTUS_MATRIX_ID]
    for cid in (_HUNGRY_GHOST, _FIVE_DRAGON):
        assert validate.charm_matches_splat(installed, rs.charms[cid], rs), cid


def test_the_matrix_bar_does_not_touch_an_alchemicals_own_charms(rs):
    """The bar is keyed on the martial_arts CATEGORY, and no Alchemical Charm lives
    in one — including Perfected Lotus Matrix itself, which she must be able to buy
    in order to lift the bar at all."""
    bare = _char("Alchemical", "orichalcum")
    plm = rs.charms[validate.PERFECTED_LOTUS_MATRIX_ID]
    assert validate.charm_matches_splat(bare, plm, rs)
    own = next(c for c in rs.charms.values()
               if c.exalt_type == "Alchemical"
               and not c.category.startswith("martial_arts"))
    assert validate.charm_matches_splat(bare, own, rs)


def test_styles_flagged_celestial(rs):
    for cid in (_HUNGRY_GHOST, _AIR_DRAGON):
        assert rs.charms[cid].open_to_tiers == ["Celestial"]
        # tier-opening is narrower than open_to_all — these stay splat-limited
        assert rs.charms[cid].open_to_all is False


def test_five_dragon_style_is_terrestrial_not_celestial(rs):
    """Corrected 2026-08-01 (human, rules authority). The data had the two Dragon-
    Blooded style families exactly backwards: Five-Dragon was tagged Celestial-only and
    the five Immaculate Dragon Paths were tagged `open_to_all` (i.e. Terrestrial).

    It is the wrong way round in BOTH directions, so it cost twice: splats with
    Terrestrial-only martial arts (mortals via Essence Mastery, ghosts via PG p.234)
    were denied Five-Dragon and offered the Immaculate Paths."""
    style = [c for c in rs.charms.values() if c.category == "martial_arts:five-dragon"]
    assert style
    assert all(c.open_to_all is True for c in style)
    assert all(c.open_to_tiers == [] for c in style)


def test_whole_style_trees_are_open_not_just_the_roots(rs):
    for cat in ("martial_arts:hungry-ghost", "martial_arts:air-dragon",
                "martial_arts:earth-dragon", "martial_arts:fire-dragon",
                "martial_arts:water-dragon", "martial_arts:wood-dragon"):
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


def test_enlightenment_charms_are_open_to_every_exalt(rs):
    # the Dragon-Path initiation tree is `open_to_all`: any Exalt may learn it, the
    # same way the Dragon Paths it initiates are open to all
    charm = rs.charms[_ENLIGHTENMENT]
    assert validate.charm_matches_splat(_char("Solar", "dawn"), charm, rs) is True
    assert validate.charm_matches_splat(_char("Abyssal", "dusk"), charm, rs) is True


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
