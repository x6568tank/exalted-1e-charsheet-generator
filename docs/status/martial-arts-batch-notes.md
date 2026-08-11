# Martial Arts batch notes — Player's Guide 49-Charm run (2026-08-11)

Authoring notes for `docs/plans/delegation-brief-martial-arts.md`. 48 of 49 Charms
authored; one skipped (see **Skipped**). Source: `images/_extracted/Player's Guide.md`
pp.236-237, 241-258 — read ONLY that, nothing in `sources/`. No `.py` file touched.

## ⚠ Read this first — the Dragon-Path gate still needs extending

The four initiation Charms are in the build and buyable, but **will NOT open the
Dragon Paths**, because `engine/validate.py` hardcodes:

```python
DB_MA_ENLIGHTENMENT_IDS = ("dragonblooded.martial-arts.spirit-sight",
                           "dragonblooded.martial-arts.spirit-walking")
```

and `db_enlightenment_met` requires **all** of them. That must become "any one
complete pair" for the new initiations to work. The build now holds **three**
complete pairs:

| Pair | Charms |
|---|---|
| Immaculate | `dragonblooded.martial-arts.spirit-sight` + `…spirit-walking` |
| Iris-Bulb | `dragonblooded.martial-arts.walker-among-irises-perception` + `…iris-bulb-discourse` |
| Tiger-and-Bear | `dragonblooded.martial-arts.tiger-and-bear-awareness` + `…tiger-and-bear-unity` |

That code change is the **reviewer's job, not mine** — I did not edit `validate.py`,
and I did not give the new Charms ids that pretend to be the existing pair. PG p.236
says the Immaculate pair is "just one set of such Charms. There are others." — the
same category (`martial_arts:enlightenment`), already exempt from the Dragon-Path
gate (`_UNGATED_MA_STYLES`), so nothing else in the gate breaks.

## Skipped

**Five Directions Formation Protocol** — Crimson Pentacle Blade, p.242. **SKIPPED.**

Every stat the page prints for it is literally "Varies": `Cost: Varies`, `Duration:
Varies`, `Type: Varies`, `Minimum Martial Arts: Varies`, `Minimum Essence: Varies`.
The page itself says it is "not a proper Charm in its own right" and "indicates the
attainment of an ability" (protocols — multi-participant Combos). The Charm model
needs a concrete `type` (the enum has no "Varies") and concrete int minimums;
encoding it would mean inventing a type and two minimums the page never printed —
forbidden by the never-author-from-memory rule. Left out rather than guessed.

Consequences: Crimson Pentacle Blade ships **13 of 14**; the build holds **1,828**
Charms, not the brief's target 1,829. The one gap is this meta-Charm. Reviewer/
human decision: represent protocols at all, and if so how (a "Varies"/attainment
Charm shape, or leave protocols as prose in Eastern Root Protocol's description,
which is where they're already explained).

Nothing else was skipped. No `"???"` values — every other printed value transcribed.

## Prerequisites

**All resolve** — checked against the full build's id universe (all `data/charms/*.json`),
not just the `*martial_arts*` glob, because two prereqs are cross-ability:

- **Vindictive Concubine's Pillow Book Understanding** (p.251) requires
  `solar.socialize.motive-discerning-technique` — a Solar **Investigation** Charm.
- **Invoking the Chimera's Coils** (p.253) requires
  `solar.socialize.knowing-the-souls-price` — a Solar **Socialize** Charm.

⚠ The brief's own check script (`glob '*martial_arts*.json'`) **false-fails on these
two** — `solar_socialize.json` isn't in the glob, so the script's local id universe
lacks them. That's a script limitation, not a data defect; the ids exist and the full
test suite (which loads the whole ruleset) is green. Run the check with all charm
files in scope.

## Worklist-vs-printed names

| Worklist | Printed (used) | Page |
|---|---|---|
| Graceful **Toroise** Technique | Graceful **Tortoise** Technique | 241 |
| Call-to-the-**Blade-ofReighteouseness** Mantra | Call-to-the-**Blade-of-Righteousness** Mantra | 246 |

Both worklist entries were typos; the printed small-caps name wins. All other names
matched the worklist exactly.

**Related page inconsistency (not a name diff):** Blessing of Righteous Solar Spark
Meditation's *prerequisite line* names its prereq "**Fire** Blossom of Inevitable
Demise Technique" (p.255) — but the Charm's own header is "Blossom of Inevitable
Demise Technique". Same Charm; the page adds "Fire". Resolved to
`blossom-of-inevitable-demise-technique`.

## Tier / access decisions (page vs worklist)

The worklist tier and the page's style header agree for all four styles (CPB
Terrestrial; Righteous Devil, Dreaming Pearl Courtesan, Celestial Monkey all print
"Type: Celestial"). **One deliberate deviation, and two restrictions the tier fields
cannot express:**

