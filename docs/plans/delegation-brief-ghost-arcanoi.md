# Delegation brief — the 71 missing Ghost Arcanoi (Book of Bone and Ebony)

**For a cheap model (DeepSeek V4 Flash), 2026-08-11.** Hand this file over whole. The
worklist of every Arcanos to author is appended at the bottom.

Third batch of this kind. The first two — 151 spells, 141 artifacts — both came back
accurate, and both times the most valuable thing produced was the notes file. **This one
is harder than either**, for a reason worth stating up front: it is the first batch that
adds *structure* rather than rows. Read *The shape of the job* before starting.

---

## The task, exactly

Author **71 Ghost Arcanoi** into `exalted_builder/data/charms/`, transcribed from
`images/_extracted/Book of Bone and Ebony.md`. The build currently holds 56 Arcanoi
across six files; it should hold **127** across fourteen when you are done.

**This is a DATA job plus a bounded set of test edits** (see *The tests you may touch*).
Do not modify any model, the engine, the UI, or the loader. If you believe those need
changing, **write it in the notes instead** — do not do it.

## ⚠️ The one rule that outranks everything

**This is Exalted FIRST Edition. Transcribe what the source says. Never supply a value
from your own knowledge.** If a cost or minimum looks wrong, it is not wrong — you are
reading 1e. **If you cannot read a value with certainty, write `"???"` and list the
Arcanos in your notes.** Never infer, never average, never "correct".

## The source — read ONLY this

`images/_extracted/Book of Bone and Ebony.md`, page-marked with `<!--PAGE n-->`.
**Do not open anything in `sources/`.** Skip anything under a `<!--GARBLED …-->`,
`<!--COLUMN SPLIT FAILED …-->` or `<!--SHATTERED HEADING …-->` marker and note it —
skipping correctly is a success, not a failure.

⚠ **One entry on the worklist is NOT in this book.** `Fertile Soul Endowment` (listed
under *Essense-Measuring Thief Arts*, p.82) is a **Player's Guide** Arcanos, not a Bone
& Ebony one. Its text is in `images/_extracted/Player's Guide.md` at p.82 — author it
from there, with `"source": {"book": "Player's Guide", "page": 82}`. That makes 70 from
Bone & Ebony and 1 from the Player's Guide.

## The shape of the job

Existing Arcanoi live one file per Arcanos, e.g. `data/charms/ghost_tangled_web.json`,
as a flat array. A record:

```json
{
  "id": "ghost.essence-measuring-thief.aura-reading-technique",
  "name": "Aura-Reading Technique",
  "category": "essence_measuring_thief",
  "exalt_type": "Ghost",
  "type": "Simple",
  "min_virtue": "temperance",
  "min_ability": 1,
  "min_essence": 1,
  "prerequisites": [],
  "cost": { "raw": "2 motes", "motes": 2 },
  "duration": "One scene",
  "description": "…",
  "source": { "book": "Book of Bone and Ebony", "page": 36 }
}
```

Field notes — these are where this batch differs from the last two:

- **`id`** — `ghost.<category-kebab>.<name-kebab>`. Unique.
- **`category`** — the exact slug given in each worklist heading. **Eight are new files
  you create; two extend existing files.** Both are marked in the worklist.
- **`exalt_type`** — always `"Ghost"`.
- **`min_virtue`** — ⚠ **the defining property of this splat.** Every Arcanos prints
  exactly one `Minimum <Virtue>`: `compassion`, `conviction`, `temperance` or `valor`.
  Lowercase. **Every record must have one**; a test enforces it.
- **`min_ability`** — the NUMBER printed after that Virtue (it rates the Virtue, despite
  the field name). Never an Ability. `min_attribute` must stay absent.
- **`min_essence`** — the printed Minimum Essence.
- **`prerequisites`** — a list of **groups**, each group a list of Charm ids:
  `[["ghost.common.dark-steed-mastery"]]` means "requires that one". Multiple ids in one
  group mean OR; multiple groups mean AND. `[]` for a root with no prerequisite. **Every
  id must resolve to a Charm you have authored or one already in the build** — the
  loader refuses a dangling reference, so a typo fails loudly at load, not silently.
