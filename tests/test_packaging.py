"""The declared package data must cover every data file on disk.

⚠ This test exists because of a real defect, found 2026-09-11. `package-data` listed
`data/*.json` and `data/charms/*.json` by name. `data/thaumaturgy/` was added later
and was not added here, thus a pip-installed wheel had 189 of the 193 data files and
no thaumaturgy at all.

⚠ Nothing reported it. `rules_db` treats every thaumaturgy file as optional
(`rules_db.py:790`), which is correct for a data set that has no thaumaturgy and is
what makes an omission in the package silent. Thaumaturgy is on all sheets, thus the
loss is not small.

The frozen products were not affected: `pack/*.spec` copies the whole `data`
directory. Only an installed wheel or sdist was, which is the deployment that
hosting uses.

The test reads the globs from `pyproject.toml` and expands them the way setuptools
does, thus it fails for a NEW uncovered directory and not only for the one above.
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
    """The specific regression. ⚠ Keep it next to the general test above: the general
    one fails if it is pointed at the incorrect directory and then covers nothing,
    and this one names the directory that was actually lost."""
    thaum = {p.relative_to(_PKG) for p in (_PKG / "data" / "thaumaturgy").rglob("*.json")}
    assert len(thaum) == 4, f"Expected 4 thaumaturgy data files, found {len(thaum)}."
    assert thaum <= _covered(), "The thaumaturgy data is not declared as package data."
