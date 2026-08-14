# The martial-arts STYLE entity

**Status: Phase 1 DONE 2026-08-14** — model, loader, link check, picker panel and
**4 of 22 styles authored**. Suite **2,420 passing** at close.
**NOT BROWSER-VERIFIED** — nobody has looked at the preamble panel in a browser.
Phase 2 (the other 18) is open.
Plan and the decisions behind it: `docs/plans/martial-arts-styles.md`.
Closes open TODO 2 in `CLAUDE.md` for the modelling half.

## What shipped

- **`MartialArtsStyle`** (`models/rules.py`) — `id`, `name`, `category`, `tier`
  (the printed `Type:` word), `preamble`, `mechanics[]`, `source`.
- **`data/martial_arts_styles.json`** — Crimson Pentacle Blade (**Terrestrial**),
  Celestial Monkey, Dreaming Pearl Courtesan, Righteous Devil (all Celestial), read
  off `images/_extracted/Player's Guide.md` pp.239-254.
- **`RuleSet.martial_arts_styles`** + a two-directional load-time link check.
- **`rules_db.unauthored_martial_arts_styles(ruleset)`** — the Phase 2 worklist.
- **`view.style_for_category`** → `StyleView`, and a **collapsible preamble panel**
  above the Charm tree on the picker's Martial Arts page.
- **`build_picker(..., initial_category=...)`** so a route can open one tree.
- `tests/test_martial_arts_styles.py` — 13 tests.

## ⚠ Righteous Devil Style — a documented exception, NOT a bug

Found by the consistency test written for this job: 11 of its 12 Charms carry
`open_to_tiers: ["Celestial"]`; **Blessing of Righteous Solar Spark Meditation**
(PG p.255) does not, so a Lunar or Sidereal may learn the style but not that Charm.

**The human ruled it CORRECT AS PRINTED (2026-08-14)** — the Charm's own text names
the Solar Exalted, so it is genuinely narrower than the Type: Celestial style around
it. It lives in `_DOCUMENTED_ACCESS_EXCEPTIONS` in the test, **and a second test
asserts that set contains exactly this one Charm**, so the exception cannot quietly
grow into an allowlist that absorbs the next real divergence.

**Do not "fix" this Charm.**

## ⚠ The Phase-1 boundary: `tier` is DISPLAY ONLY

The style's printed `Type:` and the Charms' `open_to_all` / `open_to_tiers` /
`restricted_to` / `immaculate` are **two descriptions of one fact**. The human's
scoping call was preamble-and-Type only: **access is still decided entirely by the
CHARM fields, exactly as before. This change altered no access rule.**

`test_no_engine_module_reads_the_style_catalogue` parses every `engine/*.py` and
fails on any read of `martial_arts_styles` or `MartialArtsStyle`. Two live
descriptions of one rule disagree — the shape decision 0011 exists to prevent, and
the reason the Edit⇄XP merge happened. If the styles should later own access, that
is a migration that **removes** the per-Charm fields, and the test changes as part
of it, on purpose.

## ⚠ An unauthored style is a WORKLIST ENTRY, not a load error

The link check runs both ways but they are **not symmetric**:

- **style → Charms is FATAL.** A style whose `category` no Charm uses is a slug
  typo; it would load clean and simply never appear.
- **Charms → style is NOT.** 18 styles are unauthored by design. Raising on them
  would stop the app from starting. They are reported by
  `unauthored_martial_arts_styles`, and a test pins the list of 18 so it can only
  shrink — authoring a style without removing it there fails, and so does losing one.

**Custom styles are exempt from both.** `custom_content.py` mints
`martial_arts:<slug>` at runtime and there is no page to write a preamble from;
decision 0012 says homebrew must never break the load. The exemption is tested with
its own negative control (the same category, printed rather than homebrew, IS work).

## Phase 2 — the remaining 18

Every source is in `sources/`. Per the 2026-08-13 authorisation, pure scans are
rasterised with `pdftoppm` and read directly.

| Book | Styles | Pages |
|---|---|---|
| Exalted 1e Dragon-Blooded | Air/Earth/Fire/Water/Wood Dragon, Five-Dragon, Enlightenment | 197-263 |
| Exalted 1e The Sidereals | Charcoal March of Spiders, Citrine Poxes, Prismatic Arrangement, Violet Bier | 179-201 |
| Castebooks (Night / Eclipse / Dawn) | Ebon Shadow, Praying Mantis, Tiger | 67-75 |
| Cult of the Illuminated | Falling Blossom | 103-104 |
| Aspect Book: Earth | **Jade Mountain** | 71 |
| Exalted: The Abyssals | Hungry Ghost | 162-165 |
| Core | Snake | 160-162 |

**Jade Mountain is the worked example** the whole TODO was written around — its
three mechanics are already transcribed in
`docs/status/dragonblooded-aspect-books.md`, waiting for exactly this entity.

⚠ **`martial_arts:enlightenment` is not a style** — it is the Dragon-Path
initiation tree (`ui/picker.py` says so). It gets an entry only if its page carries
a preamble of its own; otherwise remove it from the worklist as a documented
absence rather than authoring something.

## Traps

- **⚠ Matching style names against the books failed THREE times in one session**,
  in both directions. A loose substring matcher scored "snake"/"tiger" as found
  anywhere in any book; a strict `NAME STYLE` + `Type:` matcher then found only 4
  of 22 and reported the other 18 as absent when they are all present; and a
  `WEAPONS AND ARMOR` regex missed the sidebar spelled `WEAPONSAND ARMOR`.
  **What worked was book + page off the Charms' own `source`.** Exactly
  `feedback_gap_matchers_wrong_both_ways`, three more times.
- **Two "Celestial Monkey Style" hits in the Player's Guide are an ASTROLOGY
  correlations table**, not the style section. A name match can land in the wrong
  chapter of the right book.
- **The preamble panel renders NOTHING for an unauthored style**, not an empty box
  — the same rule the printed sheet's panels follow.
- `whitespace-pre-line` on the preamble label, or NiceGUI collapses the paragraph
  breaks (`docs/status/backgrounds.md` learned this first).
- **`initial_category` is validated against the offered options before use.** A
  caller-supplied category that is not on offer is the `ui.select` build-time crash
  that blanks sibling tabs (`adding-a-splat.md` trap #3), so it falls back rather
  than trusting the caller.
