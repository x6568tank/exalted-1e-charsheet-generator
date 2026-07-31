# Merits & Flaws — mechanical-effect triage (2026-07-30)

Step one of the plan in `merits-flaws.md` ("NEXT SESSION"): every one of the 94
unmodelled M&F read in full and sorted, so the human can rule on the boundary before
any code is written. **Nothing here is implemented.** Four entries already have effects
(Essence Awareness, Essence Mastery, Oathbound Magic, Holy Mien) and are not listed.

Buckets, after the human's rulings (2026-07-30, recorded below):

| | Meaning | Count |
|---|---|---|
| **A** | Implementable — a hook exists or is a small, well-shaped addition | **26** |
| **B** | Out of scope: the whole effect is dice or difficulty (decisions 0008/0009) | 31 |
| **C** | Narrative / ST adjudication — there is nothing to compute | 32 |
| **D** | Deferred or out of scope for a stated reason | 5 |

The estimate in the plan (10-20) was low. **A is 26, and it is really 8 mechanisms**,
which is the number that matters — several entries share one hook.

## RULINGS (human, rules authority, 2026-07-30)

1. **The dice line is drawn correctly.** Virtue Specialty and Vice stay OUT: both are
   dice-rolling, and both only take effect during play. Buckets B and C are skipped
   entirely — no work, now or later.
2. **Callous is an exception to decision 0005.** "If Callous is taken, Willpower
   changes. Otherwise it is locked where it is." So the pinned-at-lock Virtue component
   is re-derived for a Callous character and for no one else.
3. **A1 is a budget delta, not a new concept.** Forfeiting dots lowers that trait's
   chargen budget (2 BP taken → Virtue budget 5→4) and the existing over-spend
   validation does the rest. **No new model field is needed**: all four are
   `variable_cost` entries, so `MeritFlawPurchase.points` is already recorded and
   `dots = points ÷ rate`; Diminished Attributes' category goes in `detail`.
4. **The whole of A is approved to implement, bit by bit.**
5. **D mostly collapses.** Maximum Limit/Paradox is 10 by default — no derivation
   needed, so Greater Curse is a subtraction from a constant. Resonance is the Abyssal
   Limit track and needs only a rename (`ExaltDefinition.limit_label`, which is unset
   for Abyssal today and should read "Resonance", exactly as Sidereal reads "Paradox").
   The luck pools are modelled only insofar as the two Merits create them. **Out of
   scope: Pain Tolerance, Slow Healing, Essence Recovery** — all per-table, play-time.
   **Deferred: artifact and Manse attunement**, to be modelled eventually, most simply
   by letting the player declare it.
6. **Derangement moves to C.** Its mechanical hooks are references to individual Virtue
   Flaws (Heart of Tears, Berserk Anger, Deliberate Cruelty — core pp.131-133), which
   are not in `data/` at all; this build knows only *whether a splat has* a Virtue Flaw.
   Nothing to point at, so there is nothing to model.

---

## A — implementable (22)

### A1. Chargen trait-forfeit → bonus points (4 entries, one mechanism)

The single highest-value cluster: four Flaws that all say "forfeit dots of X during
character creation, receive N bonus points per dot". Today they grant their printed
value like any Flaw, which is wrong — their value IS the forfeit.

| Entry | Rule |
|---|---|
| `mf.diminished-attributes` | 3 BP per Physical Attribute dot forfeited. May not forfeit the free dot; may not then buy Physical Attributes with BP. Mental/Social variants exist as separate categories. |
| `mf.callous` | 2 BP per Virtue dot forfeited. Cannot forfeit the last dot of a Virtue. **Willpower may not start more than 1 above the sum of the two highest Virtues** — this collides with decision 0005. Flaw self-removes at 9 total Virtue dots. Bans the Paragon Nature. |
| `mf.unskilled` | 1 BP per Ability dot forfeited. Must still meet Favored-Ability minimums; may not then buy Ability dots with BP. |
| `mf.weak-willed` | 1 BP per permanent Willpower dot forfeited. Floor of 4 for Exalted, 2 for un-Exalted or Callous characters. |

Needs a `forfeited_dots` shape on the purchase (or reuse of `points`), plus the "may
not spend BP on the forfeited category" restriction. **Question for you:** is the
forfeit recorded as a number, or inferred from the character being below the chargen
minimum? Inferring is fragile; recording is explicit but is a new field.

### A2. Health levels (2 entries) — `derive.health_track`

| Entry | Rule |
|---|---|
| `mf.large-size` | 4-pt: +1 `-0` level. 6-pt: +1 `-0` and +1 `-1`. |
| `mf.small` | −1 `-1` level. (Its other half — Strength −1 for weapon minimums — is combat, out under 0008.) |

`health_track` reads Charms and Ox-Body only; these are the first non-Charm callers.

### A3. Trait caps (4 entries)

| Entry | Rule |
|---|---|
| `mf.legendary-attribute` | One Attribute may go one dot above the Essence-imposed limit, at chargen or after. Mortals/Essence 1-5 → 6. |
| `mf.true-paragon` | May raise any Virtue to 6 with BP or XP (+1 to the permitted max if already above 5). Permanent Willpower still capped at 10. Paragon Nature only. |
| `mf.disfigured` | 3-pt: Appearance may never exceed 1. 4-pt: Appearance 0, unraisable by BP or XP. |
| `mf.weak-essence` | Starting Essence rating forced to 1. Also lets the player withhold up to 5 Charms, XP-free. |

