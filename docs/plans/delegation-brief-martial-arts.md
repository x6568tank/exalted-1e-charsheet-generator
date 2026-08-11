# Delegation brief — the 49 missing Martial Arts Charms (Player's Guide)

**For a cheap model (DeepSeek V4 Flash), 2026-08-11.** Hand this file over whole. The
worklist is appended at the bottom.

Fourth batch. The Ghost Arcanoi run was the best of the three so far, and the single
most valuable thing in it was **a real UI bug you found in the build and correctly
refused to fix** (multi-Virtue Arcanoi categories falling through `picker._group_of` to
the wrong page). That instinct — diagnose precisely, propose the fix, do not apply it —
is exactly right. Keep doing it.

---

## The task, exactly

Author **49 Martial Arts Charms** into `exalted_builder/data/charms/`, transcribed from
`images/_extracted/Player's Guide.md` — **45 across four new styles** (pp.241-258) plus
**4 initiation Charms** that join an existing tree (pp.236-237). The build holds 1,780
Charms today; it should hold **1,829** when done.

**This is a DATA-ONLY job.** Do not modify any `.py` file — not the models, engine, UI,
loader, or any test. Unlike the last batch there is no test to re-scope: no assertion
counts Martial Arts styles. If you believe code needs changing, **write it in the notes
instead.**

## ⚠️ The one rule that outranks everything

**This is Exalted FIRST Edition. Transcribe what the source says. Never supply a value
from your own knowledge.** Martial Arts is the single most 2e-contaminated corner of
this game — you have seen far more 2e MA than 1e, and the styles below exist in both.
**If a cost, minimum or prerequisite looks wrong to you, it is not wrong.** Write
`"???"` and note it rather than reaching for a remembered value.

## The source — read ONLY this

`images/_extracted/Player's Guide.md`, pages **236-237 and 241-258**, page-marked with
`<!--PAGE n-->`. Do not open anything in `sources/`. Skip anything under a
`<!--GARBLED …-->`, `<!--COLUMN SPLIT FAILED …-->` or `<!--SHATTERED HEADING …-->`
marker and note it.

⚠ **pp.210-213 and 216 carry markers** — those are outside your range, but the
Player's Guide is the most marker-heavy extraction in the set. Check before authoring
from any page.

## The record shape

One file per style, a flat array, same shape as the existing MA files (see
`exalted_builder/data/charms/solar_martial_arts_tiger.json`):

```json
{
  "id": "solar.martial-arts.crimson-pentacle-blade.<name-kebab>",
  "name": "Crimson Pentacle Blade Form",
  "category": "martial_arts:crimson-pentacle-blade",
  "ability": "martial_arts",
  "type": "Simple",
  "min_ability": 4,
  "min_essence": 3,
  "prerequisites": [["solar.martial-arts.crimson-pentacle-blade.<prereq>"]],
  "cost": { "raw": "5 motes", "motes": 5 },
  "duration": "One scene",
  "description": "…",
  "source": { "book": "Player's Guide", "page": 243 }
}
```

**Match the existing files exactly** — read one before you start, and copy its field
set and id convention rather than the sketch above if they differ.

- **`category`** — `martial_arts:<style-slug>`, slug given per style in the worklist.
  The engine parses this namespace generically (`category.split(":", 1)[0]`), so a new
  style needs **no registration anywhere** — the category string is the whole wiring.
- **`min_ability`** — the printed Minimum Martial Arts.
- **`prerequisites`** — list of groups; group members are OR, groups are AND. `[]` for
  a style's root Form. Every id must resolve.
- **`cost`** — `{"raw": "<printed>", "motes": N}`; keep `raw` verbatim always.

## ⚠ The access fields — the part that decides who can learn these Charms

Each style is either **Terrestrial** or **Celestial** tier, and that is a mechanical
gate, not flavour. The worklist states the tier for each style. Set it as:

| Tier | Field |
|---|---|
| **Terrestrial** | `"open_to_all": true` |
| **Celestial** | `"open_to_tiers": ["Celestial"]` |

That is the build's existing convention — `martial_arts:hungry-ghost` and the five
Immaculate Dragon paths use `open_to_tiers: ["Celestial"]`; `five-dragon` and
`falling-blossom` use `open_to_all`. **Do not invent a third pattern**, and do not set
both. `exalt_type` should be omitted (the tier fields carry the access).

**If the printed text contradicts the tier the worklist gives, follow the page and note
it loudly** — that is a real rules disagreement, not a typo.

## Four traps specific to this batch

1. **⚠ 2e contamination.** Righteous Devil, Dreaming Pearl Courtesan and Celestial
   Monkey all exist in 2e with different numbers. Transcribe the 1e page.
2. **Style Forms are the roots.** Each style has a "… Form" Charm that most others
   depend on. Get that chain right; a wrongly-rooted style is browser-visible.
