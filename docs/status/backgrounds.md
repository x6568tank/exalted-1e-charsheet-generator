# Backgrounds — the overhaul (2026-08-11 → 2026-08-12)

**DONE, browser-verified 2026-08-12.** Suite **2,152 passing**.

Came out of a friend's play-test, which found the Background surface doing three
things wrong at once: offering every splat every other splat's Backgrounds, saying the
same sentence at one dot as at five, and (for Ghosts) never warning about an unspent
pool. The authoring brief that drove the sweep is `docs/briefs-backgrounds-sweep.md`.

## What shipped

**Per-splat catalogues.** Every splat/origin row in `chargen_budgets.json` (18 of 33
rows) now carries `catalogue_backgrounds` — its own book's printed list. Before this,
Backgrounds were almost entirely untagged, so a Solar was offered Lookshy's **Arsenal**
and E:DB's Command / Henchmen / Reputation / Family. Sidereals were missing six their
book prints (Acquaintances, Celestial Manse, Connections, Salary, Savant, Sifu) and
offered four it bars. God-Blooded saw **13 of the 25** their chapter grants — the other
twelve are printed in other splats' books and cross-referenced by PG p.50.

**The Storyteller override** is `HouseRules.all_backgrounds_available` (The Outcaste
p.66, which asks for the switch in so many words). It is TABLE-WIDE, reads through
`validate.background_catalogue_for`, and prints a live count on the toggle so the ST can
see what flipping it is worth to this character before flipping it. It does **not** lift
a splat's own prohibitions — the Great Geas still bars the Mountain Folk a Cult.

**The printed dot ladder.** `BackgroundType.ladder` is a 6-tuple (the book's `x` row plus
five dots) or empty; a partial ladder raises at load, because the sheet indexes it BY
RATING and four rungs would print the wrong text rather than no text. 49 of 61 entries
carry one. It is TEXT — nothing in the engine reads a rung, and the numeric rules a rung
happens to state belong in `BackgroundRule`.

It renders in two places, and they are deliberately different: the **row** shows only the
one rung the character holds (`view.background_rung`), the **catalogue dialog** carries
the whole ladder (`view.background_ladder`), because the dialog is where a rating gets
chosen and the row is where one is held.

**Artifact and Manse are reworked per splat** instead of one entry with a pile of
per-splat parentheses and a Solar-only ladder.

**Ghosts got their unspent-pool warning.** Every other chargen pool warned about
leftovers and the Charm pool warned about none. `ExaltDefinition.charm_noun` is new —
presentation data exactly like `caste_noun` — so a ghost reads "Arcanoi", not "Charms",
in both the chargen readout and the picker header.

## What the work turned up on the way

- **`catalogue_backgrounds` is NOT `allowed_backgrounds`.** The first decides what the
  dropdown OFFERS; the second is HARD validation that makes an unlisted Background an
  ERROR. They were first written as one field, and the suite caught it: every free-text
  Background became illegal for the splats that had a list. Where a row has both,
  offered must be a SUBSET of allowed (tested).
- **A list entry may be a NAME or an exact id, and an id bypasses the splat tag.** Use an
  id when a name is ambiguous — five names are printed twice (Connections, Celestial
  Manse, Salary, Savant, Sorcery) — or when a book grants another splat's Background. A
  bare NAME in a splat that has both an untagged and its own tagged copy offers the row
  twice.
- **The rung label was correct and completely untested through the UI.**
  `background_rung` had unit tests; the label is refreshed by a callback the rating
  control has to invoke, and the play regime's number input does not rebuild the panel.
  A rung frozen at the rating the row was drawn at would have been invisible to the whole
  suite. Three harness tests now drive it (drawn rating, play number input, chargen dot
  track), and breaking the play callback fails the play test — the wiring was right, the
  coverage was not. This is the `preflight` skill's whole thesis, hit again.
- **The dialog's ladder was rendered as a wall of text.** A plain NiceGUI label collapses
  every newline it is given, so six rungs ran together into one paragraph and the extra
  blank lines alone would have changed nothing. The fix is two halves — blank lines
  BETWEEN rungs, and `whitespace-pre-line` on the label. Anywhere a `full` string in
  `ui/catalogue.py` is STRUCTURED rather than prose, that class is required.
