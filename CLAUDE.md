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

### 📝 The comment standard (human, 2026-08-17) — applies to ALL new code
A docstring carries **input, output, and how it gets from one to the other. Nothing
else.** No decision-making logs, no chain of thought, no dated narration of how the code
reached its shape. *"Commit messages are fine to be wordy… we do want a log, but that
shouldn't bloat the code."* Put the reasoning, the alternatives and the
bugs-found-along-the-way in the commit message and `docs/status/`.

Three things STAY: **page citations** ("core p.104", or a short undated "human's ruling"
where no page exists); **⚠ records of behavioural traps** — *"those are important to
anyone working on this"*, and a trap buried in narration should come OUT as an explicit
⚠, not be deleted with it; and the contract itself.

`engine/validate/` has had this pass (2026-08-17). Not yet done, in size order as
measured THEN: **`ui/`** (3,676 prose lines, 24%), **`models/`** (2,672, 61% — densest in
the build), **`engine/` outside validate** (2,496, 38%) — plus **`qt/`**, which did not
exist at that measurement and has never had the pass. ⚠ Re-measure before acting on those
numbers; `ui/` in particular has shrunk as the port moved logic into `engine/` and
`view.py`. Use `prose_guard.py`'s method: strip all docstrings,
compare the AST (byte-identical ⇒ no code changed), then assert no page citation and no
⚠ marker was lost. ⚠ **Judge such a pass by what the prose IS, never by line count** —
validate's only went 35% → 34% and that was the correct outcome.

### The house bug — stated once
A rule that IS implemented, sitting where it does not run when it matters. It has
appeared in three species; all three keep recurring.

1. **Wired to the wrong phase.** Three M&F instances, then mortal magic access wired to
   chargen only, then the XP tab's hardcoded trait ceiling. `preflight`'s read-site audit
   reports single-site fields as healthy — **a single read site is as suspect as none
   when the read sits in the phase that wrote it. Test the buy path, not the effect.**
2. **Zero read sites, and still looks healthy**, because something else does its job by
   accident (`heritage_traits.magic_track`; the Ghost catalogue holds no sorcery, so
   Charm access happened to produce the right answer while both Half-Castes were broken).
   **Correct behaviour in the case you tested is not evidence the mechanism exists.**
3. **The switch is player-editable to a value that switches it off.** A custom M&F row
   keyed on `custom_name` being truthy — and the name input writes that field on every
   keystroke. **A discriminator must be a field nothing on the screen can edit.** When
   you add a "kind" flag, ask which widget can write it.

The mechanical sweep for all three is `docs/delegated-authoring.md` — **read it before
delegating a splat to a cheap model, and run its four checks before booking browser
time.** (Godblooded was authored end to end by DeepSeek V4 Flash; the review found four
defects, every one of them the house bug.)

### Lessons that generalise past their own area
Each is written up in full where it happened; these are the reusable one-liners.

- **"Missing from the build" is not "should be authored."** A gap diff cannot see a human
  ruling — grep `docs/status/` and `tests/` for an entry name first.
- **A search shaped like what you expect proves nothing about a thing shaped
  differently.** Before trusting a sweep, ask which shapes it **cannot see** (rituals
  print no stat block; one has no heading at all).
- **A fuzzy gap count is a LOWER bound on the work.** When a name match fails, match on
  **book + page** — but keep the name check too; entries printed in two books slip a
  page-keyed check.
- **A permission toggle must move the OFFER as well as the bar.** A granted-but-unfindable
  Background is worse than no toggle.
- **A predicate that answers "True, not applicable" outside its subject is a grant waiting
  to happen.**
- **When you teach one formatter a new fact, grep for its siblings.** Per-module display
  helpers touch no engine code, so containment tests never see them.
- **When a structural invariant is relaxed, name where it moved TO in the same change.**
- **An exemption keyed on a basename is an exemption anything can claim** — key on path.
- **Check sign conventions against `data/`** before consuming a field (`Armor.mobility_penalty`
  is stored NEGATIVE; a consumer reading it as a magnitude adds dice).
- **A GUI toolkit can silently degrade a value you hand it and hand back.** Qt stores
  combo item data as a QVariant, and a `str`-valued Enum returns from `currentData()` as
  a plain `str`; with no `validate_assignment` on the model, writing it succeeds and
  fails later somewhere else. **Never read a key back out of a widget — index the dict
  you built the widget from.**
- **A gap-list entry can name the wrong MODULE, not just the wrong size.** Downtime sat
  under "Edit's deferred panels" for two sessions and is a shell control. Check where
  the webapp puts a thing before porting it to where the list says it is.
