# 0004 — Chargen and advancement are different shapes

**Status:** Accepted. Predates the status log.

## Problem

Before play, a character is a set of values that must satisfy a budget. After play, it is
a history of purchases that must each have been paid for. Treating those as one mode
means either the budget keeps applying forever, or it stops applying and nothing checks
the spending.

## Alternatives

* **One mode, budgets enforced only pre-lock.** Simple, and unable to audit XP at all.
* **A ledger from the start**, chargen included, with pools as opening balances. Uniform,
  but it forces [0003](0003-current-state-is-canonical.md)'s per-dot tagging back in.

## Decision

Two shapes with an explicit transition:

* **Pre-lock** — a *constraint snapshot*. Current traits are validated against
  `ChargenBudgets`. Nothing is recorded about how they got there.
* **`lock_chargen()`** — deep-copies every purchasable collection into a
  `ChargenSnapshot`, which becomes the XP baseline.
* **Post-lock** — an *append-only* `xp_log`. `advancement.validate_xp` reconciles current
  state against snapshot + log and re-prices every entry.

## Consequences

* Post-lock removal is undo-only (LIFO against the log), not free editing.
* The XP tab and the Edit tab are one tab slot showing two sides of the same character;
  Charms and Combos switch from picking to buying rather than being duplicated.
* Hand-edited saves that drift from snapshot + log are *detected* rather than repaired.
  Full state reconciliation is deliberately not built — the read-only lock guards normal
  use.
* `unlock_chargen()` exists as the escape hatch, and re-locking re-snapshots.
