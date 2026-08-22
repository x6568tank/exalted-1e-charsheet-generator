# Session handoff — 2026-08-22 (Gear + Advantages native; the Qt layout is settled;
# milestone 6 prepped)

# 👉 YOU ARE HERE

Last FULL green suite: **2,675 passed, 1 skipped** (main PC, `qt-port`, 6m55s) at
`1f3ba76`. Three commits since are covered by targeted runs only — see **Next up**. The
branch is **10 commits ahead** of where the session started and **23 ahead of `main`** (this handoff commit included), no
upstream, **unpushed**.

Nothing is half-finished, and the tree is clean. Everything shipped below was
human-clicked and approved on the real display. Pick up at **milestone 6's remaining
half: building `qt/play.py`** — its engine prep is already done and committed.

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

**A Traits spacing fix** (`c75b8c9`). ⚠ A nested layout whose spacing is unset (`-1`)
INHERITS its parent's, so the 24px gap set between the Attribute COLUMNS became the gap
between the ROWS inside them — 41px against the Virtues' 21, which reads as the card
trying to fill itself vertically. Abilities had it too. One `_ROW_SPACING` constant now
carries the warning.

**`engine/play.py`** (`2ac4465`) — milestone 6's prep, see below.

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

## Next up: milestone 6 — build `qt/play.py`

**Both questions are already answered and the prep is committed.** What remains is the
widget.

*The engine question* was YES, and it is done: `engine/play.py` (`2ac4465`) holds
`play_state`, `normalize_health`, `cycle_mark`, `set_motes`, `set_fatigue`, `set_count`,
`clear_damage` and `clear_motes`. `ui/play.py` re-exports every name — ⚠ `ui/gm.py`
imports several off that module by name, so do not remove the re-exports.

⚠ **decision 0006 is now enforced structurally**, not by memory:
`tests/test_play.py` walks the AST of every `engine/validate/` module and fails on any
`play` import OR any `.play` attribute read. Both were verified against a planted
violation. If you need play-state in validation, that is a decision to reopen with the
human, not a guard to delete.

*The layout question* was answered separately and is **the one stated exception to the
collection rule** (human, 2026-08-22): Play is a live TRACKER with nothing to select — a
health track you click to mark, mote pools, the dice-pool sidebar — so a detail pane
would hide the numbers you glance at mid-roll. **Toolbar over panels.** Everything else
(ST Options, Custom) still gets the collection layout.

What the tab needs, from `ui/play.py` (617 lines) and `view.build_play_view`: the health
track with its wound penalties, Personal/Peripheral motes, temporary Willpower, Limit,
armour fatigue, the dice-pool sidebar and custom pools. Roughly Gear-sized.

⚠ **Run the full suite before calling milestone 6 done** — the last full green run
predates the spacing fix, the play extraction and this. Targeted runs since: 172 Qt tests
(`c75b8c9`) and 228 play/pools/GM/shell tests (`2ac4465`).

After Play: ST Options, then Custom.

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
