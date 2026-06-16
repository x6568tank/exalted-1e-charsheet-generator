"""Tests for magical-material weapon/armour bonuses (core p.341).

A material's stat bonus applies ONLY in the hands of its resonant Exalt type
(Exalt-gated, per the page): an orichalcum weapon aids a Solar but a jade one
does not. Values are loaded from data/materials.json, not hard-coded here.
"""

from pathlib import Path

import exalted_builder
from exalted_builder import rules_db
from exalted_builder.engine import derive
from exalted_builder.models.character import Armor, Character, Weapon

DATA_DIR = Path(exalted_builder.__file__).parent / "data"


def _rs():
    return rules_db.load_ruleset(DATA_DIR)


def test_material_catalog_loaded():
    rs = _rs()
    assert "orichalcum" in rs.material_catalog
    assert rs.material_catalog["orichalcum"].exalt_type == "Solar"


def test_orichalcum_aids_a_solar():
    rs = _rs()
    c = Character(id="c", exalt_type="Solar")
    w = Weapon(name="Daiklave", speed=4, accuracy=2, damage=6, defense=1, material="orichalcum")
    eff = derive.effective_weapon(rs, c, w)
    assert (eff.speed, eff.accuracy, eff.damage, eff.defense) == (5, 3, 6, 2)  # +1 spd/acc/def
    assert derive.applied_material(rs, c, w).id == "orichalcum"


def test_jade_does_not_aid_a_solar():
    rs = _rs()
    c = Character(id="c", exalt_type="Solar")
    w = Weapon(name="Jade Daiklave", speed=4, accuracy=2, damage=6, defense=1, material="jade")
    eff = derive.effective_weapon(rs, c, w)
    assert (eff.speed, eff.accuracy, eff.damage, eff.defense) == (4, 2, 6, 1)  # unchanged
    assert derive.applied_material(rs, c, w) is None


def test_starmetal_aids_a_sidereal():
    rs = _rs()
    c = Character(id="c", exalt_type="Sidereal")
    w = Weapon(name="Starmetal Blade", damage=5, material="starmetal")
    assert derive.effective_weapon(rs, c, w).damage == 7  # +2 damage


def test_mundane_weapon_unchanged():
    rs = _rs()
    c = Character(id="c", exalt_type="Solar")
    w = Weapon(name="Sword", speed=4, accuracy=2, damage=6)
    eff = derive.effective_weapon(rs, c, w)
    assert (eff.speed, eff.accuracy, eff.damage) == (4, 2, 6)
    assert derive.applied_material(rs, c, w) is None


def test_unknown_material_id_is_inert():
    rs = _rs()
    c = Character(id="c", exalt_type="Solar")
    w = Weapon(name="Sword", accuracy=2, material="adamant")
    assert derive.effective_weapon(rs, c, w).accuracy == 2
    assert derive.applied_material(rs, c, w) is None


def test_orichalcum_armor_adds_two_to_both_soaks_for_a_solar():
    rs = _rs()
    c = Character(id="c", exalt_type="Solar")
    a = Armor(name="Articulated Plate", soak_lethal=12, soak_bashing=14, material="orichalcum")
    eff = derive.effective_armor(rs, c, a)
    assert (eff.soak_lethal, eff.soak_bashing) == (14, 16)


def test_soulsteel_armor_adds_two_to_both_soaks_for_an_abyssal():
    rs = _rs()
    c = Character(id="c", exalt_type="Abyssal")
    a = Armor(name="Plate", soak_lethal=10, soak_bashing=9, material="soulsteel")
    eff = derive.effective_armor(rs, c, a)
    assert (eff.soak_lethal, eff.soak_bashing) == (12, 11)


def test_moonsilver_armor_negates_mobility_for_a_lunar():
    rs = _rs()
    c = Character(id="c", exalt_type="Lunar")
    a = Armor(name="Lune Plate", mobility_penalty=-2, fatigue=2, material="moonsilver")
    eff = derive.effective_armor(rs, c, a)
    assert eff.mobility_penalty == 0 and eff.fatigue == 2     # fatigue untouched


def test_jade_armor_negates_fatigue_for_a_terrestrial():
    rs = _rs()
    c = Character(id="c", exalt_type="Dragon-Blooded")
    a = Armor(name="Jade Plate", mobility_penalty=-2, fatigue=2, material="jade")
    eff = derive.effective_armor(rs, c, a)
    assert eff.fatigue == 0 and eff.mobility_penalty == -2    # mobility untouched


def test_armor_material_is_exalt_gated():
    rs = _rs()
    c = Character(id="c", exalt_type="Solar")                 # a Solar in jade armor
    a = Armor(name="Jade Plate", soak_lethal=8, fatigue=2, material="jade")
    eff = derive.effective_armor(rs, c, a)
    assert (eff.soak_lethal, eff.fatigue) == (8, 2)           # no bonus for a Solar


def test_soak_with_ruleset_folds_armor_material():
    # soak() with a ruleset routes armour through effective_armor (Exalt-gated).
    rs = _rs()
    c = Character(id="c", exalt_type="Solar")
    c.armor = [Armor(name="Plate", soak_lethal=5, soak_bashing=4, material="orichalcum")]
    s = derive.soak(c, rs)
    assert s.armor_lethal == 7 and s.armor_bashing == 6       # +2/+2 orichalcum
    # Without the ruleset, the material bonus is not applied (base stats only).
    assert derive.soak(c).armor_lethal == 5
