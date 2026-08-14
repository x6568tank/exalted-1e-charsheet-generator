# Session handoff — 2026-08-14 (printed sheet + martial-arts styles)

**Rewritten each session.** Suite: **2,420 passing**, one warning (the pre-existing
71-entry M&F source-text deferral — see the ⚠ in CLAUDE.md's Status section; it is
machine-dependent, not a regression).

Two of the three open TODOs were closed or half-closed today.

## 1. The printable / PDF sheet — DONE, fully verified

`docs/status/printable-sheet.md`. **Browser-verified AND packaged-build-verified by
the human the same day** (loaded a character and printed from a freshly rebuilt
`dist/ExaltedBuilder`), so `collect_all("reportlab")` in the spec is confirmed
sufficient. Committed as `02da1cd`.

⚠ **There is no print stylesheet and there must not be one.** `Ctrl+P` prints the
app's DOM and was rejected. `ui/pdf.py` takes a `SheetView` and nothing else and
imports no `nicegui`.

The one review finding — *"Specialties box doesn't zero out when there's nothing in
it"* — generalised to **a panel holding nothing is dropped, never printed as a box
saying "—"**, applied to Specialties, Backgrounds and Equipment. `ui/app.py` keeps
the placeholder and should: the two surfaces differ deliberately.

## 2. Martial-arts STYLE entity — PHASE 1 DONE, **not browser-verified**

`docs/status/martial-arts-styles.md`, plan `docs/plans/martial-arts-styles.md`.
`MartialArtsStyle` (printed `Type:`, preamble, style-level `mechanics`), the loader
and link check, a collapsible preamble panel on the picker's Martial Arts page, and
**4 of 22 styles authored** off the Player's Guide. 13 tests.

### 👉 What to click (the only thing outstanding on this work)

Nobody has seen the preamble panel in a browser. Charms tab → Martial Arts page:

1. **Righteous Devil** — the panel should carry its `Type: Celestial`, two
   paragraphs of prose, the firewand "Weapons and Armor" rule, and `Player's Guide
   p.254`. Check the paragraph break survived (`whitespace-pre-line`).
2. **Tiger, or any of the other 17 unauthored styles** — there must be **no panel at
   all**, not an empty box.
3. **Dreaming Pearl Courtesan** — four `mechanics` rules, the longest list; check it
   does not crowd the tree.

## Open question waiting on you

**None.** The one rules question this work raised — Righteous Devil's
`open_to_tiers` divergence — you ruled on: **correct as printed, Solar-only**. It is
recorded in the test as a documented exception with a second test pinning the
exception set to exactly that one Charm, and in CLAUDE.md as *do not "fix" it*.

## Where the work goes next

1. **Martial-arts Phase 2 — the other 18 preambles.**
   `rules_db.unauthored_martial_arts_styles` is the pinned worklist; every source is
   in `sources/`. **Jade Mountain first** — the example the TODO was written around,
   its three mechanics already transcribed in `dragonblooded-aspect-books.md`.
   ⚠ `martial_arts:enlightenment` is the Dragon-Path initiation tree, **not a
   style** — it gets an entry only if its page carries a preamble of its own.
2. **Split `engine/validate.py`** — unchanged, `docs/plans/validate-refactor.md`.
   Write the roll-up membership test FIRST.

## The trap worth carrying out of today

**Matching content by NAME failed three separate ways in one session** — a loose
matcher that found "snake"/"tiger" in every book, a strict header matcher that then
declared 18 present styles absent, and a regex that missed `WEAPONSAND ARMOR`
(no space). **Book + page off the entry's own `source` is what worked every time.**
And a name match can land in the wrong CHAPTER of the right book: two "Celestial
Monkey Style" hits in the Player's Guide are an astrology correlations table.

This is `feedback_gap_matchers_wrong_both_ways` firing three more times, in an area
it had never bitten before. It is now in CLAUDE.md's traps list.

Still deferred indefinitely and **not** gaps: the Mist numina, Cult Abyssals.
Training times are still a no.
