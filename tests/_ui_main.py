"""Helper 'main file' for the NiceGUI User-simulation regression test."""
import json
import tempfile
from pathlib import Path
from nicegui import ui
from exalted_builder import rules_db
from exalted_builder.engine import lifecycle
from exalted_builder.models.character import (
    MeritFlawPurchase,
    Armor, ArtSpecialty, BackgroundEntry, Character, CollegeRating, Damage,
    ArtifactEntry, FetterEntry, GearEntry, HearthstoneEntry, HouseRules,
    PassionEntry,
    PathRating, PlayState,
    RitualEntry, ScienceRating, Specialty, ThaumaturgyState, VirtueFlaw, Weapon)
from exalted_builder.engine import adversaries as adversaries_engine
from exalted_builder.models.adversary import (Adversary, AdversaryAttack,
                                              AdversaryTrait)
from exalted_builder.models.party import Party, PartyMember
from exalted_builder.models.rules import (AbilityName, AttributeName, Orientation,
                                          VirtueName)
from exalted_builder.ui import gear, advantages, app as sheet_app
from exalted_builder.ui import (builder, combos, custom, editor, gm, picker,
                                play, storyteller, view)

RS = rules_db.load_ruleset(Path("exalted_builder/data"))

# (a) a fresh character carrying off-catalog (custom) gear/nature — the "reload" path
CHAR_CUSTOM = Character(id="t", name="Test", caste="dawn", nature="Wanderer")
CHAR_CUSTOM.weapons.append(Weapon(name="My Custom Blade", accuracy=2, damage=5))
CHAR_CUSTOM.armor.append(Armor(name="My Plate", soak_lethal=4))
CHAR_CUSTOM.backgrounds.append(BackgroundEntry(name="", rating=1))   # a Background row to autofill

# (b) a blank weapon to type a new name into live
CHAR_BLANK = Character(id="b", name="Blank", caste="dawn")
CHAR_BLANK.weapons.append(Weapon(name="", accuracy=7, damage=9))

# (c) a character with some marked play-state, for the Play tab render test
CHAR_PLAY = Character(id="p", name="Player", caste="dawn")
CHAR_PLAY.play = PlayState(health=[Damage.BASHING, Damage.LETHAL], motes_personal_spent=3,
                          willpower_spent=1, limit=4)

# (d) a locked character with XP, for the XP tab render test (cards show only post-lock)
CHAR_XP = Character(id="x", name="Veteran", caste="dawn")
lifecycle.lock_chargen(CHAR_XP)
CHAR_XP.xp_earned = 30

# (e) a Dragon-Blooded (Fire aspect, Dynastic) — the Origin dropdown + DB budget headers
CHAR_DB = Character(id="d", name="Cathak", exalt_type="Dragon-Blooded", caste="fire",
                    origin="dynastic")
CHAR_DB.backgrounds.append(BackgroundEntry(name="", rating=1))       # a Background row to autofill

@ui.page('/custom')
def page_custom():
    editor.build_editor(RS, CHAR_CUSTOM, Path("x.json"), with_header=False)

# Off-catalogue gear renders on the GEAR tab now — the crash this guards against (a
# `ui.select` whose stored value is not in its options) followed the panels there.
@ui.page('/custom-gear')
def page_custom_gear():
    gear.build_gear(RS, CHAR_CUSTOM, Path("x.json"), with_header=False)

@ui.page('/blank')
def page_blank():
    editor.build_editor(RS, CHAR_BLANK, Path("x.json"), with_header=False)

# The same character's GEAR tab. Equipment moved off Edit on 2026-08-13, so a test
# about weapons, armour or goods opens this route and one about traits opens the other.
@ui.page('/blank-gear')
def page_blank_gear():
    gear.build_gear(RS, CHAR_BLANK, Path("x.json"), with_header=False)

@ui.page('/play')
def page_play():
    play.build_play(RS, CHAR_PLAY, Path("x.json"), with_header=False)

# (f) the dice-pool calculator (decision 0016) gets its OWN route and character:
# it reads the character's CONTENT (weapons, armour, specialties, marked damage), so
# sharing CHAR_PLAY would make this pass alone and fail in the suite.
CHAR_POOLS = Character(id="dp", name="Duelist", caste="dawn")
CHAR_POOLS.attributes[AttributeName.DEXTERITY] = 4
CHAR_POOLS.abilities[AbilityName.MELEE] = 3
CHAR_POOLS.abilities[AbilityName.DODGE] = 2
CHAR_POOLS.weapons.append(Weapon(name="Short Sword", accuracy=2, defense=3))
CHAR_POOLS.armor.append(Armor(name="Buff Jacket", soak_lethal=3, mobility_penalty=-1, fatigue=2))
CHAR_POOLS.specialties.append(Specialty(ability=AbilityName.MELEE, name="Swords", rating=2))
CHAR_POOLS.play = PlayState(health=[Damage.BASHING, Damage.LETHAL])

@ui.page('/pools')
def page_pools():
    play.build_play(RS, CHAR_POOLS, Path("x.json"), with_header=False)

# (g) the click test MUTATES its character's health marks, so it gets its own copy —
# a shared fixture whose CONTENT a test changes makes the next reader pass alone and
# fail in the suite.
CHAR_POOLS_CLICK = CHAR_POOLS.model_copy(deep=True)
CHAR_POOLS_CLICK.id = "dpc"

@ui.page('/pools-click')
def page_pools_click():
    play.build_play(RS, CHAR_POOLS_CLICK, Path("x.json"), with_header=False)

# (h) accumulated armour fatigue (p.332) — its own character, because the points
# subtract from every pool and would move every other route's expected total.
CHAR_POOLS_FATIGUE = CHAR_POOLS.model_copy(deep=True)
CHAR_POOLS_FATIGUE.id = "dpf"
CHAR_POOLS_FATIGUE.play = PlayState(fatigue=2)

@ui.page('/pools-fatigue')
def page_pools_fatigue():
    play.build_play(RS, CHAR_POOLS_FATIGUE, Path("x.json"), with_header=False)

# (i) the empty shape: a Mortal with no weapons, no armour, no specialties and no
# marked damage — every optional control in the calculator absent at once.
CHAR_POOLS_BARE = Character(id="dpb", name="Peasant", exalt_type="Mortal", caste="")

@ui.page('/pools-bare')
def page_pools_bare():
    play.build_play(RS, CHAR_POOLS_BARE, Path("x.json"), with_header=False)

@ui.page('/xp')
def page_xp():
    editor.build_editor(RS, CHAR_XP, Path("x.json"), with_header=False)

@ui.page('/xp-gear')
def page_xp_gear():
    gear.build_gear(RS, CHAR_XP, Path("x.json"), with_header=False)

@ui.page('/db')
def page_db():
    editor.build_editor(RS, CHAR_DB, Path("x.json"), with_header=False)

# Backgrounds live on the Advantages tab, so the splat-aware autofill list is checked
# there — a Dragon-Blooded gains Breeding/Connections and loses Contacts.
@ui.page('/db-advantages')
def page_db_advantages():
    advantages.build_advantages(RS, CHAR_DB, Path("x.json"), with_header=False)

@ui.page('/custom-advantages')
def page_custom_advantages():
    advantages.build_advantages(RS, CHAR_CUSTOM, Path("x.json"), with_header=False)

@ui.page('/dbpicker')
def page_dbpicker():
    # the charm-tree picker themed for a Dragon-Blooded character (red palette).
    # CHAR_DB holds no Immaculate Charm → the picker shows the STANDARD path banner.
    picker.build_picker(RS, CHAR_DB, Path("x.json"), with_header=True)

# (e2) a Dragon-Blooded already on the Immaculate path (holds Dragon-style Charms)
CHAR_DB_IMMACULATE = Character(id="di", name="Immaculate", exalt_type="Dragon-Blooded",
                               caste="air", origin="dynastic")
CHAR_DB_IMMACULATE.charms = ["dragonblooded.air-dragon.air-dragons-sight"]

@ui.page('/dbpicker-immaculate')
def page_dbpicker_immaculate():
    picker.build_picker(RS, CHAR_DB_IMMACULATE, Path("x.json"), with_header=True)

@ui.page('/dbsheet')
def page_dbsheet():
    # the read-only sheet, themed by the SheetView's exalt type
    sheet_app.render_sheet(view.build_sheet_view(RS, CHAR_DB))

# (f) a fresh Solar for the full builder app — changing its Exalt type live must
# re-theme the header/background chrome, not just the editor body.
CHAR_BUILDER = Character(id="bld", name="Fresh", caste="dawn")

@ui.page('/builder')
def page_builder():
    builder.build_app(RS, CHAR_BUILDER, Path("x.json"))

# (g) a Solar holding a described Charm + spell — the sheet shows their descriptions
CHAR_SHEET = Character(id="sh", name="Described", caste="dawn")
CHAR_SHEET.charms = ["solar.melee.fire-and-stones-strike"]
CHAR_SHEET.spells = ["spell.terrestrial.death-of-obsidian-butterflies"]

@ui.page('/sheet-desc')
def page_sheet_desc():
    sheet_app.render_sheet(view.build_sheet_view(RS, CHAR_SHEET))

# (h) an Abyssal — reaches BOTH tracks (sorcery + necromancy), so the picker's
# Spells page offers five Circles in its dropdown
CHAR_AB = Character(id="ab", name="Ash", exalt_type="Abyssal", caste="dusk", origin="loyal")

@ui.page('/abpicker')
def page_abpicker():
    picker.build_picker(RS, CHAR_AB, Path("x.json"), with_header=True)

# (h2) a modern Dragon-King — the Paths page (breed ★ + favoured ✚ + a rating), the
# breed soak/health, and the sheet's Paths / sectioned-charms panels.
CHAR_DK = Character(id="dk", name="Karn the Winged", exalt_type="Dragon-Kings",
                    caste="pterok", essence_rating=2)
CHAR_DK.virtues.update({"conviction": 3, "valor": 2, "compassion": 2, "temperance": 2})
CHAR_DK.favored_abilities = [AbilityName.MELEE, AbilityName.DODGE, AbilityName.SURVIVAL]
CHAR_DK.favored_path = "dk.solid-earth"
CHAR_DK.paths = [PathRating(path_id="dk.celestial-air", rating=3),
                 PathRating(path_id="dk.solid-earth", rating=2)]

@ui.page('/dksheet')
def page_dksheet():
    sheet_app.render_sheet(view.build_sheet_view(RS, CHAR_DK))

@ui.page('/dkpicker')
def page_dkpicker():
    picker.build_picker(RS, CHAR_DK, Path("x.json"), with_header=True)

# (h2b) a modern Dragon-King exercising the p.175 effective-over-5 attribute cap: a
# stored Dexterity 5 on the Pterok's +2 breed reads as an effective 7 on the sheet
# (the breed bonus stacks on top; the two effective dots above 5 are BP-bought at the
# attribute rate — this fixture is display-only, so no budget is asserted here).
CHAR_DK_BIG = Character(id="dkbig", name="Pterok Seer", exalt_type="Dragon-Kings",
                        caste="pterok", essence_rating=2)
CHAR_DK_BIG.virtues.update({"conviction": 3, "valor": 2, "compassion": 2, "temperance": 2})
CHAR_DK_BIG.favored_abilities = [AbilityName.MELEE, AbilityName.DODGE, AbilityName.SURVIVAL]
CHAR_DK_BIG.favored_path = "dk.solid-earth"
CHAR_DK_BIG.attributes[AttributeName.DEXTERITY] = 5

@ui.page('/dksheet-big')
def page_dksheet_big():
    sheet_app.render_sheet(view.build_sheet_view(RS, CHAR_DK_BIG))

# (i) an in-play (locked) Solar with XP in hand — the Charms and Combos tabs switch
# from picking to BUYING once chargen locks, so these pages exercise that mode.
CHAR_INPLAY = Character(id="ip", name="Veteran Solar", caste="dawn")
CHAR_INPLAY.abilities[AbilityName.MELEE] = 3
CHAR_INPLAY.charms = ["solar.melee.excellent-strike", "solar.melee.one-weapon-two-blows"]
lifecycle.lock_chargen(CHAR_INPLAY)
CHAR_INPLAY.xp_earned = 50
# build_picker returns its select(); calling it here opens the detail card on a
# given Charm, which is the only way to reach the buy button without a real tap.
# One route per Charm, so a test never has to reach back into this module.
@ui.page('/inplay-picker')
def page_inplay_picker():
    picker.build_picker(RS, CHAR_INPLAY, Path("x.json"), with_header=True)

@ui.page('/inplay-picker-buy')       # an available Charm — shows its XP price
def page_inplay_picker_buy():
    picker.build_picker(RS, CHAR_INPLAY, Path("x.json"),
                        with_header=True)("solar.melee.hungry-tiger-technique")

@ui.page('/inplay-picker-known')     # a Charm already known — no Remove in play
def page_inplay_picker_known():
    picker.build_picker(RS, CHAR_INPLAY, Path("x.json"),
                        with_header=True)("solar.melee.excellent-strike")

# (j) its own fresh character for the lock-swaps-the-tab-bar test
CHAR_LOCKME = Character(id="lk", name="Locks", caste="dawn")

@ui.page('/builder-lock')
def page_builder_lock():
    builder.build_app(RS, CHAR_LOCKME, Path("x.json"))

@ui.page('/inplay-combos')
def page_inplay_combos():
    combos.build_combos(RS, CHAR_INPLAY, Path("x.json"), with_header=False)

# (k) the GM party page. A @ui.page route builds once per session, so each GM test
# gets its OWN party and context — never a shared one — or one test's clicks leak
# into the next test's assertions.
def _gm_ctx(*members):
    ctx = builder.make_context(Character(id="solo", name="Solo"), Path("x.json"))
    ctx["party"] = Party(id="p", name="Tuesday Game",
                         members=[PartyMember(character=c) for c in members])
    return ctx

# a mixed-splat party: the cards must show each member's own splat vocabulary
GM_MIXED = _gm_ctx(
    Character(id="g1", name="Ashes of Dawn", caste="dawn"),
    Character(id="g2", name="Cathak Jade", exalt_type="Dragon-Blooded", caste="fire"))

