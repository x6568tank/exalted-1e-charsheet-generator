# Content gap — re-triage after `sources/` landed (2026-08-13)

`docs/status/content-gap-entries.md` was generated **2026-08-10**, before the six sweep
batches ran and before `sources/` was on this machine. Its "Pages on disk?" column and
its 213-entry residue are both stale. This file is the re-triage; the entry lists in the
old file are still correct as *discovery* (name · book · page) and are not regenerated.

**Method:** re-diffed all 647 gap rows against the current catalogues (1,818 Charm names,
246 spells, 222 artifacts plus rated gear rows), matching exact → substring →
fuzzy ≥0.86, same filters the original used. Script kept in the session scratchpad; it
reads only committed files, so it is reproducible from this description.

**467 of the 647 have been authored since. 180 remain — 120 after the Book of Three
Circles was read on 2026-08-13 (`book-of-three-circles.md`), which closed 60 of them
and left 2 unauthorable.**

⚠ **The first pass said 199, and 19 of those were a matcher bug — read this before
trusting any gap number.** The diff compared `name` fields only, and **a Charm modelled as
a `variants` menu on its parent has no `name`**. All 16 "missing" Lunar Charms (pp.126-127)
and 3 of the Player's Guide 5 (p.207) are the Deadly Beastman Transformation **Gifts**,
authored as 22 variant labels on one Charm and browser-verified long ago. The build holds
41 variant labels across 11 files; the matcher now reads them.

This is trap #1 from `catalogue-sweep.md` firing again, one level up: **a search shaped
like a Charm row proves nothing about a Charm modelled as a menu.** The tell was there in
the data — `lunar_shapeshifting.json` cites "p.126-127; see `variants` for the Gift menu"
in the parent's own description.

## The re-triage, by what unblocks it

| Group | Entries | What it needs |
|---|---|---|
| **A — born-digital, never extracted** | **63** | `tools/extract_born_digital.py`, today, no new tooling |
| **B — pure scans** | **101** (39 left) | rasterise with `pdftoppm`, then read the pages |
| **C — leftovers in already-extracted books** | **16** | case by case; 8 of them are closed, see below |

### Group A — 63 entries, extractable now

Every one of these books is in `sources/`, born-digital, and **not ciphered** — spot-read
of a body page in each returns clean English. None was extracted in the 2026-08-10 run.

