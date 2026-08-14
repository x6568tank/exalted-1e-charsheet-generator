"""Tests over the *shipped* data files in exalted_builder/data — distinct from
test_rules_db.py, which exercises the loader on synthetic tmp_path data. These
guard the real authored content against drift.
"""

from pathlib import Path

import pytest

import exalted_builder
from exalted_builder import rules_db
from exalted_builder.engine import derive, validate
from exalted_builder.models.character import Character
from exalted_builder.models.rules import AbilityName, SpellCircle, TRACK_CIRCLES

DATA_DIR = Path(exalted_builder.__file__).parent / "data"


def test_shipped_ruleset_loads():
    rs = rules_db.load_ruleset(DATA_DIR)
    # all five Solar castes present, keyed by their lowercase id
    solar = {cid for cid, cd in rs.castes.items() if cd.exalt_type == "Solar"}
    assert solar == {"dawn", "zenith", "twilight", "night", "eclipse"}
    # ...and the five Dragon-Blooded Aspects
    db = {cid for cid, cd in rs.castes.items() if cd.exalt_type == "Dragon-Blooded"}
    assert db == {"air", "earth", "fire", "water", "wood"}


@pytest.mark.parametrize("exalt_type", ["Solar", "Dragon-Blooded"])
def test_caste_abilities_partition_the_roster(exalt_type):
    """Each splat's castes/aspects partition the 25 abilities exactly (no gaps, no
    overlaps) — the 1e caste-grouped roster."""
    rs = rules_db.load_ruleset(DATA_DIR)
    castes = [cd for cd in rs.castes.values() if cd.exalt_type == exalt_type]
    all_caste_abilities = [a for cd in castes for a in cd.caste_abilities]
    assert len(all_caste_abilities) == 25
    assert set(all_caste_abilities) == set(AbilityName)   # exact partition
    assert all(len(cd.caste_abilities) == 5 for cd in castes)


def test_each_caste_keyed_by_its_own_id():
    rs = rules_db.load_ruleset(DATA_DIR)
    assert all(key == cd.id for key, cd in rs.castes.items())


def test_every_caste_has_a_description_and_anima_power():
    rs = rules_db.load_ruleset(DATA_DIR)
    assert len(rs.castes) == 41          # 5 Solar + 5 DB + 5 Abyssal + 4 Lunar + 5 Sidereal + 5 Alchemical + 5 Godblooded heritages + 4 Dragon-King breeds + 3 Mountain Folk
    for cd in rs.castes.values():
        assert cd.description and cd.anima_powers
    assert rs.castes["dawn"].description.startswith("Masters of war")
    assert rs.castes["fire"].exalt_type == "Dragon-Blooded"
    assert rs.castes["dusk"].exalt_type == "Abyssal"
    assert rs.castes["full-moon"].exalt_type == "Lunar"
    assert rs.castes["orichalcum"].exalt_type == "Alchemical"
    assert rs.castes["anklok"].exalt_type == "Dragon-Kings"


def test_ox_body_technique_loads_repeatable_with_three_variants():
    rs = rules_db.load_ruleset(DATA_DIR)
    ox = rs.charms["solar.endurance.ox-body-technique"]
    assert ox.repeatable_cap_ability == "endurance"
    by_key = {v.key: v.health_levels for v in ox.variants}
    assert by_key == {
        "one-zero": [0],
        "two-one": [-1, -1],
        "one-one-two-two": [-1, -2, -2],
    }


def test_nature_catalog_loads_the_p105_archetypes():
    rs = rules_db.load_ruleset(DATA_DIR)
    cat = rs.nature_catalog
    assert len(cat) == 20                                  # p105 (Solar) + 4 Lunar-only (p91)
    names = {n.name for n in cat.values()}
    assert {"Architect", "Bravo", "Caregiver", "Judge", "Rebel"} <= names
    assert {"Savant", "Survivor", "Thrillseeker", "Visionary"} <= names
    assert cat["rebel"].description == "You constantly seek to challenge authority."


def test_background_catalog_has_the_ten_core_backgrounds():
    rs = rules_db.load_ruleset(DATA_DIR)
    names = {b.name for b in rs.background_catalog.values()}
    # the ten core Backgrounds are always present…
    assert {"Allies", "Artifact", "Backing", "Contacts", "Familiar",
            "Followers", "Influence", "Manse", "Mentor", "Resources"} <= names
    # …alongside the Dragon-Blooded splatbook additions (Traits chapter, p156-160)
    assert {"Breeding", "Connections", "Command", "Henchmen", "Reputation"} <= names


