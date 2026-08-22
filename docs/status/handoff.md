# Session handoff — 2026-08-21 (Gear ported; Combos moved under Charms)

# 👉 YOU ARE HERE

Suite green and measured: **2,659 passed, 1 skipped** (main PC, `qt-port`, 7m58s). The
branch is **4 commits ahead of where the session started, no upstream, unpushed.**

Nothing is half-finished. **Milestone 4 is human-clicked and approved** — including the
Gear rebuild below. Pick up at **milestone 5, the Play tab**.

## What happened

**Milestone 4 shipped: the Gear tab is native, and Combos moved under Charms.** Full
write-up in `docs/plans/qt-port.md`; the Gear-specific half is also in
`docs/status/gear-and-inventory.md`.

The milestone-2 question ("does this surface need an engine dispatcher extracted?") was
asked of Gear first and came back **yes, emphatically** — unlike Advantages.
`engine/gear_actions.py` now owns what a catalogue re-pick carries across, what an
artifact grants, and which channel stamps a purchase. `ui/gear.py` went **947 → 650
lines** and both shells call the same code.

## ⚠ The extraction found a live bug in shipped code

`set_weapon`/`set_armor` REPLACE the row with a catalogue copy, carrying the player's
own fields across by a hand-written list. That list carried `from_artifact` because a
comment warned about it — and **never knew `acquired` existed**. So re-picking a
cash-bought artifact weapon's own name from its own dropdown reset it to `background`
and charged the p.131 budget for something Resources had already paid for:

```
budgeted before re-pick: []
budgeted after  re-pick: ['Daiklave']
```

**This affects the shipped webapp, not just the port**, and the fix is in shared code,
so the webapp is fixed too. It is worth a moment of your attention: the fix is not "add
`acquired` to the list" but `_owned_fields`, the complement of `_catalogue_stats`, both
derived from the two pydantic models — because what a field-by-field copy leaves out is
exactly what gets silently discarded.

**The reusable one-liner:** *when code copies one model into another field by field,
derive the field set from the models. A hand-written list documents the fields someone
thought of.*

**Checking the neighbouring paths found two more routes to the same defect**, and both
are now closed (`docs/status/gear-and-inventory.md` has the full three):
`grant_gear` did not copy the channel onto the stat line it created, and switching the
channel afterwards left that stat line on the old one. Both are invisible while the pair
is linked — `artifact_items` merges them and reads the artifact's channel — and both
surface the moment the artifact is deleted and its stat line is orphaned.
`gear_actions.set_acquired` is now the only way either shell writes the field.

⚠ **The negative control is the part worth remembering.** A "fix" that made every orphan
uncharged would have passed both new tests and silently broken the documented ruling that
a genuinely Background-funded orphan **is** still charged — *visible rather than free*.
That control is `test_a_background_funded_orphan_is_still_charged`.

## Combos under Charms — and a negative control that went stale

Cheap, because the Combos page had never been ported: this was a placement decision, not
a move. It is a **placeholder in its new home**; the surface is still on the webapp.

Two things worth knowing before touching the shell:

- **The two shells now have different tab sets, deliberately.**
  `_visible_rail_tabs` *discards* the presenter's answer about Combos rather than
  changing the presenter — `view.visible_tabs` is still exactly right for the webapp,
  where Combos stays top-level.
- ⚠ **`test_shell_hides_combos_for_a_ghost` went stale the instant the rail entry
  vanished.** With nothing to hide it passed for every splat and proved nothing. It now
  asserts on the ghost's Charms *sub-tabs*, with `"Arcanoi" in subtabs` as the positive
  control that the tab bar was built at all. Caught only because the change was made
  deliberately — this is the rot CLAUDE.md warns about, in the wild.

## ⚠ Gear was built twice, and the second build is the lesson

The first Gear tab was the NiceGUI page **transliterated**: a Buy button floating
mid-page with an explanatory sentence beside it, accordion "Edit" expanders, and a stack
of cards in a scroll area. Every test passed. The human's verdict on seeing it: *"the
page as a whole is a copy of the NiceGUI's look."* They were right, and the plan had
predicted it in as many words — *"a port attempted as a mechanical translation will
produce something that works and feels wrong."*

