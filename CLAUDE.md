# Exalted 1E Character Builder — Project Guide

## What this is
A character creator / validator for **Exalted First Edition (1e)** — character
generation, point validation, and XP advancement, with a character-sheet view.
Scope is deliberately smaller than EdExalted (which is 2e/2.5e only); **1e is
unserved, which is the entire point of building this.** Initial target was
**Solar** Exalted from the core rulebook; **Dragon-Blooded and Abyssal are now
also fully supported.** Sidereal, Lunar, Alchemical, and Mortal splats are next
— see **Next Exalt Types** below.

## ⚠️ EDITION: 1e ONLY — never substitute 2e/2.5e rules
This is the single most important constraint. 2e is far better represented than
1e in training data, so the default failure mode is silently "correcting" a 1e
value to its 2e equivalent. **Do not.** Treat the `data/` files and this document
as ground truth. If a rule isn't covered here or in the data, ASK — do not fill
the gap with a 2e value.

### Solar baseline (the numbers below are Solar-only)
Other splats have their own numbers in `data/exalts.json`, `data/chargen_budgets.json`,
and `data/costs_bonus.json` (each keyed by exalt_type) — check those tables before
assuming a Solar number generalizes. Dragon-Blooded and Abyssal already have their
own rows; do not reuse the Solar figures below for them. Broadly speaking, anything
that is not specified by a splat (bonus points, XP costs, etc) *will* default to 
Solar values. If unsure, ask human.

- Attribute chargen pools: **8/6/4** across prioritized categories (all start at 1).
- Abilities at chargen: 25 dots, ≥10 on caste/favored, ≥1 in each favored ability,
  max 3 in any ability without spending bonus points.
- Charms at chargen: 10, with ≥5 from caste/favored. Bonus points: 15.
- Willpower = sum of the **two highest Virtues** (may not start >8 unless ≥2
  Virtues are ≥4). Raising a Virtue *after creation does NOT raise Willpower.*
- Personal Essence (Solar) = Essence×3 + Willpower.
  Peripheral = Essence×7 + Willpower + ΣVirtues.
- XP increases are `current rating × N`: attribute ×4, ability ×2,
  favored/caste ability `(×2)−1`, virtue ×3, willpower ×2, essence ×8.
  New charm 10 (8 if favored/caste). New spell 10 (8 if Occult is caste/favored).
  Health: 7 base levels + Charm bonuses.
- The ability roster is the 25 caste-grouped abilities. **Martial Arts is a
  separate ability from Brawl, and there is no "War" ability in 1e core.**

## Next Exalt Types
Dragon-Blooded and Abyssal are done (see Status). **Lunar is functionally
complete** (chargen foundation + full Charm catalogue, started 2026-07-22) —
see the Status entry below. **Sidereal and Alchemical are next** — no build
order chosen for them yet; ask the user before starting. **Mortals**
(Godblooded/Ghosts/Heroic Mortals/etc.) are planned after the Exalt types.

Work on a given splat starts only once its rulebook images land in
`images/<ExaltName>/` — never author data from memory, per the Workflow rule below.

**Splat color scheme (UI theming):**

| Splat | Color | Status |
|---|---|---|
| Solar | Amber/Gold (default) | DONE |
| Abyssal | Black on ash | DONE |
| Dragon-Blooded | Vermillion | DONE |
| Lunar | Moonsilver blue (`slate`) | DONE (chargen, full Charm catalogue, Combos, Gifts, Form Library; UI clicked through 2026-07-22) |
| Sidereal | Purple | waiting on Sidereal chargen work |
| Alchemical | Brass | waiting on Alchemical chargen work |
| Mortals | Muddy brown | waiting on Mortal chargen work |

**Merits & Flaws will return once every splat above is implemented** — as a
single centralized M&F calculation function, specifically so mechanical effects
don't get scattered invasively across files the way the old implementation did.
Until that milestone, the removal in Status stands: do not reintroduce the old
per-file hooks.

## Architecture — keep these boundaries
- **Pure engine, disposable UI.** All validation and derivation are pure functions
  of `(RuleSet, Character)` — no I/O, no UI, no mutation. The UI calls the engine
  and contains **zero game logic.**
- **Two data domains, kept separate:** *rules data* (the rulebook — static, loaded
  once, read-only) and *character data* (the save file — mutable). Characters
  reference rules by id.
