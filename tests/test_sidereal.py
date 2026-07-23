"""Sidereal chargen foundation — exercises the shipped Sidereal data (exalts.json
Sidereal row, chargen_budgets/costs_bonus/costs_xp Sidereal rows, the 5 Maiden
castes) against the existing ability-caste machinery. Charms and the Astrological
College subsystem land in later phases, so these tests assert on the specific
pieces the foundation provides rather than a fully-clean validate_chargen (which
needs the 12-Charm pool the catalogue will supply).

Sources: The Sidereals p96-101 (Character Creation); see [[sidereal-chargen-findings]].
"""

from pathlib import Path

import pytest

import exalted_builder
from exalted_builder import rules_db
from exalted_builder.engine import costs, derive, validate
from exalted_builder.models.character import Character
from exalted_builder.models.rules import AbilityName as A
from exalted_builder.models.rules import AttributeName as AT
from exalted_builder.models.rules import VirtueName as V

DATA_DIR = Path(exalted_builder.__file__).parent / "data"


@pytest.fixture(scope="module")
def rs():
    return rules_db.load_ruleset(DATA_DIR)


def _codes(issues, code):
    return [i for i in issues if i.code == code]


def _sidereal(caste="battles") -> Character:
    """A Chosen of Battles meeting the Celestial Hierarchy ability minimums, a legal
    8/6/4 attribute spend and a full 35-dot ability spend (≥15 on Auspicious/Favored,
    ≤3 each). Auspicious (Battles): archery, brawl, melee, presence, resistance."""
    c = Character(id="sid.test", exalt_type="Sidereal", caste=caste)
    c.favored_abilities = [A.AWARENESS, A.OCCULT, A.LORE, A.STEALTH]     # 4, none Battles-auspicious
    c.attributes.update({
        AT.STRENGTH: 5, AT.DEXTERITY: 4, AT.STAMINA: 2,        # Physical spend = 8
        AT.CHARISMA: 4, AT.MANIPULATION: 3, AT.APPEARANCE: 2,  # Social spend = 6
        AT.PERCEPTION: 3, AT.INTELLIGENCE: 2, AT.WITS: 2,      # Mental spend = 4
    })
    c.abilities.update({
        A.ARCHERY: 1, A.BRAWL: 1, A.MELEE: 3, A.PRESENCE: 2, A.RESISTANCE: 2,  # auspicious = 9
        A.AWARENESS: 2, A.OCCULT: 2, A.LORE: 3, A.STEALTH: 1,                   # favored = 8
        A.BUREAUCRACY: 2, A.LINGUISTICS: 1, A.MARTIAL_ARTS: 2, A.SOCIALIZE: 1,  # other minimums = 6
        A.DODGE: 3, A.RIDE: 3, A.SAIL: 3, A.SURVIVAL: 3,                        # filler = 12  (total 35)
    })
    c.virtues.update({V.COMPASSION: 3, V.CONVICTION: 2, V.TEMPERANCE: 3, V.VALOR: 1})
    c.essence_rating = 2
    return c


def test_sidereal_essence_pools(rs):
    c = _sidereal()
    # WP = 6 (3+3, two highest Virtues). Personal = 2×2 + 6; Peripheral = 2×6 + 6 + Σ(3+2+3+1).
    assert derive.willpower(c) == 6
    assert derive.essence_pools(rs, c) == (10, 27)


def test_sidereal_five_maiden_castes(rs):
    castes = {cid: c for cid, c in rs.castes.items() if c.exalt_type == "Sidereal"}
    assert set(castes) == {"journeys", "serenity", "battles", "secrets", "endings"}
    # Auspicious Abilities are the caste abilities (p.97).
    assert set(castes["battles"].caste_abilities) == {A.ARCHERY, A.BRAWL, A.MELEE, A.PRESENCE, A.RESISTANCE}
    assert set(castes["secrets"].caste_abilities) == {A.INVESTIGATION, A.LARCENY, A.LORE, A.OCCULT, A.STEALTH}


def test_sidereal_budgets(rs):
    b = rs.budgets_for("Sidereal")
    assert b.attribute_pools == (8, 6, 4)
    assert (b.ability_dots, b.ability_min_caste_favored, b.favored_count) == (35, 15, 4)
    assert (b.charm_count, b.charm_min_caste_favored) == (12, 5)
    assert (b.background_dots, b.virtue_dots, b.bonus_points) == (15, 5, 18)
    assert len(b.required_min_abilities) == 9


def test_sidereal_bonus_and_xp_costs(rs):
    bc = rs.bonus_costs_for("Sidereal")
    assert (bc.charm, bc.charm_favored_caste) == (7, 5)
    assert bc.essence == 10
    xp = rs.xp_costs_for("Sidereal")
    assert xp.essence.coeff == 9                       # user rule (p265 omits it; Lunar's is ×9)
    assert (xp.new_charm, xp.new_charm_favored_caste) == (11, 9)   # p265


def test_sidereal_required_minimums_satisfied(rs):
    c = _sidereal()
    assert _codes(validate.validate_chargen(rs, c), "required-min-ability") == []


def test_sidereal_missing_lore_minimum_flagged(rs):
    c = _sidereal()
    c.abilities[A.LORE] = 2                            # Celestial Hierarchy floor is Lore ●●●
    assert _codes(validate.validate_chargen(rs, c), "required-min-ability") != []


def test_sidereal_auspicious_ability_gets_the_discount(rs):
    c = _sidereal()
    # Melee is a Battles Auspicious (caste) ability → discounted; Sail is neither.
    assert costs.ability_step(rs, c, A.MELEE, 2) == 3      # 2×2 − 1
    assert costs.ability_step(rs, c, A.SAIL, 2) == 4       # 2×2, full