@ui.page('/gm')
def page_gm():
    gm.build_gm(RS, GM_MIXED, with_header=False)

# an empty party — the page must say so rather than render a bare grid
GM_EMPTY = _gm_ctx()

@ui.page('/gm-empty')
def page_gm_empty():
    gm.build_gm(RS, GM_EMPTY, with_header=False)

# its own party for the click test, so the marks it makes are its alone
GM_CLICK = _gm_ctx(Character(id="c1", name="First", caste="dawn"),
                   Character(id="c2", name="Second", caste="dawn"))

@ui.page('/gm-click')
def page_gm_click():
    gm.build_gm(RS, GM_CLICK, with_header=False)

GM_CYCLE = _gm_ctx(Character(id="cy", name="Cycler", caste="dawn"))

@ui.page('/gm-cycle')
def page_gm_cycle():
    gm.build_gm(RS, GM_CYCLE, with_header=False)

GM_PENALTY = _gm_ctx(Character(id="pn", name="Wounded", caste="dawn"))

@ui.page('/gm-penalty')
def page_gm_penalty():
    gm.build_gm(RS, GM_PENALTY, with_header=False)

# (k2) the adversary roster. Its own party again, and its own catalogue: the
# templates are passed through the context, so a test can hand the page exactly
# the rows it wants to assert on rather than depending on data/adversaries.json.
ADV_TEMPLATE = Adversary(
    id="adv.tpl.thug", name="Hired Thug", category="Extra", base_initiative=4,
    willpower=3, virtues={"valor": 2},
    health_levels=adversaries_engine.expand_health("-1/-3/I"))

def _adv_ctx(*entries, catalog=True):
    ctx = _gm_ctx(Character(id="pc", name="Player One", caste="dawn"))
    ctx["adversary_catalog"] = {ADV_TEMPLATE.id: ADV_TEMPLATE} if catalog else {}
    ctx["party"].adversaries = list(entries)
    return ctx

# an empty roster — the section must invite rather than render a bare grid
GM_ADV_EMPTY = _adv_ctx()

@ui.page('/gm-adv-empty')
def page_gm_adv_empty():
    gm.build_gm(RS, GM_ADV_EMPTY, with_header=False)

# a populated roster: a beast with no dodge and an armoured NPC, so the card's
# stat line is asserted on both branches of the nullable dodge.
GM_ADV = _adv_ctx(
    Adversary(id="adv.1", name="Bear", category="Beast", base_initiative=5,
              dodge=None, soak_lethal=3, soak_bashing=6, willpower=3,
              attributes={"strength": 7, "dexterity": 2, "stamina": 6},
              abilities=[AdversaryTrait(name="Brawl", rating=3)],
              attacks=[AdversaryAttack(name="Bite", speed=2, accuracy=6, damage=8,
                                       damage_type="L")],
              health_levels=adversaries_engine.expand_health("-0/-1 x 2/-2/-4/I")),
    Adversary(id="adv.2", name="Sad Ivory", category="NPC", base_initiative=8,
              dodge=9, willpower=8, essence=4, personal_essence=16,
              peripheral_essence=47, nature="Bravo",
              charms="Adds dice to Melee and Archery as a supplemental action.",
              health_levels=adversaries_engine.expand_health("-0/-1/-1/-2/-4/I")))

@ui.page('/gm-adv')
def page_gm_adv():
    gm.build_gm(RS, GM_ADV, with_header=False)

# its own roster for the click tests, so its marks and duplicates are its alone
GM_ADV_CLICK = _adv_ctx(
    Adversary(id="adv.c", name="Bandit", category="Extra", base_initiative=4,
              willpower=3, health_levels=adversaries_engine.expand_health("-1/-3/I")))

@ui.page('/gm-adv-click')
def page_gm_adv_click():
    gm.build_gm(RS, GM_ADV_CLICK, with_header=False)

GM_ADV_ADD = _adv_ctx()

@ui.page('/gm-adv-add')
def page_gm_adv_add():
    gm.build_gm(RS, GM_ADV_ADD, with_header=False)

# a BARE entry: no health track, no Willpower, no motes, no attacks. Every
# tracker on the card is conditional, so this is the shape that finds a card
# which only renders when it happens to have something to render.
GM_ADV_BARE = _adv_ctx(Adversary(id="adv.bare", name="Nameless Thing"))

@ui.page('/gm-adv-bare')
def page_gm_adv_bare():
    gm.build_gm(RS, GM_ADV_BARE, with_header=False)

# an entry using the SPIRIT mote shape (one pool) rather than the Exalted split
GM_ADV_SPIRIT = _adv_ctx(
    Adversary(id="adv.sp", name="Hungry Ghost", category="Undead", essence=1,
              essence_pool=39, cost_to_materialize=40, willpower=5,
              powers="Cunning Thief, Measure the Wind",
              health_levels=adversaries_engine.expand_health("-0/-1/-2/I")))

@ui.page('/gm-adv-spirit')
def page_gm_adv_spirit():
    gm.build_gm(RS, GM_ADV_SPIRIT, with_header=False)

# NO catalogue at all: the Add dialog must still work, offering a blank only.
GM_ADV_NOCAT = _adv_ctx(catalog=False)

@ui.page('/gm-adv-nocat')
def page_gm_adv_nocat():
    gm.build_gm(RS, GM_ADV_NOCAT, with_header=False)

# the REAL shipped catalogue, loaded off disk — proves the authored data renders,
# which no hand-built fixture can.
GM_ADV_REAL = _adv_ctx()
GM_ADV_REAL["adversary_catalog"] = rules_db.load_adversary_catalog(
    Path("exalted_builder/data"))
GM_ADV_REAL["party"].adversaries = [
    adversaries_engine.instantiate(GM_ADV_REAL["adversary_catalog"][k], f"adv.r{i}")
    for i, k in enumerate(("adv.extra_weak", "adv.beast_bear", "adv.militia",
                           "adv.zephyr", "adv.elite_troops"))]

@ui.page('/gm-adv-real')
def page_gm_adv_real():
    gm.build_gm(RS, GM_ADV_REAL, with_header=False)

# (f) a Sidereal with Astrological Colleges — the sheet panel and the XP tab's
# College buy/raise rows (both are Sidereal-only, gated on b.college_dots).
CHAR_SID = Character(id="s", name="Chosen of Battles", exalt_type="Sidereal", caste="battles")
CHAR_SID.colleges = [
    CollegeRating(college_id="sidereal.battles.shield", rating=2),    # own Maiden (star)
    CollegeRating(college_id="sidereal.journeys.gull", rating=1),
]

@ui.page('/sidsheet')
def page_sid_sheet():
    sheet_app.render_sheet(view.build_sheet_view(RS, CHAR_SID))

CHAR_SID_XP = Character(id="sx", name="Locked Sidereal", exalt_type="Sidereal", caste="battles")
CHAR_SID_XP.colleges = [CollegeRating(college_id="sidereal.battles.shield", rating=2)]
lifecycle.lock_chargen(CHAR_SID_XP)
CHAR_SID_XP.xp_earned = 40

@ui.page('/sidxp')
def page_sid_xp():
    editor.build_editor(RS, CHAR_SID_XP, Path("x.json"), with_header=False)

# (g) an Illuminated Solar (Cult of the Illuminated) — the editor's Training Camp +
# Calling panel, the ✧ Calling marks on the Abilities panel, the granted-Charm rows on
# the sheet, and the picker's Calling/granted tags. One route per test.
def _illuminated(cid: str) -> Character:
    c = Character(id=cid, name="Shining One", exalt_type="Solar", caste="dawn",
                  origin="illuminated", camp="kether-rock", calling="deacon",
                  essence_rating=3)
    c.abilities[AbilityName.BRAWL] = 1
    c.abilities[AbilityName.ENDURANCE] = 1
    c.abilities[AbilityName.MEDICINE] = 1
    c.abilities[AbilityName.MELEE] = 2
    c.abilities[AbilityName.PRESENCE] = 1
    c.abilities[AbilityName.RESISTANCE] = 1
    c.abilities[AbilityName.SURVIVAL] = 3
    c.granted_charms = list(RS.camps["kether-rock"].granted_charms) + [
        "solar.resistance.durability-of-oak-meditation",
        "solar.resistance.iron-skin-concentration"]
    return c

CHAR_ILL_EDIT = _illuminated("i1")

@ui.page('/ill-editor')
def page_ill_editor():
    editor.build_editor(RS, CHAR_ILL_EDIT, Path("i.json"), with_header=False)

CHAR_ILL_SHEET = _illuminated("i2")

@ui.page('/ill-sheet')
def page_ill_sheet():
    sheet_app.render_sheet(view.build_sheet_view(RS, CHAR_ILL_SHEET))

# The Tabernacle variant exercises the OTHER grant shape — "two Charms from one of four
# martial arts" rather than "one of these pairs".
CHAR_ILL_TAB = Character(id="i3", name="Tabernacle", exalt_type="Solar", caste="zenith",
                         origin="illuminated", camp="sequestered-tabernacle",
                         calling="exemplar", essence_rating=3)
# Resolve the style choice, so the select renders its chosen value. A closed
# ui.select puts only its VALUE in the DOM, never its option list — the options are
# covered by a presenter test instead (test_illuminated.py).
_SNAKE = sorted((c for c in RS.charms.values() if c.category == "martial_arts:snake"),
                key=lambda c: (c.min_ability, c.min_essence, c.name))[:2]
CHAR_ILL_TAB.granted_charms = (list(RS.camps["sequestered-tabernacle"].granted_charms)
                               + [c.id for c in _SNAKE])
CHAR_ILL_TAB.abilities[AbilityName.MARTIAL_ARTS] = 5
CHAR_ILL_TAB.abilities[AbilityName.PRESENCE] = 3

@ui.page('/ill-editor-tabernacle')
def page_ill_editor_tab():
    editor.build_editor(RS, CHAR_ILL_TAB, Path("i3.json"), with_header=False)

# A Cult DRAGON-BLOODED (Cult p.96) — the second splat to own training camps, and the
# first flat-pool grant ("three Charms from five styles or Ox-Body Technique", picked
# in any combination). Two shapes need a render route rather than a unit test: the
# pool choice renders ONE control where a category choice renders two, and a camp id
# belonging to the other splat's Cult is a value outside the select's options, which
# `ui.select` raises on at build time.
def _cult_db(cid: str, camp: str) -> Character:
    c = Character(id=cid, name="Cult Terrestrial", exalt_type="Dragon-Blooded",
                  caste="fire", origin="illuminated", camp=camp, essence_rating=2)
    for ability, dots in ((AbilityName.BRAWL, 1), (AbilityName.ENDURANCE, 1),
                          (AbilityName.MEDICINE, 1), (AbilityName.MELEE, 2),
                          (AbilityName.PRESENCE, 3), (AbilityName.RESISTANCE, 1),
                          (AbilityName.SURVIVAL, 3), (AbilityName.MARTIAL_ARTS, 5),
                          (AbilityName.LINGUISTICS, 1), (AbilityName.LORE, 1),
                          (AbilityName.OCCULT, 1), (AbilityName.SOCIALIZE, 1)):
        c.abilities[ability] = dots
    return c

CHAR_CULT_DB = _cult_db("cdb1", "sequestered-tabernacle-db")
# Resolve the pool with three Charms from TWO different styles — the combination a
# category choice would reject and this shape must accept.
_EBON = sorted((c for c in RS.charms.values() if c.category == "martial_arts:ebon-shadow"),
               key=lambda c: (c.min_ability, c.min_essence, c.name))[:2]
_TIGER = sorted((c for c in RS.charms.values() if c.category == "martial_arts:tiger"),
                key=lambda c: (c.min_ability, c.min_essence, c.name))[:1]
CHAR_CULT_DB.granted_charms = (
    list(RS.camps["sequestered-tabernacle-db"].granted_charms)
    + [c.id for c in _EBON + _TIGER])

@ui.page('/cult-db-editor')
def page_cult_db_editor():
    editor.build_editor(RS, CHAR_CULT_DB, Path("cdb1.json"), with_header=False)

# The crash shape: a Dragon-Blooded holding the SOLAR Cult's camp id. `camp_for`
# resolves it against the whole table, so the select would be handed a value none of
# its options carry.
CHAR_CULT_DB_CROSSED = _cult_db("cdb2", "kether-rock")
CHAR_CULT_DB_CROSSED.calling = "deacon"

@ui.page('/cult-db-crossed')
def page_cult_db_crossed():
    editor.build_editor(RS, CHAR_CULT_DB_CROSSED, Path("cdb2.json"), with_header=False)

# A plain Solar, for the test that the Origin dropdown renders at all and offers the
# Illuminated option — it was missing from _SPLAT_ORIGINS on the first pass, which made
# the whole origin unselectable while every engine test passed.
CHAR_SOLAR_ORIGIN = Character(id="so", name="Plain Solar", exalt_type="Solar", caste="dawn")

@ui.page('/solar-origin')
def page_solar_origin():
    editor.build_editor(RS, CHAR_SOLAR_ORIGIN, Path("so.json"), with_header=False)

if __name__ in {"__main__", "__mp_main__"}:
    ui.run()


# --- The Outcaste Dragon-Blooded origins (upbringing axis) ------------------- #
# A Lookshy character exercises the new second dropdown AND the origin-granted Charm
# rows. A ui.select whose value is not in its options raises at RENDER time, and the
# upbringing select is seeded from character state, so this is exactly the shape that
# needs a render route rather than a unit test.
CHAR_LOOKSHY = Character(id="lk1", name="Karal Fire Orchid", exalt_type="Dragon-Blooded",
                         caste="air", origin="lookshy", upbringing="foreign",
                         essence_rating=2)
CHAR_LOOKSHY.abilities[AbilityName.LINGUISTICS] = 3
CHAR_LOOKSHY.abilities[AbilityName.SAIL] = 2

@ui.page('/lookshy-editor')
def page_lookshy_editor():
    editor.build_editor(RS, CHAR_LOOKSHY, Path("lk.json"), with_header=False)

CHAR_LOOKSHY_SHEET = Character(id="lk2", name="Karal Fire Orchid",
                               exalt_type="Dragon-Blooded", caste="air",
                               origin="lookshy", essence_rating=2)

