# Exalted 1E Character Builder — Project Guide

## What this is
A character creator / validator for **Exalted First Edition (1e)** — character
generation, point validation, and XP advancement, with a character-sheet view.
Scope is deliberately smaller than EdExalted (which is 2e/2.5e only); **1e is
unserved, which is the entire point of building this.** Initial target: **Solar**
Exalted from the core rulebook. Other Exalt types come later.

## ⚠️ EDITION: 1e ONLY — never substitute 2e/2.5e rules
This is the single most important constraint. 2e is far better represented than
1e in training data, so the default failure mode is silently "correcting" a 1e
value to its 2e equivalent. **Do not.** Treat the `data/` files and this document
as ground truth. If a rule isn't covered here or in the data, ASK — do not fill
the gap with a 2e value.

1e-distinct values that must NOT drift to 2e:
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
- **Play-state is out of scope:** current motes/Willpower, marked health damage,
  Virtue channels, Limit accrual, and the Resources purchase transaction. The
  builder stores permanent values only. If ever added, it is a separate layer and
  must not enter chargen validation.

## Stack
- Python + pydantic v2 + pytest.
- Frontend: **NiceGUI** (chosen over Reflex). Installed as the optional `[ui]`
  extra. A JS graph library (Cytoscape/d3) is still planned ONLY for the
  charm-tree picker. Run the venv as `.venv/`; tests: `.venv/bin/python -m pytest`.

## Workflow expectations
- **Test-first on the engine.** That's where bugs hide.
- **The human is the rules authority.** 1e has ambiguous and errata'd corners
  (Combo legality, the specialty cap, Charm interactions). Flag them and ask; do
  not silently choose an interpretation.
- **Game data comes from the page, never from your own knowledge.** Any concrete value — a cost, minimum, prerequisite, rating, or rules detail — that you write into `data/` or code must come from a page image the human gave you, or from an existing `data/` file. Do not supply one from your own knowledge of Exalted even when you are confident — 2e values will feel right and be wrong for 1e. If you need a value and have no page for it, stop and ask for a PNG. Never choose an interpretation, invent a number, or read the PDFs in `sources/` yourself. PNGs will be dropped in `images/`.
- Don't leak game logic into the UI. Don't re-derive what the engine already
  computes. Don't hardcode the cost tables — they live in `data/`.

## Status (173 tests passing)
- **Models + loader:** `models/rules.py`, `models/character.py`, `rules_db.py` — done.
- **Engine (done, test-first):**
  - `engine/derive.py` — Willpower, Solar Essence pools, health track, and per-type
    soak (bashing/lethal/aggravated, core pp.231-232).
  - `engine/validate.py` — reference integrity, Charm prereqs (AND-of-OR + min
    ability/essence), `meets_charm_requirements`/`charms_depending_on` (picker
    eligibility + safe-removal), spell-circle access (exact circle; the pp.191
    prereq chain gives higher-grants-lower), and `validate_chargen` (attribute
    8/6/4, ability/background/virtue budgets + pre-bonus caps, caste/favoured
    minimums, charm counts, Willpower start-cap, bonus-point accounting, pp.104-105).
    **Spells at chargen (p.100):** Charms and spells share one pool of 10 — a spell
    takes a Charm pick 1:1, costs the same in BP, gets the discount when Occult is
    Caste/Favoured, and counts toward the ≥5 Caste/Favoured minimum on that basis
    (rules-authority confirmed). Solar Circle spells are barred at creation.
    `meets_spell_requirements`/`granted_sorcery_circles` give picker eligibility.
    **Combos at chargen (pp.213-214):** `validate_combos`/`combo_issues` enforce the
    RAW mechanical rules as hard errors — ≥2 *known* Charms, instant duration only,
    no duplicate Charm, ≤1 Simple, ≤1 Extra Action (ST veto + in-play activation are
    out of scope). `eligible_combo_charms` feeds the picker. Chargen BP cost folds
    into `validate_chargen` as 1 BP per Charm in the Combo.
  - `engine/lifecycle.py` — `lock_chargen` freezes wp_virtue_component + snapshot
    (snapshot now includes `combos`, alongside charms/spells); `unlock_chargen`
    reverses it (drops snapshot + pinned WP component so Willpower re-lives).
  - `engine/costs.py` — pure per-advance XP price from `RuleSet.xp_costs`: scaled
    traits cost `current rating × N` (pay on the rating you leave), new Charm 10/8,
    new spell 10/8 (Occult c/f), new specialty 3, new Combo = Σ member `min_ability`
    (p.213).
  - `engine/advancement.py` — **post-lock XP transitions** (the play-side counterpart
    to lifecycle): `raise_attribute/ability/virtue/willpower/essence`,
    `learn_charm/learn_spell`, `add_combo/add_specialty` — each prices, legality-checks
    (locked, ≤5 dot cap / WP 10, prereqs via validate), applies the trait, and appends
    an append-only `XpEntry`. `undo_last` reverses the most recent row (LIFO, so the
    log and traits never desync). `xp_spent`/`xp_available`/`add_xp`, plus `validate_xp`
    (overspend + per-row cost-tamper audit; `AdvancementError` carries the UI message).
