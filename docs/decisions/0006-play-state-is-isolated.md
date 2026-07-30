# 0006 — Play-state is a separate, validation-isolated layer

**Status:** Accepted, 2026-06-16. Reverses the original decision to exclude play-state.

## Problem

Tracking a character in play — spent motes, marked health, temporary Willpower, Limit —
is genuinely useful, and was originally out of scope for exactly the right reason: it is
ephemeral, and if it leaks into the permanent character it corrupts both the chargen
validation and the XP audit.

## Alternatives

* **Stay out of scope.** Safe, and leaves everyone with a paper sheet next to the app.
* **Model it properly** — auto-deduct motes on Charm activation, wrap damage across the
  health track, heal over time. Big, rules-heavy, and needs the combat engine that
  [0008](0008-no-combat-derivation.md) refuses.

## Decision

Include it as a **deliberately dumb manual tracker** on `Character.play`
(`PlayState`, optional so old saves load with it `None`), and make the isolation a hard
rule:

* **Play-state must NOT enter chargen validation, the XP audit, or any permanent
  derivation.**
* Capacities flow **out** of the engine into the tracker — the health track, Essence
  pools, permanent Willpower. Nothing flows back.

## Consequences

* No auto mote-accounting, no damage-wrapping, no auto-healing. The user marks boxes.
* The Play tab and the GM party cards edit play-state (and notes) only.
* Still excluded: Virtue channels and the Resources purchase transaction.
* Permanent trait *reductions* (curses) are a different thing and live on the XP ledger,
  not here — see [0004](0004-chargen-and-advancement-are-different-shapes.md).