@ui.page('/lookshy-sheet')
def page_lookshy_sheet():
    sheet_app.render_sheet(view.build_sheet_view(RS, CHAR_LOOKSHY_SHEET))


# --- Thaumaturgy (Player's Guide CH3) --------------------------------------- #
# The picker's Thaumaturgy page and the Storyteller-options tab. Occult 3 is the
# interesting rating: it opens Summoning, Warding and Exorcism but leaves Astrology
# (Occult 4) locked, and it makes level-3 rituals legal — so one character exercises
# both the available and the locked branch of every gate.
def _thaumaturge(cid: str, occult: int = 3) -> Character:
    c = Character(id=cid, name="Hedge Wizard", exalt_type="Solar", caste="twilight")
    c.abilities[AbilityName.OCCULT] = occult
    return c

CHAR_THAUM = _thaumaturge("th1")

@ui.page('/thaum-picker')
def page_thaum_picker():
    picker.build_picker(RS, CHAR_THAUM, Path("th.json"), with_header=True,
                        initial_group="thaum")

# A thaumaturge who already holds one of each kind, so the owned-row controls (drop,
# add-orientation, the "Bought" summary) are on the page.
CHAR_THAUM_OWNED = _thaumaturge("th2")
CHAR_THAUM_OWNED.thaumaturgy = ThaumaturgyState(
    arts=["art.warding"],
    art_specialties=[ArtSpecialty(art_id="art.warding", name="Ghosts")],
    sciences=[ScienceRating(science_id="science.alchemy", rating=2)],
    rituals=[RitualEntry(ritual_id="ritual.calling-the-flames-beneficence",
                         level=1, orientations=[Orientation.REALM])],
)

@ui.page('/thaum-picker-owned')
def page_thaum_picker_owned():
    picker.build_picker(RS, CHAR_THAUM_OWNED, Path("th2.json"), with_header=True,
                        initial_group="thaum")

# Locked + XP in hand: the page switches from bonus points to experience.
CHAR_THAUM_INPLAY = _thaumaturge("th3")
lifecycle.lock_chargen(CHAR_THAUM_INPLAY)
CHAR_THAUM_INPLAY.xp_earned = 40

@ui.page('/thaum-picker-inplay')
def page_thaum_picker_inplay():
    picker.build_picker(RS, CHAR_THAUM_INPLAY, Path("th3.json"), with_header=True,
                        initial_group="thaum")

# "Magic for Everyone" on, at Occult 4 -> a 2-purchase free grant, which the page
# must announce even before anything is bought.
CHAR_THAUM_MFE = _thaumaturge("th4", occult=4)
CHAR_THAUM_MFE.house_rules = HouseRules(magic_for_everyone=True)

@ui.page('/thaum-picker-mfe')
def page_thaum_picker_mfe():
    picker.build_picker(RS, CHAR_THAUM_MFE, Path("th4.json"), with_header=True,
                        initial_group="thaum")

# --- Storyteller options tab ------------------------------------------------ #
CHAR_ST = Character(id="st1", name="Table Rules", caste="dawn")

@ui.page('/st-options')
def page_st_options():
    storyteller.build_storyteller(RS, CHAR_ST, Path("st.json"), with_header=False)

# An Eclipse: the per-character foreign-Charm permission actually bites here, so it
# renders without the "no effect" note that a Dawn gets.
CHAR_ST_ECLIPSE = Character(id="st2", name="Eclipse", caste="eclipse")

@ui.page('/st-options-eclipse')
def page_st_options_eclipse():
    storyteller.build_storyteller(RS, CHAR_ST_ECLIPSE, Path("st2.json"), with_header=False)

# Locked: the toggles are frozen into the chargen snapshot, so the tab is read-only.
CHAR_ST_LOCKED = Character(id="st3", name="Locked Table", caste="dawn")
lifecycle.lock_chargen(CHAR_ST_LOCKED)

@ui.page('/st-options-locked')
def page_st_options_locked():
    storyteller.build_storyteller(RS, CHAR_ST_LOCKED, Path("st3.json"), with_header=False)


# A thaumaturge's read-only sheet, and their XP ledger. Thaumaturgy is cross-splat,
# so the sheet panel can appear on any character — and must be absent from every
# character who bought none, which /sheet-desc already covers.
CHAR_THAUM_SHEET = Character(id="th5", name="Hedge Wizard", exalt_type="Solar",
                             caste="twilight")
CHAR_THAUM_SHEET.abilities[AbilityName.OCCULT] = 3
CHAR_THAUM_SHEET.thaumaturgy = ThaumaturgyState(
    arts=["art.warding"],
    art_specialties=[ArtSpecialty(art_id="art.warding", name="Ghosts")],
    sciences=[ScienceRating(science_id="science.geomancy", rating=2)],
    rituals=[RitualEntry(ritual_id="ritual.calling-the-flames-beneficence",
                         level=1, orientations=[Orientation.REALM, Orientation.NORTH])],
)

@ui.page('/thaum-sheet')
def page_thaum_sheet():
    sheet_app.render_sheet(view.build_sheet_view(RS, CHAR_THAUM_SHEET))

# A locked thaumaturge with a spent ledger — the XP tab must name each purchase
# rather than printing the raw log target.
CHAR_THAUM_XP = Character(id="th6", name="Veteran Thaumaturge", exalt_type="Solar",
                          caste="twilight")
CHAR_THAUM_XP.abilities[AbilityName.OCCULT] = 4
lifecycle.lock_chargen(CHAR_THAUM_XP)
CHAR_THAUM_XP.xp_earned = 100
picker.buy_thaum_art(RS, CHAR_THAUM_XP, "art.warding")
picker.raise_thaum_science(RS, CHAR_THAUM_XP, "science.alchemy")
picker.buy_thaum_entry(RS, CHAR_THAUM_XP, "ritual",
                       "ritual.warding-of-undue-influence", Orientation.REALM)
picker.add_thaum_orientation(RS, CHAR_THAUM_XP, "ritual",
                             "ritual.warding-of-undue-influence", Orientation.NORTH)

@ui.page('/thaum-xp')
def page_thaum_xp():
    editor.build_editor(RS, CHAR_THAUM_XP, Path("th6.json"), with_header=False)


# Its own character for the ST-tab test, so clicking a toggle here cannot leak into
# another builder test's assertions.
CHAR_BUILDER_ST = Character(id="bst", name="Table", caste="dawn")

@ui.page('/builder-st')
def page_builder_st():
    builder.build_app(RS, CHAR_BUILDER_ST, Path("bst.json"))


# --------------------------------------------------------------------------- #
# The custom-content page. Its own throwaway library under the OS temp dir, seeded
# with one good row and one that the loader must reject, so the page's two list
# states (valid / invalid-with-a-reason) both render. A separate RuleSet, because
# the page mutates the one it is given and no other test's assertions should move.
# --------------------------------------------------------------------------- #
CUSTOM_DIR = Path(tempfile.mkdtemp(prefix="exalted-ui-custom-"))
(CUSTOM_DIR / "charms").mkdir(parents=True, exist_ok=True)
(CUSTOM_DIR / "charms" / "custom-charms.json").write_text(json.dumps([
    {"id": "custom.house-strike", "name": "House Strike", "category": "melee",
     "type": "Supplemental", "min_ability": 2, "min_essence": 1,
     "cost": {"motes": 3}, "description": "A homebrew Melee Charm."},
    {"id": "custom.orphan", "name": "Orphan Charm", "category": "melee",
     "type": "Supplemental", "prerequisites": [["no-such-charm"]]},
]))
RS_CUSTOM = rules_db.load_ruleset(Path("exalted_builder/data"), custom_dir=CUSTOM_DIR)

@ui.page('/custom-content')
def page_custom_content():
    custom.build_custom(RS_CUSTOM, custom_dir=CUSTOM_DIR, with_header=False)

# A character holding the seeded homebrew Charm: the sheet must badge it as custom.
CHAR_CUSTOM_CHARM = Character(id="cc", name="Homebrewer", caste="dawn")
CHAR_CUSTOM_CHARM.charms = ["custom.house-strike"]
CHAR_CUSTOM_CHARM.spells = ["custom.gone-missing"]     # never defined -> the ⚠ row

@ui.page('/custom-sheet')
def page_custom_sheet():
    sheet_app.render_sheet(view.build_sheet_view(RS_CUSTOM, CHAR_CUSTOM_CHARM))

# (h) a Mortal: the first CASTELESS splat. Its editor must render with no caste
# dropdown and no caste-info box, and its sheet must lay Abilities out by the
# default grouping rather than blank (adding-a-splat.md traps #3 and #5).
CHAR_MORTAL = Character(id="mt", name="Nine Cups", exalt_type="Mortal", caste="",
                        origin="heroic", essence_rating=1)

@ui.page('/mortal')
def page_mortal():
    editor.build_editor(RS, CHAR_MORTAL, Path("x.json"), with_header=False)

@ui.page('/mortal-sheet')
def page_mortal_sheet():
    sheet_app.render_sheet(view.build_sheet_view(RS, CHAR_MORTAL))

# A mortal's Charm picker: they have NO Charms, so the Abilities/Martial Arts pages
# must not be offered at all. Building the Category dropdown with an empty option
# list raises at BUILD time and takes every sibling tab down with it — this page is
# the regression guard for that (reported 2026-07-30: Abilities AND Thaumaturgy both
# rendered blank).
@ui.page('/mortalpicker')
def page_mortalpicker():
    picker.build_picker(RS, CHAR_MORTAL, Path("x.json"), with_header=False)

# A mortal holding Merits: the editor's Merits panel and the sheet's block must both
# render, including the variable-cost row (Oathbound Magic) whose tier/arena controls
# only exist for that entry.
CHAR_MERITS = Character(id="mf", name="Oathsworn", exalt_type="Mortal", caste="",
                        origin="heroic", essence_rating=1)
CHAR_MERITS.merits_flaws = [
    MeritFlawPurchase(merit_id="thaum.essence-awareness"),
    MeritFlawPurchase(merit_id="thaum.essence-mastery"),
    MeritFlawPurchase(merit_id="thaum.oathbound-magic", tier="major", arena="combat",
                      detail="Never raise a hand in anger: +1 Strength"),
    MeritFlawPurchase(merit_id="thaum.gone-missing"),      # unresolvable -> the warn row
]

@ui.page('/merits')
def page_merits():
    advantages.build_advantages(RS, CHAR_MERITS, Path("x.json"), with_header=False)

# The Essence dot row's Merit-override pips (2026-08-06 regression fix): post-lock the
# row is capped by the splat ceiling UNLESS the calc's essence_cap_override lifts it —
# Essence Mastery on a mortal (p.114), Awakened Essence on a God-Blooded. Three shapes:
# a mortal with the Merit (3 pips), a God-Blooded with it (3 pips), and a plain locked
# mortal (still 1 pip, so the override is not leaking into the ordinary case).
CHAR_MORTAL_ESS = Character(id="me", name="Seer", exalt_type="Mortal", caste="",
                            origin="heroic", essence_rating=1)
CHAR_MORTAL_ESS.merits_flaws = [MeritFlawPurchase(merit_id="thaum.essence-mastery")]
lifecycle.lock_chargen(CHAR_MORTAL_ESS, RS)
CHAR_MORTAL_ESS.xp_earned = 200

CHAR_GB_AWAKENED = Character(id="ga", name="Awakened", exalt_type="God-Blooded",
                             caste="ghost-blooded", essence_rating=1)
CHAR_GB_AWAKENED.virtues = {VirtueName.COMPASSION: 2, VirtueName.CONVICTION: 3,
                            VirtueName.TEMPERANCE: 2, VirtueName.VALOR: 2}
CHAR_GB_AWAKENED.merits_flaws = [MeritFlawPurchase(merit_id="mf.awakened-essence")]
lifecycle.lock_chargen(CHAR_GB_AWAKENED, RS)
CHAR_GB_AWAKENED.xp_earned = 200

CHAR_MORTAL_PLAIN = Character(id="mp", name="Plain", exalt_type="Mortal", caste="",
                              origin="heroic", essence_rating=1)
lifecycle.lock_chargen(CHAR_MORTAL_PLAIN, RS)

@ui.page('/essence-cap-mortal')
def page_essence_cap_mortal():
    editor.build_editor(RS, CHAR_MORTAL_ESS, Path("x.json"), with_header=False)

@ui.page('/essence-cap-gb')
def page_essence_cap_gb():
    editor.build_editor(RS, CHAR_GB_AWAKENED, Path("x.json"), with_header=False)

@ui.page('/essence-cap-plain')
def page_essence_cap_plain():
    editor.build_editor(RS, CHAR_MORTAL_PLAIN, Path("x.json"), with_header=False)

# The OTHER mortal picker shape: a mortal whose Merits reopen part of the Charm bar.
# `/mortalpicker` proves the pages vanish when there is nothing to show; these two
# prove they come BACK — Martial Arts and Spells both, unlocked and locked. The
# locked one is the shape a player reported broken (2026-07-31): buying with XP asked
# the splat's flat charms_available flag and never asked the Merit.
def _mastery_mortal(cid: str, name: str) -> Character:
    c = Character(id=cid, name=name, exalt_type="Mortal", caste="", origin="heroic",
                  essence_rating=1)
    c.abilities[AbilityName.MARTIAL_ARTS] = 3
    c.abilities[AbilityName.OCCULT] = 3
    c.merits_flaws = [MeritFlawPurchase(merit_id="thaum.essence-awareness"),
                      MeritFlawPurchase(merit_id="thaum.essence-mastery")]
    return c

CHAR_MASTERY = _mastery_mortal("mm", "Unbound")

@ui.page('/mastery-picker')
def page_mastery_picker():
    picker.build_picker(RS, CHAR_MASTERY, Path("x.json"), with_header=False)

CHAR_MASTERY_XP = _mastery_mortal("mm2", "Unbound Veteran")
lifecycle.lock_chargen(CHAR_MASTERY_XP, RS)
CHAR_MASTERY_XP.xp_earned = 60

@ui.page('/mastery-picker-xp')
def page_mastery_picker_xp():
    picker.build_picker(RS, CHAR_MASTERY_XP, Path("x.json"), with_header=False)

