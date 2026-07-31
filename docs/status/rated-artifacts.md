# Rated artifacts — DEFERRED, sourced and planned (2026-07-30)

**Nothing here is implemented.** This file exists because the source page is transcribed
below and `images/` is gitignored, so this is the only copy that travels with a clone.

Human's call (2026-07-30): **cluster 7 of the M&F triage first**, then this.

## How it came up

A6 shipped Damaged Artifact's point limit as "points ≤ Artifact rating − 1", checked
against the character's TOTAL Artifact Background (`MeritFlaw.points_limited_by`). The
printed rule is per-item — "the rating of the artifact it modifies" — and the build has
no individual artifacts to point at.

**Ruling (human, rules authority, 2026-07-30): worth closing. It should work on a
specific Artifact.** Today a character with two Artifact rows (4 and 2) can take the
three-point Flaw against the two-dot daiklave, because the check sums to 6.

## Source: Abyssal Artifact Background (E:Ab p.131)

Transcribed from `images/Abyssals/Traits/130-131.png`. The Abyssal Artifact Background
is **not a cost curve** — it is a BUDGET of combined Artifact rating, plus a per-item
ceiling:

| Rating | Name | Combined Artifact rating | Individual cap |
|---|---|---|---|
| × | None | — | — |
| • | Trinkets | no higher than 3 | — |
| •• | Sound Gear | no higher than 5 | none individually above Artifact 3 without ST permission |
| ••• | Well-Equipped | no higher than 7 | none individually above Artifact 4 without ST permission |
| •••• | Supremely Appointed | no higher than 10 | no limit on individual level, other than it cannot be N/A |
| ••••• | Divine Regalia | no higher than 13 | no limit on individual level, other than it cannot be N/A |

**The loyal/renegade split is already modelled.** "This alteration of the Artifacts
Background only applies to those Abyssals who continue to faithfully serve their
Deathlords. Renegade Abyssals use the Artifact Background found in Chapter Four: Traits
of the main **Exalted** rulebook." That is exactly the existing origin axis — `Abyssal`
(loyal, 13 Background dots) takes the table above, `Abyssal:fugitive` takes core. No new
axis is needed.

Also on the page, not required for this work: artifacts of the dead "can be purchased for
their normal Artifact value, but… are of no use outside the Underworld"; all deathknight
artifacts are soulsteel unless the ST permits otherwise; no Abyssal in a Deathlord's
service may begin with Backing or Mentor (they use Liege instead).

**This confirms the Player's Guide worked example** under Damaged Artifact (p.38): a
combined rating of 4 needs Abyssal Artifact ••, hence "it would cost only two Background
points to obtain the wings with the Abyssal version of the Artifact Background".

## What it would take

The two rulings converge on one prerequisite: **individual artifacts as rated objects.**
Weapons and armour already carry `artifact_rating` (`character.Weapon` / `character.Armor`),
but the book's own example — the tattered wings of the raptor — is neither, and nothing
links a `BackgroundEntry` to an item.

1. **An artifact list on the character** (name + rating), with the existing weapon and
   armour `artifact_rating` fields folding into it rather than duplicating it.
2. **The p.131 budget rule** — combined cap and individual cap per Background dot, keyed
   by splat + origin, so it applies to `Abyssal` and not to `Abyssal:fugitive` or to any
   other splat. Shape to consider: an extension of `BackgroundRule`, which already
   carries per-Background chargen mechanics.
3. **Damaged Artifact pointing at a specific entry** — `MeritFlawPurchase` gains a
   reference, and `BackgroundPointLimit` gains a `per_entry` flag so the limit reads the
   referenced item instead of the summed total.

Rough size: about a day. It is a splat feature that A6 happened to surface, not an M&F
cluster.

## The Flaw's EFFECT on armour — RULED, not yet implemented

Damaged Artifact's mechanical effect is mostly decision 0008 (a weapon losing damage or
accuracy is combat derivation, which this build does not do). **Armour soak is the
exception** — `derive.soak` exists, so "armor loses an equivalent number of points from
its lethal and bashing soak" is implementable.

**Ruling (human, rules authority, 2026-07-30): the two-point tier's "six points from
weapons and armor" splits evenly — 3 lethal and 3 bashing**, reading "an equivalent
number of points from its **lethal and bashing** soak" as applying to each track.

That scales consistently across the tiers, which is the argument for it:

| Points | Printed | Armour soak |
|---|---|---|
| 1 | "minor damage… a point… an equivalent number of points" | −1 lethal, −1 bashing |
| 2 | "major damage, costing six points" | −3 lethal, −3 bashing |
| 3 | "near-total damage. The artifact is presently useless" | unusable — no soak at all |

⚠ **Confirm the tier-1 row before implementing.** It is an INFERENCE from the ruling,
not something the human stated: the page's "a point… an equivalent number" is what the
even split is being applied to, so one point comes off each track. The alternative
reading — one point TOTAL, split half and half — does not divide, which is why this one
is preferred. Ask before coding it.

Soak floors at 0 in every case; a damaged artifact never soaks negatively.
