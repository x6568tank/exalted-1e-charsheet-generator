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

# pywebview backs the native window. collect_all grabs its platform backends
# (gtk/qt/cocoa/winforms/edgechromium) and data; the per-OS GUI backend itself
# (WebKit2GTK or Qt on Linux, the Edge WebView2 runtime on Windows) must be present
# on the build/target machine — see pack/BUILD.md.
wv_datas, wv_binaries, wv_hidden = collect_all("webview")

datas = ng_datas + wv_datas + [
    (str(ROOT / "exalted_builder" / "data"), "exalted_builder/data"),
    (str(ROOT / "exalted_builder" / "ui" / "vendor"), "exalted_builder/ui/vendor"),
    (str(ROOT / "examples"), "examples"),
]

a = Analysis(
    [str(ROOT / "pack" / "run_app.py")],
    pathex=[str(ROOT)],
    binaries=ng_binaries + wv_binaries,
    datas=datas,
    hiddenimports=ng_hidden + wv_hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
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
