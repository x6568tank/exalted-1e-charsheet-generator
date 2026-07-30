# Architecture

How the thing works. No implementation history — that is `docs/status/`. No rationale
for individual rulings — that is the status files and (going forward)
`docs/decisions/`.

## The one rule

**Dependencies run one way: `ui → engine → models`.** Nothing flows back inward. The
engine never imports the UI, the models never import the engine, and no game rule is
ever decided outside `engine/`.

```
        data/*.json                    a .character.json
             │                                │
             ▼                                ▼
        rules_db.py                     persistence.py          ← the edges: I/O lives here
     (+ custom_content.py)
             │                                │
             ▼                                ▼
          RuleSet  ─────────┐      ┌────────  Character
        (immutable)         │      │        (mutable, yours)
                            ▼      ▼
                    engine/  validate · derive · costs
                             advancement · lifecycle · refit
                       pure functions of (RuleSet, Character)
                                   │
                                   ▼
                              ui/view.py                        ← presenter: view models, no toolkit
                                   │
                                   ▼
                        ui/*  (NiceGUI: builder, picker, sheet, …)
```

`RuleSet` and `Character` are **two independent inputs**. The character is not derived
from the rule set — it is loaded from its own file and merely *references* the rules by
id. Keeping those two domains apart is the central idea of the whole design.

## The two data domains