- **A "free" ruling that contradicts the book's price language needs the human's intent
  confirmed** — a mistaken "free" ships as a silent under-charge.
- **When a tool closes a blocker, the prose describing the blocker is part of the change.**
  A stale "page-blocked" line reads exactly like a live one.
- **Negative controls go stale silently and keep passing.** After authoring content that
  used to be missing, grep the tests for the names you just added; when no real subject
  remains, rebuild the control on a synthetic fixture — never delete it. **Moving a
  feature stales them too** — once Combos left the rail, "a ghost's rail has no Combos"
  passed for every splat and proved nothing.
- **When code copies one model into another field by field, derive the field set from the
  models.** A hand-written copy list documents the fields someone thought of: `ui/gear.py`
  carried `from_artifact` across a catalogue re-pick because a comment warned about it,
  and silently dropped `acquired` — re-charging the Artifact budget for a cash-bought
  item. `gear_actions._owned_fields` is the complement of `_catalogue_stats`, so neither
  half can be forgotten.
- **A page added to a shell inherits a HOOK CONTRACT from its sibling pages** — diff the
  constructor calls, not the page. `CharmsPage` was built without the `on_change` every
  other Qt page passes, so spending on it never moved the shell's readout bar; the tab's
  own local readout updated fine, which is what hid it.
- **Address a widget by name, never by position in a `findChildren` list.** A test that
  grabbed `findChildren(QSpinBox)[0]` got the row's quantity box instead of the stat it
  meant, and passed a wrong assertion into existence.
- **A guard in a DISPATCHER can shadow a more careful guard one layer down, turning
  implemented support into dead code.** `charm_actions.learn_charm` refused any owned
  Charm post-lock with a bare `in character.charms`; `advancement.learn_charm` beneath
  it had supported the repeatable case all along, cap check and page citation included.
  Both shells go through the dispatcher, so nothing could reach it. **When you write a
  broad refusal, check what the layer below already handles more precisely.**
- **A test's SUBJECT can quietly become the wrong subject.** The Qt "Add another" tests
  used a Charm that later turned out to be a variant menu, not a generic repeatable.
  They were green throughout and proved nothing about the case they named. When a
  thing's classification changes, grep the tests that named it.

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
- **Deferred INDEFINITELY, and neither is a gap** — the **Mist numina / Mist aspect**
  (`docs/status/mist-numina.md`: there is no numen effect LIST to author) and **Cult
  Abyssals** (`docs/status/illuminated.md`: 56 Charms needing human-approved mappings).
  A sweep that lists either as unauthored is counting a deferral as an oversight. **Do
  not offer them as follow-ups.**
