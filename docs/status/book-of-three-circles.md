# Book of Three Circles — DONE 2026-08-13, browser-verified 2026-08-14

The largest single item in the post-sweep gap: **62 entries, a third of everything left**
(`content-gap-retriage.md`). **All 62 authored** — the last two after the human ruled on
what "(ARTIFACT N/A)" costs.

| Catalogue | Before | After |
|---|---|---|
| Spells | 246 | **294** (+48: 31 Terrestrial, 3 Celestial, 14 Solar) |
| Artifacts | 222 | **237** (+15 — 14 from this book, plus the B&E Xoanon the same ruling unblocked) |
| Weapons | 102 | **103** (+1 — the Crimson Bow's stat row) |

Suite: **2,355 passing / 2,356 total** — the one failure is the documented machine-only
`test_every_description_matches_the_source_text`, green on the laptop. Three catalogue-count
assertions were updated with the reasoning inline, and nine tests were added for the
merit-gated channel below.

## How it was read — no VLM leg

`sources/WW8802 - The Book Of Three Circles [scanned By Otha].pdf` is a **pure scan** —
0 characters of text in the whole book, so `extract_born_digital.py` and
`solve_cid_bands.py` are both inapplicable. It was rasterised with **`pdftoppm -r 110`**
and the pages read directly.

⚠ **The Ollama VLM leg is for non-visual models** (human, 2026-08-13). A vision-capable
model reads the rasterised page itself; `vlm_read_ratings.py` and the
`vlm-cannot-count-dots` caution are about the small local VLM's output, not about page
reading as such. 110 dpi was ample — body text, cost lines and dot strings all legible.

**PDF page = book page + 1.**

## The human's ruling that shaped it

> **"Some spells in it will conflict with Savant and Sorcerer. In the event of a conflict,
> S&S wins."** — human, 2026-08-13

This is the general [[source-precedence-rule]] applied in the other direction, and it was
free to honour: the gap list is by construction the names the build does **not** already
hold, and the build's copies of the shared spells came from S&S. So **only names absent
from the catalogue were authored, and no existing S&S entry was touched.** A post-hoc
fuzzy sweep of all 48 new names against the 246 existing ones found exactly one near
match — *Voice of Distant Command* (BOTC p.66) against *Voices of Distant Regard* (S&S
p.137) — and the book prints **both, on the same page**, as separate spells. No conflict.

## Three things the pages settled

1. **The ch.4 circle is SOLAR, not "Adamant."** The fan spell index groups those 15 under
   "Adamant"; the book's own chapter head reads **CHAPTER FOUR • THE SOLAR CIRCLE**. The
   book wins, and the build's existing `Solar` circle absorbs them. (Adamant appears in
   the book only as *Adamant Countermagic*, which several of these spells name.)
2. **ch.5 "New Wonders" rates its artifacts by SECTION HEADING**, not per-entry dot
   strings: `LEVEL 1` p.91, `LEVEL 2` p.92, `LEVEL 3` p.94, `LEVEL 4` p.95, `LEVEL 5`
   p.96. An entry's rating is whichever LEVEL block it sits in. All nine agreed with the
   fan index's ratings, which is the corroboration that mattered — I did not count dots.
   ch.1's five artifacts (pp.24-27) use the ordinary per-entry `(ARTIFACT ••••)` form.
3. **Four printed names differ from the index**, and the book wins each time:
   *Commanding **Presence** of Fire* (not "the Presence"), ***Impervious** Sphere of
   Water* (not "Imperious"), *Summoning **of** the Harvest*, and *Trave**l**er's Staff*
   (one l).

## The two "(ARTIFACT N/A)" entries — a THIRD acquisition channel

**Human's ruling, 2026-08-13:** *"Mantle of Brigid is N/A because it is a plot device.
Make it require the LEGENDARY ARTIFACT 10pt merit. Author Sword of Ice the same way."*

The book all but says it already: **Legendary Artifact** (PG p.24, a 10-pt Merit already
in the build as `mf.legendary-artifact`) is described as *"an artifact of world-shaking
power, a relic on par with **the Mantle of Brigid** or the Eye of Autochthon"*, and warns
that Storytellers *"do not need to allow this Merit ever, as legendary artifacts are
innately and grossly unfair plot devices"*. The Sword of Ice's own text names the Eye of
Autocthon as its yardstick.