# --------------------------------------------------------------------------- #
# Solar Melee charms
# --------------------------------------------------------------------------- #

def test_melee_charm_tree_loads_with_intact_prerequisites():
    # load_ruleset itself link-checks prerequisites; reaching here means the whole
    # tree resolves. Confirm the expected shape.
    rs = rules_db.load_ruleset(DATA_DIR)
    melee = [c for c in rs.charms.values()
             if c.category == "melee" and c.exalt_type == "Solar"]
    # 22 corebook/Illuminated Charms + 4 from Caste Book: Night (p.70-71) and
    # 2 from Caste Book: Dawn (p.74).
    assert len(melee) == 28
    roots = {c.name for c in melee if not c.prerequisites}
    assert roots == {"Excellent Strike", "Retrieve the Fallen Weapon",
                     "Golden Essence Block", "Dual Slaying Stance"}


def test_dawn_caste_charm_trees_load_with_expected_counts():
    from collections import Counter
    rs = rules_db.load_ruleset(DATA_DIR)
    # Solar-only counts (DB and other splats share ability categories like "thrown").
    cats = Counter(c.category for c in rs.charms.values() if c.exalt_type == "Solar")
    # 12 corebook + 3 from Caste Book: Dawn (p.71).
    assert cats["archery"] == 15
    # 10 corebook Brawl Charms + the 5 from Cult of the Illuminated (p.100-102)
    # + 3 from Caste Book: Dawn (p.72).
    assert cats["brawl"] == 18
    # 9 corebook + 4 from Caste Book: Dawn (p.74-76).
    assert cats["thrown"] == 13
    assert cats["martial_arts:snake"] == 10
    # Falling Blossom Style (Cult of the Illuminated, p.102-104) is a second Solar
    # Martial Arts style and lives in its own file, like the Sidereal styles do.
    assert cats["martial_arts:falling-blossom"] == 7
    # The three castebook styles: Tiger (Dawn p.73-74), Praying Mantis (Eclipse
    # p.73-75) and Ebon Shadow (Night p.67-70). Their category keys are the ones
    # the Sequestered Tabernacle training camp already names in data/camps.json.
    assert cats["martial_arts:tiger"] == 9
    assert cats["martial_arts:praying-mantis"] == 10
    assert cats["martial_arts:ebon-shadow"] == 11
    assert cats["melee"] == 28


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
    assert d.duration == rs.charms["solar.melee.blazing-solar-bolt"].duration
    assert viewmod.build_charm_detail(rs, c, "nope") is None


def test_sheet_charm_rows_carry_duration():
    """Duration is on the Charm data but was never surfaced; the sheet's Charm
    rows must expose it alongside cost."""
    from exalted_builder.ui import view as viewmod
    rs = rules_db.load_ruleset(DATA_DIR)
    c = Character(id="c.duration")
    c.charms = ["solar.melee.excellent-strike", "not-a-real-charm"]
    rows = {r.name: r for r in viewmod.build_sheet_view(rs, c).charms}
    assert rows["Excellent Strike"].duration == "Instant"
    assert rows["not-a-real-charm"].duration == "—"


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
    assert len(rs.spells) == 294
    by_circle: dict = {}
    for s in rs.spells.values():
        by_circle[s.circle] = by_circle.get(s.circle, 0) + 1
    # Three Sorcery circles (Terrestrial gained the Dragon-Blooded Sworn Brothers'
    # Oath, p161) plus the three Necromancy circles authored in the Abyssal phase
    # (Abyssal p224-229), plus the two Alchemical weaving circles — 23 Man-Machine
    # and 15 God-Machine protocols (Autochthonians CH4).
    # Caste Book: Twilight (p.74-77) adds 2 Terrestrial, 3 Celestial and 2 Solar.
    # The Outcaste (p.93-95) adds 4 more Terrestrial, the pirates' sea spells.
    # 2026-08-11: the delegated spell batch added 151 — Book of Bone and Ebony
    # (17 Labyrinth, 32 Shadowlands, 10 Void) and Savant and Sorcerer (51 Terrestrial,
    # 32 Celestial, 9 Solar). Cleansing Solar Flames (B&E p.139, human-ruled attribution)
    # brought Solar to 16 and the total to 244. See docs/status/spell-batch-notes.md.
    # 2026-08-13: the Book of Three Circles adds 48 — 31 Terrestrial (ch.2), 3 Celestial
    # (ch.3) and 14 Solar (ch.4). ⚠ The fan spell index labels the ch.4 group "Adamant";
    # the BOOK's chapter head reads "THE SOLAR CIRCLE" and the book wins. Read off the
    # scanned pages directly (pdftoppm -r 110; PDF page = book page + 1). Where the two
    # books print the same spell, Savant and Sorcerer wins (human's ruling), so the S&S
    # copies were left untouched and only names absent from the build were authored.
    assert by_circle == {SpellCircle.TERRESTRIAL: 98,
                         SpellCircle.CELESTIAL: 44,
                         SpellCircle.SOLAR: 31,
                         SpellCircle.SHADOWLANDS: 42,
                         SpellCircle.LABYRINTH: 24,
                         SpellCircle.VOID: 17,
                         SpellCircle.MAN_MACHINE: 23,
                         SpellCircle.GOD_MACHINE: 15}


