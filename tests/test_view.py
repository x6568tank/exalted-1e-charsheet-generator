"""Tests for ui.view.build_sheet_view — the pure presenter. No NiceGUI import,
so these run anywhere. Exercised against the shipped ruleset and the bundled
example character, plus focused cases.
"""

from pathlib import Path

import exalted_builder
from exalted_builder import persistence, rules_db
from exalted_builder.models.character import Character, HealthLevel
from exalted_builder.models.rules import AbilityName
from exalted_builder.ui import view as viewmod

DATA_DIR = Path(exalted_builder.__file__).parent / "data"
EXAMPLE = Path(exalted_builder.__file__).parent.parent / "examples" / "ashes-of-dawn.character.json"


def _rs():
    return rules_db.load_ruleset(DATA_DIR)


def test_example_character_builds_a_clean_sheet():
    rs = _rs()
    char = persistence.load_character(EXAMPLE)
    v = viewmod.build_sheet_view(rs, char)

    assert v.name == "Ashes-of-Dawn"
    assert v.caste == "Dawn"
    assert v.willpower == 6                      # two highest Virtues 3 + 3
    assert v.essence_personal == 2 * 3 + 6       # Essence 2
    # the example is a legal chargen -> no error issues, only the BP info line
    assert [i for i in v.issues if i.severity == "error"] == []
    assert any(i.code == "bonus-points" for i in v.issues)


def test_charms_resolve_to_names_with_costs():
    rs = _rs()
    char = persistence.load_character(EXAMPLE)
    v = viewmod.build_sheet_view(rs, char)
    names = [c.name for c in v.charms]
    assert "Excellent Strike" in names           # resolved from id, not the raw id
    assert all(not n.startswith("solar.") for n in names)
    # Excellent Strike's variable cost is carried through verbatim.
    es = next(c for c in v.charms if c.name == "Excellent Strike")
    assert es.cost == "1 mote per die" and es.category == "melee"


def test_abilities_grouped_by_ability_caste_with_flags():
    rs = _rs()
    char = persistence.load_character(EXAMPLE)
    v = viewmod.build_sheet_view(rs, char)
    group_names = [name for name, _ in v.ability_groups]
    assert group_names == ["Dawn", "Zenith", "Twilight", "Night", "Eclipse"]
    by_label = {r.label: r for _, rows in v.ability_groups for r in rows}
    assert by_label["Melee"].caste is True       # Dawn caste ability
    assert by_label["Dodge"].favored is True     # a favored ability
    assert by_label["Lore"].caste is False and by_label["Lore"].favored is False


def test_health_labels_mark_charm_levels():
    rs = _rs()
    char = persistence.load_character(EXAMPLE)
    char.health_bonus_levels = [HealthLevel(penalty=-2, source_charm="ox-body")]
    v = viewmod.build_sheet_view(rs, char)
    assert v.health[0] == "-0"
    assert v.health[-1] == "Incap"
    assert any("★" in label for label in v.health)   # the bonus level is marked


def test_unknown_charm_id_falls_back_to_the_id():
    rs = _rs()
    c = Character(id="char.x")
    c.charms = ["solar.melee.does-not-exist"]
    v = viewmod.build_sheet_view(rs, c)
    assert len(v.charms) == 1
    assert v.charms[0].name == "solar.melee.does-not-exist" and v.charms[0].category == "?"
