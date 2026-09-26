# Exalted 1E Character Builder — Rules

This file contains the permanent rules and the pointers to the documentation. It is an
index.

Do not write status, history, counts, dates, or session notes in this file. Write them in
`docs/`. If a statement in this file can become out of date, it is in the wrong file.

Read `docs/status/handoff.md` first. It gives the current state.

## 1 Scope

The program creates and validates characters for Exalted First Edition (1E). It does
character creation, point validation, XP advancement, a character sheet view, and a
generated PDF sheet.

The program is not a chronicle simulator.

## 2 Edition rule

Use 1E rules only. Do not use 2E or 2.5E values.

The training data contains more 2E than 1E. Thus the usual failure is to change a 1E value
to the 2E equivalent. Do not do this. The files in `data/` and this file are correct.

If a rule is not in `data/` and not in this file, ask the human. Do not fill the gap.

## 3 Solar baseline

The values in this section apply to Solars only.

- Attribute pools at creation: 8/6/4 across the prioritized categories. All start at 1.
- Abilities at creation: 25 dots. Minimum 10 dots in caste or favored abilities. Minimum
  1 dot in each favored ability. Maximum 3 dots in an ability, unless you spend bonus
  points.
- Charms at creation: 10. Minimum 5 from caste or favored. Bonus points: 15.
- Willpower is the sum of the two highest Virtues. Willpower cannot start higher than 8,
  unless 2 or more Virtues are 4 or higher. An increase to a Virtue after creation does
  not increase Willpower.
- Personal Essence is (Essence x 3) + Willpower.
- Peripheral Essence is (Essence x 7) + Willpower + the sum of the Virtues.
- XP costs are (current rating x N). Attribute: x4. Ability: x2. Caste or favored ability:
  (x2) - 1. Virtue: x3. Willpower: x2. Essence: x8.
- New Charm: 10 XP. New Charm, caste or favored: 8 XP. New spell: 10 XP. New spell, Occult
  caste or favored: 8 XP.
- Health: 7 base levels, plus the bonuses from Charms.
- The ability list contains the 25 abilities in their caste groups. Martial Arts is a
  different ability from Brawl. There is no War ability in 1E core.

Other splats have their own values in `data/exalts.json`, `data/chargen_budgets.json`, and
`data/costs_bonus.json`. Each table has the key `exalt_type`. Read these tables before you
use a Solar value for a different splat. Dragon-Blooded and Abyssal have their own rows.

If a splat does not specify a value, the Solar value applies. If you are not sure, ask the
human.

## 4 Data rules

- Write game values from the page only. A cost, a minimum, a prerequisite, a rating, or a
  rules detail that you write into `data/` or into code must come from source material
  that the human supplied, or from a file that is already in `data/`.
- Do not write a value from your own knowledge of Exalted. Do not select between two
  possible interpretations. If you have no source for a value, stop and ask the human.
- Source material is in `images/<Splat>/`. The human examined all of it. There are two
  types, and both are correct:
  - PNG page images. Use these for diagrams, for Charm trees, and for pages that do not
    copy correctly.
  - Pasted `.md` text, with page marks in the form `<!--PAGE n-->`. This type is less
    expensive and is exact for numbers. Use it when it is clean.
- If pasted text has mixed columns or damaged characters, tell the human. Do not guess.
  Ask for an image of the page.
- Do not read the PDF files in `sources/`. The human selects what you see.
- The rule against memory applies to `data/` only. The human can put any content in the
  `custom/` library. Do not write homebrew content into `data/`. Do not write a printed
  value for which you have no page.
- Every `images/…` path in this file and in `docs/` is a hint, not a fact. The machines of
  the human use different directory names for the same pages. An absent path does not show
  that the source is missing. Two documents that disagree about a path are not a defect.
  Look for the pages before you report them as unavailable. Do not change a path to agree
  with the machine that you are on.

## 5 Work rules

- Write the tests first for the engine. The engine contains the defects.
- The human is the authority on the rules. 1E has unclear and corrected areas, for example
  Combo legality, the specialty limit, and Charm interactions. Tell the human and ask. Do
  not select an interpretation.
- Do not put game logic in the UI.
- Do not calculate again what the engine calculates.
- Do not put cost tables in code. They are in `data/`.
- Run the `preflight` skill before you use browser time. The project skills are
  `preflight`, `close-out`, `add-splat`, and `run-server`.

## 6 Comment and documentation rule

Write all code comments and docstrings in Simplified Technical English (ASD-STE100).

