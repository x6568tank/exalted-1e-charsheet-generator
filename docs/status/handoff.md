# Session handoff — 2026-08-22c (Edit is done, clicked and approved)

# 👉 YOU ARE HERE

Last FULL green suite: **2,776 passed, 1 skipped** (main PC, `qt-port`, 7m01s), run
after the last code change. The tree is clean and nothing is half-finished.

**Group 4's Edit work is DONE, human-clicked and approved.** All seven deferred panels
ship, the click found three more defects and they are fixed, and the Traits redesign
question was asked, spiked and answered. There is no half-finished thread to pick up.

## What shipped this session

| Thing | Where |
|---|---|
| Edit's seven deferred panels | `qt/editor.py`, `qt/main_window.py` (Downtime) |
| Three click-through defects | popover sizing/teardown, combo placeholder, one-column camp |
| Bonus points → chargen-only in the popover | `qt/main_window.py` |
| Specialties fold into their Abilities | `qt/editor.py`, `view.specialty_groups` |
| The Gear/Advantages trees stop rendering white | `qt/theme.py::qss` |
| Four new engine modules | `camp.py`, `camp_actions.py`, `health_actions.py`, `labels.py` |

Full write-ups: **`docs/plans/qt-port.md`** (the port, the click-through, the declined
redesign) and **`docs/status/edit-xp-merge.md`** (specialties). Do not re-derive them.

## 👉 NEXT: the rest of group 4 — the per-splat Charm surfaces

Still the human's stated order: **close the within-tab gaps before porting another
tab.** Edit's are closed; the Charm ones are not.

- Alchemical **submodules**
- the **Immaculate-vs-standard DB banner**
- the **martial-arts style panel**
- the **foreign-charms splat dropdown**
- **"Add another"** for repeatable Charms

⚠ **Audit before building, and click before believing.** This list has never been
re-derived against the webapp. Both previous items on it turned up defects that were on
no list at all — a stale shell readout, a `reload()` that never pinged the shell, a
`_combo` degrading enum keys — and then the click-through found three more that no test
saw. **Diff `qt/charms.py` against `ui/picker.py` AND against its sibling Qt pages'
constructor signatures first.**

**After group 4:** ST Options, then Custom, then Combos, then Party.

## ⚠ What is left overall — the rail is STILL not the measure

**1 — the last two rail placeholders.** `ui/storyteller.py` (183 lines) and
`ui/custom.py` (576). Both get the COLLECTION layout. Copy `qt/gear.py` or
`qt/advantages.py`; never transliterate `ui/<tab>.py`.

**2 — the Combos sub-tab** (`ui/combos.py`, 423 lines), still a placeholder under
Charms. ⚠ Easy to miss because it is not on the rail.

**3 — the Party / ST screen has NO Qt counterpart at all.** `ui/gm.py` (610) +
`ui/adversaries.py` (489) ≈ 1,100 lines. A second WINDOW, not a tab, so the settled tab
layout does not decide its shape — an open design question, not a port.

**4 — the within-tab gaps.** Edit's are CLOSED; the Charm ones above remain.

**NOT a gap:** the Play tab renders no Lunar **Renown** or **face** — neither does the
webapp's, so that is parity. Both are wholly Storyteller-adjudicated.

## Decisions taken this session — do not relitigate

- **The Traits tab keeps its card layout.** Asked, spiked six ways (including a
  QTreeWidget collection exactly like Gear's), declined: *"the way it is right now works
  best for this information specifically."* **Identity + Traits are now the SECOND
  written exception to the one-tab-layout rule**, alongside Play. `spikes/qt_traits/` is
  the record of what lost.
- **Bonus points are a chargen surface only.** The readout bar already dropped the line
  post-lock; the popover now agrees with it.
- **Backwards compatibility with old saves is not a concern.** No migrations, no schema
  versions, no compat shims without asking. This closed the `acquired`-channel item that
  had been carried for two sessions — it is not a thing to do.
- **Shared logic that the engine cannot reach moves INTO the engine.** `engine/` may not
  import `ui/`, so when `camp_actions` needed `build_camp_view` the view moved down to
  `engine/camp.py` (+ `engine/labels.py`) and `ui/view.py` re-exports every name. Chosen
  over a `ui/`-side actions module or a duplicate.

## The lesson this session keeps re-teaching

**An ancestor stylesheet beats a set palette, every time.** Three disguises now: a
`QTextEdit` in a `_Panel`, the Gear/Advantages **trees rendering white across two
shipped human-clicked milestones**, and small buttons going invisible on a card. If a
widget class is not named in `qt/theme.py::qss`, assume it is unstyled. **No test sees
any of this — the offscreen grab is what caught all three.**

## No open questions

No rules questions. Everything this session came from `engine.validate`,
`engine.elder`, `engine.derive` and the existing presenters; the only calls needed were
design ones, and the human made them.

## Still deferred, still NOT gaps

The Mist numina and Cult Abyssals (both indefinitely), and the one martial-arts absence
(`enlightenment`). Training times are still a no.
