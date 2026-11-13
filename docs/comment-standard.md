# Comment standard

Applies to all `*.py` files. Write comments and docstrings in Simplified Technical
English (`CLAUDE.md` §6).

## Keep

- **Docstring:** the input, the output, and the method that connects them. Nothing else.
- **Field comment:** a page citation. Add one short clause only if the name and the
  default value do not give the meaning.
- **Page citations:** `core p.104`, `PG pp.175-177`. If there is no page, write
  `human's ruling`, with no date.
- **⚠ traps:** a behavior that breaks if someone changes the code without knowing it. If
  a trap is inside narration, rewrite it as a ⚠ line. Do not delete it.

## Delete

- Dates, session notes, bug history ("used to", "found when", "the human reported").
- Reasons, alternatives, and design discussion. Put them in the commit message or in
  `docs/decisions/`. If necessary, leave a one-line pointer.
- Text that the default value already gives ("0 for every other splat", "unused by X").
- "Mirrors X" cross-references. If the link is important, a test enforces it.
- Book quotes when the code already holds the value. Keep a quote only if the exact
  words decide the interpretation.
- Text that restates the code.

## Verify a pass

Run `tools/prose_guard.py <baseline-ref> <paths…>`. It strips the docstrings, compares
the AST, and reports a lost page citation or ⚠. It also passes on a no-op, thus read the
diff.

⚠ The guard reports CODE CHANGED for comments inside string literals. Check these files
by hand: `qt/theme.py` (`/* … */` in the QSS f-string) and `server/db.py` (`--` in SQL
strings).

A package is done when this returns nothing:
`grep -rE '20[0-9]{2}-[0-9]{2}-[0-9]{2}' exalted_builder/<package> --include=*.py`
