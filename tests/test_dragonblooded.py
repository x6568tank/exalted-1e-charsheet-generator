"""Dragon-Blooded chargen: exercises the shipped DB data (exalts.json,
chargen_budgets.json, costs_bonus.json, the five Aspects) and the intra-splat
Dynastic/Outcaste origin machinery. Values are from the DB splatbook Character
Creation summary (p150-153) and the Aspect Traits pages (p164-172).
"""

from pathlib import Path

import pytest

import exalted_builder
from exalted_builder import rules_db
from exalted_builder.engine import costs, derive, validate
from exalted_builder.models.character import BackgroundEntry, Character, OxBodyPurchase
from exalted_builder.models.rules import AbilityName as A
from exalted_builder.models.rules import AttributeName as AT
from exalted_builder.models.rules import VirtueName as V
from exalted_builder.models.rules import Charm, CharmType

DATA_DIR = Path(exalted_builder.__file__).parent / "data"


@pytest.fixture(scope="module")
def rs():
    return rules_db.load_ruleset(DATA_DIR)


def _codes(issues, code):
    return [i for i in issues if i.code == code]


def _db_fire(origin="dynastic") -> Character:
    """A Fire-aspect Dragon-Blooded that MEETS the Dynastic schooling minimums
    (Archery•, Brawl/MA•, Melee•, Performance•, Presence•, Ride•, Lore••, Socialize••).
    Fire Aspect abilities: athletics, dodge, melee, presence, socialize."""
    c = Character(id="db.fire", exalt_type="Dragon-Blooded", caste="fire", origin=origin)
    c.favored_abilities = [A.ARCHERY, A.RIDE, A.LORE]           # 3, none Fire-aspect
    c.attributes.update({
        AT.STRENGTH: 4, AT.DEXTERITY: 3, AT.STAMINA: 1,        # Physical = 7
        AT.CHARISMA: 3, AT.MANIPULATION: 3, AT.APPEARANCE: 1,  # Social = 6
        AT.PERCEPTION: 3, AT.INTELLIGENCE: 1, AT.WITS: 1,      # Mental = 4
    })
    c.abilities.update({
        A.MELEE: 1, A.PRESENCE: 1, A.SOCIALIZE: 2,              # aspect
        A.PERFORMANCE: 1, A.ARCHERY: 1, A.RIDE: 1, A.LORE: 2,   # schooling + favored
        A.BRAWL: 1,                                             # brawl-or-MA
    })
    c.virtues.update({V.COMPASSION: 3, V.CONVICTION: 3, V.TEMPERANCE: 2, V.VALOR: 1})
    c.essence_rating = 2
    return c


# --- budgets ---------------------------------------------------------------- #

def test_db_budget_dynastic_vs_outcaste(rs):
    dyn = rs.budgets_for("Dragon-Blooded", "dynastic")
    out = rs.budgets_for("Dragon-Blooded", "outcaste")
    assert (dyn.ability_dots, dyn.ability_min_caste_favored) == (35, 13)
    assert (out.ability_dots, out.ability_min_caste_favored) == (25, 10)
    assert dyn.attribute_pools == (7, 6, 4)
    assert dyn.favored_count == 3 and dyn.background_dots == 12
    assert dyn.charm_count == 7 and dyn.charm_min_caste_favored == 4
    assert len(dyn.required_min_abilities) == 8 and out.required_min_abilities == []
    # default (no origin) is the Dynastic row
    assert rs.budgets_for("Dragon-Blooded").ability_dots == 35


def test_db_calls_its_caste_slot_aspect(rs):
    # the UI labels the caste slot per splat: Dragon-Blooded say "Aspect", Solar "Caste"
    assert rs.exalt_for("Dragon-Blooded").caste_noun == "Aspect"
    assert rs.exalt_for("Solar").caste_noun == "Caste"


