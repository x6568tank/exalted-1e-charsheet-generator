# Exalted 1E Character Builder — Project Guide

This file is the **durable operating guide**: the rules, constraints and pointers that
stay true across sessions. It is an INDEX, not a build log. The record of what was built
and what it taught us lives in `docs/`; do not re-accumulate it here.

### 👉 START HERE → `docs/status/handoff.md`
Current state, open threads and flagged items. **Rewritten each session.**

## What this is
A character creator / validator for **Exalted First Edition (1e)** — chargen, point
validation, XP advancement, a character-sheet view and a generated PDF sheet. Scope is
deliberately smaller than EdExalted (2e/2.5e only); **1e is unserved, which is the
entire point.** Eleven splats ship, each browser-verified; the catalogue is complete.
It is a **character builder and validator, not a chronicle simulator.**

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
- **Run the `preflight` skill before booking browser time.** Project skills:
  `preflight`, `close-out`, `add-splat`, `run-server`.

### 📝 The comment standard → `docs/comment-standard.md`
A docstring carries **input, output, and how it gets from one to the other. Nothing
else** (human, 2026-08-17) — reasoning and war stories go in the commit message and
`docs/status/`. Three things STAY: **page citations**, **⚠ records of behavioural traps**,
and the contract itself. Which packages have had the pass, and how to run one safely, are
in the file.

### The house bug, and the lessons → `docs/lessons.md`
**The house bug: a rule that IS implemented, sitting where it does not run when it
matters.** Three species, all recurring — (1) wired to the wrong phase; (2) zero read
sites and still looks healthy, because something else does its job by accident; (3) the
switch is player-editable to a value that switches it off. **Test the buy path, not the
effect. Correct behaviour in the case you tested is not evidence the mechanism exists. A
discriminator must be a field nothing on the screen can edit.**

The mechanical sweep for all three is `docs/delegated-authoring.md` — **read it before
delegating a splat to a cheap model, and run its four checks before booking browser
time.**

`docs/lessons.md` also carries the ~25 one-liners that generalise past where they
happened — sweeps and gap lists, engine code, tests, cross-shell parity, Qt widgets.
**Read it before a sweep, a parity audit, or any change you expect tests to cover.**

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

Three directives that are description-in-disguise, so they live here:
- UI assets go in `assets/`.
- `sources/` (rulebook PDFs) and `images/` (rulebook page images) are gitignored and
  are never committed — so they do NOT travel with a clone, and authoring new rules data
  on a second machine needs those files synced out-of-band.
- **⚠ Every `images/…` path written in this file or in `docs/` is a HINT, not a fact.**
  The human's machines organise `images/` differently — the Dragon-Kings pages are
  `images/Mortals/Dragon Kings/` on the laptop and `images/Non-Exalts/Dragon Kings/` on
  the main PC, both correct. A recorded path being absent does NOT mean the source is
  missing, and two docs disagreeing about one is not a defect to reconcile. **Look for
  the pages before concluding they are unavailable, and never "fix" a path to match the
  machine you happen to be on.**

## Decisions already made → `docs/decisions/`
**Do not relitigate any of these without the human reopening it.** One numbered record
per closed decision, each with the alternatives that were rejected and what the choice
costs — read the record before proposing anything that contradicts it.
`docs/decisions/README.md` is the index.

| # | Decision |
|---|---|
| 0001 | **1e only, never 2e** — also the source of the never-author-from-memory rule above |
| 0002 | **Data-driven rules, pure engine, disposable UI** — the rulebook is JSON; the engine is pure functions |
| 0003 | Current state is canonical; the engine computes the point accounting |
| 0004 | Chargen and advancement are different shapes (snapshot + append-only XP log) |
| 0005 | Willpower's Virtue component is pinned at lock |
| 0006 | Play-state is validation-isolated — never in chargen, the XP audit or a permanent derivation |
| 0007 | **Ids for invariant content, inline copies for variable** — Charms/spells by id; weapons/armor inline copies |
| 0008 | No combat/attack derivation |
| 0009 | No dice rolling, ever — broader than 0008; do not propose it |
| 0010 | The Fair Folk are permanently out of scope |
| 0011 | Merits & Flaws return as ONE centralized calc, never the old per-file hooks |
| 0012 | Homebrew: the `custom/` library is the store, saves carry copies, homebrew errors are non-fatal |
| 0013 | **Edit and XP are ONE surface** — the dot track is the buy control; there is no XP tab |
| 0014 | Essence is XP-purchasable to the splat cap; the age chart is gone |
| 0015 | **Exalt tiers are RANKED** — Terrestrial < Celestial < Solar; a splat reaches its own tier and every tier below, never up |
| 0016 | **Base dice pools are in scope; resolution is not** — narrows 0008, leaves 0009 untouched |
| 0017 | **Artifacts have acquisition CHANNELS** — the Artifact Background is pre-game (core p.342, budgeted); cash is in-play (M&C pp.122-125). ⚠ A **third** joined 2026-08-13/14 and is not yet its own record: a plot device printing "(ARTIFACT N/A)" is bought with the **Legendary Artifact** 10-pt Merit and charged to no budget — the standing answer for the shape, still confirm each. `docs/status/book-of-three-circles.md` |
| 0018 | **The Qt port is committed** — a PySide6 native app alongside the NiceGUI webapp; the plan doc becomes the build record |

