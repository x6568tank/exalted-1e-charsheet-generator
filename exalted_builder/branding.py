"""Locating the app's icon, for both shells and both packaged builds.

`assets/` sits at the repo root, outside the package, so neither the normal
`exalted_builder/data` lookup nor `persistence.default_save_dir` finds it.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ASSETS = "assets"
_ICON = "icon.png"


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
