# Thaumaturgy (Player's Guide CH3)

**STATUS: COMPLETE — engine and UI, browser-verified 2026-07-29.** Catalogue, models,
costs, BP breakdown, chargen gates, snapshot freeze, XP advancement and audit, plus the
ST Options tab, the picker's Thaumaturgy page, the sheet panel and the XP-ledger
labels. Clicked through by the human with no notes; the ST Options tab confirmed
working. Also covered by NiceGUI User-simulation render tests, which catch crashes and
missing content but are not a substitute for looking at it.
Source survey and architecture written up 2026-07-29; build started same day.
Source: `images/Mortals/Mortals & Heroic Mortals/Player's Guide.md` (pasted text,
pp. 11-12 + 96-150) and `Exalted p103.png` (corebook heroic-mortal chargen).


## ⚠ Rituals from the Book of Bone and Ebony — pp.118-119, authored 2026-08-14

BoBE's "NOT QUITE NECROMANCY" sidebar gives **mortal thaumaturges** three rituals for
necromancy-like effects: **Jawbone Echoes** (Ritual •, question a corpse),
**Garrote and Murder Mansion** (Ritual ••, animate one as a common zombie) and
**Obstinate Crumbs** (Ritual •••, a longer-lasting variant that degrades the corpse).
The `ThaumaturgicRitual` model already fits — it was written knowing the catalogue is
a seed the book expects to grow (PG p.148).

⚠ **My gap scan could not have found these, and the reason generalises.** The scan
keyed on printed stat blocks (`Cost:` / `Prerequisite Charms:` lines). **Rituals have
no stat block at all** — the model's own docstring says so: "the heading is the name
with its dot rating inline and everything else is prose." A stat-block detector is
blind to an entire content type by construction, not by accident. **Before trusting a
gap sweep, ask which record shapes it is structurally incapable of seeing.**

⚠ **Obstinate Crumbs has no heading of its own** — it is introduced mid-paragraph
inside Garrote and Murder Mansion's prose ("There is another ritual called Obstinate
Crumbs (Ritual •••)"). Even a *ritual-aware* sweep looking for headings misses it.

Also on p.118 and NOT authored: guidance for summoning a **nemissary** with the
existing Art of Summoning (difficulty 2 Intelligence + Occult to know whether a given
ghost can manipulate dead flesh; +2 difficulty to cast a general call). That is advice
on using a shipped Art, not a new entry.

## ⚠ "Formulas From Other Works" — PG p.143, authored 2026-08-14

Found by the transcribed-book gap scan. The Alchemy section ends with a table of
**16 compounds printed in other books**, and the PG supplies their mechanical values
itself: *"For the Storyteller's convenience, the difficulties and material costs are
listed here."* The section text supplies the two columns the table omits — *"a
formula's required Alchemy level is equal to its difficulty"* and *"all of these
substances are produced using an Intelligence + Occult (Alchemy) roll."*

**`effects` is the table's own Effects cell, cross-reference included.** The PG says
*"for precise effects, Storytellers and players should reference the original
works"*, so the pointer IS the printed effect text — writing more would mean
authoring from four other books when the page in hand already says what it says.
Books referenced: Manacle and Coin, Caste Book: Night, the corebook, Savage Seas.

⚠ **The gap this closed was sharper than a missing row.** Seven Bounties Paste and
Sweet Cordial already existed as **gear** — purchasable goods off Manacle and Coin
p.125 — but not as formulas. A thaumaturge could buy them and not brew them, with
Alchemy shipped as a Science. The other 14 were absent entirely.

### The two calls the human made

* **Greater Poisons and Lesser Poisons are ONE ROW EACH**, as the book designs them —
  each names several venoms across two books rather than being a single substance.
