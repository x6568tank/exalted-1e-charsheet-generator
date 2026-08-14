# Plan — the printable / PDF character sheet

**Status:** IMPLEMENTED 2026-08-14, suite green, awaiting the human's browser
verification and a packaged-build check. What actually shipped, and the three traps
that fired during the build, are in **`docs/status/printable-sheet.md`** — read that
first; this file is the plan it was built from. Written 2026-08-14.
**Closes:** open TODO 1 in `CLAUDE.md` ("A printable / PDF character sheet").

## The decision that shapes everything

**A real generated PDF, not a print stylesheet.** The human tried `Ctrl+P` on the
Sheet tab and rejected it: *"Looks like shit."* It prints the app's DOM — tinted
cards, truncated flex rows, tab chrome — and no amount of `@media print` turns a
screen layout into a sheet. **There is no print-stylesheet phase.** We take the
same data the Sheet tab renders from and lay out a document designed for paper.

That is the whole reason this is cheap: `SheetView` already exists and is already
pure. `build_sheet_view(ruleset, character)` does every lookup, resolves every id,
and hands back a dataclass with no ruleset and no callbacks in it. A second
renderer over that same dataclass is a presentation job with no game logic in it
at all.

## Decisions taken (human, 2026-08-14)

| # | Decision | Consequence |
|---|---|---|
| 1 | **reportlab**, not fpdf2, not WeasyPrint | Platypus flowables give tables, frames, `KeepTogether` and automatic pagination. WeasyPrint was rejected on native deps (pango/cairo) breaking the PyInstaller onefile build. |
| 2 | **Charms and spells print as NAMES AND COSTS ONLY** | No description text anywhere. No appendix. Applies equally to Dragon-King Path powers (`PathRow.powers[].text` is dropped, name/cost/duration kept). |
| 3 | **Notes print; rules text does not** | Background notes, artifact source, M&F `detail`, animal-form notes, Fetter/Passion notes all print inline. The M&F tooltip's rules-text half is dropped; its printed-cost half prints anyway. |
| 4 | **Neither build-time block prints** | No Validation panel, no XP ledger. The experience TOTAL prints as one line. |
| 5 | **Splat-themed, print-tuned** | Accent colour from `theme.palette()` on headings and hairline rules; white page, no filled card tints. A Dragon-Blooded sheet still reads crimson. |
| 6 | **Paper size is chosen at export time** | A4 / Letter selector in the export dialog. Not persisted — it is a per-export choice, not a house rule. |

Taken here rather than asked, because it follows `render_sheet` and reversing it
would be a surprise: **an empty panel is dropped, not printed as "—".** One layout
for every splat; the splat differences are already the presence or absence of
panels (Fetters, Colleges, Paths, breed weapons, elemental powers).

## Architecture

**New module: `exalted_builder/ui/pdf.py`.** One public function:

```python
def build_pdf(view: SheetView, *, paper: str = "A4") -> bytes: ...
```

Three constraints on it, each of which pays for itself:

1. **It takes a `SheetView` and nothing else.** No `RuleSet`, no `Character`, no
   callbacks — exactly the purity `render_sheet` already has, and for the same
   reason: it makes the thing testable headlessly and usable from the GM party
   screen without a second code path.
2. **It must not import `nicegui`.** It imports `reportlab` and `theme` (which is
   itself pure — dataclasses only). A test asserts this. That keeps it in the set
   of modules the Qt port carries over unchanged (`docs/plans/qt-port.md`), so a
   PySide6 build gets PDF export for free.
3. **It lives in `ui/`** — `CLAUDE.md`'s instruction, and correct: nothing about
   page geometry is game logic.

The UI wiring (button, dialog, download) lives in `ui/builder.py` and `ui/gm.py`
beside the save/load flow it mirrors, not in `pdf.py`.

## Layout

**Page 1 — the sheet proper.** Follows `render_sheet`'s reading order, because the
human already approved that order on screen:

- Header band: name · player · caste/aspect · exalt type · concept · nature ·
  anima · lock state.
- Attributes — three columns, one per category.
- Innate Weapons (Dragon-King breeds only) — the printed Spd/Acc/Dmg/Def line.
- Abilities — the caste/ability groups, three columns per row, `●`/`✦` markers.
- Advantages band — Backgrounds, Artifacts, Fetters, Passions, Specialties,
  Merits & Flaws, Colleges, Thaumaturgy. Each panel dropped when empty.
- Bottom band — Equipment (weapons/armour stat lines, Forms, Anima, Virtue Flaw) ·
  Willpower / Soak / Health · Virtues / Essence / Experience total.

