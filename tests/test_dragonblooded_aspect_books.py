"""The five Dragon-Blooded Aspect Books — Chapter Six Charm catalogues.

Authored from `images/Dragonblooded/Aspects/<Air|Earth|Fire|Water|Wood>/CH 6 - *.md`,
human-pasted text. 87 Charms: 80 keyed to Abilities and the 7 of Jade Mountain Style.
Water's file is clean markdown; the other four are raw paste with drop-cap damage
("P ILLAR OF MARBLE STANCE") and, in Air and Wood, fi/fl ligature damage.

Two rules-authority calls are pinned here because they are the ones a later editor is
most likely to "fix" wrongly:

  * `element` follows the ABILITY, never the chapter. Two Charms are printed in one
    aspect's book but keyed to another aspect's Ability, and every one of the Charms
    shipped before this landed derives element from the Ability.
  * Jade Mountain Style is NOT Immaculate. The Earth book calls it "This
    Terrestrial-level martial art ... similar in tone and yet far less powerful than
    the Immaculate Earth Dragon Style", so it must not get the Immaculate BP/XP rates
    or feed the single-elemental-tree chargen path.
"""

from pathlib import Path

import pytest

import exalted_builder
from exalted_builder import rules_db
from exalted_builder.engine import validate
from exalted_builder.models.rules import AbilityName as AB

DATA_DIR = Path(exalted_builder.__file__).parent / "data"
DB = "Dragon-Blooded"
ASPECT_ABILITIES = {
    "Air": {"linguistics", "lore", "occult", "stealth", "thrown"},
    "Earth": {"awareness", "craft", "endurance", "martial_arts", "resistance"},
    "Fire": {"athletics", "dodge", "melee", "presence", "socialize"},
    "Water": {"brawl", "bureaucracy", "investigation", "larceny", "sail"},
    "Wood": {"archery", "medicine", "performance", "ride", "survival"},
}


@pytest.fixture(scope="module")
def rs():
    return rules_db.load_ruleset(DATA_DIR)


@pytest.fixture(scope="module")
def aspect_charms(rs):
    return [c for c in rs.charms.values()
            if c.source and c.source.book.startswith("Aspect Book:")]


def test_all_87_aspect_book_charms_are_present(rs, aspect_charms):
    from collections import Counter
    assert len(aspect_charms) == 87
    per_book = Counter(c.source.book.split(": ")[1] for c in aspect_charms)
    assert per_book == Counter({"Air": 22, "Earth": 20, "Fire": 12,
                                "Water": 24, "Wood": 9})


def test_every_aspect_book_charm_is_complete(rs, aspect_charms):
    """The parse had to survive drop-cap and ligature damage, so this asserts that no
    Charm came through with a hole where a field should be."""
    for c in aspect_charms:
        assert c.name and not c.name.isupper(), c.id
        assert c.exalt_type == DB, c.id
        assert 1 <= c.min_ability <= 5, c.id
        assert 1 <= c.min_essence <= 10, c.id
        assert c.duration, c.id
        assert c.cost.motes or c.cost.willpower or c.cost.raw, c.id
        assert len(c.description) > 100, c.id
        assert c.source.page, c.id
        # OCR scars that would mean the healer missed a line-break hyphen.
        assert "- " not in c.name, c.id
        assert not any(len(w) > 20 and w.isalpha() for w in c.description.split()), c.id


def test_no_charm_kept_a_stat_block_label_in_its_description(rs, aspect_charms):
    """The stat block is parsed field-by-field; a label leaking into the prose means a
    wrapped value was mis-attributed and the numbers above it are suspect."""
    for c in aspect_charms:
        head = c.description[:60]
        for label in ("Cost:", "Duration:", "Type:", "Minimum Essence",
                      "Prerequisite Charm"):
            assert label not in head, f"{c.id}: {label!r} leaked into the description"


