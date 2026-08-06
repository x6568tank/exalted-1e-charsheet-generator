# Dragon-Kings — status

**DONE 2026-08-05.** The ninth splat, the fourth non-Exalt, the first with a rated
subsystem that is not Charms. Source: the Player's Guide CH4 (pp.154-195), delivered
as pasted markdown (`images/Mortals/Dragon Kings/CH 4 - The Dragon Kings.md`).

## What makes the Dragon-Kings different

* **The ten Paths of Prehuman Mastery** — a rated-track subsystem, not Charms: each
  Path is rated 1-6, learned in fixed order, with its own chargen pool (6 modern /
  10 ancient), its own BP/XP tables, and an Essence gate (max 1/3/5/6). The 60
  dot-level powers are data attached to each Path; the loader also projects them into
  the charm catalogue as **virtual Charm rows** so Combos and the sheet can name them.
* **Four Breeds** instead of castes, each with attribute modifiers (free dots ON TOP
  of the stored value — the effective total may pass 5, per ruling 2), innate soak,
  a +0 health level (Anklok/Mosok), breed abilities, and display-only innate weapons.
* **A custom Essence pool**: `(Essence×4) + (Willpower×2) + Conviction + Valor`, ONE
  pool (fully harmonized), no anima banner — the first use of the
  `personal_named_virtues` pool field (two specific named Virtues).
* **Custom soak** (p.165 physiology): Stamina adds nothing to lethal; bashing =
  Stamina + innate armour, lethal = innate armour — via the data-driven
  `stamina_adds_to_lethal_soak` flag, which retired the hardcoded `exalt_type !=
  "Mortal"` string compare.
* **Two origins**: modern (7/5/4, 25 abilities, 6 Paths, 7 backgrounds, Essence 2,
  15 BP) vs ancient (8/6/5, 35, 10, 12, Essence 3, 25 BP, must know Linguistics-Old
  Realm / Lore•• / Occult••).
* **Terrestrial Circle Sorcery** only, gated like every initiation Charm; Combos work
  (p.177) via the virtual-Charm bridge.
* **Essence-gated trait ceilings**: Intelligence and Paths cap at 1/3/5/6 by Essence;
  at Essence 6 Abilities (via `elder.trait_ceiling`) and Virtues (a DK-only table —
  the first splat with a Virtue above 5) raise to 6.

## Human rulings (2026-08-05)

1. **Breed Paths**: each breed auto-favours its two element-matching Paths (Pterok →
   Celestial Air + Clear Air, etc.); the player picks ONE more from any of the other
   eight. The breed→element mapping is NOT in the book — it is an interpretation
   (confirmed by the human) backed by the flavour text.
2. **Breed attribute modifiers** are free dots ON TOP of the stored value, and they
   may push the EFFECTIVE total past 5 at 0 BP (a Pterok's stored Dexterity 5 reads
   as an effective 7). p.175's "cannot have any Attributes higher than 5 without
   spending bonus or experience points" is a gate on the STORED value only — and
   the stored ceiling at creation is 5 because the trait cap is Essence
   (`max(5, Essence)`, an interpretation a friend's 1E reading confirmed 2026-08-06:
   "Essence being the normal Trait cap isn't just an Exalt rule"), and chargen
   Essence is 2/3/5. Past 5 is the post-lock XP path at Essence 6 (stored 6,
   effective 8 for the +2 breeds). The old `attribute-breed-bonus-cap` chargen
   predicate is deleted — nothing needs it once the stored-5 range check is the
   whole bound.
3. **DK Combos are in scope** (p.177 is printed, not a ruling — the virtual-Charm
   bridge is required by the book).
4. **Intelligence cap by Essence IS modelled** (an earlier "skip" was reversed).
5. **`highest_magic_circle_id` = `""`** (review finding 1): `chargen_barred_circle`
   is an equality test on one circle; nothing is barred, access comes from
   `granted_circles`. A test pins it with the reasoning in the docstring.
