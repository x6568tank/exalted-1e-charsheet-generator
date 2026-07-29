# Thaumaturgy (Player's Guide CH3)

**STATUS: engine complete — catalogue, models, costs, BP breakdown, chargen gates,
snapshot freeze and XP advancement. UI is the only piece left.**
Source survey and architecture written up 2026-07-29; build started same day.
Source: `images/Mortals/Mortals & Heroic Mortals/Player's Guide.md` (pasted text,
pp. 11-12 + 96-150) and `Exalted p103.png` (corebook heroic-mortal chargen).

## Build log
Tests: `tests/test_thaumaturgy_data.py` (38, catalogue + cost ladder) and
`tests/test_thaumaturgy_engine.py` (85, integration). Suite 873 -> 996.

**Done:**
- `data/thaumaturgy/{arts,sciences,rituals,formulas}.json` — 4 Arts (+25 aspects),
  4 Sciences (+21 dot rungs), 8 ritual ids, 14 formulas.
- Models: `Orientation`, `ThaumaturgicAspect/Art`, `ScienceLevel`,
  `ThaumaturgicScience` (with `max_rating` and rating-keyed `level()`),
  `ThaumaturgicRitual`, `ThaumaturgicFormula`; character-side `ArtSpecialty`,
  `ScienceRating`, `RitualEntry`, `FormulaEntry`, `ThaumaturgyState`.
- `Character.thaumaturgy` and `ChargenSnapshot.thaumaturgy`, both `Optional`.
- `ExaltDefinition.thaumaturgy_usable` / `.thaumaturgy_cost_multiplier`.
- Loader + `_check_thaumaturgy` link-check (unknown science, level above
  `max_rating`, duplicate aspect id across Arts).
- Cost ladder in `engine/costs.py`: `thaum_art_*`, `thaum_specialty_*`,
  `thaum_ritual_*`, `thaum_formula_*`, `thaum_orientation_*`, both currencies.
- **The purchase enumeration** — `validate.ThaumPurchase` / `thaum_purchases` /
  `chargen_thaum_purchases` / `thaum_purchase_bp_costs`, built on the Charm-pick
  template: five heterogeneous lists enumerated once and priced once, so the BP
  breakdown, the XP audit and (later) the UI all consume one thing.
- `_chargen_source` carries thaumaturgy as its 17th element; `bonus_point_breakdown`
  grows a **Thaumaturgy** line, shown only once something is bought so every
  existing splat's breakdown is unchanged.
- `validate.thaumaturgy_issues` — Occult gates on Arts, printed aspects and rituals;
  per-Science `max_rating`; narrowing refused outside Summoning; `thaumaturgy_usable`
  as an *info* issue, never a bar. Called from `validate_chargen`.
- `lock_chargen` deep-copies `ChargenSnapshot.thaumaturgy`, leaving it None for a
  character who has none, so untouched saves still round-trip to None.
- XP advancement: `learn_thaum_art`, `add_thaum_specialty`, `raise_thaum_science`,
  `learn_thaum_ritual`, `learn_thaum_formula`, `add_thaum_orientation`, plus undo
  and `_expected_cost` re-pricing for all six.
- Science costs on both ladders (see below) — `raise_thaum_science` caps at the
  Science's OWN `max_rating`, so Alchemy reaches 6 where Geomancy stops at 5.

**Not done:** the UI page. The Knowledge restricted-BP pool is deliberately
deferred to the M&F milestone.

### Science costs — RESOLVED, and the one rate here with no page behind it
Neither printed cost table has a Science row: the BP table (p.116) runs Attribute /
Ability / Background / Specialty / Virtue / Willpower / Essence / **Art / Art
Specialty / Ritual / Procedure-Formula** / Merit, and the XP table (p.115) matches.
The only prose is p.113 — points may go on Arts, Sciences and rituals "in any
combination without limitation", which is a permission, not a rate.

**That omission is a PRINTING ERROR that Grabowski cleared up later.** The rate,
supplied by the rules authority (human, 2026-07-29):

| | First dot | Each dot after |
|---|---|---|
| Bonus points | 5 | 7 |
| Experience | 7 | current rating × 6 |

Note the XP side takes the ordinary "new trait flat, raises scale" shape every other
rated trait uses, and that the two ladders disagree — the same asymmetry the Art
Specialty rows already have (2 BP / 3 XP). Do not tidy them into agreement.

⚠️ **This is the only value in the whole thaumaturgy build with no page behind it.**
It is flagged at all four sites (`BonusPointCosts.thaum_science_first_dot`,
`ExperienceCosts.thaum_new_science`, both `costs.thaum_science_*` docstrings) so
nobody later mistakes it for something read off a table. If a printed source ever
contradicts it, the printed source wins.

