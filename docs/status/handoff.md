# Session handoff — 2026-09-09b (the Party rebuild verified; attunement-by-absence ruled)

# 👉 YOU ARE HERE

Last FULL suite: **3390 passed · 1 skipped · 0 failed** (main PC, `main`, 10m41s),
**3391 collected**, run AFTER the deletion below. The arithmetic checks out: 3390 before,
plus the new attunement test, minus the deleted description test.

⚠ **THE SUITE NO LONGER HAS A KNOWN FAILURE. A red run is a real one.**

The long-running "known machine-dependent failure" was
`test_every_description_matches_the_source_text`, and it is **DELETED** (human,
2026-09-09: *"you can just get rid of it entirely at this point"*). What prompted it: on
its final run it **passed by deferring 71 entries** where last session it deferred 46 and
failed — only `images/Merits & Flaws/CH 1` is on disk, so the Godblooded (PG pp.65-80) and
ghost (p.234) entries routed to nothing and were skipped rather than checked. **It got
greener by checking less**, and the only trace was a warnings summary.

It compared descriptions to gitignored source by normalised LENGTH (fail below 92%), which
is what made the suite's outcome depend on the machine. **If the check is wanted again it
is a SCRIPT that diffs content against source and reports the differences** — more useful
(it names what changed) and broader (Charms and spells carry the same transcription risk
and never had such a test). Not written, nothing waiting on it. ⚠ Its structural siblings
SURVIVE and are the useful half — `test_no_description_carries_extraction_debris` and
`test_no_name_was_mangled_by_title_casing` assert shape, need no source, and caught eight
defects the length test provably could not see. `docs/testing.md` has the full record.

⚠ Older prose across `docs/` still calls it "the known machine-specific failure" — those
are **dated batch notes and delegation briefs, deliberately left as the record they are.**
The files that assert CURRENT state were updated: `CLAUDE.md`, `docs/testing.md`,
`docs/lessons.md`, `status/merits-flaws.md`.

**Working tree: docs + one test changed, uncommitted at the time of writing.**

## ✅ CLOSED this session — both of the things that were owed

**1. The Qt Party rebuild is VERIFIED and done.**

⚠ **The previous handoff said "Working tree is DIRTY and nothing is committed." It was
already committed** — `b6b10de "qt gm page rework"` carries `qt/party.py`,
`qt/adversaries.py`, the derived test fixture, the docs and `spikes/qt_party_dense/`,
pushed to `origin/main`. The handoff was written before the commit and never re-checked,
so its single most alarming line was the one false thing in it. **Check `git status`
against the handoff's claims before acting on them.**

What was actually owed, and is now done:

* **The suite after the width-budget pass** (`_BOXES_PER_ROW` 16→14, boxes 14→13, mote
  spin 60→54, `_CARD_WIDTH` 430→400): `test_qt_party.py` + `test_qt_adversaries.py` =
  **118 passed**, then the full suite above. `test_a_wrapped_card_health_track_keeps_one_pitch`
  — the one flagged as most likely to bite — followed `_BOXES_PER_ROW` down as its derived
  fixture intended. That had never been observed before; it has now.
* **The width budget**, which no test can see. Measured on a 4-purchase Ox-Body Solar at
  the 1250px design size: `minimumSizeHint().width()` **809** vs viewport **870**, 61px of
  headroom, no horizontal scrollbar. (Probe was a throwaway test file, deleted.)
* **The click-through.** Human clicked it 2026-09-09: *"Everything looks good. No issues."*
  That covers the wound-penalty ladder at 9px over 18px boxes, the four bordered row
  actions, narrow-window degradation, the Ox-Body wrap and six-plus adversaries — plus the
  carried batch-roll checks (two characters at 5 and 3 dice, the `#2`/`#3` suffixing, the
  x3 repeat lines). **The duplicate-id regression is confirmed fixed on a real display.**

**2. Attunement-by-absence is RULED, and three rows are pinned.**

Human, 2026-09-09: *"If no attunement, leave it as 0."* Asked about the **Forge-Hand
Gauntlets** (Aspect Book: Fire, pp.80-81), then extended by name — *"Pin them the same
way"* — to **Cold Wind Knives** (Kingdom of Halta p.93) and the **Powerbow of Perfect
Accuracy** (Caste Book: Dawn pp.80-81). All three were already 0; **no data changed.**

⚠ **The reason this needed a test rather than nothing: a ruled 0 and an unread page are
byte-identical in the data.** Both are an absent `attunement` field falling back to the
model default, and nothing on the row says which it is — that is the standing invitation
for a later session to fill the "gap" from its own 2e knowledge.
`test_the_ruled_zero_attunement_rows` pins each 0 **against a same-spread neighbour that
does print one** (Eye of the Fire Dragon 10 for the Gauntlets; Razor Claws 2 / Lightning
Chain 5 / Daiklave of Conquest 10 for the Powerbow), so the assertion discriminates a real
absence instead of restating the current value. ⚠ **Cold Wind Knives has no neighbour on
disk** — a lone entry — so its 0 rests on the ruling alone; add one if that book's other
gear ever lands. Written up in `status/rated-artifacts.md`.