**Permanently out of scope** — 0008, 0009 and 0010 (no combat/attack derivation, no dice
rolling of any kind, no Fair Folk); all three are closed. ⚠ 0008's boundary was NARROWED
by 0016: computing a BASE dice pool is in scope — read 0016 before citing 0008 against a
pool calculation.

### Standing bars that are not numbered decisions
- **⚠ Backwards compatibility with old saves is NOT a concern** (human, 2026-08-22:
  *"there's no backwards compatability to really worry about"*). The build is months
  old and the saves are the human's own. **Do not write a migration, a schema version
  or a compat shim without asking** — and do not carry "this old save may be damaged"
  as an open item, which is what prompted the ruling.
- **⚠️ Training times are almost certainly NEVER being added** (human, 2026-07-30:
  *"that goes out of the dumb-tracker scope"*). Hedged rather than closed, so treat it as
  a no unless they reopen it — **do not propose it, plan around it, or offer it as a
  follow-up.** `XpEntry.training_complete` is a dormant hook. Four printed rules hang off
  it and ship deliberately incomplete (Weak Essence, Brigid's Heir, Death's Taint's
  Harrowing, the elder-Exalt ceilings); that is accepted, not a gap. Anything needing the
  passage of in-game time is out for the same reason `PlayState` is a manual tracker.
- **Deferred INDEFINITELY, and none is a gap** — the **Mist numina / Mist aspect**
  (`docs/status/mist-numina.md`: there is no numen effect LIST to author), **Cult
  Abyssals** (`docs/status/illuminated.md`: 56 Charms needing human-approved mappings)
  and **Haltan pets** (Scavenger Sons p.28 — a bonus-point rule with no origin axis to
  hang it on). A sweep that lists any of them as unauthored is counting a deferral as an
  oversight. **Do not offer them as follow-ups.**
- **The Qt port** — **COMMITTED as decision 0018 (2026-08-20)**, and ⚠ **FEATURE-COMPLETE
  (2026-08-27)**: a PySide6 native app offered alongside the NiceGUI webapp, every tab
  plus the **Party / ST window** shipped and human-clicked. Run it with
  `python -m exalted_builder.qt [path]`; the code is `exalted_builder/qt/`.
  **⚠ `docs/plans/qt-port.md` opens with STANDING RULES FOR THE PORT — read that section
  before touching `qt/`, rather than re-deriving any of it here.** In one line each, what
  is in there: the ONE tab layout and its **three written exceptions** (Play,
  Identity+Traits, the Party tab) · **the gap list was a lower bound all SEVEN times**, so
  audit each tab against its `ui/` counterpart, click it, and render it offscreen and
  LOOK · **an ancestor stylesheet beats a set palette** · **a defect one widget class over
  is still yours** · `clear_layout`, the deliberate tab-set difference, and the settled
  dark theme. What each milestone contains and every trap it cost is in the same file.

## Stack
- Python + pydantic v2 + pytest. Frontend: **NiceGUI** (chosen over Reflex), the optional
  `[ui]` extra. A JS graph library (Cytoscape/d3) is still planned ONLY for the
  charm-tree picker.
- Venv is `.venv/`; tests: `.venv/bin/python -m pytest`.
- **Git remote:** `origin` → `github.com/x6568tank/exalted-1e-charsheet-generator`, tracking `main`.
- **A `v*` tag builds FOUR assets** — 2 OSes x 2 products (webapp + native), one release,
  extras per matrix row. ⚠ **A build that is not in the matrix does not exist to a tag:**
  the native spec shipped and CI kept building only the webapp, so a tag would have
  published a release that looked complete with no native app on it. `pack/BUILD.md`.
- Shipped **1.0.0** on 2026-08-17.

## Splats — all eleven shipped and browser-verified

