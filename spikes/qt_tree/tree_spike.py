"""Qt spike: render the app's Charm catalogue with QGraphicsView, reusing the existing
framework-free layers.

Input: a RuleSet + fresh Character from rules_db.load_ruleset, a splat label, category
keys and circle values — the inputs ui.view's picker helpers take. Output: a bare-Qt
window imitating the picker's tab bar (Charms / Martial Arts / Arcanoi as Charm trees,
Spells and Thaumaturgy as list panels), with pan/zoom/click and a detail panel.
Mechanism: QGraphicsScene holds rounded-rect node items and straight edge paths in a
tidy-tree layout (each node centred over its children, leaves spaced by their own
width); QGraphicsView supplies pan (ScrollHandDrag) and delta-proportional wheel zoom;
group/tab membership mirrors picker._group_of; node colours come from ui.theme.palette.

What this is for: docs/plans/qt-port.md, "Recommended before commitment" — prove the
QGraphicsView fit and the pytest-qt test story before any full port. Nothing in
exalted_builder/ imports Qt; this file is the only thing that does.
"""

from __future__ import annotations

import html
import math
import sys
from collections import defaultdict
from pathlib import Path

import exalted_builder
from PySide6.QtCore import QPointF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import (
    QApplication, QComboBox, QGraphicsItem, QGraphicsPathItem, QGraphicsRectItem,
    QGraphicsScene, QGraphicsView, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QMainWindow, QSizePolicy, QSplitter, QStyle, QTabWidget, QTextBrowser,
    QVBoxLayout, QWidget,
)

from exalted_builder.models.character import Character
from exalted_builder.rules_db import load_ruleset
from exalted_builder.ui import theme
from exalted_builder.ui.view import (CIRCLE_DISPLAY_ORDER, _cost_str, _style_label,
                                     build_charm_detail, build_charm_graph,
                                     build_spell_picker, charm_on_splat_page,
                                     virtue_split)

DATA_DIR = Path(exalted_builder.__file__).parent / "data"

ROW_H = 160            # vertical space between tree levels
GAP_X = 40             # horizontal gap between sibling subtrees
NODE_H = 56
MIN_W = 150            # smallest node box
MAX_NODE_W = 260       # largest node box; longer labels elide with an ellipsis
MAX_LEVEL_NODES = 6    # cap nodes in one tree-level row; wider levels sub-row


def load_world():
    """(ruleset, fresh Solar character) — the two objects the picker helpers need."""
    ruleset = load_ruleset(DATA_DIR)
    return ruleset, Character(id="char.new")


def splat_labels(ruleset, character):
    """Distinct Exalt types that have Charm pages, the character's own first."""
    types = {c.exalt_type for c in ruleset.charms.values()}
    types.discard("")
    return [character.exalt_type] + sorted(t for t in types if t != character.exalt_type)


def _arcanoi_categories(ruleset):
    """Category names whose Charms are Arcanoi: Virtue-keyed and not the spirit Charms
    (which share the min_virtue axis but are a different class, exalt_type "Spirit")."""
    return {c.category for c in ruleset.charms.values()
            if c.min_virtue and c.exalt_type != "Spirit"}


def group_of(category, ruleset):
    """The picker group a category belongs to: 'styles' / 'arcanoi' / 'abilities'.

    Mirrors picker._group_of: martial-arts categories are named by prefix; a category
    is an arcanos when its base name (before any `:virtue` split) is one of the
    Virtue-keyed non-spirit categories; everything else is an ability Charm."""
    if category.startswith("martial_arts:"):
        return "styles"
    return ("arcanoi" if category.split(":", 1)[0] in _arcanoi_categories(ruleset)
            else "abilities")


def trees_for(ruleset, character, splat, group):
    """[(category_key, node_count)] for one splat's page in `group`, biggest first."""
    found: set[str] = set()
    for c in ruleset.charms.values():
        if not charm_on_splat_page(ruleset, character, c, splat):
            continue
        for key in (virtue_split(ruleset, c.category) or [c.category]):
            if group_of(key, ruleset) == group:
                found.add(key)
    out = []
    for key in found:
        graph = build_charm_graph(ruleset, character, key, splat)
        if graph.nodes:
            out.append((key, len(graph.nodes)))
    return sorted(out, key=lambda t: -t[1])


