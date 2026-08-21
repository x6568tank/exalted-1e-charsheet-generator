# Session handoff — 2026-08-21 (Advantages ported to Qt)

# 👉 YOU ARE HERE

**The full suite was NOT run to completion this session** (out of time). What WAS run,
green: `test_qt_advantages.py` (31 new), `test_qt_shell.py`, `test_qt_editor.py`,
`test_qt_charms.py`, `test_qt_sheet.py`, `test_view.py`, `test_merit_postlock.py`,
`test_backgrounds_splat.py`, and the whole `-k "advantage or merit or flaw or fetter or
passion or background"` slice (469 passed, 1 skipped). **First job at home:**

```
.venv/bin/python -m pytest -q     # last full-run baseline: 2,541 passed, 1 skipped
```

Expect roughly 2,581 — the baseline plus 31 Qt + 4 view + 5 advancement tests.

## What happened: milestone 3 — the Advantages tab is native

`exalted_builder/qt/advantages.py` fills the rail's placeholder: Backgrounds, Merits &
Flaws, and (for ghosts) Fetters and Passions, in both regimes. Full record:
`docs/plans/qt-port.md` "Milestone 3"; the tab's own file is
`docs/status/advantages-tab.md`.

**The two prep moves went in FIRST**, so no rules decision was copied into a second
widget — this is the "extract before you port" rule from milestone 2:

- **`view.default_merit_tier`** (+ `merit_tier_label`, `merit_option_label`) — the
  splat-aware default a fresh M&F row opens on. The Prodigy trap is now tested in
  `test_view.py`.
- **`advancement.gain_merit_or_flaw`** — the merit-vs-flaw side resolution and both of
  its refusals. Which of `buy_merit` / `gain_flaw` runs is what makes the XP positive or
  negative, so it is a rules decision, not layout. `ui/advantages.py` delegates to all
  four; that is what keeps the two shells from drifting.
- **`qt/catalogue.py`** — the native browse-before-you-choose dialog, same
  `(key, name, summary, full)` + `on_pick` contract as the web one, **reusable by Gear**.
  Its filter HIDES rows rather than removing them.

## ⚠ Not yet human-clicked

Everything above is tests + offscreen screenshots only. **The Advantages tab has not
been driven on the real display** — that is the next thing to do, and the milestone is
not "done" until it has been. What to look at: the Background rows (rung + Hearthstone
total under a Manse, the Demesne toggle), a Merit row's second control line, and the
post-lock gain/lose card.

## What the port had to decide for itself (all three are recorded in the plan)

- **The tab prints its own ISSUES only** — the shell's readout bar already carries the
  bonus-point total, and printing it here too showed the same sentence twice. Post-lock
  the line becomes XP available + debt.
- **Long printed prose is clamped, full text on the tooltip** (`_clamp`) — Qt has no CSS
  line-clamp and a Manse paragraph pushed every other row off the panel.
- **A merit row is TWO lines** — Qt has no flex-wrap, and a no-wrap row crushes its later
  children to slivers.

One shell fix fell out: `self.status` is now built BEFORE the pages (AdvantagesPage
derives its issue line during construction and `_refresh` writes to both readouts), and
the readout no longer opens on " · " post-lock.

## Known Qt gaps (unchanged by this milestone)

- **Ox-Body Technique + Deadly Beastman gifts**: the picker still needs the variant
  MENU. The mis-write is closed — `engine.charm_actions` refuses a package Charm from an
  ordinary toggle in both shells.
- Submodules (Alchemical), the Immaculate-vs-standard DB banner, the MA style panel, the
  foreign-charms splat dropdown, "Add another" for repeatable Charms.
- Edit's deferred panels: Training Camp & Calling, Colleges, Specialties, Permanent
  Resonance/Limit, Virtue Flaw, bonus health levels, Downtime.
- Rail placeholders still on the webapp: **Gear, Combos, Play, ST Options, Custom**.

## Next up: the Gear tab

Apply the milestone-2 question to it before porting — **does it need an engine
dispatcher first?** (Advantages' answer was no; Charms' was yes.) `qt/catalogue.py`
already exists for its pickers.

## ⚠ Where the branch lives (unchanged)

`qt-port` is checked out in the main directory; the `…-ds` worktree is gone. The branch
has **no upstream** and is unpushed.

## Still deferred, still NOT gaps
The Mist numina and Cult Abyssals (both indefinitely), and the one martial-arts absence
(`enlightenment`). Training times are still a no.
