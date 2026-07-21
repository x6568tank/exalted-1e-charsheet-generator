"""
pack/run_app.py — entry point for the packaged desktop build.

Double-clicking the built executable runs this: it starts the local NiceGUI
server (bound to loopback) and opens the user's default browser to the app. No
arguments, no terminal. Cytoscape is vendored locally, so it works fully offline.

Re-launch behaviour:
  * Closing the last browser tab quits the server (see `_quit_if_no_tabs`).
  * If a previous instance is still serving when the executable is run again, this
    just opens the browser to it instead of failing on the busy port — so a
    double-click always lands on a working app, whether or not the old one closed.
"""

import os
import sys

# In a windowed (console=False) PyInstaller build there is no console, so
# sys.stdout / sys.stderr are None. uvicorn's log formatter calls
# sys.stdout.isatty() while configuring logging, which then fails with
# "'NoneType' object has no attribute 'isatty'" -> "Unable to configure formatter
# 'default'", crashing before the server starts (seen on the Windows .exe; a
# double-clicked Linux binary has the same gap). Give them real sinks first. This
# MUST run before nicegui/uvicorn are imported below.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

import asyncio
import multiprocessing
import socket
import webbrowser

# Must run before anything spawns a process, or PyInstaller's frozen child
# re-executes this script (causing duplicate servers / import errors).
multiprocessing.freeze_support()

from nicegui import app, ui  # noqa: E402

from exalted_builder.ui import builder  # noqa: E402

# Loopback only: a desktop app should not be reachable from the LAN, and the
# 127.0.0.1 literal is also less likely than "localhost" to be force-upgraded to
# https by a browser's HTTPS-Only mode (which breaks this plain-http server).
_HOST = "127.0.0.1"
_PORT = 8080
_URL = f"http://{_HOST}:{_PORT}"

# Must exceed NiceGUI's reconnect_timeout (default 3s): a page refresh disconnects
# then reconnects within that window, and must NOT be mistaken for the tab closing.
_RECONNECT_GRACE = 4.0


def _already_serving() -> bool:
    """True if something is already listening on the app's port — almost certainly a
    previous instance of this app still running."""
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex((_HOST, _PORT)) == 0


async def _quit_if_no_tabs() -> None:
    """Fired on every browser disconnect; quits the server once the reconnect window
    passes with no tab still connected (so a refresh survives, a closed tab doesn't)."""
    await asyncio.sleep(_RECONNECT_GRACE)
    if not builder.any_tab_connected():
        app.shutdown()


def run() -> None:
    # If a previous instance is already up, don't try to bind the port (which would
    # crash); just open the browser to the running app and exit.
    if _already_serving():
        webbrowser.open(_URL)
        return

    ruleset, character, path = builder.load(None)
    # Registers both '/' (the builder) and '/gm' (the party page) over one context.
    builder.register_pages(ruleset, builder.make_context(character, path))

    app.on_disconnect(_quit_if_no_tabs)

    # show=True opens the default browser; reload=False is required when frozen
    # (and is also what makes app.shutdown() able to stop the server).
    ui.run(title="Exalted 1e — Solar Builder", reload=False, show=True,
           host=_HOST, port=_PORT)


# Guard covers PyInstaller's multiprocessing re-import (__mp_main__).
if __name__ in {"__main__", "__mp_main__"}:
    run()
