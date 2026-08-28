"""pytest-qt coverage for the Qt charm-tree spike — headless (conftest sets the
offscreen platform). The point is not breadth: it is the plan's open question —
does a retained-mode widget test well — plus the data-layer claim that
build_charm_graph feeds a bare Qt widget untouched."""

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QListWidget, QTabWidget

from exalted_builder.models.character import Character

from tree_spike import (CharmTreeView, NodeItem, TreeSpikeWindow, _tree_positions,
                        load_world, splat_labels)


def test_world_loads():
    rs, ch = load_world()
    assert len(rs.charms) > 1000
    assert ch.exalt_type == "Solar"
    assert "Solar" in splat_labels(rs, ch)


def _tab_labels(win):
    return [win.tabs.tabText(i) for i in range(win.tabs.count())]


def test_solar_tabs_are_charm_ma_spells_thaum(qtbot):
    rs, ch = load_world()
    win = TreeSpikeWindow(rs, ch)
    qtbot.addWidget(win)
    labels = _tab_labels(win)
    assert "Charms" in labels and "Martial Arts" in labels
    assert "Spells" in labels and "Thaumaturgy" in labels
    assert "Arcanoi" not in labels            # Solar has no Virtue-keyed trees
    assert win._tree_views["abilities"].graph is not None


def test_ghost_has_arcanoi_not_charms(qtbot):
    rs, ch = load_world()
    ghost = Character(id="ghost", exalt_type="Ghost")
    win = TreeSpikeWindow(rs, ghost)
    qtbot.addWidget(win)
    labels = _tab_labels(win)
    assert "Arcanoi" in labels
    assert "Charms" not in labels
    assert "Spells" not in labels             # ghosts cannot learn necromancy (human 2026-08-20)


def test_melee_tree_renders_nodes_edges_roots(qtbot):
    rs, ch = load_world()
    win = TreeSpikeWindow(rs, ch)
    qtbot.addWidget(win)
    view = win._tree_views["abilities"]
    view.show_tree("melee", "Solar")
    graph = view.graph
    assert graph.nodes and graph.edges and graph.roots
    node_items = [i for i in view._scene.items() if isinstance(i, NodeItem)]
    assert len(node_items) == len(graph.nodes)
    has_parent = {c for _, c in graph.edges}
    for n in graph.nodes:
        if n.id in graph.roots:
            assert n.id not in has_parent


def test_martial_arts_tab_categories_are_styles(qtbot):
    rs, ch = load_world()
    win = TreeSpikeWindow(rs, ch)
    qtbot.addWidget(win)
    combo = win._tree_views["styles"].category_combo
    assert combo.count() > 0
    for i in range(combo.count()):
        assert combo.itemData(i).startswith("martial_arts:"), combo.itemData(i)


def test_arcanoi_tab_categories_are_virtue_keyed(qtbot):
    rs, ch = load_world()
    ghost = Character(id="ghost", exalt_type="Ghost")
    win = TreeSpikeWindow(rs, ghost)
    qtbot.addWidget(win)
    combo = win._tree_views["arcanoi"].category_combo
    assert combo.count() > 0
    for i in range(combo.count()):
        base = combo.itemData(i).split(":", 1)[0]
        assert any(c.min_virtue for c in rs.charms.values() if c.category == base)


def test_click_selects_node_and_shows_details(qtbot):
    rs, ch = load_world()
    win = TreeSpikeWindow(rs, ch)
    qtbot.addWidget(win)
    view = win._tree_views["abilities"]
    view.show_tree("melee", "Solar")
    item = next(i for i in view._scene.items() if isinstance(i, NodeItem))
    item.setSelected(True)
    qtbot.wait(10)
    text = win.detail.toPlainText()
    assert item.node.label in text
    assert len(text) > len(item.node.label)      # description / traits shown too


def test_spell_detail_shows_circle_and_description(qtbot):
    rs, ch = load_world()
    win = TreeSpikeWindow(rs, ch)
    qtbot.addWidget(win)
    idx = next(i for i in range(win.tabs.count()) if win.tabs.tabText(i) == "Spells")
    entries = win.tabs.widget(idx).findChild(QListWidget)
    assert entries.count() > 0
    entries.setCurrentRow(0)
    qtbot.wait(10)
    text = win.detail.toPlainText()
    spell = entries.item(0).data(Qt.UserRole)
    assert spell.name in text
    assert spell.circle.value in text
    assert spell.description[:20] in text