# A mortal at the Essence-3 human ceiling with an unlocked pool. The editor shows
# PG p.114's "limit of human potential — mortals that exceed Essence 3 become gods"
# beside the track there and only there: a plain mortal (no unlock), an unlocked
# mortal still below 3, and an AWARENESS-ONLY mortal (pool unlocked but no cap
# override — real ceiling 1) must all stay silent. One route per character.
CHAR_GOD_CEILING = _mastery_mortal("mgc", "Glorious Once-Born")
CHAR_GOD_CEILING.essence_rating = 3
lifecycle.lock_chargen(CHAR_GOD_CEILING, RS)

@ui.page('/editor-god-ceiling')
def page_editor_god_ceiling():
    editor.build_editor(RS, CHAR_GOD_CEILING, Path("x.json"), with_header=False)

CHAR_MASTERY_EDITOR = _mastery_mortal("mm3", "Unbound Below")

@ui.page('/editor-mastery-mortal')
def page_editor_mastery_mortal():
    editor.build_editor(RS, CHAR_MASTERY_EDITOR, Path("x.json"), with_header=False)

# The wrong-field regression: Awareness-only, pool unlocked but no cap override, its
# free-setter dot track clicked to 3 pre-lock. The god-transition clause must NOT
# blame itself — the real ceiling here is 1, and the +1 would be refused at 1.
CHAR_AWARENESS_ONLY = Character(id="maw", name="Glimmering", exalt_type="Mortal",
                                caste="", origin="heroic", essence_rating=3)
CHAR_AWARENESS_ONLY.merits_flaws = [MeritFlawPurchase(merit_id="thaum.essence-awareness")]

@ui.page('/editor-awareness-only')
def page_editor_awareness_only():
    editor.build_editor(RS, CHAR_AWARENESS_ONLY, Path("x.json"), with_header=False)

# A6: a Solar holding Heir Apparent (whose purchase records STIPULATIONS, a control no
# other entry gets) and Innocuous' veiled tier (which caps Allies and closes Cult, so
# the Background dot rows must stop where the Flaw says).
CHAR_BG_MERITS = Character(id="mfbg", name="Heir", exalt_type="Solar", caste="dawn",
                           essence_rating=1)
CHAR_BG_MERITS.merits_flaws = [
    MeritFlawPurchase(merit_id="mf.heir-apparent", tier="3", stipulations=2),
    MeritFlawPurchase(merit_id="mf.innocuous", tier="4"),
    # Cluster 7: an entry whose trait prerequisite must be VISIBLE in the row, not just
    # reported as an issue after the player has already picked it.
    MeritFlawPurchase(merit_id="mf.cache", points=2),
]
CHAR_BG_MERITS.backgrounds = [
    BackgroundEntry(name="Allies", rating=2),
    BackgroundEntry(name="Resources", rating=5),
]

@ui.page('/merits-backgrounds')
def page_merits_backgrounds():
    advantages.build_advantages(RS, CHAR_BG_MERITS, Path("x.json"), with_header=False)

# The same character, locked — the per-row Background descriptions print in play too,
# where the rows swap the dot track for a plain number.
CHAR_BG_MERITS_XP = CHAR_BG_MERITS.model_copy(deep=True)
CHAR_BG_MERITS_XP.id = "bgx"
CHAR_BG_MERITS_XP.chargen_locked = True

@ui.page('/backgrounds-description-xp')
def page_backgrounds_description_xp():
    advantages.build_advantages(RS, CHAR_BG_MERITS_XP, Path("x.json"), with_header=False)

# A7: an Abyssal whose Resonance track is BOTH renamed and shortened, who has a
# permanent Resonance counter, and who holds both luck pools at once.
CHAR_PLAY_MERITS = Character(id="mfplay", name="Ashen", exalt_type="Abyssal",
                             caste="dusk", essence_rating=3, limit_permanent=2)
CHAR_PLAY_MERITS.merits_flaws = [
    MeritFlawPurchase(merit_id="mf.greater-curse", tier="3"),
    MeritFlawPurchase(merit_id="mf.death-taint", points=6),
    MeritFlawPurchase(merit_id="mf.lucky", tier="2"),
    MeritFlawPurchase(merit_id="mf.unlucky", tier="1"),
]

@ui.page('/merits-play')
def page_merits_play():
    play.build_play(RS, CHAR_PLAY_MERITS, Path("x.json"), with_header=False)

# The same character, locked, so the XP tab's permanent-Resonance panel renders — the
# tracker tells the ST to come here, so this must actually exist.
CHAR_RESONANCE_XP = CHAR_PLAY_MERITS.model_copy(deep=True)
CHAR_RESONANCE_XP.id = "mfxp"
CHAR_RESONANCE_XP.chargen_locked = True
CHAR_RESONANCE_XP.xp_earned = 20

@ui.page('/merits-resonance-xp')
def page_merits_resonance_xp():
    editor.build_editor(RS, CHAR_RESONANCE_XP, Path("x.json"), with_header=False)

# Ruling 1 of the Advantages plan: the shared bonus-point readout. A Solar with a
# 5-point Merit has spent bonus points on THIS tab, and the total must be visible here
# rather than only on the Edit tab the player cannot see from here.
CHAR_ADV_BP = Character(id="advbp", name="Spender", exalt_type="Solar", caste="dawn",
                        essence_rating=1)
CHAR_ADV_BP.merits_flaws = [MeritFlawPurchase(merit_id="mf.legendary-attribute",
                                              detail="Strength")]

@ui.page('/advantages-bp')
def page_advantages_bp():
    advantages.build_advantages(RS, CHAR_ADV_BP, Path("x.json"), with_header=False)

@ui.page('/advantages-bp-edit')
def page_advantages_bp_edit():
    editor.build_editor(RS, CHAR_ADV_BP, Path("x.json"), with_header=False)

# A save whose structured detail is off-list — "strength", not "Strength". validate
# accepts it (it title-cases before comparing), so nothing else in the build objects,
# and `ui.select` would raise at BUILD time and blank the whole tab.
CHAR_ADV_ODD = Character(id="advodd", name="Oddly", exalt_type="Solar", caste="dawn",
                         essence_rating=1)
CHAR_ADV_ODD.merits_flaws = [
    MeritFlawPurchase(merit_id="mf.legendary-attribute", detail="strength"),
    MeritFlawPurchase(merit_id="mf.diminished-attributes", points=3, detail="nonsense"),
]

@ui.page('/advantages-odd-detail')
def page_advantages_odd_detail():
    advantages.build_advantages(RS, CHAR_ADV_ODD, Path("x.json"), with_header=False)

# Render-matrix shapes for the Advantages tab. A CASTELESS splat (Mortal) unlocked —
# every caste-keyed lookup on this tab takes `character.caste == ""` — and a save
# holding an id the catalogue has never heard of, which is what opening a character
# without its homebrew looks like.
CHAR_ADV_MORTAL = Character(id="advm", name="Villager", exalt_type="Mortal", caste="",
                            origin="ordinary", essence_rating=1)
CHAR_ADV_MORTAL.backgrounds = [BackgroundEntry(name="Resources", rating=2)]
CHAR_ADV_MORTAL.merits_flaws = [MeritFlawPurchase(merit_id="thaum.essence-awareness")]

@ui.page('/advantages-mortal')
def page_advantages_mortal():
    advantages.build_advantages(RS, CHAR_ADV_MORTAL, Path("x.json"), with_header=False)

CHAR_ADV_UNKNOWN = Character(id="advu", name="Stranger", exalt_type="Solar",
                             caste="dawn", essence_rating=1)
CHAR_ADV_UNKNOWN.merits_flaws = [MeritFlawPurchase(merit_id="homebrew.not-in-catalogue",
                                                   tier="7")]
CHAR_ADV_UNKNOWN.backgrounds = [BackgroundEntry(name="A Thing Nobody Authored", rating=2)]

@ui.page('/advantages-unknown')
def page_advantages_unknown():
    advantages.build_advantages(RS, CHAR_ADV_UNKNOWN, Path("x.json"), with_header=False)

CHAR_ADV_UNKNOWN_XP = CHAR_ADV_UNKNOWN.model_copy(deep=True)
CHAR_ADV_UNKNOWN_XP.id = "advux"
CHAR_ADV_UNKNOWN_XP.chargen_locked = True
CHAR_ADV_UNKNOWN_XP.xp_earned = 20

@ui.page('/advantages-unknown-xp')
def page_advantages_unknown_xp():
    advantages.build_advantages(RS, CHAR_ADV_UNKNOWN_XP, Path("x.json"), with_header=False)

@ui.page('/merits-sheet')
def page_merits_sheet():
    sheet_app.render_sheet(view.build_sheet_view(RS, CHAR_MERITS))


# The XP tab's Merits & Flaws card: a LOCKED character under the experience method,
# already carrying a debt, so the card renders its warning and both controls.
CHAR_MF_XP = Character(id="mfx", name="Indebted", exalt_type="Mortal", caste="",
                       origin="heroic", essence_rating=1)
CHAR_MF_XP.merits_flaws = [MeritFlawPurchase(merit_id="thaum.essence-awareness")]
CHAR_MF_XP.chargen_locked = True

@ui.page('/mf-xp')
def page_mf_xp():
    advantages.build_advantages(RS, CHAR_MF_XP, Path("x.json"), with_header=False)


# A Solar holding a two-sided entry (Eternal Vow, "3-PT. MERIT OR 1-PT. FLAW"). The
# editor's Merits panel must offer the side selector for it, and its Merit dropdown
# must not offer entries this character is barred from: Chimera is Lunars-only and
# Prodigy is barred to Solars, so neither may appear in the options.
CHAR_MF_SIDE = Character(id="mfs", name="Vowbound", exalt_type="Solar", caste="dawn",
                         essence_rating=1)
CHAR_MF_SIDE.merits_flaws = [MeritFlawPurchase(merit_id="mf.eternal-vow")]

@ui.page('/mf-side')
def page_mf_side():
    advantages.build_advantages(RS, CHAR_MF_SIDE, Path("x.json"), with_header=False)


# The same entry on the XP tab, locked and in funds, so the gain card renders its
# "choose a side" state rather than silently routing to the Merit branch.
CHAR_MF_SIDE_XP = Character(id="mfsx", name="Vowbound", exalt_type="Solar",
                            caste="dawn", essence_rating=1, xp_earned=50)
CHAR_MF_SIDE_XP.chargen_locked = True

@ui.page('/mf-side-xp')
def page_mf_side_xp():
    advantages.build_advantages(RS, CHAR_MF_SIDE_XP, Path("x.json"), with_header=False)


# A LOCKED character holding a player-authored "Custom" M&F row (2026-08-10). The
# play surface's "Held" dropdown must offer the custom row by name — a custom
# purchase has an empty `merit_id`, so the built options must come from `custom_name`
# or the select crashes on a value it does not offer.
CHAR_MF_CUSTOM_XP = Character(id="mfcx", name="House-Bound", exalt_type="Solar",
                              caste="dawn", essence_rating=1, xp_earned=50)
CHAR_MF_CUSTOM_XP.merits_flaws = [
    MeritFlawPurchase(merit_id="", custom_name="Bloodline trait")]
CHAR_MF_CUSTOM_XP.chargen_locked = True

@ui.page('/mf-custom-xp')
def page_mf_custom_xp():
    advantages.build_advantages(RS, CHAR_MF_CUSTOM_XP, Path("x.json"), with_header=False)


# 14 points of Flaws against the 10-point cap (p.17), so both surfaces have to say
# that four points are being swallowed rather than printing the capped 10 alone.
CHAR_MF_CAPPED = Character(id="mfc", name="Overburdened", exalt_type="Mortal", caste="",
                           origin="heroic", essence_rating=1)
CHAR_MF_CAPPED.merits_flaws = [
    MeritFlawPurchase(merit_id="thaum.dark-magics"),            # 3
    MeritFlawPurchase(merit_id="thaum.sheltered-upbringing"),   # 3
    MeritFlawPurchase(merit_id="thaum.oathbound-magic", tier="legendary", arena="x"),
]

@ui.page('/mf-capped')
def page_mf_capped():
    advantages.build_advantages(RS, CHAR_MF_CAPPED, Path("x.json"), with_header=False)


# The same overload on the XP tab, locked, where the cap truncates the XP AWARD.
CHAR_MF_CAPPED_XP = CHAR_MF_CAPPED.model_copy(deep=True)
CHAR_MF_CAPPED_XP.id = "mfcx"
CHAR_MF_CAPPED_XP.chargen_locked = True

@ui.page('/mf-capped-xp')
def page_mf_capped_xp():
    advantages.build_advantages(RS, CHAR_MF_CAPPED_XP, Path("x.json"), with_header=False)


# The XP tab's trait rows against Merit-RAISED ceilings. Reported by a player
# 2026-07-31: the rows hardcoded a cap of 5, so Legendary Attribute (Strength 6) and
# True Paragon (Virtues 6) both showed "max" with the Raise button disabled, while the
# engine would have allowed the buy. Both traits sit AT 5 here, which is precisely the
# rating the old constant refused and the new cap must permit.
CHAR_XP_CAPS = Character(id="xpc", name="Legendary", exalt_type="Solar", caste="dawn",
                         essence_rating=2, nature="Paragon")
CHAR_XP_CAPS.merits_flaws = [
    MeritFlawPurchase(merit_id="mf.legendary-attribute", detail="strength"),
    MeritFlawPurchase(merit_id="mf.true-paragon"),
]
CHAR_XP_CAPS.attributes[AttributeName.STRENGTH] = 5
CHAR_XP_CAPS.virtues[VirtueName.VALOR] = 5
lifecycle.lock_chargen(CHAR_XP_CAPS, RS)
CHAR_XP_CAPS.xp_earned = 200

@ui.page('/xp-caps')
def page_xp_caps():
    editor.build_editor(RS, CHAR_XP_CAPS, Path("x.json"), with_header=False)


