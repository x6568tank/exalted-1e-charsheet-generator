# The printable / PDF character sheet

**Status: DONE 2026-08-14 — browser-verified AND packaged-build-verified the same
day** (the human loaded a character and printed from a freshly rebuilt
`dist/ExaltedBuilder`; `collect_all("reportlab")` in the spec is confirmed
sufficient, so reportlab's runtime AFM font data does reach the onefile bundle).
Suite green at 2407.
Plan and the decisions behind it: `docs/plans/print-pdf.md`. Closes open TODO 1 in
`CLAUDE.md`.

## What shipped

A real generated PDF, not a print stylesheet. **The human tried `Ctrl+P` on the
Sheet tab and rejected it** — it prints the app's DOM, tinted cards and truncated
flex rows included. There is no `@media print` route in the build and none was
attempted.

- **`exalted_builder/ui/pdf.py`** — `build_pdf(view, *, paper="A4") -> bytes` and
  `build_party_pdf(views, …)`, plus `suggested_filename` / `normalize_pdf_filename`.
- **A Print button** on the builder's header bar, beside Save/Load. A dialog asks
  paper size (A4 / Letter, per-export, not stored) and a filename, then hands the
  bytes to the same native-window / browser-download split `save()` already used.
- **The GM party screen** gets a per-member PDF button and a **Print all** button
  that renders every member into one document, one per page.
- **`tests/test_pdf.py`** — 33 tests.
- reportlab added to the `ui`, `desktop` and `dev` extras; `pypdf` to `dev` (the
  tests read the rendered pages back). `pack/exalted-builder.spec` now
  `collect_all("reportlab")`.

## The shape, and why it is that shape

`build_pdf` takes a **`SheetView` and nothing else** — no RuleSet, no Character, no
callbacks — which is the purity `app.render_sheet` already had. Three things fall
out of it: the GM party export is a list rather than a second layout, the tests
render real documents with no browser, and the module imports no `nicegui` (a test
asserts it by parsing the import statements, not by grepping the text — the
docstring mentions the word). That last one keeps it in the set of modules the Qt
port carries over untouched.

**The Print button is on the header, not on the Sheet tab.** `render_sheet` takes a
SheetView and no callbacks, and a button inside it would need one — which would
break the GM party screen and the render tests that depend on that purity.

## The human's content rulings (2026-08-14)

1. reportlab, not fpdf2 (Platypus pagination) and not WeasyPrint (native deps would
   break the PyInstaller onefile build).
2. **Charms and spells print as names and costs only.** No description text
   anywhere, no appendix. Dragon-King Path powers follow the same rule —
   `PathPowerRow.text` is dropped, name/type/duration/cost kept.
3. **Notes print, rules text does not.** Background notes, artifact source, M&F
   `detail`, animal-form notes all print. The M&F tooltip's rules-text half is the
   one casualty; its printed-cost half prints anyway.
4. **Neither the Validation panel nor the XP ledger prints.** The experience TOTAL
   does. `DELIBERATELY_OMITTED` records this as data, and a test pins the set.
5. Splat accent on a white page, hairline borders, no filled card tints.
6. Paper size is chosen at export time.

## The field-coverage test — read this before adding a splat

`test_every_sheetview_field_is_printed_or_declared_omitted` walks
`dataclasses.fields(SheetView)` and fails on any field that `ui/pdf.py` neither
reads as `view.<field>` nor names in `DELIBERATELY_OMITTED` / `READ_VIA_METHOD`.

It exists because of this project's recurring bug in its sharpest form. **A new
splat adds a field, the Sheet tab renders it, and the PDF omits it forever — and
nothing fails, because on paper an unread field is just absent.** There is no
accidental second mechanism to cover for it the way the Ghost catalogue covered for
`heritage_traits.magic_track`. The test also rejects a *stale* entry in either
list, so a renamed field cannot silence it.

**If you add a SheetView field, this test will fail until you decide.** That is the
whole point; do not add the name to `DELIBERATELY_OMITTED` to make it pass.

## ⚠ No panel prints an empty box (human, 2026-08-14)

Raised on review: *"Specialties box doesn't zero out when there's nothing in it."*
**A panel holding nothing is DROPPED, never printed as a box containing "—".**

`ui/app.py` prints the placeholder, and that is right on screen — the panel is a
landmark you return to, and it will fill up. On paper it is a blank rectangle
taking a third of a row to say nothing. **The two surfaces deliberately differ
here; do not "fix" the PDF to match the screen.**

Applied to all three offenders, not just the one reported — Specialties,
Backgrounds and the Equipment panel — because they were one defect with three
instances. Two consequences fell out, and both are now tested:

- **The Equipment panel is not empty merely because there is no gear.** It also
  holds Forms / Anima / Virtue Flaw; an Alchemical with no weapons still has an
  Anima, and the panel was printing "—" above it for the gear that was not there.
  It is dropped only when all six are absent, and it loses its TITLE when it holds
  no gear (the remaining sections have their own sub-headings, and a title there
  sits directly under the band's own "TRAITS" rule saying the same word twice).
- **⚠ Dropping a panel re-spreads its band; the column count is decided BEFORE
  anything is built.** A `_Panel`'s inner tables are laid out against the width it
  was constructed with, so widening one afterwards leaves its contents at the old
  width — the dots detach from their labels and the panel looks half-empty. The
  first cut did exactly that.
- **The Advantages heading can now outlive its content**, since every panel under
  it is droppable. Guarded, same as the Charms heading.

## Traps, three of which fired during the build

- **⚠ Every glyph is drawn or ASCII.** reportlab's base-14 fonts encode as WinAnsi
  (cp1252). Dots, caste/favoured marks and health boxes are vector art;
  everything else became words. **This is not only about this module's own source
  — `ui/view.py` bakes marks into DISPLAY STRINGS that arrive as data.**
  `view.health` carries `★` on a Charm-granted level and `PathRow.favored` is
  literally `★` or `✚`. Reading `pdf.py` cannot catch those, so
  `test_no_unprintable_glyph_reaches_the_page` asserts on the RENDERED page
  instead. The `★` became `*` **with a printed legend** — paper has no tooltip, so
  a mark the sheet never explains is noise.
  ⚠ The guard is **cp1252, not latin-1**: the em dash, bullet and middle dot are
  all in WinAnsi and print correctly. A latin-1 check fails on healthy text (it
  did, first try).
- **⚠ The health track WRAPS.** An Ox-Body Solar has nineteen levels; a single-row
  track ran out of its panel and printed over the Virtues beside it. Nothing in
  `_HealthTrack` assumes seven boxes. (And when the legend was added, the reserved
  strip was subtracted from the FIRST row instead of the last — the rows then
  printed on top of the legend. Rows fill from the top; the strip is already in
  `height`.)
- **⚠ A heading is emitted only if something follows it.** A Sidereal fresh out of
  chargen owns no Charms, and an empty "CHARMS" rule ruled across the page reads
  as a renderer that lost the list, not as a character who has none.
- **`Armor.mobility_penalty` is stored NEGATIVE.** The equipment format strings are
  `ui/app.py`'s verbatim for that reason; do not re-derive the sign here.
- **Free text is escaped.** Every string on this sheet can come from a save file or
  the custom library, and Paragraph text is mini-HTML — a character named
  "Sword & Shield" would raise.

## Layout

Page 1 follows `render_sheet`'s reading order (already approved on screen): header,
Attributes, Innate Weapons (Dragon-King breeds), Abilities, Advantages, then the
Equipment / Willpower-Soak-Health / Virtues-Essence band. Holdings follow — Charms
by section, Spells, Paths, Combos — as flowing tables with repeating headers.

**No forced page break before the holdings.** A `CondPageBreak(45mm)` moves them on
only when too little room is left; a hard break spent a third of a page on nothing.

## Still to do

1. **Browser click-through** — the acceptance criterion here is "looks good", and
   only the human can call it. The tests prove no field was dropped; they prove
   nothing about the design.
2. **A packaged-build check.** `collect_all("reportlab")` is in the spec but has
   NOT been verified by building the executable and exporting from it. reportlab
   loads its base-14 AFM metrics from data files at runtime, so an import-only scan
   would miss them and the failure appears the first time someone clicks Print in
   the packaged app.
