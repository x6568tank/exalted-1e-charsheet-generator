"""Qt spike: four shapes for the Traits tab, over one character, side by side.

Input: a real RuleSet + Character (an examples/ file). Output: a window with a
VARIANT switcher and a CHARACTER switcher, rendering the same traits four ways.
Mechanism: each `build_*` fills a QWidget with the same rows — the real
`qt.editor.DotTrack`, the real `qt.theme` palette — so the only thing that differs
between variants is the CONTAINER.

Answers the human's question (2026-08-22): "should we change the design of the Traits
tab to be more inline with the rest of the app? The dot-displays are non-negotiable,
but it feels a little odd being a UI of scrolled cards."

The four:

  0 · Cards       what ships today — a vertical scroll of _Panel cards. The baseline.
  1 · Sub-tabs    a sub-tab per category, flat panes, no card chrome. This is already
                  the settled tab layout's own idiom ("a sub-tab per category where a
                  tab has more than one"), so it is the cheapest way to be "in line".
  2 · Sheet grid  everything on ONE pane in newspaper columns, headings instead of
                  cards. Closest to the paper sheet.
  3 · Flat rules  one scroll like today, but the cards become headings + hairlines.
                  Isolates "is it the CARDS or the SCROLLING that reads wrong?"

⚠ This is a SPIKE. It renders the dot surface only — the deferred panels
(Specialties, Colleges, Virtue Flaw, health levels, Permanent Resonance) are drawn as
a labelled stub, because WHERE THEY LAND is part of what is being decided, not
something the spike should presuppose. Nothing here is wired to buying: the tracks
free-set, so clicking is safe and tells you nothing about the lock.

Run:  .venv/bin/python spikes/qt_traits/traits_spike.py
"""

import sys
from pathlib import Path

import exalted_builder
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QMainWindow, QScrollArea, QSplitter, QTabWidget, QToolBar, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

from exalted_builder.engine import derive, elder, health_actions, merits, validate
from exalted_builder.persistence import load_character
from exalted_builder.rules_db import load_ruleset
from exalted_builder.qt import theme as qtheme
from exalted_builder.qt.editor import DotTrack, _Panel, _ROW_SPACING
from exalted_builder.qt.layout import clear_layout
from exalted_builder.ui import theme
from exalted_builder.ui import view as viewmod
from exalted_builder.models.character import AbilityName, AttributeName, VirtueName

DATA_DIR = Path(exalted_builder.__file__).parent / "data"
EXAMPLES = sorted(Path("examples").glob("*.character.json"))

VARIANTS = ["0 · Cards (today)", "1 · Sub-tabs", "2 · Sheet grid", "3 · Flat rules",
            "4 · Collection (app language)", "5 · Sheet grid v2"]

# The panels Edit grew after the card layout was designed. Their home is part of the
# question, so the spike names them rather than placing them.
EXTRA_PANELS = ["Specialties", "Astrological Colleges", "Virtue Flaw",
                "Bonus health levels", "Permanent Resonance"]


def _label(value: str) -> str:
    return value.replace("_", " ").title()


