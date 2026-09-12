"""The state that the account-homebrew test and its main file both use.

⚠ Import this module BY NAME on both sides. The main file runs by path (runpy),
thus a value in its own module scope is absent from the test. See
`tests/_hosted_save_state.py`, which has the same shape for the same reason.
"""

from __future__ import annotations

from pathlib import Path
import os
import tempfile

# The session root. The process id keeps one run apart from an earlier run.
ROOT = Path(tempfile.gettempdir()) / f"exalted-account-homebrew-{os.getpid()}"

# The DEFAULT library. The test points `EXALTED_CUSTOM_DIR` here and asserts that
# nothing is ever written into it.
DEFAULT_LIBRARY = Path(tempfile.gettempdir()) / f"exalted-default-library-{os.getpid()}"

# The registry that `register_pages` returns. The main file assigns it.
# ⚠ Read it as `state.REGISTRY`. A `from ... import` copies the None.
REGISTRY = None