- **pydantic guards shape; the engine guards rules.** Models enforce only
  structural invariants (non-negative ratings, valid enums, ≤5). Game legality
  (budgets, caps, prerequisites) lives in `engine/validate.py`, which takes the
  `RuleSet`. The models deliberately do **not** import the rules.
- Dependency direction: `ui → engine → models`. `rules_db` and persistence sit at
  the edges. Nothing flows back inward.
- Does not currently exist, but when the UI is being engineered put any UI assets in `assets/`.

## Layout
This is the TARGET structure. See **Status** for what exists today.
```
Exalted-1E-Charsheet-Generator/      (project root)
  CLAUDE.md            this file
  conftest.py          pytest import shim (makes the package importable)
  pyproject.toml       dependencies + pytest config
  .gitignore           ignores sources/, __pycache__/, .venv/, *.pyc
  exalted_builder/     the package
    __init__.py
    models/            rules.py, character.py   (pydantic; import nothing game-specific)
    rules_db.py        loads data/*.json -> RuleSet; indexes by id; link-checks
                       prerequisites and spell-circle access
    engine/            derive.py, validate.py, costs.py   PURE: (RuleSet, Character) -> result
    persistence.py     load/save a Character to/from JSON
    ui/                thin frontend; no game logic
    data/              rules data as JSON (see below)
  assets/              assets for web ui
  tests/               pytest; fixtures of known-good AND known-illegal characters
  sources/             rulebook PDFs — GITIGNORED, never committed
  images/              rulebook images — GITIGNORED, where any requested images from the rulebook will go
```

## Data conventions
- **Schemas live in code, not in this file.** The authoritative shapes are the
  pydantic models in `exalted_builder/models/` (`rules.py`, `character.py`) — read
  them for field-level truth; never duplicate or infer them. For the concrete JSON
  a data file should produce, copy a working example: `data/armor.json` for armor,
  `data/charm.example.json` for charms.
- Rules data is JSON under `data/`. Charms are split per ability/splat in
  `data/charms/*.json`.
- Stable string ids (e.g. `solar.melee.fire-and-stones-strike`). Reference by id,
  never by name.
- Charm prerequisites are **AND-of-OR**: `list[list[str]]`. Every inner group must
  be satisfied; a group is satisfied by any one of its ids. A flat list of
  single-id groups is the common "all required" case.
- Equipment is stored as an **inline copy** on the character (artifacts and
  customization vary per character); the catalog in the RuleSet is an autofill
  source, not a hard reference. Charms and spells, which never vary, ARE
  referenced by id — the distinction is intentional.
- `rules_db.load_ruleset` accumulates every data error and raises them together,
  so the data set is fixed in one pass. Optional cost/budget tables fall back to
  the model defaults when absent.

## Decisions already made (do not relitigate without reason)
- **Current state is canonical and editable.** The engine *computes* the point
  accounting; the user does not hand-tag each dot's currency.
- **Chargen and advancement are different shapes.** Chargen is a constraint
  snapshot validated against the budgets; `lock_chargen()` freezes it. Post-lock
  changes are an append-only XP log the engine reconciles against the snapshot.
- `lock_chargen()` must compute and store `wp_virtue_component` (the two highest
  Virtues at lock). This is the mechanism by which post-creation Virtue gains do
  not raise Willpower.
- **Play-state is a SEPARATE, validation-isolated layer.** It was originally out
  of scope; the user has since added an in-play tracker (the Play tab): marked
  health damage, motes spent, temporary Willpower, and Limit. It lives on
  `Character.play` (`PlayState`, optional → old saves load with it `None`) and is a
  deliberately dumb manual tracker — no auto mote-accounting, no damage-wrapping, no
  auto-healing. The hard rule survives: **play-state must NOT enter chargen validation,
  the XP audit, or the permanent-value derivations.** Capacities only flow OUT of the
  engine (health track, Essence pools, permanent WP) into the tracker; nothing flows
  back. Still out of scope: Virtue channels and the Resources purchase transaction.

## Stack
- Python + pydantic v2 + pytest.
- Frontend: **NiceGUI** (chosen over Reflex). Installed as the optional `[ui]`
  extra. A JS graph library (Cytoscape/d3) is still planned ONLY for the
  charm-tree picker. Run the venv as `.venv/`; tests: `.venv/bin/python -m pytest`.
