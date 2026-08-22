# Session handoff — 2026-08-22 (milestone 6: the Play tab is native)

# 👉 YOU ARE HERE

Last FULL green suite: **2,710 passed, 1 skipped** (main PC, `qt-port`, 6m51s) at this
session's tip — a fresh run AFTER the last code change, not the one that was in flight
while `_pool_row` was rebuilt.

The tree is clean and nothing is half-finished. **`qt/play.py` shipped and was
human-clicked and approved on the real display** — first build, no rebuild.

## What shipped: milestone 6 — the Play tab

`exalted_builder/qt/play.py` (689 lines) replaces the rail's Play placeholder. Both of
the milestone's questions were answered before a line was written — `engine/play.py`
landed last session (`2ac4465`) and the layout was ruled on — so this was the widget and
nothing else.

**Toolbar over panels**, the ONE written exception to the collection layout: a tracker
has nothing to select. Two scrolling columns in a splitter — the tracker LEFT (health,
armour fatigue, Essence, temporary Willpower, Limit **or** Clarity, luck, the custom
Attribute + Ability pool), the roll list RIGHT — under `Clear damage` and
`Clear motes spent`.

⚠ The column order is the webapp's **reversed**, deliberately. Every other Qt tab puts
the interactive half left and the reference half right, and the tab should read like the
app it is in rather than like the page it came from.

`worst_penalty` moved from `ui/play.py` to `view.py` — the last row of the port plan's
extraction table, and the easy one. `ui/play.py` re-exports it because `ui/gm.py` reaches
it through that module by name.

Full write-up, with every trap: `docs/plans/qt-port.md`, milestone 6.

## The lessons this session bought

- **A word-wrapped QLabel needs an unbroken vertical layout chain to the top.**
  QBoxLayout does not propagate `heightForWidth` from a nested child layout, so the first
  `_pool_row` — a total in a column beside a nested QVBoxLayout — drew all sixty rows on
  top of each other. Anywhere text wraps, watch for a QHBoxLayout in the ancestry.
- **Screenshot only after the layout has SETTLED.** One `processEvents()` after `show()`
  catches the pre-layout pass, and it looks exactly like a real sizing bug — squeezed
  panels, clipped last lines, no scrollbar. Eight, and the same build is correct. Two of
  the "defects" I found that way were not real. ⚠ **The offscreen grab is still worth
  doing**: it is what caught the row overlap, which no test saw.
- **Species 2 of the house bug, in a field rather than a mechanism.** `PoolRow.note` is
  filled by `view.build_pool_sidebar` and was rendered by NO shell — a printed rider with
  zero readers, sitting there looking healthy. It is a row tooltip in Qt now.
- **Rendering must not create state.** `engineplay.play_state` writes a `PlayState` on
  first call, so the draw path reads `char.play or PlayState()` — otherwise merely
  OPENING the tab makes a never-played character save dirty. There is a test.

## ⚠ What is actually left — the rail is NOT the measure

Counted at the end of the session — the human asked *"ST Options & Custom are all that's
left?"* and immediately added *"And Combos, and Party."* **Two rail tabs, one sub-tab,
one whole window, and a list of within-tab gaps.** Written down because the RAIL shows
only the first of those four: a rail with no placeholders left will look finished while
Combos is empty, Party answers "not part of this milestone", and the tabs that are
"ported" are still missing panels.

**1 — the last two rail placeholders.** `ui/storyteller.py` (183 lines) and
`ui/custom.py` (576). Both get the COLLECTION layout — toolbar · sub-tab per category ·
sortable table · splitter with a detail pane. Copy `qt/gear.py` or `qt/advantages.py`;
never transliterate `ui/<tab>.py`.

**2 — the Combos sub-tab** (`ui/combos.py`, 423 lines) is still a placeholder in its new
home under Charms. ⚠ **It is easy to miss because it is not on the rail** — a rail with
no placeholders left will look finished while this is empty.