Chargen caps live at `validate.py:2908` (`attribute_base <= attr <= 5`); the XP-side
caps live in `advancement.py`. Both would read a `MeritEffects` field.

### A4. Point-cost modifiers (2 entries)

| Entry | Rule |
|---|---|
| `mf.brigid-s-heir` | **Doubles** BP/XP cost and training time of all Charms; **halves** the same for spells. Ox-Body and anything on the Terrestrial Circle Sorcery line are exempt from the doubling. |
| `mf.prodigy` | Grants one extra Favored Ability per purchase (cap 5 total; barred to Solars/Abyssals/Lunars/Alchemicals). The optional +2 BP "increased aptitude" lowers that Ability's XP cost to `(rating × 2) − 2`. Its `+1 die` half is out. |

Both are clean: the cost tables are already data, and the calc can hand back a
multiplier and a Favored-Ability grant.

### A5. Essence-pool shape (2 entries)

| Entry | Rule |
|---|---|
| `mf.legendary-breeding` | Breeding Background counts as 6 → +6 Personal, +11 Peripheral, anima activation −3. `derive._breeding_bonus` is already the hook. Requires Breeding 5. DB only. |
| `mf.beacon-of-power` | One pool equal to Personal + Peripheral, all of it treated as Peripheral for anima. Exalted only; Night and Day may not take it. |

### A6. Background budget and rating restrictions (5 entries)

| Entry | Rule |
|---|---|
| `mf.heir-apparent` | 2 Background dots per point invested (max 5 points), **may exceed the rating-3 chargen cap**, +1 dot per stipulation (max 3). |
| `mf.innocuous` (4-pt) | Allies / Contacts / Mentor capped at 2 dots each; no Followers, Henchmen, Cult or Command at all. Sidereals barred entirely. |
| `mf.damaged-artifact` | Points may not exceed the artifact's rating, nor the BP/Background spent on it; character needs Artifact ≥ points + 1. |
| `mf.known-anathema` | Points may not exceed the character's Influence rating. |
| `mf.debt` | Functions as inverse Resources; if the character also has Resources, Debt must exceed it. |

### Adjacent mechanism, not an entry: **trait prerequisites**

`MeritFlaw.prerequisites` holds Merit ids only; every trait-rated prerequisite is
currently unchecked printed text in `prerequisite_note`. At least six entries want it:
Hidden Manse (Manse Background), Cache (Resources 4+ / Salary 2+), Innocuous 2-pt
(Appearance 2), Legendary Breeding (Breeding 5), Alternative Divination (purchases
≤ Occult rating), Large Size (Strength and Stamina 3+, though that one is printed as
"most characters", not a requirement). Worth doing as one field, independent of effects.

---

## B — dice pools and difficulties only (31)

Nothing to hook: the entire printed effect is "+N dice" or "+N difficulty", and this
build derives no dice pools (0008) and rolls nothing (0009).

`thaum.flow-of-essence` · `thaum.sheltered-upbringing` · `mf.ambidextrous` ·
`mf.acute-sense` · `mf.double-jointed` · `mf.special-resistance` ·
`mf.internal-compass` · `mf.virtue-specialty` · `mf.driving-passion` ·
`mf.tactical-instincts` · `mf.true-love` · `mf.jack-of-all-trades` · `mf.born-to-rule` ·
`mf.enchanting-feature` · `mf.past-lives` · `mf.signature-style` · `mf.daredevil` ·
`mf.prescient-dreamer` · `mf.unusual-appearance` · `mf.one-eye` · `mf.sun-seared` ·
`mf.climate-sensitive` · `mf.weak-immune-system` · `mf.diminished-sense` · `mf.vice` ·
`mf.nightmares` · `mf.pacifist` · `mf.barbarian` · `mf.disturbing` · `mf.child` ·
`mf.chimera`

**Boundary case for you:** `mf.virtue-specialty` and `mf.vice` modify *Virtue* dice, and
Virtues are a permanent trait this build does track. They are still dice — but they are
the closest B gets to A. Same question for `mf.innocuous`'s dice half, whose Background
restrictions I put in A6.

---

## C — narrative / ST adjudication (31)

No mechanical effect at all, or one the Storyteller arbitrates entirely.

`thaum.celestial-travel-permit` · `thaum.dark-magics` · `mf.selective-conception` ·
`mf.special-sense` · `mf.mutation` · `mf.common-sense` · `mf.eidetic-recall` ·
`mf.favor` · `mf.heirloom` · `mf.legendary-artifact` · `mf.terrestrial-bloodline` ·
`mf.priest` · `mf.destiny` · `mf.sworn-brotherhood` · `mf.taint-s-warning` ·
`mf.eternal-vow` · `mf.mute` · `mf.sterile` · `mf.limited-forms` · `mf.amputee` ·
`mf.amnesia` · `mf.superstition` · `mf.addiction` · `mf.secrets` · `mf.disciple` ·
`mf.enemy-rival` · `mf.wanted` · `mf.unbidden-oracle` · `mf.dark-fate` ·
`mf.permanent-caste-mark` · `mf.throwback` · `mf.derangement`

These are exactly what `MeritEffects.narrative_only` exists to report.

---

## A7. Play-state pools and tracks (4 entries) — promoted from D by ruling 5

