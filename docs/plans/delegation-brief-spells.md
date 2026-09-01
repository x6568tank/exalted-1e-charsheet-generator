# Delegation brief — the 153 missing spells (Bone & Ebony + Savant and Sorcerer)

**For a cheap model (DeepSeek V4 Flash), 2026-08-10.** Hand this file over whole. The
worklist of every spell to author is appended at the bottom.

Follow-up review is by Claude against `docs/delegated-authoring.md`. This brief is
written to make that review short, so the checks it will run are stated up front —
**not as a trap, but so you can pass them.**

---

## The task, exactly

Add **153 spell records** to `exalted_builder/data/spells.json`, transcribed from two
already-extracted source files. Nothing else.

**This is a DATA-ONLY job.** Do not modify any `.py` file, any model, the engine, the
UI, or any other data file. If you believe a code change is needed, **stop and write it
down in the notes instead** — do not make it. (The last delegated batch's every defect
was a code change that described a rule without implementing it. This job avoids that
class entirely by having no code in it.)

## ⚠️ The one rule that outranks everything

**This is Exalted FIRST Edition. Transcribe what the source says. Never supply a value
from your own knowledge.**

Second Edition is a different game with different numbers and you have seen far more of
it. If a cost looks wrong to you, it is not wrong — you are reading 1e. Copy it.

**If you cannot read a value with certainty, write `"???"` in its place and list the
spell in your notes.** A `???` costs the reviewer five seconds. A confidently wrong
number survives for months. Never average, never infer from a neighbouring entry, never
"correct" anything, never fill a gap from memory.

## The sources — read ONLY these

| Book | File | Spell pages |
|---|---|---|
| Book of Bone and Ebony | `images/_extracted/Book of Bone and Ebony.md` | 119-143 |
| Savant and Sorcerer | `images/_extracted/Savant and Sorcerer.md` | 101-143 |

Both are page-marked with `<!--PAGE n-->`. **Do not open anything in `sources/`.**

### Passages you must NOT author from

The extractor marks text it could not render safely. **Treat a marked passage exactly
like a page that does not exist** — skip the spell, and list it in your notes:

- `<!--GARBLED ...-->`
- `<!--COLUMN SPLIT FAILED ...-->`
- `<!--SHATTERED HEADING, name unreadable: ...-->`

## The record shape

`spells.json` is a **flat JSON array**. Append to it; do not restructure it. Match the
existing entries exactly:

```json
{
  "id": "spell.terrestrial.death-of-obsidian-butterflies",
  "name": "Death of Obsidian Butterflies",
  "circle": "Terrestrial",
  "cost": { "motes": 15 },
  "description": "Calls forth a cascade of sculpted obsidian butterflies with razor-sharp wings in a pattern approximately 30 yards wide, 100 yards long and 10 yards high. […] The butterflies have a raw damage of 8, plus extra successes on the attack roll, and the damage is lethal.",
  "source": { "book": "Core", "page": 217 }
}
```

- **`id`** — `spell.<circle-lowercased>.<name-kebab-cased>`. Strip punctuation;
  `The Battle's End` → `spell.celestial.the-battles-end`. Ids must be unique.
- **`circle`** — one of exactly: `Terrestrial`, `Celestial`, `Solar`, `Shadowlands`,
  `Labyrinth`, `Void`. (`Man-Machine` / `God-Machine` exist but are Alchemical and not
  in this batch.) **Do not invent a circle.**
- **`cost`** — `{"motes": 15}` when it is a plain mote number. When it is anything more
  complex — "20 or 25 motes", "10 motes + 2 motes per additional hour", a Willpower
  component — use `{"raw": "<the printed text verbatim>"}`. Do not try to parse it.
- **`description`** — **your own summary of the printed effect**, not the full printed
  text. Every number in it must come from the page.

  ⚠ **This clause said "one-or-two-sentence" until 2026-09-01, and that length cap is
  what cost us the 19 Core spells.** Held to literally it drops mechanics: Death of
  Obsidian Butterflies lost its damage (8L), its automatic successes and its real area,
  and shrank a 30x100x10-yard pattern to "a roughly 10-yard area" — a wrong number, not
  a short one. Blood of Boiling Oil came out saying *aggravated* where the page says
  lethal. **A description is not length-capped: it is done when every mechanical clause
  on the page is in it.** Flavour compresses freely; numbers, durations, dice pools,
  soak, damage types and the conditions attached to them do not compress at all. The
  Core spells were re-transcribed on 2026-09-01 and are now the length reference.
  ⚠ **The same cap is still written into both artifact briefs** (`delegation-brief-
  artifacts.md` line 86 and `-artifacts-2.md` line 94, each "1-4 sentences"), and 330
  artifacts were authored under it. Whether they get this edit — and whether the
  artifact catalogue needs the same audit the Core spells just had — is the human's
  ruling, not a sweep to run unasked.
