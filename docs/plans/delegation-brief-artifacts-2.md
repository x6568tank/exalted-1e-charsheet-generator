# Delegation brief — the last 23 artifacts on disk

**For a cheap model (DeepSeek V4 Flash), 2026-08-11.** Hand this file over whole. The
worklist is appended at the bottom.

Fifth batch, and a **closing-out** one: these 23 are everything still missing from the
artifact catalogue that can be authored from text already on disk. After this, every
remaining artifact needs a page sync.

Two of them were previously recorded as **permanently blocked** — the Slayer Khatar
above all. The corebook's text layer has since been decoded, so its pages are readable
for the first time.

---

## The task, exactly

Add **23 artifact records** to `exalted_builder/data/artifacts.json`, transcribed from
six already-extracted source files. The file holds 181; it should hold **204** when done.

**DATA-ONLY, with one permitted code edit**: `tests/test_data.py` asserts
`len(rs.artifact_catalog) == 181`. Updating that single assertion is part of the job —
add a house-style comment above it pointing at your notes. **That is the only line of
Python you may write.** Any *other* failing test is a real defect: report it, do not
edit it.

## ⚠️ The one rule that outranks everything

**Exalted FIRST Edition. Transcribe what the source says. Never supply a value from your
own knowledge.** If you cannot read a value with certainty, write `"???"` and list the
artifact in your notes.

**Ratings are the sharp end.** An artifact's rating is spent against the Artifact
Background budget — a wrong dot count is a wrong game rule that reads as verified.

## The sources — read ONLY these

