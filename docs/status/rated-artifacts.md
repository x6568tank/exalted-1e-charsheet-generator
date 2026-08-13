# Rated artifacts — DONE (2026-08-02), browser-verified 2026-08-05, catalogue 2026-08-08

Individual artifacts are now rated objects. Two printed rules that could not be
expressed before are implemented: the loyal Abyssal's Artifact **budget** (E:Ab p.131)
and Damaged Artifact's **per-item** point limit (PG p.38), plus the one mechanical
effect of that Flaw this build can derive.

**2,065 tests** (was 1,835). Preflight clean; **browser-verified 2026-08-05** (clicked
through, no findings).

**The click-through wish is SHIPPED 2026-08-08:** the standalone-artifact rows' free-text
name input is now a **combobox fed from `data/artifacts.json`** — the first slice of the
rated-artifact catalogue, the ten Mountain Folk Technology-chapter artifacts
(`docs/status/mountain-folk.md`). The four of those ten that carry weapon/armour stat
blocks also got equipment-catalogue rows, and the same day the **six dual-nature
devices** (the four crossbows + Flamecaster + Pyromantic Grenade) shipped as catalogue
rows you can fund with *Resources OR Artifact* — see **The catalogue & the dropdown**,
**The dual-nature devices**, and **The description label** below.

## Why it came up

A6 shipped Damaged Artifact's point limit as "points ≤ Artifact rating − 1", checked
against the character's TOTAL Artifact Background. The printed rule is per-item — "the
rating of the artifact it modifies" — and the build had no individual artifacts to
point at, so a character with two Artifact rows (4 and 2) could take the three-point
Flaw against the two-dot daiklave because the check summed to 6.

Human's ruling (2026-07-30): worth closing, it should work on a specific Artifact.

## Source: Abyssal Artifact Background (E:Ab p.131)

Transcribed from `images/Abyssals/Traits/130-131.png`. `images/` is gitignored, so this
stays the only copy that travels with a clone. The Abyssal Artifact Background is **not
a cost curve** — it is a BUDGET of combined Artifact rating, plus a per-item ceiling:

| Rating | Name | Combined Artifact rating | Individual cap |
|---|---|---|---|
| × | None | — | — |
| • | Trinkets | no higher than 3 | — |
| •• | Sound Gear | no higher than 5 | none individually above Artifact 3 without ST permission |
| ••• | Well-Equipped | no higher than 7 | none individually above Artifact 4 without ST permission |
| •••• | Supremely Appointed | no higher than 10 | no limit on individual level, other than it cannot be N/A |
| ••••• | Divine Regalia | no higher than 13 | no limit on individual level, other than it cannot be N/A |

**The loyal/renegade split needed no new axis.** "This alteration of the Artifacts
Background only applies to those Abyssals who continue to faithfully serve their
Deathlords. Renegade Abyssals use the Artifact Background found in Chapter Four: Traits
of the main **Exalted** rulebook." That is the existing origin axis, and `_keyed_row`'s
cascade REPLACES rather than merges, so authoring the table on the `Abyssal` budget row
leaves `Abyssal:fugitive` on the core rules automatically. A test pins that.

Also on the page, still not required: artifacts of the dead "can be purchased for their
normal Artifact value, but… are of no use outside the Underworld"; all deathknight
artifacts are soulsteel unless the ST permits otherwise; no Abyssal in a Deathlord's
service may begin with Backing or Mentor (they use Liege instead).

This confirms the Player's Guide worked example under Damaged Artifact (p.38): a
combined rating of 4 needs Abyssal Artifact ••, hence "it would cost only two Background
points to obtain the wings with the Abyssal version of the Artifact Background".

## What shipped

### 1. Artifacts as rated objects — `engine/artifacts.py`

`ArtifactEntry` (name + rating + note) on `Character.artifacts`, for artifacts that are
**neither weapon nor armour** — the book's own worked example, the tattered wings of the
raptor, is one. Weapons and armour keep the `artifact_rating` they have always carried.

`artifact_items(character)` is **the ONE enumeration** that folds all three sources into
a single keyed list, the same shape as `validate.charm_picks`. Everything else — the
budget, the Flaw's limit, the sheet — reads it, so counting and display cannot disagree,
and re-entering a daiklave in `artifacts` (which would double-count it) is unnecessary.

Item keys are `"<source>:<lowercased name>"`. **Renaming an artifact changes its key**
and any purchase pointing at it stops resolving — deliberate, matching the soft-reference
treatment Backgrounds already get. A dangling key is REPORTED, never silently re-bound.

### 2. The budget — data, not code

`BackgroundBudgetTier` rows on `BackgroundRule.budget_tiers`, authored on the `Abyssal`
`chargen_budgets.json` row only. `individual_max: 0` means no per-item ceiling.
`validate.check_artifacts` is a no-op for every splat that prints no table.

