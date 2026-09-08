# Session handoff — 2026-09-03 (artifact attunement, and two rules with no implementation)
### + 2026-09-08 addendum: decision 0019, the dice roller — see the first NEXT section

# 👉 YOU ARE HERE

Last FULL green suite: **3,238 passed, 1 skipped** (main PC, `main`, 17m22s).
**4 commits ahead of `origin/main`, not pushed** — `ceac278` (attunement blockers + the
comment-pass correction), `46a4f30` (attunement phase 1), `bbdc661` (phase 2 + two Merit
fixes), plus the two carried from the previous session — and ⚠ **the working tree is
DIRTY**: the ST toggle, the species-3 fix and this whole close-out are uncommitted.

⚠ The count moved 3,181 → 3,238; all 57 are tests added this session. Nothing was fixed
by accident and nothing went missing.

## What shipped

**1. Artifact attunement, phases 1 and 2** (`status/rated-artifacts.md`, and
`plans/artifact-attunement.md` for the full design). An owned artifact with a printed
cost can commit its motes, and the Play tab's maxima come down by the total, on all four
mote surfaces. The flag is the player's — nothing auto-attunes. The derivation walks
`artifacts.artifact_items()`, the one enumeration, so a daiklave entered as both an
artifact row and its weapon stat line commits once; the **gear row wins** (human's
ruling). **Not browser-verified.**

**2. `MeritEffects.no_magical_material_bonus`** (`status/merits-flaws.md`). Both Magical
Attunement Merits refuse the material bonus in as many words and nothing implemented it —
the right answer arrived by coincidence, because a Mortal/God-Blooded exalt_type matches
no material. The same pages settled the attunement doubling: a character no material
resonates with pays the **printed** cost.

**3. `MeritEffects.essence_pool_split_thirds`** (`status/godblooded.md`). Aura of Power
was read from the save, stored, and had **zero read sites**. `essence_pool_is_merged`
asked the splat first, and a God-Blooded's `single_essence_pool` is True, so the Flaw
never got a vote. Reported from the human's own save; Taban now reads Personal 10 ·
Peripheral 21 instead of Single pool 31.

## 👉 NEXT — the dice roller (decision 0019, new 2026-09-08)

⚠ **0009 ("no dice rolling, ever") was REOPENED BY THE HUMAN on 2026-09-08** and
narrowly reversed by **`docs/decisions/0019-a-dumb-dice-roller.md`**. Read that record
before writing a line of it; `0009` and `0016` carry amendment pointers, and CLAUDE.md's
"permanently out of scope" line no longer names 0009.

**Build this first, and standalone.** It needs no server, works in both shells, and it
tells the human whether reversing 0009 feels right at the table *before* the ~12 days of
hosting work below. **~2–3 days.**

- `engine/` gets a pure roller: `(count, target_number, die_faces)` → faces + success
  count + botch flag, applying the Rule of Ten and the Rule of One below. **Injectable
  RNG** — a roller that cannot be seeded cannot be tested. No `RollDefinition`, no
  `PoolBreakdown`, no character, ever, in its signature. Both rules are properties of a
  handful of dice and know nothing about the character, so neither breaches the no-wire
  rule.
- **The initiative rating** is a separate, tiny derivation (Dex + Wits + weapon Speed) —
  a sheet line, not a roll. See below.
- Surfaces in `ui/play.py` **and** `qt/play.py`. One shell only is how the two products
  drift.
- Results are **not persisted** to the character — a transcript, not play-state.
- ⚠ **The no-wire rule is 0019's load-bearing clause and NO TEST WILL CATCH ITS LOSS.**
  Pre-filling the dice box from a pool row is legal only if the field stays editable, the
  player presses Roll, and **the result never carries the roll's name**. Put "the result
  is not labelled with the roll's name" on the click-through list.

### ⚠ The three dice rules — SOURCED 2026-09-08, and two overturned what we assumed

Grepped out of `images/_extracted/Exalted Core.md`. **Nothing here is blocked any more.**
Full quotes and page cites are in 0019; the short form:

⚠ Page numbers are from the book's **index** (`Rule of One 89`, `Rule of Ten 90`); the
transcription's `<!--PAGE-->` markers sit one page early here — the known offset trap.