# Decision 0013 / P1: the editor rendered POST-LOCK, where its dot tracks are steppers
# that spend XP rather than free setters. The Edit tab does not reach this state on the
# tab bar until P2, so this route is what keeps the new code path from being written and
# never built — the failure mode docs/status/edit-xp-merge.md calls out.
CHAR_EDIT_XP = Character(id="exp", name="Locked Editor", caste="dawn")
CHAR_EDIT_XP.abilities[AbilityName.MELEE] = 3
lifecycle.lock_chargen(CHAR_EDIT_XP, RS)
CHAR_EDIT_XP.xp_earned = 100

@ui.page('/editor-locked')
def page_editor_locked():
    editor.build_editor(RS, CHAR_EDIT_XP, Path("x.json"), with_header=False)

# The downward-click dialog itself, built for each of the three states it can be in.
# A render test cannot reach it — it exists only in response to a click on a pip — and
# an unbuilt NiceGUI branch is exactly the bug class that keeps surviving this suite.
CHAR_DIALOG = Character(id="dlg", name="Cursed", caste="dawn")
CHAR_DIALOG.attributes[AttributeName.STRENGTH] = 3
lifecycle.lock_chargen(CHAR_DIALOG, RS)
CHAR_DIALOG.xp_earned = 100

@ui.page('/editor-lower-both')       # bought a dot: refund AND reduce both offered
def page_editor_lower_both():
    from exalted_builder.engine import advancement as adv
    if adv.refundable_depth(CHAR_DIALOG, "attributes.strength") == 0:
        adv.raise_to(RS, CHAR_DIALOG, "attributes.strength", 4)
    open_dialog = editor.build_editor(RS, CHAR_DIALOG, Path("x.json"), with_header=False)
    open_dialog("attributes.strength", 4, 3, lambda: None)

# A chargen dot with nothing bought on top: refund is impossible, a curse is not.
CHAR_DIALOG_CURSE = Character(id="dlg2", name="Only Cursable", caste="dawn")
CHAR_DIALOG_CURSE.attributes[AttributeName.STRENGTH] = 3
lifecycle.lock_chargen(CHAR_DIALOG_CURSE, RS)

@ui.page('/editor-lower-curse-only')
def page_editor_lower_curse_only():
    open_dialog = editor.build_editor(RS, CHAR_DIALOG_CURSE, Path("x.json"),
                                      with_header=False)
    open_dialog("attributes.strength", 3, 2, lambda: None)


# P3: the in-play sticky column — Adjust XP, then a read-only log, then validation
# ONLY when it has something to say. Two characters, because the demotion is a
# behaviour, not a layout: one clean, one whose curse broke a Charm it still knows.
CHAR_COL_CLEAN = Character(id="col1", name="Clean Veteran", caste="dawn")
CHAR_COL_CLEAN.abilities[AbilityName.MELEE] = 3
lifecycle.lock_chargen(CHAR_COL_CLEAN, RS)
CHAR_COL_CLEAN.xp_earned = 40

@ui.page('/column-clean')
def page_column_clean():
    editor.build_editor(RS, CHAR_COL_CLEAN, Path("x.json"), with_header=False)

CHAR_COL_BROKEN = Character(id="col2", name="Cursed Veteran", caste="dawn")
CHAR_COL_BROKEN.abilities[AbilityName.MELEE] = 3
CHAR_COL_BROKEN.charms = ["solar.melee.excellent-strike",
                          "solar.melee.hungry-tiger-technique"]
lifecycle.lock_chargen(CHAR_COL_BROKEN, RS)
CHAR_COL_BROKEN.xp_earned = 40

@ui.page('/column-broken')
def page_column_broken():
    from exalted_builder.engine import advancement as adv
    if CHAR_COL_BROKEN.abilities[AbilityName.MELEE] > 1:
        adv.lower_to(CHAR_COL_BROKEN, "abilities.melee", 1, "a curse")
    editor.build_editor(RS, CHAR_COL_BROKEN, Path("x.json"), with_header=False)

# The Undo control. A read-only log has no per-row undo button, so this is the ONLY
# way to reverse a Charm/Combo/spell/specialty purchase — traits have their dot-track
# dialog, those do not. It must name the row it will reverse.
CHAR_COL_UNDO = Character(id="col3", name="Buyer", caste="dawn")
CHAR_COL_UNDO.abilities[AbilityName.MELEE] = 3
lifecycle.lock_chargen(CHAR_COL_UNDO, RS)
CHAR_COL_UNDO.xp_earned = 100

@ui.page('/column-undo')
def page_column_undo():
    from exalted_builder.engine import advancement as adv
    if not CHAR_COL_UNDO.charms:
        adv.learn_charm(RS, CHAR_COL_UNDO, "solar.melee.excellent-strike")
    editor.build_editor(RS, CHAR_COL_UNDO, Path("x.json"), with_header=False)


# Chargen choices frozen at the lock. An Illuminated Solar, so the Training Camp and
# Calling selects exist too — they are chargen picks with mechanical consequences
# (free Charms, discounted Calling Abilities) and were exposed the moment Edit became
# a both-sides tab.
CHAR_FROZEN = Character(id="frz", name="Fixed", caste="dawn", origin="illuminated")
CHAR_FROZEN.favored_abilities = [AbilityName.OCCULT, AbilityName.DODGE,
                                 AbilityName.ATHLETICS, AbilityName.RESISTANCE,
                                 AbilityName.ENDURANCE]
CHAR_FROZEN.camp = "sequestered-tabernacle"     # a camp is what makes Callings exist
lifecycle.lock_chargen(CHAR_FROZEN, RS)
CHAR_FROZEN.xp_earned = 40

@ui.page('/identity-frozen')
def page_identity_frozen():
    editor.build_editor(RS, CHAR_FROZEN, Path("x.json"), with_header=False)

CHAR_UNFROZEN = Character(id="ufz", name="Still Building", caste="dawn",
                          origin="illuminated")
CHAR_UNFROZEN.camp = "sequestered-tabernacle"

@ui.page('/identity-open')
def page_identity_open():
    editor.build_editor(RS, CHAR_UNFROZEN, Path("x.json"), with_header=False)


# P3 rehoming: an Abyssal with Death's Taint (permanent Resonance track) and Weak
# Essence (withheld Charm credits), locked. Both cards lived only on the XP tab.
CHAR_REHOMED = Character(id="rhm", name="Rehomed", exalt_type="Abyssal", caste="dusk",
                         origin="loyal", essence_rating=3)
CHAR_REHOMED.merits_flaws = [MeritFlawPurchase(merit_id="mf.death-taint", tier="5"),
                             MeritFlawPurchase(merit_id="mf.weak-essence")]
lifecycle.lock_chargen(CHAR_REHOMED, RS)
CHAR_REHOMED.xp_earned = 60

@ui.page('/rehomed')
def page_rehomed():
    editor.build_editor(RS, CHAR_REHOMED, Path("x.json"), with_header=False)


# P5 render matrix for the merged trait surface: the two splat shapes that have
# broken editors before. A Mortal has NO castes and NO Charms (so the caste select is
# absent and Essence is pinned at 1); an Alchemical allocates FAVORED ATTRIBUTES
# instead of favored Abilities, a different control on the same panel.
CHAR_MORTAL_LOCKED = Character(id="mlk", name="Locked Mortal", exalt_type="Mortal",
                               caste="", origin="heroic", essence_rating=1)
lifecycle.lock_chargen(CHAR_MORTAL_LOCKED, RS)
CHAR_MORTAL_LOCKED.xp_earned = 30

@ui.page('/editor-locked-mortal')
def page_editor_locked_mortal():
    editor.build_editor(RS, CHAR_MORTAL_LOCKED, Path("x.json"), with_header=False)

CHAR_ALCH_LOCKED = Character(id="alk", name="Locked Alchemical",
                             exalt_type="Alchemical", caste="orichalcum")
lifecycle.lock_chargen(CHAR_ALCH_LOCKED, RS)
CHAR_ALCH_LOCKED.xp_earned = 30

@ui.page('/editor-locked-alchemical')
def page_editor_locked_alchemical():
    editor.build_editor(RS, CHAR_ALCH_LOCKED, Path("x.json"), with_header=False)


# P4: the sheet's read-only copy of the ledger. Built from the SheetView alone, so
# the same route proves both that it renders and that `render_sheet` still needs
# nothing but the dataclass.
CHAR_SHEET_LEDGER = Character(id="shl", name="Spent Solar", caste="dawn")
CHAR_SHEET_LEDGER.abilities[AbilityName.MELEE] = 3
lifecycle.lock_chargen(CHAR_SHEET_LEDGER, RS)
CHAR_SHEET_LEDGER.xp_earned = 100

@ui.page('/sheet-ledger')
def page_sheet_ledger():
    from exalted_builder.engine import advancement as adv
    if not CHAR_SHEET_LEDGER.xp_log:
        adv.raise_to(RS, CHAR_SHEET_LEDGER, "attributes.strength", 3)
        adv.learn_charm(RS, CHAR_SHEET_LEDGER, "solar.melee.excellent-strike")
    sheet_app.render_sheet(view.build_sheet_view(RS, CHAR_SHEET_LEDGER))


# P5 matrix, continued: a LUNAR (castes carry no caste-abilities, so the Ability panel
# groups differently) and a locked character carrying OFF-CATALOGUE gear and a custom
# Nature — the `ui.select` value-not-in-options trap, which the freeze now also touches
# because a frozen select still has to build with whatever the save holds.
CHAR_LUNAR_LOCKED = Character(id="lnk", name="Locked Lunar", exalt_type="Lunar",
                              caste="full-moon", origin="society")
lifecycle.lock_chargen(CHAR_LUNAR_LOCKED, RS)
CHAR_LUNAR_LOCKED.xp_earned = 30

@ui.page('/editor-locked-lunar')
def page_editor_locked_lunar():
    editor.build_editor(RS, CHAR_LUNAR_LOCKED, Path("x.json"), with_header=False)

CHAR_ODD_LOCKED = Character(id="odd", name="Odd Kit", caste="dawn",
                            nature="Not In The Catalog")
CHAR_ODD_LOCKED.weapons.append(Weapon(name="Grandpa's Axe", accuracy=2, damage=6))
CHAR_ODD_LOCKED.armor.append(Armor(name="Scrap Plate", soak_lethal=3))
lifecycle.lock_chargen(CHAR_ODD_LOCKED, RS)
CHAR_ODD_LOCKED.xp_earned = 30

@ui.page('/editor-locked-odd')
def page_editor_locked_odd():
    editor.build_editor(RS, CHAR_ODD_LOCKED, Path("x.json"), with_header=False)

@ui.page('/editor-locked-odd-gear')
def page_editor_locked_odd_gear():
    gear.build_gear(RS, CHAR_ODD_LOCKED, Path("x.json"), with_header=False)


# Essence and trait ceilings (Player's Guide pp.258-259): the first characters in the
# build whose Essence, Abilities and Attributes legally sit above 5. Three shapes,
# because the dot tracks are BUILT from the ceilings and a too-high value has to render
# as well as a too-high ceiling: a Celestial past 5 on every track, a Terrestrial held
# at the tier's 7, and the sheet's read-only view of the same character.
CHAR_ELDER = Character(id="eld", name="Elder Solar", caste="dawn")
lifecycle.lock_chargen(CHAR_ELDER, RS)
CHAR_ELDER.xp_earned = 500
CHAR_ELDER.essence_rating = 8
CHAR_ELDER.abilities[AbilityName.MELEE] = 7

@ui.page('/editor-elder')
def page_editor_elder():
    editor.build_editor(RS, CHAR_ELDER, Path("x.json"), with_header=False)

@ui.page('/sheet-elder')
def page_sheet_elder():
    sheet_app.render_sheet(view.build_sheet_view(RS, CHAR_ELDER))

CHAR_ELDER_DB = Character(id="elddb", name="Elder Dragon", exalt_type="Dragon-Blooded",
                          caste="fire", origin="dynastic")
lifecycle.lock_chargen(CHAR_ELDER_DB, RS)
CHAR_ELDER_DB.xp_earned = 500
CHAR_ELDER_DB.essence_rating = 7

@ui.page('/editor-elder-terrestrial')
def page_editor_elder_terrestrial():
    editor.build_editor(RS, CHAR_ELDER_DB, Path("x.json"), with_header=False)


# The p.259 downtime calculator, on its OWN character: the Grant button mutates the
# calculator's local age and the character's xp_earned, and a route that shares
# CHAR_ELDER would leak that into every other elder test. The start-age is typed in
# by the test (it is a calculator input, not a trait).
CHAR_DOWNTIME = Character(id="dwn", name="Sleeper", caste="dawn")
lifecycle.lock_chargen(CHAR_DOWNTIME, RS)

@ui.page('/editor-downtime')
def page_editor_downtime():
    editor.build_editor(RS, CHAR_DOWNTIME, Path("x.json"), with_header=False)

# The read-only half of the same panel, on its own character and route: a route builds
# once per session, so the test that GRANTS must not share one with the test that only
# looks. The start-age is typed in by the test.
CHAR_DOWNTIME_VIEW = Character(id="dwnv", name="Dreamer", caste="dawn")
lifecycle.lock_chargen(CHAR_DOWNTIME_VIEW, RS)

@ui.page('/editor-downtime-view')
def page_editor_downtime_view():
    editor.build_editor(RS, CHAR_DOWNTIME_VIEW, Path("x.json"), with_header=False)


# --- Ghosts (E:Ab) ---------------------------------------------------------- #
# The render matrix for the seventh splat, one route per SHAPE rather than per known
# bug. The shapes that have blanked panels before and all apply here: a CASTELESS
# splat (every caste-grouped UI), a splat barred from other people's Charms (the
# picker's category dropdown), and two brand-new rated traits with their own panels.
def _ghost(cid: str, name: str, *, origin: str = "heroic", upbringing: str = "") -> Character:
    c = Character(id=cid, name=name, exalt_type="Ghost", caste="",
                  origin=origin, upbringing=upbringing, essence_rating=2)
    c.virtues = {VirtueName.COMPASSION: 3, VirtueName.CONVICTION: 2,
                 VirtueName.TEMPERANCE: 1, VirtueName.VALOR: 1}
    c.fetters = [FetterEntry(name="my widowed wife", rating=3),
                 FetterEntry(name="the sword I died on", rating=2)]
    c.passions = [PassionEntry(name="avenge my murder",
                               virtue=VirtueName.COMPASSION, rating=3),
                  PassionEntry(name="finish the work",
                               virtue=VirtueName.CONVICTION, rating=2)]
    return c

