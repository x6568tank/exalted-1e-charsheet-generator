"""exalted_builder/qt/charms.py — the Charms tab: the charm catalogue as Qt trees.

Input: a RuleSet and a Character from the shared context. Output: a tab widget with tree
tabs (Charms / Martial Arts / Arcanoi) and list panels (Spells, Thaumaturgy), over one
shared detail panel.

Mechanism: `build_charm_graph` supplies a QGraphicsScene of node items with rounded
corners, in a tidy-tree layout. Each node is centred over its children, and a wide level
divides into sub-rows. The edge routing avoids the nodes and the rails. The user pans with
ScrollHandDrag, and zooms with the wheel in proportion to the wheel delta. Group membership
agrees with `picker._group_of`. `ui.theme.palette` supplies the node colours. `reload()`
rebuilds the scene for the character in ctx. Thus a different splat replaces the full set
of groups.
"""

from __future__ import annotations

import html
import math
from collections import defaultdict
from dataclasses import replace

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
from exalted_builder.qt.combos import CombosPage
from exalted_builder.qt.editor import DotTrack
from exalted_builder.qt.layout import clear_layout
from exalted_builder.models.rules import Orientation
from exalted_builder.ui import theme

from .theme import CARD, CUSTOM, MUTED, TREE, accent as accent_light
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

    ⚠ The cache belongs to ONE build. Never store it on the page, and never key it on the
    RuleSet. `rules_db.reload_custom_layer` changes `ruleset.charms` IN PLACE. Thus a new
    homebrew Charm appears on every page that holds that object. A cache that stays after
    one build then supplies a catalogue that the user has changed.
    """
    if cache is None:
        return compute()
    if key not in cache:
        cache[key] = compute()
    return cache[key]


def _arcanoi_categories(ruleset, cache=None):
    """The category names whose Charms are Arcanoi. They are keyed on a Virtue. ⚠ They are
    not the spirit Charms. A spirit Charm uses the same `min_virtue` axis, and it is a
    different class with the `exalt_type` "Spirit"."""
    return _cached(cache, "arcanoi_categories", lambda: {
        c.category for c in ruleset.charms.values()
        if c.min_virtue and c.exalt_type != "Spirit"})


def group_of(category, ruleset, cache=None):
    """The picker group a category belongs to: 'styles' / 'arcanoi' / 'abilities'.

    ⚠ This function must agree with `picker._group_of`. A prefix names a martial-arts
    category. A category is an arcanos when its base name, before a `:virtue` part, is one
    of the Virtue-keyed categories that are not spirit categories. Every other category is
    an ability Charm."""
    if category.startswith("martial_arts:"):
        return "styles"
    return ("arcanoi" if category.split(":", 1)[0] in _arcanoi_categories(ruleset, cache)
            else "abilities")


def trees_for(ruleset, character, splat, group, cache=None):
    """[(category_key, node_count)] for one splat's page in `group`, biggest first.

    `cache` is an optional memo for one build. The other calls in the same rebuild share it
    (see `_cached`). Each helper below is a pure function of the ruleset, and the
    augmentation category also reads the splat of the character. ⚠ Each helper SCANS the
    full Charm catalogue, and one rebuild calls them thousands of times.
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


def splats_for(ruleset, character, group, cache=None):
    """[exalt_type] the Splat dropdown offers on one tree group: the character's own
    always first, then every other Exalt type with Charms in `group` while the caste
    generalist privilege is open (core p.127).

    One entry means the dropdown has nothing to choose and the caller hides it.

    ⚠ Scan the catalogue. Do not call `trees_for` for each splat. `trees_for` builds the
    graph of every category. One call for each Exalt type in each group lays out the full
    Charm tree of every splat, and it does that to fill a dropdown.
    """
    own = character.exalt_type
    if not validate.foreign_charms_open(ruleset, character):
        return [own]
    found: set[str] = set()
    for c in ruleset.charms.values():
        if not c.exalt_type or c.exalt_type == own:
            continue
        if not charm_on_splat_page(ruleset, character, c, c.exalt_type):
            continue
        split = _cached(cache, ("virtue_split", c.category),
                        lambda cat=c.category: virtue_split(ruleset, cat))
        if any(group_of(key, ruleset, cache) == group for key in (split or [c.category])):
            found.add(c.exalt_type)
    return [own] + sorted(found)


def _collapse_augment_nodes(ruleset, character, graph, cache=None):
    """Collapse the Alchemical augmentation templates into ONE node for each type,
    Transitory and Sustained, and route the prerequisite edges to those nodes. ⚠ The 18
    '<Type> Augmentation of <Attribute>' ids stay separate in the data, because other Charms
    name one of them as a prerequisite. The tree shows two summary nodes, and a selection on
    one offers 'Pick Attributes'. Without this collapse, eighteen unconnected nodes appear
    in every tree that depends on them. For example, a close-combat Charm names 'Transitory
    Augmentation of Dexterity'."""
    # ⚠ This function is the slow one. It reads every Charm through `charm_matches_splat`,
    # and one rebuild collapses approximately 90 trees. Without the cache, one page build
    # makes 180,000 calls.
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
    """The rich-text detail panel for a CharmDetail, a Spell or a Thaumaturgy entry. It
    shows the name, the trait lines (the requirement, the prerequisites, the cost, the
    circle) and the description. The `price` of a Thaumaturgy row appears as a Cost line.
    Most printed specialties have no description, thus the price fills the panel."""
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
    # ⚠ Show the regional versions that the character KNOWS. A ritual row and a formula row
    # carry this information, and no other entry does. The "add another version" price uses
    # it (p.124).
    known = getattr(obj, "orientations", None)
    if known:
        lines.append(f"Known in: {html.escape(', '.join(known))}")
    # ⚠ The SHEET records a narrowing (p.127). Thus the program must show a narrowed aspect
    # that the character owns. The user buys it at half price, and without this line it
    # reads as an ordinary aspect. ⚠ Put this fact in the panel. A tree label becomes stale
    # after a purchase, because no code rebuilds it.
    if getattr(obj, "narrowed", False):
        lines.append("Narrowed — a further-limited aspect at half cost (p.127)")
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

    # ⚠ A root is a LEAF root only when no graph edge leaves it. A root whose graph-children
    # selected a different primary parent still has edges to draw. Thus it must stay in the
    # forest. If you read `children`, which is the primary tree, such a root moves to the
    # bottom row, and its edges become long lines back into the forest.
    graph_children = {p for p, _ in graph.edges}
    tree_roots = [r for r in roots if r in graph_children]
    leaf_roots = [r for r in roots if r not in graph_children]
    # Group the roots by the children that they feed. Thus a tree where many entry Charms
    # go to one form, for example Prismatic Arrangement, reads as a group. The shared form
    # goes below its first feeder, and the feeders are next to each other. Thus the other
    # feeder edges are short, and they do not cross the full group.
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
    """True when the segment (bx,by)-(ex,ey) crosses the rect. This function tests points
    along the segment. It does not calculate the exact intersection."""
    for i in range(21):
        f = i / 20
        px = bx + (ex - bx) * f
        py = by + (ey - by) * f
        if l <= px <= r and t <= py <= b:
            return True
    return False


