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
| `ui/play.py` (~42L) | `play_state`, `normalize_health`, `cycle_mark`, `set_motes`, `set_count` — the PlayState mutators, and the "ui/play.py precedent" the thaumaturgy move cited. **⚠ decision 0006:** if these land in an `engine/play.py`, play-state must stay unreachable from validation | `engine/` |
| `ui/play.py` | `worst_penalty` — already takes a `viewmod.PlayView` | `view.py` |
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
dispatcher BEFORE it is ported, not after.** Advantages (Backgrounds + M&F) is the
next one — check whether its buy paths already have an engine home, and give them one
if not, while there is still only a single copy to move.

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

Test count: **2,482 passed, 3 skipped, 1 warning** (2026-08-21, the `-ds` machine).

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

## Open questions — not decided

* **Porting the 228 NiceGUI harness tests.** Both spikes proved retained-mode widgets
  test well with pytest-qt (28 + 14 tests, offscreen) — what each of the existing 228
  harness tests becomes in Qt is a per-test translation, done with the port.
* **PySide6 licensing** is LGPL, which is fine for this project — noted so it is not
  re-researched.
* **Theming.** `ui/theme.py`'s per-splat palettes are the design asset worth keeping;
  the Tailwind class strings that carry them are not. Qt Style Sheets are the likely
  target, but the mapping is unexamined.