- **Persistence:** `persistence.py` — atomic JSON load/save, enum-keyed dicts.
  Save naming: `slugify_name`/`suggested_filename` name the file after the character
  (`Ashes-of-Dawn` -> `ashes-of-dawn.character.json`); `default_save_dir` is next to
  the executable when frozen (PyInstaller), else CWD — so a double-clicked build
  writes saves beside itself, not into the temp extraction dir. `normalize_save_filename`
  turns free-text Save input into a filename (blank -> character-derived; bare stem ->
  slug + `.character.json`; an explicit `.json` kept). `character_to_json`/`_from_json`
  are the in-memory (de)serialisers the browser upload/download path reuses.
- **UI (NiceGUI):** `ui/view.py` is the pure, toolkit-free presenter (sheet view +
  charm-graph data + `build_spell_picker`). `ui/app.py` read-only sheet,
  `ui/editor.py` chargen editor (live validation), `ui/picker.py` Cytoscape
  charm-tree picker **with a Spells card** that appears under the graph **only on
  the Occult page**, three columns (Terrestrial / Celestial / Solar), circle-gated
  add/remove; it refreshes on every Charm change so learning a Circle Sorcery Charm
  immediately unlocks its spells, and the shared-pool tally shows in the readout.
  `ui/combos.py` is the **Combo builder** (`view.build_combo_view`): assemble named
  Combos from known instant-duration Charms, with per-Combo legality + BP cost.
  `ui/xp.py` is the **post-lock XP tab** (`view.build_xp_log` for the ledger): add XP,
  raise traits / learn Charms-spells / add Combos-specialties at the engine's price,
  with a running spend log and last-first undo; inert until locked. A right-hand
  Details panel (`view.build_charm_detail`/`build_spell_detail`) describes the
  Charm/spell currently selected in the Learn dropdowns.
  `ui/builder.py`
  is the **unified tabbed app** (Edit / Charms / Combos / XP / Sheet, one shared
  Character, with New / Save / Load / Finish & Lock / Unlock). Once locked the chargen
  tabs (Edit/Charms/Combos) go read-only (a notice points to the XP tab or Unlock);
  the XP tab is where advancement happens. It **starts on a
  blank character** (the example is no longer auto-loaded — open it via the path arg
  or Load). **Save/Load are deployment-aware:** the shipped build runs in the **browser**
  (`pack/run_app.py` → `ui.run(show=True)`), where Save prompts for a filename and
  `ui.download.content`s the JSON to the browser's download folder, and Load is an
  `ui.upload` file picker (with a path field as a fallback). A native-window path also
  exists (`--native`, needs pywebview + a Qt/GTK backend): there `_native_window()` is
  truthy and Save/Load use the OS "Save As"/"Open" dialogs via
  `app.native.main_window.create_file_dialog` (`builder._dialog_type` passes the
  picklable `webview.FileDialog` enum — NOT the legacy `SAVE_DIALOG`/`OPEN_DIALOG`
  Proxy objects, which can't cross NiceGUI's multiprocessing queue and silently no-op).
  **Native was dropped from packaging** (bundling Qt → ~280MB and non-portable across
  Linux distros); `--native` remains a dev/optional path only. Run the app:
  `.venv/bin/python -m exalted_builder.ui.builder [char.json] [--show] [--port N] [--native]`
  (the individual modules also run standalone). Example char:
  `examples/ashes-of-dawn.character.json`.
- **Data authored:** `castes.json`, `backgrounds.json` (10 core), `armor.json`
  (mundane + 5 artifact), `weapons.json` (mundane + artifact), `spells.json` (all 3
  circles), `natures.json` (16 — the p105 Archetype summary list), and the Circle
  Sorcery charms (`solar_occult.json`, 3).
