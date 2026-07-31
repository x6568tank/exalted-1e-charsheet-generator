# Merits & Flaws

**Status: DONE (2026-07-30) — engine, UI, and the WHOLE chapter authored. 98 Merits &
Flaws: the 11 Thaumaturgy ones (`thaum.*`, pp.120-122) and all 87 of the general
chapter (`mf.*`, pp.16-41).** NOT browser-verified — that is the human's step. 31 tests in
`tests/test_merits_flaws.py`. NOT browser-verified — that is the human's step.

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
  exceed Essence 3 become gods, in the same way the God-Blooded do" (PG p.114). A hook
  into the Godblooded splat when it lands.
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
  who is precisely that character. New `MeritEffects.trait_requirement_unmet` +
  `merit-trait-required`, following the `nature_requirement_unmet` shape. **Reported,
  not enforced**: the override still applies so the sheet stays internally consistent.

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

New `MeritFlaw.trait_prerequisites: list[TraitPrerequisite]` (`kind` background/attribute,
`name`, `minimum`, optional `tier`). **This REMOVED Legendary Breeding's id from
`engine/merits.py` rather than adding one**: a printed restriction is as inert as a cost,
so it belongs on the model beside `barred_castes` and `barred_exalt_types`, and the
evaluation is generic. The catalogue can grow a trait prerequisite on any entry with no
engine change at all.

Three are authored, and only three — the chapter was swept mechanically and the
near-misses are flavour rather than gates:

| Entry | Printed | Note |
|---|---|---|
| `mf.legendary-breeding` | "must already have Breeding 5" (p.28) | Background ≥ 5 |
| `mf.hidden-manse` | "must have the Manse Background" (p.24) | Background ≥ 1, both tiers |
| `mf.innocuous` | "must have Appearance 2 … to purchase **this version**" (p.23) | Attribute ≥ 2, **tier "2" only** — the 4-pt version is a Supernatural Merit in all but name and is ungated |

Rejected as descriptive: Large Size's "**MOST** characters with this Merit have Strength
and Stamina 3 or higher" (typical holders, not a gate) and Barbarian's "not assumed to be
literate unless they have Lore 2 or higher" (a consequence of the Flaw, not a gate on
it). Legendary Attribute, True Paragon, Destiny, Callous, Derangement and Death-Taint all
match the search but describe caps or effects.

**Reported, never enforced** — the effect still applies, so the sheet stays internally
consistent and the Storyteller decides. Enforcing would silently change a pool the player
can see.

**Load-time check** (`rules_db._check_merits_flaws`): a trait prerequisite is looked up by
NAME at validation time and an unmatched name simply reads 0, so a typo would not error —
it would make the entry permanently unbuyable. Attributes are a closed enum and are
checked outright; a `tier` must be one of the entry's own cost options. **Backgrounds are
deliberately NOT checked**: they are soft references by design, and a character may name
one the catalogue has never heard of.

### ⚠ Two open rules questions, deliberately unauthored

Both were found in the same sweep and are the human's call — nothing is authored for
either:

1. **Chimera** (p.38): "True chimerae cannot have the Renown Background." A NEGATIVE
   prerequisite, which the model cannot currently express — but the harder problem is
   scope. The preceding sentence distinguishes "actual chimerae — those who have lost
   themselves to the Wyld" from a Lunar merely holding the Flaw, so it is unclear
   whether the bar applies to every holder or only to that subset.
2. **Weak Essence** (p.41): "Other magical beings may take this Flaw, provided that they
   normally have a starting Essence of 2. Dragon Kings are an exception." A gate on the
   SPLAT's starting Essence rather than on a character trait, and its named exception is
   a splat that does not exist yet. Best authored alongside Dragon Kings, with Prodigy's
   "2- OR 4-PT. FOR DRAGON KINGS OR GOD-BLOODED" override.
