# Status detail — Solar alternate origin: Cult of the Illuminated

Referenced from `CLAUDE.md` → Status. DONE 2026-07-24.

Read from `images/Solars/Illuminated Origin.md` (human-pasted text, page-marked
p.89-106). The FIRST alternate origin that adds new *structure* rather than just a
budget row. Open items, source defects and the rules calls are recorded in
`images/Solars/_ILLUMINATED_PENDING.md` — read that before touching this.
- **Budget row `Solar:illuminated`**: abilities 25→**30**, backgrounds 7→**9**, charms
  10→**8** (C/F minimum 5→**4**), Essence 2→**3**. Attributes (8/6/4), Virtues and the
  15 BP are unchanged. New `ChargenBudgets.essence_start_cap` (5) is a ceiling applied
  AFTER bonus points — "under no circumstances ... Essence of six (6) or higher"
  (p.90); 0 = no ceiling, i.e. every other splat.
- **TrainingCamp is a THIRD axis beyond splat and caste** (`rules.TrainingCamp`,
  `data/camps.json`, `RuleSet.camps`/`camps_for`, `Character.camp`). Any caste may
  attend either camp and both camps share one origin row, so it could live neither on
  `CasteDefinition` nor on `ChargenBudgets`. A camp carries Ability floors — unioned
  into `validate_chargen` exactly as the Sidereal per-house floors are, so they surface
  as the existing `required-min-ability` code — and a free-Charm package. Kether Rock's
  "either Archery • or Brawl •" needed ZERO new machinery: `AbilityMinimum` already
  means "≥ rating in at least one of these".