class TraitData:
    """Everything the four builders need, derived once. Mirrors what
    `qt/editor.py::TraitsPage._build_body` computes, minus the buying plumbing."""

    def __init__(self, ruleset, char):
        self.ruleset, self.char = ruleset, char
        self.pal = theme.palette(char.exalt_type)
        self.accent = qtheme.accent(self.pal)
        caste_def = ruleset.castes.get(char.caste)
        self.caste_abilities = set(caste_def.caste_abilities) if caste_def else set()
        self.favored = set(char.favored_abilities)
        self.b = validate.effective_budgets(ruleset, char)
        self.mf = merits.merits_and_flaws_calc(ruleset, char)
        self.attr_cap = elder.trait_ceiling(char, ruleset, domain="attribute")
        self.abil_cap = elder.trait_ceiling(char, ruleset, domain="ability")
        self.virtue_cap = (self.mf.virtue_cap if self.mf.virtue_cap is not None
                           else merits.DOT_MAX)
        self.essence_cap, _ = elder.essence_cap(ruleset, char)
        self.ability_groups = viewmod.ability_group_defs(ruleset, char.exalt_type)
        # The panels that landed on Traits after the card layout was designed. Each is
        # asked of the ENGINE, never of the splat name — `perm_cap` non-zero IS the
        # "holds Death's Taint" test, and `college_dots` is the "ships Colleges" one.
        self.has_virtue_flaw = derive.has_virtue_flaw(ruleset, char)
        self.perm_cap = derive.permanent_limit_cap(ruleset, char)
        self.limit_label = derive.limit_label(ruleset, char)
        self.college_dots = self.b.college_dots

    def track(self, get, setv, lo, hi):
        return DotTrack(get, setv, lo, hi, accent=self.accent)

    def attr_row(self, a: AttributeName):
        char = self.char
        return self._row(_label(a.value),
                         "●" if a in self.caste_abilities else "",
                         self.track(lambda: char.attributes[a],
                                    lambda v: char.attributes.__setitem__(a, v),
                                    1, self.attr_cap))

    def ability_row(self, a: AbilityName, *, specialties: bool = False):
        char = self.char
        mark = "●" if a in self.caste_abilities else ("✦" if a in self.favored else "")
        row = self._row(_label(a.value), mark,
                        self.track(lambda: char.abilities[a],
                                   lambda v: char.abilities.__setitem__(a, v),
                                   0, self.abil_cap))
        if specialties:
            # Specialties hang off the Ability they belong to rather than living in a
            # section of their own (human, 2026-08-22). ⚠ A specialty is an INSTANCE,
            # not a rated trait — taking "Swords" twice is two instances, which is why
            # a repeat shows as ×2 and never as a second dot.
            row.insertWidget(row.count() - 1, self._specialty_chips(a))
        return row

    def specialties_for(self, a: AbilityName) -> dict:
        """{name: how many instances} for one Ability, in insertion order."""
        counts: dict = {}
        for sp in self.char.specialties:
            if sp.ability == a and sp.name:
                counts[sp.name] = counts.get(sp.name, 0) + 1
        return counts

    def _specialty_chips(self, a: AbilityName) -> QWidget:
        holder = QWidget()
        lay = QHBoxLayout(holder)
        lay.setContentsMargins(8, 0, 0, 0)
        lay.setSpacing(4)
        for name, count in self.specialties_for(a).items():
            chip = QLabel(f"{name} ×{count}" if count > 1 else name)
            chip.setStyleSheet(
                f"color:{self.accent}; border:1px solid #55535a; border-radius:7px; "
                f"padding:0px 6px; font-size:8pt;")
            lay.addWidget(chip)
        add = QLabel("+")
        add.setToolTip(f"Add a specialty in {_label(a.value)}")
        add.setCursor(Qt.PointingHandCursor)
        add.setStyleSheet(f"color:{qtheme.MUTED}; font-weight:700; padding:0px 4px;")
        lay.addWidget(add)
        return holder

    def virtue_row(self, v: VirtueName):
        char = self.char
        return self._row(_label(v.value), "",
                         self.track(lambda: char.virtues[v],
                                    lambda val: char.virtues.__setitem__(v, val),
                                    1, self.virtue_cap))

    def _row(self, name: str, mark: str, track) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(6)
        m = QLabel(mark)
        m.setFixedWidth(12)
        m.setStyleSheet(f"color:{self.accent};")
        row.addWidget(m)
        label = QLabel(name)
        label.setMinimumWidth(88)
        row.addWidget(label)
        row.addWidget(track)
        # ⚠ The stretch goes AFTER the track, never on the label. On the label it
        # pushes the dots to the far edge of the column — unnoticeable inside a narrow
        # card, glaring the moment the column is full width.
        row.addStretch(1)
        return row

    # --- headings the real tab shows ------------------------------------- #

    def attr_header(self) -> str:
        pools = "/".join(str(p) for p in
                         validate.effective_attribute_pools(self.ruleset, self.char))
        return (viewmod.attribute_budget_summary(self.ruleset, self.char)
                or f"prioritise {pools}")

    def ability_header(self) -> str:
        b = self.b
        return (f"{b.ability_dots} dots; ≥{b.ability_min_caste_favored} caste/favoured; "
                f"≤{b.ability_cap_pre_bp} each pre-bonus")


def _heading(text: str, data: TraitData, *, size: int = 0) -> QLabel:
    label = QLabel(text)
    css = f"font-weight:700; color:{data.accent}; letter-spacing:1px;"
    if size:
        css += f" font-size:{size}pt;"
    label.setStyleSheet(css)
    return label


def _sub(text: str) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet(f"color:{qtheme.MUTED}; font-size:9pt;")
    return label


def _rule() -> QFrame:
    line = QFrame()
    line.setFixedHeight(1)
    line.setStyleSheet("background:#55535a;")
    return line