| | Rules data | Character data |
|---|---|---|
| What | The rulebook: Charms, spells, costs, budgets, gear | One character's current state and its audit trail |
| Where | `exalted_builder/data/*.json` (+ the user's `custom/`) | A `.character.json` wherever the user put it |
| Lifetime | Loaded once at startup, read-only | Mutated constantly while building |
| Shape | `models/rules.py` → `RuleSet` | `models/character.py` → `Character` |
| Identity | Stable string ids (`solar.melee.fire-and-stones-strike`) | References rules **by id, never by name** |

## Module responsibilities

### `models/` — shape only

Pydantic models enforce **structural** invariants and nothing else: non-negative
ratings, valid enums, ratings ≤ 5 where the trait is bounded. Game legality — budgets,
caps, prerequisites, whether that Charm is learnable — is `engine/validate.py`'s job,
because it needs the `RuleSet` and the models deliberately do not have it.

* `rules.py` — the catalogue: `Charm`, `Spell`, `CasteDefinition`, `ExaltDefinition`,
  the cost/budget tables, `RuleSet` itself, and the shared enums.
* `character.py` — the save file. It imports the shared **enums** from `rules.py`
  (`AbilityName`, `AttributeName`, `VirtueName`, `Damage`, `Orientation`) because both
  domains name the same traits; it must never import the **catalogue** — no `RuleSet`,
  no `Charm`. That is the line, and it is what "the models don't import the rules"
  means in practice.

### `rules_db.py` — the loader (an edge)

Reads `data/` into an immutable `RuleSet`, indexes Charms and spells by id, and
**link-checks referential integrity at load time**: every prerequisite id resolves,
every spell's circle is granted by some Charm, camps and Callings point at real
Charms, thaumaturgy's aspects are globally unique. Errors **accumulate** and raise
together as one `RuleDataError`, because fixing a hand-entered data set one error per
run is miserable.

Optional tables (`costs_bonus.json`, `costs_xp.json`, `chargen_budgets.json`) fall
back to the model defaults, so a partial data set still loads.

### `custom_content.py` — the user's homebrew (an edge)

A second, optional data source overlaid on the book: the user's `custom/` library, same
file shapes, merged by `load_app_ruleset`. Its failures are **non-fatal** — reported on
`RuleSet.custom_problems`, never raised — because homebrew must not be able to stop the
app from starting. It also owns embedding definitions into a save and absorbing them
back out. See `docs/status/custom-content.md`.

### `engine/` — where the rules live

Every function here is pure: `(RuleSet, Character) → result`. No I/O, no UI, and
(except for the lifecycle and advancement mutators, which exist to edit a character)
no mutation.

| Module | Answers |
|---|---|
| `validate.py` | Is this legal? Chargen budgets, trait minimums, Charm prerequisites, Combos, Arrays, spell access, splat gates, the canonical Charm-pick enumeration |
| `derive.py` | What follows from the traits? Willpower, Essence pools, the health track, soak, Clarity |
| `costs.py` | What did chargen cost? Bonus-point accounting and the per-purchase breakdown |
| `advancement.py` | What does this cost now, and was the ledger honest? Post-lock purchases and the XP audit |
| `lifecycle.py` | `lock_chargen` / `unlock_chargen` — the transition between the two modes |
| `refit.py` | Alchemical vat refit: moving Charms between Slots and the Panoply |

`validate.py` is by far the largest module, and that is where the splat-specific
mechanics live — Charm Slots, Colleges, the Immaculate path, Attribute-keyed Charms.
The data-driven design covers *content*; a splat's novel *subsystem* is code.

### `persistence.py` — save files (an edge)

Load/save a `Character` or a `Party` as JSON, written atomically (temp file +
`os.replace`) so a crash cannot truncate an existing save. No game logic; pydantic
enforces structure on load. It is also the single choke point where a save's homebrew
definitions are embedded and absorbed — there are ~20 save/load call sites in `ui/`,
and doing it per-call-site would guarantee one gets missed.

### `ui/` — disposable frontend

Contains **zero game logic**. Two layers:

* `view.py` — the presenter. Turns `(RuleSet, Character)` into display-ready view
  models (`SheetView`, `CharmDetail`, `CharmGraph`, …). Imports no UI toolkit, so it is
  unit-testable on its own; this is where most UI tests actually aim.
* everything else — NiceGUI renderers, one per screen: `builder.py` (the shell and tab
  bar), `editor.py` (chargen), `picker.py` (the Cytoscape Charm tree), `combos.py`,
  `xp.py`, `play.py`, `storyteller.py` (ST options), `custom.py` (homebrew authoring),
  `app.py` (the read-only sheet), `gm.py` (the party page), plus `theme.py` for the
  per-splat palette.

If a renderer needs to know a rule, the answer is to add a function to the engine or
the presenter, not an `if` to the render.

## The character lifecycle

Chargen and advancement are **different shapes**, not two settings of one shape.

```
   building                          lock_chargen()                       in play
─────────────────────────────────────────────────────────────────────────────────────
current traits are the truth   ──▶  snapshot frozen   ──▶   snapshot + append-only
validated against the budgets       wp_virtue_component     xp_log, audited against
(a constraint snapshot)             pinned                  current state
```

* **Before the lock**, current state is canonical and freely editable. The engine
  *computes* the point accounting; the user never hand-tags which dot came from where.
  `validate_chargen` compares current traits to `ChargenBudgets`.
* **`lock_chargen()`** deep-copies every purchasable collection into a
  `ChargenSnapshot` and pins `wp_virtue_component` — the two highest Virtues *at lock*.
  That pin is the mechanism by which raising a Virtue later can never raise Willpower.
  It does not judge legality; validate first if you want to refuse an illegal lock.
* **After the lock**, every change is an `XpEntry` in an append-only log.
  `advancement.validate_xp` reconciles current state against snapshot + log and
  re-prices each entry, so a hand-edited save is caught rather than trusted.

## Invariants worth knowing before you change anything

1. **Play-state is validation-isolated.** `Character.play` (spent motes, marked
   health, temporary Willpower, Limit) must never enter chargen validation, the XP
   audit, or any permanent derivation. Capacities flow *out* of the engine into the
   tracker; nothing flows back. It is a deliberately dumb manual tracker — no
   auto-accounting.
2. **Charms and spells are referenced by id; equipment and Backgrounds are inline
   copies.** Charms never vary between characters, so an id is right. A named artifact
   or a Background does vary, so the catalogue is an autofill source and the character
   carries its own copy. The asymmetry is intentional.
3. **Charm prerequisites are AND-of-OR**: `list[list[str]]`. Every inner group must be
   satisfied; any one id inside a group satisfies it. Breadth prerequisites ("any three
   Lore Charms") are a *count over a category* and live in `prerequisite_counts`,
   because AND-of-OR cannot express them.
4. **One enumeration for what a character holds.** Charms live on four lists
   (`charms`, `retainer_charms`, `granted_charms`, and the repeatable purchase records).
   Consumers call `validate.charm_picks` instead of walking them — the last time four
   call sites each walked their own subset, all four missed Gifts when Gifts landed.
5. **Unresolvable ids degrade, they do not crash.** A Charm id with no definition still
   produces a row (marked missing) and an `unknown-charm` error, everywhere.
6. **Cost tables are data.** Never hardcode a price; `costs_bonus.json`,
   `costs_xp.json` and `chargen_budgets.json` are keyed by exalt type with a `default`
   row, and the `*_for()` accessors handle the fallback.

## Data conventions

* **Schemas live in code.** The authoritative field-level truth is
  `models/rules.py` and `models/character.py`. Do not duplicate a schema into prose
  where it can drift; for a working example of a data file, copy
  `data/charm.example.json` or `data/armor.json`.
* **Ids are stable, namespaced strings** — `solar.melee.fire-and-stones-strike`. User
  homebrew is namespaced `custom.` so it can never collide with printed content.
* **A Charm's `category`** is an `AbilityName` value, `"sorcery"`, or a Martial Arts
  style written `martial_arts:<slug>`. The picker derives its style groups from that
  string, which is why a new style needs no schema change at all.
* **Backgrounds are soft free text** — `BackgroundEntry.name` is a name, not an id, and
  the catalogue is autofill. The single exception is
  `ChargenBudgets.background_rules`, which attaches per-splat chargen mechanics to a
  Background *by name* (added for the Alchemical; empty for every other splat).
* **Charms are split per ability/splat** across `data/charms/*.json`. The filename
  carries no meaning; `category` and `exalt_type` do.

## Testing

`tests/` is engine-first (~1,180 tests). Pure engine and presenter behaviour is tested
directly; render behaviour goes through NiceGUI's `User` harness against routes defined
in `tests/_ui_main.py`, which is the only way to catch the failure mode that has bitten
this project most — a `ui.select` whose initial value is not among its options, which
500s at render time and never in a unit test. A `@ui.page` route builds once per
session, so each test state gets its own route.