- **`source.book`** — exactly `"Book of Bone and Ebony"` or `"Savant and Sorcerer"`.
  `source.page` is an integer; for a spell spanning `125-126`, use the first page.

## The five traps specific to this batch

1. **`Adamant` = the `Solar` circle.** The worklist and the fan index call the third
   sorcery circle *Adamant*; the build calls it `Solar`. **These are the same circle
   under two in-universe naming schemes** (Realm vs. non-Realm study) — human's ruling,
   2026-08-10. Write `"Solar"`. Do NOT create an `Adamant` circle.
2. **The worklist's spelling is NOT authoritative — the book's is.** The worklist comes
   from a fan index that carries typos. It says `Sorcerer's Irrestible Puppetry`; the
   book prints `SORCERER'S IRRESISTIBLE PUPPETRY`. **Always use the spelling printed in
   the source file.** If the two differ, note it.
3. **Spell names are printed in SMALL CAPS** in these books, so they appear in the
   extraction as `CALLING THE WIND'S KISS`. Convert to Title Case for `name`.
   Do not copy the all-caps form.
4. **Do not touch the 92 existing spells.** If a spell on the worklist appears to
   already exist, **do not add a duplicate and do not edit the existing record** — note
   it and move on. (Two spells are printed in more than one book; the reviewer will
   resolve those.)
5. **Savant and Sorcerer's glyphs are already mapped**, so its punctuation is correct.
   One residue: `≠` appears once on p.110 as a real not-equals sign. It is not damage.

## What to hand back

1. The edited `exalted_builder/data/spells.json`.
2. **A notes file** (`docs/status/spell-batch-notes.md`) with, at minimum:
   - every spell you **skipped**, and why (garbled, not found, already present);
   - every `"???"` you wrote and what was unreadable;
   - every place the **worklist name disagreed with the printed name**;
   - every spell whose **cost you had to put in `raw`** because it was not a plain
     mote number;
   - anything you noticed and did not act on.

**Your notes list is the single most valuable thing you produce.** The last delegated
batch's notes were honest and good, and still missed a rule it had skipped without
noticing — so err heavily toward over-reporting. A gap you flag costs a minute; a gap
you don't costs a browser session.

## How to check your own work before handing back

```bash
.venv/bin/python -m pytest -q          # must stay at 2,091 passing
.venv/bin/python -c "
import json; d=json.load(open('exalted_builder/data/spells.json'))
ids=[s['id'] for s in d]
assert len(ids)==len(set(ids)), 'duplicate ids'
print(len(d), 'spells')"
```

Expect **245 spells** at the end (92 existing + 153 new). One failing test,
`test_every_description_matches_the_source_text`, is a known machine-specific failure
and is **not** yours — ignore it, but do not let the count of *other* failures rise
above zero.

## What the review will check

Stated so you can pre-empt it:

- **Every number traced back to the page.** Spot-checked against the source `.md`.
- **A prohibition sweep** — `grep -inE "\b(may not|cannot|can never|may never)\b"` over
  the source pages. Cheap models reliably implement what a source *grants* and miss what
  it *forbids*. If a spell's text restricts who may cast it or what it may target,
  that belongs in the description.
- **Circle assignment**, since it decides what each splat can reach.
- **Ids resolve and are unique**; the loader link-checks them.
- **No `.py` file touched.**

---

## The worklist

### Book of Bone and Ebony — 60 spells

