# Status detail — Dragon-Blooded Aspect Books (Chapter Six)

Referenced from `CLAUDE.md` → Status. DONE 2026-07-29.
Read from `images/Dragonblooded/Aspects/<Air|Earth|Fire|Water|Wood>/CH 6 - *.md`
(human-pasted text). **87 Charms + Jade Mountain Style + 8 weapons + 1 armour.**
Tests: `tests/test_dragonblooded_aspect_books.py` (32).

| Book | Charms | Deity |
|---|---|---|
| Air | 22 | Miracles of Mela |
| Earth | 20 (13 ability + 7 Jade Mountain) | Miracles of Pasiap |
| Fire | 12 | Miracles of Hesiesh |
| Water | 24 | Miracles of Daana'd |
| Wood | 9 | Miracles of Sextes Jylis |

## The parse
Water's file is clean markdown (`## ABILITY` / `### CHARM`); the other four are raw
paste needing three repairs, all of which bit:
1. **Drop-cap damage** — `P ILLAR OF MARBLE STANCE`, `E NDURANCE`, `N EW C HARMS`. The
   naive `([A-Z]) ([A-Z]{2,})` merge also ate `DRAGON'S SOUL` → `DRAGON'SSOUL`, so it
   excludes a capital preceded by an apostrophe.
2. **Wrapped stat-block values** — `Cost: 20 motes, 1 Willpower, 1 aggravated health` /
   `level, 1 experience point`. A value runs from its label to the NEXT label; only the
   last field continues, and only across explicit hyphenation. The first cut let
   prerequisite continuation greedily swallow whole descriptions (5 Charms lost theirs).
3. **End-of-line hyphens** — 147 of them. Resolved against a **vocabulary built from the
   corpus itself** (`build_vocab`), not a capitalisation rule, which gets `well- known`
   wrong in the other direction. Healing iterates to a fixed point because a word split
   twice (`com- munication- oriented`) loses the boundary the second repair needs. One
   legitimate suspended hyphen survives by design: `Linguistic- and communication-oriented`.

All 14 initially-unresolved prerequisites were the books abbreviating a name that
already exists (`Seeking Throw` → *Seeking Throw Technique*); resolved by UNAMBIGUOUS
prefix match. Scripts lived in the session scratchpad, not committed — the JSON is the
durable artifact, as with the Sidereal pipeline ([[sidereal-charm-ocr-pipeline]]).
**Unlike Sidereal, not one minimum was missing** — no `_MISSING_MINIMUMS.md` was needed.

## Rules-authority calls (confirmed 2026-07-29 — do not relitigate)
- **`element` follows the ABILITY, never the chapter.** Two Charms are printed in one
  aspect's book but keyed to another's Ability: **Diligent Engineer Discipline** (Air
  book, Craft → Earth) and **Spark Kindling Rescue Technique** (Fire book, Medicine →
  Wood). All 169 previously-shipped DB Charms derive element from the Ability with zero
  exceptions, and `element` is read mechanically ONLY for Immaculate Charms (the
  single-elemental-tree check), so this is consistency rather than a rules effect.
- **Jade Mountain Style is NOT Immaculate.** The Earth book: "This Terrestrial-level
  martial art ... similar in tone and yet far less powerful than the Immaculate Earth
  Dragon Style." Flagging it `immaculate` would hand it the Immaculate BP/XP rates and
  drag characters onto the single-elemental-tree chargen path (p.151). Its own file and
  category `martial_arts:jade-mountain`, Dragon-Blooded-only (no `open_to_all`).

## New model shape: breadth prerequisites
**`Charm.prerequisite_counts: list[CharmCountRequirement]`** — "any three Lore Charms",
which five Charms require (Favored Quill Mastery, Flawless Study Focus, Embracing the
Arcane, Favored Haunt Stance, Resplendent Artisan Mastery; all Min Ability 3 / Essence 3,
one per aspect Ability — a deliberate design pattern).

`prerequisites` could not express it: it is AND-of-OR over **ids**, and encoding "3 of
11" as three groups each listing all eleven is satisfied three times over by a single
owned Charm. Wiring:
- `validate.charm_count_shortfalls(ruleset, held_ids, charm)` — ONE function feeding
  both `check_charm_prerequisites` (retrospective, code
  `charm-prerequisite-count`) and `meets_charm_requirements` (forward-looking), so the
  picker's "selectable" and the sheet's "illegal" cannot disagree.
