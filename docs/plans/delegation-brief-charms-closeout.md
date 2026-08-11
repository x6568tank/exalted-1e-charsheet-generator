# Delegation brief — the last 16 Charms on disk (five different shapes)

**For a cheap model (DeepSeek V4 Flash), 2026-08-11.** Hand this file over whole.

Sixth batch, and the last one that can be authored from text already on disk. After it,
every remaining entry in every track needs a page sync.

⚠ **This batch is different from the previous five: it is SMALL and MIXED.** Sixteen
entries across **five different record shapes**, in five different files. The previous
batches were one shape repeated; this one is five shapes barely repeated. **Read each
section's shape spec separately and do not carry a convention across sections.** The
likeliest error here is a correct record written in the wrong file.

---

## ⚠️ The one rule that outranks everything

**Exalted FIRST Edition. Transcribe what the source says. Never supply a value from your
own knowledge.** If you cannot read a value with certainty, write `"???"` and note it.

Skip anything under a `<!--GARBLED …-->`, `<!--COLUMN SPLIT FAILED …-->` or
`<!--SHATTERED HEADING …-->` marker and note it. Do not open anything in `sources/`.

**Scope: DATA-ONLY.** Do not modify any `.py` file, including tests. No test counts
these, so none should need touching. If one fails, that is a real defect — report it.

---

# Section 1 — five Dragon-Blooded Charms (The Outcaste)

**Source:** `images/_extracted/The Outcaste.md`
**File:** append to the existing `exalted_builder/data/charms/dragonblooded_<ability>.json`
for each Charm's ability — they are ordinary ability Charms.

| Name | Ability | Page |
|---|---|---|
| Vision Outside Time | Investigation | 130 |
| Atsiluth's Bounty | Investigation | 130 |
| Tireless Footfalls Cadence | Performance | 44 |
| Flawless Training Execution | Performance | 44 |
| Peerless Training Method Protocols | Performance | 45 |

Shape — copy an existing record in the target file exactly:

```json
{
  "id": "dragonblooded.investigation.vision-outside-time",
  "name": "Vision Outside Time",
  "category": "investigation",
  "exalt_type": "Dragon-Blooded",
  "type": "Simple",
  "min_ability": 4,
  "min_essence": 3,
  "prerequisites": [["dragonblooded.investigation.<prereq>"]],
  "cost": { "raw": "2 motes, 1 Willpower", "motes": 2, "willpower": 1 },
  "duration": "One scene",
  "description": "…",
  "source": { "book": "Exalted 1e The Outcaste", "page": 130 }
}
```

⚠ **`source.book` is exactly `"Exalted 1e The Outcaste"`** — five Outcaste Charms are
already in the build using that string; match it. (Book naming is not uniform across the
project; see `docs/source-attribution.md`. Copy the neighbours, do not invent.)

⚠ **`Vision Outside Time` is ONE Charm, not two.** The index lists it under both
Investigation and Lore; the book prints a single entry on p.130 with
`Minimum Investigation: 4`. Author it once, under Investigation.

---

# Section 2 — two Solar Charms + one Dragon-Blooded Charm (Player's Guide)

**Source:** `images/_extracted/Player's Guide.md`
**Files:** the existing `solar_lore.json`, `solar_performance.json`,
`dragonblooded_bureaucracy.json`.

| Name | Splat / Ability | Page |
|---|---|---|
| Power-Investing Prana | Solar / Lore | 123 |
| Dragon-Soul Enlightening Method | Solar / Performance | 158 |
| Wise Commander's Gift | Dragon-Blooded / Bureaucracy | 123 |

Same ordinary-Charm shape as Section 1. `source.book` is `"Player's Guide"` for all
three (that exact string is already used by 64 Charms in the build).

---

# Section 3 — four Elemental Powers (Games of Divinity)

**Source:** `images/_extracted/Games of Divinity.md` p.56, the *New Elemental Powers*
sidebar.
**File:** `exalted_builder/data/elemental_powers.json` — **NOT a charms file.**

| Name | Page |
|---|---|
| Day to Night | 56 |
| Foul the Waters | 56 |
| Immolation | 56 |
| Elemental Unction | 56 |

Different shape — no `category`, no `exalt_type`, no `prerequisites`, no `type`:

```json
{
  "id": "elemental.day-to-night",
  "name": "Day to Night",
  "bp_cost": 7,
  "min_essence": 2,
  "required_merits": ["mf.elemental-dominion"],
  "activation": "<the printed activation cost and timing, in prose>",
  "description": "<the printed effect>",
  "source": { "book": "Games of Divinity", "page": 56 }
}
```