| Book | Charms | Spells | Artifacts | Total | Gap pages |
|---|---|---|---|---|---|
| Aspect Book: Air | — | — | 13 | **13** | 75-78, 81 |
| The Abyssals *(the OCR'd copy — carries text)* | — | — | 14 | **14** | 254-261 |
| Blood and Salt | — | 2 | 9 | **11** | 89, 119-124 |
| Aspect Book: Earth | — | — | 6 | **6** | 79-81 |
| Kingdom of Halta | — | — | 5 | **5** | 93-95 |
| Cult of the Illuminated | — | — | 4 | **4** | 69-70 |
| Aspect Book: Wood | — | — | 4 | **4** | 79-81 |
| Aspect Book: Water | — | — | 3 | **3** | 80-81 |
| Aspect Book: Fire | — | — | 2 | **2** | 79-81 |
| Manacle and Coin | — | — | 1 | **1** | 31 |

The five Aspect Books are 28 artifacts across the same three-page slot in each book, and
`parse_mc_prices.py` already proved Manacle and Coin's two-column pages parse.

### Group B — 101 entries behind pure scans (**39 left** — BOTC is done)

0 characters of text in the whole PDF; `extract_born_digital` and `solve_cid_bands` both
inapplicable. These need `pdftoppm -r 110` (proved on The Lunars) and then **the pages
read**. ⚠ **The Ollama VLM leg is for a non-visual model** — human, 2026-08-13. A
vision-capable model reads the rasterised pages directly, and the
`vlm-cannot-count-dots` caution is about the *small local VLM*, not about page reading
as such. It still applies to anything `vlm_read_ratings.py` produces.

| Book | Charms | Spells | Artifacts | Total | Gap pages |
|---|---|---|---|---|---|
| ~~Book of Three Circles~~ | — | ~~48~~ | ~~14~~ | ~~**62**~~ | **DONE 2026-08-13 — 60 authored, 2 print `(ARTIFACT N/A)`; `book-of-three-circles.md`** |
| Savage Seas | 10 | 4 | 3 | **17** | Charms 114-116 · spells 117-118 · artifacts 123-124, 127 |
| Time of Tumult | 2 | — | 11 | **13** | Charms 95-96 · artifacts 15, 23, 49, 94-95 |
| Sidereals | — | 2 | 3 | **5** | spells 122-123 · artifacts 24, 39 |
| Storyteller's Companion | — | — | 4 | **4** | 78-80 |

~~**Book of Three Circles is a third of everything left** and is the single highest-yield
read in the build.~~ **DONE 2026-08-13.** The next-biggest read is **Savage Seas (17)**,
which unlike BOTC spans Charms, spells and artifacts. ⚠ **The Lunars is NOT on this list** — its 16 were the false gap above.

### Group C — 15 leftovers in books already extracted

**Seven are closed, not work** (the Xoanon left this pile on 2026-08-13):

| Entry | Why it stays unauthored |
|---|---|
| Day to Night, Foul the Waters, Immolation, Elemental Unction (GoD p.56) | PG p.68 — only two of the six are learnable; encoded in a test |
| Investiture of Infernal Glory (PG p.85) | akuma-only, human 2026-08-07: *"do not author it"* |
| Heart of Chaos (Fair Folk p.247) | Fair Folk are out of scope, decision 0010 |
| ~~The Insidious Ebon Xoanon (B&E p.104)~~ | **AUTHORED 2026-08-13** — the human ruled it a Legendary Artifact plot device, the same as the two BoTC `ARTIFACT N/A` entries; `book-of-three-circles.md` |
| Kireeki-class Assault Skyreme (Outcaste p.64) | the name appears nowhere in the book; p.64 is the Skywolf |

**Eight are real and each is small:**

* **Ruins of Rathess p.86** ×3 (Crystal of Protection, Ring of Disguise, Ring of Images)
  — under a `COLUMN SPLIT FAILED` marker. The reassembly is in
  `artifact-batch-2-notes.md` awaiting one read; the page can now also be rasterised and
  read directly, which settles it without trusting the reassembly.
* **Player's Guide p.242** ×1 (Five Directions Formation Protocol). *(The p.207 three —
  Aspect of the Gillman, Soaring Pinions, Fluttering Wings — are DBT Gifts and are
  authored; see the false-gap note at the top.)*
* **Games of Divinity p.49** ×1 (Transference of the Sanctum, a spell).
* **The Outcaste p.59** ×1 (Implosion Bow, Medium).
* **Autochthonians p.185** ×1 (Nutrient Recycling Engine).
* **`E:S` p.?** ×1 — one spell under the index's unresolved book code.

Each sat in a book that WAS extracted, so each is a per-entry miss, not a page block:
worth one pass with the extracted Markdown open before assuming anything is wrong.

## What this changes

The old line "**213 entries and every one is page-blocked**" is now wrong in both halves.
**Nothing is page-blocked.** 63 entries need a tool run, 39 need pages rasterised and
read (101 minus the 62 Book of Three Circles closed on 2026-08-13), 8 need a look at text
already on disk, and 7 are closed decisions — one fewer than before, because the human's
`ARTIFACT N/A` ruling on 2026-08-13 turned the Insidious Ebon Xoanon from unauthorable
into authored, along with the two BoTC entries that raised the question.

And **19 of the 213 were never missing at all.** Treat any gap number as an upper bound
until the matcher has been pointed at every shape a Charm takes in this build — `name`,
`variants[].label`, and the parameterised entries the original generator already warned
about.

---

## Group A — DONE 2026-08-14 (all 68 authored)

All ten books extracted with `tools/extract_born_digital.py`, which is all Group A was
ever supposed to need. Catalogues: artifacts **237 → 302**, spells **294 → 296**,
weapons **103 → 110**.

| Book | Authored | Notes |
|---|---|---|
| The Abyssals pp.254-261 | 16 | the OCR'd copy carries a text layer |
| Blood and Salt | 13 | 11 artifacts + 2 Terrestrial spells (p.125) |
| Aspect Book: Air | 13 | |
| Aspect Book: Earth | 6 | |
| Cult of the Illuminated | 5 | |
| Kingdom of Halta | 5 | incl. the Iron Puzzle Box — see below |
| Aspect Book: Wood | 4 | |
| Aspect Book: Water | 3 | |
| Aspect Book: Fire | 2 | |
| Manacle and Coin p.31 | 1 | |

