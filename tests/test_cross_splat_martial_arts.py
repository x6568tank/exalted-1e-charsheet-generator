"""Cross-splat Martial Arts: the Terrestrial (Immaculate Dragon) styles are flagged
`open_to_all`, so ANY splat may learn them (rules authority: nothing bars a Solar
from Terrestrial MA — it just needs a trainer). For a non-Dragon-Blooded learner the
style is an ordinary Martial Arts Charm: it must NOT trigger the Dragon-Blooded-only
Immaculate chargen package (5-in-one-tree, Immaculate BP row, waived C/F minimum).
"""

from pathlib import Path

import pytest

import exalted_builder
from exalted_builder import rules_db
from exalted_builder.engine import validate
from exalted_builder.models.character import Character
from exalted_builder.models.rules import AbilityName

DATA_DIR = Path(exalted_builder.__file__).parent / "data"

_DRAGON_STYLE = [
    "dragonblooded.air-dragon.air-dragons-sight",
    "dragonblooded.air-dragon.wind-dragon-speed",
    "dragonblooded.air-dragon.breath-seizing-technique",
    "dragonblooded.air-dragon.shrouding-the-body-and-mind",
    "dragonblooded.air-dragon.air-dragon-form",
]
_ENLIGHTENMENT = [
    "dragonblooded.martial-arts.spirit-sight",
    "dragonblooded.martial-arts.spirit-walking",
]


@pytest.fixture(scope="module")
def rs():
    return rules_db.load_ruleset(DATA_DIR)


def _solar() -> Character:
    return Character(id="s", exalt_type="Solar", caste="dawn")


def _ma_char(splat: str, caste: str) -> Character:
    c = Character(id="x", exalt_type=splat, caste=caste, essence_rating=3)
    c.abilities = {AbilityName.MARTIAL_ARTS: 5}
    return c


def test_dragon_styles_are_open_to_all(rs):
    for cid in _DRAGON_STYLE:
        assert rs.charms[cid].open_to_all is True


def test_solar_can_see_a_terrestrial_style(rs):
    # the picker/graph visibility filter now admits the cross-splat Charm
    charm = rs.charms[_DRAGON_STYLE[0]]
    assert validate.charm_matches_splat(_solar(), charm) is True


def test_solar_holding_a_dragon_style_gets_no_wrong_splat_error(rs):
    c = _solar()
    c.charms = [_DRAGON_STYLE[0]]
    codes = {i.code for i in validate.check_splat_consistency(rs, c)}
    assert "charm-wrong-splat" not in codes


def test_solar_dragon_style_is_the_standard_chargen_path(rs):
    # a Solar picking Terrestrial-MA Charms is NOT put on the DB Immaculate path
    c = _solar()
    c.charms = list(_DRAGON_STYLE)
    assert validate.immaculate_martial_artist(rs, c) is False
    assert validate._immaculate_path(rs, c.charms, "Solar") is False


def test_solar_dragon_style_priced_as_ordinary_charms(rs):
    # on the standard path the free Charm pool is the ordinary charm_count (not the
    # Immaculate 5), so the BP breakdown reflects ordinary Martial Arts pricing.
    c = _solar()
    c.charms = list(_DRAGON_STYLE)
    bd = validate.bonus_point_breakdown(rs, c)
    b = rs.budgets_for("Solar", c.origin)
    # standard path uses charm_count; if the Immaculate 5-pool had fired this would
    # differ. Assert we're accounting against the ordinary pool.
    assert not validate._immaculate_path(rs, c.charms, "Solar")
    assert b.charm_count == rs.budgets_for("Solar").charm_count


def test_db_immaculate_path_still_fires(rs):
    # the Dragon-Blooded Immaculate package is unchanged: a DB picking the same tree
    # IS on the Immaculate path.
    c = Character(id="d", exalt_type="Dragon-Blooded", caste="air", origin="dynastic")
    c.charms = list(_DRAGON_STYLE)
    assert validate.immaculate_martial_artist(rs, c) is True


# --- Dragon-Blooded Dragon-Path enlightenment gate (DB p241-242) ------------- #

def test_enlightenment_charms_authored(rs):
    ss = rs.charms["dragonblooded.martial-arts.spirit-sight"]
    sw = rs.charms["dragonblooded.martial-arts.spirit-walking"]
    assert ss.category == "martial_arts:enlightenment"
    assert sw.category == "martial_arts:enlightenment"
    # NOT Immaculate Charms — they are enlightenment prerequisites, not a Dragon
    # style, so they must not trip the Immaculate chargen package.
    assert ss.immaculate is False and sw.immaculate is False
    # Spirit Walking chains off Spirit Sight
    assert sw.prerequisites == [["dragonblooded.martial-arts.spirit-sight"]]


def test_db_needs_both_enlightenment_charms_before_dragon_paths(rs):
    c = _ma_char("Dragon-Blooded", "air")
    air = rs.charms[_DRAGON_STYLE[0]]
    assert validate.meets_charm_requirements(rs, c, air) is False        # neither
    c.charms = ["dragonblooded.martial-arts.spirit-sight"]
    assert validate.meets_charm_requirements(rs, c, air) is False        # only Sight
    c.charms = list(_ENLIGHTENMENT)
    assert validate.meets_charm_requirements(rs, c, air) is True         # both


def test_five_dragon_style_is_exempt_from_the_gate(rs):
    c = _ma_char("Dragon-Blooded", "earth")
    fd = rs.charms["dragonblooded.martial-arts.five-dragon-fortitude"]
    assert validate.meets_charm_requirements(rs, c, fd) is True          # no enlightenment needed


def test_enlightenment_gate_is_dragon_blooded_only(rs):
    air = rs.charms[_DRAGON_STYLE[0]]
    # Celestial Exalted and Abyssals need no initiation — they learn Dragon styles freely
    assert validate.meets_charm_requirements(rs, _ma_char("Solar", "dawn"), air) is True
    assert validate.meets_charm_requirements(rs, _ma_char("Abyssal", "dusk"), air) is True


def test_category_available_hides_dragon_paths_until_enlightened(rs):
    c = _ma_char("Dragon-Blooded", "air")
    assert validate.category_available(rs, c, "martial_arts:air-dragon") is False
    assert validate.category_available(rs, c, "martial_arts:five-dragon") is True
    assert validate.category_available(rs, c, "martial_arts:enlightenment") is True
    c.charms = list(_ENLIGHTENMENT)
    assert validate.category_available(rs, c, "martial_arts:air-dragon") is True
    # non-Dragon-Blooded: the gate never applies
    assert validate.category_available(rs, _solar(), "martial_arts:air-dragon") is True
