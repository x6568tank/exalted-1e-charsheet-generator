# Mountain Folk — DONE (2026-08-07)

**Browser-verified 2026-08-07.** The human's click-through found four things, all
fixed same-day: (1) the Enlightenment origin selector was missing from
`_SPLAT_ORIGINS` — no Enlightened/Unenlightened dropdown, so the budget fell back
to the default row (7 Backgrounds, no ceilings, no Cult ban); (2) the Advantages
tab displayed `b.background_dots` rather than the per-caste helper, so an Artisan
read 10 not 13; (3) `limit_label` was never set, so the tracker said "Limit"
instead of "DIVERGENCE" and the Great Geas reference panel never matched; (4)
banned Backgrounds (Cult; Followers for the Unenlightened) are now OMITTED from
the autofill catalog rather than offered-then-flagged — a name the sheet cannot
hold is not in the dropdown.

The tenth splat, the fifth non-Exalt. **CH6 "The Mountain Folk"**, pp.214-293 —
one pasted chapter that packs chargen, new Traits, a five-Pattern Charm economy, a
technology/artifact section and a monster roster (the human's "three chapters'
worth of data" was accurate). The Jadeborn, Autochthon's underground children:
castes of reincarnating stone, ruled by an Enlightened artisan aristocracy beneath
the yoke of the Great Geas.

## The two deep mechanics (the engine work)

1. **The Enlightenment origin axis** — Enlightened / Unenlightened, the `origin`
   axis, and it rewrites nearly every chargen number:

   | | Enlightened | Unenlightened |
   |---|---|---|
   | Attribute pools | 16/13/10 | 8/4/3 |
   | Attribute ceiling | 7 (floor 3) | 5 (Intelligence 2) |
   | Ability dots | 10 favored + 25 free | 14 favored + 8 free |
   | Ability ceiling | 6 | 5 |
   | Background dots | 10 (Artisan 13) | 6 |
   | Charms | 6 | 3 |
   | Essence start / cap | 2 / 5 | 1 / 3 |
   | Willpower | start-cap 8 (2×≥4) | **hard cap 6** |
   | Cross-Pattern access | ≤3 of 6 | own Pattern + Foundation only |

   New `ChargenBudgets` fields: `ability_favored_dots` (the two-pool Ability
   budget), `background_dots_by_caste` (13/10/6), `attribute_min` (floor 3),
   `attribute_cap` / `attribute_caps` (7 / Int 2), `ability_cap` (6),
   `willpower_hard_cap` (6), `essence_cap` (per-origin 3), `banned_backgrounds`
   (Cult prohibited; Unenlightened additionally barred from Followers).

2. **The Pattern Charm gate** — 94 Charms in five Patterns (Foundation 8, Worker
   22, Warrior 24, Artisan 28, Enlightened 12), gated on **Minimum Essence only**
   ("lacks any minimum Trait requirements apart from Essence", p.244). New
   `CharmType.ENCHANTMENT` (36 of the 78 blocks; the book's signature type — a
   simple Charm that outlasts the instant without committed Essence) and
   `SIMPLE_ENCHANTMENT` for the one dual-typed Charm. Unenlightened may learn only
   their own Caste Pattern + Foundation; Enlightened at most 3 chargen Charms from
   another caste's Pattern. Cross-Pattern Charms price at 7 BP / 12 XP (vs 5/10).

## What was authored

- **94 Charms** from pp.244-275, extracted mechanically from the pasted text and
  linter-verified (0 errors, 0 warnings). Five variable templates expand: Pillar
  of (Virtue) ×4, (Virtue)-Bolstering Meditation ×4, (Color) Jade Transformation
  ×5, Fivefold Embodiment of (Color) Jade ×5, Mien of (Virtue) ×4. The extraction
  script lives at `tools/_extract_mountain_folk.py` (re-runnable).
- **Repeatables**: Ox-Body Technique caps on **highest Virtue**
  (`repeatable_cap_highest_virtue`); Essence Satiation Method and Stone-Still
  Lungs cap on Essence (third purchase needs Essence 3) **and** a flat `max 3`
  (`repeatable_cap_max`) — an Essence-5 Jadeborn still buys at most three.
- **Modified Backgrounds** (pp.234-235): Artifact 2:1 dots + exempt from the
  above-3 cap; Resources effective +2 (max 3 dots); Cult **prohibited**; the
  Unenlightened caps (Backing ≤2, Influence ≤1, Mentor ≤3, no Followers).
- **Innate Powers** (pp.236-237): Superior Craftsmanship — Craft Abilities and
  specialties at half XP (`costs_xp.craft` coeff 1, `craft_specialty` 2), Craft
  abilities hold up to five specialties; the rest are display-only.
- **Costs** (p.233): BP Essence 10, Charm 5/7-cross; XP Essence ×10, New Charm
  10/12-cross, Craft current-rating.
- **Great Geas**: Divergence as the splat's Limit track (`limit_label:
  "Divergence"`, `has_virtue_flaw: False`), plus a **reference panel** of the nine
  trigger clauses on the GM tracker (human's ruling — the Geas is ST-adjudicated,
  never engine-enforced).
- **Adversaries** (pp.284-292): Hruggha, Cephalid, Vodak. Underpeople and
  Darkbroods are "use the Wyld templates" advice, not stat blocks; Buried Gods are
  narrative.
- **Single Essence pool** = Essence × 10, no anima banner, no personal/peripheral
  split (merged to Peripheral like the ghosts').

## Rulings (human, 2026-08-07)

- The chargen "no more than three of these dots in any Ability" cap binds the **25
  free dots only**, not the 10 favored dots (p.230 is ambiguous; the Unenlightened
  symmetry confirms favored abilities can exceed 3 without BP).
- The Enlightened "no Attribute below 3" is a **spend-to floor** — combined with
  the base-1 start, at least two pool dots must reach every Attribute.
- The Artisan College's "•• divided among Craft Abilities" is a **group-sum floor**
  (`AbilityGroupMinimum`), a new shape alongside the per-ability OR floors.
- The Great Geas clause list is a **reference panel**, not engine enforcement.
- **Combos available** (the Echo Jewel's "cannot be part of a Combo" implies
  Jadeborn Charm-users can combo).
- The Fivefold Embodiment colours are **five separate Charms** (per-variant
  external prerequisites the engine cannot express), so the "not more versions than
  permanent Essence" cap is display-noted, not enforced.

## Code-review fixes (2026-08-07, Opus)

A code review found three defects and five minor items, all fixed same-day (the
first three test-first, each test failing before the change):

1. **Two-pool Ability billing overcharged legal sheets** — `bonus_point_breakdown`
   routed every dot ≤3 through the free pool alone, so a legal 10-favored + 25-free
   Enlightened sheet was billed 10 BP. Now a single read site
   (`validate.two_pool_ability_accounting`) computes the player-favourable
   allocation (favored pool funds favored dots at any rating up to the chargen
   ceiling of 5; the 6th dot is BP), and `bonus_point_breakdown`, the unspent
   warning and the editor readout all agree.
2. **Supernatural martial arts were reachable** — p.244 "they cannot learn
   supernatural martial arts" was never modelled; 17 cross-splat Charms leaked in.
   `foreign_charms_barred: true` on the exalt row (like ghosts/DK/God-Blooded)
   closes it; the 94 native Charms are unaffected.
3. **The Unenlightened Pattern bar was chargen-only** — p.244 states it as access;
   it now lives in `charm_matches_splat` / `meets_charm_requirements` (beside the
   ghost Spirit-Walking bar), so an Unenlightened Worker cannot buy an
   Artisan-Pattern Charm with XP. The Enlightened ≤3-of-six cap stays chargen-only.
4. **Flat repeat cap** — Satiation/Stone-Still are exactly "three times" (new
   `repeatable_cap_max: 3`), not "as many as your Essence".
5. **Attribute floor follows a Flaw-lowered ceiling** down (no unsatisfiable "3-0"
   range for a Disfigured Enlightened Jadeborn).
6. **Editor `_attr_cap` reads the origin's per-Attribute caps** — an Unenlightened
   Intelligence dot track caps at 2 instead of running to 5 and being flagged after.
7. **Per-focus Craft specialty cap** — see Flagged below.
8. **Stale comment** on `repeatable_cap_highest_virtue` corrected.

## Flagged / not modelled

- The **artifact catalogue** (pp.276-280: ten rated artifacts + alchemical goods)
  is NOT authored — it feeds the long-wished artifact-catalogue dropdown, a
  separate chunk. The ten artifacts are free text like Backgrounds for now.
- **Craft specialties are capped across all Crafts, not per-focus** (p.232: "up to
  five Specialties in any Craft"). Specialties carry no focus, so the 5-cap
  (`advancement.specialty_cap`) counts every Craft specialty in one bucket, and the
  printed "cannot purchase the same specialty more than three times" is not
  separately enforced for the fifth row. Not cleanly modelable without a focus on
  the specialty — flagged, not invented.
- The **Unenlightened Backing** clause (p.234: rank ≤2 for the military, ≤3 for
  private organizations) is modelled at the military ≤2 only; the private-org 3 is
  the same Background and not separately represented.
- The Eclipse/Moonshadow bar (cannot learn Artisan/Enlightened Patterns or Essence
  4+ MF Charms, double commitment for enchantments) is a foreign-Charm edge, not
  modelled.
- The Artifact Background's "beyond 5 costs 1 BP per dot" is under-modelled (the
  pool-side shape covers dots 1-5 exactly; beyond-5 is a rare, display-noted edge).
- The Path counts the book prints for "Entire Pattern" (21/23/30) do not match the
  authored counts (22/24/28+); the prereq resolves to whatever is authored.
