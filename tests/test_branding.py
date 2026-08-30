"""The app icon resolves for both shells and survives a frozen build."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from exalted_builder import branding

ROOT = Path(__file__).resolve().parent.parent


def test_icon_resolves_in_a_source_checkout() -> None:
    icon = branding.app_icon_path()
    assert icon is not None and icon.is_file()
    assert icon == ROOT / "assets" / "icon.png"


def test_a_missing_icon_is_none_and_not_an_error(monkeypatch: pytest.MonkeyPatch,
                                                 tmp_path: Path) -> None:
    """⚠ The icon is cosmetic: absent, the app must still start. A raise here would
    take down both shells at their first line."""
    monkeypatch.setattr(branding, "assets_dir", lambda: tmp_path)
    assert branding.app_icon_path() is None


def test_frozen_builds_look_in_the_pyinstaller_extraction_dir(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Frozen, `assets/` is not beside the package — it is where the spec put it."""
    monkeypatch.setattr(branding.sys, "frozen", True, raising=False)
    monkeypatch.setattr(branding.sys, "_MEIPASS", str(tmp_path), raising=False)
    assert branding.assets_dir() == tmp_path / "assets"


@pytest.mark.parametrize("spec", ["exalted-builder.spec", "exalted-builder-qt.spec"])
def test_both_specs_bundle_the_icon_and_brand_the_executable(spec: str) -> None:
    """⚠ Wiring the icon in code is only half of it — an unbundled asset resolves to
    a path that does not exist inside the build, so the packaged app silently loses
    the icon while every source-tree test still passes."""
    text = (ROOT / "pack" / spec).read_text()
    ast.parse(text)                                   # the spec is executed as python
    assert '"assets" / "icon.png"), "assets"' in text
    assert 'icon=str(ROOT / "assets" / "icon.ico")' in text


def test_the_executable_icon_file_exists_and_is_square() -> None:
    """⚠ .ico must be square or Windows refuses it; the source png is 500x502."""
    ico = ROOT / "assets" / "icon.ico"
    assert ico.is_file()
    from PIL import Image
    with Image.open(ico) as im:
        assert im.size[0] == im.size[1]
