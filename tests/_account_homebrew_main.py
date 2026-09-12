"""Main file for the account-homebrew test. PRODUCTION wiring of the builder.

The builder gets the BOOK ruleset and a session root, as `server/main.build_server`
gives it. Each session then merges the library of its own folder. The route is "/"
because this file registers no public front page.

See `docs/plans/hosting-state-model.md` section 5.3.
"""

import sys
from pathlib import Path

from nicegui import ui

from exalted_builder import rules_db
from exalted_builder.server import main as server_main
from exalted_builder.ui import builder

# runpy executes this file by path, thus the repository root can be absent from
# sys.path and `tests` is then not importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests import _account_homebrew_state as state  # noqa: E402

BOOK = rules_db.load_ruleset(Path("exalted_builder/data"))

state.REGISTRY = builder.register_pages(
    BOOK, server_main.prototype_context(state.ROOT), session_root=state.ROOT)


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(storage_secret="account-homebrew-test-secret")
