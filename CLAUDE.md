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
- **Play-state is a SEPARATE, validation-isolated layer (added 2026-06-16).** It was
  originally out of scope; the user has since added an in-play tracker (the Play tab):
  marked health damage, motes spent, temporary Willpower, and Limit. It lives on
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

## Workflow expectations
- **Test-first on the engine.** That's where bugs hide.
- **The human is the rules authority.** 1e has ambiguous and errata'd corners
  (Combo legality, the specialty cap, Charm interactions). Flag them and ask; do
  not silently choose an interpretation.
- **Game data comes from the page, never from your own knowledge.** Any concrete value — a cost, minimum, prerequisite, rating, or rules detail — that you write into `data/` or code must come from a page image the human gave you, or from an existing `data/` file. Do not supply one from your own knowledge of Exalted even when you are confident — 2e values will feel right and be wrong for 1e. If you need a value and have no page for it, stop and ask for a PNG. Never choose an interpretation, invent a number, or read the PDFs in `sources/` yourself. PNGs will be dropped in `images/`.
- Don't leak game logic into the UI. Don't re-derive what the engine already
  computes. Don't hardcode the cost tables — they live in `data/`.

## Status (230 tests passing)
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
    **Permanent trait reductions (curses / Charm costs — done 2026-06-16):**
    `lower_attribute/ability/virtue/willpower/essence` lower a permanent trait OUTSIDE
    the XP economy — they refund no XP and log a `cost 0` row with `to_rating <
    from_rating`, so `_expected_cost` prices any reduction at 0 (the audit never flags a
    curse) and `undo_last` reverses it like any row. Engine enforces only the floor
    (attr/virtue/WP/essence ≥ 1, ability ≥ 0), not a rules reason; the free-text reason
    rides on the row's `detail`. **Willpower below the Virtue floor:** permanent WP =
    pinned `wp_virtue_component` + `willpower_purchased`; a curse decrements purchased,
    which may go **net-negative** (its `ge=0` guard was relaxed for exactly this), and
    `undo_last` for willpower is symmetric (`-= to−from`) so it reverses raises AND
    reductions. A reduction that drops an Ability below a known Charm's `min_ability` is
    surfaced by the normal `validate()` — intended, not blocked.
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
  Charm/spell currently selected in the Learn dropdowns. It also has a **"Reduce a
  Trait" card** (curse / Charm cost): a dropdown of every reducible trait with its
  current value + a reason field → `advancement.lower_*` (free, logged, undoable).
  `ui/play.py` is the **in-play tracker (the Play tab)** — `view.build_play_view`
  supplies the capacities (health-track boxes, mote pools, permanent WP); the tab
  overlays the fill-state stored on `Character.play`: clickable health boxes cycling
  empty→`/`→`x`→`*`, numeric motes-spent (Personal/Peripheral), temp-WP dot boxes, a
  bare 10-box Limit counter, and **Rest / refresh** (clears motes + temp WP only —
  damage/Limit are ST discretion). Live regardless of lock; ZERO game logic, never
  feeds back into validation. `ui/builder.py`
  is the **unified tabbed app** (Edit / Charms / Combos / XP / Play / Sheet, one shared
  Character, with New / Save / Load / Finish & Lock / Unlock). Once locked the chargen
  tabs (Edit/Charms/Combos) go read-only (a notice points to the XP tab or Unlock);
  the XP tab is where advancement happens; the Play tab is live throughout. It **starts on a
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
  circles), `natures.json` (16 — the p105 Archetype summary list), `materials.json` (5
  magical materials; weapon bonuses from p341, armour bonuses from p345-346), and the
  Circle Sorcery charms (`solar_occult.json`, 3).
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
  **Custom-name crash fixed — 2026-06-16 (NiceGUI 3.x).** NiceGUI 3.13's `ui.select` raises
  `ValueError: Invalid value` when constructed with a `value` not in its `options` (a v2→v3
  change, same family as the `e.file` upload break). Typing a custom (off-catalog) weapon/
  armor/nature/background name stored the name but left the select's options as the catalog
  only, so the next render/reload threw — the equipment panel vanished and a page reload 500'd.
  Fix: `editor._opts_with(names, current)` folds the current value into the option list (applied
  to every `new_value_mode="add-unique"` select in `ui/editor.py` and `ui/xp.py`); and
  `set_weapon`/`set_armor` now only overwrite stats on a **catalog** match — a custom name just
  renames the inline item, preserving typed stats instead of zeroing them. Regression test:
  `tests/test_custom_equipment_render.py` (NiceGUI User-sim; the suite now sets
  `asyncio_mode="auto"` + registers `nicegui.testing.user_plugin` in `conftest.py`). **Rule of
  thumb:** any `ui.select(options, value=…)` whose value can be off-list must include it in
  `options`. See [[nicegui-3x-select-value-validation]].
