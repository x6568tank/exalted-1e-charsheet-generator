# Status detail — Models, Engine, UI

Referenced from `CLAUDE.md` → Status. This file covers the splat-agnostic
foundation: persistence, `engine/`, and the NiceGUI frontend. Per-splat detail
lives in sibling files in this directory.

## Models, loader, persistence — done
`models/rules.py`, `models/character.py`, `rules_db.py`, `persistence.py`.
Persistence is atomic JSON load/save (tempfile + `os.replace`, shared by
`save_character`/`save_party`), enum-keyed dicts, and deployment-aware filenames
(`slugify_name`/`suggested_filename`; `default_save_dir` sits next to the
executable when frozen so a double-clicked build doesn't write into its temp
extraction dir). `character_to_json`/`_from_json` and their `party_*` mirrors are
the in-memory (de)serialisers the browser upload/download path reuses.

## Engine
- `derive.py` — Clarity (Alchemical, see `alchemical.md`); Willpower; per-splat Essence pools via `RuleSet.exalts`/`exalt_for`
  (essence coefficients + an optional Breeding-Background term for Dragon-Blooded);
  health track; per-type soak (bashing/lethal/aggravated, core pp.231-232).
- `validate.py`:
  - Reference integrity; Charm prereqs (AND-of-OR + min ability/essence);
    `meets_charm_requirements`/`charms_depending_on` (picker eligibility + safe removal).
  - **The generalist rule — Solar Eclipse (core p.127,
    `images/Solar/Traits/126-127.png`) AND Abyssal Moonshadow (Abyssals p.146,
    `images/Abyssal/Traits/145-146.png`), DONE 2026-07-29:**
    "Provided they have a willing tutor, they may learn the Charms of other types
    of Exalted... Such Charms cost double the normal experience to learn (usually
    20 points) and use. Eclipse Caste characters may not start the game knowing
    the Charms of other such beings without Storyteller permission." The Moonshadow
    page prints the same rule in the same words (it adds only "(including ghosts)"),
    so it is the same numbers: ×2, and no chargen Charms without ST permission.
    **The chargen permission moved 2026-07-29** — it was `Character.st_foreign_charms`
    and is now `Character.house_rules.st_foreign_charms`, gathered with the other
    Storyteller options; read it via `validate.foreign_charms_permitted(character)`.
    A legacy top-level key is migrated forward on load (`Character.
    _migrate_legacy_st_foreign_charms`), so already-saved Eclipses and Moonshadows
    keep their permission. The picker still renders the checkbox, marked with a
    TODO — it belongs on the ST-options tab once that exists.
    Modeled as
    DATA, not a caste check in code: `CasteDefinition.foreign_charms` +
    `foreign_charm_xp_multiplier` (2), now set on BOTH `eclipse` and `moonshadow`.
    That design paid off exactly as intended — the Moonshadow half was three keys in
    `castes.json` (`foreign_charms`, `foreign_charm_xp_multiplier`,
    `foreign_panoply_charm_xp: 8`) and ZERO engine, pricing or UI changes; the picker's
    Splat dropdown and the ST-permission toggle are gated on `foreign_charms_open`,
    never on a caste id. `tests/test_eclipse_foreign_charms.py` now runs the whole rule twice,
    once per caste, with a Dusk as the same-splat control. The chargen
    permission is `Character.house_rules.st_foreign_charms` (read it via
    `validate.foreign_charms_permitted`); post-lock it falls away (a willing
    tutor is narrative). Engine surface: `validate.foreign_charms_caste` /
    `foreign_charms_open` / `is_foreign_charm` / `charm_learnable_by_splat`;
    `check_splat_consistency` raises `charm-foreign-no-st-permission` (not
    `charm-wrong-splat`) for a permitted caste that lacks ST sign-off.
    Rules-authority calls, 2026-07-22 — **not printed on the page, do not
    relitigate as if they were**: (1) chargen pricing is UNCHANGED — a foreign
    Charm takes a Charm pick, or normal BP; only the XP economy doubles;
    (2) **full Caste/Favored treatment** — the discount applies FIRST and the ×2
    LAST (`costs.charm_cost`), and a foreign Charm counts toward the C/F chargen
    minimum; (3) **prereqs only** — the other splat's *internal* gates do not
    follow the Charm, so the DB Dragon-Path enlightenment pair does not bind an
    Eclipse (this already fell out of `db_enlightenment_met` returning True for
    non-DB; it is now pinned by a test); (4) **sorcery/necromancy access is NOT
    widened** — `accessible_circles` still asks `charm_matches_splat`, so a foreign
    initiation Charm does not grant its Circle and an Eclipse cannot route around
    their own splat's magic-track ceiling through someone else's initiation.
    `is_foreign_charm` takes the RuleSet on purpose: the `open_to_tiers` styles a
    Celestial learns natively (Hungry Ghost, Five-Dragon) are NOT foreign and must
    never double. **Deliberately not modelled:** the doubled cost "to use" (motes —
    play-time math, same bucket as combat derivation), and spirit Charms (no
    catalogue exists).
  - **Splat consistency:** `Charm.exalt_type` gates a Charm to one splat;
    `Charm.open_to_tiers` gates it to an Exalt *tier* instead (e.g. Hungry Ghost
    Style and Five-Dragon Style are `[Celestial]` — any Celestial Exalt can learn
    them, so adding Lunars/Sidereals as Celestial splats grants both with no code
    or data change).
  - **Dragon Path enlightenment gate:** a Dragon-Blooded needs both Spirit Sight
    and Spirit Walking (ordinary Charm picks, not exempt) before any elemental
    Dragon Path style opens; no other splat needs this gate.
  - **Spell-circle access spans both magic tracks:** `CircleKind` distinguishes
    sorcery (Terrestrial/Celestial/Solar) from necromancy (Shadowlands/Labyrinth/
    Void); `accessible_circles()` returns every circle reachable via any learnable
    initiation Charm rather than just the splat's nominal `magic_track`, so e.g. an
    Abyssal's sorcery spells don't hide behind its necromancy track.
  - `validate_chargen` — attribute/ability/background/virtue budgets + pre-bonus
    caps, caste/favoured minimums, charm counts, Willpower start-cap, bonus-point
    accounting (pp.104-105) — all pulled per-exalt-type via `RuleSet.budgets_for`/
    `bonus_costs`. `bonus_point_breakdown` is the pure per-domain BP accounting the
    chargen ceiling check consumes.
  - **The canonical Charm-pick enumeration — BOTH HALVES DONE 2026-07-29.** A
    repeatable Charm lives on its own `Character` list (`ox_body`, `beastman_gifts`)
    and granted Charms on a third, never in `character.charms`; every consumer that
    walked `character.charms` used to special-case each list, and four separately did
    not when Gifts landed. There is now exactly one enumeration and one price ladder:
    - `charm_picks(ruleset, character)` → `list[CharmPick]` — what the character holds
      RIGHT NOW, in sheet order. `charm_id`/`name`/`label`/`category`/`source`/
      `counts_toward_pool`/`caste_favored`. Repeatable purchases arrive one entry each,
      already labelled with their variant(s); granted Charms are listed with
      `counts_toward_pool=False`. Consumed by `view.build_sheet_view` and both chargen
      counters (`ui/picker.py`, `ui/editor.py`), plus `charm_pick_count`.
    - `chargen_charm_picks` — the same list over what the chargen accounting reads: the
      frozen snapshot once locked, else the current lists. Granted Charms are read live
      either way (they cost nothing and the snapshot does not hold them).
    - `charm_pick_bp_costs` — the price of each pool-counting pick. ONE ladder, most
      specific claim first: Calling (p.90) → Immaculate (DB p.151) → Martial Arts
      (Sidereal p.101, `None` → the ordinary rate) → ordinary. `bonus_point_breakdown`
      calls it instead of rebuilding the pick list, and `validate_chargen`'s
      Caste/Favoured pick minimum counts `caste_favored` off the same picks.
    `_ox_body_caste_favored`/`_gift_caste_favored` are GONE — `_charm_is_caste_favored`
    now decides for every source uniformly. **One behaviour change fell out, and the human RULED ON IT
    2026-07-29 (confirmed — do not relitigate):** the Paladin Calling (Cult of the
    Illuminated p.91) names Ox-Body Technique in its discount list, so an Ox-Body
    *purchase* pays the Calling rate (4/3) rather than the flat Charm rate — "if it says
    it should be discounted, discount it", and that applies to every purchase, not just
    the first. The old code priced that list separately and never consulted the Calling.
    Paladin is the only Calling naming a repeatable Charm, so it is the only character
    affected. Pinned in `tests/test_charm_picks.py`. `tests/test_chargen.py`'s fixture
    RuleSet gained an `exalts` row naming its Ox-Body Charm; without one
    `ox_body_charm` resolves to nothing and a purchase is invisible to every consumer.
    **Still not unified:** the XP-log label in `view.py` is keyed by XP *domain*, a
    different axis, and is untouched. A new repeatable Charm still needs its own
    `Character` list, cap/variant checks, lock snapshot, undo and picker panel — but
    display, counting AND pricing now come free once it is enumerated. The concrete case
    waiting on that storage work: Environmental Hazard-Resisting Meditation
    (Caste Book: Zenith p.72-73).
  - **Spells at chargen (p.100):** share one pool with Charms — a spell takes a
    Charm pick 1:1, costs the same BP, gets the Occult discount, and counts toward
    the C/F minimum. The circle barred at creation is
    `ExaltDefinition.highest_magic_circle_id` (`""` = nothing withheld — e.g.
    Dragon-Blooded, whose only circle is Terrestrial).
  - **Combos (pp.213-214):** ≥2 *known* Charms, instant duration only, no duplicate
    Charm, ≤1 Simple, ≤1 Extra Action; BP = 1 per Charm in the Combo.
  - **Immaculate Order path:** 5 Immaculate Charms all in one elemental tree, the
    C/F minimum waived, a separate BP row (10/7) — the two Dragon-Path enlightenment
    Charms count as ordinary Charms within this package, not exempt.
  - **Ox-Body Technique (p170):** repeatable once per dot of the splat's cap
    trait — Endurance for Solar/DB/Abyssal, **Stamina for Lunar** (p.132), and
    Essence for Deadly Beastman Transformation. Never write that trait as a literal
    in UI copy or an engine message: use `view.repeatable_cap_trait` (label + "dot"/
    "point" unit) or `validate.repeatable_cap_trait_name`, both of which read the
    same `repeatable_cap_ability` field the cap arithmetic does; each purchase picks ONE health-level-package variant;
    lives on `Character.ox_body` (not `character.charms`) so N copies are
    representable.
  - **Craft (p136):** per-focus Abilities on `Character.crafts`, each budgeted/
    capped/discounted like its own Ability instance; the `AbilityName.CRAFT` dot
    itself is unused.