def _rect_entry(px, py, qx, qy, l, t, r, b):
    """The first point where the segment (px,py)-(qx,qy) enters the rect. The start must be
    outside the rect, and the end must be on the rect or inside it. The method is the entry
    parameter of the Liang-Barsky algorithm."""
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

    ⚠ Move the tip from the ENTRY point along the OUTWARD NORMAL of the entry edge. Do not
    move it along the direction of the edge. A shallow diagonal that moves along its own
    direction keeps the arrow at the height of the box, and the node then covers half of the
    arrow. With a `margin` that is larger than the half-width of the arrow, the full
    triangle is outside the box. The tip is `margin` out along the normal, and the base is
    `margin + L·|n·u|` out."""
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
    """A polyline from `start` to `end` that avoids `boxes` and `rails`. `boxes` are the
    node rects, and this function excludes the two endpoints. `rails` are the horizontal
    runs that the detours already use. ⚠ A new detour must not use an existing rail. Thus a
    parallel detour takes an offset, and the two do not overlap.

    The line is straight when it avoids everything. In any other case, the route is a U
    along the side of the band of boxes that the straight line crosses. The order of the
    attempts is: left, then right, then rail offsets up and down. This function moves the
    last point away from the child (`target`), thus the arrowhead is clear of the node. It
    returns the straight line when it finds no clear detour."""
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

    `_tree_positions` gives the position of each node. Each node is centred over its
    children, and the leaves pack by their own width. An edge runs from the bottom centre of
    each prerequisite in the graph to the top centre of the node. The route avoids each node
    box that the straight path crosses."""
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
    """The Charm tree of one category. It fills its scene again from `build_charm_graph`.

    `graph` is the CharmGraph that this view rendered last. The detail panel and the tests
    read it. `category_combo` and `splat_combo` are the dropdowns of the owning tab, and
    `reload_tree` reads them."""

    def __init__(self, ruleset, character, cache=None):
        super().__init__()
        self._ruleset = ruleset
        self._character = character
        # The memo of the owning rebuild (see `_cached`). The view can hold it for its full
        # life, because `_tree_page` builds a NEW view on each reload. Thus the two have the
        # same life. ⚠ Put only splat-derived values in this memo. Never put a value that
        # depends on the Charms that the character OWNS. A purchase changes that set while
        # the view exists.
        self._cache = cache
        self.graph = None
        self.category_combo = None
        self.splat_combo = None
        self.style_head = None          # the martial-arts style panel, when the tab
        self.style_body = None          # has one — see CharmsPage._style_panel
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

    def reload_tree(self):
        """Re-render from the two dropdowns this view owns.

        ⚠ This method is the ONE place that reads the (category, splat) pair. Do not pass
        `character.exalt_type` to `show_tree`. A call site on the purchase path that does
        that shows no fault until the user buys something. A tree of a different splat then
        changes back to the splat of the character on the next click."""
        category = (self.category_combo.currentData()
                    if self.category_combo is not None else "")
        splat = self.splat_combo.currentData() if self.splat_combo is not None else ""
        self.show_tree(category or "", splat or self._character.exalt_type)

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
        # Fit the scene at the smallest zoom that shows every node. ⚠ The viewport of a new
        # tab starts at 0x0, and it grows in stages during the layout. Thus one immediate
        # `fitInView` runs against a small size and leaves the tree at a small zoom. Defer
        # the fit, and fit again until the viewport size stops to change. Then leave the
        # transform to the user.
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
            # The layout completes over several event cycles. Fit again a limited number of
            # times, thus the transform reaches the final viewport size.
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
        # Fit again when the view changes size, for example on a window resize or a
        # splitter drag. Thus the tree fills the current view. ⚠ A wheel zoom makes the
        # scrollbars appear, which makes the VIEW smaller for several frames and sends
        # resize events. A fit on those events removes the zoom. Thus skip a resize while
        # the user turns the wheel. The deferred fit sets the initial size.
        if self._just_zoomed or event.size() == event.oldSize():
            return
        if self.graph is not None and self._scene.items():
            self.fitInView(self._scene.sceneRect(), Qt.KeepAspectRatio)

    def _clear_zoom_flag(self):
        self._just_zoomed = False

    def wheelEvent(self, event):
        # Zoom in proportion to the delta. One full mouse notch (delta 120) scales by
        # approximately 1.2. The small smooth-scroll deltas of a trackpad scale less. Thus
        # the same physical scroll distance gives the same zoom on each device. ⚠ Do not use
        # a fixed factor for each event. A trackpad then zooms much faster than a mouse.
        # ⚠ A Wayland touchpad sends `pixelDelta` only. Read that value as a fallback, and
        # treat a delta of zero as no action. Do not treat it as "scroll down".
        delta = event.angleDelta().y()
        if delta == 0:
            delta = event.pixelDelta().y()
        if delta == 0:
            event.accept()
            return
        # A zoom makes the scrollbars appear. That makes the view smaller and sends resize
        # events for several frames. ⚠ A fit on those events removes the zoom. Set this flag,
        # thus `resizeEvent` ignores a resize until the wheel action ends.
        self._just_zoomed = True
        QTimer.singleShot(250, self._clear_zoom_flag)
        factor = 1.0015 ** delta
        if 0.05 <= self.transform().m11() * factor <= 10:
            self.scale(factor, factor)
        event.accept()


