"""Tests for engine.derive — the pure (RuleSet, Character) derivations.

Grounded in CLAUDE.md's 1e formulas: Willpower = two highest Virtues (frozen at
lock), Solar Essence pools, and the fixed health track. Soak is intentionally
unimplemented pending its 1e rule, and that contract is tested too.
"""

import pytest

from exalted_builder.engine import derive
from exalted_builder.models.character import Armor, Character, HealthLevel, OxBodyPurchase
from exalted_builder.models.rules import AttributeName, VirtueName


def _char(**kw) -> Character:
    """A Solar with explicit Virtues; everything else default."""
    c = Character(id="char.derive")
    virtues = kw.pop("virtues", None)
    if virtues:
        c.virtues = dict(virtues)
    for k, v in kw.items():
        setattr(c, k, v)
    return c


# --------------------------------------------------------------------------- #
# Willpower
# --------------------------------------------------------------------------- #

def test_willpower_is_two_highest_virtues():
    c = _char(virtues={
        VirtueName.COMPASSION: 3,
        VirtueName.CONVICTION: 2,
        VirtueName.TEMPERANCE: 4,
        VirtueName.VALOR: 1,
    })
    assert derive.two_highest_virtues(c.virtues) == 7   # 4 + 3
    assert derive.willpower(c) == 7


def test_purchased_willpower_adds_to_virtue_component():
    c = _char(
        virtues={
            VirtueName.COMPASSION: 3,
            VirtueName.CONVICTION: 2,
            VirtueName.TEMPERANCE: 4,
            VirtueName.VALOR: 1,
        },
        willpower_purchased=1,
    )
    assert derive.willpower(c) == 8


def test_locked_component_is_frozen_against_virtue_gains():
    # Locked at a component of 5; afterward a Virtue rises but WP must not.
    c = _char(
        virtues={
            VirtueName.COMPASSION: 5,
            VirtueName.CONVICTION: 5,   # current two-highest would be 10
            VirtueName.TEMPERANCE: 1,
            VirtueName.VALOR: 1,
        },
        wp_virtue_component=5,
    )
    assert derive.wp_virtue_component(c) == 5
    assert derive.willpower(c) == 5


# --------------------------------------------------------------------------- #
# Essence pools (Solar)
# --------------------------------------------------------------------------- #

def test_solar_essence_pools():
    c = _char(
        essence_rating=2,
        virtues={
            VirtueName.COMPASSION: 3,
            VirtueName.CONVICTION: 2,
            VirtueName.TEMPERANCE: 4,
            VirtueName.VALOR: 1,
        },
    )
    # WP = 7, sum of virtues = 10
    personal, peripheral = derive.essence_pools(c)
    assert personal == 2 * 3 + 7            # 13
    assert peripheral == 2 * 7 + 7 + 10     # 31


def test_essence_pools_reject_non_solar():
    c = _char(exalt_type="Lunar")
    with pytest.raises(NotImplementedError):
        derive.essence_pools(c)


# --------------------------------------------------------------------------- #
# Health track
# --------------------------------------------------------------------------- #

def test_base_health_track():
    c = _char()
    track = derive.health_track(c)
    assert len(track) == 7                              # 6 wound levels + Incap
    assert [lv.penalty for lv in track] == [0, -1, -1, -2, -2, -4, None]
    assert track[-1].incapacitated is True
    assert all(lv.source == "" for lv in track)


def test_curse_removes_a_health_level():
    c = _char(health_bonus_levels=[
        HealthLevel(penalty=-1, source_charm="curse", removed=True),
    ])
    track = derive.health_track(c)
    # base track has two -1 levels; the curse removes one.
    assert [lv.penalty for lv in track] == [0, -1, -2, -2, -4, None]


