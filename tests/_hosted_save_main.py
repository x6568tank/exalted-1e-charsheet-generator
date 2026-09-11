"""Main file for the hosted-save test. Two routes, one hosted and one not.

'/' is PRODUCTION wiring: `register_pages` with a `session_root`, which is what
`server/main.py` does. The property under test is that Save writes server-side on
that path, thus the test cannot use a route that supplies its own arrangement.

'/desktop' is the CONTROL. It calls `build_app` directly with no hosted flag,
which is the browser branch: a download, and no file. ⚠ It is deliberately NOT
production wiring — its only job is to show that the test can tell the two
branches apart. A control that passed through `register_pages` would need a second
route set and would register '/' twice.

⚠ Do not import `tests/_ui_main.py` here. Its module-level characters are shared.

See `docs/plans/hosting-state-model.md` section 5.1a.
"""

import sys
from pathlib import Path

from nicegui import ui

from exalted_builder import rules_db
from exalted_builder.models.character import Character
from exalted_builder.ui import builder

# runpy executes this file by path, thus the repository root can be absent from
# sys.path and `tests` is then not importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests import _hosted_save_state as state  # noqa: E402

RS = rules_db.load_app_ruleset(Path("exalted_builder/data"))

# ⚠ The prototype path is OUTSIDE the root on purpose. See
# `server/main.prototype_context`: a prototype path that turns up inside a session
# directory is the section 3.7 defect, and a prototype inside the root hides it.
CTX = builder.make_context(Character(id="hosted", name=state.START_NAME, caste="dawn"),
                           state.ROOT.parent / "prototype.character.json")
CTX["adversary_catalog"] = {}

state.REGISTRY = builder.register_pages(RS, CTX, session_root=state.ROOT)

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


if __name__ in {"__main__", "__mp_main__"}:
    # ⚠ The secret is necessary and the harness does not supply it for a main file.
    ui.run(storage_secret="hosted-save-test-secret")
