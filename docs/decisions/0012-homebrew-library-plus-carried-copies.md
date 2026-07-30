# 0012 — Homebrew: a library is the store, saves carry copies

**Status:** Accepted, 2026-07-29. Implemented; see `docs/status/custom-content.md`.

## Problem

Users want their own Charms, Martial Arts styles and spells. Characters reference Charms
by id ([0007](0007-ids-for-invariant-content-inline-copies-for-variable.md)), so homebrew
ids resolve only against whatever library defined them — and a character handed to another
player would arrive full of dead references.

## Alternatives

* **A library only.** Reusable across characters, one merge point, but a save sent
  elsewhere loses its Charms.
* **Definitions embedded in the character only.** Portable, but there is no reusable
  library, and every engine call site would need a per-character merged `RuleSet`.

## Decision

**Both, with the library as the store.** A `custom/` library is merged over the book data
at load; on save, a character embeds copies of exactly the definitions it references (plus
their prerequisite closure); on load, definitions it carries that the local library lacks
are absorbed into it.

Supporting rules, each load-bearing:

* **Book data errors stay fatal; homebrew errors never are.** A bad custom row is dropped
  and reported on `RuleSet.custom_problems`. A typo must not stop the app from starting.
* **The book wins an id collision**, and page-authored ids are forced to a `custom.`
  prefix, so shadowing printed content is impossible by construction.
* **The local library wins an absorb conflict** — opening someone's character never
  reverts your own edit of the same id.
* **Homebrew is marked wherever it is read** (✎ on the sheet, in the picker, on the Charm
  tree), so it is never mistaken for printed content.

## Consequences

* Embed/absorb live in `persistence`, not the UI: there are ~20 save/load call sites and
  one of them would have been missed.
* Definitions are re-derived from the library on every save, *except* rows the local
  library does not have — those are carried verbatim, or re-saving someone else's
  character would strip their homebrew out.
* Deleting a custom Charm a character owns is allowed and leaves a marked missing row
  rather than being blocked; the id comes back if it is re-created.
* The never-author-from-memory rule of [0001](0001-first-edition-only.md) applies to
  `data/` only. The user's library is theirs.
