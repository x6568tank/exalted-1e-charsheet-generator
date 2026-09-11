"""
server/config.py — the deployment settings that come from the environment.

NiceGUI signs the session cookie with `storage_secret`. Without one,
`app.storage.user` raises, and tier 1 of `docs/plans/hosting-state-model.md`
section 3.4 cannot work. This module supplies the secret.

⚠ Do not put a default secret in this file, or in any file. A known secret lets a
client forge a session cookie. The fallback here is random for each process.

⚠ A random fallback changes at each restart. Thus every session cookie becomes
invalid, and each user gets a new empty session. This is correct for the desktop
application, which has one user and no server. A hosted deployment must set
`EXALTED_STORAGE_SECRET`.
"""

from __future__ import annotations

import os
import secrets

# The environment variable. `custom_content.CUSTOM_DIR_ENV` uses the same prefix.
STORAGE_SECRET_ENV = "EXALTED_STORAGE_SECRET"

# The secret of this process, if the environment gives none. Made one time, at the
# first request, and kept for the life of the process.
_ephemeral: str | None = None


def storage_secret() -> str:
    """Return the key that signs the session cookie.

    Read `EXALTED_STORAGE_SECRET`. If it is absent or empty, make a random key and
    return the same key for each subsequent call in this process.
    """
    configured = os.environ.get(STORAGE_SECRET_ENV, "").strip()
    if configured:
        return configured
    global _ephemeral  # noqa: PLW0603
    if _ephemeral is None:
        _ephemeral = secrets.token_urlsafe(32)
    return _ephemeral


def reset_ephemeral_secret() -> None:
    """Discard the random key of this process. The next call to `storage_secret`
    makes a new one.

    ⚠ This is for the tests. A call to it in a running server makes every session
    cookie invalid.
    """
    global _ephemeral  # noqa: PLW0603
    _ephemeral = None