def test_sworn_brothers_oath_loads(rs=None):
    rs = rules_db.load_ruleset(DATA_DIR)
    s = rs.spells["spell.terrestrial.sworn-brothers-oath"]
    assert s.name == "Sworn Brothers' Oath"
    assert s.circle == SpellCircle.TERRESTRIAL       # any sorcerer of this circle may learn it
    assert s.cost.motes == 10                         # base; the +1/Exalt is in the raw string
    assert "1 mote" in s.cost.raw
    assert s.source.page == 161


def test_each_circle_is_granted_by_its_sorcery_charm():
    # load_ruleset would raise if any spell's circle were ungranted; assert the
    # mapping explicitly too.
    rs = rules_db.load_ruleset(DATA_DIR)
    grants = {c.grants_circle for c in rs.charms.values()
              if c.grants_circle is not None}
    # Every circle of every track now has an initiation Charm: the three Sorcery
    # circles (Solar/DB Occult), the three Necromancy circles (Abyssal Occult), and
    # the two Alchemical weaving circles (the Man-/God-Machine Weaving Engines).
    assert grants == (set(TRACK_CIRCLES["sorcery"]) | set(TRACK_CIRCLES["necromancy"])
                      | set(TRACK_CIRCLES["weaving"]))


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
    # 49 corebook + 30 from the Solar castebooks (Dawn p.79/81, Night p.77-81,
    # Zenith p.80-81) + 8 from the Dragon-Blooded Aspect Books (Fire p.81, Wood p.83,
    # Water p.80, Air p.81 — the last being the Lightning Corona's two modes)
    # + 9 from the Mountain Folk Technology chapter (Skirmish Pike, Dragon Sigh Wand,
    # Essence Pulse Grenade, pp.280-282, and the six dual-nature devices — the four
    # crossbows and the flamecaster + pyromantic grenade, p.278 — which carry BOTH
    # `artifact_rating` and `resources_cost` so the player funds them either way).
    # + 2 from the 2026-08-08 backlog batch: the Hooked Daiklaves of Dual Prowess
    # (Night p.81) and the Direlance (core p.342 table; its p.341 description page
    # is not on disk — see the notes field).
    # + 4 ARROWS (core p.330), tagged "ammunition": in 1e the arrow IS the bow's
    # damage ("broadhead arrows do the firing character's Strength + 2"), which is why
    # every bow row in this catalogue carries none. They have no printed Resources cost
    # and are free unless a specific type states otherwise (human, 2026-08-12).
    # + The Crimson Bow (Book of Three Circles p.95), the one BOTC artifact printed with
    # a full weapon stat line, so it gets a stat row here as well as a catalogue entry.
    assert len(rs.weapon_catalog) == 103
    # 17 corebook + the artifact Chain Shirt (Dawn p.81), Cloak of Vanishing
    # Escape (Night p.81) and the Most Terrifying Armor of the Air Dragon (Air p.81),
    # + the three p.335 SHIELDS, which are armour rows tagged "shield" rather than a
    # model of their own (see ArmorType), + the Myrmidon Carapace (Mountain Folk
    # p.283). rs.body_armor() / rs.shields() split them.
    # + the three p.334-335 HELMS, which are armour rows tagged "helm" and carry no
    # stats at all — the book says all helms are mechanically identical and largely
    # cosmetic. rs.body_armor() excludes both accessories.
    assert len(rs.armor_catalog) == 27
    assert len(rs.body_armor()) == 21
    assert len(rs.shields()) == 3
    assert len(rs.helms()) == 3
    assert all(h.soak_lethal == 0 and h.soak_bashing == 0 and h.fatigue == 0
               and h.mobility_penalty == 0 for h in rs.helms())