def _vsep() -> QFrame:
    line = QFrame()
    line.setFixedWidth(1)
    line.setStyleSheet("background:#55535a;")
    return line


def _extras_stub(data: TraitData) -> QVBoxLayout:
    """⚠ Deliberately a STUB. Where these five land is part of the decision."""
    lay = QVBoxLayout()
    lay.setSpacing(2)
    lay.addWidget(_sub("— the panels that need a home in this layout —"))
    for name in EXTRA_PANELS:
        row = QLabel(f"▫ {name}")
        row.setStyleSheet(f"color:{qtheme.MUTED}; font-style:italic;")
        lay.addWidget(row)
    return lay


# --------------------------------------------------------------------------- #
# the column builders — shared by every variant
# --------------------------------------------------------------------------- #

def _attribute_columns(data: TraitData) -> QHBoxLayout:
    cols = QHBoxLayout()
    cols.setSpacing(24)
    for i, (category, members) in enumerate(validate.ATTRIBUTE_CATEGORIES.items()):
        if i:
            cols.addWidget(_vsep())
        group = QVBoxLayout()
        group.setSpacing(_ROW_SPACING)
        cap = QLabel(category)
        cap.setStyleSheet(f"font-weight:600; color:{qtheme.MUTED};")
        group.addWidget(cap)
        for a in members:
            group.addLayout(data.attr_row(a))
        group.addStretch(1)
        cols.addLayout(group, 1)
    return cols


def _ability_columns(data: TraitData, per_row: int = 3) -> QVBoxLayout:
    outer = QVBoxLayout()
    outer.setSpacing(8)
    groups = data.ability_groups
    for start in range(0, len(groups), per_row):
        cols = QHBoxLayout()
        cols.setSpacing(24)
        for j, (group_label, abilities) in enumerate(groups[start:start + per_row]):
            if j:
                cols.addWidget(_vsep())
            group = QVBoxLayout()
            group.setSpacing(_ROW_SPACING)
            if group_label:
                g = QLabel(group_label)
                g.setStyleSheet(f"font-weight:600; color:{data.accent};")
                group.addWidget(g)
            for a in abilities:
                group.addLayout(data.ability_row(a))
            group.addStretch(1)
            cols.addLayout(group, 1)
        # A final row with fewer groups than the rest must be PADDED, or its columns
        # spread to fill the width and stop lining up with the rows above.
        for _ in range(per_row - len(groups[start:start + per_row])):
            cols.addStretch(1)
        outer.addLayout(cols)
    return outer


def _virtue_column(data: TraitData) -> QVBoxLayout:
    group = QVBoxLayout()
    group.setSpacing(_ROW_SPACING)
    for v in VirtueName:
        group.addLayout(data.virtue_row(v))
    group.addStretch(1)
    return group


def _essence_column(data: TraitData) -> QVBoxLayout:
    char = data.char
    group = QVBoxLayout()
    group.setSpacing(_ROW_SPACING)
    group.addLayout(data._row(
        "Essence", "",
        data.track(lambda: char.essence_rating,
                   lambda v: setattr(char, "essence_rating", v),
                   1, min(elder.DOT_MAX, data.essence_cap))))
    wp = QLabel("Willpower  6")
    group.addWidget(wp)
    group.addStretch(1)
    return group


def _crafts_column(data: TraitData) -> QVBoxLayout:
    char = data.char
    group = QVBoxLayout()
    group.setSpacing(_ROW_SPACING)
    if not char.crafts:
        group.addWidget(_sub("no craft focuses"))
    for cr in char.crafts:
        group.addLayout(data._row(
            cr.focus or "(unnamed craft)", "",
            data.track(lambda cr=cr: cr.rating,
                       lambda v, cr=cr: setattr(cr, "rating", v), 0, data.abil_cap)))
    group.addStretch(1)
    return group


# --------------------------------------------------------------------------- #
# variant 0 — cards (what ships today)
# --------------------------------------------------------------------------- #

def build_cards(data: TraitData) -> QWidget:
    body = QWidget()
    lay = QVBoxLayout(body)
    lay.setSpacing(8)

    def panel(title):
        card = _Panel(title, data.pal)
        lay.addWidget(card)
        return card.body()

    panel("Favoured Picks").addWidget(_sub("(the chip pickers)"))
    panel(f"Attributes ({data.attr_header()})").addLayout(_attribute_columns(data))
    panel(f"Abilities ({data.ability_header()})").addLayout(_ability_columns(data))
    panel("Crafts (each focus a separate Ability)").addLayout(_crafts_column(data))
    ve = QHBoxLayout()
    lay.addLayout(ve)
    v_card = _Panel("Virtues", data.pal)
    ve.addWidget(v_card)
    v_card.body().addLayout(_virtue_column(data))
    e_card = _Panel("Essence & Willpower", data.pal)
    ve.addWidget(e_card)
    e_card.body().addLayout(_essence_column(data))
    panel("…").addLayout(_extras_stub(data))
    lay.addStretch(1)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setWidget(body)
    return scroll