### ⚠ Group A was 68, not 63 — the fuzzy matcher over-matched again

Re-checking each name by EXACT match rather than substring/fuzzy found five entries the
retriage had scored as present:

* **Abyssals 14 → 16.** *Implosion Bow, Light* fuzzy-matched the already-authored
  **Medium Implosion Bow**; the Light bow is a different weapon on a different page.
* **Cult 4 → 5.**
* **Blood and Salt 11 → 13.** *Masks that Command Animals* matched the unrelated
  artifact literally named **Mask**.

This is the retriage's own trap — *"a search shaped like what you expect proves nothing
about a thing shaped differently"* — firing on the retriage. **Any gap count produced by
a fuzzy matcher is a LOWER bound on the work and an UPPER bound on what is present.**
The far cheaper check is exact name equality plus a manual eye over the near-misses; a
0.86 cutoff over a 300-name catalogue produces false positives at a rate that matters
when each one silently deletes a real entry from the worklist.

### Two source-reading notes

* **Six of the seven GARBLED markers were running heads** — letter-spaced furniture
  (`E XALTED • A SPECT B OOK : W ATER`) that the `SPACED_OUT` regex catches and the
  running-head stripper does not. They block nothing. Read the marked line before
  treating a marker as a blocker.
* **The extractor's column-split detection has false NEGATIVES.** Aspect Book: Wood p.81
  was correctly flagged `COLUMN SPLIT FAILED`, but **Cult of the Illuminated p.70 was
  interleaved and NOT flagged** — the Tears of the Harvest and the Shining Daiklave of
  Darkness had their sentences spliced together mid-clause, and nothing said so. Both
  pages were resolved by rasterising with `pdftoppm -r 110` and reading them directly,
  the Book of Three Circles method. ⚠ **An unflagged page is not a clean page.** Where an
  entry's prose stops making sense mid-sentence, suspect the columns and rasterise.

### The Iron Puzzle Box (Halta p.93) — ruled, and authored

It prints **`(ARTIFACT N/A)`** — a fourth entry of the shape `book-of-three-circles.md`
said none remained of. Its text reads as a plot device of exactly the Mantle of Brigid
class (it opens onto any realm in or outside Creation, and can open onto Yozi and then
refuse to close). It was **held rather than authored on the pattern** — that ruling had
been given per-entry each time, and a plot device charged to no budget is not a decision
to make on the human's behalf. **Human, 2026-08-14: "Legendary Artifact, yes."** Authored
with `requires_merit`, verified against all six behaviours of the channel (off the
Artifact-dot surface, hidden without the Merit, offered with it, `artifact-missing-merit`
when the Merit is dropped, charged to nothing).

⚠ **It is the standing counter-example to "no `(ARTIFACT N/A)` entry remains
unauthored."** That was only ever a claim about the books read so far — a book nobody has
extracted yet can hold a fifth, and Group B still has three unsynced.

---

## Group C — resolved 2026-08-14 (3 authored, 2 false gaps, 3 pending one sign-off)

Of the eight listed as "real and each is small", **two were already authored** and one was
**misfiled**. The eight were really five.

| Entry | Outcome |
|---|---|
| Five Directions Formation Protocol (PG p.242) | **AUTHORED** — a Crimson Pentacle Blade **Charm**, not an artifact |
| Transference of the Sanctum (GoD p.49) | **AUTHORED** — Solar Circle spell, 45 motes |
| Gift of Knowledge (`E:S` p.123) | **AUTHORED** — `E:S` **is** The Sidereals (see below) |
| Implosion Bow, Medium (Outcaste p.59) | **FALSE GAP** — authored as `artifact.outcaste.medium-implosion-bow`, same page |
| Nutrient Recycling Engine (Autochthonians p.185) | **FALSE GAP** — the book prints **"Portable Nutriment Recycling Engine"**, authored, same page |
| Crystal of Protection / Ring of Disguise / Ring of Images (Rathess p.86) | **PENDING** — needs one sign-off, see below |

### `E:S` is The Sidereals — the code is resolved

