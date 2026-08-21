# Session handoff — 2026-08-21 (the left-rail shell; Edit splits into Identity + Traits)

# 👉 YOU ARE HERE

**GREEN — 2,541 passed, 1 skipped, 1 warning** (2026-08-21, the main checkout, 7m00s).

```
.venv/bin/python -m pytest -q     # expect: 2,541 passed, 1 skipped, 1 warning
```

⚠ The 1 SKIP is conditional and healthy; the 1 warning is the 71-entry M&F deferral —
neither is a failure. **The Godblooded `CH 4 - Spirit Charms.md` IS present here now
and the deferral is still 71**, so that chapter is not the one the test wants. That is
pre-existing and unchased, not something the port broke.

⚠ **Without the optional `qt` extra the count drops by 72 and four modules SKIP** —
that is the `importorskip` working, not tests going missing.
`.venv/bin/pip install -e '.[qt]'` (already done here).

## ⚠ Where the branch lives changed (2026-08-21)

`qt-port` is now checked out in the **main** directory
(`/home/gil/Projects/exalted-1e-charsheet-generator`); the `…-ds` worktree that held it
was removed. Its `images/` was diffed first and the three chapters it uniquely held —
Dragon Kings CH 4, Godblooded Spirit Charms CH 4, Mountain Folk CH 6 — were copied
across and checksum-verified. **Any doc still pointing at `-ds` is stale**; the two
that did (`plans/content-completeness.md`, this file) are fixed.

`qt-port` has **no upstream** and is unpushed (9 commits). `origin` holds only `main`.

## What happened: the shell is now the approved spike layout

The `spikes/qt_edit/` layout — a left rail of app tabs, a readout bar, a bottom status
strip — went from prototype to the REAL app (human-clicked and approved). Full record:
`docs/plans/qt-port.md` "Milestone 2".

- **Shell** (`qt/main_window.py`): the top QTabWidget became a **left rail**
  (`QListWidget#appRail`, accent-selected) over a stack. A **readout bar**
  (budget · validation) whose **"≡ details"** opens a popover holding the validation
  issues + bonus-point breakdown + (post-lock) the Experience card + ledger. A
  **bottom status strip** (Willpower · pools · Soak). The old Edit-page side column is
  gone — its content lives in the popover.
- **Edit split** (`qt/editor.py`): `EditPage` → **`IdentityPage`** (name/anima,
  structural selectors, free-fill biography, caste info) + **`TraitsPage`** (favoured
  chips, Attributes/Abilities/Crafts/Virtues/Essence, the read-only Charm & Spells
  count), sharing an `_EditorPage` base.
- **Bio fields** (`models/character.py`): ten `str = ""` fields (sex, age, eye/hair/
  skin colour, height, weight, description, backstory, notes) — old saves load
  unchanged; they print on the PDF sheet's header. ⚠ **The NiceGUI web app's Identity
  does NOT expose them yet** (deferred by the human 2026-08-21).

## ⚠ What the shell work taught (re-bites in the Advantages port)

- **A QTextEdit inside a `_Panel` renders the card shade no matter what** — the
  panel's QSS forces the stylesheet renderer onto descendants, beating the window QSS
  AND a set palette. The only fix is an inline stylesheet ON the widget.
- **The input shade must be a real step off the card** — `INPUT` is now `#52525c`;
  the old `#47474f` read as the same shade as the card.
