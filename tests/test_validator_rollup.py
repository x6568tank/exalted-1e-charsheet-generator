"""
tests/test_validator_rollup.py — the safety net for splitting `engine/validate.py`.

Plan: docs/plans/validate-refactor.md. This file exists BEFORE the split, on purpose.

The project's recurring defect (CLAUDE.md's "house bug") is *a rule that IS
implemented, sitting where it does not run when it matters* — and carving a
5,800-line validator into modules is the ideal way to manufacture one. Drop a
`check_*` from the `validate()` roll-up and it still exists, its own unit tests
still pass, and it never runs again. Nothing else in the suite can see that.

So: every Issue-producing validator in `engine/` must be reachable from one of the
three roots below. The call graph is built by AST over the whole package and is
deliberately COARSE — it matches on the called name only, ignoring the module it
was reached through (`validate.check_artifacts` and a bare `check_artifacts` are
the same node). That over-approximates reachability, which is the right direction
for a safety net: it will never fail because a call moved between modules, and it
still fails the moment a validator has no caller at all.

⚠ What this test canNOT see: a checker whose call site survives but is guarded by a
condition that is never true. Reachability is not execution. The three roots are
the entry points, not a claim that every branch runs.

The second guard here is the FACADE's completeness. `validate.X` is the one public
path to every name in the package (the human's call, 2026-08-17), which is what let
the split leave 1,465 call sites untouched — but only while the re-export list in
`__init__.py` stays exhaustive. Forget one line there and the failure surfaces in
whichever unrelated caller happens to use that name, or in no test at all if the
name is only read by `ui/`.
"""

from __future__ import annotations

import ast
import collections
from pathlib import Path

import pytest

_ENGINE = Path(__file__).resolve().parents[1] / "exalted_builder" / "engine"

# The entry points a caller outside `engine/` is expected to use. `validate` and
# `validate_chargen` are the two sides of the lock; `validate_xp` is the XP-log
# audit, a third root reached from neither (decision 0004 — chargen and
# advancement are different shapes).
ROOTS = ("validate", "validate_chargen", "validate_xp")

# Naming conventions that mark a function as producing `Issue`s. Anything matching
# these must be reachable; see `DELIBERATELY_UNREACHED` for the escape hatch.
_VALIDATOR_PREFIXES = ("check_", "validate_")
_VALIDATOR_SUFFIXES = ("_issues",)

# A validator that is intentionally not wired into any root belongs here WITH ITS
# REASON — never add a name to silence a failure you have not explained.
DELIBERATELY_UNREACHED: dict[str, str] = {}


def _is_validator(name: str) -> bool:
    return (name.startswith(_VALIDATOR_PREFIXES)
            or name.endswith(_VALIDATOR_SUFFIXES))


