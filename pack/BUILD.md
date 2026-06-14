# Building the desktop app

The Exalted 1e Solar Builder packages into a **single double-click executable**
that bundles Python, the app, all rules data, and a local copy of Cytoscape — so it
runs with no Python install and **no internet**. On launch it opens a **real native
desktop window** (via pywebview), so Save and Load use the OS file dialogs.

## The native window needs a web backend
pywebview draws the window with the platform's web view. That backend is **not**
bundled by pip and differs per OS:

| OS      | Backend pywebview uses                | How to provide it |
|---------|---------------------------------------|-------------------|
| Windows | **Edge WebView2** (Chromium)          | Built into Windows 10/11 — nothing to install. |
| Linux   | **WebKit2GTK** or **Qt WebEngine**    | A system package (see below). |
| macOS   | **WKWebView** (Cocoa)                 | Built into macOS — nothing to install. |

So on **Windows and macOS the native build is self-contained**; only **Linux**
needs a backend present on the build/run machine.

## Important: no cross-compiling
PyInstaller builds for the OS it runs **on**:
- a **Windows** `.exe` → build on Windows,
- a **Linux** binary → build on Linux,
- a **macOS** app → build on macOS.

There is no way to build a Windows `.exe` from Linux (or vice versa). Use a Windows
machine (or a Windows CI runner / VM) for the Windows build.

## Build steps (same on every OS)

1. Get the repo and a Python 3.11+ environment.
2. Install the app plus the build tools (this now pulls in **pywebview**):
   ```
   python -m pip install -e ".[ui,desktop]"
   ```
   On **Linux only**, also install a web backend (pick one):
   ```
   # Qt (fully pip-installable, self-contained in the venv). The `native-qt` extra
   # bundles all three pieces pywebview's Qt backend needs (pyqt6, pyqt6-webengine,
   # and qtpy — pywebview imports qtpy, and omitting it makes the window fail to open):
   python -m pip install -e ".[ui,desktop,native-qt]"
   # OR GTK (lightest on a GTK desktop) — system packages, e.g. Arch:
   sudo pacman -S python-gobject webkit2gtk-4.1
   #   …then create the venv with --system-site-packages so it sees `gi`.
   ```
3. Build from the **repo root**:
   ```
   pyinstaller pack/exalted-builder.spec
   ```
4. The executable is in `dist/`:
   - Windows: `dist/ExaltedBuilder.exe`
   - Linux: `dist/ExaltedBuilder`
   - macOS: `dist/ExaltedBuilder`

Double-click it — it opens the builder in a native window. Distribute that single
file; recipients need nothing else installed (on Windows/macOS; a Linux recipient
needs the matching system WebKit/Qt, which is normally already present).

## Windows quick recipe
On a Windows machine with Python installed, from a terminal in the repo root:
```
py -m venv .venv
.venv\Scripts\python -m pip install -e ".[ui,desktop]"
.venv\Scripts\pyinstaller pack\exalted-builder.spec
```
Ship `dist\ExaltedBuilder.exe`. The recipient just double-clicks it; the Edge
WebView2 runtime is already part of Windows 10/11.

## Running native from source (no packaging) — for testing
```
python -m exalted_builder.ui.builder --native
```
Same backend rule as above: Windows/macOS work out of the box; on Linux install the
backend first (see step 2 — easiest is `pip install -e ".[ui,desktop,native-qt]"`).
Without `--native` the app still opens in the browser and uses the upload/download
Save/Load fallback.

If `--native` doesn't open a real window (you get a **browser tab**, or it exits
asking you to "pip install pywebview"), the Linux web stack is incomplete. The full
set is **pywebview + pyqt6 + pyqt6-webengine + qtpy** — exactly what
`.[desktop,native-qt]` installs. (qtpy is the one most easily missed: pywebview's Qt
backend imports it, and without it the window silently fails to load.)

## Notes
- First launch of the one-file build may take a few seconds (it unpacks to a temp
  dir).
- The build is large (~100+ MB) because it embeds a Python runtime and the web
  assets; that is normal for a PyInstaller one-file app. Don't commit `dist/` or
  `build/`.
- If the native window fails to open with "You must have either QT or GTK…", the
  Linux backend is missing — install one as in step 2.