def test_db_may_learn_terrestrial_spells_at_chargen(rs):
    # Terrestrial is the DB's only circle, so nothing is barred at creation: a DB who
    # takes the Terrestrial Circle Sorcery initiation Charm CAN learn its spells at
    # chargen. (Regression: the old "bar the top circle" default barred their only one.)
    c = _db_fire()
    c.charms = ["dragonblooded.occult.terrestrial-circle-sorcery"]
    assert validate.chargen_barred_circle(rs, c) is None
    spell = rs.spells["spell.terrestrial.death-of-obsidian-butterflies"]
    assert validate.meets_spell_requirements(rs, c, spell) is True
    # and the Solar top-circle bar is unaffected
    assert rs.exalt_for("Solar").highest_magic_circle_id == "Solar"


def test_db_bonus_costs(rs):
    bc = rs.bonus_costs_for("Dragon-Blooded")
    assert (bc.charm, bc.charm_favored_caste) == (7, 5)
    assert (bc.immaculate_charm, bc.immaculate_charm_favored_caste) == (10, 7)
    assert bc.essence == 10
    # Solar is untouched by the DB rows
    assert rs.bonus_costs_for("Solar").charm == 5 and rs.bonus_costs_for("Solar").essence == 7


# --- Dynastic schooling minimums ------------------------------------------- #

def test_db_dynastic_minimums_satisfied(rs):
    c = _db_fire("dynastic")
    assert _codes(validate.validate_chargen(rs, c), "required-min-ability") == []


def test_db_dynastic_missing_lore_flagged(rs):
    c = _db_fire("dynastic")
    c.abilities[A.LORE] = 1                       # needs Lore ••
    issues = _codes(validate.validate_chargen(rs, c), "required-min-ability")
    assert [i.where for i in issues] == ["lore"]


def test_db_brawl_or_martial_arts_is_an_or(rs):
    c = _db_fire("dynastic")
    c.abilities[A.BRAWL] = 0                       # drop Brawl...
    c.abilities[A.MARTIAL_ARTS] = 1               # ...satisfy via Martial Arts
    assert _codes(validate.validate_chargen(rs, c), "required-min-ability") == []


def test_db_outcaste_has_no_schooling_minimums(rs):
    c = _db_fire("outcaste")
    c.abilities[A.LORE] = 0                        # would fail as Dynastic
    c.abilities[A.ARCHERY] = 0
    assert _codes(validate.validate_chargen(rs, c), "required-min-ability") == []


# --- essence pools on the shipped data ------------------------------------- #

def test_db_essence_pools_from_shipped_exalt(rs):
    c = _db_fire()
    c.virtues.update({V.COMPASSION: 3, V.CONVICTION: 2, V.TEMPERANCE: 4, V.VALOR: 1})
    # WP = 7 (4+3); two highest Virtues = 7. Personal = 2+7; Peripheral = 2*4+7+7.
    assert derive.essence_pools(rs, c) == (9, 22)


def test_db_breeding_background_boosts_pools(rs):
    c = _db_fire()
    c.virtues.update({V.COMPASSION: 3, V.CONVICTION: 2, V.TEMPERANCE: 4, V.VALOR: 1})
    c.backgrounds = [BackgroundEntry(name="Breeding", rating=4)]
    # Breeding 4: +4 Personal, +7 Peripheral.
    assert derive.essence_pools(rs, c) == (9 + 4, 22 + 7)


def test_db_xp_costs_from_shipped_table(rs):
    """DB XP costs (splatbook p.292): Essence x10, new Charm/Spell 12 (10 favored),
    Immaculate Charm 15 (12 favored) — not the Solar defaults (x8, 10/8)."""
    c = _db_fire()
    assert costs.essence_step(rs, c, 2) == 20                       # 2 x 10
    plain = Charm(id="t.lore", name="Plain", category="lore",
                  exalt_type="Dragon-Blooded", type=CharmType.SIMPLE,
                  min_ability=1, min_essence=1)
    imm = Charm(id="t.imm", name="Imm", category="martial_arts:immaculate-fire-dragon",
                exalt_type="Dragon-Blooded", element="Fire", immaculate=True,
                type=CharmType.SIMPLE, min_ability=1, min_essence=1)
    c.favored_abilities = []                                        # Lore/MA/Occult not favored (nor Fire-caste)
    rs2 = rs.model_copy(update={"charms": {**rs.charms, plain.id: plain, imm.id: imm}})
    assert costs.charm_cost(rs2, c, plain) == 12                    # ordinary new Charm
    assert costs.charm_cost(rs2, c, imm) == 15                      # Immaculate full rate
    assert costs.spell_cost(rs2, c) == 12                           # new spell, Occult not favored


