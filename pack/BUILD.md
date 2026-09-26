# Building the desktop app

**One product builds from this tree**: the native PySide6 app (decision 0018), a single
double-click executable that bundles Python, the app and all the rules data, and runs
with no Python install and **no internet**.

| Spec | Entry point | Output |
|---|---|---|
| `pack/exalted-builder-qt.spec` | `pack/run_qt.py` | `dist/ExaltedBuilderQt` |

The packaged **webapp** build (`exalted-builder.spec`, `run_app.py`, `linux.sh`,
`windows.bat`) was retired by decision 0021. The browser product is now the hosted
server (`python -m exalted_builder.server.main`), which is not packaged with PyInstaller;
see the README's Self-hosting section. `python -m exalted_builder.ui.builder` still runs
the NiceGUI builder locally, as a development entry point.

## Important: no cross-compiling
PyInstaller builds for the OS it runs **on**. To produce:
- a **Linux** binary → build on Linux,
- a **Windows** `.exe` → build on Windows,
- a **macOS** app → build on macOS.
NOTE: I HAVE NOT TESTED THE macOS BUILD. BUILD AT YOUR OWN RISK, BECAUSE I AIN'T
DOING THAT FOR YOU

There is no way to build a Windows `.exe` from Linux (or vice versa). Use a
Windows machine (or a Windows CI runner / VM) for the Windows build.

Note also that a Linux PyInstaller binary is **not reliably portable between Linux
distributions** (glibc and system-library differences). For broad Linux sharing,
build on the **oldest** distro you need to support.

Or just grab from the release page.

## What a release ships — `.github/workflows/release.yml`

A `v*` tag builds **two** assets and attaches both to that one release
(2 OSes, `fail-fast: false` so no row can discard another's artifact):
`ExaltedBuilderQt-linux-x86_64` and `ExaltedBuilderQt-windows-x86_64.exe`.

⚠ **The extras are PER ROW**, `.[desktop,qt]`. Adding a product means adding a matrix
row — nothing discovers the specs.

⚠ **Until 2026-08-28 the matrix had only the two webapp rows**, months after the native
spec landed. A tag would have published a release that looked complete — two green
assets, no failures — with no native app on it. The build scripts were the
Qt spec's only callers. **A build that is not in the matrix does not exist to a tag.**

⚠ A headless runner builds a GUI app fine: PyInstaller only *collects* the Qt platform
plugins. What needs a display is running the result, on the user's machine.

**Dry-run a change to this workflow with `workflow_dispatch` before tagging** — it
uploads the artifacts and skips the release step, so a broken row cannot leave a
half-populated public release behind.

## Quickest path: the build scripts

The repo root has one script per platform. Each creates `.venv`, installs the app
with its build extras, and runs PyInstaller — a fresh clone to a finished binary
in one command:

```
./linux-qt.sh        # Linux/macOS
windows-qt.bat       # Windows
```

They are line-for-line equivalents; keep them in step when either changes. The
manual steps below are the same thing spelled out, for when a build misbehaves.

## Build steps (same on every OS)

1. Get the repo and a Python 3.11+ environment.
2. Install the app plus the build tools:
   ```
   python -m pip install -e ".[qt,desktop]"
   ```
3. Build from the **repo root**:
   ```
   pyinstaller pack/exalted-builder-qt.spec
   ```
4. The executable is in `dist/` — `ExaltedBuilderQt` (`.exe` on Windows).

Double-click it (or run it) and it opens a native window. Distribute that single file;
recipients need nothing else installed.

## Windows quick recipe
On a Windows machine with Python installed, run `windows-qt.bat` from the repo root —
or, by hand, from a terminal there:
```
py -m venv .venv
.venv\Scripts\python -m pip install -e ".[qt,desktop]"
.venv\Scripts\pyinstaller pack\exalted-builder-qt.spec
```
Ship `dist\ExaltedBuilderQt.exe`.

## Notes
- The spec builds **windowed** (`console=False`), so the running app has no console
  and `sys.stdout`/`sys.stderr` are `None`. `run_qt.py` redirects those to `os.devnull`
  at startup, before any other import. Keep that guard.
- First launch may take a few seconds (the one-file build unpacks to a temp dir).
- Don't commit `dist/` or `build/`.

## Notes on the native (Qt) build

- **92 MB on Linux**, measured 2026-08-27 — the whole Python runtime plus Qt. About
  15 MB of that is the QML/Quick shared libraries, which a collected Qt plugin depends
  on; they are left in rather than risk breaking a plugin to save 15% of an already
  large binary.
- **PySide6 installs at ~650 MB**, so the spec excludes every Qt module by name except
  the three the app imports (QtCore, QtGui, QtWidgets). ⚠ That list is a SUBTRACTION:
  a module absent from `_PYSIDE_UNUSED` is in the binary.
- **UPX is off**: compressed Qt shared libraries are a
  known source of crashes that only reproduce on someone else's machine.
- reportlab is **not optional** in this build — Print and the party window's "Print
  all" both go through `ui/pdf.py`, and `collect_all` is what brings its runtime font
  metrics along. Clicking Print is the only thing that exercises it, so test that on
  any new build.
- The binary takes an optional character path, exactly like `python -m
  exalted_builder.qt`: `./ExaltedBuilderQt ~/dace.character.json`.
- Saves land **next to the executable** (`persistence.default_save_dir` under
  `sys.frozen`), and the homebrew library in a `custom/` folder beside it. Put the
  binary somewhere writable, or set `EXALTED_CUSTOM_DIR`.
