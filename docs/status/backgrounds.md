# Backgrounds — the overhaul (2026-08-11 → 2026-08-12)

**DONE, browser-verified 2026-08-12.** Suite **2,134 passing**.

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

## Still open, and needs no pages
**Engine enforcement of the Background numeric rules** — the last item from the original
ask. The thresholds are now visible in committed data (descriptions and ladders):
Sidereal Connections capped at total Attributes (27 at chargen), Celestial Manse ≤3
without ST permission, Sidereal Resources ronin-only, mortals barred from Artifact/Manse
without permission, Mountain Folk Backing ≤2 for the Unenlightened. Most map onto existing
`BackgroundRule` fields; Connections needs a new "cap from a trait total" field. Read
`engine/artifacts.py` first — it is the precedent, and the rule of the area is thresholds
as DATA, nothing splat-specific in code.

## Click-through record (2026-08-12)
Verified by the human: the rung following the dot track at chargen; the rung following the
number input in play; the dialog's full ladder including the two deliberate no-ladder
entries; the house-rules toggle's live count AND the Advantages dropdown picking it up
after a tab switch; the Ghost "Arcanoi" wording; the Sidereal and God-Blooded offered
lists. Ladder rungs read correctly. The readability change (blank lines +
`whitespace-pre-line`) landed after that pass and is covered by test, not by eyes.
