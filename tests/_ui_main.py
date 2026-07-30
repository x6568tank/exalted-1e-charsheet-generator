"""Helper 'main file' for the NiceGUI User-simulation regression test."""
import json
import tempfile
from pathlib import Path
from nicegui import ui
from exalted_builder import rules_db
from exalted_builder.engine import lifecycle
from exalted_builder.models.character import (
    Armor, ArtSpecialty, BackgroundEntry, Character, CollegeRating, Damage,
    HouseRules, PlayState, RitualEntry, ScienceRating, ThaumaturgyState, Weapon)
from exalted_builder.models.party import Party, PartyMember
from exalted_builder.models.rules import AbilityName, Orientation
from exalted_builder.ui import app as sheet_app
from exalted_builder.ui import (builder, combos, custom, editor, gm, picker,
                                play, storyteller, view, xp)

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

@ui.page('/blank')
def page_blank():
    editor.build_editor(RS, CHAR_BLANK, Path("x.json"), with_header=False)

@ui.page('/play')
def page_play():
    play.build_play(RS, CHAR_PLAY, Path("x.json"), with_header=False)

@ui.page('/xp')
def page_xp():
    xp.build_xp(RS, CHAR_XP, Path("x.json"), with_header=False)

@ui.page('/db')
def page_db():
    editor.build_editor(RS, CHAR_DB, Path("x.json"), with_header=False)

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
    xp.build_xp(RS, CHAR_SID_XP, Path("x.json"), with_header=False)

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
    xp.build_xp(RS, CHAR_THAUM_XP, Path("th6.json"), with_header=False)


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