| # | Name | Circle | Page |
|---|---|---|---|
| 1 | Baneful Sun | Labyrinth | 131 |
| 2 | Clamoring Shackles | Labyrinth | 132 |
| 3 | Crystal Ghost Shard | Labyrinth | 132 |
| 4 | Dead Man’s Voice | Labyrinth | 133 |
| 5 | Denying the Call | Labyrinth | 133 |
| 6 | Golden Shadows Cast in Frieze | Labyrinth | 134 |
| 7 | Gray Eyes Shield and Shell | Labyrinth | 135 |
| 8 | Infinite Footsteps | Labyrinth | 135 |
| 9 | Joyless Spirit’s Corruption | Labyrinth | 135 |
| 10 | Links Born of Tumult | Labyrinth | 136 |
| 11 | Rattled Bones of War | Labyrinth | 136 |
| 12 | Rebirth Into Darkness | Labyrinth | 137 |
| 13 | Seven Visions Wisdom | Labyrinth | 137 |
| 14 | Shadow Stones Travel | Labyrinth | 137 |
| 15 | Shield of Shattering Bones | Labyrinth | 138 |
| 16 | Silenced Whispered Prayers | Labyrinth | 138 |
| 17 | Sweet Voice Familiar | Labyrinth | 138 |
| 18 | Banish Ghost | Shadowlands | 119 |
| 19 | Black Candle Visage | Shadowlands | 119 |
| 20 | Bless the Rapine Soul | Shadowlands | 120 |
| 21 | Blessed Dead Fools | Shadowlands | 120 |
| 22 | Blood Mirror Speech | Shadowlands | 120 |
| 23 | Bone Puppet Dance | Shadowlands | 121 |
| 24 | Bonfire Visions | Shadowlands | 121 |
| 25 | Death Flies Two Sails | Shadowlands | 121 |
| 26 | Death Inversion Loop | Shadowlands | 122 |
| 27 | Death Mask | Shadowlands | 122 |
| 28 | Drawing Blind Edge | Shadowlands | 123 |
| 29 | Dusk Eyes | Shadowlands | 123 |
| 30 | Easing the Forsaken Memory | Shadowlands | 123 |
| 31 | Emperor’s Chains | Shadowlands | 124 |
| 32 | Faces of the Dead | Shadowlands | 124 |
| 33 | Field of Fell Dreams | Shadowlands | 124 |
| 34 | Five Gifts | Shadowlands | 124 |
| 35 | Flesh and Bone Winds | Shadowlands | 125 |
| 36 | Flesh-Sloughing Wave | Shadowlands | 126 |
| 37 | Gathering a Ghost’s Strings | Shadowlands | 126 |
| 38 | Gentle Call of Lethe | Shadowlands | 127 |
| 39 | Master Puppeteer’s Knife | Shadowlands | 127 |
| 40 | Midnight Shadow Sun | Shadowlands | 127 |
| 41 | Mother Darkness | Shadowlands | 128 |
| 42 | Piercing the Heel | Shadowlands | 128 |
| 43 | Ringing Hun Rebuke | Shadowlands | 128 |
| 44 | Seat of Deadly Splendors | Shadowlands | 129 |
| 45 | Shattered Void Mirror | Shadowlands | 129 |
| 46 | Silent Master’s Pollen | Shadowlands | 129 |
| 47 | Smoothing the Crease-Worn Mind | Shadowlands | 130 |
| 48 | Stones Worn Smooth | Shadowlands | 130 |
| 49 | Trolling the Dark Water | Shadowlands | 130 |
| 50 | Without Pity, Without Scorn | Shadowlands | 130 |
| 51 | Birth of Sanity’s Sorrow | Void | 139 |
| 52 | Black Faith | Void | 140 |
| 53 | Forsaken Life Engine | Void | 140 |
| 54 | Grandmother Void | Void | 141 |
| 55 | Mouth of the Void | Void | 142 |
| 56 | Pyre-Flame Guardian | Void | 142 |
| 57 | Risen and Screaming | Void | 143 |
| 58 | Sins of the Father | Void | 143 |
| 59 | Summon Hekatonkhire | Void | 143 |
| 60 | The Clay of Warped Dreams | Void | 140 |

### Savant and Sorcerer — 93 spells

