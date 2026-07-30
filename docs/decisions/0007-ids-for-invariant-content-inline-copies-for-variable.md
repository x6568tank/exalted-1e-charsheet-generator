# 0007 — Ids for invariant content, inline copies for variable content

**Status:** Accepted. Predates the status log.

## Problem

A character references rulebook content. Two ways to store the reference: point at the
catalogue by id, or copy the thing onto the character. Charms and named artifacts pull in
opposite directions — a Charm is identical for everyone who knows it, while an artifact
gets renamed, re-statted and attuned per character.

## Alternatives

* **Ids for everything.** Every custom weapon then needs a catalogue entry, and the
  catalogue fills with one-off junk.
* **Copies for everything.** Saves balloon, and a Charm text fix never reaches the
  characters that already know it.

## Decision

Split by whether the thing varies between characters:

* **Referenced by id** — Charms and spells. They never vary.
* **Inline copies on the character** — weapons, armor. They vary constantly.
* **Soft free text with a catalogue as autofill** — Backgrounds. `BackgroundEntry.name`
  is a name, not an id.

## Consequences

* Fixing a Charm's text or cost fixes it everywhere at once; fixing a weapon in the
  catalogue does not touch existing characters, which is correct for both.
* Ids must be stable and namespaced (`solar.melee.fire-and-stones-strike`). Renaming a
  Charm is free; changing its id is a migration.
* A referenced id can go missing, so every consumer degrades gracefully — a missing Charm
  still shows as a row, plus an `unknown-charm` error.
* One deliberate exception to Backgrounds being purely soft:
  `ChargenBudgets.background_rules` attaches per-splat chargen mechanics to a Background
  **by name** (added for the Alchemical; empty for every other splat).
