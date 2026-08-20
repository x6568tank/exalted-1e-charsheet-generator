# Qt charm-tree spike

Proves the claims `docs/plans/qt-port.md` needs before a full PySide6 port is
scheduled: that `QGraphicsView` is a decent fit for the charm-tree picker, that a
retained-mode widget tests well with pytest-qt, and that the framework-free layers feed
a bare Qt widget with **zero changes**.

## Run the window (real display, the feel test)

```sh
.venv/bin/python spikes/qt_tree/tree_spike.py
```

The window imitates the app's picker, not its architecture — `QTabWidget` keeps
persistent pages; nothing rebuilds per click.

- **Splat dropdown** — switch pages; the tab bar rebuilds per splat exactly like the
  app's `GROUPS` (a Solar gets Charms/Martial Arts/Spells/Thaumaturgy and no Arcanoi;
  a Ghost gets Arcanoi/Thaumaturgy and no Charms).
- **Tree tabs** (Charms / Martial Arts / Arcanoi) — category dropdown over a
  pan/zoom/click tree. A tidy-tree layout fans each tree from its roots, nodes centred
  over their children and spaced by their own width (capped at `MAX_NODE_W`, longer
  labels elide). A level wider than `MAX_LEVEL_NODES` sub-rows (6+5 for Prismatic
  Arrangement of Creation's eleven roots); roots with no edges move to their own row;
  roots are grouped by the children they feed, so fan-in trees read as clusters. Each
  tree opens at the minimum zoom that shows every node, and re-fits when the window or
  splitter is resized. An edge is a straight diagonal when its path is clear; a
  prerequisite line that would cross a node box detours around it, and parallel
  detours offset onto separate rails; edges are semi-transparent with a target
  arrowhead that never hides under a node.
- **Panel tabs** — Spells (circle dropdown → spell list) and Thaumaturgy
  (Arts/Sciences/Rituals/Formulas sub-tabs).
- Click a tree node or a list row: the right panel shows the full detail (description,
  requirement, prerequisites, cost — via `build_charm_detail` / the app's own
  `_cost_str`). Scroll zooms (delta-proportional, so a trackpad and a mouse feel the
  same) and is not undone by the scrollbars zooming in causes.

## Run the tests (headless)

```sh
.venv/bin/python -m pytest spikes/qt_tree -q
```

`conftest.py` pins `QT_QPA_PLATFORM=offscreen`. **28 tests**: the per-splat tab set,
tree node/edge/root counts, MA/Arcanoi category membership, grouping and root-leaf rows,
node-width caps, click→detail (description + spell circle), wheel zoom (incl. pixel-
delta, proportional-delta, and not-undone-by-scrollbars), edge detour/rail routing,
arrow visibility, scene-vs-graph parity, the popup height cap, fit-to-view and resize
re-fit, and the spells/thaumaturgy panels.

## What it reuses vs. what it adds

| Reused (framework-free, as a port would) | Spike-only |
|---|---|
| `rules_db.load_ruleset` | `NodeItem` / `EdgeItem` (QGraphicsScene rendering) |
| `ui.view.build_charm_graph` / `charm_on_splat_page` / `virtue_split` / `_style_label` / `build_spell_picker` / `build_charm_detail` / `_cost_str` / `CIRCLE_DISPLAY_ORDER` | `_tree_positions` (tidy-tree forest + grouping + sub-rows + root-leaf rows), `_route_edge` (node/rail-aware routing) |
| `ui.theme.palette` (per-splat colours) | `CharmTreeView` (pan/zoom/click/fit), `CappedCombo` |
| group/tab rules mirroring `picker._group_of` | the QTabWidget pages + detail panel |

## Footprint

- `PySide6` and `pytest-qt` are installed in `.venv` for this spike **only**; nothing
  under `exalted_builder/` imports them (a test-greppable invariant the plan relies on).
  They are deliberately **not** added to `pyproject.toml` — if the spike earns a port,
  they get added then, in their proper extras.
- `spikes/` sits outside `testpaths = ["tests"]`, so the main suite never sees it.
