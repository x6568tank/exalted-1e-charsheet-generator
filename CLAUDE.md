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

## Status (788 tests passing)

The detailed build log lives in `docs/status/` — one file per topic/splat, kept
out of this file so CLAUDE.md stays readable. **Read the relevant file before
touching that area**; the summaries below are pointers, not the full record.

| Area | File |
|---|---|
| Models, loader, persistence, `engine/`, NiceGUI UI | `docs/status/engine-and-ui.md` |
| Core data files, Charm counts, `tools/` | `docs/status/data-and-tooling.md` |
| Solar castebooks (Dawn/Eclipse/Night/Twilight/Zenith) | `docs/status/solar-castebooks.md` |
| Lunar (chargen, Attribute-keyed Charms, Gifts, Combos) | `docs/status/lunar.md` |
| Sidereal (Colleges, ronin, Paradox, Charms, SMA wiring) | `docs/status/sidereal.md` |
| Alchemical (Charm Slots, Arrays, Submodules, Clarity, Vat Refit) | `docs/status/alchemical.md` |
| Solar alt-origin: Cult of the Illuminated (Camps, Callings, granted Charms) | `docs/status/illuminated.md` |

**One-paragraph state of the world:** Models/persistence/engine/UI foundation is
done (`engine-and-ui.md`). Every splat's data, engine and UI is shipped and
browser-verified: Solar (core + 5 castebooks + Cult of the Illuminated origin),
Dragon-Blooded, Abyssal, Lunar, Sidereal, Alchemical. 1,378 Charms total across
six splats (`data-and-tooling.md`). GM party mode and the Storyteller reference
screen are done. **Mortals is the only splat left** (see **Next Exalt Types**
above), blocked on source images. See **TODO** below for what's actually next.

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
Illuminated Solar origin, the five Solar castebooks, and the **canonical Charm-pick
enumeration** (both halves — see `docs/status/engine-and-ui.md`), and the **Abyssal
Moonshadow's half of the generalist rule** (2026-07-29, from `images/Abyssal/Traits/
145-146.png` — pure data, no new code; see `docs/status/engine-and-ui.md`).

**Next:**
- **Mortals** — the LAST splat (Godblooded / Ghosts / Heroic Mortals / …). Blocked on
  source images landing in `images/Mortals/`, per the never-author-from-memory rule.
  See **Next Exalt Types** above for the colour scheme.
- **Merits & Flaws**, after Mortals — one centralized `merits_and_flaws_calc`, NOT the
  old per-file hooks. See **Removed**.

Full multi-splat plan: `~/.claude/plans/should-we-plan-out-encapsulated-crab.md`.
DB chargen numbers as verified from source pages: [[db-chargen-findings]].