* **Variable material costs needed no new machinery.** Four rows print a
  region-dependent cost (`•• (••• outside the East)`) and two print a pointer
  (`Cost of firedust`, `Cost of pollen`). **`ThaumaturgicFormula.materials_raw`
  already existed for exactly this** — "authoritative when set, because one printed
  formula costs 'Equal to poison cost' rather than a number of Resources dots" — so
  the printed string goes in verbatim and `materials_resources` keeps the base
  number. A UI toggle was considered and is unnecessary: it would add per-character
  state to what is a display string.

### ⚠ Scope: this is REFERENCE, not creation

The build records what a formula is and whether a character knows it.
`difficulty`, `roll` and `materials_*` have **zero engine reads** — a grep confirms
it — and `thaum_actions.py` dispatches *learning* a formula, never brewing one.
Resolving a brew (rolling, spending the days, producing N doses, tracking potency
expiry) is simulation and stays out, the same bucket as dice rolling (decision 0009)
and training times. Authoring these 16 applied that boundary; it did not move it.

## Build log
Tests: `tests/test_thaumaturgy_data.py` (38, catalogue + cost ladder),
`tests/test_thaumaturgy_engine.py` (119, integration) and
`tests/test_thaumaturgy_ui.py` (67, presenter + purchases + render). Suite 873 -> 1097.

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
  Science's OWN `max_rating` (all four are 5; see the Alchemy note below).
- **"Magic for Everyone"** — `HouseRules` on `Character` (frozen into the snapshot),
  `magic_for_everyone_grant`, `magic_for_everyone_eligible`, and the `free_picks`
  argument to `thaum_purchase_bp_costs`.
- **The two optional p.113 chargen caps** — `restrict_chargen_ritual_level` and
  `restrict_chargen_science_rating`, checked by `thaumaturgy_chargen_issues`. Kept
  separate from `thaumaturgy_issues` because they are creation-time only: a Science
  raised past 3 with XP must not start failing them.
- **`HouseRules` is now the home for every Storyteller toggle**, not just
  thaumaturgy's — the Eclipse/Moonshadow chargen permission moved onto it
  (`st_foreign_charms`), with a load migration for existing saves.

**Not done:** nothing. The Knowledge restricted-BP pool is deliberately deferred to
the M&F milestone, and is the only thaumaturgy-adjacent work left anywhere.

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

### "Magic for Everyone" (p.115) — the optional free grant
Rulings from the human, 2026-07-29. **One ritual, formula/procedure or printed aspect
free per two dots of Occult** (`Occult // 2`), rituals and formulas capped at level 3,
**Arts and Sciences never free** ("only specialties in Arts, not the Arts themselves").

**Where the toggle lives — `Character.house_rules`.** It is a table choice, not a
character trait and not rulebook data, so it belongs on neither the RuleSet (static,
shared, read-only — it is the rulebook) nor a new settings file. `Character.play`
already set the precedent for an optional sub-document, and putting it on the save
means the accounting still adds up when the file moves to another machine.
`HouseRules` is a container from the outset so the next toggle needs no new field.

It is **frozen into the ChargenSnapshot** alongside the traits. Flipping it post-lock
would otherwise retroactively re-price a locked chargen — use `unlock_chargen` to
change it, the same as any other chargen correction.

**The grant does not follow Occult into XP** (explicit ruling). This falls out for
free rather than needing a mechanism: the allowance reads Occult from
`_chargen_source`, which is the snapshot once locked.

**Which purchases go free is COMPUTED, not tagged** — the dearest eligible ones
first, the player-favourable assignment this module already uses wherever a free pool
meets mixed rates, and consistent with the standing decision that the engine computes
the accounting rather than the user tagging each dot's currency.