- **A Charm never counts toward its own requirement** — otherwise buying it would
  part-satisfy the thing gating it.
- Counting is by `category`, so the cross-book Craft Charm counts toward "any three
  Craft Charms".
- Display: `charm_count_requirement_label` → "any 3 Occult Charms". It has **no source
  node to draw an edge from**, so it rides as a single-entry `prerequisite_group` on the
  detail card and as `CharmNode.count_requirement`, rendered into the graph node's
  label — otherwise a capstone Charm sits among the roots looking entry-level.

## Model limits recorded rather than papered over
- **`Type: Reflexive or Simple`** (Pulse of the Dragon's Soul, matching its "1 or 3
  motes"). `CharmType` has no disjunction, so it is `Special` — the Ox-Body escape hatch
  — with the mechanic in the description. It is the ONLY aspect-book Charm forced there;
  a second would mean the enum needs revisiting.
- **The Jade Mountain style preamble is not stored anywhere.** Its style-level rules
  (non-Earth-Aspects pay a 1-mote elemental surcharge; the style fails unless the Exalt
  touches the ground; Charms may be used freely with armor and treat one-handed crushing
  weapons as unarmed) belong to the STYLE, and there is no style entity — categories are
  bare strings. Same treatment every other style preamble has had (Falling Blossom's, the
  Sidereal styles'). **If a style entity is ever added, this is the content waiting for it.**
- **`ArmorType` gained `notes`.** `WeaponType` has carried it since the castebooks; a
  `notes` key in `armor.json` was silently DROPPED on load before this. Found because
  the Air armour has a Strength column and flight rules with nowhere to go.

## Gear (Solar-castebook precedent: weapons/armour yes, hearthstones no)
Weapon tables in **Fire, Wood and Air are column-scrambled** in the paste (one cell per
line) — the shape CLAUDE.md says to flag. The column ORDER is regular, so they were read
directly and every value is pinned in a test. Water's table is clean markdown.

| Weapon | Book | Speed | Acc | Dmg | Def | Artifact |
|---|---|---|---|---|---|---|
| Forge-Hand Gauntlets | Fire p.81 | -3 | -1 | +4A | +2 | •••• |
| Eye of the Fire Dragon | Fire p.81 | +10 | +3 | +8L | +2 | ••••• |
| Black Widow Razors | Wood p.83 | +1 | +1 | +4L (+poison) | +2 | ••• (pair) |
| Grand Grimcleaver | Wood p.83 | -6 | +1 | +13L | -1 | none printed |
| Death at the Root | Wood p.83 | -5 | +2 | +13L | -0 | •••• |
| Gauntlets of Distant Touch | Water p.80 | +3 | +2 | +5L | +3 | ••• |
| Lightning Corona (melee) | Air p.81 | +2 | +1 | +5L | +1 | integral |
| Lightning Corona (ranged) | Air p.81 | — | +0 | 10L | — | integral |

- **Most Terrifying Armor of the Air Dragon** (Air p.81): Soak 13L/15B, Mobility -0,
  Fatigue 1, Artifact ••••. Strength "+2 (8)" and the flight rules are in `notes`.
  The source prints the name **"Most Terryfying"** in the stat table and correctly in
  the heading.
- **Lightning Corona is two rows**, melee and ranged — the armour's integral weapon, not
  a separate artifact. Same treatment as the castebooks' Ultimately Useful Tube. The
  ranged row's Speed/Defense are **not printed** and were not invented.
- **Every table prints a second "Exalted Power Combat" row** — an alternate ruleset. The
  standard row is canonical; the variant lives in `notes` and must never be what the
  catalog reports.
- **Skipped** (no weapon/armour line at all): Elemental Lens, Reaver Dragonfly,
  Dragonfly's Ranging Eye, Hearthstone Compass, Cache Egg, Skin-Mount Amulet, Perfected
  Kata Bracers, Dueling Torcs, Emerald Thurible, the Resplendent Dolphin Undersea
  Courier, and every hearthstone. Grand Grimcleaver and Lightning Corona are named ONLY
  in tables — the chapters carry no write-up for either.
