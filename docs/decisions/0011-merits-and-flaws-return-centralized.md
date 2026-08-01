# 0011 — Merits & Flaws return as one centralized calculation

**Status:** Accepted and implemented 2026-07-30 — pulled FORWARD of the non-Exalt splats
rather than following them, because mortals shipped with no route to magic and that route
runs through Merits. Build record: `docs/status/merits-flaws.md`.

## Problem

The original Merits & Flaws implementation scattered mechanical effects across every file
they touched — health levels here, trait caps there, XP formula overrides somewhere else —
and bundled Charm rewrites that wrecked the point balance. It was removed rather than
patched.

## Alternatives

* **Leave them out permanently.** Loses a real part of the system.
* **Reintroduce the old per-file hooks.** Rejected — that shape is why it was removed.

## Decision

M&F come back as **one centralized `merits_and_flaws_calc`** returning every effect it can
have, with no per-file hooks anywhere else. The known effect surface, from the three
examples worked through (Large Size, Legendary Attribute, Prodigy), is:

1. bonus health levels
2. trait maximum overrides
3. added Favoured abilities
4. XP formula changes — an **offset**, not merely a multiplier
5. splat gates
6. dice modifiers

Scheduled **after** the six non-Exalt splats, because several M&F are mortal-only and the
mortal rules define the surface.

## Consequences

* Until that work starts, do not reintroduce the old hooks in any form.
* The Essence-based Attribute cap is a *mortals* rule and is not modelled yet; the
  engine's flat cap of 5 is correct until then.
