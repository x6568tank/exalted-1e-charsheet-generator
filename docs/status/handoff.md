# Session handoff — 2026-08-14 (printable / PDF sheet)

**This file is rewritten each session.** The previous handoff covered the Book of
Three Circles and Groups A/B/C of the content re-triage; all of that is closed and
lives in `docs/status/content-gap-retriage.md` and
`docs/status/book-of-three-circles.md`. Nothing from it is outstanding.

## What shipped: open TODO 1, the printable character sheet

**A real generated PDF, not a print stylesheet.** The human tried `Ctrl+P` on the
Sheet tab first and rejected it — *"Looks like shit"* — because it prints the app's
DOM: tinted cards, truncated flex rows, tab chrome. **There is no `@media print`
route in the build and there must not be one.**

- `exalted_builder/ui/pdf.py` — reportlab. `build_pdf(view, *, paper="A4") -> bytes`,
  `build_party_pdf(views, …)`, `suggested_filename`, `normalize_pdf_filename`.
- A **Print** button on the builder header bar; a per-member PDF button and a
  **Print all** button on the GM party page (one document, one member per page).
- `tests/test_pdf.py` — 41 tests. Suite green.
- reportlab in the `ui` / `desktop` / `dev` extras, pypdf in `dev`;
  `pack/exalted-builder.spec` now `collect_all("reportlab")`.

Full record, including the human's six content rulings:
**`docs/status/printable-sheet.md`**. Plan: `docs/plans/print-pdf.md`.

## ⚠ Two things that are NOT done

1. **The human has not looked at it.** "Looks good" is the acceptance criterion for
   this feature and only they can call it. Ten sample PDFs were generated for that
   purpose — see *What to click* below.
2. **The packaged build is unverified.** `collect_all("reportlab")` is in the spec
   on reasoning, not on evidence. reportlab loads its base-14 AFM font metrics from
   data files at RUNTIME, so an import-only scan would miss them and the failure
   appears the first time somebody clicks Print in the packaged `.exe`. Build it and
   export from it.

## What to click, in priority order

Sample PDFs are already rendered under the session scratchpad (`sheets/`): the four
examples, five blank splats (Mortal / Ghost / Lunar / Dragon-Kings / Mountain Folk)
and a four-member party document. Regenerate any of them with `pdf.build_pdf`.

1. **`yarak.pdf`** — the richest one. Locked, Ox-Body (a nineteen-box wrapped health
   track), artifacts, a spell, orichalcum gear. If anything is ugly it is here.
2. **The Print button itself**, on a character you have edited but not saved — the
   export renders from the live in-memory character, not from disk.
3. **Print all** on a mixed-splat party. Each member starts a new page and carries
   its OWN splat accent colour.
4. **`nine-bells-ringing.pdf`** — Sidereal purple, Colleges with their House names
   printed (they are hover-only on screen), and no Charms at all.
5. **Letter as well as A4** — the selector is in the dialog, and it is a per-export
   choice by your ruling, not a stored setting.

## Open question for you (rules/presentation, not code)

**Nothing mechanical.** One presentational call you may want to reverse: Charm
`category` prints title-cased (`craft` → `Craft`, `martial_arts:snake-style` →
`Martial Arts: Snake-Style`) where the screen sheet prints the raw string. That was
my call, on the grounds that the raw form reads as a leaked internal on paper. Say
if you would rather the two surfaces matched exactly.

## Your one review finding so far, and what it generalised to

*"Specialties box doesn't zero out when there's nothing in it."* — **a panel holding
nothing is now dropped, never printed as a box containing "—".** `ui/app.py` keeps
the placeholder and should: on screen the panel is a landmark, on paper it is a
blank rectangle. **The two surfaces deliberately differ here.**

Fixed in all three places rather than the one reported: Specialties, Backgrounds and
Equipment. That turned up two more of the same shape — the Equipment panel is not
empty just because there is no gear (it also holds Forms / Anima / Virtue Flaw), and
the Advantages heading can now outlive its content the way the Charms heading could.

## The traps this job produced — worth carrying past it

- **⚠ A glyph that arrives as DATA cannot be caught by reading the renderer.**
  reportlab's base-14 fonts are WinAnsi, and `ui/view.py` bakes marks into display
  STRINGS: `view.health` carries `★` on a Charm-granted level, and
  `PathRow.favored` *is* a glyph (`★`/`✚`). The guard therefore asserts on the
  RENDERED page, not on the module source. ⚠ And it checks **cp1252, not latin-1** —
  the em dash and middle dot are in WinAnsi and print fine; a latin-1 check failed
  on healthy text.
- **⚠ Translating a mark is not enough — say what it MEANS.** Paper has no tooltip.
  `★` became `*` *with a printed legend*; the Sidereal House names and the
  custom/missing content marks became words for the same reason.
- **⚠ A heading must not outlive its content.** A Sidereal fresh out of chargen owns
  no Charms, and an empty "CHARMS" rule ruled across the page reads as a renderer
  that lost the list rather than a character who has none.
- **The field-coverage test is the house-bug guard, and it is the point of the
  file.** `test_every_sheetview_field_is_printed_or_declared_omitted` walks
  `dataclasses.fields(SheetView)`. On a PDF, an unread field is simply absent from
  the paper — there is no accidental second mechanism to cover for it the way the
  Ghost catalogue covered for `heritage_traits.magic_track`. **It will fail the day
  a new splat adds a field. Decide; do not silence it.**

## The two remaining open TODOs (unchanged)

2. **A martial-arts STYLE entity** — 22 styles have their Charms but no home for
   their preamble. A modelling job, not a reading one.
3. **Split `engine/validate.py`** — 5,791 lines, 47% of the engine.
   `docs/plans/validate-refactor.md`. ⚠ Write the roll-up membership test FIRST; the
   failure mode is the house bug.

Still deferred indefinitely and **not** gaps: the Mist numina, Cult Abyssals.
Training times are still a no.
