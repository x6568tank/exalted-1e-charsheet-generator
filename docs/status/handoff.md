# Session handoff — 2026-09-08 (the dumb dice roller, initiative, the GM's batch roll)

# 👉 YOU ARE HERE

Last FULL green suite: **3,356 passed, 1 skipped** (main PC, `main`, 9m08s).
**4 commits ahead of `origin/main`, not pushed** (unchanged from the last session:
`ceac278`, `46a4f30`, `bbdc661`, plus two carried) — and ⚠ **the working tree is
DIRTY**: everything below is uncommitted, on top of the previous session's uncommitted
close-out.

⚠ The count moved from 3,238; the difference is tests added this session and nothing
else. Nothing was fixed by accident and nothing went missing.

⚠ **MERGED 2026-09-08 with a SECOND line of work that this handoff was written without
seeing**: the artifact-attunement session of 2026-09-07 (the 89-row catalogue backfill
and phase 3, the sheet mark) landed on `main` while the roller was being built on
another clone. Both are in the tree now. **Neither suite figure below covers the other
line's tests** — the post-merge run is **3,369 passed · 1 skipped · 1 failed** (the
known machine-dependent M&F description test, 46 entries, failing here because the source
chapters are present). Read `status/rated-artifacts.md`
alongside `status/dice-roller.md`. The 09-07 handoff was superseded by this file rather
than merged into it; its findings live in `status/rated-artifacts.md`.

**The full record is `docs/status/dice-roller.md`.** What follows is the session
summary; do not restate that file here.

## What shipped

Decision **0019** is now built, in both shells. Read the record before touching any of
it — its **no-wire rule** is the whole safety mechanism and no test catches its loss by
accident.

**1. The roller** (`engine/dice.py`, `view.roll_dice`, `ui/play.py`, `qt/play.py`). A
dice COUNT the player types, a target number, a free-text label and two switches →
faces, successes, botch. Carries the **Rule of Ten** (a 10 is TWO successes, p.90) and
the **Rule of One** (no success plus at least one 1, p.89; ⚠ 1s never subtract). RNG
injectable. Results are a transcript: capped at 12, never written to a `Character`. The
newest roll shows and the rest fold behind "Previous rolls (N)" — the fold was the
human's ask after seeing a session's worth of log.

**2. The initiative RATING** (`engine/initiative.py`). Dexterity + Wits + weapon Speed,
itemised, in its own card captioned "A RATING, NOT A POOL", with the `+1d10 each turn`
line and the tie-break. Speed is adjusted by the magical material and by unmet weapon
minimums — both through `derive.effective_weapon` and `pools.weapon_minimum_shortfall`,
which already owned those rules. ⚠ Mobility, encumbrance, fatigue and wound penalties
are all OUT, per the human's ruling of 2026-09-08 (wounds reach initiative only under
**Power Combat**, which this build does not implement).

**3. The GM's batch roll** (`view.roll_batch`, `ui/gm.py`, `qt/party.py`). A name for
the batch, one typed count per roster row, one press; the log folds under the batch's
name and opening it shows a line per row. A row at 0 sits out. Adversaries included.
⚠ Shape **B** of three the human was offered — the pool-filled version is the wire 0019
rejects by name, and building it needs the decision reopened.

**4. Two Qt layout defects, both PRE-EXISTING and neither mine** — the wrapped health
track drawing at two different pitches (`qt/play.py` AND `qt/party.py`, the same bug one
widget class apart), and a long roster name pushing its batch row's controls out of
line. Both fixed, both covered by geometry tests, both negative-controlled.

**Browser/app-verified?** The human clicked the **roller** and the **initiative rating**
mid-session and reported them fine. ⚠ **The fold, the batch roll and both layout fixes
have only been rendered offscreen** — `status/dice-roller.md` has the click list.

## ✅ DONE — the dice roller (decision 0019). Kept below: what it did NOT decide

⚠ **0009 ("no dice rolling, ever") was REOPENED BY THE HUMAN on 2026-09-08** and
narrowly reversed by **`docs/decisions/0019-a-dumb-dice-roller.md`**. Read that record
before writing a line of it; `0009` and `0016` carry amendment pointers, and CLAUDE.md's
"permanently out of scope" line no longer names 0009.

