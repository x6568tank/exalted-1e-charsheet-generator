# Working with the rules data

How the JSON under `exalted_builder/data/` is organised, and the conventions that make a
new row load instead of being rejected.

**This file does not list fields.** The authoritative, field-level truth is the pydantic
models in `exalted_builder/models/rules.py` — read them, or copy a working row out of
`data/charm.example.json` (annotated) or `data/armor.json`. A hand-written schema table
here would drift the first time a field is added, and then there would be two answers.

| I want to… | Read |
|---|---|
| know a field's name, type or default | `models/rules.py` |
| see a minimal working row | `data/charm.example.json` |
| transcribe Charms from a book page | `tools/CHARM_AUTHORING_SPEC.md` |
| check a file before committing it | `tools/validate_charms.py` |
| understand where the data sits in the app | `docs/ARCHITECTURE.md` |
| add *my own* content, not book content | the app's **Custom** tab; `docs/status/custom-content.md` |

## The files

```
data/
    charms/*.json        Charms, split per ability and splat. The FILENAME CARRIES NO
                         MEANING — `category` and `exalt_type` do. Split for the
                         maintainer's benefit only
    spells.json          Sorcery, necromancy and Alchemical weaving protocols, all keyed
                         by `circle`
    castes.json          Castes / Aspects / Maiden castes, with anima powers
    exalts.json          One row per splat: its tier, caste noun, Essence formula
    chargen_budgets.json ┐ keyed by exalt type with a "default" row; the `*_for()`
    costs_bonus.json     │ accessors fall back to "default". Per-origin and
    costs_xp.json        ┘ per-upbringing rows override further
    backgrounds.json     Catalogue for autofill, plus per-splat availability
    weapons.json         ┐
    armor.json           │ catalogues for autofill; characters carry inline copies
    materials.json       ┘
    natures.json         The p105 Nature archetypes
    colleges.json        Astrological Colleges (Sidereal)
    camps.json           ┐ Cult of the Illuminated training camps and their Callings
    callings.json        ┘
    thaumaturgy/         arts, sciences, rituals, formulas — cross-splat
    st_screen.json       Static Storyteller reference tables; pure display
```

Every file except `castes.json` is optional as far as the loader is concerned: absent
means "this data set has none of that", and the cost/budget tables fall back to the model
defaults. That is what lets tests run against a three-Charm data set.

## Ids

* **Stable, namespaced, lowercase, hyphenated**:
  `solar.melee.fire-and-stones-strike`, `abyssal.occult.shadowlands-circle-necromancy`.
* The convention is `<splat>.<category>.<name-slug>`, but nothing parses it — it only has
  to be unique and stable. `category` and `exalt_type` are what the engine reads.
* **Renaming is free; changing an id is a migration.** Characters store ids, so a changed
  id silently orphans every character that owned it.
* Duplicate ids are a load error, reported with every other problem in one raise.
* `custom.` is **reserved** for the user's homebrew. Never use it in `data/`.

## Charms

**`category`** is one of:

* an `AbilityName` value — `melee`, `occult`, `martial_arts`, …
* `"sorcery"` — no gating Ability
* a Martial Arts style, written **`martial_arts:<slug>`** — e.g. `martial_arts:tiger`.
  The picker derives its style groups from this string, so **a new style needs no schema
  change and no code**: pick a slug nobody has used and it becomes its own tree.
* for splats that group by element (Dragon-Blooded), `element` is a *separate* field —
  the category stays the ability or style.

**Prerequisites are AND-of-OR** — `list[list[str]]`. Every inner group must be satisfied;
any one id inside a group satisfies it.

```jsonc
"prerequisites": [["a"], ["b"]]        // needs BOTH a and b
"prerequisites": [["a", "b"]]          // needs EITHER a or b
"prerequisites": [["a"], ["b", "c"]]   // needs a, AND (b or c)
```

A **breadth** requirement — "any three Lore Charms" — cannot be written this way (three
groups each listing all eleven Lore Charms would be satisfied three times over by one
owned Charm). It goes in `prerequisite_counts` as a count over a category.

