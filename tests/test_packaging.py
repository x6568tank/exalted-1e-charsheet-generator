"""The declared package data must cover each data file on disk.

⚠ A directory missing from `package-data` gives a wheel without it, with no error:
`rules_db` treats each thaumaturgy file as optional (`rules_db.py:790`). The frozen
products copy the whole `data` directory, thus only a wheel or sdist (the hosting
deployment) is affected.

⚠ The frozen products hide the defect: test the wheel globs.

The test reads the globs from `pyproject.toml` and expands them the way setuptools
does, thus it fails for each NEW uncovered directory.
"""

import tomllib
from pathlib import Path

import exalted_builder

_ROOT = Path(__file__).resolve().parent.parent
_PKG = Path(exalted_builder.__file__).parent


def _declared_globs() -> list[str]:
    """The package-data patterns for the exalted_builder package."""
    with (_ROOT / "pyproject.toml").open("rb") as fh:
        config = tomllib.load(fh)
    globs = config["tool"]["setuptools"]["package-data"]["exalted_builder"]
    assert globs, "pyproject.toml declares no package data for exalted_builder."
    return globs


def _covered() -> set[Path]:
    """Every file the declared globs match, relative to the package directory."""
    found: set[Path] = set()
    for pattern in _declared_globs():
        found.update(p.relative_to(_PKG) for p in _PKG.glob(pattern) if p.is_file())
    return found


def test_every_data_file_is_declared_as_package_data() -> None:
    on_disk = {p.relative_to(_PKG) for p in (_PKG / "data").rglob("*.json")}
    assert on_disk, "No data files found. The test is looking in the incorrect place."

    missing = sorted(str(p) for p in on_disk - _covered())
    assert not missing, (
        "These data files are on disk but no package-data glob matches them, thus a "
        "pip install does not get them and the loader does not report it:\n  "
        + "\n  ".join(missing)
    )


def test_the_vendored_javascript_is_declared_as_package_data() -> None:
    """The Charm tree inlines this file at run time. An install without it renders
    no tree. See `ui/assets.py`."""
    on_disk = {p.relative_to(_PKG) for p in (_PKG / "ui" / "vendor").rglob("*.js")}
    assert on_disk, "No vendored JavaScript found."

    missing = sorted(str(p) for p in on_disk - _covered())
    assert not missing, f"Vendored JavaScript is not declared as package data: {missing}"


def test_the_thaumaturgy_directory_is_covered() -> None:
    """The specific directory. ⚠ Keep it next to the general test above: the general
    one covers nothing if it points at an incorrect directory."""
    thaum = {p.relative_to(_PKG) for p in (_PKG / "data" / "thaumaturgy").rglob("*.json")}
    assert len(thaum) == 4, f"Expected 4 thaumaturgy data files, found {len(thaum)}."
    assert thaum <= _covered(), "The thaumaturgy data is not declared as package data."
