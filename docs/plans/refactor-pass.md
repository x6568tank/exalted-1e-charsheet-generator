# Optimization and refactoring pass — opened 2026-10-09

Features are paused (the human, 2026-10-09). Order agreed:

1. **Test suite speed.** 6–7 min per `docs/testing.md`; the step-9 run passed 18 min
   before it was stopped.
2. **Split the oversized modules**, the `engine/validate/` way (facade package, suite
   green at every commit, an import DAG). First target `ui/view.py` (5,081 lines).
3. The docstring pass (deferred until after the validate split, never done).
4. Audit for presenter/engine values computed twice across `ui/` and `qt/` — not a
   UI parity merge (the two are separate design surfaces).

## Item 1 — suite speed: DONE 2026-10-09

21 min 22 s (one process) → 8:06 (one process, the freeze alone) → 3:00 (`-n 4`), same
4,177 passed + 1 skipped. After the rebase onto the other machine's 24 commits: 4,390
passed + 1 skipped in 4:42 at `-n 4`. Two changes: a per-module `gc.freeze()` in `tests/conftest.py` (NiceGUI's user
simulation runs a full `gc.collect()` twice per UI test over a heap past a million
objects), and pytest-xdist in the `dev` extra. Found on the way: a vacuous Qt scroll test, now
real. Detail: `docs/testing.md`.

Left, measured, not done: each UI test re-loads the rulebook through its main file
(~0.1 s); ~18 table tests wait on the real 2 s poll; NiceGUI's own event dispatch
(`inspect.signature` per change) is ~10% of a UI test.

## Item 2 — split `ui/view.py`: DONE 2026-10-09

5,143 lines → the package `ui/view/`, 21 domain modules and a facade. One commit,
mechanical: a script sliced the file by line range, computed each module's imports from
what its slice reads, and generated the facade. Every non-blank line of the old body is
in the package (checked by a line multiset); every old top-level name is defined exactly
once. Module list and the DAG: `ARCHITECTURE.md`, "`ui/view/` — a package".

| | before | after |
|---|---|---|
| Largest file | 5,143 | ~780 (`sheet.py`) |
| Call sites changed | — | **1 test** (a monkeypatch, below) |

**Suite: 4,397 passed + 1 skipped, OBSERVED 2026-10-09 at `-n 4` in 4:35** (4,390 before, +7 in the new safety net). Comment and doc edits followed the run; `test_view_facade.py` and `test_engine_seam.py` re-run green after them (57). No UI behaviour changed, so nothing is owed in a browser.

Five helpers moved to `_base` to break the one cycle (`charm_trees` ↔ `sheet`):
`_cost_str`, `_charm_description`, `_SHAPING_TURNS`, `source_label`, `_health_label`.

The safety net, `tests/test_view_facade.py` (now `test_package_facades.py`), was written first and passed on the unsplit
file. What went wrong anyway:

1. **Function-local relative imports.** Ten `from ..engine import dice` lines inside
   functions needed a third dot. The undefined-name check cannot see it — the import
   binds the name — and an import smoke test does not run the function. 105 tests
   failed. Now `test_every_relative_import_in_the_package_resolves`, negative-controlled.
2. **A monkeypatch on the facade.** `test_a_merged_pool_gets_ONE_mote_input` patched
   `viewmod.build_play_view`; `build_party_card_view` reads it inside `play_state`. It
   patches `view.play_state` now. (`test_qt_play`'s twin still patches the facade,
   correctly — `qt/play.py` reads `viewmod.build_play_view`.)

### `models/rules.py` → `models/rules/`: DONE 2026-10-09

3,162 lines → 9 modules, largest `budgets.py` (~900, the cost tables and
`ExaltDefinition`). Same script, same checks: every line and every name accounted for,
the real rulebook loads (1,921 Charms), and every pydantic model reports
`__pydantic_complete__` — a forward reference to a name a module does not import only
fails at validation time, so that check matters more here than an import. Eight small
shared models moved to `_base` to break the one cycle (`charms`/`castes` ↔ `budgets` ↔
`backgrounds`): `Source`, `Damage`, `DAMAGE_LABELS`, the three ability/attribute
minimums, `EssencePoolSpec`, `BackgroundBudgetTier`. No call site changed. The safety net is now
`tests/test_package_facades.py`, parametrized over both packages.

