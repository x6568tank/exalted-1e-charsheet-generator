# Building the desktop app

The Exalted 1e Solar Builder can be packaged into a **single double-click
executable** that bundles Python, the app, all rules data, and a local copy of
Cytoscape — so it runs with no Python install and **no internet**. On launch it
starts a local server and opens the user's browser to the app.

## Important: no cross-compiling
PyInstaller builds for the OS it runs **on**. To produce:
- a **Linux** binary → build on Linux,
- a **Windows** `.exe` → build on Windows,
- a **macOS** app → build on macOS.

There is no way to build a Windows `.exe` from Linux (or vice versa). Use a
Windows machine (or a Windows CI runner / VM) for the Windows build.

Note also that a Linux PyInstaller binary is **not reliably portable between Linux
distributions** (glibc and system-library differences). For broad Linux sharing,
build on the **oldest** distro you need to support.

## Build steps (same on every OS)

1. Get the repo and a Python 3.11+ environment.
2. Install the app plus the build tools:
   ```
   python -m pip install -e ".[ui,desktop]"
   ```
3. Build from the **repo root**:
   ```
   pyinstaller pack/exalted-builder.spec
   ```
4. The executable is in `dist/`:
   - Linux: `dist/ExaltedBuilder`
   - Windows: `dist/ExaltedBuilder.exe`
   - macOS: `dist/ExaltedBuilder`

Double-click it (or run it) — it opens the builder in the default browser.
Distribute that single file; recipients need nothing else installed.

## Windows quick recipe
On a Windows machine with Python installed, from a terminal in the repo root:
```
py -m venv .venv
.venv\Scripts\python -m pip install -e ".[ui,desktop]"
.venv\Scripts\pyinstaller pack\exalted-builder.spec
```
Ship `dist\ExaltedBuilder.exe`.

## Notes
- First launch may take a few seconds (the one-file build unpacks to a temp dir).
- The build is ~60 MB because it embeds a Python runtime; that is normal and
  expected for a PyInstaller one-file app. Don't commit `dist/` or `build/`.
- The app opens in the browser for maximum portability and the fewest GUI
  dependencies. Save/Load therefore use a file-upload picker (Load) and a download
  (Save) rather than native OS dialogs.
- A native-window mode exists in source (`python -m exalted_builder.ui.builder
  --native`, needs pywebview + a Qt/GTK backend) but is **not** used by the packaged
  build — it was dropped for packaging because bundling Qt made the binary large and
  non-portable across Linux distros.