# --- Immaculate Order charm package (p.151) -------------------------------- #
#
# "Immaculate Order Charms" are the Fivefold Dragon Method martial-arts styles
# (DB splatbook ch.6) — one elemental tree per element. A DB may take the
# Immaculate chargen path (5 Charms, all one tree) instead of 7 DB Charms; the
# real trees aren't authored yet, so these tests layer synthetic ones on `rs`.

def _immaculate(cid: str, element: str) -> Charm:
    return Charm(id=cid, name=cid, category=f"martial_arts:immaculate-{element.lower()}-dragon",
                 exalt_type="Dragon-Blooded", element=element, immaculate=True,
                 type=CharmType.SIMPLE, min_ability=1, min_essence=1)


def _rs_with_immaculate(rs):
    """`rs` plus a Fire and a Water Immaculate tree and one ordinary DB Charm."""
    extra = {c.id: c for c in (
        [_immaculate(f"imm.fire.{i}", "Fire") for i in range(6)]
        + [_immaculate(f"imm.water.{i}", "Water") for i in range(2)]
    )}
    extra["db.melee.plain"] = Charm(
        id="db.melee.plain", name="Plain DB Melee", category="melee",
        exalt_type="Dragon-Blooded", type=CharmType.SIMPLE, min_ability=1, min_essence=1)
    return rs.model_copy(update={"charms": {**rs.charms, **extra}})


def _charm_bp(rs, c) -> int:
    line = next(l for l in validate.bonus_point_breakdown(rs, c).lines
                if l.domain == "Charms & Spells")
    return line.points


def test_immaculate_five_one_tree_is_legal(rs):
    rs2 = _rs_with_immaculate(rs)
    c = _db_fire()
    c.charms = [f"imm.fire.{i}" for i in range(5)]
    codes = {i.code for i in validate.validate_chargen(rs2, c)}
    assert "immaculate-single-tree" not in codes
    assert "charm-caste-favored-min" not in codes      # waived on the Immaculate path
    assert _charm_bp(rs2, c) == 0                       # 5 free Immaculate Charms


def test_immaculate_mixed_trees_flagged(rs):
    rs2 = _rs_with_immaculate(rs)
    c = _db_fire()
    c.charms = [f"imm.fire.{i}" for i in range(4)] + ["imm.water.0"]
    codes = {i.code for i in validate.validate_chargen(rs2, c)}
    assert "immaculate-single-tree" in codes


def test_immaculate_mixing_ordinary_charm_flagged(rs):
    rs2 = _rs_with_immaculate(rs)
    c = _db_fire()
    c.charms = [f"imm.fire.{i}" for i in range(4)] + ["db.melee.plain"]
    codes = {i.code for i in validate.validate_chargen(rs2, c)}
    assert "immaculate-single-tree" in codes


def test_immaculate_extra_charm_uses_immaculate_bp_row(rs):
    rs2 = _rs_with_immaculate(rs)
    c = _db_fire()
    # 6 Fire Immaculate Charms: 5 free, the 6th is an extra. Martial Arts is not a
    # Fire-aspect/favored Ability here, so it prices from the full Immaculate row (10).
    c.charms = [f"imm.fire.{i}" for i in range(6)]
    assert _charm_bp(rs2, c) == 10


