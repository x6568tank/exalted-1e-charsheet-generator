"""The state that the hosted-save test and its main file both use.

⚠ This module must stay free of side effects, and both sides must import it BY
NAME. `tests/_hosted_save_main.py` is executed by path (runpy), thus it becomes a
module object that is not the one the test imports. A value that the main file
keeps in its own module scope reads as absent from the test.

`tests/_session_dest_state.py` exists for the same reason.
"""

from __future__ import annotations

from pathlib import Path
import os
import tempfile

# ⚠ The names hold the process id, thus one run never sees the directories of an
# earlier run and `assert not path.exists()` does not depend on that history.
ROOT = Path(tempfile.gettempdir()) / f"exalted-hosted-save-{os.getpid()}"

# The destination of the DESKTOP control route. It is outside `ROOT`, and the
# control asserts that nothing is ever written into it.
DESKTOP_DIR = Path(tempfile.gettempdir()) / f"exalted-desktop-save-{os.getpid()}"

START_NAME = "Unedited"

# The registry that `register_pages` returns. The main file assigns it.
#
# ⚠ Read this through the module (`state.REGISTRY`), not with a `from ... import
# REGISTRY`. The import copies the None that is here at import time.
REGISTRY = None
