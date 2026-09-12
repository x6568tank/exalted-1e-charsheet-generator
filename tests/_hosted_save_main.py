"""Main file for the desktop-save test: the CONTROL routes only.

'/desktop' calls `build_app` with no hosted flag, which is the browser branch: a
download, and no file. '/desktop-gm' is the party page, which is desktop only.
The hosted cases are on the production pages, in `tests/test_character_pages.py`.

⚠ Do not import `tests/_ui_main.py` here. Its module-level characters are shared.
"""

import sys
from pathlib import Path

from nicegui import ui

from exalted_builder import rules_db
from exalted_builder.models.character import Character
from exalted_builder.ui import builder, gm

# runpy executes this file by path, thus the repository root can be absent from
# sys.path and `tests` is then not importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests import _hosted_save_state as state  # noqa: E402

RS = rules_db.load_app_ruleset(Path("exalted_builder/data"))

# The desktop control. Its own context and its own directory, so a write that
# lands here is distinguishable from a write that lands in a session directory.
DESKTOP_CTX = builder.make_context(
    Character(id="desktop", name=state.START_NAME, caste="dawn"),
    state.DESKTOP_DIR / "desktop.character.json")
DESKTOP_CTX["adversary_catalog"] = {}


@ui.page("/desktop")
def desktop_page() -> None:
    build = DESKTOP_CTX
    builder.build_app(RS, build["char"], build["path"], ctx=build)


# The party page. It is desktop only.
@ui.page("/desktop-gm")
def desktop_gm_page() -> None:
    gm.build_gm(RS, DESKTOP_CTX)


if __name__ in {"__main__", "__mp_main__"}:
    # ⚠ The secret is necessary and the harness does not supply it for a main file.
    ui.run(storage_secret="hosted-save-test-secret")