| Splat | Colour | Detail |
|---|---|---|
| Solar (+ castebooks) | Amber/gold (default) | `docs/status/solar-castebooks.md` |
| Solar alt-origin: Cult of the Illuminated | — | `docs/status/illuminated.md` |
| Dragon-Blooded (+ Outcaste origins, Aspect Books) | Vermillion | `dragonblooded-origins.md`, `dragonblooded-aspect-books.md` |
| Abyssal | Black on ash | `docs/status/engine-and-ui.md` |
| Lunar | Moonsilver `slate` | `docs/status/lunar.md` |
| Sidereal | Purple | `docs/status/sidereal.md` |
| Alchemical | Brass | `docs/status/alchemical.md` |
| Mortals + Heroic Mortals | Muddy `stone` | `docs/status/mortals.md` |
| Ghosts | Grave-mould `zinc` | `docs/status/ghosts.md` |
| Godblooded | Celestial `teal` | `docs/status/godblooded.md` |
| Dragon-Kings | Jade `emerald` | `docs/status/dragon-kings.md` |
| Mountain Folk | Geothermal `cyan` | `docs/status/mountain-folk.md` |
| ~~Fair Folk / Fae~~ | — | **NEVER — permanently out of scope** (decision 0010) |

The non-Exalt palettes past Mortal are placeholders — whether the rest share the Mortal
`stone` or each get their own is UNDECIDED.

**"Mortals" is shorthand, not one splat** (human, 2026-07-29): the non-Exalts are
separate splats in separate books, each with its own budgets, Charm economy and shape.
Mortals + Heroic Mortals turned out to be ONE splat with two origins (core p.103 runs a
single procedure through both) — that revision says nothing about the others.

Work on a new splat starts only once its rulebook pages land in `images/` — never author
from memory. **Read `docs/adding-a-splat.md` before estimating one**: it records what
each finished splat needed BEYOND data (Charm Slots, Colleges, Attribute-keyed Charms,
the `origin` / `upbringing` axes) and the traps, `highest_magic_circle_id` chief among
them.

## The test suite → `docs/testing.md`
**3,181 passing, 1 skipped** (2026-09-03, main PC). ⚠ **The count is machine-dependent by
DOZENS of tests, and by 522 more where the optional `qt` extra is missing** — a lower
number is that working, not tests going missing. **Do not "reconcile" two machines'
numbers.** ⚠ **The SKIP is conditional and healthy, and one M&F test is machine-dependent
in OUTCOME** — pass-with-deferrals on some machines, a real failure on others, neither a
regression. `docs/testing.md` has both by name, how to read a run's numbers honestly, and
the Qt-font trap that looks like a machine crash.

## The record → `docs/status/`
One file per topic. **Read the relevant file before touching that area.** The rows below
are pointers only; the traps and history live in the files.