| Entry | Rule |
|---|---|
| `mf.lucky` | A luck pool equal to points invested (Sidereals: +2, pool capped 5, min 3). The pool exists only because the Merit does — so it is a `MeritEffects` field, tracked in play-state. Spending it to reroll is 0009 and stays out; the pool is just a counter. |
| `mf.unlucky` | The same, ST-side and negative. May be held simultaneously with Lucky. |
| `mf.greater-curse` | Maximum Limit/Paradox reduced by 1 per point, max 5. The maximum is the constant 10, so this is `10 − points`. Celestial Exalted only. |
| `mf.death-taint` | Permanent Resonance, cumulative with the temporary track. Needs the Abyssal `limit_label` rename to "Resonance" first, plus a permanent counterpart to the pool. Abyssals and ghosts only — the ghost half waits on that splat. |

These are play-state (decision 0006): they may be tracked and displayed, and must never
enter chargen validation or the XP audit.

---

## D — deferred or out of scope (5)

| Entry | Call |
|---|---|
| `mf.pain-tolerance` | **Out of scope.** Wound-penalty arithmetic; per-table, play-time. |
| `mf.slow-healing` | **Out of scope.** Healing rates; per-table, play-time. |
| `thaum.essence-recovery` | **Out of scope.** Mote regeneration rate; per-table, play-time. |
| `thaum.magical-attunement` | **Deferred.** Artifact attunement should be modelled eventually — simplest is to let the player declare it. |
| `thaum.manse-attunement` | **Deferred.** Manse attunement, same. |

`mf.derangement` moved to **C** (ruling 6).

---

## Implementation order

Bit by bit, per ruling 4. Each cluster is self-contained; do not batch them.

| # | Cluster | Why here |
|---|---|---|
| 1 | **A1** forfeit → budget delta | The core job: chargen point accounting is wrong without it. Carries the Callous/0005 ruling. |
| 2 | **A2** health levels | Smallest. First non-Charm caller of `derive.health_track`. |
| 3 | **A3** trait caps | Same shape as A1 — a per-trait delta, chargen and XP side. |
| 4 | **A4** cost modifiers | Cost tables are already data. |
| 5 | **A5** Essence pools | Legendary Breeding hooks `_breeding_bonus`; Beacon of Power needs more care. |
| 6 | **A6** Background restrictions | Plain validation rules. **DONE 2026-07-30.** |
| 7 | **Trait prerequisites** | Catalogue data, not effects — independent of everything above. **DONE 2026-07-30.** |
| 8 | **A7** play-state pools | Needs the Abyssal `limit_label` rename first. **DONE 2026-07-30.** |

## A1 — COMPLETE 2026-07-30 (all four)

Callous, Unskilled, Weak-Willed and Diminished Attributes, engine and chargen UI.
1304 tests pass (was 1285). **Browser-verified 2026-07-31** (the thorough pass — 13 findings, 10 real bugs; `merits-flaws.md`).

* `MeritEffects` gained `forfeited_ability_dots`, `forfeited_virtue_dots`,
  `forfeited_willpower_dots`, `forfeited_attribute_dots`, `willpower_virtue_margin`,
  `willpower_floor`, `barred_natures`. No new field on `MeritFlawPurchase` — dots are
  `points // rate`, exactly as ruling 3 predicted.
* `validate.effective_budgets(ruleset, character)` returns the budgets reduced by the
  forfeit; it returns the printed object unchanged when nothing forfeits. Swapped into
  the three chargen-accounting sites (unspent-dot warnings, `bonus_point_breakdown`,
  `validate_chargen`).
* New issue codes: `callous-willpower-cap`, `willpower-below-flaw-floor`,
  `nature-barred-by-flaw`.
* `derive.willpower` takes an optional `ruleset` — the same shape `soak` already uses —
  and subtracts the Weak-Willed forfeit only when given one.

* **Diminished Attributes** is wired through `validate.attribute_pool_assignment`, which
  does the spend-to-pool matching FIRST and takes the forfeit off the pool the category
  actually receives. Consequence the human accepted explicitly: forfeiting dots lowers a
  category's spend, which can drop it to a smaller pool, and that reshuffle can cost
  bonus points elsewhere — *"if BP need be consumed because of how the pools change,
  then that's what happens."*
* **The chargen editor** now reads `validate.effective_budgets`, so its Ability and
  Virtue headers show the budget the engine charges against. The Attribute header cannot
  fold the forfeit into the printed 8/6/4 (the pools are spend-matched, not fixed), so
  it names the shortfall alongside: `8/6/4 −2 Physical`.
* **`mf.callous`'s tier menu was wrong in the data** and is fixed: authored 2..10, but
  the entry prices itself at "two bonus points for every dot", so 3/5/7/9 granted points
  without buying a dot. Now 2/4/6/8/10.

## A2 — COMPLETE 2026-07-30 (health levels)

Large Size and Small. 1315 tests pass. **Browser-verified 2026-07-31** (the thorough pass — 13 findings, 10 real bugs; `merits-flaws.md`).

* `MeritEffects` gained `health_levels_granted` (as `(penalty, source label)` pairs, so
  the sheet attributes a Merit level exactly as it does an Ox-Body one) and
  `health_levels_removed`.
* `derive.health_track` takes an optional `ruleset` — the third function to use that
  shape, after `soak` and `willpower`. These are its first non-Charm callers.
* Small reuses the removal path that already existed for curses, and takes a BASE level
  before a granted one. Large Size 6 + Small therefore nets out at the printed track
  with the granted `-1` surviving and still attributed.