**"(along with any appropriate specialties)" is deliberately unimplemented.** The
rules authority could not determine what the clause means (human, 2026-07-29) and
told me to ignore it rather than guess. Do not implement it on a hunch; it needs a
ruling first. Relatedly, "knowledge of one aspect" is read as a **printed** aspect,
so a player-invented narrower specialty is not eligible — that is the conservative
read of a rule that enumerates its own targets, but it is a read, not a quotation.

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
4. **"Magic for Everyone" (p.115) — RESOLVED 2026-07-29, BUILT.** The optional rule
   granting every character one ritual/formula/aspect per two dots of Occult (max
   level 3, aspects only, never Arts). Three rulings: it is a **toggleable table
   setting**; the sidebar's "(along with any appropriate specialties)" is
   **deliberately unimplemented** — the rules authority could not determine what it
   means, so do not guess; and the **grant does not follow Occult into XP**. See the
   Magic for Everyone section below.
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

### Sciences — RATED 1-5, each with printed dot descriptions
Costs: **5 BP first dot / 7 after; 7 XP first dot / current x 6 after** — see the
printing-error note in the Build log; not from either printed table.
| Science | Roll | Cost | Notes |
|---|---|---|---|
| Alchemy | Intelligence + Occult | normally none | Lab (Resources 3) required for effects 3+; ingredients cost `level - 1`. Internal alchemy: +2 difficulty, 1 Willpower, own failure table |
| Enchantment | Dexterity + Occult | 3 motes per level of effect, +1 Willpower | Time: 1 day per dot of effect |
| Geomancy | Perception + Occult | normally none | Time varies |
| Weather Working | Charisma + Occult | 2 motes per level, +1 Willpower at levels 4-5 | **always +2 difficulty**. Its 1-5 dot ladder is printed INSIDE the "Council of Winds" sidebar (p.149), not under the Weather Working heading — the paste is not missing it |

Chargen may be capped at "the third level of knowledge in any Science" (ST option,
p.113) — **BUILT** as `HouseRules.restrict_chargen_science_rating`, with its ritual
twin `restrict_chargen_ritual_level`; p.113's "and/or" is why they are two flags.
Enchantment 3 gates warding-talisman crafting (p.130 sidebar).

### Alchemy's printed SIX-dot rung is a typo for five — REVERSED 2026-07-30

**Superseded ruling.** From 2026-07-29 this file recorded the literal reading: the
printed ladder runs `• •• ••• ••••` then `••••••`, so Alchemy reached 6 with no five-dot
description, and the entry said *"Do NOT 'fix' this by renumbering the six-dot entry to
five."*

**That is now reversed** (human, rules authority, 2026-07-30, on a report from a player
familiar with the system — likely a designer answer this project has no copy of). The
printed 6 is a **typographical error for 5**. The top rung is authored at rating 5,
`max_rating` is 5, and Alchemy matches the other three Sciences exactly.

The internal evidence is what made the reversal believable, and it is worth keeping:
under the literal reading Alchemy was simultaneously the only Science with a *hole* in
its ladder and the only one whose formulas required a rung the book never describes —
Heavenly Transmutation Processes and Six-Demon Potion are both `Alchemy: •••••`, and "a
formula's required Alchemy level is equal to its difficulty" (p.143). Read as 5, both
anomalies vanish at once.

**This is a deliberate departure from the printed page**, which decision 0001 normally
forbids. It is recorded in the Science's own `description` field in
`data/thaumaturgy/sciences.json` so a future session reading the book cannot quietly
"correct" it back, and `test_the_typo_reading_resolves_every_alchemy_anomaly` pins the
reasoning.

What survives the reversal:
- **`Science.max_rating` stays per-Science.** All four now read 5, so it expresses
  nothing exceptional today — but the ceiling is rules data, not an engine constant, and
  the next book may need it.
- **The sparse dot-description list stays.** Descriptions are keyed by rating and the
  loader still tolerates a formula sitting at a rating with no printed rung. Nothing
  exercises that tolerance now; it costs nothing and the next book may.
