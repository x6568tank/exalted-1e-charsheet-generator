# PyInstaller spec for the NATIVE (PySide6/Qt) desktop app — decision 0018.
# Build (from the repo root, after `pip install -e ".[qt,desktop]"`):
#     pyinstaller pack/exalted-builder-qt.spec
# Produces a single-file executable in dist/ for the OS you build on.
# Cross-compiling is NOT supported: build the Windows .exe on Windows, etc.
#
# The sibling `exalted-builder.spec` packages the NiceGUI WEBAPP and deliberately
# EXCLUDES PySide6. This one is its mirror image: Qt in, nicegui out. Two products
# from one tree; keep the shared guards (readline, run_*.py) in step.

from pathlib import Path

from PyInstaller.utils.hooks import collect_all

# repo root (the spec lives in pack/)
ROOT = Path(SPECPATH).parent

# reportlab is NOT optional here: the Qt app's Print and the party window's
# "Print all" both go through ui/pdf.py. It ships DATA it loads at runtime (the
# base-14 AFM font metrics under reportlab/fonts, plus rl_settings) that a plain
# import scan does not find — and the failure only shows when someone clicks
# Print in the packaged app.
rl_datas, rl_binaries, rl_hidden = collect_all("reportlab")

datas = rl_datas + [
    (str(ROOT / "exalted_builder" / "data"), "exalted_builder/data"),
    # The window/tab icon, read at runtime via branding.app_icon_path().
    (str(ROOT / "assets" / "icon.png"), "assets"),
    (str(ROOT / "assets" / "icons"), "assets/icons"),
]

# ⚠ The app imports exactly THREE Qt modules (QtCore, QtGui, QtWidgets — grep it).
# PySide6 installs at ~650 MB, and PyInstaller's hook will happily bundle the lot,
# so everything else is excluded by name. The list is long because it is a
# subtraction, not a selection: a module absent from here IS in the binary.
_PYSIDE_UNUSED = [
    "PySide6.Qt3DAnimation", "PySide6.Qt3DCore", "PySide6.Qt3DExtras",
    "PySide6.Qt3DInput", "PySide6.Qt3DLogic", "PySide6.Qt3DRender",
    "PySide6.QtBluetooth", "PySide6.QtCharts", "PySide6.QtConcurrent",
    "PySide6.QtDataVisualization", "PySide6.QtDesigner", "PySide6.QtHelp",
    "PySide6.QtHttpServer", "PySide6.QtLocation", "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets", "PySide6.QtNfc", "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets", "PySide6.QtPdf", "PySide6.QtPdfWidgets",
    "PySide6.QtPositioning", "PySide6.QtQml", "PySide6.QtQuick",
    "PySide6.QtQuick3D", "PySide6.QtQuickControls2", "PySide6.QtQuickWidgets",
    "PySide6.QtRemoteObjects", "PySide6.QtScxml", "PySide6.QtSensors",
    "PySide6.QtSerialBus", "PySide6.QtSerialPort", "PySide6.QtSpatialAudio",
    "PySide6.QtSql", "PySide6.QtStateMachine", "PySide6.QtSvg",
    "PySide6.QtSvgWidgets", "PySide6.QtTest", "PySide6.QtTextToSpeech",
    "PySide6.QtUiTools", "PySide6.QtWebChannel", "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineQuick", "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebSockets", "PySide6.QtXml",
]

a = Analysis(
    [str(ROOT / "pack" / "run_qt.py")],
    pathex=[str(ROOT)],
    binaries=rl_binaries,
    datas=datas,
    hiddenimports=rl_hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        # The other product. A native build has no server and no browser in it.
        "nicegui", "uvicorn", "fastapi", "starlette", "webview",
        # Rival bindings, in case one is installed in the build environment.
        "PyQt5", "PyQt6", "PySide2", "qtpy",
        # The dev/test toolchain.
        "pytest", "pytestqt", "IPython",
        # ⚠ CPython's readline module drags libreadline/libtinfo into the bundle,
        # which a CHILD process then loads against the wrong host version and dies
        # ("undefined symbol: rl_trim_arg_from_keyseq"). Nothing in a GUI app needs
        # readline or a terminfo database. Same filter as the webapp spec, and the
        # binary sweep below is its belt-and-braces half.
        "readline", "rlcompleter",
    ] + _PYSIDE_UNUSED,
    noarchive=False,
)

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
    name="ExaltedBuilderQt",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # ⚠ UPX OFF, unlike the webapp spec. Compressed Qt shared libraries are a known
    # source of "works here, segfaults there" — the saving is not worth debugging a
    # crash that only reproduces on someone else's machine.
    upx=False,
    runtime_tmpdir=None,
    console=False,        # no terminal window; this is a native GUI app
    # ⚠ The EXECUTABLE's own icon, which is NOT the same thing as the window
    # icon set in code — this one is baked into the binary by the OS shell and
    # needs .ico. Windows and macOS use it; Linux ignores it entirely.
    icon=str(ROOT / "assets" / "icon.ico"),
)
# Passing a.binaries and a.datas into EXE (with no COLLECT step) produces a
# single-file executable in dist/.