### Errata: p.116 Step Four
The character-creation summary reads "Choose Backgrounds (5 in addition to recorded
**Inheritance**)". It should read "**in addition to recorded Knowledge**" (human,
2026-07-29). Step One is the step that records Knowledge, and Knowledge is the
Background that grants the extra magical bonus points — so the 5 ordinary Background
dots are on top of the Knowledge rating, not on top of Inheritance.

Nothing consumes this yet: mortal/thaumaturge chargen is not built, and the Knowledge
restricted-BP pool is deferred to the M&F milestone. **Read this before building
either** — it decides whether Knowledge comes out of the Background pool (it does
not).

### One place the design changed while building
`ArtSpecialty` gained a stored `narrowed: bool`. Summoning's discount reads "a
thaumaturge may choose to further limit one or more of their summoning aspects …
This halves the cost of the aspect **and should be noted on the character sheet**"
(p.127) — so narrowing is a recorded property of a purchase, not something to infer
from whether the specialty's name matches a printed aspect. Inferring it would also
have made the XP audit unable to re-price the row: a narrowed and an un-narrowed
"Summoning (Beasts)" are otherwise identical log entries at 2 XP and 3 XP.

Extra orientations are likewise their **own** logged purchase rather than a count
folded into the base row, which is what makes the append-only log unambiguous — the
exact failure the "build orientation now" argument was about.

## The one-line architectural claim
**Thaumaturgy is an orthogonal capability layer, not a splat and not an origin.**
p.114 sidebar "Others and Thaumaturgy": the Exalted learn it "without any
difficulty", the Wyld-tainted "with no restraint", Dragon Kings can, **spirits pay
double** BP/XP for any Art, Science or ritual, **the Fair Folk not at all**, and
**the dead retain what they learned but are forever barred from using it**.

So it hangs off neither `exalt_type` nor `origin`. It is an optional sub-document
on `Character`, exactly like `Character.play`:
```python
thaumaturgy: ThaumaturgyState | None = None   # old saves load with None
```

## Rules-authority calls (human, 2026-07-29 — do not relitigate)
1. **Ghosts hold it, flagged unusable.** Not "cannot purchase". The dead keep the
   knowledge and can act as tutors; they may never use it. Model as a flag, not a
   purchase bar.
2. **Retroactive across all six shipped splats.** Thaumaturgy appears on Solar,
   Abyssal, Dragon-Blooded, Lunar, Sidereal and Alchemical sheets, not just mortals.
   This is the first feature to touch every existing splat.
3. **The mortal XP/BP table is the Mortal splat's cost row, independent of
   thaumaturgy.** Note **Virtue is `current × 4`** there (p.115), NOT the Solar ×3 —
   a live example of the never-generalize-a-Solar-number rule. The thaumaturgy part
   is only the Art / Art Specialty / Ritual / Formula rows, which apply to everyone.
4. **"Magic for Everyone" (p.115) — OPEN.** The optional rule granting every
   character one ritual/formula/aspect per two dots of Occult (max level 3, aspects
   only, never Arts). Human is still deciding. Author nothing for it.
5. **Spirits' ×2 multiplier — note it, wire nothing.** No playable spirit splat
   exists. Author when/if one does.

## The four branches (this is the sub-tab answer)
The book's own two cost tables (BP p.116, XP p.115) enumerate the purchasable nouns
and agree exactly:

| Purchasable | BP | XP |
|---|---|---|
| Art | 5 | 5 |
| Art Specialty | 2 | 3 |
| Ritual | 2 + 1/level | 3 + 1/level |
| Procedure/Formula | 1 | 1 |
| *Science (first dot)* | *5* | *7* |
| *Science (each dot after)* | *7* | *current x 6* |

The two Science rows are **italicised because they are not in either printed table** —
that omission is a printing error, and the rates come from the Grabowski clarification
via the rules authority. Everything above them is printed. p.113 names the branches:
"the Arts …, the Sciences (Alchemy, Enchantment, Geomancy and Weather Working) and
rituals". Tabs: **Arts · Sciences · Rituals · Formulas**, Art Specialties nesting
under Arts.

These are four genuinely different mechanical shapes — one flat list would fight us.

### Arts — BINARY, not rated
Training = +2 dice, full stop. Specialties = +1 die, **max two applied to any one
roll** (so the ceiling is +4: Art +2, general specialty +1, narrow specialty +1).
**You may buy a specialty without owning the Art** — stated three separate times
(p.126 twice, p.116 BP-table footnote). Player-invented specialties are explicitly
allowed, with scope guidance (geographic + conceptual limiter, or tied to a location).

