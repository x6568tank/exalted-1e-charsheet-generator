# Exalted 1E Character Builder — Project Guide

## What this is
A character creator / validator for **Exalted First Edition (1e)** — character
generation, point validation, and XP advancement, with a character-sheet view.
Scope is deliberately smaller than EdExalted (which is 2e/2.5e only); **1e is
unserved, which is the entire point of building this.** Initial target was
**Solar** Exalted from the core rulebook; **Dragon-Blooded, Abyssal, Lunar,
Sidereal and Alchemical are now also fully supported.** **Mortals** are the only
splat left — see **Next Exalt Types** below.

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
**Every Exalt splat is done.** Dragon-Blooded, Abyssal, Lunar (2026-07-22),
Alchemical (2026-07-23) and Sidereal (2026-07-24) all shipped complete — chargen,
Charms, XP/advancement and UI, each clicked through in a browser. See their Status
entries below for the per-splat detail.

**Mortals** (Godblooded/Ghosts/Heroic Mortals/etc.) are the ONE remaining splat, and
the next piece of splat work. After that comes the centralized Merits & Flaws re-add
(see **Removed**).

Work on a given splat starts only once its rulebook images land in
`images/<ExaltName>/` — never author data from memory, per the Workflow rule below.

**Splat color scheme (UI theming):**

| Splat | Color | Status |
|---|---|---|
| Solar | Amber/Gold (default) | DONE |
| Abyssal | Black on ash | DONE |
| Dragon-Blooded | Vermillion | DONE |
| Lunar | Moonsilver blue (`slate`) | DONE (chargen, full Charm catalogue, Combos, Gifts, Form Library; UI clicked through 2026-07-22) |
| Sidereal | Purple | DONE (shipped 2026-07-24): chargen + Colleges + 193-Charm catalogue + SMA cost/cap wiring + UI click-through |
| Alchemical | Brass | DONE (shipped 2026-07-23): chargen + Charm Slots + Arrays + Submodules + CH3 catalogue (121 Charms) + CH4 weaving (38 protocols) + XP/advancement (slot economy, retainer Panoply, per-circle protocols, Eclipse crossover) + Clarity + Backgrounds + brass theme + full UI (favored-Attribute panel, Charm-Slot budgets, weaving Spells page, Arrays tab, Submodules panel, Vat Refit, Clarity tracker); UI clicked through 2026-07-23 |
| Mortals | Muddy brown | NOT STARTED — the only row left; blocked on source images |

**Merits & Flaws return once Mortals lands** — the last row above, and the last splat.
It comes back as a single centralized M&F calculation function, specifically so
mechanical effects don't get scattered invasively across files the way the old
implementation did. Until that milestone the removal in Status stands: do not
reintroduce the old per-file hooks.

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
    engine/            derive.py, validate.py, costs.py, refit.py   PURE: (RuleSet, Character) -> result
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
- **Backgrounds are soft free text** — `BackgroundEntry.name` is a name, not an id,
  and the catalog is an autofill source, never a hard reference. ONE exception, added
  for the Alchemical: `ChargenBudgets.background_rules` attaches per-splat chargen
  mechanics (auto-rating, prerequisites, per-dot pool cost, cap exemption) to a
  Background by NAME. Empty for every splat that does not need it.
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
- **Game data comes from the page, never from your own knowledge.** Any concrete value — a cost, minimum, prerequisite, rating, or rules detail — that you write into `data/` or code must come from source material the human gave you, or from an existing `data/` file. Do not supply one from your own knowledge of Exalted even when you are confident — 2e values will feel right and be wrong for 1e. If you need a value and have no source for it, stop and ask. Never choose an interpretation, invent a number, or read the PDFs in `sources/` yourself.
- **Source material lives in `images/<Splat>/` and is human-vetted.** Two forms, both authoritative: **PNG page images** (diagrams — especially Charm-tree boxes-and-arrows — and any page not cleanly copyable), and **pasted `.md` text** the human copies out of a text-selectable book (prose + cost/prereq tables, page-marked with `<!--PAGE n-->`). Pasted text is preferred where it's clean: cheaper (no image rasterization) and exact for numbers, and the copy step is the human's vetting checkpoint. Reading the `sources/` PDFs yourself is still forbidden — the point is the human curates what you see. When pasted text looks column-scrambled or garbled (multi-column PDFs interleave), flag it rather than guess; screenshot the diagram instead.
- Don't leak game logic into the UI. Don't re-derive what the engine already
  computes. Don't hardcode the cost tables — they live in `data/`.

