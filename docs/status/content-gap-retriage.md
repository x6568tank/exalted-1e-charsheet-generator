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