# --------------------------------------------------------------------------- #
# variant 1 — a sub-tab per category, flat panes
# --------------------------------------------------------------------------- #

def build_subtabs(data: TraitData) -> QWidget:
    tabs = QTabWidget()

    def pane(*blocks) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(10)
        for block in blocks:
            if isinstance(block, str):
                lay.addWidget(_sub(block))
            elif isinstance(block, QWidget):
                lay.addWidget(block)
            else:
                lay.addLayout(block)
        lay.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(w)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        return scroll

    tabs.addTab(pane(data.attr_header(), _attribute_columns(data)), "Attributes")
    tabs.addTab(pane(data.ability_header(), _ability_columns(data)), "Abilities")
    crafts = QHBoxLayout()
    crafts.addLayout(_crafts_column(data), 1)
    crafts.addWidget(_vsep())
    crafts.addLayout(_extras_stub(data), 1)
    tabs.addTab(pane("Each craft focus is a separate Ability.", crafts),
                "Crafts && Specialties")
    ve = QHBoxLayout()
    ve.setSpacing(24)
    v = QVBoxLayout()
    v.addWidget(_heading("VIRTUES", data))
    v.addLayout(_virtue_column(data))
    ve.addLayout(v, 1)
    ve.addWidget(_vsep())
    e = QVBoxLayout()
    e.addWidget(_heading("ESSENCE & WILLPOWER", data))
    e.addLayout(_essence_column(data))
    ve.addLayout(e, 1)
    tabs.addTab(pane(ve), "Virtues && Essence")
    return tabs


# --------------------------------------------------------------------------- #
# variant 2 — one sheet-like grid, no cards, no sub-tabs
# --------------------------------------------------------------------------- #

def build_sheet_grid(data: TraitData) -> QWidget:
    body = QWidget()
    grid = QGridLayout(body)
    grid.setContentsMargins(18, 14, 18, 14)
    grid.setHorizontalSpacing(28)
    grid.setVerticalSpacing(6)

    def section(row: int, col: int, title: str, sub: str, block) -> int:
        """Place one section in `col` starting at `row`; return the next free row.

        ⚠ The caller must ADVANCE by the returned value. Reusing the row a previous
        section STARTED at drops the next heading on top of it — grid cells overlap
        silently, and the first draft put CRAFTS through the middle of VIRTUES."""
        grid.addWidget(_heading(title, data, size=10), row, col)
        r = row + 1
        if sub:
            grid.addWidget(_sub(sub), r, col)
            r += 1
        grid.addWidget(_rule(), r, col)
        r += 1
        if isinstance(block, QWidget):
            grid.addWidget(block, r, col)
        else:
            holder = QWidget()
            holder.setLayout(block)
            grid.addWidget(holder, r, col)
        return r + 2          # +1 for the block, +1 for breathing room

    left = section(0, 0, "ATTRIBUTES", data.attr_header(), _attribute_columns(data))
    left = section(left, 0, "VIRTUES", "", _virtue_column(data))
    left = section(left, 0, "CRAFTS", "", _crafts_column(data))
    right = section(0, 1, "ABILITIES", data.ability_header(),
                    _ability_columns(data, per_row=2))
    right = section(right, 1, "ESSENCE & WILLPOWER", "", _essence_column(data))
    right = section(right, 1, "STILL TO PLACE", "", _extras_stub(data))
    grid.setRowStretch(max(left, right), 1)
    grid.setColumnStretch(0, 1)
    grid.setColumnStretch(1, 1)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setWidget(body)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    return scroll


# --------------------------------------------------------------------------- #
# variant 3 — one scroll, cards replaced by headings + hairlines
# --------------------------------------------------------------------------- #

