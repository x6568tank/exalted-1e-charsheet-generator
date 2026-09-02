# Trait reference text — Attributes, Abilities, Virtues

**Shipped 2026-09-02.** The core rulebook's Chapter Four prose for the three rated trait
families, behind an ⓘ beside every dot row in both shells. Display-only: no engine module
reads it, and the file is optional.

## What the book actually prints — the shape trap

The three families do **NOT** have the same shape, and assuming they do is the way to get
this wrong:

| Family | Per-trait ladder? | Also prints |
|---|---|---|
| **Attributes** (pp.127-128) | **Yes** — 1-5, labelled Poor / Average / Good / Exceptional / Superb, each rung concrete ("●●● Good: Doughty laborer, dead lift 200 lbs.") | — |
| **Abilities** (pp.132-140) | **No.** ⚠ There is no per-Ability ladder in 1e. The rungs are **generic and shared** (Unskilled / Novice / Practiced / Competent / Expert / Master, p.132) | sample **specialties** + three **example feats**: Standard = 1 success, Challenging = 3, Legendary = 5 |
| **Virtues** (pp.129-130) | **Yes** — 1-5, but **unlabelled**: bare prose per dot | "**Virtue** aids in" and "Characters must fail a **Virtue** check to" |

The Ability ladder is the one that starts at **0** ("Unskilled", −2 dice) — Attributes and
Virtues have no rung 0.

⚠ **Backgrounds are NOT here.** Their descriptions already live in the Background
catalogue (`data/backgrounds.json`); a second copy would rot.

## Where it lives

- `exalted_builder/data/trait_descriptions.json` — one **object**, not three arrays, so
  the shared `ability_ladder` has a home that belongs to no single Ability.
- `models/rules.py` — `TraitDescriptions` (+ `AttributeDescription`,
  `AbilityDescription`, `VirtueDescription`), and `RuleSet.trait_descriptions`, optional.
- `rules_db.py` — `_load_object`, plus **`_check_trait_descriptions`**: every member of the
  three closed enums must have exactly one row. That check is the point. The text is
  display-only, so a missing Attribute would show as one empty panel out of nine and
  produce no error, no failing test and no symptom a player could name. Coverage is
  checkable because the vocabularies are enums, so it is checked.
- `ui/view.py` — `attribute_info` / `ability_info` / `virtue_info` → a `TraitInfo`
  (description, ladder rows flagged with the character's own rung, ordered sections).
  **Both shells render this and only this**, so they cannot drift into describing a trait
  differently.
- `ui/catalogue.py: trait_reference_dialog` and `qt/editor.py: _build_trait_dialog` — the
  two renderers. `ui/editor.py: trait_info_button` and `qt/editor.py: _info_button` place
  the ⓘ; both call the presenter **twice** — once at build to decide whether the button
  exists at all, once on click so the highlighted rung is the rating at click time.

38 ⓘ buttons per shell (9 + 25 + 4), asserted in both.

## Source

`images/_extracted/Exalted Core.md`, lines ~9320-10520 — the human ruled on 2026-09-02
that the extractor's output counts as vetted for this. Two extraction hazards were live in
that range and both are handled in the authored file:

- **The +1 cipher.** Italic/bold runs are shifted one character up: `Fxample9` = "Example:",
  `Dompassion` = "Compassion", `Specialties9` = "Specialties:". Decode by −1.
- **⚠ The `�` glyph is ambiguous and I resolved it by reading.** It is the fallback for
  every non-Latin1 glyph, so it stands for the dot bullet, the em-dash AND the colon
  (ASCII survives extraction intact, which is why it is never a semicolon). "the Ability�
  the character is a dabbler" is an em-dash; "the following language families exist�" must
  be a colon. **Nothing verified those calls against the page** — they are cosmetic, but
  they are mine, not the book's.
- Two pages interleave columns (139/140): **Bureaucracy** and **Sail** each have their
  body split around the other's heading. Both are reassembled.

Typos preserved from the page rather than silently fixed: Archery's "apple off someone's
**heat**", Larceny's run-together "FencingStolen Goods" (spaced, since it is a list item),
Presence's "into **an** highly motivated unit".