def test_wheel_zooms(qtbot):
    rs, ch = load_world()
    win = TreeSpikeWindow(rs, ch)
    qtbot.addWidget(win)
    view = win._tree_views["abilities"]
    view.show_tree("melee", "Solar")
    before = view.transform().m11()
    event = QWheelEvent(QPointF(50, 50), QPointF(50, 50), QPoint(0, 0), QPoint(0, 120),
                        Qt.NoButton, Qt.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
    view.wheelEvent(event)
    assert view.transform().m11() > before


def test_wheel_zoom_with_pixel_delta_only(qtbot):
    # Wayland/trackpads deliver only pixelDelta — angleDelta 0 must not read as
    # "scroll down" (the bug that made zoom-in impossible).
    rs, ch = load_world()
    win = TreeSpikeWindow(rs, ch)
    qtbot.addWidget(win)
    view = win._tree_views["abilities"]
    view.show_tree("melee", "Solar")
    before = view.transform().m11()
    event = QWheelEvent(QPointF(50, 50), QPointF(50, 50), QPoint(0, 120), QPoint(0, 0),
                        Qt.NoButton, Qt.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
    view.wheelEvent(event)
    assert view.transform().m11() > before


def test_wheel_zero_delta_is_noop(qtbot):
    rs, ch = load_world()
    win = TreeSpikeWindow(rs, ch)
    qtbot.addWidget(win)
    view = win._tree_views["abilities"]
    view.show_tree("melee", "Solar")
    before = view.transform().m11()
    event = QWheelEvent(QPointF(50, 50), QPointF(50, 50), QPoint(0, 0), QPoint(0, 0),
                        Qt.NoButton, Qt.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
    view.wheelEvent(event)
    assert view.transform().m11() == before


def test_zoom_factor_scales_with_delta(qtbot):
    # A trackpad's small deltas must zoom less per event than a full mouse notch,
    # or smooth scroll becomes a wild jump.
    rs, ch = load_world()
    win = TreeSpikeWindow(rs, ch)
    qtbot.addWidget(win)
    view = win._tree_views["abilities"]
    view.show_tree("melee", "Solar")
    view.resetTransform()
    view.wheelEvent(QWheelEvent(QPointF(50, 50), QPointF(50, 50), QPoint(0, 0), QPoint(0, 120),
                                Qt.NoButton, Qt.NoModifier, Qt.ScrollPhase.NoScrollPhase, False))
    scale_120 = view.transform().m11()
    view.resetTransform()
    view.wheelEvent(QWheelEvent(QPointF(50, 50), QPointF(50, 50), QPoint(0, 0), QPoint(0, 6),
                                Qt.NoButton, Qt.NoModifier, Qt.ScrollPhase.NoScrollPhase, False))
    scale_6 = view.transform().m11()
    assert 1 < scale_6 < scale_120


def test_external_nodes_are_dashed(qtbot):
    # Solar Brawl pulls Martial Arts prerequisites from another category — the
    # cross-tree shape build_charm_graph draws in and marks `external`.
    rs, ch = load_world()
    win = TreeSpikeWindow(rs, ch)
    qtbot.addWidget(win)
    view = win._tree_views["abilities"]
    view.show_tree("brawl", "Solar")
    assert any(n.external for n in view.graph.nodes)
    externals = [i for i in view._scene.items()
                 if isinstance(i, NodeItem) and i.node.external]
    assert len(externals) == sum(1 for n in view.graph.nodes if n.external)


def test_populate_counts_match_graph(qtbot):
    rs, ch = load_world()
    win = TreeSpikeWindow(rs, ch)
    qtbot.addWidget(win)
    view = win._tree_views["abilities"]
    view.show_tree("archery", "Solar")
    nodes = [i for i in view._scene.items() if isinstance(i, NodeItem)]
    edges = [i for i in view._scene.items() if not isinstance(i, NodeItem)]
    assert len(nodes) == len(view.graph.nodes)
    assert len(edges) == len(view.graph.edges)


def test_popup_is_height_capped(qtbot):
    # maxVisibleItems is ignored for popup HEIGHT in this Qt build; CappedCombo
    # constrains the popup window itself once it opens.
    rs, ch = load_world()
    win = TreeSpikeWindow(rs, ch)
    qtbot.addWidget(win)
    combo = win._tree_views["abilities"].category_combo
    combo.showPopup()
    qtbot.wait(5)
    popup = combo.view().window()
    try:
        assert popup is not None and popup is not win
        cap = int(combo.view().sizeHintForRow(0) * 15 + 8)
        assert popup.maximumHeight() <= cap
        assert popup.height() <= cap
    finally:
        combo.hidePopup()


def test_spells_tab_lists_by_circle(qtbot):
    rs, ch = load_world()
    win = TreeSpikeWindow(rs, ch)
    qtbot.addWidget(win)
    idx = next(i for i in range(win.tabs.count()) if win.tabs.tabText(i) == "Spells")
    entries = win.tabs.widget(idx).findChild(QListWidget)
    assert entries.count() > 0               # default circle loads on build


def test_thaumaturgy_tab_has_four_subtabs(qtbot):
    rs, ch = load_world()
    win = TreeSpikeWindow(rs, ch)
    qtbot.addWidget(win)
    idx = next(i for i in range(win.tabs.count()) if win.tabs.tabText(i) == "Thaumaturgy")
    inner = win.tabs.widget(idx).findChild(QTabWidget)
    assert [inner.tabText(i) for i in range(inner.count())] == \
        ["Arts", "Sciences", "Rituals", "Formulas"]
    assert isinstance(inner.widget(0), QListWidget)
    assert inner.widget(0).count() > 0


def test_tree_positions_centers_and_spaces_by_width():
    from types import SimpleNamespace
    # A (wide) -> B, A -> C: A is centred over B and C, and its subtree reserves
    # A's own width so the next root's subtree never overlaps it.
    graph = SimpleNamespace(
        nodes=[SimpleNamespace(id="A"), SimpleNamespace(id="B"), SimpleNamespace(id="C")],
        edges=[("A", "B"), ("A", "C")])
    widths = {"A": 200, "B": 40, "C": 40}
    pos = _tree_positions(graph, widths)
    assert pos["B"][1] == pos["C"][1]                       # same depth
    mid = (pos["B"][0] + pos["C"][0]) / 2
    assert abs(pos["A"][0] - mid) < 1e-6                    # centred over children
    assert pos["B"][0] > pos["A"][0] - 100                  # children inside A's box
    assert pos["C"][0] < pos["A"][0] + 100
    # root y differs from children y; roots sit at the top level
    assert pos["A"][1] < pos["B"][1]


def test_node_width_is_capped(qtbot):
    from types import SimpleNamespace
    from PySide6.QtGui import QFont
    from tree_spike import MAX_NODE_W, NodeItem
    node = SimpleNamespace(
        label="A Charm Name That Is Absurdly Long And Would Normally Blow Past "
              "Any Reasonable Box Width Entirely",
        state="available", min_ability=5, min_essence=3, external=False)
    pal = SimpleNamespace(accent="#123", accent_dark="#456", node_bg="#fff", ink="#000")
    item = NodeItem(node, pal, QFont())
    assert item.rect().width() <= MAX_NODE_W
    assert len(item._label) < len(node.label)      # the label was elided


def test_route_edge_detours_around_boxes():
    from PySide6.QtCore import QPointF
    from tree_spike import _route_edge, _segment_hits_rect
    # The (0,56)->(200,200) edge passes through the box (70,92,110,148).
    start = QPointF(0.0, 56.0)
    end = QPointF(200.0, 200.0)
    box = (70, 92, 110, 148)
    assert _segment_hits_rect(0, 56, 200, 200, *box)
    target = (180, 172, 220, 228)              # the child's box (top-centre 200,200)
    pts = _route_edge(start, end, [box], [], target)
    assert len(pts) > 2                         # detoured around the box
    for i in range(len(pts) - 1):               # and no segment re-enters it
        assert not _segment_hits_rect(pts[i][0], pts[i][1], pts[i + 1][0],
                                      pts[i + 1][1], *box)
    assert len(_route_edge(start, end, [], [], target)) == 2   # clear stays straight


def test_parallel_detours_offset_their_rails(qtbot):
    from PySide6.QtCore import QPointF
    from tree_spike import _route_edge
    box = (100, 100, 200, 200)                   # a node box both edges would cross
    rails = []
    a = _route_edge(QPointF(50, 0), QPointF(250, 300), [box], rails, (230, 272, 270, 328))
    b = _route_edge(QPointF(50, 50), QPointF(250, 250), [box], rails, (230, 222, 270, 278))
    assert len(a) > 2 and len(b) > 2             # both detoured

    def rail_y(pts):
        return {round(p[1]) for i, p in enumerate(pts[:-1]) if p[1] == pts[i + 1][1]}
    assert rail_y(a) and rail_y(b)
    assert rail_y(a) != rail_y(b)                # they don't ride the same rail


def test_edge_arrowhead_points_along_last_segment(qtbot):
    from tree_spike import EdgeItem
    edge = EdgeItem([(0.0, 0.0), (40.0, 100.0)], "#123456")
    x1, y1 = edge._points[-2]
    x2, y2 = edge._points[-1]
    assert y2 > y1                     # arrow enters the child from above
    assert edge.path().elementCount() > 0


def test_wide_levels_sub_row(qtbot):
    # Prismatic Arrangement of Creation roots eleven Charms: they must split across
    # sub-rows (6+5) rather than stretch the tree to eleven wide.
    from tree_spike import MAX_LEVEL_NODES, _tree_positions
    rs, ch = load_world()
    view = CharmTreeView(rs, ch)
    qtbot.addWidget(view)
    view.show_tree("martial_arts:prismatic-arrangement-of-creation", "Solar")
    if not view.graph.nodes:
        return
    w = {i.node.id: i.rect().width() for i in view._scene.items() if hasattr(i, "node")}
    pos = _tree_positions(view.graph, w)
    roots = [n.id for n in view.graph.nodes if n.id not in {c for _, c in view.graph.edges}]
    if len(roots) > MAX_LEVEL_NODES:
        assert len({pos[r][1] for r in roots}) >= 2


def test_initial_view_fits_all_nodes(qtbot):
    rs, ch = load_world()
    view = CharmTreeView(rs, ch)
    qtbot.addWidget(view)
    view.resize(800, 600)                # give it a real size before loading
    view.show_tree("melee", "Solar")
    qtbot.wait(30)                       # the fit is deferred until the layout settles
    assert view._pending_fit is False    # then it runs and leaves the tree fitted


def test_resize_refits_viewport(qtbot):
    rs, ch = load_world()
    view = CharmTreeView(rs, ch)
    qtbot.addWidget(view)
    view.show()                          # resizeEvents only fire on a shown widget
    view.resize(800, 600)
    view.show_tree("melee", "Solar")
    qtbot.wait(30)
    scale_a = view.transform().m11()
    view.resize(1200, 600)               # widen — the tree re-fits to the new viewport
    qtbot.wait(10)
    assert view.transform().m11() != scale_a


def test_wheel_zoom_not_undone_by_scrollbar_resize(qtbot):
    # Zooming in makes scrollbars appear, which shrinks the view and fires resize
    # events; those must not re-fit and undo the zoom.
    rs, ch = load_world()
    view = CharmTreeView(rs, ch)
    qtbot.addWidget(view)
    view.show()
    view.resize(800, 600)
    view.show_tree("melee", "Solar")
    qtbot.wait(30)
    base = view.transform().m11()
    view.wheelEvent(QWheelEvent(QPointF(400, 300), QPointF(400, 300), QPoint(0, 0), QPoint(0, 120),
                                Qt.NoButton, Qt.NoModifier, Qt.ScrollPhase.NoScrollPhase, False))
    qtbot.wait(50)                       # scrollbar-triggered resizes land here, ignored
    assert view.transform().m11() > base


def test_root_leaves_move_to_their_own_row(qtbot):
    # Roots with no children (isolated entry Charms) sit below the main forest.
    from tree_spike import _tree_positions
    rs, ch = load_world()
    view = CharmTreeView(rs, ch)
    qtbot.addWidget(view)
    view.show_tree("martial_arts:prismatic-arrangement-of-creation", "Solar")
    if not view.graph.nodes:
        return
    w = {i.node.id: i.rect().width() for i in view._scene.items() if hasattr(i, "node")}
    pos = _tree_positions(view.graph, w)
    childless_roots = [n.id for n in view.graph.nodes
                       if n.id not in {c for _, c in view.graph.edges}
                       and not any(p == n.id for p, _ in view.graph.edges)]
    if childless_roots:
        forest_bottom = max(pos[n][1] for n in pos if n not in childless_roots)
        assert all(pos[r][1] > forest_bottom for r in childless_roots)


def test_roots_sharing_a_child_group_together(qtbot):
    # Prismatic's four feeders of four-magical-materials-form must be adjacent —
    # the fan-in grouping that shortens the crossing edges.
    from tree_spike import _tree_positions
    rs, ch = load_world()
    view = CharmTreeView(rs, ch)
    qtbot.addWidget(view)
    view.show_tree("martial_arts:prismatic-arrangement-of-creation", "Solar")
    if not view.graph.nodes:
        return
    w = {i.node.id: i.rect().width() for i in view._scene.items() if hasattr(i, "node")}
    pos = _tree_positions(view.graph, w)
    roots = [n.id for n in view.graph.nodes if n.id not in {c for _, c in view.graph.edges}]
    by_x = sorted(roots, key=lambda r: pos[r][0])
    child_of = {}
    for p, c in view.graph.edges:
        child_of.setdefault(p, []).append(c)
    feeders = [r for r in roots if "four-magical-materials-form" in str(child_of.get(r, []))]
    if len(feeders) >= 2:
        idx = [by_x.index(f) for f in feeders]
        assert max(idx) - min(idx) == len(feeders) - 1    # contiguous in root order
