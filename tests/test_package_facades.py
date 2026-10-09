"""
tests/test_package_facades.py — the safety net for each module that the refactor pass
split into a facade package.

Plan: docs/plans/refactor-pass.md, item 2. The worked example is
docs/plans/validate-refactor.md. Each package is added to `PACKAGES` BEFORE its split,
and the tests must pass on the unsplit file first.

`pkg.X` is the ONE public path to every name of a split package. Callers keep working
only while the facade `__init__.py` re-exports every name that a caller reads. These
tests make that a checked fact. For each package:

* Every public name that a domain module defines is on the facade.
* Every `<alias>.X` in the codebase, where the alias is bound to the package,
  resolves. Also every name in a `from ...pkg import` line. This walk goes from the
  callers, so it also sees private names and imported modules that a caller reads.
* No function in the package reads a name that no scope binds. A domain module that
  lacks an import fails here, before a branch of the suite runs it.
* Every relative import in the package resolves.
* No domain module has the basename of a sibling module of the package. See the
  naming rule in docs/plans/validate-refactor.md: `from .. import play` and
  `from . import play` must not be two different modules.
"""

from __future__ import annotations

import ast
import importlib
import importlib.util
from pathlib import Path

import pytest

from tests.test_validator_rollup import _loads, _module_scope, _own_scope

_ROOT = Path(__file__).resolve().parents[1]

# (dotted name, the least number of distinct names that callers read). The minimum
# is a premise: a walk that finds fewer names is broken, not clean.
PACKAGES = [
    ("exalted_builder.ui.view", 150),
    ("exalted_builder.models.rules", 50),
]
_IDS = [dotted.rsplit(".", 1)[1] for dotted, _ in PACKAGES]


def _location(dotted: str) -> Path:
    """The path of the package, or of the single module before the split, without
    the suffix."""
    return _ROOT.joinpath(*dotted.split("."))


def _package_files(dotted: str) -> list[Path]:
    """Every source file of the package, or the single module before the split."""
    where = _location(dotted)
    if where.is_dir():
        return sorted(where.rglob("*.py"))
    return [where.with_suffix(".py")]


def _domain_files(dotted: str) -> list[Path]:
    """The domain modules of the package. Empty before the split."""
    where = _location(dotted)
    return [p for p in _package_files(dotted)
            if p.name != "__init__.py" and p.parent == where]


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


def _absolute(module: str | None, level: int, path: Path) -> str:
    """The dotted name that `from <dots><module> import` in `path` names."""
    if level == 0:
        return module or ""
    package = ".".join(path.parent.relative_to(_ROOT).parts)
    return importlib.util.resolve_name("." * level + (module or ""), package)


def _references(dotted: str, path: Path, tree: ast.AST) -> set[str]:
    """Every name that `path` reads from the module `dotted`: `<alias>.X` for each
    alias an import binds to the module, and each name of a `from <module> import`
    line."""
    parent, leaf = dotted.rsplit(".", 1)
    aliases: set[str] = set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == dotted and alias.asname:
                    aliases.add(alias.asname)
        elif isinstance(node, ast.ImportFrom):
            try:
                target = _absolute(node.module, node.level, path)
            except (ValueError, ImportError):
                continue
            if target == dotted:
                names.update(a.name for a in node.names if a.name != "*")
            elif target == parent:
                aliases.update(a.asname or leaf for a in node.names if a.name == leaf)
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


def _caller_files(dotted: str) -> list[Path]:
    own = set(_package_files(dotted))
    files: list[Path] = []
    for sub in ("exalted_builder", "tests", "tools"):
        root = _ROOT / sub
        if root.is_dir():
            files.extend(p for p in sorted(root.rglob("*.py")) if p not in own)
    return files