## Status (776 tests passing)

### Models, loader, persistence — done
`models/rules.py`, `models/character.py`, `rules_db.py`, `persistence.py`.
Persistence is atomic JSON load/save (tempfile + `os.replace`, shared by
`save_character`/`save_party`), enum-keyed dicts, and deployment-aware filenames
(`slugify_name`/`suggested_filename`; `default_save_dir` sits next to the
executable when frozen so a double-clicked build doesn't write into its temp
extraction dir). `character_to_json`/`_from_json` and their `party_*` mirrors are
the in-memory (de)serialisers the browser upload/download path reuses.

### Engine
- `derive.py` — Clarity (Alchemical, see below); Willpower; per-splat Essence pools via `RuleSet.exalts`/`exalt_for`
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
  frozen chargen snapshot; see the Alchemical Vat Refit note for why.

### UI (NiceGUI)
File map: `ui/view.py` (pure, toolkit-free presenter), `ui/app.py` (read-only
sheet), `ui/editor.py` (chargen editor), `ui/picker.py` (Cytoscape charm/spell
picker, plus the Alchemical Vat Refit page), `ui/combos.py` (Combo builder — and
the Alchemical Arrays builder, which replaces Combos for a Charm-Slot splat), `ui/xp.py` (post-lock XP tab),
`ui/play.py` (in-play tracker), `ui/builder.py` (unified tabbed app), `ui/gm.py`
(party page). Run: `.venv/bin/python -m exalted_builder.ui.builder [char.json]
[--show] [--port N] [--native]`. Example char: `examples/ashes-of-dawn.character.json`.

- **The picker's group toggle is built from what the splat HAS**, so no character
  sees all of it. The base three are Abilities / Martial Arts / Spells (each omitted
  when the splat has none of that kind); **Form Library** is added for a splat with
  `ExaltDefinition.form_library` (Lunar) and **Vat Refit** for one with Charm Slots or
  a Panoply (Alchemical, plus a crossover Eclipse) — both detailed in their splat's
  section below. Martial Arts holds every `martial_arts:*` style category. Spells has
  a Circle dropdown offering every circle the character can reach across BOTH tracks,
  one full-width row per spell (add/remove/locked, cost, description, lock reason).
  A Charm category may also swap the Cytoscape canvas for its own panel — the
  Alchemical Augmentation pop-ups do, staying an Abilities page while replacing the
  graph.