@pytest.fixture(scope="module")
def call_graph() -> tuple[dict[str, str], dict[str, set[str]]]:
    """(name -> defining module, name -> names it calls) over all of `engine/`."""
    defs: dict[str, str] = {}
    calls: dict[str, set[str]] = collections.defaultdict(set)
    # ⚠ rglob, NOT glob. `engine/validate/` is a PACKAGE — a non-recursive glob
    # would silently stop seeing every validator the moment the split moved them
    # into it, which is this test's own subject matter turned on itself.
    for path in sorted(_ENGINE.rglob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            defs.setdefault(node.name, str(path.relative_to(_ENGINE)))
            for sub in ast.walk(node):
                if not isinstance(sub, ast.Call):
                    continue
                func = sub.func
                if isinstance(func, ast.Name):
                    calls[node.name].add(func.id)
                elif isinstance(func, ast.Attribute):
                    # Coarse by design — see the module docstring.
                    calls[node.name].add(func.attr)
    return defs, dict(calls)


def _reachable(calls: dict[str, set[str]], roots) -> set[str]:
    seen: set[str] = set()
    stack = list(roots)
    while stack:
        name = stack.pop()
        if name in seen:
            continue
        seen.add(name)
        stack.extend(calls.get(name, ()))
    return seen


def test_the_roots_exist(call_graph):
    """If a root is renamed or moved out of `engine/`, every assertion below turns
    vacuous — this is the premise check that keeps them honest.

    It is also the canary for the AST walk itself: should the glob ever stop
    reaching the files the validators live in, the roots vanish from `defs` and this
    fails loudly, instead of the reachability test passing over an empty graph."""
    defs, _ = call_graph
    missing = [r for r in ROOTS if r not in defs]
    assert not missing, f"root(s) not defined anywhere in engine/: {missing}"


def test_every_validator_is_reachable_from_a_root(call_graph):
    """THE point of this file. A `check_*` that no root reaches is dead code that
    looks alive: it keeps its unit tests and stops guarding anything."""
    defs, calls = call_graph
    reachable = _reachable(calls, ROOTS)
    orphans = sorted(
        f"{name} ({defs[name]})"
        for name in defs
        if _is_validator(name)
        and name not in reachable
        and name not in DELIBERATELY_UNREACHED
    )
    assert not orphans, (
        "validator(s) unreachable from " + "/".join(ROOTS) + ": "
        + ", ".join(orphans)
        + "\nEither wire it into the roll-up, or add it to DELIBERATELY_UNREACHED "
        "with the reason. Do NOT add it to silence the failure."
    )


def test_the_unreached_allowlist_is_not_stale(call_graph):
    """A name that became reachable must leave the allowlist, or the allowlist stops
    describing the build. (Negative controls in this project have gone stale four
    times in one session — CLAUDE.md.)"""
    defs, calls = call_graph
    reachable = _reachable(calls, ROOTS)
    for name in DELIBERATELY_UNREACHED:
        assert name in defs, f"{name} is allowlisted but no longer defined"
        assert name not in reachable, (
            f"{name} is allowlisted as unreached but IS now reachable — remove it")


def test_the_reachability_check_can_fail(call_graph):
    """The negative control. A coarse name-matched call graph is exactly the kind of
    check that passes because it found everything, so prove it can still miss."""
    _, calls = call_graph
    reachable = _reachable(calls, ROOTS)
    assert "check_charm_prerequisites" in reachable, "premise: a known-wired checker"
    assert "check_a_rule_nobody_wrote" not in reachable


# --------------------------------------------------------------------------- #
# The facade
# --------------------------------------------------------------------------- #

def _toplevel_names(src: str) -> set[str]:
    """Every name a module binds at top level: defs, classes and assignments."""
    out: set[str] = set()
    for node in ast.parse(src).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(node.name)
        elif isinstance(node, ast.Assign):
            out |= {t.id for t in node.targets if isinstance(t, ast.Name)}
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            out.add(node.target.id)
    return out


def test_every_name_in_a_domain_module_is_reachable_as_validate_X():
    """The facade contract for the PUBLIC surface. Callers reach everything through
    `validate.X`, so a public name that lands in a domain module and is not
    re-exported has silently left the API.

    ⚠ Underscore-private names are deliberately exempt HERE, and covered by
    `test_every_validate_dot_reference_in_the_codebase_resolves` instead. Several are
    genuinely package-internal (`_chargen_charm_issues` and its fourteen siblings are
    private sections of `validate_chargen` that no caller should reach), while others
    (`_chargen_source`, `_immaculate_path`) ARE read from outside. The distinction
    that matters is not the underscore but whether anything actually references it —
    which is a question about call sites, so the call-site test is what answers it.
    """
    from exalted_builder.engine import validate

    package = Path(validate.__file__).parent
    orphans: list[str] = []
    for path in sorted(package.glob("*.py")):
        if path.name == "__init__.py":
            continue
        for name in sorted(_toplevel_names(path.read_text())):
            if name.startswith("_"):
                continue
            if not hasattr(validate, name):
                orphans.append(f"{name} ({path.name})")
    assert not orphans, (
        "defined in a domain module but NOT re-exported by validate/__init__.py: "
        + ", ".join(orphans)
        + "\nAdd it to the re-export list — `validate.X` is the one public path."
    )


def test_the_facade_check_has_something_to_check():
    """Premise. If the package ever held only `__init__.py` again, the test above
    would pass by iterating over nothing — the shape of vacuous pass this project
    has been bitten by four times."""
    from exalted_builder.engine import validate

    package = Path(validate.__file__).parent
    domains = [p.name for p in package.glob("*.py") if p.name != "__init__.py"]
    assert domains, "no domain modules found — the facade test would be vacuous"


def test_every_validate_dot_reference_in_the_codebase_resolves():
    """The facade's OTHER half, and the one the split actually broke.

    `test_every_name_in_a_domain_module_is_reachable_as_validate_X` walks outward
    from what the package defines. It cannot see a caller reaching a name the package
    never defined but happened to expose — `validate.merits` worked for months only
    because the old single file did `from .. import merits`, so trimming that
    "unused" import broke 22 tests through `advancement.py`'s three call sites.

    So this walks the other way: every `validate.<name>` attribute access anywhere in
    the package or the suite must resolve. Imported MODULES are part of the public
    surface whether or not anyone intended them to be.

    Read with AST rather than a regex, so prose in docstrings that happens to write
    `validate.py` or `validate.X` is not mistaken for a call site.
    """
    from exalted_builder.engine import validate

    # Accesses guarded by an explicit `hasattr(validate, ...)` are deliberately
    # optional and must NOT be required to resolve.
    optional = {"commit_ox_body_purchase"}

    root = Path(__file__).resolve().parents[1]
    seen: dict[str, str] = {}
    for sub in ("exalted_builder", "tests"):
        for path in sorted((root / sub).rglob("*.py")):
            try:
                tree = ast.parse(path.read_text(), filename=str(path))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if (isinstance(node, ast.Attribute)
                        and isinstance(node.value, ast.Name)
                        and node.value.id == "validate"):
                    seen.setdefault(node.attr, str(path.relative_to(root)))

    assert len(seen) > 100, f"only found {len(seen)} validate.X accesses — the walk broke"
    missing = sorted(f"validate.{n} (first seen {where})"
                     for n, where in seen.items()
                     if n not in optional and not hasattr(validate, n))
    assert not missing, (
        "call site(s) reference a name the validate package does not expose: "
        + "; ".join(missing)
    )


# --------------------------------------------------------------------------- #
# Undefined names
# --------------------------------------------------------------------------- #

def _module_scope(tree: ast.AST) -> set[str]:
    """Names visible to every function in the module: imports, top-level defs and
    top-level assignments, plus builtins."""
    import builtins

    out = set(dir(builtins))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                out.add((alias.asname or alias.name).split(".")[0])
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(node.name)
        elif isinstance(node, ast.Global):
            out.update(node.names)
    for node in tree.body:
        if isinstance(node, ast.Assign):
            out |= {n.id for t in node.targets for n in ast.walk(t)
                    if isinstance(n, ast.Name)}
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            out.add(node.target.id)
    return out


_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)


