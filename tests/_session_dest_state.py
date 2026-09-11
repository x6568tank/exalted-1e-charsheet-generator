"""The state that the per-session destination test and its main file both use.

⚠ This module must stay free of side effects, and both sides must import it BY
NAME. `tests/_session_dest_main.py` is executed by path (runpy), thus it becomes
a module object that is not the one the test imports. A value that the main file
keeps in its own module scope reads as absent from the test, and every case then
fails for a reason that is not the defect.

`tests/_isolation_names.py` exists for the same reason. See
`docs/status/handoff.md` on the runpy trap.
"""

from __future__ import annotations

from pathlib import Path
import os
import tempfile

# The save root the harness runs with. Both sides read it from this module, thus
# they agree on it without passing it through the simulation.
#
# ⚠ The name holds the process id. Thus one run never sees the directories of an
# earlier run, and `assert not path.exists()` does not depend on that history.
ROOT = Path(tempfile.gettempdir()) / f"exalted-session-dest-{os.getpid()}"

# The name of the character that '/' starts with.
START_NAME = "Unedited"

# The registry that `register_pages` returns. The main file assigns it; the test
# reads the live contexts out of it.
#
# ⚠ Read this through the module (`state.REGISTRY`), not with a `from ... import
# REGISTRY`. The import copies the None that is here at import time.
REGISTRY = None
