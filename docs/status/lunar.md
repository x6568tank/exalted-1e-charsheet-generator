# Status detail — Lunar

Referenced from `CLAUDE.md` → Status. DONE (started 2026-07-22).

Read from `images/Lunar/Character Creation 88-93`, `Traits 96-115`, and
`Charms 118-193` (core "The Lunars" splatbook). Chargen foundation, Attribute-
keyed Charm machinery, every Charm in the Charms chapter (p.118-193, including
Deadly Beastman Transformation's Gifts), the p.122 Combo mixing rule, and a
picker/view bugfix that only surfaced once real Lunar data existed are all
authored and tested. The picker UI has been driven by a human in a browser —
the Gift-picker dialog caveats noted below are cleared.

- **No Caste Abilities at all (p.90)** — "Abilities are not divided along caste
  lines," so `CasteDefinition.caste_abilities` is empty for every Lunar caste.
  Anything that laid out the Ability roster by caste therefore rendered BLANK for
  a Lunar (the editor's Abilities panel and the sheet's Abilities block both did).
  `ui/view.ability_group_defs` is the one place that decides the grouping now: by
  caste when the splat has ability-castes, otherwise `view.DEFAULT_ABILITY_GROUPS`
  — **War / Life / Wisdom**, as printed on the canonical 1e Lunar sheet
  (`images/Lunar/character sheet.png`). That is the DEFAULT for any splat without
  ability-castes; caste grouping is the override. It is a sheet-layout convention
  with nothing mechanical keyed off it, so it lives in the presenter, not `data/`.
  The editor's caste-info box and Attribute panel show `caste_attributes` in the
  slot where other splats show Caste Abilities.
- **Lunar Charms are Attribute-keyed, not Ability-keyed (p.90-93, p.122)** — the
  single biggest structural difference from every other splat. `Charm.min_attribute`
  (an `AttributeName` value) is the new parallel to `min_ability`; a Charm sets
  one or the other. `CasteDefinition.caste_attributes` is the Lunar parallel to
  `caste_abilities` (empty for Ability-caste splats, and vice versa). A Charm's
  Caste-favored-ness is derived, not flagged: its `min_attribute`'s category
  (Physical/Social/Mental, `engine.validate.ATTRIBUTE_CATEGORIES`) must match the
  caste's favored category — Full Moon→Physical, Changing Moon→Social, No
  Moon→Mental (`validate._caste_favored_attribute_category`/
  `_charm_attribute_caste_favored`). The **Charm min_attribute *requirement*
  check** (gating `meets_charm_requirements`/`check_charm_prerequisites` the way
  `min_ability` does) IS wired (`validate.py` ~line 120) and exercised by the
  per-category cascade tests below.
- **Two picker/costs bugs found and fixed only once real Lunar Charm data
  existed to trip them** (neither was reachable with zero Attribute-keyed
  Charms in the game): `ui/view.build_charm_detail` resolved every Charm's
  requirement label from category-as-Ability, silently mislabeling every Lunar
  Charm ("Melee 2" instead of "Dexterity 2", since 'melee' is coincidentally
  also a valid AbilityName) — fixed to check `min_attribute` first, same as
  `validate._min_trait_rating` already did internally. `engine.costs.charm_cost`
  had the identical blind spot for the Caste/Favored XP discount — every Lunar
  Charm bought post-lock was silently charged the full (non-favored) rate. Both
  are exactly the kind of bug that's invisible until real cross-cutting data
  exists; if a future splat introduces another new gating axis, budget time to
  re-audit `_category_ability`/`min_ability` call sites the same way.
- **Charm catalogue (217 Charms, `data/charms/lunar_*.json`), by category/page
  range:** `body_enhancement`/Ox-Body (11, p.170-ish), `defensive` (21),
  `melee` (26), `perception` (27, p.174-181 — includes Sense-Borrowing Method,
  a cross-tree pull requiring BOTH Sense-Sharpening Change AND Pack-Forming
  Presence (Interaction and Knowledge, p.189) as separate AND groups; it was
  initially missed on a first pass through the p.174-175 diagram and had to be
  added back in), `ranged_combat` (17),
  `shapeshifting` (17, p.123-132 — the totem-form/beastman tree),
  `survival_and_healing` (22), `unarmed_combat` (37), `stealth` (6, p.182-183),
  `interaction_and_knowledge` (24, p.183-191 — storytelling, crowd/Virtue
  manipulation, intimidation, beast-command, and the wolf-sibling
  Brotherhood-of-Lake-and-River charms), `spirit` (4, p.191-192), `sorcery` (5,
  p.192-193 — Form-Fixing Method/Tattoo-Cutting Wisdom/Moonsilver-Shaping Rite
  chain into Terrestrial/Celestial Circle Sorcery; Celestial requires BOTH
  Terrestrial Circle Sorcery AND Moonsilver-Shaping Rite as separate AND
  groups, not an OR — a real gotcha since the sourcebook draws it as one
  converging diagram). `id` namespace segments for multi-word categories use
  hyphens (`lunar.survival-and-healing.*`, `lunar.interaction-and-knowledge.*`)
  while the JSON `category` field uses underscores — mismatched separators are
  intentional, follow the existing files' convention exactly when adding more.
  Every category's root Charms and full prerequisite-chain resolution are
  covered in `tests/test_lunar.py` (one cascade block per category).
- **Beastman Transformation Gifts (p.126-127) — modeled on Ox-Body, done.** 19
  Gifts (not 17 — Terrible Beast Claws and Savage Moonsilver Talons were
  missed on the first read of the page and had to be added back) live as
  `variants` on `lunar.shapeshifting.deadly-beastman-transformation`, the same
  repeatable-Charm shape Ox-Body uses but generalized two ways: `CharmVariant`
  gained `prerequisites` (AND-of-OR over OTHER variant keys of the SAME Charm —
  e.g. Glue-Foot Climbing needs Spider-Foot Climbing needs Bestial
  Reflexes-or-Lightning Speed) and `max_purchases` (2 for Bestial Reflexes and
  Enhanced Senses only — an earlier draft description wrongly claimed Lightning
  Speed also repeats; it doesn't, per the actual page text). `Charm` gained
  `variant_picks_first_purchase`/`variant_picks_per_purchase` (2 Gifts on the
  first purchase of Deadly Beastman Transformation, 1 on each after) and
  `repeatable_cap_ability` now accepts the special value `"essence"` (Deadly
  Beastman Transformation caps on Essence, p.124 — not an Ability or Attribute,
  so the existing Ability→Attribute fallback chain needed a third branch).
  `ExaltDefinition.gift_charm_id` names the splat's Gift-granting Charm
  (Lunar-only today, `""` elsewhere), mirroring `ox_body_charm_id`.
  `Character.beastman_gifts: list[BeastmanGiftPurchase]` holds one record per
  purchase (its `gifts` list, NOT `character.charms` — same reasoning as
  `ox_body`). **Anything that enumerates `character.charms` must special-case BOTH
  repeatable lists**: the sheet's Charm rows, the XP-log label, and the chargen
  Charm-pick counters in `ui/picker.py` and `ui/editor.py` each had an ox_body
  branch and no gift branch, so a bought DBT was invisible on the sheet, logged as
  the raw string "beastman_gifts", and uncounted against the Charm pool. Grep
  `ox_body` across the UI when adding a third such Charm. `models/rules.py`/`validate.py`/`costs.py`/`advancement.py`/
  `lifecycle.py` all got the same treatment ox_body already has (cap/prereq/
  repeat-cap checks, BP/XP pricing as an ordinary Charm pick per purchase,
  snapshot copy, undo). The +Attribute points each purchase also grants
  (war-form Strength/Dexterity/Stamina) are deliberately NOT tracked — per the
  human's call, they only apply while the Lunar is actually in hybrid form,
  the same transient territory as the existing combat/attack-derivation
  out-of-scope decision. Picker UI: `ui/picker.py`'s `gift_detail()` panel
  shows what has been bought plus an **Add Gifts** button; the choosing happens in
  a dialog (`open_gift_dialog()`) with one row per Gift — name, repeat marker,
  full description, and the reason it is unpickable. 19 Gifts do NOT fit in the
  sticky detail card the way Ox-Body's two variants do, which is why this diverges
  from `ox_body_detail()`. Selection is dialog-local so Cancel is a true cancel,
  unchecking a Gift cascades away anything selected that depended on it, and the
  dialog says the p.126 list is "Sample Gifts", not exhaustive. `ui/view.build_charm_graph`
  got the same owned/available/locked special case ox_body's node already has.
  The human clicked through this UI on 2026-07-22 and it found two things no
  server-render check could: the dialog was translucent (it used `pal.card`, whose
  50/60 tint lets the page show through — dialogs now use `pal.card_solid`), and a
  bought DBT never appeared on the sheet. **Serve-and-grep proves a page renders and
  nothing throws; it says nothing about whether the result is right.** Budget a
  browser pass regardless.
- **Attributes are 9/7/5** (Casteless: 8/6/4, not a typo of Solar's 8/6/4 — same
  numbers, different reason). The Caste Attribute BP discount
  (`BonusPointCosts.attribute_caste_favored`, e.g. Lunar "4, 3 if a Caste
  Attribute") is a genuinely new per-category rate in `bonus_point_breakdown`'s
  Attribute accounting — every prior splat priced all three categories flatly.
- **Essence is a third distinct formula (p.91):** Personal = Essence + Willpower×2;
  Peripheral = Essence×4 + Willpower×2 + (highest Virtue × 4) — the *single*
  highest Virtue, not ΣVirtues (Solar/Abyssal) or the two highest (Dragon-Blooded).
  `EssencePoolSpec` gained `peripheral_virtue_mode: "highest"` and a
  `peripheral_virtue_coeff` (Lunar's is 4; every other splat's implicit ×1 is now
  explicit as the default).
- **Casteless is ONE condition on TWO fields, not an independent origin axis**
  like Dragon-Blooded's Dynastic/Outcaste. `character.origin == "casteless"` and
  `character.caste == "casteless"` must always agree — enforced by the new
  `validate.check_lunar_casteless_consistency` (`lunar-casteless-mismatch`),
  wired into `validate()`. Casteless: 8/6/4 attributes, 6 Charms (no free
  Finding-the-Spirit's-Shape, no Caste-favored minimum), no Ability minimums, no
  Renown Background. `ChargenBudgets.required_favored` is new (Lunar: Survival
  must always be a Favored Ability, p.90 — even for Casteless); the Survival-≥2
  /one-combat-Ability-≥1 floor (Casteless-exempt) reuses the existing
  `required_min_abilities` mechanism as-is.
- **Renown and Face are Storyteller-adjudicated, NOT dotted/XP-priced traits**
  (p.112-115) — each of 4 Renown scores (Succor/Mettle/Cunning/Glory, one per
  Virtue) runs 0-100 and is gained/lost via GM-called Virtue checks; Face (0-10)
  derives from total Renown plus freeform GM-judged feats this tracker doesn't
  and shouldn't try to check. Modeled on `PlayState.renown`/`.face` — the same
  ST-discretion, no-auto-accounting precedent as Limit — so it never touches
  chargen validation, the XP audit, or permanent derivations.
- **Theme:** `theme._LUNAR` — moonsilver, a cool silver-blue accent (`#3f5f80`) on
  a pale silvered parchment, `fam="slate"` so card tints read as brushed metal
  rather than sky blue.
- **Data authored:** `castes.json` (Full Moon/Changing Moon/No Moon/Casteless,
  with anima powers), `exalts.json` Lunar row, `chargen_budgets.json` `"Lunar"`
  + `"Lunar:casteless"` rows, `costs_bonus.json` Lunar row (Charm BP 7/5, Attribute
  4/3), `costs_xp.json` (Lunar row: new Charm 15/12, Essence `×9`, Caste-Attribute
  `(×4)−1`, per-circle spell `{Terrestrial:12, Celestial:15}` with No Moon's `−2` via
  `castes.json`'s `spell_cost_discount` — all from the Storytelling-chapter XP table,
  p.251; a Dragon-Blooded row was added the same pass: Essence `×10`, new Charm/Spell
  12/10, Immaculate Charm 15/12, p.292. Abyssal is intentionally absent — p.282 says
  its XP costs are the Solar default), 4 new Nature archetypes (Savant/
  Survivor/Thrillseeker/Visionary, p.91 — Lunars' list is Solar's 16 plus these),
  and 2 new Backgrounds (Heart's Blood, Renown — both Lunar-only via `exalt_type`).
  Editor's `_SPLAT_ORIGINS` gained a `"Lunar"` entry (Society/Casteless) so the
  origin is reachable in the UI; the Caste dropdown does NOT yet auto-sync with
  it, so picking one without the other trips the new consistency check.
- **Four Shapeshifting Charms may NOT be learned by other Exalted (2026-07-23).**
  The Eclipse/Moonshadow generalist rule (core p.127) otherwise opens ANY splat's
  Charms to a Celestial with a willing tutor, but shapeshifting is bound up with the
  Lunar body itself. `Charm.no_foreign_learning: true` — the same flag the Alchemical
  Weaving Engines use — is set on **Finding the Spirit's Shape, Deadly Beastman
  Transformation, Humble Mouse Shape and Prey's Skin Disguise**, and on nothing else
  Lunar. Human-listed in `images/Lunar/No Foreign Exalts.md`. The bar is narrow on
  purpose: every OTHER Lunar Charm still crosses over normally (Ox-Body, the
  Body Enhancement tree, ...), and a Lunar is unaffected. Pinned by three tests in
  `tests/test_lunar.py`, including one asserting the flagged set is EXACTLY those four
  so a later addition has to be deliberate.
- **Magic-track ceiling (rules-authority confirmed, 2026-07-22):** Lunars and
  Sidereals, as Celestial Exalted (not native sorcerers or necromancers, unlike
  Solar/Abyssal), reach **sorcery up to Celestial Circle** and **necromancy up
  to Shadowlands Circle** only. `exalts.json`'s Lunar row sets
  `highest_magic_circle_id: "Celestial"` — two circles below the bar
  (Terrestrial, Celestial), so barring the top one still leaves chargen sorcery
  reachable, the same shape as Solar's own bar. The Shadowlands-only necromancy
  cap has no separate field to set (see Solar's Shadowlands/Labyrinth necromancy
  access, p.223) — it's enforced purely by NOT authoring a Labyrinth or
  Void Circle Necromancy initiation Charm in Lunar's (or, later, Sidereal's)
  Occult charm file. **Flag for whoever authors Lunar/Sidereal Occult Charms:**
  stop at a Shadowlands Circle Necromancy initiation; do not add Labyrinth/Void.
  **Lunar Combo mixing rule (p.122) — done.** Any Attribute-based Charms combo
  freely already, unchanged (no restriction existed to relax). What p.122 adds:
  only Solar Eclipse and Abyssal Moonshadow may combine an Ability-based Charm
  with an Attribute-based one in the same Combo — every other caste, including
  every Lunar caste (whose native Charms are all Attribute-based anyway), may
  not. This matters once a Lunar (a Celestial-tier splat) learns an
  `open_to_tiers` Ability-keyed style like Five-Dragon Style alongside their
  native Charms. `engine.validate.combo_issues` flags
  `"combo-mixed-attribute-ability"` when a Combo mixes both kinds and the
  character's caste isn't `eclipse`/`moonshadow`. The p.122 dice-pool cap (2x
  Essence) for a legally-mixed Combo is NOT enforced — it's play-time numeric
  math with no home in this engine, same as the rest of attack/damage
  derivation; only Combo *composition* legality is checked. Tests:
  `tests/test_validate.py` (synthetic ruleset) and `tests/test_lunar.py` (real
  data, incl. the Five-Dragon Style crossover case).
