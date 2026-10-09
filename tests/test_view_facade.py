"""
tests/test_view_facade.py — the safety net for the split of `ui/view.py`.

Plan: docs/plans/refactor-pass.md, item 2. The worked example is
docs/plans/validate-refactor.md. This file exists BEFORE the split, on purpose.

`view.X` is the ONE public path to every presenter name. 95 files reach the
presenter through `view`, `viewmod` or a `from .view import` line. A split keeps
them working only while the facade in `ui/view/__init__.py` re-exports every name
that a caller reads. These tests make that a checked fact.

Four guards:

* Every public name that a domain module defines is on the facade.
* Every `<alias>.X` in the codebase, where the alias is bound to the view module,
  resolves. Also every name in a `from ...view import` line. This walk goes from the
  callers, so it also sees private names and imported modules that a caller reads.
* No function in the package reads a name that no scope binds. A domain module that
  lacks an import fails here, before a branch of the suite runs it.
* No domain module has the basename of a module in `ui/`. See the naming rule in
  docs/plans/validate-refactor.md: `from .. import play` and `from . import play`
  must not be two different modules.
"""

from __future__ import annotations

import ast
from pathlib import Path

from tests.test_validator_rollup import _loads, _module_scope, _own_scope

_ROOT = Path(__file__).resolve().parents[1]
_UI = _ROOT / "exalted_builder" / "ui"
_VIEW_DOTTED = "exalted_builder.ui.view"


def _view_files() -> list[Path]:
    """Every source file of the presenter: the package, or the single module."""
    package = _UI / "view"
    if package.is_dir():
        return sorted(package.rglob("*.py"))
    return [_UI / "view.py"]


def _domain_files() -> list[Path]:
    """The domain modules of the package. Empty before the split."""
    return [p for p in _view_files() if p.name != "__init__.py" and p.parent.name == "view"]


def _toplevel_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                names.update(n.id for n in ast.walk(target) if isinstance(n, ast.Name))
    return names


def _is_view_module(module: str | None, level: int, path: Path) -> bool:
    """True if `from <module> import ...` (at `level`) in `path` names the presenter
    package or one of its parents."""
    if level == 0:
        return module == _VIEW_DOTTED
    package = path.parent
    for _ in range(level - 1):
        package = package.parent
    try:
        base = ".".join(package.relative_to(_ROOT).parts)
    except ValueError:
        return False
    return (f"{base}.{module}" if module else base) == _VIEW_DOTTED