CHAR_GHOST = _ghost("gh", "Sighing Reed")

@ui.page('/ghost-advantages')
def page_ghost_advantages():
    advantages.build_advantages(RS, CHAR_GHOST, Path("x.json"), with_header=False)

@ui.page('/ghost-editor')
def page_ghost_editor():
    editor.build_editor(RS, CHAR_GHOST, Path("x.json"), with_header=False)

@ui.page('/ghost-picker')
def page_ghost_picker():
    picker.build_picker(RS, CHAR_GHOST, Path("x.json"), with_header=False)

@ui.page('/ghost-sheet')
def page_ghost_sheet():
    sheet_app.render_sheet(view.build_sheet_view(RS, CHAR_GHOST))

# The Immaculate-region upbringing: 5 Background dots and the Ancestor Cult ceiling.
CHAR_GHOST_IMM = _ghost("ghi", "Ash On The Wind", upbringing="immaculate")
CHAR_GHOST_IMM.backgrounds = [BackgroundEntry(name="Ancestor Cult", rating=3)]

@ui.page('/ghost-advantages-immaculate')
def page_ghost_advantages_immaculate():
    advantages.build_advantages(RS, CHAR_GHOST_IMM, Path("x.json"), with_header=False)

# The mundane dead — the other origin, and the smaller budgets.
CHAR_GHOST_MUNDANE = _ghost("ghm", "Nobody", origin="mundane")

@ui.page('/ghost-editor-mundane')
def page_ghost_editor_mundane():
    editor.build_editor(RS, CHAR_GHOST_MUNDANE, Path("x.json"), with_header=False)

# LOCKED: the post-lock half of both panels — the Fetter buy controls and the Shift
# Passion control, neither of which exists pre-lock.
CHAR_GHOST_XP = _ghost("ghx", "Long Dead")
lifecycle.lock_chargen(CHAR_GHOST_XP, RS)
CHAR_GHOST_XP.xp_earned = 100

@ui.page('/ghost-advantages-xp')
def page_ghost_advantages_xp():
    advantages.build_advantages(RS, CHAR_GHOST_XP, Path("x.json"), with_header=False)

@ui.page('/ghost-sheet-xp')
def page_ghost_sheet_xp():
    sheet_app.render_sheet(view.build_sheet_view(RS, CHAR_GHOST_XP))

# A locked ghost with NO Fetters and NO Passions: the empty-options shape. `ui.select`
# raises at BUILD time when its value is not among its options, and an empty option
# list is the easiest way there — adding-a-splat.md trap #3, which has blanked whole
# tabs twice. Both post-lock controls build their dropdowns from the character's own
# lists, so this is the route that proves an empty one is survivable.
CHAR_GHOST_EMPTY = Character(id="ghe", name="Forgotten", exalt_type="Ghost", caste="",
                             origin="heroic", essence_rating=2)
CHAR_GHOST_EMPTY.virtues = {VirtueName.COMPASSION: 1, VirtueName.CONVICTION: 1,
                            VirtueName.TEMPERANCE: 1, VirtueName.VALOR: 1}
lifecycle.lock_chargen(CHAR_GHOST_EMPTY, RS)

@ui.page('/ghost-advantages-empty')
def page_ghost_advantages_empty():
    advantages.build_advantages(RS, CHAR_GHOST_EMPTY, Path("x.json"), with_header=False)

@ui.page('/ghost-sheet-empty')
def page_ghost_sheet_empty():
    sheet_app.render_sheet(view.build_sheet_view(RS, CHAR_GHOST_EMPTY))

# The whole builder for a ghost — the tab bar is only assembled here, so neither the
# missing Arcanoi canvas nor the stray Combos tab was reachable from the per-tab
# routes above. Both were found in the browser (2026-08-01) with 1,684 tests passing.
CHAR_GHOST_APP = _ghost("gha", "Tab Test")

@ui.page('/ghost-app')
def page_ghost_app():
    builder.build_app(RS, CHAR_GHOST_APP, Path("gha.json"))

# --------------------------------------------------------------------------- #
# Rated artifacts (E:Ab p.131) — a loyal Abyssal with all three kinds of artifact
# and a Damaged Artifact Flaw pointed at the armour. The panel and the picker are
# the read sites that stop `Character.artifacts` and `MeritFlawPurchase.artifact_key`
# becoming dead fields; see tests/test_rated_artifacts.py.
# --------------------------------------------------------------------------- #
CHAR_ARTIFACTS = Character(id="art", name="Clutching Owl", exalt_type="Abyssal",
                           caste="Dusk", essence_rating=2)
CHAR_ARTIFACTS.backgrounds.append(BackgroundEntry(name="Artifact", rating=3))
CHAR_ARTIFACTS.artifacts.append(ArtifactEntry(name="Tattered Wings", rating=2,
                                              note="of the raptor"))
CHAR_ARTIFACTS.weapons.append(Weapon(name="Soulsteel Daiklave", accuracy=2, damage=5,
                                     artifact_rating=3))
CHAR_ARTIFACTS.armor.append(Armor(name="Grave Plate", soak_lethal=8, soak_bashing=10,
                                  artifact_rating=2))
CHAR_ARTIFACTS.merits_flaws.append(
    MeritFlawPurchase(merit_id="mf.damaged-artifact", tier="1",
                      artifact_key="armor:grave plate"))

@ui.page('/artifacts-advantages')
def page_artifacts_advantages():
    gear.build_gear(RS, CHAR_ARTIFACTS, Path("x.json"), with_header=False)

# The same character's ADVANTAGES tab. Damaged Artifact is a Merit, so its per-item
# picker stayed with M&F when the artifacts themselves moved to Gear — one character,
# two tabs, and the tests that read each need their own route.
@ui.page('/artifacts-merits')
def page_artifacts_merits():
    advantages.build_advantages(RS, CHAR_ARTIFACTS, Path("x.json"), with_header=False)

@ui.page('/artifacts-sheet')
def page_artifacts_sheet():
    sheet_app.render_sheet(view.build_sheet_view(RS, CHAR_ARTIFACTS))

# The same character past the lock: artifacts are equipment, so the panel is on the
# bar both sides and must not vanish or turn read-only.
CHAR_ARTIFACTS_XP = CHAR_ARTIFACTS.model_copy(deep=True)
CHAR_ARTIFACTS_XP.id = "artxp"
lifecycle.lock_chargen(CHAR_ARTIFACTS_XP, RS)
CHAR_ARTIFACTS_XP.xp_earned = 20

@ui.page('/artifacts-advantages-xp')
def page_artifacts_advantages_xp():
    gear.build_gear(RS, CHAR_ARTIFACTS_XP, Path("x.json"), with_header=False)

# A splat with no budget table: the panel still edits artifacts, but prints no budget.
CHAR_ARTIFACTS_SOLAR = Character(id="arts", name="Velgash", caste="dawn")
CHAR_ARTIFACTS_SOLAR.backgrounds.append(BackgroundEntry(name="Artifact", rating=4))
CHAR_ARTIFACTS_SOLAR.artifacts.append(ArtifactEntry(name="Tattered Wings", rating=4))

@ui.page('/artifacts-advantages-solar')
def page_artifacts_advantages_solar():
    gear.build_gear(RS, CHAR_ARTIFACTS_SOLAR, Path("x.json"), with_header=False)

# The same Solar past the lock, where the Background rating control is a NUMBER input
# (the unlocked regime draws dots, which a test can only click one pip at a time). The
# corebook Artifacts header reads the Artifact BACKGROUND, which is edited in a
# different panel — its own route because the test MUTATES this character's rating.
CHAR_ARTIFACT_HEADER = CHAR_ARTIFACTS_SOLAR.model_copy(deep=True)
CHAR_ARTIFACT_HEADER.id = "arth"
lifecycle.lock_chargen(CHAR_ARTIFACT_HEADER, RS)

@ui.page('/artifact-header-sync')
def page_artifact_header_sync():
    gear.build_gear(RS, CHAR_ARTIFACT_HEADER, Path("x.json"), with_header=False)

# …and its ADVANTAGES side, where the Artifact Background row states what its dots buy.
@ui.page('/artifact-background-note')
def page_artifact_background_note():
    advantages.build_advantages(RS, CHAR_ARTIFACT_HEADER, Path("x.json"),
                                with_header=False)

# Picking an artifact that is ALSO a weapon must grant the stat line, linked, so the
# budget counts one daiklave rather than two. Its own character: the test picks from the
# catalogue and mutates it.
CHAR_ARTIFACT_GRANT = Character(id="artg", name="Swordbearer", exalt_type="Solar",
                                caste="dawn")
CHAR_ARTIFACT_GRANT.backgrounds.append(BackgroundEntry(name="Artifact", rating=3))

@ui.page('/artifact-grant')
def page_artifact_grant():
    gear.build_gear(RS, CHAR_ARTIFACT_GRANT, Path("x.json"), with_header=False)

# The equipment surface for the SAME character, so a test can pick an artifact on one
# page and see the granted stat line on the other without reaching into module state.
@ui.page('/artifact-grant-editor')
def page_artifact_grant_editor():
    gear.build_gear(RS, CHAR_ARTIFACT_GRANT, Path("x.json"), with_header=False)

# A LOCKED character who bought an artifact with cash (Manacle and Coin pp.122-125) —
# the acquisition control exists only post-lock, and the budget must not charge for it.
CHAR_ARTIFACT_BOUGHT = Character(id="artb", name="Merchant", exalt_type="Solar",
                                 caste="dawn")
CHAR_ARTIFACT_BOUGHT.backgrounds.append(BackgroundEntry(name="Artifact", rating=2))
CHAR_ARTIFACT_BOUGHT.backgrounds.append(BackgroundEntry(name="Resources", rating=4))
CHAR_ARTIFACT_BOUGHT.artifacts.append(ArtifactEntry(name="Tattered Wings", rating=2))
lifecycle.lock_chargen(CHAR_ARTIFACT_BOUGHT, RS)

@ui.page('/artifact-bought')
def page_artifact_bought():
    gear.build_gear(RS, CHAR_ARTIFACT_BOUGHT, Path("x.json"), with_header=False)

# The same shape UNLOCKED, where the control must not exist at all.
CHAR_ARTIFACT_UNLOCKED = Character(id="artu", name="Fresh", exalt_type="Solar",
                                   caste="dawn")
CHAR_ARTIFACT_UNLOCKED.backgrounds.append(BackgroundEntry(name="Artifact", rating=2))
CHAR_ARTIFACT_UNLOCKED.artifacts.append(ArtifactEntry(name="Tattered Wings", rating=2))

@ui.page('/artifact-unlocked')
def page_artifact_unlocked():
    gear.build_gear(RS, CHAR_ARTIFACT_UNLOCKED, Path("x.json"), with_header=False)

# Damaged Artifact held by a character owning NO artifacts — the empty-options case
# for the artifact picker, which is the NiceGUI build-time crash class (a ui.select
# whose value is not among its options takes the whole tab down, siblings included).
CHAR_ARTIFACTS_NONE = Character(id="artn", name="Owns Nothing", exalt_type="Abyssal",
                                caste="Dusk", essence_rating=2)
CHAR_ARTIFACTS_NONE.merits_flaws.append(
    MeritFlawPurchase(merit_id="mf.damaged-artifact", tier="1"))

@ui.page('/artifacts-advantages-none')
def page_artifacts_advantages_none():
    advantages.build_advantages(RS, CHAR_ARTIFACTS_NONE, Path("x.json"),
                                with_header=False)

# ...and one whose stored key resolves to nothing, because the artifact was renamed.
CHAR_ARTIFACTS_STALE = Character(id="arts2", name="Renamed", exalt_type="Abyssal",
                                 caste="Dusk", essence_rating=2)
CHAR_ARTIFACTS_STALE.backgrounds.append(BackgroundEntry(name="Artifact", rating=3))
CHAR_ARTIFACTS_STALE.artifacts.append(ArtifactEntry(name="New Name", rating=3))
CHAR_ARTIFACTS_STALE.merits_flaws.append(
    MeritFlawPurchase(merit_id="mf.damaged-artifact", tier="1",
                      artifact_key="artifact:old name"))

@ui.page('/artifacts-advantages-stale')
def page_artifacts_advantages_stale():
    advantages.build_advantages(RS, CHAR_ARTIFACTS_STALE, Path("x.json"),
                                with_header=False)


# --- God-Blooded (Phase A: core + the Ghost-Blooded heritage) ---------------- #

def _godblooded(cid: str, name: str) -> Character:
    c = Character(id=cid, name=name, exalt_type="God-Blooded",
                  caste="ghost-blooded", essence_rating=2)
    c.virtues = {VirtueName.COMPASSION: 2, VirtueName.CONVICTION: 3,
                 VirtueName.TEMPERANCE: 2, VirtueName.VALOR: 2}
    c.merits_flaws = [MeritFlawPurchase(merit_id="mf.awakened-essence")]
    c.backgrounds = [BackgroundEntry(name="Inheritance", rating=3),
                     BackgroundEntry(name="Patron", rating=2)]
    c.favored_abilities = [AbilityName.MELEE]
    c.charms = ["ghost.savage-ghost-tamer.taste-the-demon-wind"]
    return c

CHAR_GODBLOODED = _godblooded("gdb", "Sighing Willow")

@ui.page('/godblooded-advantages')
def page_godblooded_advantages():
    advantages.build_advantages(RS, CHAR_GODBLOODED, Path("x.json"), with_header=False)

@ui.page('/godblooded-editor')
def page_godblooded_editor():
    editor.build_editor(RS, CHAR_GODBLOODED, Path("x.json"), with_header=False)

@ui.page('/godblooded-picker')
def page_godblooded_picker():
    picker.build_picker(RS, CHAR_GODBLOODED, Path("x.json"), with_header=False)

@ui.page('/godblooded-sheet')
def page_godblooded_sheet():
    sheet_app.render_sheet(view.build_sheet_view(RS, CHAR_GODBLOODED))


