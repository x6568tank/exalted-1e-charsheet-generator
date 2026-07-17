"""Tests for rules_db.load_ruleset: a clean load, and each referential-integrity
failure it is supposed to catch. Data is written into pytest's tmp_path so the
tests are self-contained and need no committed fixtures.
"""

import json
from pathlib import Path

import pytest

from exalted_builder.rules_db import RuleDataError, load_ruleset


def _write_clean_set(d: Path) -> None:
    """A minimal but valid data set: two linked Occult charms (one granting the
    Terrestrial circle) and a Terrestrial spell that is therefore reachable."""
    (d / "charms").mkdir(parents=True)
    (d / "castes.json").write_text(json.dumps([
        {"id": "twilight", "exalt_type": "Solar", "label": "Twilight",
         "caste_abilities": ["craft", "investigation", "lore", "medicine", "occult"]},
    ]))
    (d / "charms" / "occult.json").write_text(json.dumps([
        {"id": "t", "name": "Terrestrial Circle Sorcery", "category": "occult",
         "type": "Permanent", "min_ability": 3, "min_essence": 1,
         "grants_circle": "Terrestrial"},
        {"id": "c", "name": "Celestial Circle Sorcery", "category": "occult",
         "type": "Permanent", "min_ability": 4, "min_essence": 3,
         "prerequisites": [["t"]], "grants_circle": "Celestial"},
    ]))
    (d / "spells.json").write_text(json.dumps([
        {"id": "s1", "name": "A Terrestrial Spell", "circle": "Terrestrial"},
    ]))


def test_clean_load(tmp_path):
    _write_clean_set(tmp_path)
    rs = load_ruleset(tmp_path)
    assert len(rs.charms) == 2
    assert len(rs.spells) == 1
    # optional tables fall back to model defaults under the "default" splat key
    assert rs.bonus_costs_for("Solar").attribute == 4
    assert rs.budgets_for("Solar").attribute_pools == (8, 6, 4)


def test_keyed_budget_table_per_splat(tmp_path):
    """A per-Exalt-type chargen_budgets.json map loads each splat's table; the
    *_for accessor returns the splat's entry, else falls back to "default"."""
    _write_clean_set(tmp_path)
    (tmp_path / "chargen_budgets.json").write_text(json.dumps({
        "default": {"bonus_points": 15},
        "Abyssal": {"bonus_points": 21},
    }))
    rs = load_ruleset(tmp_path)
    assert rs.budgets_for("Abyssal").bonus_points == 21      # splat-specific entry
    assert rs.budgets_for("Solar").bonus_points == 15        # falls back to "default"


def test_legacy_bare_budget_object_wraps_under_default(tmp_path):
    """A legacy single-object chargen_budgets.json (the old shape) is wrapped under
    the "default" key so every splat reads it."""
    _write_clean_set(tmp_path)
    (tmp_path / "chargen_budgets.json").write_text(json.dumps({"bonus_points": 18}))
    rs = load_ruleset(tmp_path)
    assert rs.budgets_for("Solar").bonus_points == 18
    assert rs.budgets_for("Abyssal").bonus_points == 18      # fallback to default


def test_dangling_prerequisite_is_caught(tmp_path):
    _write_clean_set(tmp_path)
    (tmp_path / "charms" / "bad.json").write_text(json.dumps([
        {"id": "b", "name": "Bad", "category": "melee", "type": "Supplemental",
         "min_ability": 1, "min_essence": 1, "prerequisites": [["does-not-exist"]]},
    ]))
    with pytest.raises(RuleDataError) as ei:
        load_ruleset(tmp_path)
    assert any("does-not-exist" in p for p in ei.value.problems)


def test_unreachable_spell_circle_is_caught(tmp_path):
    _write_clean_set(tmp_path)
    # a Solar-circle spell, but nothing grants the Solar circle
    (tmp_path / "spells.json").write_text(json.dumps([
        {"id": "s2", "name": "Solar Spell", "circle": "Solar"},
    ]))
    with pytest.raises(RuleDataError) as ei:
        load_ruleset(tmp_path)
    assert any("Solar circle" in p for p in ei.value.problems)


def test_duplicate_charm_id_is_caught(tmp_path):
    _write_clean_set(tmp_path)
    (tmp_path / "charms" / "dup.json").write_text(json.dumps([
        {"id": "t", "name": "Duplicate", "category": "occult", "type": "Permanent",
         "min_ability": 1, "min_essence": 1, "grants_circle": "Terrestrial"},
    ]))
    with pytest.raises(RuleDataError) as ei:
        load_ruleset(tmp_path)
    assert any("duplicate charm id" in p for p in ei.value.problems)


def test_all_problems_reported_together(tmp_path):
    """Errors accumulate rather than failing on the first one."""
    _write_clean_set(tmp_path)
    (tmp_path / "charms" / "bad.json").write_text(json.dumps([
        {"id": "b1", "name": "Bad1", "category": "melee", "type": "Supplemental",
         "min_ability": 1, "min_essence": 1, "prerequisites": [["ghost-1"]]},
        {"id": "b2", "name": "Bad2", "category": "melee", "type": "Supplemental",
         "min_ability": 1, "min_essence": 1, "prerequisites": [["ghost-2"]]},
    ]))
    with pytest.raises(RuleDataError) as ei:
        load_ruleset(tmp_path)
    assert sum("ghost" in p for p in ei.value.problems) == 2
