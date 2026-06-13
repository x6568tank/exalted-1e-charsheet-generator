"""Tests over the *shipped* data files in exalted_builder/data — distinct from
test_rules_db.py, which exercises the loader on synthetic tmp_path data. These
guard the real authored content against drift.
"""

from pathlib import Path

import exalted_builder
from exalted_builder import rules_db
from exalted_builder.engine import validate
from exalted_builder.models.character import Character
from exalted_builder.models.rules import AbilityName, Caste, SpellCircle

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


def test_background_catalog_has_the_ten_core_backgrounds():
    rs = rules_db.load_ruleset(DATA_DIR)
    names = {b.name for b in rs.background_catalog.values()}
    assert names == {"Allies", "Artifact", "Backing", "Contacts", "Familiar",
                     "Followers", "Influence", "Manse", "Mentor", "Resources"}


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


def test_dawn_caste_charm_trees_load_with_expected_counts():
    from collections import Counter
    rs = rules_db.load_ruleset(DATA_DIR)
    cats = Counter(c.category for c in rs.charms.values())
    assert cats["archery"] == 12
    assert cats["brawl"] == 10
    assert cats["thrown"] == 9
    assert cats["martial_arts:snake"] == 10
    assert cats["melee"] == 22


def test_snake_style_charms_gate_on_martial_arts_ability():
    rs = rules_db.load_ruleset(DATA_DIR)
    c = Character(id="c.snake")
    c.essence_rating = 2
    c.charms = ["solar.martial-arts.striking-cobra-technique",
                "solar.martial-arts.serpentine-evasion",
                "solar.martial-arts.snake-form"]   # Snake Form needs Martial Arts 4
    c.abilities[AbilityName.MARTIAL_ARTS] = 4
    assert validate.check_charm_prerequisites(rs, c) == []
    c.abilities[AbilityName.MARTIAL_ARTS] = 3
    assert any(i.code == "charm-min-ability"
               for i in validate.check_charm_prerequisites(rs, c))


def test_build_charm_detail_shows_requirements_and_named_prereqs():
    from exalted_builder.ui import view as viewmod
    rs = rules_db.load_ruleset(DATA_DIR)
    c = Character(id="c.detail")
    c.abilities[AbilityName.MELEE] = 5
    c.essence_rating = 3
    c.charms = ["solar.melee.corona-of-radiance", "solar.melee.sandstorm-wind-attack"]
    d = viewmod.build_charm_detail(rs, c, "solar.melee.blazing-solar-bolt")
    assert d.name == "Blazing Solar Bolt"
    assert d.requirement == "Melee 5, Essence 3"
    assert d.prerequisite_groups == [["Corona of Radiance"], ["Sandstorm-Wind Attack"]]
    assert d.available is True and d.owned is False
    assert viewmod.build_charm_detail(rs, c, "nope") is None


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


# --------------------------------------------------------------------------- #
# Spells + sorcery circles
# --------------------------------------------------------------------------- #

def test_spells_load_with_expected_circle_counts():
    rs = rules_db.load_ruleset(DATA_DIR)
    assert len(rs.spells) == 19
    by_circle = {circle: 0 for circle in SpellCircle}
    for s in rs.spells.values():
        by_circle[s.circle] += 1
    assert by_circle == {SpellCircle.TERRESTRIAL: 9,
                         SpellCircle.CELESTIAL: 6,
                         SpellCircle.SOLAR: 4}


def test_each_circle_is_granted_by_its_sorcery_charm():
    # load_ruleset would raise if any spell's circle were ungranted; assert the
    # mapping explicitly too.
    rs = rules_db.load_ruleset(DATA_DIR)
    grants = {c.grants_sorcery_circle for c in rs.charms.values()
              if c.grants_sorcery_circle is not None}
    assert grants == set(SpellCircle)


def _sorcerer(charms) -> Character:
    c = Character(id="char.sorc")
    c.abilities[AbilityName.OCCULT] = 5
    c.essence_rating = 5
    c.charms = list(charms)
    return c


def test_terrestrial_initiate_cannot_cast_celestial_spell():
    rs = rules_db.load_ruleset(DATA_DIR)
    c = _sorcerer(["solar.occult.terrestrial-circle-sorcery"])
    c.spells = ["spell.celestial.travel-without-distance"]
    codes = {i.code for i in validate.check_spell_access(rs, c)}
    assert "spell-circle" in codes


def test_celestial_initiate_casts_both_circles_via_prereq_chain():
    # Knowing Celestial Circle Sorcery requires Terrestrial Circle Sorcery, so the
    # character holds both Charms and can cast spells of both circles.
    rs = rules_db.load_ruleset(DATA_DIR)
    c = _sorcerer(["solar.occult.terrestrial-circle-sorcery",
                   "solar.occult.celestial-circle-sorcery"])
    c.spells = ["spell.terrestrial.death-of-obsidian-butterflies",
                "spell.celestial.travel-without-distance"]
    assert validate.check_spell_access(rs, c) == []


# --------------------------------------------------------------------------- #
# Weapon and armour catalogs (mundane + artifact)
# --------------------------------------------------------------------------- #

def test_weapon_and_armor_catalogs_load():
    rs = rules_db.load_ruleset(DATA_DIR)
    assert len(rs.weapon_catalog) == 49
    assert len(rs.armor_catalog) == 17


def test_mundane_melee_weapons_present():
    rs = rules_db.load_ruleset(DATA_DIR)
    sledge = rs.weapon_catalog["weapon.melee.sledge"]
    assert (sledge.speed, sledge.damage, sledge.min_strength) == (-6, 10, 4)
    # impact weapons are lethal in 1e (per the page, not intuition)
    assert rs.weapon_catalog["weapon.melee.mace"].damage_type == "L"
    # a martial-arts weapon carries Dex + Martial Arts minimums
    sss = rs.weapon_catalog["weapon.melee.seven_section_staff"]
    assert sss.min_dexterity == 4 and sss.min_martial_arts == 4


