# Merits & Flaws

**Status: DONE (2026-07-30) — engine, UI, and the WHOLE chapter authored. 100 Merits &
Flaws: the 11 Thaumaturgy ones (`thaum.*`, pp.120-122) and all 89 of the general
chapter (`mf.*`, pp.16-41). BROWSER-VERIFIED 2026-07-31** — every A-list mechanism
clicked through; see the A-list section below. 290 tests in
`tests/test_merits_flaws.py`.

**2026-08-05** — the two Dragon-Kings-era hooks shipped: Prodigy's DK/God-Blooded rate
(`cost_options_by_exalt_type`) and the PG p.114 mortal-god note (a UI note at the
mortal's Essence-3 ceiling; see "Rulings and traps"). Suite at **1,972 passing**.
**Not browser-verified** — a click-through of the Prodigy picker on a Dragon-King and a
God-Blooded, and a pool-unlocked mortal at Essence 3 seeing the note, is still owed.

M&F were ripped out 2026-06-15 because the old implementation scattered their
mechanical effects across every file they touched. **Decision 0011** is that they come
back as one centralized calculation. This is that calculation, built early — ahead of
the remaining non-Exalt splats — because mortals shipped 2026-07-30 with **no route to
magic at all**, and that route runs entirely through Merits.

## Why this slice, and why now

The 11 **Thaumaturgy Merits** (Player's Guide pp.120-122) were already in the vetted
source paste; a prior session recorded the human saying *"feel free to ignore until M&F
are in"*, so they were skipped deliberately, not for want of pages. They are also
exactly the mortal magic-access set. The general chapter (PG p.16 onward) was a 4-line
header stub when this was built.

So this is not "M&F, partially done" — it is the mortal unlock, delivered through the
architecture decision 0011 demands, with the general chapter dropping into the same
data file and the same calc.

## The architecture — read this before adding a Merit

Three pieces, and the separation is the entire point:

| Piece | Holds | Never holds |
|---|---|---|
| `rules.MeritFlaw` (data) | printed text, cost, prerequisites, category | anything about what a Merit DOES |
| `engine/merits.py` | the id→effect mapping, and the only mention of any Merit id | rules that belong to a caller |
| `MeritEffects` (its return) | effects keyed by EFFECT, not by Merit | |

**No module outside `engine/merits.py` may name a Merit id.** Callers read
`MeritEffects` fields. `test_no_module_outside_engine_merits_names_a_merit_id` enforces
this by grepping the package, and it is the single most important test in the module —
if it ever fails, move the branch into the calc and give `MeritEffects` a new field.
Do not add an allowlist.

`MeritEffects` is keyed by effect deliberately: the general chapter is far broader
(social, physical, supernatural) and will attach new Merits to **existing** effects far
more often than it invents new ones.

A Merit with no mechanical effect — most of them — needs a **data row only**.

## What the 11 do

Authored: Essence Awareness, Essence Recovery, Magical Attunement, Manse Attunement,
Celestial Travel Permit, The Flow of Essence, Essence Mastery, Holy Mien (Merits);
Sheltered Upbringing, Dark Magics, Oathbound Magic (Flaws).

Only **three** have effects this engine can express. The rest are narrative and are
reported in `MeritEffects.narrative_only` so the UI can say so rather than silently
ignoring them:

* **Essence Awareness** (3) — unlocks the mortal Essence pool. The printed 1/3-free,
  2/3-on-a-Willpower-roll split is not modelled: we do not roll dice (decision 0009),
  so only "some access" vs "full access" is distinguished.
* **Essence Mastery** (5, prereq Awareness) — full pool; raises `essence_cap` 1→3;
  opens **Terrestrial Martial Arts** and **Terrestrial sorcery**.
* **Oathbound Magic** (variable Flaw) — grants bonus points.

Several are narrative *only because this build has no such system*, not because the
page is vague: Essence Recovery sets a regeneration rate, Magical/Manse Attunement
govern artifact and Manse attunement. If attunement is ever modelled, they attach to it.

## Rulings and traps

* **Spirit Walking stays barred.** Essence Mastery opens Terrestrial MA "except the 2nd
  charm in Enlightening, Spirit Walking" (human, 2026-07-30) because it is what grants
  Celestial Martial Arts. **The tier machinery does not catch this** — Spirit Walking is
  `open_to_all`, so it would otherwise come free with the style. Its prerequisite,
  Spirit Sight, IS legal and simply dead-ends; the human confirmed "just the one Charm".
* **A Merit-granted circle needs no initiating Charm.** Sorcery normally requires one,
  and mortals may hold no Charms, so `accessible_circles` unions
  `MeritEffects.granted_circles` directly. Terrestrial only.
* **Essence 3 is printed, not inferred**: "the limit of human potential — mortals that
  exceed Essence 3 become gods, in the same way the God-Blooded do" (PG p.114). **DONE
  2026-08-05** — human ruling: the clause is a UI note, not a transition mechanic. The
  cap stays enforced (`essence_cap_override` 3; the mortal XP table prices nothing past
  3), and the editor shows the book's clause beside the Essence track when
  `essence_cap_override` is set and the mortal sits at it. The trigger is the OVERRIDE,
  not `essence_pool_unlocked` (review fix 2026-08-05): an Awareness-only mortal has the
  pool unlocked but no override — real ceiling 1 — and must not be blamed on the god
  clause. **Do not build a "mortal → god" splat transition without reopening this.**
* **The unlocked mortal pool needed a model extension.** PG p.114 gives
  `Essence + Willpower + Conviction + (highest Virtue × 2)` — a NAMED Virtue added flat
  alongside a scaled highest-Virtue term, which `EssencePoolSpec` could not express.
  Added `personal_named_virtue`/`_coeff` and `personal_virtue_mode`/`_coeff`, plus
  `ExaltDefinition.unlocked_essence` to hold the post-unlock spec. Selected by
  `derive.essence_pools` via the calc, never by splat name.
* **A Flaw's value raises `available`, not the spend.** Modelled on the allowance rather
  than as a negative BP line, so a Flaw can never silently pay for an overspend
  elsewhere in the same total.
* **Oathbound Magic's prose and its worked example disagree.** The prose says each
  stacked oath "is reduced in value by the total number of oaths" (two moderate oaths →
  3 + 1 = 4); the worked example says 3 + 3 − 1 = **5**. The example is implemented and
  pinned by a test. Flagged rather than silently reconciled.

## Open — needs the general chapter

* **Do non-Oathbound Flaws grant bonus points? — ANSWERED, not yet implemented.** The
  general chapter landed 2026-07-30 and its opening paragraph (PG p.16) settles it:
  "Flaws work in reverse, imposing disadvantages in exchange for additional bonus points
  to spend on other Traits. Characters may only receive up to **10 extra bonus points
  from Flaws**, regardless of the number." So every Flaw's printed value is a grant, and
  there is a hard cap of 10 across all of them.

  **Today the calc grants points for Oathbound Magic only, and applies no cap** — it was
  written before the chapter arrived and deliberately did not guess. Two changes are
  needed in `merits_and_flaws_calc`: grant every Flaw's value, and clamp the total to 10.
  Note the interaction to think about: Oathbound Magic's own stacking reduction happens
  BEFORE that cap, and it is not obvious whether the 10 counts oath points too (the
  wording "regardless of the number" suggests yes).
* ~~Holy Mien's cross-Merit grant~~ — **DONE**, once Priest arrived with the general
  chapter. `MeritEffects.granted_merits` and `merit_cost_overrides` carry it: Priest's
  one-point level costs 0 and its seven-point level 6. Both are effects, so no caller
  names either Merit — the decision-0011 containment test still passes.
* **Is there a cap on the NUMBER of Merits?** p.16: "Characters may theoretically have
  as many Merits as they can afford to purchase, limited only by the relative scarcity
  of bonus points" — so no, and none is enforced. The 10-point Flaw cap IS enforced.
* **The ST restriction on p.120**: "Storytellers who desire less powerful mortals may
  choose to restrict the purchase of these Merits to characters who have taken dots in
  the Knowledge Background or have some other source of mystical awareness." A
  `HouseRules` toggle, not yet added.

## Post-creation change (PG p.17) — DONE 2026-07-30

The book's "Gaining and Losing Merits and Flaws" gives the Storyteller **three
methods** and says they may "use any of these three methods or a combination". It is
NOT open ST fiat, and it is not silent. `HouseRules.mf_change_method` is TABLE-WIDE and
defaults to **experience** (human's call, 2026-07-30); the other two are selectable on
the ST Options tab, which now renders a select for a multiple-choice rule rather than
a checkbox — the first non-boolean house rule.

| Method | What the engine does |
|---|---|
| `experience` (default) | Gaining a Merit / losing a Flaw **charges** twice its bonus-point value; losing a Merit / gaining a Flaw **pays** the same. Unaffordable changes go into debt. |
| `backgrounds` | Nothing. "do not cost or reward players after character creation." |
| `swap` | Nothing. |

**The last two are mechanically identical to this engine** and are deliberately kept as
separate values anyway: they oblige the ST to different things at the table, and the
sheet should record which was chosen. Do not collapse them.

Confirmation worth having: p.17's "twice its bonus point value" is the **same rate** as
the mortal thaumaturgy table on p.115 ("New Merit (mystical only) | cost in bonus points
x2"), arrived at independently. Note also that `buy_merit` had silently implemented the
experience method before this toggle existed — flagged to the human rather than left
buried.

### The debt mechanic, and the bug it started as

p.17: "If the character cannot pay this full cost, she pays whatever she has available
and must allocate all further experience to the remaining balance until it is paid in
full." A Merit change is not always the player's choice — a Flaw healed by someone
else's Charm charges her whether or not she can pay — so `_pay_or_owe` takes on a
balance instead of refusing, unlike `_commit`, which still refuses an unaffordable Charm.

**`xp_debt` is DERIVED, not stored, and that is load-bearing.** The first cut stored the
balance and paid it down inside `add_xp` while logging only the *affordable* part of the
cost — so the remainder was never counted as spent and **6 XP silently vanished** in a
worked example. Logging the full cost and letting `xp_available` go negative makes the
debt self-evident, self-clearing, and impossible to lose.
`test_debt_never_destroys_experience` pins it.

## Not done

* Nothing. The editor panel, the sheet block, the ST Options selector and the **XP-tab
  card** are all done. The XP card appears only under the `experience` method; under the
  other two it explains that changes cost and reward nothing and points at the character
  tab, rather than offering buttons that all read 0 XP. It shows any outstanding debt,
  and previews the selected entry before you commit: printed cost line, whether it is a
  Merit or a Flaw (gaining a Flaw PAYS), the price this character would pay at the
  chosen tier, any splat restriction, and the rules text. Buying blind off a dropdown
  label is how you take a Flaw by accident.

  **Sheet layout note:** the Merits & Flaws block shares a row with Backgrounds,
  Specialties, Colleges and Thaumaturgy. That row WRAPS deliberately — as a `no-wrap`
  row, five panels crushed the later ones to unreadable slivers and the block looked
  missing when it was merely squeezed. Do not re-add `no-wrap` without dropping the
  per-panel min widths. The rules text rides on a **hover tooltip** (printed cost line
  + description) because there is no room to print it inline — `merit_rows` returns it
  as the row's fifth element.
* **The 10-point Flaw cap is still unenforced** at chargen (p.16, "may only receive up
  to 10 extra bonus points from Flaws") and post-creation (p.17, "receive no experience
  for the excess"). Only Oathbound Magic currently grants anything at all — see the
  open item above; both belong in the same change.
* Nothing in the chapter — all 87 are authored: 43 Merits and 44 Flaws across
  Physical / Mental / Social / Property / Supernatural.

### How the chapter is being authored — read before continuing

**The cost lines DO parse mechanically.** An earlier note here claimed they did not;
that was wrong, and the two failures behind the claim were both parser bugs, not
irregularities in the source:

* splitting on commas, so `(3-, 5- OR 7-PT. MERIT)` was read as "3 points, splat clause
  `5- OR 7-PT`" — losing two of three prices. Also hit MUTE, SUN-SEARED, AMNESIA.
* reading a single line, so `PRODIGY`'s wrapped cost line truncated mid-clause.

The working grammar (human's suggestion, 2026-07-30): match the **balanced parens**
rather than the line, then split on the word **`MERIT`/`FLAW`** — everything before it
is the price, everything after is a qualifier. `TO` means an inclusive range, `OR` a
menu of discrete choices. All 87 entries parse, with each parse printed beside its
printed line for review.

Two OCR traps worth keeping in the cleaner: a word broken after a capital
("DOUBLE-J OINTED", "HIDDEN M ANSE") must be rejoined, but NOT across an apostrophe —
"TAINT'S WARNING" is two words. And the curly `U+2019` must be normalised BEFORE that
rejoin runs, or the lookbehind never sees it.

**19 distinct qualifiers** remain, and those ARE hand-mapped — a small, reviewable set
rather than 87 numbers. Five cost shapes exist, all resolving in `validate.merit_points`:

| Printed | Modelled as |
|---|---|
| `(3-PT. MERIT)` | `cost` |
| `(1- OR 2-PT.)`, `(2- TO 6-PT.)` | `cost_options`, numeric string keys |
| `(5-PT., 3-PT. FOR EXALTED)` | `cost_options_by_exalt_type`, splats ENUMERATED (no "any Exalt" magic key) |
| `(VARIABLE COST MERIT)` | `variable_cost`, value on the purchase |
| `LUNARS ONLY` | `exalt_types` (authored, not yet enforced) |

**Every entry carries `cost_note` — its printed cost line, verbatim.** That is what
makes the four unmodellable qualifiers safe: the entry is authored at its base price
and the full printed text still reaches the sheet, so the Storyteller sees the rule
even where the engine cannot apply it. The editor renders it under each row.

**The four awkward qualifiers — RESOLVED (human, 2026-07-30):**

* `4-PT. FOR TWILIGHT CASTE` (Brigid's Heir) → **a per-caste cost axis**,
  `cost_options_by_caste`, which OUTRANKS the per-splat override. The only price in 87
  entries that keys on caste; the field exists now for whatever needs it next.
* `1-PT. LESS FOR EXALTED` (Mute) → the −1 is applied and **the rung that would become
  0 is dropped**: an Exalt pays 2 or 3 where a mortal pays 1, 3 or 4. A Flaw granting
  nothing is not a purchase.
* `MERIT OR FLAW` (Mutation, Favor, Eternal Vow) → **`kind: "either"`**, with the side
  recorded on the purchase (`taken_as`). Eternal Vow prices each side separately via
  `cost_by_kind` — its 1-point Flaw price had been lost entirely. Pricing defaults an
  unchosen side to "merit" so nothing crashes, and `merit-side-unchosen` reports it so
  the choice is never silently made for the player.
* `2- OR 4-PT. FOR DRAGON KINGS OR GOD-BLOODED` (Prodigy) → **left unauthored**; add it
  with those splats. Nothing is wrong today, since no character can be either.

`exalt_types` is now ENFORCED too (`merit-wrong-splat`), where it was previously
authored but inert.

The other 15 qualifiers ARE mapped: per-splat prices, splat restrictions (`exalt_types`)
and `PER SENSE` repeatability.

**Deliberately not authored:** Prodigy's "2- OR 4-PT. FOR DRAGON KINGS OR GOD-BLOODED"
override — neither splat exists in this build. Add it with them.

## Resolved

* **The Dragon-Path question is CLOSED** (human, 2026-07-30): **Immaculate Martial Arts
  are barred from mortals.** Implemented as `MeritEffects.bar_immaculate_charms`, a
  CLASS of Charms rather than a list of ids, keyed off the existing `Charm.immaculate`
  data flag. Note this does not ride on the ordinary Dragon-Path gate:
  `db_enlightenment_met` is Dragon-Blooded-specific and returns True for every other
  splat, so a mortal would otherwise have walked straight in. Consistent with barring
  Spirit Walking, since the Dragon Paths are exactly what Spirit Walking unlocks.


## NEXT SESSION — modelling the mechanical effects (planned 2026-07-30)

> **SUPERSEDED — this section is the PLAN as it was written, kept for its reasoning
> (especially "why not parallel subagents"). The work is under way and its record is
> `merits-flaws-triage.md`:** the triage pass is done, the human has ruled on the
> boundary, and clusters **A1-A5 are implemented** (trait forfeits, health levels, trait
> caps, cost modifiers, Essence-pool shape). A6-A7 remain. The counts below are the
> pre-triage estimate; the real answer is 26 implementable entries in 8 mechanisms.

**Only 4 of 98 M&F have their mechanical effects modelled**: Essence Awareness, Essence
Mastery, Oathbound Magic, and Holy Mien's Priest grant. The other 94 are printed text on
the sheet and nothing more. The catalogue, costs, validation and UI are all complete —
what is missing is the *effects*.

### The useful number is much smaller than 94

Rough triage by what each description actually touches (regex over the descriptions, so
treat as indicative, not final):

| Bucket | Count | Expressible here? |
|---|---|---|
| Dice pools / difficulties | 30 | **No.** This build models no dice pools (decisions 0008/0009) — there is nothing to hook. |
| Pure narrative | 33 | **No.** Nothing to model. |
| Mentions Willpower / Virtue | 21 | **Mixed.** Most are "make a Willpower roll" (out of scope); a few may be real permanent modifiers. This bucket needs reading. |
| Health levels | 2 | **Yes** — Large Size, Small |
| Attribute rating / cap | 3 | **Yes** — Legendary Attribute, Diminished Attributes, The Flow of Essence |
| Favored abilities | 2 | **Yes** — Prodigy, Unskilled |

Expect the genuinely implementable set to land around **10-20**, not 94.

### The plan

1. **Triage pass.** Produce a table of all 94: each marked *implementable / out of scope
   (dice) / narrative*, with a one-line reason. The 21-row Willpower/Virtue bucket is
   where the real reading is.
2. **Human rules on the boundary cases.** The dice/no-dice line has to be drawn once and
   applied consistently, or the same rule gets two answers in different entries.
3. **Implement the survivors in ONE sweep** through `MeritEffects` — new fields, new
   branches in `merits_and_flaws_calc`, and the corresponding reads in derive/validate.

### Why NOT parallel subagents (assessed 2026-07-30)

Considered at the human's suggestion and advised against, for reasons specific to this
work rather than any capability limit:

* **Decision 0011 funnels every effect through one object and one function.** Parallel
  agents would all be editing `MeritEffects` and `merits_and_flaws_calc` — same two
  files, same two spots. Maximum collision on work that is mostly deciding, not typing.
* **The hard part is scope adjudication, not implementation.** "+2 dice to Perception"
  has nothing to attach to. That boundary must be drawn ONCE; split across agents you
  get several different readings of it.
* **Each real effect is small but architectural.** Large Size granting a -0 health level
  touches `derive.health_track`, which today reads only Charms and Ox-Body purchases.

The one place parallelism would genuinely help is **step 1**: several agents each
classifying a slice of the chapter against a fixed rubric, with the results merged. That
was the human's fallback if they want it.

### Known first targets

* `derive.health_track` — currently reads Charms + Ox-Body only. Large Size (+1 -0 level
  at 4pts; +1 -0 and +1 -1 at 6pts) and Small are the first callers that are not Charms.
* `ExaltDefinition`/validate attribute caps — Legendary Attribute raises the ceiling one
  dot above what Essence allows, "during character creation or after it".
* `validate.favored_ability_count` — Prodigy grants "one additional Favored Ability for
  every" rung; Unskilled is its inverse.

## Two-sided entries and the editor's splat filter (2026-07-31)

Two of the three UI gaps CLAUDE.md listed. 1,370 tests pass. **Not browser-verified.**

**`kind: "either"` entries could not be chosen — and could not be gained in play at
all.** Mutation, Favor and Eternal Vow are printed "MERIT OR FLAW"; the side lives on
`MeritFlawPurchase.taken_as`, and validation has always flagged an unrecorded one
(`merit-side-unchosen`). Nothing could SET it. Worse than the TODO recorded: the XP tab
routed every either-entry into `buy_merit`, which demanded `kind == "merit"` and raised,
so the Merit branch it "always routed to" rejected them outright.

* **Editor**: a two-option `ui.select` on any either-row. No blank option and no
  default — the value decides whether the row charges bonus points or grants them.
  `set_merit` clears it when the row's entry changes, for the reason it already cleared
  `tier`: a choice made for the old entry says nothing about the new one.
* **XP tab**: the same selector inside the refreshable detail preview, driving the
  Merit/Flaw banner and the price line as well as the routing. `_gain_mf` refuses to
  act on an unchosen side rather than picking one.
* **`buy_merit`/`gain_flaw`** take `taken_as` and admit an either-entry only when it
  names THEIR side. Defaulting it here was never an option: the side is the direction
  of the transaction.
* **`drop_merit` branched on the CATALOGUE's `kind`**, so buying off an either-entry
  held as a Flaw paid the character instead of charging her. It now reads
  `validate.effective_merit_kind(definition, purchase)`.
* **`costs.merit_cost` could not see `cost_by_kind`** — it read `merit.cost`, which is
  0 for Eternal Vow, so gaining it in play cost nothing. It now delegates to
  `validate.merit_points`, which is where every cost shape was already resolved, so the
  XP path and the chargen path cannot disagree about a price. That also fixed
  variable-cost entries in play (Mutation and Favor are variable AND two-sided): the
  agreed `points` reach the pricing, and the p.17 Flaw-point cap is measured against
  the value the purchase actually carries.

**The editor's Merit dropdown now filters by splat and caste**, as the XP tab already
did. New `validate.merit_available_to(definition, exalt_type, caste)` is the single
predicate, sharing its three conditions with the `merit-wrong-splat` /
`merit-barred-splat` / `merit-barred-caste` issues so a dropdown can never offer
something validation would immediately reject. Both dropdowns and `add_merit`'s default
row read it.

* It checks the printed restrictions ONLY — splat allow-list, splat bar, caste bar —
  all of them inert catalogue data, so no Merit id is named and `engine/merits.py` is
  not consulted. Prerequisites, tiers and "thaumaturges only" are deliberately NOT
  filtered on: they depend on the rest of the sheet and would make the dropdown flicker
  as it is edited. Validation still reports them.
* A HELD entry that became illegal (a caste change) survives the filter through the
  existing `row_opts.setdefault` guard, so it stays visible and flagged rather than
  vanishing from the sheet.

**Still open**, and the last of the three: the XP tab's tier/points field is one
free-text input doing double duty — a tier key for a menu-priced entry, a point value
for a variable-cost one. Works; crude.

## Browser click-through, 2026-07-31 — 13 findings, 10 real bugs

The first click-through of the M&F work, done by the human against a served app. **1,370
tests were passing throughout**; every bug below was invisible to all of them. 1,386
tests now.

**The pattern, and the reason a click-through keeps paying:** almost every one is a rule
that WAS implemented, sitting somewhere that does not run when it matters. Nothing was
missing; things were mis-placed. Unit tests assert the implemented thing directly and so
never notice.

### Engine

* **Callous's Willpower exception did not exist.** `willpower_virtue_margin` was read in
  exactly one place — `validate`, as a CHARGEN CEILING — and the comment there claimed
  it was the decision-0005 exception. A ceiling does nothing post-lock, so raising a
  Virtue on a locked Callous character moved nothing. New
  `MeritEffects.willpower_tracks_virtues`; `derive.willpower` re-derives from the
  current Virtues when set. Writing the test found the neighbouring rule: raising a
  Virtue far enough EXPIRES Callous (9 dots, p.35), after which Willpower correctly
  re-pins. Both are now tested.
* **All 11 variable-cost entries were inert at chargen.** `grep -c variable_cost
  ui/editor.py` was 0 — no points field existed, so `MeritFlawPurchase.points` stayed 0,
  and at 0 points a variable-cost entry is legal, costless and effectless. Nothing could
  fail. Three of the four trait-forfeit Flaws are variable-cost, which is exactly why
  Callous (the one with a printed tier menu) worked and Diminished Attributes appeared
  to do nothing at all.
* **Legendary Attribute was silently inert without a `detail`**, and
  `_attribute_forfeits`' docstring claimed validate flagged a missing category. No such
  check existed. Both details are now closed sets (`merits.detail_choices`) with a
  `merit-detail-unchosen` issue.
* **Legendary Breeding's Breeding-5 prerequisite was unchecked** — it paid its full
  rating-6 row to a character with no Breeding Background at all. Found on an Outcaste,
  who is precisely that character. Fixed by `MeritFlaw.trait_prerequisites` and the
  `merit-trait-prerequisite` issue (see below). **Reported, not enforced**: the override
  still applies so the sheet stays internally consistent.

### Data — and why the fidelity test could not see it

Two defects spotted by eye turned into **eight** entries once grepped for structurally:

* 5 descriptions opened with the second line of a MULTI-LINE printed cost note
  (`"DRAGON KINGS OR GOD-BLOODED) The character excels at..."`). Each strip was verified
  against that entry's own `cost_note` rather than applied blind.
* 1 had the next section's markdown headers glued on (`"... Legacy of Hesiesh. ## FLAWS
  ### PHYSICAL"`). The first pass stripped only the last header — `## FLAWS ###
  PHYSICAL` is two, so the regex needed a repeated group.
* 2 names were mangled by naive title-casing of a SHOUTED source header: `Brigid'S Heir`.

**`test_every_description_matches_the_source_text` provably could not catch any of it.**
It fails a description below 92% of its source length; all of these make a description
LONGER, and by so little that every ratio stayed within 1.5% of 1.0. Structure, not
length, separates debris from prose — hence
`test_no_description_carries_extraction_debris` and
`test_no_name_was_mangled_by_title_casing`, which assert the SHAPE rather than an
allowlist of the eight then known. That is what turned 2 sightings into 8.

### UI

* The editor's **25-dot tally summed raw ratings**. The human ruled 2026-07-31 that dots
  above the pre-bonus cap are BP-only, and **the engine already had this right** (the
  `within_by_tier`/`above_by_tier` split), so one Ability at 4 read 25/25 while a free
  dot was genuinely unspent. Display-only fix, with a test pinning the tally's
  arithmetic to the engine's so they cannot drift.
* **The Nature select never refreshed validation** (`setattr` with no `changed()`), so
  the Live Validation box reported a stale empty Nature — which read as True Paragon's
  requirement being broken when it was fine.
* **Disfigured at 4 points caps Appearance at 0**, and the per-category attribute tally
  discounted a flat one free dot per Attribute, so a legal Social row read "−1 spent".
  The baseline is now `min(1, cap)`.
* **Beacon of Power's merged pool rendered a 0/0 Personal track** on the Play tab.
  `PlayView.single_pool` now carries the shape (not inferred from `personal_max == 0`,
  which cannot tell "merged by rule" from "no Personal pool"), and the tracker renders
  one track.
* **The tier select was labelled "Oath" for all 36 menu-priced entries** and the arena
  box appeared beside every one of them — only Oathbound Magic's stacking rule reads it
  (`merits.uses_arena`).
* The XP ledger showed the raw target `charms_withheld` instead of the Charm's name: the
  target has no dot in it, so `domain` was the whole string and the row fell through.

### Confirmed NOT bugs

* `10/23` on an Outcaste DB with Legendary Breeding is the Breeding-6 row on the DB
  formula, verified against Breeding 5 → 8/17 and Breeding 5 + LB → 9/19.
* Unspent attribute dots never convert to bonus points.

### Decisions taken (human, 2026-07-31)

* **Dots above the pre-bonus Ability cap are BP-only** and do not draw on the 25.
* **The forfeit Flaws collect DOTS, not points** — the dots are what a player chooses
  ("three points for every Physical Attribute dot") and entering points directly can
  silently lose a remainder. `merits.forfeit_rate()` is the accessor that lets the UI
  multiply without naming a Merit id.
* The other 8 variable-cost entries take a plain points field.
* Mortals may take Prodigy; they are its main audience.

## The last UI gap, and trait prerequisites (2026-07-31)

1,392 tests. **Not browser-verified.**

### The XP tab now collects values the way the editor does

The third of the three UI gaps, and by the end of the day an inconsistency this work had
itself created: the editor grew proper tier / dots / points / structured-detail controls
in the morning, leaving the XP tab pricing everything through **one free-text input
doing double duty** — a tier key for a menu-priced entry, a point value for a
variable-cost one. Two halves of the app collecting the same rules through different
widgets is precisely the shape that produced the splat-filter bug.

The controls now live inside the refreshable detail block so they can rebuild per entry,
and changing the entry clears **every** value that belonged to the old one — side, tier,
points and detail all mean something entry-specific, and a carried-over value silently
mis-prices. `test_the_xp_and_chargen_paths_price_a_purchase_identically` pins the two
paths across every cost SHAPE the catalogue uses, since it was a shape (`cost_by_kind`)
that the XP path could not see at all until this morning.

### Trait prerequisites are catalogue DATA, and that removed an id

A prerequisite on a TRAIT rather than on another Merit. `MeritFlaw.prerequisites` holds
Merit ids only, so these had nowhere to live and went unchecked — the Legendary Breeding
hole the click-through found.

New `MeritFlaw.trait_prerequisites: dict[str, list[list[TraitRequirement]]]`, keyed by
TIER (`""` is the requirement every tier carries) and **AND-of-OR** inside, the same
shape `Charm.prerequisites` uses. **This REMOVED Legendary Breeding's id from
`engine/merits.py` rather than adding one**: a printed restriction is as inert as a cost,
so it belongs on the model beside `barred_castes` and `barred_exalt_types`, and
`validate.unmet_trait_prerequisites` evaluates it generically. The catalogue can grow a
trait prerequisite on any entry with no engine change at all.

`TraitRequirement.trait` is a NAME, not an id, resolved by `validate.trait_rating`
across **Attributes, Abilities, Virtues and Backgrounds** in that order. Not laziness:
the entries span all four namespaces, and Backgrounds are free text with no id to
reference. A name that resolves nowhere reads 0 and the requirement fails — the
graceful-unresolvable-reference rule the rest of the build follows.

Five are authored, and only five — the chapter was swept mechanically and the
near-misses are flavour rather than gates:

| Entry | Printed | Note |
|---|---|---|
| `mf.legendary-breeding` | "must already have Breeding 5" (p.28) | Background ≥ 5 |
| `mf.hidden-manse` | "must have the Manse Background" (p.24) | Background ≥ 1, both tiers |
| `mf.innocuous` | "must have Appearance 2 … to purchase **this version**" (p.23) | Attribute ≥ 2, **tier "2" only** — the 4-pt version is a Supernatural Merit in all but name and is ungated |
| `mf.cache` | "Resources 4 or Salary 2" (p.25) | the **OR group** the dict-of-lists shape exists for |
| `thaum.celestial-travel-permit` | Celestial Patron 2 | a Background, prose prerequisite now checked |

Rejected as descriptive: Large Size's "**MOST** characters with this Merit have Strength
and Stamina 3 or higher" (typical holders, not a gate) and Barbarian's "not assumed to be
literate unless they have Lore 2 or higher" (a consequence of the Flaw, not a gate on
it). Legendary Attribute, True Paragon, Destiny, Callous, Derangement and Death-Taint all
match the search but describe caps or effects.

**Reported, never enforced** — the effect still applies, so the sheet stays internally
consistent and the Storyteller decides. Enforcing would silently change a pool the player
can see.

**Load-time check** (`rules_db._check_merits_flaws`): a `tier` key must be one of the
entry's own cost options. The trait NAME is deliberately NOT checked — it is resolved
across four namespaces, Backgrounds are soft references by design (a character may name
one the catalogue has never heard of) and Abilities include per-focus Crafts, so there is
no closed set to check it against.

### ⚠ Two open rules questions, deliberately unauthored

Both were found in the same sweep and are the human's call — nothing is authored for
either:

1. **Chimera** (p.38) — **RULED 2026-07-31: not modelled, deliberately.** "True chimerae
   cannot have the Renown Background." The human's call: *"an ST-tell, since the
   description is hedging."* The preceding sentence distinguishes "actual chimerae —
   those who have lost themselves to the Wyld" from a Lunar merely holding the Flaw, and
   that hedge is the tell — the page is describing a Storyteller judgement, not a
   purchase gate. **Do not author a `trait_prerequisites` row for it**, and do not add
   negative trait prerequisites to the model on its account: it was the only candidate.
2. **Weak Essence** (p.41): "Other magical beings may take this Flaw, provided that they
   normally have a starting Essence of 2. Dragon Kings are an exception." A gate on the
   SPLAT's starting Essence rather than on a character trait. **Prodigy's DK/God-Blooded
   override shipped alongside Dragon Kings (2026-08-05); the DK exception itself is
   still open.** The `min_starting_essence: 2` floor already admits both DK origins
   (modern 2, ancient 3), so the current data permits Dragon Kings to take the Flaw —
   what the exception clause actually adds is a **rules question for the human**: the
   "feral predators unsuitable for players" reasoning reads like an ST warning against
   dropping a Dragon King to Essence 1, but nothing in the build expresses a
   "playable only above Essence 1" gate, and the exception could equally be a bar. No
   interpretation chosen.

## The optional-`ruleset` audit (2026-07-31)

1,394 tests. `derive.soak`, `derive.willpower` and `derive.health_track` take an
OPTIONAL `RuleSet` because without one there is no way to know a Flaw is held. That
shape is deliberate and documented — but it makes **every omission a silent bug rather
than a TypeError**: the call succeeds and quietly returns the pre-Flaw number.
`advancement.raise_willpower` was one such omission, found and fixed earlier. This was
the sweep for the rest.

**Three more callers were omitting it**, all reading Willpower:

* `advancement.lower_willpower` — its "already at 1" floor guard and its ledger row
  both read the current value. Blind to the Flaw, a Weak-Willed character reads 4 where
  the truth is 2: the guard lets through a reduction it should refuse, and the log
  records a drop that did not happen. Now takes `ruleset` as an optional keyword,
  matching its `lower_*` siblings rather than breaking their signature.
* `ui/xp.py` (the raise row) — the WORST of the three, because it was user-visible and
  self-contradictory. `wp` drove both the button's label and
  `costs.willpower_step(rs, character, wp)`, while `advancement.raise_willpower` (already
  fixed) priced from the true value. A Weak-Willed character was **quoted 8 XP for a
  dot that was then charged at 4**.
* `ui/xp.py` (the Reduce-a-Trait dropdown) — wrong current value in the label.

`soak` and `health_track` have no external callers that omit it.

**The guard is source-level** (`test_no_caller_omits_the_ruleset_when_reading_willpower`),
which is the only kind that works here: there is nothing to observe at runtime, since the
blind call returns a plausible number. Verified against the previous commit — it flags
both `ui/xp.py` sites. If a future reading legitimately cannot supply a RuleSet, the
answer is to widen the test deliberately, not to route around it.

## Weak Essence's hole, and Prodigy's two halves (2026-07-31)

1,403 tests. **Not browser-verified.**

### Weak Essence was a live 6-point exploit on Mortals

Not the Dragon Kings question it was first filed as. Weak Essence is a **6-point Flaw
whose entire cost is "reduces the character's starting Essence rating to 1"** — and a
Mortal is pinned at Essence 1 already. So it cost them nothing and paid 6 bonus points
against a 21-point budget, a 29% increase for no drawback. It also handed 5
withheld-Charm credits to a splat with no Charms. Nothing complained.

The printed clause exists precisely to close this: *"Other magical beings may take this
Flaw, provided that they normally have a starting Essence of 2"* (p.41). New
`MeritFlaw.min_starting_essence`, read against `ChargenBudgets.essence_start` (Solar 2,
DB 2, Mortal 1), so it excludes Mortals and nothing else currently shipped. The Dragon
Kings exception stays unauthored until that splat exists.

The gate also filters both dropdowns. Its argument is **optional and omitting it is
permissive** — a caller without the budgets to hand can only fail to hide, never wrongly
hide.

### Prodigy: one entry, two independent purchases

**RULED 2026-07-31: the aptitude half escapes the splat bar**, and it stays a single
catalogue entry.

The page prices two things that the 2/3/4/5 menu had squashed into one axis: the Favored
Ability grant (3 points, 2 for Dragon Kings and God-Blooded) and "increased aptitude"
(+2), which "may be stacked onto the cost of purchasing the Trait as Favored with
Prodigy **or paid separately** for characters who innately gain Favored Abilities as part
of character creation" — which describes exactly the four splats the entry is otherwise
barred to.

* **Semantic tiers** replace the numeric menu: `{favored: 3, favored_aptitude: 5,
  aptitude: 2}`. The old menu could not express this — **"aptitude only" and "Dragon King
  grant only" are both 2 points**, so the price could not say which had been bought. A
  trap that would have sprung exactly when Dragon Kings landed. Distinct keys, whatever
  they cost.
* **`MeritFlaw.tier_barred_exalt_types`** — splat bars per OPTION rather than per entry.
  `barred_exalt_types` is now unused by the catalogue. The whole-entry answer is
  DERIVED from the per-option ones (barred at every option = barred outright), so the
  two can never disagree.
* **One Ability per purchase.** The page stacks the aptitude cost "onto the cost of
  purchasing *the Trait* as Favored" or has it "paid separately" for an already-favored
  Trait — singular, and the same Trait in both branches. So `detail` suffices and no
  second slot is needed. `detail_choices` supplies the Ability list (Craft excluded: it
  is taken per focus).
* **The gated dropdown is "Buying", not the Ability one.** A Solar buying the aptitude
  half still has to say which Ability; they simply cannot buy the grant for it.
* **`MeritEffects.ability_xp_discount`** is `{ability: XP subtracted}` — the AMOUNT, not
  just the fact, so `costs.ability_step` reads a number and names nothing. A constant
  called `PRODIGY_*` imported into costs.py would have satisfied the letter of decision
  0011 while breaking its point. Keyed per Ability, so buying it twice for the same
  Trait cannot stack. The subtraction sits beside the Calling discount, which is the
  same shape.
* Its bonus die stays out of scope (dice, decision 0009).

**Browser follow-up (2026-07-31).** A fresh Prodigy row on a Solar opened on `favored`
and flagged itself immediately: `add_merit`/`set_merit` defaulted the tier to the first
AUTHORED option, unfiltered by splat. (The disappearing "Favored" entry the human saw
afterwards was correct behaviour — the retained-tier guard stops offering it once a
legal tier is chosen — but it exposed the bad default.) Both now default to the first
tier `merit_tiers_available` returns. Pinned two ways: the specific shape of the
mistake, and a generic invariant over every menu-priced entry × every splat, so an entry
that grows a per-option bar later cannot reintroduce it.

**The DK/God-Blooded rate shipped 2026-08-05**, the day both splats existed:
`cost_options_by_exalt_type` keys `favored: 2` / `favored_aptitude: 4` / `aptitude: 2`
for Dragon-Kings and God-Blooded (all heritages) — "three bonus points for most
characters and two points for Dragon Kings and God-Blooded of all heritages" (p.20),
with the "+2" aptitude half unchanged. Resolved through the same `merit_cost_options`
cascade, so Solar/DB/etc. still price 3/5/2 and the tier bar is untouched. Pinned by
`test_prodigy_s_dragon_king_and_god_blooded_rate_is_2_and_4`.

**Bug found on the way:** Prodigy was authored `repeatable_by: ""`, i.e. once-only,
against "one additional Favored Ability for **every time this Merit is purchased**". Now
`"ability"`; the five-Favored cap is enforced by `favored_ability_count`, not by
forbidding the repeat.

## The flaw-point cap is now visible on both surfaces (2026-07-31)

`MeritEffects.flaw_points_raw` was computed and read by **nothing**. Its own comment
said what it was for — "so the UI can say '10 of 13' rather than silently swallowing
three points the player thinks they have" — and the UI never said it. A test asserted
the field's value directly and passed, which is why 1,415 green tests never noticed.
Found by `.claude/skills/preflight/effect_reads.py`, the read-site audit.

The rule is p.17: "Characters with more than 10 points of Flaws receive no experience
for the excess." It bites in two different ways and both were silent:

* **Chargen editor** — the panel header printed the CAPPED grant alone, so a character
  carrying 14 points of Flaws read `+10 from Flaws` with nothing to distinguish the
  ceiling from an arithmetic bug. Now an amber line under the header names the raw
  total, the granted total and the difference, and says **the Flaws still apply** —
  what is lost is the points, not the disadvantage.
* **XP tab** — in play the cap truncates the XP *award* (`award * room // value` in
  `advancement`), so a Flaw bought past the ceiling quietly pays a fraction or nothing
  at all. The card now states the remaining room *before* anything is bought, and warns
  when there is none.

Three UI tests, two new `_ui_main.py` routes (`/mf-capped`, `/mf-capped-xp`). This is
display only: the engine already enforced the cap correctly in both places, which is
exactly why the gap was invisible. **Browser-verified 2026-07-31**, both surfaces, at
the cap and under it, including the warning clearing when a Flaw is removed.

**Open judgement call, deliberately left in:** the XP tab states the headroom even at
`0 of 10`, on every character. Raised with the human at click-through and kept. If it
reads as clutter later, gate it behind holding at least one Flaw — the at-cap warning
is the half that matters.

The read-site audit now reports **zero** unconsumed `MeritEffects` fields.

## The desktop/work merge, and the click-through that followed (2026-07-31)

**1,475 tests.** Two branches had been developed in parallel — the desktop's A6, cluster
7 and A7 against the work machine's A5 addendum, two-sided entries, XP-tab controls and
splat filter — and neither had seen the other. The merge and the browser pass that
followed are one record because the pass is what made the merge trustworthy.

### Cluster 7 was implemented twice, and one had to go

Both branches grew a `MeritFlaw.trait_prerequisites` field with the **same name and a
different type**. Git merged the model file without conflict at that point, leaving the
class carrying the field twice — pydantic silently kept the last one. Nothing failed.

| | desktop (kept) | work machine (dropped) |
|---|---|---|
| shape | `dict[tier, list[list[TraitRequirement]]]` | `list[TraitPrerequisite]` |
| namespaces | Attributes, Abilities, Virtues, Backgrounds | Attributes, Backgrounds |
| OR groups | yes | no |
| entries | 5 | 3 |
| reported as | `merit-trait-prerequisite` | `merit-trait-required` |

Both surfaced as a validation Issue and neither enforced, so no behaviour was lost by
picking. The desktop's is a strict superset: Cache is "Resources 4 **or** Salary 2"
(p.25) and the work machine's shape cannot express the OR at all. Dropped with it:
`MeritEffects.trait_requirement_unmet`, `merits._trait_rating`, the `merit-trait-required`
code and six tests. The work machine's load-time check was kept, narrowed to the tier key
— the trait NAME is deliberately unchecked, since it resolves across four namespaces and
two of them are open sets.

**Consequence worth knowing: cluster 7 has now been browser-verified in the merged shape
only.** The work machine clicked through its own implementation, and that is the one that
went.

Two silent breakages git caused on its own, both found by tests rather than by reading:
`_locked_abyssal` lost its body (it shares three tail lines with the work machine's
`_locked_solar`, which git matched as common context and kept once), and a UI test lost
its `@pytest.mark` decorators at a hunk seam. Neither produced a conflict marker.

### The click-through: five findings, five real

A6, cluster 7 and A7 all clicked. **Everything on the A-list is now browser-verified.**

* **Permanent Resonance was in the wrong shape entirely.** It had been built as a rating
  riding alongside a full 10-point track. **Ruled 2026-07-31 (human, rules authority):**
  "Permanent Resonance is cumulative with temporary Resonance" (p.41) means it OCCUPIES
  the track — 2 permanent and the temporary track tops out at 8, with the Break arriving
  two points sooner, exactly as a permanent Limit would work on a Solar. `derive.limit_max`
  now subtracts it, stacking with Greater Curse and flooring at 0.
* **`permanent_limit_start` was computed and read by nothing** — the third dead effect
  field in this area. Death's Taint's price above its base four points buys a starting
  permanent Resonance ("add one additional bonus point per dot", p.41) that never reached
  the character, who always began at 0. Seeded in `lifecycle.lock_chargen`, which now
  takes an OPTIONAL `ruleset` on the `derive.willpower` pattern. It will not overwrite a
  track the XP ledger has already moved, so a re-lock cannot undo a Harrowing.
  This is why the human's report ("3-point Death's Taint shows 2 permanent") could not be
  reproduced in the engine: the 2 was a stored value, unrelated to the price.
* **The tier dropdown offered options that priced at 0.** It filtered per-splat on
  `tier_barred_exalt_types` but built its MENU from the generic `cost_options`, so a
  Sidereal saw Lucky at 4 and 5 — "1- TO 5-PT. MERIT, 1- TO 3-PT. FOR SIDEREALS" (p.39).
  `validate.merit_cost_options` is now the single resolution order (caste > splat >
  generic) that both the menu and `merit_points` read, so a dropdown can no longer offer
  something the pricer will not honour. A save already recording one now flags
  `merit-bad-tier` instead of being silently worth nothing. **A catalogue-wide test now
  asserts no entry offers any splat a 0-point option**; Lucky was the only one.
* **Two artifacts read as one big artifact.** `background_rating` SUMS duplicate rows,
  which is right for a rating held once and wrong for a Background held per possession:
  two 2-dot Artifacts read as Artifact 4 and satisfied a 3-point Damaged Artifact. New
  `validate.background_best` (highest single instance) backs the point-limit check, since
  the rule measures "the rating of the artifact it modifies" (p.37), singular. Trait
  prerequisites still SUM — no printed case distinguishes them, and it was left alone
  rather than changed on speculation.
* **Innocuous' two open-ended clauses got a ruling.** "Any other socially dependent
  Backgrounds" and "other Backgrounds contingent on being widely known" (p.22) had been
  left as ST adjudication, modelling only the eight Backgrounds named on the page. The
  human ruled them 2026-07-31 off each Background's own catalogue description:
  **capped at 2** — Backing, Connections, Retainers, Renown and **Liege**, the strongest
  case, since it "stands in for both Mentor and Backing" and an Abyssal was therefore
  dodging the cap the Mentor line imposes; **barred** — Reputation and Influence.
  Renown was considered for the barred list and capped instead: standing within the
  Silver Pact is known to a faction, not to the world.

### Still open

* **Salary does not exist as a Background.** Cache's prerequisite names it, and the
  catalogue has no such entry, so that half of the OR reads 0 and can never fire. Left
  deliberately (human, 2026-07-31) under the graceful-unresolvable-reference rule until a
  page for Salary turns up. The OR machinery itself is exercised by the Resources branch.

## Player report, 2026-07-31 — mortal magic access never left chargen

A friend clicked through a mortal with Essence Awareness + Essence Mastery and found two
things, which turned out to be three instances of ONE mistake: **`charms_available` is a
flat per-splat flag, and three gates asked it instead of asking whether the Merit had
reopened this particular Charm.** `charm_matches_splat` has known the answer since the
Merit shipped; only the chargen picker was asking it.

* **"Essence Mastery should allow a mortal to use Martial Arts."**
  `advancement.learn_charm` refused on the flat flag, so a style Charm a mortal could
  legally pick at creation became unbuyable the instant they locked. It now refuses only
  when `charm_matches_splat` also refuses — Spirit Walking, the Immaculate styles and
  every ordinary Charm stay barred, and the p.103 message is unchanged for them.
* **`check_splat_consistency` condemned every Charm a mortal held.** Same flag, same
  short-circuit: a legally bought Falling Blossom Charm sat on the sheet as a permanent
  `charms-not-available` error. Found by preflight, not reported — the friend would have
  hit it the moment they bought one.
* **"A mortal with Essence Mastery cannot see/take Terrestrial Circle Sorcery."**
  The Merit's circle grant reached `accessible_circles` (what the picker LISTS) but not
  `granted_circles` (what the picker marks *available*, what `meets_spell_requirements`
  gates on and what `check_spell_access` validates). Every Terrestrial spell rendered as
  a locked row reading "needs a Charm granting the Terrestrial Circle" — a Charm a mortal
  can never hold. The grant moved into `granted_circles`; `accessible_circles` inherits it
  from there and lost its own duplicate union.

**One tightening came out of the move.** `granted_circles` is now consulted for everyone,
and the grant was unconditional on holding the Merit, so a Solar with Essence Mastery
would have cast Terrestrial spells without buying Terrestrial Circle Sorcery — invisible
before, because a Solar reaches that circle through Charms anyway. The grant is now gated
on `not exalt.charms_available`: it SUBSTITUTES for the initiating Charm, so it belongs
only to a splat that can hold none.

**The lesson is the one this file already records, one level up.** The dead-effect-field
trap has a sibling: a field with exactly one read site, in the phase where it was written.
`open_charm_categories` and `granted_circles` both read as healthy on
`effect_reads.py` — a single site in `validate.py` — and both were wired to chargen only.
The tests had the same shape, asserting `charm_matches_splat` and `accessible_circles`
directly and never the gate that spends the points. **Test the buy path, not the effect.**
Eight new tests do, plus two render routes (`/mastery-picker`, `/mastery-picker-xp`) that
are the mirror of `/mortalpicker`: the pages that must vanish for a plain mortal must come
back for this one, before and after the lock.

Not browser-verified.
