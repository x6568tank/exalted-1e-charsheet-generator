"""Main file for the public-page test. PRODUCTION wiring: `server/main.build_server`
and `auth.install_gate`, in the order that `server/main.main` uses.

⚠ The test's autouse fixture writes the homebrew library and points
`EXALTED_CUSTOM_DIR` at it BEFORE this file runs. Thus the builder's ruleset holds
the homebrew Charm, and the test asserts that the wiki does not. The fixture uses
`monkeypatch`, thus the variable does not reach a later test.

See `docs/plans/vtt.md` sections 9.4 and 9.5.
"""

import shutil
import sys
from pathlib import Path

from nicegui import ui

from exalted_builder.server import auth, db, main

# runpy executes this file by path, thus the repository root can be absent from
# sys.path and `tests` is then not importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests import _public_state as state  # noqa: E402

db.BCRYPT_ROUNDS = 4
db._dummy_hash = None

shutil.rmtree(state.ROOT, ignore_errors=True)
shutil.rmtree(state.DB.parent, ignore_errors=True)

main.build_server(session_root=state.ROOT, db_path=state.DB)
auth.install_gate()

if __name__ in {"__main__", "__mp_main__"}:
    ui.run(storage_secret="public-test-secret")