**Page 2+ — holdings.** Charms & Sorcery by section (`view.charm_sections`, so a
Ghost's read "Arcanoi" and a Lunar's "Gifts"), then Spells, Elemental Powers,
Paths, Combos. Name · category · duration · cost, in flowing balanced columns.
This is where a Solar with 40 Charms spills to a third page, and it is the only
part that should.

**Dots are drawn, never typed.** A vector `circle()` flowable, filled or hollow,
with the `+N` overflow suffix `_dots()` already handles. Health boxes likewise.

## The traps, named in advance

- **⚠ reportlab's base-14 fonts are latin-1.** Every glyph the sheet leans on —
  `● ○ ✦ ★ ⚔ 🛡 ⚠ ✎ −` — is outside it and will print as a blank or a black box.
  Each becomes a drawn mark or an ASCII label. This is the single most likely way
  the first draft looks broken.
- **⚠ `Armor.mobility_penalty` is stored NEGATIVE** (`docs/status/dice-pools.md`).
  `app.py` prints it with `{:+d}` and gets the right answer; copy that format
  string verbatim rather than re-deriving the sign. A self-authored fixture will
  happily agree with the bug.
- **Long names overflow reportlab table cells** — they neither truncate nor wrap
  by default. Every free-text cell (Background names, custom Charm names, M&F
  details) must be a `Paragraph`, not a bare string.
- **The house bug is the real risk here**, and it has an exact shape in this job:
  a future splat adds a `SheetView` field, the Sheet tab renders it, and the PDF
  silently omits it forever. Nothing fails. See the first test below.

## Tests — written before the layout

**1. The field-coverage test, FIRST.** This is this job's version of the roll-up
membership test the `validate.py` refactor calls for, and it exists because
`CLAUDE.md`'s sharpest rule applies directly: *a zero-site field can still look
healthy.* Walk `dataclasses.fields(SheetView)`; assert each name is either read by
`pdf.py` or listed in an explicit

```python
_DELIBERATELY_OMITTED = {"issues", "xp_log", "xp_earned", "xp_spent",
                         "xp_available", "charms"}   # `charms` = flat dup of charm_sections
```

A new field then fails the test until somebody decides whether it prints. Decision
4's omissions are recorded as data, not as absence.

**2. Content round-trip, per splat.** Generate for all four `examples/` characters
plus one fixture per shipped splat; extract text with `pypdf` (test-only dep) and
assert every ability label and rating, every Charm name, every Background, every
M&F name and every Specialty appears.

**3. Negative controls.** Assert a validation error message and an XP-log label do
*not* appear — decision 4 enforced, not assumed. Per the worktree-`sys.path`
memory, use a character that actually has both.

**4. Purity.** Assert `nicegui` appears nowhere in `pdf.py`'s imports.

**5. Pagination.** A character with a large Charm holding produces >1 page and
raises nothing.

## Steps

1. `ui/pdf.py` skeleton + `build_pdf` returning a one-page stub. **Test 1 first**,
   then 4. Add `reportlab>=4` to the `ui`, `desktop` and `dev` extras.
2. Page 1: header, attributes, abilities. The dot flowable. Test 2 starts passing
   in pieces.
3. Page 1: advantages band, bottom band. All conditional panels.
4. Page 2+: charm sections, spells, powers, paths, combos. Tests 3 and 5.
5. UI wiring — an Export PDF button on the Sheet tab and beside Save in the header;
   a dialog with the A4/Letter selector and a filename. Reuse `builder.py`'s
   existing `_native_window()` / `ui.download.content` split verbatim; that
   branch is already correct for both the packaged app and a plain browser.
6. GM party screen: per-member export. One PDF for the whole party is nearly free
   with reportlab (`PageBreak` between stories) — offer it, do not assume it.
7. `pack/exalted-builder.spec`: reportlab ships data files and a `_rl_accel` C
   module, so it likely needs `collect_all("reportlab")`. **Verify by building the
   executable and exporting from it**, not by reading the spec.
8. Browser click-through across splats, and the human eyeballs four generated PDFs.
   Per `feedback_serve_and_grep_is_not_verification`: the tests prove no field was
   dropped, they prove nothing about whether it looks good. Only step 8 does.

## Estimate

`ui/pdf.py` ~600-800 lines, tests ~250, UI wiring ~80. The layout iteration in
steps 2-4 dominates, and step 8 is where the real cost lands — "looks good" is the
acceptance criterion and only the human can call it.
