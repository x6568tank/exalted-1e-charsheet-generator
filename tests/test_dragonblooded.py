"""Dragon-Blooded chargen: exercises the shipped DB data (exalts.json,
chargen_budgets.json, costs_bonus.json, the five Aspects) and the intra-splat
Dynastic/Outcaste origin machinery. Values are from the DB splatbook Character
Creation summary (p150-153) and the Aspect Traits pages (p164-172).
"""

from pathlib import Path

import pytest

import exalted_builder
from exalted_builder import rules_db
from exalted_builder.engine import derive, validate
from exalted_builder.models.character import BackgroundEntry, Character
from exalted_builder.models.rules import AbilityName as A
from exalted_builder.models.rules import AttributeName as AT
from exalted_builder.models.rules import VirtueName as V

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
