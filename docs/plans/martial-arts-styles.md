# Plan — the martial-arts STYLE entity

**Status:** **Phase 1 SHIPPED 2026-08-14** (model, loader, link check, picker panel,
4 of 22 styles), suite 2,420, **not browser-verified**. Phase 2 — the remaining 18
preambles — is open. What actually shipped and the traps it produced are in
**`docs/status/martial-arts-styles.md`**; read that first, this is the plan it was
built from. Closes the modelling half of open TODO 2 in `CLAUDE.md`.

## The problem

Charm categories are bare strings (`martial_arts:<slug>`). **22 styles** have their
Charms and nowhere to put their PREAMBLE — the style-level text that sits above the
Charm list on the page. Some of it is pure flavour; some of it is mechanical and is
currently lost:

- **Jade Mountain** (Aspect Book: Earth p.71) — non-Earth Aspects pay a 1-mote
  elemental surcharge; the style fails unless the Exalt touches the ground; Charms
  may be used freely with armour and treat one-handed crushing weapons as unarmed.
  The worked example, recorded in `docs/status/dragonblooded-aspect-books.md`.
- Falling Blossom's, the five Immaculate Dragon styles', the Sidereal styles'.

Every style preamble authored so far has been dropped on the floor for want of a
place to put it.

## What the pages carry that the build does not

