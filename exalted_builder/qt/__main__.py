"""Run the native app: `python -m exalted_builder.qt [path/to/foo.character.json]`.

With a path it opens that character; with none it starts a blank new character whose
save lands next to the executable (see persistence.default_save_dir), matching the
NiceGUI builder's load(). The ruleset comes from load_app_ruleset so the custom layer
is present, as the webapp loads it.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox

import exalted_builder
from exalted_builder import persistence, rules_db
from exalted_builder.models.character import Character
from exalted_builder.qt.main_window import MainWindow

_DATA_DIR = Path(exalted_builder.__file__).parent / "data"


def open_character(argv: list[str]) -> tuple[Character, Path, str]:
    """Resolve the command line to `(character, save_path, complaint)`.

    A readable path opens that character; no argument opens a blank one. ⚠ An
    UNREADABLE path opens a blank one too, with the complaint for the caller to show —
    it must never be fatal. The packaged build is windowed (`console=False`), so an
    exception here means the executable dies with the traceback going nowhere and
    nothing at all appearing on screen: a mistyped path, a moved save, or a stray
    argument from a desktop launcher would read as "the app doesn't work".
    """
    if len(argv) > 1:
        path = Path(argv[1])
        try:
            return persistence.load_character(path), path, ""
        except Exception as ex:               # noqa: BLE001 - any load failure, reported
            complaint = f"Could not open {path}: {ex}\n\nStarted a new character instead."
    else:
        complaint = ""
    character = Character(id="char.new")
    return (character,
            persistence.default_save_dir() / persistence.suggested_filename(character),
            complaint)


def main() -> None:
    app = QApplication(sys.argv)
    ruleset = rules_db.load_app_ruleset(_DATA_DIR)
    character, save_path, complaint = open_character(sys.argv)
    win = MainWindow(ruleset, character, save_path)
    win.show()
    if complaint:
        QMessageBox.warning(win, "Exalted 1e", complaint)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
