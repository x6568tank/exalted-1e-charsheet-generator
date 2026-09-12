"""Main file for the login-gate test. PRODUCTION wiring: `server/main.build_server`
and `auth.install_gate`, in the order that `server/main.main` uses.

⚠ Do not add a route here. Each route of this app must be behind the gate, and
the test enumerates them. A control route here must be gated too.

See `docs/plans/hosting-state-model.md` section 5.1d.
"""

import shutil
import sys
from pathlib import Path

from nicegui import ui

from exalted_builder import persistence
from exalted_builder.server import auth, db, main, quota

# runpy executes this file by path, thus the repository root can be absent from
# sys.path and `tests` is then not importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests import _auth_state as state  # noqa: E402

# A full bcrypt hash costs a quarter second, and each case makes accounts.
db.BCRYPT_ROUNDS = 4
db._dummy_hash = None

# Each case starts with no accounts and no session folders.
shutil.rmtree(state.DB.parent, ignore_errors=True)
shutil.rmtree(state.ROOT, ignore_errors=True)

state.REGISTRY = main.build_server(session_root=state.ROOT, db_path=state.DB)
auth.install_gate()
# ⚠ The guard stays installed after the case. It checks paths under `state.ROOT`
# only, thus no other test sees it.
persistence.set_write_guard(quota.FolderQuota(state.ROOT))

if __name__ in {"__main__", "__mp_main__"}:
    ui.run(storage_secret="auth-test-secret")
