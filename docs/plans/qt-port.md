# Plan — a PySide6/Qt native app alongside the NiceGUI webapp

**Status: COMMITTED — decision 0018, 2026-08-20.** Raised by the human 2026-08-10 as
the intended direction *after* the 1.0 ship (feature-complete: sourcebooks, the full
artifact and spell catalogues). The two spikes below answered its open questions and the
human approved both; **decision 0018** records the commitment. This file is now the
port's build record.

**The goal, stated plainly by the human 2026-08-20: a native, non-Electron desktop app
offered *alongside* the browser webapp.** That is the point of the port, and it settles
the counterweight below: this is not ~10,000 lines rewritten for aesthetics, and it is
not the pywebview middle path either — the human wants **native widgets**, not a packaged
browser. The webapp stays a shipping product; the shared `view.py` presenter is what
makes "one engine, two thin shells" tractable.

**1.0 shipped 2026-08-17; this was never a 1.0 blocker and is still not scheduled.** A
different widget toolkit is not a feature; it is the foundation a 2.0 native app is built
on, offered alongside the existing webapp.

## Why it is feasible — the measured baseline

Measured 2026-08-10 at 2,092 passing tests; LOC re-measured 2026-08-20 (suite is 2,455,
per CLAUDE.md). These numbers are the whole argument, so re-measure before acting on them
rather than trusting the table:

```sh
for d in models engine ui; do find exalted_builder/$d -name '*.py' | xargs wc -l | tail -1; done
grep -rln nicegui exalted_builder/          # which modules are actually bound to it
grep -rc "nicegui_main_file" tests/*.py     # which tests die with the toolkit
```

| Layer | LOC 2026-08-10 | LOC 2026-08-20 | Survives the port? |
|---|---|---|---|
| `models/` | 3,579 | 4,280 | Yes, untouched |
| `engine/` | 10,615 | 13,131 | Yes, untouched |
| loader / persistence / `custom_content` / … | 1,320 | 1,569 | Yes, untouched |
| `ui/view.py` — the presenter | 2,439 | 3,186 | **Yes** — imports no UI toolkit |
| `ui/pdf.py` (new since 08-10) | — | 900 | **Yes** — reportlab, toolkit-free; shipped 08-14 |
| `ui/theme.py`, `ui/assets.py` | 214 | 213 | Palette data yes; the Tailwind class strings die |
| the 13 NiceGUI widget modules | ~9,200 | ~10,490 | **No — this is the rewrite** (gear.py, 947, is new) |

Tests split the same way: **1,747 of 1,975 test functions are framework-free**; only
**228** use the NiceGUI `user` harness.

Two facts make this unusually cheap for a UI port, and both are decision 0002
("data-driven rules, pure engine, **disposable UI**") having actually been honoured
rather than merely written down:

1. **Nothing outside `ui/` imports `nicegui`.** The engine, the models, the loader and
   persistence are toolkit-agnostic today. Verify with the grep above before starting —
   if that stops being true, fix it first, because it is the precondition for everything
   else here. **Verified 2026-08-20:** the files importing it are exactly the 13 widget
   modules.
2. **`ui/view.py` is a pure presenter.** Its own docstring says it imports no UI toolkit
   and is unit-testable standalone. It is the largest file in `ui/` and it ports as-is.

## What does NOT translate — the paradigm shift

This is the real cost, and it is not measured in lines.

The current UI idiom is **declarative rebuild-the-world**: `@ui.refreshable`,
`body.refresh()`, regenerate the panel and let the framework diff it. Qt is
**retained-mode**: build the widgets once and mutate them, or go model/view
(`QAbstractTableModel` + signals). Rebuilding a panel per keystroke in Qt is possible but
flickery and wasteful.

So `advantages.py` cannot be ported line by line — it gets re-architected. Budget for
that, not for a transliteration. The corollary is that a port attempted as a mechanical
translation will produce something that works and feels wrong.

## What it buys — and the honest counterweight

Three things genuinely argue for Qt here:

* **The charm-tree picker.** `cytoscape.min.js` is vendored in `ui/vendor/` for it.
  `QGraphicsView` is a better fit for boxes-and-arrows with pan/zoom/hit-testing, and
  drops a JS dependency from a Python project.
* **Printing — a former argument, now resolved without Qt.** `ui/pdf.py` (reportlab,
  2026-08-14, 33 tests) generates real PDFs and **carries over untouched** — it imports no
  `nicegui`, so it joins the free-carry set. The plan's original "browser print CSS"
  concern was answered by a generated PDF, not a toolkit change; `QPrinter` is off the
  table.
* **A whole class of bug disappears.** Every one of these was paid for in real sessions
  and none exists in Qt: the nested-dialog canary trap and slot-deleted-mid-handler
  (`docs/status/catalogue-dialogs.md`), `@ui.refreshable` inside a loop, `ui.scroll_area`
  not sizing from `max-h`, and the test harness dispatching clicks without bubbling.

The counterweight, stated so it is not forgotten: **NiceGUI already packages to a
standalone executable** via `pack/` (the `desktop` extra, PyInstaller). That is a
**packaged browser** — native window chrome around the same DOM. The human has said
plainly (2026-08-20) that the goal is a **native-widget app offered alongside the
webapp**, which the packaged-browser middle path does not deliver (same DOM, so the whole
NiceGUI bug class stays). So the honest ledger is now: **~10,490 lines of rewrite, buying
the native offering itself plus the charm tree — printing is already off the board**
(reportlab, `ui/pdf.py`). The webapp is not abandoned: both shells ship, and the shared
engine + `view.py` is what keeps both thin.

## The prep work — ordinary hygiene, port or no port

The human's own framing (2026-08-10): *the refactor we'd do by moving things into
`view.py` would probably clean it up a good bit.* That is the point. **Every line moved
out of a widget module into `view.py` now is a line not written twice**, and it improves
the NiceGUI build on its own merits whether or not the port ever happens.

* **Push derived state out of the widget files.** The three big ones are
  `ui/picker.py` (2,313), `ui/editor.py` (1,785) and `ui/advantages.py` (1,297) —
  5,395 lines, of which the layout is genuinely UI and the rest is presentation logic
  that belongs in `view.py`.
* **Convert click-through tests into presenter assertions where the assertion is really
  about data.** A `should_see` test dies with NiceGUI; the same claim made against a
  `view.py` function survives the port, runs far faster, and is a better test anyway.
  Do it opportunistically, not as a campaign — some of those 228 genuinely test wiring
  and must stay UI tests.
* **Keep the `nicegui`-free grep green.** It is the invariant the whole plan rests on.

None of this is speculative work for a port that may not happen: it is the same
separation decision 0002 already asks for.

### The audit — what a sweep of `ui/` actually found (2026-08-10)

A pass over every module-level function in `ui/` whose body never touches the toolkit.
**Tiers 1 and 2 are done; tier 3 is recorded here and deliberately NOT scheduled** —
it is small, it is spread thin, and it is best swept up while porting the module it
lives in rather than as a task of its own.

Done already:

* **`engine/thaum_actions.py`** — 206 lines of lock-dispatching thaumaturgy purchases
  moved out of `ui/picker.py` (verbatim; `picker.py` re-exports every name).
* **Tier 2, `ui/adversaries.py` 640 → 487 lines.** Ids, duplicate naming and the
  trait/attack codec went to `engine/adversaries.py`; `summary_line` and
  `trait_map_line` went to `view.py`. **The interesting finding:** `trait_line` and
  `attack_line` look like presenters and are not — they fill the edit inputs that
  `parse_traits`/`parse_attacks` read back, with the round trip asserted in tests, so
  they are codec halves and went to `engine/` with their parsers. *Model→text does not
  imply `view.py`; ask what reads the text back.*
* **Tier 1, the two places one printed rule was encoded twice** —
  `editor._BASE_HEALTH` is now `Counter(derive.BASE_WOUND_PENALTIES)` instead of a
  hand-written `{0: 1, -1: 2, -2: 2, -4: 1}`, and the weapon/armour stat lines are one
  copy in `view.weapon_stat_line` / `armor_stat_line` instead of two. **The armour pair
  had already drifted** (two spaces before `Mob` in the row readout, one in the
  catalogue dialog, while the dialog's docstring claimed they matched) — the cheapest
  possible demonstration that duplicated presentation does not stay in sync.

**Tier 3 — carry these into the port, module by module.** Each is a handful of lines
that belongs in `view.py` (presentation) or `engine/` (rules), and each is already
toolkit-free, so it is a lift-and-shift whenever its module comes up:

| Where | What | Belongs in |
|---|---|---|
| ~~`ui/play.py` (~42L)~~ **DONE 2026-08-22** (`2ac4465`) | `play_state`, `normalize_health`, `cycle_mark`, `set_motes`, `set_count` — the PlayState mutators, and the "ui/play.py precedent" the thaumaturgy move cited. **⚠ decision 0006:** if these land in an `engine/play.py`, play-state must stay unreachable from validation | `engine/` |
| ~~`ui/play.py`~~ **DONE 2026-08-22** (milestone 6) | `worst_penalty` — already takes a `viewmod.PlayView`; `ui/play.py` re-exports it for `ui/gm.py` | `view.py` |
| `ui/editor.py` (~25L) | `_origin_options`, `upbringing_options`, `_heritage_uses_origin` — splat-shape questions, i.e. rules | `view.py` or `engine/` |
| `ui/builder.py` (33L) | `visible_tabs` — which tabs a splat shows | `view.py` |
| `ui/storyteller.py` (19L) | `set_rule` — HouseRules coercion | `engine/` |
| `ui/app.py`, `ui/advantages.py` | three separate dot-string formatters: `_dots`, and `'•' * rating` inline at `advantages.py:319` and `:395` | `view.py`, one copy |

**Checked and clean, so nobody re-audits them:** `engine/` imports `ui/` zero times and
`models/` imports `engine/` zero times — the layering rule holds. `RuleSet.backgrounds_for`
/ `budgets_for` / `bonus_costs_for` are data accessors on the data object and are fine
where they are. `picker._style` / `_elements` / `_node_classes` are the Cytoscape
adapter — genuinely toolkit code, and precisely the ~72 lines that get rewritten against
`QGraphicsView`.

## Sequencing, when it starts

1. 1.0 is shipped (2026-08-17). The webapp is a **co-shipping product, not a parallel
   target**: during the port it is frozen and becomes the reference implementation to
   diff behaviour against. Both shells ship afterward; the engine + `view.py` hold the
   logic, so a feature mostly lands in shared code with a thin touch-up in each shell.
2. Branch. Build the Qt layer up against the untouched `engine/` + `models/` +
   `view.py` until it reaches parity; only then does it become 2.0's bedrock.
3. Write **decision 0018** at the moment of commitment, recording the rejected
   alternatives so a later session does not reopen it: *stay NiceGUI-only* — the packaged
   `pack/` webview is "native enough" (the human has rejected this: native **widgets** are
   the point); *NiceGUI `native=True` via pywebview* (native window, same DOM — none of
   the native benefits); *a Qt port before 1.0*; *no native app at all*.

## The charm-tree spike — DONE 2026-08-20, human-approved

The tree picker is the one widget the current toolkit fights hardest — the reason it has
been deferred since before this plan was written (`cytoscape.min.js` still sits in
`ui/vendor/`, and the adapter in `picker.py` is only ~72 lines). The two questions this
plan needed answered cheaply were answered with **`spikes/qt_tree/`**: a standalone
bare-Qt process that imports the framework-free `models` + `rules_db.load_ruleset` +
`ui.view.build_charm_graph` data layers and renders real Charm trees, with **no change to
any existing file**. The human drove it across every splat and called it "very, very
good."

1. **`QGraphicsView` fits the charm-tree picker.** The spike grew into: a per-splat tab
   bar mirroring the app's `GROUPS` (Charms / Martial Arts / Arcanoi as trees, Spells
   and Thaumaturgy as panels); a tidy-tree forest layout (nodes centred over children,
   spaced by real width, wide levels sub-rowed, root-leaves on their own row); roots
   grouped by the children they feed (fan-in trees read as clusters); edge routing that
   detours a prerequisite line around node boxes it would cross AND offsets parallel
   detours onto separate rails; arrowheads that never hide under a node; fit-to-view
   that re-fits on resize without blocking wheel zoom; and a detail panel showing the
   app's own `build_charm_detail` (description, requirement, prerequisite groups).