**3 — the Party / ST screen has NO Qt counterpart at all.** `ui/gm.py` (610) +
`ui/adversaries.py` (489) ≈ 1,100 lines, and the toolbar's `Party` button still answers
"not part of this milestone". This is a second WINDOW, not a tab, so the settled tab
layout does not decide its shape — that is an open design question, not a port.

**4 — the within-tab gaps, which are what decide whether the native app can replace the
webapp:**

- **Ox-Body Technique + Deadly Beastman gifts**: the picker still needs the variant MENU.
  The mis-write is closed — `engine.charm_actions` refuses a package Charm from an
  ordinary toggle in both shells.
- Submodules (Alchemical), the Immaculate-vs-standard DB banner, the MA style panel, the
  foreign-charms splat dropdown, "Add another" for repeatable Charms.
- Edit's deferred panels: Training Camp & Calling, Colleges, Specialties, Permanent
  Resonance/Limit, Virtue Flaw, bonus health levels, Downtime.

**NOT a gap:** the Play tab does not render Lunar **Renown** or **face** — neither does
the webapp's, so that is parity. Both are wholly Storyteller-adjudicated (`PlayState`'s
docstring).

## Next up — group 4, the within-tab gaps (the human's call, 2026-08-22)

**Close the gaps in the tabs that already shipped, BEFORE porting another tab.** Not ST
Options, not Custom, not Party — those wait.

⚠ **Nothing will remind you these exist.** Every tab in group 4 is ported, human-clicked
and green; the rail shows no placeholder and the suite reports no failure. That is the
whole reason this went to the top of the list rather than the bottom, and it is the
condition on which the native app can *replace* the webapp instead of sitting beside it.

The list is group 4 above. Suggested order, cheapest and most load-bearing first:

1. **The Ox-Body / Deadly Beastman variant MENU** in the Charm picker — the only one of
   these with a closed bug behind it (`engine.charm_actions` already refuses a package
   Charm from an ordinary toggle in both shells, so the mis-write cannot happen; what is
   missing is the way to make the RIGHT pick).
2. **Edit's deferred panels** — Training Camp & Calling, Colleges, Specialties, Permanent
   Resonance/Limit, Virtue Flaw, bonus health levels, Downtime. Seven panels, and
   Specialties and Permanent Resonance both have rulings attached (see
   `docs/status/edit-xp-merge.md` and the Limit panel in `qt/play.py`, which shows
   permanent Resonance READ-ONLY and points at Traits for the edit — that pointer is
   currently to a panel that does not exist).
3. **The per-splat Charm surfaces** — Alchemical submodules, the Immaculate-vs-standard
   DB banner, the MA style panel, the foreign-charms splat dropdown, "Add another" for
   repeatable Charms.

⚠ **Audit before building.** The gap list was assembled milestone by milestone and has
never been re-derived against the webapp. Diff each shipped Qt tab against its
`ui/<tab>.py` counterpart before trusting the list to be complete — the same reasoning
that put "a fuzzy gap count is a LOWER bound on the work" in `CLAUDE.md`.

**After group 4:** ST Options, then Custom, then Combos, then Party.

## A live bug in shipped code, still unmigrated (carried from last session)

`set_weapon` / `set_armor` used to drop an artifact's `acquired` channel, re-charging the
p.131 budget for something Resources had already paid for. **The routes are all closed**
— `gear_actions.set_acquired` is the only writer in either shell — but there is **no
migration**: a save already damaged has `acquired` sitting at `background` on disk. Worth
a look if you have a character with a cash-bought artifact weapon.

## No open questions

No rules questions. The layout question is closed and its one exception is written down
in `CLAUDE.md`, `docs/plans/qt-port.md` and this file.

## Still deferred, still NOT gaps

The Mist numina and Cult Abyssals (both indefinitely), and the one martial-arts absence
(`enlightenment`). Training times are still a no.