Sidereals p.123 (PDF page = book page + 3) prints **all three** of that book's spells in
one paragraph: *Open the Spirit Door* (which it says originally appeared in Games of
Divinity), *Gift of Knowledge* and *Summoning the Heavenly Portal*. The gap list filed
Gift of Knowledge under `E:S` and the other two under "Sidereals", splitting one page
across two book codes. **`E:S` should be folded into Sidereals wherever it appears.**

⚠ This also means **Gift of Knowledge was never a Group C entry** — Group C is "leftovers
in books already extracted", and Sidereals has never been extracted. It is a pure scan
and belongs to Group B. It is authored here only because resolving the code required
reading the page anyway.

### Two more false gaps — that is SEVEN across Groups A and C

Group A produced five (`Implosion Bow, Light` → *Medium Implosion Bow*, `Masks that
Command Animals` → *Mask*, and three more). Group C produced two, and one of them is the
**same** Medium Implosion Bow that caused a Group A false positive from the other
direction. Both Group C misses are the same shape: **the fan index's name is not the
book's name**, and the build correctly stores the printed one. `Nutrient` vs the printed
`Portable Nutriment`, `Implosion Bow, Medium` vs the printed `Medium Implosion Bow`.

**The check that works is: match on NAME, then when that fails, match on BOOK + PAGE.**
Every false gap so far would have been caught instantly by the page number — both of
Group C's cite the exact page of the entry already in the catalogue. No fuzzy name
matcher was ever going to close that gap, and one keyed on page would have closed all
seven without a single false positive.

### Ruins of Rathess p.86 ×3 — RESOLVED by reading the page, not the reassembly

**The book landed in `sources/` on 2026-08-14**, which made the sign-off moot: p.86 was
rasterised with `pdftoppm -r 110` (PDF page = book page + 1) and read directly. All three
are authored — **Ring of Images ••, Crystal of Protection •••, Ring of Disguise •••**.

⚠ **Both independent reassemblies turned out to be exactly right** — every rating, every
mechanic, every clause. That is worth recording in BOTH directions:

* the reassembly method is sound where the interleave is strictly line-alternating and
  each column reads as continuous coherent prose, which is a checkable condition and not
  a matter of judgement;
* **and it still should not have been authored on that basis.** Two batches were right to
  skip it. The correct resolution took one `pdftoppm` call the moment the book existed,
  and "my reconstruction is probably right" would have bought three entries at the price
  of a precedent for guessing. **When a marked page is blocked, the answer is to acquire
  the page, not to argue about the reassembly.**

### Sidereals — 3 of 5 done (2026-08-14)

Reading pp.122-123 for the `E:S` identification gave all three of that book's spells for
the price of one page, so all three are authored: **Gift of Knowledge** (Celestial 25m),
**Open the Spirit Door** (Terrestrial, 15m + 5m per additional target) and **Summoning
the Heavenly Portal** (Celestial 35m). Sidereals' remaining **2 artifacts (pp.24, 39)**
are still open and need those two pages read.


---

## Group B — DONE 2026-08-14, browser-verified same day. The content gap is CLOSED.

All four remaining books landed in `sources/` and all 39 entries were read and authored.
**Every one of the four is a PURE SCAN** — 0 of the first 40 pages carries text in any of
them — so `extract_born_digital.py` was inapplicable throughout and each page was
rasterised with `pdftoppm -r 110` and read directly, the Book of Three Circles method.

| Book | Entries | Offset | Notes |
|---|---|---|---|
| Savage Seas | 18 | PDF = book + 1 | 10 Charms, 4 spells, 4 artifacts |
| Time of Tumult | 14 | PDF = book + 1 | 3 Craft Charms, 11 artifacts |
| Storyteller's Companion | 6 | PDF = book + 1 | incl. the **Eye of Autochthon** |
| The Sidereals | 6 | PDF = book + 3 | 3 spells + 3 artifacts |

Final catalogue state: **artifacts 330, spells 304, Charms 1,910, weapons 112, armour 28.**

### The counts were low again — every book had more than the triage said

Savage Seas 17→**18**, Time of Tumult 13→**14**, Storyteller's Companion 4→**6**,
Sidereals 5→**6**. Same cause as Groups A and C: fuzzy name matching scored real gaps as
present. Across all three groups the triage undercounted by **11 entries**. The rule
stands and is now proven three times: **a fuzzy gap count is a LOWER bound on the work**,
and the cheap corrective is to match on **book + page** when the name match fails.