- **The human's framing that `≤5` is a convention, not an invariant** (2026-07-29) is
  UNAFFECTED and still true: ratings above 5 genuinely exist in 1e (very old Exalts run
  Essence past 5). Do not treat a `≤5` bound anywhere in `models/` as load-bearing
  without checking. Alchemy is no longer an instance of that soft spot, but the soft
  spot is real.

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
- ~~**Alchemy's six-dot ladder with no five-dot rung**~~ — **NO LONGER AN ODDITY.**
  Confirmed as printed on 2026-07-29, then reversed 2026-07-30: the printed 6 is a typo
  for 5. See the Sciences section. Left here struck through because a reader who knows
  the book WILL notice the ladder and needs to find out why the data disagrees.
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
4. ~~UI — two pages, not one.~~ **DONE** (2026-07-29, browser-verified). Both shipped,
   plus two follow-ons that turned out to be part of the same job:
   **(a) the Storyteller-options tab** — `ui/storyteller.py`, a seventh builder tab
   ("ST Options", `gavel`). Renders `view.build_house_rules`, splitting TABLE-WIDE
   from PER-CHARACTER into two labelled sections, and goes read-only once chargen
   locks with Unlock named as the way to change a toggle. The Eclipse/Moonshadow
   permission moved here; the picker keeps only the Splat dropdown it unlocks, plus a
   line pointing at this tab when permission is missing.
   **(b) the fourth picker page** — `GROUPS["thaum"]`, four sub-tabs, built on
   `view.build_thaum_picker`. Real `ui.tabs` rather than the picker's usual
   `ui.toggle`, because a toggle's options are not separate elements and so cannot be
   clicked in a test. Narrowing checkbox on Summoning aspects only, per-entry
   orientation menu, custom-ritual authoring, and a "Bought" summary read straight off
   `thaum_purchases` / `thaum_purchase_bp_costs` so the free-grant zeroes shown are
   the ones actually charged.
   **(c) the read-only sheet** grew a conditional Thaumaturgy panel
   (`view.thaumaturgy_rows`) — otherwise everything above was purchasable but
   invisible on the sheet.
   **(d) the XP ledger** learned to name thaum purchases; without that branch those
   rows printed raw log targets like `thaum_arts`.

   Two things worth knowing about how this was built:
   - **The per-purchase gates were extracted into `engine/validate.py`**
     (`thaum_art_locked_reason`, `thaum_aspect_locked_reason`,
     `thaum_ritual_locked_reason`, `thaum_science_raise_reason`). They existed only
     inside `thaumaturgy_issues` before, so a picker would have had to reimplement
     them — the "no game logic in the UI" rule. The reason strings ARE the issue
     messages, and `thaumaturgy_issues` now calls these, so a greyed-out row explains
     itself in the same words the validator uses. `chargen=True` adds the p.113
     creation-only caps, mirroring `meets_spell_requirements(..., chargen=...)`.
   - **The purchase functions live in `engine/thaum_actions.py`.** They mutate the
     save, and several buy buttons legitimately share a label ("5 BP" is every Art),
     so click-testing one in particular is impossible — a module-level function makes
     them unit-testable. Each dispatches on the lock, returns the message to show, and
     raises `AdvancementError` on refusal.
     **⚠ Moved 2026-08-10** — they were module-level in `ui/picker.py` (the
     `ui/play.py` precedent), which was the wrong layer: they are game logic and never
     imported `nicegui`. The move was verbatim, `picker.py` re-exports every name, and
     no call site changed. Two things must not drift: the raised type stays
     `advancement.AdvancementError` (picker catches exactly that to notify), and
     `thaum_actions.raise_thaum_science` / `add_thaum_orientation` share a name with
     the `advancement` functions they call after the lock — the dispatcher and the
     priced purchase are different things, which is why this is its own module rather
     than more of `advancement.py`.
   - `build_picker` gained `initial_group=` so a caller can open the picker on any of
     its pages. Used by the render tests; also the obvious hook for deep-linking.
5. ~~Formulas catalogue (14).~~ **DONE.** The p.143 cross-reference table stays skipped.
6. ~~Rituals catalogue (8 ids from 5 printed).~~ **DONE** — the chapter ends there.

Deferred by decision, not blocked: the Knowledge restricted-BP pool (M&F milestone).
**No open rules questions remain.** The Science rate and "Magic for Everyone" are
both resolved and built.

