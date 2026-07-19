"""Helper 'main file' for the NiceGUI User-simulation regression test."""
from pathlib import Path
from nicegui import ui
from exalted_builder import rules_db
from exalted_builder.engine import lifecycle
from exalted_builder.models.character import (
    Armor, BackgroundEntry, Character, Damage, PlayState, Weapon)
from exalted_builder.ui import app as sheet_app
from exalted_builder.ui import builder, editor, picker, play, view, xp

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

if __name__ in {"__main__", "__mp_main__"}:
    ui.run()
