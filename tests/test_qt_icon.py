"""The native app's window icon.

⚠ Skips whole without the optional `qt` extra, like every other tests/test_qt_*.py.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtGui import QIcon                      # noqa: E402
from PySide6.QtWidgets import QMainWindow            # noqa: E402

from exalted_builder import branding                 # noqa: E402


def test_the_icon_file_actually_loads_into_qt(qapp) -> None:
    """⚠ QIcon accepts an unreadable path SILENTLY and yields an empty icon — it does
    not raise. `isNull` and a real pixmap are the only proof the file was read, so a
    test that merely constructs the QIcon passes against a missing file."""
    icon = QIcon(str(branding.app_icon_path()))
    assert not icon.isNull()
    assert icon.availableSizes()
    assert not icon.pixmap(32, 32).isNull()


def test_setting_it_on_the_application_reaches_every_window(qapp) -> None:
    """⚠ It is set once on the QApplication, not per window, so that the party/ST
    window — a SECOND QMainWindow, built nowhere near the entry point — gets it
    without its own wiring. Guards that inheritance, not the entry point's one call."""
    qapp.setWindowIcon(QIcon(str(branding.app_icon_path())))
    assert not QMainWindow().windowIcon().isNull()


def test_no_window_sets_an_icon_of_its_own(qapp) -> None:
    """A per-window setWindowIcon would silently shadow the application's for that
    window only — the exact shape that leaves one window looking unbranded."""
    from pathlib import Path
    qt_dir = Path(branding.__file__).resolve().parent / "qt"
    offenders = [p.name for p in qt_dir.rglob("*.py")
                 if p.name != "__main__.py" and "setWindowIcon" in p.read_text()]
    assert not offenders, f"these set their own window icon: {offenders}"
