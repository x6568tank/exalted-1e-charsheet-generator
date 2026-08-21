# Session handoff — 2026-08-21 (the left-rail shell; Edit splits into Identity + Traits)

# 👉 YOU ARE HERE

**GREEN — 2,482 passed, 3 skipped, 1 warning** (this machine, 2026-08-21).

```
.venv/bin/python -m pytest -q     # expect: 2,482 passed, 3 skipped, 1 warning
```

⚠ The 1 SKIP is conditional and healthy; the 1 warning is the 71-entry M&F deferral
(Godblooded chapter markdown absent on this machine) — neither is a failure.

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

- **Ox-Body Technique + Deadly Beastman gifts**: the Qt `_toggle_charm` would
  mis-write an Ox-Body buy to `char.charms` (a latent bug) — it needs the variant menu.
- Submodules (Alchemical), the Immaculate-vs-standard DB banner, the MA style panel,
  the foreign-charms splat dropdown, "Add another" for repeatable Charms.
- Edit's deferred panels: Training Camp & Calling, Colleges, Specialties, Permanent
  Resonance/Limit, Virtue Flaw, bonus health levels, Downtime (a disabled stub).

## Next up: the Advantages tab

The human is clearing context to port the **Advantages** tab (Backgrounds + Merits &
Flaws). The shell has a placeholder Advantages rail item to fill.

## Still deferred, still NOT gaps
The Mist numina and Cult Abyssals (both indefinitely), and the one martial-arts
absence (`enlightenment`). Training times are still a no.