- **Splat dropdown on the Charms tab (Eclipse generalist rule).** Rendered only for
  a caste with `foreign_charms`, and only on the two Charm-tree pages (spells are
  gated by circle, the Form Library is the character's own). Beside it, pre-lock
  only, an "ST permission" checkbox bound to `Character.st_foreign_charms` —
  without it the dropdown has one option and hides itself. `view.charm_on_splat_page`
  is the filter: `""`/own splat is EXACTLY `charm_matches_splat` (so every existing
  splat's picker is byte-identical), and a foreign page is that splat's own Charms
  minus anything already native, so a Celestial's Hungry Ghost Style doesn't appear
  twice. Category names collide across splats ("melee" belongs to five), so
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

### Data authored
- Core: `castes.json`, `backgrounds.json`, `armor.json` (19), `weapons.json` (79),
  `spells.json` (**88**, across all three magic tracks — 27 sorcery, 23 necromancy,
  38 Alchemical weaving protocols), `natures.json` (20 Archetypes), `materials.json`
  (5 magical materials, Exalt-gated weapon/armor bonuses, p341/p345-346),
  `colleges.json` (25 Sidereal Astrological Colleges), `camps.json` + `callings.json`
  (Cult of the Illuminated), `st_screen.json` (the GM reference screen).
- Charms — **1,378 across six splats; every implemented splat has a complete
  catalogue.** Counts are `Counter(c.exalt_type for c in rs.charms.values())`:
  - **Solar: 381** — 222 corebook across every ability, 20 from Cult of the Illuminated
    (incl. Falling Blossom Style, and the 5 castebook Charms that book reprints) and
    **139 from the five castebooks** (incl. Tiger, Praying Mantis and Ebon Shadow
    Style; see the castebook section below).
  - **Dragon-Blooded: 233** — 164 per-element (Air/Earth/Fire/Water/Wood) ability-tree
    charms, 59 Immaculate style-tree charms, 8 Five-Dragon Style, Ox-Body.
  - **Abyssal: 233** across every ability, incl. Hungry Ghost Style, sorcery +
    necromancy initiations, Ox-Body.
  - **Lunar: 217** — Attribute-keyed, incl. Deadly Beastman Transformation's Gifts.
  - **Sidereal: 193** — 24 ability trees, Violet Bier of Sorrows, and 3 Celestial-open
    Sidereal Martial Arts styles.
  - **Alchemical: 121** — Attribute-keyed, Charm-Slot installed, many with submodules.
- **Cross-splat Martial Arts:** Hungry Ghost Style and Five-Dragon Style are
  `open_to_tiers: [Celestial]`, so every Celestial splat gets them for free — which is
  how Lunars and Sidereals picked them up with no data or code change when those splats
  landed. The mechanism is proven; a future Celestial splat needs nothing.

### Solar castebooks — DONE 2026-07-25
Read from `images/Solars/Castebooks/<Dawn|Eclipse|Night|Twilight|Zenith>/*.png`
(29 page scans). **139 Charms, 7 spells, 30 weapons, 2 armours.** Open items,
source defects and the rules calls are in
`images/Solars/Castebooks/_CASTEBOOK_PENDING.md` — read that before touching this.
Tests: `tests/test_solar_castebooks.py`.
- **The three missing Martial Arts styles are now authored** — the ones
  `data/camps.json`'s Sequestered Tabernacle package has named since the Illuminated
  work: **Tiger** (`martial_arts:tiger`, 9, Dawn p.73-74), **Praying Mantis**
  (`martial_arts:praying-mantis`, 10, Eclipse p.73-75) and **Ebon Shadow**
  (`martial_arts:ebon-shadow`, 11, Night p.67-70), each in its own file per the
  one-file-per-style convention. All three are **Solar-only** (no `open_to_all`/
  `open_to_tiers` — their pages say nothing about other splats, unlike Falling
  Blossom). Eclipse's own heading is "Mantis-Style", but the category key is
  `praying-mantis` because `camps.json` already said so; the key is pinned from BOTH
  sides in the tests, since renaming it would silently empty that grant.
- **Five castebook Charms were already in `data/`** from Cult of the Illuminated,
  which reprints them — Tireless Traveler's Stamina, Excellent Emissary's Tongue,
  Graceful Courtier Attitude, Prey-Freezing Gaze, Game-Snaring Huntsman's Method.
  They were NOT re-authored. **Rules-authority call, 2026-07-25: where the two books
  disagree the ILLUMINATED version wins, in every case** — including Excellent
  Emissary's Tongue, which Illuminated lists as merely "reprinted for ease of
  reference" yet prices differently (4 motes + 1 WP vs the castebook's 3 motes).
  `data/` already held the Illuminated numbers, so nothing changed. Do not
  "correct" them back; the discrepancies are tabulated in `_CASTEBOOK_PENDING.md`.
- **Four new multi-gate Charms** join Ascendant Battle Visage in using
  `extra_min_abilities` (Masterful Training Manual, Impenetrable Identity, Drunken
  Warrior Technique, Inebriated Fool Defense). Same rule as before: the extra is a
  requirement check ONLY and never touches pricing — pinned by a test.
- **Environmental Hazard-Resisting Meditation (Zenith p.72-73) is a SECOND
  repeatable Solar Charm** — 4 resistance variants, cap = Resistance dots, "similar
  to Ox-Body Technique". The DATA is complete (`repeatable_cap_ability`+`variants`);
  the ENGINE is deliberately NOT wired, because a repeatable Charm needs its own
  `Character` list and this would be the fifth list outside `character.charms`.
  Today it is an ordinary one-off pick (legal, priced, gated). The DISPLAY/COUNT half
  of the blocker is gone — `validate.charm_picks` (below) is now the one place a new
  repeatable list has to be taught about. What remains is the storage/pricing half:
  a `Character` list, an `ExaltDefinition` field naming the Charm, cap/variant checks,
  BP/XP, the lock snapshot, undo and a picker panel.
- All seven Twilight spells are authored (p.74-77); p.77 then turns to hearthstones,
  which `note.md` puts out of scope, so the castebooks are complete within it.
- Gear: `notes` carries everything the models have no field for — Strength-relative
  damage, the Siege Crossbow's 1/10 rate, the Flame Spear's `+6/8*` split. Two items
  (Ultimately Useful Tube, Gauntlets of Distant Claws) are two catalog rows each.
  Per the human's `note.md`, hearthstones/Manses/non-gear artifacts were skipped.

### Lunar — DONE (started 2026-07-22)
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
  its XP costs are the Solar default. See [[xp-costs-by-splat]]), 4 new Nature archetypes (Savant/
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

### Sidereal — DONE (started 2026-07-22, shipped 2026-07-24)
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
  Spells page, XP-tab MA pricing) — all fine — and pushed. Next splat is **Mortals**.

### Alchemical — DONE (started and shipped 2026-07-23)
Read from `images/Alchemical/` — pasted text from the Autochthonians book (1e
conventions — WP = two highest Virtues, health 7+Ess; it supersedes *Time of
Tumult*): `CH 2 Character Creation and Traits.md` (p.58-85), `CH 3 Charms.md`
(p.88-193, the Charm mechanics + catalogue), `CH 4 Miracles of the Machine God.md`
(the Alchemical sorcery-analogues / "weaving"). **Done so far: the chargen
foundation AND the Charm Slot system.** Per user decisions 2026-07-23, still to
build in THIS push: **Arrays, Submodules, the full CH3/CH4 Charm catalogue, and
Alchemical XP/advancement** — build order is slot-engine-first (done), then the rest.

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
  Enhancement System). This is the slot-engine test bed — the FULL catalogue
  (CH3 ~4459 lines + CH4 ~1732) is the next grind, Lunar-sized.
