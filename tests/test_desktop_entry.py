"""The Linux .desktop entry that gives Wayland compositors an icon to find."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from exalted_builder import branding


@pytest.fixture()
def xdg(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setattr(sys, "platform", "linux")
    return tmp_path


def test_it_writes_an_entry_and_copies_the_icons(xdg: Path) -> None:
    """⚠ The icons must be COPIED, not referenced in place: a one-file PyInstaller
    build unpacks to a temp dir that is gone once the app exits, so an Icon= pointing
    there resolves to nothing exactly when the launcher needs it."""
    target = branding.install_desktop_entry("/opt/app/ExaltedBuilderQt")
    assert target == xdg / "applications" / f"{branding.APP_ID}.desktop"
    text = target.read_text()
    assert f"Icon={branding.APP_ID}\n" in text          # a NAME, not a path
    assert "/opt/app/ExaltedBuilderQt" in text
    for n in (16, 32, 256):
        assert (xdg / "icons" / "hicolor" / f"{n}x{n}" / "apps"
                / f"{branding.APP_ID}.png").is_file()


def test_the_app_id_matches_what_qt_reports_as_the_desktop_file_name(xdg: Path) -> None:
    """⚠ The whole fix hinges on these being the SAME string: Qt sends APP_ID as the
    Wayland app_id, and the compositor looks for <app_id>.desktop. Drift between the
    entry's filename and setDesktopFileName silently restores the fallback icon."""
    target = branding.install_desktop_entry("/x")
    assert target.stem == branding.APP_ID
    assert f"StartupWMClass={branding.APP_ID}\n" in target.read_text()


def test_rerunning_is_idempotent(xdg: Path) -> None:
    first = branding.install_desktop_entry("/x")
    stamp = first.stat().st_mtime_ns
    assert branding.install_desktop_entry("/x") == first
    assert first.stat().st_mtime_ns == stamp, "rewrote an unchanged entry"


def test_a_failure_is_swallowed_not_fatal(monkeypatch: pytest.MonkeyPatch,
                                          tmp_path: Path) -> None:
    """⚠ This runs at startup for a cosmetic gain; it must never take the app down."""
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "nope"))
    monkeypatch.setattr(branding.Path, "mkdir",
                        lambda *a, **k: (_ for _ in ()).throw(PermissionError("ro")))
    assert branding.install_desktop_entry("/x") is None


def test_skipped_off_linux(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert branding.install_desktop_entry("/x") is None
    assert not (tmp_path / "applications").exists()