def test_ox_body_bonus_levels_merge_by_severity():
    c = _char(health_bonus_levels=[
        HealthLevel(penalty=-1, source_charm="solar.resistance.ox-body"),
        HealthLevel(penalty=-2, source_charm="solar.resistance.ox-body"),
    ])
    track = derive.health_track(c)
    assert len(track) == 9
    assert [lv.penalty for lv in track] == [0, -1, -1, -1, -2, -2, -2, -4, None]
    # The bonus -1 follows the two base -1 levels (stable order within a tier).
    ones = [lv for lv in track if lv.penalty == -1]
    assert [lv.source for lv in ones] == ["", "", "solar.resistance.ox-body"]


def test_ox_body_purchases_add_their_package_levels():
    # one "two-one" package (-1, -1) plus one "one-one-two-two" (-1, -2, -2)
    c = _char(ox_body=[
        OxBodyPurchase(variant="two-one", health_levels=[-1, -1]),
        OxBodyPurchase(variant="one-one-two-two", health_levels=[-1, -2, -2]),
    ])
    track = derive.health_track(c)
    assert [lv.penalty for lv in track] == [0, -1, -1, -1, -1, -1, -2, -2, -2, -2, -4, None]
    assert sum(1 for lv in track if lv.source == "Ox-Body Technique") == 5


# --------------------------------------------------------------------------- #
# Soak (Exalted 1e pp. 231-232)
# --------------------------------------------------------------------------- #

def _stamina(c: Character, n: int) -> Character:
    c.attributes[AttributeName.STAMINA] = n
    return c


def test_unarmored_exalt_soak():
    c = _stamina(_char(), 3)
    s = derive.soak(c)
    assert s.bashing == 3            # Stamina
    assert s.lethal == 1            # floor(3/2)
    assert s.aggravated == 0        # never from Stamina
    assert (s.natural_bashing, s.natural_lethal) == (3, 1)
    assert (s.armor_bashing, s.armor_lethal) == (0, 0)


def test_lethal_half_stamina_rounds_down():
    s = derive.soak(_stamina(_char(), 5))
    assert s.lethal == 2            # floor(5/2)


def test_armored_exalt_soak():
    c = _stamina(_char(), 3)
    c.armor = [Armor(name="Test Plate", soak_bashing=4, soak_lethal=5)]
    s = derive.soak(c)
    assert s.bashing == 3 + 4       # Stamina + armor bashing
    assert s.lethal == 1 + 5        # half Stamina + armor lethal
    assert s.aggravated == 5        # armor lethal only


def test_armor_soak_sums_across_pieces():
    c = _stamina(_char(), 2)
    c.armor = [
        Armor(name="A", soak_bashing=2, soak_lethal=1),
        Armor(name="B", soak_bashing=3, soak_lethal=4),
    ]
    s = derive.soak(c)
    assert s.armor_bashing == 5 and s.armor_lethal == 5


def test_mortal_gets_no_stamina_lethal_soak():
    c = _stamina(_char(exalt_type="Mortal"), 3)
    c.armor = [Armor(name="Buff Jacket", soak_bashing=2, soak_lethal=5)]
    s = derive.soak(c)
    assert s.bashing == 3 + 2       # mortals still soak bashing with Stamina
    assert s.lethal == 0 + 5        # but NOT lethal — armor only
    assert s.natural_lethal == 0
    assert s.aggravated == 5


# --------------------------------------------------------------------------- #
# derive() bundle
# --------------------------------------------------------------------------- #

def test_derive_bundle():
    c = _stamina(_char(
        essence_rating=2,
        virtues={
            VirtueName.COMPASSION: 3,
            VirtueName.CONVICTION: 2,
            VirtueName.TEMPERANCE: 4,
            VirtueName.VALOR: 1,
        },
    ), 3)
    d = derive.derive(ruleset=None, character=c)        # ruleset unused by these derivations
    assert d.willpower == 7
    assert d.essence_personal == 13
    assert d.essence_peripheral == 31
    assert len(d.health_levels) == 7
    assert d.soak.bashing == 3 and d.soak.lethal == 1
