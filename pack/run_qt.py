"""
pack/run_qt.py — entry point for the packaged NATIVE (PySide6/Qt) build.

Double-clicking the built executable runs this: it loads the ruleset, opens the
native builder window, and hands over to the Qt event loop. An optional path
argument opens that character, exactly as `python -m exalted_builder.qt` does.

The sibling `run_app.py` packages the NiceGUI webapp, which starts a local server
and opens a browser. This one has no server and no browser: it is the desktop app
of decision 0018. The two guards below are the same in both, and for the same
reasons — see the comments; both were paid for once already.
"""

import os
import sys

# In a windowed (console=False) PyInstaller build there is no console, so
# sys.stdout / sys.stderr are None. Any library that touches them — or any stray
# print() — then raises AttributeError somewhere unhelpful, before or during
# startup. Give them real sinks first, ahead of every other import.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

# PyInstaller's bootloader points LD_LIBRARY_PATH at the onefile extraction dir and
# stashes the caller's original in LD_LIBRARY_PATH_ORIG. Child processes inherit the
# former, so anything we shell out to — xdg-open from a QDesktopServices link, a file
# manager, /bin/sh — tries to load OUR bundled copies of the system libraries and dies
# on a version mismatch against the host. Restore the original for children.
#
# Safe for us: glibc reads LD_LIBRARY_PATH once at process start, so editing
# os.environ affects only processes we spawn, never this one's own loading.
if getattr(sys, "frozen", False):
    _orig = os.environ.pop("LD_LIBRARY_PATH_ORIG", None)
    if _orig is not None:
        os.environ["LD_LIBRARY_PATH"] = _orig
    else:
        os.environ.pop("LD_LIBRARY_PATH", None)

from exalted_builder.qt.__main__ import main

if __name__ == "__main__":
    main()