def test_artifact_catalog_loads_the_ten_mountain_folk():
    rs = rules_db.load_ruleset(DATA_DIR)
    # 2026-08-11: the 141-entry delegation batch (B&E 71, Outcaste 26, Rathess 15,
    # Autochthonians 15, Player's Guide 14) grew the catalogue from 40 to 181 — see
    # docs/status/artifact-batch-notes.md for the 8 worklist entries skipped/merged.
    # 2026-08-11 (batch 2): +15 from Exalted Core (8), Savant and Sorcerer (5) and
    # Book of Bone and Ebony p.114 (2) — 8 worklist rows skipped/dup — see
    # docs/status/artifact-batch-2-notes.md.
    # 2026-08-12: +26 from the corebook Wonders chapter, unblocked when the display
    # face that draws its entry NAMES was decoded (tools/glyph_maps/exalted-core.json)
    # — the ten Hearthstones (pp.338-340) and sixteen Greater Wonders (pp.340-346).
    # 2026-08-13: +12 from the Book of Three Circles — 3 from ch.1 (pp.24-27) and 9 from
    # ch.5 "New Wonders" (pp.92-96), whose ratings come from LEVEL N section headings
    # rather than per-entry dot strings. +2 the same day: the Mantle of Brigid (p.25)
    # and the Sword of Ice (p.27), which print "(ARTIFACT N/A)" because they are plot
    # devices — the human ruled 2026-08-13 that they cost the Legendary Artifact 10-pt
    # Merit instead, which `requires_merit` carries. Their `rating` of 5 is a placeholder
    # the model's 1-5 bound requires and nothing charges: `rating_notes` says N/A, and
    # `purchasable_with_artifact` keeps them off every Artifact-dot surface.
    # +1 more: the Insidious Ebon Xoanon (B&E p.104), unauthorable since the 2026-08-11
    # sweep for exactly that reason and ruled the same way by the human on 2026-08-13.
    assert len(rs.artifact_catalog) == 237
    # Ratings and the printed ranges, from the Technology chapter (pp.279-283).
    visor = rs.artifact_catalog["artifact.mountain-folk.essence-scrying-visor"]
    assert visor.rating == 1 and visor.source == "Mountain Folk p.279"
    assert rs.artifact_catalog["artifact.mountain-folk.myrmidon-carapace"].rating == 3
    talisman = rs.artifact_catalog["artifact.mountain-folk.talisman-of-suspended-evocation"]
    assert talisman.rating == 1 and talisman.rating_notes == "• to •••••"
    # Every entry is readable — "a Merit you cannot read the text of is just a word".
    assert all(a.name and a.description for a in rs.artifact_catalog.values())


def test_artifact_catalog_loads_the_castebook_artifacts():
    """The 2026-08-08 backlog batch: ten non-gear artifacts from the Solar castebooks
    (Dawn pp.78/81, Night pp.79-81, Zenith pp.80-81) were authorable now and are in
    the catalogue. Ratings and sources come from the pages; the two rating disputes
    are pinned here so a "correction" toward the guide (which is 2e-derived and never
    a values source) cannot slip in silently."""
    rs = rules_db.load_ruleset(DATA_DIR)
    cat = rs.artifact_catalog
    assert cat["artifact.castebook-dawn.shield-bracer"].rating == 2
    assert cat["artifact.castebook-dawn.map-of-azure-victory"].rating == 3
    assert cat["artifact.castebook-dawn.chariot-of-aerial-conquest"].rating == 5
    assert cat["artifact.castebook-dawn.arrows-of-distant-death"].rating == 3
    assert cat["artifact.castebook-night.spider-grippers"].rating == 2
    assert cat["artifact.castebook-night.belt-of-shadow-walking"].rating == 3
    assert cat["artifact.castebook-night.circlet-of-spirits"].rating == 3
    assert cat["artifact.castebook-zenith.death-shield-ring"].rating == 3
    # Both pin a rating the guide misprints: the Hooked Daiklaves is •••• per the
    # heading (human ruling 2026-08-08; the page's own table misprints ••••• — the
    # weapon row follows the same ruling), and Ring of the Deliberative is •••• (the
    # guide's ••••• is 2e; page as authority).
    assert cat["artifact.castebook-night.hooked-daiklaves-of-dual-prowess"].rating == 4
    assert cat["artifact.castebook-zenith.ring-of-the-deliberative"].rating == 4
    # Source strings point at the transcribed pages.
    assert cat["artifact.castebook-night.belt-of-shadow-walking"].source == "Caste Book: Night p.80"
    assert cat["artifact.castebook-zenith.death-shield-ring"].source == "Caste Book: Zenith p.80"