def build_flat_rules(data: TraitData) -> QWidget:
    body = QWidget()
    lay = QVBoxLayout(body)
    lay.setContentsMargins(18, 14, 18, 14)
    lay.setSpacing(6)

    def section(title: str, sub: str, block):
        lay.addSpacing(8)
        lay.addWidget(_heading(title, data, size=10))
        if sub:
            lay.addWidget(_sub(sub))
        lay.addWidget(_rule())
        lay.addSpacing(4)
        (lay.addWidget(block) if isinstance(block, QWidget) else lay.addLayout(block))

    section("FAVOURED PICKS", "", _sub("(the chip pickers)"))
    section("ATTRIBUTES", data.attr_header(), _attribute_columns(data))
    section("ABILITIES", data.ability_header(), _ability_columns(data))
    section("CRAFTS", "Each focus is a separate Ability.", _crafts_column(data))
    ve = QHBoxLayout()
    ve.setSpacing(24)
    ve.addLayout(_virtue_column(data), 1)
    ve.addWidget(_vsep())
    ve.addLayout(_essence_column(data), 1)
    section("VIRTUES · ESSENCE · WILLPOWER", "", ve)
    section("STILL TO PLACE", "", _extras_stub(data))
    lay.addStretch(1)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setWidget(body)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    return scroll


# --------------------------------------------------------------------------- #
# variant 4 — the app's own design language: toolbar + table + detail pane
# --------------------------------------------------------------------------- #