⚠ **`bp_cost: 7`, `min_essence: 2` and `required_merits: ["mf.elemental-dominion"]` are
UNIFORM across all nine existing powers and are NOT printed on the page.** The 7 is the
Elemental Dominion Merit's own cost. **Copy those three fields verbatim from the
existing entries — do not derive, and do not put a mote cost in `bp_cost`.** The mote
costs the page prints belong in `activation`.

Two of that sidebar's six powers (Consume Element, Plague of Menaces) are **already
authored** — leave them alone.

---

# Section 4 — three Lunar Beastman Gifts (Player's Guide p.207)

**Source:** `images/_extracted/Player's Guide.md` p.207
**File:** `exalted_builder/data/charms/lunar_shapeshifting.json`

⚠ **These are NOT new Charm records.** They are **variants appended to the existing
Charm** `lunar.shapeshifting.deadly-beastman-transformation`, which already carries 19.
Append three entries to its `variants` array and change nothing else about it:

```json
{ "key": "aspect-of-the-gillman",
  "label": "Aspect of the Gillman",
  "max_purchases": 1,
  "description": "<the printed effect>" }
```

| Label | Page |
|---|---|
| Aspect of the Gillman | 207 |
| Soaring Pinions | 207 |
| Fluttering Wings | 207 |

`key` is the label kebab-cased. Use `max_purchases: 1` unless the page says the gift can
be taken more than once — check, and note what you found either way.

---

# Section 5 — one Spirit Charm (Player's Guide p.85)

**Source:** `images/_extracted/Player's Guide.md` p.85
**File:** `exalted_builder/data/charms/spirit_templates.json`

| Name | Page |
|---|---|
| Investiture of Infernal Glory | 85 |

A **Virtue-keyed** shape — like the ghost Arcanoi, not like Sections 1-2:

```json
{
  "id": "spirit.spirit-templates.investiture-of-infernal-glory",
  "name": "Investiture of Infernal Glory",
  "category": "spirit_templates",
  "exalt_type": "Spirit",
  "type": "Simple",
  "min_virtue": "conviction",
  "min_ability": 5,
  "min_essence": 4,
  "cost": { "raw": "60 motes, 6 Willpower", "motes": 60, "willpower": 6 },
  "duration": "Until completed",
  "description": "…",
  "source": { "book": "Player's Guide", "page": 85 }
}
```

⚠ `min_virtue` is required and `min_ability` RATES that Virtue (it is not an Ability).
⚠ The heading extracts glued as `INVESTITUREOF INFERNAL GLORY` — the name is
**Investiture of Infernal Glory**. Read the printed minimums off the page; the values
above are the shape, not the data.

---

## NOT in this batch

**`Five Directions Formation Protocol`** (PG p.242) stays unauthored. It prints `Varies`
for Cost, Duration, Type, Minimum Martial Arts *and* Minimum Essence; the model needs a
concrete type and integer minimums, so encoding it means inventing five numbers. A
previous batch correctly skipped it and the reasoning has not changed.

## What to hand back

1. The edited data files.
2. **A notes file** (`docs/status/charms-closeout-notes.md`) with, at minimum:
   - every entry **skipped**, and why;
   - every `"???"`;
   - every **prerequisite you could not resolve**;
   - every worklist-vs-printed **name** disagreement;
   - **whether any Beastman Gift is repeatable** (`max_purchases`);
   - anything you noticed and did not act on.

## How to check your own work

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -c "
import json,glob
rows=[r for f in glob.glob('exalted_builder/data/charms/*.json') for r in json.load(open(f))]
ids={r['id'] for r in rows}
assert len(ids)==len(rows), 'duplicate charm ids'
for r in rows:
    for g in r.get('prerequisites',[]):
        for p in g: assert p in ids, (r['id'], p)
ep=json.load(open('exalted_builder/data/elemental_powers.json'))
assert len({e['id'] for e in ep})==len(ep)
print(len(rows),'charms |',len(ep),'elemental powers')"
```

Expect **1,837 Charms** (1,828 + 5 Outcaste + 3 Player's Guide + 1 Spirit — the
Beastman Gifts are variants, not records, and the Elemental Powers are a separate file),
**13 elemental powers**, and exactly one failing test —
`test_merits_flaws.py::test_every_description_matches_the_source_text`, known and
machine-specific.

## What the review will check

- **Every cost, minimum and prerequisite traced to the page.**
- **Each entry in the RIGHT FILE for its shape** — the most likely error in a mixed
  batch is a correct record in the wrong place.
- **The elemental powers' three uniform fields copied, not derived.**
- **The Beastman Gifts appended as variants**, with the parent Charm otherwise untouched.
- **No `.py` file touched.**