@pytest.mark.parametrize("dotted,minimum", PACKAGES, ids=_IDS)
def test_every_reference_in_the_codebase_resolves(dotted, minimum):
    module = importlib.import_module(dotted)
    seen: dict[str, str] = {}
    for path in _caller_files(dotted):
        try:
            tree = ast.parse(path.read_text(), filename=str(path))
        except SyntaxError:
            continue
        for name in _references(dotted, path, tree):
            seen.setdefault(name, str(path.relative_to(_ROOT)))

    assert len(seen) > minimum, f"only found {len(seen)} references — the walk broke"
    missing = sorted(f"{name} (first read in {where})"
                     for name, where in seen.items() if not hasattr(module, name))
    assert not missing, (f"read through the {dotted} facade but NOT on it:\n  "
                         + "\n  ".join(missing))


def test_the_reference_walk_sees_every_import_shape():
    """Negative control for the walk. Each import shape that the codebase uses must
    give its names, and a local variable with the alias name must not."""
    dotted = "exalted_builder.ui.view"
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
    names = _references(dotted, probe, ast.parse(src))
    assert names == {"build_sheet_view", "alpha", "beta", "gamma"}

    inside = _ROOT / "exalted_builder" / "ui" / "_probe.py"
    src = "from .view import resolve_tab\nfrom . import view\nx = view.delta\n"
    assert _references(dotted, inside, ast.parse(src)) == {"resolve_tab", "delta"}

    engine = _ROOT / "exalted_builder" / "engine" / "validate" / "_probe.py"
    src = "from ...models.rules import RuleSet, Charm\n"
    assert _references("exalted_builder.models.rules", engine,
                       ast.parse(src)) == {"RuleSet", "Charm"}


@pytest.mark.parametrize("dotted", [d for d, _ in PACKAGES], ids=_IDS)
def test_every_public_name_in_a_domain_module_is_on_the_facade(dotted):
    """Private names are exempt here. The call-site walk above covers each private
    name that a caller reads."""
    module = importlib.import_module(dotted)
    orphans: list[str] = []
    for path in _domain_files(dotted):
        for name in sorted(_toplevel_names(ast.parse(path.read_text()))):
            if not name.startswith("_") and not hasattr(module, name):
                orphans.append(f"{name} ({path.name})")
    assert not orphans, (f"defined in a domain module but NOT re-exported by "
                         f"{dotted}: " + ", ".join(orphans))


@pytest.mark.parametrize("dotted", [d for d, _ in PACKAGES], ids=_IDS)
def test_no_function_reads_a_name_it_never_binds(dotted):
    offenders: list[str] = []
    files = _package_files(dotted)
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
    the function runs. The view split moved ten such imports one package deeper."""
    bad: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or not node.level:
            continue
        target = _absolute(node.module, node.level, path)
        try:
            found = importlib.util.find_spec(target) is not None
        except ModuleNotFoundError:
            found = False
        if not found:
            bad.append(f"{path.relative_to(_ROOT)}:{node.lineno} {target}")
    return bad


@pytest.mark.parametrize("dotted", [d for d, _ in PACKAGES], ids=_IDS)
def test_every_relative_import_in_the_package_resolves(dotted):
    bad: list[str] = []
    for path in _package_files(dotted):
        bad += _unresolved_imports(path, ast.parse(path.read_text()))
    assert not bad, "relative imports that name no module:\n  " + "\n  ".join(bad)


def test_the_relative_import_check_can_fail():
    path = _ROOT / "exalted_builder" / "ui" / "view" / "_probe.py"
    src = "def f():\n    from ..engine import dice\n    return dice\n"
    assert _unresolved_imports(path, ast.parse(src)) == [
        "exalted_builder/ui/view/_probe.py:2 exalted_builder.ui.engine"]
    src = "def f():\n    from ...engine import dice\n    return dice\n"
    assert _unresolved_imports(path, ast.parse(src)) == []


@pytest.mark.parametrize("dotted", [d for d, _ in PACKAGES], ids=_IDS)
def test_no_domain_module_shares_a_basename_with_a_sibling_module(dotted):
    siblings = {p.stem for p in _location(dotted).parent.glob("*.py")}
    clashes = sorted(p.stem for p in _domain_files(dotted) if p.stem in siblings)
    assert not clashes, (f"{dotted} modules with the name of a sibling module: "
                         f"{clashes}. Rename them; see docs/plans/validate-refactor.md.")