This **amends decision 0017**, which said artifacts have two acquisition channels
(Background pre-game, cash in-play). There are three: a plot device is paid for with a
**Merit**, and charged to no budget at all — not because you bought it, but because there
is no rating to charge.

| Piece | Where |
|---|---|
| Which Merit gates an entry | `ArtifactType.requires_merit` — **data**, so no module names a Merit id (decision 0011) |
| The channel on an owned item | `artifacts.ACQUIRED_LEGENDARY`, stamped from the catalogue at pick time |
| Kept off Artifact-dot surfaces | `artifacts.purchasable_with_artifact` excludes them, exactly as it does Hearthstones |
| The OFFER | `artifacts.purchasable_artifacts` adds them back once the Merit is held |
| The BAR | `validate.check_artifacts` → `artifact-missing-merit`, **both sides of the lock** |
| Charged to nothing | `artifacts.budgeted_items` skips them alongside purchased items |

Two deliberate choices worth keeping:

* **The bar keys on the artifact's NAME against the catalogue, not on
  `ArtifactEntry.acquired`** — that field is player-editable by design, and a
  discriminator anything on the screen can write is not a discriminator (the
  catalogue-dialog lesson). Flipping the Acquired select cannot shake the Merit off; a
  test asserts it for all three channels.
* **`rating` is 5 and that is a placeholder**, not a printed value: the model bounds it
  1-5 and the page prints N/A. `rating_notes` says so, nothing charges it, and the
  inventory line prints **"Artifact N/A · by Merit"** rather than five dots — the one
  place that could have stated the fiction as a fact.

⚠ `_art_catalog` in `ui/gear.py` is a **function, not a captured list**: the offer now
depends on state edited on the *Advantages* tab, and a value computed once at page build
is the stale-closure trap verbatim — take the Merit, come back, and the artifact you paid
ten bonus points for is missing from the dropdown.

**The Insidious Ebon Xoanon (B&E p.104) was the same shape and is now authored the same
way** — human, 2026-08-13: *"it is."* The First and Forsaken Lion's necromantic warstrider
had been unauthorable since the 2026-08-11 sweep for precisely this reason.

⚠ **This file once said that closed "every `ARTIFACT N/A` entry in the build". It did
not, and could not.** That is a claim about the books READ SO FAR, never about the game:
the **Iron Puzzle Box** (Kingdom of Halta p.93) turned up on 2026-08-14 the moment Group A
was extracted, and was ruled the same way. Three Group B books are still unsynced and any
of them can hold a fifth. See `content-gap-retriage.md`.

## The Crimson Bow is in two places on purpose

It is the one BOTC artifact printed with a full weapon stat line (Accuracy +4, Damage +6,
Rate 3, Range 500, Artifact ••••, Minimums Strength •••), so it follows the established
dual pattern — 14 names already live in both — with a catalogue entry in `artifacts.json`
and a stat row in `weapons.json` carrying `artifact_rating: 4` and `attunement: 10`.

## The click-through — 2026-08-14, clean

Four items, all passing: the spell picker's Circle dropdown (Terrestrial **98** /
Celestial **44** / Solar **31**, and the four names where the book overruled the fan index
read as printed); the artifact and weapon name comboboxes; **the merit gate in both
directions** (holding Legendary Artifact offers the Mantle, the Sword of Ice and the
Xoanon; dropping it raises `artifact-missing-merit` AND withdraws them from the dropdown —
the `_art_catalog` stale-closure trap did not fire, and flipping `acquired` could not
shake the gate off); and their absence from the Artifact-dot surfaces.

**One finding, and it was presentational rather than a defect:** the Crimson Bow showed as
an artifact row and a weapon row, which the human read as *"odd, and a little obtuse."*
That was `grant_gear` working correctly — the two stored halves of one object — but the
inventory rendered them as unrelated peers. Fixed the same day by merging the pair into
one row; the record is in `gear-and-inventory.md`, because it is the inventory's behaviour
and not this book's.

## Still open here

* Nothing in the book that the index lists is now unauthored, and no `ARTIFACT N/A`
  entry remains unauthored anywhere in the build.
