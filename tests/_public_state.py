"""The state that the public-page test and its main file both use.

⚠ Import this module BY NAME on both sides. `tests/_public_main.py` is executed by
path (runpy), thus a value in its own module scope is absent from the test. See
`tests/_auth_state.py`.
"""

from __future__ import annotations

from pathlib import Path
import os
import tempfile

_BASE = Path(tempfile.gettempdir()) / f"exalted-public-{os.getpid()}"

ROOT = _BASE / "sessions"
DB = _BASE / "accounts" / "exalted.db"
# A homebrew library with one Charm in it. The builder reads it; the wiki must not.
CUSTOM = _BASE / "custom"

PASSWORD = "correct horse"

# The homebrew Charm. A name that no book prints, thus a search finds it only if
# the wiki reads the custom layer.
HOMEBREW_NAME = "Zanzibar Quokka Homebrew Strike"
HOMEBREW_ID = "custom.zanzibar-quokka-homebrew-strike"
