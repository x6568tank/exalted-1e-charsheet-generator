"""Run the native app: `python -m exalted_builder.qt [path/to/foo.character.json]`.

A path opens that character. No argument starts a blank character. The save of a blank
character goes next to the executable (see `persistence.default_save_dir`). This agrees
with the `load()` of the NiceGUI builder. The ruleset comes from `load_app_ruleset`, thus
the custom layer is present, as it is in the webapp.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

import exalted_builder
from exalted_builder import branding, persistence, rules_db
from exalted_builder.models.character import Character, new_character_id
from exalted_builder.qt.main_window import MainWindow

_DATA_DIR = Path(exalted_builder.__file__).parent / "data"


def open_character(argv: list[str]) -> tuple[Character, Path, str]:
    """Resolve the command line to `(character, save_path, complaint)`.

    Input: the command line. Output: a character, the path to save it to, and a
    complaint for the caller to show. A readable path opens that character. No argument
    opens a blank character.

    ⚠ An UNREADABLE path also opens a blank character and returns a complaint. This
    function must never be fatal. The packaged build is windowed (`console=False`). Thus
    an exception here stops the executable, the traceback goes nowhere, and no window
    appears. A mistyped path, a moved save or an unwanted argument from a desktop
    launcher then reads as a failure of the whole app.
    """
    if len(argv) > 1:
        path = Path(argv[1])
        try:
            return persistence.load_character(path), path, ""
        except Exception as ex:               # noqa: BLE001 - any load failure, reported
            complaint = f"Could not open {path}: {ex}\n\nStarted a new character instead."
    else:
        complaint = ""
    character = Character(id=new_character_id())
    return (character,
            persistence.default_save_dir() / persistence.suggested_filename(character),
            complaint)


def main() -> None:
    app = QApplication(sys.argv)
    # ⚠ Wayland gets no icon pixels from setWindowIcon. KWin matches the app_id of the
    # surface to an installed .desktop entry. With no identity, the title bar shows a
    # generic icon, but the task bar shows the correct icon. `setDesktopFileName` supplies
    # that app_id.
    app.setApplicationName(branding.APP_NAME)
    app.setOrganizationName(branding.ORG_NAME)
    app.setDesktopFileName(branding.APP_ID)
    branding.install_desktop_entry()      # returns None on failure; never fatal
    # Set the icon on the APPLICATION, not on the window. Every window then gets it,
    # including the separate QMainWindow of the party/ST screen. An absent file leaves
    # Qt's default icon. This must not be fatal.
    # ⚠ Build the icon from the SQUARE sizes that are rendered in advance. Do not use the
    # master. The master is 500x502, and Qt keeps the aspect ratio. Thus pixmap(16,16)
    # from the master is 15x16 and is not correctly aligned in a square title-bar slot.
    # `addFile` lets Qt select the nearest rendering. The fallback is the master, then
    # Qt's default. Thus an absent asset costs the icon only.
    sizes = branding.app_icon_sizes() or [p for p in [branding.app_icon_path()] if p]
    if sizes:
        icon = QIcon()
        for path in sizes:
            icon.addFile(str(path))
        app.setWindowIcon(icon)
    ruleset = rules_db.load_app_ruleset(_DATA_DIR)
    character, save_path, complaint = open_character(sys.argv)
    win = MainWindow(ruleset, character, save_path)
    win.show()
    if complaint:
        QMessageBox.warning(win, "Exalted 1e", complaint)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
