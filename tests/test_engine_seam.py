"""The engine side of the package must not import a UI toolkit or a shell.

This is the boundary decision 0002 states and `docs/plans/vtt.md` section 1 depends
on: a third consumer (`exalted-table`) imports `exalted_builder.engine` and must not
pull in NiceGUI or PySide6.

The boundary holds today. This test stops it rotting, because an import added inside
a function is invisible until the deployment that has no toolkit runs that function.

⚠ It reads the syntax tree, it does not search the text. Two engine modules contain
the words "imports no `nicegui`" in a comment (`engine/combo_actions.py`,
`engine/thaum_actions.py`), thus a text search reports them and a reader learns to
ignore the test.

⚠ It examines source files, thus it finds an import in a branch that never runs. An
import-based check finds only the imports that the test itself caused to run.
"""

import ast
from pathlib import Path

import pytest

import exalted_builder

_PKG = Path(exalted_builder.__file__).parent

# The modules that ship to a consumer which installs no extras. `data/` holds no
# Python. See pyproject.toml: `pydantic` is the only hard dependency.
_ENGINE_SIDE = ["models", "engine", "rules_db.py", "persistence.py",
                "custom_content.py"]

# A toolkit or a shell. `branding.py` is not here: it belongs to the shells.
_FORBIDDEN_ROOTS = {"nicegui", "PySide6", "PySide2", "PyQt5", "PyQt6", "reportlab"}
_FORBIDDEN_SUBMODULES = {"ui", "qt"}


def _engine_source_files() -> list[Path]:
    files: list[Path] = []
    for entry in _ENGINE_SIDE:
        target = _PKG / entry
        files.extend([target] if target.is_file() else sorted(target.rglob("*.py")))
    return files


def _imported_names(tree: ast.AST) -> list[tuple[str, int]]:
    """Every module an import statement names, with its line. Relative imports give
    the name after the dots, which is what the submodule check needs."""
    names: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend((alias.name, node.lineno) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.append((node.module, node.lineno))
            if node.level:
                # `from .. import qt` names the submodule in the alias, not in
                # `node.module`, which is None.
                names.extend((alias.name, node.lineno) for alias in node.names)
    return names


def test_the_engine_side_files_exist() -> None:
    """⚠ The control. Without it, a renamed directory makes every test below pass
    over an empty file list."""
    missing = [entry for entry in _ENGINE_SIDE if not (_PKG / entry).exists()]
    assert not missing, (
        f"_ENGINE_SIDE names paths that do not exist: {missing}. The seam tests below "
        f"then check nothing."
    )

    files = _engine_source_files()
    assert len(files) > 30, (
        f"Found only {len(files)} engine-side source files, which is too few to be "
        f"the engine. _ENGINE_SIDE is stale."
    )


@pytest.mark.parametrize("path", _engine_source_files(), ids=lambda p: p.name)
def test_no_engine_module_imports_a_toolkit_or_a_shell(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    offences = [
        f"{path.relative_to(_PKG)}:{line} imports {name!r}"
        for name, line in _imported_names(tree)
        if name.split(".")[0] in _FORBIDDEN_ROOTS
        or name.split(".")[0] in _FORBIDDEN_SUBMODULES
        or any(part in _FORBIDDEN_SUBMODULES for part in name.split(".")[:2])
    ]

    assert not offences, (
        "The engine must stay free of a UI toolkit and of both shells — see decision "
        "0002 and docs/plans/vtt.md section 1:\n  " + "\n  ".join(offences)
    )
