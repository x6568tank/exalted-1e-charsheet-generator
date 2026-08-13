# 0017 — Artifacts have two acquisition channels: the Background and cash

**Status:** Accepted, 2026-08-13. Refines how
[0007](0007-ids-for-invariant-inline-for-variable.md)'s inline-copy gear and the p.131
Artifact budget relate; does not touch the budget rules themselves.

## Problem

Manacle and Coin pp.122-125 prices wonders in Resources — "Daiklave ••••", "Grand
Daiklave •••••", "Hearthstone Amulet •••" — while `data/artifacts.json` rates that same
daiklave **Artifact ••**. Read as one number in two books, that is a contradiction, and
the obvious readings are both wrong: pick one and the other book's table becomes
unauthorable; average them and neither is right.

It surfaced the day the corebook one-artifact rule shipped, because that rule makes the
question sharp: if cash can buy artifacts, a character with Resources •••• has a hoard
the Artifact Background never paid for and the rule constrains nothing.

## The two numbers measure different things, and the corebook says so

Every gear table in the corebook defines its Artifact column the same way:

> **Artifact** — The number of dots in the Artifact Background the character must spend
> **to start the game owning** one of these weapons. — core p.342 (p.345 repeats it for
> armour)

So the Background is the **pre-game** channel by printed definition, not merely by
narrative implication. Manacle and Coin is explicit that it supplies the other half:

> These pages closely follow the Wonders and Equipment tables on **pp. 324-346** in the
> main *Exalted* book, but there are some minor additions. — M&C p.122

Artifact •• is what it costs to *begin play* holding a daiklave; Resources •••• is what
it costs to *buy* one from the Guild or a craftsman. Both are printed, and they do not
compete.

## Decision

An owned artifact records **how it was acquired** (`acquired`: `background` or
`purchased`), and:

1. **Only Background-funded artifacts are charged to the Artifact budget** — the p.131
   tiers, the multiplier rules and the corebook one-artifact rule all read
   `artifacts.budgeted_items`. A purchased artifact is equipment paid for in cash.
2. **Everything owned is still owned.** `artifact_items` is unchanged and remains the
   ONE enumeration; Damaged Artifact, the sheet, the dice-pool weapon list and the
   pickers all read it. A bought daiklave can be damaged, attuned and swung.
3. **Artifacts may not be purchased at character creation** (`artifact-purchased-at-
   chargen`). This is the load-bearing half — see below.
4. **No money is tracked.** Resources stays an affordability HINT, never a validation
   (core p.325's own rule contradicts an ownership invariant in its middle clause), so
   buying an artifact deducts nothing and the build does not know what a character can
   afford. Nothing here changes that.

## Why the chargen bar is not optional

`acquired` is a discriminator the player is **meant** to edit — unlike
`Weapon.from_artifact`, which is set once and editable by nothing on screen. That makes
it a hole straight through the Artifact budget by construction: mark every artifact
purchased and the Background stops binding.

The bar closes it at the only phase where it matters. Creation is what the budget exists
to constrain, and it is precisely the phase the printed phrase excludes — you cannot
"start the game owning" something you bought during play. Post-lock the check is silent,
because buying things with money is the entire point of the other channel.

⚠ **This is the catalogue-dialog scar pointed at a field where the edit is legitimate.**
The rule there was "a discriminator must be a field nothing on the screen can edit". Here
the player must be able to edit it, so the protection moves from the field to the
lifecycle. When you add a player-editable flag that switches a rule off, ask what stops
it being switched off in the phase the rule is for.

## Alternatives rejected

* **Cash cannot buy artifacts; ignore M&C p.125.** Discards a printed table for a
  conflict that does not exist once the two columns are read as different questions.
* **One number: make Resources cost derive from the Artifact rating.** They do not
  correlate (Artifact •• ↔ Resources ••••, Artifact ••• ↔ Resources ••••• on the same
  page), and inventing a conversion is authoring a rule from nothing.
* **Purchase allowed at chargen behind a `HouseRules` toggle.** Offered and declined
  (human, 2026-08-13). A toggle would be the right shape if the books were silent, but
  they are not — p.342 says what the Background is *for*.
* **Let purchased artifacts count toward the budget anyway.** Then the two channels are
  one channel with extra typing, and a character who buys a sword in play retroactively
  breaks a chargen-legal build.

## Cost

The budget can be evaded post-lock by flagging artifacts purchased, and the build will
not object — by design, since it tracks no money and cannot tell whether a character
could afford the thing. That is the Storyteller's call, consistent with every other
Resources decision here. A group that wants purchases audited has the same recourse they
have for Resources generally: the sheet reports, the table rules.
