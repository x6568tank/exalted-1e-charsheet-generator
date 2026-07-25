# Charm authoring spec

Hand this file verbatim to anyone (or any agent) transcribing Charms from a page
into `exalted_builder/data/charms/`. It is deliberately mechanical: everything a
transcriber has to *decide* is a bug waiting to happen, so almost nothing is left
to decide.

Validate before handing work back:

```
.venv/bin/python tools/validate_charms.py exalted_builder/data/charms/<your file>.json
```

Zero errors is the bar. Warnings need a one-line justification each, not silence.

---

## 0. The one rule that overrides everything

**This project is Exalted FIRST EDITION. Every value comes from the page in front
of you — never from what you know about Exalted.**

2nd edition is far better represented in training data than 1st, so the default
failure mode is silently "correcting" a 1e value to its 2e equivalent. Do not.

If a value is missing, illegible, or ambiguous on the page:

1. Leave the field at its default (`0`, `""`, `[]`, `null`).
2. Add the id and the missing field to a `_MISSING.md` note beside your output.
3. Report it in your summary.

**Never invent a number. Never infer one from a sibling Charm. Never "fix" one
that looks wrong.** A gap that is reported gets filled by the human in seconds; a
plausible invented number can survive for months. That is the worst outcome
available to you, worse than doing nothing.

Do not read anything in `sources/` (the PDFs). Your source is the text or images
you were given, plus existing files in `data/`.

---

## 1. File and shape

- One file per category: `data/charms/<splat>_<category>.json`, lowercase, e.g.
  `solar_brawl.json`, `sidereal_martial_arts_citrine.json`.
- Top level is a **JSON array** of Charm objects.
- Format with `json.dumps(data, indent=2, ensure_ascii=False)` + trailing newline.
  `ensure_ascii=False` matters: curly quotes, em dashes and `×` stay literal.
- Order Charms as the page's tree diagram reads them: roots first, then each tier.
- Copy `data/charm.example.json` as your starting shape. The authoritative field
  list is `exalted_builder/models/rules.py` (`class Charm`) — read it, do not guess.

## 2. Required fields

```jsonc
{
  "id": "solar.brawl.inevitable-victory-meditation",
  "name": "Inevitable Victory Meditation",
  "category": "brawl",
  "exalt_type": "Solar",
  "type": "Simple",
  "min_ability": 5,
  "min_essence": 2,
  "prerequisites": [["solar.brawl.fists-of-iron-technique"]],
  "cost": { "motes": 3, "willpower": 1, "health": 0, "raw": "3 motes, 1 Willpower" },
  "duration": "Until used",
  "description": "…",
  "source": { "book": "Exalted 1e Cult of the Illuminated", "page": 91 }
}
```

### `id` — hyphens, always
`<splat>.<category>.<charm-name>`, all lowercase, **hyphens between words**.
Strip apostrophes: *Tireless Traveler’s Stamina* → `tireless-travelers-stamina`.

**The separator trap:** ids use `-`, the `category` field uses `_`. So
`"id": "lunar.survival-and-healing.wolf-endurance-method"` with
`"category": "survival_and_healing"`. Mismatched separators are the single most
common transcription error in this project. The validator checks it.

For a Martial Arts style, `category` is `martial_arts:<style-slug>` and the id's
middle segment may be either `martial-arts` (Solar/Abyssal/DB convention) or the
style slug (Sidereal convention). **Match whatever the sibling files for that
splat already do** — do not introduce a third convention.

### `type`
Exactly one of: `Reflexive`, `Supplemental`, `Simple`, `Extra Action`,
`Permanent`, `Special`. Copy the page's `Type:` line. Do not reason about which
type it "should" be — the Sidereal pass found three Charms mistyped `Simple` that
the page prints as `Supplemental`/`Reflexive`.

### `min_ability` / `min_attribute` / `min_essence`
- Ability-keyed Charm (Solar, DB, Abyssal, Sidereal): `min_ability` = the number
  from `Minimum <Ability>: N`. Leave `min_attribute` as `""`.
- Attribute-keyed Charm (Lunar, Alchemical): `min_attribute` = the lowercase
  Attribute **name** (`"dexterity"`), and **`min_ability` = its rating**.

  **`min_attribute` NAMES the trait, `min_ability` RATES it.** The Alchemical
  catalogue once shipped 120 Charms with `min_ability: 0` because the first pass
  captured only the name. Every one of them gated on nothing, and every Array
  priced at 0 XP. Do not repeat this.
- `min_essence` ≥ 1 always. If the page omits it, use 1 and note it.

**A Charm gated on MORE THAN ONE Ability** — the page prints two `Minimum <Ability>:`
lines, e.g. Ascendant Battle Visage's "Minimum Brawl: 5 / Minimum Endurance: 5". Put
the one matching the Charm's `category` in `min_ability`, and every other one in
`extra_min_abilities`:

```jsonc
"category": "brawl",
"min_ability": 5,                                        // Brawl, the primary gate
"extra_min_abilities": [
  { "abilities": ["endurance"], "rating": 5 }            // AND Endurance 5
]
```

Each entry is an independent **AND**, and the `abilities` list inside one entry is an
**OR** — so `[{"abilities": ["melee", "thrown"], "rating": 3}]` means "Melee 3 **or**
Thrown 3". Do not repeat the primary gate here.

Which one is primary matters: the primary gate drives pricing and the Caste/Favored
discount, and the extras are requirement checks only. Put the wrong one first and the
Charm gets mispriced.

### `prerequisites` — AND-of-OR, `list[list[str]]`
Every inner group must be satisfied; a group is satisfied by **any one** id in it.

- `Prerequisite Charms: None` → `[]`
- `Prerequisite Charms: A` → `[["solar.x.a"]]`
- `Prerequisite Charms: A, B` (both needed) → `[["solar.x.a"], ["solar.x.b"]]`
- "A **or** B" → `[["solar.x.a", "solar.x.b"]]`

A comma-separated list on the page means **AND** — one group per Charm. This is
the most consequential thing to get right; converging diagrams look like an OR and
usually are not (the Lunar sorcery chain is drawn as one converging diagram and is
two separate AND groups).

Prerequisites may point **outside** your file (a Charm in another category, or
another splat's tree). Use the real id and let the validator resolve it. Grep for
it — do not construct an id you have not seen:

```
grep -rn '"name": "Hypnotic Tongue Technique"' exalted_builder/data/charms/
```

### `cost`
- `motes`, `willpower`, `health` = the **flat** numeric part only.
- `raw` = the page's cost string verbatim, and it is **authoritative for variable
  costs**. `"Cost: 1 mote per die"` → `{"motes": 0, ..., "raw": "1 mote per die"}`
  — 0, not 1, because there is no flat component.
- `Cost: None` → all zeros, `"raw": "None"`.
- `committed: true` only if the page says the motes stay committed.
- `raw` is a short label, never prose. If it runs past ~80 characters you have
  probably captured description text.

### `duration`
The page's `Duration:` line verbatim: `Instant`, `One scene`, `Permanent`,
`Until used`, `Five turns`, `Indefinite`, `One day`. Long ones are fine when real
(`"Until the character applies Mercury's bridle"`). Sentences are not — that means
the description spilled in.

### `description`
The Charm's full body text, transcribed.

- Paragraph breaks are `\n\n`. Bulleted lists in the source get one `\n\n` per
  bullet, each starting `• `.
- **Do not summarise, tighten, or rewrite.** Transcribe.
- **Stop at the next Charm's title.** Titles are ALL CAPS on the page and bleed
  into the previous description constantly. Do not include the title, the
  following Charm's `Cost:` block, sidebar/box text ("WEAPONS AND ARMOR"), or
  section headings.
- Keep the page's own cross-references (`see Exalted, p. 182`) as printed.
- Do include trailing rules lines that belong to the Charm, e.g.
  "Sidereal Exalted may always use their Temperance with this Charm."
- Include a Martial Arts style's italic sutra fragment if the page prints it above
  the body, as its own first paragraph.

### `source`
`book` = the book you were given, exactly as sibling files in that splat spell it.
`page` = the `<!--PAGE n-->` marker your text sits under, or the page number
printed on the scan. **Always set it.** Every value must be traceable back.

## 3. Fields you almost certainly should not touch

Leave these at their defaults unless your instructions explicitly say otherwise —
each exists for one splat's mechanic and setting one by mistake changes engine
behaviour:

`element`, `immaculate`, `open_to_all`, `open_to_tiers`, `installation_cost`,
(but see `extra_min_abilities` above — that one you DO set when the page prints two
Ability minimums),
`repeatable_cap_ability`, `variants`, `variant_picks_*`, `grants_circle`,
`no_foreign_learning`, `submodules`, `arrayable`, `permanent_install`,
`permanent_clarity`.

If the page describes something that seems to need one of these, **stop and
report it** rather than setting it. It probably needs an engine change too.

## 4. Hand back

1. `.venv/bin/python tools/validate_charms.py <your file>` → 0 errors.
2. A `_MISSING.md` beside the file listing every field you could not fill and why.
3. A summary containing:
   - the count of Charms authored, and the page range,
   - every value you could not read,
   - every prerequisite you could not resolve to an existing id,
   - anything on the page that looked like a **new mechanic** rather than a Charm.

Do not run the test suite, edit any file outside `data/charms/`, or touch
`CLAUDE.md`. Reporting an unresolved question is a successful outcome.