Built 2026-09-08, both shells. **The record is `docs/status/dice-roller.md`**; the
rules, their page cites and the rejected alternatives are in the decision record. The
spec that stood here has been deleted rather than left to rot beside two copies that
are now more accurate than it.

⚠ Two things from that spec are worth keeping in front of a reader's eyes, because
they are the parts that decay silently:

- **The no-wire rule is 0019's load-bearing clause and NO TEST CATCHES ITS LOSS by
  accident.** The tests that catch it deliberately are listed in `status/dice-roller.md`
  — deleting one of those is deleting the mechanism, not tidying a test.
- **The page numbers for the two dice rules come from the book's INDEX** (`Rule of One
  89`, `Rule of Ten 90`); the transcription's `<!--PAGE-->` markers sit one page early
  here. That is the known offset trap, and it is why the rules were quoted from the
  prose and never from a worked example's digits — ⚠ those examples are glyph-ciphered,
  rendering `1` as `0` and `10` as `/`.

### Costed but NOT ruled — hosting, a shared roll log, a whiteboard

No decision record exists for these on purpose: the human asked the cost, not for a
ruling. Estimates from 2026-09-08, built on `docs/plans/hosting-state-model.md`:

| Piece | Cost |
|---|---|
| Hosting/session refactor (the gate for anything shared) | **10–12 days** |
| Shared roll log broadcast to the party | +2 days |
| Shared whiteboard (freehand + text, last-write-wins) | +4–6 days, **web only** |
| *Cheaper substitute:* shared notes + pasted-image pane | +1 day |

⚠ **The `ctx` isolation defect is real today and independent of hosting.**
`ui/builder.py:456` builds `ctx` once in `main()` and both routes close over it — one
process serves one `Character` to every connection. Harmless for a desktop app; it is
§3 of the hosting plan and its §3.8 isolation test (**must fail on today's code**) is
worth writing whenever that area is touched.

⚠ **The copyright question is still open and hosting changes its shape.** `data/` carries
~1.8M characters of transcribed prose (~361 pages), which is why the repo is private. The
human cites the Exalted Essence fan app (`exalted-essence-app.vercel.app`) as precedent —
that app has campaigns and a wiki, no dice roller, and an explicit *"unofficial, fan-made
… no copyright infringement is intended"* notice attributing Onyx Path and Paradox. ⚠ **Its
clean record is evidence about enforcement appetite, not about verbatim prose** — whether
it ships descriptions or only mechanics was not determined (SPA; only the homepage was
readable). Two cheap mitigations, neither ruled: **copy that disclaimer**, and **strip or
gate `description` in the hosted build** (a build-time filter, not a refactor — the sheet,
pools and trackers all work without it).

## 👉 TODO — raised by the human 2026-09-08, at the end of the roller session

Both captured verbatim; neither is started, and neither was a defect report.

1. **The Qt Party window is still shaped like a copy of the webapp.** Human's words:
   *"The gm party view is still structured as a 'copy' of the webapp; write that down
   to fix sometime."* Deliberately vague on the remedy because they did not name one.
   ⚠ Note before acting: the Party tab is one of the **three written exceptions** to the
   port's ONE tab layout (`docs/plans/qt-port.md` — it is a live TRACKER with nothing to
   select, so it has no detail pane on purpose). This TODO is NOT licence to fold it back
   into the collection layout; the exception stands until the human reopens it. What they
   are pointing at is the *card-grid-and-scroll* structure reading as a ported web page
   rather than a native window. Ask what shape they want before designing one.

2. **The batch roll must not be all-or-nothing.** Human's words: *"I do not want to roll
   for everyone immediately. I want to be able to choose how many rolls I make, and for
   who."* ⚠ Read that as the INTERACTION shape, not a missing capability: a row left at 0
   dice already sits the batch out (`view.roll_batch` skips it), so "for who" is possible
   today but only by zeroing everyone you *don't* want. The ask is for selecting the
   participants directly, and for controlling **how many rolls** are made — which may mean
   several rolls for one character, a shape the batch does not have at all today (one row
   = one roll). **Ask which of the two they meant before building either.**
   ⚠ Whatever the shape, decision 0019 is unchanged: counts stay typed, no row may offer a
   named roll to fill itself from, and a result may never carry a roll's name.

## 👉 NEXT — carried

Nothing is blocked. In rough order of what would bite:

- ⚠ **The `ArtifactType.attunement` backfill and phase 3 are BOTH DONE** — they shipped
  on the 2026-09-07 line of work this handoff was merged with, and the two bullets that
  stood here are stale. 89 of the 330 rows now carry a printed commitment, and the sheet,
  the Qt sheet and the PDF all print `attuned · Nm` through `view.attunement_mark`.
  `status/rated-artifacts.md`.
- **A human click-through of attunement** — now the ONLY thing left in it, and it has real
  catalogue data behind it. The five-item list lives at the bottom of
  `status/rated-artifacts.md`'s 2026-09-03 section; pick a **daiklave**, then a
  **standalone Wonder** (the Ring of Being at 15 motes is the loudest), then the mortal
  case that was silently free until 2026-09-03 — and now also **the sheet and the PDF**,
  which should say `attuned · Nm` beside the item while the pools stay full.
- **Six gear rows need a page, and they are all Aspect Book rows** — the Most Terrifying
  Armor of the Air Dragon (Air p.81), Forge-Hand Gauntlets + Eye of the Fire Dragon (Fire
  p.81), Black Widow Razors + Death at the Root (Wood p.83), Gauntlets of Distant Touch
  (Water p.80). ⚠ **No Aspect Book material is under `images/` on the main PC** as of
  2026-09-07, though `derive.py` cites an `images/Dragonblooded/Aspects/…` path and the six
  stat lines were authored from those books. That citation was deliberately NOT "fixed" —
  an absent path is not a missing source. The pages need putting in front of me.
- **Two more want a ruling, not a page** — Cold Wind Knives and the Powerbow of Perfect
  Accuracy. Both pages ARE on disk and were read 2026-09-07; neither prints a commitment,
  and the Powerbow's whole spread has every neighbour's cost already authored, so its 0 is
  right-by-absence. `status/rated-artifacts.md`.
- **`qt/` is the one real comment-pass gap** (carried; `docs/comment-standard.md`).
- **The Backgrounds in the scan-only splat books** — still the one known content gap, a
  reading job.

## Rules questions — NONE OUTSTANDING

This session's were all answered by the human on the spot (2026-09-08): the two dice
rules off the page, and the initiative modifiers — magical material, unmet weapon
minimums, and the exclusion of mobility, encumbrance, fatigue and wound penalties. ⚠ The
mobility exclusion is explicitly the human's **reading of p.332's scope**, not an
explicit exclusion in the text; it is recorded as a ruling in `engine/initiative.py` and
`status/dice-roller.md`, and reversing it is theirs to do.

### Carried, both ANSWERED 2026-09-03

- **`free_max` and committed motes** became an ST toggle rather than a ruling:
  `HouseRules.committed_motes_reduce_free_essence`, PER-CHARACTER, default OFF. The app
  cannot decide it, because both Willpower rolls involved are the table's.
- **Aura of Power's anima clause needs no implementation** — anima is a user-entered
  field. Not a gap; do not re-raise it.

⚠ **The toggle's own test found a SPECIES 3 house bug in the phase-2 work, and the
DEFAULT VALUE was the off switch.** A mortal's pool is entirely Personal and
`attuned_pool` defaults to `"peripheral"`, so a mortal's commitment landed on a
0-maximum pool and cost nothing — checkbox ticked, number right, tracker untouched.
Fixed by generalising the merged-pool case: **a commitment allocated to a pool the
character does not have is re-routed to the one they do.** Found by accident, because an
unrelated test's fixture happened to be a mortal. `status/rated-artifacts.md`.

## What a human should click

**This session, the roller and the initiative rating WERE clicked** (human, 2026-09-08,
both approved). ⚠ **Everything else below is still owed** — the fold, the batch roll and
the two layout fixes have only been rendered offscreen, and the whole attunement list
below is carried unclicked from 2026-09-03.

**From this session** — the full list with expected numbers is in
`status/dice-roller.md`; the three that matter most:

1. ⚠ **Roll with the label box EMPTY, both shells.** The transcript line must carry the
   outcome and the dice and **no roll name anywhere**. This is 0019's safety mechanism
   and no test failure will ever tell you it broke.
2. **The batch roll** on the party surface, both shells — name it, give two rows dice,
   leave one at 0; the fold shows the name, opening it shows a line per row.
3. **A wrapped health track** (Yarak's 19 levels) on the Play tab **and** a party card —
   one pitch across both rows.

**Carried from 2026-09-03, attunement, still unclicked:**

1. A **daiklave** on the Gear tab in both shells — real catalogue attunement (5 motes).
   Checkbox appears; pool dropdown only once checked.
2. The **Play tab** after attuning it — the pool shrinks and the note says why.
3. A **ghost** (merged pool) — no pool choice offered at all.
4. A **mortal** with Essence Awareness and an attuned artifact — the motes must come out
   of Personal (their only pool), and the new ST toggle should appear on ST Options and
   move the free-mote line when flipped. This is the path that was silently free until
   2026-09-03.
5. **Taban's sheet and printed PDF** — the split reads Personal 10 · Peripheral 21.

## ⚠ Test traps paid for, all re-bitable elsewhere

**New, 2026-09-08:**

1. **`qtbot.waitExposed` returns BEFORE a nested `QScrollArea` lays its contents out.**
   Every widget then reports the same `y`, so a geometry assertion reads one row where
   there are two — it fails confusingly, or passes vacuously. Needs `qtbot.wait(50)`
   before measuring. ⚠ Adding that wait across a file by search-and-replace broke an
   unrelated scroll test whose assertion depended on the original timing: apply it ONLY
   where geometry is measured.
2. **A `QHBoxLayout` of fixed-size cells spreads its slack BETWEEN them.** Stretching
   only the last row of a wrapped track justifies the full rows and packs the short one,
   changing box pitch mid-track. Invisible to widget-count and text assertions; a human
   spotted it on sight. Test by measuring pitch per row.
3. **`_StatLine` cannot be given a fixed width** — its `Ignored` horizontal size policy
   beats `setFixedWidth` and collapses the label to nothing. The collapse was invisible
   to every test and showed only in a render.

**Carried from 2026-09-03:**

1. **Qt: `isVisible()` is False for everything on a page that is never shown.** A
   headless visibility assertion passes against a control that is *always* shown, and its
   positive half cannot pass at all. Use **`isHidden()`**.
2. **A fixture that omits the axis a rule keys on produces a confident, WRONG gap
   report.** A synthetic God-Blooded built with no `caste` showed an Essence pool of 0,
   and that was written up as "Awakened Essence grants no pool" — a fabricated second
   bug. The pool formula is heritage-keyed and had worked all along. It was the human's
   real save that corrected it. Same shape bit the merged-pool test the same day: a
   synthetic ruleset with no Ghost exalt made it assert the exact bug it guarded.
   **Splat-shape and merged-pool tests need the REAL `ruleset` fixture.**

## Carried forward, still true

The Qt port is feature-complete and the Party window is clicked. Four surfaces are still
**rendered offscreen but never used**: the **Sheet tab**, the Party window's **Reference
tab**, the **Thaumaturgy → Rituals tab** and the **Custom tab's Rituals sub-tab**.

⚠ **`dist/` is gitignored and its binaries are from 2026-08-14 / 2026-08-30** — neither
has this session's work. Rebuild before showing the app to anyone, and remember the
launcher trap: `branding.install_desktop_entry()` pins `Exec=` to the first frozen binary
that ever ran, and nothing in the UI reports a version. ⚠ **On 2026-09-03 the
stale-binary theory was WRONG** — the suspected fix predated the binary by a month.
Check the dates before blaming the build.

⚠ **A stale RUNNING SERVER wears the same disguise, and it bit on 2026-09-08.**
`ui/builder.py` runs `reload=False`, so a server started before an edit serves old code
— and `fuser -k 8080/tcp` silently failed to kill it, the replacement exited with
"address already in use", and `curl` still answered **200**. The port looked healthy
while serving the previous build. **Kill by PID and re-check the port is 000 before
relaunching**, whenever you are about to show the human something.

## Still deferred, still NOT gaps

The Mist numina and Cult Abyssals (both indefinitely), the one martial-arts absence
(`enlightenment`), and Haltan pets. Training times are still a no.

⚠ **The other splats' Charms were explicitly left as they are** (human, 2026-09-01),
including the `min_essence == min_ability` duplication grep that found three bad rows in
Core. Untested, not verified.