* **The play tracker followed for free** — `build_play_view` reads `derive.derive()`,
  so a Large Size character gets 8 or 9 damage boxes rather than 7, with no change in
  `ui/play.py`.
* An unrecorded Large Size tier grants NOTHING rather than guessing a size. That is only
  safe because `merit-bad-tier` already reports it; the test pins both halves together.

## A3 — COMPLETE 2026-07-30 (trait caps)

Legendary Attribute, True Paragon, Disfigured, Weak Essence. 1333 tests pass.
**Browser-verified 2026-07-31** (the thorough pass — 13 findings, 10 real bugs; `merits-flaws.md`). The first cluster to span the chargen/advancement boundary.

* `MeritEffects` gained `attribute_caps` (keyed by `AttributeName.value`, which is
  **lowercase** — a normalisation bug caught by tests), `virtue_cap`,
  `essence_start_override` and `nature_requirement_unmet`.
* **Legendary Attribute and Disfigured share `attribute_caps`.** Raising a ceiling and
  lowering one are the same question — "what may this trait reach" — so they are one
  field, keyed by effect rather than by Merit, as the module docstring requires. Where
  both apply to one trait the **lowest cap wins**, so a Merit can never undo a Flaw's
  ceiling by being processed second.
* Legendary Attribute's cap is `max(5, essence) + 1`, from "for mortals and Exalted with
  Essence 1 to 5, this allows a rating of 6. Exalted with Essence 6 may raise the
  Attribute to 7". **This does NOT introduce an Essence-scaled cap build-wide** — the
  base ceiling stays a flat 5 for everyone without the Merit. If the underlying
  Essence-limits-Attributes rule is ever wanted generally, it needs its own page.
* Read in `validate` (chargen range checks, Essence start) and in `advancement`
  (`raise_attribute`, `raise_virtue`) — Legendary Attribute is explicitly "during
  character creation or after it".
* **A Flaw ceiling can sit below the chargen floor.** Disfigured at four points forces
  Appearance 0, and the free dot every Attribute starts with is what it takes away, so
  the floor follows the ceiling down. Without that the sheet reported `must be 1-0`.
* The editor's dot rows read the per-trait cap instead of a hardcoded 5 — a ceiling the
  player cannot click to is a ceiling they cannot use.
* New issue codes: `merit-nature-required`, `essence-above-flaw-start`.

**Fixed in passing — an A1 regression.** `advancement.raise_willpower` measured against
`derive.willpower(character)` with no RuleSet, so a Weak-Willed character was capped as
though they still had the dots they had sold. Now passes the ruleset. **Worth a general
check:** every `derive.willpower` / `derive.soak` / `derive.health_track` call that
omits the optional ruleset is potentially the same bug.

### Weak Essence's withheld Charms — DONE (2026-07-30, after the A3 sweep)

Initially deferred as needing new persistent state; that assessment was **wrong** and
the human pushed back on it. Nothing new is stored:

```
granted   = min(5, charm_count − chargen picks taken)     # the snapshot already
remaining = granted − rows logged under `charms_withheld` # records both halves
```

`validate.withheld_charm_credits` returns the pair. The human's rule — "keep the free
Charms at 5; if more than five are selected during chargen, subtract the number over" —
is stated against `charm_count` rather than a literal 10 so it holds for any splat's
budget. Banking can never yield MORE Charms than the ordinary budget: it defers picks,
it does not add them.

**Ruling (human, 2026-07-30): banked PICKS, not Charms named at creation.** The Flaw
exists because a character pinned at Essence 1 cannot choose well, so what is held back
is the choice itself.

**The trap, and why redemptions get their own XP-log target.** `_expected_cost`
re-prices every entry from the table, so a 0 filed under `charms` would be reported as
`xp-cost-mismatch` on every later validation. Redemptions log under
`validate.WITHHELD_CHARM_TARGET` (`"charms_withheld"`), which prices at 0 by rule —
the same distinct-target pattern the Eclipse crossover already uses. That target is
also what makes the credits countable.

`learn_charm` spends a credit automatically while one remains; `undo_last` removes the
row and the credit returns, since credits are counted from the log rather than stored.
The XP tab shows "N of M withheld Charm(s) still in reserve".

**Still out: the training-time half.** "They still require the same training time" hangs
on `XpEntry.training_complete`, a dormant hook. **Training times are almost certainly
never being added** (human, 2026-07-30 — "that goes out of the dumb-tracker scope"), so
this is not a gap awaiting a fix: the XP waiver ships without its counterweight, and that
is the final state unless the human reopens it. See CLAUDE.md.

**A robustness note found while testing:** credits are counted against the FROZEN
chargen pick list. A character locked *without* a `ChargenSnapshot` would count every
Charm learned afterwards as a chargen pick and silently eat its own credits.
`lifecycle.lock_chargen` always writes one, so the normal path is safe.

## A4 — COMPLETE 2026-07-30 (point-cost modifiers), with two open rulings

Brigid's Heir and Prodigy. 1351 tests pass. **Browser-verified 2026-07-31** (the thorough pass — 13 findings, 10 real bugs; `merits-flaws.md`).

* `MeritEffects` gained `charm_cost_doubled`, `spell_cost_halved` and
  `extra_favored_abilities`.
* **Brigid's Heir could not be a plain multiplier field** — the answer depends on WHICH
  Charm, because the sorcery line is exempt. So `merits.adjust_charm_cost` and
  `merits.adjust_spell_cost` are the read: callers hand over a cost and get one back,
  and still name no Merit id. Decision 0011's rule is about not branching on ids, and a
  function in `engine/merits.py` honours that better than leaking the exemption set.
