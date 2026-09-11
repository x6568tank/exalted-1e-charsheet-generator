"""Main file for the per-session destination test. PRODUCTION wiring on purpose.

`register_pages` receives a `session_root`, which is what a hosted run does. The
property under test is that wiring, thus the test cannot use a fixture that
supplies its own per-page state.

⚠ Do not import `tests/_ui_main.py` here. That file builds shared module-level
characters, which makes the test report sharing that the app did not cause.

See `docs/plans/hosting-state-model.md` section 3.7.
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

from tests import _session_dest_state as state  # noqa: E402

RS = rules_db.load_app_ruleset(Path("exalted_builder/data"))

# ⚠ The prototype path is OUTSIDE the root on purpose. A session that keeps this
# path is the defect: the destination must come from the session key, not from the
# prototype.
CTX = builder.make_context(Character(id="dest", name=state.START_NAME, caste="dawn"),
                           state.ROOT.parent / "prototype.character.json")
CTX["adversary_catalog"] = {}

# Assign through the shared module, thus the test sees it. See that file.
state.REGISTRY = builder.register_pages(RS, CTX, session_root=state.ROOT)

if __name__ in {"__main__", "__mp_main__"}:
    # ⚠ The secret is necessary and the harness does not supply it for a main file.
    # Without it `app.storage.browser` raises. See hosting-state-model.md section
    # 3.4, Constraint 3.
    ui.run(storage_secret="session-dest-test-secret")
