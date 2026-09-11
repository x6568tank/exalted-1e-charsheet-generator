"""Main file for the session-isolation test. It uses PRODUCTION wiring on purpose.

`register_pages` builds one `ctx` and both routes close over it, which is what
`ui/builder.py:main()` does. The property under test is that wiring, thus the test
cannot use a fixture that supplies its own per-page state.

⚠ Do not import `tests/_ui_main.py` here. That file builds shared module-level
characters. A shared character makes the test report sharing that the app did not
cause.

See `docs/plans/hosting-state-model.md` section 3.8.
"""

import sys
from pathlib import Path

from nicegui import ui

from exalted_builder import rules_db
from exalted_builder.models.character import Character
from exalted_builder.models.party import Party, PartyMember
from exalted_builder.ui import builder

# runpy executes this file by path, thus the repository root can be absent from
# sys.path and `tests` is then not importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests._isolation_names import MEMBER_NAME, START_NAME  # noqa: E402

RS = rules_db.load_app_ruleset(Path("exalted_builder/data"))

CHAR = Character(id="iso", name=START_NAME, caste="dawn")

CTX = builder.make_context(CHAR, Path("iso.json"))
CTX["party"] = Party(
    id="party.iso",
    members=[PartyMember(character=Character(id="iso.member", name=MEMBER_NAME,
                                             caste="dawn"))],
)

# Supply an empty catalogue. `register_pages` reads the adversary templates from
# disk only if the caller gives none, and this test does not use them.
CTX["adversary_catalog"] = {}

builder.register_pages(RS, CTX)

if __name__ in {"__main__", "__mp_main__"}:
    # ⚠ The secret is necessary, and the harness does not supply it. The User
    # simulation passes a secret only when it builds the application from a `root`
    # function. This file goes through `main_file`, which runpy executes, thus the
    # secret must come from this call. Without it `app.storage.user` raises.
    # See hosting-state-model.md section 3.4, Constraint 3.
    ui.run(storage_secret="isolation-test-secret")
