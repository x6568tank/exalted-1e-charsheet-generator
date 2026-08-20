"""The Qt Charms tab (exalted_builder/qt/charms.py) — QGraphicsView charm trees.

Ports the qt_tree spike's layout/routing coverage into the port: per-splat tab sets,
node/edge/root counts, the tidy-tree layout, wheel zoom, and selection → detail. The
layout and routing functions are pure, so they test without a widget at all.
"""

from types import SimpleNamespace

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QWheelEvent

from exalted_builder.engine import advancement, lifecycle
from exalted_builder.models.character import AbilityName, Character
from exalted_builder.qt.charms import (CharmsPage, CharmTreeView, EdgeItem,
                                       NodeItem, _tree_positions, populate)
from exalted_builder.ui.view import build_thaum_picker


def _visible_tabs(page):
    return [page.tabs.tabText(i) for i in range(page.tabs.count())]


def test_solar_page_tabs(ruleset, qtbot):
    page = CharmsPage(ruleset, {"char": Character(id="char.new", exalt_type="Solar")})
    qtbot.addWidget(page)
    assert _visible_tabs(page) == ["Charms", "Martial Arts", "Spells", "Thaumaturgy"]
    assert "abilities" in page._tree_views


def test_ghost_page_tabs(ruleset, qtbot):
    page = CharmsPage(ruleset, {"char": Character(id="char.new", exalt_type="Ghost")})
    qtbot.addWidget(page)
    tabs = _visible_tabs(page)
    assert "Charms" not in tabs          # ghosts have no Charm trees
    assert "Arcanoi" in tabs
    assert "Spells" not in tabs          # ghosts cannot learn necromancy
    assert "arcanoi" in page._tree_views


def test_melee_tree_renders_nodes_edges(qtbot, ruleset):
    char = Character(id="char.new")
    page = CharmsPage(ruleset, {"char": char})
    qtbot.addWidget(page)
    view = page._tree_views["abilities"]
    graph = view.graph
    assert graph is not None
    scene = view.scene()
    node_items = [i for i in scene.items() if isinstance(i, NodeItem)]
    edge_items = [i for i in scene.items() if isinstance(i, EdgeItem)]
    assert len(node_items) == len(graph.nodes)
    assert len(edge_items) == len(graph.edges)


def test_tree_positions_centers_parent_over_children():
    # A 3-node tree: a parent with two children of equal width. The parent sits at
    # the centre of its children's span, above them.
    graph = SimpleNamespace(
        nodes=[SimpleNamespace(id=n) for n in ("root", "a", "b")],
        edges=[("root", "a"), ("root", "b")])
    width = {"root": 100, "a": 60, "b": 60}
    pos = _tree_positions(graph, width)
    assert pos["root"][1] < pos["a"][1]
    children_centre = (pos["a"][0] + pos["b"][0]) / 2
    assert abs(pos["root"][0] - children_centre) < 1e-6


def test_wide_levels_sub_row():
    # A parent with eleven children (Prismatic Arrangement of Creation) must not sit
    # them all on one row — the level sub-rows at MAX_LEVEL_NODES (6 + 5).
    nodes = [SimpleNamespace(id="center")] + [SimpleNamespace(id=f"c{i}") for i in range(11)]
    edges = [("center", f"c{i}") for i in range(11)]
    graph = SimpleNamespace(nodes=nodes, edges=edges)
    width = {n.id: 100.0 for n in nodes}
    pos = _tree_positions(graph, width)
    child_ys = {pos[f"c{i}"][1] for i in range(11)}
    assert len(child_ys) >= 2


def test_click_selects_node_and_shows_detail(qtbot, ruleset):
    char = Character(id="char.new")
    page = CharmsPage(ruleset, {"char": char})
    qtbot.addWidget(page)
    view = page._tree_views["abilities"]
    node_item = next(i for i in view.scene().items() if isinstance(i, NodeItem))
    node_item.setSelected(True)
    qtbot.wait(5)
    detail = page.detail.toPlainText()
    assert len(detail) > 0


