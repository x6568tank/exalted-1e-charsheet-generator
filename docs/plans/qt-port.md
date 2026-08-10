# Plan — replace NiceGUI with PySide6/Qt, after 1.0

**Status: a standing goal, not scheduled and not started.** Raised by the human
2026-08-10 as the intended direction *after* the 1.0 ship (feature-complete: sourcebooks,
the full artifact and spell catalogues). Nothing here is committed — when it is, it
becomes **decision 0015** and this file turns into its build record.

**Do not start this before 1.0, and do not treat it as a 1.0 blocker.** A different
widget toolkit is not a feature; it is the foundation a 2.0 would be built on.

## Why it is feasible — the measured baseline

Taken 2026-08-10, at 2,092 passing tests. These numbers are the whole argument, so
re-measure before acting on them rather than trusting the table:

```sh
for d in models engine ui; do find exalted_builder/$d -name '*.py' | xargs wc -l | tail -1; done
grep -rln nicegui exalted_builder/          # which modules are actually bound to it
grep -rc "nicegui_main_file" tests/*.py     # which tests die with the toolkit
```

| Layer | LOC | Survives the port? |
|---|---|---|
| `models/` | 3,579 | Yes, untouched |
| `engine/` | 10,615 | Yes, untouched |
| loader / persistence / `custom_content` / … | 1,320 | Yes, untouched |
| `ui/view.py` — the presenter | 2,439 | **Yes** — imports no UI toolkit |
| `ui/theme.py`, `ui/assets.py` | 214 | Palette data yes; the Tailwind class strings die |
| the 12 NiceGUI widget modules | ~9,200 | **No — this is the rewrite** |

Tests split the same way: **1,747 of 1,975 test functions are framework-free**; only
**228** use the NiceGUI `user` harness.

Two facts make this unusually cheap for a UI port, and both are decision 0002
("data-driven rules, pure engine, **disposable UI**") having actually been honoured
rather than merely written down:

1. **Nothing outside `ui/` imports `nicegui`.** The engine, the models, the loader and
   persistence are toolkit-agnostic today. Verify with the grep above before starting —
   if that stops being true, fix it first, because it is the precondition for everything
   else here.
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
* **Printing.** There is no PDF or print path today, and a character sheet is a thing
  people print. `QPrinter` / `QPdfWriter` is first-class; from the browser you are at the
  mercy of print CSS.
* **A whole class of bug disappears.** Every one of these was paid for in real sessions
  and none exists in Qt: the nested-dialog canary trap and slot-deleted-mid-handler
  (`docs/status/catalogue-dialogs.md`), `@ui.refreshable` inside a loop, `ui.scroll_area`
  not sizing from `max-h`, and the test harness dispatching clicks without bubbling.

The counterweight, stated so it is not forgotten: **NiceGUI already packages to a
standalone executable** via `pack/` (the `desktop` extra, PyInstaller). "A real app" is
therefore *not* a reason on its own. If the charm tree and printing turn out not to
matter, this is ~9,200 lines rewritten for aesthetics.

## The prep work — do this before 1.0, as ordinary hygiene

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

1. Ship 1.0 on NiceGUI and **freeze it**. Do not maintain two UIs — the NiceGUI build
   becomes the reference implementation to diff behaviour against, not a parallel target.
2. Branch. Build the Qt layer up against the untouched `engine/` + `models/` +
   `view.py` until it reaches parity; only then does it become 2.0's bedrock.
3. Write **decision 0015** at the moment of commitment, recording the rejected
   alternatives so a later session does not reopen it: *stay on NiceGUI*; *NiceGUI
   `native=True` via pywebview* (the cheap middle path — a native window without the
   rewrite, which gets none of the three benefits above); *a Qt port before 1.0*.

## Open questions — not decided

* **`pytest-qt` and what replaces the 228 harness tests.** Qt is testable, but the shape
  of a click-through test changes. Unknown until someone tries it.
* **Does the sheet view become a `QTextDocument`?** That would give printing and the
  on-screen sheet from one source, but it is a different rendering model again.
* **PySide6 licensing** is LGPL, which is fine for this project — noted so it is not
  re-researched.
* **Theming.** `ui/theme.py`'s per-splat palettes are the design asset worth keeping;
  the Tailwind class strings that carry them are not. Qt Style Sheets are the likely
  target, but the mapping is unexamined.
