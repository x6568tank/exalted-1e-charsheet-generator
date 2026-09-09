# Session handoff — 2026-09-09 (Aspect Book attunements, batch-roll selection, one shared id)

# 👉 YOU ARE HERE

Last FULL suite: **3,389 passed · 1 skipped · 1 failed** (main PC, `main`, 8m45s).
⚠ The failure is the known machine-dependent M&F description test (46 entries); it
fails here because the source chapters are on disk and goes green where they are not.
Not a regression. ⚠ **Do not reconcile this count against the laptop's** — an absent
optional dependency moves it further than the gap between two machines.

Up from 3,369 at session start: **+20 tests, all from this session.**

**Working tree CLEAN, pushed to `origin/main`.** Three commits:
`a3ba511` (Aspect Book data) · `91f83c0` (batch roll + the id fix) · this doc.

⚠ **`sources/` and `images/` are gitignored and do NOT travel with a clone.** The
Aspect Book work below was read out of `sources/` on the main PC. Re-reading any of
it on the laptop needs those PDFs synced out-of-band.

## What shipped

**1. The six Aspect Book gear rows are resolved** (`a3ba511`). Read through
`tools/extract_born_digital.py` — the human authorised the pipeline for this — with
every value checked against the page's own printed FOOTER digits rather than the
extractor's detected offset. Five carry a printed commitment; the sixth does not.
Also corrected three citations naming a page that does not contain the entry.
Details are in the commit message; the numbers are in `data/`.

**2. The batch roll now selects participants and repeats** (`91f83c0`). Each roster
row is `tick · name · Dice · xN · Label` in both shells. Decision 0019 is untouched —
counts and repeats are typed, no row offers a named roll, repeat lines carry an
ordinal ("Yarak (2 of 3)") and never a roll's name.

**3. A PRE-EXISTING bug the roller made visible.** See the trap below — it is the
most re-bitable thing this session produced.

## ⚠ The trap this session paid for: one id for every blank character

Entering 5 dice for one character and 3 for another gave both the same count. Every
app path that made a blank character handed it the literal `"char.new"` — **seven
sites across `ui/` and `qt/`** — so two of them in one party shared a `batch_roster`
key and the second row's count overwrote the first's.

**The shape, and why it generalises:** an id used as a unique key that is not unique.
Nothing keyed by `character.id` was safe, not just the roller; the roller is only
where it became visible. The full suite was green throughout, because every test
that builds two characters gives them different ids by hand.

Fixed twice, and **either alone is insufficient**:

1. `models.character.new_character_id()` at all seven sites — new characters differ.
2. `view.batch_roster` suffixes a duplicate key `#2` — parties **already saved** with
   the duplicate cannot be migrated (no save migrations here), so the key derivation
   has to be total on its own.

⚠ **The test that matters is the grep** (`test_no_app_path_hands_out_a_constant_character_id`).
The defect was one literal repeated seven times; fixing the site the bug surfaced in
would have left six. Reach for a grep test whenever a defect is a repeated literal.

## ⚠ Second trap, re-bitten the same day: the stale server wears a healthy port

`ui/builder.py` runs `reload=False`. A `kill <pid>` on the PID from `pgrep … | tail -1`
killed the WRAPPER, not the listener; `curl` still answered **200** and the old build
was still being served. The real listener came from `ss -ltnp | grep 8080`.

**Kill by the PID that `ss` names, and confirm the port reads 000 with no listener,
before telling the human anything is up.** This is the second time this trap has cost
a session (2026-09-08, 2026-09-09).

## 👉 NEEDS THE HUMAN — one rules question

**Forge-Hand Gauntlets (Aspect Book: Fire, p.80-81) prints no attunement.** The entry
is complete across both pages and names no commitment anywhere. Its chapter-neighbour
the Eye of the Fire Dragon prints one, which is the argument that the absence is real
— the same right-by-absence shape the human took for the Powerbow of Perfect Accuracy.
**Left at 0 pending the ruling.** Asked twice on 2026-09-09, not yet answered.

## ⚠⚠ FIRST THING NEXT SESSION — the Party rebuild is UNVERIFIED

**The Qt Party tab was rebuilt from a card grid into a list-plus-rail on 2026-09-09 and
the work is NOT finished being checked.** It is written up in `docs/plans/qt-port.md`
("The Party tab is a LIST plus a fixed RAIL"). Two things are owed before it can be
called done:

1. **⚠ The suite was NOT run to completion after the last edits.** `tests/test_qt_party.py`
   + `tests/test_qt_adversaries.py` went **118 passed** — but that was BEFORE the final
   width-budget pass (`_BOXES_PER_ROW` 16→14, count boxes 14→13, mote spin 60→54,
   `_CARD_WIDTH` 430→400). Nothing has been run since. **Run the qt tests first, then the
   full suite.** The one test most likely to bite is
   `test_a_wrapped_card_health_track_keeps_one_pitch`, whose fixture is now DERIVED from
   `party._BOXES_PER_ROW` for exactly this reason — it should follow the constant down,
   but that has not been observed.
2. **No click-through.** Nothing below has been seen outside an offscreen render.

**Working tree is DIRTY and nothing is committed.** Changed: `exalted_builder/qt/party.py`
(the rebuild), `exalted_builder/qt/adversaries.py` (`AdversaryTrackers(dense=True)`, a new
side-by-side mode), `tests/test_qt_party.py` (the derived fixture), `docs/plans/qt-port.md`,
`docs/status/dice-roller.md`, this file, and the untracked `spikes/qt_party_dense/`.

⚠ **The width budget is the trap this rebuild leaves behind.** `_BOXES_PER_ROW`, the
tracker box sizes and `_RAIL_WIDTH` are ONE budget — line 2 of a member block holds four
panels side by side, and the widest real member (a 19-level Ox-Body Solar) hit 887px
against an 856px viewport, i.e. a horizontal scrollbar at the window's own design size.
**No test can see it** — every widget is present either way. Measure
`page._scroll.widget().minimumSizeHint().width()` against
`page._scroll.viewport().width()`; it currently reads **830 vs 856**.

## 👉 NEXT — carried, in rough order of what would bite

- **`qt/` is the one real comment-pass gap** — human parked it 2026-09-09 ("yeah, it
  can wait"). Carried.
- **The Backgrounds in the scan-only splat books** — still the one known content gap,
  a reading job, ~1,800 pages.
- **Roll initiative for the whole table — BLOCKED on the GM page holding real
  characters** (human, 2026-09-09). Written up in `status/dice-roller.md`: it needs the
  party roster to link to the players' characters instead of owning its own entries, and
  it stays a one-off because initiative's +1d10 is a printed fixed count. Do not
  generalise it to other rolls.
- **Two artifacts want a ruling, not a page** — Cold Wind Knives and the Powerbow of
  Perfect Accuracy; neither prints a commitment. `status/rated-artifacts.md`.

## ✅ CLOSED this session

- **Artifact attunement is DONE** — the human clicked it through on 2026-09-09 and
  reported no issues. That was the last item in it.
- **The dice roller click-through is DONE** — clicked 2026-09-09, fine.
- **The six "needs a page" Aspect Book gear rows** — five authored, one awaiting the
  ruling above. No longer page-blocked; the pages were in `sources/` all along.

## What a human should click

**The rebuilt Qt Party tab** (`python -m exalted_builder.qt`, then Party on the toolbar),
all of it render-only so far. Scoped to what a display can settle and a test cannot:

1. **The wound-penalty ladder over the health boxes.** The human asked for it back
   explicitly over hover-only; the question is whether it survived being shrunk to 9px
   over 18px boxes, or has become noise.
2. **The four row actions** — Sheet / PDF / Builder / Remove. They are bordered rather
   than flat text, at the human's call. Do they read as buttons at that weight?
3. **A window NARROWER than 1250.** The width budget above fits at 1250 and degrades to a
   horizontal scrollbar below it. Drag it narrow and confirm that degradation is the one
   that happens — not clipped buttons or overlapping labels.
4. **An Ox-Body character** (Yarak, 19 levels) — the track wraps to a second row. Both
   rows must hold ONE pitch, and the Essence/Willpower/Limit panels must still line up
   against the boxes rather than the captions.
5. **Six-plus adversaries** — they go two-up; check the block grid reflows on a resize
   (only the roster reflows now, members never do).

Carried from last session, still unverified:

1. **`/gm` and the Qt Party window** — add two characters, give one 5 dice and the
   other 3, Roll all. Two lines, one of 5 faces and one of 3. ⚠ This is the
   duplicate-id regression; it is the reason the fix exists.
2. **A third character**, same page — the `#2`/`#3` suffixing is where a positional
   key could still misbehave.
3. **Tick two of three rows, set one to x3**, press Roll all — four lines, three of
   them "Name (n of 3)".
4. **Type dice into an unticked row** — the tick must flip on as you type.
5. **Untick a row that has dice in it** — the number stays, the row does not roll.

## Still deferred, still NOT gaps

The Mist numina and Cult Abyssals (both indefinitely), the one martial-arts absence
(`enlightenment`), and Haltan pets. Training times are still a no. The other splats'
Charms were explicitly left as they are (human, 2026-09-01).