def test_prerequisites_all_resolve(rs, aspect_charms):
    """The books abbreviate ("Seeking Throw" for "Seeking Throw Technique"), so these
    were name-matched — a dangling id would be a silently unreachable branch."""
    for c in aspect_charms:
        for group in c.prerequisites:
            assert group, c.id
            for pid in group:
                assert pid in rs.charms, f"{c.id} -> missing {pid}"


# --- the two rules-authority calls ------------------------------------------- #

def test_element_follows_the_ability_not_the_chapter(rs, aspect_charms):
    """Every Dragon-Blooded ability Charm in the data derives `element` from its
    Ability's aspect, with no exceptions — including the two Charms printed in the
    "wrong" book. `element` is only ever read mechanically for Immaculate Charms
    (the single-elemental-tree check), so this is consistency, not a rules effect."""
    ab_to_el = {a: el for el, abs_ in ASPECT_ABILITIES.items() for a in abs_}
    for c in rs.charms.values():
        if c.exalt_type != DB or c.immaculate or ":" in c.category:
            continue
        assert c.element == ab_to_el[c.category], c.id


def test_the_two_cross_book_charms(rs):
    """Diligent Engineer Discipline is printed in Air's chapter but gates on Craft (an
    EARTH Ability); Spark Kindling Rescue Technique is printed in Fire's but gates on
    Medicine (a WOOD Ability). Both keep their Ability's element."""
    craft = rs.charms["dragonblooded.craft.diligent-engineer-discipline"]
    assert craft.source.book.endswith("Air") and craft.element == "Earth"
    assert craft.category == "craft"

    med = rs.charms["dragonblooded.medicine.spark-kindling-rescue-technique"]
    assert med.source.book.endswith("Fire") and med.element == "Wood"
    assert med.category == "medicine"


def test_jade_mountain_style_is_a_terrestrial_style_not_an_immaculate_one(rs):
    """Earth book: "This Terrestrial-level martial art channels the overwhelming
    strength and resilience of the mountain, similar in tone and yet far less powerful
    than the Immaculate Earth Dragon Style."

    If any of these were flagged `immaculate` they would price at the Immaculate BP/XP
    rates and drag a character onto the single-elemental-tree chargen path (p.151).
    """
    jade = [c for c in rs.charms.values() if c.category == "martial_arts:jade-mountain"]
    assert len(jade) == 7
    for c in jade:
        assert c.immaculate is False, c.id
        assert c.exalt_type == DB and c.element == "Earth", c.id
        assert c.id.startswith("dragonblooded.martial-arts."), c.id
    # It is its own style, distinct from the shipped Immaculate trees and Five-Dragon.
    styles = {c.category for c in rs.charms.values()
              if c.exalt_type == DB and c.category.startswith("martial_arts:")}
    assert "martial_arts:jade-mountain" in styles
    assert "martial_arts:five-dragon" in styles


def test_jade_mountain_is_not_open_to_other_splats(rs):
    """Nothing on the page opens it up the way Falling Blossom's does, so it stays
    Dragon-Blooded-only — no open_to_all, no open_to_tiers."""
    for c in rs.charms.values():
        if c.category == "martial_arts:jade-mountain":
            assert not c.open_to_all and not c.open_to_tiers, c.id


# --- the model's limits, recorded so they are not mistaken for bugs ----------- #

def test_the_one_charm_whose_printed_type_the_enum_cannot_express(rs):
    """Pulse of the Dragon's Soul prints "Type: Reflexive or Simple" (matching its
    "Cost: 1 or 3 motes"). CharmType has no disjunction, so it is stored as Special —
    the same escape hatch Ox-Body uses — and the mechanic lives in the description."""
    c = rs.charms["dragonblooded.awareness.pulse-of-the-dragons-soul"]
    assert c.type.value == "Special"
    assert c.cost.raw == "1 or 3 motes"
    assert "3 motes" in c.description
    # It is the only aspect-book Charm forced into Special; a second would mean the
    # enum needs revisiting rather than another escape-hatch entry. (Special is used
    # legitimately elsewhere for genuinely special Charms — Ox-Body and the Unmakings.)
    forced = [x.id for x in rs.charms.values()
              if x.source and x.source.book.startswith("Aspect Book:")
              and x.type.value == "Special"]
    assert forced == ["dragonblooded.awareness.pulse-of-the-dragons-soul"]


