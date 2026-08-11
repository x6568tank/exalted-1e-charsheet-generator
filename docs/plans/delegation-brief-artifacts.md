# Delegation brief — the 149 rated artifacts (5 extracted books)

**For a cheap model (DeepSeek V4 Flash), 2026-08-11.** Hand this file over whole. The
worklist of every artifact to author is appended at the bottom.

This is the second batch of this kind. The first — 151 spells — came back accurate:
every name traced to its page, 132 costs verified verbatim on the first pass, and the
prohibition sweep found nothing missing. **Two things from that run are carried into
this brief**: one was a real defect (a formatting convention silently dropped), and one
was a contradiction in *my* instructions that you correctly refused to resolve on your
own. Both are addressed below.

---

## The task, exactly

Add **149 artifact records** to `exalted_builder/data/artifacts.json`, transcribed from
five already-extracted source files. The file currently holds 40; it should hold **189**
when you are done.

**This is a DATA job with exactly one permitted code edit** (see *The one test you may
touch*). Do not modify any other `.py` file, any model, the engine, or the UI. If you
believe further code changes are needed, **write them in the notes instead** — do not
make them.

## ⚠️ The one rule that outranks everything

**This is Exalted FIRST Edition. Transcribe what the source says. Never supply a value
from your own knowledge.**

If a rating or an effect looks wrong to you, it is not wrong — you are reading 1e. Copy
it. **If you cannot read a value with certainty, put `"???"` in the text and list the
artifact in your notes.** Never average, never infer from a neighbouring entry, never
"correct" anything.

**Ratings are the sharp end of this.** An artifact's rating is a *mechanical value* — it
is spent against a character's Artifact Background budget. A wrong dot count is a wrong
game rule that reads as verified. Treat every rating the way the spell batch treated a
mote cost.

## The sources — read ONLY these