def test_artifact_weapon_attunement_costs():
    rs = rules_db.load_ruleset(DATA_DIR)
    w = rs.weapon_catalog
    assert w["weapon.melee.daiklave"].attunement == 5
    assert w["weapon.melee.grand_daiklave"].attunement == 8
    assert w["weapon.melee.goremaul"].artifact_rating == 1
    assert w["weapon.archery.long_powerbow"].attunement == 7


# --------------------------------------------------------------------------- #
# Charm eligibility + picker graph (real Melee data)
# --------------------------------------------------------------------------- #

def test_meets_charm_requirements_gates_on_ability_essence_and_prereqs():
    rs = rules_db.load_ruleset(DATA_DIR)
    fire = rs.charms["solar.melee.fire-and-stones-strike"]   # Melee 3, prereq Hungry Tiger

    low = Character(id="c.low")
    low.abilities[AbilityName.MELEE] = 2                     # below Melee 3
    low.essence_rating = 5
    low.charms = ["solar.melee.hungry-tiger-technique"]
    assert validate.meets_charm_requirements(rs, low, fire) is False

    no_prereq = Character(id="c.np")
    no_prereq.abilities[AbilityName.MELEE] = 3
    no_prereq.essence_rating = 2                            # has ability, lacks the prereq charm
    assert validate.meets_charm_requirements(rs, no_prereq, fire) is False

    ok = Character(id="c.ok")
    ok.abilities[AbilityName.MELEE] = 3
    ok.essence_rating = 2
    ok.charms = ["solar.melee.hungry-tiger-technique"]
    assert validate.meets_charm_requirements(rs, ok, fire) is True


def test_charms_depending_on_blocks_removing_a_load_bearing_charm():
    rs = rules_db.load_ruleset(DATA_DIR)
    c = Character(id="c.dep")
    c.charms = ["solar.melee.golden-essence-block",     # prereq of dipping-swallow
                "solar.melee.dipping-swallow-defense"]
    # Golden Essence Block is load-bearing -> removing it would orphan Dipping Swallow.
    assert validate.charms_depending_on(rs, c, "solar.melee.golden-essence-block") \
        == ["Dipping Swallow Defense"]
    # The leaf is safe to remove.
    assert validate.charms_depending_on(rs, c, "solar.melee.dipping-swallow-defense") == []


def test_prerequisite_error_names_the_charm_not_the_id():
    rs = rules_db.load_ruleset(DATA_DIR)
    c = Character(id="c.orphan")
    c.abilities[AbilityName.MELEE] = 2
    c.essence_rating = 2
    c.charms = ["solar.melee.dipping-swallow-defense"]   # missing its prereq
    issue = next(i for i in validate.check_charm_prerequisites(rs, c)
                 if i.code == "charm-prerequisite")
    assert "Golden Essence Block" in issue.message       # name, not the raw id
    assert "solar.melee." not in issue.message


def test_build_charm_graph_tags_owned_available_and_locked():
    from exalted_builder.ui import view as viewmod
    rs = rules_db.load_ruleset(DATA_DIR)
    c = Character(id="c.graph")
    c.abilities[AbilityName.MELEE] = 5
    c.essence_rating = 5
    c.charms = ["solar.melee.excellent-strike"]

    g = viewmod.build_charm_graph(rs, c, "melee")
    assert len(g.nodes) == 22
    state = {n.id: n.state for n in g.nodes}
    assert state["solar.melee.excellent-strike"] == "owned"
    assert state["solar.melee.hungry-tiger-technique"] == "available"   # prereq owned
    assert state["solar.melee.fire-and-stones-strike"] == "locked"      # its prereq not owned yet
    assert state["solar.melee.retrieve-the-fallen-weapon"] == "available"  # a root
    # graph wiring
    assert ("solar.melee.excellent-strike", "solar.melee.hungry-tiger-technique") in g.edges
    assert "solar.melee.excellent-strike" in g.roots


def test_artifact_gear_is_marked_and_carries_its_extra_fields():
    rs = rules_db.load_ruleset(DATA_DIR)
    daiklave = rs.weapon_catalog["weapon.melee.daiklave"]
    assert daiklave.artifact_rating == 2 and daiklave.min_strength == 2
    assert daiklave.damage == 5 and daiklave.damage_type == "L"
    plate = rs.armor_catalog["armor.artifact.superheavy_plate"]
    assert plate.artifact_rating == 5 and plate.attunement == 8
    # mundane gear keeps the defaults
    assert rs.armor_catalog["armor.breastplate"].artifact_rating == 0


def test_dual_mode_weapon_has_one_entry_per_mode():
    rs = rules_db.load_ruleset(DATA_DIR)
    thrown = rs.weapon_catalog["weapon.thrown.lightning_torment_hatchet"]
    melee = rs.weapon_catalog["weapon.melee.lightning_torment_hatchet"]
    assert thrown.range == 20 and thrown.defense == 0       # thrown profile
    assert melee.speed == 3 and melee.range == 0            # melee profile
    assert thrown.artifact_rating == melee.artifact_rating == 5


def test_ranged_weapons_carry_range_and_bows_max_strength():
    rs = rules_db.load_ruleset(DATA_DIR)
    long_bow = rs.weapon_catalog["weapon.archery.long_bow"]
    assert long_bow.range == 200 and long_bow.max_strength == 4
    powerbow = rs.weapon_catalog["weapon.archery.long_powerbow"]
    assert powerbow.range == 350 and powerbow.artifact_rating == 3
