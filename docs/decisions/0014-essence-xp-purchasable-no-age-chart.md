# 0014 — Essence is XP-purchasable; the age chart is gone

**Status:** Accepted and implemented 2026-08-06. Build record:
`docs/status/elder-exalts.md` and `docs/status/dragon-kings.md`.

## Problem

Raising permanent Essence past 5 was gated behind an **age chart** (Player's Guide
pp.258-259): 100/6, 250/7, 500/8, 1,000/9, with `Character.age` only settable through
the downtime-XP grant. That surfaced three problems during the Dragon-Kings attribute
work:

1. The age gate hid Essence-raising behind a downtime grant, which was awkward and
   unobvious.
2. The age rules are printed for **Exalts**; the non-Exalt splats (Dragon-Kings, Ghosts,
   God-Blooded, Mortals) have no such rules, and it was unknown how they'd change.
3. The book never states a higher cap than "5 without bonus or experience points" for
   the Dragon-Kings, so an Essence gate that only unlocked via age was an invention.

## Alternatives

* **Keep the age chart; make age editable from chargen.** The human floated this, then
  set it aside — a starting age would let a character collect a century's maturation
  XP for a passage of time never played, and it still forced the age rules onto splats
  that don't have them.
* **Keep the age chart for Exalts; make Essence straight-purchasable only for non-Exalts.**
  More faithful to which splats print the age rules, but split-brain: the same ceiling
  worked two ways depending on the splat, and the Exalts kept the awkward gate.
* **Remove the age chart entirely; Essence is XP-purchasable for everyone.** Chosen.

## Decision

Essence is **XP-purchasable** to the splat's ceiling — the six Exalts set
`essence_cap: 9` (the p.258 chart's printed "9+" taken as a flat number), a Terrestrial
is held at **7** without the ST's "outside energies" toggle (unchanged from before), the
non-Exalts keep their own caps (Dragon-Kings 6, Ghosts 5, God-Blooded 1, Mortals 1).
The age chart and `Character.age` are **removed**. Chargen still caps Essence at 5
(`essence-above-elder-chargen-cap`): no character leaves creation with more. The p.259
downtime calculator survives, but its "Exalted years" field is a **calculator-local
input** (the chart's rate still depends on it), not a character trait, and grants XP
only.

The trait ceiling (`max(5, Essence)`, the p.258 rule binding only above 5) is unchanged
and now the entire elder module.

## Consequences

* `engine/elder.py` shrank to the trait ceiling, the Essence cap (splat + Terrestrial-7),
  and the downtime calculator. `ElderCaps`, `essence_cap_for_age` and the age table are
  deleted.
* An old save carrying `"age"` loads (the field is dropped); nothing reads it.
* The Dragon-Kings' Essence-6 is now XP-reachable (no age), which is what the DK book's
  "cannot exceed Essence 6" alone warrants.
* Training times remain unmodelled; with no age chart, the elder ceilings are no longer
  even partially gated by the passage of in-game time — a known, accepted incompleteness
  (see CLAUDE.md).
