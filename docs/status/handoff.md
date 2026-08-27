# Session handoff — 2026-08-27 (ST Options shipped; TWO click-throughs now owed)

# 👉 YOU ARE HERE

Last FULL green suite: **2,857 passed, 1 skipped** (main PC, `qt-port`, 7m37s), run
after the last code change. The tree is clean and nothing is half-finished.

**ST Options is ported.** It is the seventh Qt tab and the first of the two remaining
rail placeholders. ⚠ **It is NOT human-clicked**, and neither is group 4's Charm work
from the previous session — **two click-throughs are owed, not one.**

## What shipped this session

| Thing | Where |
|---|---|
| The ST Options tab | `qt/storyteller.py` (new, 300 lines) |
| House-rule writes moved into the engine | `engine/house_rule_actions.py` (new) |
| `HouseRuleRow.inert` — a rule that cannot bite, dimmed not hidden | `ui/view.py` |
| `HOUSE_RULE_SCOPES` + `house_rule_setting_label` — one copy for both shells | `ui/view.py` |
| **`QCheckBox:disabled` — PORT-WIDE, every disabled checkbox looked live** | `qt/theme.py` |
| A sort that threw away the presenter's order, and a stray sort arrow | `qt/storyteller.py` |
| A column that elided while dead space sat beside it | `qt/storyteller.py` |
| The foreign-Charms note printed the caste ID ("and dawn is not one") | `ui/view.py` |
| `tests/test_qt_theme.py` — pixels, because a QSS rule is invisible to tests | new |

Full write-up: **`docs/plans/qt-port.md`**, section "ST Options — the seventh tab".
Do not re-derive it.

## 👉 NEXT: two click-throughs, then Custom

**1 — group 4's Charm surfaces**, still owed from the last session. Five surfaces
rendered offscreen and never touched:

- an **Eclipse with ST permission** switching the Splat dropdown and buying a foreign
  Charm (check the tree re-renders in the foreign splat's accent, and that buying does
  not snap it back to the native page);
- a **martial-arts tab** expanding the style panel and changing category;
- an **Alchemical** selecting Chemical Fog Generator, adding a submodule, and checking
  the two Essence-3 gases read as disabled;
- a **Dragon-Blooded** readout before and after picking a Dragon-style Charm;
- a **Jadeborn** buying a second Essence Satiation Method ("Add another");
- a **Solar with Resistance 5** on Environmental Hazard-Resisting Meditation — the
  variant chooser, both pre- and post-lock. ⚠ **The WEBAPP's version of this panel
  (`ui/picker.py::variant_menu_detail`) has never been rendered at all**, in a browser
  or otherwise. It is the least-verified thing in the tree.

**2 — ST Options**, new this session. Flip Magic for Everyone on a character with
Occult and watch the shell's bonus-point line move; lock and confirm every control
reads read-only; a God-Blooded's Inheritance select. ⚠ **And re-check Play and
Advantages** — the checkbox theme fix is port-wide and touches surfaces that were
already signed off.

**3 — then Custom**, then the Combos sub-tab, then Party. Custom gets the COLLECTION
layout; copy `qt/gear.py` or `qt/advantages.py`, never transliterate `ui/custom.py`.

## ⚠ What is left overall — the rail is STILL not the measure

**1 — one rail placeholder left.** `ui/custom.py` (576 lines).

**2 — the Combos sub-tab** (`ui/combos.py`, 423 lines), still a placeholder under
Charms. ⚠ Easy to miss because it is not on the rail.

**3 — the Party / ST screen has NO Qt counterpart at all.** `ui/gm.py` (610) +
`ui/adversaries.py` (489) ≈ 1,100 lines. A second WINDOW, not a tab, so the settled tab
layout does not decide its shape — an open design question, not a port.

**4 — the within-tab gaps: CLOSED.**

**NOT a gap:** the Play tab renders no Lunar **Renown** or **face** — neither does the
webapp's, so that is parity. Nor does the Qt Charm readout list per-issue lines: the
shell's details popover carries them (`main_window.py:297-330`).

**Parity limitation, deliberately not fixed:** the tab set is decided by NATIVE trees,
so an Eclipse whose own splat has no Arcanoi cannot reach foreign Arcanoi. The webapp
has the same limitation for the same reason.

## Decisions taken this session — do not relitigate

- **ST Options gets NO action toolbar.** The collection layout puts actions in one and
  this collection has none — the rules are fixed by the books, so there is nothing to
  add, buy or delete. Written into the module docstring so the absence reads as a
  decision rather than drift. This is not the layout being re-litigated per tab.
- **An inert rule is DIMMED, never hidden**, and `inert` is derived in the presenter
  rather than by matching a "No effect:" prefix on the note. A prose reword would
  otherwise silently un-dim every row.
- **A disabled checkbox that is CHECKED keeps a distinct look** (a filled MUTED square).
  Styling `::indicator:disabled` alone loses the tick, and a locked rule that is ON
  would read as OFF.

## The lesson this session adds

**Negative-control a rendering test by deleting the rule it guards.**
`test_qt_theme.py`'s first version compared whole-widget images with `!=` and passed
against the exact defect it was named for — Qt dims disabled TEXT by itself. Cropping to
the indicator was not enough either: the two drawings differ by antialiasing, so `!=`
still passed with the theme rules deleted. The real gap was **7 out of 255, and
inverted for a ticked box.** It took a brightness assertion, checked by deleting the
rules and watching it fail.

And the older lesson held for the fourth time: **the gap list was a lower bound.** ST
Options was listed as one placeholder module; the render turned up four defects, one of
them port-wide and older than this session's work.

## No open rules questions

Nothing new. The ST Options port introduced no rules interpretation — every value,
citation and note comes from `view.build_house_rules`, unchanged.

## Still deferred, still NOT gaps

The Mist numina and Cult Abyssals (both indefinitely), and the one martial-arts absence
(`enlightenment`). Training times are still a no.