BREADTH = {
    "dragonblooded.linguistics.favored-quill-mastery": "linguistics",
    "dragonblooded.lore.flawless-study-focus": "lore",
    "dragonblooded.occult.embracing-the-arcane": "occult",
    "dragonblooded.stealth.favored-haunt-stance": "stealth",
    "dragonblooded.craft.resplendent-artisan-mastery": "craft",
}


@pytest.mark.parametrize("cid,category", sorted(BREADTH.items()))
def test_breadth_prerequisites_are_modelled_not_dropped(rs, cid, category):
    """Five Charms require "any three <Ability> Charms" — a COUNT over a category,
    which `prerequisites` cannot express (it is AND-of-OR over ids, and "3 of 11"
    encoded as three groups of all eleven is satisfied three times by one owned
    Charm). `prerequisite_counts` carries them instead."""
    c = rs.charms[cid]
    assert c.prerequisites == []            # no id-based prerequisite is printed
    assert [(r.category, r.count) for r in c.prerequisite_counts] == [(category, 3)]


def test_only_those_five_charms_have_a_breadth_prerequisite(rs):
    """A sixth has to be deliberate — this is a rare shape."""
    got = sorted(c.id for c in rs.charms.values() if c.prerequisite_counts)
    assert got == sorted(BREADTH)


def test_a_breadth_prerequisite_actually_gates(rs):
    """The whole point: holding too few Charms of the category must make the Charm
    unlearnable, and must be reported against a character who has it anyway."""
    from exalted_builder.models.character import Character
    cid = "dragonblooded.occult.embracing-the-arcane"
    charm = rs.charms[cid]
    others = [c.id for c in sorted(rs.charms.values(), key=lambda c: c.id)
              if c.category == "occult" and c.exalt_type == DB and c.id != cid]

    c = Character(id="c", exalt_type=DB, caste="air", essence_rating=5)
    c.abilities = {a: 5 for a in AB}
    assert validate.meets_charm_requirements(rs, c, charm) is False

    c.charms = others[:2]                   # two of the three needed
    assert validate.meets_charm_requirements(rs, c, charm) is False
    c.charms = others[:3]
    assert validate.meets_charm_requirements(rs, c, charm) is True

    # ...and retrospectively, a character holding it with too few is flagged.
    c.charms = others[:1] + [cid]
    codes = {i.code for i in validate.check_charm_prerequisites(rs, c)}
    assert "charm-prerequisite-count" in codes
    c.charms = others[:3] + [cid]
    assert "charm-prerequisite-count" not in {
        i.code for i in validate.check_charm_prerequisites(rs, c)}


def test_a_charm_does_not_count_toward_its_own_breadth_requirement(rs):
    """Otherwise buying it would part-satisfy the thing gating it."""
    from exalted_builder.models.character import Character
    cid = "dragonblooded.lore.flawless-study-focus"
    others = [c.id for c in sorted(rs.charms.values(), key=lambda c: c.id)
              if c.category == "lore" and c.exalt_type == DB and c.id != cid]
    c = Character(id="c", exalt_type=DB, caste="air", essence_rating=5)
    c.abilities = {a: 5 for a in AB}
    c.charms = others[:2] + [cid]           # 2 others + itself != 3 Lore Charms
    assert {i.code for i in validate.check_charm_prerequisites(rs, c)} >= \
        {"charm-prerequisite-count"}


