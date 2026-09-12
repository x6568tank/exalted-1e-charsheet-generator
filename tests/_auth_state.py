"""The state that the login-gate test and its main file both use.

⚠ Import this module BY NAME on both sides. `tests/_auth_main.py` is executed by
path (runpy), thus a value in its own module scope is absent from the test. See
`tests/_hosted_save_state.py`.
"""

from __future__ import annotations

from pathlib import Path
import os
import tempfile

# ⚠ The names hold the process id, thus one run never sees an earlier run.
ROOT = Path(tempfile.gettempdir()) / f"exalted-auth-sessions-{os.getpid()}"
DB = Path(tempfile.gettempdir()) / f"exalted-auth-{os.getpid()}" / "exalted.db"

PASSWORD = "correct horse"

# The registry that `build_server` returns. The main file assigns it. Read it
# through the module, not with `from ... import REGISTRY`.
REGISTRY = None
