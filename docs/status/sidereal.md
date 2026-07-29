# Status detail — Sidereal

Referenced from `CLAUDE.md` → Status. DONE (started 2026-07-22, shipped 2026-07-24).

Read from `images/Sidereals/96 - 101 Character Creation`. Budgets/structure in
[[sidereal-chargen-findings]]. **Phase 1 (foundation) DONE** — reuses the existing
ability-caste + required-minimums + essence-spec machinery with ZERO new engine code:
- **Data authored:** `castes.json` 5 Maiden castes (Journeys/Serenity/Battles/Secrets/
  Endings — ability-caste splat, the 5 **Auspicious Abilities** ARE `caste_abilities`,
  each with its anima power); `exalts.json` Sidereal row (Essence 2/6 virtue-all —
  Personal E×2+WP, Peripheral E×6+WP+ΣVirtues; sorcery, `highest_magic_circle_id`
  "Celestial", tier Celestial, `ox_body_charm_id` "" until Charms land);
  `chargen_budgets.json` Sidereal row (8/6/4 attrs, 35 abilities ≥15 C/F, 4 favored,
  12 charms ≥5, 15 backgrounds, 5 virtues, 18 BP + the 9 universal Celestial Hierarchy
  ability minimums); `costs_bonus.json` + `costs_xp.json` Sidereal rows (Essence XP ×9
  per the user rule since p265 omits base rows; new Charm 11/9 per p265). Theme
  `theme._SIDEREAL` = purple, `fam="purple"`. Editor picks the splat up with no code
  change (it iterates `ruleset.exalts`). Tests: `tests/test_sidereal.py`.
- **Per-house ability minimums DONE 2026-07-22** — `CasteDefinition.required_min_abilities`
  (new field; `AbilityMinimum` moved above `CasteDefinition` in `models/rules.py`) is
  unioned with the exalt-type-keyed budget floor in `validate_chargen`. Each Sidereal
  caste carries its house floor (p.98): e.g. Battles = Archery/Melee ●●●, Athletics ●●,
  Dodge ●●, Presence ●●, Resistance ●●. Overlaps with the universal minimums resolve to
  the higher rating automatically (each `AbilityMinimum` is checked independently).
- **Astrological Colleges DONE 2026-07-23** (engine, data AND UI). A budgeted
  per-instance rated trait with its **OWN pool** — 7 dots, ≥4 in the character's own
  Maiden's house, cap 3 pre-bonus, BP 8/6, XP 5 new / ×3 raise — so it is NOT a pure
  Craft clone (Craft spends from the Ability pool; Colleges do not). `rules.College`
  (`data/colleges.json`, 25 across 5 houses) + `character.CollegeRating`;
  `ChargenBudgets.college_dots/college_min_own_house/college_cap_pre_bp`;
  `BonusPointCosts.college/college_own_house`; `ExperienceCosts.new_college/college`.
  A College's `house` IS a caste id, which is how the own-Maiden rule matches
  `Character.caste` with no lookup table. Validation: `unknown-college`,
  `college-range`, `college-own-house-min`. Advancement: `learn_college`/
  `raise_college` (+ undo + `_expected_cost` audit). UI: the editor's add/remove rows,
  a ★-marked sheet panel (`view.college_rows` → `SheetView.colleges`, rendered in
  `ui/app.py` only when non-empty, so no other splat grows an empty panel), the XP
  tab's buy/raise dropdowns, and a `colleges` branch in the XP-log label — that last
  one is the same miss Beastman Gifts had, so **grep the log labels whenever a new
  purchasable trait lands**. Every UI gate is `b.college_dots > 0`, data not a splat
  name, so a later College-like splat opts in for free. Astrology EFFECTS stay out of
  scope (like combat derivation); their reference tables (Pattern Bite / Effect
  Scope-Duration-Power, p.214-219) belong in the GM reference screen, not here.
  Data source: `images/Sidereals/Storytelling/220-235`. Tests: the College block in
  `tests/test_sidereal.py` + `tests/test_sidereal_ui.py` (render).