| Book | File | Artifact pages |
|---|---|---|
| Book of Bone and Ebony | `images/_extracted/Book of Bone and Ebony.md` | 58-79, 104, 113-114 |
| The Outcaste | `images/_extracted/The Outcaste.md` | 50-54, 58-59, 62-64, 92, 121-122 |
| Ruins of Rathess | `images/_extracted/Ruins of Rathess.md` | 80-84, 86-88, 91, 194 |
| Autochthonians | `images/_extracted/Autochthonians.md` | 182-190 |
| Player's Guide | `images/_extracted/Player's Guide.md` | 192-195, 211 |

All are page-marked with `<!--PAGE n-->`. **Do not open anything in `sources/`.**

### Passages you must NOT author from

Skip the artifact and list it in your notes:

- `<!--GARBLED ...-->`
- `<!--COLUMN SPLIT FAILED ...-->`
- `<!--SHATTERED HEADING, name unreadable: ...-->`

The spell batch skipped two entries this way and was **right to**; both were authored
later once a human signed off. Skipping correctly is a success, not a failure.

## The record shape

`artifacts.json` is a **flat JSON array**. Append to it; do not restructure it.

```json
{
  "id": "artifact.mountain-folk.essence-scrying-visor",
  "name": "Essence-Scrying Visor",
  "rating": 1,
  "description": "Crystal goggles: 1 mote per scene ignores low-light penalties; 3 motes activates Essence sight, which negates all visual penalties, pierces smoke and darkness, and adds three dice to Awareness rolls to notice illuminated beings and objects. Useless inside Demesnes and Manses. Artifact •• versions provide constant Essence sight for 4 committed motes.",
  "source": "Mountain Folk p.279",
  "tags": ["senses", "tool"]
}
```

- **`id`** — `artifact.<book-slug>.<name-kebab-cased>`. The book slug per book is given
  in the worklist headings. Ids must be unique.
- **`rating`** — an **integer 1-5**, from the printed dots. Required.
- **`rating_notes`** — a string, only when the source prints a **range or a
  disagreement** (`"• or •••"`, `"• to •••••"`). Leave it out otherwise. If the printed
  dots and the worklist's rating disagree, **follow the page**, put the discrepancy in
  `rating_notes`, and list it in your notes.
- **`description`** — your own summary of the printed effect, 1-4 sentences, matching
  the length and register of the existing 40. Every number in it comes from the page.
- **`source`** — `"<Book> p.<n>"`, e.g. `"Bone & Ebony p.64"`. Use the exact book label
  given in each worklist heading.
- **`tags`** — zero or more from the **existing vocabulary only**:
  `armor`, `charm-store`, `combat`, `communication`, `healing`, `protection`, `senses`,
  `social`, `sorcery`, `spirit`, `summoning`, `thrown`, `tool`, `utility`, `vehicle`,
  `weapon`. **Do not invent a tag.** If nothing fits, use `[]` and say so in the notes.

## The six traps specific to this batch

1. **⚠ Ratings are mechanical.** Read the dots off the page, not off the worklist. The
   worklist comes from a fan index and is discovery only.
2. **The Outcaste's text is DECODED**, not natively readable — its PDF stored every
   glyph reflected. It is correct now, but its headings still carry spacing damage
   (`MAGMA K RAKEN`-style, and occasional glued words like `GUARDIANOF`). **Read
   artifact names carefully there**, and prefer the printed name over the worklist's.
3. **Small-caps names** appear in the extraction as `SHIELD BRACER`. Convert to Title
   Case. Do not copy the all-caps form.
4. **Some artifacts are also weapons or armour.** The build stores those in
   `weapons.json` / `armor.json` *as well*, and the catalogue entry still belongs here
   (a Skirmish Pike is in both). **You are only authoring the catalogue entry** — do not
   add weapon or armour rows, and do not edit those files. Note any artifact that
   clearly needs gear stats.
5. **Do not touch the existing 40.** If a worklist entry looks like it already exists,
   do not duplicate and do not edit — note it and move on.
6. **Two entries are known-blocked and are NOT on your worklist**: the Direlance
   catalogue entry and the Slayer Khatar. Do not author them.

## The one test you may touch

`tests/test_data.py` asserts `len(rs.artifact_catalog) == 40`. Your batch legitimately
changes that number, and **updating that single assertion is part of the job.**

```python
assert len(rs.artifact_catalog) == 189   # or whatever you actually authored
```

Add a comment above it in the house style saying what changed and pointing at your notes
file. **That assertion is the only line of Python you may edit.** If any *other* test
fails, that is a real defect — investigate it and report it rather than editing the test.

> This is the correction from the spell batch: that brief demanded a green suite *and*
> forbade all `.py` edits, which was impossible. You flagged it instead of guessing,
> which was the right call. This time the permission is explicit and bounded.

## What to hand back

1. The edited `exalted_builder/data/artifacts.json` and the one test line.
2. **A notes file** (`docs/status/artifact-batch-notes.md`) with, at minimum:
   - every artifact **skipped**, and why (garbled, not found, already present);
   - every `"???"` and what was unreadable;
   - every **rating disagreement** between the page and the worklist;
   - every artifact that **needs weapon/armour stats** you did not add;
   - every entry you gave **no tags**, and why;
   - anything you noticed and did not act on.

**Over-report.** The spell batch's notes were honest and useful, and its most valuable
line was a spell it found that was not on its worklist at all. That kind of observation
is worth more than the transcription.

## How to check your own work before handing back

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -c "
import json; d=json.load(open('exalted_builder/data/artifacts.json'))
ids=[a['id'] for a in d]
assert len(ids)==len(set(ids)), 'duplicate ids'
assert all(isinstance(a['rating'],int) and 1<=a['rating']<=5 for a in d), 'bad rating'
ok={'armor','charm-store','combat','communication','healing','protection','senses',
    'social','sorcery','spirit','summoning','thrown','tool','utility','vehicle','weapon'}
bad={t for a in d for t in a.get('tags',[]) if t not in ok}
assert not bad, f'unknown tags: {bad}'
print(len(d),'artifacts')"
```

Expect **exactly one** failing test at the end:
`test_merits_flaws.py::test_every_description_matches_the_source_text`, which is a known
machine-specific failure and **not yours**.

## What the review will check

- **Every rating traced back to the printed dots.** This is the main review.
- **Every name present in its source book**, allowing for spacing damage.
- **`source` page within range** of where the entry actually appears.
- **Tag vocabulary closed**; ids unique; ratings integers in 1-5.
- **A prohibition sweep** over the artifact pages — attunement requirements, who may
  use an artifact, and what it cannot do belong in the description.
- **No `.py` file touched except the one assertion.**

---

## The worklist

### Book of Bone and Ebony — 74 artifacts   (id prefix `artifact.bone-ebony`)

