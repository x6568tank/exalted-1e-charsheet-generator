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
    QCheckBox, QComboBox, QDialog, QFrame, QGraphicsItem, QGraphicsPathItem,
    QGraphicsRectItem, QGraphicsScene, QGraphicsView, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QPushButton, QScrollArea, QSizePolicy, QSpinBox,
    QSplitter, QStyle, QTabWidget, QTextBrowser, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget,
)

from exalted_builder.engine import (advancement, charm_actions, costs, merits,
                                    refit, thaum_actions, validate)
from exalted_builder.engine import paths as engine_paths
from exalted_builder.models.character import AbilityName, AnimalForm, PathRating
from exalted_builder.qt.editor import DotTrack
from exalted_builder.qt.layout import clear_layout
from exalted_builder.models.rules import Orientation
from exalted_builder.ui import theme

from .theme import CARD, MUTED, TREE, accent as accent_light
from exalted_builder.ui import view as viewmod
from exalted_builder.ui.view import (CIRCLE_DISPLAY_ORDER, _cost_str, _style_label,
                                     CharmGraph, CharmNode, augmentation_category,
                                     build_augmentation_view,
                                     build_charm_detail, build_charm_graph,
                                     build_elemental_power_picker,
                                     build_package_menu, build_sheet_view,
                                     build_spell_picker,
                                     build_thaum_picker, charm_on_splat_page,
                                     package_menu_kind, prune_package_selection,
                                     virtue_split)

ROW_H = 160            # vertical space between tree levels
GAP_X = 40             # horizontal gap between sibling subtrees
NODE_H = 56
MIN_W = 150            # smallest node box
MAX_NODE_W = 260       # largest node box; longer labels elide with an ellipsis
MAX_LEVEL_NODES = 6    # cap nodes in one tree-level row; wider levels sub-row


def _cached(cache, key, compute):
    """Memoize `compute()` under `key` in `cache`, or just run it when `cache` is None.

    ⚠ The cache is per-BUILD and must never be stored on the page or keyed on the
    RuleSet. `rules_db.reload_custom_layer` mutates `ruleset.charms` IN PLACE so that
    authoring a homebrew Charm shows up on every page that already holds the object —
    so a cache outliving one build would serve a catalogue the player has just edited.
    """
    if cache is None:
        return compute()
    if key not in cache:
        cache[key] = compute()
    return cache[key]


def _arcanoi_categories(ruleset, cache=None):
    """Category names whose Charms are Arcanoi: Virtue-keyed and not the spirit Charms
    (which share the min_virtue axis but are a different class, exalt_type "Spirit")."""
    return _cached(cache, "arcanoi_categories", lambda: {
        c.category for c in ruleset.charms.values()
        if c.min_virtue and c.exalt_type != "Spirit"})


def group_of(category, ruleset, cache=None):
    """The picker group a category belongs to: 'styles' / 'arcanoi' / 'abilities'.

    Mirrors picker._group_of: martial-arts categories are named by prefix; a category
    is an arcanos when its base name (before any `:virtue` split) is one of the
    Virtue-keyed non-spirit categories; everything else is an ability Charm."""
    if category.startswith("martial_arts:"):
        return "styles"
    return ("arcanoi" if category.split(":", 1)[0] in _arcanoi_categories(ruleset, cache)
            else "abilities")


def trees_for(ruleset, character, splat, group, cache=None):
    """[(category_key, node_count)] for one splat's page in `group`, biggest first.

    `cache` is an optional per-build memo shared with the other calls in the same
    rebuild — see `_cached`. Every helper below is a pure function of the ruleset (and
    for the augmentation category, the character's splat), but each one SCANS the whole
    Charm catalogue, and a rebuild asks for them thousands of times.
    """
    found: set[str] = set()
    for c in ruleset.charms.values():
        if not charm_on_splat_page(ruleset, character, c, splat):
            continue
        split = _cached(cache, ("virtue_split", c.category),
                        lambda cat=c.category: virtue_split(ruleset, cat))
        for key in (split or [c.category]):
            if group_of(key, ruleset, cache) == group:
                found.add(key)
    out = []
    for key in found:
        graph = build_charm_graph(ruleset, character, key, splat)
        graph = _collapse_augment_nodes(ruleset, character, graph, cache)
        if graph.nodes:
            out.append((key, len(graph.nodes)))
    return sorted(out, key=lambda t: -t[1])