- **A shared module-level test character is an ordering trap.** The new dialog test
  passed alone and failed in the full suite: `/merits-backgrounds`'s character is
  RENAMED by the description tests. Any test that reads a fixture character's *content*
  needs its own route.
- **"Missing pages" is a claim to check, not assume.** Twice in this work something was
  called page-blocked that was not — the Abyssal/Alchemical/Dragon-King Artifact reworks
  were all on disk, and the Lunars book was in `sources/` the whole time.

## Deliberate gaps — not TODOs
- **Family** has no ladder: E:DB p.159 prints a random table instead.
- **Alchemical Artifact** has no ladder: the book prints none.
- **Cult** is `universal: true` (human's ruling) — offered to every splat, and still
  bannable; the Great Geas keeps it off both Mountain Folk origins. A universal
  Background must appear in no splat's list, and a Background with no splat tag that no
  list names must be marked universal — tested both ways, so the invariant cannot rot.

## Borrowed ladders, and the duplicate they exposed (2026-08-12)
**Human's ruling:** CH6 prints the ten shared Mountain Folk Backgrounds as PROSE, with no
dot ladder — "it's prose only, but you should probably make them point to the Solar
backgrounds, just makes life easier". So `BackgroundType.ladder_from` is an exact
Background id whose rungs are copied onto the borrower **once, by the loader**
(`rules_db._resolve_borrowed_ladders`), after which every reader sees an ordinary ladder.

Two design points that are the whole reason it is shaped this way:
- **Resolved at LOAD, not at the read sites.** The read sites are handed a
  SPLAT-FILTERED catalogue — a Mountain Folk list does not contain the Solar entry it
  borrows from — so a lookup there would find nothing and silently render no rung. The
  house bug, with the mechanism present and pointed at the wrong collection.
- **A per-entry POINTER, never a same-name fallback.** Alchemical Artifact and Family
  have no ladder on purpose; a fallback would hand Alchemical Artifact the core Artifact
  ladder, which is a different Background wearing the same name. Four ways to get a
  pointer wrong (dangling, chained, target unladdered, both fields set) are load problems.

**The duplicate it exposed.** Writing the test that reads the Mountain Folk Allies entry
turned up `backgrounds_for("Mountain-Folk")` returning **21 rows with all ten names
twice** — their own copies AND the core entries those replace. It hides whenever an
origin is passed (their catalogue list is keyed `Mountain-Folk:enlightened`) and the
editor defaults the origin, so the browser never showed it; a save written before the
axis existed, or any character built without an origin, gets the doubled list. Fixed
generally rather than in the data: **a splat's own tagged copy displaces the untagged one
of the same name**, in `backgrounds_for`, for every splat. Deliberately NOT applied under
`all_available` — there the ST asked for every book's version and the five Artifacts are
the point.

⚠ The lesson is the handoff's own trap, arriving from the other side: it was written up
as "a bare NAME offers the row twice", so the fix went into the LIST format and the
**fallback path was never checked**. A trap recorded as a data-authoring rule can still
be live as a code path.

**Tiger Warriors: signed off** (human, 2026-08-12). The reassembly across the page break
was already in the data and reads monotonic — 5/15/25/100/250 warriors, 1/2/3/4/5 heroic
mortals.

## The numeric rules — DONE, browser-verified 2026-08-12
`docs/briefs-background-rules.md` was the authoring brief; every ruling in it is CLOSED.
Suite **2,152 passing** at the time of writing.

**Review round two (2026-08-12).** The three review defects were fixed and verified
through the real path, and the fix to the last of them left one narrower opening, now
closed: the universal-cap pass skipped a Background whenever a rule merely EXISTED, so
the three rules that state no maximum — Alchemical Class (`min_rating`), Alchemical
Backing (`requires`), Illuminated Illumination (`min_rating`) — lost the cap at chargen
while keeping it post-lock. **A rule may RAISE the universal cap; it may never remove
it.** ⚠ The lesson is the rounds themselves: the universal 5 was once a structural
invariant on `BackgroundEntry.rating`, and every fix since relaxing that bound has been
re-deriving it from `BackgroundRule`, which was never meant to carry it. Three rounds,
each narrowing rather than closing. **When a structural invariant is relaxed, name where
it moved TO in the same change.**

**Connections is capped at 5 per row, and its printed TOTAL binds across rows.**
`max_rating` and `max_rating_is_attribute_sum` both read `background_rating`, which SUMS
every row sharing a name, so the printed cap ("the total number of dots in Connections may
not exceed" the Attribute sum) says nothing about one row — and the control first offered
the whole 27-dot allowance as pips. A per-row ceiling of 10 shipped briefly and was
reverted the same day (human: "row should be five"), taking `BackgroundRule.max_rating_per_row`
with it rather than leaving an unused mechanism behind. The row now keeps the universal 5
like every other Background; six rows of 5 against a sum of 27 errors, two rows of 5 do not.

⚠ **A fixture can hide behind a filtered error.** Four R1 tests used a SINGLE Connections
row of 10 — expressible only while the row ceiling was 10, and each asserted on
`background-above-attribute-cap` while filtering out the `background-above-universal-cap`
the same row now raises. They stayed green through a ruling that reversed the thing they
were testing. Fixtures are now rows within 5.

**The offer and the bar are separate mechanisms, and a toggle must move both** (browser,
2026-08-12): a mortal granted Storyteller permission still could not find Artifact or Manse
in the catalogue, because `catalogue_backgrounds` omitted them entirely and only the
`barred` rule lifted. Both mortal rows now list them, and `background_catalogue_for` hides
a barred Background until its toggle lifts it — the treatment `banned_backgrounds` already
had. Lifting a prohibition the player cannot then act on is worse than not offering the
toggle.

The already-modelled inventory stands unchanged (chargen-only): Mountain Folk Backing ≤2 /
Influence ≤1 / Mentor ≤3 (Unenlightened) and Resources ≤3 (both origins); Dragon-Kings
Celestial Manse ≤2 and Salary ≤2; Ghost Ancestor Cult and Grave Goods ≤1 (Immaculate);
God-Blooded Inheritance 1–5; Alchemical Class ≥3 with Backing requiring Class 3.

**R1 — Sidereal Connections ≤ the Attribute sum** (CHARGEN ONLY). A new `BackgroundRule`
field `max_rating_is_attribute_sum` — the DATA names what is summed, the engine never
hardcodes "Attributes" or the 27 a default chargen spend happens to sum to (Sidereals
pp.106-108).

**R2 — Sidereal Celestial Manse ≤3** (BOTH SIDES). `max_rating: 3` on the Sidereal row
with `bind_post_lock: true`, lifted by a PER-CHARACTER `HouseRules` toggle
(`st_celestial_manse_over_three`, Sidereals p.106) read through
`validate.background_st_permitted` — the `foreign_charms_permitted` shape, one read site,
no UI module learns the name.

**R3 — mortals barred from Artifact/Manse** (CHARGEN ONLY, both origins). A `barred` rule
on the `Mortal` and `Mortal:ordinary` rows — rating must be 0, distinct from
`banned_backgrounds` because a PER-CHARACTER toggle (`st_mortal_artifact_manse`, core
p.103 — the page was on disk all along) lifts it.

**R4 — Mountain Folk Artifact ≤10** (BOTH SIDES). `max_rating: 10` on both MF origin rows
(the ceiling is the human's call 2026-08-12 — the book prints no upper bound) and one
bonus point per dot above 5 via the new `bp_above_rating: 5`: dots 1-5 stay in the pool
(`cap_pre_bp_exempt` unchanged), dots 6-10 are `above_rates` at 1 each. Every other splat
still stops at 5.

**R5 — the plumbing, which was the real work.** `background_issues` now takes an OPTIONAL
`character` (the merits-flaws silent-fallback shape) and a `post_lock` flag; it is called
post-lock from `validate.validate` and applies ONLY rules flagged `bind_post_lock`, so
every other splat's caps keep behaving exactly as before (pinned by a test — a locked
Unenlightened Mountain Folk can be given Backing 4 by the story). Both rating controls
read their ceiling from a new `validate.background_rating_cap`: the hardcoded 5s in
`cap_for` and the play `ui.number` are gone.

Backgrounds have **no XP path at all** (`advancement.py` does not know them) — post-lock
they are free story edits. "Binds post-lock" therefore means a validation ceiling, never a
purchase price. R4's per-dot cost is likewise chargen-side; a dot gained by story pays
nothing.

**Skipped deliberately** (still) — Mountain Folk Backing ≤3 "for private organizations"
(narrative); "non-ronin Sidereals do not generally start with Resources" ("do not
generally" is a ruling, not a threshold).

**What the work turned up on the way:**
- **The model was a THIRD hardcoded 5.** The brief listed the two UI controls, but
  `BackgroundEntry.rating`'s pydantic `le=5` also blocked R4 — a rating of 10 could not
  even be STORED (construction raised). Relaxed to `le=10`, the highest ceiling the build
  supports (the human's R4 number). Every real ceiling stays the engine's job
  (`background_issues` / `background_rating_cap`), which is the model's contract.
- **The code review found the sharpest form of the house bug: `validate_chargen` never
  passed the character to `background_issues`.** The new optional `character` was a silent
  fallback (the merits-flaws shape), and the real caller omitted it — so the Attribute-sum
  cap and both PER-CHARACTER toggles never ran in production. All nine first-pass tests
  called `background_issues(b, bgs, c)` directly, so the read site was tested and the
  caller was not. Exactly what `docs/delegated-authoring.md` predicts: an optional
  parameter needs a test through the caller. Three tests now drive `validate_chargen`.
- **Relaxing the model removed the only structural enforcement of the universal cap.**
  `le=5` used to hold every Background with no rule at 5 on both sides; with `le=10` a
  hand-edited Solar Artifact 10 passed clean. `background_issues` now enforces the
  universal cap itself (`background-above-universal-cap`) on both sides, raising it only
  where a rule says so (the MF Artifact ≤10).
- **The Attribute-sum cap is a TOTAL, not a per-row ceiling.** The first pass had
  `background_rating_cap` return the whole attribute sum as one row's pip ceiling — a
  wall of dots. The per-row control stays at the universal 5; the total (via
  `background_rating`, which sums duplicates) is `background_issues`' job.
- **`st_toggle` is a field-name pointer read via `getattr`.** A data typo silently never
  lifts (fails toward over-restriction, the safe direction). Not link-checked at load;
  the R2/R3 tests drive both toggles, so a typo breaks them. Flagged rather than silently
  trusted.

**Tests** — `tests/test_background_rules.py`, **18 tests**, one per binding (12 from the authoring run, 3 from the review rounds, 3 render-matrix shapes added by `preflight`). Which pins which:
R1 (cap is the COMPUTED attribute sum, never the literal 27; BP on Attributes raises the
allowance; the same cap fires through `validate_chargen`, not just `background_issues`),
R2 (errors at chargen AND post-lock; the per-character toggle lifts both; a second
character at the same table is unaffected), R3 (both origins, both Backgrounds; toggle
lifts; a Solar is unaffected; the toggle also lifts through `validate_chargen`), R4 (10
legal / 11 refused on both sides; dots above 5 cost one bonus point each; no other splat's
Artifact ceiling moved), R5 (the chargen dot track offers 10 pips for a Mountain Folk
Artifact row and 5 for a Solar one; the play number input accepts 7 for the former and
refuses it for the latter — both through the UI harness, where the hardcoded 5s were
invisible to engine tests; the post-lock call site does not move the chargen-only caps;
the universal cap holds a no-rule Background at 5 on BOTH sides — the Solar Artifact 10
case the relaxed model had exposed).

**Click-through record — the numeric rules (2026-08-12).** Verified by the human, after
`preflight`: Mountain Folk Artifact showing 10 pips at chargen and accepting 10 in play,
1 BP per dot above 5; every other splat's Artifact stopping at 5 on both sides; Sidereal
Connections at 5 pips per row with the TOTAL flagged when the summed rows pass the
Attribute sum; Celestial Manse ≤3 erroring on both sides and its PER-CHARACTER toggle
clearing both; the mortal Artifact/Manse bar and its toggle; the two new ST Options rows
reading "No effect: …" for a splat they do not touch.

Two rounds of clicking, and the browser found what the harness could not both times: the
mortal toggle lifted the bar without revealing the Backgrounds, and Connections offered a
row ceiling that was legal but looked like nothing else on the sheet.

## Click-through record (2026-08-12)
Verified by the human: the rung following the dot track at chargen; the rung following the
number input in play; the dialog's full ladder including the two deliberate no-ladder
entries; the house-rules toggle's live count AND the Advantages dropdown picking it up
after a tab switch; the Ghost "Arcanoi" wording; the Sidereal and God-Blooded offered
lists. Ladder rungs read correctly. The readability change (blank lines +
`whitespace-pre-line`) landed after that pass and is covered by test, not by eyes.
