# Session handoff — 2026-08-22 (milestone 6: the Play tab is native)

# 👉 YOU ARE HERE

Last FULL green suite: **2,710 passed, 1 skipped** (main PC, `qt-port`, 6m51s) at this
session's tip — a fresh run AFTER the last code change, not the one that was in flight
while `_pool_row` was rebuilt.

The tree is clean and nothing is half-finished. **`qt/play.py` is built, tests-green and
smoke-rendered, and has NOT been human-clicked.** That is the one thing this session
leaves open, and it is the only thing that has ever caught a wrong Qt design.

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

## The one thing left

⚠ **Get the tab human-clicked on the real display.** Milestone 4 is the standing proof
that tests-green plus a smoke render cannot tell anyone whether a surface is right — the
first Gear tab was both and was rejected on sight.

```sh
python -m exalted_builder.qt examples/ashes-of-dawn.character.json
```

Then **Finish & Lock** — Play only appears at the lock — and open Play.

## Next up

**ST Options, then Custom** — both get the COLLECTION layout (toolbar · sub-tab per
category · sortable table · splitter with a detail pane). Copy `qt/gear.py` or
`qt/advantages.py`; never transliterate `ui/<tab>.py`. That leaves the Combos sub-tab and
the known gaps below.

## Known Qt gaps

- **Ox-Body Technique + Deadly Beastman gifts**: the picker still needs the variant MENU.
  The mis-write is closed — `engine.charm_actions` refuses a package Charm from an
  ordinary toggle in both shells.
- Submodules (Alchemical), the Immaculate-vs-standard DB banner, the MA style panel, the
  foreign-charms splat dropdown, "Add another" for repeatable Charms.
- Edit's deferred panels: Training Camp & Calling, Colleges, Specialties, Permanent
  Resonance/Limit, Virtue Flaw, bonus health levels, Downtime.
- Still on the webapp: **ST Options and Custom**, plus the Combos sub-tab.
- The Play tab does not render Lunar **Renown** or **face** — neither does the webapp's,
  so this is parity, not a port gap. Both are wholly Storyteller-adjudicated
  (`PlayState`'s docstring).

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