| Area | File |
|---|---|
| **Session handoff — rewritten each session** | `status/handoff.md` |
| How it works: module boundaries, lifecycle, invariants | `ARCHITECTURE.md` |
| Why: closed decisions, one record each | `decisions/` |
| The house bug's three species + every lesson that generalises | `lessons.md` |
| The comment standard, and which packages have had the pass | `comment-standard.md` |
| The suite — the count, why it moves per machine, the two healthy oddities | `testing.md` |
| The rules data — conventions, what the loader checks | `content.md` |
| Implementing a splat — honest cost, from the eleven done | `adding-a-splat.md` |
| Delegating a splat to a cheap model — the four-check audit | `delegated-authoring.md` |
| How `source.book` is written, and why it rots | `source-attribution.md` |
| Models, loader, persistence, `engine/`, NiceGUI UI | `status/engine-and-ui.md` |
| Core data files, Charm counts, `tools/` | `status/data-and-tooling.md` |
| The 1.0 catalogue sweep — six delegated batches, the `sources/` extraction pipeline and its glyph ciphers | `status/catalogue-sweep.md` |
| The content gap — CLOSED 2026-08-14, all 647 discovery rows resolved | `status/content-gap-retriage.md` |
| Phase-1 scan — the five never-opened books, DONE 2026-08-15; 22 gear rows | `status/phase-1-scan.md` |
| Phase-2 scan — the two scan-only books, DONE 2026-08-15; **every book in `sources/` has now been opened** | `status/phase-2-scan.md` |
| Book of Three Circles — spells, artifacts, the Merit-gated plot devices | `status/book-of-three-circles.md` |
| Corebook Wonders — Hearthstones, Greater Wonders, the Hearthstone allowance | `status/corebook-wonders.md` |
| Rated artifacts — the Artifact budget, dual-nature devices, the corebook default | `status/rated-artifacts.md` |
| 1E artifact backlog — the discovery layer (parse method + per-book page lists) | `status/artifact-backlog.md` |
| Martial-arts STYLE entity — 21 of 22 authored, tiers, `Charm.ma_tier` access | `status/martial-arts-styles.md` |
| Merits & Flaws — the centralized calc (decision 0011), all 100 authored | `status/merits-flaws.md` |
| M&F mechanical-effect triage — what was modelled, what was skipped and why | `status/merits-flaws-triage.md` |
| Backgrounds — per-splat catalogues, the dot ladder, the numeric rules | `status/backgrounds.md` |
| Trait reference text — the ⓘ beside every dot row; ⚠ the three families print DIFFERENT shapes, and Abilities have no per-Ability ladder | `status/trait-descriptions.md` |
| Thaumaturgy — cross-splat Arts/Sciences/Rituals/Formulas | `status/thaumaturgy.md` |
| Custom content — user-authored Charms/styles/spells/**rituals**/gear, the `/custom` page | `status/custom-content.md` |
| Dice pools — decision 0016, the Play-tab sidebar | `status/dice-pools.md` |
| Elder Exalts — Essence to the splat cap, the p.259 downtime calculator | `status/elder-exalts.md` |
| Edit⇄XP merge — one trait surface both sides of the lock | `status/edit-xp-merge.md` |
| Advantages tab — Backgrounds + M&F on one both-sides tab | `status/advantages-tab.md` |
| Gear tab, inventory & shop — everything owned on one surface | `status/gear-and-inventory.md` |
| Catalogue picker dialogs — the shared `ui/catalogue.py` dialog | `status/catalogue-dialogs.md` |
| Printable / PDF sheet — a real generated PDF, not a print stylesheet | `status/printable-sheet.md` |
| Adversary roster — GM-mode extras/beasts/NPCs | `status/adversary-roster.md` |
| The `engine/validate/` split — 15 modules, `validate.X` is the ONE public path | `plans/validate-refactor.md` |
| The Qt port — decision 0018; the build record. **FEATURE-COMPLETE 2026-08-27**: milestones 1–6, the **ST Options**, **Custom** and **Combos** tabs and the **Party / ST window**, all human-clicked (the Party window 2026-08-28, after its roster gained adversary cards). Milestone 5 SETTLES the one layout; milestone 6, Identity+Traits and the Party tab are its three written exceptions | `plans/qt-port.md` |
| Variant-menu Charms — the generic `variant_purchases` list, `Charm.variants_unique`, and why Ox-Body and the Gifts were deliberately NOT migrated onto it | `plans/variant-menu-charms.md` |
| Core Charm re-transcription — the 220 descriptions, the 32 corrected values, the offset trap | `status/core-charm-retranscription.md` |
| The 265 delegated spells re-transcribed — restored variant-spell mentions, a truncated entry, two resistance-direction bugs | `status/spell-retranscription.md` |

**State of the world:** foundation, splats, engine and UI are done and browser-verified;
a character can be put on paper. **The catalogue is COMPLETE (2026-08-14):** Charms
1,921 · spells 306 · artifacts 330 · weapons 112 · armour 28 · thaumaturgy 4 Arts /
4 Sciences / 30 formulas / 11 rituals. **Nothing is page-blocked**, and as of 2026-08-15
**every book in `sources/` has been opened** (the phase-1 and phase-2 scans). Everything
else unauthored is deliberately deferred (see **Standing bars**).

⚠ **COMPLETE means every entry EXISTS, not that every entry is RIGHT.** The Core Charms
were all present and all counted, and their descriptions were still an order of magnitude
too thin — four of them describing a rule the page does not contain — because the
delegation brief capped description length. Re-transcribed 2026-09-01, along with 32 wrong
minimums/costs/types: `status/core-charm-retranscription.md`. The **265 non-Core spells**
authored under the same cap were re-transcribed 2026-09-03 (116 of 265 changed):
`status/spell-retranscription.md`. ⚠ The **artifacts were ruled
FINE and their cap stays** (human, 2026-09-01) — do not re-propose that audit. Do not read
a catalogue count as a quality signal.

⚠ **`source.book` is a zero-read-site field and it ROTS.** Two Charms were still
attributed to `Core` carrying **Abyssals** page numbers — the same fingerprint as the 233
mis-attributed Abyssal Charms the 1.0 sweep caught. The tell is cheap (a citation whose
page does not contain the Charm) and **nothing runs it**. `status/catalogue-sweep.md`,
`status/core-charm-retranscription.md`.