- **Artifact magical materials — done 2026-06-16 (core p341).** `data/materials.json` →
  `MagicalMaterial` model + `RuleSet.material_catalog` (loaded by `rules_db`). Each material
  resonates with ONE Exalt type and grants its bonus **only in the hands of that type**
  (`exalt_type` matches `Character.exalt_type`): Orichalcum→Solar +1 spd/acc/def,
  Moonsilver→Lunar +2 acc, Jade→Dragon-Blooded +3 spd, Starmetal→Sidereal +2 dmg,
  Soulsteel→Abyssal +1 acc (+narrative mote drain). **Armour (p345-346):** Orichalcum &
  Soulsteel +2 to both soaks; Moonsilver negates the mobility penalty; Jade negates fatigue;
  Starmetal −1 to the attacker's damage successes (a damage-roll effect → `notes` only, since
  combat derivation is deferred). The two negate effects are flags (`armor_negate_mobility_penalty`/
  `armor_negate_fatigue`) not deltas, because they zero a base-dependent value. `Weapon`/`Armor`
  gained a `material` field (id; "" = mundane). Pure engine `derive.effective_weapon`/`effective_armor`
  fold the delta in, Exalt-gated via `derive.applied_material`; `derive.soak(character, ruleset)`
  routes armour through `effective_armor`. UI: a **Material** dropdown in the editor's per-item
  Edit-stats; summaries + the read-only sheet show **effective** stats with a `◈ <Material>` tag.
  Only Solar exists today, so in practice only Orichalcum is mechanically active until other
  splats are added — but all five materials are authored and Exalt-gated, ready for them.
- **Chargen BP-spend log — done 2026-06-16.** `validate.bonus_point_breakdown(rs, char)` is the
  pure per-domain BP accounting (Attributes/Abilities/Backgrounds/Virtues/Charms & Spells/
  Combos/Specialties/Willpower/Essence), now the single source `validate_chargen` consumes for
  the ceiling check (the arithmetic moved out of `validate_chargen`; `_chargen_source` is the
  shared snapshot-vs-current selector). The editor renders it as a live "Bonus Points" card
  **under the caste-info box** on the left column.
- **Craft as separate per-focus Abilities — done 2026-06-16 (RAW p136).** "Master multiple
  crafts → take the Ability multiple times," so each craft is its own rated Ability, NOT a
  specialty. `Character.crafts: list[CraftRating]` (focus + rating); the `AbilityName.CRAFT`
  dot in `abilities` is **unused** (read craft via `validate.craft_rating` = highest instance,
  used for Craft-Charm `min_ability`). Chargen accounting expands craft into per-instance
  Ability slots (`validate._ability_slots`) so each craft dot is budgeted/capped/discounted
  like the Ability it is and counts toward the ≥10 Caste/Favoured min when Craft is C/F; snapshot
  carries `crafts`. Costs reuse `ability_step(CRAFT, …)`; `advancement.learn_craft`/`raise_craft`
  (+ undo + audit; XpEntry `target="crafts"`, `detail=focus`). UI: editor has a **Crafts panel**
  (Craft row in the abilities grid is replaced by a "↓ per-focus" pointer); the XP tab has a
  **Crafts card** (raise an existing focus / learn a new one); the sheet shows one "Craft (Focus)"
  row per instance. Old saves' `abilities.craft` value is ignored (not migrated).
