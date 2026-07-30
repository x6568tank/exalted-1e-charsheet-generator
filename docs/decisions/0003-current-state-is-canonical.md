# 0003 — Current state is canonical; the engine computes the accounting

**Status:** Accepted. Predates the status log.

## Problem

Chargen spends from several currencies at once — prioritised Attribute pools, an Ability
pool with Caste/Favoured minimums, Charm picks, and bonus points that can top up
anything. Something has to decide which currency paid for a given dot.

## Alternatives

* **Tag each dot with the currency that bought it.** Exact, and miserable: the user
  answers accounting questions instead of building a character, and every edit
  invalidates earlier tags.
* **Wizard-style irreversible steps**, spending pools in a fixed order. Matches the
  book's presentation but makes a late change mean starting over.

## Decision

**The character's current trait values are the truth, and the engine derives the
accounting from them.** The user sets ratings; `engine/costs.py` works out what the pools
covered and what bonus points had to make up.

## Consequences

* Editing is free-form and order-independent; nothing is irreversible before the lock.
* The engine must *minimise* bonus-point spend rather than read it off the character —
  and one accepted edge falls out of that: Caste/Favoured minimums are checked separately
  from the minimisation, so an exotic build can be told it is short on a minimum while
  the BP total is already optimal.
* The sheet can always explain a cost, because the cost is computed, never stored.
