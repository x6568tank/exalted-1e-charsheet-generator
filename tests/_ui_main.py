"""Helper 'main file' for the NiceGUI User-simulation regression test."""
from pathlib import Path
from nicegui import ui
from exalted_builder import rules_db
from exalted_builder.models.character import Character, Caste, Weapon, Armor
from exalted_builder.ui import editor

RS = rules_db.load_ruleset(Path("exalted_builder/data"))

# (a) a fresh character carrying off-catalog (custom) gear/nature — the "reload" path
CHAR_CUSTOM = Character(id="t", name="Test", caste=Caste.DAWN, nature="Wanderer")
CHAR_CUSTOM.weapons.append(Weapon(name="My Custom Blade", accuracy=2, damage=5))
CHAR_CUSTOM.armor.append(Armor(name="My Plate", soak_lethal=4))

# (b) a blank weapon to type a new name into live
CHAR_BLANK = Character(id="b", name="Blank", caste=Caste.DAWN)
CHAR_BLANK.weapons.append(Weapon(name="", accuracy=7, damage=9))

@ui.page('/custom')
def page_custom():
    editor.build_editor(RS, CHAR_CUSTOM, Path("x.json"), with_header=False)

@ui.page('/blank')
def page_blank():
    editor.build_editor(RS, CHAR_BLANK, Path("x.json"), with_header=False)

if __name__ in {"__main__", "__mp_main__"}:
    ui.run()