6. **Essence 6 raises Abilities AND Virtues to 6** — Abilities already delivered by
   `elder.trait_ceiling` (no new field); Virtues via a DK-only
   `virtue_max_by_essence` table (decided over extending the trait ceiling to Virtues,
   which would silently let every splat raise Virtues past 5).
7. **The DB/DK Artifact rule** (E:DB p.157 / PG p.176) — "twice the dots' worth":
   **total artifact dots ≤ Background × 2, no single artifact above the Background
   rating, and at most ONE artifact rated AT the Background rating** (the flagship;
   the "two or more smaller artifacts" must be below it). Human correction
   2026-08-05 after an initial loose reading: Artifact 5 + two 5-dot artifacts is two
   flagships and invalid; Artifact 5 + a 4-dot + a 1-dot is the intended shape. This
   was **data-only, never enforced** until this splat — the same dormant gap existed
   for Dragon-Blooded (and Alchemical's flat triple-dot, which keeps a combined cap
   only).

## What was authored

* **Data**: the exalt row, 4 breed rows, modern + ancient budget rows, BP/XP rows,
  3 backgrounds (Celestial Manse, Salary, Savant — the last ancient-only via the new
  `excluded_origins`), an `emerald` theme, the Terrestrial Circle Sorcery charm.
* **`data/paths.json`**: the 10 Paths × 6 powers, transcribed from pp.177-191
  (names, costs, durations, types, full prose). The bulk of the authoring.
* **Models**: `Path`/`PathPower`, `BreedTraits`, `Charm.virtual`,
  `EssencePoolSpec.personal_named_virtues`, `ExaltDefinition.stamina_adds_to_lethal_soak`,
  the `ChargenBudgets` path/cap/ceiling fields, path cost fields,
  `BackgroundType.excluded_origins`, `Character.paths`/`favored_path`.
* **Engine**: `engine/paths.py` (the shared read sites), Paths BP/XP accounting and
  Essence-gate/favour/required-Virtue validations, breed soak/health derivation, the
  Combos bridge, the virtual-Charm read-site gating (picker hides, learn refuses,
  Combos/sheet resolve).
* **UI**: a **Paths page** under the Charms tab (each Path, a rating control, the
  powers each dot grants, the favoured-Path picker), and the **sheet now splits the
  charm holdings into Arcanoi/Gifts/Ox-Body/Charms sections and renders Paths and
  Combos panels** — the latter two were entirely absent from the sheet before.

## The four-check audit (docs/delegated-authoring.md)

Run 2026-08-05. Two defects found and fixed, both the house bug (a rule wired into
chargen only, not the buy path):

1. **Dead-field sweep** — `intelligence_max_by_essence` was read only in
   `validate_chargen`, so XP could raise a modern Dragon King's Intelligence past the
   Essence-2 cap of 3; and `virtue_max_by_essence` was read only in chargen while
   `raise_virtue`'s default ceiling of 5 made the Essence-6 Virtue-6 unlock (ruling
   #6) **unreachable**. Both are now gated in `advancement.raise_attribute` /
   `raise_virtue`, with buy-path tests. `excluded_origins` is read in
   `RuleSet.backgrounds_for`, and the Advantages tab caller was missing `origin` — a
   modern-only Savant bar was hiding Savant from ancients too; fixed.
2. **Prohibition sweep** — p.177's "Favored Abilities … may not be the same as Breed
   Abilities" is already enforced by the existing `favored-overlaps-caste` check.
3. **Link-check** — no new id-bearing fields need load-time checks; the virtual-Charm
   prerequisite chain passes `_check_prereqs`, and `favored_path`/`path_id` are
   validated at chargen.
4. **Stale identifiers** — clean.

**Click-through findings (2026-08-05):** the DK (and DB/Alchemical) `rating_per_dot`
Artifact multiplier was data-only — never enforced — so `check_artifacts` now enforces
"combined artifact rating ≤ Artifact background dots × rating_per_dot"
(`artifact-over-background-dots`), fixing the same dormant gap for Dragon-Blooded and
Alchemical. The ancient Lore/Occult floors are enforced (all three fire when unmet);
they simply don't display a permanent "required" indicator once satisfied.

