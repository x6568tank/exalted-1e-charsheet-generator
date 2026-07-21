"""Helper 'main file' for the NiceGUI User-simulation regression test."""
from pathlib import Path
from nicegui import ui
from exalted_builder import rules_db
from exalted_builder.engine import lifecycle
from exalted_builder.models.character import (
    Armor, BackgroundEntry, Character, Damage, PlayState, Weapon)
from exalted_builder.models.party import Party, PartyMember
from exalted_builder.models.rules import AbilityName
from exalted_builder.ui import app as sheet_app
from exalted_builder.ui import builder, combos, editor, gm, picker, play, view, xp

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

if __name__ in {"__main__", "__mp_main__"}:
    ui.run()
