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


# --------------------------------------------------------------------------- #
# Suite hygiene: a dotted-string monkeypatch target into the package
# --------------------------------------------------------------------------- #

_TESTS_DIR = Path(__file__).parent


def _string_monkeypatch_targets(path: Path) -> list[tuple[int, str]]:
    """Return the (line, target) of each `monkeypatch.setattr("exalted_builder…")`
    in `path`.

    Read the syntax tree. Match a call whose function is an attribute named
    `setattr` or `delattr` on a name `monkeypatch`, and whose first argument is a
    string constant that starts with the package name.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr not in {"setattr", "delattr"}:
            continue
        if not isinstance(func.value, ast.Name) or func.value.id != "monkeypatch":
            continue
        first = node.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str) \
                and first.value.startswith("exalted_builder"):
            found.append((node.lineno, first.value))
    return found


def test_no_test_patches_by_dotted_string() -> None:
    """⚠ A dotted-string target makes pytest re-walk the path from `sys.modules`
    at call time, and a NiceGUI main-file test replaces
    `sys.modules["exalted_builder"]` with a hollow namespace stub (`__file__`
    None, `__path__` []). The walk then fails at the FIRST step — "module
    'exalted_builder' has no attribute 'qt'" — while the real module is still in
    `sys.modules` and every already-imported class still works.

    ⚠ The failure is ORDERING-DEPENDENT, thus it is invisible. It appears only
    when a main-file test sorts before the patching file. It cost a red full suite
    on 2026-09-11: the one violation had sorted after every main-file test for
    months, until a new test file landed at 'h'.

    Import the module and patch the object. See `tests/test_qt_shell.py`.

    ⚠ ONE case over all the test files, not one for each. The rule is repo-wide and
    the count of the test files is not a property worth 104 cases in the suite. The
    message names each offending file and line, thus nothing is lost.
    """
    offenders = [(path, line, target)
                 for path in sorted(_TESTS_DIR.glob("test_*.py"))
                 for line, target in _string_monkeypatch_targets(path)]

    assert not offenders, (
        "These tests patch by dotted string: "
        + "; ".join(f"{path.name}:{line} {target!r}" for path, line, target in offenders)
        + ". Import the module and patch the object instead — a string target "
          "breaks after any NiceGUI main-file test, depending only on file order."
    )


# --------------------------------------------------------------------------- #
# Shell text: the two Advantages tabs must not copy a display string
# --------------------------------------------------------------------------- #

# A shared literal shorter than this is a label or a key, e.g. "Merits & Flaws".
_SHARED_TEXT_MIN = 40


def _display_literals(path: Path) -> set[str]:
    """Return the string constants of `path` with `_SHARED_TEXT_MIN` or more characters.

    Read the syntax tree. Do not include docstrings: a docstring is not display text.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    docstrings = {id(node.body[0].value) for node in ast.walk(tree)
                  if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                       ast.AsyncFunctionDef))
                  and ast.get_docstring(node, clean=False) is not None}
    return {node.value for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
            and len(node.value) >= _SHARED_TEXT_MIN and id(node) not in docstrings}


def test_the_advantages_tabs_share_no_display_text() -> None:
    """⚠ A string in both shells drifts: one copy gets the correction, the other does
    not, and no test sees the difference. `ui/view.py` holds the text for both.

    ⚠ This test covers the Advantages pair only. Other shell pairs still copy text.
    """
    shared = (_display_literals(_PKG / "qt" / "advantages.py")
              & _display_literals(_PKG / "ui" / "advantages.py"))

    assert not shared, (
        "qt/advantages.py and ui/advantages.py both contain: "
        + "; ".join(repr(text) for text in sorted(shared))
        + ". Move the text into ui/view.py and read it from both shells."
    )
