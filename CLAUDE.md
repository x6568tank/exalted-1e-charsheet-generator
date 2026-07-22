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
Dragon-Blooded and Abyssal are done (see Status). **Sidereal, Lunar, and
Alchemical are next** — no build order or plan has been chosen yet as of
2026-07-22; ask the user before starting one. **Mortals** (Godblooded/Ghosts/
Heroic Mortals/etc.) are planned after the Exalt types.

Work on a given splat starts only once its rulebook images land in
`images/<ExaltName>/` — never author data from memory, per the Workflow rule below.

**Splat color scheme (UI theming):**

| Splat | Color | Status |
|---|---|---|
| Solar | Amber/Gold (default) | DONE |
| Abyssal | Black on ash | DONE |
| Dragon-Blooded | Vermillion | DONE |
| Lunar | Silverish-blue | waiting on Lunar chargen work |
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

## Status (377 tests passing)

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
    ability (Endurance); each purchase picks ONE health-level-package variant;
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
- **Sidereal, Lunar, and Alchemical** Exalt types, then **Mortals** — see
  **Next Exalt Types** above for the color scheme and the M&F-return plan. No
  build order chosen yet; ask the user before starting.
- **Windows .exe** — needs building on an actual Windows host (PyInstaller
  can't cross-compile); same spec as `linux.sh`/`windows.bat`.

Full multi-splat plan: `~/.claude/plans/should-we-plan-out-encapsulated-crab.md`.
DB chargen numbers as verified from source pages: [[db-chargen-findings]].