1. **Rule of Ten (p.90): a 10 counts as TWO successes.** ⚠ Neither the human nor the
   model raised this — plain `d >= tn` counting would have shipped silently wrong. This
   is the roller's core arithmetic; get it right first and test it first. General, with
   two printed per-effect exceptions (damage rolls; the Rune), each switching off double
   10s **and** botching together — hence two default-ON switches on the roller, not logic.
2. **Rule of One (p.89): botches DO exist.** No die at target-or-higher **and** at
   least one 1. One success or more and all 1s are ignored. ⚠ **1s NEVER subtract
   successes** — that is another edition's convention; refuse it if proposed. (The
   human's "1e has no botch logic by default" was overturned on the first half and
   correct on the second.)
3. **Initiative (p.226; weapon Speed p.326) is NOT a dice pool.** Base = **Dexterity +
   Wits**, adjusted by the weapon's Speed — *"added to or subtracted from the character's
   initiative total"*, a **flat modifier, not dice** — then **+1d10 every turn**.
   ⚠ **Do not author an initiative row in `data/dice_pools.json`.** It is a derived
   rating line (trait arithmetic, in scope under 0016) plus a `1d10` the dumb roller
   already does. Cheaper than the row that was planned. `Weapon.speed`'s comment
   (`models/rules.py:1206`) was right all along.

⚠ **Those Core passages are glyph-ciphered** — "Iowever" for However, and in the worked
examples `1` renders as `0` and `10` as `/`. The **prose rules are clean**; nothing above
came from an example's digits, and nothing later should.

✅ **`README.md` is already updated** (2026-09-08) — both the "NO FUCKING DICE" bullet and
the Play-tab paragraph that said to go roll on a table. The bullet's replacement is the
human's own words and is the one-line statement of this whole design: *"There is a dumb
dice roller. It has a label, and you input how many dice. I will not do charm effects for
you, fuck off."*

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

## 👉 NEXT — carried

Nothing is blocked. In rough order of what would bite:

- **The `ArtifactType.attunement` backfill.** All 330 rows are 0, so the
  standalone-Wonder path is unexercised by real data. It is a **parse job, not a
  re-read**: 74 rows state a commitment in their transcribed description. ⚠ Exclude
  gear-statblocked duplicates first (`gear_stat_line`) — the Skirmish Pike is in the 74
  and must stay 0 because `weapons.json` holds its 5.
- **Attunement phase 3's remainder** — whether the printed sheet marks an attuned item.
  Low priority, untouched.
- **`qt/` is the one real comment-pass gap** (carried; `docs/comment-standard.md`).
- **The Backgrounds in the scan-only splat books** — still the one known content gap, a
  reading job.

## Rules questions — both ANSWERED 2026-09-03, none outstanding

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

**Nothing this session was browser- or app-clicked.** In priority order:

1. A **daiklave** on the Gear tab in both shells — real catalogue attunement (5 motes).
   Checkbox appears; pool dropdown only once checked.
2. The **Play tab** after attuning it — the pool shrinks and the note says why.
3. A **ghost** (merged pool) — no pool choice offered at all.
4. A **mortal** with Essence Awareness and an attuned artifact — the motes must come out
   of Personal (their only pool), and the new ST toggle should appear on ST Options and
   move the free-mote line when flipped. This is the path that was silently free until
   2026-09-03.
5. **Taban's sheet and printed PDF** — the split reads Personal 10 · Peripheral 21.

## ⚠ Two test traps this session paid for, both re-bitable elsewhere

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
that ever ran, and nothing in the UI reports a version. ⚠ **This session, the stale-binary
theory was WRONG** — the suspected fix predated the binary by a month. Check the dates
before blaming the build.

## Still deferred, still NOT gaps

The Mist numina and Cult Abyssals (both indefinitely), the one martial-arts absence
(`enlightenment`), and Haltan pets. Training times are still a no.

⚠ **The other splats' Charms were explicitly left as they are** (human, 2026-09-01),
including the `min_essence == min_ability` duplication grep that found three bad rows in
Core. Untested, not verified.
