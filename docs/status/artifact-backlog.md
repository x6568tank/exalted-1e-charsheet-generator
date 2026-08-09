# 1E artifact backlog — from "When Autochthon Dreams" (2026-08-08)

A discovery index, not a source of values. Parsed from the fanmade guide
**"When Autochthon Dreams" v1.1** by Wordman
(`images/when-autochthon-dreams-1.1.pdf`, gitignored) — its **Canonical Artifacts**
chapter (pdf pp.7-12) indexes every 1E **and** 2E artifact with a sourcebook+page,
sorted first by rating, then by name. This record extracts the **1E slice** (decision
0001) into a per-book backlog, flagging which source pages already exist in `images/`
(authorable now) vs which the human must sync. **Values still come from the real pages
— the guide is book+page discovery only, and the never-author-from-memory rule applies.**

## The parse

- **Method: pdfplumber, not the VLM.** The PDF is born-digital text, so the VLM
  pipeline would re-OCR clean text and add hallucination risk for zero transcription
  gain; the real problem is two-column table reassembly, which is deterministic. A
  dedicated parser groups words into y-rows per header-anchored block, then splits each
  row's refs into `refs_1e` / `refs_2e` by x-position relative to the block's column
  boundary. Rendered region + char-dump verified against the printed rows.
- **`botc` = Book of Three Circles** — the guide's code legend omits it, but it is a 1E
  book (human-confirmed 2026-08-08). `eixn` / `rol1` / `tsdo` are typos of the 2E codes
  `exin` / `rgd1` / `tdso` and sit in the 2E column. Verified: **zero 2E-only codes leak
  into the 1E column**; `botc` is the only legend-external code there.
- **One guide quirk, cosmetic:** a handful of rows print a stray name fragment in the
  2E-ref column (e.g. `Cloak of Vermin bone.65 Collar of` on pdf p.8, where `Collar of`
  belongs to the row above). The fragment never lands in `refs_1e`, so the backlog is
  unaffected.

## The numbers

**749 total entries → 417 with a 1E ref (360 unique names).** 1E entries by rating:
{•:93, ••:103, •••:112, ••••:64, •••••:38, n/A:7}. Every 1E entry carries the guide's
book code + page (e.g. `bone.65`), which is the discovery key.

## The backlog, by source book

Book names and on-disk flags are **verified against `images/` (2026-08-08)** — the first
draft of this table mislabelled five codes and overstated what is on disk; both are
corrected below. The guide's own ERS legend (PDF p.6) is the source of the names.

| Book | 1E artifacts (unique) | Pages | Pages on disk? |
|---|---|---|---|
| Bone & Ebony | 74 | 58-79, 104, 113-114 | **NO** |
| Outcastes | 27 | 50-54, 58-59, 62-64, 92, 121-122 | **NO** |
| Fair Folk | 27 | 205-211, 279-283 | 279-283 YES (**already authored** — the ten MF artifacts in `data/artifacts.json`); 205-211 NO |
| core | 24 | 336-338, 340-341, 343-345 | **PARTIAL** — 341, 343, 344, 345 (Arms & Armor table crops) + the 342/327-331 stat tables |
| Ruins of Rathess | 18 | 80-84, 86-88, 91, 194 | **NO** |
| Autochthonians | 17 | 182-190 | **NO** |
| Abyssals | 16 | 254-261 | **NO** (only Traits 130-153 on disk) |
| Book of Three Circles | 14 | 24-27, 92-96 | **NO** |
| Player's Guide | 14 | 192-195, 211 | **NO** |
| Aspect Book: Air | 13 | 75-78, 81 | **NO** |
| Caste Book: Dawn | 11 | 78-81 | **YES** |
| Time of Tumult | 11 | 15, 23, 49, 94-95 | **NO** |
| Caste Book: Twilight | 12 | 79-81 | **NO** (only to 77 on disk) |
| Blood and Salt | 11 | 89, 119-124 | **NO** |
| Caste Book: Eclipse | 9 | 79-81 | **NO** (only to 77-78 on disk) |
| Caste Book: Night | 8 | 79-81 | **YES** |
| Aspect Book: Earth | 6 | 79-81 | **NO** |
| Aspect Book: Wood | 6 | 79-81 | **NO** |
| Storyteller's Companion | 6 | 77-80 | **NO** (only CH3 spirit pages on disk) |
| Caste Book: Zenith | 5 | 80-81 | **YES** |
| Savage Seas | 4 | 123-124, 126-127 | **NO** |
| Aspect Book: Fire | 4 | 79-81 | **NO** |
| Aspect Book: Water | 4 | 80-81 | **NO** |
| Cult of the Illuminated | 5 | 69-70 | **NO** (only the p.89+ chargen paste on disk) |
| Savant & Sorcerer | 5 | 40-43 | **NO** |
| Halta | 5 | 93-95 | **NO** |
| Sidereals | 3 | 24, 39 | **NO** (only 96-125, 128-201, Storytelling on disk) |
| Manacle and Coin | 1 | 31 | **NO** |