- **Free background editing on the XP screen — done 2026-06-16.** The XP tab has a
  "Backgrounds (free — no XP)" card editing `character.backgrounds` directly post-lock (add/
  remove/name/note/rating); story-driven, so **no XP cost and no log entry** (like equipment,
  not a dotted trait). Backgrounds aren't XP-audited, so this doesn't perturb `validate_xp`.
- **Free equipment swap/edit on the XP screen — done 2026-06-16.** The XP tab also has an
  "Equipment (free — no XP)" card mirroring the editor's Armor/Weapons panels (catalog autofill
  + per-item Edit-stats expander + Material dropdown + add/remove), editing the inline
  `character.weapons`/`armor` copies post-lock at **no XP cost / no ledger row** (equipment is an
  inline copy, not an XP-priced trait). Summaries show material-effective stats. UI-only; the
  shared autofill/stat-widget helpers are duplicated from the editor (small, render-bound closures).
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
  profile. (Limit is now tracked in the Play tab — see the play-state layer above.)
- **In-play tracker — done 2026-06-16.** `Character.play: Optional[PlayState]` (Damage
  enum `/ x *`, health marks aligned to the derived track, motes spent, temp WP, Limit
  0..10); the Play tab (`ui/play.py`) + `view.build_play_view`; permanent trait
  reductions on the XP tab (`advancement.lower_*`). Tests in `tests/test_play.py` +
  reduction tests in `tests/test_advancement.py` + render tests via the User-sim harness.

## TODO — planned next
All prior TODOs DONE (2026-06-15): ~~remove M&F~~, ~~repeatable Ox-Body~~,
~~Nature dropdown~~, ~~Caste info box (description + Anima Power)~~, ~~re-package the Linux
binary~~, ~~editable custom weapons/armor in the editor~~.

DONE 2026-06-16: ~~Craft as separate per-focus Abilities (RAW p136)~~, ~~artifact
magical-material weapon AND armour bonus (Exalt-gated, p341/p345-346)~~, ~~chargen
BP-spend log~~, ~~free background editing on the XP screen~~, ~~free equipment swap/edit on
the XP screen~~, ~~custom weapon/armor-name crash (NiceGUI 3.x select-value)~~. **All queued
TODOs are now cleared.**

**In progress — multi-splat refactor.** Generalizing Solar-only → all Exalt
types, **all-splats-RuleSet + runtime-filtering** design, **Dragon-Blooded first** (switched
from Abyssal 2026-07-17). **Phases 0-4 DONE (on `main`). Phase 5 (DB) IN PROGRESS: the chargen
FOUNDATION is done + tested (243 tests)** — Breeding term + `EssencePoolSpec.peripheral_virtue_mode`
+ `breeding_*` tables in `derive.essence_pools`; `exalts.json` DB row (Personal=Ess+WP,
Peripheral=Ess×4+WP+two-highest-Virtues, cap Terrestrial); `chargen_budgets.json` + `costs_bonus.json`
DB rows; the 5 Aspects in `castes.json`; **Dynastic/Outcaste origin** (`Character.origin`,
`RuleSet.budgets_for(exalt_type, origin)`, `ChargenBudgets.required_min_abilities`, editor Origin
dropdown + budget-driven panel headers). **STILL TODO: DB charm trees + DB Ox-Body (the huge
content grind — DB charms are organized by ELEMENT→ability; the `Charm.element` field now exists,
default `""`, "Air"/"Earth"/"Fire"/"Water"/"Wood" for DB). The **Immaculate Order charm package
ENGINE is DONE (2026-07-18):** "Immaculate Order Charms" turned out to be the Fivefold Dragon
Method martial-arts styles (ch.6), NOT a separate ability-charm flavour — marked by the data flag
`Charm.immaculate`. `validate` now branches the chargen Charm rules on whether any Immaculate Charm
is chosen: standard path = charm_count Charms, ≥charm_min_caste_favored Caste/Favored; Immaculate
path = `immaculate_charm_count` (5) Charms all one elemental tree (`immaculate-single-tree`), the
Caste/Favored min waived, Immaculate BP row (10/7). **STILL TODO: author the five Immaculate style
charm trees** from `images/Dragonblooded/Martial Arts/` (the content grind) and the DB ability charm
trees + DB Ox-Body. Full plan:
`~/.claude/plans/should-we-plan-out-encapsulated-crab.md`.
- **P0-1:** per-Exalt-keyed cost/budget tables (`RuleSet.{budgets,xp_costs,bonus_costs}:
  dict[str,…]` + `*_for(exalt_type)`, "default" fallback); `ExaltDefinition`/`EssencePoolSpec`
  + `RuleSet.exalts` + `exalt_for`; `data/exalts.json`; data-driven `derive.essence_pools`;
  `validate.ox_body_charm`; `validate.check_exalt_type`.