def test_artifact_catalog_loads_the_twilight_and_eclipse_backlog():
    """The 2026-08-08 VLM-sync batch: the 12 Caste Book: Twilight + 8 Caste Book:
    Eclipse artifacts from pp.79-81 (VLM-transcribed, human-vetted — the .md pages
    are `images/Solars/Castebooks/{Twilight,Eclipse}/`). Ratings and sources come from
    the pages. Two things are pinned so nothing silent can slip:
    - Bracer of the Hawk is •• (the page prints two dots; the guide lists • — human
      confirmed 2026-08-08, page as authority).
    - Audient Brush is NOT in the catalogue — the guide's cb_e row is a phantom (no
      such text in the Eclipse book; full 98-page word-sweep, 2026-08-08)."""
    rs = rules_db.load_ruleset(DATA_DIR)
    cat = rs.artifact_catalog
    # Twilight p.79 — Bracer pins the page-vs-guide dispute.
    assert cat["artifact.castebook-twilight.bracer-of-the-hawk"].rating == 2
    assert cat["artifact.castebook-twilight.whistle-of-ghost-summoning"].rating == 2
    assert cat["artifact.castebook-twilight.seed-of-the-immaculate-blood"].rating == 2
    assert cat["artifact.castebook-twilight.seed-of-the-immaculate-blood"].rating_notes == "•• base; ••• red seeds"
    assert cat["artifact.castebook-twilight.cup-of-flowing-blood"].rating == 3
    # Twilight p.80.
    assert cat["artifact.castebook-twilight.eye-of-the-living-earth"].rating == 3
    assert cat["artifact.castebook-twilight.ghost-seeing-blindfold"].rating == 3
    assert cat["artifact.castebook-twilight.honey-of-the-bees-of-zarlath"].rating == 3
    assert cat["artifact.castebook-twilight.mirrors-of-illusion-shattering"].rating == 3
    assert cat["artifact.castebook-twilight.scabbard-of-the-living-weapon"].rating == 3
    # Twilight p.81 — Cord carries its three printed variant ratings; Veil and Jackal
    # pin •••• (the VLM's first pass misread •••••; the page prints four dots).
    assert cat["artifact.castebook-twilight.sorcery-capturing-cord"].rating == 3
    assert cat["artifact.castebook-twilight.sorcery-capturing-cord"].rating_notes == "••• emerald / •••• sapphire / ••••• adamant"
    assert cat["artifact.castebook-twilight.veil-that-holds-back-time"].rating == 4
    assert cat["artifact.castebook-twilight.the-jackals-skull"].rating == 4
    # Eclipse p.79.
    assert cat["artifact.castebook-eclipse.lotus-blossom-cup"].rating == 1
    assert cat["artifact.castebook-eclipse.players-mask"].rating == 1
    assert cat["artifact.castebook-eclipse.silver-quill"].rating == 1
    assert cat["artifact.castebook-eclipse.silver-quill"].rating_notes == "• base; •• self-writing quills"
    # Eclipse p.80.
    assert cat["artifact.castebook-eclipse.seven-jeweled-peacock-fans"].rating == 2
    assert cat["artifact.castebook-eclipse.silken-armor"].rating == 3
    assert cat["artifact.castebook-eclipse.solar-seal"].rating == 1
    # Eclipse p.81.
    assert cat["artifact.castebook-eclipse.folding-ship"].rating == 4
    assert cat["artifact.castebook-eclipse.iron-horse"].rating == 4
    # The phantom index row is blocked, not authored.
    assert "artifact.castebook-eclipse.audient-brush" not in cat
    # Sources point at the transcribed pages.
    assert cat["artifact.castebook-twilight.cup-of-flowing-blood"].source == "Caste Book: Twilight p.79"
    assert cat["artifact.castebook-twilight.sorcery-capturing-cord"].source == "Caste Book: Twilight p.81"
    assert cat["artifact.castebook-eclipse.folding-ship"].source == "Caste Book: Eclipse p.81"