## The Qt picker caught up — 2026-08-28

A shell-parity audit (`ui/view.py` and `engine/` names, by which shell references them)
found **three holes, all of them in this feature and all of them in the Qt picker**. The
webapp had had every one since Thaumaturgy shipped.

1. **Owned orientations were never shown.** `ThaumEntryRow.orientations` had zero readers
   in `qt/`, so a ritual you knew in the Realm version did not say so anywhere. Now a
   "Known in: …" line in the detail panel.
2. **A further regional version was UNBUYABLE.** `add_thaum_orientation` had no Qt caller
   at all: the orientation combo was hidden the moment a row was owned, on the reasoning
   that "an owned entry is dropped, not re-learned" — true of the *Drop* button and false
   of the flat-point second version (p.124). The combo now offers the regions still
   missing, beside an **Add version — N** button.
3. **No custom ritual could be written.** `buy_custom_ritual` had no Qt caller either.
   The Rituals sub-tab now carries a name + level + Add row under the list — ⚠ the ONE
   list in the picker that can be added to, because a ritual is the one printed thing the
   book asks you to write more of.

Two more things the fix turned up, neither in the gap list:

* ⚠ **`_refresh_thaum_selection` re-found the row and left the DETAIL TEXT stale.** It
  had always been wrong; nothing had made it visible, because no line in that panel used
  to change on a purchase. "Known in:" does.
* ⚠ **The Qt combo defaulted to NORTH**, being first in the enum, where the webapp's
  page-level picker has always defaulted to **Realm**. Same purchase, same price, in a
  tradition nobody chose. It defaults to Realm now where Realm is on offer.

**Rituals are also a custom-library kind now** — `custom/rituals.json`, authored on either
shell's Custom tab, merged into this catalogue and bought by id like a printed one. The
two shapes (library row vs inline `RitualEntry`) and why both stay:
`docs/status/custom-content.md`.

### Three MORE, from a second pass on the same panel — 2026-08-28

The first sweep compared `view`/`engine` NAMES by shell. A second pass, asked for as a
final check, compared **handler functions per tab pair** instead — a different axis, and
it found three more holes, all in this same picker:

4. **An Art's aspect could not be bought NARROWED.** `ThaumArtRow.allows_narrowing` and
   `ThaumSpecialtyRow.narrowed` had zero readers in `qt/`, and `buy_thaum_specialty` was
   called without the keyword — so Summoning's half-price option (p.127) was unreachable
   and a webapp-bought narrowed aspect displayed here as an ordinary one. Now a **narrow**
   checkbox beside the buy button, offered only on an unowned PRINTED aspect of an Art
   that allows it, plus a "Narrowed" line in the detail panel.
5. **A specialty of your own could not be written.** p.126 invites player-invented
   specialties in as many words; the Qt tree offered only the printed aspects (it
   displayed a custom one you already owned, which is what made this hard to see). The
   Arts tab now has an authoring row that acts on the selected Art.
6. **A Science could not be stepped back DOWN.** `lower_thaum_science` had no Qt caller,
   so a mis-click in chargen was unfixable without editing the save. A **Lower** button
   beside Raise, chargen only — ⚠ the engine function does not check the lock itself,
   because after the lock a rating comes back through the XP ledger's undo.

And a webapp bug the fix exposed:

⚠ **Ticking "narrow" halved what was CHARGED and left the button saying the full price.**
`ThaumSpecialtyRow.narrowed_price` now carries the second number — computed in `view.py`
from `engine.costs`, because a price is never a widget's answer — and both shells read it.
The Qt detail panel re-prices with it too, so the panel and the button cannot disagree.

⚠ **`_show_thaum_detail` is now the ONE renderer** for the panel (the Arts tree, the entry
lists, and the post-purchase refresh). The third of those was missing for as long as
nothing in the panel could change on a purchase — which stopped being true the moment it
grew "Known in:".
