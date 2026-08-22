# Session handoff — 2026-08-22 (group 4 begins: the variant-menu chooser)

# 👉 YOU ARE HERE

Last FULL green suite: **2,729 passed, 1 skipped** (main PC, `qt-port`, 7m12s), run
after the last code change. The tree is clean and nothing is half-finished.

**Group 4's first item shipped and is human-clicked and approved** — the Ox-Body /
Deadly Beastman variant menu in the Qt Charm picker. The click found two defects; both
are fixed and re-clicked. Full write-up: `docs/plans/qt-port.md`, "Group 4 … item 1".

## What shipped

`view.build_package_menu` / `package_menu_kind` / `prune_package_selection` — one
presenter for both package Charms — plus `CharmsPage._build_package_dialog`, one dialog
that draws both. The web picker's Gift chooser now runs the same two functions and its
local `_blocked`/`_prune` are gone, so the cascade cannot live in one shell again.

⚠ **`CharmVariant.max_purchases` is 1 for every Ox-Body variant and means nothing
there** — a repeat purchase picks a variant again, same or different. The taken/max rule
is Gifts-only; applying it to both greys the whole Ox-Body menu out after one purchase
while every Gift-side test stays green.

## The lessons this session bought

- **A rebuild under the click sends a QScrollArea to the bottom.** Deleting the focused
  checkbox hands focus on, and the scroll area follows it. Fixed by shape: a pick changes
  no row's EXISTENCE, so it syncs in place; a full rebuild is reserved for a buy or a
  remove. **The test asserts widget IDENTITY survives a pick** — asserting the enabled
  states would have passed straight over the bug.
- **`CharmsPage` was the one page the shell built without `on_change`**, so nothing bought
  on the Charms tab ever moved the shell's top readout bar. Species 2 of the house bug:
  the mechanism existed, every sibling page used it, and the tab's own local readout
  updated fine — which is what made the missing half invisible. ⚠ **When a page is added
  to the shell, its hook set is a contract with the sibling pages; diff against them.**
- **A hook belongs in a wrapper when the function it guards has two exits.**
  `_update_readout` now wraps `_draw_readout` for exactly that reason.
- The **offscreen grab** earned its keep a second milestone running: Deadly Beastman's
  eleven-line description pushed every pick off the dialog's first screen. No test sees
  that.

## ⚠ What is actually left — the rail is NOT the measure

Unchanged from last session except item 4's first line. **Two rail tabs, one sub-tab, one
whole window, and the within-tab gaps.** The RAIL shows only the first: a rail with no
placeholders left will look finished while Combos is empty, Party answers "not part of
this milestone", and the ported tabs are still missing panels.

**1 — the last two rail placeholders.** `ui/storyteller.py` (183 lines) and
`ui/custom.py` (576). Both get the COLLECTION layout — toolbar · sub-tab per category ·
sortable table · splitter with a detail pane. Copy `qt/gear.py` or `qt/advantages.py`;
never transliterate `ui/<tab>.py`.

**2 — the Combos sub-tab** (`ui/combos.py`, 423 lines) is still a placeholder in its new
home under Charms. ⚠ **It is easy to miss because it is not on the rail.**

**3 — the Party / ST screen has NO Qt counterpart at all.** `ui/gm.py` (610) +
`ui/adversaries.py` (489) ≈ 1,100 lines, and the toolbar's `Party` button still answers
"not part of this milestone". This is a second WINDOW, not a tab, so the settled tab
layout does not decide its shape — an open design question, not a port.

**4 — the within-tab gaps, which are what decide whether the native app can replace the
webapp:**

- ~~Ox-Body Technique + Deadly Beastman gifts: the picker needs the variant MENU.~~
  **DONE and human-clicked, 2026-08-22.**
- Submodules (Alchemical), the Immaculate-vs-standard DB banner, the MA style panel, the
  foreign-charms splat dropdown, "Add another" for repeatable Charms.
- Edit's deferred panels: Training Camp & Calling, Colleges, Specialties, Permanent
  Resonance/Limit, Virtue Flaw, bonus health levels, Downtime.

**NOT a gap:** the Play tab does not render Lunar **Renown** or **face** — neither does
the webapp's, so that is parity. Both are wholly Storyteller-adjudicated.

## Next up — the rest of group 4 (the human's call, 2026-08-22)

**Close the gaps in the tabs that already shipped, BEFORE porting another tab.** Not ST
Options, not Custom, not Party — those wait.

⚠ **Nothing will remind you these exist.** Every tab in group 4 is ported, human-clicked
and green; the rail shows no placeholder and the suite reports no failure.

Remaining order, cheapest and most load-bearing first:

1. **Edit's deferred panels** — seven of them. Specialties and Permanent Resonance both
   have rulings attached (`docs/status/edit-xp-merge.md`, and the Limit panel in
   `qt/play.py` shows permanent Resonance READ-ONLY and points at Traits for the edit —
   **that pointer is currently to a panel that does not exist**).
2. **The per-splat Charm surfaces** — Alchemical submodules, the Immaculate-vs-standard
   DB banner, the MA style panel, the foreign-charms splat dropdown, "Add another" for
   repeatable Charms.

⚠ **Audit before building, and this session is why.** The gap list was assembled
milestone by milestone and has never been re-derived against the webapp — the stale top
bar was in none of its entries, and it was a shipped, human-clicked, fully green tab
missing a hook every sibling page had. **Diff each shipped Qt tab against its
`ui/<tab>.py` counterpart AND against its sibling Qt pages' constructor signatures**
before trusting the list to be complete.

**After group 4:** ST Options, then Custom, then Combos, then Party.

## A live bug in shipped code, still unmigrated (carried from last session)

`set_weapon` / `set_armor` used to drop an artifact's `acquired` channel, re-charging the
p.131 budget for something Resources had already paid for. **The routes are all closed**
— `gear_actions.set_acquired` is the only writer in either shell — but there is **no
migration**: a save already damaged has `acquired` sitting at `background` on disk. Worth
a look if you have a character with a cash-bought artifact weapon.

## No open questions

No rules questions. This work needed no new rules call: every number came from
`engine.validate` and the two Charms' own `variants` data.

## Still deferred, still NOT gaps

The Mist numina and Cult Abyssals (both indefinitely), and the one martial-arts absence
(`enlightenment`). Training times are still a no.