- **Charms authored** (`data/charms/solar_<ability>.json`):
  - **Dawn — complete:** Melee (22), Archery (12), Brawl (10), Thrown (9),
    Martial Arts / Snake Style (10, category `martial_arts:snake`).
  - **Zenith — complete:** Endurance (8), Performance (10), Presence (6),
    Resistance (12), Survival (10).
  - **Twilight — complete:** Craft (7), Investigation (6), Lore (7), Medicine (10),
    Occult (8 = 3 Circle Sorcery + 5 spirit charms).
  - **Night — complete:** Athletics (11), Awareness (4), Dodge (5), Larceny (8),
    Stealth (6).
  - **Eclipse — complete:** Bureaucracy (9), Linguistics (8), Ride (8), Sail (8),
    Socialize (6).
  - **ALL corebook Solar charms authored — 220 charms across every ability.**
- **Charm convention:** category is the plain ability (`melee`) or
  `martial_arts:<style>`; ids `solar.<ability>.<kebab>`. Author one ability at a
  time from page PNGs; verify cut-off values, never guess. CharmType has a
  `Special` value (Ox-Body Technique).
- **The data catalogue is complete:** 220 corebook charms + all spells, the M&F
  catalog, backgrounds, weapons/armor.
- **Desktop packaging:** Cytoscape vendored locally (offline-ready). `pack/` has the
  PyInstaller one-file spec + **browser-launch entry** (`run_app.py` → `ui.run(show=True)`
  on **loopback** `host=127.0.0.1`). Lifecycle hardening so re-launching the exe always
  lands on a working app: (a) `app.on_disconnect` quits the server ~4s after the last
  tab closes [grace > NiceGUI's 3s reconnect_timeout so a refresh survives; uses
  `builder.any_tab_connected()`]; (b) on startup `_already_serving()` checks the port —
  if a previous instance is still up it just `webbrowser.open`s it and exits instead of
  crashing on the busy port. (127.0.0.1 also dodges some browsers' HTTPS-Only upgrade of
  `localhost`, which would break this plain-http server — Firefox HTTPS-Only on localhost
  was a real user snag.) + BUILD.md. The spec `collect_all("nicegui")` and **excludes the native stack**
  (`webview`, `qtpy`, `PyQt*`, `PySide*`) so the build stays ~60MB even if those happen
  to be installed. **Linux browser build done & verified** (`pyinstaller
  pack/exalted-builder.spec` → `dist/ExaltedBuilder`, ~60MB). NOTE: a Linux PyInstaller
  binary is NOT portable across distros (glibc/system-lib differences) — build on the
  oldest target distro for sharing. **Windows .exe still needs building ON Windows**
  (PyInstaller can't cross-compile); same spec. (A native-window packaging was tried and
  reverted — Qt bundling made it ~280MB and non-portable; `--native` stays a dev option.)
- **Merits & Flaws — REMOVED** (was: a Player's Guide catalog + mechanical-effect
  hooks). Ripped out entirely on 2026-06-15 per the user's decision (the M&F system
  bundles balance-wrecking Charm rewrites they dislike). Gone: `data/merits_flaws.json`,
  `MeritFlawType`/`MeritFlawEffect`/`Character.merits_flaws`/`MeritFlaw`,
  `RuleSet.merit_flaw_catalog`, the chargen BP folding, the `validate.trait_max`/
  `cost_multiplier` machinery and its use in `costs.py`/`advancement.py`/the editor & XP
  dot caps (all dot caps are now the flat 5 / WP 10), the editor M&F combobox, the XP-tab
  M&F card, `advancement.gain/lose_merit_flaw`, and `XpEntry.mf`. `XpEntry.cost` is no
  longer signed (no XP-granting rows). `HealthLevel.removed` (curses → fewer levels)
  stays — it's independent of M&F. Old saves with a stray `merits_flaws` field still load
  (the field is just dropped). Do NOT reintroduce M&F.
- **Combos — done** (chargen BP *and* during-play XP cost = Σ member `min_ability`,
  via `costs.combo_cost`/`advancement.add_combo`).
