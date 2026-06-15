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

datas = ng_datas + [
    (str(ROOT / "exalted_builder" / "data"), "exalted_builder/data"),
    (str(ROOT / "exalted_builder" / "ui" / "vendor"), "exalted_builder/ui/vendor"),
    (str(ROOT / "examples"), "examples"),
]

a = Analysis(
    [str(ROOT / "pack" / "run_app.py")],
    pathex=[str(ROOT)],
    binaries=ng_binaries,
    datas=datas,
    hiddenimports=ng_hidden,
    hookspath=[],
    runtime_hooks=[],
    # The app runs in the browser; keep the native (pywebview/Qt) stack out of the
    # bundle even if it happens to be installed, so the build stays small/portable.
    excludes=["webview", "qtpy", "PyQt6", "PyQt5", "PySide6", "PySide2"],
    noarchive=False,
)
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