The corrected labels: the five `ab_*` codes are the Dragon-Blooded **Aspect Books**
(Air/Earth/Fire/Water/Wood), not "Abyssal" anything; `salt` is **Blood and Salt**, not
"Salt & Smoke"; `coin` is **Manacle and Coin**, not "Coin of the Realm". The earlier
"YES (Abyssals/Traits)", "YES (Sidereals)", "YES (Illuminated)" and the
Caste Books Twilight/Eclipse "YES" rows were all wrong — those pages are **not** on this
machine.

**Authorable NOW, no sync needed: 40 entries** — Caste Book Dawn (11), Caste Book Night
(8), Caste Book Zenith (5), and the core subset (16, via the Arms & Armor crops). Of
those 40, **28 already have rated-equipment rows in the build** (the Solar-castebook gear
work; e.g. Razor Claws, Flame Spear, Powerbow of Perfect Accuracy). **The 12 genuinely-new
remainder were AUTHORED 2026-08-08** (the `cat` checklist build flag was added to expose
exactly this gap): ten became standalone catalogue entries in `data/artifacts.json`
(`artifact.castebook-<dawn|night|zenith>.<slug>` — Shield Bracer, Map of Azure Victory,
Chariot of Aerial Conquest, Arrows of Distant Death, Spider Grippers, Belt of Shadow
Walking, Circlet of Spirits, Daiklave Hooked, Death Shield Ring, Ring of the
Deliberative), the **Hooked Daiklaves** and the **Direlance** got rated weapon rows, and
the **Direlance's catalogue entry + the Slayer Khatar are BLOCKED** (their description
pages aren't on disk — p.341's crop is Artifact Materials and p.344's is the Lightning
Torment Hatchet). See `docs/status/rated-artifacts.md` → *The 2026-08-08 castebook
batch*. Plus the ten Fair Folk 279-283 entries already shipped as the rated artifacts in
`data/artifacts.json`. Everything else needs the human to sync source pages. The earlier
~90 estimate was more than double the truth. **The per-entry authoring queue, with build
status on every row, is `docs/status/artifact-backlog-entries.md`.**

⚠ **Fair Folk 205-211:** these 21 artifacts sit in the Fair Folk splatbook, and the Fair
Folk splat itself is permanently out of scope (decision 0010). Individual *artifacts*
from that book are a separate question from the *splat* — decide before starting it.

## Where things stand

- `data/artifacts.json` (SHIPPED 2026-08-08): the ten Mountain Folk rated artifacts
  (pp.279-283) + the four stat-blocked gear rows + the six dual-nature devices. The
  same day it grew to **20 entries** with the ten Caste Book Dawn/Night/Zenith items
  (pp.78-81) — the first non-MF slice of the wider cross-splat catalogue.