def test_a_cross_book_charm_counts_toward_its_abilitys_breadth(rs):
    """Counting is by `category`, so Diligent Engineer Discipline — printed in the Air
    book but a Craft Charm — counts toward "any three Craft Charms"."""
    from exalted_builder.models.character import Character
    craft = [c.id for c in sorted(rs.charms.values(), key=lambda c: c.id)
             if c.category == "craft" and c.exalt_type == DB
             and c.id != "dragonblooded.craft.resplendent-artisan-mastery"]
    assert "dragonblooded.craft.diligent-engineer-discipline" in craft
    c = Character(id="c", exalt_type=DB, caste="air", essence_rating=5)
    c.abilities = {a: 5 for a in AB}
    # Craft is taken per focus (core p.136) — the AbilityName.CRAFT dot is unused, so a
    # Craft Charm's minimum is met from `crafts`, not from `abilities`.
    from exalted_builder.models.character import CraftRating
    c.crafts = [CraftRating(focus="Smithing", rating=5)]
    c.charms = list(dict.fromkeys(
        ["dragonblooded.craft.diligent-engineer-discipline"] + craft))[:3]
    assert len(c.charms) == 3
    assert validate.meets_charm_requirements(
        rs, c, rs.charms["dragonblooded.craft.resplendent-artisan-mastery"]) is True


def test_the_breadth_requirement_reaches_the_ui(rs):
    """It has no source node, so there is no edge to draw — it must show as text on the
    detail card AND as a badge on the graph node, or a capstone Charm reads as an
    entry-level root."""
    from exalted_builder.models.character import Character
    from exalted_builder.ui import view

    c = Character(id="c", exalt_type=DB, caste="air", essence_rating=5)
    c.abilities = {a: 5 for a in AB}
    detail = view.build_charm_detail(rs, c, "dragonblooded.occult.embracing-the-arcane")
    assert ["any 3 Occult Charms"] in detail.prerequisite_groups

    graph = view.build_charm_graph(rs, c, "occult")
    node = next(n for n in graph.nodes
                if n.id == "dragonblooded.occult.embracing-the-arcane")
    assert node.count_requirement == "any 3 Occult Charms"
    assert all(not n.count_requirement for n in graph.nodes if n.id != node.id)


def test_parameterised_charm_names_follow_the_shipped_convention(rs):
    """The Earth book prints "Mantle of (Element) Invulnerability" as one Charm
    covering all five elements, exactly like the already-shipped "(Element) Protection
    Form". Perfected Scales of the Dragon requires "All five Mantle of (Element)",
    which resolves to that single Charm — the model does not track per-element
    repetition."""
    mantle = rs.charms["dragonblooded.resistance.mantle-of-element-invulnerability"]
    assert mantle.name == "Mantle of (Element) Invulnerability"
    scales = rs.charms["dragonblooded.resistance.perfected-scales-of-the-dragon"]
    assert [[mantle.id]] == [g for g in scales.prerequisites if mantle.id in g]


def test_multi_gate_charms_use_extra_min_abilities(rs):
    """Three Charms print a second Ability minimum. The primary gate is the Charm's
    own category (pricing, the picker layout and the Caste/Favoured discount all key
    off `min_ability`); the extra is a requirement check only."""
    expected = {
        "dragonblooded.craft.diligent-engineer-discipline": (4, AB.LINGUISTICS, 1),
        "dragonblooded.stealth.empty-hand-posture": (4, AB.LARCENY, 2),
        "dragonblooded.melee.style-countering-meditation": (4, AB.DODGE, 4),
    }
    for cid, (primary, extra_ab, extra_rating) in expected.items():
        c = rs.charms[cid]
        assert c.min_ability == primary, cid
        assert [(list(r.abilities), r.rating) for r in c.extra_min_abilities] == \
            [([extra_ab], extra_rating)], cid


# --- gear, per the Solar castebook precedent ---------------------------------- #
# Weapons and armour are authored; hearthstones, Manses and non-gear artifacts are
# skipped (the Elemental Lens, Reaver Dragonfly, Cache Egg, Skin-Mount Amulet and the
# rest print no weapon/armour line at all).

