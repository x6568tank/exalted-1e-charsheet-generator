# Session handoff — 2026-09-09b (the Party rebuild verified; attunement-by-absence ruled)

# 👉 YOU ARE HERE

Last FULL suite: **3390 passed · 1 skipped · 0 failed** (main PC, `main`, 9m58s).
Collection is now **3392** — that run predates the one test added after it, which was
run on its own and passes.

⚠ **The "known failing" M&F test PASSED this time, and that is not good news.**
`test_every_description_matches_the_source_text` went green by **deferring 71 entries**
where last session it deferred 46 and failed. Only `images/Merits & Flaws/CH 1` is on
disk; the Godblooded (PG pp.65-80) and ghost (p.234) chapters cover nothing, so those
entries are not checked at all. **The suite got greener by checking less** — the deferral
list is in the warnings summary and nowhere else. Do not record this as the failure being
fixed. ⚠ And do not reconcile the count against another machine's.

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

- **`qt/` is the one real comment-pass gap** — human parked it 2026-09-09 ("yeah, it can
  wait"). ⚠ Cheapest it will ever be *right now*: `qt/party.py` was just rewritten, so the
  context is loaded and the file is fresh.
- **The Backgrounds in the scan-only splat books** — the one known content gap, a reading
  job, ~1,800 pages, and it needs the human feeding pages. ⚠ What makes it finite is
  backfilling `source` on the existing Backgrounds first — missing on **63/63**.
- **Roll initiative for the whole table — BLOCKED** on the GM page holding real characters
  (human, 2026-09-09). `status/dice-roller.md`: the party roster must link to the players'
  characters instead of owning its own entries. Stays a one-off — initiative's +1d10 is a
  printed fixed count. Do not generalise it to other rolls.
- **The M&F deferral above** is not a gap to fix in code — it needs the two chapters
  pasted into `images/`. Until then 71 entries have no fidelity check.

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
⚠ Check the DATES before blaming the build; the stale-binary theory has been wrong twice.

## Still deferred, still NOT gaps

The Mist numina and Cult Abyssals (both indefinitely), the one martial-arts absence
(`enlightenment`), and Haltan pets. Training times are still a no. The other splats'
Charms were explicitly left as they are (human, 2026-09-01).
