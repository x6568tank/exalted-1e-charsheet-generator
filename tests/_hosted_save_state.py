"""The state that the desktop-save test and its main file both use.

⚠ This module must stay free of side effects, and both sides must import it BY
NAME. `tests/_hosted_save_main.py` is executed by path (runpy), thus it becomes a
module object that is not the one the test imports. A value that the main file
keeps in its own module scope reads as absent from the test.
"""

from __future__ import annotations

from pathlib import Path
import os
import tempfile

# The destination of the DESKTOP control route. The control asserts that nothing
# is ever written into it. ⚠ The name holds the process id, thus one run never
# sees the directory of an earlier run.
DESKTOP_DIR = Path(tempfile.gettempdir()) / f"exalted-desktop-save-{os.getpid()}"

START_NAME = "Unedited"
