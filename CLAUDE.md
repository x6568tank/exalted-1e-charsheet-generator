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

## Status (86 tests passing)
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
  - `engine/lifecycle.py` — `lock_chargen` freezes wp_virtue_component + snapshot.
- **Persistence:** `persistence.py` — atomic JSON load/save, enum-keyed dicts.
- **UI (NiceGUI):** `ui/view.py` is the pure, toolkit-free presenter (sheet view +
  charm-graph data). `ui/app.py` read-only sheet, `ui/editor.py` chargen editor
  (live validation), `ui/picker.py` Cytoscape charm-tree picker. `ui/builder.py`
  is the **unified tabbed app** (Edit / Charms / Sheet, one shared Character, with
  Save / Load / Finish & Lock). Run the unified app:
  `.venv/bin/python -m exalted_builder.ui.builder [char.json] [--show] [--port N]`
  (the individual modules also run standalone). Example char:
  `examples/ashes-of-dawn.character.json`.
- **Data authored:** `castes.json`, `backgrounds.json` (10 core), `armor.json`
  (mundane + 5 artifact), `weapons.json` (mundane + artifact), `spells.json` (all 3
  circles), and the Circle Sorcery charms (`solar_occult.json`, 3).
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
- **Next:** the Merits & Flaws data catalog (PG pp.16-41) to finish the catalogue
  (currently free-entry). Corebook Solar charms are 100% authored (220).
- **Merits & Flaws** (Player's Guide): `Character.merits_flaws` is free-entry
  (name/points/merit-or-flaw); `validate_chargen` folds them into bonus points
  (Merits cost, Flaws grant up to 10). The full catalog (PG pp.16-41) is NOT yet
  authored as rules data — author later like charms. Health curses: `HealthLevel.
  removed` lets a character have fewer levels than the base 7.
- **Deferred / not yet authored:** Merits & Flaws data catalog; `chargen_budgets.json`,
  `costs_bonus.json`,
  `costs_xp.json` (optional — loader falls back to verified model defaults);
  combat/attack derivation (weapons are display-only); the Dire Lance mounted
  profile; Limit Break (play-state — add at sheet-export time, not chargen).