def test_standard_db_path_still_uses_ordinary_charm_rules(rs):
    # No Immaculate Charm chosen -> ordinary path: the >=4 Caste/Favored rule applies.
    rs2 = _rs_with_immaculate(rs)
    c = _db_fire()
    c.charms = ["db.melee.plain"]                       # 0 Caste/Favored Charms
    codes = {i.code for i in validate.validate_chargen(rs2, c)}
    assert "charm-caste-favored-min" in codes
    assert "immaculate-single-tree" not in codes


# --- shipped Immaculate style trees (real data, not synthetic) ------------- #

def test_shipped_immaculate_trees_counts(rs):
    from collections import Counter
    by_el = Counter(c.element for c in rs.charms.values() if c.immaculate)
    assert by_el == Counter({"Air": 12, "Earth": 12, "Fire": 11, "Water": 12, "Wood": 12})
    for c in (x for x in rs.charms.values() if x.immaculate):
        assert c.exalt_type == "Dragon-Blooded"
        assert c.category == "martial_arts:" + c.element.lower() + "-dragon"


def test_shipped_air_dragon_immaculate_build_is_one_tree(rs):
    c = _db_fire()
    c.charms = [
        "dragonblooded.air-dragon.air-dragons-sight",
        "dragonblooded.air-dragon.wind-dragon-speed",
        "dragonblooded.air-dragon.breath-seizing-technique",
        "dragonblooded.air-dragon.shrouding-the-body-and-mind",
        "dragonblooded.air-dragon.air-dragon-form",
    ]
    assert validate.immaculate_martial_artist(rs, c)
    codes = {i.code for i in validate.validate_chargen(rs, c)}
    assert "immaculate-single-tree" not in codes
    assert "charm-caste-favored-min" not in codes      # waived on the Immaculate path


def test_shipped_cross_tree_immaculate_flagged(rs):
    c = _db_fire()
    c.charms = [
        "dragonblooded.air-dragon.air-dragons-sight",
        "dragonblooded.fire-dragon.flash-fire-technique",
    ]
    codes = {i.code for i in validate.validate_chargen(rs, c)}
    assert "immaculate-single-tree" in codes


def test_immaculate_path_allows_enlightenment_charms(rs):
    # The Enlightenment Charms (Spirit Sight / Spirit Walking) are part of Immaculate
    # martial arts — the required entry to any Dragon Path (p241-242) — so they do NOT
    # trip the single-tree rule alongside one elemental tree.
    c = _db_fire()
    c.charms = [
        "dragonblooded.martial-arts.spirit-sight",
        "dragonblooded.martial-arts.spirit-walking",
        "dragonblooded.air-dragon.air-dragons-sight",
        "dragonblooded.air-dragon.wind-dragon-speed",
        "dragonblooded.air-dragon.breath-seizing-technique",
        "dragonblooded.air-dragon.shrouding-the-body-and-mind",
        "dragonblooded.air-dragon.air-dragon-form",
    ]
    assert validate.immaculate_martial_artist(rs, c)
    codes = {i.code for i in validate.validate_chargen(rs, c)}
    assert "immaculate-single-tree" not in codes
    # NOT free/exempt: the two enlightenment Charms still consume Charm picks, so with
    # 7 picks against the 5-Immaculate free pool the overflow costs bonus points.
    assert _charm_bp(rs, c) > 0


def test_enlightenment_charms_do_not_rescue_a_mixed_tree(rs):
    # Adding enlightenment must not mask a genuine cross-tree violation.
    c = _db_fire()
    c.charms = [
        "dragonblooded.martial-arts.spirit-sight",
        "dragonblooded.martial-arts.spirit-walking",
        "dragonblooded.air-dragon.air-dragons-sight",
        "dragonblooded.fire-dragon.flash-fire-technique",
    ]
    codes = {i.code for i in validate.validate_chargen(rs, c)}
    assert "immaculate-single-tree" in codes


