# 0001 — First Edition only, never 2e

**Status:** Accepted. Predates the status log; it is the project's founding premise.

## Problem

Exalted has four editions plus Essence. Every surviving tool targets 2e/2.5e or later;
1e is unserved, which is the entire reason this project exists. But 1e and 2e differ in
costs, Charm text, Essence formulas, the Ability roster and much else, and 2e is far
better represented everywhere — in search results, in wikis, in any language model's
training data.

## Alternatives

* **Support several editions behind a switch.** Doubles or triples the data, and every
  rule becomes a per-edition branch. The 2e audience is already served.
* **Support 1e "plus obvious 2e improvements."** Rejected outright: there is no stable
  line between an improvement and a different game, and the result would be a house
  edition nobody has books for.

## Decision

**1e only, and the 1e books are the sole authority.** Where the editions differ, this
project is 1e. A value goes into `data/` only if it came from a 1e page the maintainer
supplied. Anyone who wants 2.5e support forks the project.

## Consequences

* The dominant failure mode is silently "correcting" a 1e value to its 2e equivalent —
  it will feel right and be wrong. Hence the never-author-from-memory rule and the
  human-curated source pipeline (`images/<Splat>/`), both in `CLAUDE.md`.
* Concrete tripwires that catch it: Martial Arts is a separate Ability from Brawl, and
  there is no "War" Ability in 1e core.
* Contributions must cite a book and page. A patch that cannot is refused, however
  confident it sounds.