def test_the_gear_artifact_rows_from_the_backlog_batch():
    """The two stat-blocked new artifacts also carry equipment rows. The Hooked
    Daiklaves' row is rated •••• (human ruling 2026-08-08: the heading is canonical;
    the table's Artifact column misprints ••••• — the row follows the heading like
    the catalogue entry); the Direlance's row follows the p.342 Daiklave Table, with
    the lance-mode stats in notes."""
    rs = rules_db.load_ruleset(DATA_DIR)
    hooks = rs.weapon_catalog["weapon.melee.hooked_daiklaves_of_dual_prowess"]
    assert hooks.artifact_rating == 4            # the heading, per the ruling
    assert hooks.attunement == 8                 # "commit 8 motes — 4 for each blade"
    assert hooks.speed == 2 and hooks.accuracy == 2 and hooks.damage == 5
    assert hooks.defense == 5 and hooks.damage_type == "L"
    assert hooks.min_strength == 2 and hooks.min_dexterity == 3 and hooks.min_martial_arts == 3
    lance = rs.weapon_catalog["weapon.melee.direlance"]
    assert lance.artifact_rating == 2 and lance.attunement == 0
    assert lance.speed == 6 and lance.accuracy == 2 and lance.damage == 5 and lance.defense == 0
    assert lance.min_strength == 1
    # The Direlance has NO standalone catalogue entry — and that is now a finding, not
    # a gap: core p.341 was decoded 2026-08-11 and carries only weapon-class prose plus
    # the p.342 stat table, so the entry does not exist to author. The rated weapon row
    # above is the whole of it.
    assert "artifact.core.direlance" not in rs.artifact_catalog
    # The Slayer Khatar WAS blocked for the same reason and is no longer: p.344 decoded
    # cleanly, so it is now authored (docs/status/artifact-batch-2-notes.md).
    assert "artifact.core.slayer-khatar" in rs.artifact_catalog


def test_the_alchemical_goods_catalogue_does_not_exist():
    """Godstrike Oil / Pyromantic Gel / Synthetic Leather (MF pp.275-277) were authored
    as a `GoodType` catalogue, shown in the browser, and removed the same day on the
    human's ruling (2026-08-08): a goods catalogue feeds no mechanical read site, and
    the precedent would open the "why not firedust, lanterns, rations?" flood. This
    pins the ruling in code — re-adding goods must be a deliberate reversal, not an
    accidental one. The full page transcription is preserved in
    docs/status/artifact-backlog.md, not in data."""
    rs = rules_db.load_ruleset(DATA_DIR)
    assert not hasattr(rs, "goods_catalog")
    assert not (DATA_DIR / "goods.json").exists()
    # GoodType must not exist in the models either — the catalogue is fully removed.
    import exalted_builder.models.rules as rules
    assert not hasattr(rules, "GoodType")


def test_mountain_folk_gear_stat_blocks():
    rs = rules_db.load_ruleset(DATA_DIR)
    pike = rs.weapon_catalog["weapon.mountain-folk.skirmish_pike"]
    assert (pike.speed, pike.accuracy, pike.damage) == (4, 1, 4)
    assert pike.damage_type == "L" and pike.artifact_rating == 1 and pike.attunement == 5
    wand = rs.weapon_catalog["weapon.mountain-folk.dragon_sigh_wand"]
    assert (wand.accuracy, wand.damage, wand.rate, wand.range) == (1, 12, 1, 30)
    assert wand.artifact_rating == 2 and wand.attunement == 5
    grenade = rs.weapon_catalog["weapon.mountain-folk.essence_pulse_grenade"]
    assert (grenade.damage, grenade.rate, grenade.range) == (10, 1, 20)
    assert grenade.artifact_rating == 2
    # The carapace carries the whole kit: the visor, the echo jewel and the mask of
    # pure breath are integrated, not listed as separate artifacts.
    carapace = rs.armor_catalog["armor.mountain-folk.myrmidon_carapace"]
    assert (carapace.soak_lethal, carapace.soak_bashing) == (8, 8)
    assert carapace.mobility_penalty == -1 and carapace.fatigue == 1
    assert carapace.artifact_rating == 3 and carapace.attunement == 5


