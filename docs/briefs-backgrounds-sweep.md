# Delegated authoring brief — the Backgrounds sweep

Two independent jobs. **Part 1** fills in Background text; **Part 2** decides which
splat may take which. They touch different files and can be done in either order.

> **Edition: Exalted FIRST edition (1e) only.** 2e is far better represented in
> training data, and the default failure mode is silently "correcting" a 1e value to
> its 2e equivalent. Do not. If a value is not on a page you were given, **leave the
> field out and list the entry as blocked** — never supply one from memory.
>
> Read only the files named below. Do **not** read the PDFs in `sources/`.

---

# Part 1 — descriptions and dot ladders

**Target file:** `exalted_builder/data/backgrounds.json` — 46 entries, **11 already
done, 35 to go.**

For each remaining Background, two things:

1. **`description`** — the full printed prose, condensed only where the book repeats
   itself. Several entries are stubs (Cult is 46 characters, Contacts 61, Resources
   70) while Class runs to 968. They should all read at full length.
2. **`ladder`** — the printed dot-by-dot ladder, **exactly six strings**, indexed by
   rating: `ladder[0]` is the book's `x` row, `ladder[1..5]` the five dots. Six
   entries, or omit the field entirely — **a partial ladder is rejected at load**,
   because the sheet indexes it by rating and four rungs would print the *wrong* text
   for a rating rather than no text.

**Do not invent a ladder for a Background whose page prints none.** Omit the field.

## Already done — do not touch these 11

`Acquaintances`, `Allies`, `Arsenal`, `Celestial Manse` (Sidereal), `Connections`
(Sidereal), `Followers`, `Retainers`, `Salary` (Sidereal), `Savant` (Sidereal),
`Sifu`, `Sorcery`.

⚠ `Celestial Manse`, `Salary`, `Savant` and `Connections` each exist **twice** — once
for the Sidereals and once for the Dragon-Kings or Dragon-Blooded, with different
printed rules. The Sidereal copies are done; **the other copies still need doing.**
Match on `id`, never on `name`.

## The 35 remaining

`Abyssal Command`, `Ancestor Cult`, `Artifact`, `Backing`, `Breeding`,
`Celestial Manse` (DK), `Class`, `Command`, `Connections` (DB), `Contacts`, `Cult`,
`Familiar`, `Family`, `Grave Goods`, `Heart's Blood`, `Henchmen`, `Influence`,
`Inheritance`, `Liege`, `Manse`, `Mentor`, `Necromancy`, `Patron`, `Renown`,
`Reputation`, `Resources`, `Salary` (DK), `Savant` (DK), `Spies`, `Underworld Cult`,
`Underworld Manse`, `Vats`, `Whispers`, `Illumination`, `Tiger Warriors`.

`Illumination` and `Tiger Warriors` are new stubs carrying only the one-line
description from the Cult of the Illuminated chargen summary; their full text and
ladders are in that book.

## Worked examples — match this shape exactly

```json
{
  "id": "background.allies",
  "name": "Allies",
  "description": "Aides and friends who help you in tasks — close, capable companions; each Ally is a Storyteller character.",
  "ladder": [
    "None — your character skulks about, having no one close to turn to.",
    "One ally of moderate ability (equivalent to a starting character).",
    "Two allies or one significant one.",
    "Three allies or fewer allies of correspondingly high power.",
    "Four allies or fewer ones of great capability.",
    "Five allies or fewer ones of immense power."
  ]
}
```

```json
{
  "id": "background.followers",
  "name": "Followers",
  "description": "Mortals who look to you for leadership, rated by their number and devotion.",
  "ladder": [
    "None — you haven't inspired anyone to rally to your banner.",
    "One follower of average capability (equivalent to a typical extra).",
    "Three followers.",
    "Seven followers.",
    "25 followers.",
    "100 loyal followers."
  ],
  "excluded_exalt_types": ["Dragon-Blooded"]
}
```

Both were transcribed from `images/_extracted/Exalted Core.md`, the `ALLIES` and
`FOLLOWERS` sections. **Keep every other field byte-identical** — `id`, `name`,
`exalt_type`, `universal`, `excluded_exalt_types`, `excluded_origins`. You are adding
`ladder` and rewriting `description`, nothing else.

## Where each Background is printed

| Source | Backgrounds |
|---|---|
| `images/_extracted/Exalted Core.md` — Chapter Four's Backgrounds section (search for the line `Backgrounds are Traits that do not measure your`; it runs to the `W ILLPOWER` heading, book pp.141-148) | Artifact, Backing, Contacts, Familiar, Influence, Manse, Mentor, Resources — **all with full ladders** |
| `images/_extracted/Games of Divinity.md` | Cult |
| `images/Dragonblooded/Traits/…p158 - 159.png` and `…p160 - 161.png` | Breeding, Command, Connections (DB), Henchmen, Reputation, Family (the optional sidebar, p.159) |
| `images/Abyssals/` — Traits chapter | Abyssal Command, Liege, Necromancy, Spies, Underworld Manse, Whispers, Ancestor Cult, Grave Goods, Underworld Cult |
| `images/Lunars/` — Traits chapter | Heart's Blood, Renown |
| `images/_extracted/Autochthonians.md` | Class, Vats |
| `images/_extracted/Player's Guide.md` | Inheritance, Patron, and the **Dragon-King** copies of Celestial Manse, Salary and Savant (p.176) |

