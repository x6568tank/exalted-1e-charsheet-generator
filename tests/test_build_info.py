"""The build line: `build_info.label` and its place at the end of the site menu."""

from __future__ import annotations

import subprocess

import pytest

from exalted_builder import build_info
from exalted_builder.server import nav, site


@pytest.fixture(autouse=True)
def _fresh_cache(monkeypatch):
    # A server test earlier in the process sets a campaign provider that needs a
    # request. The menu cases here have no request.
    monkeypatch.setattr(nav, "_campaigns", None)
    real = build_info.label
    real.cache_clear()
    yield
    real.cache_clear()


def test_the_deploy_file_gives_the_label(tmp_path, monkeypatch) -> None:
    stamp = tmp_path / "BUILD_COMMIT"
    stamp.write_text("6c8658d 2026-09-25\n", encoding="utf-8")
    monkeypatch.setattr(build_info, "STAMP_FILE", stamp)
    assert build_info.label() == "Build 6c8658d · 2026-09-25"


def test_the_deploy_file_wins_over_git(tmp_path, monkeypatch) -> None:
    """⚠ The deployed server has no `.git`. A dev machine has both. The file is the
    record of what was shipped, thus it wins."""
    stamp = tmp_path / "BUILD_COMMIT"
    stamp.write_text("abc1234 2026-01-02", encoding="utf-8")
    monkeypatch.setattr(build_info, "STAMP_FILE", stamp)
    monkeypatch.setattr(build_info, "_from_git", lambda: pytest.fail("git was asked"))
    assert build_info.label() == "Build abc1234 · 2026-01-02"


def test_no_file_and_no_git_gives_no_label(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(build_info, "STAMP_FILE", tmp_path / "absent")

    def no_git(*args, **kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr(subprocess, "run", no_git)
    assert build_info.label() == ""


def test_an_empty_file_falls_back_to_git(tmp_path, monkeypatch) -> None:
    stamp = tmp_path / "BUILD_COMMIT"
    stamp.write_text("\n", encoding="utf-8")
    monkeypatch.setattr(build_info, "STAMP_FILE", stamp)
    monkeypatch.setattr(build_info, "_from_git", lambda: "def5678 2026-03-04")
    assert build_info.label() == "Build def5678 · 2026-03-04"


def test_a_git_checkout_gives_a_label(tmp_path, monkeypatch) -> None:
    """This repository is a git checkout. Skip on a copy with no `.git`."""
    monkeypatch.setattr(build_info, "STAMP_FILE", tmp_path / "absent")
    if not build_info._from_git():
        pytest.skip("not a git checkout, or no git")
    assert build_info.label().startswith("Build ")


def test_the_menu_ends_with_the_build_line(monkeypatch) -> None:
    monkeypatch.setattr(build_info, "label", lambda: "Build 6c8658d · 2026-09-25")
    for username in (None, "Harmonious"):
        last = nav.groups(username)[-1]
        assert [(link.href, link.label, link.key) for link in last] == [
            ("", "Build 6c8658d · 2026-09-25", "build")]


def test_no_label_gives_no_build_line(monkeypatch) -> None:
    monkeypatch.setattr(build_info, "label", lambda: "")
    keys = [link.key for group in nav.groups("Harmonious") for link in group]
    assert "build" not in keys


def test_the_html_drawer_shows_the_build_line(monkeypatch) -> None:
    monkeypatch.setattr(build_info, "label", lambda: "Build 6c8658d · 2026-09-25")
    assert "Build 6c8658d · 2026-09-25" in site.drawer_html(None)