3. **Names are small-caps** and the extraction sometimes glues them
   (`CRIMSON PENTACLE BLADE FORM`, and glue artifacts like `GUARDIANOF`). Convert to
   Title Case and **prefer the printed name over the worklist's** — the worklist is a
   fan index with typos (it has `Call-to-the-Blade-ofReighteouseness Mantra`).
4. **Do not touch the existing MA files.** These are four genuinely new styles.

## The four initiation Charms — pp.236-237, and they DO belong in the build

The index lists these under a *Celestial Initiation* tree:
**Walker-Among-Irises Perception**, **Iris-Bulb Discourse** (p.236),
**Tiger-and-Bear Awareness**, **Tiger-and-Bear Unity** (p.237).

They are **not a style**. They are two alternate **Charm pairs** that initiate a
Terrestrial Exalt into the Celestial martial arts — the Player's Guide says so directly:
*"The Immaculate Charms Spirit Sight and Spirit Walking are just one set of such Charms.
There are others."*

**The build already models this**, and they go in the existing tree:

- `"category": "martial_arts:enlightenment"` — the same category as the build's
  Immaculate pair (`dragonblooded.martial-arts.spirit-sight` / `…spirit-walking`).
- That category is already exempt from the Dragon-Path gate (`_UNGATED_MA_STYLES` in
  `engine/validate.py`), so nothing about the existing gate breaks.
- They are full Charms with printed `Minimum Martial Arts` and `Minimum Essence` —
  author them exactly like any other Charm in this batch.
- Access: follow the existing pair's fields in the data (it uses `open_to_all`).

⚠ **One thing you must NOT do, and must NOT work around.** `engine/validate.py` gates
the Dragon Paths on a hardcoded pair:

```python
DB_MA_ENLIGHTENMENT_IDS = ("dragonblooded.martial-arts.spirit-sight",
                           "dragonblooded.martial-arts.spirit-walking")
```

and `db_enlightenment_met` requires **all** of them. So until that becomes "any one
complete pair", your four Charms will load and be buyable but will **not** open the
Dragon Paths — the initiation they describe will not happen.

**That code change is the reviewer's job, not yours.** Author the data, and **list all
four in your notes under a heading saying the gate still needs extending**, so the
dependency is tracked rather than assumed. Do not edit `validate.py`, and do not give
them ids that pretend to be the existing pair.

## What to hand back

1. Four new style files under `exalted_builder/data/charms/`, plus the four
   initiation Charms added to the existing enlightenment tree.
2. **A notes file** (`docs/status/martial-arts-batch-notes.md`) with, at minimum:
   - every Charm **skipped**, and why;
   - every `"???"`;
   - every **prerequisite you could not resolve**;
   - every **worklist-vs-printed name disagreement**;
   - **any place the page's stated tier disagreed with the worklist**;
   - the per-style count you ended with;
   - anything you noticed and did not act on.

## How to check your own work

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -c "
import json,glob,collections
rows=[r for f in glob.glob('exalted_builder/data/charms/*martial_arts*.json') for r in json.load(open(f))]
ids={r['id'] for r in rows}
assert len(ids)==len(rows), 'duplicate ids'
for r in rows:
    for g in r.get('prerequisites',[]):
        for p in g:
            assert p in ids, (r['id'], p)
    assert not (r.get('open_to_all') and r.get('open_to_tiers')), r['id']
