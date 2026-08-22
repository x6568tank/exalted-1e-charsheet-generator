# Session handoff — 2026-08-21 (Gear ported; Combos moved under Charms)

# 👉 YOU ARE HERE

Suite green and measured: **2,648 passed, 1 skipped** (main PC, `qt-port`, 6m20s). The
branch is **4 commits ahead of where the session started, no upstream, unpushed.**

Nothing is half-finished. **Pick up by clicking milestone 4 through on the real
display** — it is the only thing standing between here and milestone 5.

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

## Next up: click milestone 4, then milestone 5

**Milestone 4 is NOT human-verified.** It is tests-green and smoke-driven offscreen
across all four example characters — every rail page built, the shop dialog opened, the
chips correct, artifacts appearing only post-lock. That is not the same thing.

⚠ The standing warning applies hardest to this tab: **a control can be correct,
reachable, fully tested, and nowhere near the thing it configures.** What to look at:

- the inventory's filter chips and the per-row Edit expanders (a merged artifact daiklave
  should show **both** editors under one Edit);
- the Buy shop's type chips, and that artifacts appear only after the lock;
- the artifacts budget header, and the services price list's **cash** column;
- the Combos sub-tab sitting between the trees and Spells, reading **Arrays** for an
  Alchemical and absent entirely for a ghost.

After that, milestone 5 is **Play**, then ST Options and Custom. Ask the milestone-2
question of each — Play's answer is not obvious, since `ui/play.py` still holds the
PlayState mutators that tier 3 of the audit wants in `engine/` (⚠ decision 0006: if they
land in an `engine/play.py`, play-state must stay unreachable from validation).

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

## No open rules questions

Nothing this milestone needed a ruling for. The `acquired` fix restores the behaviour
decision 0017 already specifies; it is a bug fix, not an interpretation.

## Still deferred, still NOT gaps

The Mist numina and Cult Abyssals (both indefinitely), and the one martial-arts absence
(`enlightenment`). Training times are still a no.