**An "Aspect" IS a printed general specialty** (settled 2026-07-29 from p.126; do
not relitigate). The stat block heads the list "Aspects:" while the prose calls the
same things specialties — "each field of study is further subdivided into a number
of specialties", "Each art lists a number of specialties" — and the worked example
uses a printed aspect as its middle term: "mastering the Art (Warding, +2), a
general specialty in the Art (**Fair Folk**, +1) and a relevant specialty (Local
Fair Folk, +1)", where Fair Folk is an item on Warding's Aspects line.

Consequences: buying an aspect costs the **Art Specialty** rate (2 BP / 3 XP);
player-invented narrower specialties cost the same and stack for another +1;
Summoning's per-aspect Occult minima gate buying that specialty; and Summoning's
"halves the cost of the aspect" (p.127) halves that point cost, **rounded up** so a
2-BP specialty becomes 1 and never 0 — rounding down would make narrowing free and
strictly dominant.

| Art | Occult | Roll | Cost | Aspects |
|---|---|---|---|---|
| Summoning | • | Charisma + Occult | 3 motes/attempt | ghosts, beasts, spirits, elementals, man |
| Warding | • | Manipulation + Occult (Per+Occ to find weaknesses, Int+Occ to pick the ritual) | 3 motes/attempt | ghosts, demons, elementals, gods, Exalts, animals, mortals, the Wyld, Fair Folk, divination, bad magic |
| Exorcism | ••• | varies by task | 6 motes/attempt | ghosts, Fair Folk, demons, spirits |
| Astrology | •••• | Intelligence + Occult | 0 motes | the Exalted, mortals, the stars of the dead, gods |

**Only Summoning gives its aspects their own Occult minima** (Beasts •, Mortals •,
Demons ••, Elementals ••, Ghosts •••, Spirits •••). Warding, Exorcism and Astrology
list aspects with no per-aspect gate. So `min_occult` on an aspect is optional.