def spell_circles(ruleset, character):
    """Spell-circle display values this splat could ever reach, in display order."""
    reachable = {r.circle for r in build_spell_picker(ruleset, character)}
    return [c.value for c in CIRCLE_DISPLAY_ORDER if c.value in reachable]


def spells_in_circle(ruleset, circle_value):
    """(name, Spell) pairs in one circle, sorted by name."""
    spells = [s for s in ruleset.spells.values() if s.circle.value == circle_value]
    spells.sort(key=lambda s: s.name)
    return [(s.name, s) for s in spells]


def _detail_html(obj):
    """Rich-text detail panel for a CharmDetail, Spell, or Thaumaturgy entry: name,
    the trait lines (requirement / prerequisites, cost, circle, …), and the
    description."""
    name = html.escape(getattr(obj, "name", ""))
    desc = html.escape(getattr(obj, "description", ""))
    lines = []
    if getattr(obj, "requirement", ""):
        lines.append(f"<b>Requirement:</b> {html.escape(obj.requirement)}")
    groups = getattr(obj, "prerequisite_groups", [])
    if groups:
        req = " and ".join(" or ".join(html.escape(n) for n in g) for g in groups)
        lines.append(f"<b>Requires:</b> {req}")
    for field, label in (("type", "Type"), ("duration", "Duration"),
                         ("circle", "Circle"), ("level", "Level"),
                         ("min_occult", "Min Occult"), ("roll", "Roll"),
                         ("resources", "Resources")):
        if hasattr(obj, field):
            v = getattr(obj, field)
            v = v.value if hasattr(v, "value") else v
            if v not in (None, ""):
                lines.append(f"{label}: {html.escape(str(v))}")
    cost = getattr(obj, "cost", "")
    if hasattr(cost, "raw"):                    # a CharmCost, not a plain string
        cost = cost.raw or _cost_str(cost)
    if cost:
        lines.append(f"Cost: {html.escape(str(cost))}")
    parts = [f"<b>{name}</b>"]
    if lines:
        parts.append("<br>".join(f"<span style='color:#555'>{ln}</span>" for ln in lines))
    if desc:
        parts.append(f"<p style='margin-top:6px'>{desc}</p>")
    return "<br>".join(parts)


class NodeItem(QGraphicsRectItem):
    """One Charm box: name + minimum line, coloured by the node's owned/available/locked
    state. `external` (a prerequisite drawn in from another category) gets a dashed
    border. Selectable so the scene's selectionChanged drives the detail panel."""

    def __init__(self, node, pal, font):
        super().__init__()
        self.node = node
        fm = QFontMetricsF(font)
        w = min(MAX_NODE_W, max(MIN_W, fm.horizontalAdvance(node.label) + 28))
        self.setRect(0, 0, w, NODE_H)
        self.setFlags(QGraphicsItem.ItemIsSelectable)
        self.setZValue(1)
        self._pal = pal
        self._font = font
        self._label = fm.elidedText(node.label, Qt.ElideRight, w - 20)
        self._min_font = QFont(font)
        self._min_font.setPointSizeF(max(6.5, font.pointSizeF() - 1.5))

    def paint(self, painter, option, widget=None):
        state = self.node.state
        if state == "owned":
            fill, border, text = self._pal.accent, self._pal.accent_dark, "#ffffff"
        elif state == "available":
            fill, border, text = self._pal.node_bg, self._pal.accent, self._pal.ink
        else:
            fill, border, text = "#ececec", "#b8b8b8", "#8a8a8a"
        path = QPainterPath()
        path.addRoundedRect(self.rect(), 7, 7)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillPath(path, QColor(fill))
        selected = bool(option.state & QStyle.State_Selected)
        pen = QPen(QColor(border), 2 if selected else 1)
        if self.node.external:
            pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        painter.drawPath(path)
        painter.setPen(QColor(text))
        painter.setFont(self._font)
        painter.drawText(self.rect().adjusted(10, 6, -10, -22), Qt.AlignLeft, self._label)
        painter.setFont(self._min_font)
        painter.drawText(
            self.rect().adjusted(10, 28, -10, -6), Qt.AlignLeft,
            f"Ab {self.node.min_ability} · Ess {self.node.min_essence}")


