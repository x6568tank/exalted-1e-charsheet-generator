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

**Target file:** `exalted_builder/data/backgrounds.json` — 44 entries, **11 already
done, 33 to go.**

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

## The 33 remaining

`Abyssal Command`, `Ancestor Cult`, `Artifact`, `Backing`, `Breeding`,
`Celestial Manse` (DK), `Class`, `Command`, `Connections` (DB), `Contacts`, `Cult`,
`Familiar`, `Family`, `Grave Goods`, `Heart's Blood`, `Henchmen`, `Influence`,
`Inheritance`, `Liege`, `Manse`, `Mentor`, `Necromancy`, `Patron`, `Renown`,
`Reputation`, `Resources`, `Salary` (DK), `Savant` (DK), `Spies`, `Underworld Cult`,
`Underworld Manse`, `Vats`, `Whispers`.

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

**Target file:** `exalted_builder/data/chargen_budgets.json`, the
`catalogue_backgrounds` field on each splat's row.

Each book enumerates the Backgrounds its splat may take, and that list decides what
the dropdown offers. Four rows are authored already and are your worked examples:

```json
"Solar":                  { "catalogue_backgrounds": ["allies","artifact","backing","contacts","familiar","followers","influence","manse","mentor","resources"] },
"Dragon-Blooded":         { "catalogue_backgrounds": ["allies","artifact","backing","familiar","manse","mentor","resources","breeding","command","connections","henchmen","reputation","family"] },
"Dragon-Blooded:lookshy": { "catalogue_backgrounds": ["allies","arsenal","artifact","backing","breeding","command","connections","familiar","manse","mentor","reputation","resources","retainers","sorcery","family"] },
"Ghost":                  { "catalogue_backgrounds": ["ancestor cult","artifact","allies","backing","contacts","followers","grave goods","influence","mentor","resources","underworld cult"] }
```

Lowercased names, matching `name` in `backgrounds.json` exactly.

## Where the list lives in a book

Two shapes, both already seen:

* **The chargen summary enumerates it.** Ghosts CH3 has a `### BACKGROUNDS` heading
  listing eleven; The Outcaste CH1 has one listing fifteen. Use it directly.
* **The chargen summary gives only a dot count** — "Choose Backgrounds (12 — none may
  be higher than 3…)", which is what Solar core p.94 and E:DB p.151 both do. Then the
  list is the **Traits chapter's Backgrounds section**, which runs as
  `ALTERED BACKGROUNDS` followed by `NEW BACKGROUNDS`. The splat's list is: the core
  ten, minus the altered section's bars, plus the new ones.

⚠ **Read the ALTERED section carefully** — its bars are easy to miss and they are how
a splat *loses* a core Background. Worked example, E:DB pp.156-157: "Dragon-Blooded
characters do not use these Backgrounds [Contacts and Influence]. Instead, they use
Connections", and "Dragon-Blooded cannot take the Followers Background." All three are
absent from the Dragon-Blooded list above for exactly that reason.

## Rows still needing a list

| Row key | Source |
|---|---|
| `Abyssal`, `Abyssal:fugitive` | `images/Abyssals/` — Traits chapter |
| `Lunar`, `Lunar:casteless` | `images/Lunars/` — Traits chapter |
| `Alchemical` | `images/_extracted/Autochthonians.md` |
| `Mortal`, `Mortal:ordinary` | `images/_extracted/Exalted Core.md`, p.103 |
| `God-Blooded` | `images/Non-Exalts/Godblooded/CH2 - Godblooded.md` |
| `Dragon-Kings`, `Dragon-Kings:ancient` | `images/_extracted/Player's Guide.md` |
| `Mountain-Folk:enlightened`, `Mountain-Folk:unenlightened` | Mountain Folk CH6 |

**`Sidereal` is already decided** — author it verbatim as:

```json
["acquaintances","allies","artifact","backing","celestial manse","connections","familiar","manse","resources","salary","savant","sifu"]
```

(Sidereals p.105's ALTERED BACKGROUNDS bars Contacts, Influence, Followers and Mentor
by name. Resources is ronin-only in practice but stays on the list.)

## Rules

1. **Only author a row you have a page for.** A row with no list falls back to the
   older per-Background filter and behaves exactly as it does today. Leaving a splat
   out is safe; guessing is not.
2. **Do not remove or rename any other key** in `chargen_budgets.json`.
3. **Never confuse `catalogue_backgrounds` with `allowed_backgrounds`.** The second is
   a HARD validation list that makes any unlisted Background an **error**, and only
   two rows should ever carry it (`Sidereal:ronin`, `Solar:illuminated`). Writing your
   list into that field makes every free-text Background illegal for that splat.
4. Return a blocked list for any splat whose pages you could not find or read.

## ⚠ Universal Backgrounds — do not put these in any splat list

Some Backgrounds belong to no splat in particular. **Cult** is the case: it is printed
in Games of Divinity, which is not a splat book, so no character-creation summary
anywhere names it. These carry `"universal": true` in `backgrounds.json` and are
offered to every splat automatically.

**If a splat's book turns out to enumerate `Cult` — or anything else already marked
`universal` — do not add it to that splat's `catalogue_backgrounds`. Report it in your
blocked list instead.** Adding it would make that Background splat-specific and strip
it from every other splat. A test checks this and will go red.

The same test also fails if a Background ends up belonging to **nobody**: no
`exalt_type` tag, `universal` not set, and no splat list naming it. If your reading
leaves an entry in that state, say so rather than guessing which splat owns it.

---

# Handing the work back

Return the two edited files, plus a **blocked list**: every entry or row you could not
complete, and why — "no ladder printed", "source page not on disk", "passage garbled",
"book lists a universal Background". A short honest blocked list is the most useful
part of the output. **Do not fill a gap to make the list shorter.**

Both files must load and both suites must pass:

```
.venv/bin/python -m pytest tests/test_backgrounds_splat.py tests/test_content.py -q
```