def _params(fn) -> set[str]:
    a = fn.args
    out = {x.arg for x in a.posonlyargs + a.args + a.kwonlyargs}
    if a.vararg:
        out.add(a.vararg.arg)
    if a.kwarg:
        out.add(a.kwarg.arg)
    return out


def _own_scope(fn) -> tuple[set[str], list]:
    """(names this function binds, nested scopes to check separately).

    Walks the body but does NOT descend into nested functions or lambdas — their
    parameters belong to them, not here. Comprehensions ARE walked: their targets
    are bound and their bodies may read enclosing names, so folding them in
    over-approximates in the safe direction.
    """
    bound = _params(fn)
    nested = []

    def walk(node):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, _SCOPES):
                nested.append(child)
                if not isinstance(child, ast.Lambda):
                    bound.add(child.name)
                continue
            if isinstance(child, ast.ClassDef):
                bound.add(child.name)
                continue
            if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store):
                bound.add(child.id)
            elif isinstance(child, (ast.Import, ast.ImportFrom)):
                for alias in child.names:
                    bound.add((alias.asname or alias.name).split(".")[0])
            elif isinstance(child, ast.ExceptHandler) and child.name:
                bound.add(child.name)
            elif isinstance(child, ast.Global):
                bound.update(child.names)
            walk(child)

    walk(fn)
    return bound, nested


def _loads(fn, skip) -> list[tuple[str, int]]:
    """(name, lineno) for every Load in `fn`, excluding nested scopes in `skip`."""
    out = []

    def walk(node):
        for child in ast.iter_child_nodes(node):
            if child in skip:
                continue
            if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load):
                out.append((child.id, child.lineno))
            walk(child)

    walk(fn)
    return out


def test_no_engine_function_reads_a_name_it_never_binds():
    """A per-FUNCTION undefined-name check over all of `engine/`.

    Both bugs the 2026-08-17 `validate_chargen` decomposition hit were this one
    shape: a section boundary swallowed an assignment (`mf_caps`, then `wp_total`)
    into the extracted helper while the parent still read it. A whole-FILE check
    cannot see either — the name IS defined in the file, just not in the function
    that reads it — and neither can an import smoke test, since the NameError only
    fires when that branch executes. Only the suite caught them, and only by running
    the branch; this catches them statically.

    Scope handling is real rather than approximate: nested functions and lambdas own
    their parameters and are checked separately against their enclosing scope, and
    Python's function-wide (not block) scoping means an assignment anywhere in a body
    binds for the whole body. Comprehensions are folded into the enclosing function,
    which over-approximates what is bound — the safe direction for a guard that must
    not cry wolf.
    """
    offenders: list[str] = []
    for path in sorted(_ENGINE.rglob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        module_names = _module_scope(tree)

        def check(fn, enclosing: set[str]) -> None:
            bound, nested = _own_scope(fn)
            visible = bound | enclosing
            for name, lineno in _loads(fn, skip=set(nested)):
                if name not in visible and name not in module_names:
                    label = getattr(fn, "name", "<lambda>")
                    offenders.append(
                        f"{path.relative_to(_ENGINE)}:{lineno} "
                        f"{label}() reads undefined {name!r}")
            for sub in nested:
                check(sub, visible)

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                check(node, set())

    assert not offenders, ("function(s) read a name bound in no reachable scope:\n  "
                           + "\n  ".join(sorted(set(offenders))))


def test_the_undefined_name_check_can_fail(tmp_path):
    """Negative control, on a synthetic module — the real subject is (correctly)
    clean, so without this the check above could silently stop working."""
    bad = tmp_path / "engine_probe.py"
    bad.write_text("def f():\n    return not_bound_anywhere\n")
    tree = ast.parse(bad.read_text())
    module_names = _module_scope(tree)
    fn = tree.body[0]
    bound, nested = _own_scope(fn)
    missing = [n for n, _ in _loads(fn, skip=set(nested))
               if n not in bound and n not in module_names]
    assert missing == ["not_bound_anywhere"]

    ok = "def g(x):\n    return sorted(x, key=lambda s: s.name)\n"
    tree = ast.parse(ok)
    module_names = _module_scope(tree)
    fn = tree.body[0]
    bound, nested = _own_scope(fn)
    assert not [n for n, _ in _loads(fn, skip=set(nested))
                if n not in bound and n not in module_names], \
        "a lambda parameter must not read as undefined"