class EdgeItem(QGraphicsPathItem):
    """A prerequisite edge drawn as a polyline with an arrowhead at the target.

    Straight when it clears every node box; a crossing edge gets a U detour down the
    side of the band of boxes it would pass through. Semi-transparent so overlaps
    read as lines rather than a solid blob. The arrowhead points along the last
    segment, from prerequisite to Charm — the direction the graph reads."""

    def __init__(self, points, color: str):
        super().__init__()
        self._color = QColor(color)
        self._points = points
        path = QPainterPath(QPointF(*points[0]))
        for pt in points[1:]:
            path.lineTo(QPointF(*pt))
        self.setPath(path)
        self.setZValue(0)
        pen_color = QColor(self._color)
        pen_color.setAlpha(170)
        self.setPen(QPen(pen_color, 1.2))

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        x1, y1 = self._points[-2]
        x2, y2 = self._points[-1]
        dx, dy = x2 - x1, y2 - y1
        norm = math.hypot(dx, dy)
        if norm == 0:
            return
        ux, uy = dx / norm, dy / norm
        length, half = 9.0, 4.0
        tip = QPointF(x2, y2)
        base = QPointF(x2 - ux * length, y2 - uy * length)
        px, py = -uy, ux
        p1 = base + QPointF(px * half, py * half)
        p2 = base - QPointF(px * half, py * half)
        painter.save()
        painter.setPen(Qt.NoPen)
        arrow = QColor(self._color)
        arrow.setAlpha(170)
        painter.setBrush(arrow)
        painter.drawPolygon(QPolygonF([tip, p1, p2]))
        painter.restore()