- `lifecycle.py` — `lock_chargen` freezes `wp_virtue_component` + a snapshot
  (charms/spells/combos/ox_body/crafts); `unlock_chargen` reverses it.
- `costs.py` — pure per-advance XP price from `RuleSet.xp_costs`, per-exalt-type:
  scaled traits cost `current rating × N`; new Charm/spell/specialty/Combo pricing.
  Two per-splat discount axes beyond the Ability Caste/Favoured one: a **Caste-
  Attribute** rating discount (`ExperienceCosts.attribute_caste_favored`, threaded
  through `attribute_step(…, attr)` — Lunar's `(×4)−1`, p.251) and an **Immaculate
  Charm** rate (`new_immaculate_charm`, keyed on `Charm.immaculate` in `charm_cost`
  — Dragon-Blooded's 15/12, p.292). Combo XP sums member `min_ability`, which also
  captures Lunar Attribute-keyed Charms since their required rating lives in
  `min_ability` (only `min_attribute` names which Attribute). **Spell XP has two
  data-selected policies:** the flat `new_spell` (discounted when Occult is Caste/
  Favoured — Solar/DB/Abyssal), OR per-circle via `ExperienceCosts.new_spell_by_circle`
  (Lunar's Terrestrial 12 / Celestial 15, p.251), in which case the discount switches
  to the learner's `CasteDefinition.spell_cost_discount` (No Moon's −2) and the
  Occult-favoured axis does NOT apply. `spell_cost(rs, char, spell)` takes the spell so
  it can read its circle; a `None` spell falls back to the flat price.
- `advancement.py` — post-lock XP transitions: `raise_attribute/ability/virtue/
  willpower/essence`, `learn_charm/spell/craft/ox_body`, `add_combo/specialty` —
  each priced, legality-checked, applied, and logged as an append-only `XpEntry`;
  `undo_last` reverses LIFO; `validate_xp` audits overspend/tampering. `lower_*`
  (curses / Charm costs) reduce a permanent trait OUTSIDE the XP economy at cost 0
  — Willpower's purchased component can go net-negative, so a curse can drop
  Willpower below the Virtue floor.
- `refit.py` — the Alchemical vat refit: moves a Charm between the Charm Slots and
  the Panoply (`character.charms` <-> `retainer_charms`). Play-state, NOT an XP
  transaction — nothing here writes the ledger or reaches chargen validation — but
  the move respects Slot fit and committed Personal Essence. Computes the LIVE Slot
  load itself rather than reusing `validate.charm_slot_usage`, which reads the
  frozen chargen snapshot; see the Alchemical Vat Refit note (`alchemical.md`) for why.

## UI (NiceGUI)
File map: `ui/view.py` (pure, toolkit-free presenter), `ui/app.py` (read-only
sheet), `ui/editor.py` (chargen editor), `ui/picker.py` (Cytoscape charm/spell
picker, plus the Alchemical Vat Refit page), `ui/combos.py` (Combo builder — and
the Alchemical Arrays builder, which replaces Combos for a Charm-Slot splat), `ui/xp.py` (post-lock XP tab),
`ui/play.py` (in-play tracker), `ui/storyteller.py` (the ST Options tab),
`ui/builder.py` (unified tabbed app), `ui/gm.py`
(party page). Run: `.venv/bin/python -m exalted_builder.ui.builder [char.json]
[--show] [--port N] [--native]`. Example char: `examples/ashes-of-dawn.character.json`.

- **The picker's group toggle is built from what the splat HAS**, so no character
  sees all of it. The base three are Abilities / Martial Arts / Spells (each omitted
  when the splat has none of that kind); **Form Library** is added for a splat with
  `ExaltDefinition.form_library` (Lunar) and **Vat Refit** for one with Charm Slots or
  a Panoply (Alchemical, plus a crossover Eclipse) — both detailed in their splat's
  section (`lunar.md` / `alchemical.md`). **Thaumaturgy** is the one page every
  character gets unconditionally, because it is a cross-splat capability layer rather
  than a splat feature (`thaumaturgy.md`). Martial Arts holds every `martial_arts:*` style category. Spells has
  a Circle dropdown offering every circle the character can reach across BOTH tracks,
  one full-width row per spell (add/remove/locked, cost, description, lock reason).
  A Charm category may also swap the Cytoscape canvas for its own panel — the
  Alchemical Augmentation pop-ups do, staying an Abilities page while replacing the
  graph.
- **Splat dropdown on the Charms tab (Eclipse generalist rule).** Rendered only for
  a caste with `foreign_charms`, and only on the two Charm-tree pages (spells are
  gated by circle, the Form Library is the character's own). Without permission the
  dropdown has one option and hides itself; **the permission checkbox itself moved to
  the ST Options tab 2026-07-29**, leaving the picker a pre-lock line pointing there. `view.charm_on_splat_page`
  is the filter: `""`/own splat is EXACTLY `charm_matches_splat` (so every existing
  splat's picker is byte-identical), and a foreign page is that splat's own Charms
  minus anything already native, so a Celestial's Hungry Ghost Style doesn't appear
  twice. Category names collide across splats ("melee" belongs to five), so
  `build_charm_graph` now takes `(category, splat)` — the pair identifies a tree, the
  category alone does not. The detail card labels a foreign Charm and its doubled
  price.
- **Form Library page (Lunar).** A fourth group on the Charms tab's toggle, beside
  Abilities / Martial Arts / Spells: the character's Totem plus every animal shape
  they have taken. Deliberately FREE — narrative bookkeeping the Storyteller
  adjudicates, so `Character.totem` / `Character.animal_forms` (`AnimalForm`) carry
  no cost, no cap and no reference into the RuleSet, and never enter chargen
  validation, the XP audit or any derivation. Same isolation as play-state, for the
  same reason. Gated on `ExaltDefinition.form_library` (data, not a splat check), so
  a later shapeshifting splat opts in without a code change.
- **ST Options tab (`ui/storyteller.py`).** The only place `Character.house_rules` is
  edited, and the home for **every** Storyteller toggle, not just thaumaturgy's — see
  `thaumaturgy.md` for the four it holds today. Three things about it are load-bearing
  for whoever adds the fifth:
  * **It is read-only post-lock.** The toggles change how chargen is PRICED and are
    frozen into the ChargenSnapshot, so flipping one after the fact would re-price a
    signed-off chargen. The tab says so and names Unlock as the route.
  * **TABLE-WIDE vs PER-CHARACTER is rendered as two sections**, from
    `view._HOUSE_RULES`. The model marks the split in comments only (human's call,
    2026-07-29 — one flat model), so the machine-readable copy lives in the presenter
    and `tests/test_thaumaturgy_ui.py` pins it to `HouseRules.model_fields`. **Add a
    field and that test fails until the table is updated** — which is the whole reason
    the comments-only choice is safe. A party-wide "apply to all" control may only
    touch the table-wide ones.
  * **An inert toggle is annotated, not hidden.** A Dawn still sees the foreign-Charm
    permission, with a note saying its caste cannot use it — an ST hunting for a
    setting should be told why it does nothing rather than wonder where it went.
- **Thaumaturgy page (`ui/picker.py` + `view.build_thaum_picker`).** Detailed in
  `thaumaturgy.md`; two notes that generalise beyond it. Its **purchase functions are
  module-level, not closures inside `build_picker`** (the `ui/play.py` precedent) —
  they mutate the save, and several buy buttons legitimately share a label ("5 BP" is
  every Art), so click-testing one in particular is impossible; module level makes them
  unit-testable. And its sub-tabs are real `ui.tabs` rather than the picker's usual
  `ui.toggle`, because **a toggle's options are not separate elements and so cannot be
  clicked from the User simulation** — worth knowing before adding another sub-paged
  panel. `build_picker` also gained `initial_group=` to open on a given page.
- **The charm graph draws cross-category prerequisites.** `build_charm_graph`
  pulls a category's out-of-category prerequisites in transitively and flags them
  `external` (dashed, smaller node); `roots` means "nothing in the graph points at
  it", not "has no prerequisites". Without this a cross-tree category has no
  visible root and Cytoscape's breadthfirst layout strings its orphaned branches
  into one long line — how the bug was spotted, on Lunar Body Enhancement, which
  is three separate trees all hanging off Shapeshifting's Shaping the Ideal Form.
  The sourcebook's own diagram boxes draw those foreign Charms too (p.132, p.135).
- **Chargen-vs-play is a MODE, not disabled tabs.** Edit and XP share one tab
  slot (Edit pre-lock, XP post-lock). Charms and Combos stay on the bar both
  stages and switch behaviour: pre-lock they pick freely against the chargen
  budget; post-lock they BUY through `engine.advancement` (priced "Buy · N XP"
  buttons, an XP-available readout, no removal — the only refund is last-first
  undo on the XP tab).
- **Save/Load is deployment-aware.** The shipped build runs in the browser
  (`pack/run_app.py`): Save downloads the JSON, Load is an upload. `--native`
  (needs pywebview + Qt/GTK) uses OS Save/Open dialogs instead — dev-only, not
  shipped (Qt bundling made native packaging ~280MB and non-portable).
- **GM mode (`/gm`)** — a Storyteller's party page: compact per-character cards,
  each a live play-state tracker with GM/session notes, saved as one
  `.party.json` (`models/party.py`: `Party` + `PartyMember` holding an
  **embedded full `Character` copy**, not a path reference — the browser
  deployment has no filesystem paths, so this is deliberate and means the GM's
  copy may drift from the player's own file). Cards edit **play-state and notes
  ONLY**; permanent-trait edits route through "Builder" against the same
  `Character` object (the roster holds it by reference, so builder edits land
  back with no sync code, and there's never a second Cytoscape instance on the
  page). **v1 scope stops here** — no initiative/turn order, no NPC stat blocks,
  no party-wide Rest; ask before adding them.
- **Storyteller reference screen (`/gm`).** A default-collapsed expansion at the
  top of the party page holding the rules tables off the tri-fold GM screen PDF
  (`images/exaltedscreen-20050917.pdf`, all 4 pages): Combat Resolution (attack
  sequence + Initiative/Movement/pools/Feats/Object Strengths/Success Modifiers/
  Cover), Actions (~68 with dice pools + page refs), the six-splat Anima Banner,
  Health/Wounds/Recovery, Environment & Hazards, and Traits & Core Rules. **Pure
  static display** — generic `RefTable`/`RefGroup`/`StScreen` models
  (`models/rules.py`), data in `data/st_screen.json` (optional → `RuleSet.st_screen`
  is `None` when absent), rendered by `gm._render_ref_table`/`_reference_panel`.
  Zero game logic: it never enters validation or derivation, the same isolation as
  play-state. Two Player's-Guide-flagged (`pg`) rows were deliberately CUT per the
  user (Combat-Pool "Delaying offensive action", Defense-Pool "Dodging (PC only)");
  the Initiative wound-penalty and Clinch/Hold `pg` items were KEPT. Values are
  transcribed from a low-res community PDF — the Feats-of-Strength lift column and
  the Anima Banner cells are the least-legible and were user-spot-checked (Feats
  row 6 corrected 650→550); re-verify against the PDF before trusting an exact cell.
- **Background dropdowns show their catalog description on hover.**
  `editor.DescribedSelect` (a `ui.select` subclass, reused by `ui/xp.py`) renders each
  option through Quasar's scoped `option` slot with a `QTooltip`. The descriptions in
  `backgrounds.json` were authored but read by nothing until this. **Do not try to
  attach the description by assigning `select._props["options"]` after construction:**
  `_props` is an observable dict, so the write schedules an update, and
  `ChoiceElement.update()` rebuilds `options` from the labels — silently discarding it.
  Overriding `_update_options` is what makes it stick (and survive `set_options`).
- **Gotcha:** NiceGUI 3.x's `ui.select` raises `ValueError` if constructed with a
  `value` not in its `options`. Any select whose value can be a free-text/custom
  entry must fold that value into `options` first (`editor._opts_with`) —
  otherwise a custom name renders once, then 500s on the next reload.
