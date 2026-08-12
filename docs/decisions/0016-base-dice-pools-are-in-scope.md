# 0016 — Base dice pools are in scope; resolution is not

**Status:** Accepted, 2026-08-12. Amends the boundary of
[0008](0008-no-combat-derivation.md); does not touch [0009](0009-no-dice-rolling.md).

## Problem

A player at the table needs one number the sheet can already answer: *how many dice do I
pick up?* To-hit is Dexterity + Melee; a Virtue check is the Virtue's rating; a Willpower
check is Willpower. Every one of those traits is on the sheet, and the arithmetic is
addition.

But [0008](0008-no-combat-derivation.md) says "no attack-roll engine", and a Dexterity +
Melee + accuracy total is recognisably an attack pool. Read literally, 0008 forbids it —
so the boundary needed restating rather than quietly stretching.

## Alternatives

* **Refuse it, citing 0008.** Costs the single most-asked-for number in play, to protect
  a line drawn against a different thing (resolution).
* **Build it as a full attack line** — pool, damage, soak interaction, Charm effects.
  This is what 0008 actually rejected, and its reasoning is unchanged: modelling Charm
  effects on rolls means modelling Charm effects generally, over 1,836 Charms, which is
  what made the old Merits & Flaws implementation unmaintainable
  ([0011](0011-merits-and-flaws-return-centralized.md)).
* **Build the pool, and let it silently omit Charms.** ⚠ This is 0008's *other* rejected
  alternative, near-verbatim: "a static attack line ignoring Charms. Worse than nothing:
  it looks authoritative and is wrong the moment a Charm fires." That objection does not
  evaporate because the feature was renamed, and it is the real risk here.

## Decision

**The app may compute a BASE dice pool. It may not resolve anything.**

The line, in the maintainer's words (2026-08-12): *"0008 is about not rolling
dice/resolving attacks. This would be calculating a base dicepool. There's a thin line
there, but it's there."*

In scope:

* Attribute + Ability, a specialty, and one stat off a chosen weapon (accuracy, etc).
* Virtue checks, Willpower checks, and any other roll whose pool is trait arithmetic.
* Wound penalties and armour mobility/fatigue — these are CHARACTER-derived, not
  Storyteller-supplied, so the pool is wrong without them. They render as separate,
  labelled, toggleable lines rather than being folded silently into the total.

Out of scope, and this is what keeps 0008 intact:

* Rolling (0009 — broader, untouched, and not reopened by this).
* Damage, soak-versus-attack interaction, opposed rolls, initiative — anything needing a
  second party or a result.
* **Charm dice.** They require knowing which Charms are ACTIVE, which is play-state, and
  play-state is validation-isolated ([0006](0006-play-state-is-isolated.md)). No Charm
  effect is modelled for this feature.
* Storyteller modifiers — stunts, disease, environment, difficulty.

## Consequences

* The surface must read as a **base** pool, never a final one. The mitigation for
  0008's "looks authoritative" objection is presentational and therefore load-bearing:
  the output is an itemised breakdown of labelled contributions, not a bare number, and
  it says what it excludes. **A future change that collapses it to one big number
  re-creates exactly the thing 0008 rejected.**
* It lives in a pure `engine/pools.py` returning a breakdown structure, per
  [0002](0002-data-driven-rules-pure-engine.md). The UI adds nothing to the arithmetic.
* Which traits compose a given roll type comes from the printed pages like any other game
  value — never from the model's own knowledge of Exalted (see
  [0001](0001-first-edition-only.md)).
* 0008 stays Accepted and unamended in its own terms; this record narrows what it was
  ever about. If the two are ever read as conflicting, this one is the later and more
  specific.