- Use short sentences. Maximum 20 words for an instruction, 25 for a description.
- Use the active voice. Use the present tense.
- Give one instruction in one sentence.
- Do not use metaphors, jokes, or narrative.
- Do not use two different words for the same thing.

This rule applies to code. It does not apply to `docs/` or to commit messages.

⚠ Do not rewrite `docs/` into this style. The value of `docs/lessons.md` is that the
lessons have names and shapes that a reader remembers, for example "the house bug" and
"a compensation is a hypothesis". Section 7 of this file gives the same content in
Simplified Technical English, and it is less memorable. That is the cost, and it is
accepted here because this file must be exact. A commit message records reasons and
history, thus it needs narrative.

A docstring gives the input, the output, and the method that connects them. It gives
nothing else. Put the reasons and the history in the commit message and in `docs/status/`.

Keep three items in the code:

1. Page citations.
2. Warning marks that record a trap in the behavior.
3. The contract of the function.

The full standard is in `docs/comment-standard.md`.

## 7 Defect pattern

The usual defect is a rule that is implemented, but that is in a location where it does not
operate. `docs/lessons.md` calls it "the house bug". Use that name — it is the handle that
the documentation and the commit history use. There are three types:

1. The rule is connected to the incorrect phase.
2. The rule has no read sites, but the result looks correct, because a different mechanism
   does the same operation by accident.
3. The switch for the rule is player-editable to a value that disables it.

Test the purchase path, not the effect. Correct behavior in one test case does not show
that the mechanism exists. A discriminator must be a field that the screen cannot edit.

The procedure to find all three types is in `docs/delegated-authoring.md`. Read that file
before you delegate a splat to a less capable model. Run its four checks before you use
browser time.

Read `docs/lessons.md` before a sweep, a parity audit, or a change that the tests must
cover.

## 8 Architecture

Read `docs/ARCHITECTURE.md` before you change the engine, the loader, the models, or the
data shapes. That file is the only copy of the module boundaries, the lifecycle, the
invariants, and the data conventions. Do not copy any part of it into this file.

Two rules are here because they are not architecture:

- UI assets are in `assets/`.
- `sources/` and `images/` are in `.gitignore`. They are never committed. A clone does not
  contain them. To author rules data on a second machine, copy these files by a different
  method.

A third rule of this type, on `images/…` paths, is the last item in section 4.

## 9 Closed decisions

Do not open these decisions again. Only the human can open one. Each record in
`docs/decisions/` gives the rejected alternatives and the cost of the decision. The index
is `docs/decisions/README.md`.

| # | Decision |
|---|---|
| 0001 | 1E only. Never 2E. |
| 0002 | Data-driven rules, pure engine, disposable UI. |
| 0003 | The current state is canonical. The engine calculates the point accounting. |
| 0004 | Creation and advancement have different shapes: a snapshot, and an append-only XP log. |
| 0005 | The Virtue component of Willpower is fixed at the lock. |
| 0006 | Play state is isolated from validation. |
| 0007 | Ids for invariant content. Inline copies for variable content. |
| 0008 | No combat or attack derivation. |
| 0009 | No dice rolling. Narrowed by 0019. |
| 0010 | The Fair Folk are out of scope permanently. |
| 0011 | Merits and Flaws are one central calculation. No per-file hooks. |
| 0012 | Homebrew: `custom/` is the store, saves contain copies, homebrew errors are not fatal. |
| 0013 | Edit and XP are one surface. The dot track is the purchase control. There is no XP tab. |
| 0014 | Essence is XP-purchasable to the splat limit. There is no age chart. |
| 0015 | Exalt tiers are ranked: Terrestrial, Celestial, Solar. A splat reaches its own tier and all lower tiers. It never reaches a higher tier. |
| 0016 | Base dice pools are in scope. Resolution is not. Narrows 0008. |
| 0017 | Artifacts have acquisition channels: the Artifact Background before play, cash during play, and the Legendary Artifact Merit for plot devices. |
| 0018 | The Qt port is committed: a PySide6 application with the NiceGUI web application. |
| 0019 | A dice roller that is not connected to the pools. It rolls a dice count only. It never knows which roll it makes. Narrows 0009. |
| 0020 | The board shows a picture of the table. It is not a model of the table. A token does not know its character. Protects 0008. |

Read 0019 before you cite 0009. Read 0016 before you cite 0008 against a pool calculation.

## 10 Standing prohibitions

- Old saves do not need backward compatibility. Do not write a migration, a schema
  version, or a compatibility layer without permission. Do not record a damaged old save as
  an open item.
