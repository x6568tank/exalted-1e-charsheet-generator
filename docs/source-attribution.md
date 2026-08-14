# Source attribution — how `source.book` is written

Every rules record in `data/` carries a `source` of `{book, page}`. The page is what
makes a value auditable; **the book is what makes the page mean anything**, and it is
the field most likely to be wrong, because nothing in the app reads it. It is pure
provenance — which is exactly why it rots silently.

## The rule

**`source.book` names the book the value was PRINTED in, not the splat it belongs to
and not the book the reader would guess.**

A Charm on an Abyssal's sheet is not automatically from *The Abyssals*; a Mountain Folk
Charm is printed in *The Fair Folk*. **The book is not the splat.** Write down where the
ink is.

Two consequences:

- **A reprint follows [[source-precedence-rule]]** — later content supersedes earlier, so
  attribute to the printing whose text you actually used. (Ruins of Rathess wins over
  the companion; the Illuminated printing wins on duplicate Solar Charms.)
- **A splat drawing on several books gets several values**, and that is correct, not a
  defect. Solar Charms carry `Core`, five Caste Books and `Cult of the Illuminated`;
  Dragon-Blooded carry the main book, five Aspect Books and `The Outcaste`.

## Why this matters mechanically

`source.book` is a **zero-read-site field** — the classic shape of this codebase's
recurring bug (see CLAUDE.md → *The house bug*, and [[dead-effect-fields]]). Nothing
validates it, so a wrong value survives indefinitely and every test passes.

It bit on **2026-08-10**: all **233 Abyssal Charms** were attributed to the core book
while carrying pages 157-229, which are *The Abyssals*. Nothing was broken by it for
months — until the content-gap diff tried to match tree entries against build entries
*by book*, and 7 Charms that were already present were reported missing. **The cost of a
wrong book value is not a wrong game rule; it is a wrong answer from any tool that
reasons about provenance.** Fixed same day.

## Canonical names

The current values, and the one to write for new work:

| Book | Write |
|---|---|
| Exalted core rules | `Core` |
| Player's Guide | `Player's Guide` |
| The Abyssals | `Exalted: The Abyssals` |
| The Dragon-Blooded | `Exalted 1e Dragon-Blooded` |
| The Lunars | `Exalted 1e The Lunars` |
| The Sidereals | `Exalted 1e The Sidereals` |
| The Autochthonians | `Exalted 1e The Autochthonians` |
| The Outcaste | `Exalted 1e The Outcaste` |
| Aspect Books | `Exalted 1e Aspect Book: <Element>` |
| Caste Books | `Exalted 1e Caste Book: <Caste>` |
| Cult of the Illuminated | `Exalted 1e Cult of the Illuminated` |
| Storyteller's Companion | `Exalted 1e Storyteller's Companion` |
| Ruins of Rathess | `Exalted 1e Ruins of Rathess` |
| Games of Divinity | `Games of Divinity` |
| The Mountain Folk chapter (in *The Fair Folk*) | `Exalted: The Mountain Folk (CH6)` |

The model default is `Core` (`models/rules.py`), so a record that omits `source.book`
silently claims the core rules. **Set it explicitly on anything that is not core.**

## ⚠ The naming is not yet consistent — an open cleanup

Three prefix styles are in use: bare (`Core`, `Player's Guide`, `Games of Divinity`),
`Exalted 1e …` (most books), and `Exalted: …` (the Abyssals, the Mountain Folk chapter).
**This is cosmetic, not a correctness problem** — every value above is unambiguous — but
it makes book-keyed tooling need an alias table.

Normalising on the bare form (`The Abyssals`, `Aspect Book: Air`, …) is the obvious
follow-up. It is **not done**, because it is a data-wide rename with live test
assertions on the current strings:

- `tests/test_ghost.py` — `== "Exalted: The Abyssals"`
- `tests/test_dragonblooded_origins.py` — `== "Exalted 1e The Outcaste"`
- `tests/test_dragonblooded_aspect_books.py` — `startswith("Exalted 1e Aspect Book:")`,
  and a `split(": ")[1]` that a rename must not break
- `tests/test_illuminated.py` — a module-level `_ILL_BOOK` constant

Do it as one deliberate commit with those four files, or not at all. Do **not** rename
opportunistically while doing other work.

## When you cannot tell

The never-author-from-memory rule applies to `source.book` exactly as it does to a cost
or a minimum. If you do not know which printing a value came from, **ask** — do not
guess from the splat, and do not copy the neighbouring record's book because it looks
right. A wrong attribution is worse than an absent one: it reads as verified.


## ⚠ `images/_extracted/Exalted Core.md` page markers run ONE LOW (found 2026-08-14)

The extractor emits `<!--PAGE n-->` *before* the page body, so content after a marker
belongs to page n — but for the **corebook extraction specifically** that `n` is one
lower than the printed folio. Verified against the PDF at `pdftoppm -r 100`:

* Wind-Defying Course Technique sits between the extraction's `PAGE 209` and `PAGE 210`
  markers, but is printed on **210** (and the corebook index agrees).
* The extraction's `PAGE 210` marker is followed by Storm-Weathering Essence Infusion,
  which is printed on **211**.

**So: a page number read off that file's markers needs +1.** This bit once already — an
attribution was questioned as "should be 209" when the stored 210 was correct all along.
Cite from the printed folio or the book's own index, not from the marker, and when the
two disagree, rasterise the page and look at the number in the footer.

The offset is a property of THIS extraction, not of the tool. Do not assume it for other
books; check one known entry per book before trusting the markers.
