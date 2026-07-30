# Building the desktop app

The Exalted 1e Character Builder can be packaged into a **single double-click
executable** that bundles Python, the app, all rules data, and a local copy of
Cytoscape — so it runs with no Python install and **no internet**. On launch it
starts a local server and opens the user's browser to the app.

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

## Quickest path: the build scripts

The repo root has one script per platform. Each creates `.venv`, installs the app
with its build extras, and runs PyInstaller — a fresh clone to a finished binary
in one command:

```
./linux.sh        # Linux/macOS
windows.bat       # Windows
```

They are line-for-line equivalents; keep them in step when either changes. The
manual steps below are the same thing spelled out, for when a build misbehaves.

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
On a Windows machine with Python installed, run `windows.bat` from the repo root —
or, by hand, from a terminal there:
```
py -m venv .venv
.venv\Scripts\python -m pip install -e ".[ui,desktop]"
.venv\Scripts\pyinstaller pack\exalted-builder.spec
```
Ship `dist\ExaltedBuilder.exe`.

## Notes
- The spec builds **windowed** (`console=False`), so the running app has no console
  and `sys.stdout`/`sys.stderr` are `None`. `run_app.py` redirects those to `os.devnull`
  at startup — without it, uvicorn's log formatter calls `sys.stdout.isatty()` and the
  app crashes with "Unable to configure formatter 'default'" before the server starts
  (most visibly on the Windows `.exe`, which never has a console). Keep that guard.
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
