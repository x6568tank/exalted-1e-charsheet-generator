# Exalted 1E Character Builder — Project Guide

## What this is
A character creator / validator for **Exalted First Edition (1e)** — character
generation, point validation, and XP advancement, with a character-sheet view.
Scope is deliberately smaller than EdExalted (which is 2e/2.5e only); **1e is
unserved, which is the entire point.** All six **Exalt** splats are done (Solar,
Dragon-Blooded, Abyssal, Lunar, Sidereal, Alchemical) — chargen, Charms, XP and UI,
each browser-verified. Five **non-Exalt** splats have shipped since — **Mortals +
Heroic Mortals** (2026-07-30; one splat, two origins), **Ghosts** (2026-08-01),
**Godblooded** (2026-08-02; Ghost-Blooded, Half-Caste and Fae-Blooded heritages),
**Dragon-Kings** (2026-08-05; the ten Paths of Prehuman Mastery) and **Mountain Folk**
(2026-08-07; the Enlightenment origin axis, the five-Pattern Charm economy) — each
browser-verified; see **Status** and `docs/status/`.

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

## Splats

### Exalt splats — all six shipped
Dragon-Blooded, Abyssal, Lunar (2026-07-22), Alchemical (2026-07-23) and Sidereal
(2026-07-24) all shipped complete — chargen, Charms, XP/advancement and UI, each
clicked through in a browser. Per-splat detail lives in the **Status** table below.

### Non-Exalt splats

| Splat | Source images | Status |
|---|---|---|
| Mortals + Heroic Mortals | `images/Mortals/Mortals & Heroic Mortals/` | **DONE 2026-07-30**, browser-verified 2026-08-01 — one splat, two origins (the `heroic`/`ordinary` axis); no Charms, Essence pinned at 1, magic via M&F. `docs/status/mortals.md` |
| Ghosts | `images/Non-Exalts/Ghosts/` | **DONE 2026-08-01**, browser-verified same day — Virtue-keyed Arcanoi, Fetters + Passions, two chargen axes, Terrestrial MA + Fighter in Life. `docs/status/ghosts.md` |
| Godblooded | `images/Non-Exalts/Godblooded/` | **DONE 2026-08-02** — Ghost-Blooded + Half-Caste (parent-Exalt origin axis, heritage Charm bars, Inheritance→BP pool) + Fae-Blooded (no Charms, no spells, `Ess×8`, Noble/Commoner origin, 23 glamour Merits), all browser-verified. `docs/status/godblooded.md` |
| Dragon-Kings | `images/Mortals/Dragon Kings/` | **DONE 2026-08-05** — modern/ancient origins; the ten Paths of Prehuman Mastery (a rated subsystem, 60 powers); four Breeds; single Essence pool; Essence-gated trait ceilings; Terrestrial sorcery. **2026-08-06:** breed attribute modifiers stack ON TOP of a stored 5, but each EFFECTIVE dot above 5 is BP-bought at the attribute rate (the same-day "free past 5" note was a misunderstanding and is reversed); stored past 5 is the XP gate. `docs/status/dragon-kings.md` |
| Mountain Folk | `images/Mortals/Mountain Folk/` | **DONE 2026-08-07, browser-verified** — the tenth splat, the last non-Exalt. The Enlightenment origin axis (Enlightened/Unenlightened — attribute pools, a two-pool Ability budget, per-caste Background dots, trait ceilings, Essence/Willpower caps); the five-Pattern Charm economy (94 Charms gated on Minimum Essence only, a new Enchantment Charm type); the Great Geas as a Divergence Limit track + reference panel; banned Backgrounds omitted from the catalog; three Darkbrood adversaries. `docs/status/mountain-folk.md` |
| ~~Fair Folk / Fae~~ | — | **NEVER — permanently out of scope** (decision 0010) |

**"Mortals" is shorthand, not one splat** (human, 2026-07-29): the non-Exalts are six
different splats scattered across different books, each needing its own sources and
chargen work. Mortals + Heroic Mortals turned out to be ONE splat with two origins
(core p.103 runs a single procedure through both, varying only 6/4/3·22 vs 4/3/3·16).
That revision says nothing about the others — treat each as its own splat with its own
budgets, Charm economy and shape until the pages say otherwise.

Work on a splat starts only once its rulebook images land in `images/<ExaltName>/` —
never author data from memory (see **Workflow expectations**). **Read
`docs/adding-a-splat.md` before estimating one**: it records what each finished splat
needed BEYOND data (Charm Slots, Colleges, Attribute-keyed Charms, the `origin` /
`upbringing` axes) and the traps, `highest_magic_circle_id` chief among them.

