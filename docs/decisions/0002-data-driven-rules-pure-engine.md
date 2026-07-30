# 0002 — The rulebook is data; the engine is pure; the UI is disposable

**Status:** Accepted. Predates the status log.

## Problem

A character builder for a crunchy system can be written as a UI that knows the rules,
or as a rules engine with a UI attached. The first is faster to start and impossible to
finish: every rule ends up spread across the widgets that display it, and no rule can be
tested without a browser.

## Alternatives

* **Rules in the UI**, validated on edit. Fastest to a demo. Rejected — untestable, and
  every new splat touches every screen.
* **Rules in code but not in the UI**, with Charms as Python objects. Better, but every
  Charm becomes a code change and a diff nobody can read against a page.

## Decision

Three layers, dependencies running one way — `ui → engine → models`:

* **The rulebook is JSON** under `data/`, loaded once into an immutable `RuleSet`.
* **The engine is pure**: validation and derivation are functions of
  `(RuleSet, Character)` — no I/O, no UI, no mutation.
* **The UI contains zero game logic** and can be thrown away and rewritten.

## Consequences

* Adding printed *content* is a data change. Adding a splat's novel *subsystem* is not —
  Charm Slots, Astrological Colleges and Attribute-keyed Charms were all engine work.
  The promise covers content, not mechanics nobody has modelled. Say so publicly rather
  than implying otherwise.
* Data errors need catching at load, not at render: `rules_db` link-checks every
  prerequisite and spell circle and accumulates all problems into one raise.
* `engine/validate.py` grows large (~3,100 lines) because it is where the rules live.
  That is the intended shape, not neglect.
* Presenter logic sits in `ui/view.py`, which imports no toolkit, so most UI behaviour
  is unit-testable without a browser.
