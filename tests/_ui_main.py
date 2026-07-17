"""Helper 'main file' for the NiceGUI User-simulation regression test."""
from pathlib import Path
from nicegui import ui
from exalted_builder import rules_db
from exalted_builder.engine import lifecycle
from exalted_builder.models.character import Character, PlayState, Damage, Weapon, Armor
from exalted_builder.ui import editor, play, xp

RS = rules_db.load_ruleset(Path("exalted_builder/data"))

# (a) a fresh character carrying off-catalog (custom) gear/nature — the "reload" path
CHAR_CUSTOM = Character(id="t", name="Test", caste="dawn", nature="Wanderer")
CHAR_CUSTOM.weapons.append(Weapon(name="My Custom Blade", accuracy=2, damage=5))
CHAR_CUSTOM.armor.append(Armor(name="My Plate", soak_lethal=4))

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

if __name__ in {"__main__", "__mp_main__"}:
    ui.run()