def build_collection(data: TraitData) -> QWidget:
    """Traits as a COLLECTION — the shape Gear and Advantages already use.

    ⚠ A **QTreeWidget**, not a QTableWidget: that is what `qt/gear.py` and
    `qt/advantages.py` are built from, so it is what "the app's design language"
    actually means here. It also groups for free — category as a top-level row — which
    a flat table cannot do without sorting Appearance, Archery and Athletics into one
    meaningless run.

    TWO sub-tabs (human, 2026-08-22), which is the settled layout's own rule — a
    sub-tab per category where a tab has more than one:

      Attributes & Abilities   the dot surface, third column SPECIALTIES
      Virtues & Advantages     everything else, third column NOTES

    ⚠ **The two sub-tabs do NOT share a third column.** Specialties hang off Abilities
    and nothing else — a Virtue cannot have one — so carrying a "Specialties" header
    over an all-empty column would be a promise the rules do not make. The second tab
    carries free NOTES instead: the flawed Virtue, a college's house, a health tier's
    printed count.
    """
    char, ruleset = data.char, data.ruleset
    outer = QWidget()
    lay = QVBoxLayout(outer)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(0)

    bar = QToolBar()
    bar.setMovable(False)
    lay.addWidget(bar)
    tabs = QTabWidget()
    lay.addWidget(tabs, 1)

    def dots_cell(track) -> QWidget:
        """⚠ Wrap the track and pad it. A bare DotTrack in a column wider than itself
        spreads its pips across the whole width — QHBoxLayout hands the slack to the
        gaps between fixed-size children."""
        holder = QWidget()
        box = QHBoxLayout(holder)
        box.setContentsMargins(2, 1, 2, 1)
        box.addWidget(track)
        box.addStretch(1)
        return holder

    def make_tab(third_column: str, name: str):
        """A sub-tab: tree on the left, detail pane on the right. Returns
        (tree, add_group, add_leaf, detail_layout)."""
        page = QWidget()
        page_lay = QVBoxLayout(page)
        page_lay.setContentsMargins(0, 0, 0, 0)
        split = QSplitter(Qt.Orientation.Horizontal)
        page_lay.addWidget(split, 1)
        tree = QTreeWidget()
        tree.setColumnCount(3)
        tree.setHeaderLabels(["Trait", "Rating", third_column])
        # ⚠ NAMED. `findChildren(QTreeWidget)[1]` does not reliably hand back the second
        # sub-tab's tree — it bit the verification script for this very spike.
        tree.setObjectName(name)
        tree.setUniformRowHeights(False)
        split.addWidget(tree)
        detail = QWidget()
        detail_lay = QVBoxLayout(detail)
        detail_lay.setContentsMargins(14, 12, 14, 12)
        detail_lay.setSpacing(6)
        split.addWidget(detail)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        tree.setColumnWidth(0, 240)
        tree.setColumnWidth(1, 150)

        def add_group(title):
            node = QTreeWidgetItem(tree, [title])
            font = node.font(0)
            font.setBold(True)
            node.setFont(0, font)
            node.setExpanded(True)
            return node

        def add_leaf(parent, name, mark="", track=None, note="", kind=""):
            item = QTreeWidgetItem(parent, [f"{mark} {name}".strip(), "", note])
            if track is not None:
                tree.setItemWidget(item, 1, dots_cell(track))
            item.setData(0, Qt.ItemDataRole.UserRole, (name, kind))
            return item

        return page, tree, add_group, add_leaf, detail_lay

    # ---- sub-tab 1: attributes & abilities ------------------------------- #
    page1, tree1, group1, leaf1, detail1 = make_tab("Specialties", "traits.dots")
    for category, members in validate.ATTRIBUTE_CATEGORIES.items():
        node = group1(f"Attributes · {category}")
        for a in members:
            leaf1(node, _label(a.value),
                  "●" if a in data.caste_abilities else "",
                  data.track(lambda k=a: char.attributes[k],
                             lambda v, k=a: char.attributes.__setitem__(k, v),
                             1, data.attr_cap), kind="attribute")
    for group_label, abilities in data.ability_groups:
        node = group1(f"Abilities · {group_label}" if group_label else "Abilities")
        for a in abilities:
            extra = data.specialties_for(a)
            leaf1(node, _label(a.value),
                  "●" if a in data.caste_abilities else ("✦" if a in data.favored else ""),
                  data.track(lambda k=a: char.abilities[k],
                             lambda v, k=a: char.abilities.__setitem__(k, v),
                             0, data.abil_cap),
                  " · ".join(f"{n} ×{c}" if c > 1 else n for n, c in extra.items()),
                  kind="ability")
    if char.crafts:
        node = group1("Abilities · Craft")
        for cr in char.crafts:
            leaf1(node, cr.focus or "(unnamed craft)", "",
                  data.track(lambda k=cr: k.rating,
                             lambda v, k=cr: setattr(k, "rating", v),
                             0, data.abil_cap), kind="craft")
    tabs.addTab(page1, "Attributes && Abilities")

    # ---- sub-tab 2: virtues, essence, willpower and the rest ------------- #
    page2, tree2, group2, leaf2, detail2 = make_tab("Notes", "traits.rest")
    node = group2("Virtues · Essence · Willpower")
    flawed = char.virtue_flaw.virtue if char.virtue_flaw else None
    for v in VirtueName:
        leaf2(node, _label(v.value), "",
              data.track(lambda k=v: char.virtues[k],
                         lambda val, k=v: char.virtues.__setitem__(k, val),
                         1, data.virtue_cap),
              "flawed Virtue" if v == flawed else "", kind="virtue")
    leaf2(node, "Essence", "",
          data.track(lambda: char.essence_rating,
                     lambda v: setattr(char, "essence_rating", v),
                     1, min(elder.DOT_MAX, data.essence_cap)),
          "personal & peripheral pools follow from this", kind="essence")
    leaf2(node, "Willpower", note="6 — the two highest Virtues, pinned at the lock",
          kind="willpower")
    if data.has_virtue_flaw:
        leaf2(node, "Virtue Flaw",
              note=(char.virtue_flaw.description if char.virtue_flaw
                    and char.virtue_flaw.description else "none chosen"),
              kind="virtue_flaw")

    if data.college_dots and ruleset.colleges:
        node = group2("Astrological Colleges")
        for cr in char.colleges:
            col = ruleset.colleges.get(cr.college_id)
            leaf2(node, col.name if col else cr.college_id,
                  "★" if col and col.house == char.caste else "",
                  data.track(lambda k=cr: k.rating,
                             lambda v, k=cr: setattr(k, "rating", v), 0, 5),
                  col.house_label if col else "not in the catalogue", kind="college")
        if not char.colleges:
            leaf2(node, "(none yet)", note="use Add college", kind="college")

    node = group2("Health levels")
    for tier in health_actions.EDITABLE_TIERS:
        total = health_actions.level_total(char, tier)
        base = health_actions.BASE_COUNTS.get(tier, 0)
        delta = ("" if total == base
                 else f"  ({total - base:+d} from Charms or curses)")
        leaf2(node, "-0" if tier == 0 else str(tier),
              note=f"{total} level(s) · printed {base}{delta}", kind="health")

    if data.perm_cap:
        node = group2(f"Permanent {data.limit_label}")
        leaf2(node, f"Permanent {data.limit_label}",
              note=f"{char.limit_permanent} of {data.perm_cap} — capped at Essence; "
                   f"gained on overflow, shed with a Harrowing",
              kind="resonance")
    tabs.addTab(page2, "Virtues && Advantages")

    # ---- toolbars follow the sub-tab ------------------------------------- #
    ACTIONS = {0: ("Add craft", "Add specialty", "Favoured picks…"),
               1: ("Add college", "Set Virtue Flaw…", "Gain/shed Resonance…")}

    def retool(index: int) -> None:
        bar.clear()
        for action in ACTIONS.get(index, ()):
            bar.addAction(action)

    tabs.currentChanged.connect(retool)
    retool(0)

    # ---- detail panes ----------------------------------------------------- #
    def detail_for(tree, detail_lay):
        def show():
            clear_layout(detail_lay)
            item = tree.currentItem()
            payload = item.data(0, Qt.ItemDataRole.UserRole) if item else None
            if not payload:
                detail_lay.addWidget(_sub("Select a trait."))
                detail_lay.addStretch(1)
                return
            name, kind = payload
            detail_lay.addWidget(_heading(name.upper(), data, size=11))
            parent = item.parent()
            detail_lay.addWidget(_sub(parent.text(0) if parent else ""))
            detail_lay.addWidget(_rule())
            blurb = {
                "ability": "Specialties — max 3 per Ability; take one twice to stack "
                           "it.\n[ + add specialty ]",
                "craft": "Each craft focus is a separate Ability.",
                "attribute": "Caps, breed bonuses and the buy price print here.",
                "virtue": "The flawed Virtue is chosen here, with the book's sample "
                          "Flaws for it.",
                "willpower": "Pinned to the two highest Virtues at the lock; raising a "
                             "Virtue afterwards does NOT raise it.",
                "virtue_flaw": "Flawed Virtue, a sample Flaw to fill the description, "
                               "and the Limit Break Condition.",
                "college": "★ marks your Maiden's house. Reducible to 0.",
                "health": "Charms raise a tier, curses lower it. The stored value is "
                          "the DELTA from the printed track.",
                "resonance": "Gain is free and logged; shedding costs 5 XP and a "
                             "Harrowing.",
                "essence": "Drives both Essence pools and every trait ceiling past 5.",
            }.get(kind, "")
            if blurb:
                detail_lay.addWidget(_sub(blurb))
            detail_lay.addStretch(1)
        return show

    show1, show2 = detail_for(tree1, detail1), detail_for(tree2, detail2)
    tree1.currentItemChanged.connect(lambda *_: show1())
    tree2.currentItemChanged.connect(lambda *_: show2())
    show1()
    show2()
    return outer