- **P2:** `Caste` enum dropped → `Character.caste: str` keyed to `ruleset.castes: dict[str,
  CasteDefinition]` (gained `id`/`exalt_type`/`label`); legacy `"Dawn"→"dawn"` save-migration;
  `validate.check_caste_splat` (`caste-wrong-splat`).
- **P3:** `Charm.exalt_type` (default "Solar"); `validate.splat_of`/`charm_matches_splat`/
  `check_splat_consistency` (`charm-wrong-splat`); picker/graph/editor filter by exalt_type;
  editor Exalt-type dropdown.
- **P4:** `grants_sorcery_circle`→`grants_circle`, `granted_sorcery_circles`→`granted_circles`;
  `validate.chargen_barred_circle` reads `ExaltDefinition.highest_magic_circle_id` (issue code
  `spell-solar-circle-chargen`→`spell-top-circle-chargen`). **Deferred with necromancy** (no DB
  payoff): Necromancy circles + `CircleKind`, and the picker's render-by-present-circles columns.

**Why DB-first changes Phases 4-5:** Dragon-Blooded do **not** use Necromancy (sorcery capped at
Terrestrial) — the sorcery→necromancy generalization is deferred. DB use **Aspects (Air/Earth/
Fire/Water/Wood), not Castes** ("Aspect" is a label over the same caste slot).

**DB chargen review (read from `images/Dragonblooded/Character Creation/` p150-153, 2026-07-17
— all values VERIFIED from the pages and recorded in [[db-chargen-findings]]):** Nearly all DB
chargen differences are **data-only** — one `"Dragon-Blooded"` row in the Phase-0 budgets table
covers **7/6/4** attrs, **3** favored, **35 dots / ≥13** abilities (Dynastic: **25/≥10** + free
minimums), **12** backgrounds, **7** charms (or 5 Immaculate) / **≥4**, **5** virtues, Essence
start **2**, **15** bonus points. **Essence formula & bonus-point cost table are read and
recorded** — they are in the **Character Creation Summary (p151-153)**, NOT the Traits chapter:
Personal = **Essence + WP**, Peripheral = **(Essence×3) + WP + ΣVirtues**, both +a Breeding-Background
term (per-dot table verified); BP costs match Solar except **Charm 7/5** and a new **Immaculate
Charm 10/7** row. See [[db-chargen-findings]] for the full numbers — do NOT re-guess them.
**Genuinely NEW structure** to build before/with Phase 5: (1) **Dynastic vs Outcaste** origin
(intra-splat budget variant + free minimum abilities — the budgets table keys by exalt_type only,
so this needs a Character origin field + selection); (2) **Immaculate Order charm package**
(7-DB-OR-5-Immaculate + one-elemental-tree constraint + the Immaculate-Charm BP row); (3) the
**Breeding term in `derive.essence_pools`** (EssencePoolSpec has no Background-derived coefficient
today). The **5 Aspects each have 5 fixed Aspect abilities** (verified) → CasteDefinition fits,
NOT new structure.

Also landed 2026-06-16: the **in-play tracker** (Play tab + trait reductions — see the
play-state layer above), which reversed the old "play-state out of scope" decision.

Open future work (unscheduled): **Phase 5 — author Dragon-Blooded data** (budgets row +
exalts row + Aspects + charm trees, from `images/Dragonblooded/`), preceded by the new
structure the DB review surfaced (Dynastic/Outcaste origin, Immaculate Order charms); the
**Windows .exe** still needs a Windows host (PyInstaller can't cross-compile; same spec);
combat/attack derivation (weapons are display-only). See [[db-chargen-findings]],
[[packaging-plan]], [[combat-engine-deferred]].