Summoning also has a **narrowing discount**: further limiting an aspect ("Summoning
(War Gods)") **halves that aspect's cost** and is noted on the sheet.

### Sciences — RATED 1-5 (Alchemy 6), each with printed dot descriptions
Costs: **5 BP first dot / 7 after; 7 XP first dot / current x 6 after** — see the
printing-error note in the Build log; not from either printed table.
| Science | Roll | Cost | Notes |
|---|---|---|---|
| Alchemy | Intelligence + Occult | normally none | Lab (Resources 3) required for effects 3+; ingredients cost `level - 1`. Internal alchemy: +2 difficulty, 1 Willpower, reaches 5 dots, own failure table |
| Enchantment | Dexterity + Occult | 3 motes per level of effect, +1 Willpower | Time: 1 day per dot of effect |
| Geomancy | Perception + Occult | normally none | Time varies |
| Weather Working | Charisma + Occult | 2 motes per level, +1 Willpower at levels 4-5 | **always +2 difficulty**. Its 1-5 dot ladder is printed INSIDE the "Council of Winds" sidebar (p.149), not under the Weather Working heading — the paste is not missing it |

Chargen may be capped at "the third level of knowledge in any Science" (ST option,
p.113). Enchantment 3 gates warding-talisman crafting (p.130 sidebar).

### ⚠️ Alchemy goes to SIX dots, and has no five-dot description
**Human's call, 2026-07-29: this is what the book prints, not paste damage.** The
Alchemy ladder runs `• •• ••• ••••` and then `••••••`. There is no five-dot rung.

But **five-dot Alchemy formulas exist** — Heavenly Transmutation Processes and
Six-Demon Potion are both `Alchemy: •••••` — and the general rule is "a formula's
required Alchemy level is equal to its difficulty." So ratings 1-6 are all reachable
and only the level-5 *description* is absent.

Consequences, and the reason this is a pain to wire:
- **`Science` needs its own `max_rating`** (Alchemy 6, the other three 5) rather than
  the ordinary rating constraint. Note the human's framing (2026-07-29): **`≤5` is a
  convention, not a real invariant** — it holds because chargen rarely exceeds 5, but
  ratings above 5 genuinely exist in 1e (very old Exalts run Essence past 5). Alchemy
  is an instance of a known soft spot, not a special case. Do not treat a `≤5` bound
  anywhere in `models/` as load-bearing without checking.
- The dot-description list is **sparse, not an array indexed 1..n** — level 5 has no
  text. Store descriptions keyed by rating, and let the UI render level 5 as a rung
  with no printed description rather than shifting level 6 down into the gap.
- Do NOT "fix" this by renumbering the six-dot entry to five. Two formulas already
  occupy level 5.

### Rituals — leveled • to •••••
"The only normal restriction on purchasing a ritual is that a thaumaturge must have
an Occult score equal to or higher than the ritual's level" (p.148). Workspace costs
Resources `level - 2`. Rituals are always available given supplies/time/frame of mind.

**Format warning:** rituals do NOT use a stat block. The heading is the name with its
dot rating inline — `CALLING THE FLAME'S BENEFICENCE •` — followed by free prose that
embeds cost, roll, difficulty and duration in sentences. Nothing is labelled. Parsing
them will look nothing like the Charm pipeline; expect to read each one by hand.

**There are exactly five, and that is the whole chapter** (human, 2026-07-29 — the
paste ends where the chapter ends; do not wait for more):
Calling the Flame's Beneficence •, Ritual of Dedicated Purification •, Art of the
Thrice-Warded Gateway ••, Dishonest Spirit's Rebuke •••, Warding of Undue Influence •••.

Counting the Rebuke's four separately-learned variants, that is **8 purchasable ritual
ids**. The Player's Guide plainly expects STs and players to write more (p.148: "there
are few constant rules, but there are guidelines") — the catalogue is a seed, not a
closed set.

**Decision (human, 2026-07-29): rituals are catalogue + custom.** Follow the editable
custom weapons/armor precedent — the catalogue is an autofill source and users may
author their own. Art specialties are likewise soft free text (the Backgrounds
precedent), which the book endorses outright.

Note **Dishonest Spirit's Rebuke is four rituals in one entry** ("one each for spirits,
demons, elementals and ghosts … each must be learned separately"). One printed entry,
four purchasable ids — the same shape problem as a Charm with per-element variants.

### Formulas / Procedures — rote recipes, 1 point each
Alchemical formula stat block (p.138): **Name / Alchemy (level) / Roll / Difficulty /
Cost of Materials / Effects / Addiction**. ~11 formulas printed in full.

## The wrinkle to build in NOW, not retrofit: orientation
Every ritual and formula has an orientation — **North, South, East, West or Realm**
(p.124). Foreign orientation is +1 difficulty at one region away (prep ×2) or +2 at
two regions (prep ×5, or ×2 prep and +1 Resources in a large city). A thaumaturge may
learn **multiple versions of the same spell**, and each extra version costs **1 point**
— "to completely master all versions of a given spell would cost four bonus points, in
addition to the normal cost of the spell."

So a character's ritual entry is NOT an id. It is `(ritual_id, set[Orientation])`, and
cost is `base(level) + (len(orientations) - 1)`. This is the one place the existing
"charms and spells are referenced by bare id" pattern does not carry.

**Build it compound from the start.** It is the same shape as `crafts: list[CraftRating]`
(focus + rating) and `colleges: list[CollegeRating]` — the established pattern for "the
character's holding carries more state than the catalogue id". We already know what the
retrofit costs, because Craft *was* one: converting a bare holding into a compound one
after the fact meant a save-format change, a cost-signature change, and fixture breakage.

Retrofitting orientation later would additionally corrupt the **XP log**, which is
append-only and is the baseline the snapshot is reconciled against. An entry reading
"bought ritual X" is ambiguous once orientations exist — buying the ritual costs
`2 + level`, buying another orientation of a ritual you already own costs `1`. Historical
entries could not be re-priced without guessing.

Scope note: orientation affects casting **difficulty** (+1/+2) and prep time, which is
dice resolution and therefore out of scope. Orientation is purely an **accounting and
display** concern here — which versions are owned, and what they cost. That is what
keeps it cheap.

## The Knowledge Background — a second, restricted BP currency
The biggest genuinely new engine concept, and the likeliest to get messy.

| Knowledge | Extra BP | Flaw cap |
|---|---|---|
| 1 | 8 | — |
| 2 | 14 | — |
| 3 | 20 | 15 |
| 4 | 26 | 15 |
| 5 | 32 | 20 |

Spendable ONLY on magical traits: Arts, Sciences, rituals, formulas, the asterisked
"Magic Backgrounds" (Artifact, Cult, Experience, Familiar, Library, Manse) and the
mystical Merits. Those asterisked Backgrounds **cannot be bought with ordinary
Background dots at all**.

**Do not build a parallel BP system.** `ChargenBudgets.background_rules` already
attaches per-splat mechanics to a Background *by name* (auto-rating, prerequisites,
per-dot pool cost, cap exemption — the Alchemical precedent). Knowledge needs two more
fields on `BackgroundRule`: a per-rating grant table and a spend-restriction tag. Then
`bonus_point_breakdown` grows a second column rather than a second implementation.

Related chargen mechanic, same shape: **"a mortal character can buy a talisman of any
level during character generation by spending one dot from the Artifact Background"**
(p.145).

## Scope line — resolution rules stay as display text
The bulk of CH3 is dice resolution, not character state: ward Strength/Durability
tables, the banishment table (roll/cost/successes/duration per entity class), summoning
difficulties, internal-alchemy failure, the expulsion extended roll, and the four ways
to pay a cost (Willpower ×3 motes, Exertion at 2 bashing/mote, Blood at 1 mote/health
level capped 6, chiminage at double).

None of it is derivable from a sheet, and building it means building a dice engine —
the same shape as the combat/attack derivation ruled out 2026-07-22. **Keep it as
display text on the Art/Science card.** The payment methods are play-state, and
play-state is validation-isolated by standing rule.

## Corebook chargen (`Exalted p103.png`) — the mortal baseline
- Attributes **6/4/3** heroic, **4/3/3** ordinary. Abilities **22** heroic, **16**
  ordinary. Backgrounds **5**. Virtues normal. Bonus points **21**.
- **No Caste.** Optional rule: one Favored Ability with the discount, which **must be
  ≥ every other Ability** the character has.
- **No Virtue Flaw and no Limit Break** — mortals do not suffer the Great Curse.
- **Cannot purchase Charms.** Essence 1, **cannot be raised with bonus points**;
  the 21 BP may go on any Trait except Charms and Essence.
- Artifact and Manse need ST permission.
- Essence 2 costs 10 BP / 20 XP and requires the Essence Mastery Merit; Essence 3
  costs 20 BP / 40 XP more and is the human ceiling. Unlocked mortals get a pool of
  `Essence + Willpower + Conviction + (highest Virtue × 2)`.

## Source status: COMPLETE
Nothing is outstanding. Arts, all four Sciences, the 14 alchemical formulas, all five
rituals, both cost tables and mortal chargen are in hand. The only deliberately skipped
item is the p.143 cross-reference table (below).

## Source oddities to preserve, not "fix"
- **Alchemy's six-dot ladder with no five-dot rung** — see the Sciences section. Human
  confirmed as printed.
- The Exceptional Equipment quality table prints difficulties 1, 2, 3, **5** — there is
  no 4. Author as printed.
- **"FORMULAS FROM OTHER WORKS" (p.143) — SKIPPED, human's call 2026-07-29.** A 16-row
  cross-reference table giving difficulty and Resources cost for substances whose
  effects live in other books (Manacle & Coin, Caste Book: Night, Savage Seas, Exalted
  core). We have the numbers but not the effects. Grab it later if wanted; author
  nothing now.
- The Thaumaturgy Merits (pp.120-122: Essence Awareness, Essence Mastery, Essence
  Recovery, Magical Attunement, Manse Attunement, Prodigy, the Oath merits, the Realm
  thaumaturge license) are in the paste but the human marked them *"feel free to ignore
  until M&F are in"* — they belong to the Merits & Flaws milestone, already scheduled
  after the non-Exalt splats.

## Phasing — where we are
1. ~~Models + the four data files.~~ **DONE**
2. ~~`ThaumaturgyState`, the orientation-aware entry, the cost ladder.~~ **DONE**
3. ~~BP breakdown, chargen gates, snapshot freeze, XP advancement + audit.~~ **DONE**
4. **UI: the fourth picker page with its four sub-tabs — the only piece left.**
   Consume `validate.thaum_purchases` / `thaum_purchase_bp_costs`; do not walk the
   five `ThaumaturgyState` lists directly, which is the whole point of the
   enumeration. Needs: the Arts/Sciences/Rituals/Formulas sub-tabs, a narrowing
   checkbox on Summoning aspects only, an orientation multi-select on rituals and
   formulas, and custom-ritual authoring (catalogue + custom, per the decision above).
5. ~~Formulas catalogue (14).~~ **DONE.** The p.143 cross-reference table stays skipped.
6. ~~Rituals catalogue (8 ids from 5 printed).~~ **DONE** — the chapter ends there.

Deferred by decision, not blocked: the Knowledge restricted-BP pool (M&F milestone).
Still open: **"Magic for Everyone" (p.115)** — the only open rules question left.
The Science rate is resolved (see above).
