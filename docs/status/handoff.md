# Session handoff — 2026-08-27 (ST Options + Custom; the rail is EMPTY)

# 👉 YOU ARE HERE

Last FULL green suite: **2,900 passed, 1 skipped** (main PC, `qt-port`, 7m26s), run
after the last code change. The tree is clean and nothing is half-finished.

**Both remaining rail placeholders are gone.** ST Options and Custom are ported, and
**all of it is human-clicked** — *"No notes, everything looks good."*

⚠ **The rail being empty does NOT mean the port is done.** Two things are left and
neither is on it: the **Combos sub-tab** under Charms, and the **Party / ST screen**,
which has no Qt counterpart at all.

## What shipped this session

| Thing | Where |
|---|---|
| The ST Options tab | `qt/storyteller.py` |
| The Custom tab — the last rail placeholder | `qt/custom.py` |
| Gear joined the Custom tab: list, delete AND a form | `qt/custom.py`, `ui/view.py` |
| `custom_content.delete_gear` — it simply did not exist | `custom_content.py` |
| **`reload_custom_layer` never re-merged the gear catalogues** | `rules_db.py` |
| House-rule writes moved into the engine | `engine/house_rule_actions.py` |
| **`QCheckBox:disabled` — port-wide, every disabled checkbox looked live** | `qt/theme.py` |
| **`QDialog` + `QPlainTextEdit` unstyled — port-wide** | `qt/theme.py` |
| `tests/test_qt_theme.py` — pixels, because a QSS rule is invisible to tests | new |

Full write-ups: **`docs/plans/qt-port.md`** (both tabs and every trap) and
**`docs/status/custom-content.md`** (the library, the gear form, the reversal).
Do not re-derive them.

## 👉 NEXT: the Combos sub-tab

**`ui/combos.py`, 423 lines**, still a placeholder under Charms. ⚠ Easy to miss because
it is **not on the rail** — Combos is a Charms SUB-TAB in Qt and a top-level tab on the
webapp, deliberately (2026-08-21). Copy `qt/gear.py` or `qt/advantages.py`; never
transliterate `ui/combos.py`.

Then the **Party / ST screen** — `ui/gm.py` (610) + `ui/adversaries.py` (489) ≈ 1,100
lines. A second WINDOW, not a tab, so the settled tab layout does not decide its shape.
An open design question, not a port.

## A decision was REVERSED this session — read before citing the old one

**Gear is authorable on the Custom tab** (human, 2026-08-27), reversing *"No authoring
form was needed: you tweak an item on a character and click once"* (2026-08-13). The old
flow made you **give a character an item in order to invent one**. **Both entry points
stay** — the Gear-tab button is retroactive, the Custom form deliberate, and both write
through `save_gear_row` so they cannot drift. `docs/status/custom-content.md` carries the
record and flags the superseded line at the top of the file.

## Not blocking, but not clicked either

Group 4's five per-splat **Charm surfaces**, carried from the previous session (Eclipse
foreign tree, MA style panel, Alchemical submodules, the DB Immaculate banner, the
Jadeborn repeat), plus the POST-lock half of the variant chooser. Each was rendered
offscreen and each has test coverage of the behaviour, so this is a low-priority sweep
rather than an owed verification.

⚠ **`ui/picker.py::variant_menu_detail` — the WEBAPP's variant panel — has still never
been rendered at all**, in a browser or anywhere else. The Qt panel is verified; its
webapp twin is not. It remains the least-verified code in the tree.

## The lesson this session keeps re-teaching

**A defect one widget class over is still your defect.** Fixing `QPushButton:disabled`
last session did not generalise, and nothing prompted a check of its siblings — so
`QCheckBox`, `QDialog` and `QPlainTextEdit` were all found the same way, one at a time,
by rendering and looking. **When you add a rule for one widget class, add it for every
interactive class in the QSS.** `tests/test_qt_shell.py` now pins the list.

**And a QSS rule is invisible to the whole suite, so guard it by RENDERING.**
`test_qt_theme.py`'s first version compared whole-widget images with `!=` and **passed
against the exact defect it was named for** — Qt dims disabled TEXT by itself. Cropping
to the indicator was not enough either (antialiasing); the real gap was **7 of 255, and
inverted for a ticked box**. **Negative-control a rendering test by deleting the rule it
guards.**

## And one about the click-through itself

**Scope a click-through to what only the display can answer.** The ST Options checklist
went out with eleven checks; the human asked whether all of it was necessary, and it was
not. Most re-drove behaviour the new tests already assert. Cut to four, five minutes,
all clean. **What a human adds is the class of defect that beats every offscreen check:
a control that is correct, tested and BELOW THE FOLD, and a shared style regressing a
surface that was already approved.** A long checklist is not more rigour — it spends the
one resource that cannot be automated on things that already were.

## No open rules questions

Neither tab introduced a rules interpretation. Every value, citation and note comes from
the existing presenters.

## Still deferred, still NOT gaps

The Mist numina and Cult Abyssals (both indefinitely), and the one martial-arts absence
(`enlightenment`). Training times are still a no.
