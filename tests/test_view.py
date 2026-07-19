"""Tests for ui.view.build_sheet_view — the pure presenter. No NiceGUI import,
so these run anywhere. Exercised against the shipped ruleset and the bundled
example character, plus focused cases.
"""

from pathlib import Path

import exalted_builder
from exalted_builder import persistence, rules_db
from exalted_builder.models.character import Character, Combo, HealthLevel, XpEntry
from exalted_builder.models.rules import (
    AbilityName, CasteDefinition, Charm, CharmType, RuleSet)
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


def test_sorcery_charms_carry_per_circle_casting_time():
    # p.216 casting time rides on the circle-granting Sorcery CHARM (which unlocks that
    # circle's spells), not on each spell: Terrestrial 1 / Celestial 2 / Solar 3 turns.
    rs = _rs()
    cases = {
        "solar.occult.terrestrial-circle-sorcery": "1 turn of shaping",
        "solar.occult.celestial-circle-sorcery": "2 turns of shaping",
        "solar.occult.solar-circle-sorcery": "3 turns of shaping",
    }
    for cid, expected in cases.items():
        c = Character(id="x", caste="twilight")
        c.charms = [cid]
        row = next(r for r in viewmod.build_sheet_view(rs, c).charms
                   if r.name == rs.charms[cid].name)
        assert expected in row.description
        assert row.description.startswith(rs.charms[cid].description)


def test_non_sorcery_charms_and_spells_get_no_casting_time_note():
    # ordinary Charms and spells are untouched — the note is only on circle-granters.
    rs = _rs()
    c = Character(id="x", caste="dawn")
    c.charms = ["solar.melee.fire-and-stones-strike"]
    c.spells = ["spell.terrestrial.death-of-obsidian-butterflies"]
    v = viewmod.build_sheet_view(rs, c)
    assert "shaping" not in v.charms[0].description
    assert "shaping" not in v.spells[0].description        # spells keep their own text


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


def test_spell_picker_states_track_circle_access():
    rs = _rs()
    c = Character(id="char.sorc")
    # No Sorcery Charm yet: every spell is locked with a reason.
    rows = viewmod.build_spell_picker(rs, c)
    assert rows and all(not r.available and not r.owned and r.reason for r in rows)
    # ordered Terrestrial -> Celestial -> Solar
    circles = [r.circle for r in rows]
    assert circles == sorted(circles, key=["Terrestrial", "Celestial", "Solar"].index)

    # Learn Terrestrial Circle Sorcery: Terrestrial spells become available,
    # higher circles stay locked, Solar is always barred at chargen.
    c.charms = ["solar.occult.terrestrial-circle-sorcery"]
    by_circle: dict[str, list] = {}
    for r in viewmod.build_spell_picker(rs, c):
        by_circle.setdefault(r.circle, []).append(r)
    assert all(r.available for r in by_circle["Terrestrial"])
    assert all(not r.available for r in by_circle["Celestial"])
    assert all(not r.available and "Solar" in r.reason for r in by_circle["Solar"])


def test_spell_picker_marks_owned_spells():
    rs = _rs()
    c = Character(id="char.sorc")
    c.charms = ["solar.occult.terrestrial-circle-sorcery"]
    owned_id = next(s.id for s in rs.spells.values() if s.circle.value == "Terrestrial")
    c.spells = [owned_id]
    row = next(r for r in viewmod.build_spell_picker(rs, c) if r.id == owned_id)
    assert row.owned and not row.reason


def test_combo_view_wires_members_cost_and_eligibility():
    rs = _rs()
    char = persistence.load_character(EXAMPLE)
    base = viewmod.build_combo_view(rs, char)
    assert base.combos == [] and base.total_cost == 0
    elig = [m.id for m in base.addable]
    assert len(elig) >= 2                        # the example knows instant-duration Charms
    char.combos = [Combo(name="Twin Fang", charm_ids=elig[:2])]
    v = viewmod.build_combo_view(rs, char)
    crow = v.combos[0]
    assert crow.name == "Twin Fang" and crow.cost == 2 and v.total_cost == 2
    assert [m.id for m in crow.members] == elig[:2]
    assert all(not m.name.startswith("solar.") for m in crow.members)   # resolved to names
    assert isinstance(crow.issues, list)


def test_xp_log_presenter_labels_entries():
    rs = _rs()
    char = persistence.load_character(EXAMPLE)
    cid = char.charms[0]
    char.xp_log = [
        XpEntry(target="abilities.melee", from_rating=2, to_rating=3, cost=4),
        XpEntry(target="charms", detail=cid, cost=8),
        XpEntry(target="willpower", from_rating=6, to_rating=7, cost=12),
        XpEntry(target="specialties", detail="melee:Swords", cost=3),
    ]
    rows = viewmod.build_xp_log(rs, char)
    assert rows[0].label == "Melee 2 → 3" and rows[0].cost == 4 and rows[0].detail == "abilities"
    assert rows[1].label == f"Charm: {rs.charms[cid].name}"
    assert rows[2].label == "Willpower 6 → 7"
    assert rows[3].label == "Specialty: melee — Swords"


def test_spell_detail_reflects_circle_access():
    rs = _rs()
    c = Character(id="char.sd")
    sid = next(s.id for s in rs.spells.values() if s.circle.value == "Terrestrial")
    d = viewmod.build_spell_detail(rs, c, sid)
    assert d is not None and d.circle == "Terrestrial"
    assert d.owned is False and d.available is False          # no Sorcery Charm yet
    c.charms = ["solar.occult.terrestrial-circle-sorcery"]
    assert viewmod.build_spell_detail(rs, c, sid).available is True
    assert viewmod.build_spell_detail(rs, c, "nope") is None


def test_unknown_charm_id_falls_back_to_the_id():
    rs = _rs()
    c = Character(id="char.x")
    c.charms = ["solar.melee.does-not-exist"]
    v = viewmod.build_sheet_view(rs, c)
    assert len(v.charms) == 1
    assert v.charms[0].name == "solar.melee.does-not-exist" and v.charms[0].category == "?"


def test_charm_graph_shows_only_the_characters_splat():
    """build_charm_graph filters a category's nodes to the character's Exalt type,
    so a Solar sees Solar Melee Charms and a Dragon-Blooded sees DB Melee Charms."""
    rs = RuleSet(
        castes={"dawn": CasteDefinition(id="dawn", label="Dawn",
                                        caste_abilities=[AbilityName.MELEE])},
        charms={
            "s": Charm(id="s", name="Solar Strike", category="melee",
                       type=CharmType.SIMPLE, min_ability=1, min_essence=1),
            "d": Charm(id="d", name="Terrestrial Strike", category="melee",
                       exalt_type="Dragon-Blooded",
                       type=CharmType.SIMPLE, min_ability=1, min_essence=1),
        },
    )
    solar_ids = {n.id for n in viewmod.build_charm_graph(rs, Character(id="s"), "melee").nodes}
    assert solar_ids == {"s"}
    db = Character(id="d", exalt_type="Dragon-Blooded")
    db_ids = {n.id for n in viewmod.build_charm_graph(rs, db, "melee").nodes}
    assert db_ids == {"d"}
