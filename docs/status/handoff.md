# Session handoff — 2026-08-21 (Advantages clicked through; Charms tab made instant)

# 👉 YOU ARE HERE

Suite green and measured: **2,597 passed, 1 skipped** (main PC, `qt-port`). The branch is
**3 commits ahead of where the session started, no upstream, unpushed.**

Nothing is half-finished. Pick up at **the Gear tab** (milestone 4).

## What happened

**Milestone 3 is now human-clicked and approved** — the deferral the last handoff opened
is closed. Driving it on the real display found three things, all fixed and committed:

1. **The M&F and Background pickers didn't let you buy.** They did, technically: picking
   an entry painted its tier/side/points controls onto a card **below the fold**, so the
   dialog closed and nothing visibly happened. Buying now happens **inside the catalogue
   dialog**, for every picker that has a choice to make.
2. **Selecting a second catalogue entry painted over the first** — my bug, from (1).
   `_clear_extras` swept only widgets and the controls are nested layouts.
3. **The description printed twice**, and long summaries scrolled rows off the screen.

Full write-up: `docs/status/advantages-tab.md`. Commit `0d82513`.

**The Charms tab's "notable loading delay" was not the trees.** It was 190,859
`charm_matches_splat` calls per build — three catalogue-scanning helpers called from
inside loops over that same catalogue. A per-build memo took it **0.791s → 0.099s**
("Instant now"). Write-up in `docs/plans/qt-port.md`; commit `999abd4`.

## The two lessons worth carrying into Gear

- ⚠ **A control can be correct, reachable, fully tested — and nowhere near the thing it
  configures.** That was defect (1), and *every offscreen test passed*. A screenshot test
  would have passed too. Gear, Combos and Play all have pickers. `qt/catalogue.py` now
  carries the answer: `extras` + `confirm` hooks, with all game logic staying in the
  caller (the dialog still cannot tell a Merit from a Flaw, and must not learn to).
- ⚠ **A teardown sweep must recurse into nested layouts** — `item.widget()` is `None` for
  a `QLayout`. This has now bitten **twice** (`_clear_lay`, then `_clear_extras`). Copy
  the recursive shape; don't write a fresh loop. **Test it by thrashing the rebuild and
  counting live descendants** — a single rebuild passes while leaking.

## No open rules questions

The one that was outstanding is **ruled and implemented**: a variable-cost Merit/Flaw
**opens at 1 point, never 0** (human, 2026-08-21). At 0 it priced to nothing, so
confirming added a row that neither cost nor paid — a purchase that looked made and did
nothing. `qt/advantages.py::_mf_purchase_block`. ⚠ The opening value is seeded into the
pending-purchase STATE as well as the spinner, because the confirm button prices the
state, not the widget.

## Next up: the Gear tab

Apply the milestone-2 question first — **does it need an engine dispatcher extracted?**
(Advantages' answer was no; Charms' was yes.) `qt/catalogue.py` is ready for its pickers
and now supports in-dialog configuration, which Gear wants for quantities and attunement.

## Known Qt gaps (unchanged)

- **Ox-Body Technique + Deadly Beastman gifts**: the picker still needs the variant MENU.
  The mis-write is closed — `engine.charm_actions` refuses a package Charm from an
  ordinary toggle in both shells.
- Submodules (Alchemical), the Immaculate-vs-standard DB banner, the MA style panel, the
  foreign-charms splat dropdown, "Add another" for repeatable Charms.
- Edit's deferred panels: Training Camp & Calling, Colleges, Specialties, Permanent
  Resonance/Limit, Virtue Flaw, bonus health levels, Downtime.
- Rail placeholders still on the webapp: **Gear, Combos, Play, ST Options, Custom**.

## Still deferred, still NOT gaps

The Mist numina and Cult Abyssals (both indefinitely), and the one martial-arts absence
(`enlightenment`). Training times are still a no.