⚠ **One known content gap remains: Backgrounds in the scan-only splat books.** Human's
ruling 2026-08-15: Backgrounds are scattered across mainly the SPLAT BOOKS, and M&F are
"pretty much all Player's Guide", so M&F are not a reason to open another book. Roughly
**1,800 pages** of pure scan (Lunars, Dragon-Blooded, Sidereals, five Caste Books, five
Aspect Books); method is phase 2's. ⚠ Backgrounds are the record type with **no discovery
index to diff against**, and `source` is missing on **63/63** of them — backfilling that
provenance first is what makes the sweep finite.

⚠ Still unswept by any method: Merits, Backgrounds and prose-described artifacts in the
eight transcribed books, and everything in the scan-only books (Sidereals,
Dragon-Blooded, castebooks, Lunars, Abyssals).

## Rulings that bite when touched
Each is written up where it landed; these are the ones that catch people mid-task.

- **A specialty is an INSTANCE, not a rated trait** — you take the same one again rather
  than raising it, capped at **3 per Ability**. Legacy rated specialties split on load.
  Also: **Crafts and Colleges can be reduced** (a usability escape hatch, not a printed
  rule), and **Nature freezes at the lock**. (`status/edit-xp-merge.md`)
- **Eight chargen choices are frozen once locked** — Favoured picks, caste, Exalt type,
  origin, upbringing, camp, Calling, flawed Virtue. Greyed but readable.
- **No module outside `engine/merits.py` may name a Merit id** — a test greps for it; add
  a `MeritEffects` FIELD, never an allowlist. And **`derive.soak`/`willpower`/
  `health_track` and `lifecycle.lock_chargen` take an OPTIONAL `ruleset`** so they can
  see Merits — every omission is a silent wrong answer, not a TypeError.
- **`catalogue_backgrounds` is what the dropdown OFFERS; `allowed_backgrounds` is HARD
  validation.** Writing a list into the wrong one makes every free-text Background
  illegal for that splat.
- **Thaumaturgy is NOT a splat** — a cross-splat capability layer everyone but the Fair
  Folk can hold (Ghosts hold it and may never use it), so it sits on every sheet.
  **`HouseRules` is the home for EVERY Storyteller toggle**; fields are marked TABLE-WIDE
  or PER-CHARACTER **in comments only**, and a party-wide "apply to all" control may only
  touch the former. ⚠ Science costs (5/7 BP, 7/current×6 XP) are the **only value in the
  build with no page behind it** — supplied by the human 2026-07-29.
- **An `Adversary` is NOT a `Character` and must never become one** — a test asserts it.
- **Passions are a LIVE DERIVATION of the Virtues** on both sides of the lock, never
  bought with BP or XP (E:Ab p.283).
- **No character may leave creation with Essence above 5** (`essence-above-elder-chargen-cap`).

## Deferred (open, just not now)
- **The app reports no version anywhere** — no titlebar string, no About item, and
  `pyproject.toml` still says `1.0.0`. "Am I running current code?" is therefore
  unanswerable from inside the app, which is what turned a fixed bug into a long hunt
  on 2026-09-02 (`status/merits-flaws.md`). ⚠ Pair it with the launcher trap:
  `branding.install_desktop_entry()` writes `Exec=` from `sys.executable`, so the
  desktop entry PINS to the first frozen binary that ever ran and only re-points when a
  different one runs — downloading a new release to a new path changes nothing until you
  execute it directly.
- `chargen_budgets.json`/`costs_bonus.json`/`costs_xp.json` overrides beyond what's
  authored — optional, loader falls back to model defaults.
- A per-session XP-grant ledger; state-reconciliation of hand-edited
  current-vs-snapshot drift (the read-only lock guards normal use).
- The comment pass on `ui/`, `models/` and `engine/` outside validate
  (`docs/comment-standard.md`).

## Background
- **Merits & Flaws were ripped out 2026-06-15** (the old system bundled balance-wrecking
  Charm rewrites) and **restored 2026-07-30** as decision 0011's single centralized calc.
  The reason they were removed is the reason no caller may name a Merit id.
- `CharmCost.health_type` was homebrew-only with no printed use when created, but
  acquired its first printed consumer on 2026-08-01 — Stolen Wax Discipline (E:Ab
  p.238), "5 motes, one lethal health level". Don't treat it as homebrew-only.
- Full multi-splat plan: `~/.claude/plans/should-we-plan-out-encapsulated-crab.md`.
- DB chargen numbers as verified from source pages: [[db-chargen-findings]].