### Splat colour scheme (UI theming)

| Splat | Color | Status |
|---|---|---|
| Solar | Amber/Gold (default) | DONE |
| Abyssal | Black on ash | DONE |
| Dragon-Blooded | Vermillion | DONE |
| Lunar | Moonsilver blue (`slate`) | DONE |
| Sidereal | Purple | DONE |
| Alchemical | Brass | DONE |
| Mortal | Muddy brown (`stone`) | DONE — the deliberately dullest palette of the shipped splats |
| Ghost | Pale grey-green (`zinc`) | DONE — grave-mould, pushed off both Abyssal ash and Mortal earth, the two it could be confused with |
| God-Blooded | Pale celestial blue-grey (`teal`) | DONE — a placeholder; whether the remaining non-Exalts share the Mortal `stone` or each get their own is UNDECIDED |
| Dragon-Kings | Jade/emerald (`emerald`) | DONE — the living green of their vegetative technology |
| Mountain Folk | Geothermal jade-cyan (`cyan`) | DONE — the blue-green of deep jade lit by Manse Essence, off the four palettes it could be swallowed by (God-Blooded teal, DK emerald, Ghost zinc, Lunar slate). Placeholder — whether the remaining non-Exalts share the Mortal `stone` or each get their own is still UNDECIDED |