class CappedCombo(QComboBox):
    """QComboBox whose popup is capped at `max_rows` rows.

    ⚠ This Qt build ignores `setMaxVisibleItems` for the HEIGHT of the popup. The popup
    takes the height of the screen, with that property set and with a maximum height on the
    view. Thus this class applies the limit to the popup window after it opens."""

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

    Build the tabs for each character, and build a tab only when that splat has content in
    the group. A Solar gets Charms, Martial Arts, Spells and Thaumaturgy, and no Arcanoi. A
    Ghost gets Arcanoi and Thaumaturgy, and no Charms. Each tree tab owns its category
    dropdown and its tree view. The shared detail panel shows the selection of the active
    tab. `reload()` rebuilds the full set of tabs for the character in ctx."""

    def __init__(self, ruleset, ctx, *, notify=None, on_change=None, parent=None):
        super().__init__(parent)
        self._ruleset = ruleset
        self._ctx = ctx
        self._notify = notify or (lambda text, kind="info": None)
        # ⚠ A purchase on THIS tab also moves the readout bar of the shell. A Charm above
        # the free pool costs bonus points, and each action here is a purchase.
        # `_update_readout` sends this signal. Every purchase path passes through it.
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
        self._detail_panel = detail_panel
        dp = QVBoxLayout(detail_panel)
        dp.setContentsMargins(0, 0, 0, 0)
        dp.setSpacing(4)
        act_row = QHBoxLayout()
        act_row.addWidget(self.action_btn, 1)
        # `action_btn` cannot show one state: the character owns the Charm, and the count is
        # below the limit. That button says Remove, and a repeatable Charm needs one MORE
        # copy. Thus this state has its own button. See `_update_action`.
        self.again_btn = QPushButton("Add another")
        self.again_btn.setVisible(False)
        self.again_btn.clicked.connect(self._add_another)
        act_row.addWidget(self.again_btn)
        # The regional version of a ritual or a formula (p.124). Enable this control only
        # when the user selects a ritual or a formula for its first purchase.
        self._orientation_combo = QComboBox()
        for o in Orientation:
            self._orientation_combo.addItem(o.value, o)
        self._orientation_combo.setVisible(False)   # only a ritual/formula buy shows it
        self._orientation_combo.setToolTip("Regional version of a ritual or formula")
        act_row.addWidget(self._orientation_combo)
        # ⚠ Use a SECOND control. Do not re-use `action_btn`. The button of a ritual that the
        # character owns says Drop. To know the ritual in one more region is a different
        # purchase at a different price: one flat point for each region (p.124). `again_btn`
        # has the same shape next to a repeatable Charm. Without this control, the user
        # reaches the combo box before the first purchase only, and cannot buy a further
        # version.
        self._orientation_btn = QPushButton("Add version")
        self._orientation_btn.setVisible(False)
        self._orientation_btn.clicked.connect(self._add_orientation)
        act_row.addWidget(self._orientation_btn)
        # The narrowing of the aspect of an Art. It applies to Summoning only (p.127). The
        # user selects it BEFORE the purchase, and the purchase stores it
        # (`ArtSpecialty.narrowed`). Thus it is a checkbox next to the button. ⚠ No code
        # applies it after the purchase.
        self._narrow_check = QCheckBox("narrow")
        self._narrow_offered = False
        self._narrow_check.setVisible(False)
        self._narrow_check.setToolTip(
            "Further limit this aspect (e.g. 'War Gods') for half cost, noted on the "
            "sheet (p.127).")
        self._narrow_check.toggled.connect(
            lambda _=False: (self._show_thaum_detail(), self._update_action()))
        act_row.addWidget(self._narrow_check)
        # Before the lock, a Science can go DOWN and up. Crafts and Colleges have the same
        # usability rule. `action_btn` says Raise, thus the decrease needs its own button.
        self._lower_btn = QPushButton("Lower")
        self._lower_btn.setVisible(False)
        self._lower_btn.setToolTip("Step this Science back down (chargen only)")
        self._lower_btn.clicked.connect(self._lower_science)
        act_row.addWidget(self._lower_btn)
        dp.addLayout(act_row)
        # The dot track of the Path rating. Show it only while a Path is selected on the
        # Paths page, which connects the track. Hide it for every other selection.
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
        # Put the submodules (Alchemical p.89) BELOW the detail text, not in it. Each row
        # makes a purchase, thus each row needs a button, and the detail pane is a
        # QTextBrowser. Hide this panel for a Charm that has no submodule. Most Charms have
        # none.
        self._submodule_box = QWidget()
        self._submodule_lay = QVBoxLayout(self._submodule_box)
        self._submodule_lay.setContentsMargins(0, 0, 0, 0)
        self._submodule_lay.setSpacing(2)
        self._submodule_box.setVisible(False)
        dp.addWidget(self._submodule_box)

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
        """Empty `lay`, and detach every descendant immediately. ⚠ Call `qt/layout.py`.
        That module holds the two traps in this operation."""
        clear_layout(lay)

    # ------------------------------------------------------------------ #
    # buying (the picker's toggle, ported) — the one thing the spike left out
    # ------------------------------------------------------------------ #

    def _chargen_pick_bp(self, *, charm_id=None, spell_id=None) -> int:
        """The bonus-point price of ONE more Charm or Spell at chargen, after the free pool
        is full. Returns 0 while the pool has space.

        ⚠ The accounting takes the most expensive picks first. The pool covers those picks.
        Thus the price of one more pick is the difference of the pool sum. It is not the
        rate of that pick. A new cheap pick can go below the pool and cost nothing, and an
        expensive pick can remove a cheaper pick from the pool."""
        ruleset, char = self._ruleset, self._char()
        if charm_id is not None and charm_id in char.charms:
            return 0
        if spell_id is not None and spell_id in char.spells:
            return 0
        b = validate.effective_budgets(ruleset, char)
        bp_costs = ruleset.bonus_costs_for(char.exalt_type, char.origin,
                                           char.upbringing)
        occult_cf = AbilityName.OCCULT in validate.caste_favored_abilities(ruleset, char)
        spell_rate = bp_costs.charm_favored_caste if occult_cf else bp_costs.charm

        def _pool_total(stage: bool) -> int:
            """The pool sum, with or without the candidate. This function runs the
            enumeration of the picker. Thus it prices the candidate with its favoured flags
            and with each Calling, Immaculate, martial-arts or magic ladder that applies.

            ⚠ Calculate the SIZE of the free pool inside this function, with the candidate
            in place. Do not calculate it one time outside. The pool of a Dragon-Blooded is
            7 on the standard path and 5 on the Immaculate path, and the pick that changes
            the path changes its own pool size. A `free` value from before the candidate
            cuts the pool at 7 when it is 5. The two Charms that the change removed then
            count as free, and the button shows 7 BP for a pick that costs 21."""
            if stage:
                if charm_id is not None:
                    char.charms.append(charm_id)
                else:
                    char.spells.append(spell_id)
            try:
                free = (b.immaculate_charm_count
                        if validate.immaculate_martial_artist(ruleset, char)
                        else b.charm_count)
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
        """Update the Learn/Remove button for the selection: a Charm tree node, a spell row
        or a Thaumaturgy entry. With no selection, the button is disabled. For a pick that
        the character owns, it says 'Remove'. In any other case it says 'Learn', and for a
        Science it says 'Raise'. The Learn side carries the price. A Charm pick at chargen
        is free. An XP purchase and every Thaumaturgy purchase show their cost."""
        char = self._char()
        self._orientation_combo.setVisible(False)      # a ritual/formula buy re-shows it
        self._orientation_btn.setVisible(False)
        self._narrow_check.setVisible(False)
        self._narrow_offered = False
        self._lower_btn.setVisible(False)
        # ⚠ Hide these controls HERE, not in each branch. `_update_action` has many early
        # returns. A button that stays visible from the previous selection offers "Add
        # another" for the current selection. Remove the submodule panel for the same
        # reason. Its rows buy against a `charm_id` from the time when the code built them.
        self.again_btn.setVisible(False)
        self._rebuild_submodules(self._selected_node)
        if self._selected_node is not None:
            cid = self._selected_node
            charm = self._ruleset.charms.get(cid)
            if charm is None:
                self.action_btn.setEnabled(False)
                self.action_btn.setText("Select an entry…")
                return
            # The user buys a variant-menu Charm as a PACKAGE. It has no toggle.
            # `charm_actions.variant_menu_reason` refuses a toggle. Thus this button opens
            # the chooser. It must not offer Learn.
            menu = build_package_menu(self._ruleset, char, cid)
            if menu is not None:
                verb = {"gift": "Choose Gifts…",
                        "variant": "Choose a version…"}.get(menu.kind,
                                                            "Choose a package…")
                self.action_btn.setText(
                    f"{verb} — {menu.price} XP each" if menu.price else verb)
                self.action_btn.setEnabled(True)
                self.action_btn.setToolTip("")
                return
            owned = cid in char.charms
            label = f"Remove {charm.name}" if owned else f"Learn {charm.name}"
            blocked = ""
            if not owned:
                if char.chargen_locked:
                    label += f" — {costs.charm_cost(self._ruleset, char, charm)} XP"
                else:
                    bp = self._chargen_pick_bp(charm_id=cid)
                    if bp:
                        label += f" — {bp} BP"
            else:
                # A repeatable Charm is owned and not full while its copies stay below the
                # trait limit. Examples: the Mountain Folk Essence Satiation Method and
                # Stone-Still Lungs (CH6 pp.245-246). Offer this button on BOTH sides of the
                # lock. After the lock, the button shows the XP price, as Learn does.
                cap = validate._repeatable_purchase_cap(charm, char)
                held = char.charms.count(cid)
                if cap and held < cap:
                    self.again_btn.setVisible(True)
                    self.again_btn.setText(
                        f"Add another — {costs.charm_cost(self._ruleset, char, charm)} XP"
                        if char.chargen_locked else "Add another")
                    self.again_btn.setToolTip(f"{held} of {cap} copies")
                # ⚠ After the lock, "Remove" applies to the LAST XP purchase only. The log
                # is append-only, and an undo takes the last entry (decision 0004). Thus
                # there is no correct method to remove any other Charm. Disable the button
                # in that state. An enabled button that refuses every click is a defect.
                blocked = charm_actions.undo_charm_reason(char, cid)
            self.action_btn.setText(label)
            self.action_btn.setEnabled(not blocked)
            self.action_btn.setToolTip(blocked)
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
                # ⚠ Show this control at chargen only. `lower_thaum_science` does not check
                # the lock. It is the free half of the dot track before the lock. After the
                # lock, a rating decreases through an undo in the XP ledger, not here.
                self._lower_btn.setVisible(bool(row.rating)
                                           and not char.chargen_locked)
            elif kind == "art_specialty":
                art, spec = self._selected_thaum[1], self._selected_thaum[2]
                # A narrowing applies to Summoning only. The user selects it before the
                # purchase, and it cannot change after that. Thus show this box only on a
                # PRINTED aspect that the character does not own, in an Art that permits it.
                offer_narrow = (art.allows_narrowing and not spec.owned
                                and spec.printed)
                # ⚠ Store this state as a FLAG. Never read it back from the widget with
                # `isVisible()`. A widget on a page that the shell never showed reports
                # invisible, whatever value you set. Thus the purchase stops the narrowing
                # in every headless test, and on any tab that the user has not opened.
                self._narrow_offered = offer_narrow
                self._narrow_check.setVisible(offer_narrow)
                if not offer_narrow:
                    self._narrow_check.setChecked(False)
                price = (spec.narrowed_price if offer_narrow
                         and self._narrow_check.isChecked() else spec.price)
                label = f"Drop {spec.name}" if spec.owned else \
                    f"Learn {spec.name} — {price} {currency}"
                self.action_btn.setText(label)
                self.action_btn.setEnabled(True)
            else:
                row = self._selected_thaum[1]
                label = f"Drop {row.name}" if row.owned else \
                    f"Learn {row.name} — {row.price} {currency}"
                self.action_btn.setText(label)
                self.action_btn.setEnabled(True)
                self._sync_orientation(row, currency)
            return
        if self._selected_elemental is not None:
            # ⚠ Read the owned state from the character. Never read it from a stored row. A
            # rebuild of the list leaves the owned flag of a row at an old value.
            char = self._char()
            row = next((r for r in build_elemental_power_picker(self._ruleset, char).powers
                        if r.id == self._selected_elemental), None)
            if row is None:
                self.action_btn.setEnabled(False)
                self.action_btn.setText("Select an entry…")
                return
            if self._selected_elemental in char.elemental_powers:
                if char.chargen_locked:
                    # In play, the user cannot drop a power that the character knows. The
                    # undo is on the Edit tab. The picker shows a disabled check icon.
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
                # An Elemental Power at chargen costs bonus points (PG p.68). The button
                # shows the BP price on both sides of the lock, as the Thaumaturgy rows do.
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

    def _sync_orientation(self, row, currency: str) -> None:
        """Fill the orientation combo for the selected ritual/formula and show the
        control that applies.

        When the character does not own the entry, the combo holds every region, and it
        selects the region of the FIRST purchase. When the character owns the entry, the
        combo holds the regions that the character does not have, next to a button that buys
        one more (p.124). When the character owns all five regions, this method shows
        neither control, because there is nothing to buy.
        """
        offered = [o for o in Orientation
                   if not row.owned or o.value not in row.orientations]
        self._orientation_combo.clear()
        for o in offered:
            self._orientation_combo.addItem(o.value, o)
        # ⚠ Set the default to REALM where the list offers it. Do not use the first member
        # of the enum. The picker of the webapp uses Realm as its default. In enum order,
        # this combo buys a NORTHERN version by default. That is the same purchase at the
        # same price, in a tradition that the user did not select.
        if offered:
            self._orientation_combo.setCurrentIndex(
                offered.index(Orientation.REALM) if Orientation.REALM in offered else 0)
        self._orientation_combo.setVisible(bool(offered))
        self._orientation_combo.setEnabled(bool(offered))
        self._orientation_combo.setToolTip(
            "Which regional version to learn it in"
            if not row.owned else
            f"Another regional version — {row.orientation_price} {currency}")
        self._orientation_btn.setVisible(row.owned and bool(offered))
        self._orientation_btn.setText(
            f"Add version — {row.orientation_price} {currency}")

    def _add_orientation(self) -> None:
        """Buy one further regional version of the selected ritual or formula."""
        if self._selected_thaum is None:
            return
        kind, row = self._selected_thaum[0], self._selected_thaum[1]
        # ⚠ PySide6 stores the str value of the enum, not the member. Build the member
        # again, as `_toggle_thaum` does. This value is not a key into a dict that this
        # code built. Never read a key back from a widget.
        raw = self._orientation_combo.currentData() or Orientation.REALM.value
        try:
            msg = thaum_actions.add_thaum_orientation(
                self._ruleset, self._char(), kind, row.key, Orientation(raw))
        except advancement.AdvancementError as ex:
            self._notify(str(ex), "warning")
            return
        self._notify(msg, "info")
        self._refresh_current_tree()

    def _lower_science(self) -> None:
        """Decrease the selected Science by one dot. This control operates at chargen."""
        if self._selected_thaum is None or self._selected_thaum[0] != "science":
            return
        row = self._selected_thaum[1]
        try:
            msg = thaum_actions.lower_thaum_science(self._ruleset, self._char(), row.id)
        except advancement.AdvancementError as ex:
            self._notify(str(ex), "warning")
            return
        self._notify(msg, "info")
        self._refresh_current_tree()

    def _add_custom_specialty(self, name: str) -> None:
        """Create a specialty for the selected Art. Page 126 permits this. It is the same
        purchase at the same rate as a printed aspect.

        ⚠ Never narrow this specialty. A narrowing limits a PRINTED aspect (p.127). A
        specialty that the user writes already has the limits that the user gave it.
        """
        art = self._selected_art()
        if art is None:
            self._notify("Select an Art first.", "warning")
            return
        try:
            msg = thaum_actions.buy_thaum_specialty(self._ruleset, self._char(),
                                                    art.id, name)
        except advancement.AdvancementError as ex:
            self._notify(str(ex), "warning")
            return
        self._notify(msg, "info")
        # This action adds a row to the tree, and only a rebuilt page holds that row.
        # `_add_custom_ritual` reloads for the same reason.
        self.reload()
        self._update_readout()

    def _selected_art(self):
        """The Art of the selection. It is the Art itself, or the parent Art of a selected
        specialty. Returns None when the selection is neither."""
        if self._selected_thaum is None:
            return None
        kind = self._selected_thaum[0]
        if kind in ("art", "art_specialty"):
            return self._selected_thaum[1]
        return None

    def _add_custom_ritual(self, name: str, level: int) -> None:
        """Write a ritual for THIS character only. It uses the inline `RitualEntry` path.
        The chapter prints five rituals and expects more (p.148).

        ⚠ This path is not the Rituals library of the Custom tab. Keep both (human's
        ruling). This path makes a ritual during a session. The library path makes a ritual
        that every character can use, and it joins the catalogue.
        """
        try:
            raw = self._orientation_combo.currentData() or Orientation.REALM.value
            msg = thaum_actions.buy_custom_ritual(
                self._ruleset, self._char(), name, level, Orientation(raw))
        except advancement.AdvancementError as ex:
            self._notify(str(ex), "warning")
            return
        self._notify(msg, "info")
        # A new entry adds a ROW, and only a rebuilt page holds that row. A purchase is
        # different: the row exists, and `_refresh_current_tree` finds it again.
        self.reload()
        self._update_readout()

    def _toggle_thaum(self, kind: str, *rest) -> None:
        """Buy or drop a Thaumaturgy entry through `engine.thaum_actions`. An Art, a ritual
        and a formula toggle. A Science raises by one dot. A specialty of an Art toggles
        below its parent Art. The action functions change the state, and they raise on a
        refusal. This method shows the outcome only."""
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
                           ruleset, char, art.id, spec.name,
                           narrowed=self._narrow_offered
                           and self._narrow_check.isChecked()))
            elif kind == "science":
                row = rest[0]
                msg = thaum_actions.raise_thaum_science(ruleset, char, row.id)
            elif rest[0].owned:
                row = rest[0]
                msg = thaum_actions.drop_thaum_entry(char, kind, row.key)
            else:
                row = rest[0]
                # ⚠ PySide6 stores the str value of the enum, not the member. Build it again.
                raw = self._orientation_combo.currentData() or Orientation.REALM.value
                msg = thaum_actions.buy_thaum_entry(
                    ruleset, char, kind, row.key, Orientation(raw))
        except advancement.AdvancementError as ex:
            self._notify(str(ex), "warning")
            return
        self._notify(msg, "info")
        self._refresh_current_tree()

    def _act(self, action, *args) -> bool:
        """Run a dispatcher in `engine.charm_actions`, and show its result. Show the return
        message, or show its AdvancementError as a warning. Returns True when the character
        changed. Thus the caller can skip its repaint."""
        try:
            self._notify(action(*args), "info")
        except advancement.AdvancementError as ex:
            self._notify(str(ex), "warning")
            return False
        return True

    def _toggle_charm(self, charm_id: str) -> None:
        """A node click: learn an unowned Charm, drop an owned one, buy post-lock.

        ⚠ Dispatch through `engine.charm_actions.toggle_charm`. Keep the logic there. The
        web picker uses the SAME function. With two copies, they become different. For
        example, the variant menu of Ox-Body reached the web copy only, and this copy then
        wrote the id of the package Charm into `char.charms`. `variant_menu_reason` refuses
        that here. Do not add a branch in the widget."""
        char = self._char()
        # ⚠ After the lock, the XP ledger removes a Charm that the character owns. Do not
        # drop it here. `toggle_charm` then tries to LEARN it again.
        if char.chargen_locked and charm_id in char.charms:
            if self._act(charm_actions.undo_charm, self._ruleset, char, charm_id):
                self._refresh_current_tree()
            return
        if self._act(charm_actions.toggle_charm, self._ruleset, char, charm_id):
            self._refresh_current_tree()

    def _rebuild_submodules(self, charm_id) -> None:
        """Rebuild the submodule rows of the selected Charm (Alchemical p.89). Hide the
        panel when the Charm has no submodule. On most splats, every Charm has none.

        Each row shows the name, the price and the Essence or Attribute minimum of that
        submodule, above an Add, Buy or Remove button. The price follows the lock: bonus
        points at chargen, and experience after the lock. The page prints both."""
        clear_layout(self._submodule_lay)
        rows = (viewmod.build_submodule_rows(self._ruleset, self._char(), charm_id)
                if charm_id else [])
        self._submodule_box.setVisible(bool(rows))
        if not rows:
            return
        char = self._char()
        pal = theme.palette(char.exalt_type)
        head = QLabel("SUBMODULES")
        head.setStyleSheet(f"color:{accent_light(pal)}; font-weight:bold; "
                           f"letter-spacing:1px;")
        self._submodule_lay.addWidget(head)
        for r in rows:
            self._submodule_lay.addWidget(self._submodule_row(r, char))

    def _submodule_row(self, r, char) -> QWidget:
        """One submodule: its text block over the button its state calls for."""
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 2, 0, 2)
        lay.setSpacing(1)
        top = QHBoxLayout()
        name = QLabel(r.name)
        name.setStyleSheet("font-weight:600;")
        top.addWidget(name, 1)
        price = QLabel(f"{r.xp_cost} XP" if char.chargen_locked else f"{r.bp_cost} BP")
        price.setStyleSheet(f"color:{MUTED};")
        top.addWidget(price)
        lay.addLayout(top)
        for text in (f"Requires {r.requirement}" if r.requirement else "",
                     r.description):
            if not text:
                continue
            sub = QLabel(text)
            sub.setWordWrap(True)
            sub.setStyleSheet(f"color:{MUTED};")
            lay.addWidget(sub)
        lay.addWidget(self._submodule_button(r, char))
        return box

    def _submodule_button(self, r, char) -> QWidget:
        """The control of one row. Before the lock, an owned submodule gets Remove. A
        blocked submodule gets a disabled button with the reason. Any other submodule gets
        Buy or Add. ⚠ After the lock, an owned submodule gets no Remove. The refund is the
        undo on the Edit tab, which takes the last entry first."""
        if r.owned:
            if char.chargen_locked:
                label = QLabel("Purchased.")
                label.setStyleSheet(f"color:{MUTED};")
                return label
            btn = QPushButton("Remove")
            btn.clicked.connect(
                lambda _=False, c=r.charm_id, k=r.key: self._drop_submodule(c, k))
            return btn
        if r.block_reason:
            btn = QPushButton("Add")
            btn.setEnabled(False)
            btn.setToolTip(r.block_reason)
            return btn
        btn = QPushButton(f"Buy · {r.xp_cost} XP" if char.chargen_locked else "Add")
        btn.clicked.connect(
            lambda _=False, c=r.charm_id, k=r.key: self._learn_submodule(c, k))
        return btn

    def _learn_submodule(self, charm_id: str, key: str) -> None:
        """Buy a submodule. It costs bonus points at chargen, and XP after the lock. One
        dispatcher handles both cases."""
        if self._act(charm_actions.learn_submodule, self._ruleset, self._char(),
                     charm_id, key):
            self._after_submodule_change()

    def _drop_submodule(self, charm_id: str, key: str) -> None:
        if self._act(charm_actions.drop_submodule, self._char(), charm_id, key):
            self._after_submodule_change()

    def _after_submodule_change(self) -> None:
        """A submodule spends bonus points or XP. Thus the budget readout and the bar of the
        shell must change. `_update_action` rebuilds the rows."""
        self._update_action()
        self._update_readout()

    def _add_another(self) -> None:
        """Buy ONE MORE copy of the selected repeatable Charm. ⚠ Call the LEARN function
        directly. `toggle_charm` finds an owned Charm and removes it. Thus this action needs
        its own button, not a second click on the main button."""
        cid = self._selected_node
        if cid is None:
            return
        if not self._act(charm_actions.learn_charm, self._ruleset, self._char(), cid):
            return
        self._refresh_current_tree()
        # Select the node again in the new scene. The user buys copies repeatedly, because
        # the limit is a trait rating and it can be several copies. A rebuild of the tree
        # drops the selection. ⚠ Without this line, the button goes away below the pointer
        # after each copy.
        self._reselect_node(cid)

    def _reselect_node(self, charm_id: str) -> None:
        """Select the node of `charm_id` in the rebuilt scene of the current tab, when that
        scene holds it. A selection sends `selectionChanged`, and that signal repaints the
        detail panel and the button."""
        view = self.tabs.currentWidget().findChild(CharmTreeView)
        if view is None:
            return
        for item in view.scene().items():
            if isinstance(item, NodeItem) and item.node.id == charm_id:
                item.setSelected(True)
                return

    def _toggle_spell(self, spell_id: str) -> None:
        """Handle a click on a spell row. It uses the same chargen and XP branches, and the
        same shared dispatcher, as a Charm."""
        if self._act(charm_actions.toggle_spell, self._ruleset, self._char(), spell_id):
            self._refresh_current_tree()

    def _refresh_current_tree(self) -> None:
        """Draw the active tree again, thus the owned state and the available state show the
        change. `build_charm_graph` reads what the character holds. Then refresh the budget
        readout, and find the selected Thaumaturgy entry again, thus its owned state sets
        the button."""
        view = self.tabs.currentWidget().findChild(CharmTreeView)
        if view is not None and view.category_combo is not None:
            view.reload_tree()
            self._tab_changed()
        if self._selected_thaum is not None:
            self._refresh_thaum_selection()
        self._update_readout()

    def _refresh_thaum_selection(self) -> None:
        """Find the selected Thaumaturgy entry again, in a new picker. ⚠ The stored row comes
        from before the purchase or the drop. Thus its owned flag is old, and the button
        stays on "Learn". The same entry in a new picker holds the new state."""
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
        # ⚠ The DETAIL text is also old, not the button only. The code wrote it from the row
        # before the purchase, and the panel holds lines that change with a purchase. For
        # example: "Known in: Realm" after the user adds a version, and "Narrowed" after a
        # half-price purchase.
        self._show_thaum_detail()
        self._update_action()

    def _show_thaum_detail(self) -> None:
        """Render the selected Thaumaturgy row into the detail panel.

        ⚠ Use ONE renderer for the three call sites: the Arts tree, the entry lists and the
        refresh after a purchase. The refresh site is necessary, because the panel holds
        lines that a purchase changes, for example "Known in:".

        The row is the LAST member of the selection tuple in every case: ("art", row),
        ("science", row), ("ritual", row), and ("art_specialty", art, spec). In the last
        form, the panel describes the specialty.
        """
        if self._selected_thaum is None:
            return
        row = self._selected_thaum[-1]
        # ⚠ The Cost line of the panel must agree with the button. With "narrow" selected,
        # the button shows the half price (p.127). If the panel prints the full price, the
        # screen shows two numbers for one purchase.
        #
        # ⚠ Calculate this value from the ROW. Do not read `_narrow_offered`.
        # `_update_action` sets that flag, and it runs AFTER this method on a selection
        # change. Thus that flag prices the new row against the state of the old row.
        if self._selected_thaum[0] == "art_specialty":
            art = self._selected_thaum[1]
            if (art.allows_narrowing and not row.owned and row.printed
                    and self._narrow_check.isChecked()):
                row = replace(row, price=row.narrowed_price)
        self.detail.setHtml(_detail_html(row, self._thaum_currency()))

    def _update_readout(self) -> None:
        """Redraw this tab's budget line AND tell the shell its own bar moved.

        ⚠ Use this wrapper. Do not put the call at the end of `_draw_readout`. That method
        has two exits, one for the locked state and one for chargen, and the shell hook must
        run from both. Every purchase path on this tab passes through this method."""
        self._draw_readout()
        self._on_change()

    def _draw_readout(self) -> None:
        """The budget line. In play it shows the XP. At chargen it shows the count of Charm
        picks and the validation result. Thus a purchase here shows when the budget fails,
        as the side column of the Edit tab does for the traits."""
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
        # ⚠ The Slots readout shows the LIVE load. It does not show the chargen snapshot.
        # The Vat Refit page records the same difference. `charm_slot_budget` reports the
        # snapshot. Thus with that function, a purchase after the lock never moves the
        # count.
        if refit.supports_refit(ruleset, char):
            load = refit.slot_load(ruleset, char)
            picks = (f"Slots: {load.installed}/{load.total_slots} used "
                     f"(G {load.general} · D {load.dedicated})")
        else:
            b = ruleset.budgets_for(char.exalt_type, char.origin, char.upbringing)
            if b.path_dots > 0:
                # A Dragon-King learns Paths, not Charms. Thus 'Charms: 0' has no meaning.
                used = sum(p.rating for p in char.paths)
                picks = f"Path dots: {used} · Spells: {len(char.spells)}"
            else:
                noun = ruleset.exalt_for(char.exalt_type).charm_noun
                picks = (f"{noun}: {validate.charm_pick_count(ruleset, char)} · "
                         f"Spells: {len(char.spells)}")
        parts = [picks, status]
        if bp:
            parts.append(bp)
        path = self._immaculate_path_line()
        if path:
            parts.append(path)
        self.readout.setText(" · ".join(parts))
        self.readout.setStyleSheet("color:#6b7280;")

    def _immaculate_path_line(self) -> str:
        """For a Dragon-Blooded at chargen, which Charm path they are on; "" for
        everyone else.

        ⚠ Any *Immaculate* Charm starts the Immaculate path. Those Charms are the five
        Dragon style trees: Air, Earth, Fire, Water and Wood Dragon. Martial arts in general
        do NOT start it. Five-Dragon Style is a Martial Arts Charm, it is a normal Charm,
        and it does not change the path. ⚠ Read the counts from the budget. Never write them
        in the code."""
        ruleset, char = self._ruleset, self._char()
        if char.exalt_type != "Dragon-Blooded":
            return ""
        b = ruleset.budgets_for(char.exalt_type, char.origin, char.upbringing)
        if validate.immaculate_martial_artist(ruleset, char):
            return (f"Immaculate path — {b.immaculate_charm_count} Charms from one "
                    f"Dragon style; Aspect/Favored minimum waived")
        return (f"Standard path — {b.charm_count} Charms, "
                f"≥{b.charm_min_caste_favored} Aspect/Favored. Pick a Dragon-style "
                f"(Immaculate) Charm to switch to the Immaculate path")

    def _tree_page(self, group, cache=None):
        """A tree tab: Splat and category dropdowns filtered to `group`, over a
        CharmTreeView.

        `cache` is the memo of the caller for one build (see `_cached`). `reload` shares one
        memo across all of its `trees_for` calls. ⚠ Without the memo, those calls read the
        full Charm catalogue one time for each group, and again for each page.

        ⚠ Each tab has its OWN Splat dropdown. The web picker has one shared dropdown
        (core p.127). Each tab offers the splats with trees in its own group only. Thus this
        page needs no fallback to another group: a splat with no martial arts is not in the
        list of the Martial Arts tab."""
        char = self._char()
        page = QWidget()
        combo = CappedCombo(15)
        combo.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        combo.setMaximumWidth(300)
        view = CharmTreeView(self._ruleset, char, cache)
        view._scene.selectionChanged.connect(lambda: self._tree_detail(view))
        view.category_combo = combo
        self._tree_views[group] = view

        splat_combo = CappedCombo(15)
        splat_combo.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        splats = splats_for(self._ruleset, char, group, cache)
        splat_combo.blockSignals(True)
        for name in splats:
            splat_combo.addItem(name, name)
        splat_combo.blockSignals(False)
        splat_combo.setToolTip("Another Exalt type's Charms — a willing tutor, and "
                               "double to learn and to use (p.127)")
        view.splat_combo = splat_combo
        splat_combo.currentIndexChanged.connect(lambda _i, v=view: self._splat_changed(v))
        # With one entry, that entry is the splat of the character, and the user has no
        # choice.
        splat_label = QLabel("Splat:")
        for w in (splat_label, splat_combo):
            w.setVisible(len(splats) > 1)

        self._fill_categories(view, group, cache)

        style_head, style_body = self._style_panel(view)
        combo.currentIndexChanged.connect(lambda _i, v=view: self._category_changed(v))

        lay = QVBoxLayout(page)
        row = QHBoxLayout()
        row.addWidget(splat_label)
        row.addWidget(splat_combo)
        row.addWidget(QLabel("Tree:"))
        row.addWidget(combo)
        row.addStretch()
        lay.addLayout(row)
        lay.addWidget(style_head)
        lay.addWidget(style_body)
        lay.addWidget(view, 1)
        # ⚠ `addItem` makes the first item current. Thus `setCurrentIndex(0)` sends no
        # `currentIndexChanged` signal. Load the tree with an explicit call.
        if combo.count():
            self._category_changed(view)
        return page

    def _style_panel(self, view):
        """The style text above a martial-arts tree, which the user can fold. It holds the
        printed `Type:`, the prose, and the "Weapons and Armor" rules. No other surface
        holds those rules (`docs/status/martial-arts-styles.md`). Returns the (header, body)
        widgets. Both are hidden until `_sync_style_panel` finds an authored style for the
        category.

        The panel starts folded. The tab exists for the tree canvas, and the text of a style
        is several paragraphs."""
        head = QPushButton("")
        head.setCheckable(True)
        head.setCursor(Qt.PointingHandCursor)
        head.setStyleSheet(
            f"QPushButton {{ background:transparent; border:none; text-align:left; "
            f"padding:2px 0; color:{accent_light(theme.palette(self._char().exalt_type))}; "
            f"font-weight:600; }}")
        body = QTextBrowser()
        body.setMaximumHeight(190)
        # ⚠ Set the stylesheet inline. Do not use a palette. An ancestor stylesheet always
        # beats a palette that you set on the widget, and a QTextBrowser in a themed page
        # then paints the card shade.
        body.setStyleSheet(f"QTextBrowser {{ background:{TREE}; border:none; "
                           f"color:{MUTED}; }}")
        body.setVisible(False)
        head.setVisible(False)
        head.toggled.connect(body.setVisible)
        head.toggled.connect(
            lambda on, b=head: b.setText(("▾" if on else "▸") + b.text()[1:]))
        view.style_head = head
        view.style_body = body
        self._sync_style_panel(view)
        return head, body

    def _sync_style_panel(self, view) -> None:
        """Point the style panel of a tab at its current category. ⚠ Render NOTHING when the
        category is not an authored style. `martial_arts:enlightenment` is the Dragon-Path
        initiation tree, not a style, and a homebrew style has no page. An empty panel on
        every other category is worse than no panel."""
        head = getattr(view, "style_head", None)
        if head is None:
            return
        category = (view.category_combo.currentData()
                    if view.category_combo is not None else "")
        style = viewmod.style_for_category(self._ruleset, category or "")
        if style is None:
            head.setVisible(False)
            view.style_body.setVisible(False)
            return
        head.setVisible(True)
        # The arrow shows the expanded state. That state STAYS through a category change. A
        # user who opened the panel also wants the text of the next style open.
        head.setText(("▾ " if head.isChecked() else "▸ ") + style.heading)
        # ⚠ Every field is optional, also on a style that is not None. The Player's Guide is
        # the one book that prints a Type: line and prose. If you insert each field without
        # a test, an empty paragraph appears below a heading.
        parts = []
        if style.preamble:
            parts.append("<p>" + html.escape(style.preamble).replace("\n", "<br>")
                         + "</p>")
        for rule in style.mechanics:
            parts.append(f"<p>• {html.escape(rule)}</p>")
        if style.source_label:
            parts.append(f"<p><i>{html.escape(style.source_label)}</i></p>")
        view.style_body.setHtml("".join(parts))
        view.style_body.setVisible(head.isChecked())

    def _category_changed(self, view) -> None:
        """Handle a category selection. Draw the tree again, and point the style panel at
        the new category."""
        view.reload_tree()
        self._sync_style_panel(view)

    def _fill_categories(self, view, group, cache=None):
        """Fill the category dropdown of a tab for the splat that its Splat dropdown names.
        ⚠ Keep the signals blocked through this method. The caller decides when the tree
        renders, and a `clear()` on a combo box sends `currentIndexChanged` with -1."""
        char = self._char()
        splat = view.splat_combo.currentData() or char.exalt_type
        combo = view.category_combo
        combo.blockSignals(True)
        combo.clear()
        for key, count in trees_for(self._ruleset, char, splat, group, cache):
            label = (_style_label(key, self._ruleset).removesuffix(" Style")
                     if key.startswith("martial_arts:") else key.replace("_", " ").title())
            combo.addItem(f"{label} ({count})", key)
        combo.blockSignals(False)

    def _splat_changed(self, view) -> None:
        """Change the trees of a tab to the page of a different Exalt type. ⚠ Two splats can
        use the same category name, thus the current category is rarely valid on the new
        page. Fill the dropdown again and select its first entry. `reload_tree` then renders
        that entry."""
        group = next((g for g, v in self._tree_views.items() if v is view), "")
        self._fill_categories(view, group)
        self._category_changed(view)

    def _tree_detail(self, view):
        # ⚠ A scene sends `selectionChanged` while Qt destroys it, for example when the
        # window closes. Its C++ object is gone at that time, thus a read raises
        # RuntimeError. Catch that error.
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
        # ⚠ A collapsed augmentation summary node ('augment:<type>') is not a Charm. Show
        # the installed-Attribute readout of that type, and offer Pick Attributes.
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
        if detail is not None:
            html_text += self._charm_flags_html(detail)
        state = {"owned": "Owned", "available": "Available"}.get(node.state, "Locked")
        menu = build_package_menu(self._ruleset, view._character, node.id)
        if menu is not None:
            html_text += self._package_summary_html(menu)
        self.detail.setHtml(f"<span style='color:#9a9894'>{state}</span><br>" + html_text)
        self._update_action()

    def _charm_flags_html(self, detail) -> str:
        """The five notes that a Charm detail card shows below its stat block: a homebrew
        Charm, a Charm of a different splat, an Immaculate Order Charm, a Calling Charm with
        a discount, and a Charm that the training camp gave free.

        Four of the five change what the Charm COSTS. Thus they go next to the price, not on
        the sheet. This method renders nothing when no note applies.
        """
        char = self._char()
        pal = theme.palette(char.exalt_type)
        accent = accent_light(pal)
        flags: list[tuple[str, str]] = []
        if detail.custom:
            flags.append((CUSTOM, "✎ Custom (homebrew) Charm — not from a rulebook"))
        if detail.foreign_splat:
            flags.append((accent, f"{html.escape(detail.foreign_splat)} Charm — needs a "
                                  "willing tutor; costs double to learn and to use (p.127)"))
        charm = self._ruleset.charms.get(detail.id)
        if charm is not None and validate.is_immaculate_charm(charm):
            flags.append((accent, "Immaculate Order Charm (Fivefold Dragon Method)"))
        if viewmod.is_calling_charm(self._ruleset, char, detail.id):
            flags.append((accent, "✧ Calling Charm — discounted"))
        if detail.id in char.granted_charms:
            flags.append((accent, "Granted by your training camp — no Charm pick spent"))
        if not flags:
            return ""
        rows = "".join(f"<div style='color:{c}; font-weight:600'>{t}</div>"
                       for c, t in flags)
        return f"<div style='margin-top:6px'>{rows}</div>"

    def _package_summary_html(self, menu) -> str:
        """The packages that the character owns, and the limit. This text goes at the end of
        the detail of a variant-menu Charm. ⚠ The tree paints the node "owned" from one
        Charm id. The user needs the NUMBER of packages and their names."""
        rows = [f"<b>Bought:</b> {menu.bought} / {menu.cap} · "
                f"{html.escape(menu.cap_phrase)}"]
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
        # ⚠ `addItem` made the first circle current before this connect. Load it explicitly.
        if circles:
            self._fill_list(entries, spells_in_circle(self._ruleset, circles[0]))
        return page

    def _thaum_page(self):
        """A panel tab with Arts, Sciences, Rituals and Formulas sub-tabs. The rows of
        `build_thaum_picker` build them. Thus each entry carries its owned state and its
        price, and the action button can offer to learn it. The Arts show their specialties
        below each Art, in a tree that the user can expand. The user buys a specialty below
        its Art, as in the web app."""
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
        inner.addTab(self._arts_tab(arts_tree), "Arts")
        for label, kind, rows in (
                ("Sciences", "science", picker.sciences),
                ("Rituals", "ritual", picker.rituals),
                ("Formulas", "formula", picker.formulas)):
            entries = QListWidget()
            for row in rows:
                # ⚠ Use `getattr`. The three lists hold three ROW TYPES. A ritual row and a
                # formula row carry `custom`. A Science row does not.
                item = QListWidgetItem(f"{row.name}  ✎" if getattr(row, "custom", False)
                                       else row.name)
                item.setData(Qt.UserRole, (kind, row))
                entries.addItem(item)
            entries.currentItemChanged.connect(
                lambda _c, _p, lw=entries: self._panel_detail(lw))
            if kind != "ritual":
                inner.addTab(entries, label)
                continue
            inner.addTab(self._rituals_tab(entries), label)
        lay = QVBoxLayout(page)
        lay.addWidget(inner)
        return page

    def _arts_tab(self, tree) -> QWidget:
        """The Arts tree, with a row below it that writes a new specialty. Page 126 permits
        a specialty that the user invents, and it is the same purchase at the same rate as a
        printed aspect.

        The row acts on the Art of the current selection. Thus it needs no Art picker. ⚠ With
        no selection, the row states that. It must not select an Art itself."""
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(tree, 1)
        row = QHBoxLayout()
        name = QLineEdit()
        name.setObjectName("thaum.custom_specialty.name")
        name.setPlaceholderText("Own specialty, e.g. Local Fair Folk…")
        row.addWidget(name, 1)
        add = QPushButton("Add specialty")
        add.setObjectName("thaum.custom_specialty.add")
        add.setToolTip("Buy a specialty you invented, in the selected Art (p.126)")
        add.clicked.connect(
            lambda: (self._add_custom_specialty(name.text()), name.clear()))
        row.addWidget(add)
        lay.addLayout(row)
        return page

    def _rituals_tab(self, entries) -> QWidget:
        """The Rituals list with an authoring row under it.

        ⚠ This is the ONE list in the picker that accepts a new entry. Every other entry
        here is printed content that the user buys. The user can also WRITE a ritual,
        because the chapter prints five and states that more exist (p.148). The regional
        version comes from the combo box that the buy button uses. Thus one control serves
        one concept.
        """
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(entries, 1)
        row = QHBoxLayout()
        name = QLineEdit()
        name.setObjectName("thaum.custom_ritual.name")
        name.setPlaceholderText("Write your own ritual…")
        row.addWidget(name, 1)
        level = QSpinBox()
        level.setObjectName("thaum.custom_ritual.level")
        level.setRange(1, 5)
        level.setPrefix("level ")
        level.setToolTip("A thaumaturge needs Occult equal to the ritual's level "
                         "(p.148)")
        row.addWidget(level)
        add = QPushButton("Add ritual")
        add.setObjectName("thaum.custom_ritual.add")
        add.setToolTip("Invent one for this character. To write one every character "
                       "can learn, use the Custom tab's Rituals library.")
        add.clicked.connect(
            lambda: (self._add_custom_ritual(name.text(), level.value()),
                     name.clear()))
        row.addWidget(add)
        lay.addLayout(row)
        return page

    # ------------------------------------------------------------------ #
    # splat-specific picker extras (Form Library / Vat Refit / Paths /
    # Elemental Powers) — the picker's pages the spike deferred
    # ------------------------------------------------------------------ #

    def _combos_label(self) -> str:
        """"Combos", or "Arrays" for a Charm-Slot splat.

        ⚠ Use the word of the book: `charm_noun`, and "Arrays" for an Alchemical.
        `view.uses_arrays` is the one place that decides the word for a character. Never
        write either word in this code."""
        return "Arrays" if viewmod.uses_arrays(self._ruleset, self._char()) \
            else "Combos"

    def _combos_page(self):
        """The Combos (or Arrays) sub-tab — `qt/combos.py`.

        ⚠ Keep this surface in its own module. It is a full collection surface, and this
        file is the largest one in the port.

        ⚠ Pass `on_change` THROUGH. Do not stop it here. A Combo costs bonus points at
        chargen and XP in play. Thus a new Combo moves the readout of this page and the
        readout of the shell. Every other page has the same hook contract."""
        return CombosPage(self._ruleset, self._ctx, notify=self._notify,
                          on_change=self._update_readout)

    def _form_library_page(self):
        """The Lunar Form Library: the Totem plus every animal shape recorded.

        ⚠ This page is free text. It has no cost, no limit and no validation. The budget
        audit and the XP audit never read it (play state, decision 0006). The Storyteller
        decides which animals a Lunar has heart's blood for. Thus this page is a notepad,
        not a picker. It is available on both sides of the lock."""
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
        # ⚠ Put the Add button BELOW the scroll area, not in it. Thus it stays at the bottom
        # of the panel with any number of forms. In the list, the button moves with the
        # content, and a short list is centred vertically in the viewport. The button then
        # moves from the bottom to the middle on the first add.
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
        """Rebuild the forms list only. The totem field and the Add button stay. Thus an add
        or a remove does not stop the user from typing in either one."""
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
        # ⚠ Add a stretch at the end of the list. Without it, a short list is centred
        # vertically in the scroll viewport, and each new form moves the rows.
        self._forms_lay.addStretch(1)

    def _vat_page(self):
        """The Vat Refit page: swap Charms between the installed Slots and the
        Panoply (Alchemical CH2/CH3 pp.88-89, or an Eclipse with a crossover Slot).
        This page holds play state, as the Form Library does. The character has already paid
        for the Charms. Thus a move costs nothing and writes no XP entry. It changes *which*
        Charms are installed.

        ⚠ Read the load from `refit.slot_load`, which is the LIVE load. Do not read
        `charm_slot_budget`, which is the chargen snapshot. The refit module records that
        difference."""
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
        """One Charm in the installed set or in the Panoply. It shows the name, the traits
        that decide its Slot, the reason for a refused move, and the move button."""
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
        """Rebuild the body of the Vat page. It holds the live load readout, the Ox-Body
        note, and then the INSTALLED rows and the PANOPLY rows. Call this after each move."""
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
        # The installed Charms that the user can move. ⚠ An ox_body Charm and a PLM Charm
        # use a Slot, and the user cannot move them. Thus they stay off this list. The web
        # app calculates the same set.
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
    # ⚠ The 18 '<Type> Augmentation of <Attribute>' Charms keep separate ids in the data,
    # because other Charms name one of them as a prerequisite. This page renders them as TWO
    # groups, Transitory and Sustained, and each group has a picker for the Attributes. The
    # web picker uses the same collapsed cards. `build_augmentation_view` supplies the rows.
    # The toggle makes the same state change as a purchase on a tree node.

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
        """Rebuild the two type cards from a live read. ⚠ Each toggle changes the install
        state. Thus the `owned` flags of a stored group hold old values."""
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
        """One checkbox for each Attribute of one type. A toggle installs or removes that
        Attribute immediately, with the same checks as a purchase on a tree node. It then
        sets the checkbox to the real state. ⚠ A refused toggle keeps its old state."""
        char = self._char()
        dialog = QDialog(self)
        dialog.setWindowTitle(group.title)
        lay = QVBoxLayout(dialog)
        intro = QLabel("Each installed Augmentation occupies a Charm Slot.")
        intro.setStyleSheet(f"color:{MUTED};")
        lay.addWidget(intro)
        # ⚠ Read the group again. Thus the checkbox states are live, and they are not the
        # snapshot of the card.
        grp = next((g for g in build_augmentation_view(self._ruleset, char)
                    if g.title == group.title), group)
        locked = char.chargen_locked
        for e in grp.entries:
            row = QHBoxLayout()
            cb = QCheckBox(e.attribute)
            cb.setChecked(e.owned)
            # In play, the user cannot drop a copy that the character owns. The undo is on
            # the Edit tab. A copy that is not available has an unsatisfied requirement, and
            # this code shows that requirement as the reason.
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
        """`_toggle_charm` makes the state change. It applies the checks, it shows a message,
        and it operates on both sides of the lock. ⚠ Then set the checkbox to the real state.
        A purchase or a removal can be refused by a requirement, by a Charm that depends on
        it, or by an advancement error."""
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
    # ⚠ Neither Charm has a toggle. Each purchase is a PACKAGE of picks, and it writes to
    # its own field on the character. Thus the action button of the node opens this dialog,
    # and it does not offer Learn. ONE dialog serves both, and `view.build_package_menu`
    # supplies it. Ox-Body selects one variant of two. Gifts select two, then one, from a
    # list with prerequisites. The widget sees one difference: `menu.needed`, and the
    # reasons of the picks.

    def _open_package_dialog(self, charm_id: str) -> None:
        dialog = self._build_package_dialog(charm_id)
        if dialog is not None:
            dialog.exec()

    def _build_package_dialog(self, charm_id: str):
        """Build the package chooser and do NOT run it. `exec()` stops a headless run, thus
        this is the seam that the tests drive. The Gear page and the Advantages page use the
        same shape. Returns None when `charm_id` is not a variant-menu Charm.

        The dialog shows the packages that the character owns, and the user can remove each
        one before the lock. Below them it shows one checkbox for each pick, then Add or
        Buy. The selection stays in the dialog, and it reaches the character on a confirm
        only. Thus Cancel changes nothing. ⚠ This dialog does not decide legality.
        `view.build_package_menu` supplies the reasons of the picks, and
        `engine.charm_actions` makes the purchase. That module refuses a purchase above the
        limit, and a purchase that the character cannot pay for.

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
        # The shape of the live menu, in lists of one element. Thus the handlers below read
        # the values of the LAST rebuild, not a copy from before a purchase.
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
            # ⚠ SYNC the rows. Never rebuild them. A pick adds no row and removes no row. A
            # rebuild below the click moves the scroll area to its bottom, because a delete
            # of the focused checkbox gives the focus to another widget, and a QScrollArea
            # scrolls to that widget. Only a purchase or a removal changes the shape of this
            # dialog.
            sync()

        def buy() -> None:
            # ⚠ Each kind writes to its OWN list on the Character. Thus `menu.kind` selects
            # the dispatcher. Never select it from the shape of the selection.
            if menu_kind[0] == "gift":
                ok = self._act(charm_actions.add_gift_purchase, self._ruleset,
                               self._char(), sorted(selection))
            elif menu_kind[0] == "variant":
                ok = self._act(charm_actions.add_variant_purchase, self._ruleset,
                               self._char(), charm_id, sorted(selection))
            else:
                ok = self._act(charm_actions.add_ox_body, self._ruleset,
                               self._char(), selection[0])
            if ok:
                self._refresh_current_tree()
                dialog.accept()

        def remove(index: int) -> None:
            action = {"gift": charm_actions.remove_gift_purchase,
                      "variant": charm_actions.remove_variant_purchase}.get(
                          menu_kind[0], charm_actions.remove_ox_body)
            if self._act(action, self._char(), index):
                selection.clear()
                self._refresh_current_tree()
                rebuild()

        def rebuild() -> None:
            # A removal changes the list of owned packages above the picks. Thus this code
            # rebuilds the rows. Keep the scroll position of the user.
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
            # ⚠ Do NOT repeat the description of the Charm here. The detail pane that opened
            # this dialog shows it. The description of Deadly Beastman is eleven lines, and
            # it moves the picks off the first screen.
            if menu.note:
                note = QLabel(menu.note)
                note.setWordWrap(True)
                note.setStyleSheet(f"color:{MUTED};")
                body.addWidget(note)
            # ⚠ The limit on the purchases comes from the data of the splat. Never write it
            # in the code. Lunar Ox-Body counts Stamina, and every other splat counts
            # Endurance. A unique-version menu takes its limit from its versions.
            # `cap_phrase` is the ONE place that builds that sentence.
            head = QLabel(f"Bought {menu.bought} / {menu.cap}  ·  {menu.cap_phrase}")
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
                # Build this label empty, also when the pick has no reason now. The reason
                # appears and goes away as the selection changes, and `sync` writes text
                # only.
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
            """Update the pick rows in place from the current selection. It sets the ticks,
            the rows that the user can pick, the reason of each row, and the confirm button.
            ⚠ It creates no widget and deletes no widget. Thus the scroll position stays."""
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
                # ⚠ A menu with one pick never disables a row that the user did not pick. A
                # new pick replaces the old one. Thus its variants stay clickable, as radio
                # buttons do.
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
        """The Elemental Powers page. It applies to a God-Blooded with an Elemental origin
        only (Core p.296, GoD p.56, PG p.68). It is a catalogue like the Charms catalogue.
        One power costs 7 bonus points at chargen, and 14 XP in play, which is twice the
        bonus-point value (PG p.68). A selection fills the shared detail pane and sets the
        Learn or Remove button, as the Spells page and the Thaumaturgy page do."""
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
        """Rebuild the power list from a new picker. Thus the owned state and the available
        state are live. Then select the same id again. ⚠ The owned flag of a stored row is
        old after a rebuild of the list."""
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
        """The detail pane for an ElementalPowerRow. It shows the name, Requires, Cost, the
        activation in italic text, and the description. ⚠ The shared `_detail_html` reads
        `requirement` and `type`, and this row has neither field. Thus this row needs its
        own formatter."""
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
        """Toggle one Elemental Power. Before the lock, this method writes the chargen list
        directly, and `validate.meets_elemental_power_requirements` controls it. The
        validation side applies the 7-BP charge. After the lock, it calls
        `advancement.learn_elemental_power`, which costs 14 XP. ⚠ In play, the user cannot
        drop a power that the character knows. The undo is on the Edit tab."""
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
        """Refresh this page after a toggle. Rebuild the list and select the same id again,
        refresh the detail pane and the action button, and refresh the readout. ⚠ Do not
        call `_refresh_current_tree`. That method renders a CharmTreeView, and this page has
        no tree."""
        self._rebuild_elemental()
        self._update_readout()

    def _paths_page(self):
        """The Dragon-King Paths page (PG pp.175-177). ⚠ A Path is a rated track with its own
        chargen pool. It is NOT a Charm. Each Path has a rating of 1 to 6. The user learns
        the dots in a fixed order, and Essence controls them. Each dot grants the power of
        that level. Before the lock, the rating writes to `character.paths` and costs
        nothing. After the lock, `advancement` raises and lowers it with XP. The two element
        Paths of the breed are favoured automatically (★), and the user selects one more (✚)
        from the other eight.

        This page is a selectable list, as the Spells page is. A selected Path fills the
        shared detail pane with its powers and the cost of the next dot. The action button
        shows the purchase price. The rating is a dot track that is bound to the selected
        Path."""
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
        """The Favoured Path combo box. After the lock it is a read-only label. The user
        selects one of the eight Paths that are not breed Paths.

        ⚠ Keep a saved `favored_path` in the options, also when it is one of the two breed
        Paths. That state is illegal and it can occur, and a combo box whose value is not in
        its options does not operate correctly.

        ⚠ Never index `ruleset.paths[saved]` directly. An old id from a rename in the
        catalogue raises a KeyError, and the whole tab fails."""
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
        # ⚠ Capture the combo box in a default argument. A `combo` name in the closure reads
        # the shared local variable, and a rebuild after the change must read THIS box.
        combo.currentIndexChanged.connect(lambda _, c=combo: (
            setattr(char, "favored_path", c.currentData() or ""),
            self._rebuild_paths_list()))
        self._fav_path_combo = combo
        fav_row.addWidget(combo, 1)

    def _rebuild_paths_list(self) -> None:
        """Rebuild the Path list, with the ★ and ✚ markers, the element and the rating.
        ⚠ Select the current Path again with the signals blocked. Thus no selection handler
        runs during the rebuild. Clear the Path pane when the list holds no Path, which
        happens on a reload."""
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
        """Handle a Path that the user selects in the list. That Path fills the shared
        detail pane, the action button and the rating track. The Spells list uses the same
        shape."""
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
        """The detail pane for a Path. It shows the name, the element, the granted powers,
        with one power for each dot that the character holds, and the XP cost of the next
        dot."""
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
        """A new DotTrack for one Path, in the hidden rating row. A selection shows that
        row. ⚠ Build a new track for each selection. The DotTrack captures `get` and `setv`
        in its constructor, thus you cannot bind it again in place. ⚠ Never call this method
        from inside the handler of a track. The track refreshes itself there."""
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
        """Write a Path rating before the lock. It costs nothing, and `validate_chargen`
        validates it. A rating of 0 removes the Path. Any other rating adds or updates the
        PathRating. This method refreshes the list, the detail pane, the action button and
        the readout. ⚠ It does NOT refresh the dot track. It runs inside the click handler of
        that track, and the track refreshes itself."""
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
        """Raise or lower a Path to `wanted` dots after the lock, through `advancement`. Each
        dot is its own XP step (PG p.176). `refresh` is the pip refresh of the DotTrack.
        ⚠ Never rebuild the track from inside its own callback."""
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
        """The action button for a selected Path. It raises the Path by one dot. Before the
        lock, the chargen pool pays for it. After the lock, it is an XP step, and a new Path
        must be learned first. This method rebuilds the dot track, thus its pips agree. That
        rebuild is safe, because the click comes from outside the track."""
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
        """Refresh the full Paths page, after a reload or a change from outside. Rebuild the
        list, the detail pane of the selected Path and its dot track, then refresh the
        readout."""
        self._rebuild_paths_list()
        if self._selected_path is not None:
            self._update_path_detail()
        self._update_action()
        self._update_readout()

    def _art_selected(self, tree):
        """Handle a selection in the Arts tree. The selection is an Art or one of its
        specialties. This method sets `_selected_thaum` to ("art", row) or to
        ("art_specialty", art, spec), and it shows the detail."""
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
        self._show_thaum_detail()
        self._update_action()

    def _thaum_currency(self) -> str:
        """The budget that pays for Thaumaturgy now. Returns 'BP' or 'XP'."""
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
            self._show_thaum_detail()
        else:
            self._selected_thaum = None
            # A Spell has a circle, and a Thaumaturgy entry does not. Thus the action button
            # identifies a spell row, and it can offer to learn that spell.
            self._selected_spell = obj.id if getattr(obj, "circle", None) else None
            self.detail.setHtml(_detail_html(obj) if obj is not None
                                else f"<b>{item.text()}</b>")
        self._update_action()

    def reload(self):
        """Rebuild the tab bar for the current character. It adds one tree tab for each group
        that has content, then Spells, then Thaumaturgy, then the extra pages of the
        splat."""
        char = self._char()
        self._tree_views.clear()
        # ⚠ Clear every selection. A reload rebuilds the pages. Thus a stored selection
        # points at a widget that no longer exists, or at an entry of a different character.
        self._selected_node = None
        self._selected_spell = None
        self._selected_thaum = None
        self._selected_elemental = None
        self._selected_augment = None
        self._selected_path = None
        # ⚠ Block the tab signals across the rebuild. A QTabWidget sends `currentChanged`
        # during `clear()` and `addTab` (see `docs/plans/qt-port.md`). This page has several
        # conditional builders, thus a signal during the build reaches a panel that is not
        # complete. The code below calls `_tab_changed()` after the bar is complete.
        self.tabs.blockSignals(True)
        try:
            self.tabs.clear()
            # ⚠ Build this memo HERE, and do not store it on the page. It is valid for this
            # one rebuild only, against this character and this catalogue.
            cache: dict = {}
            for group, label in (("abilities", "Charms"), ("styles", "Martial Arts"),
                                 ("arcanoi", "Arcanoi")):
                if trees_for(self._ruleset, char, char.exalt_type, group, cache):
                    self.tabs.addTab(self._tree_page(group, cache), label)
            if _cached(cache, "augmentation_category",
                       lambda: augmentation_category(self._ruleset, char)) is not None:
                self.tabs.addTab(self._augment_page(), "Augmentations")
            # Combos go with the Charms that build them (human's ruling). On the webapp,
            # Combos is a top-level tab. ⚠ This page also holds the show/hide rule.
            # `has_combos_tab` is false for a splat that builds neither Combos nor Arrays,
            # for example the dead, who can never learn Combos (E:Ab p.234). An empty tab
            # that answers each attempt with a validation error is worse than no tab.
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
        # The Path rating row is in the shared detail panel, and it belongs to the Paths page
        # only. ⚠ Hide it on every other tab, and drop the old selection.
        if self.tabs.currentWidget() is not getattr(self, "_paths_page_widget", None):
            if self._selected_path is not None:
                self._selected_path = None
                self._path_box.setVisible(False)
        # A summary-node selection belongs to a tree tab. Drop it on every other tab.
        if self._selected_augment is not None:
            self._selected_augment = None
        # ⚠ The Combos sub-tab is the ONE sub-tab with its own detail pane. Every other
        # sub-tab is a content pane that FILLS the shared pane. Thus the shared pane next to
        # the splitter of `CombosPage` puts two detail panes on the screen: the real one,
        # and an empty column that says "Select an entry to see details." Hide the shared
        # pane on this sub-tab.
        self._detail_panel.setVisible(
            not isinstance(self.tabs.currentWidget(), CombosPage))
        self._update_action()