1. **Blessing of Righteous Solar Spark Meditation** (p.255) ends with **"Only Solar
   Exalted can use this particular Charm."** I set `"exalt_type": "Solar"` on this one
   Charm — the ONLY `exalt_type` set anywhere in the batch, and a deliberate exception
   to the brief's "omit exalt_type". Every other Righteous Devil Charm is
   `open_to_tiers: ["Celestial"]` per the style header; this one carries the printed
   Solar-only gate. If the reviewer prefers a different encoding for per-Charm access,
   this is the spot — but leaving it Celestial-open contradicts the page.

2. **Dreaming Pearl Courtesan** (p.250 intro) is "mastered only by the Solar Exalted
   and Moonshadow Caste Abyssals, as it requires the understanding of certain Solar
   techniques of persuasion." Worklist says Celestial tier → encoded `open_to_tiers:
   ["Celestial"]`. Not hard-gated; the two Charms with Solar-Socialize prereqs
   (Motive-Discerning Technique, Knowing the Soul's Price) largely enforce it, since
   foreign Solar Charms need the Eclipse/Moonshadow permission. Reviewer call if a
   hard gate is wanted.

3. **Celestial Monkey** (p.246 intro): "those who would grow in the wisdom of the
   Celestial Monkey can not have any Virtue rating higher than 3." A style-wide Virtue
   cap with no data field. Noted, not encoded.

## Per-style counts

| Style | Authored | Notes |
|---|---|---|
| Crimson Pentacle Blade | **13** (of 14) | Five Directions Formation Protocol skipped |
| Righteous Devil | **12** | includes Blessing… (Solar-only, see above) |
| Dreaming Pearl Courtesan | **10** | |
| Celestial Monkey | **9** | |
| Celestial Initiation | **4** | added to existing `dragonblooded_martial_arts.json` |
| **Total new** | **48** | build 1,780 → **1,828** |

New files: `solar_martial_arts_crimson_pentacle_blade.json`,
`solar_martial_arts_righteous_devil.json`,
`solar_martial_arts_dreaming_pearl_courtesan.json`,
`solar_martial_arts_celestial_monkey.json`. Initiation Charms went into the existing
`dragonblooded_martial_arts.json` (that's where Spirit Sight / Spirit Walking live),
category `martial_arts:enlightenment`, fields copied from the existing pair
(`exalt_type` Dragon-Blooded + `open_to_all`, `element: ""`).

## Noticed and not acted on

- **Combo-OK column** in the worklist is informational — no Combo-OK field exists in
  the Charm model or any existing MA data (checked). Not encoded anywhere.
- **Page typo kept verbatim in `raw`:** Cloud of Ebon Devils (p.255) prints "Cost: **1
  motes**". `raw` kept as "1 motes" per the "raw verbatim" instruction; `motes: 1`.
- **Righteous Devil prose is Solar-heavy** even in Charms I did NOT gate Solar-only
  (e.g. "The Solar Exalted meditates" in Blessing, "a Solar with this Charm" in Cloud
  of Ebon Devils). Only Blessing carries the explicit "Only Solar Exalted can use this
  particular Charm" sentence, so only that one is gated. If the intent is that the
  whole style is Solar-restricted, that's a bigger change for the reviewer.
- **Committed costs:** set `"committed": true` where the page says committed —
  Blessing of Righteous Solar Spark Meditation (2 motes until the weapon fires,
  p.255) and Call-to-the-Blade-of-Righteousness Mantra (3 motes, p.246). The model
  supports it; matches the printed text.
- **Cost: None / no XP field:** Celestial Godbody Understanding (p.249) is
  `Cost: None`, `Duration: Permanent`, `Type: Special` → `motes: 0`, `raw: "None"`.
  Walking in the Footsteps of Ten Thousand Things (p.248) costs "10 motes, 1
  Willpower, **2 Experience Points**" — `CharmCost` has no XP field, so the 2 XP is
  in `raw` and the description (it's spent once regardless of repeats).
- **"Varies" durations** (Caress of 1,000 Hells p.258; Invoking the Chimera's Coils
  p.253; Resplendent Sash Grapple Technique p.251) transcribed verbatim — `duration`
  is a free string, and the build already does this (e.g. `abyssal_sail.json`).
- No `<!--GARBLED…-->`, `<!--COLUMN SPLIT FAILED…-->` or `<!--SHATTERED HEADING…-->`
  markers on any page I authored from (236-237, 241-258). The first such marker in
  the extract is p.259, outside range.
- No `.py` file was touched. `git status` should show only the four new JSON files,
  the edit to `dragonblooded_martial_arts.json`, and this notes file (plus whatever
  was already modified before this batch).

## Verification

- Full suite: **2,091 passed, 1 failed** — the single failure is the known
  machine-specific `test_merits_flaws.py::test_every_description_matches_the_source_text`
  (46 Godblooded entries, green on the laptop, red here), exactly the one the brief
  says to expect. No other failures.
- Brief's check script (widened to the full-build id universe): no duplicate ids, no
  unresolved prerequisites, no Charm with both `open_to_all` and `open_to_tiers`.

---

## Review addendum — 2026-08-11 (Claude)

**Verified:** scope clean (no `.py` touched by the batch); 1,828 Charms; zero dangling
prerequisites across the whole build; no record with both access fields set; access
encoding correct per style (CPB `open_to_all`, the three Celestial styles
`open_to_tiers: ["Celestial"]`, the enlightenment tree matching the existing pair).
**39 of 44 style Charms verified exact** against the printed `Cost:` / `Minimum` lines;
four of the five apparent mismatches were the reviewer's regex truncating at line
breaks, not data errors.

Both flagged judgment calls check out against the page:
- **Five Directions Formation Protocol** genuinely prints `Varies` for Cost, Duration,
  Type, Minimum Martial Arts *and* Minimum Essence. Skipping was right — the model needs
  a concrete enum and integer minimums, so encoding it would have meant inventing five
  numbers. **1,828 is the correct total, not 1,829.**
- **Blessing of Righteous Solar Spark Meditation** — p.255 does print "Only Solar
  Exalted can use this particular Charm", so `exalt_type: "Solar"` is right, and it is
  the correct encoding: `charm_matches_splat` matches on splat when no tier is set.

### The Dragon-Path gate — EXTENDED (this was the reviewer's job)
`DB_MA_ENLIGHTENMENT_IDS` required the Immaculate pair specifically, so the four new
initiation Charms would have loaded, been buyable, and opened nothing. It is now
`DB_MA_ENLIGHTENMENT_PAIRS` — three pairs (Immaculate, Iris-Bulb, Tiger-and-Bear) —
and `db_enlightenment_met` returns True on **any one complete pair**. PG p.236 states
the rule directly: *"The Immaculate Charms Spirit Sight and Spirit Walking are just one
set of such Charms. There are others."*

**Three tests added** (`tests/test_dragonblooded.py`), because a gate with no test is
how this class of bug survives: each pair opens the Paths; half a pair does not, and
neither does one Charm from each of two different pairs; and every id in the table
resolves to a real Charm in the enlightenment category — a gate keyed on hardcoded ids
fails *silently* if a Charm is renamed.

### Two small corrections applied
- **`raw` must be the printed Cost line verbatim.** Blessing of Righteous Solar Spark
  Meditation had `"2 motes (committed)"`; the page prints `Cost: 2 motes` and the
  commitment appears in the body text. `raw` is now `"2 motes"`; the structured
  `committed: true` — which is the right way to capture it — stays.
- **The page prints `DEFENSE`, not `DEFENCE`.** `Pearlescent Filigree Defence` →
  `Pearlescent Filigree Defense`, id regenerated, no references to the old id remained.

### Still open, deliberately
The two style-wide restrictions the batch documented — Dreaming Pearl Courtesan
"mastered only by Solar and Moonshadow Abyssals", Celestial Monkey "no Virtue rating
above 3" — remain un-gated. Neither is expressible in `open_to_all` / `open_to_tiers`,
and inventing a field for them is a design decision, not a transcription one.

### The two style-wide restrictions — NOW GATED (human's call, 2026-08-11)
Both were documented-but-unenforced, which is the dead-rule shape this build keeps
hitting. Both are now data with read sites and tests.

**Dreaming Pearl Courtesan** — PG p.249: *"it can be mastered only by the Solar Exalted
and Moonshadow Caste Abyssals."* New field **`Charm.restricted_to`**, a list of
`"<Splat>"` / `"<Splat>:<caste>"` entries the character must match ONE of:
`["Solar", "Abyssal:moonshadow"]`. It **narrows** an access already granted — the style
is also tier-Celestial, and the restriction is what stops a Lunar or Sidereal reaching
it. Read in `charm_matches_splat`, above every grant so no later branch talks past it.

**Celestial Monkey** — PG p.246: *"those who would grow in the wisdom of the Celestial
Monkey can not have any Virtue rating higher than 3."* New field
**`Charm.max_virtue`** (0 = no cap). This is **the only requirement in the build a
character fails by having MORE of a trait**, so it cannot ride on the `min_*` shortfall
machinery. Read in **two** places, deliberately: `meets_charm_requirements` (so the
picker will not offer it) and `check_charm_prerequisites` (so raising a Virtue *after*
buying in reports `charm-max-virtue`). A forward-looking bar alone would have let the
rule silently stop applying the moment the character improved.

Six tests cover both, including that neither field touches any other Charm in the
catalogue. ⚠ **Trap for the next person:** the per-Charm checks run in
`validate.validate()`, **not** `validate.validate_chargen()` — asserting against the
latter yields an empty set and a rule that looks enforced when it is not. That mistake
was made and caught while writing these tests.