- **Git remote:** `origin` → `github.com/x6568tank/exalted-1e-charsheet-generator`,
  tracking `main`. Note that `images/` and `sources/` are gitignored and therefore
  do NOT travel with a clone — they are the only authoritative source of game
  values, so authoring new rules data on a second machine needs those PNGs synced
  out-of-band.

## Workflow expectations
- **Test-first on the engine.** That's where bugs hide.
- **The human is the rules authority.** 1e has ambiguous and errata'd corners
  (Combo legality, the specialty cap, Charm interactions). Flag them and ask; do
  not silently choose an interpretation.
- **Game data comes from the page, never from your own knowledge.** Any concrete value — a cost, minimum, prerequisite, rating, or rules detail — that you write into `data/` or code must come from a page image the human gave you, or from an existing `data/` file. Do not supply one from your own knowledge of Exalted even when you are confident — 2e values will feel right and be wrong for 1e. If you need a value and have no page for it, stop and ask for a PNG. Never choose an interpretation, invent a number, or read the PDFs in `sources/` yourself. PNGs will be dropped in `images/`.
- Don't leak game logic into the UI. Don't re-derive what the engine already
  computes. Don't hardcode the cost tables — they live in `data/`.

## Status (497 tests passing)

### Models, loader, persistence — done
`models/rules.py`, `models/character.py`, `rules_db.py`, `persistence.py`.
Persistence is atomic JSON load/save (tempfile + `os.replace`, shared by
`save_character`/`save_party`), enum-keyed dicts, and deployment-aware filenames
(`slugify_name`/`suggested_filename`; `default_save_dir` sits next to the
executable when frozen so a double-clicked build doesn't write into its temp
extraction dir). `character_to_json`/`_from_json` and their `party_*` mirrors are
the in-memory (de)serialisers the browser upload/download path reuses.

### Engine
- `derive.py` — Willpower; per-splat Essence pools via `RuleSet.exalts`/`exalt_for`
  (essence coefficients + an optional Breeding-Background term for Dragon-Blooded);
  health track; per-type soak (bashing/lethal/aggravated, core pp.231-232).