| # | Name | Rating | Page |
|---|---|---|---|
| 1 | Bonestrider | ••••• | 104 |
| 2 | The Insidious Ebon Xoanon | n/A | 104 |
| 3 | Manifestation Engine | •••• | 113 |
| 4 | Soulsteel Mesh Swathing | ••••• | 114 |
| 5 | Soulsteel Net | •••• | 114 |
| 6 | Blood Apples | • | 58 |
| 7 | Bloody Ice Comb | • | 58 |
| 8 | Collar of the Bestial Shade | • | 58 |
| 9 | Drum of the Living Heart | • | 59 |
| 10 | Forms of Harmony | • | 59 |
| 11 | Grapes of Torment | • | 59 |
| 12 | Ivory Butterfly | • | 59 |
| 13 | Jade Harmony Needles | • | 60 |
| 14 | Labyrinth Doorknocker | • | 60 |
| 15 | Mirror of Life | • | 60 |
| 16 | Pillow of Grass | • | 60 |
| 17 | Robe of Life | • | 61 |
| 18 | Scroll of Unending Stories | • | 61 |
| 19 | Stallion-Thrashing Whip | • | 61 |
| 20 | Steel Pen of Refinement | • | 61 |
| 21 | Stone of Ten Thousand Tears | • | 62 |
| 22 | Storm-Running Boots | • | 62 |
| 23 | Storm-Warding Parasol | • | 62 |
| 24 | Thirst-Quenching Pitcher | • | 62 |
| 25 | Bag of Harvested Plagues | •• | 63 |
| 26 | Bone Bridge | •• | 63 |
| 27 | The Tongue-Binder | • | 63 |
| 28 | Whip of the Dead | • | 63 |
| 29 | Bone Harpoon | •• | 64 |
| 30 | Bracelets of Passionate Artistry | •• | 64 |
| 31 | Candelabrum of Remembered Kin | •• | 64 |
| 32 | Chair of Guilty Sorrows | •• | 65 |
| 33 | Cloak of Vermin | •• | 65 |
| 34 | Essence Dice | •• | 65 |
| 35 | Fingerbone Bracelet | •• | 65 |
| 36 | Hairpin Blade | •• | 66 |
| 37 | Hilt of the Bloody Sword | •• | 66 |
| 38 | Inkbrush of the Heart’s Desire | •• | 66 |
| 39 | Onyx Soul Window | •• | 67 |
| 40 | Patch Hide Armor | •• | 67 |
| 41 | Ring of Flies | •• | 67 |
| 42 | The Loom of Cobwebs | •• | 67 |
| 43 | Sacrificial Gem | •• | 68 |
| 44 | Shadow Gloves | •• | 68 |
| 45 | Shadow Peacock Earring | •• | 68 |
| 46 | The Speaking Dagger | •• | 69 |
| 47 | Whispering Fan | •• | 69 |
| 48 | Worm-Ridden Veil | •• | 69 |
| 49 | Bath That Warms | ••• | 70 |
| 50 | Bell of the Endless Caravan | ••• | 70 |
| 51 | Boat of Bones | ••• | 70 |
| 52 | Bow of Screaming Doom | ••• | 70 |
| 53 | Chart of the Final Lands | ••• | 71 |
| 54 | Eyes of the Pyre Flame | ••• | 72 |
| 55 | The Codex of the Damned | ••• | 72 |
| 56 | The Crusher of Souls | ••• | 72 |
| 57 | Fire-Belly Centipede | ••• | 73 |
| 58 | Girdle of Skulls | ••• | 73 |
| 59 | Hammer of the Damned | ••• | 73 |
| 60 | Hand Snare Chains | ••• | 73 |
| 61 | Mirror That Looks Upon Its Twin | ••• | 74 |
| 62 | Night Mother Doll | ••• | 74 |
| 63 | Pale Bees of the Ghostly Hive | ••• | 74 |
| 64 | Phantom Mantle | ••• | 75 |
| 65 | Razor Teeth | ••• | 75 |
| 66 | Rosary That Feeds on Souls | ••• | 75 |
| 67 | Scourge of Thorns | ••• | 75 |
| 68 | Shadow-Casting Gem | ••• | 76 |
| 69 | Stomach-Weighting Powder | ••• | 77 |
| 70 | Taming Muzzle | ••• | 77 |
| 71 | Thieving Harness of Servitude | ••• | 77 |
| 72 | Urn That Voids Darkness | ••• | 78 |
| 73 | Keystone of the Stair Inescapable | •••• | 79 |
| 74 | The White Snakes That Hunger | ••• | 79 |

### The Outcaste — 27 artifacts   (id prefix `artifact.outcaste`)