**Trait minimums come in three flavours**, and only the first affects price:

1. `min_ability` — the primary gate, resolved through `category`. Pricing and the
   Caste/Favoured discount key off this one. For Attribute-keyed splats, `min_attribute`
   *retargets* it at an Attribute.
2. `extra_min_abilities` — additional Ability minimums, ANDed, each an OR over its own
   list. (Ascendant Battle Visage: Brawl 5 **and** Endurance 5.)
3. `extra_min_attributes` — the same over Attributes. No printed 1e Charm uses it; it
   exists for homebrew.

**Costs.** `cost.raw` is the display string and is authoritative for anything variable
("1 mote per die"); the numeric fields are what the engine reads. Author both when the
page prints a fixed cost, and lean on `raw` when it does not.

**Circle initiation.** A Charm that unlocks a spell circle sets `grants_circle`. The
loader refuses any spell whose circle no Charm grants — an unreachable spell would be
unlearnable, so this catches a whole class of transcription error at load.

## Splat-keyed tables

`chargen_budgets.json`, `costs_bonus.json` and `costs_xp.json` are maps keyed by exalt
type, always including a `"default"` row:

```jsonc
{
  "default":  { "bonus_points": 15 },
  "Abyssal":  { "bonus_points": 21 }
}
```

Read them through `RuleSet.budgets_for(...)` / `bonus_costs_for(...)` /
`xp_costs_for(...)`, **never by subscripting** — the accessors implement the fallback, and
a row may specialise further by origin and then by upbringing. The key is
`<ExaltType>[:<origin>[:<upbringing>]]`, most specific wins:

```jsonc
{
  "default":                               { "background": 1, "background_above_3": 2 },
  "Dragon-Blooded":                        { "background": 1, "background_above_3": 2 },
  "Dragon-Blooded:lost-egg":               { "background": 2, "background_above_3": 3 },
  "Dragon-Blooded:forest-witch:oreithyia": { "virtue": 2, "essence": 8 }
}
```

So `bonus_costs_for("Dragon-Blooded", origin="lost-egg")` gives 2/3 per Background dot
where the plain Dragon-Blooded row gives 1/2. Pass the axes as arguments — hand-building
the key, or passing an origin on the wrong axis, silently falls back to the general row
and the difference is invisible.

Anything a splat does not state falls back to the Solar baseline, which is usually right
and occasionally is not: check the page.

## What the loader checks

`rules_db.load_ruleset` **accumulates every problem and raises them together**, so a
freshly transcribed file is fixed in one pass rather than one error per run. It verifies:

* every Charm id and spell id is unique
* every prerequisite id resolves
* every spell's circle is granted by some Charm
* camps and Callings point at Charms that exist
* thaumaturgic aspect ids are globally unique, and formulas belong to a real Science
  whose `max_rating` they do not exceed

A `RuleDataError` lists the lot. **Book data errors are fatal** — the app will not start
on them, deliberately. (Homebrew is the opposite: see
`docs/decisions/0012-homebrew-library-plus-carried-copies.md`.)

## Adding printed content: the loop

1. Get the page into `images/<Splat>/` — a PNG, or `.md` text the maintainer pasted out
   of a text-selectable book. **Never transcribe from memory, and never read the PDFs in
   `sources/`.** See `CLAUDE.md`.
2. Write the rows, following `tools/CHARM_AUTHORING_SPEC.md`. Leave anything the page does
   not state at its default and note the omission rather than filling it in.
3. `.venv/bin/python tools/validate_charms.py <your file>` — zero errors is the bar;
   warnings need a one-line justification each.
4. `.venv/bin/python -m pytest` — the loader's link-checking runs against the real data
   set, so a dangling prerequisite fails here.
5. Record what landed in `docs/status/<topic>.md`, with page numbers.

If a value is missing, illegible or ambiguous on the page: **stop and ask.** A 2e value
will feel right and be wrong — that is decision
`docs/decisions/0001-first-edition-only.md`, and it is the most common way this data set
could get worse.
