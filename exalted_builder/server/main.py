"""server/main.py — the hosted entry point.

Section 5.1 of `docs/plans/hosting-state-model.md`. The desktop entry points
(`ui/builder.py:main` and `pack/run_app.py`) call `builder.register_pages`. This
module calls `server/home.py` instead: `/home` lists the characters of the
account, and each character has its own page, context, file and auto-save.

Piece 3 adds the login gate. `build_server` registers the login pages; `main`
installs the gate. See server/auth.py.

⚠ `main` installs the gate, not `build_server`. The tests call `build_server` in a
process where the app can already run, and a middleware cannot be added then.
`tests/test_server_main.py` asserts that `main` installs it.

⚠ Run ONE worker. The session registry holds live `Character` objects, thus it can
never be JSON, thus it can never cross a process boundary. Section 3.4 gives the
evidence, and it shows that Redis is not an alternative.

Each account has its own homebrew library and RuleSet (section 5.3), and `main`
switches the default library off.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from nicegui import ui

from .. import custom_content, persistence, rules_db
from ..server import (auth, characters, chrome, config, db, home, nav, public, quota,
                      table_log, table_view, tables, wiki)
from ..server.session import SessionRegistry

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


def _campaign_links(table_store: tables.TableStore) -> list[tuple[str, str]]:
    """Return (address, name) of each campaign of the account of the request."""
    user_id = auth.current_user_id()
    if user_id is None:
        return []
    return [(chrome.table_url(row.id), row.name) for row in table_store.for_user(user_id)]


def build_server(session_root: Path | None = None,
                 db_path: Path | None = None) -> SessionRegistry:
    """Register the hosted routes and return the registry of session contexts.

    Read the session root from `EXALTED_SESSION_ROOT` and the database from
    `EXALTED_DB_PATH` if the caller gives none. Each call raises when its variable
    is absent; there is no default, because one shared directory is the defect
    that section 3.7 removes.

    Make the account and character tables. Register the login pages, the public
    front page, About, the wiki, and the pages of `server/home.py`: `/home` lists
    the characters of the account and `/character/<id>` opens one. Each character
    has its own context; each account has its own homebrew library and RuleSet.
    There is no `/gm` on the server until P3 (docs/plans/vtt.md 9.3a).

    The character pages get a BOOK ruleset. Each account merges its library over
    it. See hosting-state-model.md section 5.3.

    ⚠ The wiki gets a SEPARATE book ruleset. The wiki is public. A session that
    reloads its library into a shared object then publishes that homebrew. See
    docs/plans/vtt.md section 9.5.

    ⚠ This does not run a server and does not install the gate. `main` does both.
    """
    root = config.session_root() if session_root is None else session_root
    database = config.db_path() if db_path is None else db_path
    db.init_db(database)
    book = rules_db.load_ruleset(_DATA_DIR)
    auth.register_auth_pages(database)
    public.register_public_pages()
    wiki.register_wiki(rules_db.load_ruleset(_DATA_DIR))
    store = characters.CharacterStore(db_path=database, root=root)
    # ⚠ ONE store for the process. It holds the join throttle, and a second store
    # has a second count.
    table_store = tables.TableStore(db_path=database, root=root)
    nav.set_campaign_source(lambda: _campaign_links(table_store))
    sessions = home.register_character_pages(
        store, book, auth.current_user_id, rules_db.load_adversary_catalog(_DATA_DIR),
        table_store)
    # The table view writes YOU PLAY through the character registry.
    table_view.register_table_page(table_store, store, book, sessions,
                                   auth.current_user_id, table_log.TableLog(table_store))
    return sessions


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

    # Each account has its own homebrew library, and there is no library of the
    # process. A call that gives no folder then raises. Section 5.3.
    custom_content.require_explicit_dir(True)

    # ⚠ `reload=False`. A reload makes a second process, and the registry holds
    # live objects that cannot cross one. See the module docstring.
    ui.run(title="Exalted 1e — Table", host=args.host, port=args.port,
           reload=False, show=False, storage_secret=secret,
           session_middleware_kwargs=SESSION_COOKIE)


if __name__ in {"__main__", "__mp_main__"}:
    main()