def test_mountain_folk_dual_nature_devices_carry_both_minima():
    # The four crossbows cost "Resources OR Artifact" (the printed column is exactly
    # "Resources/Artifact"); the flamecaster and pyromantic grenade print Resources
    # only, so their Artifact rating is a flagged mirror (the ST sets the real value)
    # that lets the dual-nature toggle fund them either way. See the notes on each row.
    rs = rules_db.load_ruleset(DATA_DIR)
    w = rs.weapon_catalog
    crossbow = w["weapon.mountain-folk.crossbow"]
    assert (crossbow.accuracy, crossbow.damage, crossbow.rate, crossbow.range) == (1, 5, 1, 125)
    assert crossbow.min_strength == 1 and crossbow.resources_cost == 2 and crossbow.artifact_rating == 2
    mech = w["weapon.mountain-folk.mechanized_crossbow"]
    assert (mech.damage, mech.range, mech.min_strength) == (7, 200, 2)
    assert mech.resources_cost == 3 and mech.artifact_rating == 3
    assault = w["weapon.mountain-folk.assault_crossbow"]
    assert (assault.accuracy, assault.damage, assault.range) == (3, 8, 250)
    assert assault.resources_cost == 2 and assault.artifact_rating == 2 and assault.attunement == 5
    onslaught = w["weapon.mountain-folk.onslaught_crossbow"]
    assert (onslaught.damage, onslaught.rate, onslaught.range) == (10, 2, 300)
    assert onslaught.resources_cost == 3 and onslaught.artifact_rating == 3 and onslaught.attunement == 6
    flame = w["weapon.mountain-folk.flamecaster"]
    assert (flame.accuracy, flame.damage, flame.rate, flame.range) == (1, 12, 1, 10)
    assert flame.resources_cost == 3 and flame.artifact_rating == 3
    grenade = w["weapon.mountain-folk.pyromantic_grenade"]
    assert (grenade.accuracy, grenade.damage, grenade.range) == (0, 10, 15)
    assert grenade.resources_cost == 3 and grenade.artifact_rating == 3
    # The four crossbows are Archery weapons; the flamecaster/grenade are not. And
    # every dual-nature row flags the Resources/Artifact split in its notes.
    for key in ("weapon.mountain-folk.crossbow", "weapon.mountain-folk.mechanized_crossbow",
                "weapon.mountain-folk.assault_crossbow", "weapon.mountain-folk.onslaught_crossbow"):
        assert "archery" in w[key].tags and "artifact" in w[key].tags
        assert "Resources" in w[key].notes and "Artifact" in w[key].notes
    assert "Resources" in flame.notes and flame.notes.count("ST") >= 1


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
    assert len(g.nodes) == 28
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


def test_virtue_flaw_is_splat_gated():
    """The Dragon-Blooded, Sidereals and Alchemicals have no Virtue Flaw (human,
    rules authority, 2026-07-30). Independent of the Limit track: the Sidereal still
    has Paradox, it just has no flawed Virtue naming it.

    Ghosts join the list from the page rather than by ruling — E:Ab p.148: ghosts "are
    not subject to the effects of the Great Curse or the influence of the Malfeans"."""
    rs = rules_db.load_ruleset(DATA_DIR)
    without = {"Dragon-Blooded", "Sidereal", "Alchemical", "Mortal", "Ghost", "God-Blooded", "Dragon-Kings", "Mountain-Folk"}
    for eid, ex in rs.exalts.items():
        assert ex.has_virtue_flaw is (eid not in without), eid
    # the derivation agrees, and a Sidereal keeps its renamed Limit track regardless
    sid = Character(id="c.sid", exalt_type="Sidereal", caste="journeys")
    assert derive.has_virtue_flaw(rs, sid) is False
    assert derive.limit_label(rs, sid) == "Paradox"
    assert derive.has_virtue_flaw(rs, Character(id="c.sol", exalt_type="Solar", caste="dawn")) is True


def test_the_corebook_wonders_are_in_the_catalogue():
    """core pp.336-346. The chapter was blocked for three years of build time not
    because the pages were missing but because the display face that draws every entry
    NAME extracted as U+FFFD — the eight entries authored before this were the ones a
    page image had been read for. Ratings for the gear-statblocked rows are the ones
    already in weapons.json/armor.json, so the two must not drift."""
    rs = rules_db.load_ruleset(DATA_DIR)
    cat = rs.artifact_catalog
    for aid, rating in (("artifact.core.daiklave", 2),
                        ("artifact.core.grand-daiklave", 3),
                        ("artifact.core.reaver-daiklave", 2),
                        ("artifact.core.short-powerbow", 2),
                        ("artifact.core.long-powerbow", 3),
                        ("artifact.core.lightning-torment-hatchets", 5),
                        ("artifact.core.superheavy-plate-artifact", 5)):
        assert cat[aid].rating == rating, aid
    # The catalogue rating and the gear row's `artifact_rating` are two copies of one
    # printed number (p.342/p.346). A player can add a daiklave from either surface.
    by_name = {w.name: w for w in rs.weapon_catalog.values()}
    for name, aid in (("Daiklave", "artifact.core.daiklave"),
                      ("Grand Daiklave", "artifact.core.grand-daiklave"),
                      ("Reaver Daiklave", "artifact.core.reaver-daiklave"),
                      ("Dire Lance", "artifact.core.dire-lance"),
                      ("Goremaul", "artifact.core.goremaul"),
                      ("Grimcleaver", "artifact.core.grimcleaver"),
                      ("Serpent-Sting Staff", "artifact.core.serpent-sting-staff"),
                      ("Smashfist", "artifact.core.smashfist"),
                      ("Short Powerbow", "artifact.core.short-powerbow"),
                      ("Long Powerbow", "artifact.core.long-powerbow")):
        assert by_name[name].artifact_rating == cat[aid].rating, name
    armour = {a.name: a for a in rs.armor_catalog.values()}
    for name in ("Breastplate (Artifact)", "Reinforced Buff Jacket (Artifact)",
                 "Reinforced Breastplate (Artifact)", "Articulated Plate (Artifact)",
                 "Superheavy Plate (Artifact)"):
        aid = "artifact.core." + name.lower().replace(" (artifact)", "-artifact"
                                                      ).replace(" ", "-")
        assert armour[name].artifact_rating == cat[aid].rating, name


