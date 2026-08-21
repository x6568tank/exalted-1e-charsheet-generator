"""exalted_builder/qt/charms.py — the Charms tab: the charm catalogue as Qt trees.

Input: a RuleSet and a Character (from the shared context). Output: a tab widget of
tree tabs (Charms / Martial Arts / Arcanoi) and list panels (Spells, Thaumaturgy)
over a shared detail panel. Mechanism: `build_charm_graph` feeds a QGraphicsScene of
rounded-rect node items in a tidy-tree layout (each node centred over its children,
wide levels sub-rowed), with node/rail-aware edge routing, pan via ScrollHandDrag and
delta-proportional wheel zoom; group membership mirrors picker._group_of; node colours
come from ui.theme.palette. Rebuilt on reload() for the character in ctx, so loading a
different splat swaps the whole group set.

This is the port of spikes/qt_tree/ (human-approved 2026-08-20); the layout, routing
and view classes are that spike's tested core, carried over. Browse-and-inspect only
in this milestone — buying and the splat extras (Form Library, Paths, Vat Refit,
Elemental Powers) are the picker port's later half.
"""

from __future__ import annotations

import html
import math
from collections import defaultdict

from PySide6.QtCore import QPointF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import (
    QComboBox, QFrame, QGraphicsItem, QGraphicsPathItem, QGraphicsRectItem,
    QGraphicsScene, QGraphicsView, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QPushButton, QScrollArea, QSizePolicy, QSpinBox, QSplitter,
    QStyle, QTabWidget, QTextBrowser, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
    QWidget,
)

from exalted_builder.engine import advancement, costs, refit, thaum_actions, validate
from exalted_builder.engine import paths as engine_paths
from exalted_builder.models.character import AnimalForm, PathRating
from exalted_builder.models.rules import Orientation
from exalted_builder.ui import theme

from .theme import CARD, MUTED, TREE, accent as accent_light
from exalted_builder.ui.view import (CIRCLE_DISPLAY_ORDER, _cost_str, _style_label,
                                     build_charm_detail, build_charm_graph,
                                     build_elemental_power_picker,
                                     build_sheet_view, build_spell_picker,
                                     build_thaum_picker, charm_on_splat_page,
                                     charm_slot_budget, virtue_split)

ROW_H = 160            # vertical space between tree levels
GAP_X = 40             # horizontal gap between sibling subtrees
NODE_H = 56
MIN_W = 150            # smallest node box
MAX_NODE_W = 260       # largest node box; longer labels elide with an ellipsis
MAX_LEVEL_NODES = 6    # cap nodes in one tree-level row; wider levels sub-row


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


