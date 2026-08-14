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

## The Cult's own Backgrounds, and the Cult Dragon-Blooded (2026-08-12)

Source: `images/Solar/Illuminated Backgrounds.md` (Cult pp.96-100, human-pasted).
Both halves came out of the same pages; the browser found the first.

- **`background.artifact-illuminated` (p.96) — the Cult prints its OWN Artifact and
  the build was handing Illuminated Solars the corebook's.** Nothing was
  mis-resolving; the entry had simply never been authored. It is the **Abyssal p.131
  BUDGET shape**, not a cost curve — combined rating ≤ 2/3/4/6/8 at •-••••• — so it
  reused `BackgroundRule.budget_tiers` and needed no new engine concept. A 4-dot
  artifact now costs an Illuminated Solar three Background dots, not four.
  - **The disambiguation trap:** both entries are called "Artifact", and a
    `catalogue_backgrounds` NAME matches both copies; the "a splat's own copy
    displaces the untagged one" rule would then have handed a **standard** Solar the
    Cult's version. Both `Solar` and `Solar:illuminated` therefore key Artifact BY ID.
    The same applies to any future splat-local rework of a shared name.
  - Two nameless-tier bugs fell out: `BackgroundBudgetTier.name` is optional (the
    Abyssal's five rows are labelled, the Cult's are bare dot rows) and three sites
    interpolated it unconditionally, producing "Artifact 3 () allows…". Issue text now
    goes through `engine.artifacts.tier_label`.
  - `tests/test_backgrounds_splat.py`'s offered-vs-allowed guard compared the two
    lists as raw strings, so it failed on a CORRECT config the moment a row carrying
    both lists used an id. It resolves ids to names now. Mountain Folk had hidden the
    gap: it uses ids throughout but carries no `allowed_backgrounds`.

- **`Dragon-Blooded:illuminated` (p.96)** — "generated as standard outcastes … with
  the following exceptions": 30 Ability dots, **7** Background dots, the Cult's
  Backgrounds, and a training camp. Budget rows REPLACE wholesale, so the row restates
  every outcaste value it does not change and a test pins them against
  `Dragon-Blooded:outcaste`.
  - **No Calling** (human, rules authority): the page names its exceptions and never
    mentions one. `requires_camp` true, `requires_calling` false — the first character
    in the build with a camp but no Calling, which is why the editor's panel heading is
    now conditional.
  - Two new camps, `sequestered-tabernacle-db` / `kether-rock-db`, borrowing the Solar
    camps' Ability floors ("the normal requirements for their training camp").
    **Kether Rock grants a Dragon-Blood nothing** — "select seven (7) standard
    Dragon-Blooded Charms" is just the outcaste allowance restated.
  - **A THIRD grant shape: `GrantedCharmChoice.pool_categories` + `pool_charms`.**
    The Tabernacle's "three (3) Charms from Ebon Shadow, Falling Blossom, Praying
    Mantis, Snake, Tiger Style or Ox-Body Technique" is ONE FLAT POOL picked in any
    combination (human, rules authority) — unlike the Solar camps' "two Charms from
    ONE of…" — and the pool MIXES style categories with a named Ability Charm, which
    `from_categories` cannot express. It renders as ONE control, not two.
  - Backgrounds: the Cult's Artifact displaces the Realm's doubled one ("For other
    Cult Exalted, orichalcum is reserved exclusively for Solars. They may take jade
    with this Background"), Illumination is capped at ••• (p.97) via `max_rating`, and
    Sorcery is offered on the strength of "any Illuminated Exalt training in the camps
    can learn sorcery" — but **capped at ••• ** (human, rules authority, 2026-08-12),
    because its •••• and ••••• rungs grant "spells from either the Terrestrial or the
    Celestial Circles" and a Terrestrial cannot cast the latter. ••• is the highest rung
    that grants Terrestrial spells only. The cap lives on the ORIGIN row, so Solars keep
    the whole ladder.

- **Preflight caught a crash the suite could not.** `validate.camp_for` resolves a
  stored camp id against the WHOLE camp table, so a Dragon-Blooded carrying the Solar
  Cult's `kether-rock` reached `ui.select` as a value outside its options — which
  raises at BUILD time and takes the enclosing tab down with it. **Unreachable until a
  second splat owned camps**, and reachable the moment one did. `build_camp_view` now
  clamps a MISMATCHED camp/Calling to something offered (a character with none chosen
  still gets the empty select it always had); the engine keeps reporting
  `camp-wrong-origin` in the issue panel, which is where a mismatch belongs.

**Browser-verified by the human 2026-08-12** — all nine checklist items confirmed:
the panel heading, the one-control pool select accepting three Charms from two styles,
Kether Rock granting nothing, the Cult Artifact ladder and budget header, the ••• caps
on Sorcery and Illumination, and — the regression that started all this — a STANDARD
Solar still getting the corebook Artifact. Suite at 2,172.

### Deliberately NOT authored

- **Cult Abyssals (p.96)** — **DEFERRED INDEFINITELY** (human, 2026-08-12 as a deferral,
  confirmed indefinite 2026-08-14 alongside the Mist numina: a very specific sub-section
  of a splat). **Do not propose it or offer it as a follow-up.** The budget deltas are
  trivial (as Cult Solars, but 7 Background dots and none of the Indoctrination flaws);
  the blocker is "their Calling Charms and required Charms are replaced with the closest
  Abyssal equivalent", which is **56 unmapped Charms** — only 3 of the 59 Solar ids in the
  camps and Callings exist by name in the Abyssal catalogue. That mapping is a design job
  requiring 56 human rulings, not an inference, and it buys one alt-origin of one splat.
  ⚠ **It is not a gap.** A sweep that lists these Charms as missing is counting a
  deferral as an oversight.
- **Tiger Warriors for Cult Dragon-Blooded** — the pages say Dragon-Blooded sometimes
  *are* tiger warriors and appear as attendants at •••• and •••••, never that they may
  buy the Background. Left out; flag if the table wants it.
- **A Cult Dragon-Blood cannot reach the CORE Artifact.** p.96 says other Cult Exalted
  must "purchase the standard Artifact Background from the Exalted main rulebook" to
  hold moonsilver, starmetal or soulsteel. Offering both would put two rows named
  "Artifact" in one dropdown — the exact duplicate the displacement rule exists to
  prevent, and displacement cannot resolve it because both copies are tagged. Only the
  Cult's is offered.
- **Illumination for Lunars (••••) and Abyssals (•••••)** — printed on p.97, but there
  is no Lunar or Abyssal Cult origin to hang the cap on.

### Open question left with the human

**Iris-Bulb Discourse requires Essence 3; a Cult Dragon-Blood starts at Essence 2.**
So the Sequestered Tabernacle grants every Dragon-Blooded graduate a Charm they cannot
hold without spending bonus points on Essence, and the sheet flags it as
`granted-charm-minimum`. p.90 makes the SOLAR packages explicitly subject to their
Charms' own minimums; p.96 only says Dragon-Blooded "gain" these two. Left flagged
rather than exempted — the alternative is granted Charms bypassing minima for this camp
only, which is a ruling, not a code choice.