* **The exemption is found through DATA, not ids**: the initiating Charm is the one
  whose `grants_circle` is Terrestrial, so it works for every splat with sorcery. The
  closure is cached per (ruleset, splat) because it walks every Charm's prerequisites.
* Applied at four sites — XP for Charms and spells (`costs`), and bonus points for both
  (`validate.charm_pick_bp_costs` and the spell row beside it), because the entry says
  "the bonus/experience cost", not just XP.
* Prodigy feeds `validate.favored_ability_count`, so the existing favored-count check
  does the work unchanged, clamped at the printed five.
* **Prodigy's splat bars are catalogue DATA, not an effect.** New `MeritFlaw
  .barred_exalt_types` — the negative of the existing `exalt_types` — with a new
  `merit-barred-splat` issue. A printed restriction is inert like a cost or a
  prerequisite, so it belongs on the model rather than in `engine/merits.py`.

### ✅ Two rulings — BOTH ANSWERED 2026-07-31 (human)

Both were resolved in the human's favour of what shipped, so **no code changed**. Kept
here as the record of a closed question rather than an open one.

1. **Is Terrestrial Circle Sorcery itself exempt from Brigid's Heir?** The text exempts
   Charms that "include [it] as an ultimate prerequisite or lead directly to that
   Charm" — neither of which is TCS itself. Leaving the one Charm the Merit is *about*
   at double cost while everything either side is exempt reads as a drafting slip, so it
   is exempt here **by inference**.
   **RULED: keep the inference** — "that's fine for now, but I don't mind." Read as
   settled-but-reopenable: the human has no strong view, so do not treat it as
   load-bearing precedent for any other exemption. Reverting is still a one-token change
   at the OPEN RULING comment in `merits._terrestrial_sorcery_line`.
2. **How does an odd spell cost halve?** The page does not say. Rounded DOWN.
   **RULED: player-favourable, i.e. DOWN — as shipped.** No printed cost in the build is
   currently odd, so this still has no effect today; it is settled against future data.

**Noted, not a bug:** Terrestrial Circle Sorcery is a ROOT Charm in this data — nothing
is its prerequisite — so the "leads directly to that Charm" clause has no members. The
implementation handles it; the test records the fact so it stays visible if a splat ever
gates it behind something. Necromancy is a separate line and is **not** exempt.

**Deferred from A4:** Prodigy's optional "+2 bonus points to increase aptitude further",
which lowers that Ability's XP to `(current × 2) − 2`. The catalogue prices Prodigy as a
2/3/4/5 tier menu that **conflates two different things** — the base grant (3, or 2 for
Dragon Kings and God-Blooded) and the +2 aptitude add-on — so there is no unambiguous
way to record that the extra was paid. Needs either a data reshape or a purchase field;
either way it is a decision, not a line of code. The bonus die it also grants is out
anyway (dice).

## A5 — COMPLETE 2026-07-30 (Essence-pool shape)

Legendary Breeding and Beacon of Power. 1360 tests pass. **Browser-verified 2026-07-31** (the thorough pass — 13 findings, 10 real bugs; `merits-flaws.md`).

* `MeritEffects` gained `breeding_rating_override` and `essence_single_pool`.
* **Legendary Breeding is modelled as the RATING it grants, not as +6/+11 motes.** The
  entry says two things — "her Breeding Background has a rating of 6" and "adds 6 motes
  … and 11 motes" — and the second is the first's consequence, not an addition on top:
  the printed 0..5 Breeding table climbs +1 Personal / +2 Peripheral per step and ends
  at 5/9, so 6/11 is exactly its rating-6 row. `data/exalts.json` gained that row and
  `derive._breeding_rating` takes the override. Reading it as additive would have paid
  a Breeding-5 character (which the Merit REQUIRES) 11/20.
* **Its Breeding-5 prerequisite is still unchecked** — that is the trait-prerequisites
  item, deliberately not done here. Nothing stops a Breeding-2 character taking it.
* **Beacon of Power merges AFTER both pools are computed**, so every term still
  contributes what it did; the test pins that by stacking it with Legendary Breeding.
  Its anima half ("all of which is considered Peripheral for the purposes of anima
  displays") needs nothing: **the build models no anima costs at all** — `anima` is a
  free-text field and `anima_powers` is printed text. The same is true of Legendary
  Breeding's −3 anima activation, its Social dice and its Exaltation roll, all out.
* **`DerivedTraits.essence_single_pool` carries the SHAPE alongside the number**, and
  the sheet and editor both read `SheetView.essence_pool_label()`. "Personal 0" alone
  reads as a character with no Essence rather than as a rule. The play tracker followed
  for free, as it did in A2.
* **`derive.essence_pools` now calls the M&F calc unconditionally** (it was conditional
  on the splat having an unlockable pool). Same local-import shape as before.
* **Beacon's caste bar is catalogue DATA**, the A4 precedent one level down: new
  `MeritFlaw.barred_castes` and a `merit-barred-caste` issue. Caste ids are unique
  across splats, so `["night", "day"]` needs no splat qualifier.

### A5 addendum — Essence Awareness' partial unlock (2026-07-31)

A5 shipped the pool's SHAPE but not its ACCESS. `essence_pool_unrestricted` was
computed and read by nothing, so a mortal with Essence Awareness and one with Essence
Mastery derived an identical pool — the p.120 split was in the dataclass and nowhere
else. Found by `.claude/skills/preflight/effect_reads.py`, not by a test: 1,412 tests
were green and one of them asserted the dead field directly.

1416 tests. **Browser-verified 2026-07-31** — clicked through on a mortal with
Awareness, the same with Mastery, and with the Merit removed; no findings. **Floor
rounding confirmed by the rules authority the same day** — it is an interpretation he
is happy with, not a printed value, and stays flagged as such.

* **New `derive.essence_freely_accessible`** — motes drawable without a Willpower
  roll, or `None` when the whole pool is (every Exalt, and any mortal with Mastery).
  `None` rather than the total, so "unrestricted" is distinguishable from a
  freely-drawable 0.
* **The pool is NOT reduced.** p.120 divides the pool in two; it does not shrink it.
  The restricted two thirds are still the character's motes, so the free share is
  carried beside the totals exactly as `essence_single_pool` carries the shape.
  `DerivedTraits.essence_free` → `SheetView.essence_pool_label()` → `PlayView.free_max`,
  the same three layers A5 used, and the play tracker's inputs still run to the full
  maximum with the line drawn as a note under them.
* **The Willpower roll is not modelled and will not be** (decision 0009, and the
  human's call 2026-07-31: Awareness is a prerequisite for Mastery, so a rolled
  sub-pool would get tied up in a state most characters pass straight through). It
  reaches the player as printed description text, which the sheet tooltip shows; a
  test pins that the sentence is still in the catalogue entry.
* **⚠ OPEN RULES QUESTION: rounding.** p.120 says "one third" and prints no rounding
  rule. **Floor** is implemented (19 motes → 6 free) and flagged in the docstring.
  Confirm before relying on it — it is currently the only number here without a page.
* An Exalt holding the Merit is unrestricted: the gate is `has_native_pool or mastery`,
  which A5 already had right.

## A6 — COMPLETE 2026-07-30 (Background budget and rating restrictions)

Heir Apparent, Innocuous, Damaged Artifact, Known Anathema, Debt. 1377 tests pass
(was 1360). **Browser-verified 2026-07-31.**

**Five entries, but only TWO are effects.** Damaged Artifact, Known Anathema and Debt
all say the same thing in different words — *this entry's point value is bounded by a
Background rating* — which is a restriction on what may be BOUGHT, not something the
entry does. So they are inert catalogue data, the A4/A5 precedent a third time: new
`MeritFlaw.points_limited_by`, a `BackgroundPointLimit` of
`(background, mode, offset)`.

| Entry | Row |
|---|---|
| Known Anathema | `Influence`, `max` — "may not … take more points of this Flaw than their rating in Influence" |
| Damaged Artifact | `Artifact`, `max`, offset −1 — "at least one more dot of Artifact than the points obtained" |
| Debt | `Resources`, `above` — "provided the former exceeds the latter" |

`mode="above"` is the only reason the field is not a plain integer cap: Debt is a FLOOR.
It needs no special case for a character with no Resources — any Debt exceeds 0.
New issues: `merit-points-above-background`, `merit-points-below-background`.

**Damaged Artifact's per-artifact half is NOT modelled — and the human ruled it should
be** (2026-07-30: "worth closing; it should work on a *specific* Artifact"). It needs
individual artifacts as rated objects, which this build does not have — Artifact is one
Background rating, and the check as shipped sums every Artifact row. That turned out to
be a splat feature rather than an M&F cluster: the source page (E:Ab p.131, supplied by
the human) shows the Abyssal Artifact Background is a **combined-rating budget with
per-item caps**, not the cost curve it was assumed to be. Transcribed, planned and
**deferred behind cluster 7 by the human's call** — see `docs/status/rated-artifacts.md`.
The rating check ships as it is until then.

* **Heir Apparent is a budget delta with the opposite sign to A1's forfeits**, and
  lives in the same place: `effective_budgets` now also ADDS
  `MeritEffects.bonus_background_dots`. That symmetry is the whole argument for where
  it went.
* **Stipulations needed a new purchase field** — `MeritFlawPurchase.stipulations`.
  Unlike A1's forfeits, they cannot be recovered from the point value, because they
  cost nothing and so leave no trace in the price. Clamped to the printed 3 in
  `engine/merits.py` rather than on the model, so an old save with a stray value loads
  instead of failing. The UI offers the control off a new inert catalogue flag,
  `MeritFlaw.takes_stipulations` — the `repeatable_by` precedent: a field that says what
  a purchase may RECORD is not a field that says what the Merit does, and it keeps the
  editor from naming an id.
* **The cap exemption is where the trap was.** "Background dots obtained with this
  Merit … may raise a Background above a rating of three" — waiving the bonus-point
  charge on those dots would have made them FREE, since an above-cap dot does not
  consume the pool either. It is now a *transfer*: a waived dot consumes one pool dot
  (out of the enlarged pool the Merit granted) instead of paying bonus points. Pinned by
  `test_the_waived_dots_still_consume_the_pool`.
* Which Background received the inheritance is not recorded, so the waiver goes to the
  **dearest** above-cap dots the character has — player-favourable, matching how free
  dots are already assigned.
* `validate.background_pool_spend` is new and is now the ONE place the Background pool
  arithmetic lives. The unspent-dot warning and `bonus_point_breakdown` had two copies
  of it; they would have drifted the moment the waiver landed in only one.
* **Innocuous is the four-point version only.** Its two-point tier is entirely dice
  (bucket B). `background_caps` (Allies/Contacts/Mentor at 2) and `barred_backgrounds`
  (Followers, Henchmen, Cult, Command) are keyed by lowercased NAME, because Backgrounds
  are free text and there is no id to key on. Its "or any other socially dependent
  Backgrounds" and "other Backgrounds contingent on being widely known" clauses are
  Storyteller adjudication and are deliberately not guessed at — only what the page
  names. New issues: `background-barred-by-merit`, `background-above-merit-cap`.
* **Innocuous' Sidereal bar is catalogue data** (`barred_exalt_types`), and the editor's
  Background dot rows now read the per-Background cap, applying A3's rule that a ceiling
  the player can still click past is not a ceiling.
* **Its Appearance 2 prerequisite for the two-point version is still unchecked** — that
  is the trait-prerequisites item (cluster 7), deliberately not done here.

## Cluster 7 — COMPLETE 2026-07-30 (trait prerequisites)

1389 tests pass (was 1377). **Browser-verified 2026-07-31.** Note that the work branch implemented this
cluster independently and clicked THAT version through; the 2026-07-31 merge kept the
desktop's richer shape, so the verification that counts is the post-merge one.
Catalogue data, not effects —
`engine/merits.py` was not touched at all.

**Every entry was re-read for a prerequisite rather than trusting the triage's list of
six.** A scan of all 99 descriptions for requirement language found the same set, and
settled two the triage had left as maybes:

| Entry | Requirement | Namespace |
|---|---|---|
| `mf.innocuous` (2-pt tier ONLY) | Appearance 2 | Attribute |
| `mf.hidden-manse` | Manse (any rating) | Background |
| `mf.cache` | Resources 4 **or** Salary 2 | Background |
| `mf.legendary-breeding` | Breeding 5 | Background |
| `thaum.celestial-travel-permit` | Celestial Patron 2 | Background |
| `mf.alternative-divination` | at most **Occult** purchases | Ability (repeat cap) |

* **`mf.large-size` was NOT given one.** "**Most** characters with this Merit have both
  Strength and Stamina rated at 3 or higher" (p.20) is descriptive, and
  `test_large_size_is_not_given_a_prerequisite` exists to stop a later pass promoting it
  into a rule.
* **`mf.damaged-artifact` was NOT given one either** — its "at least one more dot of
  Artifact" is the SAME rule A6 already ships as `points_limited_by`, and encoding it
  twice would report it twice.
* **`mf.destiny`'s "Destiny 4 or better"** is flavour about how Sidereals come by it,
  not a purchase gate. Skipped.

**Shape.** `MeritFlaw.trait_prerequisites` is `{tier: [[TraitRequirement]]}`:

* **Keyed by TIER**, because Innocuous' Appearance gate applies to its two-point version
  and not its four-point one. `""` is the requirement every tier carries.
* **AND-of-OR inside**, the same shape `Charm.prerequisites` uses and for the same
  reason — Cache is one OR group of two.
* **`TraitRequirement.trait` is a NAME, not an id**, resolved by `validate.trait_rating`
  across Attributes → Abilities → Virtues → Backgrounds. The six entries span all four,
  and Backgrounds are free text with no id to reference in the first place. An
  unresolvable name reads as 0 and the requirement fails, per the graceful-unresolvable
  rule. No 1e trait name collides across those namespaces.
* Alternative Divination is a REPEAT cap rather than a rating floor, so it is its own
  field, `max_purchases_from_trait`. New issues: `merit-trait-prerequisite`,
  `merit-repeats-above-trait`.

**The one real interaction, and it is pinned:** Legendary Breeding grants an effective
Breeding of 6 and REQUIRES Breeding 5. `trait_rating` reads the purchased rating, so the
Merit cannot satisfy its own prerequisite —
`test_legendary_breeding_does_not_satisfy_its_own_prerequisite`. This closes the gap A5
recorded explicitly.

**The editor now shows the requirement in the Merit row.** It had never displayed
prerequisites of any kind — not the Merit-id ones, not `prerequisite_note` — so the only
feedback was an issue after the fact.

## A7 — COMPLETE 2026-07-30 (play-state pools and tracks). **The A-list is DONE.**

Lucky, Unlucky, Greater Curse, Death's Taint. 1403 tests pass (was 1389).
**Browser-verified 2026-07-31.** A7's click-through is where permanent Resonance turned out to be in the
wrong shape — see `merits-flaws.md`. **The whole A-list is now browser-verified.**

**The blocking rename landed first:** `data/exalts.json` gives Abyssal
`limit_label: "Resonance"`, exactly as Sidereal reads "Paradox". A label, not a second
mechanic — `derive.limit_label` already existed and needed no change.

* `MeritEffects` gained `luck_pool`, `bad_luck_pool`, `limit_max` and
  `permanent_limit_start`. Four new `derive` reads: `limit_max`,
  `permanent_limit_cap`, `permanent_limit_start`, `luck_pools`.
* **Greater Curse is a subtraction from the constant 10**, per ruling 5 — no derivation
  of the maximum was needed. `merits.LIMIT_MAX` is the one source, and the play
  tracker's three hardcoded `10`s now read `derive.limit_max`. The page's own worked
  example is the test: three points → Limit Break at seven.
* **Sidereal Lucky is a band, not a bonus**: `min(5, max(3, points + 2))`. Its
  "1- TO 3-PT. FOR SIDEREALS" price was already authored as a per-splat cost override,
  so nothing was needed there.
* **Death's Taint's starting permanent Resonance comes out of the price** — `points − 4`,
  the same trick A1 established, so no new field. `permanent_limit_start` is
  `None`/`0`-distinct on purpose: a character may hold the Flaw and start clean, which
  is what its base four-point value buys, and a sheet must be able to tell that from not
  holding it at all.
* `Character.limit_permanent` is the only new stored field, capped at Essence by the page
  (`derive.permanent_limit_cap`). **⚠ AMENDED 2026-07-31: it also SHORTENS the temporary
  track** — ruled by the human, "cumulative with temporary Resonance" (p.41) means it
  occupies the 10 rather than riding beside it, so 2 permanent leaves a track of 8. It
  had been built as a separate rating next to a full track. `derive.limit_max` subtracts
  it alongside Greater Curse. **It was first written onto `PlayState` — see the
  CORRECTION below for why that was wrong.**
* **The tracker does NOT seed itself.** It reports "began play with N permanent
  Resonance" instead. Seeding would reset a chronicle already in progress every time the
  tab was opened, and the tracker is deliberately dumb (`ui/play.py` docstring).
  **⚠ AMENDED 2026-07-31: nothing else seeded it either.** `permanent_limit_start` was
  derived and read by NOTHING, so the price above the base four points bought a starting
  rating that never reached the character. The seed belongs at LOCK, not in the tracker —
  `lifecycle.lock_chargen` now does it, guarded so it never overwrites a track the XP
  ledger has moved. The reasoning above is still right about the tracker; it was wrong to
  conclude no one had to do it.
* **`ui/play.py` imports `engine.merits` for `LIMIT_MAX` only.** Reading a constant is
  not branching on a Merit id, which is what decision 0011 forbids; the containment test
  greps for ids and is unaffected.

**Deliberately out, all of it decision 0009:** spending luck to reroll, the 10%-per-point
game-of-chance rule, and the Storyteller's forced rerolls. The pools are counters.

**Death's Taint's five-XP shed IS modelled** — see the correction below. Only the
**Harrowing** is out, and permanently: it is a story requirement of the same class as
training time, which is almost certainly never being added (human, 2026-07-30).

### CORRECTION (2026-07-30, same day): permanent Resonance was in the wrong layer

`limit_permanent` was first written onto `PlayState` beside the temporary track, and the
five-XP shed was written off as forbidden by decision 0006. **Both were wrong, and 0006
says so in its own last bullet:** "permanent trait *reductions* (curses) are a different
thing and live on the XP ledger, not here."

Permanent Resonance is bought at chargen, gained in play, shed for XP and capped at
Essence — only the second of those is play-state. Its temporary counterpart
(`PlayState.limit`) was correct all along; the two share a name, not a layer.

Now: `Character.limit_permanent`, with `advancement.gain_permanent_resonance` (free —
inflicted, not bought) and `advancement.shed_permanent_resonance` (five XP), both logged
so the trait has an audit trail like every other permanent one. The play tracker shows it
READ-ONLY, because it is "cumulative with temporary Resonance" and the ST needs the total
at the table, and points at the XP tab, which has the controls.

**The trap, and why it needs its own target.** `_expected_cost` prices any row whose
`to_rating` is below its `from_rating` at 0 — the curse rule — which would have reported
the five-point shed as `xp-cost-mismatch` on every later validation.
`validate.PERMANENT_RESONANCE_TARGET` is tested BEFORE that rule and prices per
direction. Same distinct-target pattern as `charms_withheld`, for the same reason.

**The GHOST half of Death's Taint is unauthored** ("Ghosts with this Flaw do not contend
with Resonance in any form, but instead suffer the tainting of their Passions by the
Whisper of Oblivion"). Passions and Whispers arrive with the Ghost splat, which is one of
the four non-Exalt splats still blocked on source material.

---

**The triage's A-list is complete.** A1-A7 plus trait prerequisites: 26 entries, 8
mechanisms, all shipped. What remains on M&F is the **browser click-through** (A6,
cluster 7 and A7 are unverified) and the three known UI gaps listed at the top of this
file.

## Source-fidelity pass (2026-07-30)

The human re-pasted the chapter after Amputee turned up truncated. Rather than fix the
one entry by hand, every `mf.*` description was diffed against its section of
`images/Merits & Flaws/CH 1 - Merits and Flaws.md` by normalised length. That found a
second, worse problem nobody had noticed:

* **`mf.amputee`** was at **12%** of its printed body — cut off mid-word at *"Alter-"*,
  with the tail of the NEXT entry glued on. Re-extracted in full.
* **`mf.dying` (p.31) was missing from the catalogue entirely.** Its opening had been
  lost and its tail was what had been glued onto Amputee. Authored from the source:
  2/4/6/10-pt Flaw, one Stamina dot lost per interval (annual / months / weeks / days).
  The general chapter is **88 entries, not 87**; the catalogue is **99**.

`test_every_description_matches_the_source_text` now pins this: it re-runs the same diff
over every entry and fails on anything below 92% of its source section. It skips when
`images/` is absent, since the source is gitignored and does not travel with a clone.

**The lesson, again:** a truncated description is invisible to every test that checks
counts, costs and links — all of which passed. Only comparing against the source found
it. Diff mechanically; do not spot-read.