2. **Retained-mode widgets test well with pytest-qt.** The spike carries **28 tests**
   (offscreen, `QT_QPA_PLATFORM=offscreen`) covering layout invariants, routing, arrows,
   fit, the per-splat tab set, and panel content — no browser harness.

**Findings a port keeps or revisits** (each is real, not cosmetic):

- **The 11-root star** (Prismatic Arrangement of Creation): sub-rowing caps rows at 6
  and root-leaves move to their own row, but eleven sibling subtrees cannot be packed
  narrower without overlap — the total width is the data's, and fit-to-view is the
  mitigation. "Grouping by prerequisites" (roots ordered by shared children) cut its
  edge span 34%.
- **`setMaxVisibleItems` is ignored for popup HEIGHT** on this Qt build — a `CappedCombo`
  subclass constrains the popup window itself once it opens.
- **Wheel-zoom makes scrollbars appear and fires resize events** — re-fitting those
  undoes the zoom; the view marks itself "just zoomed" and skips resize re-fits briefly.
- **`resizeEvent` only fires on a SHOWN widget** — a test-only foot-gun.
- **Ghosts get no Spells tab** — `accessible_circles` gives a ghost no circle; the human
  confirmed this is correct (ghosts cannot learn necromancy). Not a gap.

**Deliberately not covered** (human, 2026-08-20): the splat-specific picker extras
(Form Library, Paths, Vat Refit, Elemental Powers) and per-splat theming (Qt Style
Sheets) wait for the actual port.

Run/test: `spikes/qt_tree/README.md`. `PySide6` + `pytest-qt` are in `.venv` for the
spike only and deliberately **not** in `pyproject.toml` — they join their proper extras
when the port is committed. With the spike singing, **0018 writes itself**; the
sequencing above stands.

## The sheet-view spike — DONE 2026-08-20, human-approved

The plan's other open rendering question — **does the sheet view become a
`QTextDocument`?** — was answered with **`spikes/qt_sheet/`**: a standalone bare-Qt
window that renders a real `ui.view.build_sheet_view` into a `QTextDocument` and prints
it via `QDoc.print_(QPdfWriter)` — one source for the on-screen sheet and the PDF.
It reuses `build_sheet_view`, `weapon_stat_line`, `armor_stat_line`, `theme.palette`,
and the four example characters in `examples/`. The human drove it across all four
splats and approved it.

**Yes — the sheet becomes a `QTextDocument`.** Findings a port keeps:

- **Dots (`●`/`○`/`□`) and accent colours render and print** — QTextDocument's HTML
  subset is enough for a real sheet.
- **The layout must be sized for the A4 page, not the window.** The 900px on-screen
  view hides column-cramming that the ~550pt printable area exposes (truncation,
  mid-word breaks). The spike settled on 3-column trait bands and 2-column advantages.
- **⚠ A document shown in a QTextBrowser has its page size rewritten to the viewport**
  (unbounded height) — printing it then makes Qt render PAGE NUMBERS. `print_pdf`
  resets the page size to the paper first; without that, every in-app print carried a
  "1"/"2" footer the offline path never had (a real, hard-to-find bug — the human
  caught it).
- **`page-break-before: always` IS honoured** — used to keep the trait band and
  Charms on whole pages.
- **Health labels pad in a MONOSPACE font**: proportional fonts make character-count
  padding unequal ("Incap" pushed its boxes right); monospace makes nbsp padding exact.
- **Health boxes group by level** (consecutive same-level boxes, one label), and the
  ★ for Charm-granted levels is dropped — the boxes are identical in play.
- **Specialties are instances, not rated traits** — "multiple dots" means multiple
  copies of the specialty; the sheet merges them and shows plain dots, no 5-track
  (human 2026-08-20).

14 tests (offscreen). Run/test: `spikes/qt_sheet/README.md`.

## Milestone 1 — the native shell + Edit/Charms/Sheet (2026-08-20)

The first build slice, on branch `qt-port`. `exalted_builder/qt/` holds the native
shell (`main_window.py`, `__main__.py`) and the three ported tabs (`sheet.py`,
`charms.py`, `editor.py`), each a retained-mode widget re-derived from the shared
engine + `view.py`. Run: `.venv/bin/python -m exalted_builder.qt [path]`.

- **Shell** mirrors `ui/builder.py`: a toolbar (New/Load/Save/Print/Finish & Lock/
  Unlock/Party) over a tab bar whose visibility follows `view.visible_tabs` /
  `resolve_tab` on both sides of the lock. Gear, Advantages, Combos, Play, ST and
  Custom are explicit placeholders until their modules are ported. The Print button
  uses reportlab `ui/pdf.py` (the plan settled printing without Qt); the Sheet tab's
  on-screen document is the QTextDocument path from the qt_sheet spike.
- **Sheet** = the qt_sheet spike's `sheet_html`/`build_document`/`print_pdf` carried
  over; **Charms** = the qt_tree spike's layout/routing/view stack carried over,
  reading the live character instead of the spike's throwaway per-splat one. Ghosts
  correctly get Arcanoi and no Spells; Solar gets Charms/MA/Spells/Thaumaturgy.