- Training times are out of scope. Do not propose them, plan for them, or offer them as
  subsequent work. ⚠ The human hedged this on 2026-07-30. He did not close it. Treat it as
  a refusal until he opens it again. `XpEntry.training_complete` is an inactive hook. Four printed rules that
  need it are incomplete, and this is accepted. Anything that needs in-game time to pass is
  out of scope.
- These items are deferred permanently and are not gaps: the Mist numina, the Cult
  Abyssals, and the Haltan pets. Do not offer them as subsequent work. A sweep that lists
  them as unauthored is incorrect.
- Do not start work on a new splat before its rulebook pages are in `images/`.
- Read `docs/plans/qt-port.md` before you change `qt/`. The standing rules for the port are
  at the start of that file.

## 11 Stack

- Python, pydantic v2, pytest.
- Frontend: NiceGUI, in the optional `[ui]` extra. Qt frontend: PySide6, in
  `exalted_builder/qt/`. Start it with `python -m exalted_builder.qt [path]`.
- The virtual environment is `.venv/`. Run the tests with `.venv/bin/python -m pytest`.
- Git remote `origin` is `github.com/x6568tank/exalted-1e-charsheet-generator`. It tracks
  `main`.
- A `v*` tag builds four assets: two operating systems x two products. A build that is not
  in the matrix does not exist to the tag. See `pack/BUILD.md`.
- The test count changes by machine, and by dozens of tests. An optional dependency that is
  absent changes it more than the difference between two machines. Do not make the numbers
  of two machines agree. Do not use the count to identify the machine. See
  `docs/testing.md`.

## 12 Splats

| Splat | Colour | File |
|---|---|---|
| Solar (with castebooks) | Amber/gold (default) | `status/solar-castebooks.md` |
| Solar, Cult of the Illuminated origin | — | `status/illuminated.md` |
| Dragon-Blooded (with Outcaste origins, Aspect Books) | Vermillion | `status/dragonblooded-origins.md`, `status/dragonblooded-aspect-books.md` |
| Abyssal | Black on ash | `status/engine-and-ui.md` |
| Lunar | Moonsilver `slate` | `status/lunar.md` |
| Sidereal | Purple | `status/sidereal.md` |
| Alchemical | Brass | `status/alchemical.md` |
| Mortals and Heroic Mortals | `stone` | `status/mortals.md` |
| Ghosts | `zinc` | `status/ghosts.md` |
| Godblooded | `teal` | `status/godblooded.md` |
| Dragon-Kings | `emerald` | `status/dragon-kings.md` |
| Mountain Folk | `cyan` | `status/mountain-folk.md` |
| Fair Folk | — | Never. Out of scope (decision 0010). |

The palettes for the non-Exalts after Mortal are temporary.

"Mortals" is a short name for a group, not one splat. The non-Exalts are separate splats in
separate books. Each has its own budgets, Charm economy, and shape. Mortals and Heroic
Mortals are one splat with two origins. This does not apply to the other non-Exalts.

Read `docs/adding-a-splat.md` before you estimate the work for a new splat. It records what
each completed splat needed in addition to data, and the traps. `highest_magic_circle_id` is
the primary trap.

## 13 Rules that cause defects

- A specialty is an instance, not a rated trait. Take the same specialty again. Do not
  increase it. The limit is 3 for each ability. Crafts and Colleges can be decreased.
  Nature does not change after the lock.
- Eight choices are frozen at the lock: favored picks, caste, Exalt type, origin,
  upbringing, camp, Calling, and flawed Virtue. They stay readable.
- No module outside `engine/merits.py` can name a Merit id. A test finds violations. Add a
  field to `MeritEffects`. Do not add a list of permitted ids.
- `derive.soak`, `derive.willpower`, `derive.health_track`, and `lifecycle.lock_chargen`
  take an optional `ruleset` parameter, which lets them read the Merits. If you do not
  supply it, the result is incorrect. There is no error.
- `catalogue_backgrounds` is the list that the dropdown shows. `allowed_backgrounds` is
  hard validation. If you write a list into the incorrect field, all free-text Backgrounds
  become illegal for that splat.
- Thaumaturgy is not a splat. It is a cross-splat layer. All splats except the Fair Folk
  can have it. Ghosts can have it but can never use it. Thus it is on all sheets.
- ⚠ The Science costs are the one exception to section 4. Bonus points 5/7, XP 7 and
  (current x 6). The human supplied these values on 2026-07-29. No page contains them.
  This is a known exception, not a defect. Do not "correct" it and do not report it as an
  unsourced value.