def _detail_html(obj, currency: str = ""):
    """Rich-text detail panel for a CharmDetail, Spell, or Thaumaturgy entry: name,
    the trait lines (requirement / prerequisites, cost, circle, …), and the
    description. A Thaumaturgy row's `price` rides as a Cost line — most printed
    specialties have no description, so the price is what fills the panel."""
    name = html.escape(getattr(obj, "name", ""))
    desc = html.escape(getattr(obj, "description", ""))
    lines = []
    price = getattr(obj, "price", None)
    if price is not None and currency:
        lines.append(f"Cost: {price} {currency}")
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
        # Light grey on the dark detail panel — the web-page mid-grey is invisible.
        parts.append("<br>".join(f"<span style='color:#b8b6b2'>{ln}</span>" for ln in lines))
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
        self.setBackgroundBrush(QColor(TREE))

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

    ⚠ `setMaxVisibleItems` is ignored for popup HEIGHT on this Qt build (measured:
    the popup sizes to the whole screen even with the property set and the view's
    maximum height set), so the cap is applied to the popup window itself once it
    opens."""

    def __init__(self, max_rows: int = 15, parent=None):
        super().__init__(parent)
        self._max_rows = max_rows

    def showPopup(self):
        super().showPopup()
        popup = self.view().window()
        row_h = self.view().sizeHintForRow(0)
        if popup is not None and popup is not self.window() and row_h > 0:
            popup.setMaximumHeight(int(row_h * self._max_rows + 8))


class CharmsPage(QWidget):
    """The Charms tab: per-splat picker groups as tree tabs (Charms / Martial Arts /
    Arcanoi) and list panels (Spells, Thaumaturgy), over a shared detail panel.

    Tabs are built per character and only when that splat has content in the group — a
    Solar gets Charms/Martial Arts/Spells/Thaumaturgy and no Arcanoi; a Ghost gets
    Arcanoi/Thaumaturgy and no Charms. Each tree tab owns its category dropdown and
    tree view; the shared detail panel shows the selection in whichever is active.
    `reload()` rebuilds the whole tab set for the character currently in ctx."""

    def __init__(self, ruleset, ctx, *, notify=None, parent=None):
        super().__init__(parent)
        self._ruleset = ruleset
        self._ctx = ctx
        self._notify = notify or (lambda text, kind="info": None)
        self._selected_node: str | None = None
        self._selected_spell: str | None = None
        self._selected_thaum: tuple | None = None
        self._selected_elemental: str | None = None
        self.detail = QTextBrowser()
        self.detail.setMinimumWidth(300)
        self.count_label = QLabel("")
        self.readout = QLabel("")
        self.readout.setWordWrap(True)
        self.readout.setContentsMargins(8, 6, 8, 6)
        self.action_btn = QPushButton("Select an entry…")
        self.action_btn.setEnabled(False)
        self.action_btn.clicked.connect(self._on_action)
        self._tree_views: dict[str, CharmTreeView] = {}

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.currentChanged.connect(self._tab_changed)

        detail_panel = QWidget()
        dp = QVBoxLayout(detail_panel)
        dp.setContentsMargins(0, 0, 0, 0)
        dp.setSpacing(4)
        act_row = QHBoxLayout()
        act_row.addWidget(self.action_btn, 1)
        # The regional version of a ritual or formula (p.124) — enabled only when a
        # ritual/formula is selected for its first purchase.
        self._orientation_combo = QComboBox()
        for o in Orientation:
            self._orientation_combo.addItem(o.value, o)
        self._orientation_combo.setVisible(False)   # only a ritual/formula buy shows it
        self._orientation_combo.setToolTip("Regional version of a ritual or formula")
        act_row.addWidget(self._orientation_combo)
        dp.addLayout(act_row)
        dp.addWidget(self.detail, 1)

        split = QSplitter()
        split.addWidget(self.tabs)
        split.addWidget(detail_panel)
        split.setSizes([880, 300])

        bar = QHBoxLayout()
        bar.addWidget(self.readout, 1)
        bar.addWidget(self.count_label)

        layout = QVBoxLayout(self)
        layout.addLayout(bar)
        layout.addWidget(split, 1)
        self.reload()

    def _char(self):
        return self._ctx["char"]

    def _clear_lay(self, lay: QVBoxLayout) -> None:
        """Remove every widget/layout from `lay` and detach it NOW.

        ⚠ `deleteLater()` alone is deferred to the event loop: a rebuild runs
        synchronously right after a change, and a build whose children are merely
        pending-delete keeps painting at stale geometry on top of the next build.
        `setParent(None)` detaches it from rendering immediately; `deleteLater()`
        still frees the C++ object. (Same pattern as the Edit tab's `_clear_lay`.)"""
        while lay.count():
            item = lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.hide()
                w.setParent(None)
                w.deleteLater()
            elif item.layout() is not None:
                self._clear_lay(item.layout())

    # ------------------------------------------------------------------ #
    # buying (the picker's toggle, ported) — the one thing the spike left out
    # ------------------------------------------------------------------ #

    def _update_action(self) -> None:
        """The Learn/Remove button follows the selection: a Charm tree node, a spell
        row, or a Thaumaturgy entry. Disabled with no selection; 'Remove' for an
        owned pick, 'Learn' otherwise (a Science reads 'Raise'). The price rides on
        the Learn side — a chargen Charm pick is free, an XP buy and every
        Thaumaturgy buy show their cost."""
        char = self._char()
        self._orientation_combo.setVisible(False)      # a ritual/formula buy re-shows it
        if self._selected_node is not None:
            cid = self._selected_node
            charm = self._ruleset.charms.get(cid)
            if charm is None:
                self.action_btn.setEnabled(False)
                self.action_btn.setText("Select an entry…")
                return
            owned = cid in char.charms
            label = f"Remove {charm.name}" if owned else f"Learn {charm.name}"
            if not owned and char.chargen_locked:
                label += f" — {costs.charm_cost(self._ruleset, char, charm)} XP"
            self.action_btn.setText(label)
            self.action_btn.setEnabled(True)
            return
        if self._selected_spell is not None:
            sid = self._selected_spell
            spell = self._ruleset.spells.get(sid)
            if spell is None:
                self.action_btn.setEnabled(False)
                self.action_btn.setText("Select an entry…")
                return
            owned = sid in char.spells
            label = f"Remove {spell.name}" if owned else f"Learn {spell.name}"
            if not owned and char.chargen_locked:
                label += f" — {costs.spell_cost(self._ruleset, char, spell)} XP"
            self.action_btn.setText(label)
            self.action_btn.setEnabled(True)
            return
        if self._selected_thaum is not None:
            currency = build_thaum_picker(self._ruleset, char).currency
            kind = self._selected_thaum[0]
            if kind == "science":
                row = self._selected_thaum[1]
                if row.can_raise:
                    self.action_btn.setText(
                        f"Raise {row.name} — {row.next_price} {currency} "
                        f"({row.rating}/{row.max_rating})")
                else:
                    self.action_btn.setText(f"{row.name} at max")
                self.action_btn.setEnabled(bool(row.can_raise))
            elif kind == "art_specialty":
                spec = self._selected_thaum[2]
                label = f"Drop {spec.name}" if spec.owned else \
                    f"Learn {spec.name} — {spec.price} {currency}"
                self.action_btn.setText(label)
                self.action_btn.setEnabled(True)
            else:
                row = self._selected_thaum[1]
                label = f"Drop {row.name}" if row.owned else \
                    f"Learn {row.name} — {row.price} {currency}"
                self.action_btn.setText(label)
                self.action_btn.setEnabled(True)
                # The orientation matters only for the FIRST purchase — an owned
                # entry is dropped, not re-learned.
                self._orientation_combo.setVisible(not row.owned)
                self._orientation_combo.setEnabled(not row.owned)
            return
        if self._selected_elemental is not None:
            # Owned-ness is read live off the character, never off a stored row — a
            # rebuilt list would leave the row's owned flag stale.
            char = self._char()
            row = next((r for r in build_elemental_power_picker(self._ruleset, char).powers
                        if r.id == self._selected_elemental), None)
            if row is None:
                self.action_btn.setEnabled(False)
                self.action_btn.setText("Select an entry…")
                return
            if self._selected_elemental in char.elemental_powers:
                if char.chargen_locked:
                    # A known power is not droppable in play — the undo lives on the
                    # Edit tab, matching the picker's disabled check-icon.
                    self.action_btn.setEnabled(False)
                    self.action_btn.setText(f"{row.name} — known")
                    self.action_btn.setToolTip(
                        "Already known — undo the purchase on the Edit tab.")
                else:
                    self.action_btn.setText(f"Remove {row.name}")
                    self.action_btn.setEnabled(True)
                    self.action_btn.setToolTip("")
                return
            if char.chargen_locked:
                self.action_btn.setText(f"Learn {row.name} — {row.price} XP")
                self.action_btn.setEnabled(True)
                self.action_btn.setToolTip("")
            else:
                self.action_btn.setText(f"Learn {row.name}")
                self.action_btn.setEnabled(row.available)
                self.action_btn.setToolTip(row.reason if not row.available else "")
            return
        self.action_btn.setEnabled(False)
        self.action_btn.setText("Select an entry…")

    def _on_action(self) -> None:
        if self._selected_node is not None:
            self._toggle_charm(self._selected_node)
        elif self._selected_spell is not None:
            self._toggle_spell(self._selected_spell)
        elif self._selected_thaum is not None:
            self._toggle_thaum(*self._selected_thaum)
        elif self._selected_elemental is not None:
            self._toggle_elemental(self._selected_elemental)

    def _toggle_thaum(self, kind: str, *rest) -> None:
        """Buy/drop a Thaumaturgy entry via engine.thaum_actions — Arts and
        Rituals/Formulas toggle, a Science raises one dot, and an Art's specialty
        toggles under its parent Art. The action functions own the state change and
        raise on refusal; this only surfaces the outcome."""
        ruleset, char = self._ruleset, self._char()
        try:
            if kind == "art":
                row = rest[0]
                msg = (thaum_actions.drop_thaum_art(ruleset, char, row.id) if row.owned
                       else thaum_actions.buy_thaum_art(ruleset, char, row.id))
            elif kind == "art_specialty":
                art, spec = rest
                msg = (thaum_actions.drop_thaum_specialty(char, art.id, spec.name)
                       if spec.owned
                       else thaum_actions.buy_thaum_specialty(
                           ruleset, char, art.id, spec.name))
            elif kind == "science":
                row = rest[0]
                msg = thaum_actions.raise_thaum_science(ruleset, char, row.id)
            elif rest[0].owned:
                row = rest[0]
                msg = thaum_actions.drop_thaum_entry(char, kind, row.key)
            else:
                row = rest[0]
                # PySide6 stores the enum's str value, not the member — reconstruct.
                raw = self._orientation_combo.currentData() or Orientation.REALM.value
                msg = thaum_actions.buy_thaum_entry(
                    ruleset, char, kind, row.key, Orientation(raw))
        except advancement.AdvancementError as ex:
            self._notify(str(ex), "warning")
            return
        self._notify(msg, "info")
        self._refresh_current_tree()

    def _toggle_charm(self, charm_id: str) -> None:
        """The web picker's toggle, ported: post-lock an XP purchase via
        advancement.learn_charm (a known Charm is not droppable — undo on the Edit
        tab); pre-lock an append/remove against the chargen budget."""
        ruleset, char = self._ruleset, self._char()
        charm = ruleset.charms.get(charm_id)
        if charm is None:
            return
        if char.chargen_locked:
            if charm_id in char.charms:
                self._notify(f"{charm.name} is already known — undo the purchase on "
                             "the Edit tab to give it back.", "info")
                return
            cost = costs.charm_cost(ruleset, char, charm)
            try:
                advancement.learn_charm(ruleset, char, charm_id)
            except advancement.AdvancementError as ex:
                self._notify(str(ex), "warning")
                return
            self._notify(f"Learned {charm.name} — {cost} XP", "info")
        elif charm_id in char.charms:
            blockers = validate.charms_depending_on(ruleset, char, charm_id)
            if blockers:
                self._notify(f"{charm.name}: can't remove — needed by "
                             f"{', '.join(blockers)}", "warning")
                return
            char.charms.remove(charm_id)
            self._notify(f"Removed {charm.name}", "info")
        else:
            if not validate.meets_charm_requirements(ruleset, char, charm):
                self._notify(f"{charm.name}: prerequisites not met", "warning")
                return
            cap = validate._repeatable_purchase_cap(charm, char)
            if cap and char.charms.count(charm_id) >= cap:
                self._notify(f"{charm.name}: already bought {cap} times — its maximum.",
                             "warning")
                return
            char.charms.append(charm_id)
            self._notify(f"Learned {charm.name}", "info")
        self._refresh_current_tree()

    def _toggle_spell(self, spell_id: str) -> None:
        """The web picker's toggle_spell, ported — same chargen/XP split."""
        ruleset, char = self._ruleset, self._char()
        spell = ruleset.spells.get(spell_id)
        if spell is None:
            return
        if char.chargen_locked:
            if spell_id in char.spells:
                self._notify(f"{spell.name} is already known — undo the purchase on "
                             "the Edit tab to give it back.", "info")
                return
            cost = costs.spell_cost(ruleset, char, spell)
            try:
                advancement.learn_spell(ruleset, char, spell_id)
            except advancement.AdvancementError as ex:
                self._notify(str(ex), "warning")
                return
            self._notify(f"Learned {spell.name} — {cost} XP", "info")
        elif spell_id in char.spells:
            char.spells.remove(spell_id)
            self._notify(f"Dropped {spell.name}", "info")
        else:
            if not validate.meets_spell_requirements(ruleset, char, spell):
                self._notify(f"{spell.name}: not available", "warning")
                return
            char.spells.append(spell_id)
            self._notify(f"Learned {spell.name}", "info")
        self._refresh_current_tree()

    def _refresh_current_tree(self) -> None:
        """Re-render the active tree so the owned/available state reflects the change
        (build_charm_graph reads the character's holdings), refresh the budget readout,
        and re-find a selected Thaumaturgy entry so its owned state flips the button."""
        view = self.tabs.currentWidget().findChild(CharmTreeView)
        if view is not None and view.category_combo is not None:
            view.show_tree(view.category_combo.currentData() or "", self._char().exalt_type)
            self._tab_changed()
        if self._selected_thaum is not None:
            self._refresh_thaum_selection()
        self._update_readout()

    def _refresh_thaum_selection(self) -> None:
        """Re-find the selected Thaumaturgy entry in a fresh picker. The row we hold
        was built before the buy/drop, so its owned flag is stale and the button would
        stay on "Learn" — the same entry in the fresh picker has the new state."""
        picker = build_thaum_picker(self._ruleset, self._char())
        kind = self._selected_thaum[0]
        if kind == "art":
            fresh = next((a for a in picker.arts if a.id == self._selected_thaum[1].id), None)
            self._selected_thaum = ("art", fresh) if fresh else None
        elif kind == "art_specialty":
            art = next((a for a in picker.arts if a.id == self._selected_thaum[1].id), None)
            spec = next((s for s in art.specialties
                         if s.name == self._selected_thaum[2].name), None) if art else None
            self._selected_thaum = ("art_specialty", art, spec) if art and spec else None
        elif kind == "science":
            fresh = next((s for s in picker.sciences
                          if s.id == self._selected_thaum[1].id), None)
            self._selected_thaum = ("science", fresh) if fresh else None
        else:
            rows = picker.rituals if kind == "ritual" else picker.formulas
            fresh = next((r for r in rows if r.key == self._selected_thaum[1].key), None)
            self._selected_thaum = (kind, fresh) if fresh else None
        self._update_action()

    def _update_readout(self) -> None:
        """The budget line: in play it is XP, in chargen the Charm pick count and the
        validation verdict — so buying Charms here shows when the budget breaks, the
        way the Edit tab's side column does for traits."""
        ruleset, char = self._ruleset, self._char()
        if char.chargen_locked:
            available = advancement.xp_available(char)
            self.readout.setText(f"{available} XP available · earned {char.xp_earned} · "
                                 f"spent {advancement.xp_spent(char)}")
            self.readout.setStyleSheet(
                f"font-weight:600; color:{'#15803d' if available >= 0 else '#b91c1c'};")
            return
        view = build_sheet_view(ruleset, char)
        bp = next((i.message for i in view.issues if i.code == "bonus-points"), "")
        errors = [i for i in view.issues if i.severity == "error"]
        status = "✓ Legal" if not errors else f"✗ {len(errors)} error(s)"
        slots = charm_slot_budget(ruleset, char)
        if slots is not None:
            over = slots.over_slots or slots.over_general
            picks = (f"Slots: {slots.installed}/{slots.general + slots.dedicated} used "
                     f"(G {slots.general} · D {slots.dedicated})")
        else:
            noun = ruleset.exalt_for(char.exalt_type).charm_noun
            picks = (f"{noun}: {validate.charm_pick_count(ruleset, char)} · "
                     f"Spells: {len(char.spells)}")
        parts = [picks, status]
        if bp:
            parts.append(bp)
        self.readout.setText(" · ".join(parts))
        self.readout.setStyleSheet("color:#6b7280;")

    def _tree_page(self, group):
        """A tree tab: category dropdown filtered to `group`, over a CharmTreeView."""
        char = self._char()
        page = QWidget()
        combo = CappedCombo(15)
        combo.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        combo.setMaximumWidth(300)
        view = CharmTreeView(self._ruleset, char)
        view._scene.selectionChanged.connect(lambda: self._tree_detail(view))
        view.category_combo = combo
        self._tree_views[group] = view
        trees = trees_for(self._ruleset, char, char.exalt_type, group)
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
        view.show_tree(view.category_combo.currentData() or "", self._char().exalt_type)

    def _tree_detail(self, view):
        # A scene emits selectionChanged as it is destroyed (window teardown); by then
        # its C++ object is gone, so touching it raises RuntimeError — ignore it.
        try:
            sel = [i for i in view._scene.selectedItems() if isinstance(i, NodeItem)]
        except RuntimeError:
            return
        if not sel:
            self._selected_node = None
            self._selected_spell = None
            self._selected_thaum = None
            self._selected_elemental = None
            self._update_action()
            return
        node = sel[0].node
        self._selected_node = node.id
        self._selected_spell = None
        self._selected_thaum = None
        self._selected_elemental = None
        detail = build_charm_detail(self._ruleset, view._character, node.id)
        html_text = _detail_html(detail) if detail else f"<b>{node.label}</b>"
        state = {"owned": "Owned", "available": "Available"}.get(node.state, "Locked")
        self.detail.setHtml(f"<span style='color:#9a9894'>{state}</span><br>" + html_text)
        self._update_action()

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
        """A panel tab: inner Arts / Sciences / Rituals / Formulas sub-tabs, built
        from build_thaum_picker's rows so each entry carries its owned/price state
        and the action button can offer to learn it. Arts show their specialties
        grouped under each Art as an expandable tree — a specialty is bought from
        under its Art, the way the web app nests it."""
        page = QWidget()
        inner = QTabWidget()
        inner.setDocumentMode(True)
        picker = build_thaum_picker(self._ruleset, self._char())
        arts_tree = QTreeWidget()
        arts_tree.setHeaderHidden(True)
        for art in picker.arts:
            art_item = QTreeWidgetItem([art.name])
            art_item.setData(0, Qt.UserRole, ("art", art))
            arts_tree.addTopLevelItem(art_item)
            for spec in art.specialties:
                spec_item = QTreeWidgetItem([spec.name])
                spec_item.setData(0, Qt.UserRole, ("art_specialty", art, spec))
                art_item.addChild(spec_item)
        arts_tree.itemSelectionChanged.connect(lambda: self._art_selected(arts_tree))
        arts_tree.expandAll()
        inner.addTab(arts_tree, "Arts")
        for label, kind, rows in (
                ("Sciences", "science", picker.sciences),
                ("Rituals", "ritual", picker.rituals),
                ("Formulas", "formula", picker.formulas)):
            entries = QListWidget()
            for row in rows:
                item = QListWidgetItem(row.name)
                item.setData(Qt.UserRole, (kind, row))
                entries.addItem(item)
            entries.currentItemChanged.connect(
                lambda _c, _p, lw=entries: self._panel_detail(lw))
            inner.addTab(entries, label)
        lay = QVBoxLayout(page)
        lay.addWidget(inner)
        return page

    # ------------------------------------------------------------------ #
    # splat-specific picker extras (Form Library / Vat Refit / Paths /
    # Elemental Powers) — the picker's pages the spike deferred
    # ------------------------------------------------------------------ #

    def _form_library_page(self):
        """The Lunar Form Library: the Totem plus every animal shape recorded.

        Entirely free-form — no cost, no cap, no validation, never budget- or
        XP-audited (play-state, decision 0006). Which animals a Lunar has heart's
        blood for is a narrative record the Storyteller adjudicates, so this is a
        notepad, not a picker. Available on both sides of the lock."""
        char = self._char()
        pal = theme.palette(char.exalt_type)
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(4)
        head = QLabel("Form Library")
        head.setStyleSheet(f"font-weight:bold; color:{accent_light(pal)};")
        lay.addWidget(head)
        cap = QLabel("Narrative record — no cost, no limit checked here.")
        cap.setStyleSheet(f"color:{MUTED};")
        lay.addWidget(cap)
        row = QHBoxLayout()
        row.addWidget(QLabel("Totem"))
        totem = QLineEdit(char.totem)
        totem.textChanged.connect(lambda t: setattr(char, "totem", t))
        row.addWidget(totem, 1)
        self._totem_field = totem
        lay.addLayout(row)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        forms_host = QWidget()
        self._forms_lay = QVBoxLayout(forms_host)
        self._forms_lay.setContentsMargins(4, 4, 4, 4)
        self._forms_lay.setSpacing(2)
        scroll.setWidget(forms_host)
        lay.addWidget(scroll, 1)
        self._rebuild_forms()
        return page

    def _add_form(self) -> None:
        self._char().animal_forms.append(AnimalForm())
        self._rebuild_forms()

    def _remove_form(self, index: int) -> None:
        del self._char().animal_forms[index]
        self._rebuild_forms()

    def _rebuild_forms(self) -> None:
        """Rebuild just the forms list (the totem field survives, so typing in it is
        not interrupted by an add/remove)."""
        self._clear_lay(self._forms_lay)
        char = self._char()
        if not char.animal_forms:
            empty = QLabel("No forms recorded yet.")
            empty.setStyleSheet(f"color:{MUTED};")
            self._forms_lay.addWidget(empty)
        for i, form in enumerate(char.animal_forms):
            row = QHBoxLayout()
            animal = QLineEdit(form.name)
            animal.setPlaceholderText("Animal")
            animal.textChanged.connect(lambda t, f=form: setattr(f, "name", t))
            row.addWidget(animal, 1)
            notes = QLineEdit(form.notes)
            notes.setPlaceholderText("Notes")
            notes.textChanged.connect(lambda t, f=form: setattr(f, "notes", t))
            row.addWidget(notes, 2)
            rm = QPushButton("✕")
            rm.clicked.connect(lambda _, i=i: self._remove_form(i))
            row.addWidget(rm)
            self._forms_lay.addLayout(row)
        add = QPushButton("+ Add form")
        add.clicked.connect(self._add_form)
        self._forms_lay.addWidget(add)

    def _vat_page(self):
        """The Vat Refit page: swap Charms between the installed Slots and the
        Panoply (Alchemical CH2/CH3 pp.88-89, or an Eclipse with a crossover Slot).
        Play-state like the Form Library — the Charms are already paid for, so the
        move costs nothing and writes no XP entry; only *which* are worn changes.

        The load readout is refit.slot_load (the LIVE load), deliberately not
        charm_slot_budget (the frozen chargen snapshot) — conflating the two is the
        refit module's documented bug to avoid."""
        char = self._char()
        pal = theme.palette(char.exalt_type)
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(4)
        head = QLabel("Vat Refit")
        head.setStyleSheet(f"font-weight:bold; color:{accent_light(pal)};")
        lay.addWidget(head)
        cap = QLabel("Swap Charms between your Slots and your Panoply. Costs nothing "
                     "— they are already bought.")
        cap.setWordWrap(True)
        cap.setStyleSheet(f"color:{MUTED};")
        lay.addWidget(cap)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        self._vat_content_lay = QVBoxLayout(content)
        self._vat_content_lay.setContentsMargins(4, 4, 4, 4)
        self._vat_content_lay.setSpacing(4)
        scroll.setWidget(content)
        lay.addWidget(scroll, 1)
        self._rebuild_vat()
        return page

    def _do_uninstall(self, charm_id: str) -> None:
        try:
            refit.uninstall(self._ruleset, self._char(), charm_id)
        except refit.RefitError as ex:
            self._notify(str(ex), "warning")
            return
        self._rebuild_vat()

    def _do_install(self, charm_id: str) -> None:
        try:
            refit.install(self._ruleset, self._char(), charm_id)
        except refit.RefitError as ex:
            self._notify(str(ex), "warning")
            return
        self._rebuild_vat()

    def _refit_row(self, charm_id: str, *, installed: bool) -> None:
        """One installed/Panoply Charm: name + the trait bits that decide which Slot
        it fits, the block reason if a move is refused, and the move button."""
        ruleset, char = self._ruleset, self._char()
        charm = ruleset.charms.get(charm_id)
        name = charm.name if charm is not None else charm_id
        reason = (refit.uninstall_block_reason(ruleset, char, charm_id) if installed
                  else refit.install_block_reason(ruleset, char, charm_id))
        text = QVBoxLayout()
        text.setSpacing(0)
        text.addWidget(QLabel(name))
        bits = []
        if charm is not None:
            if charm.min_attribute:
                bits.append(f"{charm.min_attribute.title()} {charm.min_ability}")
            if charm.installation_cost:
                bits.append(f"{charm.installation_cost}m install")
            if not validate.charm_fits_dedicated_slot(ruleset, char, charm):
                bits.append("General Slot only")
        if bits:
            sub = QLabel(" · ".join(bits))
            sub.setStyleSheet(f"color:{MUTED};")
            text.addWidget(sub)
        if reason:
            r = QLabel(reason)
            r.setStyleSheet("color:#b45309; font-style:italic;")
            text.addWidget(r)
        row = QHBoxLayout()
        row.addLayout(text, 1)
        btn = QPushButton("To Panoply" if installed else "Install")
        if reason:
            btn.setEnabled(False)
            btn.setToolTip(reason)
        else:
            handler = self._do_uninstall if installed else self._do_install
            btn.clicked.connect(lambda _, c=charm_id, h=handler: h(c))
        row.addWidget(btn)
        self._vat_content_lay.addLayout(row)

    def _rebuild_vat(self) -> None:
        """Rebuild the Vat page body: the live load readout, the Ox-Body note, then
        the INSTALLED and PANOPLY rows. Rebuilt after every move."""
        self._clear_lay(self._vat_content_lay)
        ruleset, char = self._ruleset, self._char()
        pal = theme.palette(char.exalt_type)
        load = refit.slot_load(ruleset, char)
        over = load.installed > load.total_slots or load.motes > load.personal
        color = "#b91c1c" if over else accent_light(pal)
        head = QHBoxLayout()
        slots = QLabel(f"Slots {load.installed}/{load.total_slots} "
                       f"({load.general} General · {load.dedicated} Dedicated)")
        slots.setStyleSheet(f"font-weight:600; color:{color};")
        head.addWidget(slots)
        for text in (f"General used {load.noncf}/{load.general}",
                     f"Committed {load.motes}m of {load.personal}m Personal"):
            lbl = QLabel(text)
            lbl.setStyleSheet(f"color:{MUTED};")
            head.addWidget(lbl)
        head.addStretch()
        self._vat_content_lay.addLayout(head)
        if char.ox_body:
            note = QLabel(f"{len(char.ox_body)} Strain Resistant Chassis purchase(s) "
                          "occupy Slots and are not refittable.")
            note.setWordWrap(True)
            note.setStyleSheet(f"color:{MUTED}; font-style:italic;")
            self._vat_content_lay.addWidget(note)
        self._vat_content_lay.addWidget(self._section_header("INSTALLED", pal))
        # The refittable installed set — ox_body and PLM Charms occupy Slots but are
        # not swappable, so they stay off this list (the web computes the same way).
        slotted = [cid for cid in char.charms
                   if (ch := ruleset.charms.get(cid)) is not None
                   and validate.charm_occupies_slot(ruleset, char, ch)]
        if not slotted:
            empty = QLabel("No Charms installed.")
            empty.setStyleSheet(f"color:{MUTED};")
            self._vat_content_lay.addWidget(empty)
        for cid in slotted:
            self._refit_row(cid, installed=True)
        self._vat_content_lay.addWidget(self._section_header("PANOPLY", pal))
        if not char.retainer_charms:
            empty = QLabel("Panoply empty — nothing on retainer.")
            empty.setStyleSheet(f"color:{MUTED};")
            self._vat_content_lay.addWidget(empty)
        for cid in char.retainer_charms:
            self._refit_row(cid, installed=False)
        self._vat_content_lay.addStretch(1)

    def _section_header(self, text: str, pal) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"font-weight:bold; color:{accent_light(pal)};")
        return lbl

    def _elemental_page(self):
        """The Elemental Powers page: Elemental-origin God-Blooded only (Core p.296,
        GoD p.56, PG p.68). A Charm-like catalogue — 7 BP each chargen, 14 XP in play
        (double the bonus-point value, PG p.68). Selection drives the shared detail
        pane and the Learn/Remove action button, exactly like Spells and Thaum."""
        char = self._char()
        pal = theme.palette(char.exalt_type)
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(4)
        head = QLabel("Elemental Powers")
        head.setStyleSheet(f"font-weight:bold; color:{accent_light(pal)};")
        lay.addWidget(head)
        self._elemental_list = QListWidget()
        self._elemental_list.currentItemChanged.connect(
            lambda _c, _p: self._elemental_selected())
        lay.addWidget(self._elemental_list, 1)
        self._rebuild_elemental()
        return page

    def _rebuild_elemental(self) -> None:
        """Rebuild the power list from a fresh picker so owned/available state is
        live, then re-select the previously selected id (a stored row's owned flag
        goes stale the moment the list is rebuilt)."""
        picker = build_elemental_power_picker(self._ruleset, self._char())
        self._elemental_list.clear()
        for row in picker.powers:
            item = QListWidgetItem(row.name)
            item.setData(Qt.UserRole, row)
            if not row.owned and not row.available:
                item.setForeground(QColor("#8a8a8a"))      # locked, visually dimmed
            self._elemental_list.addItem(item)
        if self._selected_elemental is not None:
            for i in range(self._elemental_list.count()):
                if self._elemental_list.item(i).data(Qt.UserRole).id == self._selected_elemental:
                    self._elemental_list.setCurrentRow(i)
                    break
        else:
            self._update_action()

    def _elemental_selected(self) -> None:
        item = self._elemental_list.currentItem()
        self._selected_node = None
        self._selected_spell = None
        self._selected_thaum = None
        if item is None:
            self._selected_elemental = None
            self._update_action()
            return
        row = item.data(Qt.UserRole)
        self._selected_elemental = row.id
        self.detail.setHtml(self._elemental_detail_html(row))
        self._update_action()

    def _elemental_detail_html(self, row, currency: str | None = None) -> str:
        """The detail pane for an ElementalPowerRow: name, Requires, Cost, activation
        (italic) and description. The shared `_detail_html` reads `requirement`/`type`,
        which this row does not carry, so it gets its own small formatter."""
        if currency is None:
            currency = "XP" if self._char().chargen_locked else "BP"
        lines = []
        if row.requires:
            lines.append(f"<b>Requires:</b> {html.escape(row.requires)}")
        lines.append(f"<b>Cost:</b> {row.price} {currency}")
        if row.activation:
            lines.append(f"<i>{html.escape(row.activation)}</i>")
        if row.description:
            lines.append(html.escape(row.description))
        parts = [f"<b>{html.escape(row.name)}</b>"]
        if lines:
            parts.append("<br>".join(f"<span style='color:#b8b6b2'>{ln}</span>"
                                     for ln in lines))
        if not row.available and row.reason:
            parts.append(f"<span style='color:#b45309'>{html.escape(row.reason)}</span>")
        return "<br>".join(parts)

    def _toggle_elemental(self, power_id: str) -> None:
        """The web picker's elemental toggle, ported. Pre-lock: edit the chargen list
        directly, gated by `validate.meets_elemental_power_requirements` (the 7-BP
        charge is validation-side). Post-lock: `advancement.learn_elemental_power`
        (14 XP); a known power is not droppable in play — undo on the Edit tab."""
        ruleset, char = self._ruleset, self._char()
        if char.chargen_locked:
            if power_id in char.elemental_powers:
                self._notify("Already known — undo the purchase on the Edit tab to "
                             "give it back.", "info")
                return
            try:
                advancement.learn_elemental_power(ruleset, char, power_id)
            except advancement.AdvancementError as ex:
                self._notify(str(ex), "warning")
                return
            power = ruleset.elemental_powers.get(power_id)
            self._notify(f"Learned {power.name} — "
                         f"{costs.elemental_power_xp(ruleset, char, power)} XP", "info")
        elif power_id in char.elemental_powers:
            char.elemental_powers.remove(power_id)
            p = ruleset.elemental_powers.get(power_id)
            self._notify(f"Dropped {p.name if p is not None else power_id}", "info")
        else:
            power = ruleset.elemental_powers.get(power_id)
            if power is None:
                return
            if not validate.meets_elemental_power_requirements(ruleset, char, power):
                self._notify(f"{power.name}: " + "; ".join(
                    validate.elemental_power_shortfalls(ruleset, char, power)), "warning")
                return
            char.elemental_powers.append(power_id)
            self._notify(f"Learned {power.name}", "info")
        self._refresh_elemental()

    def _refresh_elemental(self) -> None:
        """After a toggle: rebuild the list (re-selecting the same id), refresh the
        detail + action button, and the readout. Not routed through
        `_refresh_current_tree` — that re-renders a CharmTreeView, wrong-shaped here."""
        self._rebuild_elemental()
        self._update_readout()

    def _paths_page(self):
        """The Dragon-King Paths page (PG pp.175-177): a rated-track subsystem with
        its own chargen pool, NOT Charms. Each Path is rated 1-6 (learned in fixed
        order, gated by Essence); each dot grants that level's power. Pre-lock the
        rating is a free setter into character.paths; post-lock it becomes XP +/-
        via advancement. The breed's two element Paths are auto-favoured (★) and the
        player chooses one more (✚) from the other eight."""
        char = self._char()
        pal = theme.palette(char.exalt_type)
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(4)
        head = QLabel("Paths of Prehuman Mastery")
        head.setStyleSheet(f"font-weight:bold; color:{accent_light(pal)};")
        lay.addWidget(head)
        b = self._ruleset.budgets_for(char.exalt_type, char.origin, char.upbringing)
        cap = QLabel(f"{b.path_dots} free dots · ≥{b.path_min_breed_favored} from "
                     f"Breed/Favoured Paths · none above {b.path_cap_pre_bp} without "
                     "bonus points")
        cap.setWordWrap(True)
        cap.setStyleSheet(f"color:{MUTED};")
        lay.addWidget(cap)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        self._paths_lay = QVBoxLayout(content)
        self._paths_lay.setContentsMargins(4, 4, 4, 4)
        self._paths_lay.setSpacing(2)
        scroll.setWidget(content)
        lay.addWidget(scroll, 1)
        self._rebuild_paths()
        return page

    def _set_path_rating(self, path_id: str, rating: int) -> None:
        """Pre-lock free setter into character.paths (validation via validate_chargen):
        a rating of 0 removes the Path, otherwise append or update the PathRating."""
        char = self._char()
        existing = next((p for p in char.paths if p.path_id == path_id), None)
        if rating <= 0:
            if existing:
                char.paths.remove(existing)
        elif existing:
            existing.rating = rating
        else:
            char.paths.append(PathRating(path_id=path_id, rating=rating))
        self._rebuild_paths()
        self._update_readout()      # the path-dots pool is budgeted, pre-lock too

    def _path_adv(self, path_id: str, direction: int) -> None:
        """Post-lock XP raise/lower of one Path dot, via advancement."""
        ruleset, char = self._ruleset, self._char()
        try:
            if direction > 0:
                if any(p.path_id == path_id for p in char.paths):
                    advancement.raise_path(ruleset, char, path_id)
                else:
                    advancement.learn_path(ruleset, char, path_id)
            else:
                advancement.lower_path(ruleset, char, path_id)
        except advancement.AdvancementError as ex:
            self._notify(str(ex), "warning")
            return
        self._rebuild_paths()
        self._update_readout()

    def _rebuild_paths(self) -> None:
        """Rebuild the Paths page body: the Favoured Path row, then one row per Path
        (marker + name + element + rating control) with the granted powers listed
        under a rated Path."""
        self._clear_lay(self._paths_lay)
        self._path_combos: dict[str, QComboBox] = {}
        self._fav_path_combo = None
        ruleset, char = self._ruleset, self._char()
        pal = theme.palette(char.exalt_type)
        ratings = {p.path_id: p.rating for p in char.paths}
        breed_el = engine_paths.breed_element(ruleset, char)
        breed_path_ids = {p.id for p in ruleset.paths.values() if p.element == breed_el}
        fav_opts = {p.id: p.name for p in ruleset.paths.values()
                    if p.id not in breed_path_ids}

        fav_row = QHBoxLayout()
        fav_row.addWidget(QLabel("Favoured Path"))
        if char.chargen_locked:
            chosen = ruleset.paths.get(char.favored_path)
            lbl = QLabel(chosen.name if chosen else "—")
            lbl.setStyleSheet(f"color:{MUTED};")
            fav_row.addWidget(lbl, 1)
        else:
            combo = QComboBox()
            combo.addItem("— none —", "")
            for pid, pname in fav_opts.items():
                combo.addItem(pname, pid)
            # ⚠ Trap #3 (the picker's Qt form): a saved `favored_path` that is one of
            # the breed's two (an illegal-but-possible state) must still be an option
            # — a combo whose value is absent from its options misbehaves. And it is
            # a SAVE value, so never index `ruleset.paths[saved]` directly: a stale
            # id from a catalogue rename would KeyError and take the whole tab down.
            # Show the printed name when the id resolves, else the raw id as its own
            # label (the web's setdefault fallback).
            combo.blockSignals(True)
            if char.favored_path:
                if combo.findData(char.favored_path) < 0:
                    p = ruleset.paths.get(char.favored_path)
                    combo.addItem(p.name if p is not None else char.favored_path,
                                  char.favored_path)
                combo.setCurrentIndex(combo.findData(char.favored_path))
            else:
                combo.setCurrentIndex(0)
            combo.blockSignals(False)
            # ⚠ Capture the combo as a default arg — a bare `combo` in the closure is
            # the shared local that the per-path rating loop below reassigns, so the
            # handler would read the LAST path's rating combo instead of this one (a
            # picked favoured path silently became '').
            combo.currentIndexChanged.connect(lambda _, c=combo: (
                setattr(char, "favored_path", c.currentData() or ""),
                self._rebuild_paths()))
            self._fav_path_combo = combo
            fav_row.addWidget(combo, 1)
        note = QLabel("★ breed · ✚ your choice")
        note.setStyleSheet(f"color:{MUTED}; font-style:italic;")
        fav_row.addWidget(note)
        self._paths_lay.addLayout(fav_row)

        for path in ruleset.paths.values():
            rating = ratings.get(path.id, 0)
            marker = ("★ " if path.element and path.element == breed_el
                      else ("✚ " if path.id == char.favored_path else ""))
            row = QHBoxLayout()
            name_lbl = QLabel(f"{marker}{path.name}")
            name_lbl.setStyleSheet("font-weight:600;")
            row.addWidget(name_lbl, 1)
            el = QLabel(path.element_label)
            el.setStyleSheet(f"color:{MUTED};")
            row.addWidget(el)
            if char.chargen_locked:
                minus = QPushButton("−")
                minus.setEnabled(rating > 0)
                minus.clicked.connect(lambda _, pid=path.id: self._path_adv(pid, -1))
                row.addWidget(minus)
                r = QLabel(str(rating))
                r.setStyleSheet("font-family:monospace;")
                r.setFixedWidth(20)
                r.setAlignment(Qt.AlignCenter)
                row.addWidget(r)
                plus = QPushButton("+")
                plus.clicked.connect(lambda _, pid=path.id: self._path_adv(pid, +1))
                row.addWidget(plus)
            else:
                # ⚠ Block signals while populating + setting the initial index — an
                # unblocked setCurrentIndex fires the handler → identical write →
                # rebuild → infinite loop.
                combo = QComboBox()
                combo.blockSignals(True)
                for i in range(0, 7):
                    combo.addItem(str(i), i)
                combo.setCurrentIndex(rating)
                combo.blockSignals(False)
                # ⚠ Capture the combo as a default arg — a bare `combo` in the
                # closure is the LOOP variable, shared by every path's handler, so
                # each one would read the LAST path's combo instead of its own.
                combo.currentIndexChanged.connect(
                    lambda _, c=combo, pid=path.id: self._set_path_rating(
                        pid, c.currentData()))
                self._path_combos[path.id] = combo
                row.addWidget(combo)
            self._paths_lay.addLayout(row)
            if rating:
                for power in path.powers[:rating]:
                    pw = QLabel(f"• {power.name} — {power.duration}")
                    pw.setContentsMargins(16, 0, 0, 0)
                    pw.setStyleSheet(f"color:{MUTED}; font-weight:600;")
                    self._paths_lay.addWidget(pw)
                    if power.text:
                        txt = QLabel(power.text)
                        txt.setWordWrap(True)
                        txt.setContentsMargins(16, 0, 0, 0)
                        txt.setStyleSheet(f"color:{MUTED};")
                        self._paths_lay.addWidget(txt)
        self._paths_lay.addStretch(1)

    def _art_selected(self, tree):
        """The Arts tree's selection: an Art or one of its specialties. Sets
        `_selected_thaum` to ("art", row) or ("art_specialty", art, spec) and shows
        the detail."""
        item = tree.currentItem()
        self._selected_node = None
        self._selected_spell = None
        self._selected_elemental = None
        if item is None:
            self._selected_thaum = None
            self._update_action()
            return
        self._selected_thaum = item.data(0, Qt.UserRole)
        kind = self._selected_thaum[0]
        obj = self._selected_thaum[2] if kind == "art_specialty" else self._selected_thaum[1]
        self.detail.setHtml(_detail_html(obj, self._thaum_currency()))
        self._update_action()

    def _thaum_currency(self) -> str:
        """'BP' or 'XP' — which budget Thaumaturgy is being bought with right now."""
        return build_thaum_picker(self._ruleset, self._char()).currency

    def _fill_list(self, entries, items):
        entries.clear()
        for name, obj in items:
            item = QListWidgetItem(name)
            item.setData(Qt.UserRole, obj)
            entries.addItem(item)

    def _panel_detail(self, entries):
        item = entries.currentItem()
        if item is None:
            self._selected_spell = None
            self._selected_thaum = None
            self._selected_elemental = None
            self._update_action()
            return
        obj = item.data(Qt.UserRole)
        self._selected_node = None
        self._selected_elemental = None
        if isinstance(obj, tuple):          # a (kind, row) Thaumaturgy entry
            kind, row = obj
            self._selected_thaum = (kind, row)
            self._selected_spell = None
            self.detail.setHtml(_detail_html(row, self._thaum_currency()))
        else:
            self._selected_thaum = None
            # A Spell carries a circle; a Thaumaturgy entry does not — that is how
            # the action button knows a spell row is selected and can offer to learn it.
            self._selected_spell = obj.id if getattr(obj, "circle", None) else None
            self.detail.setHtml(_detail_html(obj) if obj is not None
                                else f"<b>{item.text()}</b>")
        self._update_action()

    def reload(self):
        """Rebuild the tab bar for the current character: a tree tab per non-empty
        group, then Spells, Thaumaturgy and the splat-specific extras."""
        char = self._char()
        self._tree_views.clear()
        # Reset every selection: a reload rebuilds the pages, so any remembered
        # selection points at widgets that no longer exist (or, worse, still exists
        # but is a different character's entry).
        self._selected_node = None
        self._selected_spell = None
        self._selected_thaum = None
        self._selected_elemental = None
        # Block tab signals across the rebuild: the QTabWidget fires currentChanged
        # during clear()/addTab (the qt-port.md construction trap), and with several
        # gated builders a mid-build signal could poke a panel that is only half
        # built. `_tab_changed()` below runs explicitly once the bar is complete.
        self.tabs.blockSignals(True)
        try:
            self.tabs.clear()
            for group, label in (("abilities", "Charms"), ("styles", "Martial Arts"),
                                 ("arcanoi", "Arcanoi")):
                if trees_for(self._ruleset, char, char.exalt_type, group):
                    self.tabs.addTab(self._tree_page(group), label)
            circles = spell_circles(self._ruleset, char)
            if circles:
                self.tabs.addTab(self._spells_page(circles), "Spells")
            if self._ruleset.exalt_for(char.exalt_type).form_library:
                self.tabs.addTab(self._form_library_page(), "Form Library")
            self.tabs.addTab(self._thaum_page(), "Thaumaturgy")
            if refit.supports_refit(self._ruleset, char):
                self.tabs.addTab(self._vat_page(), "Vat Refit")
            if self._ruleset.budgets_for(char.exalt_type, char.origin,
                                         char.upbringing).path_dots > 0:
                self.tabs.addTab(self._paths_page(), "Paths")
            if validate.elemental_powers_available(self._ruleset, char):
                self.tabs.addTab(self._elemental_page(), "Elemental Powers")
        finally:
            self.tabs.blockSignals(False)
        self.detail.setText("Select an entry to see details.")
        self._tab_changed()
        self._update_readout()
        self._update_action()

    def _tab_changed(self, *_):
        view = (self.tabs.currentWidget().findChild(CharmTreeView)
                if self.tabs.currentWidget() else None)
        if view is not None and view.graph:
            self.count_label.setText(f"{len(view.graph.nodes)} nodes · "
                                     f"{len(view.graph.edges)} edges")
        else:
            self.count_label.setText("")
