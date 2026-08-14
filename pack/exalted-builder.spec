# PyInstaller spec for the Exalted 1e Solar Builder desktop app.
# Build (from the repo root, after `pip install -e ".[ui,desktop]"`):
#     pyinstaller pack/exalted-builder.spec
# Produces a single-file executable in dist/ for the OS you build on.
# Cross-compiling is NOT supported: build the Windows .exe on Windows, etc.

from pathlib import Path

from PyInstaller.utils.hooks import collect_all

# repo root (the spec lives in pack/)
ROOT = Path(SPECPATH).parent

# Pull in NiceGUI's web assets, binaries, and submodules.
ng_datas, ng_binaries, ng_hidden = collect_all("nicegui")

# reportlab (ui/pdf.py, the printable character sheet) ships DATA it loads at
# runtime -- the base-14 AFM font metrics under reportlab/fonts, plus its
# rl_settings. A plain import scan finds the modules but not those files, and the
# failure only shows up when someone clicks Print in the packaged app, which is
# exactly the sort of thing nobody exercises before shipping. collect_all also
# picks up the optional _rl_accel C extension when it is installed.
rl_datas, rl_binaries, rl_hidden = collect_all("reportlab")

datas = ng_datas + rl_datas + [
    (str(ROOT / "exalted_builder" / "data"), "exalted_builder/data"),
    (str(ROOT / "exalted_builder" / "ui" / "vendor"), "exalted_builder/ui/vendor"),
    (str(ROOT / "examples"), "examples"),
]

a = Analysis(
    [str(ROOT / "pack" / "run_app.py")],
    pathex=[str(ROOT)],
    binaries=ng_binaries + rl_binaries,
    datas=datas,
    hiddenimports=ng_hidden + rl_hidden,
    hookspath=[],
    runtime_hooks=[],
    # The app runs in the browser; keep the native (pywebview/Qt) stack out of the
    # bundle even if it happens to be installed, so the build stays small/portable.
    excludes=["webview", "qtpy", "PyQt6", "PyQt5", "PySide6", "PySide2",
              # CPython's readline module drags libreadline/libtinfo into the
              # bundle; see the binary filter below for why that breaks the host.
              "readline", "rlcompleter"],
    noarchive=False,
)

# The bootloader points LD_LIBRARY_PATH at the onefile extraction dir, and every
# CHILD process inherits it -- including /bin/sh, which the browser-open path
# shells out through. A bundled libreadline built on the CI runner (Ubuntu,
# readline 8.1) then gets loaded by the host's own bash (Arch, expects 8.2),
# which dies with "undefined symbol: rl_trim_arg_from_keyseq". Nothing in a
# browser-based GUI app needs readline or a terminfo database, so drop them.
_HOST_LIBS = ("libreadline.so", "libtinfo.so", "libncurses.so", "libncursesw.so")
a.binaries = [b for b in a.binaries
              if not b[0].split("/")[-1].startswith(_HOST_LIBS)]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="ExaltedBuilder",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    runtime_tmpdir=None,
    console=False,        # no terminal window; the app opens a browser
)
# Passing a.binaries and a.datas into EXE above (with no COLLECT step) produces a
# single-file executable in dist/.