The Dragon-King copies of Celestial Manse / Salary / Savant cross-reference the
Sidereal book but carry their own cap ("may not exceed two dots even if bonus points
are used"). Keep that; do not paste the Sidereal text over them.

## ⚠ The glyph problem in the extracted `.md` files

The extracted files came from ciphered PDFs and one glyph did not resolve: **`�`
stands for both the bullet `•` and for curly quotes and dashes.** Inside a ladder it
is always a bullet, and the RATING is the *count* of them:

```
�� Two allies or one significant one.                 →  ladder[2]
���� Four allies or fewer ones of great capability.   →  ladder[4]
```

In prose it is a quote or a dash — read it from context and write the right character.
**If a passage is too garbled to read without heavy interpretation, mark it and skip
that entry.** Never author a value out of a marked passage.

---

# Part 2 — the per-splat catalogue lists

**Mostly DONE.** `images/core backgrounds/` turned out to hold each splat's printed
BACKGROUNDS block, and Claude transcribed all ten. The following rows are authored and
must not be touched:

`Solar`, `Solar:illuminated`, `Dragon-Blooded`, `Dragon-Blooded:lookshy`, `Abyssal`,
`Lunar`, `Sidereal`, `Sidereal:ronin`, `Alchemical`, `Ghost`.

## What is left

Four splats have no image and no transcribed list. They fall back to the older
per-Background `exalt_type` filter, which is safe but wrong in detail:

| Row key | Source |
|---|---|
| `Mortal`, `Mortal:ordinary` | `images/_extracted/Exalted Core.md`, p.103 |
| `God-Blooded` | `images/Non-Exalts/Godblooded/CH2 - Godblooded.md` |
| `Dragon-Kings`, `Dragon-Kings:ancient` | `images/_extracted/Player's Guide.md` |
| `Mountain-Folk:enlightened`, `Mountain-Folk:unenlightened` | Mountain Folk CH6 |

Also open, and needing pages rather than guesses:

* **`Abyssal:fugitive`** — the base Abyssal list includes `Liege` ("your relationship
  with your Deathlord"), which a renegade plainly cannot hold, and the fugitive origin
  uses the core Artifact Background rather than the Abyssal one. Its own list is not
  transcribed.
* **Alchemical exile characters** — the printed list marks `Followers` and `Resources`
  "(Exile characters only)" and restricts `Manse` to stories set after the breaking of
  the Seal of Eight Divinities. There is no exile origin row to hang that on, so the
  base list currently carries all three unqualified.

## Format

Lowercased names, matching `name` in `backgrounds.json` exactly. Worked examples:

```json
"Ghost":     { "catalogue_backgrounds": ["ancestor cult","artifact","allies","backing","contacts","followers","grave goods","influence","mentor","resources","underworld cult"] },
"Alchemical":{ "catalogue_backgrounds": ["allies","artifact","backing","class","contacts","familiar","followers","manse","resources","vats"] }
```

## Where the list lives in a book

Two shapes:

* **The chargen summary enumerates it** under a `BACKGROUNDS` heading — every splat in
  `images/core backgrounds/` does this. Use it directly.
* **The summary gives only a dot count** ("Choose Backgrounds (12 — none may be higher
  than 3…)"). Then the list is the **Traits chapter's Backgrounds section**, which runs
  as `ALTERED BACKGROUNDS` then `NEW BACKGROUNDS`: the core ten, minus the altered
  section's bars, plus the new ones.

⚠ **Read the ALTERED section carefully** — its bars are how a splat *loses* a core
Background, and they are easy to miss. E:DB pp.156-157: "Dragon-Blooded characters do
not use these Backgrounds [Contacts and Influence]" and "Dragon-Blooded cannot take the
Followers Background."

## Rules

1. **Only author a row you have a page for.** A row with no list falls back and behaves
   as it does today. Leaving a splat out is safe; guessing is not.
2. **Do not remove or rename any other key** in `chargen_budgets.json`.
3. **Never confuse `catalogue_backgrounds` with `allowed_backgrounds`.** The second is
   a HARD list that makes any unlisted Background an **error**, and only two rows carry
   it (`Sidereal:ronin`, `Solar:illuminated`). Writing your list there makes every
   free-text Background illegal for that splat. Where a row has both, the offered list
   must be a SUBSET of the allowed one — a test enforces it.
4. **Do not orphan a Background.** A test fails if any entry ends up with no
   `exalt_type`, no `universal` flag and no list naming it: it would be offered to
   nobody. If your reading leaves one in that state, report it.
5. `universal` entries (currently just Cult) are offered to every splat automatically.
   A splat book MAY also list one — the Lunar summary lists Cult — and that is fine;
   the two are independent. Include it in the list if the page prints it.
6. Return a blocked list for any splat whose pages you could not find or read.

## Validation

```
.venv/bin/python -m pytest tests/test_backgrounds_splat.py -q
```

---

# Handing the work back

Return the edited file(s), plus a **blocked list**: every entry or row you could not
complete, and why — "no ladder printed", "source page not on disk", "passage garbled".
A short honest blocked list is the most useful part of the output. **Do not fill a gap
to make the list shorter.**

```
.venv/bin/python -m pytest tests/test_backgrounds_splat.py tests/test_content.py -q
```