- **Edit** is a re-architecture, not a transliteration (the plan's "What does NOT
  translate"): dot tracks are `DotTrack` widgets that free-set in chargen and hand
  post-lock clicks to `engine.advancement` (decision 0013, with the refund-vs-curse
  dialog). Covers Identity, the structural selects + cascades, Attributes, Abilities,
  Crafts, Virtues, Essence/Willpower, the chargen/XP side column, and the read-only
  Charm/Spell counts. **Deferred inside Edit** (each still ships on the webapp):
  Training Camp & Calling, Colleges, Specialties, Permanent Resonance/Limit, the
  Virtue Flaw, bonus health levels, and the Downtime calculator.
- **Tier-3 moves done here** (to `ui/view.py`, toolkit-free; the NiceGUI modules
  re-export the names so tests and callers keep working): `_TABS` +
  `visible_tabs`/`resolve_tab` (from `ui/builder.py`), and `_SPLAT_ORIGINS` +
  `_ORIGIN_UPBRINGINGS` + `_origin_options`/`upbringing_options`/
  `_heritage_uses_origin` (from `ui/editor.py`).
- `pyproject.toml` gained a `qt` extra (`PySide6`, `pytest-qt`) — the spikes' promise
  kept. `tests/conftest.py` pins `QT_QPA_PLATFORM=offscreen` and shares a `ruleset`
  fixture; **39 pytest-qt tests** cover the shell (tab set both sides of the lock,
  ghost hides Combos, New resets, the theme), the sheet (sections, accent, print), the
  charms trees (per-splat tabs, node/edge counts, layout, zoom, detail) and buying
  (chargen append, post-lock XP, Thaum art/specialty/formula with unlearn + the
  orientation combo), and the editor (DotTrack, the Favored picker, structural
  cascades, post-lock XP buying). Full suite on the `qt-port` branch: **2,448 passed,
  3 skipped** (2026-08-20).
- **The nicegui-free grep is still green** — nothing in `exalted_builder/qt/` imports
  NiceGUI, and nothing new does.

### Buying — the picker's business half

The Charms tab's spike was browse-only; this milestone added the purchase path, the
same toggle semantics as the web picker (chargen picks against the budget, post-lock
XP via `engine.advancement`):

- **Charms** (tree node selected) and **Spells** (list row): Learn/Remove, priced on
  the button post-lock (`Learn X — N XP`); a chargen pick is free and just says
  `Learn X`. Already-known post-lock notifies to Undo on the Edit tab.
- **Thaumaturgy**: Arts and their **specialties** (grouped under each Art in a
  collapsible `QTreeWidget`), Sciences (Raise a dot), Rituals/Formulas. The detail and
  the button carry the price (`N BP/XP`). Rituals/Formulas get an **orientation
  picker** (North/South/East/West/Realm) that appears only when buying the first
  orientation.

⚠ **This was the port's first duplicated RULE, and it is now extracted** (2026-08-21).
Thaumaturgy was fine — it already went through `engine/thaum_actions.py`, which is why
`qt/charms.py` could just call it. Charms, spells and the two variant-menu packages
were not: the Qt picker re-implemented the lock dispatch, the guards and the message
text by hand from `ui/picker.py`. They drifted **within one milestone** — the web
picker branches to a variant menu in its detail card before an Add button is ever
drawn, and the Qt picker toggles straight from a node click, so an Ox-Body click would
have appended the package Charm's id into `character.charms`.

`engine/charm_actions.py` is that logic in one place, `thaum_actions`' shape exactly,
and both shells are now thin `_act(...)` notification wrappers over it. The guard that
was living in a WIDGET is now `charm_actions.variant_menu_reason`, where every shell
runs it.

**The general rule this milestone bought: a purchase surface gets its engine
dispatcher BEFORE it is ported, not after.**

⚠ **The rule is "ask the question", not "always extract".** Asked of Advantages
(2026-08-21, before porting it) the answer came back NO: it has no lock-toggle to
extract, its post-lock half is already `engine/advancement.py`, and its chargen half is
`list.append`. An `advantages_actions.py` would be a module with nothing in it. What it
needs instead is two small widget-resident decisions moved out (`_default_tier`'s
splat-aware default, `_gain_mf`'s merit-vs-flaw side resolution) — the reasoning and
the Prodigy trap are in `docs/status/handoff.md`, "Advantages is NOT shaped like
Charms". **Apply the same test to each remaining tab rather than assuming its answer.**

### The theme — a desktop app, not a web-app mimicry

The human's direction (2026-08-20): stop mimicking the web app; a native app should
look native. One **unified dark** base (brighter than stock Qt6 dark-grey —
`#333338`/`#3d3d45`, off-white text), with the splat showing as **light** touches —
the printed palette accents are dark and invisible on dark, so `theme.accent` lightens
each toward white; it carries the toolbar, headings, the selected tab and chips. No
element borders anywhere (the card shade vs the page is the delineation); the Sheet
tab stays light "paper" (it is a document), the charm trees get a slightly lighter
canvas. `exalted_builder/qt/theme.py` holds the palette→Qt mapping.

### Human-verified on the real display

The human drove the shell across several click-through rounds and tuned against their
feedback — this is not "tests green, unverified". Remaining to look at: the six
placeholder tabs, per-splat theming beyond the accent, the picker's splat extras
(Forms/Panoply/Paths/Elemental), and Edit's deferred panels.

### Bugs that cost real iterations (all re-testable, all have tests now)

- **The `deleteLater()` deferral.** `reload()` runs synchronously several times at
  startup (constructor, the first tab-change signal, `_sync_tabs`); widgets that were
  only pending-delete kept painting at stale geometry, stacking each build on the last
  — "every element has its own boundary" + garbled text. Detach (`hide()` +
  `setParent(None)`) before `deleteLater()`.
- **Qt QSS reads 8-digit hex as AARRGGBB (alpha first).** `#RRGGBBAA` scrambled every
  accent border into a mauve. ⚠ in `qt/theme.py`.
- **Every side-column label stretched to ~72px** — the cards filled the splitter and
  the labels stretched with them ("Live Validation too spaced out"). A trailing
  `addStretch` keeps cards at natural height.
- **A `QTabWidget` that is never `setCentralWidget` renders a blank window.**
- **The tab widget fires `currentChanged` during construction** — block signals while
  building, or the first page reloads before the other tabs exist.
- **PySide6 QComboBox has `textActivated(str)`, not `activated[str]`** (IndexError).
- **PySide6 stores an Enum's str value in a combo's userData** — reconstruct with
  `Orientation(raw)`.
- **The stale-selection trap.** After a buy/drop, the selected Thaumaturgy row kept
  its pre-action `owned` flag, so the button stayed "Learn" (a re-click refused
  "already known"). Re-find the entry in a fresh picker after the action.
- **19/25 Thaumaturgy specialty rows have no description in the source** (they are
  just aspect names in the book) — a data reality, not a bug. The price fills the
  detail instead.

## Milestone 2 — the left-rail shell; Edit splits into Identity + Traits (2026-08-21)

The human approved the `spikes/qt_edit/` layout — the whole app as a master-detail
(a left rail of tabs, a readout bar, a bottom status strip) — and it is now the real
shell.

- **Shell** (`qt/main_window.py`): the top QTabWidget became a left rail
  (`QListWidget#appRail`, accent-selected) over a QStackedWidget, with the app's
  `viewmod._TABS` where "Edit" is split into **Identity + Traits**. A readout bar
  (budget · validation) whose "≡ details" opens a click-to-open popover holding the
  issue list + bonus-point breakdown + (post-lock) the Experience card + ledger; a
  bottom status strip (Willpower · pools · Soak). The old Edit-page side column is
  gone — its content moved into the popover. `_sync_tabs` maps the old "Edit" key to
  showing both Identity and Traits; a resolved "Edit" answer lands on Identity.
- **Edit split** (`qt/editor.py`): the monolithic EditPage became `IdentityPage`
  (name/concept/anima, the structural selectors, the free-fill biography, the caste
  info) and `TraitsPage` (favoured-pick chips, Attributes/Abilities/Crafts/Virtues/
  Essence, the read-only Charm & Spells count), sharing a `_EditorPage` base
  (DotTrack, _FavoredPicker, _buy, the refund-vs-curse dialog, scroll-hold).
- **Bio fields** (`models/character.py`): ten free-fill `str = ""` fields (sex, age,
  eye/hair/skin colour, height, weight, description, backstory, notes) — pydantic
  defaults keep every old save loadable. They print on the PDF sheet's header.
  ⚠ The NiceGUI web app's Identity does NOT expose them yet (deferred by the human
  2026-08-21).

Test count at this milestone: **2,482 passed, 3 skipped, 1 warning** (2026-08-21,
measured in the since-removed `-ds` worktree). After the `charm_actions` extraction
below, and in the main checkout where `qt-port` now lives: **2,541 passed, 1 skipped,
1 warning** (7m00s). ⚠ **The two are not reconcilable and must not be reconciled** —
this checkout has `sources/` and a fuller `images/`, so dozens more tests COLLECT
(the `images/`-presence deferral pattern). Record where you measured, as here.

### Human-verified on the real display

The user clicked through the new shell and approved it. What to look at: the Identity
bio + caste info, the Traits dot tracks, the "≡ details" popover on both sides of the
lock, and the rail's Play appearing at the lock.

### Traps that cost real iterations (all re-testable)

- **A QTextEdit inside a `_Panel` renders the card shade no matter what.** The
  panel's own QSS (`QFrame { background:CARD }`) forces the stylesheet renderer onto
  every descendant, so the QTextEdit's viewport paints CARD — the window QSS
  `background` and a manually-set palette both lose. The fix is an inline stylesheet
  ON the QTextEdit itself (`QTextEdit { background:INPUT; ... }`), which wins over
  the ancestor. (The "Description/Backstory/Notes fill-in invisible" bug.)
- **The INPUT shade was too close to CARD** — `#47474f` vs `#3d3d45` read as the
  same shade on a real display; brightened to `#52525c`.
- **`QTextEdit.textChanged` carries NO argument** (unlike QLineEdit's `str`) — a
  lambda that reads the signal's argument crashes on first keystroke; read the text
  off the widget instead.
- **A `dict.fromkeys` rail-label dict yields None values** — every rail item rendered
  empty. Build the label dict with a comprehension.
- **The rail's `currentRowChanged` handler must call `stack.setCurrentIndex`** — a
  reload-on-select handler that forgets to switch the stack leaves the old page up.
- ⚠ **A teardown sweep MUST recurse into nested layouts.** `item.widget()` is `None`
  for a `QLayout`, so a widget-only loop detaches nothing inside a row and the previous
  build paints ON TOP of the next. This has now bitten **twice** — `_clear_lay`
  (milestone 1) and `CatalogueDialog._clear_extras` (milestone 3) — and it will bite any
  new surface that builds its content as rows, which is all of them. Copy the recursive
  shape; do not write a fresh loop. **Test it by thrashing the rebuild several times and
  counting live descendants**: a single rebuild passes while leaking.
- **`deleteLater()` alone is not enough** — it is deferred to the event loop, so hide
  and unparent NOW or a pending-delete build keeps painting at stale geometry.

## Milestone 3 — the Advantages tab (2026-08-21)

Backgrounds + Merits & Flaws + (for ghosts) Fetters and Passions, on one native
surface: `qt/advantages.py`, filling the rail's placeholder. The two prep moves the
previous milestone's "ask the question" audit called for were done FIRST, so no rules
decision was copied into a second widget:

- **`view.default_merit_tier(definition, exalt_type, caste)`** — the splat-aware
  default a fresh M&F row opens on, plus `view.merit_tier_label` and
  `view.merit_option_label` (the signed "−4 supernatural" menu line). `ui/advantages.py`
  now delegates to all three.
- **`advancement.gain_merit_or_flaw`** — the merit-vs-flaw side resolution and both of
  its refusals ("Pick a Merit or Flaw first", "…is a Merit OR a Flaw — pick which
  side"). Which of `buy_merit` / `gain_flaw` runs is what makes the XP positive or
  negative, so it is a rules decision, not layout. Both shells call it now.

- **`qt/catalogue.py`** — the native browse-before-you-choose dialog, taking the same
  `(key, name, summary, full)` rows and `on_pick` contract as `ui/catalogue.py` (so
  Gear can reuse it). The filter HIDES rows rather than removing them, which is what
  keeps the current selection alive while typing.
- **`qt/advantages.py`** — one row body per list, two regimes off `char.chargen_locked`:
  a Background is a DotTrack pre-lock and a free QSpinBox post-lock (ceiling from
  `background_rating_cap(..., post_lock=True)`, never a hardcoded 5); M&F are editable
  rows pre-lock and the gain/lose card post-lock; a Fetter is a DotTrack pre-lock and
  read-only pips + the priced Raise/Form/Shift controls after; a Passion keeps a FREE
  dot track on both sides (its dots come from the Virtues — p.283 — and are never
  bought).

Three things the port had to decide for itself, all recorded because the web original
answers them differently:

- **The tab's own readout is the ISSUE list only.** The shell's readout bar already
  prints the bonus-point total; printing it here too put the same sentence on screen
  twice. Post-lock the line becomes XP available + any debt.
- **Long printed prose is clamped with the full text on the tooltip** (`_clamp`). The
  web app's blurbs are CSS line-clamped; Qt has none, and a Manse's full paragraph
  pushed every other row off the panel.
- **A merit row is TWO lines, not a wrapping one.** Qt has no flex-wrap, and a no-wrap
  row crushes its later children to slivers — the entry combo + delete sit on the first
  line, the entry-specific controls (side, tier, arena, points, artifact,
  stipulations, detail) on the second.

⚠ Traps carried over and re-tested here: the Prodigy default tier; the Hearthstone
DENOMINATOR moving with the Manse rating; the custom-row discriminator being the EMPTY
`merit_id` and never `custom_name`'s truthiness (the name box writes it per keystroke);
and the filter re-optioning rows in place rather than rebuilding the search box.

One shell fix fell out: the pages are built before the status strip existed, and
`AdvantagesPage` derives its issue line during construction — `self.status` is now
created before the pages, and the readout no longer opens on " · " post-lock.

Tests: `tests/test_qt_advantages.py` (43), plus the extractions' own —
`test_view.py` (4: the Prodigy default, the blank menu, the signed label, the tier
label) and `test_merit_postlock.py` (5: the side resolution's two refusals and its
three routes).

### Human-verified on the real display — 2026-08-21

Clicked through and **approved**. Backgrounds read correctly first time; the pickers did
not, and the fix (buying moved INTO the catalogue dialog, for every picker that has a
choice to make) plus the two bugs it introduced and the summary clamp are written up in
full in `docs/status/advantages-tab.md`. The one line worth carrying here:

⚠ **A control can be correct, reachable, tested, and still nowhere near the thing it
configures.** The M&F tier/side controls sat on a card below the fold, so picking an
entry looked like it did nothing. Every offscreen test passed, and a screenshot test
would have passed too. **Watch for this shape in Gear, Combos and Play** — those all
have pickers, and `qt/catalogue.py` now carries the answer (`extras` + `confirm` hooks,
game logic staying in the caller).

### The Charms tab's open delay — a catalogue-scan problem, not a rendering one

The human reported "a notable loading delay" opening Charms and assumed the
`QGraphicsView` trees were the cost. **They were not.** Profiling one page build found
`charm_matches_splat` called **190,859 times**. Three helpers are pure functions of the
ruleset (and, for the augmentation category, the character's splat) but each SCANS the
whole 1,921-Charm catalogue — and each was being called from inside a loop over that
same catalogue:

| helper | calls per build | called from |
|---|---|---|
| `augmentation_category` | 93 | once per collapsed tree — ~180k of the total |
| `virtue_split` | 2,870 | once per Charm |
| `_arcanoi_categories` | 1,745 | once per `group_of` |

`reload` compounds it: `trees_for` runs five times — three to decide which tabs exist,
then again per page. A memo created fresh per rebuild and threaded through took the
build **0.791s → 0.099s**, with no rendering or layout change. Human: "Instant now."

⚠ **The obvious version of this fix is a bug.** Keying the cache on the RuleSet looks
right and is wrong: `rules_db.reload_custom_layer` mutates `ruleset.charms` **IN PLACE**,
deliberately, so that authoring a homebrew Charm becomes visible on every page already
holding the object. A ruleset-keyed cache would serve a stale catalogue precisely when
the player edits their custom content. So the memo is **per-build and never stored on the
page**; the one longer-lived copy (on `CharmTreeView`) is safe only because `_tree_page`
builds a new view every reload, and only splat-derived answers go in it — nothing keyed
on which Charms are OWNED, which changes under a live view on a buy.

Verified beyond the suite: cached and uncached `trees_for` agree for every example
character × every group, **and for Alchemical specifically** — it is the only splat whose
`augmentation_category` is non-`None`, so caching a `None` everywhere would pass a
Solar-only test while breaking the one splat that uses the feature.

⚠ The guard test pins the **mechanism** (one scan per build regardless of how many groups
are asked for), not a timing and not a call-count ratio. Two earlier versions were wrong
in instructive ways: the first asserted a 5× ratio *tuned until it passed*, the second
was off by one against the data (the test character has exactly 10 trees). Its negative
control now asserts only "more than once", so it will not rot when a Charm is added.

## Milestone 4 — the Gear tab; Combos moves under Charms (2026-08-21)

Everything the character OWNS on one native surface (`qt/gear.py`), filling the rail's
last big placeholder — and the Combos rail entry becomes a **Charms sub-tab** in the
same pass.

### The milestone-2 question, asked of Gear: YES

Unlike Advantages, Gear was full of rules living in a widget, and every one of them
would have been copied into a second shell. **`engine/gear_actions.py`** is
`thaum_actions`/`charm_actions`' shape applied to equipment: `add_row` / `remove_row` /
`remove_artifact`, `set_weapon` / `set_armor` (the catalogue re-pick), `grant_gear`,
`add_artifact` / `set_artifact`, `buy` (the shop's key dispatch) and the library codec
`library_payload` / `reserved_ids`. `ui/gear.py` went **947 → 650 lines** and is now
thin refresh wrappers.

⚠ **The extraction found a live bug in shipped code, and it is the `from_artifact` bug
on a sibling field.** `set_weapon`/`set_armor` REPLACE the row with a catalogue copy,
carrying the player's own fields across by a hand-written list. That list carried
`from_artifact` because a comment warned about it — and never knew **`acquired`**
existed. So re-picking a cash-bought artifact weapon's own name from its dropdown reset
it to `background` and charged the p.131 budget for something Resources had paid for.
Confirmed against the real catalogue before fixing:

```
budgeted before re-pick: []
budgeted after  re-pick: ['Daiklave']
```

The fix is not "add `acquired` to the list" — it is `_owned_fields`, the **complement**
of `_catalogue_stats`, both derived from the two pydantic models. What a copy leaves out
is exactly what gets silently discarded, so neither half may be written by hand.
**Generalises: when code copies one model into another field by field, derive the field
set from the models — a hand list documents the fields someone thought of.**

### Presentation moved to `view.py`

So the Qt shell re-derives none of it: `artifacts_header` (the budget line, all three
regimes), `artifacts_bought_note`, `artifacts_also_counted`, `inventory_heading`,
`inventory_filter_label`, `inventory_row_tags` (including the "Artifact N/A · by Merit"
plot-device case), `shop_rows` + `ShopRow`, `shop_custom_kinds`, `service_rows`, and
`catalog_weapon_summary` / `catalog_armor_summary` / `gear_cost_note` lifted out of
`ui/catalogue.py` (which re-exports them). ⚠ That last move is not tidying: `qt/` must
never import `ui/catalogue.py`, because it imports nicegui and "nothing outside `ui/`
imports nicegui" is the invariant the whole port rests on.

**Icons stayed per-shell** — `icon_for` returns Material Icon names and Qt draws from a
different set, so `ShopRow` carries `tags` and each shell picks its own.

### `qt/catalogue.py` grew the shop's two missing features

**Type chips** (`group_of`) and **multiple Custom buttons** (`custom_kinds`, the kind
riding back as `custom:<kind>`), plus `dimmed` for unaffordable rows. Still no game
logic: the dialog cannot tell a weapon from a bolt of silk and must not learn to.

⚠ **A chip click re-homes the selection; typing does not.** Hiding the selected row
leaves the confirm button labelled and enabled for something off screen, and `_choose`
then silently refuses — a dead button with no stated reason. Typing is exempt because
the selection must survive a half-typed word.

### ⚠ The tab was built TWICE, and the second build is the lesson

**The first version was the NiceGUI page transliterated** — a Buy button floating
mid-page with an explanatory sentence beside it, accordion "Edit" expanders, and a stack
of cards in a scroll area. Every test passed. The human's verdict on seeing it: *"the
page as a whole is a copy of the NiceGUI's look."* This plan predicted exactly that in
"What does NOT translate" — *a port attempted as a mechanical translation will produce
something that works and feels wrong* — and it happened anyway, because the content was
ported thoughtfully and the STRUCTURE was ported by reflex.

**The rule, and it governs every remaining tab: a new Qt surface copies
`qt/charms.py`'s LAYOUT, not `ui/<tab>.py`'s.** Toolbar for actions, table with a header
for lists, splitter with a detail pane for the selected thing.

| Web idiom | Native replacement |
|---|---|
| Buy button floating in the content flow | a toolbar (`Buy…`, `+ Artifact`, filter, search) |
| Filter pills | a `Show:` dropdown carrying live counts |
| Accordion "Edit" expanders | select a row, edit in the detail pane |
| `QLabel` rows in an HBox | `QTreeWidget` — sortable, five real columns, a header |
| Card stack in one scroll area | a splitter; Prices became its own sub-tab |
| Budget line inside a card | a status line under the splitter, spanning both panes |

A merged artifact row still renders **both** editors, now in the one detail pane.

Traps, all now tested:

- ⚠ **`editingFinished` fires on every focus loss**, and a name re-pick rebuilds the
  table — so an untouched combo must stay silent, or tabbing past it drops the player out
  of the row they are working in. The combo remembers its last text and compares.
- ⚠ **Re-optioning a filter combo emits `currentIndexChanged`.** Without blocking
  signals across the refill, the filter reset to "All" on every table rebuild — the
  filter was un-keepable while editing. `test_the_filter_survives_a_table_rebuild`.
- ⚠ **`setSortingEnabled(False)` across a fill.** With it on, Qt re-sorts after every
  insert — quadratic, and it scrambles insertion order.
- ⚠ **The selection is a POSITION**, and adding or deleting a row renumbers everything
  after it. `_rebuild` drops it rather than re-selecting whatever slid into that slot;
  `_fill_table` restores it when the row is still shown.
- ⚠ **A stat edit refreshes only its own table ROW**, never the whole table — a rebuild
  mid-keystroke would drop focus out of the spin box.
- ⚠ **The stat grid wraps at three pairs per row.** Qt has no flex-wrap, and thirteen
  weapon stats on one no-wrap line crush their later children to slivers — the trap the
  Advantages merit rows already paid for once.
- ⚠ **Address a widget by `objectName`, not by position in `findChildren`.** The first
  test of a stat edit grabbed `findChildren(QSpinBox)[0]` and got the row's *quantity*
  box — it passed a wrong assertion into existence. The stat boxes are named
  `stat.<field>`.
- ⚠ `Armor.mobility_penalty` is stored NEGATIVE, so its spin box is signed. A box
  floored at 0 makes every printed armour penalty unenterable.
- **No inline stylesheet on the inputs.** The window QSS already names `QSpinBox` /
  `QLineEdit` / `QComboBox`; setting only `background` inline wins and drops their
  colour, padding and radius.

### Combos is now a sub-tab of Charms

The human's call, and cheap because the Combos page had never been ported — so this was
a placement decision, not a move. A Combo is assembled out of Charms the character
already owns, and the two were a rail apart.

- `"Combos"` is gone from `_RAIL_TABS`; `_visible_rail_tabs` **discards** the presenter's
  answer about it rather than changing the presenter — `view.visible_tabs` is still
  exactly right for the webapp, where Combos stays top-level. **The two shells now have
  different tab sets, deliberately.**
- The **show/hide rule came with it**: `CharmsPage.reload` asks `has_combos_tab` itself
  (the dead may never learn Combos — E:Ab p.234), and the **Arrays** relabel for a
  Charm-Slot splat is `_combos_label`, still off `view.uses_arrays`.
- ⚠ **`resolve_tab` can still answer "Combos"**, which is no longer a rail tab. The
  `target not in _RAIL_TABS` fallback in `_sync_tabs` is what catches that, and it is
  **load-bearing now rather than defensive**.
- ⚠ **`test_shell_hides_combos_for_a_ghost` went stale the moment the rail entry
  vanished** — with nothing to hide it passed for every splat and proved nothing. It now
  asserts on the ghost's *sub-tabs*, with `"Arcanoi" in subtabs` as the positive control
  that the tab bar was built at all. Exactly the negative-control rot CLAUDE.md warns
  about, caught because the change was made deliberately rather than discovered later.

The page is a **placeholder in its new home** — the Combos surface itself is still on the
webapp.

Tests: `tests/test_qt_gear.py` (26), `tests/test_gear_actions.py` (21), plus the shell's
three new Combos tests. Full suite on `qt-port`, main PC: **2,659 passed, 1 skipped, 1
warning** (6m20s).

### Human-verified on the real display — 2026-08-21

Clicked and **approved** — but only on the SECOND build. The first was rejected on sight
as a copy of the webapp's look; see "The tab was built TWICE" above, which is the part of
this section worth reading. Combos-under-Charms was approved in the same pass.

⚠ **What the offscreen tests could not tell anyone:** the first version was tests-green
and smoke-driven across all four example characters — every rail page built, the shop
dialog opened, chips correct, artifacts appearing only post-lock — and it was still the
wrong design. *A control can be correct, reachable, tested, and still nowhere near the
thing it configures*; a whole tab can be all of those and still read as a web page.

## Milestone 5 — Advantages rebuilt as a collection; the layout is settled (2026-08-21)

Not a new tab: the **third** rebuild of an existing one, and the one that fixed the
pattern for everything left.

### The question, and the answer

Asked after the Gear rebuild — *"I think it's fine as is, but I am curious"* — and posed
concretely by a throwaway spike (`spikes/qt_advantages/`, now deleted): one window, the
real `AdvantagesPage` beside three mockups. **Is a tab a COLLECTION (browse and revisit →
table + detail) or a FORM (fill in once at chargen → everything visible)?**

The human ruled out the form candidate on sight, asked the two table candidates for the
full printed text on the right, and chose **B — a sub-tab per category**.

⚠ **This is now settled for the whole app, not just Advantages.** One layout: toolbar
for actions · a sub-tab per category where a tab has more than one · a sortable table
with a header · a splitter with the selected entry's editor in a detail pane. **Play, ST
Options and Custom get it. Do not re-litigate per tab.**

### What the rebuild changed, and what it did not

Most of `qt/advantages.py` survived — the catalogue dialogs, `_mf_purchase_block`, the
pricing, `_bg_cap_for`, `_merit_rules_text`, the hearthstones, the fetter/passion
controls. Only the CONTAINERS changed: five panel builders became three table fillers,
and `_background_row` / `_merit_row` became detail-pane editors.

Three things the pane can do that the card stack could not:

- **A Background shows its whole printed LADDER, with the rung held called out.** This
  was the human's condition for either table candidate. ⚠ It is not one paragraph — a
  Background's printed text differs per rating — and it reuses `view.background_ladder`
  rather than inventing a second rendering. The lookup goes through the SPLAT-FILTERED
  catalogue: `BackgroundEntry` stores a name, not an id, and several names belong to two
  splats with different text.
- **Post-lock, a held Merit shows its rules text.** The shipped card listed held entries
  in a dropdown and said nothing about any of them.
- **"Lose / buy off" acts on the table selection.** The card carried its own "Held"
  dropdown beside a list of the same entries — two controls naming one thing, and the
  one you were looking at was not the one the button acted on.

**One feature MOVED rather than being dropped.** The on-page filter bar (search + side +
category) is gone; filtering belongs where the choosing happens, so both M&F dialogs now
carry the five printed categories as `group_of` chips plus their own search box.
`_mf_matches` survives and still gates what a dialog offers — with no bar to set
`_mf_filter` it simply passes everything, which is what a self-filtering dialog wants.

### Traps

- ⚠ **`setSortingEnabled(True)` with no explicit indicator** sorted the first fill
  reverse-alphabetical, which reads as a bug rather than a sort. Pin it:
  `sortByColumn(0, Qt.AscendingOrder)`.
- ⚠ **Re-optioning a filter/tab control emits its change signal** — block signals across
  the refill or the selection resets on every rebuild. (Third time: Gear's `Show:`
  combo, the Charms tab bar, now this.)
- ⚠ **In the offscreen harness `isVisible()` is False for any widget whose parent was
  never shown.** A test asserting a button is visible fails however the code is written;
  assert `not w.isHidden()`.
- ⚠ **Deleting a container method takes its helpers with it.** `_fetter_play_controls`
  lived inside the `_fetters_panel` → `_do_reload` range and vanished with the panel; the
  post-lock Fetter test caught it. Check what a deleted range actually spanned.

Tests: `tests/test_qt_advantages.py` (54 — the 44 retargeted at tables and the pane, plus
10 for what shape B newly guarantees). Full suite: **2,675 passed, 1 skipped** (main PC,
`qt-port`, 6m55s).

### Human-verified on the real display — 2026-08-21

Clicked and approved.

## Milestone 6 — the Play tab (2026-08-22)

`exalted_builder/qt/play.py`, 689 lines, wired into the rail in place of its
placeholder. Both of the milestone's questions were already answered before the widget
was written — the engine extraction (`engine/play.py`, `2ac4465`) and the layout ruling
— so this was the widget and nothing else.

### The layout: the ONE stated exception

**Toolbar over panels**, not the collection layout (human, 2026-08-22). A tracker has
nothing to select: you click a health box and glance at a mote count mid-roll, and a
detail pane would hide the numbers the surface exists to show. Two scrolling columns in
a splitter — the tracker on the LEFT (the thing you click), the roll list on the right
(the thing you read) — under a toolbar holding `Clear damage` and `Clear motes spent`.

⚠ **An exception that is written down is not drift; a second unwritten one is.** ST
Options and Custom still get the collection layout.

The column order is the webapp's reversed, deliberately: on the web the pool sidebar sat
left, but every other Qt tab puts the interactive half left and the reference half
right, and the tab should read like the app it is in rather than like the page it came
from.

### What it renders

Health (clickable boxes carrying their wound-penalty labels, the marked counts and the
deepest penalty), armour fatigue, the Essence pools, temporary Willpower, Limit **or**
Clarity, luck pools, the custom Attribute + Ability pool, and the full roll list with its
controls and its exclusions block. Every capacity comes from `view.build_play_view` /
`view.build_pool_sidebar`; every mutation from `engine.play`. Zero game logic.

### What moved

`worst_penalty` went from `ui/play.py` to `view.py` — the last row of the extraction
table above, and the easy one: it only ever read a `PlayView`. `ui/play.py` re-exports
it, because `ui/gm.py` reaches it through that module by name.

### Traps

- ⚠ **Rendering must not create a `PlayState`.** `engineplay.play_state` writes one on
  first call, so the draw path reads `char.play or PlayState()` — otherwise merely
  OPENING the tab makes a never-played character save dirty. There is a test.
- ⚠ **A spin box must not trigger a redraw of the panel it lives in.** `clear_layout`
  would delete the widget mid-keystroke and take the focus with it. The mote and fatigue
  inputs write to the model and move only their own readout (plus the pools, which are a
  different widget); the box tracks are QPushButtons, so those can redraw freely. Same
  `_rebuild` / `_changed` split `qt/gear.py` uses.
- ⚠ **The shell stylesheet paints every QPushButton's hover the splat accent** — which
  is exactly the colour a FILLED Willpower box already is, so an empty box read as full
  under the mouse. Each tracker box sets its own `:hover` keeping its fill and adding an
  accent border.
- ⚠ **A word-wrapped QLabel inside a nested QHBoxLayout does not get its height.**
  `QLabel` sizes itself through `heightForWidth`; **QBoxLayout does not propagate that
  from a nested child layout**, so the first `_pool_row` — total in a column beside a
  nested QVBoxLayout of name + breakdown — drew every row on top of the one below it,
  sixty deep. The fix is to put both labels STRAIGHT into the panel's QVBoxLayout; the
  aligned total column was worth less than a legible list. **This is the shape to watch
  anywhere text wraps: a wrapped label wants an unbroken vertical chain to the top.**
- ⚠ **Screenshot only after the layout has SETTLED.** `w.show(); processEvents()` once
  catches the pre-layout pass — squeezed panels, clipped last lines, no scrollbar — and
  it looks exactly like a real sizing bug. Eight `processEvents()` and the same build
  renders correctly and scrolls. Two of the "defects" found this way were not real.
- **`PoolRow.note` had ZERO readers** — `build_pool_sidebar` fills it and neither shell
  rendered it. Species 2 of the house bug, in a field rather than a mechanism. It is a
  row TOOLTIP here; a paragraph per row on a list built for scanning is not an option.
- ⚠ **No `on_change` hook to the shell.** Play-state moves nothing the readout bar or
  status strip shows, and decision 0006 keeps it out of every one of them; a hook wired
  "for symmetry" would be a dormant invitation to change that.
- Health-track box colour changed shape from the webapp's: gold fill plus a tinted glyph
  reads as one colour at a glance on the dark base, so the BOX carries the damage type
  and the glyph only disambiguates it.

Tests: `tests/test_qt_play.py` (32).

### Human-verified on the real display — 2026-08-22

Clicked and **approved** — *"I like it; looks good."* First build, no rebuild. **The
toolbar-over-panels exception and the tracker-left / rolls-right split are both
confirmed**, which is what the click was for: those two were my calls, and the second is
the reverse of the webapp.

## Group 4 (within-tab gaps) — item 1: the variant-menu chooser (2026-08-22)

Not a milestone: the first of the **within-tab gaps**, which the human put ahead of
porting any further tab. The gap was that Ox-Body Technique and Deadly Beastman
Transformation had no way to be bought in Qt at all — `engine.charm_actions` already
refused the ordinary toggle (so the mis-write could not happen), but nothing offered the
RIGHT pick, and the Charm's node sat there answering "bought as a package — choose from
its detail panel" about a panel that did not exist.

### One presenter, one dialog, both Charms

`view.build_package_menu(ruleset, character, charm_id, selection)` is the new seam:
`PackageMenu` (kind, cap, cap trait/unit, `needed`, price, held packages, picks) plus
`package_menu_kind` and `prune_package_selection`. Ox-Body and Gifts differ in exactly
two things the widget can see — `menu.needed` and the picks' `reason` — so
`CharmsPage._build_package_dialog` draws both.

The web picker's `open_gift_dialog` now runs the SAME two functions; its local
`_blocked`/`_prune` are gone. That is the point of doing it in `view.py`: the Gift
legality cascade existed in one shell only, which is how `charm_actions` came about in
the first place.

⚠ **`CharmVariant.max_purchases` is 1 for every Ox-Body variant and means nothing
there** — a repeat purchase picks a variant again, same or different. The taken/max rule
is applied to Gifts ONLY; applying it to both greys the whole Ox-Body menu out after one
purchase, and every test on the Gift side still passes. There is a test for it.

### What the widget adds

* The node's action button reads **"Choose a package…" / "Choose Gifts…"** (with the XP
  price post-lock) instead of Learn, keyed on `package_menu_kind` — the character's own
  package-Charm ids, which no widget can edit.
* The detail pane appends **Bought N / cap** and each package's picks. The tree paints a
  node owned off one Charm id; how MANY packages is what a player needs here.
* The dialog: held packages each with **Remove** (pre-lock only — post-lock the undo is
  the XP ledger), the cap line in the splat's own cap trait, a checkbox per pick with its
  reason, and Add / Buy · N XP.
* A **one-pick menu replaces rather than blocks** — with `needed == 1` (Ox-Body always,
  Gifts after the first purchase) picking a second row swaps it in, so the rows read as
  radio buttons instead of greying out the moment one is ticked.
* The Charm's own description is **not** repeated in the dialog: it is already in the
  detail pane behind it, and Deadly Beastman's runs eleven lines, which pushed the picks
  off the first screen. The offscreen grab is what showed that.

`_build_package_dialog` returns the dialog WITHOUT running it (`exec()` blocks a headless
run) — the Gear/Advantages seam. Its handles are `.selection`, `.checks` (keyed by pick
key, never a `findChildren` index), `.confirm`, `.rebuild`.

### The click found two, and only one of them was in the new code

⚠ **A rebuild under the click sends a QScrollArea to the bottom.** Every Gift pick tore
the rows down and built them again; that deletes the checkbox being clicked, Qt hands
focus to the next widget in the chain, and a `QScrollArea` scrolls to whatever has focus.
The fix is the shape, not a scroll-position patch: a pick changes no row's EXISTENCE —
only ticked/enabled and the reason text — so `sync()` updates the rows in place and
`rebuild()` is reserved for a buy or a remove, where the held-packages list above the
picks really does change. (`rebuild` restores the scroll offset as well.) **The test
asserts widget IDENTITY survives a pick**, because that is the property that keeps the
scroll still; asserting the enabled states would pass over the bug.

⚠ **`CharmsPage` was the ONE page the shell built without `on_change`.** Identity,
Traits, Gear and Advantages all pass `on_change=self._refresh`; Play omits it
deliberately and says so in a comment. Charms just omitted it — so nothing bought on that
tab (Charms, spells, Thaumaturgy, packages, and now the packages' dialog) ever told the
shell its readout bar had moved, and a bonus-point spend sat stale in the top bar until
another tab was touched. **Not a bug in this work** — it predates the whole port's Charms
tab and was found only because a package purchase was the first thing anyone watched the
top bar during.

`_update_readout` is now a two-line wrapper over `_draw_readout`, because the body has
two exits (locked / chargen) and a hook appended to the end would have fired from one of
them. Two tests, one per half: the page fires the hook, and the shell passes it.

**This is the house bug's second species again** (`CLAUDE.md`): the mechanism existed,
every sibling page used it correctly, and the tab's own local readout updated fine —
which is exactly what made the missing half invisible.

Tests: 8 in `tests/test_view.py`, 11 in `tests/test_qt_charms.py`. Suite **2,729 passed,
1 skipped** (main PC, 7m12s).

### Human-verified on the real display — 2026-08-22

Clicked and **approved** — *"Looks good."* The two defects above are what that click
bought; both were fixed and re-clicked before the approval.

## Group 4 item 2 — Edit's seven deferred panels (2026-08-22)

Closes the itemised Edit gaps. `d157913` (five panels) + `b9ee454` (the last two).
**Green, NOT human-clicked at the time of writing** — the human's call was one
click-through over the whole Edit surface rather than one per panel. ⚠ That click
happened and the whole Edit surface was approved; this line was left standing and read
as a live claim for days. Corrected 2026-08-27.

| Panel | Home | Gate |
|---|---|---|
| Permanent Resonance / Limit | TraitsPage | `derive.permanent_limit_cap` — no caller names a Merit id |
| Virtue Flaw | TraitsPage | `derive.has_virtue_flaw` |
| Specialties | TraitsPage | always |
| Astrological Colleges | TraitsPage | `b.college_dots` — the BUDGET, not the splat name |
| Bonus health levels | TraitsPage | always |
| Training Camp & Calling | IdentityPage | `build_camp_view is not None` |
| Downtime | **`qt/main_window.py`** | post-lock, in `_xp_section` |

### Three new engine modules, and a move

Two shells driving one write is what the `*_actions` modules exist for, so each shared
write went into one:

* **`engine/health_actions.py`** — `level_total` / `set_level_total`. ⚠ The stored list
  is a DELTA from the printed track, so an empty `health_bonus_levels` means
  "unmodified", never "no health levels". `ui/editor.py` migrated onto it, its copies
  deleted.
* **`engine/camp_actions.py`** — the four camp writes. ⚠ **A refusal is RETURNED, not
  raised and not notified.** It sits below the UI so it cannot call `ui.notify`, and
  unlike a purchase there is no `AdvancementError` shape — a refused pick is an ordinary
  outcome. Both halves matter at the call site: **say why, and REDRAW**, or the control
  keeps showing a selection the character does not hold.
* **`engine/labels.py`** — `_label` + `_style_label`, one copy each.

**`build_camp_view` + `CampView` moved from `ui/view.py` to `engine/camp.py`** — the
human's call (2026-08-22) over a `ui/`-side module or a duplicate. `camp_actions` needs
the view, and `engine/` may not import `ui/`. `view.py` re-exports the names, so
`viewmod.build_camp_view`, `viewmod.CampView`, `viewmod._style_label` and
`viewmod._label` all still resolve — including `ui/picker.py` deferring to
`view._style_label`, which a test asserts. `_charm_name` turned out to be a straight
duplicate of `engine/validate`'s, so view.py re-exports that instead of keeping a second.

### The two defects the audit found — neither was on the gap list

The handoff said to audit before building, because last session's stale readout bar had
appeared in none of its entries. It paid twice, both the house bug's first species.

1. **`_EditorPage.reload()` never pinged `on_change`.** Ten call sites — every
   structural change (Exalt type, caste, origin, upbringing, both favoured setters,
   add/remove craft) plus `_do_trait` and `_lower_willpower` — moved the bonus-point
   spend and the validation errors while the shell's readout bar kept showing the
   previous answer. `_changed()` pinged; `reload()` did not, and the structural setters
   only ever call `reload()`.
   **The page's own body rebuilt correctly every time, which is what hid it.**
   Fixed in the WRAPPER, not at the ten sites — one ping is a mechanism, ten remembered
   call sites is the same bug waiting for an eleventh. ⚠ **The test asserts the PING.**
   Asserting the page would have passed straight over it.
2. **`_combo` degraded enum keys.** Qt stores item data as a QVariant and a `str`-valued
   Enum comes back out of `currentData()` as a plain `str`. `Character` has no
   `validate_assignment`, so `setattr(sp, "ability", "dodge")` onto a field typed
   `AbilityName` **succeeded, silently** — it would have failed later at the first
   `.value`. The key is now looked up by INDEX in the caller's own dict, so every key
   type round-trips identically. Found by a test that failed with `KeyError: 'conviction'`.

### Traps

* ⚠ **"Address a widget by name, not position" bit while writing the TEST for it.** The
  first Virtue Flaw locator walked out to the label's `parentWidget()` and took the
  first `QComboBox` — but a `QHBoxLayout` does not reparent, so **every combo in a panel
  shares one parent**, and it grabbed the Flawed Virtue box while looking for the sample
  list. Every control added here has an `objectName`; the tests use
  `findChild(kind, name)`.
* ⚠ **A gap-list entry can name the wrong MODULE.** Downtime was filed under "Edit's
  deferred panels" for two sessions. It is not a panel — in the webapp it is a button
  beside Adjust XP, so its Qt home is the shell's popover.
* ⚠ **Two different things wore the name `age`.** The 2026-08-06 ruling removed the
  numeric age trait; a free-text biography `age` arrived 2026-08-21 and is unrelated. A
  test pins that the calculator does not read the bio field.
* ⚠ **`CharmVariant.max_purchases`-style parity traps in the camp panel:** the category
  choice is TWO controls, not one — "two Charms from ONE of four martial arts" (p.90).
  And the heading follows what the panel CONTAINS, because Cult p.96 gives a
  Dragon-Blooded a camp and no Calling.

Tests: 37 added across `tests/test_qt_editor.py` and `tests/test_qt_shell.py`. Suite
**2,766 passed, 1 skipped** (main PC, 7m36s).

### Human-verified on the real display — YES, 2026-08-22

Written as "NOT YET" and left that way after the click happened; corrected 2026-08-22.
The click is the next section, and it found three defects.

## The Edit click-through, and the Traits redesign that was declined (2026-08-22)

The human clicked the whole Edit surface (both commits of group 4 item 2) and approved
it. Everything worked; three defects came out of the click, none of which any test saw.

### The three the click found

1. **The details popover clipped its own content.** Two causes, and the second matters
   more: no floor size on the dialog, AND `rebuild()` swept the layout with a
   hand-written widget-only loop. ⚠ `item.widget()` is None for a nested `QLayout`, so
   the bonus-point ROWS' labels stayed parented and painted over the new build — that is
   what made wrapped issue lines look like they clipped into each other. Now
   `clear_layout` (the helper that exists for this, **bitten a fifth time**), a 560×420
   floor, and the body scrolls with Done pinned outside it.
2. **An unresolved camp style choice ANNOUNCED a pick the character did not hold.** Qt
   has no empty state for a combo: handed a value that is not among the keys it sits on
   index 0, so the select displayed the first martial art with no Charm list beneath it,
   reading as "a style is chosen and its Charms failed to load". Fixed at the helper
   with `_combo(..., placeholder=…)` rather than per caller; the placeholder row exists
   only while the value is missing, so a resolved control never offers a blank.
3. **A camp with no Calling held an empty right column open.** Cult p.96 gives a
   Dragon-Blooded a camp and no Calling; the panel now builds ONE column in that case.

### Bonus points are chargen-only (human's call)

The popover's BP breakdown is pre-lock only. The readout BAR already dropped the line
post-lock, so a popover reporting "12 / 15 spent" for a locked character disagreed with
the bar directly above it. Post-lock that slot is the Experience card and its ledger.

### The Traits redesign — asked, spiked, DECLINED

The human asked whether Traits should stop being "a UI of scrolled cards". Four shapes
were built in `spikes/qt_traits/`, then two more from their notes: cards (baseline),
sub-tabs, sheet grid, flat rules, a COLLECTION built on QTreeWidget like Gear and
Advantages, and a revised sheet grid.

**The answer was no.** *"The way it is right now works best for this information
specifically."* ⚠ **Identity and Traits are a written EXCEPTION to the one-tab-layout
rule** — see CLAUDE.md. Do not re-propose a Traits redesign without the human reopening
it; the spike is the record of what was tried and why it lost.

One thing DID come out of it: specialties fold into their Abilities as child rows.
Written up in `docs/status/edit-xp-merge.md`, not here.

### ⚠ The theme bug the spike exposed, which was NOT spike-only

**The Gear and Advantages trees had been rendering WHITE on the dark page** — both
shipped, both human-clicked, both live the whole time. The QSS had no `QTreeWidget`
rule at all and relied on `QPalette.Base`; but setting a stylesheet on the window hands
the stylesheet renderer every descendant, and it ignores the palette. Fixed in `qss()`
so both tabs and any future tree get it.

That is now **three** instances of one rule — `QTextEdit` in a `_Panel`, the trees, and
the invisible card-on-card buttons. **An ancestor stylesheet beats a set palette, every
time; the only fix is an inline stylesheet on the widget itself.**

### Traps the spike paid for, worth keeping

* A stretch on a row's NAME label pushes the dots to the far edge of the column —
  invisible inside a narrow card, glaring the moment a column goes full width.
* **QGridLayout cells overlap SILENTLY.** A `section()` helper returning the row it
  *started* at drew CRAFTS straight through the middle of VIRTUES. No exception.
* **QTableWidget will not move `setCellWidget` widgets when it sorts** — ratings stay
  put while names move, silently pairing every trait with the wrong dots. (Moot: the
  app is built on QTreeWidget, which is the actual answer to "the app's design
  language".)
* A short final row of ability groups must be PADDED or its columns stop lining up.
* ⚠ **`findChildren(QTreeWidget)[1]` does not reliably return the second sub-tab's
  tree.** It silently handed back the first and made a verification script report the
  wrong groups for every splat. Third time this session that addressing a widget by
  position produced a confident wrong answer.

## Group 4 item 3 — the per-splat Charm surfaces (2026-08-22) — GROUP 4 CLOSED

The last of the within-tab gaps. **Audited `qt/charms.py` against `ui/picker.py`
before building**, as the handoff insisted: all five listed gaps were real (no stale
entries), and the list was a lower bound for the third time running.

### The five, as built

| Gap | Where it landed |
|---|---|
| Foreign-charms **Splat dropdown** (core p.127) | `splats_for` + a PER-TAB combo in `_tree_page` |
| **"Add another"** for generic repeatables | `again_btn` beside the action button; `charm_actions.learn_charm` |
| **Martial-arts style panel** | `_style_panel` / `_sync_style_panel`, collapsible above the tree |
| **Alchemical submodules** (p.89) | `_rebuild_submodules` under the detail pane |
| **Immaculate-vs-standard DB banner** | `_immaculate_path_line`, in the readout's chargen branch |

⚠ **The Splat dropdown is PER TAB in Qt, and that is not a port defect.** The web
picker has ONE shared dropdown over a group toggle; Qt builds an independent
`_tree_page` per group, so each tab offers only the splats with trees in ITS group.
That deletes `set_splat`'s fall-back-to-another-group dance entirely — a splat with no
martial arts simply is not on the Martial Arts tab's list. `splats_for` scans the
catalogue rather than calling `trees_for` per splat, which would lay out every splat's
whole Charm tree to fill a dropdown.

⚠ **The tab set is still decided by NATIVE trees** (`reload` asks `trees_for` with
`char.exalt_type`). An Eclipse whose own splat has no Arcanoi gets no Arcanoi tab and
so cannot reach foreign Arcanoi. **The webapp has the same limitation** — its `GROUPS`
is built from `_all_categories`, which is `charm_matches_splat`, native-only. Parity,
not a regression, and not fixed here.

### Two more the audit found, on no list

* **The detail pane rendered NONE of the five flag lines** the web card shows —
  homebrew, foreign-splat, Immaculate Order, Calling, camp-granted. Four of the five
  change what the Charm COSTS. It stayed invisible because the foreign one is only
  reachable through the Splat-dropdown gap above. Now `_charm_flags_html`.
* **The QSS had no `QPushButton:disabled` rule**, so a disabled button was
  pixel-identical to a live one — every "Add" whose prerequisites are unmet read as
  clickable, across the WHOLE port. Found only by the offscreen grab; no test sees it.
  Fixed in `qt/theme.py::qss`, which fixes it everywhere.

### The house bug, species 1, caught by a test that fails against the old code

`char.exalt_type` was passed straight to `show_tree` at THREE call sites, and the one
on the purchase path (`_refresh_current_tree`) does not run until you buy something —
so a foreign tree silently snapped back to the native splat on the next click, with
nothing else on screen showing it. All three now go through
`CharmTreeView.reload_tree`, which is the ONE place the (category, splat) pair is read.

### Traps

* ⚠ **`isVisible()` is useless on a child of a widget that was never shown** — False
  however the widget is configured, so a negative assertion passes vacuously.
  `test_qt_advantages.py:490` already recorded this and the first splat-dropdown test
  walked into it anyway. `isHidden()` throughout.
* ⚠ **A QGraphicsScene selection is not exclusive.** `setSelected(True)` on a second
  node leaves BOTH selected and `_tree_detail` keeps reading the first, so a test that
  moved the selection went on asserting about the old node. Clear first.
* ⚠ **Hide a conditional button at the TOP of `_update_action`, not per branch.** It
  has a dozen early returns; one that forgot would offer "Add another" against
  somebody else's Charm.
* The style panel's mechanics glyph ⚖ renders as tofu offscreen. Now `•`.
* `_first_available` returns a LIST despite the singular name.

### Submodules moved INTO the engine

The web picker mutated `character.submodules` directly with no legality check — it
relied on the button being greyed, which is a guard in a widget.
`charm_actions.learn_submodule` / `drop_submodule` now own it, both shells call them,
and the chargen path gained the `submodule_block_reason` check it never had.

### Human-verified on the real display — NOT YET

All four new surfaces were rendered offscreen and looked at (that is what caught the
disabled-button defect). **Not browser-verified and not human-clicked.** What to click:
an Eclipse with ST permission switching the Splat dropdown and buying a foreign Charm;
a martial-arts tab expanding the style panel and changing category; an Alchemical
selecting Chemical Fog Generator and adding a submodule; a Dragon-Blooded's readout
before and after picking a Dragon-style Charm; a Jadeborn buying a second Essence
Satiation Method.

## Group 4's tail — three defects behind the gaps (2026-08-22)

Found while explaining the above, all three filed initially as judgement calls and all
three actually bugs.

**The chargen BP preview under-quoted the pick that flips the Immaculate path.**
`_chargen_pick_bp` derived the free-pool SIZE once, before staging the candidate, then
sliced the STAGED pool with it. A DB's pool is 7 standard / 5 Immaculate, so the pick
that flips the path changes its own denominator. Measured, pool exactly full, picking
Air Dragon's Sight: **button 7 BP, accounting 21 BP**. Display-only — `build_sheet_view`
was right both sides — but a 3x under-quote on the one decision the banner exists for.

**Post-lock repeatable purchases were unreachable.** The house bug again:
`advancement.learn_charm` has supported a second copy since it was written, cap check
and CH6 pp.245-246 citation included — but `charm_actions.learn_charm`'s post-lock
guard was a bare `charm_id in character.charms` with no cap, and it refuses first.
Both shells go through the dispatcher, so the support was dead code. Ox-Body and the
Gifts were never affected (their ids never enter `character.charms`), which is why it
never surfaced.

**Post-lock "Remove" was a button that always failed.** Enabled, and `drop_charm`
refuses every post-lock removal. Now `charm_actions.undo_charm` / `undo_charm_reason`:
enabled only for the LAST XP entry (the log is append-only and undo is LIFO, decision
0004), otherwise disabled with the reason as a tooltip. The webapp's in-play card gets
the same offer, which "Known." had been hiding.

⚠ **`test_selecting_a_charm_in_play_buys_it_with_xp` changed meaning, not correctness.**
It asserted "Known." after a buy; the just-bought Charm is now the undoable one. The
discriminating case — a known Charm that is NOT the last entry — still says "Known."
and has its own test.

## Open questions — not decided

* **Porting the 228 NiceGUI harness tests.** Both spikes proved retained-mode widgets
  test well with pytest-qt (28 + 14 tests, offscreen) — what each of the existing 228
  harness tests becomes in Qt is a per-test translation, done with the port.
* **PySide6 licensing** is LGPL, which is fine for this project — noted so it is not
  re-researched.
* **Theming.** `ui/theme.py`'s per-splat palettes are the design asset worth keeping;
  the Tailwind class strings that carry them are not. Qt Style Sheets are the likely
  target, but the mapping is unexamined.

## ST Options — the seventh tab (2026-08-27)

`qt/storyteller.py`, 300 lines, wired into the rail in place of its placeholder. The
settled collection layout, minus one part of it: **no action toolbar, deliberately.**
The rules are fixed by the books, so there is nothing to add, buy or delete — the
absence is written into the module docstring so it reads as a decision rather than
drift. Everything else is the standard shape: a readout line, a sub-tab per SCOPE
(Table-wide / This character), a sortable three-column table (Rule · Setting · Source),
and a splitter with the selected rule's one control in a detail pane.

**The lock is the tab's distinguishing behaviour.** These toggles change how chargen is
PRICED and are frozen into the snapshot at the lock, so post-lock every control is
disabled and the readout carries the full explanation plus the pointer at Unlock. Same
rule the webapp's tab has.

### What moved

* **`engine/house_rule_actions.py`** — `house_rules()` + `set_rule()` lifted out of
  `ui/storyteller.py`, which now re-exports them. The native shell must not import
  nicegui to set a toggle, and the value coercion is game data: ⚠ `bool(value)` is
  right for exactly ONE of the three control shapes. A checkbox sends a bool; the M&F
  select sends a stored string that `bool()` would turn into True; the Inheritance
  select sends an option key that must land as None or an int.
* **`HouseRuleRow.inert`** (new, `ui/view.py`) — True when a rule cannot bite for this
  character as she stands. Derived in the presenter, ⚠ **not** by reading `note` for a
  "No effect:" prefix, which would silently un-dim every row the day someone rewords a
  sentence. The Qt table dims inert rows rather than hiding them, which is the
  presenter's whole premise: an ST hunting for a toggle must find it and be told why it
  does nothing.
* **`view.HOUSE_RULE_SCOPES`** and **`view.house_rule_setting_label`** — the scope
  headings and the short cell text, in one copy for both shells.

### What the offscreen render caught — four, all invisible to 2,857 tests

**1. A disabled QCheckBox is pixel-identical to a live one.** The `QPushButton:disabled`
defect from group 4, one widget class over: the base style's greying does not survive
the stylesheet renderer. This is **port-wide**, not an ST Options bug — Play's pool
boxes, Advantages' Demesne box and the Charms tab's variant boxes all disable
legitimately. `qt/theme.py` now styles the disabled states only; the live look is the
one that shipped and was clicked.
⚠ **Checked-disabled had to stay distinguishable from unchecked-disabled.** Styling
`QCheckBox::indicator:disabled` alone replaces the tick with nothing, so a locked rule
that is ON would render exactly like one that is OFF. The filled MUTED square carries
"on, frozen".

**2. `setSortingEnabled(True)` sorts immediately**, throwing the rules into alphabetical
order and losing the presenter's — which is the order the books introduce them in.
`sortByColumn(-1)` leaves insertion order until the player clicks a header. ⚠ And the
per-fill disable/re-enable had to save and restore the player's sort, or every toggle
silently re-imposed column 0 ascending. ⚠ `setSortingEnabled(True)` also turns the sort
INDICATOR on, and with no section to point at Qt drew the arrow over the last header, as
though the rules were sorted by Source.

**3. `QHeaderView` stretches its LAST section by default**, so "Sidereal may hold
Celestial Manse above 3 dots" elided to "…Manse abo…" while dead space sat under the
Source header. `setStretchLastSection(False)` and the Rule column takes the slack.

**4. The foreign-Charms note printed the caste ID** — "and dawn is not one". A presenter
bug, so both shells had it. `ruleset.castes.get(...).label` now.

### The test that passed against the defect it was named for

`tests/test_qt_theme.py` is new, and exists because **a QSS rule is invisible to every
other test in the suite** — that is how the original disabled-button hole shipped green.
It renders the widget and measures pixels.

⚠ **The first version was worthless and looked fine.** It compared whole-widget images
with `!=`, which passes whether or not the indicator was fixed, because Qt dims the
disabled TEXT on its own. Cropping to the indicator was not enough either: Qt's two
drawings are not byte-identical (border antialiasing), so `!=` STILL passed with the
theme rules deleted. The measured brightness gap without the fix was **7 out of 255, and
INVERTED for a ticked box** — the disabled one was brighter. The test now asserts a
brightness gap, verified by deleting the rules and watching it fail.
**Negative-control a rendering test by deleting the rule it guards.**

### Human-verified on the real display — YES (2026-08-27)

**Clicked and approved**, on the day it shipped. Four things were driven:

1. **The port-wide checkbox theme change**, against **Play, Advantages and Charms** —
   the surfaces the shared stylesheet touches that were already signed off under the
   old look. No regression.
2. **ST Options on an unlocked Solar** — read at real size, nothing below the fold.
3. **ST Options on a locked character** — the read-only state reads as locked rather
   than as broken.
4. **The variant chooser** on a Solar with Resistance 5, and the cap refusal wording
   (below).

⚠ **The checklist was cut down before it was run, and that was the right call.** The
first version had eleven checks; the human asked whether all of it was necessary and it
was not. Most of it re-drove behaviour that `test_qt_storyteller.py` and
`test_qt_theme.py` already assert — the Setting column, the readout counts, the dimming,
`isEnabled`, the three stored types, the checked-vs-unchecked appearance. **What a human
adds is the class of defect that beats every offscreen check: a control that is correct,
tested, and below the fold** (milestone 3's M&F picker), **and a shared style regressing
a surface that was already approved.** Four checks, five minutes. Scope a click-through
to what only the display can answer.

### Still NOT clicked

Group 4's five per-splat Charm surfaces (Eclipse foreign tree, MA style panel,
Alchemical submodules, the DB Immaculate banner, the Jadeborn repeat) and the POST-lock
half of the variant chooser. Each was rendered offscreen and each has test coverage of
the behaviour; they are not blocking, but they are not clicked.

⚠ **`ui/picker.py::variant_menu_detail` — the WEBAPP's variant panel — has still never
been rendered at all**, in a browser or anywhere else. The Qt panel was verified here;
its webapp twin was not. It remains the least-verified code in the tree.

## Custom — the last rail placeholder (2026-08-27)

`qt/custom.py`. The rail now has none left. **Human-clicked the same day, with the gear
work below.** Details in `docs/status/custom-content.md`; what belongs to the PORT:

* The collection layout, with the webapp's third column becoming a toolbar **dialog**
  rather than a nested tab — one detail pane is the layout, and JSON in-and-out is an
  action on the row rather than a property of it.
* ⚠ **The one collection whose detail pane is not a projection of a selected row.** It
  also holds an unsaved NEW row. `_fill_tables` must never fall back to row 0 — every
  other collection does, and here it discards a half-written Charm on every rebuild.
* ⚠ **`reload()` is deliberately not called in the constructor.** The only tab whose
  refresh touches the FILESYSTEM, and the shell builds all nine pages up front.

Both invariants have tests, and both were negative-controlled by breaking the code and
watching the right test go red.

### What the render caught — four, none visible to the tests

1. ⚠ **`QDialog` was never styled — PORT-WIDE.** A dialog is a top-level window and does
   not inherit the main window's palette, so every dialog in the app drew the platform's
   light `#efefef`: a thin light halo on the catalogue and the details popover (whose
   content fills the area), a glaring light page around anything with margins. One QSS
   rule fixed all of them.
2. ⚠ **`QPlainTextEdit` was missing from the input rule while `QTextEdit` was in it** —
   a paste box rendered white-on-white beside a correctly themed pane. The same
   check-the-siblings trap as `QCheckBox:disabled` the session before.
3. `_FavoredPicker` PRINTS its cap in the placeholder, so passing 999 to mean
   "unlimited" put "Type a name… (pick 999)" on screen. It takes `cap=None` now.
4. A `_labelled` caption is vertically centred by Qt, so the 90px Description box's label
   floated to its middle and scrolled clean out of view. Top-aligned.

### A test that broke for the right reason and asserted the wrong thing

`test_theme_does_not_border_every_widget` pinned the literal selector string
`"QLineEdit, QSpinBox, QComboBox, QListWidget, QTextEdit {"`, so adding a sixth class
turned a correct change red — the shape that teaches the next person to edit the test
rather than read it. Now asserts MEMBERSHIP, plus a sibling test pinning every editable
class the port instantiates, so an unthemed input fails here rather than at a
click-through.

### Gear on the Custom tab, and the ruling it reversed

The human reopened the 2026-08-13 "no authoring form was needed" ruling and it is now
reversed — `docs/status/custom-content.md` has the full record, including the
`reload_custom_layer` bug that had made library gear need an app restart to reach Buy.
Two port-shaped notes:

* ⚠ The form is a **flat dict validated on save**, not `setattr` down a model, because
  `WeaponType` and friends are FROZEN and shared with the book data. That is the Custom
  tab's Charm-form pattern, not `qt/gear.py`'s owned-row-editor pattern — **the two tabs
  edit different models and only one of them is mutable.**
* A test's SUBJECT changed again: `test_saving_on_the_gear_tab_points_at_the_gear_tab`
  asserted the old refusal. Replaced with a parametrised authoring test over all four
  kinds, not deleted.

### Human-verified on the real display — YES (2026-08-27)

Clicked and approved, form and list, all four kinds. *"No notes, everything looks good."*

## The Combos sub-tab (2026-08-27)

`qt/combos.py` + `engine/combo_actions.py`. **Human-clicked the same day** — *"Everything
looks good, no complaints from me."* The last thing under Charms; only the Party / ST
screen remains after this.

⚠ **THE GAP LIST WAS A LOWER BOUND FOR THE SIXTH TIME.** It read "the Combos sub-tab,
`ui/combos.py`, 423 lines". It is **two systems, not one**: a Charm-Slot splat
(Alchemical, p.89-90) builds **Arrays** *instead of* Combos. Same tab, different noun,
different presenter (`build_array_view`), different engine calls, different cost sentence
— and `view.uses_arrays` is the ONE place that decides which. A splat that builds neither
gets no sub-tab at all (`view.has_combos_tab`; the dead may never learn Combos, E:Ab
p.234).

### The mutations had no engine home

The chargen edits — create, delete, add member, drop member, rename, for both systems —
were **closures inside `ui/combos.py`**, so the native shell could not reach them at all.
`engine/combo_actions.py` now owns them and the webapp calls it too; one path, both
shells. Same shape as `thaum_actions` and `house_rule_actions`.

⚠ **Legality is NOT enforced at add time.** `validate.combo_issues` reports an illegal
set as an issue on the row, so a half-built Combo can be inspected rather than refused
mid-assembly. An empty one is legal to HAVE and illegal to KEEP, and shows ⚠ from the
moment it is created.

### Two shapes, not one shape greyed

At chargen a Combo is assembled in place and priced in bonus points. In play it is bought
**whole** — `advancement.add_combo` prices, validates and logs in one go — so the toolbar
swaps `+ Combo` for `Buy Combo…`, the table goes read-only, and a bought one is undone in
the shell's Experience card, not here.

⚠ **A bought Combo's Cost column reads "—", not a BP figure.** Bonus points are a chargen
fact; in play the thing is already paid for and its XP price is on the ledger, so quoting
BP beside it invents a cost that is not owed.

### What the render caught — three, none visible to the tests

1. ⚠ **TWO detail panes on screen.** Every other Charms sub-tab is a content pane that
   FEEDS the shared `QTextBrowser`; this one brings its own splitter, so the shared panel
   sat beside it as an empty column saying "Select an entry to see details." **A page
   added to a shell inherits a LAYOUT contract from its siblings** — this one breaks it
   deliberately, so `_tab_changed` hides the shared panel for `CombosPage` and says why.
2. The buy dialog's price line clipped its page citation — "…minimum Ability ratings
   (p.21". Not word-wrapped.
3. ⚠ **A multi-select `QListWidget` highlights row 0 by default**, so the dialog opened
   looking like something was already picked while `selectedItems()` was empty and Buy
   was disabled: a visible selection and a dead button, with no way to tell why.
   `setCurrentRow(-1)`.

Both the shared-pane fix and the one-Array-per-Charm pool rule are negative-controlled —
each guard removed, the right test watched to go red.

### One rule worth not re-deriving

⚠ **An Array's add-pool excludes every Charm linked into ANY Array**, not merely the one
being edited: a Charm may join only one (p.90). The engine refuses a reuse either way, so
offering it would produce nothing but a rejection. `combo_actions.linked_array_charms` is
the one copy of that set.

## The Party / ST window — THE LAST THING (2026-08-27)

`qt/party.py` + `qt/adversaries.py` + `qt/trackers.py`, and roster mutations added to
`engine/adversaries.py`. **The port is now feature-complete against the webapp.**

It was flagged as a DESIGN QUESTION rather than a port, and it was asked before any code:
four decisions, all four taken as recommended.

| Question | The human's answer |
|---|---|
| Shape | **A second `QMainWindow`**, opened from the builder's Party toolbar action. A `QDialog` was rejected for the same reason — you must be able to read a sheet and the party at once. |
| Layout | **Sub-tabs, mixed**: Party · Adversaries · Reference. Cards for the members, the settled collection layout for the roster. |
| "Open in builder" | **Retarget the one builder**, not a window per member. |
| The ST reference screen | **A tab on this window**, not on the builder's ST Options tab. |

### The Party tab is the THIRD written exception to the collection layout

And it is Play's exception for Play's reason: the cards are live TRACKERS — there is
nothing to select, and a detail pane would hide the health tracks the surface exists to
show. **The Adversaries tab beside it IS a collection**, because its entries are *edited*
as well as tracked. The two halves of one window are deliberately different shapes; that
is the whole design, not drift.

⚠ **An exception that is written down is not drift.** The three are now: Play,
Identity+Traits, and the Party tab. ST Options' missing toolbar remains a partial, not a
fourth.

### What the collection layout bought on the roster, and what it cost

The webapp renders adversaries as cards, and cards did exactly one thing better: six
bandits' damage visible at once. That is kept as the table's **Damage column**
(`1/ 0x 0*  (-1)`) — it is not decoration, it is the compensation that makes the
collection layout acceptable here. The editor that was a modal dialog on the webapp
becomes the detail pane, which is strictly better for a 28-field statblock.

⚠ **The roster table is sortable but NOT SORTED.** Roster order is meaningful here in a
way it is not on Gear or Advantages: a duplicate is deliberately inserted *beside* its
original so a squad reads as a squad, and an alphabetical default would scatter it on the
very click that made it. `sortByColumn(-1, …)` clears the indicator and leaves the header
clickable — the only tab in the port that needs it.

### The mutations had no engine home — the same hole Combos had

`add_blank`, `add_from_template`, `duplicate`, `remove`, `reset_tracking`, `mote_cap`,
`set_motes_spent` and `set_count` were closures inside `ui/adversaries.py`. They are now
in **`engine/adversaries.py`** and the webapp calls them too: one path, both shells.
`test_reset_clears_exactly_what_instantiate_clears` pins the pair — a new tracked field
added to one and not the other is how a "fresh" duplicate ends up carrying spent motes.

### The dead-field guard was rebuilt for Qt, as a DRIVE rather than a grep

This surface has already shipped the dead-field bug once: `powers`, `combat_pool` and
`cost_to_dematerialize` were authored, editable nowhere, and silently wiped on save, with
1,777 tests green over it. The webapp's guard greps `edit_dialog`'s source for
`a.<field> =`. The Qt guard **parametrises over `Adversary.model_fields` and drives the
named widget**, so a field wired to a widget that writes the *wrong* attribute fails too
— a grep could never see that.

### Three things the WIDGETS had to decide, all of them printed rules

1. **`0` means absent in the trait grids**, shown as "—". A beast prints three of the
   nine Attributes (p.316) and no printed block carries a rating of zero, so storing one
   would claim the book printed it.
2. **The nullable combat numbers run from −1**, shown as "—", because absent is NOT zero:
   the Bear prints no dodge figure (p.316) and Nagezzer prints "Does not dodge" (p.307).
   Both states must be reachable from one box.
3. **Charms / Spells / Powers stay free text.** "All Solar Charms the Storyteller cares
   to give him" (p.303) is not a list of ids, and the loader's link-checking would reject
   the attempt.

### The card fixed a bug the webapp card still has

⚠ **A merged Essence pool is ONE track** — "all of which is considered Peripheral"
(p.41). `ui/gm.py`'s card draws Personal and Peripheral unconditionally, so a merged-pool
character gets a Personal box sitting at a permanent 0/0 that reads as broken. The Qt
card honours `PlayView.single_pool` the way the Play tab does. **The webapp card was not
changed** — flagged here rather than fixed silently.

### What the render caught — four, none of them visible to the tests

1. **A nested `QVBoxLayout` inherits an 11px margin on all four sides.** Six panels down
   a card added ~130px of nothing between each heading and the boxes it labelled.
2. **A grid stretches every card in a row to the tallest**, and a QVBoxLayout hands that
   spare height to the gaps between its children. `addWidget(…, Qt.AlignTop)` per card.
3. **A full-width `QSpinBox`** holding a two-digit printed number reads as a text field
   somebody forgot to size. `_labelled` now sizes spin boxes and stretches nothing else.
4. **The first grab lied.** A `QScrollArea` measured before the layout settles reports a
   crushed body — panels overlapping, no scrollbar. It is not a defect; **process events
   more than once before believing a screenshot.**

### The wiring back to the builder

* **ONE party window**, held on the MainWindow and reused. A fresh one per click would
  give each its own cards over the same roster, and a box ticked in the old one would be
  invisible in the new.
* **The context is SHARED, not copied** — same roster, same member Characters, same
  adversary catalogue (loaded on demand, as `ui/builder.py` does, because templates are
  book data but not *rules*).
* **Members are held BY REFERENCE**, which is what makes "Open in builder" need no
  syncing code — and what makes a stale `ctx["member"]` dangerous. Every path that drops
  or replaces the roster calls `on_close_member`, and the builder clears it on New and
  Load too.
* **`_refresh` redraws the party window only when it is VISIBLE.** A card shows DERIVED
  capacities, so spending XP in the builder makes its pixels stale even though both
  windows hold one object.
* ⚠ **`closeEvent` takes the party window down with the builder.** A parentless
  `QMainWindow` is its own top-level window; without this the Storyteller window survives
  the builder with no way back to one.

### Tests

`tests/test_qt_party.py` (30) and `tests/test_qt_adversaries.py` (49), plus 8 shell tests
for the wiring and 7 engine tests for the mutations. `qt/trackers.py` now owns the
tracker box and the damage-colour map for all three surfaces — a Storyteller should not
have to learn two damage trackers, and three copies of a colour map is how they drift.

**NOT human-clicked yet.** Rendered offscreen and looked at, tab by tab and dialog by
dialog; that is not the same thing.

### The first click found it in seconds: an empty table looks BROKEN (2026-08-27)

The human opened the Adversaries tab and reported *"the adversaries list doesn't load
anything?"* — a header over a large blank rectangle, and no way to tell "empty" from
"failed to load". The catalogue was fine (52 templates); there was simply nothing on
screen to say the roster starts empty.

**Every collection tab in the port had the same hole.** Gear, Advantages, Combos and
Custom all render a bare void before you own anything; the detail pane's "select one, or
add one" sits on the far side of a splitter and does not answer it. The roster is where
it bit because empty is that tab's *opening* state, every session.

`qt/layout.py::empty_note(tree, text)` is the mechanism — a muted label over the table's
viewport, wired to the MODEL's own row signals so no `_fill_table` has to remember to
toggle it (`tree.clear()` emits `modelReset`, so it survives every rebuild). Applied to
all six tables that can legitimately be empty; ST Options' tables are fixed by the books
and never are.

⚠ **The slot must be a BOUND METHOD of the label, not a closure.** The Advantages and
Custom tables are rebuilt with their sub-tab pages, so the label dies while its model
lives on — a closure keeps firing into a deleted C++ object ("libshiboken: Internal C++
object already deleted"). Qt drops a connection when its *receiver* QObject is destroyed,
which is the whole reason `_EmptyNote` is a class.

⚠ **That crash is ASYNCHRONOUS to the code that causes it.** It surfaces inside Qt's
event loop, so pytest-qt reports it against whichever test runs NEXT — the first version
of the guard passed while the closure crashed three other tests. The assertion that
actually holds is structural: `note.sync.__self__ is note`.

The guard is a **sweep, not a per-tab test**:
`test_no_empty_table_anywhere_in_the_port_is_a_bare_void` builds every page of both
windows for a fresh character and fails on any table that holds no rows and offers no
explanation — so a new collection tab fails there until it is wired. Negative-controlled
by deleting Gear's call.

## The two DOCUMENT surfaces went dark (2026-08-28)

The Sheet tab and the Party window's Reference tab were the only light surfaces left in
the app. Both were deliberate — a sheet is a *document*, and the 2026-08-20 direction was
that it stays "paper" — but in use, tabbing from the dark Edit page to a white page is a
flashbang, and the Reference tab had inherited the treatment purely by copying the Sheet
tab's one-line stylesheet. Reversed at the human's call: **on screen both are dark; the
PRINTED sheet is still ink on paper.**

`qt/sheet.py::SheetColors` is the mechanism — a frozen dataclass of the seven colours the
sheet draws with, in two constructors: `print_colors` (the old hard-coded greys) and
`screen_colors` (the dark base, with the accent LIGHTENED exactly as `qt/theme.py::accent`
does for every widget — the printed accents are dark tones that vanish on the dark page).
Every `_dots`/`_trait_table`/`_section` helper now takes the colour set instead of a bare
accent string, so **one document has two palettes rather than there being two documents**
— which is what keeps the print path honest. `sheet_html(view)` still defaults to the
paper set, so a caller that just wants something printable cannot pick up the dark page
by omission (`test_the_printed_sheet_stays_ink_on_paper`).

⚠ **`ink` and `paper` are the two colours the HTML does NOT carry.** A QTextBrowser takes
its page shade from the WIDGET's stylesheet, and the shell QSS hands every QTextBrowser
the card shade — so each surface sets an inline stylesheet as well as building the HTML,
and `SheetPage.reload` sets it on every reload rather than once, because a splat change
re-renders. This is the ancestor-stylesheet-beats-palette trap in its fourth disguise.

⚠ **A document's colours are baked into its HTML, so a palette change does not reach
them.** `ReferencePage.apply_colors(pal)` re-renders, and `PartyWindow.apply_chrome`
calls it — otherwise a party that becomes single-splat re-tints its chrome and leaves the
reference screen on the default gold.

The guard is a RENDER, in `tests/test_qt_theme.py` where the other invisible-QSS tests
live: `test_no_document_surface_is_a_white_page_on_the_dark_app` measures the mean
brightness of each page's viewport and fails above 120/255. Negative-controlled both
halves — restoring either surface's `#fffdf7` line fails it (paper renders at ~250).

### A test that had been aborting the interpreter for months

`test_print_pdf_writes_a_real_file` takes `qapp` now, though it builds no widget.
⚠ **Laying a QTextDocument out for the printer hits QFontDatabase, which ABORTS the
process — not fails the test — when no QApplication exists.** It passed for months
because in a full run some earlier module's `qtbot` had already made one; running
`pytest tests/test_qt_sheet.py` on its own took the whole run down with a C stack trace,
and read exactly like a Qt/font regression on the machine.

## The shell-parity audit — 2026-08-28

Asked directly ("is anything in one shell missing from the other?"), and answered
mechanically rather than by eye: every public name in `ui/view.py` and every public
function in `engine/`, scored by **which shell references it**. Most of the diff is
architectural noise and says so — the Qt shell routes through `view.py` and the action
modules where the webapp calls the engine directly, which is the dependency rule working.
What survived being chased to a real surface:

**In the webapp, missing from Qt — three, all in the Thaumaturgy picker.** Owned
orientations were never displayed; `add_thaum_orientation` had no Qt caller, so every
regional version after the first was unbuyable; `buy_custom_ritual` had no Qt caller, so
no ritual could be written. Written up in `docs/status/thaumaturgy.md`, all three fixed.

**In Qt, missing from the webapp — one.** The Custom page authored Charms and spells only,
so a custom weapon saved from its Buy dialog could be neither listed nor deleted there:
`custom_content.delete_gear`'s own docstring describes that defect, and it had been closed
on one side only. Closed on both now, along with the new Rituals kind.

⚠ **The method's blind spot, stated so the next audit does not trust it too far:** it can
only see a difference that shows up as a NAME going unreferenced. A control that exists in
both shells but is disabled in one, a panel that renders fewer lines, a different default
— none of those are visible to it. Two of the three Thaumaturgy findings were found this
way *and the other two defects in the same code* (a stale detail panel, a combo defaulting
to North where the webapp defaults to Realm) were found only by fixing them and looking at
the render. **Eight for eight: the list was a lower bound again.**

### The second pass, on a different axis — three more (2026-08-28)

The audit above compared `view`/`engine` NAMES by shell and said in writing what it could
not see. Asked for a final check, the second pass compared **handler functions per tab
pair** — `ui/<tab>.py`'s nested `def`s against the Qt page's methods — and found three
more, every one of them in the Thaumaturgy picker again: an aspect could not be bought
narrowed (p.127), a specialty of your own could not be written (p.126), and a Science
could not be stepped back down. `docs/status/thaumaturgy.md` has all three.

**Nine for nine, and the shape of the result is the finding.** All six webapp→Qt gaps
found across both passes are in ONE panel — the Thaumaturgy page, which is where the port
compressed hardest (a four-column NiceGUI page became a tree, three lists and one shared
detail pane). ⚠ **When a port collapses a surface's SHAPE, that surface is where its
missing controls will be** — not spread evenly across the tabs, which is what the gap
lists kept assuming.

Everything else chased back to parity: submodules (Qt has Remove pre-lock, deliberately no
post-lock refund), the foreign-splat picker, the Form Library, Paths, augments, the
Panoply, health-level editing, the p.259 downtime calculator (in `main_window`, not
`editor`), hearthstones, passions, fetters, magical materials, dice pools, adversary
reset, and combo/array member removal. One cosmetic difference is left and is **not** a
gap by the human's call: the webapp's catalogue dialog takes per-row `icons`, and
`qt/catalogue.py` has no such parameter.