def _view_references(path: Path, tree: ast.AST) -> set[str]:
    """Every name that `path` reads from the view module: `<alias>.X` for each alias
    an import binds to the module, and each name of a `from ...view import` line."""
    aliases: set[str] = set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == _VIEW_DOTTED and alias.asname:
                    aliases.add(alias.asname)
        elif isinstance(node, ast.ImportFrom):
            if _is_view_module(node.module, node.level, path):
                names.update(a.name for a in node.names if a.name != "*")
            else:
                for alias in node.names:
                    parent = node.module or ""
                    if alias.name == "view" and _is_view_module(
                            f"{parent}.view" if parent else "view", node.level, path):
                        aliases.add(alias.asname or "view")
    # ⚠ An alias can also be a local variable in another function of the same file
    # (`view = build_sheet_view(...)`). Read only the accesses in a scope where the
    # alias is not assigned.
    for scope in [tree] + [n for n in ast.walk(tree)
                           if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        body_nodes = list(_own_nodes(scope))
        assigned = {n.id for n in body_nodes
                    if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
        assigned |= {a.arg for n in body_nodes if isinstance(n, ast.arguments)
                     for a in n.args + n.kwonlyargs + n.posonlyargs}
        for node in body_nodes:
            if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                    and node.value.id in aliases and node.value.id not in assigned):
                names.add(node.attr)
    return names


def _own_nodes(scope):
    """The nodes of `scope`, without the bodies of the functions nested in it."""
    stack = list(ast.iter_child_nodes(scope))
    while stack:
        node = stack.pop()
        yield node
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node.args
            continue
        stack.extend(ast.iter_child_nodes(node))


def _caller_files() -> list[Path]:
    view_files = set(_view_files())
    files: list[Path] = []
    for sub in ("exalted_builder", "tests", "tools"):
        root = _ROOT / sub
        if root.is_dir():
            files.extend(p for p in sorted(root.rglob("*.py")) if p not in view_files)
    return files


def test_every_view_reference_in_the_codebase_resolves():
    from exalted_builder.ui import view

    seen: dict[str, str] = {}
    for path in _caller_files():
        try:
            tree = ast.parse(path.read_text(), filename=str(path))
        except SyntaxError:
            continue
        for name in _view_references(path, tree):
            seen.setdefault(name, str(path.relative_to(_ROOT)))

    assert len(seen) > 150, f"only found {len(seen)} view references — the walk broke"
    missing = sorted(f"{name} (first read in {where})"
                     for name, where in seen.items() if not hasattr(view, name))
    assert not missing, ("read through the view facade but NOT on it:\n  "
                         + "\n  ".join(missing))


def test_the_reference_walk_sees_every_import_shape(tmp_path):
    """Negative control for the walk. Each import shape that the codebase uses must
    give its names, and a local variable with the alias name must not."""
    probe = _ROOT / "exalted_builder" / "qt" / "_probe.py"
    src = (
        "from ..ui import view as viewmod\n"
        "from exalted_builder.ui.view import build_sheet_view\n"
        "import exalted_builder.ui.view as vm\n"
        "def f():\n"
        "    return viewmod.alpha, vm.beta\n"
        "def g():\n"
        "    from exalted_builder.ui import view\n"
        "    return view.gamma\n"
        "def h(rs, ch):\n"
        "    view = build_sheet_view(rs, ch)\n"
        "    return view.not_a_module_name\n"
    )
    names = _view_references(probe, ast.parse(src))
    assert names == {"build_sheet_view", "alpha", "beta", "gamma"}

    inside = _UI / "_probe.py"
    src = "from .view import resolve_tab\nfrom . import view\nx = view.delta\n"
    assert _view_references(inside, ast.parse(src)) == {"resolve_tab", "delta"}


def test_every_public_name_in_a_domain_module_is_on_the_facade():
    """Private names are exempt here. The call-site walk above covers each private
    name that a caller reads."""
    from exalted_builder.ui import view

    orphans: list[str] = []
    for path in _domain_files():
        for name in sorted(_toplevel_names(ast.parse(path.read_text()))):
            if not name.startswith("_") and not hasattr(view, name):
                orphans.append(f"{name} ({path.name})")
    assert not orphans, ("defined in a domain module but NOT re-exported by "
                         "ui/view/__init__.py: " + ", ".join(orphans))


def test_no_view_function_reads_a_name_it_never_binds():
    offenders: list[str] = []
    files = _view_files()
    assert files and all(p.exists() for p in files), files
    for path in files:
        tree = ast.parse(path.read_text(), filename=str(path))
        module_names = _module_scope(tree)

        def check(fn, enclosing: set[str]) -> None:
            bound, nested = _own_scope(fn)
            visible = bound | enclosing
            for name, lineno in _loads(fn, skip=set(nested)):
                if name not in visible and name not in module_names:
                    offenders.append(f"{path.relative_to(_ROOT)}:{lineno} "
                                     f"{getattr(fn, 'name', '<lambda>')}() reads "
                                     f"undefined {name!r}")
            for sub in nested:
                check(sub, visible)

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        check(item, set())
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                check(node, set())

    assert not offenders, ("function(s) read a name bound in no reachable scope:\n  "
                           + "\n  ".join(sorted(set(offenders))))


def _unresolved_imports(path: Path, tree: ast.AST) -> list[str]:
    """Each relative import in `path`, at any depth, that names no module or package.

    ⚠ The check above cannot see these. A function-local `from ..engine import dice`
    binds `dice` in the function, so the name is defined. The import fails only when
    the function runs. The split moved such imports one package deeper."""
    import importlib.util

    package = ".".join(path.parent.relative_to(_ROOT).parts)
    bad: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or not node.level:
            continue
        target = importlib.util.resolve_name("." * node.level + (node.module or ""), package)
        try:
            found = importlib.util.find_spec(target) is not None
        except ModuleNotFoundError:
            found = False
        if not found:
            bad.append(f"{path.relative_to(_ROOT)}:{node.lineno} {target}")
    return bad


def test_every_relative_import_in_the_package_resolves():
    bad: list[str] = []
    for path in _view_files():
        bad += _unresolved_imports(path, ast.parse(path.read_text()))
    assert not bad, "relative imports that name no module:\n  " + "\n  ".join(bad)


def test_the_relative_import_check_can_fail():
    path = _view_files()[0]
    src = "def f():\n    from ..engine import dice\n    return dice\n"
    if path.parent.name == "view":
        assert _unresolved_imports(path, ast.parse(src)) == [
            f"{path.relative_to(_ROOT)}:2 exalted_builder.ui.engine"]
    src = "def f():\n    from ...engine import dice\n    return dice\n"
    assert _unresolved_imports(_UI / "view" / "_probe.py", ast.parse(src)) == []


def test_no_domain_module_shares_a_basename_with_a_ui_module():
    shells = {p.stem for p in _UI.glob("*.py")}
    clashes = sorted(p.stem for p in _domain_files() if p.stem in shells)
    assert not clashes, (f"ui/view/ modules with the name of a ui/ module: {clashes}. "
                         "Rename them; see docs/plans/validate-refactor.md.")
