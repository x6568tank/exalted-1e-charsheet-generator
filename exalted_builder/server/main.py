"""server/main.py — the hosted entry point.

Section 5.1 of `docs/plans/hosting-state-model.md`. This module is the caller that
turns on the per-session state of section 3. The desktop entry points
(`ui/builder.py:main` and `pack/run_app.py`) stay as they are, and they supply no
session root.

**What this module adds over the desktop entry points, and it is one argument.**
`register_pages(ruleset, ctx, session_root=...)` gives each browser session its own
save directory and its own auto-save timer. All three desktop callers pass no root.
Thus section 3 was complete and unreachable until this file.

⚠ This module has NO authentication. It is piece 1 of section 5; the login gate and
the database are piece 3 and piece 4. Thus `DEFAULT_HOST` is loopback, and a
non-loopback bind needs `--public`. See `check_bind_is_allowed`.

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

from .. import rules_db
from ..models.character import Character, new_character_id
from ..server import config
from ..server.session import SessionRegistry
from ..ui import builder

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# ⚠ Loopback, not 0.0.0.0. Section 5.1 sketches a public bind, and it assumes the
# auth gate of section 5 that this file does not have.
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080

# The hosts that need no acknowledgement. A name that resolves to the loopback
# interface reaches no other machine.
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


def check_bind_is_allowed(host: str, *, acknowledged: bool) -> None:
    """Raise `RuntimeError` if `host` reaches other machines and `acknowledged` is
    false. Return None in all other cases.

    ⚠ This is a mechanism, not a warning, because there is no authentication yet.
    An un-gated hostname gives whoever finds it the character, the homebrew library
    and the Storyteller screen. `docs/plans/hosting-per-instance.md` records that
    cost. Delete this function when the auth gate of section 5 lands, not before.
    """
    if host in _LOOPBACK_HOSTS or acknowledged:
        return
    raise RuntimeError(
        f"Refusing to bind {host}: this server has no authentication yet. Anyone "
        "who reaches the port gets every character, the homebrew library and the "
        "Storyteller page. Bind 127.0.0.1, or pass --public to accept that.")


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


def build_server(session_root: Path | None = None) -> SessionRegistry:
    """Register the hosted routes and return the registry of session contexts.

    Read the session root from `EXALTED_SESSION_ROOT` if the caller gives none.
    That call raises when the variable is absent; there is no default, because one
    shared directory is the defect that section 3.7 removes.

    ⚠ This does not run a server. `main` does that. The split exists so a test can
    assert on the wiring, which is the only thing this file adds.
    """
    root = config.session_root() if session_root is None else session_root
    ruleset = rules_db.load_app_ruleset(_DATA_DIR)
    return builder.register_pages(ruleset, prototype_context(root), session_root=root)


def main() -> None:
    parser = argparse.ArgumentParser(description="Exalted 1e builder — hosted server")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--public", action="store_true",
                        help="accept that this server has no authentication")
    args = parser.parse_args()

    check_bind_is_allowed(args.host, acknowledged=args.public)

    # Read both settings before the server starts. Each raises when it is absent,
    # thus a misconfigured deployment fails at the start and not at the first
    # request.
    secret = config.required_storage_secret()
    root = config.session_root()
    root.mkdir(parents=True, exist_ok=True)

    build_server(session_root=root)

    # ⚠ `reload=False`. A reload makes a second process, and the registry holds
    # live objects that cannot cross one. See the module docstring.
    ui.run(title="Exalted 1e — Table", host=args.host, port=args.port,
           reload=False, show=False, storage_secret=secret)


if __name__ in {"__main__", "__mp_main__"}:
    main()
