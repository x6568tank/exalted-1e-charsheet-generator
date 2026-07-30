# 0005 — Willpower's Virtue component is pinned at lock

**Status:** Accepted. Predates the status log.

## Problem

At creation, Willpower equals the sum of the two highest Virtues. Raising a Virtue after
creation does **not** raise Willpower. A naive derivation — "Willpower = two highest
Virtues + purchased" — silently gives away free Willpower with every Virtue bought in
play.

## Alternatives

* **Recompute from Virtues always.** Wrong by the rules, and quietly generous.
* **Store total Willpower as a plain number at lock.** Correct for the base, but then
  purchased dots and curse-driven reductions have nothing to compose with, and the sheet
  cannot explain the number.

## Decision

`lock_chargen()` computes and stores **`wp_virtue_component`** — the two highest Virtues
*at the moment of lock*. Permanent Willpower is that pinned component plus purchased
dots. The component is never recomputed.

## Consequences

* Post-creation Virtue gains cannot raise Willpower, which is the rule.
* Re-locking re-snapshots the component, which is the intended escape hatch.
* A curse that reduces permanent Willpower can push `willpower_purchased` negative; the
  engine floors permanent Willpower at 1 rather than forbidding it.