# --- Dragon-Blooded Ox-Body Technique (Earth/Endurance, p195) -------------- #
#
# DB Ox-Body has no variant menu: each purchase is a fixed one -1 + one -2, and
# it may be bought once per dot of Endurance. The Phase-5 exalt row already names
# it as the DB ox_body_charm_id; this data resolves that reference.

def test_shipped_db_ox_body_resolves_caps_and_folds_in(rs):
    c = Character(id="db.ox", exalt_type="Dragon-Blooded", caste="earth", essence_rating=2)
    c.abilities[A.ENDURANCE] = 2
    assert validate.ox_body_charm(rs, c).id == "dragonblooded.endurance.ox-body-technique"
    assert validate.ox_body_cap(rs, c) == 2                 # once per Endurance dot
    base = len(derive.health_track(c))
    c.ox_body = [OxBodyPurchase(variant="db-standard", health_levels=[-1, -2])] * 2
    assert len(derive.health_track(c)) == base + 4          # each purchase adds -1 and -2
    assert validate.check_ox_body(rs, c) == []
    c.ox_body.append(OxBodyPurchase(variant="db-standard", health_levels=[-1, -2]))
    assert any(i.code == "ox-body-over-cap" for i in validate.check_ox_body(rs, c))


# --- shipped DB ability charm trees (Charms chapter, element->ability) ------ #

def test_shipped_db_air_ability_charm_counts(rs):
    from collections import Counter
    air = [c for c in rs.charms.values()
           if c.exalt_type == "Dragon-Blooded" and c.element == "Air" and not c.immaculate]
    assert Counter(c.category for c in air) == Counter(
        {"linguistics": 7, "lore": 6, "occult": 6, "stealth": 7, "thrown": 8})
    # all ability charms carry element but are not Immaculate MA
    for c in air:
        assert ":" not in c.category and c.immaculate is False


def test_shipped_db_earth_ability_charm_counts(rs):
    from collections import Counter
    earth = [c for c in rs.charms.values()
             if c.exalt_type == "Dragon-Blooded" and c.element == "Earth" and not c.immaculate]
    assert Counter(c.category for c in earth) == Counter(
        {"awareness": 7, "craft": 6, "endurance": 7,
         "martial_arts:five-dragon": 8, "resistance": 6})


def test_shipped_db_fire_ability_charm_counts(rs):
    from collections import Counter
    fire = [c for c in rs.charms.values()
            if c.exalt_type == "Dragon-Blooded" and c.element == "Fire" and not c.immaculate]
    assert Counter(c.category for c in fire) == Counter(
        {"athletics": 8, "dodge": 8, "melee": 8, "presence": 7, "socialize": 8})


def test_shipped_db_water_ability_charm_counts(rs):
    from collections import Counter
    water = [c for c in rs.charms.values()
             if c.exalt_type == "Dragon-Blooded" and c.element == "Water" and not c.immaculate]
    assert Counter(c.category for c in water) == Counter(
        {"brawl": 7, "bureaucracy": 7, "investigation": 6, "larceny": 7, "sail": 5})
    for c in water:
        assert ":" not in c.category and c.immaculate is False


def test_shipped_db_wood_ability_charm_counts(rs):
    from collections import Counter
    wood = [c for c in rs.charms.values()
            if c.exalt_type == "Dragon-Blooded" and c.element == "Wood" and not c.immaculate]
    assert Counter(c.category for c in wood) == Counter(
        {"archery": 7, "medicine": 7, "performance": 5, "ride": 7, "survival": 7})
    for c in wood:
        assert ":" not in c.category and c.immaculate is False


def test_shipped_db_terrestrial_sorcery_grants_circle(rs):
    from exalted_builder.models.rules import SpellCircle
    c = Character(id="db.sorc", exalt_type="Dragon-Blooded", caste="air", essence_rating=3)
    c.abilities[A.OCCULT] = 3
    c.charms = ["dragonblooded.occult.terrestrial-circle-sorcery"]
    assert SpellCircle.TERRESTRIAL in validate.granted_circles(rs, c)