### The fifth `(ARTIFACT N/A)`: the Eye of Autochthon

Storyteller's Companion p.80. The `book-of-three-circles.md` note predicted a fifth would
turn up in an unread book, and it did — one book later. It is **the** exemplar of the
channel: the Legendary Artifact Merit's own text names *"the Mantle of Brigid or the Eye
of Autochthon"*, and the artifact's System paragraph says its active powers "may be
summarized as 'plot device.'" Authored with `requires_merit` on the human's standing
ruling. `PLOT_DEVICES` is now five.

### Four printed-name corrections, and the book won each time

* *Orichalcum Lined Cloak* (index) → **The Fur Merchant's Cloak** (ToT p.15)
* *Wavecleaver Daiklave* → **Wavecleaver Daiklaive** (Savage Seas p.126)
* *Collar of Dutiful Submission* → **The Collar of Dutiful Submission** (Sidereals p.39)
* *Masks that Command Animals* → **The Masks That Command the Animals** (B&S p.123)

### Shared entries across books — authored ONCE

Savage Seas reprints **Water's Ally**, **Steelsilk Sails**, **Storm Sapphire**, **Cord of
Winds** and the **Light Implosion Bow**, all of which Blood and Salt also prints with the
same text. One entry each, authored off whichever book was read first. A name-keyed dedup
caught them; a page-keyed one would not have, which is the counter-case to the matcher
lesson above — **use both.**

### ⚠ Two printed defects, recorded and NOT silently fixed

1. **Time of Tumult p.96 prints "Minimum Offult: 3"** for World Within a Picture Style's
   second Ability minimum. Checked at **300 dpi**: the ligature is unmistakably "ff", so
   it is the book's typo and not a rasterisation artifact. **RULED 2026-08-14 (human):
   "Should be Occult"** — encoded as `extra_min_abilities: [{occult, 3}]`, and the
   printed spelling is recorded in the Charm's own description so the book's text is not
   lost. Barring verified both ways: Occult 2 raises `charm-min-ability`, Occult 3 is
   clean.
2. **Savage Seas p.115 cites "Wind-Defying Course Method"** as Mast's Unbreakable Will
   Prana's prerequisite, while the two Charms printed beside it cite "Wind-Defying Course
   **Technique**". There is exactly one such Charm and it is in the **COREBOOK, Exalted
   p.209-210** (the Solar Sail tree, after Salty Dog Method) — NOT in Savant and
   Sorcerer, which is where it was looked for first. Wired to the Charm that exists, with
   the discrepancy noted in the data; the links resolve.

### One matcher lesson that is NOT about names

Savage Seas cites **"Keen Sight Technique"** and **"Unsurpassed Sight Discipline"** as
prerequisites. Neither name exists in the build — because both are authored
**parameterised**, as `Keen (Sense) Technique` and `Unsurpassed (Sense) Discipline`, with
Sight as one instance. This is the `variants` trap from the top of this file wearing a
different hat: **a prerequisite that resolves to nothing may be a naming shape, not a
missing entry.** Check the parameterised forms before authoring a "missing" prerequisite.


## Browser click-through — 2026-08-14, clean

Four items, all passing, against a Solar Twilight at Essence 5 / Occult 3 / Craft 5
holding Legendary Artifact (`/tmp/sweep.character.json`):

1. **The inventory merge with real catalogue content** — five rows, not eight. The three
   dual-nature pairs merged, the armour one rendering `Soak 10L/12B, Mob-2, Ftg1`, and
   both editors present under each merged row's Edit.
2. **The `Offult`→Occult gate** — World Within a Picture Style reads "Craft 5, Occult 3"
   and is legal at exactly those ratings.
3. **The merit-gated five** — Eye of Autochthon and Iron Puzzle Box offered alongside the
   original three, printing "Artifact N/A · by Merit"; dropping the Merit raises the
   Issue and withdraws all five from the dropdown.
4. **The new catalogue** — spell circle counts, the six new Sail Charms with Mast's
   Unbreakable Will Prana resolving to *Wind-Defying Course Technique*, and artifact
   spot-checks.

**No defects found.** Preflight caught the one gap beforehand: the armour side of the
merge had no test, and the Armor of Aquatic Puissance had just made it a live shape.