- **`cost`** — `{"raw": "<printed text>", "motes": N}` when it is a plain mote number;
  `{"raw": "<printed text>"}` alone when it is anything more complex. **Always keep
  `raw` verbatim.**
- **`source`** — `{"book": "Book of Bone and Ebony", "page": <int>}` for all but one;
  `Fertile Soul Endowment` is `{"book": "Player's Guide", "page": 82}`.

## The five traps specific to this batch

1. **⚠ `Evoke the Ancient Clay` and `Shifting Ghost-Clay Path` are DIFFERENT Arcanoi**,
   not the same one renamed. So are `Shadow Constraint Craft` and anything in the
   existing six. **Do not merge an Arcanos into an existing category** because the name
   looks similar — the worklist tells you which file each entry belongs in, and it is
   authoritative on that point.
2. **`Common Arcanoi` is not a path.** The book says: *"The Arcanoi listed below are not
   part of long Charm trees. Most are individual arts that can be learned piecemeal."*
   They still get a category (`common`) so the picker can group them, but expect most to
   have `"prerequisites": []`.
3. **The prerequisite graph is the part most likely to go wrong.** A prerequisite you
   cannot resolve is not a reason to invent an id — leave `[]`, and **note it**. An
   Arcanos wrongly made a root is visible; a dangling id refuses to load.
4. **Names are printed in SMALL CAPS** and the extraction sometimes glues or spaces
   them (`DARK STEED MASTERY`, `POLETHE BLACK DEPTHS`). Convert to Title Case and
   **prefer the printed name over the worklist's** — the worklist is a fan index and
   carries typos (it spells one path `Essense-Measuring`).
5. **Two Arcanoi appear in more than one tree** in the index. Author once, in the file
   the worklist names, and note the cross-listing.

## The tests you may touch

Six assertions in `tests/test_ghost.py` describe **the E:Ab CH6 set specifically** — its
56 Arcanoi, its six paths, its 18/18/11/9 Virtue split, its page range, its 50/56/6
prerequisite shape. That evidence is valuable and **must not be destroyed by loosening
the numbers.**

**So: scope them to the E:Ab subset rather than widening them.** Change the helper:

```python
def _arcanoi(rs) -> list:
    """Every Ghost Charm."""
    return [c for c in rs.charms.values() if c.exalt_type == "Ghost"]


def _abyssals_arcanoi(rs) -> list:
    """Only the E:Ab CH6 set. The assertions below count THAT source's printed shape;
    Book of Bone and Ebony adds its own Arcanoi and must not move these numbers."""
    return [c for c in _arcanoi(rs)
            if c.source and c.source.book == "Exalted: The Abyssals"]
```

Then point these six tests at `_abyssals_arcanoi` and **leave every number unchanged**:

- `test_all_fifty_six_arcanoi_are_authored`
- `test_the_six_paths_have_their_printed_counts`
- `test_the_virtue_split_matches_the_source`
- `test_every_arcanos_carries_its_page`
- `test_every_prerequisite_resolves_within_the_catalogue`
- `test_the_one_health_level_cost_uses_the_damage_shorthand` (only if it fails)

`test_every_arcanos_is_virtue_keyed` should stay on `_arcanoi` — **it must apply to your
new Arcanoi too.** If it fails, that is a real defect in your data.

**Those edits are the only Python you may write.** If any *other* test fails,
investigate and report it rather than editing it.

## What to hand back

1. The new/edited files under `exalted_builder/data/charms/` and the scoped tests.
2. **A notes file** (`docs/status/ghost-arcanoi-batch-notes.md`) with, at minimum:
   - every Arcanos **skipped**, and why;
   - every `"???"`;
   - every **prerequisite you could not resolve**, and what the page said;
   - every place the **worklist name disagreed with the printed name**;
   - the **per-category count** you ended with, so the reviewer can diff it;
   - anything you noticed and did not act on.

