"""Tests over the *shipped* data files in exalted_builder/data — distinct from
test_rules_db.py, which exercises the loader on synthetic tmp_path data. These
guard the real authored content against drift.
"""

from pathlib import Path

import exalted_builder
from exalted_builder import rules_db
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
