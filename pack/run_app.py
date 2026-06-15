"""
pack/run_app.py — entry point for the packaged desktop build.

Double-clicking the built executable runs this: it starts the local NiceGUI
server and opens the user's default browser to the app. No arguments, no
terminal. Cytoscape is vendored locally, so it works fully offline.

Closing the last browser tab quits the server, so re-launching the executable
always opens a fresh app rather than orphaning a server on the port.
"""

import asyncio
import multiprocessing

# Must run before anything spawns a process, or PyInstaller's frozen child
# re-executes this script (causing duplicate servers / import errors).
multiprocessing.freeze_support()

from nicegui import app, ui  # noqa: E402

from exalted_builder.ui import builder  # noqa: E402

# Must exceed NiceGUI's reconnect_timeout (default 3s): a page refresh disconnects
# then reconnects within that window, and must NOT be mistaken for the tab closing.
_RECONNECT_GRACE = 4.0


async def _quit_if_no_tabs() -> None:
    """Fired on every browser disconnect; quits the server once the reconnect window
    passes with no tab still connected (so a refresh survives, a closed tab doesn't)."""
    await asyncio.sleep(_RECONNECT_GRACE)
    if not builder.any_tab_connected():
        app.shutdown()


def run() -> None:
    ruleset, character, path = builder.load(None)

    @ui.page("/")
    def index() -> None:
        builder.build_app(ruleset, character, path)

    app.on_disconnect(_quit_if_no_tabs)

    # show=True opens the default browser; reload=False is required when frozen
    # (and is also what makes app.shutdown() able to stop the server).
    ui.run(title="Exalted 1e — Solar Builder", reload=False, show=True, port=8080)


# Guard covers PyInstaller's multiprocessing re-import (__mp_main__).
if __name__ in {"__main__", "__mp_main__"}:
    run()