def _half_caste(cid: str, name: str, parent: str) -> Character:
    c = Character(id=cid, name=name, exalt_type="God-Blooded",
                  caste="half-caste", origin=parent, essence_rating=2)
    c.virtues = {VirtueName.COMPASSION: 2, VirtueName.CONVICTION: 3,
                 VirtueName.TEMPERANCE: 2, VirtueName.VALOR: 2}
    c.merits_flaws = [MeritFlawPurchase(merit_id="mf.awakened-essence")]
    c.charms = ["solar.melee.fire-and-stones-strike"]
    return c

CHAR_HALF_CASTE = _half_caste("hc", "Golden Child", "Solar")

@ui.page('/godblooded-halfcaste-advantages')
def page_godblooded_halfcaste_advantages():
    advantages.build_advantages(RS, CHAR_HALF_CASTE, Path("x.json"), with_header=False)

@ui.page('/godblooded-halfcaste-editor')
def page_godblooded_halfcaste_editor():
    editor.build_editor(RS, CHAR_HALF_CASTE, Path("x.json"), with_header=False)

@ui.page('/godblooded-halfcaste-picker')
def page_godblooded_halfcaste_picker():
    picker.build_picker(RS, CHAR_HALF_CASTE, Path("x.json"), with_header=False)

@ui.page('/godblooded-halfcaste-sheet')
def page_godblooded_halfcaste_sheet():
    sheet_app.render_sheet(view.build_sheet_view(RS, CHAR_HALF_CASTE))


def _fae(cid: str, name: str, origin: str) -> Character:
    c = Character(id=cid, name=name, exalt_type="God-Blooded",
                  caste="fae-blooded", origin=origin, essence_rating=2)
    c.virtues = {VirtueName.COMPASSION: 2, VirtueName.CONVICTION: 3,
                 VirtueName.TEMPERANCE: 2, VirtueName.VALOR: 2}
    c.merits_flaws = [MeritFlawPurchase(merit_id="mf.awakened-essence"),
                      MeritFlawPurchase(merit_id="mf.fae-virtue-attunement",
                                        detail="compassion"),
                      MeritFlawPurchase(merit_id="mf.fae-wyld-sense")]
    return c

CHAR_FAE_NOBLE = _fae("fae-n", "Sidhe-Spun", "Noble")
CHAR_FAE_COMMONER = _fae("fae-c", "Changling", "Commoner")
# A Commoner holding TWO Virtue Attunements is illegal (p.74: once only) — the
# advantages tab must render the refusal without crashing.
CHAR_FAE_COMMONER_2X = _fae("fae-c2", "Illegally Attuned", "Commoner")
CHAR_FAE_COMMONER_2X.merits_flaws.append(
    MeritFlawPurchase(merit_id="mf.fae-virtue-attunement", detail="valor"))

@ui.page('/godblooded-fae-advantages')
def page_godblooded_fae_advantages():
    advantages.build_advantages(RS, CHAR_FAE_NOBLE, Path("x.json"), with_header=False)

@ui.page('/godblooded-fae-editor')
def page_godblooded_fae_editor():
    editor.build_editor(RS, CHAR_FAE_NOBLE, Path("x.json"), with_header=False)

@ui.page('/godblooded-fae-picker')
def page_godblooded_fae_picker():
    picker.build_picker(RS, CHAR_FAE_NOBLE, Path("x.json"), with_header=False)

@ui.page('/godblooded-fae-sheet')
def page_godblooded_fae_sheet():
    sheet_app.render_sheet(view.build_sheet_view(RS, CHAR_FAE_NOBLE))

@ui.page('/godblooded-fae-commoner-2x-advantages')
def page_godblooded_fae_commoner_2x_advantages():
    advantages.build_advantages(RS, CHAR_FAE_COMMONER_2X, Path("x.json"), with_header=False)

# Review repro (Fix 1): a Fae-Blooded SAVED with a stale origin — the Half-Caste's
# "Solar" parent, and a blank — must render the editor, not raise ValueError on the
# Origin select (whose options are Noble/Commoner). The stale value is reported by
# validation (heritage-foreign-origin) instead.
CHAR_FAE_STALE_ORIGIN = _fae("fae-stale", "Mis-Saved Changeling", "Solar")
CHAR_FAE_NO_ORIGIN = _fae("fae-none", "Originless Changeling", "")

@ui.page('/godblooded-fae-stale-origin-editor')
def page_godblooded_fae_stale_origin_editor():
    editor.build_editor(RS, CHAR_FAE_STALE_ORIGIN, Path("x.json"), with_header=False)

@ui.page('/godblooded-fae-no-origin-editor')
def page_godblooded_fae_no_origin_editor():
    editor.build_editor(RS, CHAR_FAE_NO_ORIGIN, Path("x.json"), with_header=False)


def _god_blooded(cid: str, name: str, origin: str) -> Character:
    c = Character(id=cid, name=name, exalt_type="God-Blooded",
                  caste="god-blooded", origin=origin, essence_rating=2)
    c.virtues = {VirtueName.COMPASSION: 2, VirtueName.CONVICTION: 3,
                 VirtueName.TEMPERANCE: 2, VirtueName.VALOR: 2}
    # Awakened Essence (shared pool) + a Divine-origin Merit (p.45) whose "Patron at
    # least 3" prerequisite is satisfied by the background below.
    c.merits_flaws = [MeritFlawPurchase(merit_id="mf.awakened-essence"),
                      MeritFlawPurchase(merit_id="mf.divine-apprentice")]
    c.backgrounds = [BackgroundEntry(name="Patron", rating=3)]
    # A held spirit Charm (Min Compassion 1 / Essence 1, no prereqs — learnable at
    # these stats). The sheet must render it under "Charms", never "Arcanoi".
    c.charms = ["spirit.spirit-templates.measure-the-wind"]
    return c


def _demon_blooded(cid: str, name: str) -> Character:
    c = Character(id=cid, name=name, exalt_type="God-Blooded",
                  caste="demon-blooded", essence_rating=2)
    c.virtues = {VirtueName.COMPASSION: 2, VirtueName.CONVICTION: 3,
                 VirtueName.TEMPERANCE: 2, VirtueName.VALOR: 2}
    # A Demon-Blooded Merit with no origin axis (p.52) + the shared pool.
    c.merits_flaws = [MeritFlawPurchase(merit_id="mf.awakened-essence"),
                      MeritFlawPurchase(merit_id="mf.gatekeeper")]
    # Same held spirit Charm — learnable by a Demon-Blooded too ("follow the same
    # rules regarding Charm selection as God-Blooded", p.48).
    c.charms = ["spirit.spirit-templates.measure-the-wind"]
    return c

CHAR_GOD_BLOODED = _god_blooded("gb", "Warden of the Gilded Gate", "Divine")
CHAR_DEMON_BLOODED = _demon_blooded("dbd", "Silver-Tongued Apostate")

@ui.page('/godblooded-god-advantages')
def page_godblooded_god_advantages():
    advantages.build_advantages(RS, CHAR_GOD_BLOODED, Path("x.json"), with_header=False)

@ui.page('/godblooded-god-editor')
def page_godblooded_god_editor():
    editor.build_editor(RS, CHAR_GOD_BLOODED, Path("x.json"), with_header=False)

@ui.page('/godblooded-god-picker')
def page_godblooded_god_picker():
    picker.build_picker(RS, CHAR_GOD_BLOODED, Path("x.json"), with_header=False)

@ui.page('/godblooded-god-sheet')
def page_godblooded_god_sheet():
    sheet_app.render_sheet(view.build_sheet_view(RS, CHAR_GOD_BLOODED))

@ui.page('/godblooded-demon-advantages')
def page_godblooded_demon_advantages():
    advantages.build_advantages(RS, CHAR_DEMON_BLOODED, Path("x.json"), with_header=False)

@ui.page('/godblooded-demon-editor')
def page_godblooded_demon_editor():
    editor.build_editor(RS, CHAR_DEMON_BLOODED, Path("x.json"), with_header=False)

@ui.page('/godblooded-demon-picker')
def page_godblooded_demon_picker():
    picker.build_picker(RS, CHAR_DEMON_BLOODED, Path("x.json"), with_header=False)

@ui.page('/godblooded-demon-sheet')
def page_godblooded_demon_sheet():
    sheet_app.render_sheet(view.build_sheet_view(RS, CHAR_DEMON_BLOODED))


def _elemental_godblooded(cid: str, name: str) -> Character:
    """An Elemental-origin God-Blooded — the only origin with the Elemental Powers
    page (PG p.68). Holds Elemental Dominion + Primal Restoration so every power is
    buyable, and a couple of owned powers for the picker to render."""
    c = Character(id=cid, name=name, exalt_type="God-Blooded",
                  caste="god-blooded", origin="Elemental", essence_rating=2)
    c.virtues = {VirtueName.COMPASSION: 2, VirtueName.CONVICTION: 3,
                 VirtueName.TEMPERANCE: 2, VirtueName.VALOR: 2}
    c.merits_flaws = [MeritFlawPurchase(merit_id="mf.awakened-essence"),
                      MeritFlawPurchase(merit_id="mf.elemental-dominion"),
                      MeritFlawPurchase(merit_id="mf.primal-restoration")]
    c.charms = ["spirit.spirit-templates.measure-the-wind"]
    c.elemental_powers = ["elemental.aegis"]
    return c

CHAR_ELEMENTAL_GODBLOODED = _elemental_godblooded("egb", "Aegis of the East Wind")

@ui.page('/godblooded-elemental-picker')
def page_godblooded_elemental_picker():
    picker.build_picker(RS, CHAR_ELEMENTAL_GODBLOODED, Path("x.json"), with_header=False)

# Locked + XP in hand: the elemental page switches from BP to XP pricing (14 per
# power) and the owned power reprices as an XP purchase.
CHAR_ELEMENTAL_INPLAY = _elemental_godblooded("egi", "In-Play Elemental")
lifecycle.lock_chargen(CHAR_ELEMENTAL_INPLAY, RS)
CHAR_ELEMENTAL_INPLAY.xp_earned = 40

@ui.page('/godblooded-elemental-picker-inplay')
def page_godblooded_elemental_picker_inplay():
    picker.build_picker(RS, CHAR_ELEMENTAL_INPLAY, Path("eg2.json"), with_header=False,
                        initial_group="elemental")

# No powers owned: the Owned section is absent, all nine still list as available.
CHAR_ELEMENTAL_EMPTY = _elemental_godblooded("ege", "Empty Elemental")
CHAR_ELEMENTAL_EMPTY.elemental_powers = []

@ui.page('/godblooded-elemental-picker-empty')
def page_godblooded_elemental_picker_empty():
    picker.build_picker(RS, CHAR_ELEMENTAL_EMPTY, Path("eg3.json"), with_header=False,
                        initial_group="elemental")

# The Sheet's Charms & Sorcery band must head an Elemental Powers section for a
# character who owns any — the click-through found the picker had them but the sheet
# did not.
@ui.page('/godblooded-elemental-sheet')
def page_godblooded_elemental_sheet():
    sheet_app.render_sheet(view.build_sheet_view(RS, CHAR_ELEMENTAL_GODBLOODED))

# Artifact re-verify repro: a Dragon King in the two-flagships shape (Artifact 5 +
# two 5-dot artifacts) so the live rating-edit round-trip can be driven in a test.
CHAR_DK_2FLAG = Character(id="dk2f", name="Two Flagships", exalt_type="Dragon-Kings",
                          caste="pterok", essence_rating=2)
CHAR_DK_2FLAG.virtues.update({"conviction": 3, "valor": 2, "compassion": 2, "temperance": 2})
CHAR_DK_2FLAG.favored_abilities = [AbilityName.MELEE, AbilityName.DODGE, AbilityName.SURVIVAL]
CHAR_DK_2FLAG.favored_path = "dk.solid-earth"
CHAR_DK_2FLAG.backgrounds.append(BackgroundEntry(name="Artifact", rating=5))
CHAR_DK_2FLAG.artifacts.append(ArtifactEntry(name="Wings of the Raptor", rating=5))
CHAR_DK_2FLAG.artifacts.append(ArtifactEntry(name="Wyld-Cutting Blade", rating=5))

@ui.page('/dk-artifacts-2flag-advantages')
def page_dk_artifacts_2flag_advantages():
    # The artifacts panel and its readout moved to Gear on 2026-08-13; the route name
    # is kept so the test's history stays greppable.
    gear.build_gear(RS, CHAR_DK_2FLAG, Path("x.json"), with_header=False)

@ui.page('/dk-artifacts-2flag-sheet')
def page_dk_artifacts_2flag_sheet():
    sheet_app.render_sheet(view.build_sheet_view(RS, CHAR_DK_2FLAG))

# The per-row Background RUNG — the printed dot ladder for the rating the row holds.
# Its own characters rather than reusing CHAR_BG_MERITS: these tests MOVE the rating,
# and a module-level character shared with the description tests would carry the edit
# into whichever test ran next.
CHAR_BG_RUNG = Character(id="bgrung", name="Rungs", exalt_type="Solar", caste="dawn",
                         essence_rating=1)
CHAR_BG_RUNG.backgrounds = [BackgroundEntry(name="Allies", rating=2)]

@ui.page('/backgrounds-rung')
def page_backgrounds_rung():
    advantages.build_advantages(RS, CHAR_BG_RUNG, Path("x.json"), with_header=False)

CHAR_BG_RUNG_XP = CHAR_BG_RUNG.model_copy(deep=True)
CHAR_BG_RUNG_XP.id = "bgrungx"
CHAR_BG_RUNG_XP.chargen_locked = True

@ui.page('/backgrounds-rung-xp')
def page_backgrounds_rung_xp():
    advantages.build_advantages(RS, CHAR_BG_RUNG_XP, Path("x.json"), with_header=False)

# The Background catalogue DIALOG's ladder rendering. Its own character again: the
# dialog test reads the full text of the Allies entry, and the description tests
# RENAME the Background on the character behind /merits-backgrounds, so sharing that
# route makes this test pass or fail on execution order.
CHAR_BG_DIALOG = Character(id="bgdlg", name="Ladders", exalt_type="Solar", caste="dawn",
                           essence_rating=1)
CHAR_BG_DIALOG.backgrounds = [BackgroundEntry(name="Allies", rating=1)]

