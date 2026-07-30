# 0009 — No dice rolling, ever

**Status:** Accepted, 2026-07-29. Stated publicly as a design goal in the README.

## Problem

Once an app knows a character's dice pools, adding a roller is a small change with obvious
appeal, and it is the single most requested feature of any character tool.

## Alternatives

* **A general dice roller.** Small to build; changes what the project is.
* **A narrow one** — "just for Feats of Strength", or a probability readout rather than a
  roll. The same thing with a smaller opening, and the opening only ever widens.

## Decision

**No dice rolling of any kind.** Not a roller, not a scoped roller, not a success-odds
display. This is a character builder and tracker and nothing else; it is not becoming a
CRPG.

## Consequences

* Broader than [0008](0008-no-combat-derivation.md): that one bars an attack engine, this
  one bars rolling anything at all, including outside combat.
* Dice pools may be *displayed* where the book prints them as a trait, since that is
  reading the sheet, not resolving an action.
* Do not propose it. In the maintainer's words: "If I do, kill me."