| Book | File | Pages |
|---|---|---|
| Exalted Core | `images/_extracted/Exalted Core.md` | 336-338, 344 |
| Savant and Sorcerer | `images/_extracted/Savant and Sorcerer.md` | 40-43 |
| Book of Bone and Ebony | `images/_extracted/Book of Bone and Ebony.md` | 104, 114 |
| Ruins of Rathess | `images/_extracted/Ruins of Rathess.md` | 86 |
| The Outcaste | `images/_extracted/The Outcaste.md` | 59, 63, 64 |
| Player's Guide | `images/_extracted/Player's Guide.md` | 211 |

Do not open anything in `sources/`. Skip anything under a `<!--GARBLED …-->`,
`<!--COLUMN SPLIT FAILED …-->` or `<!--SHATTERED HEADING …-->` marker and note it.

## ⚠ Reading ratings in the CORE book — the one new mechanic here

The corebook is decoded from a subsetted-font cipher. Its **body text is clean**, but
the artifact headings print their rating dots in a **display font that is NOT decoded**,
so each dot arrives as a replacement character:

```
SLAYER KHATAR *ARTIFACT ��+          -> Artifact ••
DRAGON TEAR TIARA *ARTIFACT ��+      -> Artifact ••
HEARTHSTONE AMULET *ARTIFACT �+      -> Artifact •
```

**The count is faithful — one `�` per dot.** That was checked against four artifacts
whose ratings are independently known, and it matched every time.

So: **count the `�` characters, then check that count against the worklist's rating.**

- **They agree** → that is your rating, and it now has two independent sources.
- **They disagree** → do NOT choose. Author the record with the worklist's rating, put
  the disagreement in `rating_notes`, and list it in your notes. A human will read the
  page image.

The other five books print real dots and need none of this.

## The record shape

`artifacts.json` is a flat JSON array — append, do not restructure. Copy the existing
entries' shape exactly:

```json
{
  "id": "artifact.core.dragon-tear-tiara",
  "name": "Dragon Tear Tiara",
  "rating": 2,
  "description": "…",
  "source": "Exalted Core p.337",
  "tags": ["senses", "tool"]
}
```

- **`id`** — `<prefix>.<name-kebab-cased>`, prefix per book in the worklist. Unique.
- **`rating`** — integer 1-5, from the printed dots. Required.
- **`rating_notes`** — only when the page prints a range (`"• or •••"`) or disagrees
  with the worklist. Omit otherwise.
- **`description`** — your own 1-4 sentence summary of the printed effect, matching the
  register of the existing 181. Every number in it comes from the page.
- **`source`** — `"<Book> p.<n>"`, book label exactly as given per worklist section.
- **`tags`** — from the **closed** vocabulary only: `armor`, `charm-store`, `combat`,
  `communication`, `healing`, `protection`, `senses`, `social`, `sorcery`, `spirit`,
  `summoning`, `thrown`, `tool`, `utility`, `vehicle`, `weapon`. **Do not invent one.**
  `[]` if nothing fits, and say so in the notes.

## Five traps specific to this batch

1. **Names as printed, not as the worklist spells them.** The worklist is a fan index
   with typos, and the last artifact batch found three (`Gunzosha Commando` → **Combat**,
   `Armor of the Immaculate Dragons` → **Armors**, `Implosion Bow, Medium` → **Medium
   Implosion Bow**). Expect more here; note every one.
2. **Some entries are generic classes, not single items** — `Charm against disease`,
   `Warding charms`, `Good Luck Charm`, `Mask`. Author what the page describes; if the
   page treats it as a category rather than a named artifact, **say so in the notes**
   rather than inventing a specific item.
3. **`Kireeki-class Assault Skyreme` and `The Insidious Ebon Xoanon` have rating `n/A`
   in the worklist.** Read the page; if it prints no rating, that is a real problem —
   `rating` is required and must be 1-5. **Do not invent one**: skip the entry and note
   it, exactly as the last batch correctly skipped Five Directions Formation Protocol.
4. **Ruins of Rathess p.86 was column-scrambled** in an earlier extraction. It has since
   been re-extracted in correct reading order, but it is the page most worth reading
   carefully — the last batch skipped its three entries for this reason.
5. **Do not touch the existing 181.** If an entry looks like it already exists under a
   different name, do not duplicate and do not edit — note it.

## Not on the worklist, and worth one look

The **Direlance** catalogue entry has been blocked for months on p.341 being unavailable.
That page is now readable, and it appears to contain only weapon-class prose plus the
p.342 stat table — **no standalone artifact entry**. If that is what you find, say so in
the notes and author nothing; that closes a long-open question. If you find a real
entry, author it and flag it as a 24th.

## What to hand back

1. The edited `exalted_builder/data/artifacts.json` and the one test line.
2. **A notes file** (`docs/status/artifact-batch-2-notes.md`) with, at minimum:
   - every artifact **skipped**, and why;
   - every `"???"`;
   - **every `�`-count vs worklist-rating disagreement**;
   - every worklist-vs-printed **name** disagreement;
   - every entry that turned out to be a generic class rather than an item;
   - what you found on core p.341 re: the Direlance;
   - anything you noticed and did not act on.

## How to check your own work

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

Expect **exactly one** failing test:
`test_merits_flaws.py::test_every_description_matches_the_source_text` — known and
machine-specific, not yours.

## What the review will check

- **Every rating against the printed dots** (`�`-count in the core book).
- **Every name present in its source book**, allowing for small-caps spacing damage.
- **`source` page within range** of where the entry actually appears.
- **Closed tag vocabulary**; ids unique; ratings integers 1-5.
- **No `.py` touched except the one assertion.**

---

## The worklist

### Exalted Core — 8

- source: `images/_extracted/Exalted Core.md`
- id prefix: `artifact.core`
- `"source": "Exalted Core p.<n>"`

| # | Name (worklist) | Rating (worklist) | Page |
|---|---|---|---|
| 1 | Charm against disease | • | 336 |
| 2 | Dragon Tear Tiara | •• | 337 |
| 3 | Good Luck Charm | • | 337 |
| 4 | Hearthstone Amulet | • | 337 |
| 5 | Walkaway | • | 337 |
| 6 | Warding charms | • | 337 |
| 7 | Hearthstone Bracers | •• | 338 |
| 8 | Slayer Khatar | •• | 344 |

### Savant and Sorcerer — 5

- source: `images/_extracted/Savant and Sorcerer.md`
- id prefix: `artifact.savant-sorcerer`
- `"source": "Savant and Sorcerer p.<n>"`

| # | Name (worklist) | Rating (worklist) | Page |
|---|---|---|---|
| 1 | Collar of Cleansing Light | • | 40 |
| 2 | Mask | •• | 41 |
| 3 | Ring of Being | •••• | 41 |
| 4 | Wings of the Raptor | •••• | 42 |
| 5 | Soul Mirror | ••••• | 43 |

### Book of Bone and Ebony — 3

- source: `images/_extracted/Book of Bone and Ebony.md`
- id prefix: `artifact.bone-ebony`
- `"source": "Book of Bone and Ebony p.<n>"`

| # | Name (worklist) | Rating (worklist) | Page |
|---|---|---|---|
| 1 | The Insidious Ebon Xoanon | n/A | 104 |
| 2 | Soulsteel Mesh Swathing | ••••• | 114 |
| 3 | Soulsteel Net | •••• | 114 |

### Ruins of Rathess — 3

- source: `images/_extracted/Ruins of Rathess.md`
- id prefix: `artifact.rathess`
- `"source": "Ruins of Rathess p.<n>"`

| # | Name (worklist) | Rating (worklist) | Page |
|---|---|---|---|
| 1 | Crystal of Protection | ••• | 86 |
| 2 | Ring of Disguise | ••• | 86 |
| 3 | Ring of Images | •• | 86 |

### The Outcaste — 3

- source: `images/_extracted/The Outcaste.md`
- id prefix: `artifact.outcaste`
- `"source": "The Outcaste p.<n>"`

| # | Name (worklist) | Rating (worklist) | Page |
|---|---|---|---|
| 1 | Implosion Bow, Medium | •••• | 59 |
| 2 | Manta-class Transport | ••••• | 63 |
| 3 | Kireeki-class Assault Skyreme | n/A | 64 |

### Player's Guide — 1

- source: `images/_extracted/Player's Guide.md`
- id prefix: `artifact.players-guide`
- `"source": "Player's Guide p.<n>"`

| # | Name (worklist) | Rating (worklist) | Page |
|---|---|---|---|
| 1 | Daiklave, Short | •• | 211 |
