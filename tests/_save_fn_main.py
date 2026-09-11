"""Main file for the tab save-callback test.

Each page builds ONE tab with `with_header=True`, which is the only state in
which a tab shows its own Save button, and gives it a recording callback. The
test clicks Save and reads `CALLS`.

⚠ The characters and the call log are in `tests/_save_fn_state.py`, not here.
runpy executes THIS file by path, thus it is not the module the test imports.
See that file.

⚠ Do not import `tests/_ui_main.py` here. That file builds shared module-level
characters, and this test asserts on object identity.

See `docs/plans/hosting-state-model.md` section 3.5.
"""

import sys
from pathlib import Path

from nicegui import ui

from exalted_builder import rules_db
from exalted_builder.ui import (advantages, combos, editor, gear, picker, play,
                                storyteller)

# runpy executes this file by path, thus the repository root can be absent from
# sys.path and `tests` is then not importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests._save_fn_state import CHARS, recorder  # noqa: E402

RS = rules_db.load_app_ruleset(Path("exalted_builder/data"))


@ui.page("/save-editor")
def page_editor() -> None:
    editor.build_editor(RS, CHARS["editor"], recorder(CHARS["editor"]))


@ui.page("/save-gear")
def page_gear() -> None:
    gear.build_gear(RS, CHARS["gear"], recorder(CHARS["gear"]))


@ui.page("/save-advantages")
def page_advantages() -> None:
    advantages.build_advantages(RS, CHARS["advantages"],
                                recorder(CHARS["advantages"]))


@ui.page("/save-picker")
def page_picker() -> None:
    picker.build_picker(RS, CHARS["picker"], recorder(CHARS["picker"]))


@ui.page("/save-combos")
def page_combos() -> None:
    combos.build_combos(RS, CHARS["combos"], recorder(CHARS["combos"]))


@ui.page("/save-storyteller")
def page_storyteller() -> None:
    storyteller.build_storyteller(RS, CHARS["storyteller"],
                                  recorder(CHARS["storyteller"]))


@ui.page("/save-play")
def page_play() -> None:
    play.build_play(RS, CHARS["play"], recorder(CHARS["play"]))


if __name__ in {"__main__", "__mp_main__"}:
    # `main_file` runs this file through runpy, thus the server start must be
    # here. These pages read no session storage, thus they need no secret.
    ui.run()