@ui.page('/backgrounds-ladder-dialog')
def page_backgrounds_ladder_dialog():
    advantages.build_advantages(RS, CHAR_BG_DIALOG, Path("x.json"), with_header=False)

# --------------------------------------------------------------------------- #
# The rating-control ceilings come from the engine (R5 of briefs-background-rules).
# Four dedicated characters, each with ONE dotted Background row so the pip count
# and the lone unlabelled number input are unambiguous:
#   * Mountain Folk Artifact — the ceiling is 10 (both sides of the lock);
#   * Solar Artifact — the ceiling stays 5 (every other splat still stops at 5).
# Dedicated because these tests MOVE the ratings; sharing a character with the
# ladder tests above would make one pass or fail on execution order.
# --------------------------------------------------------------------------- #
# Attributes are passed to the CONSTRUCTOR so pydantic coerces the string keys to
# AttributeName — assignment after construction would bypass validation and leave raw
# strings in the dict, which the range checks crash on.
_CHAR_ATTRIBUTES_MF = {"strength": 3, "dexterity": 3, "stamina": 3,
                       "charisma": 3, "manipulation": 3, "appearance": 3,
                       "perception": 3, "intelligence": 3, "wits": 3}
_CHAR_ATTRIBUTES_1 = {"strength": 1, "dexterity": 1, "stamina": 1,
                      "charisma": 1, "manipulation": 1, "appearance": 1,
                      "perception": 1, "intelligence": 1, "wits": 1}
CHAR_MF_ART = Character(id="mfart", name="Jadeborn", exalt_type="Mountain-Folk",
                        origin="enlightened", caste="worker", essence_rating=2,
                        attributes=_CHAR_ATTRIBUTES_MF)
CHAR_MF_ART.backgrounds = [BackgroundEntry(name="Artifact", rating=3)]

@ui.page('/mf-artifact-chargen')
def page_mf_artifact_chargen():
    advantages.build_advantages(RS, CHAR_MF_ART, Path("x.json"), with_header=False)

# A Mountain Folk holding the capped Resources Background, for the effective-rating
# note on the row. Its own character because the test reads this row's CONTENT.
CHAR_MF_RES = CHAR_MF_ART.model_copy(deep=True)
CHAR_MF_RES.id = "mfres"
CHAR_MF_RES.backgrounds = [BackgroundEntry(name="Resources", rating=3)]

@ui.page('/mf-resources')
def page_mf_resources():
    advantages.build_advantages(RS, CHAR_MF_RES, Path("x.json"), with_header=False)

# The mundane-goods section and the services price list (M&C p.123). Its own character
# because the goods test MUTATES the list, and its own Resources rating so the
# affordability hint has something to say.
CHAR_GOODS = Character(id="goods", name="Buyer", exalt_type="Solar", caste="dawn",
                       essence_rating=2)
CHAR_GOODS.backgrounds = [BackgroundEntry(name="Resources", rating=3)]

@ui.page('/goods')
def page_goods():
    gear.build_gear(RS, CHAR_GOODS, Path("x.json"), with_header=False)

# The inventory VIEW: one character owning something of every kind at once, including
# the overlap that makes the filters non-exclusive (an artifact daiklave is a weapon
# AND an artifact) and an ammunition stack.
CHAR_INV = Character(id="inv", name="Packrat", exalt_type="Solar", caste="dawn",
                     essence_rating=2)
CHAR_INV.backgrounds = [BackgroundEntry(name="Artifact", rating=2),
                        BackgroundEntry(name="Resources", rating=3)]
CHAR_INV.weapons.append(Weapon(name="Daiklave", artifact_rating=2, accuracy=2, damage=5))
CHAR_INV.weapons.append(Weapon(name="Long Bow", accuracy=1))
CHAR_INV.weapons.append(Weapon(name="Frog Crotch Arrow", damage=4, quantity=20))
CHAR_INV.armor.append(Armor(name="Buff Jacket", soak_lethal=3, soak_bashing=4))
CHAR_INV.artifacts.append(ArtifactEntry(name="Tattered Wings", rating=2))
CHAR_INV.gear.append(GearEntry(name="Fine clothes", resources_cost=2))

@ui.page('/inventory')
def page_inventory():
    gear.build_gear(RS, CHAR_INV, Path("x.json"), with_header=False)

CHAR_MF_ART_PLAY = CHAR_MF_ART.model_copy(deep=True)
CHAR_MF_ART_PLAY.id = "mfartx"
lifecycle.lock_chargen(CHAR_MF_ART_PLAY, RS)

@ui.page('/mf-artifact-play')
def page_mf_artifact_play():
    advantages.build_advantages(RS, CHAR_MF_ART_PLAY, Path("x.json"), with_header=False)

CHAR_SOLAR_ART = Character(id="solart", name="Aurora", exalt_type="Solar", caste="dawn",
                           essence_rating=1, attributes=_CHAR_ATTRIBUTES_1)
CHAR_SOLAR_ART.backgrounds = [BackgroundEntry(name="Artifact", rating=3)]

@ui.page('/solar-artifact-chargen')
def page_solar_artifact_chargen():
    advantages.build_advantages(RS, CHAR_SOLAR_ART, Path("x.json"), with_header=False)

CHAR_SOLAR_ART_PLAY = CHAR_SOLAR_ART.model_copy(deep=True)
CHAR_SOLAR_ART_PLAY.id = "solartx"
lifecycle.lock_chargen(CHAR_SOLAR_ART_PLAY, RS)

@ui.page('/solar-artifact-play')
def page_solar_artifact_play():
    advantages.build_advantages(RS, CHAR_SOLAR_ART_PLAY, Path("x.json"), with_header=False)

# Three more rating-ceiling shapes the four routes above do not produce, each a
# different way the engine-supplied ceiling can be wrong on screen:
#   * a PER-ROW lift (Sidereal Connections 10) where the rule's own cap is a TOTAL;
#   * a BAR (mortal Artifact, cap 0) on a row the character already holds — the
#     control must still be steppable DOWN or the player cannot fix the error;
#   * a locked character holding MORE than the post-lock ceiling (Celestial Manse 5
#     against a max of 3), the shape a save written before the rule existed has.
CHAR_SID_CONN = Character(id="sidconn", name="Chejop", exalt_type="Sidereal",
                          caste="journeys", essence_rating=2,
                          attributes=_CHAR_ATTRIBUTES_MF)
CHAR_SID_CONN.backgrounds = [BackgroundEntry(name="Connections", rating=3)]

@ui.page('/sidereal-connections-chargen')
def page_sidereal_connections_chargen():
    advantages.build_advantages(RS, CHAR_SID_CONN, Path("x.json"), with_header=False)

CHAR_MORTAL_ART = Character(id="mortart", name="Hopeful", exalt_type="Mortal", caste="",
                            origin="heroic", essence_rating=1,
                            attributes=_CHAR_ATTRIBUTES_1)
CHAR_MORTAL_ART.backgrounds = [BackgroundEntry(name="Artifact", rating=2)]

@ui.page('/mortal-artifact-barred-chargen')
def page_mortal_artifact_barred_chargen():
    advantages.build_advantages(RS, CHAR_MORTAL_ART, Path("x.json"), with_header=False)

CHAR_SID_OVER = Character(id="sidover", name="Overhoused", exalt_type="Sidereal",
                          caste="journeys", essence_rating=2,
                          attributes=_CHAR_ATTRIBUTES_MF)
CHAR_SID_OVER.backgrounds = [BackgroundEntry(name="Celestial Manse", rating=5)]
CHAR_SID_OVER.chargen_locked = True

@ui.page('/sidereal-over-ceiling-play')
def page_sidereal_over_ceiling_play():
    advantages.build_advantages(RS, CHAR_SID_OVER, Path("x.json"), with_header=False)

# The Resources affordability hint on the gear dialogs (core p.325). Resources 2 puts
# the three bows on the three printed cases at once — Self Bow 1 under, Long Bow 2
# equal, Composite Bow 3 over — so one route exercises the whole rule.
CHAR_RESOURCES_2 = Character(id="res2", name="Thrifty", exalt_type="Solar", caste="dawn",
                             essence_rating=2)
CHAR_RESOURCES_2.backgrounds = [BackgroundEntry(name="Resources", rating=2)]

@ui.page('/gear-resources')
def page_gear_resources():
    gear.build_gear(RS, CHAR_RESOURCES_2, Path("x.json"), with_header=False)

# A chargen character sitting on the transient over-cap state the editor creates every
# time a specialty row is appended: `add_spec` writes the row on Melee and the player
# retargets it afterwards, so row 4 is blank-and-Melee until the select is touched. Its
# own route because the test edits this character's specialty list through the UI.
CHAR_SPEC_STALE = Character(id="spec", name="Specialist", exalt_type="Solar", caste="dawn")
CHAR_SPEC_STALE.specialties = [
    Specialty(ability=AbilityName.MELEE, name="Daiklaives", rating=1) for _ in range(3)
] + [Specialty(ability=AbilityName.MELEE, name="", rating=1)]

@ui.page('/specialty-retarget')
def page_specialty_retarget():
    editor.build_editor(RS, CHAR_SPEC_STALE, Path("x.json"), with_header=False)

# A character holding a Manse, for the Hearthstone picker. Its own route because the
# test reads this character's Background list and note text.
CHAR_MANSE = Character(id="manse", name="Stonekeeper", exalt_type="Solar", caste="dawn")
CHAR_MANSE.backgrounds = [BackgroundEntry(name="Manse", rating=3),
                          BackgroundEntry(name="Artifact", rating=3)]

@ui.page('/manse-hearthstones')
def page_manse_hearthstones():
    advantages.build_advantages(RS, CHAR_MANSE, Path("x.json"), with_header=False)

# Picking a Hearthstone MUTATES the character, so it needs a character of its own — a
# @ui.page route builds once per session and a shared global leaks between render
# tests.
CHAR_MANSE_PICK = Character(id="mansep", name="Picker", exalt_type="Solar",
                            caste="dawn")
CHAR_MANSE_PICK.backgrounds = [BackgroundEntry(name="Manse", rating=3)]

@ui.page('/manse-pick')
def page_manse_pick():
    advantages.build_advantages(RS, CHAR_MANSE_PICK, Path("x.json"),
                                with_header=False)

# Raising the Manse rating must move the DENOMINATOR of the running total. Its own
# route because the test mutates this character's rating.
# LOCKED, so the rating control is the play regime's number input rather than the
# chargen dot track — a Manse grows or falls through the story, which is when this
# actually bites, and the dots are unmarked icons no test can aim at.
CHAR_MANSE_RAISE = Character(id="mr", name="Climber", exalt_type="Solar", caste="dawn",
                             chargen_locked=True)
CHAR_MANSE_RAISE.backgrounds = [BackgroundEntry(
    name="Manse", rating=3,
    hearthstones=[HearthstoneEntry(name="Gem of Adamant Skin", rating=4)])]

@ui.page('/manse-raise')
def page_manse_raise():
    advantages.build_advantages(RS, CHAR_MANSE_RAISE, Path("x.json"),
                                with_header=False)

# A Manse row flipped to Demesne: it keeps the toggle (so it can be flipped back) but
# loses the Hearthstone picker.
CHAR_DEMESNE = Character(id="dem", name="Wildling", exalt_type="Solar", caste="dawn")
CHAR_DEMESNE.backgrounds = [BackgroundEntry(name="Manse", rating=3, is_demesne=True)]

@ui.page('/manse-demesne')
def page_manse_demesne():
    advantages.build_advantages(RS, CHAR_DEMESNE, Path("x.json"), with_header=False)

# A TIERED Manse allowance (Abyssal / Dragon-Blooded ladders), which is a different
# code path from the linear one — it carries a printed tier label and a per-stone
# ceiling the corebook's Manse has no equivalent of.
CHAR_MANSE_TIERED = Character(id="mt", name="Graveward", exalt_type="Abyssal",
                              caste="Dusk")
CHAR_MANSE_TIERED.backgrounds = [BackgroundEntry(
    name="Underworld Manse", rating=3,
    hearthstones=[HearthstoneEntry(name="Gem of Adamant Skin", rating=4)])]

@ui.page('/manse-tiered')
def page_manse_tiered():
    advantages.build_advantages(RS, CHAR_MANSE_TIERED, Path("x.json"),
                                with_header=False)

# A STRANDED stone: one held on a row that grows none, which is what renaming a Manse
# row leaves behind. The allowance is None here, so the row renders through a branch
# nothing else reaches.
CHAR_STRANDED = Character(id="st", name="Magpie", exalt_type="Solar", caste="dawn")
CHAR_STRANDED.backgrounds = [BackgroundEntry(
    name="Resources", rating=3,
    hearthstones=[HearthstoneEntry(name="Stone of Healing", rating=1)])]

@ui.page('/manse-stranded')
def page_manse_stranded():
    advantages.build_advantages(RS, CHAR_STRANDED, Path("x.json"), with_header=False)

# An archer carrying arrows, for the nocked-arrow control on the Play tab. Its own
# route because the test reads this character's weapon list.
CHAR_ARCHER = Character(id="arch", name="Fletcher", exalt_type="Solar", caste="dawn")
CHAR_ARCHER.attributes[AttributeName.DEXTERITY] = 4
CHAR_ARCHER.abilities[AbilityName.ARCHERY] = 3
CHAR_ARCHER.weapons.append(Weapon(name="Long Bow", accuracy=1, rate=3, range=200,
                                  max_strength=4))
CHAR_ARCHER.weapons.append(Weapon(name="Frog Crotch Arrow", damage=4, damage_type="L",
                                  quantity=20,
                                  notes="the lethal soak of the target's armour is doubled"))

@ui.page('/archer-pools')
def page_archer_pools():
    play.build_play(RS, CHAR_ARCHER, Path("x.json"), with_header=False)

# A Solar with a flawed Valor, for the sample-Flaw dropdown.
CHAR_VFLAW = Character(id="vf", name="Cursed", exalt_type="Solar", caste="dawn")
CHAR_VFLAW.virtue_flaw = VirtueFlaw(virtue=VirtueName.VALOR)

@ui.page('/virtue-flaw')
def page_virtue_flaw():
    editor.build_editor(RS, CHAR_VFLAW, Path("x.json"), with_header=False)