# --------------------------------------------------------------------------- #
# variant 5 — the sheet grid, revised against the human's notes
# --------------------------------------------------------------------------- #

def build_sheet_grid_v2(data: TraitData) -> QWidget:
    """Variant 2 with the three notes applied (human, 2026-08-22):

    * Attributes are no longer three wide columns — nine rows in one narrow column,
      which is what nine traits deserve next to twenty-five.
    * Crafts moved UNDER Abilities, where they belong: each focus is an Ability.
    * Virtues, Essence, Willpower and the Virtue Flaw merged into ONE section — none
      of them has enough in it to hold a section open alone.
    * Specialties are gone as a section; they hang off their Ability's row.
    """
    body = QWidget()
    grid = QGridLayout(body)
    grid.setContentsMargins(18, 14, 18, 14)
    grid.setHorizontalSpacing(28)
    grid.setVerticalSpacing(6)

    def section(row: int, col: int, title: str, sub: str, block) -> int:
        grid.addWidget(_heading(title, data, size=10), row, col)
        r = row + 1
        if sub:
            grid.addWidget(_sub(sub), r, col)
            r += 1
        grid.addWidget(_rule(), r, col)
        r += 1
        if isinstance(block, QWidget):
            grid.addWidget(block, r, col)
        else:
            holder = QWidget()
            holder.setLayout(block)
            grid.addWidget(holder, r, col)
        return r + 2

    # left: attributes in ONE column, then the merged virtue/essence block
    attrs = QVBoxLayout()
    attrs.setSpacing(_ROW_SPACING)
    for category, members in validate.ATTRIBUTE_CATEGORIES.items():
        cap = QLabel(category)
        cap.setStyleSheet(f"font-weight:600; color:{qtheme.MUTED};")
        attrs.addWidget(cap)
        for a in members:
            attrs.addLayout(data.attr_row(a))
    attrs.addStretch(1)
    left = section(0, 0, "ATTRIBUTES", data.attr_header(), attrs)

    merged = QVBoxLayout()
    merged.setSpacing(_ROW_SPACING)
    for v in VirtueName:
        merged.addLayout(data.virtue_row(v))
    merged.addSpacing(6)
    merged.addLayout(data._row(
        "Essence", "",
        data.track(lambda: data.char.essence_rating,
                   lambda v: setattr(data.char, "essence_rating", v),
                   1, min(elder.DOT_MAX, data.essence_cap))))
    wp = QHBoxLayout()
    wp.addWidget(QLabel("Willpower"))
    wp.addWidget(QLabel("6"))
    wp.addStretch(1)
    merged.addLayout(wp)
    merged.addSpacing(6)
    flaw = QLabel("Virtue Flaw:  ▫ none chosen")
    flaw.setStyleSheet(f"color:{qtheme.MUTED}; font-style:italic;")
    merged.addWidget(flaw)
    merged.addStretch(1)
    left = section(left, 0, "VIRTUES · ESSENCE · WILLPOWER", "", merged)

    # right: abilities with inline specialties, then crafts underneath them
    abilities = QVBoxLayout()
    abilities.setSpacing(8)
    groups = data.ability_groups
    for start in range(0, len(groups), 2):
        cols = QHBoxLayout()
        cols.setSpacing(24)
        for j, (group_label, members) in enumerate(groups[start:start + 2]):
            if j:
                cols.addWidget(_vsep())
            group = QVBoxLayout()
            group.setSpacing(_ROW_SPACING)
            if group_label:
                g = QLabel(group_label)
                g.setStyleSheet(f"font-weight:600; color:{data.accent};")
                group.addWidget(g)
            for a in members:
                group.addLayout(data.ability_row(a, specialties=True))
            group.addStretch(1)
            cols.addLayout(group, 1)
        for _ in range(2 - len(groups[start:start + 2])):
            cols.addStretch(1)
        abilities.addLayout(cols)
    crafts_head = QLabel("Craft")
    crafts_head.setStyleSheet(f"font-weight:600; color:{data.accent};")
    abilities.addWidget(crafts_head)
    abilities.addLayout(_crafts_column(data))
    right = section(0, 1, "ABILITIES", data.ability_header(), abilities)

    still = QVBoxLayout()
    still.setSpacing(2)
    still.addWidget(_sub("— still unplaced —"))
    for name in ("Astrological Colleges", "Bonus health levels",
                 "Permanent Resonance"):
        row = QLabel(f"▫ {name}")
        row.setStyleSheet(f"color:{qtheme.MUTED}; font-style:italic;")
        still.addWidget(row)
    right = section(right, 1, "STILL TO PLACE", "", still)
    grid.setRowStretch(max(left, right), 1)
    grid.setColumnStretch(0, 2)
    grid.setColumnStretch(1, 3)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setWidget(body)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    return scroll