- **The Qt port** — **COMMITTED as decision 0018 (2026-08-20)**: branch and rebuild the
  UI on **PySide6/Qt** as the bedrock of a 2.0, offered alongside the NiceGUI webapp.
  Plan and build record: **`docs/plans/qt-port.md`**. The two spikes (`spikes/qt_tree/`
  + `spikes/qt_sheet/`, built and human-approved 2026-08-20) answered the port's open
  questions: `QGraphicsView` fits the charm-tree picker; the sheet becomes a
  `QTextDocument` (on-screen and print from one source); and retained-mode widgets
  test well with pytest-qt (28 + 14 tests, offscreen). **Milestones 1–3 have shipped
  and are human-clicked on the real display** (the shell + Edit/Charms/Sheet; the
  left-rail shell + Identity/Traits; the Advantages tab). **Milestones 4 and 5 — the Gear tab
  with Combos moving under Charms, and Advantages rebuilt as a collection — have
  shipped and are human-clicked.** **Milestone 6 — the Play tab (`qt/play.py`) — has
  shipped and is human-clicked (2026-08-22).** Run it
  with `python -m exalted_builder.qt [path]`; the code is `exalted_builder/qt/`. **What
  each milestone contains, and every trap it cost, is in `docs/plans/qt-port.md` — read
  that before touching the port rather than re-deriving it here.**

  ⚠ **THE PORT IS FEATURE-COMPLETE (2026-08-27).** Every tab shipped, and so did the
  **Party / ST window** — the one thing that was a DESIGN QUESTION rather than a port
  (`qt/party.py`, `qt/adversaries.py`, `qt/trackers.py`). Its four design answers, taken
  as recommended: a **second `QMainWindow`** · **sub-tabs Party / Adversaries /
  Reference, with mixed layouts** · **"Open in builder" retargets the ONE builder** ·
  **the ST reference screen lives on that window**. ⚠ **The rail was never the measure of
  what was left** — the Combos sub-tab never appeared on it and the within-tab gaps never
  could. **What is OWED is a click-through of the Party window** (rendered offscreen and
  looked at, not used); group 4's five per-splat Charm surfaces are still unclicked too,
  a low-priority sweep rather than an owed verification.

  ⚠ **The gap list was a LOWER bound every single time — SEVEN for seven.** The Party
  window's "~1,100 lines" missed the **ST reference screen** (in no Qt module at all),
  the **roster mutations having no engine home**, and four layout defects only a render
  could show. Item 1
  turned up a stale shell readout on no list; item 2 a `reload()` that never pinged the
  shell and a `_combo` degrading enum keys, then three more at click-through; item 3 a
  detail pane missing five cost-relevant flag lines and a QSS with no
  `QPushButton:disabled` rule, which made every disabled button in the WHOLE port look
  clickable; ST Options, listed as one placeholder module, four more — including the
  SAME hole for `QCheckBox`, again port-wide and older than the tab; Custom, four more
  again — including the SAME hole a third time, for `QDialog` and `QPlainTextEdit`; and
  "the Combos sub-tab, 423 lines" turned out to be TWO systems, Combos *or* Arrays.
  **A defect one widget class over is still your defect: when you add a rule for one
  widget class, add it for every interactive class in the QSS.** **Audit each
  remaining tab against its `ui/` counterpart before trusting the list, click it before
  believing it, and render it offscreen and LOOK — both stylesheet defects were
  invisible to every one of the 2,857 tests.**

  ⚠ **A QSS rule is invisible to the whole suite, so guard it by RENDERING.**
  `tests/test_qt_theme.py` exists for this and its first version was worthless: it
  compared whole-widget images with `!=` and passed against the very defect it was
  named for, because Qt dims disabled TEXT on its own. Cropping to the indicator was
  still not enough — antialiasing makes the two drawings unequal, and the real
  brightness gap was **7 of 255, inverted for a ticked box.** **Negative-control a
  rendering test by deleting the rule it guards.**

  Four things that affect work NOW, so they live here:
  - ⚠ **A Qt tab is a COLLECTION, and there is ONE layout — with THREE written
    exceptions now.** Settled by the human
    2026-08-21 after the `qt_advantages` spike: toolbar for actions · sub-tab per
    category where a tab has more than one · a sortable table with a header · a
    splitter with the selected entry's editor in a detail pane. Charms, Gear and
    Advantages, ST Options and Custom all have it — **do not re-litigate per tab.**
    ⚠ **THREE exceptions are stated, and all are WRITTEN DOWN** —
    an exception that is written down is not drift; an unwritten one is. (**ST Options
    omits the TOOLBAR only**, because the rules are fixed by the books and there is
    nothing to add, buy or delete. Written into `qt/storyteller.py`'s docstring; it
    keeps every other part of the layout and is not a third exception.)
    **Play** (human, 2026-08-22) is a live TRACKER, not a list — a health track you
    click to mark, mote pools, the dice-pool sidebar — so there is nothing to select and
    a detail pane would hide numbers you glance at mid-roll. Toolbar over panels;
    `qt/play.py` is built that way.
    **The PARTY tab** (human, 2026-08-27) is the third, and it is Play's exception for
    Play's reason — the member cards are live trackers with nothing to select. ⚠ The
    **Adversaries** tab in the same window IS a collection, because its entries are
    edited as well as tracked: **two shapes in one window is the design.**
    **Identity + Traits** (human, 2026-08-22) KEEP their card scroll. Asked, spiked six
    ways — including a `QTreeWidget` collection exactly like Gear's — and declined:
    *"the way it is right now works best for this information specifically."* A trait
    surface is a fixed FORM, not a collection; there is nothing to select. **Do not
    re-propose a Traits redesign** — `spikes/qt_traits/` records what lost.
    Gear was built TWICE because its first version ported the
    webapp's structure by reflex (floating button, accordion expanders, card stack) and
    was rejected on sight with every test green. **Copy `qt/gear.py` or
    `qt/advantages.py`; never transliterate `ui/<tab>.py`.**
  - ⚠ **Tear a layout down with `qt/layout.py::clear_layout`** — never a fresh loop.
    `item.widget()` is None for a nested `QLayout` and `deleteLater()` is deferred, and
    the hand-written version has now got that wrong on five separate outings — most
    recently leaving the details popover's old rows painting over its new ones.
  - ⚠ **An ancestor stylesheet BEATS a set palette, every time.** Setting a stylesheet
    on the window hands the stylesheet renderer every descendant, and it ignores
    `QPalette`. Bitten three times in different disguises: a `QTextEdit` in a `_Panel`
    painting the card shade; the Gear and Advantages **trees rendering white on the dark
    page for two shipped, human-clicked milestones**; and small buttons inside a card
    going invisible because the QSS gives every `QPushButton` `background:CARD`. **The
    only fix is an inline stylesheet on the widget itself** — and if a widget class is
    not named in `qt/theme.py::qss`, assume it is unstyled.
  - ⚠ **The two shells' tab sets differ deliberately.** Combos is a **sub-tab of Charms**
    in Qt and a top-level tab on the webapp. `view.visible_tabs` still names it — the Qt
    shell discards that one answer and `CharmsPage` runs `has_combos_tab` itself. Do not
    "fix" the presenter to match the rail.
  - The port is cheap only because nothing outside `ui/` imports `nicegui` and
    `ui/view.py` is a pure presenter. **Keep it that way** — prefer derived state in
    `view.py` over inline computation in a widget module.
  - **Theme is settled** (the human's desktop direction): one unified dark base, the
    splat as a light accent. The dark printed accents are invisible on dark; do not
    reintroduce them.

## Stack
- Python + pydantic v2 + pytest. Frontend: **NiceGUI** (chosen over Reflex), the optional
  `[ui]` extra. A JS graph library (Cytoscape/d3) is still planned ONLY for the
  charm-tree picker.
- Venv is `.venv/`; tests: `.venv/bin/python -m pytest`.
- **Git remote:** `origin` → `github.com/x6568tank/exalted-1e-charsheet-generator`, tracking `main`.
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

## The test suite
**3,015 passing, 1 skipped** (2026-08-27, main PC, the `qt-port` branch after the Party
/ ST window — includes the Qt-port tests in `tests/test_qt_*.py`,
`tests/test_charm_actions.py`, `tests/test_gear_actions.py` and
`tests/test_variant_purchases.py`).

- ⚠ **The Qt tests need the OPTIONAL `qt` extra, and SKIP without it** (470 of them,
  fourteen whole modules). `pytest.importorskip("PySide6")` guards each; before that guard
  a bare import was a COLLECTION ERROR, which takes the entire run down rather than
  those tests. **A count 470 lower on a webapp-only machine is that working**, not
  tests going missing — install with `.venv/bin/pip install -e '.[qt]'`.

- ⚠ **Quote the RUN's numbers, not `--collect-only`'s** — the two have disagreed by one
  here and the cause was not chased. The run is what tells you the suite is green.
- ⚠ **Read the "passed" count off a run that was GREEN.** `2674 passed` on a line that
  also says `1 failed` is not the suite's number, and it went into three docs on
  2026-08-21 before the fix put the real figure one higher. Check the failure count
  before you copy the pass count.
- ⚠ **The SKIP is conditional and healthy, not a disabled test:**
  `test_buy_merit_prices_the_tier_against_the_characters_own_menu` skips when no Merit
  tier exists that is generic-but-not-Solar.
- ⚠ **The COUNT is machine-dependent, by dozens of tests** — the `images/`-presence
  deferral pattern showing up in COLLECTION rather than outcomes. **Do not treat a lower
  count as tests having been deleted**, and do not "reconcile" two machines' numbers.
  Record the number you measured, where and when.
- ⚠ **One test is machine-dependent in OUTCOME, and that is the point:**
  `test_every_description_matches_the_source_text` **defers** entries whose source
  chapter is absent, and fails them where the chapter is present. **Neither outcome is a
  regression**, and do not "fix" it by editing a path. `docs/status/godblooded.md`.

## The record → `docs/status/`
One file per topic. **Read the relevant file before touching that area.** The rows below
are pointers only; the traps and history live in the files.

| Area | File |
|---|---|
| **Session handoff — rewritten each session** | `status/handoff.md` |
| How it works: module boundaries, lifecycle, invariants | `ARCHITECTURE.md` |
| Why: closed decisions, one record each | `decisions/` |
| The rules data — conventions, what the loader checks | `content.md` |
| Implementing a splat — honest cost, from the eleven done | `adding-a-splat.md` |
| Delegating a splat to a cheap model — the four-check audit | `delegated-authoring.md` |
| How `source.book` is written, and why it rots | `source-attribution.md` |
| Models, loader, persistence, `engine/`, NiceGUI UI | `status/engine-and-ui.md` |
| Core data files, Charm counts, `tools/` | `status/data-and-tooling.md` |
| The 1.0 catalogue sweep — six delegated batches, the `sources/` extraction pipeline and its glyph ciphers | `status/catalogue-sweep.md` |
| The content gap — CLOSED 2026-08-14, all 647 discovery rows resolved | `status/content-gap-retriage.md` |
| Book of Three Circles — spells, artifacts, the Merit-gated plot devices | `status/book-of-three-circles.md` |
| Corebook Wonders — Hearthstones, Greater Wonders, the Hearthstone allowance | `status/corebook-wonders.md` |
| Rated artifacts — the Artifact budget, dual-nature devices, the corebook default | `status/rated-artifacts.md` |
| 1E artifact backlog — the discovery layer (parse method + per-book page lists) | `status/artifact-backlog.md` |
| Martial-arts STYLE entity — 21 of 22 authored, tiers, `Charm.ma_tier` access | `status/martial-arts-styles.md` |
| Merits & Flaws — the centralized calc (decision 0011), all 100 authored | `status/merits-flaws.md` |
| M&F mechanical-effect triage — what was modelled, what was skipped and why | `status/merits-flaws-triage.md` |
| Backgrounds — per-splat catalogues, the dot ladder, the numeric rules | `status/backgrounds.md` |
| Thaumaturgy — cross-splat Arts/Sciences/Rituals/Formulas | `status/thaumaturgy.md` |
| Custom content — user-authored Charms/styles/spells, the `/custom` page | `status/custom-content.md` |
| Dice pools — decision 0016, the Play-tab sidebar | `status/dice-pools.md` |
| Elder Exalts — Essence to the splat cap, the p.259 downtime calculator | `status/elder-exalts.md` |
| Edit⇄XP merge — one trait surface both sides of the lock | `status/edit-xp-merge.md` |
| Advantages tab — Backgrounds + M&F on one both-sides tab | `status/advantages-tab.md` |
| Gear tab, inventory & shop — everything owned on one surface | `status/gear-and-inventory.md` |
| Catalogue picker dialogs — the shared `ui/catalogue.py` dialog | `status/catalogue-dialogs.md` |
| Printable / PDF sheet — a real generated PDF, not a print stylesheet | `status/printable-sheet.md` |
| Adversary roster — GM-mode extras/beasts/NPCs | `status/adversary-roster.md` |
| The `engine/validate/` split — 15 modules, `validate.X` is the ONE public path | `plans/validate-refactor.md` |
| The Qt port — decision 0018; the build record. **FEATURE-COMPLETE 2026-08-27**: milestones 1–6, the **ST Options**, **Custom** and **Combos** tabs (all human-clicked) and the **Party / ST window** (built, NOT yet clicked — that is the one owed thing, with group 4’s per-splat Charm surfaces). Milestone 5 SETTLES the one layout; milestone 6, Identity+Traits and the Party tab are its three written exceptions | `plans/qt-port.md` |
| Variant-menu Charms — the generic `variant_purchases` list, `Charm.variants_unique`, and why Ox-Body and the Gifts were deliberately NOT migrated onto it | `plans/variant-menu-charms.md` |

**State of the world:** foundation, splats, engine and UI are done and browser-verified;
a character can be put on paper. **The catalogue is COMPLETE (2026-08-14):** Charms
1,921 · spells 306 · artifacts 330 · weapons 112 · armour 28 · thaumaturgy 4 Arts /
4 Sciences / 30 formulas / 11 rituals. **Nothing is page-blocked and nothing is a known
gap** — the only unauthored content is deliberately deferred (see **Standing bars**).

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
- `chargen_budgets.json`/`costs_bonus.json`/`costs_xp.json` overrides beyond what's
  authored — optional, loader falls back to model defaults.
- A per-session XP-grant ledger; state-reconciliation of hand-edited
  current-vs-snapshot drift (the read-only lock guards normal use).
- The comment pass on `ui/`, `models/` and `engine/` outside validate (see **The comment
  standard**).

## Background
- **Merits & Flaws were ripped out 2026-06-15** (the old system bundled balance-wrecking
  Charm rewrites) and **restored 2026-07-30** as decision 0011's single centralized calc.
  The reason they were removed is the reason no caller may name a Merit id.
- `CharmCost.health_type` was homebrew-only with no printed use when created, but
  acquired its first printed consumer on 2026-08-01 — Stolen Wax Discipline (E:Ab
  p.238), "5 motes, one lethal health level". Don't treat it as homebrew-only.
- Full multi-splat plan: `~/.claude/plans/should-we-plan-out-encapsulated-crab.md`.
- DB chargen numbers as verified from source pages: [[db-chargen-findings]].