**Suite: 4,411 passed + 1 skipped, OBSERVED 2026-10-09 at `-n 4` in 4:44.** The +14
over the view split: +5 facade tests, +9 `test_engine_seam` cases (it parametrizes per
engine-side file, and `rules/` is 9 files where `rules.py` was 1).

### Not split, by the human's rule ("if a file is better off on its own, don't")

* `qt/charms.py` (3,121) — 2,386 lines are ONE class, `CharmsPage` (86 methods).
* `ui/picker.py` (2,155) — 1,993 lines are ONE function, `build_picker` (closures).
* `server/table_view.py` (2,092) — 1,447 lines are ONE class, `_TableView`.

A file split cannot move a class or a closure; each would need a decomposition of the
class or the function, which is a different refactor with real behaviour risk.

Next by size, re-counted 2026-10-09: `models/rules.py` 3,162, `qt/charms.py` 3,121,
`engine/advancement.py` 2,173, `ui/picker.py` 2,155, `server/table_view.py` 2,092.

## Runtime measurements, 2026-10-09 (dev laptop)

⚠ **Taken on a stale checkout** (`dd997e5`, before P4, accounts and v1.4.0). Re-measure
before acting on any of them; line numbers and module sizes have moved.

| | |
|---|---|
| `load_ruleset` (1,921 Charms) | 0.07 s |
| `validate()` on each `examples/` character | ~1 ms |
| Qt `MainWindow` build, `ashes-of-dawn` | 0.97 s |
| One Qt `_refresh` | ~6 ms |

Ruling: no standalone runtime optimization pass — nothing a user feels.

## ⏸ Deferred until AFTER the splits — three runtime findings

From a cProfile of the Qt `MainWindow` build (offscreen). Do these once the modules are
split, when the call paths are easy to see. Re-profile first; the numbers will move.

1. **677 `setStyleSheet` calls, 0.27 s** (over a quarter of the build), most under
   `theme.apply` via `_apply_chrome`. Style at a higher level instead of per widget.
   ⚠ Memory: an ancestor stylesheet beats a set palette — a rendering test must be
   negative-controlled.
2. **The same unchanged character is derived over and over in one build:**
   `build_sheet_view` ×16, `validate_chargen` ×16, `merits_and_flaws_calc` ×875.
   Compute once per refresh and hand the result down. Structural, not only speed.
3. **`charm_matches_splat` ×14,277, ~0.2 s**, from `qt/charms.py::trees_for` (5 calls)
   through `view.charm_on_splat_page`. The answer changes only when the splat changes;
   memoize on the splat, invalidate on splat change and on homebrew writes.

Target: window build ~0.4 s. Nice to have, not urgent.

4. **The NiceGUI builder page takes ~350 ms to build (`GET /`, `yarak`, 517 KB of
   HTML), and half of that is the dot tracks.** `editor.dot_track` makes one `ui.icon`
   with its own click listener PER PIP: 280 `dots()` calls over 7 builds cost 1.06 s
   cumulative; the ⓘ `trait_info_button`s another 0.27 s. One element per track, with the
   pip index taken from the click event, should roughly halve the page. This matters
   on the hosted server, not the desktop: it runs ONE worker, so a page build blocks
   every other user. ⚠ Memory: a tracker click must repaint, never rebuild; and
   `_handle_event` is how tests click one pip of many — the tests change with it.

### Measured and NOT worth doing

| Path | Cost | Why not |
|---|---|---|
| `build_sheet_view` / `build_play_view` / `build_party_card_view` | 0.3–2 ms | — |
| `pdf.build_pdf`, one sheet / party of 4 | 50–85 ms / 266 ms | inside reportlab (the pure-Python `rl_accel` fallbacks), on a click |
| Table poll, every 2 s per client | well under 1 ms | `character_digest` ~0.05 ms; a file copy is one `stat` |