def _learnable_char():
    """A Solar with a few ability dots, so some Charms are actually available — a
    fresh Character's abilities are all 0 and nothing passes a prerequisite."""
    char = Character(id="char.new")
    for ab in (AbilityName.MELEE, AbilityName.ARCHERY, AbilityName.DODGE,
               AbilityName.OCCULT):
        char.abilities[ab] = 3
    return char


def _first_available(ruleset, char):
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    view = page._tree_views["abilities"]
    return [i.node.id for i in view.scene().items()
            if isinstance(i, NodeItem) and i.node.state == "available"]


def test_charms_learn_appends_in_chargen(qtbot, ruleset):
    char = _learnable_char()
    avail = _first_available(ruleset, char)
    assert avail
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    page._toggle_charm(avail[0])
    assert avail[0] in char.charms


def test_charms_buy_post_lock_spends_xp(qtbot, ruleset):
    char = _learnable_char()
    advancement.add_xp(char, 100)
    lifecycle.lock_chargen(char, ruleset)
    avail = _first_available(ruleset, char)
    assert avail
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    available_before = advancement.xp_available(char)
    page._toggle_charm(avail[0])
    assert avail[0] in char.charms
    assert advancement.xp_available(char) < available_before


def test_charms_learn_thaum_art(qtbot, ruleset):
    char = _learnable_char()
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    picker = build_thaum_picker(ruleset, char)
    arts = [r for r in picker.arts if r.available]
    assert arts
    page._toggle_thaum("art", arts[0])
    after = build_thaum_picker(ruleset, char)
    assert any(r.id == arts[0].id and r.owned for r in after.arts)


def test_charms_learn_thaum_art_specialty(qtbot, ruleset):
    char = _learnable_char()
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    picker = build_thaum_picker(ruleset, char)
    art = next((a for a in picker.arts if a.specialties), None)
    assert art is not None
    spec = next((s for s in art.specialties if s.available), None)
    assert spec is not None
    page._toggle_thaum("art_specialty", art, spec)
    after = build_thaum_picker(ruleset, char)
    owned_specs = {s.name for a in after.arts for s in a.specialties if s.owned}
    assert spec.name in owned_specs


def test_charms_thaum_buy_flips_button_and_unlearns(qtbot, ruleset):
    char = _learnable_char()
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    picker = build_thaum_picker(ruleset, char)
    formula = next(r for r in picker.formulas if r.available)
    page._selected_thaum = ("formula", formula)
    page._toggle_thaum("formula", formula)
    assert page._selected_thaum[1].owned       # the button now reads "Drop"
    assert not page._orientation_combo.isEnabled()   # owned -> no orientation pick
    page._toggle_thaum("formula", page._selected_thaum[1])
    assert not page._selected_thaum[1].owned   # unlearned


def test_charms_thaum_orientation_combo_for_first_buy(qtbot, ruleset):
    char = _learnable_char()
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    picker = build_thaum_picker(ruleset, char)
    formula = next(r for r in picker.formulas if r.available)
    page._selected_thaum = ("formula", formula)
    page._update_action()
    assert page._orientation_combo.isEnabled()      # a first purchase needs the region
    assert page._orientation_combo.count() == 5


def test_charms_remove_in_chargen(qtbot, ruleset):
    char = _learnable_char()
    avail = _first_available(ruleset, char)
    char.charms.append(avail[0])
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    page._toggle_charm(avail[0])
    assert avail[0] not in char.charms


def test_wheel_zoom_scales(qtbot, ruleset):
    char = Character(id="char.new")
    page = CharmsPage(ruleset, {"char": char})
    qtbot.addWidget(page)
    view = page._tree_views["abilities"]
    before = view.transform().m11()
    event = QWheelEvent(QPoint(50, 50), QPoint(50, 50), QPoint(0, 0),
                        QPoint(0, 120), Qt.MouseButton.NoButton,
                        Qt.KeyboardModifier.NoModifier,
                        Qt.ScrollPhase.NoScrollPhase, False)
    view.wheelEvent(event)
    assert view.transform().m11() != before
