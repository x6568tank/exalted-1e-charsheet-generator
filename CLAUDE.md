# Exalted 1E Character Builder — Project Guide

## What this is
A character creator / validator for **Exalted First Edition (1e)** — character
generation, point validation, and XP advancement, with a character-sheet view.
Scope is deliberately smaller than EdExalted (which is 2e/2.5e only); **1e is
unserved, which is the entire point of building this.** Initial target was
**Solar** Exalted from the core rulebook; **Dragon-Blooded, Abyssal, Lunar,
Sidereal and Alchemical are now also fully supported.** Every *Exalt* splat is done,
and **Mortals + Heroic Mortals shipped 2026-07-30** (one splat, two origins);
what's left is the four remaining **non-Exalt** splats (Godblooded, Ghosts,
Dragon-Kings, Mountain Folk) — see **Next Exalt Types** below.

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

**The non-Exalt splats are what's left, and the first of them is done.** Both pieces of
Dragon-Blooded book work that came first (human's call, 2026-07-29) are DONE — the four
**Outcaste-book origins** (`docs/status/dragonblooded-origins.md`) and the five **Aspect
books** (`dragonblooded-aspect-books.md`). **Mortals + Heroic Mortals shipped
2026-07-30** (`docs/status/mortals.md`) — chargen only: their route to Martial Arts and
Sorcery runs through Merits, so it is deliberately absent until the M&F work.
After the non-Exalts comes the centralized Merits & Flaws re-add (see **Removed**).

**⚠️ "Mortals" is NOT one splat** (human, 2026-07-29). It is shorthand for **six
different splats scattered across different books**, each needing its own sources and
its own chargen/data work:

| Splat | Source images | Status |
|---|---|---|
| Mortals | `images/Mortals/Mortals & Heroic Mortals/` | **DONE 2026-07-30** — chargen, engine, UI, tests. Magic access deferred to M&F. Not browser-verified yet. `docs/status/mortals.md` |
| Heroic Mortals | *(same, core p.103)* | **DONE 2026-07-30** — NOT a separate splat after all: the `heroic`/`ordinary` origin axis on `Mortal`. See below |
| Godblooded | — | NOT STARTED |
| Ghosts | — | NOT STARTED |
| Dragon-Kings | — | NOT STARTED |
| Mountain Folk | — | NOT STARTED |
| ~~Fair Folk / Fae~~ | — | **NEVER — permanently out of scope** (human, 2026-07-29) |

**Mortals and Heroic Mortals turned out to be ONE splat, two origins** (core p.103 runs
a single procedure through both, varying only 6/4/3·22 vs 4/3/3·16). That is a revision
of the 2026-07-29 "six separate splats" note *for those two only* — it says nothing
about the other four, which remain unstarted, sourceless and presumed unrelated.

**No source exists for the remaining four.** Do not start them, and do not
assume they share budgets, a Charm economy, or even a common shape — treat each as its
own splat until the pages say otherwise.

The **Fair Folk are the one splat that is never being implemented** — see *Deferred /
permanently out of scope*. Six to go, not seven.

Work on a given splat starts only once its rulebook images land in
`images/<ExaltName>/` — never author data from memory, per the Workflow rule below.
**Read `docs/adding-a-splat.md` before estimating one**: it records what each of the six
finished splats needed BEYOND data (Charm Slots, Colleges, Attribute-keyed Charms, the
`origin`/`upbringing` axes) and the traps, `highest_magic_circle_id` chief among them.

**Splat color scheme (UI theming):**

| Splat | Color | Status |
|---|---|---|
| Solar | Amber/Gold (default) | DONE |
| Abyssal | Black on ash | DONE |
| Dragon-Blooded | Vermillion | DONE |
| Lunar | Moonsilver blue (`slate`) | DONE (chargen, full Charm catalogue, Combos, Gifts, Form Library; UI clicked through 2026-07-22) |
| Sidereal | Purple | DONE (shipped 2026-07-24): chargen + Colleges + 193-Charm catalogue + SMA cost/cap wiring + UI click-through |
| Alchemical | Brass | DONE (shipped 2026-07-23): chargen + Charm Slots + Arrays + Submodules + CH3 catalogue (121 Charms) + CH4 weaving (38 protocols) + XP/advancement (slot economy, retainer Panoply, per-circle protocols, Eclipse crossover) + Clarity + Backgrounds + brass theme + full UI (favored-Attribute panel, Charm-Slot budgets, weaving Spells page, Arrays tab, Submodules panel, Vat Refit, Clarity tracker); UI clicked through 2026-07-23 |
| Mortal | Muddy brown | DONE (shipped 2026-07-30): `stone` family, the deliberately dullest palette of the seven. Whether the other four non-Exalt splats share it or get their own is UNDECIDED |

**Dragon-Blooded sub-sources:** the Outcaste book's four origins and all five Aspect
Books shipped 2026-07-29 (`docs/status/dragonblooded-origins.md`,
`dragonblooded-aspect-books.md`). Only the Outcaste book's numina/Mist aspect is still
open — see **TODO**.

**Merits & Flaws are BACK, as of 2026-07-30** — pulled forward of the remaining
non-Exalt splats because mortals shipped with no route to magic and that route runs
through Merits. They returned as decision 0011 demanded: ONE centralized calculation
(`engine/merits.py`), never the per-file hooks that got them ripped out. 99 entries
authored. `docs/status/merits-flaws.md`.

## Architecture, layout and data conventions → `docs/ARCHITECTURE.md`
**Read that file before touching the engine, the loader, the models or the data
shapes.** It is the SINGLE copy of: the `ui → engine → models` dependency rule, the two
data domains (rules vs character) and why they stay apart, what each module is
responsible for, the chargen → lock → XP lifecycle, the load-time link checking, the
invariants that must survive a refactor (play-state isolation, id-vs-inline references,
AND-of-OR prerequisites, the one Charm-pick enumeration, graceful unresolvable ids,
cost tables as data), and the data conventions (schemas live in the pydantic models
and nowhere else; namespaced ids; `martial_arts:<slug>` categories; soft-reference
Backgrounds).

**Do not restate any of it here.** One copy, or the two drift and the next session
believes the wrong one.

Two things that are directives rather than description, so they live here:
- UI assets go in `assets/`.
- `sources/` (rulebook PDFs) and `images/` (rulebook page images) are gitignored and
  are never committed.

## Decisions already made → `docs/decisions/`
**Do not relitigate any of these without the human reopening it.** One numbered record
per closed decision, each with the alternatives that were rejected and what the choice
costs — read the record before proposing anything that contradicts it.

`docs/decisions/README.md` is the index. The ones most likely to matter mid-task:

| # | Decision |
|---|---|
| 0001 | **1e only, never 2e** — also the source of the never-author-from-memory rule below |
| 0003 | Current state is canonical; the engine computes the point accounting |
| 0004 | Chargen and advancement are different shapes (snapshot + append-only XP log) |
| 0005 | Willpower's Virtue component is pinned at lock |
| 0006 | Play-state is validation-isolated — it must never enter chargen, the XP audit or a permanent derivation |
| 0008 | No combat/attack derivation |
| 0009 | **No dice rolling, ever** — broader than 0008; do not propose it |
| 0010 | The Fair Folk are permanently out of scope — six non-Exalt splats left, not seven |
| 0011 | Merits & Flaws return as ONE centralized calc, never the old per-file hooks |
| 0012 | Homebrew: the `custom/` library is the store, saves carry copies, homebrew errors are non-fatal |

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
- **The never-author-from-memory rule covers `data/` only.** The USER's custom
  library (`custom/`, see `docs/status/custom-content.md`) is theirs to fill with
  whatever they like — that is the point of it. You still never write a *printed*
  value you have no page for, and homebrew never goes into `data/`.
- Don't leak game logic into the UI. Don't re-derive what the engine already
  computes. Don't hardcode the cost tables — they live in `data/`.

## Status (1370 tests passing)

The detailed build log lives in `docs/status/` — one file per topic/splat, kept
out of this file so CLAUDE.md stays readable. **Read the relevant file before
touching that area**; the summaries below are pointers, not the full record.

| Area | File |
|---|---|
| **How it works** (module boundaries, lifecycle, invariants) | `docs/ARCHITECTURE.md` |
| **Why** (closed decisions, one record each) | `docs/decisions/` |
| **The rules data** (conventions, what the loader checks) | `docs/content.md` |
| **Implementing a splat** (honest cost, from the six done) | `docs/adding-a-splat.md` |
| Models, loader, persistence, `engine/`, NiceGUI UI | `docs/status/engine-and-ui.md` |
| Core data files, Charm counts, `tools/` | `docs/status/data-and-tooling.md` |
| Solar castebooks (Dawn/Eclipse/Night/Twilight/Zenith) | `docs/status/solar-castebooks.md` |
| Lunar (chargen, Attribute-keyed Charms, Gifts, Combos) | `docs/status/lunar.md` |
| Sidereal (Colleges, ronin, Paradox, Charms, SMA wiring) | `docs/status/sidereal.md` |
| Alchemical (Charm Slots, Arrays, Submodules, Clarity, Vat Refit) | `docs/status/alchemical.md` |
| Solar alt-origin: Cult of the Illuminated (Camps, Callings, granted Charms) | `docs/status/illuminated.md` |
| DB origins: Lookshy / Forest Witches / Lost Eggs / Pirates (`upbringing` axis) | `docs/status/dragonblooded-origins.md` |
| DB Aspect Books CH6 (87 Charms, Jade Mountain, breadth prereqs, gear) | `docs/status/dragonblooded-aspect-books.md` |
| **Thaumaturgy — DONE** (cross-splat Arts/Sciences/Rituals/Formulas; engine + UI, browser-verified) | `docs/status/thaumaturgy.md` |
| **Custom content — DONE** (user-authored Charms/styles/spells: library, `/custom` page, saves that carry homebrew) | `docs/status/custom-content.md` |
| **Mortals & Heroic Mortals — DONE** (one splat, two origins; casteless, no Charms, Essence pinned at 1; magic via M&F) | `docs/status/mortals.md` |
| **Merits & Flaws — DONE** (centralized calc per decision 0011; all 98 M&F authored; mortal magic unlock; editor + sheet + ST Options UI) | `docs/status/merits-flaws.md` |
| **Advantages tab — PLAN ONLY** (Backgrounds + M&F onto one both-sides tab; blocked behind A6) | `docs/status/advantages-tab.md` |

**One-paragraph state of the world:** Models/persistence/engine/UI foundation is
done (`engine-and-ui.md`). Every splat's data, engine and UI is shipped and
browser-verified: Solar (core + 5 castebooks + Cult of the Illuminated origin),
Dragon-Blooded, Abyssal, Lunar, Sidereal, Alchemical. 1,470 Charms total across
six splats (`data-and-tooling.md`). GM party mode and the Storyteller reference
screen are done. **Thaumaturgy is done end to end** (2026-07-29) — the cross-splat
capability layer, including its ST Options tab, which is now the home for every
Storyteller toggle. **User-authored custom content is done end to end** (2026-07-29):
a Storyteller can write their own Charms, Martial Arts styles and spells in the app,
they merge over the book data non-fatally, and a character save carries the homebrew
it uses (`docs/status/custom-content.md`). **Every Exalt splat is done, and the first
non-Exalt splat shipped 2026-07-30**: Mortals + Heroic Mortals, which turned out to be
one splat with two origins rather than two splats (`docs/status/mortals.md`). Their
chargen is complete, and so is their magic: **Merits & Flaws came back the same day**
(99 entries, one centralized calc — `docs/status/merits-flaws.md`), which is what opens
Terrestrial Martial Arts and Sorcery to a mortal. **Four non-Exalt splats remain** (Godblooded,
Ghosts, Dragon-Kings, Mountain Folk), all blocked on source material. See **TODO**
below for what's actually next.

### Removed
- **Merits & Flaws** — ripped out 2026-06-15 (the old system bundled
  balance-wrecking Charm rewrites), and **RESTORED 2026-07-30** as the single
  centralized `merits_and_flaws_calc` decision 0011 called for. This entry stays as
  history: the reason they were removed is the reason no caller may name a Merit id.
  See `docs/status/merits-flaws.md` and the TODO.

### Deferred (still open, just not now)
- `chargen_budgets.json`/`costs_bonus.json`/`costs_xp.json` overrides beyond
  what's authored — optional, loader falls back to model defaults.
- A per-session XP-grant ledger and the "training time" rule
  (`XpEntry.training_complete` is a dormant hook); state-reconciliation of
  hand-edited current-vs-snapshot drift (the read-only lock guards normal use).

### Permanently out of scope
Recorded as decision records, not restated here — read them before proposing any of it:
**no combat/attack derivation** (`0008`), **no dice rolling of any kind** (`0009`), and
**the Fair Folk** (`0010`).

## TODO
**Done:** M&F removal, repeatable Ox-Body, Nature dropdown, Caste info box,
editable custom weapons/armor, magical materials, Craft as per-focus Abilities,
chargen BP-spend log, free background/equipment editing on the XP tab, the
in-play tracker, the multi-splat engine (P0-P4), tier-gated cross-splat Martial Arts,
the picker's three-page Abilities/Martial Arts/Spells split, GM mode + the ST
reference screen, **all five non-Solar Exalt splats** (Dragon-Blooded, Abyssal, Lunar,
Alchemical, Sidereal — data, engine and UI, each browser-verified), the Cult of the
Illuminated Solar origin, the five Solar castebooks, the **four Outcaste-book
Dragon-Blooded origins** (Lookshy, Forest Witches, Lost Eggs, Pirates — with the new
`upbringing` axis), the **five Aspect Books' Chapter Six** (87 Charms, Jade Mountain
Style, breadth prerequisites and gear), and the **canonical Charm-pick
enumeration** (both halves — see `docs/status/engine-and-ui.md`), and the **Abyssal
Moonshadow's half of the generalist rule** (2026-07-29, from `images/Abyssal/Traits/
145-146.png` — pure data, no new code; see `docs/status/engine-and-ui.md`), and
**Thaumaturgy end to end** (engine + the ST Options tab, the picker's Thaumaturgy
page, the sheet panel and the XP-ledger labels — `docs/status/thaumaturgy.md`).

**Also done (2026-07-29):** **user-authored custom content**, all five phases,
browser-verified — the `custom/` library merged over the book data (non-fatally; book
data errors stay fatal), the `/custom` authoring page and builder tab, the ✎/⚠
provenance markers, and saves that carry the homebrew they depend on.
`docs/status/custom-content.md`. Two additive model fields came out of it, both
homebrew-only with no printed use: `CharmCost.health_type` and
`Charm.extra_min_attributes`.

**Next:**
- **Dragon-Blooded numina / the Mist aspect** — the ONE piece of the Outcaste book
  left unauthored (deliberate, human's call 2026-07-29: "add it to the TODO, don't add
  it anywhere in the code"). **Blocked on pages.** The Forest Witch summary (p.133)
  gives Mist as an aspect with NO Aspect Abilities whose power is "one numen effect per
  point of Essence"; a numen must buy Cult • or Cult ••, replaces one Charm with
  Dematerialize, and reduces Temperance by one dot if it has a blight or affliction
  (p.132). The numen effect list itself is on **p.118**, which is not in
  `images/Dragonblooded/`, and the Forest Witch text also points at *Games of Divinity*
  p.127 and *Exalted: The Lunars* p.98 for Cult. Author nothing until those land.
- **Thaumaturgy — DONE (2026-07-29), engine and UI.** Kept here rather than only in
  Done because its rulings are load-bearing for the mortal splats. It is **NOT a
  splat**: a cross-splat capability layer any character except the Fair Folk can hold
  (Ghosts hold it but may never use it), so it sits on all six shipped splats' sheets.
  `docs/status/thaumaturgy.md`. Source COMPLETE. Shipped: catalogue, models, cost
  ladder, purchase enumeration, BP breakdown, chargen Occult gates, snapshot freeze,
  XP advancement + audit, the **ST Options tab**, the picker's **Thaumaturgy page**
  (four sub-tabs), the sheet panel and the XP-ledger labels. **Browser-verified
  2026-07-29** (clicked through, no notes).
  **No open rules questions.** "Magic for Everyone" (p.115) shipped as a toggleable
  table setting on `Character.house_rules` (frozen into the ChargenSnapshot).
  **`HouseRules` is the home for EVERY Storyteller toggle**, not just thaumaturgy's:
  it also holds the two optional p.113 chargen caps and the Eclipse/Moonshadow chargen
  permission, which **moved off `Character.st_foreign_charms`** (read it via
  `validate.foreign_charms_permitted`; a legacy top-level key is migrated forward on
  load). Fields are marked TABLE-WIDE or PER-CHARACTER **in comments only** — a
  party-wide "apply to all" control may only touch the former, and
  `tests/test_thaumaturgy_ui.py` pins `view._HOUSE_RULES` to the model so the tab's
  scope table cannot drift from it. Its "(along with any appropriate specialties)"
  clause is DELIBERATELY unimplemented (human could not determine what it means,
  2026-07-29) — do not guess at it.
  Science costs are RESOLVED (5/7 BP, 7/current×6 XP) but are the **only value in the
  build with no page behind it** — the printed tables omit Sciences entirely, a
  printing error Grabowski cleared up later, rate supplied by the human 2026-07-29.
  Also recorded there: the p.116 Step Four errata ("5 in addition to recorded
  **Knowledge**", not Inheritance) — read it before building mortal chargen or the
  Knowledge BP pool.
- **The four remaining non-Exalt splats** — **Godblooded, Ghosts, Dragon-Kings,
  Mountain Folk**. Separate splats scattered across different books (human,
  2026-07-29); **all four are blocked on source material** — none exists yet — per the
  never-author-from-memory rule. Order is the human's call. See **Next Exalt Types**.
  Mortals + Heroic Mortals are DONE (2026-07-30) and were the exception to the
  "six separate splats" note: p.103 runs one procedure through both, so they shipped as
  one splat with a `heroic`/`ordinary` origin axis. Do not generalise that to the other
  four. `docs/status/mortals.md`.
- **Merits & Flaws — DONE 2026-07-30, ahead of schedule.** Decision 0011's centralized
  `merits_and_flaws_calc` exists (`exalted_builder/engine/merits.py`) and **99 M&F are
  authored**: the 11 Thaumaturgy ones (PG pp.120-122) and all 88 of the general chapter
  (pp.16-41). It was pulled forward of the remaining non-Exalt splats because mortals
  shipped with no route to magic at all, and that route runs entirely through Merits.
  `docs/status/merits-flaws.md` is the full record — **read it before touching M&F.**
  The one rule that must not be broken: **no module outside `engine/merits.py` may name
  a Merit id**; callers read `MeritEffects` fields, and
  `test_no_module_outside_engine_merits_names_a_merit_id` enforces it by grepping the
  package. If it fails, add a FIELD to MeritEffects — never an allowlist.
- **Mortal magic access — DONE.** Essence Awareness unlocks the pool, Essence Mastery
  unlocks it fully and opens Terrestrial Martial Arts (minus Spirit Walking AND minus
  the Immaculate Dragon styles) plus Terrestrial Sorcery, and raises `essence_cap` 1→3.

**Next (2026-07-30, after lunch):**
- **Model the M&F mechanical effects — IN PROGRESS, step by step.** **The triage is
  DONE** and `docs/status/merits-flaws-triage.md` is the record: all 94 unmodelled
  entries read in full and sorted, the human's rulings on the boundary recorded at the
  top. **26 are implementable, in 8 mechanisms** (A1-A7 plus trait prerequisites); the
  31 dice-only and 32 narrative entries are **skipped permanently** — not deferred, not
  worth revisiting. **Read the triage doc before touching any of this**, especially the
  RULINGS section: Callous is the one sanctioned exception to decision 0005, forfeit
  Flaws are a budget delta and nothing more, and Limit/Paradox maxima are the constant
  10 rather than something to derive.
  **A1-A5 are COMPLETE (2026-07-30).** A1: all four trait-forfeit Flaws
  (Callous, Unskilled, Weak-Willed, Diminished Attributes), engine and chargen UI —
  `validate.effective_budgets` and `validate.attribute_pool_assignment` are the hooks.
  A2: health levels (Large Size, Small), which the in-play damage tracker picked up for
  free. A3: trait caps (Legendary Attribute, True Paragon, Disfigured, Weak Essence) —
  the first cluster to span chargen AND advancement, plus Weak Essence's withheld-Charm
  credits (`validate.withheld_charm_credits`, redeemed through the `charms_withheld` XP
  target so the audit does not re-price them). A4: point-cost modifiers (Brigid's Heir,
  Prodigy) — `merits.adjust_charm_cost`/`adjust_spell_cost` are the read, since the
  sorcery-line exemption makes it per-Charm rather than a flat multiplier.
  **None is browser-verified, and A4 carries two open rules questions** (is Terrestrial
  Circle Sorcery itself exempt; how does an odd spell cost halve) — both recorded in
  `docs/status/merits-flaws-triage.md`.
  Three engine functions now take an OPTIONAL `ruleset` so they can see Merits —
  `derive.soak`, `derive.willpower`, `derive.health_track`. Follow that shape rather
  than threading MeritEffects through call sites.
  A5: Essence-pool shape — **Legendary Breeding is the Breeding RATING it grants**
  (the rating-6 row now exists in `data/exalts.json`; its printed +6/+11 motes ARE that
  row, not an addition on top of the Breeding 5 it requires), and **Beacon of Power
  merges the pools after every other effect**. `DerivedTraits.essence_single_pool`
  carries the shape so a sheet can tell "Personal 0 by rule" from "no Essence at all",
  and `MeritFlaw.barred_castes` is A4's splat-bar precedent one level down.
  **Next cluster is A6** (Background budget and rating restrictions), then
  A7 in the order the triage doc gives. Do them one at a time —
  the human's instruction, and each is architecturally small but touches a different
  derivation.
- **Browser click-through of Merits & Flaws** — NOT done, and it is the highest-value
  thing outstanding. The Mortal pass earned its keep this morning: it found three bugs
  1,200 tests missed, and a further four surfaced during the M&F work (a picker crash
  that blanked two tabs, an XP tab taken down by a shadowed local, a sheet panel crushed
  invisible by a `no-wrap` row, and a sheet block with no rules text). Assume more.
- **Two-sided entries and the editor's splat filter — DONE 2026-07-31.** Both gaps
  closed; see `docs/status/merits-flaws.md`. The side of a `kind: "either"` entry is
  now selectable in the editor AND on the XP tab, and `validate.merit_available_to` is
  the one predicate both Merit dropdowns filter on. Three things it turned up on the
  way: `drop_merit` branched on the catalogue's `kind` (so buying off an either-entry
  held as a Flaw PAID the character), `costs.merit_cost` could not see `cost_by_kind`
  (so Eternal Vow cost 0 XP in play, and it now delegates to `validate.merit_points`
  so the XP and chargen paths cannot disagree about a price), and two-sided entries
  could not be gained in play AT ALL — `buy_merit` demanded `kind == "merit"` and
  raised. Not browser-verified.
- **The Advantages tab — AGREED 2026-07-31, PLAN ONLY, do not start yet.** Backgrounds
  and M&F move off the Edit⇄XP split onto one top-level both-sides tab (the Charms/Combos
  shape), deleting the two duplicate implementations of each. Full plan, the human's four
  rulings and the touch points: `docs/status/advantages-tab.md`. **Blocked behind the
  unpushed desktop A6**, which lives in exactly the code this relocates.
- **The XP tab's tier/points field is one free-text input doing double duty** — a tier
  key for a menu-priced entry, a point value for a variable-cost one. Works; crude.
- **The four remaining non-Exalt splats** — Godblooded, Ghosts, Dragon-Kings, Mountain
  Folk. All blocked on source material; order is the human's call. Note PG p.114 gives a
  hook for the first: "mortals that exceed Essence 3 become gods, in the same way the
  God-Blooded do." Prodigy's "2- OR 4-PT. FOR DRAGON KINGS OR GOD-BLOODED" cost override
  is deliberately unauthored and should be added with those splats.

Full multi-splat plan: `~/.claude/plans/should-we-plan-out-encapsulated-crab.md`.
DB chargen numbers as verified from source pages: [[db-chargen-findings]].