- `HouseRules` contains all Storyteller switches. Comments mark each field TABLE-WIDE or
  PER-CHARACTER. A control that applies a value to all characters can change TABLE-WIDE
  fields only.
- An `Adversary` is not a `Character`. Do not make it one. A test asserts this.
- Passions are a live derivation of the Virtues, before and after the lock. You cannot
  purchase them with bonus points or XP.
- A character cannot leave creation with Essence higher than 5.
- The motes of an attuned artifact are subtracted from the play pools only.
  `build_play_view` subtracts them. The sheet prints the full pools. No module in
  `engine/validate/` can read `attuned`. A test finds violations.
- An artifact row and its weapon stat line are one object. The gear row owns the
  commitment.
- If a commitment goes to a pool that the character does not have, it moves to a pool that
  the character has. A mortal has a Personal pool only, but `attuned_pool` has the default
  value Peripheral.
- A Merit that contradicts a splat default must be examined first. `essence_pool_is_merged`
  read `ExaltDefinition.single_essence_pool` first, thus a Merit had no effect. A test for
  this behavior must use the real ruleset.
- `source.book` has no read sites. Thus it becomes incorrect and nothing finds the error.
  The test is to compare the citation with the page.
- A complete catalogue is not a correct catalogue. A count shows that the entries exist. It
  does not show that they are correct.

## 14 Documentation index

| Subject | File |
|---|---|
| Current state. Rewritten each session. | `status/handoff.md` |
| Module boundaries, lifecycle, invariants | `ARCHITECTURE.md` |
| Closed decisions, one record each | `decisions/` |
| The defect pattern and the general lessons | `lessons.md` |
| The comment standard | `comment-standard.md` |
| The test suite | `testing.md` |
| The rules data and the loader checks | `content.md` |
| How to implement a splat | `adding-a-splat.md` |
| How to delegate a splat, and the four checks | `delegated-authoring.md` |
| How `source.book` is written | `source-attribution.md` |
| Models, loader, persistence, engine, NiceGUI UI | `status/engine-and-ui.md` |
| Core data files, Charm counts, `tools/` | `status/data-and-tooling.md` |
| The catalogue sweep and the extraction pipeline | `status/catalogue-sweep.md` |
| The content gap retriage | `status/content-gap-retriage.md` |
| Phase-1 and phase-2 book scans | `status/phase-1-scan.md`, `status/phase-2-scan.md` |
| Core Charm re-transcription | `status/core-charm-retranscription.md` |
| Spell re-transcription | `status/spell-retranscription.md` |
| Book of Three Circles | `status/book-of-three-circles.md` |
| Corebook Wonders | `status/corebook-wonders.md` |
| Rated artifacts and attunement | `status/rated-artifacts.md`, `plans/artifact-attunement.md` |
| Artifact discovery backlog | `status/artifact-backlog.md` |
| Martial-arts styles | `status/martial-arts-styles.md` |
| Merits and Flaws | `status/merits-flaws.md`, `status/merits-flaws-triage.md` |
| Backgrounds | `status/backgrounds.md` |
| Trait reference text | `status/trait-descriptions.md` |
| Thaumaturgy | `status/thaumaturgy.md` |
| Custom content | `status/custom-content.md` |
| Dice pools and the dice roller | `status/dice-pools.md`, `status/dice-roller.md` |
| Elder Exalts | `status/elder-exalts.md` |
| Edit and XP merge | `status/edit-xp-merge.md` |
| Advantages tab | `status/advantages-tab.md` |
| Gear tab, inventory, shop | `status/gear-and-inventory.md` |
| Catalogue picker dialogs | `status/catalogue-dialogs.md` |
| Printable PDF sheet | `status/printable-sheet.md` |
| Adversary roster | `status/adversary-roster.md` |
| The `engine/validate/` split | `plans/validate-refactor.md` |
| The Qt port. Read the standing rules first. | `plans/qt-port.md` |
| The hosted table and the board. Read before any hosting work. | `plans/vtt.md` |
| P4, the board: the rulings, the build log | `plans/p4-board.md` |
| P3, campaigns: the design, the build order, the open questions | `plans/p3-tables.md` |
| Deploying to the home server: the container, the tunnel, the backups | `deploy/homeserver.md` |
| Variant-menu Charms | `plans/variant-menu-charms.md` |
| Why the Mist numina are deferred: there is no effect list to author | `status/mist-numina.md` |
| The full multi-splat plan | `~/.claude/plans/should-we-plan-out-encapsulated-crab.md` |
