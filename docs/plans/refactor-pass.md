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