**This closes the two "want a ruling, not a page" artifacts** that have been carried for
sessions. They are no longer open items.

## 👉 NEXT — carried, in rough order of what would bite

- ~~**`qt/` is the one real comment-pass gap**~~ — **DONE 2026-09-10**, all 18 files. See
  `docs/comment-standard.md` for what came out and the two traps the pass surfaced (the
  `theme.py` guard hole, and the ⚠ count rising 363 → 561 by design).
- **The Backgrounds in the scan-only splat books** — the one known content gap, a reading
  job, ~1,800 pages, and it needs the human feeding pages. ⚠ What makes it finite is
  backfilling `source` on the existing Backgrounds first — missing on **63/63**.
- **Roll initiative for the whole table — BLOCKED** on the GM page holding real characters
  (human, 2026-09-09). `status/dice-roller.md`: the party roster must link to the players'
  characters instead of owning its own entries. Stays a one-off — initiative's +1d10 is a
  printed fixed count. Do not generalise it to other rolls.
- ⚠ **Two long-deferred items that lived ONLY in `CLAUDE.md`'s "Deferred" section**, moved
  here 2026-09-09 when that section was dropped in the rewrite. Neither is urgent; both
  would have vanished silently otherwise:
  - `chargen_budgets.json` / `costs_bonus.json` / `costs_xp.json` overrides beyond what is
    authored. Optional — the loader falls back to the model defaults.
  - A per-session XP-grant ledger, and state-reconciliation of hand-edited
    current-vs-snapshot drift. The read-only lock guards normal use.
- **A content-fidelity SCRIPT** (`tools/`), if the human ever wants the check back — diff
  authored descriptions against pasted source and REPORT differences, across Charms and
  spells too, not just M&F. ⚠ **This is an option, not a debt.** Nothing is blocked on it
  and it must never go back into the suite.

## 🐞 Found by the comment pass, and FIXED

**Both shells printed an authoring date to the player.** The Custom Merit/Flaw dialog read
*"Display-only — recorded on the sheet, no mechanical effect (2026-08-10)."* — a stray
note-to-self in **user-facing UI text**, not a comment. The parenthetical is gone from both
sites: `qt/advantages.py:1417` and `ui/advantages.py:975`. No test asserted the string;
445 advantages/M&F tests pass.

A sweep of every non-docstring string literal under `exalted_builder/` now returns **zero**
dates, so this class is closed.

⚠ **The sentence is still duplicated across the two shells**, byte-for-byte, and nothing
stops them drifting. `ui/view.py` owns every other shared string and should own this one.
Not done — it is a real refactor, not a one-liner.

## ⚠ Traps still live

**The stale server wears a healthy port.** `ui/builder.py` runs `reload=False`; a `kill`
on the PID from `pgrep … | tail -1` kills the WRAPPER, not the listener, and `curl` still
answers **200** off the old build. Get the PID from `ss -ltnp | grep 8080`, and confirm the
port reads 000 with no listener before telling the human anything is up. **Cost two
sessions (2026-09-08, 2026-09-09).**

**The width budget** — `_BOXES_PER_ROW`, the tracker box sizes and `_RAIL_WIDTH` are ONE
budget; line 2 of a member block holds four panels side by side. No test can see it,
because every widget is present either way. Measure
`page._scroll.widget().minimumSizeHint().width()` against `page._scroll.viewport().width()`.

**One id for every blank character** (fixed `91f83c0`, now display-confirmed) — an id used
as a unique key that was not unique, the literal `"char.new"` at seven sites. The test that
matters is the grep, `test_no_app_path_hands_out_a_constant_character_id`. **Reach for a
grep test whenever a defect is a repeated literal.**

**The app still reports no version anywhere** — `pyproject.toml` says 1.0.0, no titlebar
string, no About item. "Am I running current code?" is unanswerable from inside the app.
⚠ Pair it with the launcher trap: `branding.install_desktop_entry()` writes `Exec=` from
`sys.executable`, so the desktop entry PINS to the first frozen binary that ever ran and
only re-points when a different one runs — downloading a new release to a new path changes
nothing until you execute it directly. ⚠ Check the DATES before blaming the build; the
stale-binary theory has been wrong twice. (Both details also in `status/merits-flaws.md`,
which is where the 2026-09-02 hunt is written up.)

## Still deferred, still NOT gaps

The Mist numina and Cult Abyssals (both indefinitely), the one martial-arts absence
(`enlightenment`), and Haltan pets. Training times are still a no. The other splats'
Charms were explicitly left as they are (human, 2026-09-01).
