"""
pack/run_app.py — entry point for the packaged desktop build.

Double-clicking the built executable runs this: it starts the local NiceGUI
server and opens it in a real native desktop window (via pywebview), so Save/Load
use the OS file dialogs. No arguments, no terminal. Cytoscape is vendored locally,
so it works fully offline.
"""

import multiprocessing

# Must run before anything spawns a process, or PyInstaller's frozen child
# re-executes this script (causing duplicate servers / import errors).
multiprocessing.freeze_support()

from nicegui import ui  # noqa: E402

from exalted_builder.ui import builder  # noqa: E402


def run() -> None:
    ruleset, character, path = builder.load(None)

    @ui.page("/")
    def index() -> None:
        builder.build_app(ruleset, character, path)

    # native=True opens a real desktop window (pywebview) instead of the browser, so
    # the OS Save As/Open dialogs are available; reload=False is required when frozen.
    ui.run(title="Exalted 1e — Solar Builder", reload=False,
           native=True, window_size=(1280, 900))


# Guard covers PyInstaller's multiprocessing re-import (__mp_main__).
if __name__ in {"__main__", "__mp_main__"}:
    run()
