# Session handoff — 2026-08-21 (Gear + Advantages native; the Qt layout is settled)

# 👉 YOU ARE HERE

Suite green and measured: **2,674 passed, 1 skipped** (main PC, `qt-port`, 6m45s). The
branch is **8 commits ahead** of where the session started, no upstream, **unpushed**.

Nothing is half-finished. Everything below was human-clicked and approved on the real
display. Pick up at **milestone 6, the Play tab**.

## The one thing to read before touching the Qt port

⚠ **A Qt tab is a COLLECTION, and there is ONE layout.** Settled by the human
2026-08-21: toolbar for actions · a sub-tab per category where a tab has more than one ·
a sortable table with a header · a splitter with the selected entry's editor in a detail
pane. Charms, Gear and Advantages all have it.

**Play, ST Options and Custom get it too. Do not re-litigate per tab.** Copy
`qt/gear.py` or `qt/advantages.py`; never transliterate `ui/<tab>.py`.

That rule cost two rebuilds to learn. Gear was built twice — the first version ported
the webapp's *structure* by reflex (a Buy button floating mid-page with a sentence beside
it, accordion "Edit" expanders, a stack of cards) and the human rejected it on sight with
every test green: *"the page as a whole is a copy of the NiceGUI's look."* The plan had
predicted exactly that. Advantages was then rebuilt to match, after a throwaway spike put
the real page beside three candidates and the human chose one.

## What shipped

**Milestone 4 — the Gear tab, and Combos moved under Charms.** `engine/gear_actions.py`
took the rules out of the widget (`ui/gear.py` 947 → 650 lines); the presentation went to
`view.py`. Combos is now a Charms sub-tab, a placeholder in its new home.

**Milestone 5 — Advantages as a collection.** Most of the module survived; only the
containers changed. Three things the detail pane does that the card stack could not: a
Background shows its whole printed **ladder** with the rung held called out; a held Merit
shows its rules text post-lock (the old card showed nothing); and "Lose / buy off" acts on
the table selection instead of a second dropdown naming the same entries.

**`qt/layout.py::clear_layout`** — one teardown, replacing six hand-written copies.

Full write-ups: `docs/plans/qt-port.md` (milestones 4 and 5),
`docs/status/gear-and-inventory.md` (the Gear extraction and the bug below).

## ⚠ A live bug in shipped code, found and fixed — worth your attention

The Gear extraction turned up `set_weapon`/`set_armor` dropping **`acquired`**, the
artifact's acquisition channel (decision 0017). Re-picking a cash-bought artifact weapon's
own name from its own dropdown reset it to `background` and charged the p.131 budget for
something Resources had already paid for:

```
budgeted before re-pick: []
budgeted after  re-pick: ['Daiklave']
```

**This affected the shipped webapp, not just the port.** Checking the neighbours found two
more routes to the same defect (`grant_gear` not copying the channel; switching it after
the grant), both closed — `gear_actions.set_acquired` is now the only way either shell
writes the field.

⚠ **No migration.** A save already damaged has `acquired` sitting at `background` on
disk; it just stops being re-damaged. Worth a look if you have a character with a
cash-bought artifact weapon.

## The reusable lessons this session bought

- **When code copies one model into another field by field, derive the field set from the
  models.** A hand-written list documents the fields someone *thought of* — that list
  carried `from_artifact` because a comment warned about it and never knew `acquired`
  existed. `_owned_fields` is the complement of `_catalogue_stats`, so neither half can be
  forgotten.
- **A warning in a doc is not enough; make it a function.** "Copy the recursive teardown
  shape, do not write a fresh loop" was already written down and I wrote a fresh loop
  anyway — fourth occurrence. It is `clear_layout` now.
- **Moving a feature stales its negative controls.** Once Combos left the rail, "a ghost's
  rail has no Combos" passed for every splat and proved nothing.
- **Address a widget by name, never by position in `findChildren`.** A test grabbed
  `findChildren(QSpinBox)[0]`, got the quantity box instead of the stat it meant, and
  passed a wrong assertion into existence.

## Next up: milestone 6, the Play tab

Ask the milestone-2 question first — **Play's answer is not obvious.** `ui/play.py` still
holds the PlayState mutators that tier 3 of the `ui/` audit wants in `engine/`, and
⚠ **decision 0006** says that if they land in an `engine/play.py`, play-state must stay
unreachable from validation.

The layout question is already answered (see the top). After Play: ST Options, then
Custom.

## Known Qt gaps

- **Ox-Body Technique + Deadly Beastman gifts**: the picker still needs the variant MENU.
  The mis-write is closed — `engine.charm_actions` refuses a package Charm from an
  ordinary toggle in both shells.
- Submodules (Alchemical), the Immaculate-vs-standard DB banner, the MA style panel, the
  foreign-charms splat dropdown, "Add another" for repeatable Charms.
- Edit's deferred panels: Training Camp & Calling, Colleges, Specialties, Permanent
  Resonance/Limit, Virtue Flaw, bonus health levels, Downtime.
- Still on the webapp: **Play, ST Options, Custom**, plus the Combos sub-tab.

## No open questions

No rules questions, and the layout question is closed. `spikes/qt_advantages/` was deleted
when it was answered, as its README said to — the other three spikes were kept because
they became build records; a stale comparison is worse than none. It is in git at
`2a45a34` if anyone wants to look.

## Still deferred, still NOT gaps

The Mist numina and Cult Abyssals (both indefinitely), and the one martial-arts absence
(`enlightenment`). Training times are still a no.