**The rule this bought, and it governs Play / ST Options / Custom: a new Qt surface
copies `qt/charms.py`'s LAYOUT, not `ui/<tab>.py`'s.** Toolbar for actions, table with a
header for lists, splitter with a detail pane for the selected thing. Concretely, what
changed on the rebuild:

| Web idiom | Native replacement |
|---|---|
| Buy button floating in the content | a toolbar (`Buy…`, `+ Artifact`, filter, search) |
| Filter pills | a `Show:` dropdown carrying live counts |
| Accordion "Edit" expanders | select a row, edit in the detail pane |
| `QLabel` rows in an HBox | `QTreeWidget`, sortable, five real columns |
| Card stack in one scroll | splitter; Prices became its own sub-tab |

Two things the rebuild fixed that the accordion had hidden:

- **The stat grid now wraps at three pairs per row.** Thirteen weapon stats on one line
  is the "no-wrap crushes later children to slivers" trap the Advantages merit rows
  already paid for once.
- ⚠ **Re-optioning the filter combo emits `currentIndexChanged`**, so without blocking
  signals the filter reset to "All" on every table rebuild — the filter was literally
  un-keepable while editing. `test_the_filter_survives_a_table_rebuild` pins it.

## Next up: milestone 5, the Play tab

Ask the milestone-2 question first — Play's answer is **not** obvious, since
`ui/play.py` still holds the PlayState mutators that tier 3 of the `ui/` audit wants in
`engine/`. ⚠ **decision 0006**: if they land in an `engine/play.py`, play-state must stay
unreachable from validation.

Then ST Options and Custom. All three are unported, and each will be either a
**collection** (table + detail, like Gear and Charms) or a **form** — see the open
question below.

## Known Qt gaps (unchanged except Gear)

- **Ox-Body Technique + Deadly Beastman gifts**: the picker still needs the variant MENU.
  The mis-write is closed — `engine.charm_actions` refuses a package Charm from an
  ordinary toggle in both shells.
- Submodules (Alchemical), the Immaculate-vs-standard DB banner, the MA style panel, the
  foreign-charms splat dropdown, "Add another" for repeatable Charms.
- Edit's deferred panels: Training Camp & Calling, Colleges, Specialties, Permanent
  Resonance/Limit, Virtue Flaw, bonus health levels, Downtime.
- Rail placeholders still on the webapp: **Play, ST Options, Custom** — plus the Combos
  sub-tab.

## One open DESIGN question — `spikes/qt_advantages/`

Not a rules question, and not scheduled. The human, after approving the Gear rebuild:
*"I think it's fine as is, but I am curious"* about an Advantages redo. The spike is
that curiosity answered — one window, four tabs, the same live character:

```sh
.venv/bin/python -m spikes.qt_advantages
```

Tab 0 is the REAL `AdvantagesPage`; A/B/C are throwaway layout mockups (they render
real data and their controls move, but they buy and validate nothing — say so before
anyone reads a missing price as a bug). All three read one `advantage_rows()`, so a
difference on screen is never a difference in data.

**The question the spike actually poses, and it outlives Advantages:** is a tab a
**collection** (browse and revisit → table + detail, the Gear/Charms pattern) or a
**form** (fill in once at chargen → everything visible, the shipped pattern)? Answering
it decides Play, ST Options and Custom too. Settling it is worth doing even if the
answer is "leave Advantages alone" — in which case the app deliberately carries two
patterns, and that should be written down rather than drifted into.

⚠ **Delete the spike once the question is answered**, either way. The other three spikes
were kept because they became build records; this one is a comparison, and a stale
comparison is worse than none.

## No open rules questions

Nothing this milestone needed a ruling for. The `acquired` fix restores the behaviour
decision 0017 already specifies; it is a bug fix, not an interpretation.

## Still deferred, still NOT gaps

The Mist numina and Cult Abyssals (both indefinitely), and the one martial-arts absence
(`enlightenment`). Training times are still a no.