### Dragon-Blooded sub-sources
The Outcaste book's four origins and all five Aspect Books shipped 2026-07-29
(`docs/status/dragonblooded-origins.md`, `dragonblooded-aspect-books.md`). The ONE
piece of the Outcaste book left unauthored is the numina/Mist aspect — deliberate
(human's call 2026-07-29) and blocked on pages; see **TODO → Blocked**.

### Merits & Flaws are back
Pulled forward of the remaining non-Exalt splats because mortals shipped with no route
to magic, and that route runs through Merits. They returned as decision 0011 demanded:
ONE centralized calculation (`engine/merits.py`), never the per-file hooks that got
them ripped out. 100 entries authored. `docs/status/merits-flaws.md`.

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

Two directives that are description-in-disguise, so they live here:
- UI assets go in `assets/`.
- `sources/` (rulebook PDFs) and `images/` (rulebook page images) are gitignored and
  are never committed.
- **⚠ Every `images/…` path written in this file or in `docs/` is a HINT, not a fact.**
  Because `images/` is gitignored it never travels, and the human's machines organise
  it differently — the Dragon-Kings pages are `images/Mortals/Dragon Kings/` on the
  laptop and `images/Non-Exalts/Dragon Kings/` on the main PC, both correct. A
  recorded path being absent does NOT mean the source is missing, and two docs
  disagreeing about one is not a defect to reconcile. **Look for the pages before
  concluding they are unavailable, and never "fix" a path to match the machine you
  happen to be on.**

## Decisions already made → `docs/decisions/`
**Do not relitigate any of these without the human reopening it.** One numbered record
per closed decision, each with the alternatives that were rejected and what the choice
costs — read the record before proposing anything that contradicts it.

`docs/decisions/README.md` is the index. The ones most likely to matter mid-task:

| # | Decision |
|---|---|
| 0001 | **1e only, never 2e** — also the source of the never-author-from-memory rule below |
| 0002 | **Data-driven rules, pure engine, disposable UI** — the rulebook is JSON; the engine is pure functions |
| 0003 | Current state is canonical; the engine computes the point accounting |
| 0004 | Chargen and advancement are different shapes (snapshot + append-only XP log) |
| 0005 | Willpower's Virtue component is pinned at lock |
| 0006 | Play-state is validation-isolated — it must never enter chargen, the XP audit or a permanent derivation |
| 0007 | **Ids for invariant content, inline copies for variable** — Charms/spells by id; weapons/armor inline copies |
| 0008 | No combat/attack derivation |
| 0009 | No dice rolling, ever — broader than 0008; do not propose it |
| 0010 | The Fair Folk are permanently out of scope |
| 0011 | Merits & Flaws return as ONE centralized calc, never the old per-file hooks |
| 0012 | Homebrew: the `custom/` library is the store, saves carry copies, homebrew errors are non-fatal |
| 0013 | **Edit and XP are ONE surface** — the dot track is the buy control; there is no XP tab |
| 0014 | Essence is XP-purchasable to the splat cap; the age chart is gone |

**Permanently out of scope** — decisions 0008, 0009 and 0010 (no combat/attack
derivation, no dice rolling of any kind, no Fair Folk). Read them before proposing any
of it; all three are closed.

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

### The house bug — stated once
A rule that IS implemented, sitting where it does not run when it matters. Three M&F
instances, then mortal magic access wired to chargen only, then the XP tab's hardcoded
trait ceiling. `preflight`'s read-site audit reports single-site fields as if they were
healthy — **a single read site is as suspect as none when the read sits in the phase
that wrote it. Test the buy path, not the effect.**

**The sharpest version, from Godblooded:** a ZERO-site field can still look healthy,
because something else may be doing its job by accident. `heritage_traits.magic_track`
had no reader at all, and Ghost-Blooded behaved correctly regardless — the Ghost
catalogue holds no sorcery, so Charm access happened to produce the p.48 answer; the
Abyssal and Solar Half-Castes, whose borrowed catalogues hold both tracks, were both
broken. **Correct behaviour in the case you tested is not evidence the mechanism
exists.** The mechanical sweep for this is `docs/delegated-authoring.md`. **Run the
`preflight` skill before booking browser time.**

### Delegated authoring (cheap-model splats)
Godblooded was authored end to end by a cheap model (DeepSeek V4 Flash) and
code-reviewed afterwards. The review found four defects, all of them the house bug.
**Read `docs/delegated-authoring.md` before delegating a splat, and run its four
checks before booking browser time.** The one finding that generalises beyond
delegation is stated above: **correct behaviour is not evidence the mechanism exists.**

## Status — the record lives in `docs/status/`

The suite is green: **2,092 passing**. ⚠ **One machine-specific exception:**
`test_every_description_matches_the_source_text` fails with 46 entries on a machine
where `images/Non-Exalts/Godblooded/CH2 - Godblooded.md` is present (descriptions
summarize the fuller printed text → below 92%) and passes where it is absent (entries
defer). It is green on the laptop, red here, and is not a regression — see
`docs/status/godblooded.md`.

The detailed build log lives in `docs/status/` — one file per topic/splat. **Read the
relevant file before touching that area**; the summaries below are pointers, not the
full record.

| Area | File |
|---|---|
| **Session handoff — rewritten each session** | `docs/status/handoff.md` |
| **How it works** (module boundaries, lifecycle, invariants) | `docs/ARCHITECTURE.md` |
| **Why** (closed decisions, one record each) | `docs/decisions/` |
| **The rules data** (conventions, what the loader checks) | `docs/content.md` |
| **Implementing a splat** (honest cost, from the six done) | `docs/adding-a-splat.md` |
| **Delegating a splat to a cheap model** (the four-check audit, from the Godblooded run) | `docs/delegated-authoring.md` |
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
| **Merits & Flaws — DONE, browser-verified** (centralized calc per decision 0011; all 100 authored; every A-list mechanism; mortal magic unlock) | `docs/status/merits-flaws.md` |
| M&F mechanical-effect triage (what was modelled, what was skipped and why) | `docs/status/merits-flaws-triage.md` |
| **Rated artifacts — DONE, browser-verified, catalogue SHIPPED 2026-08-08** (individual artifacts as rated objects; the E:Ab p.131 Artifact budget; per-item Damaged Artifact + its armour-soak effect; `data/artifacts.json` — the ten Mountain Folk artifacts, GROWN TO 40 the same day across three castebook batches (`artifact.castebook-*`: Dawn/Night/Zenith pp.78-81 + Twilight/Eclipse pp.79-81 — the last on-disk artifacts, none remain unauthored) and the Hooked Daiklaves/Direlance rated gear rows, two blocked core items flagged — feeding the standalone rows' name combobox, which autofills rating, with a per-row description label; the six dual-nature devices shipped the same day — crossbows/flamecaster carry BOTH `artifact_rating` and `resources_cost`, and the player picks the funding with the Art/Res edit fields, per human's ruling 2026-08-08; **the 20 Twilight/Eclipse names are NOT yet browser-verified**) | `docs/status/rated-artifacts.md` |
| **Advantages tab — DONE, browser-verified** (Backgrounds + M&F on one both-sides tab; two duplicate panels deleted; per-row Background descriptions) | `docs/status/advantages-tab.md` |
| **Catalogue picker dialogs — DONE, browser-verified 2026-08-10** (a shared `ui/catalogue.py` dialog on every add surface — weapons/armour/artifacts/backgrounds/M&F; browse name + summary, full description collapsible, a **Custom** row; custom M&F via `MeritFlawPurchase.custom_name`, display-only with no mechanical effect; the old silent cheapest-append `add_merit` deleted) | `docs/status/catalogue-dialogs.md` |
| **1E artifact backlog — the discovery layer** (parsed from the fanmade "When Autochthon Dreams" index, 2026-08-08: 749 entries → 417 with a 1E ref, 360 unique names, per-book page lists; which source pages are already on disk vs blocked; pdfplumber not the VLM. **2026-08-08 correction:** five mislabelled codes fixed — `ab_a/e/f/v/w` are the Dragon-Blooded **Aspect Books**, `salt` = Blood and Salt, `coin` = Manacle and Coin. **The on-disk slice is now EXHAUSTED** — the 40 entries authorable-now plus the 20 Caste Book Twilight/Eclipse entries (their pp.79-81 pages landed and were VLM-transcribed 2026-08-08) are all in the build (`data/artifacts.json` = 40); only the Direlance catalogue entry, the Slayer Khatar and the Fair Folk 205-211 question remain, all blocked on pages; per-entry authoring queue with build status in `artifact-backlog-entries.md`) | `docs/status/artifact-backlog.md` |
| **Edit⇄XP merge — DONE, browser-verified** (one trait surface both sides of the lock; `ui/xp.py` deleted) | `docs/status/edit-xp-merge.md` |
| **Ghosts — DONE, browser-verified** (7th splat, 2nd non-Exalt; Virtue-keyed Arcanoi, Fetters + Passions, two axes, Terrestrial MA + Fighter in Life) | `docs/status/ghosts.md` |
| **Godblooded — DONE, browser-verified** (8th splat, 3rd non-Exalt; Ghost-Blooded, Half-Caste and Fae-Blooded heritages, plus God/Demon-Blooded heritage rows + 16 M&F + the 80-Charm spirit catalogue authored 2026-08-07 and the p.48 sorcery initiation 2026-08-08, every printed prereq wired — browser-verified 2026-08-08) | `docs/status/godblooded.md` |
| **Dragon-Kings — DONE, browser-verified** (9th splat, 4th non-Exalt; the ten Paths of Prehuman Mastery as a rated subsystem, four Breeds, single Essence pool, Essence-gated trait ceilings, Terrestrial sorcery) | `docs/status/dragon-kings.md` |
| **Mountain Folk — DONE, browser-verified** (10th splat, 5th non-Exalt, the last; the Enlightenment origin axis, the five-Pattern Charm economy with a new Enchantment type, the Great Geas as Divergence + reference panel, three Darkbrood adversaries) | `docs/status/mountain-folk.md` |
| **Elder Exalts — DONE, browser-verified** (simplified 2026-08-06: Essence XP-purchasable to the splat cap — 9 flat, Terrestrial-7 held; trait ceilings follow Essence; age chart removed; + the p.259 downtime calculator) | `docs/status/elder-exalts.md` |
| **Adversary roster — DONE, browser-verified** (GM-mode extras/beasts/NPCs; one small model that is NOT a Character; 49 generic templates; instancing) | `docs/status/adversary-roster.md` |

**State of the world:** the foundation (models, persistence, engine, UI) is done
(`engine-and-ui.md`); every shipped splat's data, engine and UI is browser-verified,
including Mountain Folk (2026-08-07). 1,470 Charms across the six Exalt splats, plus
56 ghost Arcanoi and 94 Mountain Folk Charms (`data-and-tooling.md`). Rated artifacts
and the catalogue/dropdown shipped 2026-08-08 — 40 entries, the on-disk backlog
exhausted (only the Direlance catalogue entry and Slayer Khatar remain, both blocked
on pages) — see `docs/status/rated-artifacts.md`.
Ship dates for everything else live in the per-splat status docs and the git log.

### Removed
- **Merits & Flaws** — ripped out 2026-06-15 (the old system bundled
  balance-wrecking Charm rewrites), and **RESTORED 2026-07-30** as the single
  centralized `merits_and_flaws_calc` decision 0011 called for. This entry stays as
  history: the reason they were removed is the reason no caller may name a Merit id.
  See `docs/status/merits-flaws.md`.

### Deferred (still open, just not now)
- `chargen_budgets.json`/`costs_bonus.json`/`costs_xp.json` overrides beyond
  what's authored — optional, loader falls back to model defaults.
- A per-session XP-grant ledger; state-reconciliation of hand-edited
  current-vs-snapshot drift (the read-only lock guards normal use).

### After 1.0 — the Qt port (a standing goal, NOT scheduled)
**Human, 2026-08-10:** after the 1.0 ship (feature-complete — sourcebooks, the full
artifact and spell catalogues), branch and rebuild the UI on **PySide6/Qt**, which
becomes the bedrock of a 2.0. Nothing is committed; it becomes **decision 0015** when it
is. **Do not start it before 1.0 and do not treat it as a 1.0 blocker** — a different
widget toolkit is not a feature. Full plan, measured baseline and open questions:
**`docs/plans/qt-port.md`**.

The one part that affects work happening NOW: the port is cheap only because nothing
outside `ui/` imports `nicegui` and `ui/view.py` is a pure presenter (decision 0002's
"disposable UI", actually honoured). **Keep it that way**, and prefer putting derived
state in `view.py` over computing it inline in a widget module — that is ordinary
hygiene that happens to be free migration work. It is not speculative effort for a port
that may never happen.

### ⚠️ Training times are almost certainly NEVER being added
**Human, 2026-07-30: "training times will probably never be added — that goes out of the
dumb-tracker scope, in my opinion."** Not a numbered decision record, because the human
hedged it rather than closing it — but treat it as a no unless they reopen it, and
**do not propose it, plan around it, or offer it as a follow-up.**

`XpEntry.training_complete` stays as a dormant hook and nothing more. Several printed
rules hang off it and are shipped deliberately incomplete as a result; that is accepted,
not a gap to close:
- Weak Essence's withheld Charms "still require the same training time" — the XP waiver
  ships without its counterweight (`docs/status/merits-flaws-triage.md`).
- Brigid's Heir doubles/halves "the bonus/experience cost **and training time**" — only
  the point costs move.
- Death's Taint's Harrowing, the story requirement attached to shedding permanent
  Resonance, is the same class of rule.
- The **elder-Exalt** ceilings (PG p.258) are gated on training time; only the XP cost
  shipped, so an elder raise is cheaper in table-time than printed. (The age chart that
  used to be the other half of that gate is GONE — 2026-08-06, Essence is XP-purchasable
  — see `docs/status/elder-exalts.md`.)

The reasoning is the tracker's, and it generalises: this build is a **character builder
and validator**, not a chronicle simulator. Anything that needs the passage of in-game
time to resolve is out for the same reason `PlayState` is a dumb manual tracker.

## TODO

### 👉 START HERE → `docs/status/handoff.md`
The session handoff — current state, open threads, flagged items and pointers — lives
in **`docs/status/handoff.md`**. **It is rewritten each session.** This file is the
durable operating guide; do not re-accumulate handoff narrative here.

### Blocked / not started
* **Dragon-Blooded numina / the Mist aspect** — the ONE piece of the Outcaste book
  left unauthored (deliberate, human's call 2026-07-29). **Blocked on pages:** the
  Forest Witch summary (p.133) gives Mist as an aspect with NO Aspect Abilities whose
  power is "one numen effect per point of Essence"; a numen must buy Cult • or Cult ••,
  replaces one Charm with Dematerialize, and reduces Temperance by one dot if it has a
  blight or affliction (p.132). The numen effect list is on **p.118**, which is not in
  `images/Dragonblooded/`, and the text also points at *Games of Divinity* p.127 and
  *Exalted: The Lunars* p.98 for Cult. Author nothing until those land.

### Recently shipped — traps to remember
The full record lives in `docs/status/`. These are the cross-cutting lessons that
survive any status rewrite:

* **Dragon-Kings breed attributes** (`docs/status/dragon-kings.md`) — breed attribute
  bonuses are free dots ON TOP of the stored value, but each EFFECTIVE dot above 5 is
  BP-bought at the attribute rate (PG p.175). **Trap: a "free" ruling that contradicts
  the book's price language ("without spending bonus or experience points") needs the
  human's intent confirmed before authoring — a mistaken "free" ships as a silent
  under-charge.**
* **The adversary roster** (`docs/status/adversary-roster.md`) — **An `Adversary` is
  NOT a `Character` and must never become one** — a test asserts it. The dead-field bug
  fired here too: two tests now force every stat field to be both editable and
  displayed. SHIELDS entered the build as `armor.json` rows tagged "shield", not a
  model of their own.
* **Ghosts** (`docs/status/ghosts.md`) — **Passions are a LIVE DERIVATION of the
  Virtues** on both sides of the lock, per-Virtue, never bought with BP or XP (E:Ab
  p.283). **⚠ A pre-existing DATA BUG surfaced here:** Five-Dragon Style is Terrestrial
  and the five Immaculate Dragon Paths are Celestial, and the catalogue had both
  exactly backwards — fixed in the data; don't re-break it.
* **Elder Exalts** (`docs/status/elder-exalts.md`) — **no character may leave creation
  with Essence above 5** (`essence-above-elder-chargen-cap`); the age chart and
  `Character.age` are GONE.
* **The Edit⇄XP merge** (`docs/status/edit-xp-merge.md`, decision 0013) — there is **no
  XP tab**; `ui/xp.py` is deleted. The dot track is the buy control both sides of the
  lock, and a downward click opens a dialog asking *undo (refund) or permanent loss
  (curse)?* — the app cannot infer which. **Eight chargen choices are frozen once
  locked** (Favoured picks, caste, Exalt type, origin, upbringing, camp, Calling, flawed
  Virtue) — greyed but readable.
* **Merits & Flaws** (`docs/status/merits-flaws.md`) — **no module outside
  `engine/merits.py` may name a Merit id** — a test greps for it; add a `MeritEffects`
  FIELD, never an allowlist. The 31 dice-only and 32 narrative entries are **skipped
  permanently** — not deferred. **Salary** is named by Cache's prerequisite and does not
  exist as a Background, left unresolvable until a page for it appears.
* **The Advantages tab** (`docs/status/advantages-tab.md`) — Backgrounds and M&F on one
  both-sides tab, two duplicate implementations deleted. The **M&F filter/search** is
  DONE (side/category/free-text over name AND rules text, one filter serving both
  regimes).

### Rulings that bite when touched
**Three rulings landed 2026-07-31** (human, rules authority — written up in
`docs/status/edit-xp-merge.md`). The first changes a model assumption, so read it before touching
specialties: **a specialty is an INSTANCE, not a rated trait** — you take the same one
again rather than raising it, capped at **3 per Ability** (two Swords + one Parrying
fills Melee). Legacy rated specialties are split on load. Also: **Crafts and Colleges
can be reduced** (a usability escape hatch, not a printed rule — undo is LIFO and
misclicks happen), and **Nature freezes at the lock** with the other chargen choices.

**Thaumaturgy** (`docs/status/thaumaturgy.md`) is DONE but its rulings are load-bearing
for the mortal splats, so they stay here. It is **NOT a splat**: a cross-splat
capability layer any character except the Fair Folk can hold (Ghosts hold it but may
never use it), so it sits on every shipped splat's sheet. **`HouseRules` is the home
for EVERY Storyteller toggle** — it also holds the two optional p.113 chargen caps and
the Eclipse/Moonshadow chargen permission, which moved off `Character.st_foreign_charms`
(read it via `validate.foreign_charms_permitted`). Fields are marked TABLE-WIDE or
PER-CHARACTER **in comments only** — a party-wide "apply to all" control may only touch
the former. Science costs (5/7 BP, 7/current×6 XP) are the **only value in the build
with no page behind it** — the printed tables omit Sciences entirely; rate supplied by
the human 2026-07-29. p.116 Step Four errata ("5 in addition to recorded **Knowledge**",
not Inheritance) — read before building mortal chargen or the Knowledge BP pool.

**M&F mechanical effects** (`docs/status/merits-flaws.md` and `merits-flaws-triage.md`,
in that order) — the whole A-list (A1-A7 plus cluster 7) is done. Three things bite:
(1) **no module outside `engine/merits.py` may name a Merit id** (see above);
(2) **`derive.soak`, `derive.willpower`, `derive.health_track` and
`lifecycle.lock_chargen` take an OPTIONAL `ruleset`** so they can see Merits — every
omission is a silent wrong answer rather than a TypeError; follow that shape, do not
thread `MeritEffects` through call sites; (3) **a derived effect field that nothing
reads is this area's recurring bug**, three times now and invisible to the suite each
time — run the `preflight` skill before booking browser time.

## Background
- `CharmCost.health_type` was homebrew-only with no printed use when created, but
  acquired its first printed consumer on 2026-08-01 — Stolen Wax Discipline (E:Ab
  p.238), "5 motes, one lethal health level". Don't treat it as homebrew-only.
- Full multi-splat plan: `~/.claude/plans/should-we-plan-out-encapsulated-crab.md`.
- DB chargen numbers as verified from source pages: [[db-chargen-findings]].