BUILDERS = [build_cards, build_subtabs, build_sheet_grid, build_flat_rules,
            build_collection, build_sheet_grid_v2]


# --------------------------------------------------------------------------- #

class SpikeWindow(QMainWindow):
    def __init__(self, ruleset, characters):
        super().__init__()
        self._ruleset = ruleset
        self._characters = characters
        self.resize(1180, 900)

        central = QWidget()
        outer = QVBoxLayout(central)
        bar = QHBoxLayout()
        bar.addWidget(QLabel("Variant"))
        self.variant = QComboBox()
        self.variant.addItems(VARIANTS)
        self.variant.currentIndexChanged.connect(self._redraw)
        bar.addWidget(self.variant)
        bar.addSpacing(24)
        bar.addWidget(QLabel("Character"))
        self.character = QComboBox()
        for label, _c in characters:
            self.character.addItem(label)
        self.character.currentIndexChanged.connect(self._redraw)
        bar.addWidget(self.character, 1)
        outer.addLayout(bar)
        self._host = QVBoxLayout()
        outer.addLayout(self._host, 1)
        self.setCentralWidget(central)
        self._redraw()

    def _redraw(self):
        clear_layout(self._host)
        _label_, char = self._characters[self.character.currentIndex()]
        data = TraitData(self._ruleset, char)
        qtheme.apply(self, data.pal)
        self.setWindowTitle(f"Traits spike — {VARIANTS[self.variant.currentIndex()]} "
                            f"— {char.name or char.id}")
        self._host.addWidget(BUILDERS[self.variant.currentIndex()](data))


def main() -> None:
    app = QApplication(sys.argv)
    ruleset = load_ruleset(DATA_DIR)
    characters = []
    for path in EXAMPLES:
        char = load_character(path)
        characters.append((f"{char.name or path.stem} — {char.exalt_type}", char))
    if not characters:
        print("no examples/*.character.json found", file=sys.stderr)
        raise SystemExit(1)
    win = SpikeWindow(ruleset, characters)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