- **Confirmed from the mechanics preamble** (resolving earlier provisional calls):
  `tier:"Alchemical"` is RIGHT — p.90 says Eclipse/Moonshadow learn Alchemical
  Charms via the existing 20-XP foreign-charm rule, and MA needs the Perfected
  Lotus Matrix Charm, so nothing should auto-grant Celestial styles. "Non-
  Alchemicals cannot learn weaving Charms" (CH4) → those must be barred from
  foreign learners when authored.
- **New subsystems still to model (user chose "both now"):** **Arrays** (Alchemical
  Combos — 1 BP/Charm or XP = Σ min-Attributes; reduce install cost to ¾; integrated
  Combos; Attribute-Charms only) and **Submodules** (per-Charm XP upgrades, post-lock).
- **Original chargen-foundation notes (still current):**
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
    rules replace the per-pick caste/favored minimum for Alchemical (see the Charm
    Slot system entry above), so this stays 0 on purpose.
- **Backgrounds — DONE 2026-07-23 (CH2 p.65-69). The FIRST Backgrounds in this
  project with real mechanics.** Backgrounds are soft everywhere else — free text,
  an autofill catalog, never hard-validated (see **Data conventions**) — and the
  Alchemical book is the first to give them chargen rules. Modelled as a narrow,
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
  dup, minima met. Real datum: Polymodal Joint Bearings' omnidextrous submodule
  (the 22nd starter Charm).
