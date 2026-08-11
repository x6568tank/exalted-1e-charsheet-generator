# 0015 — The Exalt tiers are a RANKED hierarchy, not a flat label

**Accepted 2026-08-11.** Human, rules authority.

## The rule

Three tiers, low to high:

| Tier | Splats |
|---|---|
| **Terrestrial** | Dragon-Blooded — the only Terrestrial Exalts |
| **Celestial** | Lunars, Sidereals, Abyssals, **Alchemicals** |
| **Solar** | the Solar Exalted, above all |

**A splat reaches its own tier and every tier below it. Nothing reaches up.** A Solar
may learn Celestial and Terrestrial martial arts; a Celestial may learn Terrestrial; a
Terrestrial reaches only Terrestrial. Lunars and Sidereals cannot touch Solar-tier
material.

`Charm.open_to_tiers` names the *Charm's* tier; access is
`character rank >= charm rank`, via `validate.tier_reaches`.

## What it replaced, and why that was wrong

`ExaltDefinition.tier` was matched by **exact string equality**. "Celestial or below"
was therefore inexpressible, and the consequences were all workarounds:

* **Solar was authored `tier: "Celestial"`** — not a taxonomy, a lie told to make
  Solars reach Celestial martial arts at all.
* **Alchemical was `tier: "Alchemical"`**, matching nothing, so Perfected Lotus Matrix
  had to be **hardcoded by id** in `engine/validate.py` to grant what the tier system
  should have handled.
* Every case needing the hierarchy grew its own patch. The human's words on being shown
  the model: *"it explains a lot of the random issues we've been having with
  Terrestrial/Celestial/Solar gating."*

## Alternatives rejected

* **Keep exact-match and list every tier on every Charm** (`["Celestial", "Solar"]`).
  Works, and is wrong in the way that costs later: it pushes the hierarchy into 140
  data rows, so adding a splat or a tier means editing all of them, and a row that
  forgets one tier fails silently.
* **Keep Solar labelled `Celestial`.** Cheapest, and the status quo — but it makes the
  data lie about the fiction, and it cannot express anything Solar-only.
* **Give Alchemicals `tier: "Celestial"` and drop the Perfected Lotus Matrix gate.**
  Rejected by the human: an Alchemical *is* a Celestial Exalt, but still reaches **no**
  martial arts of any tier without PLM installed (CH3 p.100). The tier says what she
  could reach; PLM says whether she may.

## What it costs

* **`tier` is now load-bearing in a way a string label was not.** A new splat must be
  placed in the hierarchy deliberately; `tier_rank` returns -1 for anything outside it
  (Mortal, Ghost, Alchemical's old value), and a -1 splat reaches **nothing** by rank.
  A typo in the tier string silently closes every tiered Charm to that splat.
* **The Alchemical bar is a splat named in code.** `charm_matches_splat` tests
  `character.exalt_type == "Alchemical"` for the martial-arts bar. That is the shape
  this codebase otherwise avoids, and it is accepted here because the rule genuinely is
  splat-specific and rides on a hardcoded Charm id already (`PERFECTED_LOTUS_MATRIX_ID`).
  If a second splat ever gates martial arts behind a Charm, this becomes a data field.
* **The bar's POSITION is load-bearing** and untested code could re-break it: it must
  sit **above** the `open_to_all` grant, because the Terrestrial styles are
  `open_to_all` and would otherwise be handed out before any tier reasoning ran. That
  bug shipped in the first version of this change and was caught at the browser.

## Where it lives

`validate.TIER_ORDER`, `validate.tier_rank`, `validate.tier_reaches`,
`validate.charm_matches_splat`; the tiers themselves in `data/exalts.json`.
Tests: `tests/test_celestial_martial_arts.py`.
