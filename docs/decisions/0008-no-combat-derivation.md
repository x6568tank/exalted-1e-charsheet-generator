# 0008 — No combat or attack derivation

**Status:** Accepted, 2026-07-22. Out of scope, not deferred.

## Problem

The app knows a character's Dexterity, Melee, specialties, Charms and weapon stats. Deriving
attack pools, damage and soak interactions from that is an obvious next step, and every
character sheet is asked for it eventually.

## Alternatives

* **Build it.** Requires modelling Charm effects on rolls, which means modelling Charm
  *effects* generally — an open-ended job on 1,470 Charms, and the exact thing that made
  the old Merits & Flaws implementation unmaintainable ([0011](0011-merits-and-flaws-return-centralized.md)).
* **Build a partial version** — a static attack line ignoring Charms. Worse than nothing:
  it looks authoritative and is wrong the moment a Charm fires.

## Decision

**Weapons and armor are display-only.** No attack-roll engine, no damage derivation, no
special mounted profiles.

## Consequences

* Weapon and armor stats are shown as printed and never combined into a derived total.
* Soak *is* derived, because it follows from armor and Stamina alone and does not need an
  attack to exist.
* Do not build this without the maintainer explicitly reopening it. See also
  [0009](0009-no-dice-rolling.md), which is broader.