- **Granted Charms** (`Character.granted_charms`, `GrantedCharmChoice`). Two grant
  shapes, both modelled: `fixed_sets` (Kether Rock's "one of the following pairs",
  all-or-nothing) and `from_categories` + `pick` (the Tabernacle's "two Charms from ONE
  of four martial arts"). `validate.granted_charm_issues` checks the package resolves
  (`granted-charm-missing`/`-extra`/`-choice-unresolved`/`-choice-mixed`/`-duplicate`/
  `-unknown`/`-not-supported`) and that the character meets each granted Charm's own
  minima (`granted-charm-minimum`, p.90 "must meet the minimum requirements") —
  prerequisites deliberately NOT checked, since the package hands out Charms whose tree
  the character has not climbed. Granted Charms cost **no BP and no pick**. This is a
  **FOURTH list outside `character.charms`** after `ox_body` and `beastman_gifts` — the
  "one canonical Charm-pick enumeration" refactor (see `CLAUDE.md` → TODO) is overdue.
- **Calling is a DISCOUNT AXIS, not a second Favored list** (`rules.Calling`,
  `data/callings.json`, `Character.calling`). It discounts 5 named Abilities and ~10
  named Charms at BOTH chargen and in play, and the page is explicit that it STACKS
  with Caste/Favoured — so a Calling Ability does NOT count toward the C/F dot minimum.
  Ability BP is therefore now **four tiers** (neither / C-F / Calling / both), the
  both-tier costing 1 BP per 2 dots and **rounding UP** (rules-authority call
  2026-07-24; the page is silent). Charm BP 4/3. XP: −1 ability, −2 charm, applied
  after the rate and before the foreign-Charm multiplier. New fields
  `BonusPointCosts.calling_ability`/`calling_ability_favored_caste_dots_per_point`/
  `calling_charm`/`calling_charm_favored_caste` and
  `ExperienceCosts.calling_ability_discount`/`calling_charm_discount`, all defaulting
  to the UNdiscounted rates so every other splat is byte-identical.
- **`BackgroundRule.free_rating`** — dots granted OUTSIDE the pool. Illumination • is
  free "in addition" to the nine dots (p.90); contrast the Alchemical Class •••, which
  is mandatory but paid for (`min_rating` with no `free_rating`). Backing is barred via
  `allowed_backgrounds` (the ronin mechanism, the p.93 permitted list of 12).
- **Charms — 20 authored** (p.100-106): Brawl 5, Endurance 1, Linguistics 1, Presence 4,
  Survival 1, Socialize 1, plus **Falling Blossom Style** (7) in its own file
  `solar_martial_arts_falling_blossom.json`, per the Sidereal one-file-per-style
  convention. Falling Blossom is `open_to_all` straight off p.102 ("a Terrestrial
  Style, and thus, Dragon-Blooded may learn it at no penalty"). The chapter has 21
  headings but one is the style preamble, not a Charm.
- **`Charm.extra_min_abilities` — a Charm may gate on MORE THAN ONE Ability.** Ascendant
  Battle Visage (p.102) prints "Minimum Brawl: 5 / Minimum Endurance: 5" and is the
  first such Charm; the field reuses `AbilityMinimum`, so each entry is an independent
  AND whose inner list is an OR. `min_ability` stays the PRIMARY gate because pricing,
  the C/F and Calling discounts and the picker layout all key off it — the extras are
  requirement checks ONLY and must never leak into pricing (pinned by a test that a
  Zenith Solar still pays full price for this Brawl Charm). **All trait-minimum checks
  now route through the single `validate.charm_ability_shortfalls`** (and
  `charm_ability_requirements` for display), because three call sites each compared
  `min_ability` by hand and a fourth would have diverged. Add a gating axis there, once.
- **NOT modelled, deliberately:** Indoctrination (p.90 — a Conviction roll + Limit,
  Storyteller-called play-state, same bucket as Renown/Clarity); the mandatory Virtue
  Flaw (Virtue Flaws are not modelled anywhere); the Sorcery Background's free spells
  (a new "Background grants spells" mechanic, and its list draws on *Savant and
  Sorcerer* which `spells.json` does not hold); Tiger Warriors troop counts
  (descriptive). See `_ILLUMINATED_PENDING.md`.
- **UI (Phase 4) DONE**: `view.build_camp_view`/`CampView`/`CampChoiceView` (pure
  presenters), the editor's Training Camp + Calling panel in the left info column
  (camp select → re-seeds Callings and fixed grants; one select per grant choice),
  ✧ Calling marks concatenated onto the Abilities panel's ● Caste / ✦ Favoured, the
  sheet's "(granted)" Charm rows, and the picker's "✧ Calling Charm — discounted" and
  "Granted by your training camp" tags. Render tests in `tests/test_illuminated_ui.py`.
  **A `from_categories` grant is TWO controls, not one** (bug found by the human in a
  browser, 2026-07-25: "two charms picker … only lets you select one"). The style select
  answers *which style*; a second multi-select answers *which `pick` Charms of it*.
  Before this the two Charms were auto-seeded by lowest requirement and there was no way
  anywhere to change them — the "the player swaps individual Charms in the picker"
  comment described an affordance that was never built. `CampChoiceView` gained
  `charm_options: list[CampCharmOption]` + `chosen_charm_ids` (empty until a style is
  chosen, and always empty for a `fixed_sets` choice, where the printed pair IS the
  grant); `editor.set_camp_choice_charms` applies it. Over-picking is REFUSED with a
  notify rather than truncated; under-picking is allowed through so the control can be
  emptied and refilled, with the engine's `granted-charm-missing` covering the gap.
  **`chosen_key` now means "any of this style's Charms is held", not "≥ pick of them"**
  — the old rule made a one-Charm selection read as *unchosen*, which hid the sub-select
  and stranded the player. Charms whose own minimums are unmet stay selectable but are
  flagged (p.90 requires them; the engine already reports `granted-charm-minimum`). This
  was only reachable once the three castebook styles landed — the grant was dead data
  before that, which is why the gap survived the original Phase 4 pass.
  **Clicked through in a browser by the human on 2026-07-25** and confirmed correct.
  That pass is what found the missing sub-select in the first place: every render test
  here had been green the whole time, because serve-and-grep proves a control renders
  and says nothing about whether the control the page NEEDS is present. Same lesson as
  the Lunar DBT dialog.