def test_the_ten_corebook_hearthstones_are_rated_by_manse_not_artifact():
    """core pp.338-340 print ten stones, two per element, and each one's dots are the
    rating of the MANSE that grew it. They live in the artifact catalogue because they
    are rated objects, but `background` keeps them out of the Artifact budget — see
    `engine.artifacts.purchasable_with_artifact`."""
    from exalted_builder.engine import artifacts as artifacts_engine
    rs = rules_db.load_ruleset(DATA_DIR)
    stones = artifacts_engine.hearthstones(rs.artifact_catalog)
    assert {s.name for s in stones} == {
        "Windhands Gemstone", "Gem of Sapphire and Emerald",
        "Salt-Gem of the Spirit's Eye", "Gem of Adamant Skin",
        "Gem of the Calm Heart", "Jewel of Hungry Fire",
        "The Freedom Stone", "Seacalm Gemstone",
        "Stone of Healing", "Gem of Incomparable Wellness"}
    assert {s.rating for s in stones} == {1, 2, 3, 4, 5}
    # Two per element, and the element is the tag that says which.
    elements = [t for s in stones for t in s.tags if t != "hearthstone"]
    assert sorted(elements) == sorted(["air"] * 2 + ["earth"] * 2 + ["fire"] * 2
                                      + ["water"] * 2 + ["wood"] * 2)
    # Nothing else in the catalogue moved off the Artifact Background — except the
    # merit-gated plot devices, which are off it for their own reason (a Merit is their
    # price, not dots) and are counted here so this stays a total.
    artifact_bought = artifacts_engine.purchasable_with_artifact(rs.artifact_catalog)
    gated = artifacts_engine.merit_gated(rs.artifact_catalog)
    assert len(artifact_bought) + len(stones) + len(gated) == len(rs.artifact_catalog)
    assert all(a.background == "artifact" and not a.requires_merit
               for a in artifact_bought)


def test_the_sample_virtue_flaws_load_keyed_to_their_virtue():
    """core pp.131-133. Ten sample Flaws, each springing from one Virtue — which is
    what the editor's dropdown filters on, since a Flaw must belong to a Virtue the
    character rates 3 or more (p.131) and the flawed Virtue is already chosen above it.
    A catalogue, never a constraint: the page says outright that these are not the only
    Flaws an Exalt might develop, so the description field stays free text."""
    rs = rules_db.load_ruleset(DATA_DIR)
    cat = rs.virtue_flaw_catalog
    assert len(cat) == 10
    by_virtue = {}
    for flaw in cat.values():
        by_virtue.setdefault(flaw.virtue.value, []).append(flaw.name)
    assert sorted(by_virtue["compassion"]) == ["Compassionate Martyrdom",
                                               "Heart of Tears",
                                               "Red Rage of Compassion"]
    assert sorted(by_virtue["conviction"]) == ["Deliberate Cruelty", "Heart of Flint"]
    assert sorted(by_virtue["temperance"]) == ["Ascetic Drive",
                                               "Contempt of the Virtuous",
                                               "Overindulgence"]
    assert sorted(by_virtue["valor"]) == ["Berserk Anger", "Foolhardy Contempt"]
    # Every one carries its printed Limit Break Condition — the half consulted at the
    # table, and the reason it is its own field rather than glued to the description.
    assert all(f.description and f.limit_break for f in cat.values())
    # Deliberate Cruelty prints a Conviction Flaw whose duration keys off TEMPERANCE.
    # Transcribed as printed, flagged in `notes`, NOT silently corrected.
    cruelty = cat["virtue-flaw.deliberate-cruelty"]
    assert "Temperance" in cruelty.description and cruelty.notes