- **The alchemical goods are the one fully-sourced authorable slice — and they were
  deliberately NOT modelled (human ruling 2026-08-08).** Godstrike Oil, Pyromantic
  Gel and Synthetic Leather (MF pp.275-277) were authored as a `GoodType` catalogue,
  shown in the browser, and removed the same day. **The principle, which applies to
  the whole backlog:** every catalogue in the build feeds a mechanical read site
  (materials → derive, artifacts → budget/dropdown, weapons/armour → the sheet); a
  goods catalogue would be the first data with no mechanism behind it, opening the
  "why not firedust, lanterns, rations?" flood. **The full page transcription for
  the three is preserved here**, as the record of that slice. Do not re-add them
  unless a real "possessions" surface exists to read them.
- This backlog is the discovery layer for the wider cross-splat catalogue (still
  open): each entry names its source book + page, so syncing a book's pages unblocks
  its whole share at once.
- **`artifact-backlog-entries.md` (2026-08-08) is the authoring queue**: every 1E
  entry, per book, with rating, book page, on-disk flag, and a `Build` column saying
  whether the build already holds a matching name — `rated` = a `weapons.json`/
  `armor.json` row carrying `artifact_rating`, `gear` = a mundane row, `cat` = a
  standalone entry in `data/artifacts.json` (the catalogue is a read site too since
  2026-08-08 — non-gear artifacts like Shield Bracer live only there), `—` = not in the
  build (so the author cross-checks instead of creating). Regenerated 2026-08-08 after
  the 12-entry batch: the ten Mountain Folk entries now also read `cat`. Verified
  against `images/` the same day — the corrected on-disk status is in the table above.

## The alchemical goods — full transcription (MF pp.275-277)

The three entries from the Technology chapter's ALCHEMICAL GOODS section, kept so the
source for this slice travels with the repo (the page paste is human-vetted). Values
come from the page text; nothing here is authored from memory. Not modelled in the
build (see "Where things stand") — this is a record, not data.

**Godstrike Oil (Resources ••• or Artifact •, p.275)** — a sticky, sapphire-colored
liquid (blended mushroom spores, crushed marble, oil, subterranean-orchid nectar) that
glows if a dematerialized spirit approaches within 10 yards. An object rubbed with
enough of it touches immaterial beings as if solid for one scene. One dose anoints one
two-handed melee weapon, two one-handed melee or thrown weapons, ten arrows, or a
character's natural weapons; anointing one dose or dipping five arrowheads is a simple
action. Ten doses cost Resources ••• in Mountain Folk lands, five doses Resources ••••
elsewhere, when it can be found at all. Loses all potency in a year unless stored in
diamond or adamant containers. Small diamond chimes filled with drops are used as
spirit alarms; chimes and jewelry of this nature are considered Artifact •, but may be
obtained for Resources •••. The Realm strictly outlaws possession by the unExalted.

**Pyromantic Gel (Resources • to •••••, p.276)** — distilled from powdered red jade,
sulfur, tar and rarer thaumaturgical compounds; a thick fluid of honey consistency that
burns with explosive incandescence, like firedust. Mountain Folk Warriors use it to
fuel their flamecasters and larger cannons. Costs the same Resources value to produce
in Mountain Folk lands as firedust, but adds +•• elsewhere due to the cost of jade, and
requires advanced alchemical foundries (only the Realm's largest cities or the
Scavenger Lands). Weakens with time, cumulatively halving its damage each year until
completely inert.

**Synthetic Leather (Resources • to ••••, p.277)** — a viscous liquid cooled into
glossy leather nearly indistinguishable from real leather, in almost any shade. All
normal clothing of it costs the same Resources value as corresponding leather but
provides +1L/1B soak. Long overcoats function as buff jackets (fatigue 1); heavier
jackets intended as armor are treated as exceptional buff jackets. Sunlight makes it
brittle and dissolves it in a number of days equal to its Resources cost; a
sunlight-resistant treatment costs one bonus point. Treatments against fire, acid or
extreme cold grant +3L soak or double its usual lethal soak against that damage,
whichever is higher.