- `validate.py`:
  - Reference integrity; Charm prereqs (AND-of-OR + min ability/essence);
    `meets_charm_requirements`/`charms_depending_on` (picker eligibility + safe removal).
  - **Eclipse generalist rule (core p.127, `images/Solar/Traits/126-127.png`):**
    "Provided they have a willing tutor, they may learn the Charms of other types
    of Exalted... Such Charms cost double the normal experience to learn (usually
    20 points) and use. Eclipse Caste characters may not start the game knowing
    the Charms of other such beings without Storyteller permission." Modeled as
    DATA, not a caste check in code: `CasteDefinition.foreign_charms` +
    `foreign_charm_xp_multiplier` (2), set on `eclipse` only so far. The chargen
    permission is `Character.st_foreign_charms`; post-lock it falls away (a willing
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
- `advancement.py` — post-lock XP transitions: `raise_attribute/ability/virtue/
  willpower/essence`, `learn_charm/spell/craft/ox_body`, `add_combo/specialty` —
  each priced, legality-checked, applied, and logged as an append-only `XpEntry`;
  `undo_last` reverses LIFO; `validate_xp` audits overspend/tampering. `lower_*`
  (curses / Charm costs) reduce a permanent trait OUTSIDE the XP economy at cost 0
  — Willpower's purchased component can go net-negative, so a curse can drop
  Willpower below the Virtue floor.

### UI (NiceGUI)
File map: `ui/view.py` (pure, toolkit-free presenter), `ui/app.py` (read-only
sheet), `ui/editor.py` (chargen editor), `ui/picker.py` (Cytoscape charm/spell
picker), `ui/combos.py` (Combo builder), `ui/xp.py` (post-lock XP tab),
`ui/play.py` (in-play tracker), `ui/builder.py` (unified tabbed app), `ui/gm.py`
(party page). Run: `.venv/bin/python -m exalted_builder.ui.builder [char.json]
[--show] [--port N] [--native]`. Example char: `examples/ashes-of-dawn.character.json`.

- **Picker has three pages** — Abilities / Martial Arts / Spells (a toggle
  omitted when a splat has none of one kind). Martial Arts holds every
  `martial_arts:*` style category. Spells has a Circle dropdown offering every 
  circle the character can reach across BOTH tracks, one full-width row per spell 
  (add/remove/locked, cost, description, lock reason).
- **Splat dropdown on the Charms tab (Eclipse generalist rule).** Rendered only for
  a caste with `foreign_charms`, and only on the two Charm-tree pages (spells are
  gated by circle, the Form Library is the character's own). Beside it, pre-lock
  only, an "ST permission" checkbox bound to `Character.st_foreign_charms` —
  without it the dropdown has one option and hides itself. `view.charm_on_splat_page`
  is the filter: `""`/own splat is EXACTLY `charm_matches_splat` (so every existing
  splat's picker is byte-identical), and a foreign page is that splat's own Charms
  minus anything already native, so a Celestial's Hungry Ghost Style doesn't appear
  twice. Category names collide across splats ("melee" belongs to three), so
  `build_charm_graph` now takes `(category, splat)` — the pair identifies a tree, the
  category alone does not. The detail card labels a foreign Charm and its doubled
  price. **Not yet clicked through in a browser.**
- **Form Library page (Lunar).** A fourth group on the Charms tab's toggle, beside
  Abilities / Martial Arts / Spells: the character's Totem plus every animal shape
  they have taken. Deliberately FREE — narrative bookkeeping the Storyteller
  adjudicates, so `Character.totem` / `Character.animal_forms` (`AnimalForm`) carry
  no cost, no cap and no reference into the RuleSet, and never enter chargen
  validation, the XP audit or any derivation. Same isolation as play-state, for the
  same reason. Gated on `ExaltDefinition.form_library` (data, not a splat check), so
  a later shapeshifting splat opts in without a code change.
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
- **Gotcha:** NiceGUI 3.x's `ui.select` raises `ValueError` if constructed with a
  `value` not in its `options`. Any select whose value can be a free-text/custom
  entry must fold that value into `options` first (`editor._opts_with`) —
  otherwise a custom name renders once, then 500s on the next reload.

### Data authored
- Core: `castes.json`, `backgrounds.json`, `armor.json`, `weapons.json`,
  `spells.json` (43, across both sorcery and necromancy circles), `natures.json`
  (16 Archetypes), `materials.json` (5 magical materials, Exalt-gated weapon/armor
  bonuses, p341/p345-346).
- Charms — **all three implemented splats have a complete catalogue:**
  - **Solar:** 220 corebook charms across every ability.
  - **Dragon-Blooded:** 231 charms — 164 per-element (Air/Earth/Fire/Water/Wood)
    ability-tree charms, 59 Immaculate style-tree charms, 8 Five-Dragon Style,
    Ox-Body.
  - **Abyssal:** 233 charms across every ability, incl. Hungry Ghost Style,
    sorcery + necromancy initiations, Ox-Body.
- **Cross-splat Martial Arts:** Hungry Ghost Style and Five-Dragon Style are
  `open_to_tiers: [Celestial]` — ready for Lunar/Sidereal with zero data change
  once those splats exist.

### Lunar — chargen, full Charm catalogue, Combos, Gifts done (started 2026-07-22)
Read from `images/Lunar/Character Creation 88-93`, `Traits 96-115`, and
`Charms 118-193` (core "The Lunars" splatbook). Chargen foundation, Attribute-
keyed Charm machinery, every Charm in the Charms chapter (p.118-193, including
Deadly Beastman Transformation's Gifts), the p.122 Combo mixing rule, and a
picker/view bugfix that only surfaced once real Lunar data existed are all
authored and tested (466 tests). **Not yet done:** a human has not clicked
through the picker UI in a browser — see the caveats on the Gift-picker widget
below, which is the least-exercised piece of this whole batch.

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
  4/3), `costs_xp.json` (**new file** — previously unauthored for any splat) with
  a Lunar row (Charm XP 12/15, p.122 — a third distinct rate alongside Solar's
  10/8 and Dragon-Blooded's un-costed default), 4 new Nature archetypes (Savant/
  Survivor/Thrillseeker/Visionary, p.91 — Lunars' list is Solar's 16 plus these),
  and 2 new Backgrounds (Heart's Blood, Renown — both Lunar-only via `exalt_type`).
  Editor's `_SPLAT_ORIGINS` gained a `"Lunar"` entry (Society/Casteless) so the
  origin is reachable in the UI; the Caste dropdown does NOT yet auto-sync with
  it, so picking one without the other trips the new consistency check.
- **Magic-track ceiling (rules-authority confirmed, 2026-07-22):** Lunars and
  Sidereals, as Celestial Exalted (not native sorcerers or necromancers, unlike
  Solar/Abyssal), reach **sorcery up to Celestial Circle** and **necromancy up
  to Shadowlands Circle** only. `exalts.json`'s Lunar row sets
  `highest_magic_circle_id: "Celestial"` — two circles below the bar
  (Terrestrial, Celestial), so barring the top one still leaves chargen sorcery
  reachable, the same shape as Solar's own bar. The Shadowlands-only necromancy
  cap has no separate field to set (see Solar's Shadowlands/Labyrinth necromancy
  access above, p.223) — it's enforced purely by NOT authoring a Labyrinth or
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

### Removed
- **Merits & Flaws** — ripped out 2026-06-15 (the old system bundled
  balance-wrecking Charm rewrites). See **Next Exalt Types** above for the
  planned centralized re-add; until then, do not reintroduce the old per-file hooks.

### Deferred / permanently out of scope
- `chargen_budgets.json`/`costs_bonus.json`/`costs_xp.json` overrides beyond
  what's authored — optional, loader falls back to model defaults.
- A per-session XP-grant ledger and the "training time" rule
  (`XpEntry.training_complete` is a dormant hook); state-reconciliation of
  hand-edited current-vs-snapshot drift (the read-only lock guards normal use).
- **Combat/attack derivation is OUT OF SCOPE, not deferred (user decision,
  2026-07-22)** — weapons stay display-only; no attack-roll engine, no Dire
  Lance mounted profile. Do not build this without the user reopening it.

## TODO
**Done:** M&F removal, repeatable Ox-Body, Nature dropdown, Caste info box,
editable custom weapons/armor, magical materials, Craft as per-focus Abilities,
chargen BP-spend log, free background/equipment editing on the XP tab, the
in-play tracker, the multi-splat engine (P0-P4) plus full Dragon-Blooded and
Abyssal data catalogues, tier-gated cross-splat Martial Arts, the picker's
three-page Abilities/Martial Arts/Spells split, GM mode.

**Next:**
- **Abyssal Moonshadow's half of the Eclipse generalist rule.** The engine, pricing
  and Splat dropdown are all data-driven off `CasteDefinition.foreign_charms`, so
  this is a one-line change to the `moonshadow` row of `castes.json` — but the page
  image has not landed yet (the human is dropping it in `images/Abyssal/`). Author it
  from that page, not from the Eclipse text: confirm the multiplier and the chargen
  permission clause actually read the same before copying them across.
- **Refactor: one canonical Charm-pick enumeration.** A repeatable Charm lives on
  its own `Character` list (`ox_body`, `beastman_gifts`), NOT in `character.charms`,
  so every consumer that walks `character.charms` has to special-case each of them —
  and four separately did not when Gifts landed (2026-07-22): the sheet's Charm rows
  and the XP-log label in `ui/view.py`, and the chargen Charm-pick counters in
  `ui/picker.py` and `ui/editor.py`. All four are fixed and pinned by tests, but the
  shape guarantees a fifth miss the moment a splat adds a third repeatable Charm.
  Fix: an engine-side enumeration (e.g. `charm_picks(ruleset, character)`) yielding
  every pick — plain Charms plus one entry per repeatable purchase, already labelled
  — that the sheet, both counters, and the XP log all consume, so the UI never
  enumerates these lists itself. `engine.validate.bonus_point_breakdown` already
  builds this list internally to price picks; that is the model to extract.
  **Refactor of working code — no behaviour change intended.**
- **Sidereal, Lunar, and Alchemical** Exalt types, then **Mortals** — see
  **Next Exalt Types** above for the color scheme and the M&F-return plan. No
  build order chosen yet; ask the user before starting.
- **Windows .exe** — needs building on an actual Windows host (PyInstaller
  can't cross-compile); same spec as `linux.sh`/`windows.bat`.

Full multi-splat plan: `~/.claude/plans/should-we-plan-out-encapsulated-crab.md`.
DB chargen numbers as verified from source pages: [[db-chargen-findings]].