- **`QTextEdit.textChanged` carries no argument** (QLineEdit's does).
- **The rail's `currentRowChanged` handler must call `stack.setCurrentIndex`.**

All in `docs/plans/qt-port.md`.

## Known Qt gaps (from the NiceGUI gap audit — not this milestone's scope)

- **Ox-Body Technique + Deadly Beastman gifts**: the Qt picker still needs the variant
  MENU (the chooser UI). The latent MIS-WRITE is closed — `engine.charm_actions`
  refuses a package Charm from any ordinary toggle, in both shells, so until the menu
  exists a click says "bought as a package" instead of corrupting `char.charms`.
- Submodules (Alchemical), the Immaculate-vs-standard DB banner, the MA style panel,
  the foreign-charms splat dropdown, "Add another" for repeatable Charms.
- Edit's deferred panels: Training Camp & Calling, Colleges, Specialties, Permanent
  Resonance/Limit, Virtue Flaw, bonus health levels, Downtime (a disabled stub).

## The shared-purchase extraction (2026-08-21, after the shell)

`engine/charm_actions.py` — the `thaum_actions` treatment applied to Charms, spells,
Ox-Body and the Beastman Gifts. Both pickers had hand-rolled the lock dispatch, the
guards and the message strings; the Ox-Body mis-write above was the first drift, and
Advantages would have been the third copy. Both shells are now notification wrappers
(`_act`) over one dispatcher. 13 tests in `tests/test_charm_actions.py`.

⚠ **Do the same BEFORE porting a purchase surface, not after.** The extraction is a
day's work when there is one copy and a week's archaeology when there are three.

Two smaller things it swept up: no shell calls `validate._repeatable_purchase_cap`
(a leading-underscore engine private) any more, and the "once per <unit> of <trait>"
wording derives its unit from `validate.repeatable_cap_unit` in one place.

**The Qt tests no longer take the suite down with them.** All four `test_qt_*.py`
`importorskip("PySide6")` — the `qt` extra is optional, and a bare import of it was a
COLLECTION ERROR (the whole run dies, not just those tests) on any machine without it.
Verified both ways: 72 pass with the extra, 4 clean skips without.

## Next up: the Advantages tab

The human is clearing context to port the **Advantages** tab (Backgrounds + Merits &
Flaws). The shell has a placeholder Advantages rail item to fill.

### ⚠ Read this before porting it — Advantages is NOT shaped like Charms

The obvious move after `charm_actions` is "extract an `advantages_actions.py` first."
**Checked 2026-08-21 against `ui/advantages.py`, and that is the wrong answer** — the
duplication risk here is a different shape, and building a dispatcher it does not need
would be busywork:

- **There is no lock-toggle to extract.** Charms had ONE control that meant "pick" or
  "buy" depending on the lock, which is what made a hand-copied dispatch dangerous.
  Advantages has **two separate panels**: chargen row editors, and `_play_merits` /
  the Fetter and Passion play cards.
- **The post-lock side is already in the engine.** `buy_merit`, `gain_flaw`,
  `drop_merit`, `raise_fetter`, `add_fetter`, `shift_fetter`, `shift_passion` all live
  in `engine/advancement.py`, priced and logged. The widget only wraps them in `_do`.
- **The pre-lock side has no rules in it.** `add_bg` / `remove_bg` / `remove_merit` are
  `list.append` and `del`. There is nothing to share.

What DOES need moving before a second shell copies it — small, widget-resident
decisions that are rules or presentation, not layout:

- **`_default_tier`** — "the first tier this SPLAT may choose, not merely the first
  authored." It already carries a ⚠: Prodigy's menu leads with `favored`, which four
  splats are barred from, so opening on the first authored tier hands a Solar a row
  that flags itself immediately. `validate.merit_tiers_available` does the work; the
  choose-the-default wrapper belongs in `view.py`.
- **`_gain_mf`'s side resolution** — an `either` entry needs the player to say which
  side, and a Flaw PAYS the character rather than costing. That branch plus its two
  refusal messages is the one genuinely rules-shaped thing in the widget.

⚠ And the standing trap that outranks all of the above: **no module outside
`engine/merits.py` may name a Merit id** — a test greps for it. Add a `MeritEffects`
FIELD, never an allowlist, and that applies to the Qt widgets exactly as it does to
the NiceGUI ones.

## Still deferred, still NOT gaps
The Mist numina and Cult Abyssals (both indefinitely), and the one martial-arts
absence (`enlightenment`). Training times are still a no.