def _tree_positions(graph, width_of):
    """{id: (x_centre, y)} for a tidy-tree layout of the Charm DAG.

    Each node is centred over its children; leaves pack left-to-right by their own
    width; a subtree reserves `max(own width, children's combined width)` so a wide
    parent never overlaps the next subtree. A level wider than MAX_LEVEL_NODES
    sub-rows (Prismatic Arrangement of Creation roots eleven Charms — 6+5, each in
    its own column, next row down), bounding width without overlapping. A node with
    several prerequisites hangs off its FIRST parent (this is a tree, not a full
    DAG); the rest draw as ordinary edges. Roots form a left-to-right forest; roots
    with NO children (isolated entry Charms — nothing in the tree needs them) move to
    their own row below the forest so they do not clutter the fan."""
    primary: dict[str, str] = {}
    for p, c in graph.edges:
        primary.setdefault(c, p)
    children: dict[str, list[str]] = defaultdict(list)
    for c, p in primary.items():
        children[p].append(c)
    for subs in children.values():
        subs.sort()
    roots = [n.id for n in graph.nodes if n.id not in primary]

    def subtree_width(nid):
        subs = children[nid]
        if not subs:
            return width_of[nid]
        span = sum(subtree_width(c) for c in subs) + GAP_X * (len(subs) - 1)
        return max(width_of[nid], span)

    pos: dict[str, tuple[float, float]] = {}

    def place(nid, x_left, y):
        w = subtree_width(nid)
        subs = children[nid]
        if not subs:
            pos[nid] = (x_left + width_of[nid] / 2, y)
            return
        child_span = sum(subtree_width(c) for c in subs) + GAP_X * (len(subs) - 1)
        acc = x_left + (w - child_span) / 2
        for i, c in enumerate(subs):
            cw = subtree_width(c)
            place(c, acc, y + ROW_H + (i // MAX_LEVEL_NODES) * ROW_H)
            acc += cw + GAP_X
        pos[nid] = (x_left + w / 2, y)

    # A root is a LEAF root only when no graph edge leaves it at all — a root whose
    # graph-children chose a different primary parent still has edges to draw, so it
    # must stay in the forest. (Judging by `children` (the primary tree) instead
    # exiled such roots to the bottom row with long edges back up into the forest.)
    graph_children = {p for p, _ in graph.edges}
    tree_roots = [r for r in roots if r in graph_children]
    leaf_roots = [r for r in roots if r not in graph_children]
    # Group roots by the children they feed: fan-in trees (many entry Charms
    # converging on one form — Prismatic Arrangement) then read as clusters. The
    # shared form hangs under its first feeder, and the feeders are adjacent, so the
    # remaining feeder-edges are short instead of crossing the whole fan.
    child_of: dict[str, list[str]] = defaultdict(list)
    for p, c in graph.edges:
        child_of[p].append(c)
    tree_roots.sort(key=lambda r: (tuple(sorted(child_of[r])), r))
    x = 0.0
    for i, r in enumerate(tree_roots):
        place(r, x, 10.0 + (i // MAX_LEVEL_NODES) * ROW_H)
        x += subtree_width(r) + GAP_X
    if leaf_roots:
        leaf_y = max((pos[n][1] for n in pos), default=10.0) + ROW_H
        lx = 0.0
        for r in leaf_roots:
            pos[r] = (lx + width_of[r] / 2, leaf_y)
            lx += width_of[r] + GAP_X
    return pos


def _segment_hits_rect(bx, by, ex, ey, l, t, r, b):
    """Whether the segment (bx,by)-(ex,ey) passes through the rect — sampled along
    the segment, since the exact intersection geometry is overkill here."""
    for i in range(21):
        f = i / 20
        px = bx + (ex - bx) * f
        py = by + (ey - by) * f
        if l <= px <= r and t <= py <= b:
            return True
    return False


def _rect_entry(px, py, qx, qy, l, t, r, b):
    """The point where segment (px,py)-(qx,qy) first enters the rect, given the start
    is outside and the end is on/inside it — Liang-Barsky's entry parameter."""
    dx, dy = qx - px, qy - py
    tmin, tmax = 0.0, 1.0
    for p, q in ((-dx, px - l), (dx, r - px), (-dy, py - t), (dy, b - py)):
        if p == 0:
            continue
        t0 = q / p
        if p < 0:
            if t0 > tmin:
                tmin = t0
        elif t0 < tmax:
            tmax = t0
    if tmin > tmax:
        return None
    return (px + tmin * dx, py + tmin * dy)


def _shorten_to_box(pts, box, margin):
    """Pull the polyline's last point back from `box` so the arrowhead sits clear.

    The tip is offset from the boundary ENTRY along the entry edge's OUTWARD NORMAL,
    not along the edge direction — a shallow diagonal pulling back along its own
    direction keeps the arrow at the box's height and leaves it half under the node.
    With `margin` > the arrow's half-width, the whole triangle is guaranteed outside
    (tip and base are margin and margin+L·|n·u| out along the normal)."""
    x1, y1 = pts[-2]
    x2, y2 = pts[-1]
    entry = _rect_entry(x1, y1, x2, y2, *box)
    if entry is None:
        return pts
    l, t, r, b = box
    ex, ey = entry
    if abs(ey - t) < 1e-6:                      # entered the top edge
        nx, ny = 0.0, -1.0
    elif abs(ey - b) < 1e-6:                    # the bottom edge
        nx, ny = 0.0, 1.0
    elif abs(ex - l) < 1e-6:                    # the left edge
        nx, ny = -1.0, 0.0
    else:                                       # the right edge
        nx, ny = 1.0, 0.0
    return pts[:-1] + [(ex + nx * margin, ey + ny * margin)]


def _route_edge(start, end, boxes, rails, target):
    """Polyline from `start` to `end` avoiding `boxes` (node rects, endpoints
    excluded) and `rails` (the horizontal runs already-routed detours ride — a new
    detour must not ride one, so parallel re-routes offset instead of overlapping).
    Straight when it clears everything; otherwise a U down the side of the band of
    boxes the straight line would cross (trying left, then right, then rail offsets
    up/down). The last point is pulled back from the child (`target`) so the arrowhead
    sits clear. Returns the straight line when no clean detour exists."""
    bx, by = start.x(), start.y()
    cx, cy = end.x(), end.y()

    def clear(pts):
        for i in range(len(pts) - 1):
            x1, y1 = pts[i]
            x2, y2 = pts[i + 1]
            for l, t, r, b in boxes:
                if _segment_hits_rect(x1, y1, x2, y2, l, t, r, b):
                    return False
        return True

    def rails_free(pts):
        for i in range(len(pts) - 1):
            x1, y1 = pts[i]
            x2, y2 = pts[i + 1]
            if y1 != y2:                 # only the horizontal runs matter
                continue
            for ry, rx1, rx2 in rails:
                if abs(y1 - ry) < 5 and min(x1, x2) < rx2 and max(x1, x2) > rx1:
                    return False
        return True

    def claim(pts):
        for i in range(len(pts) - 1):
            x1, y1 = pts[i]
            x2, y2 = pts[i + 1]
            if y1 != y2:
                continue
            rails.append((y1, min(x1, x2), max(x1, x2)))

    straight = [(bx, by), (cx, cy)]
    if clear(straight):
        return _shorten_to_box(straight, target, 8)
    hit = [box for box in boxes if _segment_hits_rect(bx, by, cx, cy, *box)]
    l = min(box[0] for box in hit)
    r = max(box[2] for box in hit)
    t = min(box[1] for box in hit)
    b = max(box[3] for box in hit)
    for sx in (l - 14, r + 14):
        for dy in (0, -16, 16, -32, 32):
            y_top, y_bot = t - 14 + dy, b + 14 + dy
            pts = [(bx, by), (bx, y_top), (sx, y_top), (sx, y_bot), (cx, y_bot), (cx, cy)]
            if clear(pts) and rails_free(pts):
                claim(pts)
                return _shorten_to_box(pts, target, 8)
    return _shorten_to_box(straight, target, 8)


def populate(scene, graph, pal, font):
    """Add node and edge items for `graph` to `scene`; returns {id: NodeItem}.

    Nodes sit at `_tree_positions` (each centred over its children, leaves packed by
    their own width). An edge runs from every in-graph prerequisite's bottom-centre
    to the node's top-centre, routed around any node box its straight path would
    cross."""
    items = {n.id: NodeItem(n, pal, font) for n in graph.nodes}
    width_of = {nid: items[nid].rect().width() for nid in items}
    height_of = {nid: items[nid].rect().height() for nid in items}
    pos = _tree_positions(graph, width_of)
    boxes = {nid: (pos[nid][0] - width_of[nid] / 2, pos[nid][1],
                   pos[nid][0] + width_of[nid] / 2, pos[nid][1] + height_of[nid])
             for nid in pos}
    for nid, (x, y) in pos.items():
        item = items[nid]
        item.setPos(x - item.rect().width() / 2, y)
        scene.addItem(item)
    rails: list[tuple[float, float, float]] = []
    for p, c in graph.edges:
        if p not in items or c not in items:
            continue
        s, e = items[p], items[c]
        start = s.pos() + QPointF(s.rect().width() / 2, s.rect().height())
        end = e.pos() + QPointF(e.rect().width() / 2, 0)
        obstacles = [box for nid, box in boxes.items() if nid != p and nid != c]
        scene.addItem(EdgeItem(_route_edge(start, end, obstacles, rails, boxes[c]),
                               pal.graph_border))
    return items


class CharmTreeView(QGraphicsView):
    """One category's Charm tree: repopulates its scene from build_charm_graph.

    `graph` is the last rendered CharmGraph, for the detail panel and tests.
    `category_combo` is the owning tab's dropdown, read back by the window."""

    def __init__(self, ruleset, character):
        super().__init__()
        self._ruleset = ruleset
        self._character = character
        self.graph = None
        self.category_combo = None
        self._pending_fit = False
        self._fit_attempts = 0
        self._just_zoomed = False
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setBackgroundBrush(QColor("#ffffff"))

    def show_tree(self, category, splat):
        graph = build_charm_graph(self._ruleset, self._character, category, splat)
        self.graph = graph
        self._scene.clear()
        if not graph.nodes:
            self._pending_fit = False
            return
        font = QFont(self.font())
        font.setPointSizeF(9.5)
        populate(self._scene, graph, theme.palette(splat or self._character.exalt_type), font)
        self._scene.setSceneRect(self._scene.itemsBoundingRect().adjusted(-40, -40, 40, 40))
        # Fit to the minimum zoom that shows every node. A freshly built tab's
        # viewport starts 0×0 AND grows in stages during layout, so a single eager
        # fitInView can run against a temporarily-small size and leave the tree
        # zoomed out (the new-splat case). Defer the fit and keep re-fitting until
        # the viewport size converges, then leave the transform to the user.
        self._pending_fit = True
        self._fit_attempts = 0
        QTimer.singleShot(0, self._fit_attempt)

    def _fit_attempt(self):
        if not self._pending_fit:
            return
        self._fit_attempts += 1
        try:
            sized = self.viewport().width() > 0 and self.viewport().height() > 0
        except RuntimeError:
            self._pending_fit = False                    # view destroyed — stop
            return
        if sized:
            self.fitInView(self._scene.sceneRect(), Qt.KeepAspectRatio)
            # The layout settles over a few event cycles; re-fit a bounded few times
            # so the transform converges on the final viewport size.
            if self._fit_attempts < 6:
                QTimer.singleShot(0, self._fit_attempt)
            else:
                self._pending_fit = False
        else:
            if self._fit_attempts >= 60:                 # never got a size — give up
                self._pending_fit = False
            else:
                QTimer.singleShot(0, self._fit_attempt)  # still no size — keep waiting

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Re-fit when the view resizes (window resize, splitter drag), so the tree
        # always fills the current view. But a wheel-zoom makes scrollbars appear,
        # which shrinks the VIEW for a few frames and fires resize events — re-fitting
        # those would undo the zoom (that is how zooming came to be blocked), so skip
        # resizes while the user is wheeling. The deferred fit handles initial sizing.
        if self._just_zoomed or event.size() == event.oldSize():
            return
        if self.graph is not None and self._scene.items():
            self.fitInView(self._scene.sceneRect(), Qt.KeepAspectRatio)

    def _clear_zoom_flag(self):
        self._just_zoomed = False

    def wheelEvent(self, event):
        # Delta-proportional zoom: a full mouse notch (Δ120) scales ~1.2×; a
        # trackpad's small smooth-scroll deltas scale proportionally less, so the
        # same physical scroll distance zooms the same on any device. (A fixed
        # per-event factor made trackpads zoom wildly faster than a mouse.)
        # Wayland touchpads deliver only pixelDelta — fall back to it, and treat a
        # zero delta as a no-op rather than as "scroll down".
        delta = event.angleDelta().y()
        if delta == 0:
            delta = event.pixelDelta().y()
        if delta == 0:
            event.accept()
            return
        # Zooming makes scrollbars appear, which shrinks the view and fires resize
        # events for a few frames; re-fitting those would undo the zoom. Flag it so
        # resizeEvent ignores resizes until the wheel interaction settles.
        self._just_zoomed = True
        QTimer.singleShot(250, self._clear_zoom_flag)
        factor = 1.0015 ** delta
        if 0.05 <= self.transform().m11() * factor <= 10:
            self.scale(factor, factor)
        event.accept()


class CappedCombo(QComboBox):
    """QComboBox whose popup is capped at `max_rows` rows.

    `setMaxVisibleItems` is ignored for popup HEIGHT on this Qt build (measured: the
    popup sizes to the whole screen even with the property set and the view's maximum
    height set), so the cap is applied to the popup window itself once it opens."""

    def __init__(self, max_rows: int = 15, parent=None):
        super().__init__(parent)
        self._max_rows = max_rows

    def showPopup(self):
        super().showPopup()
        popup = self.view().window()
        row_h = self.view().sizeHintForRow(0)
        if popup is not None and popup is not self.window() and row_h > 0:
            popup.setMaximumHeight(int(row_h * self._max_rows + 8))


class TreeSpikeWindow(QMainWindow):
    """Splat dropdown over a tab bar mirroring the app's picker groups: the three tree
    groups (Charms / Martial Arts / Arcanoi) and two panels (Spells, Thaumaturgy).

    Tabs are built per splat and only when that splat has content in the group — a
    Solar gets Charms/Martial Arts/Spells/Thaumaturgy and no Arcanoi; a Ghost gets
    Arcanoi/Thaumaturgy and no Charms. Each tree tab owns its category dropdown and
    tree view; a shared detail panel shows the selection in whichever is active.
    `_tree_views` maps group key to view, for the tests."""

    def __init__(self, ruleset, character):
        super().__init__()
        self._ruleset, self._character = ruleset, character
        self.setWindowTitle("Charm-tree spike — PySide6/QGraphicsView")
        self.resize(1180, 720)

        self.detail = QTextBrowser()
        self.detail.setMinimumWidth(300)
        self.count_label = QLabel("")
        self._tree_views: dict[str, CharmTreeView] = {}

        self.splat_combo = CappedCombo(15)
        self.splat_combo.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self.splat_combo.blockSignals(True)
        self.splat_combo.addItems(splat_labels(ruleset, character))
        self.splat_combo.blockSignals(False)
        self.splat_combo.currentTextChanged.connect(self._rebuild_tabs)

        bar = QHBoxLayout()
        bar.addWidget(QLabel("Splat:"))
        bar.addWidget(self.splat_combo)
        bar.addStretch()
        bar.addWidget(self.count_label)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.currentChanged.connect(self._tab_changed)

        split = QSplitter()
        split.addWidget(self.tabs)
        split.addWidget(self.detail)
        split.setSizes([880, 300])

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addLayout(bar)
        layout.addWidget(split, 1)
        self.setCentralWidget(central)

        self._rebuild_tabs()

    def _current_splat(self):
        return self.splat_combo.currentText()

    def _page_char(self):
        """A fresh character of the SELECTED splat.

        The spike browses each splat's own catalogue, so the Splat dropdown must
        show native pages, not the Eclipse-foreign pages of the window's base
        character (which `charm_on_splat_page` gates behind foreign_charms_open —
        that is why a Solar-base window showed no Ghost Arcanoi or Lunar Charms)."""
        return Character(id="char.new", exalt_type=self._current_splat())

    def _tree_page(self, group):
        """A tree tab: category dropdown filtered to `group`, over a CharmTreeView."""
        page = QWidget()
        combo = CappedCombo(15)
        combo.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        combo.setMaximumWidth(300)
        view = CharmTreeView(self._ruleset, self._page_char())
        view._scene.selectionChanged.connect(lambda: self._tree_detail(view))
        view.category_combo = combo
        self._tree_views[group] = view
        trees = trees_for(self._ruleset, self._page_char(), self._current_splat(), group)
        combo.blockSignals(True)
        for key, count in trees:
            label = (_style_label(key, self._ruleset).removesuffix(" Style")
                     if key.startswith("martial_arts:") else key.replace("_", " ").title())
            combo.addItem(f"{label} ({count})", key)
        combo.blockSignals(False)
        combo.currentIndexChanged.connect(lambda _i, v=view: self._load_tree(v))

        lay = QVBoxLayout(page)
        row = QHBoxLayout()
        row.addWidget(QLabel("Tree:"))
        row.addWidget(combo)
        row.addStretch()
        lay.addLayout(row)
        lay.addWidget(view, 1)
        # The first added item is already current (addItem selects it), so
        # setCurrentIndex(0) would not fire currentIndexChanged — load explicitly.
        if combo.count():
            self._load_tree(view)
        return page

    def _load_tree(self, view):
        view.show_tree(view.category_combo.currentData() or "", self._current_splat())

    def _tree_detail(self, view):
        # A scene emits selectionChanged as it is destroyed (window teardown); by then
        # its C++ object is gone, so touching it raises RuntimeError — ignore it.
        try:
            sel = [i for i in view._scene.selectedItems() if isinstance(i, NodeItem)]
        except RuntimeError:
            return
        if not sel:
            return
        node = sel[0].node
        detail = build_charm_detail(self._ruleset, view._character, node.id)
        html_text = _detail_html(detail) if detail else f"<b>{node.label}</b>"
        state = {"owned": "Owned", "available": "Available"}.get(node.state, "Locked")
        self.detail.setHtml(f"<span style='color:#888'>{state}</span><br>" + html_text)

    def _spells_page(self, circles):
        """A panel tab: circle dropdown over a spell-name list."""
        page = QWidget()
        combo = CappedCombo(15)
        combo.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        combo.addItems(circles)
        entries = QListWidget()
        combo.currentTextChanged.connect(
            lambda circle: self._fill_list(entries, spells_in_circle(self._ruleset, circle)))
        entries.currentTextChanged.connect(lambda *_, lw=entries: self._panel_detail(lw))
        lay = QVBoxLayout(page)
        row = QHBoxLayout()
        row.addWidget(QLabel("Circle:"))
        row.addWidget(combo)
        row.addStretch()
        lay.addLayout(row)
        lay.addWidget(entries, 1)
        # addItem already made the first circle current before the connect; load it.
        if circles:
            self._fill_list(entries, spells_in_circle(self._ruleset, circles[0]))
        return page

    def _thaum_page(self):
        """A panel tab: inner Arts / Sciences / Rituals / Formulas sub-tabs."""
        page = QWidget()
        inner = QTabWidget()
        inner.setDocumentMode(True)
        for label, collection in (
                ("Arts", self._ruleset.thaum_arts),
                ("Sciences", self._ruleset.thaum_sciences),
                ("Rituals", self._ruleset.thaum_rituals),
                ("Formulas", self._ruleset.thaum_formulas)):
            entries = QListWidget()
            for entry in collection.values():
                item = QListWidgetItem(entry.name)
                item.setData(Qt.UserRole, entry)
                entries.addItem(item)
            entries.currentTextChanged.connect(lambda *_, lw=entries: self._panel_detail(lw))
            inner.addTab(entries, label)
        lay = QVBoxLayout(page)
        lay.addWidget(inner)
        return page

    def _fill_list(self, entries, items):
        entries.clear()
        for name, obj in items:
            item = QListWidgetItem(name)
            item.setData(Qt.UserRole, obj)
            entries.addItem(item)

    def _panel_detail(self, entries):
        item = entries.currentItem()
        if item is None:
            return
        obj = item.data(Qt.UserRole)
        self.detail.setHtml(_detail_html(obj) if obj is not None else f"<b>{item.text()}</b>")

    def _rebuild_tabs(self):
        """Rebuild the tab bar for the current splat: a tree tab per non-empty group,
        then Spells (if any circle is reachable), then Thaumaturgy."""
        self._tree_views.clear()
        self.tabs.clear()
        for group, label in (("abilities", "Charms"), ("styles", "Martial Arts"),
                             ("arcanoi", "Arcanoi")):
            if trees_for(self._ruleset, self._page_char(), self._current_splat(), group):
                self.tabs.addTab(self._tree_page(group), label)
        circles = spell_circles(self._ruleset, self._page_char())
        if circles:
            self.tabs.addTab(self._spells_page(circles), "Spells")
        self.tabs.addTab(self._thaum_page(), "Thaumaturgy")
        self.detail.setText("Select an entry to see details.")
        self._tab_changed()

    def _tab_changed(self, *_):
        view = (self.tabs.currentWidget().findChild(CharmTreeView)
                if self.tabs.currentWidget() else None)
        if view is not None and view.graph:
            self.count_label.setText(f"{len(view.graph.nodes)} nodes · "
                                     f"{len(view.graph.edges)} edges")
        else:
            self.count_label.setText("")


def main():
    app = QApplication(sys.argv)
    ruleset, character = load_world()
    win = TreeSpikeWindow(ruleset, character)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
