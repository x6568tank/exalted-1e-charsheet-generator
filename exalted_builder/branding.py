"""Locating the app's icon, for both shells and both packaged builds.

`assets/` sits at the repo root, outside the package, so neither the normal
`exalted_builder/data` lookup nor `persistence.default_save_dir` finds it.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ASSETS = "assets"
_ICON = "icon.png"
_ICON_DIR = "icons"

APP_ID = "exalted-builder"                 # also the Wayland app_id and the icon name
APP_NAME = "Exalted 1e Character Builder"
ORG_NAME = "Exalted 1e"


def assets_dir() -> Path:
    """Return the directory holding the UI assets.

    Frozen, that is PyInstaller's extraction dir (`sys._MEIPASS`), where both spec
    files place `assets/`; from a source checkout it is `<repo root>/assets`, one
    level above this package.
    """
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / _ASSETS
    return Path(__file__).resolve().parent.parent / _ASSETS


def app_icon_path() -> Path | None:
    """Return the app icon's path, or None when the file is not there.

    ⚠ Every caller must tolerate None. The icon is cosmetic, and a build that
    shipped without it — or a checkout where it was never added — must still start.
    """
    icon = assets_dir() / _ICON
    return icon if icon.is_file() else None


def app_icon_sizes() -> list[Path]:
    """Return the pre-rendered square icon renderings, smallest first; [] if absent.

    ⚠ The master `icon.png` is 500x502. Qt keeps aspect ratio, so a QIcon built from
    it alone answers `pixmap(16,16)` with a FIFTEEN-by-sixteen image that then sits
    off-centre in a square titlebar slot. These renderings are padded square, and
    supplying several also stops Qt downscaling 500px to 16px in one step.
    """
    icons = assets_dir() / _ICON_DIR
    if not icons.is_dir():
        return []
    found = []
    for f in icons.glob("icon-*.png"):
        try:
            found.append((int(f.stem.split("-")[1]), f))
        except (IndexError, ValueError):     # not one of ours; ignore rather than crash
            continue
    return [f for _, f in sorted(found)]


def _xdg_data_home() -> Path | None:
    """`$XDG_DATA_HOME`, else `~/.local/share`; None when neither resolves."""
    import os
    raw = os.environ.get("XDG_DATA_HOME")
    if raw:
        return Path(raw)
    home = os.environ.get("HOME")
    return Path(home) / ".local" / "share" if home else None


def install_desktop_entry(exec_command: str | None = None) -> Path | None:
    """Install a .desktop entry and its icons under XDG data home; return its path.

    Copies each rendering to `icons/hicolor/<n>x<n>/apps/<APP_ID>.png` and writes
    `applications/<APP_ID>.desktop` pointing `Icon=` at that NAME. Returns None on
    a non-Linux platform, when no data dir resolves, or on any failure.

    ⚠ The icons must be COPIED out, not referenced where they sit. A one-file
    PyInstaller build unpacks to a temp dir that is deleted on exit, so an `Icon=`
    pointing into it resolves to nothing the moment the app closes.

    ⚠ Every failure is swallowed. This runs at startup for a cosmetic gain; a
    read-only or unusual home must cost the desktop entry and never the app.
    """
    import shutil
    import sys
    if not sys.platform.startswith("linux"):
        return None
    data = _xdg_data_home()
    if data is None:
        return None
    try:
        for icon in app_icon_sizes():
            n = int(icon.stem.split("-")[1])
            dest = data / "icons" / "hicolor" / f"{n}x{n}" / "apps"
            dest.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(icon, dest / f"{APP_ID}.png")

        if exec_command is None:
            exec_command = (f'"{sys.executable}"' if getattr(sys, "frozen", False)
                            else f'"{sys.executable}" -m exalted_builder.qt')
        entry = ("[Desktop Entry]\n"
                 "Type=Application\n"
                 f"Name={APP_NAME}\n"
                 "Comment=Character creator and validator for Exalted First Edition\n"
                 f"Exec={exec_command} %f\n"
                 f"Icon={APP_ID}\n"
                 "Terminal=false\n"
                 "Categories=Game;RolePlaying;\n"
                 "MimeType=application/json;\n"
                 f"StartupWMClass={APP_ID}\n")
        apps = data / "applications"
        apps.mkdir(parents=True, exist_ok=True)
        target = apps / f"{APP_ID}.desktop"
        # Idempotent: an unchanged entry is not rewritten, so a read-only rerun is free.
        if not target.is_file() or target.read_text() != entry:
            target.write_text(entry)
        return target
    except OSError:
        return None