- **The rest of the push, all since completed** (kept as the build record — every
  item below is DONE; the sub-bullets say when and how):
  - **`costs_xp.json` + Alchemical advancement (post-lock).** Slot-based: new Slots
    12/10, upgrade Dedicated→General 2, Weaving Protocols 12/14, MA 11 (Perfected
    Lotus Matrix gate), retainer Charm 6, Essence ×9. ALSO needs a new
    `ExperienceCosts.attribute_favored_caste` field for the (rating×4)−1 Caste/
    Favored-Attribute XP discount (model doesn't have it yet). Don't half-author —
    the missing discount would silently over-charge, the invisible-bug class the
    Lunar charm-discount fix warned about.
  - The full **CH3** Charm catalogue is DONE: **121 Alchemical Charms** across all
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
    "44 = 32+12" the earlier plan estimated: that count was a line-range guess whose
    Man-Machine range swept in the 6 summoned-golem stat blocks and their 12 innate
    Charms (which are the golems' abilities, not protocols). Modeled exactly as the
    agreed plan (protocols as `Spell`s): (1) `SpellCircle.MAN_MACHINE`/`.GOD_MACHINE`
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
    **Foreign-learner bar — the plan's stated auto-bar had a hole, now closed.** The
    plan claimed `accessible_circles` (which asks `charm_matches_splat`) blocks a
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
    now do (see the Lunar section).
  - **XP / advancement — DONE 2026-07-23** (verified against the CH2 p.64 EXPERIENCE
    COSTS table — the real numbers, not the plan's paraphrase). Trait costs:
    `ExperienceCosts.attribute_favored_caste` = (rating×4)−1 (new field, model default,
    inert for category-mode splats whose caste-favored attribute SET is empty), Essence
    ×9 (`costs_xp.json` Alchemical row). **Charm-Slot economy** (user chose "build
    retainer now too", 2026-07-23): new `Character.retainer_charms` (the Panoply —
    OWNED-but-not-installed Charms, kept OUT of `charms` which the Slot rules count);
    `advancement.buy_charm_slot(dedicated=…, charm_id=…)` (General 12 / Dedicated 10,
    installs the bundled free Charm, Dedicated requires
    `validate.charm_fits_dedicated_slot`), `upgrade_charm_slot` (Dedicated→General, 2),
    `learn_retainer_charm` (flat 6, no Slot). Per-circle protocol XP via new
    `ExperienceCosts.spell_cost_by_circle` (`{Man-Machine:12, God-Machine:14}`; wins
    over the flat rate and ignores the Occult discount) — `spell_cost` now takes the
    spell. `learn_charm` now RAISES for a `uses_charm_slots` splat (routes to the Slot/
    Panoply calls) so a Slot is never silently skipped — the exact silent-undercharge
    the "don't half-author" warning is about. Undo + `_expected_cost` audit cover every
    new domain (`charm_slots.general/dedicated`, `charm_slot_upgrade`,
    `retainer_charms`). Tests: `tests/test_alchemical.py` XP section.
    **Martial Arts via Perfected Lotus Matrix — DONE 2026-07-23** (CH3 p.100). PLM
    installed lets an Alchemical learn Terrestrial/Celestial MA Charms "as any Celestial
    Exalt": `validate.charm_matches_splat` now grants a `Celestial`-tier MA style when
    `has_perfected_lotus_matrix` (PLM id in `charms`); `advancement.learn_martial_arts_
    charm` costs the flat 11 (`new_martial_arts_charm`); the Charm is stored IN the
    Matrix, so `validate.charm_occupies_slot` returns False for it and the Slot count
    skips it (it still lives in `charms`, so its style-tree prereqs resolve normally).
    Remove PLM → `charm_matches_splat` stops granting the style (access revoked, p.100).
    Only Hungry Ghost + Five-Dragon MA data exist today, so those are what an Alchemical
    can currently learn; more styles = pure data. **Ox-Body takes a Slot — DONE
    2026-07-23** (user ruling: every Alchemical Charm occupies a Slot). Each Strain
    Resistant Chassis purchase counts against Slots at chargen (the slot block adds
    `len(ox_body)` + its install motes) and, post-lock, `learn_ox_body(..., dedicated=)`
    costs a Slot (12/10) and raises the Slot count for a `uses_charm_slots` splat (flat
    new-charm rate still applies to Solar/DB/Abyssal/Lunar Ox-Body). New undo/audit
    domains `ox_body_slot.*` and `martial_arts`.
    **Eclipse/Moonshadow ↔ Alchemical crossover — DONE 2026-07-23** (p.90). A
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
    **Vat refit — DONE 2026-07-23.** See the UI pass entry below.
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
  - **UI pass — DONE 2026-07-23.** Done: `theme._ALCHEMICAL` (brass, `fam="yellow"`,
    accent `#a8792c` — a true warm brass; the first attempt `#9a7b1f` read too olive
    and the user flagged it, so do not revert toward yellow-green); a legal example
    (`examples/gearheart.character.json`, Orichalcum, fills all 8 Slots); the editor
    Attribute panel now handles caste_favored mode (`view.uses_caste_favored_attributes`/
    `attribute_budget_summary` — a Favored-Attributes multi-select, ● Caste / ✦ Favored
    marks, the set-based "Caste 9 (min 2 each) · Favored 6 · Other 4" header, and the
    Favored-Abilities picker hides itself when `favored_count==0`); the picker + editor
    Charm readouts show Slot occupancy for slot-splats (`view.charm_slot_budget` →
    `SlotBudget`, backed by the new engine `validate.charm_slot_usage`, which the chargen
    Slot check now also consumes so they can't disagree); the weaving Spells page works
    for free (accessible_circles surfaces Man-/God-Machine) with the track labelled
    "Weaving Protocols" and per-circle pricing (12/14, `spell_cost` now takes the spell).
    Alchemical has no origin sub-types, so `_SPLAT_ORIGINS` needs no entry.
    **Augmentation grouping (user request 2026-07-23):** the 18 "Transitory/Sustained
    Augmentation of (Attribute)" Charms STAY 18 distinct ids in the data — 82 other
    Charms name a SPECIFIC one as a prerequisite, so a literal merge to 2 Charms would
    break all of them (confirmed: `grep augmentation-of- ... | wc` = 82). Instead the
    picker COLLAPSES the Alchemical `general` category from an 18-node Cytoscape graph
    into two per-type pop-up cards (Transitory / Sustained), each opening a DBT-style
    dialog with a checkbox per Attribute that installs/removes that specific id.
    Presenters: `view.augmentation_category` (the category is detected by "all its
    Charms are '<Type> Augmentation of <Attr>'", data-driven, not hardcoded) +
    `build_augmentation_view` → `AugmentGroup`/`AugmentEntry`. Picker: `_is_augment_page`
    swaps the canvas for `augment_panel` (the category dropdown STAYS so you can leave;
    `init_graph`/`update_graph` no-op there); `toggle_augment` is an immediate pre-lock
    add/remove with the usual `charms_depending_on` removal guard. In-play buying still
    routes through the (unbuilt) post-lock Slot flow — the dialog is pre-lock only.
    **Arrays tab — DONE 2026-07-23.** A Charm-Slot splat builds Arrays INSTEAD of
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
    **Submodules — DONE 2026-07-23.** A SUBMODULES section on the picker's sticky
    detail card, on the Charm they upgrade (not a catalogue page — they are per-Charm).
    Shows the dual price (BP pre-lock, XP post-lock), the submodule's own minima, owned
    state, and the block reason. `validate.submodule_block_reason`/`owns_submodule` are
    the single eligibility source (same gates `validate_submodules` and
    `advancement.learn_submodule` apply); presenter `view.build_submodule_rows` →
    `SubmoduleRow`. Renders nothing for the ~112 Charms with no submodules.
    **Vat Refit — DONE 2026-07-23.** A "Vat Refit" group on the Charms tab toggle,
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
    Curse, so they have no Limit at all. Modelled as a **split**, per the user's call:
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
      project until the centralized re-add (see **Removed**). Revisit it with M&F, not
      before.
    **Weaving Engines can never be uninstalled** (CH3 p.141: "she cannot ever remove
    the Man-Machine Weaving Engine"). New `Charm.permanent_install` (True on both
    engines) which `refit.uninstall_block_reason` refuses — a flag, not an id check, so
    another such Charm is pure data.

    **Rules-authority call, CONFIRMED 2026-07-23 — do not relitigate:** moving a Charm
    to the Panoply leaves its *dependents* installed. `refit.uninstall` deliberately
    does NOT cascade or block the way the pre-lock picker's `charms_depending_on` guard
    does, because a Panoply Charm is still OWNED — a prerequisite must be owned, not
    worn. (The pre-lock guard is a different case: there the Charm is being *unlearned*.)

### Solar alternate origin — Cult of the Illuminated (DONE 2026-07-24)
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
  "one canonical Charm-pick enumeration" refactor in the TODO is now overdue.
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

### Tooling
- **`tools/validate_charms.py`** — lints Charm JSON before it reaches the RuleSet:
  schema, the id-hyphen/category-underscore convention, AND-of-OR prereq shape,
  cross-file prereq resolution, orphan/cycle trees, cost/duration spillover, OCR
  ligature damage, `extra_min_abilities` nesting, and a **2e-terminology blocklist that
  ERRORS** (MDV, DV, Intimacies, "War Ability", 2e pool notation) — then hands the set
  to `load_ruleset`. `--splat <name>` scopes it; it reads every file for prereq
  resolution but only reports on the targeted ones. Found two real bugs on existing
  data the day it was written.
- **`tools/CHARM_AUTHORING_SPEC.md`** — the verbatim brief for a delegated transcriber.
  Load-bearing parts: never invent a missing value (report it), `min_attribute` NAMES /
  `min_ability` RATES, a comma on the page means AND not OR, `extra_min_abilities` for
  a multi-gate Charm, and a do-not-touch list of the splat-specific fields.
  **Delegation is worth it at Lunar/Alchemical scale (120+ Charms, self-contained
  trees), not at 20** — a cold agent lacks the existing catalogue and will guess
  prerequisite ids, which costs more to check than to author.

### Removed
- **Merits & Flaws** — ripped out 2026-06-15 (the old system bundled
  balance-wrecking Charm rewrites). Back in scope, scheduled AFTER Mortals as one
  centralized `merits_and_flaws_calc` (see **Next Exalt Types**); until that work
  starts, do not reintroduce the old per-file hooks.

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
in-play tracker, the multi-splat engine (P0-P4), tier-gated cross-splat Martial Arts,
the picker's three-page Abilities/Martial Arts/Spells split, GM mode + the ST
reference screen, **all five non-Solar Exalt splats** (Dragon-Blooded, Abyssal, Lunar,
Alchemical, Sidereal — data, engine and UI, each browser-verified), the Cult of the
Illuminated Solar origin, and the five Solar castebooks.

**Next:**
- **Abyssal Moonshadow's half of the Eclipse generalist rule.** The engine, pricing
  and Splat dropdown are all data-driven off `CasteDefinition.foreign_charms`, so
  this is a one-line change to the `moonshadow` row of `castes.json` — but the page
  image has not landed yet (the human is dropping it in `images/Abyssal/`). Author it
  from that page, not from the Eclipse text: confirm the multiplier and the chargen
  permission clause actually read the same before copying them across. Also set
  `foreign_panoply_charm_xp: 8` on the `moonshadow` row (the Alchemical-crossover
  Panoply rate, p.90 — it names both castes), so the crossover works for Moonshadows too.
- **Refactor: one canonical Charm-pick enumeration — DISPLAY HALF DONE 2026-07-25,
  pricing half still open.** A repeatable Charm lives on its own `Character` list
  (`ox_body`, `beastman_gifts`), and granted Charms on a third, NOT in
  `character.charms` — so every consumer that walked `character.charms` had to
  special-case each list, and four separately did not when Gifts landed (2026-07-22).
  **Done:** `engine.validate.charm_picks(ruleset, character)` → `list[CharmPick]`
  (`charm_id`/`name`/`label`/`category`/`source`/`counts_toward_pool`), plus
  `charm_pick_count`. Repeatable purchases arrive one entry each, already labelled with
  their variant(s); granted Charms are listed but `counts_toward_pool=False`. The
  sheet's Charm rows (`view.build_sheet_view`) and BOTH chargen counters
  (`ui/picker.py`, `ui/editor.py`) now consume it and no longer enumerate the lists
  themselves. No behaviour change — `tests/test_charm_picks.py` pins row order, the
  counts and the free-granted rule. **Still open:** `bonus_point_breakdown` builds its
  own pick list to PRICE picks, and that arithmetic (Caste/Favoured × Calling ×
  Martial Arts × Immaculate rates) was deliberately left alone — extracting it is the
  larger, riskier half. The XP-log label in `view.py` is keyed by XP *domain*, a
  different axis, and is also untouched. A new repeatable Charm therefore still needs
  its own storage/pricing wiring; only the display/count side is now free. The
  concrete case waiting on it: Environmental Hazard-Resisting Meditation (Caste Book:
  Zenith p.72-73).
- **Mortals** — the LAST splat (Godblooded / Ghosts / Heroic Mortals / …). Blocked on
  source images landing in `images/Mortals/`, per the never-author-from-memory rule.
  See **Next Exalt Types** above for the colour scheme.
- **Merits & Flaws**, after Mortals — one centralized `merits_and_flaws_calc`, NOT the
  old per-file hooks. See **Removed**.
- **Windows .exe** — needs building on an actual Windows host (PyInstaller
  can't cross-compile); same spec as `linux.sh`/`windows.bat`.

Full multi-splat plan: `~/.claude/plans/should-we-plan-out-encapsulated-crab.md`.
DB chargen numbers as verified from source pages: [[db-chargen-findings]].