**Errors vs warnings:** the combined budget is an error; the per-item ceilings are
**warnings**, because the page makes them ST-overridable ("without Storyteller
permission"). That is how every other soft printed limit here behaves.

### 3. ⚠ It runs on BOTH sides of the lock, and artifacts are NOT snapshotted

The budget is keyed to a Background that **experience can raise**, so the ceiling MOVES.
This follows `check_fetters_and_passions` exactly, and for the same reason: a
chargen-only check goes quiet at the moment the cap starts changing. Artifacts are
therefore deliberately absent from `ChargenSnapshot` — as weapons and armour always
were. **Do not add them to it.**

### 4. Damaged Artifact per-item — `MeritFlaw.points_limits` is now PLURAL

The Flaw prints **two** constraints that measure different things, and collapsing them
into one summed check with `offset: -1` is what caused the original bug:

* "may not gain more points from this Flaw than the rating of the artifact it modifies"
  → `per_entry: true`, `offset: 0`, read through `MeritFlawPurchase.artifact_key`;
* "characters must have at least one more dot of Artifact than the points obtained"
  → the summed Background, `offset: -1`, unchanged.

`points_limited_by` (singular) is gone; Known Anathema and Debt carry one-element lists.

### 5. The armour soak effect

Damaged Artifact's effect is mostly decision 0008 — a weapon losing damage or accuracy
is combat derivation, which this build does not do. **Armour soak is the exception**,
because `derive.soak` exists. `derive.damaged_armor` applies it, **after** the magical
material bonus (applying it first would let moonsilver repair the damage).

| Points | Printed | Armour soak |
|---|---|---|
| 1 | "minor damage… a point… an equivalent number of points" | −1 lethal, −1 bashing |
| 2 | "major damage, costing six points" | −3 lethal, −3 bashing |
| 3 | "near-total damage. The artifact is presently useless" | unusable — no soak at all |

The 2-point row is the human's ruling of 2026-07-30. **The 1-point row was flagged in
this doc as an inference and was confirmed by the human on 2026-08-02**: it scales the
same way, one point off each track, not one point shared. Soak floors at 0. Two
purchases against one item take the worse of the two rather than summing — "presently
useless" cannot be exceeded.

### 6. UI

* **The Advantages tab** gets an Artifacts panel (both regimes — artifacts are equipment
  and have never been XP-priced), printing the budget in its header (`7/7 combined —
  Artifact 3, Well-Equipped`) and naming the artifact weapons and armour it counted but
  does not edit.
* **The Damaged Artifact row** gets an artifact picker, gated on the catalogue's
  `per_entry` flag and **never on the Merit's id** (decision 0011).
* **The sheet** gets an Artifacts panel, marking a damaged item with its point value —
  its soak is already reduced above, and an unexplained low figure reads as a bug.

## The corebook default — the fourth rule, added 2026-08-13

⚠ **Amended the same day, after the browser: the allowance is ONE ARTIFACT PER
BACKGROUND ROW, not one per character.** A character holding Artifact •• twice holds two
artifacts. `background_best`'s docstring has said exactly that since 2026-07-31 — "two
Artifacts at 2 dots each are two artifacts, not one artifact at 4", which is why Damaged
Artifact reads the best row rather than the sum — and the first cut of this rule summed
the rows and demanded a single artifact, agreeing with neither ruling. `background_rows`
is the third reader of a repeated Background (sum / best / rows), and rows are matched to
artifacts LARGEST FIRST, which is exact rather than approximate: a smaller artifact fits
anywhere a larger one does.

**The lesson generalises past this rule:** when a new check reads a Background, ask which
of the three readings it needs — and grep the other two for a docstring that already
answered the question. This one was answered months earlier, in the codebase, and the new
code did not look.

**Human ruling, 2026-08-13:** *"Default Artifact core is one artifact per background.
The ones with different rulings (DB, DK, MF, Alchemical) are the ones that can have
multiple per background. If a splat has the Artifact background, and it isn't altered
in any way, then it uses the Corebook's."*

Resolved with the human before authoring, because "one artifact per background" has
three readings that differ materially: **exactly one artifact, rated no higher than the
Background** — not one per DOT, and not a combined-rating pool. Artifact ••• is one
3-dot daiklave; a 2-dot sword plus a 1-dot amulet is illegal. Reported as an **error**,
not a warning: the corebook ladder carries no "without Storyteller permission" clause,
which is the thing that made the Abyssal per-item cap a warning.

The printed ladder is the corroboration and is already in `data/backgrounds.json` —
every rung describes a SINGLE item ("A useful item, a weapon or suit of armor"), where
`background.artifact-dragonblooded` spells out pairs at every rung from •• up.

⚠ **What this fixed is the house bug in its purest form.** `check_artifacts` had
`if rule is None: return issues` — a splat with no `BackgroundRule` read as *no budget*
rather than *the default budget*. So the rule was implemented, tested and green, and
did not run for **plain Solar, Lunar, Sidereal, Ghost, Godblooded or the Abyssal
renegade** — most of the roster. A Solar could hold five 5-dot daiklaves on Artifact 0
in silence. Three tests asserted `== []` on exactly that behaviour, which is why the
suite never noticed: **the tests encoded the gap as the specification.**

* `engine/artifacts.uses_corebook_rule(rule)` is the ONE predicate — the validator and
  the on-screen budget line both call it, so they cannot disagree about which of the
  four rules is running.
* `validate._corebook_artifact_issues` raises `artifact-item-over-background` per
  oversized item and `artifact-over-background-dots` for a second item;
  `artifact-without-background` at rating 0, the same code the other branches use.
* The count is over `artifacts.artifact_items`, so an artifact **weapon** plus an
  artifact **armour** is a breach — that is the surface a player actually hits it on,
  and neither lives in `Character.artifacts`.
* The Advantages header now READS the rule (`Artifacts (1/1 — Artifact 4, one artifact
  rated up to 4)`) instead of the bare word "Artifacts". A limit whose first appearance
  is a validation error after the second pick is the "permission must move the offer as
  well as the bar" lesson pointed the other way.

### The Dragon King entry (PG p.175-176, authored 2026-08-13)

Found by auditing every splat after the corebook default landed: `chargen_budgets.json`
listed `background.artifact-dragonblooded` in the **Dragon-Kings** catalogue, so a
Dragon King read the DB entry — House assignments, the Realm's arsenal of First Age war
machines. The page shows they have their own:

> •**Artifact** — Weapons and tools, either vegetative, crystal or orichalcum.\*
>
> \* Minor Dragon King artifacts are relatively plentiful. Like the Terrestrial Exalted,
> the Artifact Background of the Dragon Kings provides twice as many dots worth of
> artifacts as normal. This Background provides the Dragon King with one artifact with a
> number of dots equal to the Background as well as two or more artifacts whose total
> number of dots add up to this number of dots. **(See E:DB, p. 157 for details.)**

Authored as `background.artifact-dragonkings` with `ladder_from:
background.artifact-dragonblooded` — the borrow is what the page itself instructs, and
the human confirmed keeping the DB rungs (2026-08-13). The footnote also corroborates
the flagship rule already enforced: *one* artifact at the Background rating, plus others
summing to it.

⚠ **The rule was right the whole time** — PG gives Dragon Kings the same doubled shape,
so the doubled budget, the flagship check and the per-item cap all produced correct
answers off a borrowed entry. Nothing could catch it but reading the page. The same
species as the Cult of the Illuminated Artifact (`illuminated.md`): a splat silently
served another's copy of a shared Background NAME.

⚠ **A false finding worth recording**, because the next reader will make it too: the
audit first reported the Yu-Shan two-dot cap on Celestial Manse and Salary as
unenforced, having probed `BackgroundType.max_rating` on the catalogue entry. Caps live
on **`BackgroundRule.max_rating` in `chargen_budgets.json`**, keyed by budget row, and
both Dragon-King rows carry them correctly.

### The artifact/gear link (2026-08-13)

Twenty catalogue artifacts are ALSO gear rows (Daiklave, Grand Daiklave, Myrmidon
Carapace…), because an artifact entry says what a thing IS and a gear row says what it
DOES. The artifact row carries no stats, so the natural way to play a daiklave was to
own it as an artifact AND add a weapon row to swing it — and both counted. Survivable
under a combined-dots budget; a **false error** under the corebook one-artifact rule.

* `Weapon.from_artifact` / `Armor.from_artifact` — the artifact key this row is the stat
  line of. Set once, by the grant, and editable by nothing on screen (the catalogue
  dialogs' own scar: a discriminator a widget could write).
* Picking an artifact GRANTS its stat line (`ui/advantages.grant_gear`), stamped with
  the key; `artifact_items` then counts the pair once.
* ⚠ The dedup **resolves at read time**, against the artifacts actually owned — not off
  the stored flag. An orphaned link (artifact renamed or deleted) makes the gear count
  on its own, so the failure mode is a visible artifact rather than a free one.
* ⚠ `set_weapon`/`set_armor` REPLACE the row with a catalogue copy. `from_artifact` has
  to be carried across like `quantity`, or re-picking the same daiklave from the
  dropdown silently drops the link and charges the budget twice.
* Deleting the artifact deliberately LEAVES the gear row. It may have been edited, and
  the orphan is counted rather than free.

`test_the_two_catalogues_agree_on_every_shared_artifact_rating` pins the invariant the
grant creates: the two halves sit side by side on screen, so a divergence would show one
daiklave priced two ways. Nothing enforces it at load; that test is the enforcement.

### Reading the Resources column — `tools/parse_resources_costs.py` (2026-08-13)

The corebook prices gear in DOTS, and the dot is a glyph the thirteen-cipher map does not
decode, so every cost read as U+FFFD. **It never needed decoding, only identifying:** the
dot is `(cid:10)` in `ZTR41CA.tmp,Bold`, and the count of that glyph inside the Resources
column IS the rating. This is a text-layer glyph count, exact — NOT the VLM dot-counting
the Lunar note warns about.

**`--verify` diffs the parse against the hand-authored values and is the point of the
tool.** Result: **42 agree, 0 disagree**, the other 19 authored costs being items from
other books. It also found a transcription typo — **Reinforced Buff Jacket was authored
Resources ••• and the page (p.331, "5/6 −2 2 ••") says ••**; corrected in `armor.json`.

Four parser bugs, each of which looked like working code:

1. **Whole-row dot counts are wrong and look right.** The weapon tables carry a
   `Minimums` column also drawn in dots, so summing a row charged a hatchet its Strength
   minimum as Resources. Only the diff against hand-authored values caught it.
2. **A header with no Resources column must CLEAR the band**, not inherit the previous
   table's. p.330 stacks the thrown table over the hand-to-hand table. This one hid
   behind a GREEN `--verify` — the correct row won the dict first.
3. **Splitting a name at the first digit-or-sign cuts hyphens**: "Seven-Section Staff"
   became "Seven" and vanished into the not-found list, looking like a page the parser
   never reached rather than a bug.
4. **"Resources Cost" is ONE word on pp.323-324 and TWO on the weapon tables** (a 1.2pt
   gap threshold). An exact-match test made the entire mundane-equipment table parse as
   zero rows — indistinguishable from a page range holding no table.

⚠ **Shields and helms have no cost in the COREBOOK** — p.334 describes Buckler,
Target/Tower Shield and the three helms in prose with no cost column. They are priced in
**Manacle and Coin p.124**, which the human supplied, and all six are now authored
(Buckler •, Target Shield ••, Tower Shield •••, Pot Helm ••, Slotted Helmet ••, Masked
Helm •••). **The lesson is the standing one, pointed at myself:** "the corebook does not
print it" is not "the line is unpriced", and I had written the stronger claim into this
file. A gap in one book is a question for the human, not a finding.

**Manacle and Coin pp.122-125 supersede the corebook as the base for the purchasing
catalogue** (the human's call, 2026-08-13), and the parser above is not needed for them:
that book has a clean text layer with real `•` characters. It carries the same tables
FULLER, plus two the corebook has not got:

* p.122 — the Resources ↔ cash conversion (jade and silver);
* p.123 — Clothing & Jewelry, Slaves & Animals, Ships & Property, with Peasant/Fine
  clothes and per-week stabling rows the corebook omits;
* p.124 — Weapons, Armor, Helmets & Shields **in full**;
* p.125 — **Everyday Wonders** (prayer papers, sacrifices, healing pastes, talismans)
  and **Greater & Lesser Wonders**.

The two books AGREE on all 39 shared rows (0 disagreements), so there is no
reconciliation to do — and M&C independently confirms the Reinforced Buff Jacket
correction above.

⚠ **A ruling is needed before authoring p.125.** It prices ARTIFACTS in Resources —
"Daiklave ••••", "Grand Daiklave •••••", "Hearthstone Amulet •••" — where the artifact
catalogue rates the same daiklave **Artifact ••**. Those are two different currencies
(what the Background rates vs what cash buys), and taken literally the page lets a
character BUY an artifact outright, which sits directly on top of the corebook
one-artifact rule ruled the same day. Do not author p.125 until the human has ruled on
whether Resources can buy artifacts at all.

## Traps recorded

* **`points_limited_by` → `points_limits`.** Anything reading the old singular field is
  broken; there was exactly one read site and three data rows.
* **`derive.soak`'s `ruleset` is still optional**, and now omitting it silently returns
  UNDAMAGED soak as well as unenchanted. A test pins both answers so the docstring
  warning cannot quietly stop being true. This is the sibling trap the memory file
  names — every omission is a wrong answer rather than a TypeError.
* **The artifact picker is the empty-options crash class.** A `ui.select` whose value is
  not among its options raises at BUILD time and takes the tab down with its siblings.
  Two render routes pin it: a Damaged Artifact held with no artifacts owned, and a
  stored key left stale by a rename.

## The third cap — DONE, and it deliberately contradicts the book

**"or the number of Background and/or bonus points spent obtaining the artifact,
whichever is less" (PG p.38)** is implemented as `engine.artifacts.acquisition_cost`,
the `measure: "acquisition_cost"` limit on Damaged Artifact. It was briefly written off
as un-computable; that was wrong, and working the page's own example through is what
showed it. The rule is:

> **`acquisition_cost(item)` = the cheapest Artifact Background rating that would permit
> that artifact ON ITS OWN.**

Which the Artifact Background's own text already describes for three splats, and the
p.131 table for the fourth:

| Splat | Printed | Cost of a rating-R artifact |
|---|---|---|
| Solar / core | one dot buys one dot of artifact | R |
| Dragon-Blooded | "receive twice the dots' worth of artifacts" | ⌈R/2⌉ |
| Alchemical | "receive THREE dots of artifacts per dot bought" | ⌈R/3⌉ |
| Abyssal (loyal) | the p.131 budget table | the cheapest row that permits it |

Two rulings from the human (rules authority, 2026-08-02):

1. **Cost is per item in isolation.** Owning a ring alongside a daiklave does not make
   the daiklave dearer. Nothing printed apportions a shared budget across its contents.
2. **⚠ The table beats the worked example.** p.38 prices the 4-dot tattered wings at two
   Abyssal Background points, reading only Sound Gear's "combined no higher than 5" and
   ignoring its "none individually above Artifact 3" — its own table, one line up. Under
   the table the wings need Well-Equipped and cost **three**. The human's ruling: *"if
   the book disregards its own table, fuck em."* So **this build answers 3 where p.38
   says 2**, knowingly. `test_acquisition_cost_respects_the_individual_cap` pins it and
   says why; do not "fix" it toward the printed example.

**The trap this hit:** `rating_per_dot` had to be authored on **all 13** Dragon-Blooded
budget rows, not just the base one — `_keyed_row`'s cascade REPLACES rather than merges,
so every origin and upbringing beneath it would otherwise have silently lost the
multiplier. That is the `highest_magic_circle_id` trap wearing a different hat, and
`test_the_multiplier_survives_every_dragonblooded_origin` walks all of them.

Everything on the page is now closed.

**Left open elsewhere, deliberately:** the Dragon-Blooded and Alchemical multipliers are
authored for acquisition cost ONLY. Neither splat gets a *combined* artifact budget
enforced, because neither book prints one — "twice the dots' worth" caps nothing on its
own. If that should become a budget too, it needs a page.

## The catalogue & the dropdown (2026-08-08)

The 2026-08-05 click-through's one wish — a drop-down of the artifact catalogue for the
standalone-artifact rows — needed a catalogue to exist first. The Mountain Folk source
pages landed on 2026-08-08 (`images/Non-Exalts/Mountain Folk/CH 6 - The Mountain
Folk.md`, Technology chapter pp.279-283), which prints **ten rated artifacts**. The
human's ruling: **all ten go in the standalone catalogue, AND the four with
weapon/armour stat blocks also get equipment-catalogue rows** — so a player who wants
the stats can add them as weapons/armour, and the standalone catalogue is complete
either way.

### `data/artifacts.json` — the new catalogue

New frozen model `ArtifactType` (id/name/rating/rating_notes/description/source/tags)
on `RuleSet.artifact_catalog`, loaded exactly like weapons/armour (no link-check —
entries are self-contained). Ten entries, ids `artifact.mountain-folk.<slug>`, every
name, rating and description from the page text (pp.279-283):

| Artifact | Rating | Source |
|---|---|---|
| Essence-Scrying Visor | • | p.279 |
| Hammerfist Bracer | • | p.279 |
| Mask of Pure Breath | • | p.279 |
| Skirmish Pike | • | p.280 |
| Echo Jewel | • or ••• | p.280 |
| Talisman of Suspended Evocation | • to ••••• | p.281 |
| Dragon Sigh Wand | •• | p.281 |
| Essence Pulse Grenade | •• | p.282 |
| Shieldstone Gauntlet | •• or ••• | p.282 |
| Myrmidon Carapace | ••• | p.283 |

### The four gear entries

The four stat-blocked items also live in the equipment catalogues, with their stats from
the chapter's own tables: **Skirmish Pike** (Spd +4, Acc +1, Dmg 4L piercing, Def +1,
min Str 1, Art 1, attune 5 — the standard table prints no Rate; Rate 3 is from the
Exalted Power Combat table), **Dragon Sigh Wand** (Acc +1, Dmg 12L, Rate 1, Range 30,
Art 2, attune 5), **Essence Pulse Grenade** (Acc +0, Dmg 10L, Rate 1, Range 20, Art 2 —
no commit cost printed) in `weapons.json`, and the **Myrmidon Carapace** (soak 8/8, mob
−1, fat 1, Art 3, attune 5) in `armor.json`. **⚠ The carapace's weight class is not
printed** — assigned **Medium** by comparison with the other Medium artifact armors;
flagged here for the human at review.

### The dropdown

`_artifacts_panel()`'s name field is now a `DescribedSelect` (option tooltips carry the
entry's rating + description) with the Background-picker guards: `_opts_with` folds an
off-catalogue stored name into the options so existing saves keep rendering (the
empty-options crash class), and `with_input=True, new_value_mode="add-unique"` keeps the
name free text. Picking a catalogue entry **autofills name + rating** (mirrors
`set_armor`); typing renames and preserves the rating. The header refreshes in place —
**and the rating `ui.number` is pushed directly**, because the header-only refresh
invariant means the body (and the number) must survive; leaving the number stale after
an autofill would desync it from the model. The combobox is labelled **"Artifact name"**
so the test that finds the Damaged Artifact picker by `label == "Artifact"` stays
unambiguous.

**Accepted behaviour:** entering a gear item both as a weapon/armour AND as a standalone
artifact counts it twice toward the budget — the same contract free text already had; no
cross-catalogue dedup.

### The description label (2026-08-08)

Each standalone-artifact row now prints a **persistent description under the row**,
mirroring the Background `bg-desc` pattern: a `ui.label` with `data-testid="art-desc"`,
synced on pick/rename without rebuilding the panel. A catalogue name shows the entry's
page-vetted description; an off-catalogue name hides the label. Tests find it by
`data-testid`, never page text — the dropdown's option tooltips also carry the
description, so a bare `should_see` could pass against code with no label at all.

### The dual-nature devices (2026-08-08)

The four crossbows (**Crossbow ••, Mechanized •••, Assault ••, Onslaught •••** — MF
p.278) print a "Resources/Artifact" column, and the **Flamecaster** and **Pyromantic
Grenade** print Resources ••• only. All six shipped as ordinary equipment-catalogue rows
(`weapon.mountain-folk.*`, the archery/thrown devices on the Archery skill) carrying
**both** minima.

**How a player picks the funding — human's ruling 2026-08-08 (no toggle):** the
Art and Res fields in the Edit-stats expansion already ARE the choice. The player sets
the Background that was paid and zeroes the other: an Artifact-funded crossbow keeps
`artifact_rating` 2 (and counts toward the budget); a Resources-funded one drops it to 0
(and is mundane gear — `artifact_rating` 0 is the mundane default the enumeration
already skips). The catalogue row's two numbers are the printed minima, not a state to
choose between. A first pass shipped a `cost_background` field + "Funded by" select and
the click-through found it unnecessary; both were removed, and the edit boxes are the
surface.

* **⚠ Flagged, not invented:** the Flamecaster and Pyromantic Grenade have **no printed
  Artifact cost** — their `artifact_rating` mirrors the Resources value (3) only so the
  Art field can be used to fund them either way; the notes say the ST sets the real
  value. The Myrmidon Carapace's weight (Medium) remains the other flagged assignment.
* `resources_cost` stays **display-only** — there is no Resources-Background enforcement,
  any more than there is for ordinary mundane gear.

Still a follow-up: the **wider cross-splat catalogue** (the discovery layer — 417
1E artifacts, per-book page lists — is in `docs/status/artifact-backlog.md`).

### The alchemical goods — deliberately NOT modelled (ruling 2026-08-08)

Godstrike Oil, Pyromantic Gel and Synthetic Leather (MF pp.275-277) were authored
as a `GoodType` catalogue and **removed the same day on the human's ruling**. The
reason generalises: **every catalogue in the build feeds a mechanical read site** —
magical materials → `derive`, artifacts → the Artifact budget + dropdown, weapons/
armour → the sheet. The goods feed nothing: no owned-list, no derivation, no
validation, and a "reference card" of them would be the first data in the build with
no mechanism behind it — the precedent that opens the "why not firedust, lanterns,
rations?" flood. The full page transcription is preserved in
`docs/status/artifact-backlog.md` (as its one fully-sourced authorable slice, now
closed). If a real "possessions" surface is ever built, the source is there.

## The 2026-08-08 castebook batch — the "12 genuinely-new" backlog entries

The `artifact-backlog-entries.md` checklists (regenerated 2026-08-08) marked 40
entries authorable-now with pages on disk: Caste Books Dawn/Night/Zenith (11+8+5) and
the core-book subset (16). Of those, 28 already had rated-equipment rows from the
Solar-castebook gear work — the **12 genuinely-new remainder** were the gap the
catalogue's own checklist (`cat` build flag) was built to expose. They were addressed
2026-08-08, all from page text transcribed via the VLM (the `_CASTEBOOK_PENDING.md`
note confirms the 12 were deliberately skipped during the castebook gear work —
"ignore anything that isn't a weapon or armor" — which is exactly the hole this fills).

### Ten catalogue entries (ids `artifact.castebook-<dawn|night|zenith>.<slug>`)

| Artifact | Rating | Source |
|---|---|---|
| Shield Bracer | •• | Caste Book: Dawn p.78 |
| Map of Azure Victory | ••• | Caste Book: Dawn p.78 |
| Chariot of Aerial Conquest | ••••• | Caste Book: Dawn p.78 |
| Arrows of Distant Death | ••• | Caste Book: Dawn p.81 |
| Spider Grippers | •• | Caste Book: Night p.79 |
| Belt of Shadow Walking | ••• | Caste Book: Night p.80 |
| Circlet of Spirits | ••• | Caste Book: Night p.80 |
| Death Shield Ring | ••• | Caste Book: Zenith p.80 |
| Ring of the Deliberative | •••• | Caste Book: Zenith p.81 |
| Hooked Daiklaves of Dual Prowess | •••• | Caste Book: Night p.81 (also a weapon row, below) |

Every description is a short summary of the transcribed page text (2-4 lines, the
established rated-artifact style). **Four page-vs-guide discrepancies resolved with
the page as authority:**
- **Ring of the Deliberative ••••** — the page heading prints four dots; the guide's
  ••••• is a 2e-derived value and is wrong for 1e. Pinned by a test.
- **Hooked Daiklaves of Dual Prowess •••• — human ruling 2026-08-08.** The page is
  internally inconsistent: the heading prints **••••**, the Artifact-table column
  prints **•••••**. The human checked the page ("It says 4 dots Artifact") and ruled the
  heading canonical, so the catalogue AND the weapon row both carry **4**; the table's
  ••••• is treated as a misprint, with the stat block's other columns unaffected.
  Pinned by tests.
- **Circlet of Spirits** — the VLM dropped a `t`; body text and the guide agree.

### Two rated gear rows (in `weapons.json`)

- **Hooked Daiklaves of Dual Prowess** — Spd 2, Acc 2, Dmg 5L, Def 5, Rate 2, Min Str 2,
  Dex 3, MA 3, **Art 4** (the heading — human ruling 2026-08-08; the table's Artifact
  column misprints •••••), attune 8 (4 per blade), with notes carrying the stat line +
  the ruling. The light-tags precedent is the Lightning Torment Hatchet's
  `(Thrown)`/`(Melee)` split.
- **Direlance** — Spd 6, Acc 2, Dmg 5L, Def 0, Min Str 1, Art 2 (core p.342 Daiklave
  Table), attune 0. **⚠ Two flags:** the weapon's description page (core p.341) is NOT
  on disk — the crop of p.341 is the Artifact Materials section — so there is **no
  catalogue entry for the Direlance** (blocked), and the p.342 table prints no attunement
  cost. The lance-on-a-charge stat line from the table is preserved in the notes.

### Slayer Khatar — fully blocked

The guide lists the Slayer Khatar at core p.344, but the on-disk crop of p.344 is the
**Lightning Torment Hatchet**; p.327's weapons table carries only the mundane Khatar.
Neither description nor stat block is on disk, so **nothing is authored** and the
checklist flags it `—`. Sync p.344's neighbor pages to unblock.

### What this changed

- `data/artifacts.json`: 10 → **20 entries**; `weapons.json`: 96 → **98**.
- The `artifact-backlog-entries.md` checklists now treat `data/artifacts.json` as a
  read site — the ten Mountain Folk entries also flip from `—` to `cat` (they were
  authored but the checklist couldn't see them).
- **2,065 → 2,068 passing** (+3 tests: two data pins in `tests/test_data.py` — the
  catalogue load test asserting all ten ratings + the two rating disputes, and the gear
  rows test pinning the Hooked Daiklaves/Direlance stat blocks + asserting the two
  blocked core items stay out of the catalogue — and one UI test in
  `tests/test_rated_artifacts.py` that the combobox offers the ten new names).
- The 40-entry "authorable-now" remainder is now 29 rated + 9 catalogue-only + 2 fully
  blocked (Direlance's catalogue entry and Slayer Khatar).

## The 2026-08-08 evening batch — Caste Book Twilight (12) + Eclipse (8)

The same day's morning batch (above) was the Dawn/Night/Zenith slice of the
authorable-now backlog. That evening the **Caste Book: Twilight and Eclipse pp.79-81
pages** — which the morning checklist had marked NOT on disk — were found/transcribed
via the VLM pipeline (qwen3-vl, human-vetted; `.md` pages + PNGs in gitignored
`images/Solars/Castebooks/{Twilight,Eclipse}/`), making another **20 entries
authorable, and all 20 were authored** (commits `42be3f7`, `18b0086`). This closed the
backlog: **no on-disk artifact remains unauthored.**

### Twenty catalogue entries (ids `artifact.castebook-<twilight|eclipse>.<slug>`)

| Artifact | Rating | Source |
|---|---|---|
| Bracer of the Hawk | •• | Caste Book: Twilight p.79 |
| Whistle of Ghost Summoning | •• | Caste Book: Twilight p.79 |
| Seed of the Immaculate Blood | •• | Caste Book: Twilight p.79 |
| Cup of Flowing Blood | ••• | Caste Book: Twilight p.79 |
| Eye of the Living Earth | ••• | Caste Book: Twilight p.80 |
| Ghost Seeing Blindfold | ••• | Caste Book: Twilight p.80 |
| Honey of the Bees of Zarlath | ••• | Caste Book: Twilight p.80 |
| Mirrors of Illusion Shattering | ••• | Caste Book: Twilight p.80 |
| Scabbard of the Living Weapon | ••• | Caste Book: Twilight p.80 |
| Sorcery-Capturing Cord | ••• | Caste Book: Twilight p.81 |
| Veil that Holds Back Time | •••• | Caste Book: Twilight p.81 |
| The Jackal's Skull | •••• | Caste Book: Twilight p.81 |
| Lotus Blossom Cup | • | Caste Book: Eclipse p.79 |
| Player's Mask | • | Caste Book: Eclipse p.79 |
| Silver Quill | • | Caste Book: Eclipse p.79 |
| Seven Jewelled Peacock Fans | •• | Caste Book: Eclipse p.80 |
| Silken Armor | ••• | Caste Book: Eclipse p.80 |
| Solar Seal | • | Caste Book: Eclipse p.80 |
| Folding Ship | •••• | Caste Book: Eclipse p.81 |
| Iron Horse | •••• | Caste Book: Eclipse p.81 |

**Rating disputes, page as authority (all pinned by tests):**
- **Bracer of the Hawk ••** — the page prints two dots; the guide lists •. Human
  confirmed 2026-08-08.
- **Veil that Holds Back Time / The Jackal's Skull ••••** — the VLM's first pass
  misread •••••; the page prints four dots (blob-count verified). The guide was right.
- **Variant ratings in `rating_notes`:** Sorcery-Capturing Cord (••• emerald / ••••
  sapphire / ••••• adamant), Seed of the Immaculate Blood (•• base, ••• red seeds),
  Silver Quill (• base, •• self-writing quills).

**Audient Brush is BLOCKED, not authored — a phantom index row.** The guide's `cb_e`
row lists it at Caste Book: Eclipse p.79, but the book contains **no** Audient Brush
(full 98-page word-sweep, 2026-08-08). The real p.79 artifact list is Lotus Blossom
Cup, Player's Mask, Silver Quill. The `artifact-backlog-entries.md` checklist marks it
`blocked`, and `test_artifact_catalog_loads_the_twilight_and_eclipse_backlog` asserts
it stays out of the catalogue.

### What this changed

- `data/artifacts.json`: 20 → **40 entries** (10 Mountain Folk + 30 castebook).
- The `artifact-backlog-entries.md` checklists: `cb_t`/`cb_e` Build column → `cat`;
  the guide's "Daiklave, Hooked ••" mislabel on `cb_n` marked `cat` (Night p.81's
  *Hooked Daiklaves of Dual Prowess* is already in the build under its real name).
- **2,068 → 2,070 passing.** ⚠ **The recorded 2,068 was already stale by one when
  this batch landed** — the true pre-batch base was **2,069** (af8051f collected 2,069),
  so the +1 test here (`test_artifact_catalog_loads_the_twilight_and_eclipse_backlog`
  in `tests/test_data.py`, pinning all 20 ratings + the three disputes + Audient Brush's
  absence) landed at **2,070**, not the "2069" the commit message claimed. The
  combobox test in `tests/test_rated_artifacts.py` gained two names.
- **Not browser-verified.** The catalogue pin test and combobox-offers-the-names
  assertions are green, but the 20 new names have not been clicked through the
  Advantages tab's combobox.


## Gear `resources_cost` — the Resources System (DONE 2026-08-12, browser-verified)
**Core p.325, the "THE RESOURCES SYSTEM" sidebar**, is the whole rule. Items carry no
money price; they are rated in the Resources dots needed to buy them. Cost **lower** than
the rating is an out-of-pocket expense ("as many of the items as she wants"); cost
**equal** is "a serious expense. When she buys it, she lowers her Resources rating by 1
until it is increased through roleplaying"; cost **greater** is unaffordable. The
equipment tables that follow (weapons p.330 onward, armour after) each carry a legend
line: "The minimum Resources the character must have to purchase the item."

**It shipped as a HINT, not a validation** (human's ruling 2026-08-12), and the reason
generalises: **the printed rule contradicts an ownership invariant in its own middle
clause.** Buy at cost EQUAL and the book leaves the character holding an item that costs
more than she now has. Gear also arrives as loot and gifts. A static "no item above your
rating" check — the shape `engine/artifacts.py` uses for the Artifact budget, which was
the assumed precedent — would flag both as errors. The Artifact budget was the wrong
model, and the tell was in the rule's own text.

- `validate.gear_affordability(character, cost)` → `"easy"` / `"serious"` /
  `"unaffordable"` / `""` (no printed cost — 56 of 122 rows, and a missing price is not
  a free item). It reads the HIGHEST Resources row, not the sum: Resources is one
  lifestyle rating, unlike Connections where the sum is the printed measure.
- The weapon and armour catalogue dialogs print the clause per row and FADE what the
  character cannot afford. Faded rows stay **pickable** — the sheet is a tracker, and a
  character can be given what she could not buy.
- The drop-by-one on an equal-cost purchase is **deliberately not applied** (human
  declined it): the app cannot know a purchase happened.
- **Nothing validates ownership**, and a test asserts that on both sides of the lock.

⚠ **The other 63 `resources_cost` values are still unattributed.** The human verified
Self/Long/Composite Bow at 1/2/3 against the p.330 table and those three now carry a
`source`; every other row's cost has no book or page behind it. The extracted corebook
cannot settle them — the Cost column is dot glyphs that did not survive the font cipher,
and p.330 carries an explicit `GARBLED … NOT authorable without a human read` marker. The
hint makes wrong values MORE visible, which is the argument for shipping it first, but
the values are a page-blocked job.
