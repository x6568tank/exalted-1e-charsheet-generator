"""Run the native app: `python -m exalted_builder.qt [path/to/foo.character.json]`.

With a path it opens that character; with none it starts a blank new character whose
save lands next to the executable (see persistence.default_save_dir), matching the
NiceGUI builder's load(). The ruleset comes from load_app_ruleset so the custom layer
is present, as the webapp loads it.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

import exalted_builder
from exalted_builder import persistence, rules_db
from exalted_builder.models.character import Character
from exalted_builder.qt.main_window import MainWindow

_DATA_DIR = Path(exalted_builder.__file__).parent / "data"


def main() -> None:
    app = QApplication(sys.argv)
    ruleset = rules_db.load_app_ruleset(_DATA_DIR)
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
        character = persistence.load_character(path)
        save_path = path
    else:
        character = Character(id="char.new")
        save_path = persistence.default_save_dir() / persistence.suggested_filename(character)
    win = MainWindow(ruleset, character, save_path)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
