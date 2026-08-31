# Status detail — Data authored & Tooling

Referenced from `CLAUDE.md` → Status.

## Data authored
- Core: `castes.json`, `backgrounds.json`, `armor.json` (19), `weapons.json` (79),
  `spells.json` (**88**, across all three magic tracks — 27 sorcery, 23 necromancy,
  38 Alchemical weaving protocols), `natures.json` (20 Archetypes), `materials.json`
  (5 magical materials, Exalt-gated weapon/armor bonuses, p341/p345-346),
  `colleges.json` (25 Sidereal Astrological Colleges), `camps.json` + `callings.json`
  (Cult of the Illuminated), `st_screen.json` (the GM reference screen).
- Charms — **1,378 across six splats; every implemented splat has a complete
  catalogue.** Counts are `Counter(c.exalt_type for c in rs.charms.values())`:
  - **Solar: 381** — 222 corebook across every ability, 20 from Cult of the Illuminated
    (incl. Falling Blossom Style, and the 5 castebook Charms that book reprints) and
    **139 from the five castebooks** (incl. Tiger, Praying Mantis and Ebon Shadow
    Style; see `solar-castebooks.md`).
  - **Dragon-Blooded: 233** — 164 per-element (Air/Earth/Fire/Water/Wood) ability-tree
    charms, 59 Immaculate style-tree charms, 8 Five-Dragon Style, Ox-Body.
  - **Abyssal: 233** across every ability, incl. Hungry Ghost Style, sorcery +
    necromancy initiations, Ox-Body.
  - **Lunar: 217** — Attribute-keyed, incl. Deadly Beastman Transformation's Gifts.
  - **Sidereal: 193** — 24 ability trees, Violet Bier of Sorrows, and 3 Celestial-open
    Sidereal Martial Arts styles.
  - **Alchemical: 121** — Attribute-keyed, Charm-Slot installed, many with submodules.
- **Cross-splat Martial Arts:** Hungry Ghost Style and Five-Dragon Style are
  `open_to_tiers: [Celestial]`, so every Celestial splat gets them for free — which is
  how Lunars and Sidereals picked them up with no data or code change when those splats
  landed. The mechanism is proven; a future Celestial splat needs nothing.

## Tooling
- **`tools/validate_charms.py`** — lints Charm JSON before it reaches the RuleSet:
  schema, the id-hyphen/category-underscore convention, AND-of-OR prereq shape,
  cross-file prereq resolution, orphan/cycle trees, cost/duration spillover, OCR
  ligature damage, `extra_min_abilities` nesting, and a **2e-terminology blocklist that
  ERRORS** (MDV, DV, Intimacies, "War Ability", 2e pool notation) — then hands the set
  to `load_ruleset`. `--splat <name>` scopes it; it reads every file for prereq
  resolution but only reports on the targeted ones. Found two real bugs on existing
  data the day it was written.
- **`tools/ocr_scan_book.py`** — the EXPENSIVE leg, for a book with no text layer at all
  (`pdftotext` returns one form feed per page, so `extract_born_digital.py` is
  inapplicable). pdftoppm at 300 dpi + tesseract per page, emitting the same
  `<!--PAGE n-->` shape in PRINTED pages; strips border-art soup, the running head and
  the folio. Generalises phase 2's hand-run method (`docs/status/phase-2-scan.md`).
  ⚠ **`--offset` is required and must be CONFIRMED against a printed folio** — it is
  per-book and not guessable (Sidereals −3, Scavenger Sons 0, most books here +1), and
  it does NOT hold in the front matter, where folio numbering has not started (the
  Sidereals run emitted `PAGE -2`/`-1`/`0`, all art plates).
  ⚠ **Prose comes out clean; STAT BLOCKS do not.** The Sidereals run (277pp, 1.04 MB,
  zero garbled markers) still put 36 of 174 `Minimum Essence:` values beyond reading —
  27 as `|`, the rest `?`/`2?`/`/` — and interleaved one Charm's two-column cost header
  so the value landed five lines below its label. Chapter-opener pages fuse the running
  head into the body. **A zero garbled-marker count is not evidence the crunch
  survived**; the markers catch collapsed word spacing, not a mis-read digit or a
  column that reflowed wrongly. Dots are worse still — `Resources •••••` came out
  `Resources ***®®`, inconsistent glyphs WITHIN one rating, so the phase-2 rule stands:
  every dot value is read off the page image, never off this output.
- **`tools/CHARM_AUTHORING_SPEC.md`** — the verbatim brief for a delegated transcriber.
  Load-bearing parts: never invent a missing value (report it), `min_attribute` NAMES /
  `min_ability` RATES, a comma on the page means AND not OR, `extra_min_abilities` for
  a multi-gate Charm, and a do-not-touch list of the splat-specific fields.
  **Delegation is worth it at Lunar/Alchemical scale (120+ Charms, self-contained
  trees), not at 20** — a cold agent lacks the existing catalogue and will guess
  prerequisite ids, which costs more to check than to author.
