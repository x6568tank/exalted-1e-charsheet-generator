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