## Open / soft items

* **Innate-weapon stats: DONE 2026-08-05.** `BreedTraits.innate_weapons` is now a
  list of `InnateWeapon` rows carrying the printed Spd/Acc/Dmg/Def (PG pp.167-174,
  transcribed after the pages landed in `images/Non-Exalts/Dragon Kings/`); the
  sheet renders an **Innate Weapons** section beside the breed's attribute bonuses,
  display-only per decision 0008. The breed's innate soak and health levels were
  already in `data/`.
* Ancient "Linguistics (Old Realm)" — the language has no trait in the model, so the
  floor is a soft note on Linguistics; no language trait.
* The p.192 half-Path-dots→spells conversion ("buy sorcery with bonus points… up to
  half of your free dots of Paths to instead learn Sorcery spells") is **printed but
  ambiguous — needs a ruling**. Proposed default: on a BP-bought initiation, up to
  half of the unspent `path_dots` pool may instead buy Terrestrial spells at the
  printed price. Not implemented.
* `essence_start_cap` 3 (modern) / 5 (ancient) — an interpretation: moderns "can
  never regain Essence 4+" without ancient aid (chargen-appropriate). The BP budget
  alone would otherwise let an ancient start at 6; post-lock Essence 6 is XP-purchasable
  (the age gate that used to hold it is gone, 2026-08-06).
* Whether Celestial Manse/Salary should also open to Sidereals (E:S backgrounds) —
  DK-only for now.
* Source discrepancy for the status doc: the p.160 ancient sidebar cites Savant at
  E:S pp.109-110, the p.176 footnote at pp.108-109. Plan uses 108-109.
* The Prodigy "2-pt for Dragon Kings" (and God-Blooded) override is **DONE 2026-08-05**
  — `cost_options_by_exalt_type` on `mf.prodigy` prices `favored` 2 / `favored_aptitude`
  4. The **Weak Essence DK exception** is still open — see `docs/status/merits-flaws.md`.
  (The PG p.114 "mortals that exceed Essence 3 become gods" hook, named beside it, is
  also DONE 2026-08-05 as a UI note at the mortal's Essence-3 ceiling.)

## Verification

* **Test count**: **1,969 passing** (the earlier "1 known failure" M&F description
  note is stale — that test passes as of 2026-08-06). Includes
  `tests/test_dragonkings.py` (39 tests: every keyed-row number, the buy-path gates,
  the Combos bridge, the derivations, the artifact budget, the effective-over-5
  attribute-cap model, and render smokes through the NiceGUI harness). Charm linter
  clean for `dragon-kings`.
* **Browser click-through**: DONE 2026-08-05 for most surfaces (Paths page, breeds,
  backgrounds, Combos, sorcery, sheet sections). The other click findings
  (Path-description wrap, breed-bonus display, ancient floors, artifact
  combined/per-item caps) are fixed and confirmed. **The 2026-08-06 attribute-cap
  correction was re-verified in a browser**: a locked Pterok bought stored Dexterity 5
  (effective 7) at 0 BP, and a Dragon-Blooded at Essence 7 was held there until the ST
  Options "Terrestrial may pass Essence 7" toggle lifted the ceiling to 9. **The Artifact
  `artifact-two-flagships` finding is RESOLVED 2026-08-05.** The engine was never
  wrong: the first click-through missed it because the server was stale mid-restart,
  and the re-verify surfaced a UI bug that masked it. The rating input's `on_change`
  called `refresh_all()`, which rebuilt the whole Advantages panel — destroying the
  `ui.number` mid-interaction, and NiceGUI silently drops events that target a
  deleted element (`Client.handle_event`), so a rapid 5→4→5 round-trip lost the
  4→5 click and the stored rating desynced from the number on screen. Fixed by making
  a rating edit refresh only the panel header (its own refreshable) and the readout,
  never the body, so the widget survives every click; the Advantages readout also
  accepts `artifact` issue codes so the two-flagships warning updates live on the tab.
  Both sides re-verified in a browser — the warning shows, clears on 5→4, and returns
  on 4→5.
