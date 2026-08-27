# Session handoff — 2026-08-27 (ST Options, Custom, Combos — all human-clicked)

# 👉 YOU ARE HERE

Last FULL green suite: **2,921 passed, 1 skipped** (main PC, `qt-port`, 6m33s), run
after the last code change. The tree is clean and nothing is half-finished.

**Three tabs shipped this session and all three are human-clicked.** ST Options and
Custom emptied the rail; the Combos sub-tab closed the last thing hiding under Charms.

## 👉 NEXT: the Party / ST screen — and it is a DESIGN QUESTION, not a port

**`ui/gm.py` (610 lines) + `ui/adversaries.py` (489) ≈ 1,100 lines.** The only thing left
in the port, and the only one the settled tab layout does **not** decide, because it is a
second WINDOW rather than a tab. ⚠ **Ask before building.** The webapp's shape is a page;
whether the native app wants a window, a dialog, or something else has never been put to
the human.

⚠ **An `Adversary` is NOT a `Character` and must never become one** — a test asserts it.
`docs/status/adversary-roster.md` before touching that half.

## What shipped this session

| Thing | Where |
|---|---|
| The ST Options tab | `qt/storyteller.py` |
| The Custom tab — the last rail placeholder | `qt/custom.py` |
| Gear joined the Custom tab: list, delete AND a form (a REVERSAL) | `qt/custom.py`, `ui/view.py` |
| The Combos / Arrays sub-tab | `qt/combos.py` |
| Combo + Array mutations moved into the engine | `engine/combo_actions.py` |
| House-rule writes moved into the engine | `engine/house_rule_actions.py` |
| `custom_content.delete_gear` — it simply did not exist | `custom_content.py` |
| **`reload_custom_layer` never re-merged the gear catalogues** | `rules_db.py` |
| **`QCheckBox`, `QDialog`, `QPlainTextEdit` unstyled — all port-wide** | `qt/theme.py` |
| `tests/test_qt_theme.py` — pixels, because a QSS rule is invisible to tests | new |

Full write-ups: **`docs/plans/qt-port.md`** (all three tabs and every trap) and
**`docs/status/custom-content.md`** (the library, the gear form, the reversal).
Do not re-derive them.

## A decision was REVERSED this session — read before citing the old one

**Gear is authorable on the Custom tab** (human, 2026-08-27), reversing *"No authoring
form was needed: you tweak an item on a character and click once"* (2026-08-13). The old
flow made you **give a character an item in order to invent one**. **Both entry points
stay** — the Gear-tab button is retroactive, the Custom form deliberate, and both write
through `save_gear_row` so they cannot drift. `docs/status/custom-content.md` carries the
record and flags the superseded line at the top of the file.

## Not blocking, but not clicked either

Group 4's five per-splat **Charm surfaces**, carried from two sessions back (Eclipse
foreign tree, MA style panel, Alchemical submodules, the DB Immaculate banner, the
Jadeborn repeat), plus the POST-lock half of the variant chooser. Each was rendered
offscreen and each has test coverage of the behaviour.

⚠ **`ui/picker.py::variant_menu_detail` — the WEBAPP's variant panel — has still never
been rendered at all**, in a browser or anywhere else. The Qt panel is verified; its
webapp twin is not. It remains the least-verified code in the tree.

## The lesson this session kept re-teaching, three times over

**A defect one widget class over is still your defect.** Fixing `QPushButton:disabled`
did not generalise, and nothing prompted a check of its siblings — so `QCheckBox`, then
`QDialog` (a top-level window does NOT inherit the main window's palette) and
`QPlainTextEdit` were each found separately, by rendering and looking. **When you add a
rule for one widget class, add it for every interactive class in the QSS.**
`tests/test_qt_shell.py` now pins the list.

**And a QSS rule is invisible to the whole suite, so guard it by RENDERING.**
`test_qt_theme.py`'s first version compared whole-widget images with `!=` and **passed
against the exact defect it was named for** — Qt dims disabled TEXT by itself. Cropping
to the indicator was not enough either; the real gap was **7 of 255, and inverted for a
ticked box**. **Negative-control a rendering test by deleting the rule it guards.**

**The gap list was a lower bound SIX times out of six.** The last one — "the Combos
sub-tab, 423 lines" — turned out to be two systems, Combos *or* Arrays.

## And one about the click-through itself

**Scope it to what only the display can answer.** The first checklist went out with
eleven checks; the human asked whether all of it was necessary, and it was not. Cut to
four. **What a human adds is the class of defect that beats every offscreen check: a
control that is correct, tested and BELOW THE FOLD, and a shared style regressing a
surface that was already approved.** A long checklist spends the one resource that cannot
be automated on things that already were.

## No open rules questions

None of the three tabs introduced a rules interpretation. Every value, citation and note
comes from the existing presenters.

## Still deferred, still NOT gaps

The Mist numina and Cult Abyssals (both indefinitely), and the one martial-arts absence
(`enlightenment`). Training times are still a no.