- **Ox-Body Technique — repeatable with a variant menu — done 2026-06-15** (core p170).
  Buyable **once per dot of Endurance** (cap), each purchase picking ONE health-level
  package (confirmed from the p170 PNG + user as rules authority): **(a)** one -0;
  **(b)** two -1; **(c)** one -1 + two -2. The minimum Endurance is the *cap itself*
  (Nth copy needs Endurance ≥ N) — it does NOT vary per package. **Data-driven:** the
  `Charm` model gained `repeatable_cap_ability` + `variants: list[CharmVariant]`
  (key/label/health_levels); authored in `data/charms/solar_endurance.json`. **Model:**
  Ox-Body lives on `Character.ox_body: list[OxBodyPurchase]` (one record per purchase,
  each carrying the chosen variant + its health levels copied inline) — it is NOT in
  `character.charms`, so N copies are representable. **Engine:** `derive.health_track`
  folds in the purchases' levels; `validate.ox_body_cap`/`check_ox_body` (cap + valid
  variant + min essence, wired into `validate()`); `validate_chargen` counts each
  purchase as a Charm pick (toward the 10-pool + ≥5 caste/favoured, Endurance-gated);
  `costs.ox_body_cost` (= a normal new Charm, 8 caste / 10 else); `advancement.learn_ox_body`
  (+ undo + audit). `validate.OX_BODY_ID` is the shared id constant; `lock_chargen`
  snapshots `ox_body`. **UI:** the picker's detail panel special-cases the Ox-Body node
  (count `n/Endurance` + a 3-package add menu + per-purchase remove) for chargen; the XP
  tab has a "Buy Ox-Body" package select (Ox-Body is excluded from the normal Learn-Charm
  dropdown); the sheet lists one row per purchase. The editor's manual per-tier health
  widget stays for other bonuses/curses (source relabelled "Bonus", no longer "Ox-Body").
- **Nature dropdown — done 2026-06-15.** `data/natures.json` (16 Archetypes from the p105
  summary: Architect/Bravo/Bureaucrat/Caregiver/Conniver/Critic/Explorer/Follower/Gallant/
  Hedonist/Jester/Judge/Leader/Martyr/Paragon/Rebel, each with its one-line description) →
  `NatureType` model + `RuleSet.nature_catalog` (loaded by `rules_db` like backgrounds).
  `Character.nature` stays **free-text** (Nature is narrative-only, no mechanical effect);
  the editor field is now a combobox of the catalog with `new_value_mode="add-unique"` so a
  custom Nature is still allowed.
- **Caste info box — done 2026-06-15.** `CasteDefinition` gained a `description` field;
  `castes.json` carries each caste's quick description (from the p104-105 summary PNG) and a
  **detailed Anima Power write-up with mote costs** (read from the per-caste anima pages,
  corebook p119-127: Dawn 10m terrify; Zenith 1m/body burn + 5m smite undead; Twilight 5m
  cancel health levels; Night double-motes to mute + 10m veil; Eclipse 10m+1WP oath + spirit
  immunity). The editor's Edit pane shows a caste-info box at the top-left (caste name,
  description, Caste Abilities, Anima Power) beside the Identity fields; it refreshes when the
  Caste dropdown changes.
- **Editable custom equipment — done 2026-06-15.** The editor's Armor/Weapons panels now let
  you fully edit each item's stats (not just pick a catalog name): every item has an "Edit
  stats" expander (`ui.expansion`) with number inputs writing back to the inline `Weapon`/
  `Armor` copy, and a live-updating summary line. Weapons expose Spd/Acc/Dmg/Type(L·B)/Def/
  Rate/Range + min Str·Dex·MA, max Str, artifact/attunement/resources, notes; armor exposes
  soak L·B, mobility, fatigue, artifact/attunement/resources. Non-negative fields are clamped;
  picking a catalog name re-fills (overwrites) the stats. UI-only — the inline-copy model
  already held every field; no engine change. (Weapons remain display-only in the engine.)
- **XP advancement — done (post-lock):** `engine/costs.py` + `engine/advancement.py`
  + the XP tab. The chargen snapshot is the baseline; purchases mutate current
  traits and append to `xp_log`; `validate_xp` audits overspend/tampering. Trait
  maxima used: dots (attr/ability/virtue/essence) = 5, Willpower = 10 — change the
  constants in `advancement.py` if a page says otherwise. NOT yet built: a
  per-session XP-grant ledger and the "training time" rule (`XpEntry.training_complete`
  is a dormant hook); state-reconciliation of hand-edited current-vs-snapshot drift
  (the read-only lock guards normal use).
- **Deferred / not yet authored:** `chargen_budgets.json`, `costs_bonus.json`,
  `costs_xp.json` (optional — loader falls back to verified model defaults);
  combat/attack derivation (weapons are display-only); the Dire Lance mounted
  profile; Limit Break (play-state — add at sheet-export time, not chargen).

## TODO — planned next
Recent TODOs all DONE (2026-06-15): ~~remove M&F~~, ~~repeatable Ox-Body~~,
~~Nature dropdown~~, ~~Caste info box (description + Anima Power)~~, ~~re-package the Linux
binary~~ (rebuilt 2026-06-15, `dist/ExaltedBuilder` ~60MB, smoke-tested: boots + serves 200).

Nothing queued. Open future work: the **Windows .exe** still needs a Windows host
(PyInstaller can't cross-compile; same spec); combat/attack derivation (weapons are
display-only); Limit Break at sheet-export time. See [[packaging-plan]],
[[combat-engine-deferred]].