Each style prints a **`Type:` line** naming its tier — verified on Righteous Devil
(Player's Guide p.254: `RIGHTEOUS DEVIL STYLE / Type: Celestial`). The build has
never stored it. Today the tier is *implied*, per-Charm, by `open_to_tiers`.

## Decisions (human, 2026-08-14)

| # | Decision |
|---|---|
| 1 | **The style owns its preamble and `Type:` and NOTHING ELSE.** Per-Charm access fields — `open_to_all`, `open_to_tiers`, `restricted_to`, `immaculate` — stay exactly where they are on the Charms. |
| 2 | **Content is sequenced model-first.** Phase 1 ships the model, loader, link check and UI with the 4 styles whose text is already cleanly readable (all Player's Guide). Phase 2 authors the other 18 by book. |
| 3 | **Righteous Devil's odd Charm is CORRECT AS PRINTED.** See below. |

### ⚠ Decision 1 has a corollary that must not be lost

**`MartialArtsStyle.tier` is DISPLAY ONLY in Phase 1.** Nothing in `engine/` may
read it. The style's `Type:` line and the Charms' `open_to_tiers` are two
descriptions of one fact, and wiring the new one into access while the old one is
still authoritative is how you get two implementations that disagree — the exact
shape `docs/decisions/` 0011 exists to prevent, and the reason the Edit/XP merge
happened. A test asserts no engine module imports or reads the style catalogue.

If the styles should later own access, that is a deliberate follow-up with a
migration, not a drive-by.

## ⚠ Righteous Devil Style — a documented exception, not a bug

11 of its 12 Charms carry `open_to_tiers: ["Celestial"]`; **Blessing of Righteous
Solar Spark Meditation** (PG p.255) does not, so a Lunar or Sidereal may learn the
style but not that Charm.

**The human ruled this CORRECT AS PRINTED (2026-08-14): the Charm's own text names
the Solar Exalted, so it is genuinely narrower than its style.** It is recorded here
and beside the data because a bare inconsistency looks like an authoring slip
forever — the next person to run a consistency check will "fix" it otherwise.

The style-consistency test therefore ships **with exactly one documented exception**,
and the test asserts the exception set is exactly that one Charm — so a second
divergence appearing anywhere fails loudly instead of joining a growing allowlist.

## Model

```python
class MartialArtsStyle(BaseModel):
    id: str                     # "style.righteous-devil"
    name: str                   # "Righteous Devil Style", as printed
    category: str               # "martial_arts:righteous-devil" — the link to Charms
    tier: str                   # the printed `Type:` word. DISPLAY ONLY (see above)
    preamble: str               # the style's prose, as printed
    mechanics: list[str]        # style-level RULES, one per printed rule; [] for
                                # the many styles whose preamble is pure flavour
    source: Source
```

`tier` is a plain `str`, not an enum: it is a printed word, and inventing the
allowed set from memory is precisely what decision 0001 forbids. The values seen so
far are "Terrestrial", "Celestial" and (expected) "Sidereal" — but that is an
observation about four pages read, not a closed list.

`mechanics` is separate from `preamble` because Jade Mountain's three rules are
things a Storyteller needs to find, not prose to read past.

## Data, loader, link-checking

- `exalted_builder/data/martial_arts_styles.json`, loaded exactly like
  `artifacts.json` / `colleges.json` — `_index(_load_array(...), "id", "style", …)`
  into `RuleSet.martial_arts_styles`.
- **Load-time link check, both directions:**
  - every style's `category` is used by at least one Charm (a style with no Charms
    is a typo in the slug);
  - every `martial_arts:*` category used by a printed Charm has a style — reported
    as a `problem`, not raised.
- **⚠ Custom styles must not trip it.** `custom_content.py:118` mints
  `martial_arts:<slug>` for user-authored styles at runtime, and decision 0012 says
  homebrew errors are non-fatal. The check skips categories whose Charms are all
  custom.

## UI

- **The picker's Martial Arts page** (`ui/picker.py`, `_group_of` → `"styles"`) —
  the preamble at the head of the selected style's tree, with `mechanics` as a short
  list beneath it. This is where a player choosing Charms needs it.
- **The Charm detail card** names the style rather than printing the raw category.
- **NOT the PDF.** Charms print as names and costs only
  (`docs/status/printable-sheet.md`); a style preamble is rules text.
- **Not the sheet in Phase 1.** Whether a character's sheet should carry the
  preambles of styles she has Charms in is a real question and a separate one.

## Tests

1. **Link check, both directions** — style→Charms and Charms→style, with the
   custom-style exemption exercised (a homebrew style must load clean).
2. **Style consistency** — every Charm in a style agrees on `open_to_all`,
   `open_to_tiers`, `restricted_to` and `immaculate`, with the single documented
   Righteous Devil exception, and the exception set asserted to be exactly that.
   This is the test that would have caught the divergence that started this job.
3. **⚠ Phase-1 boundary** — no module under `engine/` reads `martial_arts_styles`.
   Pins decision 1's corollary; fails loudly if someone wires `tier` into access.
4. **Source fidelity** — each authored preamble matches its page text, in the
   manner of `test_every_description_matches_the_source_text`.
5. **UI render** — the preamble appears on the Martial Arts page for a style, and
   (negative control) does not appear before the style is selected.

## Phasing

**Phase 1 — model + plumbing + 4 styles.** Celestial Monkey (PG 246-249), Crimson
Pentacle Blade (PG 241-246), Dreaming Pearl Courtesan (PG 250-253), Righteous Devil
(PG 254-258). All four are in `images/_extracted/Player's Guide.md`, already
extracted and clean, with `Type:` lines intact.

**Phase 2 — the remaining 18, by book.** Every source is in `sources/`; per the
2026-08-13 authorisation, pure scans are rasterised with `pdftoppm` and read
directly.

| Book | Styles | Pages |
|---|---|---|
| Exalted 1e Dragon-Blooded | Air/Earth/Fire/Water/Wood Dragon, Five-Dragon, Enlightenment | 197-263 |
| Exalted 1e The Sidereals | Charcoal March of Spiders, Citrine Poxes, Prismatic Arrangement, Violet Bier | 179-201 |
| Castebooks (Night / Eclipse / Dawn) | Ebon Shadow, Praying Mantis, Tiger | 67-75 |
| Cult of the Illuminated | Falling Blossom | 103-104 |
| Aspect Book: Earth | Jade Mountain | 71 |
| Exalted: The Abyssals | Hungry Ghost | 162-165 |
| Core | Snake | 160-162 |

⚠ **Enlightenment is not a style** — `martial_arts:enlightenment` is the Dragon-Path
initiation tree (`ui/picker.py` says so explicitly). It gets an entry only if the
page gives it a preamble of its own; otherwise it is a documented absence, and the
link check needs to know that.

## What this plan does NOT do

- It does not move any access rule. Learning, pricing and barring are untouched.
- It does not change any Charm.
- It does not put style text on the sheet or in the PDF.
