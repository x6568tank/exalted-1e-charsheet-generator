"""Guard a comment/docstring-only edit (the CLAUDE.md comment standard).

Usage: prose_guard.py <baseline-git-ref> <path> [path ...]

Asserts, per file, that the edit changed PROSE ONLY:
  * the AST with all docstrings stripped is byte-identical  -> no code changed
  * every rulebook page citation still appears              -> citations kept
  * every ⚠ marker still appears                            -> traps kept
Reports anything lost instead of failing silently.
"""
import ast
import re
import subprocess
import sys

CITE = re.compile(r"(?:pp?\.\s?\d+(?:\s?-\s?\d+)?)", re.I)
WARN = "⚠"


def strip_docstrings(src: str) -> str:
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.ClassDef)):
            continue
        body = node.body
        if (body and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)):
            node.body = body[1:] or [ast.Pass()]
    return ast.dump(ast.parse(ast.unparse(tree)), annotate_fields=False)


def main():
    ref, paths = sys.argv[1], sys.argv[2:]
    bad = False
    for path in paths:
        old = subprocess.run(["git", "show", f"{ref}:{path}"],
                             capture_output=True, text=True).stdout
        new = open(path).read()
        name = path.split("/")[-1]

        if strip_docstrings(old) != strip_docstrings(new):
            print(f"✗ {name}: CODE CHANGED (not a prose-only edit)")
            bad = True
            continue

        lost_cites = sorted(set(CITE.findall(old)) - set(CITE.findall(new)),
                            key=str.lower)
        lost_warns = old.count(WARN) - new.count(WARN)
        note = []
        if lost_cites:
            note.append(f"citations gone: {', '.join(lost_cites)}")
        if lost_warns > 0:
            note.append(f"{lost_warns} ⚠ marker(s) gone")
        status = "✓" if not note else "!"
        if note:
            bad = True
        shrink = len(old.splitlines()) - len(new.splitlines())
        print(f"{status} {name}: code identical, -{shrink} lines"
              + ("  [" + "; ".join(note) + "]" if note else ""))
    sys.exit(1 if bad else 0)


main()
