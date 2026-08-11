# Spell batch notes — B&E + S&S (2026-08-11)

**Delegated batch for `docs/plans/delegation-brief-spells.md`.** Data-only job:
add the missing spells to `exalted_builder/data/spells.json`; nothing else touched.

## Deliverables

- `exalted_builder/data/spells.json`: **92 → 244** spells (152 added). Ids unique;
  schema (`id`/`name`/`circle`/`cost`/`description`/`source`) matches the existing
  entries; all new `source.book` values are exactly `"Book of Bone and Ebony"` or
  `"Savant and Sorcerer"`.
- This notes file.

**Count vs the brief:** the brief expects **245** (92 + 153). Actual is **244** (92 + 152):
2 worklist spells were skipped as unreadable (below), and **Cleansing Solar Flames** — not
on the worklist but printed on B&E p.139 — was added on the human's ruling (see the
"Spells noticed but not authored" section).

## The 2 skipped spells

1. **Emperor's Chains** (Shadowlands, B&E p.124, worklist #31) — **SKIPPED.**
   Reason: `<!--SHATTERED HEADING, name unreadable: 'E MPEROR ' S C HAINS'-->` at B&E
   line 10102. Per the brief, a SHATTERED HEADING means the name is unreadable → treat
   like a non-existent page; the spell is NOT in the build.
   Legible fragments (NOT authored, for the reviewer's reference): cost **16 motes**;
   either ghosts within 50 yards have their movement halved and the Essence cost of
   movement-Arcanoi doubled, OR a single ghost within 20 yards is immobilized, movement-
   Arcanoi costing three times as much.

2. **Wrath of the Five Elements** (Solar, S&S p.142-143, worklist #42) — **SKIPPED.**
   Reason: the p.143 continuation sits inside `<!--GARBLED p.143: 10 line(s)...-->` at
   S&S line 12266. A spell half-read is a spell not read; NOT in the build.
   Legible p.142 half (NOT authored): **45 motes**; the caster's Intelligence + Occult
   roll sets the difficulty to resist; five elemental attacks follow the target.

## Every `"???"`

**None.** Every cost, number and restriction in all 151 records was legible in the
source.

## Worklist-vs-printed name disagreements (book spelling used; see brief trap #2)

| Worklist | Book prints | Resulting id |
|---|---|---|
| Sorcerer's Irrestible Puppetry | SORCERER'S IRRESISTIBLE PUPPETRY (fan-index typo "Irrestible") | `spell.terrestrial.sorcerers-irresistible-puppetry` |
| Summoning of the Heart of Darkness | SUMMONING THE HEART OF DARKNESS (no "of") | `spell.celestial.summoning-the-heart-of-darkness` |
| Sacred Tongue | THE SACRED TONGUE (prefixed "The") | `spell.terrestrial.the-sacred-tongue` |

## Count discrepancy inside the brief itself

The brief's prose says **"50 Terrestrial, 32 Celestial, 11 Solar"** but its own worklist
**table** has **51 Terrestrial, 32 Celestial, 10 Solar** (both sum to 93). I authored per
the TABLE (51/32/10, minus Wrath → 92 S&S records). The reviewer should confirm which the
count test should encode.

## Every cost put in `raw` (not a plain mote number) — 38 total

### Book of Bone and Ebony (15)

| Spell | `raw` |
|---|---|
| Crystal Ghost Shard | `15 motes (committed)` |
| Golden Shadows Cast in Frieze | `30+` |
| Links Born of Tumult | `22 motes, 1 lethal health level` |
| Rattled Bones of War | `22 motes (committed)` |
| Banish Ghost | `12+` |
| Blood Mirror Speech | `10 motes, 1 lethal health level` |
| Death Flies Two Sails | `14 motes (seven committed)` |
| Easing the Forsaken Memory | `12+` |
| Gathering a Ghost's Strings | `10 or 20 motes` |
| Birth of Sanity's Sorrow | `10 motes, 1 permanent Willpower` |
| Black Faith | `30 motes, 1 lethal health level` |
| Forsaken Life Engine | `50+` |
| Grandmother Void | `40 motes, 1 lethal health level` |
| Sins of the Father | `50 motes, 1 permanent Willpower` |
| The Clay of Warped Dreams | `60 motes (committed)` |

### Savant and Sorcerer (23)

| Spell | `raw` |
|---|---|
| Blood Lash | `10 motes and 1 health level` |
| Calling the Wind's Kiss | `10 motes + 2 motes per additional hour (maximum 20 additional motes)` |
| Emerald Circle Banishment | `10+` |
| Eye of Alliance | `5 motes per participant` |
| Food from the Aerial Table | `10+` |
| Hypnotic Piping | `21 motes, and 10 motes to activate` |
| Incantation of Spiritual Discretion | `20+` |
| Lightning Spider | `10+` |
| Manifestations of Vigorous Design | `5+ motes (committed)` |
| Private Plaza of Downcast Eyes | `20+` |
| River of Blood | `15 + motes` |
| Sleep of Stony Safety | `15+` |
| Sorcerer's Irresistible Puppetry | `25 motes + 20 motes to activate` |
| Spirit of Might | `10+` |
| The Spy Who Walks in Darkness | `15 motes (committed), 5 motes to possess` |
| The Tree's Many Branches | `5 motes per pair` |
| Virtuous Guardian of Flame | `25 motes (committed)` |
| The Faithful Ally | `20 motes to cast, 20 motes to activate` |
| Imbue Amalgam | `15+` |
| Rolling Earth Carpet | `20 motes (committed)` |
| Shadows of the Ancient Past | `25+` |
| Unity of Dreams | `20+` |
| Abjuration of the Maidens | `40 motes + 1 lethal health level` |

## ⚠ Test failures — NOT ACTED ON (the brief is data-only)

Two tests assert hardcoded pre-batch spell counts and now fail purely because the data
grew. The brief forbids `.py` edits ("If you believe a code change is needed, **stop and
write it down in the notes instead** — do not make it"), so these are left for the
reviewer/human:

1. **`tests/test_data.py::test_spells_load_with_expected_circle_counts`** — asserts
   `len(rs.spells) == 92` and a hardcoded per-circle dict. Now stale. New expected:
   `{Terrestrial: 67, Celestial: 41, Solar: 16, Shadowlands: 41, Labyrinth: 24,
   Void: 17, Man-Machine: 23, God-Machine: 15}` (sums 244).
2. **`tests/test_abyssal.py::test_abyssal_necromancy_spells_authored`** — asserts
   Shadowlands == 9, Labyrinth == 7, Void == 7. Now stale: 41 / 24 / 17.

`test_every_description_matches_the_source_text` still fails — the known machine-specific
failure (green on laptop), untouched, not a regression.

Result on this machine: **2,089 passed / 3 failed**. After the two count assertions above
are updated it returns to the known 1-failure state (2,091 passing / 1 machine-specific).

## Spells noticed but NOT authored (worklist is the defined scope)

- **Cleansing Solar Flames** (B&E p.139 sidebar) — **AUTHORED 2026-08-11** as
  `spell.solar.cleansing-solar-flames` (Solar; `raw` cost `50+ motes`) on the human's
  ruling. The **masterlist files it under E:Ab** (Exalted: the Abyssals); the human ruled
  it be **attributed to Book of Bone and Ebony** — the book whose p.139 is actually on
  disk. Not on the worklist; added because the human directed it after the batch.
- **Peacock Shadow Eyes** (S&S p.111) — **already exists** in the build (10 motes,
  Terrestrial, source Caste Book: Twilight). Not on this worklist; no duplicate added, the
  existing record is untouched.
- **Plague of Bronze Snakes** — the build already carries `spell.man-machine.plague-of-
  bronze-snakes` (an Alchemical protocol whose cost is `"As Plague of Bronze Snakes
  (Savant & Sorcerer)"`, source Exalted 1e The Autochthonians p.153). This batch **adds the
  Terrestrial original** (`spell.terrestrial.plague-of-bronze-snakes`, S&S p.112). NOT a
  duplicate — different circle, different id; the Man-Machine protocol's cross-reference
  now resolves to a real spell.
- **Passing mentions in B&E text** that are not their own entries (no pages authorable in
  this range / not on the worklist — listed so the reviewer knows they were seen, not
  missed): Willful Flesh Commands (Labyrinth, 24), Consorting with Devils (Shadowlands,
  10), Invisible Doorway (Shadowlands, 18 + 1 lethal HL), White Shard (Labyrinth, 28),
  The Barless Gate (Void, 42), Funerary Misted Vessel (Labyrinth, 22, 11 committed),
  Congealing the Last Thought (12), Folding Midnight (Void, 46), Brick-by-Brick Solitude
  (Labyrinth), Black Vial (Labyrinth, 24), Empty Night Future (Void, 32), Blackstorm Wagon
  (Void, 48), Walking Gore Titan (Labyrinth, 16, committed), Void Cocoon Warrior (Void,
  28 minimum, committed), Barred Tomb (Void), Puzzle Box of Love (Labyrinth), Baneful
  Shadow (Shadowlands), Raise the Skeletal Horde, Arisen Legion. **Exquisite Undead Aide
  already exists** in the build (referenced by Master Puppeteer's Knife).
- **The `≠` on S&S p.110** (brief trap #5) — confirmed present as a real not-equals glyph
  used as a dash: *"tied to or around objects ≠— or people"* (Lightning Spider dragline).
  No quantity is involved, so it has no authoring impact; noted as instructed.

## Other observations

- **B&E p.124 `<!--GARBLED p.124: 1 line(s)...-->`** is a running header ("EXALTED •
  BOOK OF BONE AND EBONY"), not spell content — no action.
- **The Battle's End** has a stray text-flow fragment earlier in the extraction; the real
  heading + cost sit at S&S line 10478. Authored from there (Celestial, 30 motes).
- Both **Puissant Sanctum** spells (pp.57-58, outside the 101-143 page range) were
  verified against the source: Raise = Celestial/30, Craft = Solar/50.
- Ids follow the existing convention: apostrophes/commas/ampersands/colons stripped,
  name kebab-cased, "The" retained when the book prints it (`spell.terrestrial.the-sacred-
  tongue`, `spell.celestial.the-battles-end`, `spell.celestial.the-faithful-ally`, …).