## How to check your own work

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -c "
import json,glob,collections
rows=[r for f in glob.glob('exalted_builder/data/charms/ghost_*.json') for r in json.load(open(f))]
ids=[r['id'] for r in rows]
assert len(ids)==len(set(ids)), 'duplicate ids'
assert all(r.get('min_virtue') in ('compassion','conviction','temperance','valor') for r in rows), 'bad min_virtue'
assert all(r.get('exalt_type')=='Ghost' for r in rows)
known=set(ids)
for r in rows:
    for g in r.get('prerequisites',[]):
        for p in g:
            assert p in known or p.startswith('ghost.'), p
print(len(rows),'arcanoi'); print(collections.Counter(r['category'] for r in rows))"
```

Expect **127 Arcanoi** and **exactly one** failing test at the end:
`test_merits_flaws.py::test_every_description_matches_the_source_text` — a known
machine-specific failure, not yours.

## What the review will check

- **Every cost, minimum and Virtue key traced back to the page.**
- **`min_virtue` present on all 71**, and the printed number in `min_ability`.
- **Prerequisite ids all resolve**, and the root/edge shape is sane per path.
- **The E:Ab tests still assert their original numbers**, scoped not loosened.
- **Names as printed**, not as the index spells them.
- **No `.py` file touched beyond `tests/test_ghost.py`.**

---

## The worklist

### Ghost: Common Arcanoi — 15 Arcanoi
`category: "common"` — **NEW file** `data/charms/ghost_common.json`

| # | Name | Page | Combo-OK |
|---|---|---|---|
| 1 | Dark Steed Mastery | 36 | ✔ |
| 2 | Moon’s Cold Glow | 36 |  |
| 3 | Pole the Black Depths | 36 | ✔ |
| 4 | Scent of Sweet Blood | 36 |  |
| 5 | Two World Vision | 36 |  |
| 6 | Whispers of the Living | 36 |  |
| 7 | Assassin’s Subtle Escape | 37 |  |
| 8 | Breeze-Carried Ash Form | 37 |  |
| 9 | Motivated Shell | 37 |  |
| 10 | Pyre Smoke Form | 37 |  |
| 11 | Ride the Mystic Vessel | 37 |  |
| 12 | Angry Trickster Ghost Method | 38 |  |
| 13 | Former Life Destruction Technique | 38 |  |
| 14 | Staggered Dark Stars Movement | 38 |  |
| 15 | Hours Like Autumn Leaves | 39 |  |

### Ghost: Evoke the Ancient Clay — 14 Arcanoi
`category: "evoke_the_ancient_clay"` — **NEW file** `data/charms/ghost_evoke_the_ancient_clay.json`

| # | Name | Page | Combo-OK |
|---|---|---|---|
| 1 | Pole the Black Depths | 36 | ✔ |
| 2 | Marsh Light | 39 |  |
| 3 | Whisper | 39 |  |
| 4 | Emody | 40 |  |
| 5 | Sleeper’s Caul | 40 |  |
| 6 | Sweet Winsome Light | 40 |  |
| 7 | Tinker’s Body | 40 |  |
| 8 | Birth the Perfected Master | 41 |  |
| 9 | Birth the Warrior Form | 41 |  |
| 10 | Conjure the Defeated Vessel | 41 |  |
| 11 | Manifest the Dark Steed | 41 |  |
| 12 | Unending Rebirth | 41 |  |
| 13 | Sunken Admiral Technique | 42 |  |
| 14 | Unconsious Speech | 42 |  |

### Ghost: Shadow Constraint Craft — 10 Arcanoi
`category: "shadow_constraint_craft"` — **NEW file** `data/charms/ghost_shadow_constraint_craft.json`

| # | Name | Page | Combo-OK |
|---|---|---|---|
| 1 | Illuminate the Shadow Constraint | 43 |  |
| 2 | Accept Amercement | 44 |  |
| 3 | Brief Exemption | 44 |  |
| 4 | Dark Sorcery Observation | 44 |  |
| 5 | Ghostly Magistrate Perception | 44 |  |
| 6 | House Arrest | 44 |  |
| 7 | Levy Fine | 44 |  |
| 8 | Curse of the Damned | 45 | ✔ |
| 9 | Hide the Living Name | 45 |  |
| 10 | Impose Stricture | 45 |  |

### Ghost: Tenacious Merchant's Way — 7 Arcanoi
`category: "tenacious_merchants_way"` — **NEW file** `data/charms/ghost_tenacious_merchants_way.json`

| # | Name | Page | Combo-OK |
|---|---|---|---|
| 1 | Bold Thief’s Way | 50 | ✔ |
| 2 | Careful Debtor Stance | 50 | ✔ |
| 3 | Earnest Creditor Technique | 50 | ✔ |
| 4 | Jangling Coin Puch Sense | 50 |  |
| 5 | Redirected Prayer Path | 50 | ✔ |
| 6 | Cannibal Call | 51 | ✔ |
| 7 | Secret Imperial Mint Technique | 51 | ✔ |

### Ghost: Noble Craftsman Ways — 6 Arcanoi
`category: "noble_craftsman_ways"` — **NEW file** `data/charms/ghost_noble_craftsman_ways.json`

| # | Name | Page | Combo-OK |
|---|---|---|---|
| 1 | Soulsteel Scream | 48 | ✔ |
| 2 | Soulsteel Shaper | 48 |  |
| 3 | Grave Goods Shaping Technique | 49 |  |
| 4 | Soulsteel Forging | 49 |  |
| 5 | Soulsteel Miner’s Sense | 49 |  |
| 6 | Soulsteel Rebuilding Technique | 49 |  |

### Ghost: Scholarly Ways — 6 Arcanoi
`category: "scholarly_ways"` — **NEW file** `data/charms/ghost_scholarly_ways.json`

| # | Name | Page | Combo-OK |
|---|---|---|---|
| 1 | Discerning Student Technique | 47 |  |
| 2 | Imperous Instructor’s Dictate | 47 |  |
| 3 | Masterly Pedagogical Inquiry | 47 | ✔ |
| 4 | Unseemly Librarian Nature | 47 |  |
| 5 | Eternally Loyal Student Prana | 48 |  |
| 6 | Favored-Student Charm | 48 |  |

### Ghost: Chains of the Ancient Monarchs — 5 Arcanoi
`category: "chains_of_the_ancient_monarchs"` — **NEW file** `data/charms/ghost_chains_of_the_ancient_monarchs.json`

| # | Name | Page | Combo-OK |
|---|---|---|---|
| 1 | Monarch’s Glorous Brilliance | 51 |  |
| 2 | Soul Anchor | 51 |  |
| 3 | Essence Binding | 52 |  |
| 4 | Snare the Fleeing Thief | 52 |  |
| 5 | Essence Lasso Form | 53 |  |

### Ghost: Stringless Puppeteer Art — 4 Arcanoi
`category: "stringless_puppeteer"` — **EXTENDS the existing file** `data/charms/ghost_stringless_puppeteer.json`

| # | Name | Page | Combo-OK |
|---|---|---|---|
| 1 | Intangible Guardian Presence | 91 |  |
| 2 | The Embalmer’s Art | 91 |  |
| 3 | Drive the Necrotic Collossus | 92 |  |
| 4 | Instauration of the Fleshly Vessel | 92 | ✔ |

### Ghost: Honored Ancestor Ways — 3 Arcanoi
`category: "honored_ancestor_ways"` — **NEW file** `data/charms/ghost_honored_ancestor_ways.json`

| # | Name | Page | Combo-OK |
|---|---|---|---|
| 1 | Courier in Dreams | 46 |  |
| 2 | Dishonorable Descendant Curse | 46 |  |
| 3 | Honorable Descendant Blessing | 46 |  |

### Ghost: Essense-Measuring Thief Arts — 1 Arcanoi
`category: "essence_measuring_thief"` — **EXTENDS the existing file** `data/charms/ghost_essence_measuring_thief.json`

| # | Name | Page | Combo-OK |
|---|---|---|---|
| 1 | Fertile Soul Endowment | 82 |  |
