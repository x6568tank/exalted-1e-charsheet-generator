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

**All 31 are the bare form** as of the 2026-08-15 normalisation. `tests/test_data.py`
holds the same list as `CANONICAL_BOOKS` and fails on any spelling not in it, so this
table and that set must be edited together.

| Book | Write |
|---|---|
| Exalted core rules | `Core` |
| Player's Guide | `Player's Guide` |
| The Abyssals | `The Abyssals` |
| The Dragon-Blooded | `The Dragon-Blooded` |
| The Lunars | `The Lunars` |
| The Sidereals | `The Sidereals` |
| The Autochthonians | `The Autochthonians` |
| The Outcaste | `The Outcaste` |
| Aspect Books | `Aspect Book: <Element>` |
| Caste Books | `Caste Book: <Caste>` |
| Cult of the Illuminated | `Cult of the Illuminated` |
| Storyteller's Companion | `Storyteller's Companion` |
| Ruins of Rathess | `Ruins of Rathess` |
| Games of Divinity | `Games of Divinity` |
| Savant and Sorcerer | `Savant and Sorcerer` |
| Book of Bone and Ebony | `Book of Bone and Ebony` |
| Book of Three Circles | `Book of Three Circles` |
| Manacle and Coin | `Manacle and Coin` |
| Blood and Salt | `Blood and Salt` |
| Savage Seas | `Savage Seas` |
| Time of Tumult | `Time of Tumult` |
| Kingdom of Halta | `Kingdom of Halta` |
| Bastions of the North | `Bastions of the North` |
| Scavenger Sons | `Scavenger Sons` |
| The Mountain Folk chapter (in *The Fair Folk*) | `The Mountain Folk (CH6)` |

The model default is `Core` (`models/rules.py`), so a record that omits `source.book`
silently claims the core rules. **Set it explicitly on anything that is not core.**

## The naming normalisation — DONE 2026-08-15

The three prefix styles (bare, `Exalted 1e …`, `Exalted: …`) collapsed onto the **bare
form** in one commit: **1,635 replacements across 154 data files, 51 distinct book
strings down to 31**, plus six `tools/` emitters that would have re-introduced the old
spellings on their next run. Two guards now hold it — `test_every_source_book_is_a_
canonical_name` and `test_no_book_is_spelled_two_ways`, both in `tests/test_data.py`.

Three ambiguous spellings were resolved by looking at the pages, not by guessing:
`Exalted` (weapons p.330, dice pools p.228) and `Exalted Core` (virtue flaws pp.131-132,
artifacts pp.336-337) are both the **core book**; `Mountain Folk` (artifacts pp.279-283)
and `Exalted: The Mountain Folk (CH6)` (Charms pp.245-256) are both **The Fair Folk ch.6**.

### ⚠ This file's own list of affected tests was incomplete — by three

It named four test files. **Seven sites existed.** The three it missed:

- `tests/test_solar_castebooks.py` — eleven literals, the largest single site
- `tests/test_godblooded.py` — `== "Exalted 1e The Autochthonians"`
- `tests/test_data.py` — `== "Mountain Folk p.279"`

The last one is the instructive one, and it is the **verification-shape trap** in its
purest form. A grep for bare book names cannot see it, because the string-shaped
`source` embeds the page in the same literal. **A `source` is two shapes — a
`{book, page}` dict and a `"Book p.12"` string — and any sweep that knows only one
silently passes the other.** `_authored_books()` in `tests/test_data.py` reads both;
copy it rather than writing a third walker.

The general lesson: **a doc's list of call sites is a hint, not an inventory.** This one
was written when it was true and rotted exactly like the field it describes. Grep.

## ⚠ The 2026-08-10 fix was INCOMPLETE — found 2026-08-15

The August fix moved all 233 Abyssal **Charms** off `Core`. It did not touch the **23
necromancy spells**, which sat attributed to `Core` pp.224-229 for another five days.
The corebook prints sorcery on pp.217-223 and **no necromancy at all** — the
Shadowlands, Labyrinth and Void Circles were introduced in *The Abyssals*, whose
necromancy chapter is exactly pp.224-229. Verified against the page (the Abyssals PDF
runs printed + 1; PDF p.225 is headed "NECROMANCY AND OTHER EXALTED") and corrected.

**The rule this gives you: when you find a misattribution, sweep every record TYPE in
that book, not just the one that reported it.** A book contributes Charms *and* spells
*and* artifacts *and* gear, they live in different files, and a fix aimed at one file
leaves the others wrong while the count in the fixed file looks healthy.

Two guards now sit in `tests/test_data.py`:
`test_no_necromancy_spell_claims_the_corebook` and, as its positive half,
`test_the_corebook_sorcery_spells_are_still_there` — which pins the 19 real corebook
spells at pp.217-223 so a future re-sweep cannot drag them out with the necromancy.

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