| # | Name | Rating | Page |
|---|---|---|---|
| 1 | Perfected Flame | ••• | 121 |
| 2 | Six-and-Finger Staff | • | 121 |
| 3 | Veil of the Anointed | •• | 121 |
| 4 | Dominca’s Mantle | ••••• | 122 |
| 5 | Walking Stone | ••• | 122 |
| 6 | Ashigaru Battle Armor | •• | 50 |
| 7 | Reaper Daiklave | •• | 51 |
| 8 | Shock Pike | •• | 51 |
| 9 | Warstrider Implosion Bow | •• | 51 |
| 10 | Elemental Lens | ••• | 52 |
| 11 | Essence Cannon | •• | 52 |
| 12 | Fire Lance | ••• | 53 |
| 13 | Gunzosha Commando Armor | ••• | 53 |
| 14 | Armor of the Immaculate Dragons | •••• | 54 |
| 15 | Infinite Weapon | ••• | 54 |
| 16 | Haze Shield | •••• | 58 |
| 17 | Crimson Armor of the Unseen Assassin | ••••• | 59 |
| 18 | Implosion Bow, Medium | •••• | 59 |
| 19 | Warstrider Fire Lance | •••• | 59 |
| 20 | Warstrider Shock Ram | •••• | 59 |
| 21 | Chariot of the Infinite Heavens | •••• | 62 |
| 22 | Manta-class Transport | ••••• | 63 |
| 23 | Kireeki-class Assault Skyreme | n/A | 64 |
| 24 | Compass of the Immanent Strife | •• | 92 |
| 25 | Freshwater Pearls | • | 92 |
| 26 | Helm of Heart’s Desire | ••••• | 92 |
| 27 | Wave Stepping Boots | •• | 92 |

### Ruins of Rathess — 18 artifacts   (id prefix `artifact.rathess`)

| # | Name | Rating | Page |
|---|---|---|---|
| 1 | Shock Gauntlet | ••• | 194 |
| 2 | Thorn Thrower | ••• | 194 |
| 3 | Boot Grafts | • | 80 |
| 4 | Breather Plant | • | 80 |
| 5 | Green Eyes | • | 80 |
| 6 | Green Iron Dust | • | 81 |
| 7 | Knife Spores | • | 81 |
| 8 | Healing Orchid | •• | 82 |
| 9 | Vine Klave | • | 82 |
| 10 | Mimic Skin | •• | 83 |
| 11 | Sun crystal | • | 84 |
| 12 | Crystal of Protection | ••• | 86 |
| 13 | Ring of Disguise | ••• | 86 |
| 14 | Ring of Images | •• | 86 |
| 15 | Lizard Tail Regrowth Sphere | •••• | 87 |
| 16 | Warbird | •••• | 88 |
| 17 | Enchiridion of All Knowledge | •• | 91 |
| 18 | Glory to the Ghoul King | • | 91 |

### Autochthonians — 16 artifacts   (id prefix `artifact.autochthonians`)

| # | Name | Rating | Page |
|---|---|---|---|
| 1 | Arc Protector | • | 182 |
| 2 | Autolabe | • | 182 |
| 3 | Essence Capacitor | • | 183 |
| 4 | Essence Capacitor exab.215, | ••• | 183 |
| 5 | Flaw Scanner | • | 183 |
| 6 | Light Amplification Visor | • | 183 |
| 7 | Light Sphere | • | 184 |
| 8 | Omnimodal Wardrobe Unit | • | 184 |
| 9 | Courier Drone | •• | 185 |
| 10 | Nutrient Recycling Engine | • | 185 |
| 11 | Respirator Module | • | 185 |
| 12 | Soulgem | •• | 186 |
| 13 | Industrial Exoskeleton | ••• | 187 |
| 14 | Fibre-Weave Bodysuit | • | 189 |
| 15 | Gyroscopic Chakram | ••• | 189 |
| 16 | Beam-Klave | •••• | 190 |

### Player's Guide — 14 artifacts   (id prefix `artifact.players-guide`)

| # | Name | Rating | Page |
|---|---|---|---|
| 1 | Reading Crystal | • | 192 |
| 2 | Bracer of Crystal Bolts | •• | 193 |
| 3 | Fire Claw | •• | 193 |
| 4 | Swordstick | • | 193 |
| 5 | Crystal Warclub | ••• | 194 |
| 6 | Necklace of Solar Charisma | ••• | 194 |
| 7 | Essence Storing Crystal | •••• | 195 |
| 8 | Globe of Transport | •••• | 195 |
| 9 | Obsidian Sheathe | •••• | 195 |
| 10 | Crushfist | • | 211 |
| 11 | Daiklave, Short | •• | 211 |
| 12 | God Kicking Boot | • | 211 |
| 13 | Grand Goremaul | ••• | 211 |
| 14 | Infinite Chakram | •• | 211 |