- **Ronin variant DONE 2026-07-23** (`Sidereal:ronin`, p.100 — read from
  `images/Sidereals/96 - 101 Character Creation/100-101.png`). 25 Ability dots ≥10
  Auspicious/Favored, 7 Backgrounds, 8 Charms, 0 Colleges, and no Ability minimums;
  attributes/virtues/essence/BP are unchanged from the standard row. Two rulings and
  two new fields came out of it:
  - **The ≥5 Caste/Favoured Charm minimum CARRIES OVER to the ronin's 8 Charms**
    (rules-authority call, 2026-07-23). The page overrides only the TOTAL and never
    restates the minimum; do not "helpfully" scale it to 4.
  - **`ChargenBudgets.allowed_backgrounds`** — the ronin is "limited to the
    Backgrounds of Acquaintances, Allies, Artifact, Backing, Connections, Familiar,
    Manse and Resources". This is the **only hard Background validation in the
    project** (code `background-not-allowed`); Backgrounds are otherwise deliberately
    soft free text, so the list is empty (= unrestricted) for every other origin and
    blank editor rows are skipped. The same paragraph's "no Backing from or
    Connections with Sidereal factions or the Celestial Bureaus" is narrative and is
    NOT modelled.
  - **`ChargenBudgets.ignore_caste_min_abilities`** — "They have no minimum required
    Ability scores." A ronin still HAS a Caste, so the per-house floor on
    `CasteDefinition.required_min_abilities` would otherwise still apply; this
    suppresses the caste half (the budget's own list is just empty).
  - Editor `_SPLAT_ORIGINS` gained `"Sidereal": hierarchy/ronin`. Unlike Lunar's
    casteless, this is independent of the Caste field — no consistency check needed.
- **Paradox DONE 2026-07-23** — `ExaltDefinition.limit_label` ("Paradox" on the
  Sidereal row, "Limit" everywhere else), read via `derive.limit_label` by both the
  Play tab and the GM card. A pure rename of the same 0-10 track with the same break
  threshold, per p.253; it is a label, not a second code path, and is ignored when
  `clarity` is True (the Alchemical has no Limit to rename).
- **Charms catalogue — DONE 2026-07-24 (v0.7).** **193 Charms** in
  `data/charms/sidereal_*.json`, authored from `images/Sidereal/chapter5 - Charms.md`
  (human-OCR'd text; systematically de-ligatured — see [[sidereal-charm-ocr-pipeline]]).
  24 ability trees + **Violet Bier of Sorrows** (`martial_arts:violet-bier-of-sorrows`,
  9, the Endings auspicious Martial Arts tree) + **3 Celestial-open Sidereal Martial
  Arts styles** (`open_to_tiers:[Celestial]`, per the preamble "treat Sidereal Martial
  Arts as Solar Charms"): **Charcoal March of Spiders** (12), **Prismatic Arrangement
  of Creation** (16), **Citrine Poxes of Contagion** (13). Terrestrial/Celestial Circle
  Sorcery carry `grants_circle`; Ox-Body is repeatable on Endurance. `ox_body_charm_id`
  is now set. The 12-Charm `validate_chargen` pool the foundation tests could not
  assert is now covered (`tests/test_sidereal.py`, catalogue + cascade + chargen block).
  **~56 Min Ability/Essence digits and a few activation-mote costs were dropped by the
  OCR and supplied by the human** (`images/Sidereal/_MISSING_MINIMUMS.md`); the SMA
  styles' `min_ability`/`min_essence` and Sequential Charm Disruption's cost came from
  the human, not guessed.
- **Sidereal Martial Arts cost/cap wiring — DONE 2026-07-24.** Rules-authority call
  (confirmed): the distinct rate applies to **ALL Martial Arts** for a Sidereal (Violet
  Bier AND the 3 supernatural styles) — there is no Solar-only Martial Arts a Sidereal
  cannot learn.
  1. **BP 8/6, XP 12/10** (p.101 / p.265). New `BonusPointCosts.martial_arts_charm`
     (+`_favored_caste`) and `ExperienceCosts.new_martial_arts_charm` (+`_favored_caste`),
     both `Optional`, defaulting `None` → **fall back to the ordinary Charm rate**, so
     every other splat's MA Charms are byte-identical (regression-guarded). Wired into
     `costs.charm_cost` and `validate.bonus_point_breakdown` for `category` starting
     `martial_arts` (the Immaculate branch is still checked first, so DB Immaculate MA
     keeps its own rate). `costs.martial_arts_charm_cost` (Alchemical PLM path) gained
     the same `None`→`new_charm` fallback. The MA discount fires when Martial Arts is
     the caste's Auspicious ability (Endings), giving the /6 & /10 rates.
  2. **≤3 Charms from a Sidereal Martial Arts *form* at chargen; ronin 0** (p.101,
     `chapter3 - Character Creation.md` line 540). New
     `ChargenBudgets.martial_arts_form_charm_cap` (3 for Sidereal, 0 for `Sidereal:ronin`,
     `None`=no cap elsewhere); `validate_chargen` counts `martial_arts` Charms that are
     `open_to_tiers` (the data-driven marker of a supernatural SMA style — Violet Bier is
     NOT `open_to_tiers`, so it is uncapped and stays open to ronin) and raises
     `charm-too-many-martial-arts-forms`. Tested in `tests/test_sidereal.py`.
- **Sidereal is COMPLETE (shipped 2026-07-24).** The human clicked through the picker
  with real Sidereal data (Charms tab, the 4 Martial Arts style trees, the sorcery
  Spells page, XP-tab MA pricing) — all fine — and pushed.
