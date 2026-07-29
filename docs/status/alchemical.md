# Status detail — Alchemical

Referenced from `CLAUDE.md` → Status. DONE (started and shipped 2026-07-23).

Read from `images/Alchemical/` — pasted text from the Autochthonians book (1e
conventions — WP = two highest Virtues, health 7+Ess; it supersedes *Time of
Tumult*): `CH 2 Character Creation and Traits.md` (p.58-85), `CH 3 Charms.md`
(p.88-193, the Charm mechanics + catalogue), `CH 4 Miracles of the Machine God.md`
(the Alchemical sorcery-analogues / "weaving").

- **Charm Slot system DONE (p.88-89).** Alchemical Charms are **Attribute-keyed**
  (`Charm.min_attribute`, same field Lunar uses — NOT a new axis). New
  `Charm.installation_cost` (Personal Essence committed to install). The character
  has **4 General + 4 Dedicated Slots** (`ChargenBudgets.charm_slots_general/
  _dedicated`; `Character.general_charm_slots/dedicated_charm_slots`, None=base):
  Dedicated holds only a Charm keyed to a **Caste OR Favored Attribute** (a
  SPECIFIC-attribute match — `validate._charm_is_caste_favored` +
  `_caste_favored_attr_names`, unlike Lunar's category match), General holds any.
  **You pay for SLOTS, not Charm picks** — each Slot comes with a free Charm; extra
  General slots cost `bonus_costs.charm` (6), Dedicated `charm_favored_caste` (5).
  So charm BP/legality is slot-based for any splat with `charm_slots_* > 0`
  (`validate.uses_charm_slots`/`charm_slot_counts`), per-pick for everyone else —
  the non-slot path was refactored through `_charm_is_caste_favored` with NO
  behaviour change (all prior splats byte-identical). Chargen legality:
  `charm-exceeds-slots`, `charm-noncf-exceeds-general-slots`,
  `charm-installation-over-personal` (installed motes ≤ Personal pool — enforced
  per the user's call, the one bit of mote math that IS in chargen). `charm_min_
  caste_favored` is now 0/moot for Alchemical (the slot rule replaces it).
- **Starter Charm batch (21):** `data/charms/alchemical_general.json` (9 Transitory
  + 9 Sustained Augmentation of (Attribute)) and `alchemical_close_combat.json`
  (Tactical Analysis Engrams, Accelerated Response System, Dynamic Reaction
  Enhancement System) — the slot-engine test bed, superseded once the full CH3
  catalogue landed (below).
- **Confirmed from the mechanics preamble** (resolving earlier provisional calls):
  `tier:"Alchemical"` is RIGHT — p.90 says Eclipse/Moonshadow learn Alchemical
  Charms via the existing 20-XP foreign-charm rule, and MA needs the Perfected
  Lotus Matrix Charm, so nothing should auto-grant Celestial styles. "Non-
  Alchemicals cannot learn weaving Charms" (CH4) → those must be barred from
  foreign learners when authored.
- **Attributes are a NEW budget shape (`attribute_mode: "caste_favored"`, p.60):**
  9/6/4 dots go to disjoint Attribute *sets* — the caste's 3 Caste Attributes
  (min 2 each), 3 player-chosen Favored Attributes, and the remaining 3 — NOT to
  prioritized Physical/Social/Mental categories the way every prior splat does.
  New `ChargenBudgets` fields `attribute_mode`/`attribute_favored_count`/
  `attribute_caste_min`; new `Character.favored_attributes` (empty for every
  category-mode splat). Engine: `validate._attr_bp_caste_favored` +
  `_caste_favored_attribute_sets` do the BP accounting (caste & favored over-spend
  charged the discounted `attribute_caste_favored` rate, remaining the flat rate);
  `validate_chargen` adds `favored-attribute-count` / `favored-attribute-overlaps-
  caste` / `caste-attribute-min`. Category-mode splats are byte-identical (the
  branch only fires on `caste_favored`). Tests: `tests/test_alchemical.py`.
- **No Caste OR Favored Abilities (p.60):** 23 Ability dots, `favored_count: 0`,
  `ability_min_caste_favored: 0`, no ability minimums. (Contrast Lunar, which has
  no Caste Abilities but keeps Favored ones.)
- **Essence is a fourth distinct formula (p.61)** and fits existing fields: Personal
  = Essence×3 + WP; Peripheral = Essence×5 + WP×3 + (highest Virtue × 2). Encoded as
  `peripheral_willpower_coeff: 3` + `peripheral_virtue_mode: "highest"` +
  `peripheral_virtue_coeff: 2`. Essence starts at 2.
- **Five castes** (Orichalcum/Moonsilver/Jade/Starmetal/Soulsteel) with Caste
  Attributes + anima powers, in `castes.json`. No `foreign_charms`.
  - `charm_count: 8` (informational); `charm_min_caste_favored: 0` — the slot-fit
    rules replace the per-pick caste/favored minimum for Alchemical, so this stays
    0 on purpose.
- **Backgrounds — DONE 2026-07-23 (CH2 p.65-69). The FIRST Backgrounds in this
  project with real mechanics.** Backgrounds are soft everywhere else — free text,
  an autofill catalog, never hard-validated (see `CLAUDE.md` → Data conventions) —
  and the Alchemical book is the first to give them chargen rules. Modelled as a narrow,
  **opt-in** mechanism rather than a special case: `ChargenBudgets.background_rules`
  maps a Background **NAME** (lowercased — `BackgroundEntry.name` is free text, NOT
  a `BackgroundType.id`, so it cannot key on the id) to a `BackgroundRule`. It is
  empty for every other splat, pinned by a test, so nothing changes for them. It
  lives on `ChargenBudgets` (per-exalt-type) and NOT on `BackgroundType` because the
  rules modify otherwise-universal Backgrounds — Artifact is ordinary for a Solar
  and heavily reworked for an Alchemical.
  - `background_dots: 13` = the auto **Class ••• grant + 10 others** ("Class 3, plus
    10 others; only Artifact may be higher than 3 without bonus points", p.61).
  - **Enforced:** Class is automatically 3 (`background-below-minimum`); Backing
    requires Class 3+ (`background-requires`); **Artifact alone may exceed the
    pre-BP cap of 3** (`cap_pre_bp_exempt`), and **its 4th and 5th dots each cost
    TWO dots of the pool** (`expensive_above`/`expensive_dot_cost`), so Artifact 5
    eats 7 of the 13 dots. Helpers: `validate.background_rule`/
    `background_pool_dots`/`background_rating`/`background_issues`.
  - **Two different charges, do not conflate them:** exceeding the cap-3 rule costs
    `bonus_costs.background_above_3` (2) per dot; overflowing the 13-dot pool costs
    `bonus_costs.background` (1) per dot.
  - **Described, NOT enforced:** "3 artifact dots per dot bought" and Charms bought
    as artifacts — both grant things outside the dot economy.
  - **Followers / Influence / Resources stay offerable to Alchemicals** (user call
    2026-07-23). Class subsumes them and *civilized* Autochthonians may not take
    them, but **Lumpen outcasts explicitly do**, and `excluded_exalt_types` would
    wrongly hide them from a Lumpen character. The rule is recorded in Class's
    description instead.
  - Also authored: **Class** and **Vats** (both `exalt_type: "Alchemical"`), and
    Alchemical notes appended to **Artifact / Backing / Familiar / Manse** using the
    existing inline-parenthetical convention (cf. Artifact's Dragon-Blooded note).
- **Arrays DONE (p.89).** `models.character.Array` (+ `Character.arrays`, snapshot,
  lock copy). `validate.array_issues`/`validate_arrays`: ≥2 known Charms, all
  Attribute-based (no supernatural MA), no duplicate/cross-Array reuse, and only a
  Charm-Slot splat may build them (Eclipse/Moonshadow may not, p.90). BP = 1/Charm
  (an "Arrays" breakdown line shown only for slot splats). The ¾-rounded-up Array
  installation discount is applied by `validate._installation_motes`, which the
  chargen install-cost check now uses. Integrated Combos are a play-time grant, not
  modelled. Codes: `array-too-small`/`-unknown-charm`/`-duplicate-charm`/
  `-non-attribute-charm`/`-not-supported`/`-charm-reused`.
- **Submodules DONE (p.89).** `rules.Submodule` (list on `Charm.submodules`) +
  `character.SubmodulePurchase` (+ `Character.submodules`, snapshot, lock copy).
  **Dual-cost — NOT post-lock-only as first assumed:** the page prints "2 bonus
  points OR 6 experience", so `Submodule` carries both `bp_cost` and `xp_cost`; they
  can be bought at chargen (BP, a "Submodules" breakdown line beside "Arrays", slot-
  splats only) or post-lock (`advancement.learn_submodule`, priced from `xp_cost`,
  with undo + `_expected_cost` audit). May gate on their own `min_essence` and/or an
  Attribute (`min_attribute`/`min_attribute_rating`, e.g. omnidextrous needs Wits 3).
  `validate.validate_submodules`/`submodule_def`: parent Charm known, key real, no
  dup, minima met. Real datum: Polymodal Joint Bearings' omnidextrous submodule.
- **Full CH3 Charm catalogue DONE: 121 Alchemical Charms** across all
  10 categories — `general` (18 Augmentations), `close_combat` (20, incl. Perfected
  Lotus Matrix, the Ability-keyed MA gate), `ranged_combat` (11), `might_and_mobility`
  (18, incl. Strain Resistant Chassis Modification = the Alchemical Ox-Body, now
  `ox_body_charm_id`), `social` (12), `stealth_and_disguise` (9),
  `sensory_and_spiritual` (10), `medical` (11), `cognitive` (9),
  `essence_and_weaving` (3, the Weaving Engines). `data/charms/alchemical_*.json`;
  cascades pinned per-category in `tests/test_alchemical.py`
  (`_EXPECTED_CATEGORY_COUNTS` + one maxed-cascade test). Many Charms carry
  submodules (Essence Pulse Cannon 11, Multifunction Hypodermic 14 drugs, etc.).
  `Charm.arrayable` (False on the 3 Essence/Weaving Charms) is a new flag
  `validate.array_issues` checks.
- **CH4 weaving protocols — DONE 2026-07-23.** The actual page holds **38
  protocols = 23 Man-Machine (p.147-156) + 15 God-Machine (p.156-159)**, NOT the
  "44 = 32+12" an earlier plan estimated: that count was a line-range guess whose
  Man-Machine range swept in the 6 summoned-golem stat blocks and their 12 innate
  Charms (which are the golems' abilities, not protocols). Modeled as `Spell`s:
  (1) `SpellCircle.MAN_MACHINE`/`.GOD_MACHINE`
  + `CircleKind.WEAVING` + `TRACK_CIRCLES["weaving"]` — additive, every other splat
  byte-identical; (2) Alchemical `exalts.json` `magic_track:"weaving"`,
  `highest_magic_circle_id:"God-Machine"` (top circle barred at chargen, like Solar
  bars Solar); (3) the two Weaving Engine Charms set `grants_circle`; (4) all 38
  protocols authored in `data/spells.json` as `spell.man-machine.*`/
  `spell.god-machine.*` (the "identical to <spell>" ones carry a reference note in
  `cost.raw` rather than an invented number); (5) "Minimum Clarity" (and the one
  Maximum Clarity, Incarnation of Bestial Malice) recorded in the description,
  NOT enforced — play-time activation gate, same bucket as mote costs. Alchemicals
  now get a Spells picker page for free.
  **Foreign-learner bar — a hole in the plan's stated auto-bar, now closed.** The
  original plan claimed `accessible_circles` (which asks `charm_matches_splat`) blocks a
  foreign Eclipse — but the LEARN/CAST gate is `granted_circles`, which is NOT
  splat-gated, and `foreign_charms: True` on Eclipse is an unrestricted boolean, so
  a locked Eclipse could foreign-learn a Weaving Engine and reach the circle. CH4
  states outright "Non-Alchemicals cannot learn weaving Charms", so this is barred
  at the Charm level: new `Charm.no_foreign_learning` (True on both engines);
  `charm_learnable_by_splat` refuses it via the generalist rule, and
  `check_splat_consistency` raises `charm-wrong-splat` even when foreign learning is
  otherwise permitted. Pinned in `tests/test_alchemical.py` (weaving section).
  NOTE for later data: any other splat's magic that must never cross via the
  generalist rule should set the same flag — the four Lunar Shapeshifting Charms
  now do (see `lunar.md`).
- **XP / advancement — DONE 2026-07-23** (verified against the CH2 p.64 EXPERIENCE
  COSTS table). Trait costs:
  `ExperienceCosts.attribute_favored_caste` = (rating×4)−1 (new field, model default,
  inert for category-mode splats whose caste-favored attribute SET is empty), Essence
  ×9 (`costs_xp.json` Alchemical row). **Charm-Slot economy:** new `Character.retainer_charms` (the Panoply —
  OWNED-but-not-installed Charms, kept OUT of `charms` which the Slot rules count);
  `advancement.buy_charm_slot(dedicated=…, charm_id=…)` (General 12 / Dedicated 10,
  installs the bundled free Charm, Dedicated requires
  `validate.charm_fits_dedicated_slot`), `upgrade_charm_slot` (Dedicated→General, 2),
  `learn_retainer_charm` (flat 6, no Slot). Per-circle protocol XP via new
  `ExperienceCosts.spell_cost_by_circle` (`{Man-Machine:12, God-Machine:14}`; wins
  over the flat rate and ignores the Occult discount) — `spell_cost` now takes the
  spell. `learn_charm` RAISES for a `uses_charm_slots` splat (routes to the Slot/
  Panoply calls) so a Slot is never silently skipped. Undo + `_expected_cost` audit cover every
  new domain (`charm_slots.general/dedicated`, `charm_slot_upgrade`,
  `retainer_charms`). Tests: `tests/test_alchemical.py` XP section.
  **Martial Arts via Perfected Lotus Matrix — DONE** (CH3 p.100). PLM
  installed lets an Alchemical learn Terrestrial/Celestial MA Charms "as any Celestial
  Exalt": `validate.charm_matches_splat` now grants a `Celestial`-tier MA style when
  `has_perfected_lotus_matrix` (PLM id in `charms`); `advancement.learn_martial_arts_
  charm` costs the flat 11 (`new_martial_arts_charm`); the Charm is stored IN the
  Matrix, so `validate.charm_occupies_slot` returns False for it and the Slot count
  skips it (it still lives in `charms`, so its style-tree prereqs resolve normally).
  Remove PLM → `charm_matches_splat` stops granting the style (access revoked, p.100).
  Only Hungry Ghost + Five-Dragon MA data exist today, so those are what an Alchemical
  can currently learn; more styles = pure data. **Ox-Body takes a Slot** (user ruling: every Alchemical Charm occupies a Slot). Each Strain
  Resistant Chassis purchase counts against Slots at chargen (the slot block adds
  `len(ox_body)` + its install motes) and, post-lock, `learn_ox_body(..., dedicated=)`
  costs a Slot (12/10) and raises the Slot count for a `uses_charm_slots` splat (flat
  new-charm rate still applies to Solar/DB/Abyssal/Lunar Ox-Body). New undo/audit
  domains `ox_body_slot.*` and `martial_arts`.
  **Eclipse/Moonshadow ↔ Alchemical crossover — DONE** (p.90). A
  non-Alchemical learning an Alchemical (Slot-splat) Charm through the generalist rule
  now gains a **General Charm Slot** with it: `advancement.learn_charm` detects
  `validate.crossover_alchemical_charm` and, alongside the 20-XP foreign price
  (Solar `new_charm` 10 × the caste's ×2), increments `general_charm_slots`, logging
  under a distinct `crossover_charms` domain so undo gives the Slot back too. The
  cheaper **Panoply** alternative (add the Alchemical Charm to `retainer_charms`, NO
  Slot) is `learn_retainer_charm` at the caste's flat crossover rate — new
  `CasteDefinition.foreign_panoply_charm_xp` (**8** on `eclipse`; set it on
  `moonshadow` too when that caste's `foreign_charms` lands). A crossover Panoply
  holds only Alchemical Charms (guarded via `splat_uses_charm_slots`). Arrays stay
  barred (already gated on `uses_charm_slots`, False for an Eclipse) and weaving stays
  barred (`no_foreign_learning`). NOTE: `uses_charm_slots` stays budget-based (False
  for an Eclipse) — their Slots are self-balancing (1 General Slot per Alchemical
  Charm), so the chargen 4/4 Slot-budget validation deliberately does NOT apply; the
  Slot count is tracked purely so the Vat-Refit UI can show/swap them.
  **Chargen Panoply (answered from source, CH2 p.68-69):** an Alchemical CAN take
  retainer/Panoply Charms at creation — via the **Vats Background** (1 retained Charm
  per dot) and the **Artifact Background** (Charms as artifacts, rating = min Essence),
  both "on retainer... do not increase installable Charms". The flat 6-XP buy is
  post-lock only. Backgrounds here are soft free-text, so a chargen retainer count is
  NOT validated against Vats rating (consistent with every other Background) — the UI
  may still let you list them.
- **Charm Attribute minima — DATA BUG FOUND AND FIXED 2026-07-23.** All 120
  Attribute-keyed Alchemical Charms shipped with `min_ability: 0`. The convention
  (shared with Lunar, `models/rules.py`) is that **`min_attribute` NAMES the gating
  trait and `min_ability` RATES it** — the first authoring pass captured only the
  name. Two silent consequences, both invisible without cross-cutting data: every
  Alchemical Charm gated on *nothing* (an Essence-2 character could install a
  Minimum Dexterity 5 Charm), and every **Array priced at 0 XP**, since an Array's
  cost IS the sum of exactly those ratings (p.89). Ratings were extracted from the
  `Minimum <Attribute>: N` lines in `images/Alchemical/CH 3 Charms.md` and are pinned
  by `test_every_attribute_keyed_charm_carries_its_minimum_rating`. **Gotchas for
  anyone re-parsing that page:** it prints both `Cost:` and `Costs:`, the typo
  `Minimums <Attr>:`, one trailing comma, one heading wrapped across two lines
  (INTERPOLATIVE SITUATIONAL ANALYSIS / PROCESSOR), and four *template* entries that
  expand to several Charms each (Transitory/Sustained Augmentation of (Attribute),
  (Material) Synthesis Wave Emitter, (Element)-Inured Frame). The 10 category
  headings all end in "CHARMS" and no Charm name does — that is what distinguishes
  them. **God-Machine Weaving Engine needs Minimum Intelligence 6**, the chapter's
  only above-5 minimum, legitimately reachable because Sustained Augmentation raises
  that Attribute's maximum by a dot (p.92); the maxed-cascade fixture sets 6 for that
  reason. This is the same bug class as the Lunar charm-discount miss: **when a splat
  introduces a new gating axis, re-audit every field that axis is supposed to fill,
  not just the one that makes the tests pass.**
- **UI pass — DONE 2026-07-23.** `theme._ALCHEMICAL` (brass, `fam="yellow"`,
  accent `#a8792c` — a true warm brass; the first attempt `#9a7b1f` read too olive
  and the user flagged it, so do not revert toward yellow-green); a legal example
  (`examples/gearheart.character.json`, Orichalcum, fills all 8 Slots); the editor
  Attribute panel handles caste_favored mode (`view.uses_caste_favored_attributes`/
  `attribute_budget_summary` — a Favored-Attributes multi-select, ● Caste / ✦ Favored
  marks, the set-based "Caste 9 (min 2 each) · Favored 6 · Other 4" header, and the
  Favored-Abilities picker hides itself when `favored_count==0`); the picker + editor
  Charm readouts show Slot occupancy for slot-splats (`view.charm_slot_budget` →
  `SlotBudget`, backed by the new engine `validate.charm_slot_usage`, which the chargen
  Slot check now also consumes so they can't disagree); the weaving Spells page works
  for free (accessible_circles surfaces Man-/God-Machine) with the track labelled
  "Weaving Protocols" and per-circle pricing (12/14, `spell_cost` now takes the spell).
  Alchemical has no origin sub-types, so `_SPLAT_ORIGINS` needs no entry.
  **Augmentation grouping:** the 18 "Transitory/Sustained
  Augmentation of (Attribute)" Charms STAY 18 distinct ids in the data — 82 other
  Charms name a SPECIFIC one as a prerequisite, so a literal merge to 2 Charms would
  break all of them. Instead the
  picker COLLAPSES the Alchemical `general` category from an 18-node Cytoscape graph
  into two per-type pop-up cards (Transitory / Sustained), each opening a DBT-style
  dialog with a checkbox per Attribute that installs/removes that specific id.
  Presenters: `view.augmentation_category` (the category is detected by "all its
  Charms are '<Type> Augmentation of <Attr>'", data-driven, not hardcoded) +
  `build_augmentation_view` → `AugmentGroup`/`AugmentEntry`. Picker: `_is_augment_page`
  swaps the canvas for `augment_panel` (the category dropdown STAYS so you can leave;
  `init_graph`/`update_graph` no-op there); `toggle_augment` is an immediate pre-lock
  add/remove with the usual `charms_depending_on` removal guard. In-play buying still
  routes through the post-lock Slot flow — the dialog is pre-lock only.
  **Arrays tab:** A Charm-Slot splat builds Arrays INSTEAD of
  Combos, so the Combos tab renders one system or the other on `view.uses_arrays`
  (which is just `uses_charm_slots` — a later Slot splat needs no UI change) and the
  tab is relabelled "Arrays" for them; the tab keeps its internal `"Combos"` name so
  tab state/visibility/`resolve_tab` are untouched. Pre-lock builds in place at
  1 BP/Charm; post-lock buys whole via the new `advancement.add_array` (XP = Σ member
  minimum Attribute ratings, `costs.array_cost`), with undo and `_expected_cost`
  audit under an `arrays` domain. The post-lock path enforces the CROSS-Array rule
  too (a Charm joins only one Array) — `array_issues` alone checks only within one
  Array. `validate.eligible_array_charms` is the pool; each Array shows the committed
  Essence its three-fourths discount saves, via the new public
  `validate.array_installation_motes` (which `_installation_motes` now calls, so the
  readout and the chargen check cannot diverge).
  **Submodules:** A SUBMODULES section on the picker's sticky
  detail card, on the Charm they upgrade (not a catalogue page — they are per-Charm).
  Shows the dual price (BP pre-lock, XP post-lock), the submodule's own minima, owned
  state, and the block reason. `validate.submodule_block_reason`/`owns_submodule` are
  the single eligibility source (same gates `validate_submodules` and
  `advancement.learn_submodule` apply); presenter `view.build_submodule_rows` →
  `SubmoduleRow`. Renders nothing for the ~112 Charms with no submodules.
  **Vat Refit:** A "Vat Refit" group on the Charms tab toggle,
  beside Abilities / Martial Arts / Spells: installed (Slot) Charms vs the Panoply,
  with swap buttons. New **`engine/refit.py`** owns the `charms` ↔ `retainer_charms`
  move (`install`/`uninstall`/`install_block_reason`/`slot_load`/`supports_refit`,
  `RefitError`). It is play-state — no BP, no XP, no log row — but the move has
  mechanical weight, so it checks Slot fit (Dedicated Slots take only Caste/Favored
  Charms) and committed Personal Essence, applying the Array discount to the delta.
  **`refit.slot_load` deliberately does NOT call `validate.charm_slot_usage`:** that
  function reads the frozen chargen snapshot once locked and answers "was this
  legally built?", while a refit asks "what is worn *right now*". Conflating them
  would make a refit either invisible or look like chargen tampering; a test pins
  that a refit moves the live count and leaves the chargen view untouched. Ox-Body
  purchases occupy Slots but live on `character.ox_body`, so they are counted as
  fixed load and are not swappable. `supports_refit` keys on having a Panoply or
  Slots rather than on the splat, so an **Eclipse who crossed over** (p.90) gets the
  page without being a Slot splat.
  **Clicked through in a browser by the human on 2026-07-23** — Edit, Charms
  (Augmentation pop-ups and Vat Refit), Arrays, XP, Play (Clarity) and Sheet, plus
  the Background dropdown tooltips. Everything up to that point had been verified by
  serve-and-grep + unit tests only, which prove no crash and say nothing about
  layout; the Lunar DBT dialog pass found two bugs no server-render check could, so
  the pass was not a formality.
  **Clarity — DONE 2026-07-23** (CH2 **p.69-71**, in the Character Creation chapter,
  not CH3/CH4). The Alchemical replacement for Limit: they took no part in the Great
  Curse, so they have no Limit at all. Modelled as a split:
  - **Permanent Clarity is DERIVED, not tracked** — one dot per dot of Essence above
    5, plus one for each installed Charm that grants it (`Charm.permanent_clarity`,
    set on exactly six Charms: Hyperdextrous Tentacle Apparatus, Insectile Locomotion
    Upgrade, Transcendent Brutality Programming, Clarified Data Assimilator, and both
    Weaving Engines). Reading it off the LIVE `character.charms` makes p.70's
    "removing these conditions immediately removes the appropriate amount of
    permanent Clarity" free — a vat refit that sheds such a Charm sheds its dots, with
    no bookkeeping. This is the "capacities flow OUT of the engine" rule, same as the
    health track.
  - **Temporary Clarity is TRACKED** on `PlayState.clarity_temporary`, alongside Limit
    and Renown — it moves on Storyteller calls (suppressing Virtues, weeks without
    human contact, Compassion rolls after a scene) that this engine does not model.
  - Total = permanent + temporary, **hard-capped at 10** ("cannot ever exceed 10 under
    any circumstances"). Unlike Limit it never breaks or resets.
  - `derive.clarity` → `ClarityView` (permanent/temporary/total/itemised sources/band/
    effects); `derive.CLARITY_BANDS` holds the p.70-71 table. **The band is DISPLAY
    ONLY** — the dice penalties and bonuses are printed text, nothing applies them to
    a roll (same scope line as combat/attack derivation).
  - `ExaltDefinition.clarity` (data, True on Alchemical) decides whether the Play tab
    and the GM card show Clarity or Limit — no splat is named in UI code.
  - **NOT modelled: Gremlin Syndrome / Dissonance** (p.71). It is explicitly "an
    Alchemical-only **Flaw** worth 5 bonus points", and Merits & Flaws are out of the
    project until the centralized re-add (see `CLAUDE.md` → Removed). Revisit it with
    M&F, not before.
  **Weaving Engines can never be uninstalled** (CH3 p.141: "she cannot ever remove
  the Man-Machine Weaving Engine"). New `Charm.permanent_install` (True on both
  engines) which `refit.uninstall_block_reason` refuses — a flag, not an id check, so
  another such Charm is pure data.

**Rules-authority call, CONFIRMED 2026-07-23 — do not relitigate:** moving a Charm
to the Panoply leaves its *dependents* installed. `refit.uninstall` deliberately
does NOT cascade or block the way the pre-lock picker's `charms_depending_on` guard
does, because a Panoply Charm is still OWNED — a prerequisite must be owned, not
worn. (The pre-lock guard is a different case: there the Charm is being *unlearned*.)
