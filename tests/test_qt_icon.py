"""The native app's window icon.

⚠ Skips whole without the optional `qt` extra, like every other tests/test_qt_*.py.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtGui import QIcon                      # noqa: E402
from PySide6.QtWidgets import QMainWindow            # noqa: E402

from exalted_builder import branding                 # noqa: E402


def test_titlebar_renders_are_square(qapp) -> None:
    """⚠ THE BUG THIS GUARDS: the master icon.png is 500x502, and Qt preserves aspect
    ratio, so a QIcon built from it alone answers pixmap(16,16) with a 15x16 image
    that sits skewed in a square titlebar slot. Only the pre-rendered square sizes
    give a square render — asserting the icon merely loads does NOT catch this."""
    icon = QIcon()
    for path in branding.app_icon_sizes():
        icon.addFile(str(path))
    assert icon.availableSizes(), "no pre-rendered sizes found"
    for n in (16, 24, 32, 48):
        pm = icon.pixmap(n, n)
        assert pm.width() == pm.height() == n, f"pixmap({n}) is {pm.width()}x{pm.height()}"


def test_small_sizes_are_pre_rendered_not_downscaled_from_the_master(qapp) -> None:
    """A titlebar asks for ~16-24px. Without renderings at that end, Qt crushes 500px
    in one step; the sizes below are what stops it."""
    have = {int(p.stem.split("-")[1]) for p in branding.app_icon_sizes()}
    assert {16, 24, 32} <= have, f"missing small renderings, have {sorted(have)}"


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
