"""Tests over the *shipped* data files in exalted_builder/data — distinct from
test_rules_db.py, which exercises the loader on synthetic tmp_path data. These
guard the real authored content against drift.
"""

from pathlib import Path

import exalted_builder
from exalted_builder import rules_db
from exalted_builder.engine import validate
from exalted_builder.models.character import Character
from exalted_builder.models.rules import AbilityName, Caste

DATA_DIR = Path(exalted_builder.__file__).parent / "data"


def test_shipped_ruleset_loads():
    rs = rules_db.load_ruleset(DATA_DIR)
    assert set(rs.castes) == set(Caste)        # all five castes present


def test_caste_abilities_partition_the_roster():
    """Every one of the 25 abilities belongs to exactly one caste (no gaps, no
    overlaps) — the 1e caste-grouped roster."""
    rs = rules_db.load_ruleset(DATA_DIR)
    all_caste_abilities = [a for cd in rs.castes.values() for a in cd.caste_abilities]
    assert len(all_caste_abilities) == 25
    assert set(all_caste_abilities) == set(AbilityName)   # exact partition
    assert all(len(cd.caste_abilities) == 5 for cd in rs.castes.values())


def test_each_caste_keyed_by_its_own_enum():
    rs = rules_db.load_ruleset(DATA_DIR)
    assert all(caste == cd.caste for caste, cd in rs.castes.items())


# --------------------------------------------------------------------------- #
# Solar Melee charms
# --------------------------------------------------------------------------- #

def test_melee_charm_tree_loads_with_intact_prerequisites():
    # load_ruleset itself link-checks prerequisites; reaching here means the whole
    # tree resolves. Confirm the expected shape.
    rs = rules_db.load_ruleset(DATA_DIR)
    melee = [c for c in rs.charms.values() if c.category == "melee"]
    assert len(melee) == 22
    roots = {c.name for c in melee if not c.prerequisites}
    assert roots == {"Excellent Strike", "Retrieve the Fallen Weapon",
                     "Golden Essence Block"}


def test_blazing_solar_bolt_requires_both_branches():
    rs = rules_db.load_ruleset(DATA_DIR)
    bolt = rs.charms["solar.melee.blazing-solar-bolt"]
    # AND-of-OR: two separate single-id groups => both required.
    assert bolt.prerequisites == [["solar.melee.corona-of-radiance"],
                                  ["solar.melee.sandstorm-wind-attack"]]


def test_deep_melee_charm_flags_missing_prerequisites_on_real_data():
    rs = rules_db.load_ruleset(DATA_DIR)
    c = Character(id="char.melee")
    c.abilities[AbilityName.MELEE] = 3
    c.essence_rating = 2
    c.charms = ["solar.melee.fire-and-stones-strike"]   # skips the two charms below it
    codes = {i.code for i in validate.check_charm_prerequisites(rs, c)}
    assert "charm-prerequisite" in codes


def test_full_melee_chain_is_legal_on_real_data():
    rs = rules_db.load_ruleset(DATA_DIR)
    c = Character(id="char.melee")
    c.abilities[AbilityName.MELEE] = 3
    c.essence_rating = 2
    c.charms = ["solar.melee.excellent-strike",
                "solar.melee.hungry-tiger-technique",
                "solar.melee.fire-and-stones-strike"]
    assert validate.check_charm_prerequisites(rs, c) == []
