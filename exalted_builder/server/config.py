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
from pathlib import Path

# The environment variable. `custom_content.CUSTOM_DIR_ENV` uses the same prefix.
STORAGE_SECRET_ENV = "EXALTED_STORAGE_SECRET"

# The parent folder of the per-session save directories.
SESSION_ROOT_ENV = "EXALTED_SESSION_ROOT"

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


def session_root() -> Path:
    """Return the folder that holds one save directory for each browser session.

    Read `EXALTED_SESSION_ROOT`. Raise `RuntimeError` if it is absent or empty.

    ⚠ This has no default, and the absent value raises. It does not return a
    fallback path. A fallback gives all sessions one directory, which is the
    defect of hosting-state-model.md section 3.7: N browsers write one file on
    the auto-save timer and nothing reports it.

    The desktop application does not call this. It has one user, thus it keeps
    the path that the user opened. See `builder.session_context_factory`, which
    shares the prototype path when it receives no root.
    """
    configured = os.environ.get(SESSION_ROOT_ENV, "").strip()
    if not configured:
        raise RuntimeError(
            f"{SESSION_ROOT_ENV} is not set. A hosted run must give each browser "
            "session its own save directory. There is no default: one shared "
            "directory makes every session write one file. See "
            "docs/plans/hosting-state-model.md section 3.7.")
    return Path(configured).expanduser()


def reset_ephemeral_secret() -> None:
    """Discard the random key of this process. The next call to `storage_secret`
    makes a new one.

    ⚠ This is for the tests. A call to it in a running server makes every session
    cookie invalid.
    """
    global _ephemeral  # noqa: PLW0603
    _ephemeral = None
