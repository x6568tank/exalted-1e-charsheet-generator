# Rated artifacts — DONE (2026-08-02), browser-verified 2026-08-05

Individual artifacts are now rated objects. Two printed rules that could not be
expressed before are implemented: the loyal Abyssal's Artifact **budget** (E:Ab p.131)
and Damaged Artifact's **per-item** point limit (PG p.38), plus the one mechanical
effect of that Flaw this build can derive.

**1,835 tests** (was 1,794). 41 new in `tests/test_rated_artifacts.py`.
Preflight clean; **browser-verified 2026-08-05** (clicked through, no findings).

**One wish for later, from the click-through:** the standalone-artifact rows currently
use a free-text name input. A **drop-down of the catalog** would be nicer — but no
artifact catalogue exists in `data/` yet (artifacts are free text, like Backgrounds),
so that needs authoring an artifact list before it can be wired. Not started.

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