def _collapse_augment_nodes(ruleset, character, graph, cache=None):
    """Collapse the Alchemical augmentation templates into ONE node per type
    (Transitory / Sustained) inside the tree, rerouting prerequisite edges. The 18
    '<Type> Augmentation of <Attribute>' ids stay distinct in the data (other Charms
    name a specific one as a prerequisite); the tree shows two summary nodes —
    selecting one offers 'Pick Attributes' — instead of eighteen disconnected nodes
    cluttering every dependent tree (a close-combat Charm names 'Transitory
    Augmentation of Dexterity')."""
    # ⚠ This is the expensive one: it scans every Charm through `charm_matches_splat`,
    # and a rebuild collapses ~90 trees. Uncached it was 180,000 calls per page build.
    aug_cat = _cached(cache, "augmentation_category",
                      lambda: augmentation_category(ruleset, character))
    if aug_cat is None:
        return graph
    owned = set(character.charms)
    types: dict[str, list[CharmNode]] = {}
    for n in graph.nodes:
        c = ruleset.charms.get(n.id)
        if c is None or c.category != aug_cat:
            continue
        title = c.name.split(" Augmentation of ", 1)[0] + " Augmentation"
        types.setdefault(title, []).append(n)
    if not types:
        return graph
    drop = {n.id for ns in types.values() for n in ns}
    title_of = {n.id: title for title, ns in types.items() for n in ns}

    summaries: list[CharmNode] = []
    summary_id: dict[str, str] = {}
    for title, ns in types.items():
        s = CharmNode(
            id=f"augment:{title.split()[0].lower()}",
            label=title,
            state="owned" if any(n.id in owned for n in ns) else "available",
            min_ability=0, min_essence=0,
            external=True)
        summaries.append(s)
        summary_id[title] = s.id

    nodes = [n for n in graph.nodes if n.id not in drop] + summaries
    edges = []
    for prereq, charm_id in graph.edges:
        if prereq in title_of:
            edges.append((summary_id[title_of[prereq]], charm_id))
        elif prereq not in drop and charm_id not in drop:
            edges.append((prereq, charm_id))
    roots = [rid for rid in graph.roots if rid not in drop]
    with_incoming = {child for _, child in edges}
    for s in summaries:
        if s.id not in with_incoming:
            roots.append(s.id)
    return CharmGraph(graph.category, nodes, edges, roots)


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

    def __init__(self, ruleset, character, cache=None):
        super().__init__()
        self._ruleset = ruleset
        self._character = character
        # The owning rebuild's memo (see `_cached`). Safe to hold for the view's whole
        # life because `_tree_page` builds a NEW view on every reload, so the two
        # lifetimes are the same one. ⚠ Only splat-derived answers go in it — nothing
        # keyed on which Charms are OWNED, which changes under a live view on a buy.
        self._cache = cache
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
        graph = _collapse_augment_nodes(self._ruleset, self._character, graph,
                                        self._cache)
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

    def __init__(self, ruleset, ctx, *, notify=None, on_change=None, parent=None):
        super().__init__(parent)
        self._ruleset = ruleset
        self._ctx = ctx
        self._notify = notify or (lambda text, kind="info": None)
        # ⚠ Spending on THIS tab moves the shell's readout bar too — a Charm pick past
        # the free pool costs bonus points, and every buy here is a buy. Fired from
        # `_update_readout`, which is the one place every purchase path already meets.
        self._on_change = on_change or (lambda: None)
        self._selected_node: str | None = None
        self._selected_spell: str | None = None
        self._selected_thaum: tuple | None = None
        self._selected_elemental: str | None = None
        self._selected_path: str | None = None
        self._selected_augment: str | None = None
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
        # The Path rating dot track — visible only while a Path is selected on the
        # Paths page (which binds the track). Hidden on every other selection.
        self._path_box = QWidget()
        self._path_box_lay = QHBoxLayout(self._path_box)
        self._path_box_lay.setContentsMargins(0, 0, 0, 0)
        self._path_box_lay.setSpacing(4)
        rating_label = QLabel("Rating:")
        rating_label.setStyleSheet(f"color:{MUTED};")
        self._path_box_lay.addWidget(rating_label)
        self._path_box.setVisible(False)
        dp.addWidget(self._path_box)
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

    def _clear_lay(self, lay) -> None:
        """Empty `lay`, detaching every descendant NOW. One line, because the shape is
        subtle enough that six hand-written copies produced a wrong one — see
        `qt/layout.py`, which owns both traps and the reason they matter."""
        clear_layout(lay)

    # ------------------------------------------------------------------ #
    # buying (the picker's toggle, ported) — the one thing the spike left out
    # ------------------------------------------------------------------ #

    def _chargen_pick_bp(self, *, charm_id=None, spell_id=None) -> int:
        """The bonus-point price of ONE more chargen Charm/Spell pick, once the free
        pool is exhausted (0 while it has room). Exact dearest-first accounting: the
        pool covers the free dearest picks, so the marginal is the delta of the pool
        sum, not the raw rate — a new cheap pick can sit below the pool and add
        nothing, a dear one displaces a cheaper held pick."""
        ruleset, char = self._ruleset, self._char()
        if charm_id is not None and charm_id in char.charms:
            return 0
        if spell_id is not None and spell_id in char.spells:
            return 0
        b = validate.effective_budgets(ruleset, char)
        immaculate = validate._immaculate_path(ruleset, list(char.charms),
                                               char.exalt_type)
        free = b.immaculate_charm_count if immaculate else b.charm_count
        bp_costs = ruleset.bonus_costs_for(char.exalt_type, char.origin,
                                           char.upbringing)
        occult_cf = AbilityName.OCCULT in validate.caste_favored_abilities(ruleset, char)
        spell_rate = bp_costs.charm_favored_caste if occult_cf else bp_costs.charm

        def _pool_total(stage: bool) -> int:
            """The pool sum with the candidate staged in (or not). Staging runs the
            picker's own enumeration, so the candidate is priced with its favoured
            flags and any Calling/Immaculate/MA/magic ladder it falls on."""
            if stage:
                if charm_id is not None:
                    char.charms.append(charm_id)
                else:
                    char.spells.append(spell_id)
            try:
                pick_costs = validate.charm_pick_bp_costs(
                    ruleset, char, validate.chargen_charm_picks(ruleset, char))
                for sid in char.spells:
                    if ruleset.spells.get(sid) is None:
                        continue
                    pick_costs.append(merits.adjust_spell_cost(ruleset, char, spell_rate))
                pick_costs.sort(reverse=True)
                return sum(pick_costs[free:])
            finally:
                if stage:
                    if charm_id is not None:
                        char.charms.remove(charm_id)
                    else:
                        char.spells.remove(spell_id)

        return _pool_total(True) - _pool_total(False)

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
            # A variant-menu Charm is bought as a PACKAGE and is not toggleable —
            # `charm_actions.variant_menu_reason` refuses the toggle, so the button
            # must open the chooser instead of offering Learn.
            menu = build_package_menu(self._ruleset, char, cid)
            if menu is not None:
                verb = "Choose Gifts…" if menu.kind == "gift" else "Choose a package…"
                self.action_btn.setText(
                    f"{verb} — {menu.price} XP each" if menu.price else verb)
                self.action_btn.setEnabled(True)
                self.action_btn.setToolTip("")
                return
            owned = cid in char.charms
            label = f"Remove {charm.name}" if owned else f"Learn {charm.name}"
            if not owned:
                if char.chargen_locked:
                    label += f" — {costs.charm_cost(self._ruleset, char, charm)} XP"
                else:
                    bp = self._chargen_pick_bp(charm_id=cid)
                    if bp:
                        label += f" — {bp} BP"
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
            if not owned:
                if char.chargen_locked:
                    label += f" — {costs.spell_cost(self._ruleset, char, spell)} XP"
                else:
                    bp = self._chargen_pick_bp(spell_id=sid)
                    if bp:
                        label += f" — {bp} BP"
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
                # A chargen Elemental Power costs bonus points (PG p.68) — the button
                # carries the BP price on both sides of the lock, like the Thaum rows.
                self.action_btn.setText(f"Learn {row.name} — {row.price} BP")
                self.action_btn.setEnabled(row.available)
                self.action_btn.setToolTip(row.reason if not row.available else "")
            return
        if self._selected_augment is not None:
            self.action_btn.setText("Pick Attributes")
            self.action_btn.setEnabled(True)
            self.action_btn.setToolTip("")
            return
        if self._selected_path is not None:
            path = self._ruleset.paths.get(self._selected_path)
            if path is None:
                self.action_btn.setEnabled(False)
                self.action_btn.setText("Select an entry…")
                return
            rating = next((p.rating for p in self._char().paths
                           if p.path_id == self._selected_path), 0)
            if self._char().chargen_locked:
                if rating >= 6:
                    self.action_btn.setEnabled(False)
                    self.action_btn.setText(f"{path.name} at max")
                elif rating:
                    cost = costs.path_step(self._ruleset, self._char(),
                                           self._selected_path, rating)
                    self.action_btn.setEnabled(True)
                    self.action_btn.setText(f"Raise {path.name} — {cost} XP")
                else:
                    cost = costs.path_new_cost(self._ruleset, self._char(),
                                               self._selected_path)
                    self.action_btn.setEnabled(True)
                    self.action_btn.setText(f"Learn {path.name} — {cost} XP")
            else:
                self.action_btn.setEnabled(rating < 6)
                self.action_btn.setText(f"Raise {path.name}" if rating
                                        else f"Learn {path.name}")
            return
        self.action_btn.setEnabled(False)
        self.action_btn.setText("Select an entry…")

    def _on_action(self) -> None:
        if self._selected_node is not None:
            if package_menu_kind(self._ruleset, self._char(), self._selected_node):
                self._open_package_dialog(self._selected_node)
            else:
                self._toggle_charm(self._selected_node)
        elif self._selected_spell is not None:
            self._toggle_spell(self._selected_spell)
        elif self._selected_thaum is not None:
            self._toggle_thaum(*self._selected_thaum)
        elif self._selected_elemental is not None:
            self._toggle_elemental(self._selected_elemental)
        elif self._selected_path is not None:
            self._path_act()
        elif self._selected_augment is not None:
            group = next((g for g in build_augmentation_view(self._ruleset, self._char())
                          if g.title == self._selected_augment), None)
            if group is not None:
                self._open_augment_dialog(group)

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

    def _act(self, action, *args) -> bool:
        """Run an engine.charm_actions dispatcher and show what it says — its return
        message, or its AdvancementError as a warning. True when the character
        changed, so the caller can skip its repaint."""
        try:
            self._notify(action(*args), "info")
        except advancement.AdvancementError as ex:
            self._notify(str(ex), "warning")
            return False
        return True

    def _toggle_charm(self, charm_id: str) -> None:
        """A node click: learn an unowned Charm, drop an owned one, buy post-lock.

        ⚠ The dispatch is engine.charm_actions.toggle_charm and must stay there — the
        web picker holds the SAME logic and the two drifted once already (Ox-Body's
        variant menu reached only the web copy, so this one would have appended the
        package Charm's id straight into `char.charms`). `variant_menu_reason` now
        refuses that here rather than relying on a widget-level branch."""
        if self._act(charm_actions.toggle_charm, self._ruleset, self._char(), charm_id):
            self._refresh_current_tree()

    def _toggle_spell(self, spell_id: str) -> None:
        """A spell row's click — the same chargen/XP split, same shared dispatcher."""
        if self._act(charm_actions.toggle_spell, self._ruleset, self._char(), spell_id):
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
        """Redraw this tab's budget line AND tell the shell its own bar moved.

        ⚠ A wrapper rather than a call at the end of `_draw_readout`, because that has
        two exits (locked/chargen) and the shell hook must fire from both. Every
        purchase path on this tab already funnels through here."""
        self._draw_readout()
        self._on_change()

    def _draw_readout(self) -> None:
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
        # ⚠ The Slots readout is the LIVE load, not the frozen chargen snapshot —
        # the same conflation the Vat Refit page documents. charm_slot_budget reports
        # the snapshot, so buying a Charm post-lock never moved the count.
        if refit.supports_refit(ruleset, char):
            load = refit.slot_load(ruleset, char)
            picks = (f"Slots: {load.installed}/{load.total_slots} used "
                     f"(G {load.general} · D {load.dedicated})")
        else:
            b = ruleset.budgets_for(char.exalt_type, char.origin, char.upbringing)
            if b.path_dots > 0:
                # A Dragon-King learns Paths, not Charms — 'Charms: 0' is noise.
                used = sum(p.rating for p in char.paths)
                picks = f"Path dots: {used} · Spells: {len(char.spells)}"
            else:
                noun = ruleset.exalt_for(char.exalt_type).charm_noun
                picks = (f"{noun}: {validate.charm_pick_count(ruleset, char)} · "
                         f"Spells: {len(char.spells)}")
        parts = [picks, status]
        if bp:
            parts.append(bp)
        self.readout.setText(" · ".join(parts))
        self.readout.setStyleSheet("color:#6b7280;")

    def _tree_page(self, group, cache=None):
        """A tree tab: category dropdown filtered to `group`, over a CharmTreeView.

        `cache` is the caller's per-build memo (see `_cached`); `reload` shares one
        across all of its `trees_for` calls, which otherwise rescan the whole Charm
        catalogue once per group and again per page."""
        char = self._char()
        page = QWidget()
        combo = CappedCombo(15)
        combo.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        combo.setMaximumWidth(300)
        view = CharmTreeView(self._ruleset, char, cache)
        view._scene.selectionChanged.connect(lambda: self._tree_detail(view))
        view.category_combo = combo
        self._tree_views[group] = view
        trees = trees_for(self._ruleset, char, char.exalt_type, group, cache)
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
            self._selected_augment = None
            self._update_action()
            return
        node = sel[0].node
        # A collapsed augmentation summary node ('augment:<type>') is not a Charm —
        # show the type's installed-Attribute readout and offer Pick Attributes.
        if node.id.startswith("augment:"):
            self._selected_augment = node.label
            self._selected_node = None
            self._selected_spell = None
            self._selected_thaum = None
            self._selected_elemental = None
            self.detail.setHtml(self._augment_summary_html(node.label))
            self._update_action()
            return
        self._selected_node = node.id
        self._selected_spell = None
        self._selected_thaum = None
        self._selected_elemental = None
        self._selected_augment = None
        detail = build_charm_detail(self._ruleset, view._character, node.id)
        html_text = _detail_html(detail) if detail else f"<b>{node.label}</b>"
        state = {"owned": "Owned", "available": "Available"}.get(node.state, "Locked")
        menu = build_package_menu(self._ruleset, view._character, node.id)
        if menu is not None:
            html_text += self._package_summary_html(menu)
        self.detail.setHtml(f"<span style='color:#9a9894'>{state}</span><br>" + html_text)
        self._update_action()

    def _package_summary_html(self, menu) -> str:
        """The packages already bought and the cap, appended to a variant-menu
        Charm's detail. The tree paints the node "owned" off a single Charm id; what
        a player needs here is HOW MANY packages and which."""
        rows = [f"<b>Bought:</b> {menu.bought} / {menu.cap} · once per "
                f"{html.escape(menu.cap_unit)} of {html.escape(menu.cap_trait)}"]
        for h in menu.held:
            rows.append("• " + html.escape(h.label))
        if not menu.held:
            rows.append("<span style='color:#9a9894'>Nothing bought yet.</span>")
        return "<br><br><span style='color:#b8b6b2'>" + "<br>".join(rows) + "</span>"

    def _augment_summary_html(self, title: str) -> str:
        """The detail pane for a collapsed augmentation summary node: the type, the
        installed Attributes, and where the Pick Attributes action leads."""
        group = next((g for g in build_augmentation_view(self._ruleset, self._char())
                      if g.title == title), None)
        if group is None:
            return f"<b>{html.escape(title)}</b>"
        installed = [e.attribute for e in group.entries if e.owned]
        parts = [f"<b>{html.escape(title)}</b>",
                 f"<span style='color:#b8b6b2'><b>Installed:</b> "
                 f"{', '.join(installed) if installed else 'None'}</span>",
                 "<span style='color:#9a9894'>Each installed copy occupies a Charm "
                 "Slot. Pick Attributes to install or remove one Attribute's copy."
                 "</span>"]
        return "<br>".join(parts)

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

    def _combos_label(self) -> str:
        """"Combos", or "Arrays" for a Charm-Slot splat.

        ⚠ The build matches the book's vocabulary deliberately (`charm_noun`, "Arrays"
        for Alchemicals), and `view.uses_arrays` is the one place that decides which
        word a character gets — this must never hardcode either."""
        return "Arrays" if viewmod.uses_arrays(self._ruleset, self._char()) \
            else "Combos"

    def _combos_page(self):
        """The Combos sub-tab. Still the webapp's surface — this is the placeholder in
        its new home, not a port of the tab."""
        page = QWidget()
        lay = QVBoxLayout(page)
        label = QLabel(f"The {self._combos_label()} tab is still on the webapp.")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet(f"color:{MUTED};")
        lay.addWidget(label)
        return page

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
        # Pinned BELOW the scroll area, not inside it: the Add button stays at the
        # panel bottom however many forms are listed. Inside the list it rode the
        # content block, and a short list was vertically centred in the viewport,
        # so the button drifted from bottom to middle on the first add.
        add = QPushButton("+ Add form")
        add.clicked.connect(self._add_form)
        lay.addWidget(add)
        self._rebuild_forms()
        return page

    def _add_form(self) -> None:
        self._char().animal_forms.append(AnimalForm())
        self._rebuild_forms()

    def _remove_form(self, index: int) -> None:
        del self._char().animal_forms[index]
        self._rebuild_forms()

    def _rebuild_forms(self) -> None:
        """Rebuild just the forms list (the totem field and the pinned Add button
        survive, so typing in either is not interrupted by an add/remove)."""
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
        # Top-anchor the list: without a trailing stretch a short list is vertically
        # centred in the scroll viewport, and the rows drift as forms are added.
        self._forms_lay.addStretch(1)

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

    # ---- Augmentation templates (Alchemical 'general') ---------------------- #
    # The 18 '<Type> Augmentation of <Attribute>' Charms stay distinct ids in the
    # data (other Charms name a specific one as a prerequisite) but render as TWO
    # groups — Transitory / Sustained — each with a per-Attribute picker, mirroring
    # the web picker's collapsed cards. `build_augmentation_view` supplies the rows;
    # the toggle is the same state change as a tree-node Charm buy.

    def _augment_page(self):
        """The Alchemical augmentations page: one card per type (Transitory /
        Sustained) with its installed-Attribute readout and a Pick-Attributes dialog."""
        char = self._char()
        pal = theme.palette(char.exalt_type)
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(4)
        head = QLabel("Augmentations")
        head.setStyleSheet(f"font-weight:bold; color:{accent_light(pal)};")
        lay.addWidget(head)
        cap = QLabel("Two templates, one per Attribute — each installed copy "
                     "occupies a Charm Slot.")
        cap.setWordWrap(True)
        cap.setStyleSheet(f"color:{MUTED};")
        lay.addWidget(cap)
        self._augment_lay = QVBoxLayout()
        lay.addLayout(self._augment_lay)
        lay.addStretch(1)
        self._rebuild_augments()
        return page

    def _rebuild_augments(self) -> None:
        """Rebuild the two type cards from a live read — install state changes with
        every toggle, so a stored group's `owned` flags go stale (the picker's
        stale-selection trap)."""
        self._clear_lay(self._augment_lay)
        for group in build_augmentation_view(self._ruleset, self._char()):
            self._augment_lay.addWidget(self._augment_card(group))

    def _augment_card(self, group):
        """One type card: title, the installed-Attribute readout, Pick Attributes."""
        char = self._char()
        pal = theme.palette(char.exalt_type)
        card = QFrame()
        card.setStyleSheet(
            f"QFrame {{ background:{CARD}; border:none; border-radius:6px; }}")
        card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(10, 8, 10, 10)
        card_lay.setSpacing(4)
        row = QHBoxLayout()
        title = QLabel(group.title)
        title.setStyleSheet(f"font-weight:bold; color:{accent_light(pal)};")
        row.addWidget(title)
        row.addStretch(1)
        pick = QPushButton("Pick Attributes")
        pick.clicked.connect(lambda _=None, g=group: self._open_augment_dialog(g))
        row.addWidget(pick)
        card_lay.addLayout(row)
        installed = [e.attribute for e in group.entries if e.owned]
        summary = QLabel(", ".join(installed) if installed else "None installed.")
        summary.setStyleSheet(f"color:{MUTED};")
        card_lay.addWidget(summary)
        return card

    def _open_augment_dialog(self, group) -> None:
        """A checkbox per Attribute for one type; toggling installs/removes it
        immediately (the same guards as a tree-node buy), then re-syncs the checkbox
        to the actual state — a refused toggle stays as it was."""
        char = self._char()
        dialog = QDialog(self)
        dialog.setWindowTitle(group.title)
        lay = QVBoxLayout(dialog)
        intro = QLabel("Each installed Augmentation occupies a Charm Slot.")
        intro.setStyleSheet(f"color:{MUTED};")
        lay.addWidget(intro)
        # Re-read the group so the checkbox states are live, not the card's snapshot.
        grp = next((g for g in build_augmentation_view(self._ruleset, char)
                    if g.title == group.title), group)
        locked = char.chargen_locked
        for e in grp.entries:
            row = QHBoxLayout()
            cb = QCheckBox(e.attribute)
            cb.setChecked(e.owned)
            # An owned copy is not droppable in play (undo on the Edit tab); an
            # unavailable one is locked behind its requirement, shown as the reason.
            if (locked and e.owned) or (not e.owned and not e.available):
                cb.setEnabled(False)
            cb.toggled.connect(lambda checked, cid=e.charm_id, c=cb:
                               self._toggle_augment(cid, c))
            row.addWidget(cb)
            if e.reason:
                reason = QLabel(e.reason)
                reason.setStyleSheet("color:#b45309; font-style:italic;")
                row.addWidget(reason, 1)
            else:
                row.addStretch(1)
            lay.addLayout(row)
        done = QPushButton("Done")
        done.clicked.connect(dialog.accept)
        lay.addWidget(done)
        dialog.exec()

    def _toggle_augment(self, charm_id: str, cb) -> None:
        """The state change is `_toggle_charm`'s (guards, notify, both sides of the
        lock); the checkbox is then re-synced to the truth, since a buy or remove can
        be refused — requirements, a dependent Charm, or an advancement error."""
        owned = charm_id in self._char().charms
        if cb.isChecked() == owned:
            return
        self._toggle_charm(charm_id)
        fresh = charm_id in self._char().charms
        cb.blockSignals(True)
        cb.setChecked(fresh)
        cb.blockSignals(False)
        self._rebuild_augments()

    # ---- Variant-menu packages (Ox-Body, Deadly Beastman Gifts) ------------ #
    # Neither Charm is toggleable: each purchase is a PACKAGE of picks landing in its
    # own character field, so the node's action button opens this instead of Learn.
    # ONE dialog for both, off `view.build_package_menu` — Ox-Body picks one variant
    # of two, Gifts pick 2-then-1 out of a prerequisite-chained roster, and the only
    # difference the widget sees is `menu.needed` and the picks' reasons.

    def _open_package_dialog(self, charm_id: str) -> None:
        dialog = self._build_package_dialog(charm_id)
        if dialog is not None:
            dialog.exec()

    def _build_package_dialog(self, charm_id: str):
        """Build the package chooser WITHOUT running it (`exec()` blocks a headless
        run, so this is the tested seam — the Gear and Advantages pages' shape).
        None when `charm_id` is not a variant-menu Charm.

        The dialog shows the packages already bought (each removable pre-lock), then a
        checkbox per pick, then Add/Buy. The selection is local and only reaches the
        character on confirm, so Cancel is a true cancel. Legality is not decided
        here — the picks' reasons come from `view.build_package_menu` and the purchase
        from `engine.charm_actions`, which refuses an over-cap or unaffordable buy.

        Handles for tests and for the rebuild: `.selection`, `.checks` (keyed by pick
        key — never index a `findChildren` list), `.confirm`, `.rebuild`."""
        first = build_package_menu(self._ruleset, self._char(), charm_id)
        if first is None:
            return None
        dialog = QDialog(self)
        dialog.setWindowTitle(first.name)
        dialog.setMinimumWidth(560)
        outer = QVBoxLayout(dialog)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        body = QVBoxLayout(inner)
        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)
        selection: list[str] = []
        # The live menu's shape, as one-element lists so the handlers below read what
        # the LAST rebuild computed rather than a snapshot taken before any purchase.
        menu_needed = [1]
        menu_kind = [""]
        sync_parts: list = []    # [the "Choose N" label, {pick key: its reason label}]

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(dialog.reject)
        confirm = QPushButton("Add")
        buttons.addWidget(cancel)
        buttons.addWidget(confirm)
        outer.addLayout(buttons)

        def flip(key: str, checked: bool) -> None:
            if checked:
                if menu_needed[0] == 1:
                    # A one-pick menu reads as radio buttons: picking replaces.
                    selection[:] = [key]
                elif key not in selection:
                    selection.append(key)
            else:
                if key in selection:
                    selection.remove(key)
                selection[:] = prune_package_selection(
                    self._ruleset, self._char(), charm_id, selection)
            # ⚠ SYNC, never rebuild. A pick changes no row's existence, and tearing
            # the rows down under the click sent the scroll area to the bottom —
            # deleting the focused checkbox hands focus on, and a QScrollArea scrolls
            # to whatever has it. Only a buy or a remove changes the dialog's shape.
            sync()

        def buy() -> None:
            if menu_kind[0] == "gift":
                ok = self._act(charm_actions.add_gift_purchase, self._ruleset,
                               self._char(), sorted(selection))
            else:
                ok = self._act(charm_actions.add_ox_body, self._ruleset,
                               self._char(), selection[0])
            if ok:
                self._refresh_current_tree()
                dialog.accept()

        def remove(index: int) -> None:
            action = (charm_actions.remove_gift_purchase if menu_kind[0] == "gift"
                      else charm_actions.remove_ox_body)
            if self._act(action, self._char(), index):
                selection.clear()
                self._refresh_current_tree()
                rebuild()

        def rebuild() -> None:
            # A remove changes the held list above the picks, so the rows really are
            # rebuilt here — hold the scroll where the reader left it.
            at = scroll.verticalScrollBar().value()
            QTimer.singleShot(0, lambda: scroll.verticalScrollBar().setValue(at))
            clear_layout(body)
            char = self._char()
            menu = build_package_menu(self._ruleset, char, charm_id, selection)
            if menu is None:                      # the Charm left the rule set
                dialog.reject()
                return
            menu_needed[0] = menu.needed
            menu_kind[0] = menu.kind
            pal = theme.palette(char.exalt_type)
            # The Charm's own description is NOT repeated here — it is already in the
            # detail pane this dialog opened from, and Deadly Beastman's runs eleven
            # lines, which pushes the picks themselves off the first screen.
            if menu.note:
                note = QLabel(menu.note)
                note.setWordWrap(True)
                note.setStyleSheet(f"color:{MUTED};")
                body.addWidget(note)
            # Which trait caps the purchases is per-splat data, never a literal:
            # Lunar Ox-Body counts Stamina where every other splat counts Endurance.
            head = QLabel(f"Bought {menu.bought} / {menu.cap}  ·  once per "
                          f"{menu.cap_unit} of {menu.cap_trait}")
            head.setStyleSheet(f"font-weight:bold; color:{accent_light(pal)};")
            body.addWidget(head)
            for h in menu.held:
                row = QHBoxLayout()
                row.addWidget(QLabel("• " + h.label), 1)
                if not char.chargen_locked:
                    drop = QPushButton("Remove")
                    drop.clicked.connect(lambda _=None, i=h.index: remove(i))
                    row.addWidget(drop)
                body.addLayout(row)
            if menu.bought >= menu.cap:
                over = QLabel(f"Raise {menu.cap_trait} to buy more." if menu.cap
                              else f"Needs at least 1 {menu.cap_unit} of "
                                   f"{menu.cap_trait}.")
                over.setStyleSheet(f"color:{MUTED};")
                body.addWidget(over)
            choose = QLabel("")
            choose.setStyleSheet("font-weight:bold;")
            body.addWidget(choose)
            dialog.checks = {}
            reasons = {}
            for pick in menu.picks:
                row = QHBoxLayout()
                cb = QCheckBox(pick.label)
                dialog.checks[pick.key] = cb
                cb.toggled.connect(lambda checked, k=pick.key: flip(k, checked))
                row.addWidget(cb)
                if pick.max_purchases > 1:
                    rep = QLabel(f"repeatable ×{pick.max_purchases}")
                    rep.setStyleSheet(f"color:{MUTED};")
                    row.addWidget(rep)
                # Built empty even when the pick is free right now: its reason appears
                # and disappears as the selection moves, and `sync` only sets text.
                why = QLabel("")
                why.setStyleSheet("color:#b45309; font-style:italic;")
                reasons[pick.key] = why
                row.addWidget(why)
                row.addStretch(1)
                body.addLayout(row)
                if pick.description:
                    text = QLabel(pick.description)
                    text.setWordWrap(True)
                    text.setContentsMargins(24, 0, 0, 4)
                    text.setStyleSheet(f"color:{MUTED};")
                    body.addWidget(text)
            body.addStretch(1)
            sync_parts[:] = [choose, reasons]
            sync()

        def sync() -> None:
            """Re-derive the pick rows in place from the current selection: what is
            ticked, what is now pickable, each row's reason, and the confirm button.
            Creates and destroys nothing, so the scroll position holds."""
            menu = build_package_menu(self._ruleset, self._char(), charm_id, selection)
            if menu is None:
                return
            choose, reasons = sync_parts
            choose.setText(f"Choose {menu.needed} — {len(selection)}/{menu.needed} "
                           f"selected")
            full = len(selection) >= menu.needed
            for pick in menu.picks:
                cb = dialog.checks[pick.key]
                picked = pick.key in selection
                cb.blockSignals(True)
                cb.setChecked(picked)
                cb.blockSignals(False)
                # A one-pick menu never disables an unpicked row — picking replaces —
                # so its variants stay clickable the way radio buttons would.
                blocked = bool(pick.reason) or (full and menu.needed > 1)
                cb.setEnabled(picked or not blocked)
                reasons[pick.key].setText(pick.reason)
            confirm.setText(f"Buy · {menu.price} XP" if menu.price else "Add")
            confirm.setEnabled(len(selection) == menu.needed)

        confirm.clicked.connect(buy)
        dialog.selection = selection
        dialog.confirm = confirm
        dialog.rebuild = rebuild
        rebuild()
        return dialog

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
            self._selected_augment = None
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
        player chooses one more (✚) from the other eight.

        A selectable list, like Spells: picking a Path fills the shared detail pane
        with its powers and the next-dot cost, the action button carries the buy
        price, and the rating is a dot track bound to the selected Path."""
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
        fav_row = QHBoxLayout()
        fav_row.addWidget(QLabel("Favoured Path"))
        self._build_favoured_picker(fav_row)
        note = QLabel("★ breed · ✚ your choice")
        note.setStyleSheet(f"color:{MUTED}; font-style:italic;")
        fav_row.addWidget(note)
        lay.addLayout(fav_row)
        self._paths_list = QListWidget()
        self._paths_list.currentItemChanged.connect(self._path_selected)
        lay.addWidget(self._paths_list, 1)
        self._paths_page_widget = page
        self._rebuild_paths_list()
        return page

    def _build_favoured_picker(self, fav_row) -> None:
        """The Favoured Path combo (a plain read-only label once locked): one choice
        from the eight non-breed Paths. ⚠ A saved `favored_path` that is one of the
        breed's two (an illegal-but-possible state) must still be an option — a combo
        whose value is absent from its options misbehaves — and never index
        `ruleset.paths[saved]` directly: a stale id from a catalogue rename would
        KeyError and take the whole tab down (the web's setdefault fallback)."""
        ruleset, char = self._ruleset, self._char()
        breed_el = engine_paths.breed_element(ruleset, char)
        breed_path_ids = {p.id for p in ruleset.paths.values() if p.element == breed_el}
        fav_opts = {p.id: p.name for p in ruleset.paths.values()
                    if p.id not in breed_path_ids}
        if char.chargen_locked:
            chosen = ruleset.paths.get(char.favored_path)
            lbl = QLabel(chosen.name if chosen else "—")
            lbl.setStyleSheet(f"color:{MUTED};")
            fav_row.addWidget(lbl, 1)
            return
        combo = QComboBox()
        combo.addItem("— none —", "")
        for pid, pname in fav_opts.items():
            combo.addItem(pname, pid)
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
        # ⚠ Capture the combo as a default arg — a bare `combo` in the closure is the
        # shared local, and a rebuild after the change must read THIS one.
        combo.currentIndexChanged.connect(lambda _, c=combo: (
            setattr(char, "favored_path", c.currentData() or ""),
            self._rebuild_paths_list()))
        self._fav_path_combo = combo
        fav_row.addWidget(combo, 1)

    def _rebuild_paths_list(self) -> None:
        """Rebuild the selectable Path list (★/✚ markers, element, held rating),
        re-selecting the current Path with signals blocked so no selection handler
        runs mid-rebuild. Clears the path pane when nothing survives (a reload)."""
        ruleset, char = self._ruleset, self._char()
        ratings = {p.path_id: p.rating for p in char.paths}
        breed_el = engine_paths.breed_element(ruleset, char)
        breed_path_ids = {p.id for p in ruleset.paths.values() if p.element == breed_el}
        self._paths_list.blockSignals(True)
        self._paths_list.clear()
        for path in ruleset.paths.values():
            marker = ("★ " if path.element and path.element == breed_el
                      else ("✚ " if path.id == char.favored_path else ""))
            rating = ratings.get(path.id, 0)
            text = f"{marker}{path.name} · {path.element_label}"
            if rating:
                text += f" — {rating}"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, path.id)
            self._paths_list.addItem(item)
            if path.id == self._selected_path:
                self._paths_list.setCurrentItem(item)
        self._paths_list.blockSignals(False)
        if not self._paths_list.currentItem():
            self._selected_path = None
            self._path_box.setVisible(False)
            self._update_action()

    def _path_selected(self, current, _prev) -> None:
        """A Path picked from the list: it owns the shared detail/action/rating pane —
        the Spells-list pattern."""
        if current is None:
            self._selected_path = None
            self._path_box.setVisible(False)
            self._update_action()
            return
        self._selected_path = current.data(Qt.UserRole)
        self._selected_node = None
        self._selected_spell = None
        self._selected_thaum = None
        self._selected_elemental = None
        self._selected_augment = None
        self._update_path_detail()
        self._update_action()

    def _update_path_detail(self) -> None:
        """Fill the detail pane and bind the rating dot track for the selected Path."""
        if self._selected_path is None:
            self._path_box.setVisible(False)
            return
        path = self._ruleset.paths.get(self._selected_path)
        if path is None:
            self._path_box.setVisible(False)
            return
        self._update_path_detail_text(path)
        self._path_box.setVisible(True)
        self._rebuild_path_track(self._selected_path)

    def _update_path_detail_text(self, path) -> None:
        """The detail pane for a Path: name, element, the granted powers (one per held
        dot), and the XP step for the next dot."""
        if path is None:
            self.detail.setHtml("<b>Unknown Path</b>")
            return
        char = self._char()
        rating = next((p.rating for p in char.paths if p.path_id == path.id), 0)
        parts = [f"<b>{html.escape(path.name)}</b>"]
        if path.element_label:
            parts.append(f"<span style='color:#b8b6b2'>{html.escape(path.element_label)}"
                         "</span>")
        if char.chargen_locked:
            if rating >= len(path.powers):
                parts.append("<span style='color:#9a9894'>at maximum</span>")
            else:
                cost = (costs.path_new_cost(self._ruleset, char, path.id)
                        if rating == 0 else
                        costs.path_step(self._ruleset, char, path.id, rating))
                parts.append(f"<span style='color:#b8b6b2'><b>Next dot:</b> {cost} XP"
                             "</span>")
        for power in path.powers[:rating]:
            line = (f"<b>· {html.escape(power.name)}</b> — "
                    f"{html.escape(power.duration)}")
            if power.text:
                line += f"<br><span style='color:#b8b6b2'>{html.escape(power.text)}</span>"
            parts.append(f"<span style='color:#b8b6b2'>{line}</span>")
        if not rating:
            parts.append("<span style='color:#9a9894'>Not yet learned.</span>")
        self.detail.setHtml("<br>".join(parts))

    def _rebuild_path_track(self, path_id: str) -> None:
        """A fresh DotTrack bound to one Path, dropped into the hidden rating row
        (which a selection shows). Rebuilt per selection — the DotTrack captures
        get/setv at construction, so it cannot be re-bound in place. Never called
        from inside a track's own handler; the track refreshes itself there."""
        while self._path_box_lay.count():
            item = self._path_box_lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.hide()
                w.setParent(None)
                w.deleteLater()
        char = self._char()
        locked = char.chargen_locked

        def get():
            return next((p.rating for p in char.paths if p.path_id == path_id), 0)

        def setv(rating):
            self._set_path_rating(path_id, rating)

        def buy(_target, current, wanted, refresh, _detail):
            self._path_buy(path_id, current, wanted, refresh)
            return True

        track = DotTrack(
            get, setv, 0, 6,
            accent=accent_light(theme.palette(char.exalt_type)),
            target=path_id if locked else None,
            buy=buy if locked else None,
            on_change=self._update_readout)
        self._path_box_lay.addWidget(track)

    def _set_path_rating(self, path_id: str, rating: int) -> None:
        """Pre-lock free setter into character.paths (validation via validate_chargen):
        a rating of 0 removes the Path, otherwise append or update the PathRating.
        Refreshes the list/detail/action/readout but NOT the dot track — this runs
        from inside the track's own click handler, which refreshes itself."""
        char = self._char()
        existing = next((p for p in char.paths if p.path_id == path_id), None)
        if rating <= 0:
            if existing:
                char.paths.remove(existing)
        elif existing:
            existing.rating = rating
        else:
            char.paths.append(PathRating(path_id=path_id, rating=rating))
        self._rebuild_paths_list()
        self._update_path_detail_text(self._ruleset.paths.get(path_id))
        self._update_action()
        self._update_readout()

    def _path_buy(self, path_id: str, current: int, wanted: int, refresh) -> None:
        """Post-lock XP raise/lower of a Path to `wanted` dots, via advancement (each
        dot its own XP step, PG p.176). `refresh` is the DotTrack's own pip refresh —
        the track must not be rebuilt from inside its own callback."""
        ruleset, char = self._ruleset, self._char()
        try:
            if wanted > current:
                if not any(p.path_id == path_id for p in char.paths):
                    advancement.learn_path(ruleset, char, path_id)
                for _ in range(current, wanted):
                    advancement.raise_path(ruleset, char, path_id)
            else:
                for _ in range(wanted, current):
                    advancement.lower_path(ruleset, char, path_id)
        except advancement.AdvancementError as ex:
            self._notify(str(ex), "warning")
        refresh()
        self._rebuild_paths_list()
        self._update_path_detail_text(ruleset.paths.get(path_id))
        self._update_action()
        self._update_readout()

    def _path_act(self) -> None:
        """The action button for a selected Path: one-dot raise — free from the
        chargen pool pre-lock, an XP step post-lock (a new Path is learned first).
        The dot track is rebuilt here (an external click, safe) so its pips agree."""
        path_id = self._selected_path
        if path_id is None:
            return
        char = self._char()
        rating = next((p.rating for p in char.paths if p.path_id == path_id), 0)
        try:
            if rating:
                if char.chargen_locked:
                    advancement.raise_path(self._ruleset, char, path_id)
                else:
                    self._set_path_rating(path_id, rating + 1)
            elif char.chargen_locked:
                advancement.learn_path(self._ruleset, char, path_id)
            else:
                self._set_path_rating(path_id, 1)
        except advancement.AdvancementError as ex:
            self._notify(str(ex), "warning")
            return
        self._rebuild_paths_list()
        self._update_path_detail()
        self._update_readout()

    def _rebuild_paths(self) -> None:
        """Full Paths refresh (reload / external change): rebuild the list and the
        selected Path's detail + dot track, and refresh the readout."""
        self._rebuild_paths_list()
        if self._selected_path is not None:
            self._update_path_detail()
        self._update_action()
        self._update_readout()

    def _art_selected(self, tree):
        """The Arts tree's selection: an Art or one of its specialties. Sets
        `_selected_thaum` to ("art", row) or ("art_specialty", art, spec) and shows
        the detail."""
        item = tree.currentItem()
        self._selected_node = None
        self._selected_spell = None
        self._selected_elemental = None
        self._selected_augment = None
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
            self._selected_augment = None
            self._update_action()
            return
        obj = item.data(Qt.UserRole)
        self._selected_node = None
        self._selected_elemental = None
        self._selected_augment = None
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
        self._selected_augment = None
        self._selected_path = None
        # Block tab signals across the rebuild: the QTabWidget fires currentChanged
        # during clear()/addTab (the qt-port.md construction trap), and with several
        # gated builders a mid-build signal could poke a panel that is only half
        # built. `_tab_changed()` below runs explicitly once the bar is complete.
        self.tabs.blockSignals(True)
        try:
            self.tabs.clear()
            # ⚠ Built fresh HERE, and deliberately not stored on the page: it is only
            # valid for this one rebuild, against this character and this catalogue.
            cache: dict = {}
            for group, label in (("abilities", "Charms"), ("styles", "Martial Arts"),
                                 ("arcanoi", "Arcanoi")):
                if trees_for(self._ruleset, char, char.exalt_type, group, cache):
                    self.tabs.addTab(self._tree_page(group, cache), label)
            if _cached(cache, "augmentation_category",
                       lambda: augmentation_category(self._ruleset, char)) is not None:
                self.tabs.addTab(self._augment_page(), "Augmentations")
            # Combos sit with the Charms they are assembled from (2026-08-21, the
            # human's call) — on the webapp this is a top-level tab, and the two were a
            # rail apart. ⚠ The show/hide rule came WITH it: `has_combos_tab` is false
            # for a splat that builds neither Combos nor Arrays (the dead may never
            # learn Combos — E:Ab p.234), and an empty tab answering every attempt with
            # a validation error is worse than no tab.
            if viewmod.has_combos_tab(self._ruleset, char):
                self.tabs.addTab(self._combos_page(), self._combos_label())
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
        # The Path rating row lives in the shared detail panel but belongs to the
        # Paths page alone — hide it (and drop the stale selection) on any other tab.
        if self.tabs.currentWidget() is not getattr(self, "_paths_page_widget", None):
            if self._selected_path is not None:
                self._selected_path = None
                self._path_box.setVisible(False)
        # A summary-node selection lives on a tree tab; drop it elsewhere.
        if self._selected_augment is not None:
            self._selected_augment = None
        self._update_action()