ASPECT_WEAPONS = {
    # name                          speed acc dmg type def artifact
    "Forge-Hand Gauntlets":          (-3, -1,  4, "A",  2, 4),   # Fire p.81
    "Eye of the Fire Dragon":        (10,  3,  8, "L",  2, 5),   # Fire p.81
    "Black Widow Razors":            (1,   1,  4, "L",  2, 3),   # Wood p.83
    "Grand Grimcleaver":             (-6,  1, 13, "L", -1, 0),   # Wood p.83
    "Death at the Root":             (-5,  2, 13, "L",  0, 4),   # Wood p.83
    "Gauntlets of Distant Touch":    (3,   2,  5, "L",  3, 3),   # Water p.80
    "Lightning Corona (melee)":      (2,   1,  5, "L",  1, 0),   # Air p.81
}


@pytest.mark.parametrize("name", sorted(ASPECT_WEAPONS))
def test_aspect_book_weapon_stats(rs, name):
    """Read off the weapon tables, which in Fire, Wood and Air are COLUMN-SCRAMBLED in
    the paste (one cell per line). The column order is regular, so these are the values
    as printed — and pinning them here is what makes a mis-read visible."""
    speed, acc, dmg, dtype, dfn, artifact = ASPECT_WEAPONS[name]
    w = next(x for x in rs.weapon_catalog.values() if x.name == name)
    assert (w.speed, w.accuracy, w.damage, w.damage_type, w.defense) == \
        (speed, acc, dmg, dtype, dfn)
    assert w.artifact_rating == artifact
    assert "Aspect Book" in w.notes


def test_the_lightning_corona_is_two_rows_one_per_mode(rs):
    """It is the Most Terrifying Armor's integral weapon with a melee and a ranged
    profile, so it is two catalog rows — the same treatment the castebooks' Ultimately
    Useful Tube and Gauntlets of Distant Claws got."""
    melee = next(x for x in rs.weapon_catalog.values()
                 if x.name == "Lightning Corona (melee)")
    ranged = next(x for x in rs.weapon_catalog.values()
                  if x.name == "Lightning Corona (ranged)")
    assert "melee" in melee.tags and "ranged" in ranged.tags
    assert (ranged.damage, ranged.damage_type) == (10, "L")
    assert ranged.rate == 1 and ranged.range == 200
    # The table prints no Speed/Defense for the ranged mode; they must not be invented.
    assert "prints no Speed or Defense" in ranged.notes


def test_the_only_aspect_book_armour(rs):
    """Most Terrifying Armor of the Air Dragon, Air p.81: Soak 13L/15B, Mobility -0,
    Fatigue 1, Artifact ••••. Its "+2 (8)" Strength column has no model field and
    rides in notes."""
    a = next(x for x in rs.armor_catalog.values()
             if x.name == "Most Terrifying Armor of the Air Dragon")
    assert (a.soak_lethal, a.soak_bashing) == (13, 15)
    assert (a.mobility_penalty, a.fatigue) == (0, 1)
    assert a.artifact_rating == 4
    assert "Strength bonus of +2" in a.notes


def test_exalted_power_combat_stats_live_in_notes_not_in_the_fields(rs):
    """Every table prints a second "Exalted Power Combat" row — an ALTERNATE ruleset.
    The standard row is the canonical one; the variant is recorded but must never be
    what the catalog reports, or every weapon silently changes system."""
    eye = next(x for x in rs.weapon_catalog.values() if x.name == "Eye of the Fire Dragon")
    assert eye.damage == 8                      # standard, not the Power Combat 12
    assert "Exalted Power Combat: Speed +15" in eye.notes


def test_the_armor_hardening_table_survived_as_readable_prose(rs):
    """Its description says "according to the table below", and the table is a tangent
    block in the source — so the numbers have to be IN the description or the Charm is
    unusable. Reformatted from the run-on the paste produces."""
    c = rs.charms["dragonblooded.resistance.armor-hardening-concentration"]
    for bit in ("Non-Magical Armor 1L/2B", "Magical Armor 2L/2B",
                "Jade Armor 2L/3B", "White Jade Armor 3L/3B"):
        assert bit in c.description, bit
