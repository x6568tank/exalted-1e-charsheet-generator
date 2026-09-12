"""server/main.py — the hosted entry point.

Section 5.1 of `docs/plans/hosting-state-model.md`. This module is the caller that
turns on the per-session state of section 3. The desktop entry points
(`ui/builder.py:main` and `pack/run_app.py`) stay as they are, and they supply no
session root.

**What this module adds over the desktop entry points, and it is one argument.**
`register_pages(ruleset, ctx, session_root=...)` gives each browser session its own
save directory and its own auto-save timer. All three desktop callers pass no root.
Thus section 3 was complete and unreachable until this file.

Piece 3 adds the login gate. `build_server` registers the login pages and keys each
context on the account; `main` installs the gate. See server/auth.py.

⚠ `main` installs the gate, not `build_server`. The tests call `build_server` in a
process where the app can already run, and a middleware cannot be added then.
`tests/test_server_main.py` asserts that `main` installs it.

⚠ Run ONE worker. The session registry holds live `Character` objects, thus it can
never be JSON, thus it can never cross a process boundary. Section 3.4 gives the
evidence, and it shows that Redis is not an alternative.

⚠ `ruleset` is shared between all sessions and is read-only. Section 5.3 records
what the custom-content layer does to that, and it is not solved here: a hosted run
still has one process-wide homebrew library.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from nicegui import ui

from .. import persistence, rules_db
from ..models.character import Character, new_character_id
from ..server import auth, config, db, public, quota, wiki
from ..server.session import SessionRegistry
from ..ui import builder

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Loopback. An operator that puts the server on a network passes `--host`.
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080


# The session cookie of the hosted server. The human ruled the HTTPS-only flag on
# 2026-09-11.
#
# ⚠ The `__Host-` prefix is a rule of the browser. A cookie with it must be Secure,
# must have the path "/", and must have no domain. Thus a different site under the
# same parent domain cannot set it or replace it. Without the prefix, a sibling
# subdomain can plant a session id before a login, and after the login it holds
# the login. See section 5.1d of docs/plans/hosting-state-model.md.
#
# ⚠ A Secure cookie is not stored over plain HTTP to a LAN address. `localhost` is
# an exception in the browsers.
SESSION_COOKIE = {
    "session_cookie": "__Host-exalted-session",
    "https_only": True,
    "path": "/",
    "same_site": "lax",
}


def prototype_context(session_root: Path) -> dict:
    """Return the prototype context that each session copies.

    The character is new and empty. `session_context_factory` deep-copies it for
    each session and computes that session's own destination from the session key.

    ⚠ The prototype path is OUTSIDE `session_root` on purpose, and it is never
    used by a hosted session. It is a marker: a path that appears inside a session
    directory shows that the factory returned the prototype's own path, which is
    the defect of section 3.7. A prototype path inside the root would hide that,
    and it would make the tests for it pass with no isolation.
    """
    character = Character(id=new_character_id())
    path = session_root.parent / "prototype.character.json"
    return builder.make_context(character, path)


def build_server(session_root: Path | None = None,
                 db_path: Path | None = None) -> SessionRegistry:
    """Register the hosted routes and return the registry of session contexts.

    Read the session root from `EXALTED_SESSION_ROOT` and the database from
    `EXALTED_DB_PATH` if the caller gives none. Each call raises when its variable
    is absent; there is no default, because one shared directory is the defect
    that section 3.7 removes.

    Make the account tables. Register the login pages, the public front page,
    About and the wiki. Register the builder at `auth.HOME_PATH`, because "/" is
    the public front page. Key each context on the logged-in account, thus each
    device of one player sees one character.

    ⚠ The wiki gets a BOOK ruleset from `load_ruleset`, not the merged ruleset of
    the builder. The merged ruleset holds the homebrew of the process, and the
    wiki is public. See docs/plans/vtt.md section 9.5.

    ⚠ This does not run a server and does not install the gate. `main` does both.
    """
    root = config.session_root() if session_root is None else session_root
    database = config.db_path() if db_path is None else db_path
    db.init_db(database)
    ruleset = rules_db.load_app_ruleset(_DATA_DIR)
    auth.register_auth_pages(database)
    public.register_public_pages()
    wiki.register_wiki(rules_db.load_ruleset(_DATA_DIR))
    return builder.register_pages(ruleset, prototype_context(root), session_root=root,
                                  key=auth.current_user_key, builder_path=auth.HOME_PATH)


def main() -> None:
    parser = argparse.ArgumentParser(description="Exalted 1e builder — hosted server")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()

    # Read the settings before the server starts. Each raises when it is absent,
    # thus a misconfigured deployment fails at the start and not at the first
    # request.
    secret = config.required_storage_secret()
    root = config.session_root()
    database = config.db_path()
    root.mkdir(parents=True, exist_ok=True)

    build_server(session_root=root, db_path=database)

    # ⚠ Before `ui.run`. `ui.run` adds the session middleware outside the gate,
    # thus the login state is readable when the gate runs.
    auth.install_gate()

    # The 10 MB limit of each account folder. Each hosted write goes through
    # `persistence.atomic_write`, thus this one guard covers each write site.
    persistence.set_write_guard(quota.FolderQuota(root))

    # ⚠ `reload=False`. A reload makes a second process, and the registry holds
    # live objects that cannot cross one. See the module docstring.
    ui.run(title="Exalted 1e — Table", host=args.host, port=args.port,
           reload=False, show=False, storage_secret=secret,
           session_middleware_kwargs=SESSION_COOKIE)


if __name__ in {"__main__", "__mp_main__"}:
    main()