| # | Name | Circle | Page |
|---|---|---|---|
| 1 | Between the Minute and the Hour | Celestial | 125 |
| 2 | Bone Lion | Celestial | 125-126 |
| 3 | Cantata of Empty Voices | Celestial | 126 |
| 4 | Cloud Trapeze | Celestial | 126-127 |
| 5 | Eternal Crystalline Encasement | Celestial | 127 |
| 6 | Force of Life’s Summer | Celestial | 128 |
| 7 | Geyser of Corruption | Celestial | 128 |
| 8 | Hideous Confusion of Tongues | Celestial | 128 |
| 9 | Imbue Amalgam | Celestial | 128-129 |
| 10 | Insidious Tendrils of Hate | Celestial | 129-130 |
| 11 | Ivory Orchid Pavilion | Celestial | 130-131 |
| 12 | Magma Kraken | Celestial | 131 |
| 13 | Mercury's Deliverance | Celestial | 131 |
| 14 | Outside Worlds Within | Celestial | 131-132 |
| 15 | Raise the Puissant Sanctum | Celestial | 57 |
| 16 | Rolling Earth Carpet | Celestial | 132-133 |
| 17 | Servant of Infallible Location | Celestial | 133 |
| 18 | Shadow Theft | Celestial | 133 |
| 19 | Shadows of the Ancient Past | Celestial | 134 |
| 20 | Summon the Army of the Wild | Celestial | 134-135 |
| 21 | Summoning of the Heart of Darkness | Celestial | 135 |
| 22 | Swift Spirit of Winged Transportation | Celestial | 136 |
| 23 | The Battle’s End | Celestial | 125 |
| 24 | The Faithful Ally | Celestial | 127 |
| 25 | The Princes of the Fallen Tower | Celestial | 132 |
| 26 | The Spawning of Monsters | Celestial | 134 |
| 27 | Threefold Binding of the Heart | Celestial | 136 |
| 28 | Torrential Cascade | Celestial | 137 |
| 29 | Unity of Dreams | Celestial | 137 |
| 30 | Voices of Distant Regard | Celestial | 137-138 |
| 31 | Wheel of the Turning Heavens | Celestial | 138 |
| 32 | Whirlwind of Fate | Celestial | 138 |
| 33 | Abjuration of the Maidens | Solar | 138-139 |
| 34 | Benediction of Archgenesis | Solar | 139 |
| 35 | Chariot of the Blazing Sun | Solar | 139-140 |
| 36 | Craft the Puissant Sanctum | Solar | 57-58 |
| 37 | Curse of Unyielding Mist | Solar | 140-141 |
| 38 | Essence Inversion | Solar | 141 |
| 39 | Gaia's Rebuke | Solar | 141-142 |
| 40 | Incantation of the Invincible Army | Solar | 142 |
| 41 | Total Annihilation | Solar | 142 |
| 42 | Wrath of the Five Elements | Solar | 142-143 |
| 43 | Becoming the Wood Friend | Terrestrial | 101-102 |
| 44 | Blood Lash | Terrestrial | 102 |
| 45 | Burning Eyes of the Offender | Terrestrial | 102 |
| 46 | Calling the Wind’s Kiss | Terrestrial | 102-103 |
| 47 | Commanding the Beasts | Terrestrial | 103 |
| 48 | Conjuring the Azure Chariot | Terrestrial | 103 |
| 49 | Corrupted Words | Terrestrial | 103-104 |
| 50 | Curse of Slavish Humility | Terrestrial | 104 |
| 51 | Dance of the Smoke Cobras | Terrestrial | 104-105 |
| 52 | Disguise of the New Face | Terrestrial | 105 |
| 53 | Emerald Circle Banishment | Terrestrial | 105 |
| 54 | Eye of Alliance | Terrestrial | 105 |
| 55 | Flight of Separation | Terrestrial | 106 |
| 56 | Flight of the Brilliant Raptor | Terrestrial | 106-107 |
| 57 | Flying Guillotine | Terrestrial | 107 |
| 58 | Food from the Aerial Table | Terrestrial | 107 |
| 59 | Fugue of Truth | Terrestrial | 107 |
| 60 | Hound of the Five Winds | Terrestrial | 108-109 |
| 61 | Hypnotic Piping | Terrestrial | 109 |
| 62 | Incantation of Spiritual Discretion | Terrestrial | 109 |
| 63 | Internal Flame | Terrestrial | 109-110 |
| 64 | Lightning Spider | Terrestrial | 110 |
| 65 | Manifestations of Vigorous Design | Terrestrial | 110 |
| 66 | Mast-Shattering Spell | Terrestrial | 110-111 |
| 67 | Mists of Eventide | Terrestrial | 111 |
| 68 | Paralyzing Contradiction | Terrestrial | 111 |
| 69 | Personal Tempest | Terrestrial | 112 |
| 70 | Plague of Bronze Snakes | Terrestrial | 112 |
| 71 | Private Plaza of Downcast Eyes | Terrestrial | 112-113 |
| 72 | Ritual of Elemental Empowerment | Terrestrial | 114 |
| 73 | River of Blood | Terrestrial | 114-115 |
| 74 | Sacred Tongue | Terrestrial | 115 |
| 75 | Shadow Summons | Terrestrial | 115-116 |
| 76 | Silent Words of Dreams and Nightmares | Terrestrial | 116 |
| 77 | Sleep of Stony Safety | Terrestrial | 117 |
| 78 | Sorcerer’s Irrestible Puppetry | Terrestrial | 117-118 |
| 79 | Spirit Sword | Terrestrial | 118 |
| 80 | Spirit of Might | Terrestrial | 118 |
| 81 | Sprouting Shackles of Doom | Terrestrial | 118-119 |
| 82 | Sting of the Ice Hornet | Terrestrial | 121 |
| 83 | Summoning the Lesser Minions of the Eyeless Face | Terrestrial | 121-122 |
| 84 | The Horse that Travels Earth and Water | Terrestrial | 108 |
| 85 | The Spy Who Walks in Darkness | Terrestrial | 119-121 |
| 86 | The Tree’s Many Branches | Terrestrial | 122-123 |
| 87 | Theft of Memory | Terrestrial | 122 |
| 88 | Thunder Wolf’s Howl | Terrestrial | 122 |
| 89 | Unbreakable Bones of Stone | Terrestrial | 123 |
| 90 | Unconquerable Self | Terrestrial | 123 |
| 91 | Unstoppable Fountain of the Depths | Terrestrial | 123 |
| 92 | Viridian Mantle of Underwater Journeys | Terrestrial | 123-124 |
| 93 | Virtuous Guardian of Flame | Terrestrial | 124-125 |