print(collections.Counter(r['category'] for r in rows))"
```

Expect **exactly one** failing test:
`test_merits_flaws.py::test_every_description_matches_the_source_text` — a known
machine-specific failure, not yours. **Any other failure is a real defect** — report it,
do not edit the test.

## What the review will check

- **Every cost, minimum and prerequisite traced to the page.**
- **Tier fields correct**, and never both set.
- **Prerequisite chains resolve** and each style has exactly one root Form.
- **Names as printed.**
- **No `.py` file touched at all.**

---

## The worklist

### Crimson Pentacle Blade — 14 Charms   (TERRESTRIAL tier)

- file: `exalted_builder/data/charms/solar_martial_arts_crimson_pentacle_blade.json` — **new**
- `"category": "martial_arts:crimson-pentacle-blade"`
- access: `"open_to_all": true`
- pages: 241-246

| # | Name | Page | Combo-OK |
|---|---|---|---|
| 1 | Graceful Toroise Technique | 241 |  |
| 2 | Crimson Pentacle Blade Form | 242 |  |
| 3 | Eastern Root Protocol | 242 |  |
| 4 | Five Directions Formation Protocol | 242 |  |
| 5 | Speardancer Concentration | 242 | ✔ |
| 6 | Northern Lotus Petal Discernment Meditation | 243 | ✔ |
| 7 | Blessing of Jeweled Vambraces and Mantle | 244 |  |
| 8 | Glorious Southern Harbinger of War and Fury | 244 |  |
| 9 | Sprinting Stag Defense | 244 | ✔ |
| 10 | Western Shield Crush Counterattack | 244 | ✔ |
| 11 | Furious Battle Scythe | 245 |  |
| 12 | Retribution of Honorable Guardianship Attitude | 245 |  |
| 13 | Call-to-the-Blade-ofReighteouseness Mantra | 246 |  |
| 14 | Central Pillar Attack Pattern Mastery | 246 | ✔ |

### Righteous Devil — 12 Charms   (CELESTIAL tier)

- file: `exalted_builder/data/charms/solar_martial_arts_righteous_devil.json` — **new**
- `"category": "martial_arts:righteous-devil"`
- access: `"open_to_tiers": ["Celestial"]`
- pages: 254-258

| # | Name | Page | Combo-OK |
|---|---|---|---|
| 1 | Kiss of the Sun Concentration | 254 | ✔ |
| 2 | Blessing of Righteous Solar Spark Meditation | 255 |  |
| 3 | Blossom of Inevitable Demise Technique | 255 | ✔ |
| 4 | Cloud of Ebon Devils | 255 | ✔ |
| 5 | Lightning Draw Stance | 255 | ✔ |
| 6 | Azure Abacus Meditation | 256 | ✔ |
| 7 | Dance of the Howling Magma Sprites | 256 | ✔ |
| 8 | Phoenix Flies on Golden Wings Attack | 256 | ✔ |
| 9 | Righteous Devil Form | 256 |  |
| 10 | Twin Salamander Fist | 256 |  |
| 11 | Phantom Flamebolt Prana | 257 | ✔ |
| 12 | Caress of 1,000 Hells | 258 |  |

### Dreaming Pearl Courtesan — 10 Charms   (CELESTIAL tier)

- file: `exalted_builder/data/charms/solar_martial_arts_dreaming_pearl_courtesan.json` — **new**
- `"category": "martial_arts:dreaming-pearl-courtesan"`
- access: `"open_to_tiers": ["Celestial"]`
- pages: 250-253

| # | Name | Page | Combo-OK |
|---|---|---|---|
| 1 | Demure Carp Feint | 250 | ✔ |
| 2 | Dreaming Pearl Courtesan Form | 250 |  |
| 3 | Lethal Paper Fan Attack | 250 | ✔ |
| 4 | Pearlescent Filigree Defence | 250 |  |
| 5 | Flurry of August Leaves Concentration | 251 | ✔ |
| 6 | Resplendent Sash Grapple Technique | 251 |  |
| 7 | Vindictive Concubine’s Pillow Book Understanding | 251 | ✔ |
| 8 | Fragrant Petal Fascination Kata | 252 |  |
| 9 | Invoking the Chimera’s Coils | 253 |  |
| 10 | Seven Storms Escape Prana | 253 | ✔ |

### Celestial Monkey — 9 Charms   (CELESTIAL tier)

- file: `exalted_builder/data/charms/solar_martial_arts_celestial_monkey.json` — **new**
- `"category": "martial_arts:celestial-monkey"`
- access: `"open_to_tiers": ["Celestial"]`
- pages: 246-249

| # | Name | Page | Combo-OK |
|---|---|---|---|
| 1 | Monkey Tail Distraction Strike | 246 | ✔ |
| 2 | Body of War Meditation | 247 |  |
| 3 | Flowing Mirror of Opposition Technique | 247 | ✔ |
| 4 | Withering Paw Strike | 247 | ✔ |
| 5 | Celestial Monkey Form | 248 |  |
| 6 | Four Halo Golden Monkey Palm | 248 | ✔ |
| 7 | Walking in the Footsteps of Ten Thousand Things | 248 | ✔ |
| 8 | Celestial Godbody Understanding | 249 |  |
| 9 | Four Halo Golden Monkey Realignment | 249 |  |

### Celestial Initiation — 4 Charms   (two alternate initiation PAIRS)

- file: the **existing** `exalted_builder/data/charms/dragonblooded_martial_arts.json`
  (or a new `players_guide_martial_arts_enlightenment.json` — match whichever the
  existing Spirit Sight / Spirit Walking records live in)
- `"category": "martial_arts:enlightenment"` — an EXISTING category, not a new one
- ⚠ the Dragon-Path gate still hardcodes the Immaculate pair; see the section above

| # | Name | Page | Pair |
|---|---|---|---|
| 1 | Iris-Bulb Discourse | 236 | Iris-Bulb pair |
| 2 | Walker-Among-Irises Perception | 236 | Iris-Bulb pair |
| 3 | Tiger-and-Bear Awareness | 237 | Tiger-and-Bear pair |
| 4 | Tiger-and-Bear Unity | 237 | Tiger-and-Bear pair |
