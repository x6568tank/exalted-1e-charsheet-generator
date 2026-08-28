"""exalted_builder/qt/adversaries.py — the Adversaries tab of the native Party window.

Input: a RuleSet, the shared context (for `party` and `adversary_catalog`). Output: the
settled collection layout — a toolbar (Add / Duplicate / Reset / Delete), a sortable
table of the roster, and the selected entry's trackers-and-editor in a detail pane.
Mechanism: `reload()` refills the table from `party.adversaries` and re-selects what was
selected; every widget in the detail pane writes its own field straight to the model and
re-syncs only the row it changed, so a keystroke never rebuilds the pane under the
cursor. Every computed number comes from `engine.adversaries`; every roster mutation
goes through it too.

⚠ **This tab is where an adversary is EDITED; the Party tab is where a fight is RUN.**
The roster is drawn twice on purpose. Here it is a collection like Gear and Advantages —
a table, and the editor that was a modal dialog on the webapp as the detail pane. On the
Party tab it is a grid of live tracker cards beside the characters fighting it
(`qt/party.py::_adversary_card`), which is what the webapp had and what the port dropped:
one detail pane shows exactly one bandit's health, and "gming combat is a challenge"
(human, 2026-08-28). `AdversaryTrackers` below is the ONE tracker both surfaces use.
The table's **Damage** column is not decoration either — it is the at-a-glance readout
while you are on this tab.

⚠ **An `Adversary` is NOT a `Character`.** Nothing here validates, prices or locks, and
no dot tracks: these values are typed off a page or invented on the spot, never bought,
so a stepper with a rules cap would be lying about what governs them.

⚠ **The dead-field class of bug is what this surface has already produced once** —
`powers`, `combat_pool` and `cost_to_dematerialize` were authored, editable nowhere, and
silently wiped on save. `tests/test_qt_adversaries.py` walks `Adversary.model_fields`
and drives each widget, so a new field fails until it is wired to both ends.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QFrame, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QPlainTextEdit, QPushButton, QScrollArea, QSizePolicy, QSpinBox,
    QSplitter,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from exalted_builder.engine import adversaries as adv
from exalted_builder.models.adversary import Adversary
from exalted_builder.models.rules import Damage
from exalted_builder.ui import theme
from exalted_builder.ui import view as viewmod

from .catalogue import CatalogueDialog
from .layout import clear_layout, empty_note
from .theme import CARD, INPUT, MUTED, accent as accent_light
from .trackers import MARK_FILL, box as tracker_box, restyle as restyle_box

_COLUMNS = ("Name", "Categories", "Damage", "Stats")

# Qt has no flex-wrap; a health track runs to 22 boxes on a Deathlord, so it wraps by
# construction — the same reason `qt/play.py` carries this number.
_BOXES_PER_ROW = 11

_ATTRIBUTES = ["strength", "dexterity", "stamina", "charisma", "manipulation",
               "appearance", "perception", "intelligence", "wits"]
_VIRTUES = ["compassion", "conviction", "temperance", "valor"]

# ⚠ `0` MEANS ABSENT in the trait grids, and it is honest here rather than a shortcut:
# a beast prints three of the nine Attributes (p.316 says the rest default to
# Intelligence 1, Perception 2, Wits 3), and no printed block carries a rating of zero.
# The box shows "—" at its minimum so the grid never claims the book printed a 0.
_ABSENT = "—"

# The nullable combat numbers, where absent is NOT zero: the Bear prints no dodge figure
# (p.316) and Nagezzer prints the literal "Does not dodge" (p.307). Their spin boxes run
# from -1, shown as "—", so both states are reachable.
_NULLABLE = (
    ("base_initiative", "Base initiative", ""),
    ("combat_pool", "Combat pool",
     "Extras only: the one pool that stands in for every roll they make (p.241). "
     "Leave blank for anything with real traits."),
    ("dodge", "Dodge pool", "Blank if the creature does not dodge at all"),
)

_SOAK = (("soak_lethal", "Natural soak L", ""), ("soak_bashing", "Natural soak B", ""))

_POOLS = (
    ("willpower", "Willpower", ""),
    ("essence", "Essence", ""),
    ("essence_pool", "Essence pool",
     "A spirit's single pool. Leave 0 for an Exalt and use Personal + Peripheral."),
    ("personal_essence", "Personal", ""),
    ("peripheral_essence", "Peripheral", ""),
    ("cost_to_materialize", "Cost to materialize", ""),
    ("cost_to_dematerialize", "Cost to dematerialize",
     "Elementals pay this instead — their natural state is the physical one (p.295)."),
)

# ⚠ `categories` is NOT in this table: it is a codec line (comma-separated), not a
# plain string field, so it is built separately in `_identity_panel`.
_IDENTITY = (
    ("name", "Name", ""),
    ("nature", "Nature", ""),
    ("caste", "Caste / Aspect", ""),
)

_PROSE = (
    ("powers", "Powers",
     "The separate Powers line ghosts and elementals print — "
     "\"Materialize, Measure the Wind\""),
    ("charms", "Charms", ""),
    ("spells", "Spells", ""),
    ("notes", "Other notes", ""),
)

_ADD_SUBTITLE = ("Pick a template to start from — you get an editable copy, and the "
                 "catalogue entry is untouched.")


class AdversaryTrackers(QWidget):
    """One adversary's live trackers — health, Willpower, Essence — as a widget.

    Input: an `Adversary`, the accent to paint it in, a name `prefix` for the boxes and
    an `on_change` the owner uses to re-render whatever else shows these numbers.
    Output: up to three panels, each a heading over its boxes. Mechanism: a click writes
    through `engine.adversaries` and then RESTYLES the boxes and re-texts the headings it
    changed; nothing here is ever torn down by its own click.

    ⚠ **ONE trackers widget, used twice.** The Adversaries detail pane and the Party
    tab's roster cards draw the same boxes for the same entries — a second copy is how
    the two drift, and drift here means two answers to "how hurt is this bandit".

    ⚠ **`framed` is presentation only.** In the detail pane each panel is its own card;
    on a roster card the surrounding card already supplies the shade, and a card inside a
    card reads as a rendering fault.

    ⚠ **A click never rebuilds this widget** (see `trackers.restyle`). The one change
    that legitimately re-lengthens the boxes is an edit to `health_levels`, and that goes
    through the owner's rebuild, not through here.
    """

    def __init__(self, entry: Adversary, accent: str, *, prefix: str = "adv",
                 on_change=None, framed: bool = True, box_size: int = 28,
                 boxes_per_row: int = _BOXES_PER_ROW, parent=None):
        super().__init__(parent)
        self._a = entry
        self._accent = accent
        self._prefix = prefix
        self._on_change = on_change or (lambda: None)
        self._framed = framed
        self._box_size = box_size
        self._per_row = boxes_per_row

        self._health_boxes: list = []
        self._wp_boxes: list = []
        self._health_head: QLabel | None = None
        self._wp_head: QLabel | None = None
        self._essence_head: QLabel | None = None
        self._motes_spin: QSpinBox | None = None

        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(4 if framed else 3)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self._build()
        # ⚠ A HARD floor, set after building, and it is not belt-and-braces. A card is a
        # stack of word-wrapped labels, and a word-wrapped QLabel answers
        # `heightForWidth` — which makes the enclosing QGridLayout's idea of how tall the
        # card needs to be smaller than the truth. Every label then shrinks gracefully
        # and the only things that CANNOT are these fixed-size boxes, so the health row
        # was clipped to half height and painted through the Willpower heading below it
        # (2026-08-28). A minimum height on the widget is a floor no parent layout may
        # go under; a size policy alone was not enough. Invisible to all 3,065 tests —
        # only a render showed it.
        self.setMinimumHeight(self._lay.minimumSize().height())

    # ---- construction ---------------------------------------------------- #

    def _panel(self, title: str) -> tuple[QVBoxLayout, QLabel]:
        """A heading over a body, carded when `framed`. Returns both, because every
        heading here carries a live count that is re-texted rather than rebuilt."""
        # ⚠ NOT word-wrapped. A wrapped QLabel answers `heightForWidth`, which
        # `QGridLayout` does not honour — and these headings sit on cards a grid lays
        # out, so wrapping them makes the card too short and clips the boxes below.
        head = QLabel(title)
        head.setStyleSheet(f"font-weight:700; letter-spacing:1px; color:{self._accent};"
                           + ("" if self._framed else " font-size:11px;"))
        body = QVBoxLayout()
        # ⚠ Margins zeroed: a nested QVBoxLayout inherits an 11px default on all four
        # sides, and three of them down a card add 66px of nothing between each heading
        # and the boxes it labels.
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(3)
        if not self._framed:
            self._lay.addWidget(head)
            self._lay.addLayout(body)
            return body, head
        frame = QFrame()
        frame.setObjectName("advPanel")
        frame.setStyleSheet(
            f"QFrame#advPanel {{ background:{CARD}; border-radius:6px; }}")
        inner = QVBoxLayout(frame)
        inner.setContentsMargins(10, 8, 10, 8)
        inner.setSpacing(4)
        inner.addWidget(head)
        inner.addLayout(body)
        self._lay.addWidget(frame)
        return body, head

    def _build(self) -> None:
        a = self._a
        marks = adv.normalize_damage(a)
        body, self._health_head = self._panel(self._health_title())
        if not a.health_levels:
            note = QLabel("No health track — set one under Combat below.")
            note.setWordWrap(True)
            note.setStyleSheet(f"color:{MUTED};")
            body.addWidget(note)
        row = None
        for i in range(len(a.health_levels)):
            if i % self._per_row == 0:
                row = QHBoxLayout()
                row.setSpacing(4)
                body.addLayout(row)
            cell = QVBoxLayout()
            cell.setSpacing(1)
            # The wound penalty is CAPTIONED, not just a tooltip: which box to mark next
            # is what a Storyteller reads off a card mid-fight, and a hover is no use
            # when six of them are on screen at once.
            caption = QLabel(adv.level_label(a.health_levels[i]))
            caption.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            caption.setStyleSheet(f"color:{MUTED}; font-size:10px;")
            cell.addWidget(caption)
            mark = marks[i]
            button = tracker_box(f"{self._prefix}.health.{i}", self._box_size,
                                 MARK_FILL[mark] if mark else INPUT,
                                 self._accent, mark.value if mark else "")
            button.clicked.connect(lambda _c=False, index=i: self.cycle(index))
            self._health_boxes.append(button)
            cell.addWidget(button)
            row.addLayout(cell)
        if row is not None:
            row.addStretch(1)

        if a.willpower:
            body, self._wp_head = self._panel(self._willpower_title())
            track = QHBoxLayout()
            track.setSpacing(4)
            for i in range(a.willpower):
                button = tracker_box(f"{self._prefix}.willpower_spent.{i}",
                                     max(16, self._box_size - 8),
                                     self._accent if i < a.willpower_spent else INPUT,
                                     self._accent)
                button.clicked.connect(lambda _c=False, index=i: self.count(index))
                self._wp_boxes.append(button)
                track.addWidget(button)
            track.addStretch(1)
            body.addLayout(track)

        cap = adv.mote_cap(a)
        if cap:
            body, self._essence_head = self._panel(self._essence_title())
            spin = QSpinBox()
            spin.setObjectName(f"{self._prefix}.motes_spent")
            spin.setRange(0, cap)
            spin.setValue(min(a.motes_spent, cap))
            # ⚠ No rebuild from a spin box either: a redraw deletes the widget
            # mid-keystroke and takes the focus with it. The heading is re-texted.
            spin.valueChanged.connect(self._write_motes)
            self._motes_spin = spin
            row = QHBoxLayout()
            label = QLabel("Motes spent")
            label.setStyleSheet(f"color:{MUTED};")
            label.setMinimumWidth(90)
            row.addWidget(label)
            spin.setFixedWidth(88)
            row.addWidget(spin)
            row.addStretch(1)
            body.addLayout(row)

    # ---- headings -------------------------------------------------------- #

    def _health_title(self) -> str:
        a = self._a
        penalty = adv.worst_penalty(a)
        shown = ("none" if penalty is None
                 else "Incap" if penalty == adv.INCAPACITATED else str(penalty))
        counts = {d: sum(1 for m in adv.normalize_damage(a) if m == d) for d in Damage}
        return (f"HEALTH   ·   penalty {shown}   ·   "
                f"{counts[Damage.BASHING]}/ {counts[Damage.LETHAL]}x "
                f"{counts[Damage.AGGRAVATED]}*")

    def _willpower_title(self) -> str:
        a = self._a
        return f"WILLPOWER   ({a.willpower - a.willpower_spent}/{a.willpower})"

    def _essence_title(self) -> str:
        a = self._a
        cap = adv.mote_cap(a)
        shape = ("one pool" if a.essence_pool
                 else f"{a.personal_essence} personal + {a.peripheral_essence} peripheral")
        return f"ESSENCE   ({max(0, cap - a.motes_spent)}/{cap} left — {shape})"

    # ---- writes ---------------------------------------------------------- #

    def cycle(self, index: int) -> None:
        """Advance one health box through none → bashing → lethal → aggravated."""
        adv.cycle_mark(self._a, index)
        self.sync()
        self._on_change()

    def count(self, index: int) -> None:
        """Click the Willpower track at `index` — spend up to it, or back off to it."""
        adv.set_count(self._a, "willpower_spent", index, self._a.willpower)
        self.sync()
        self._on_change()

    def _write_motes(self, value: int) -> None:
        adv.set_motes_spent(self._a, value)
        if self._essence_head is not None:
            self._essence_head.setText(self._essence_title())
        self._on_change()

    def sync(self) -> None:
        """Repaint every box and heading from the model, in place.

        ⚠ Zips against the boxes it BUILT. A change to `health_levels` re-lengthens the
        track, and that is the owner's rebuild — this method would silently render the
        old length."""
        marks = adv.normalize_damage(self._a)
        for i, button in enumerate(self._health_boxes):
            mark = marks[i] if i < len(marks) else None
            restyle_box(button, MARK_FILL[mark] if mark else INPUT, self._accent,
                        mark.value if mark else "")
        if self._health_head is not None:
            self._health_head.setText(self._health_title())
        for i, button in enumerate(self._wp_boxes):
            restyle_box(button,
                        self._accent if i < self._a.willpower_spent else INPUT,
                        self._accent)
        if self._wp_head is not None:
            self._wp_head.setText(self._willpower_title())
        if self._essence_head is not None:
            self._essence_head.setText(self._essence_title())
        if self._motes_spin is not None:
            # ⚠ Signals blocked: "Reset" writes 0 to the model and then here, and an
            # un-blocked setValue would write it straight back out through
            # `_write_motes` — harmless today, and exactly the loop a future cap change
            # would turn into a fight between the two.
            self._motes_spin.blockSignals(True)
            self._motes_spin.setValue(min(self._a.motes_spent,
                                          self._motes_spin.maximum()))
            self._motes_spin.blockSignals(False)


class AdversariesPage(QWidget):
    """The tab widget. `reload()` rebuilds the roster table for the party in ctx;
    `notify` surfaces transient messages."""

    def __init__(self, ruleset, ctx, *, notify=None, on_change=None, parent=None):
        super().__init__(parent)
        self._ruleset = ruleset
        self._ctx = ctx
        self._notify = notify or (lambda text, kind="info": None)
        # ⚠ Every Qt page takes an `on_change`, and this one was built without: the
        # roster is now drawn on the Party tab too, so an edit here that never announced
        # itself would leave two surfaces showing different damage (the hook-contract
        # trap that hid `CharmsPage`'s missing readout — CLAUDE.md).
        self._on_change = on_change or (lambda: None)
        # The selected entry's ID, not its row. ⚠ Positions shift on add, duplicate and
        # delete — the roster is the one list here that inserts in the MIDDLE (a
        # duplicate sits beside its original), so an index would re-select a neighbour.
        self._selected: str | None = None
        # The live trackers of whatever is selected, so a click repaints instead of
        # rebuilding the pane it is standing in.
        self._trackers: AdversaryTrackers | None = None

        bar = QHBoxLayout()
        bar.setContentsMargins(8, 4, 8, 4)
        self.add_btn = QPushButton("Add…")
        self.add_btn.clicked.connect(self._open_catalogue)
        bar.addWidget(self.add_btn)
        self.dup_btn = QPushButton("Duplicate")
        self.dup_btn.setToolTip("Five bandits off one row, each with its own health "
                               "track")
        self.dup_btn.clicked.connect(self._duplicate)
        bar.addWidget(self.dup_btn)
        self.reset_btn = QPushButton("Reset")
        self.reset_btn.setToolTip("Clear damage and both spent pools")
        self.reset_btn.clicked.connect(self._reset)
        bar.addWidget(self.reset_btn)
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.clicked.connect(self._delete)
        bar.addWidget(self.delete_btn)
        bar.addStretch(1)

        self.table = QTreeWidget()
        self.table.setColumnCount(len(_COLUMNS))
        self.table.setHeaderLabels(list(_COLUMNS))
        self.table.setRootIsDecorated(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        # ⚠ Sortable, but NOT sorted to begin with. Roster order is meaningful here in a
        # way it is not on the other collection tabs: a duplicate is deliberately
        # inserted beside its original so a squad reads as a squad, and an alphabetical
        # default would scatter it on the very click that made it. `sortByColumn(-1)`
        # clears the indicator and leaves the header clickable.
        self.table.sortByColumn(-1, Qt.AscendingOrder)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.header().setStretchLastSection(False)
        self.table.header().setSectionResizeMode(3, QHeaderView.Stretch)
        # ⚠ Widths set, not left to Qt. A list of categories needs room the single
        # word never did — "Undead · Sold…" in a 90px column is the one cell you file a
        # squad by, truncated. Interactive, so they stay draggable.
        for column, width in ((0, 175), (1, 175), (2, 115)):
            self.table.header().resizeSection(column, width)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        empty_note(self.table,
                   "No adversaries yet.\n\nUse “Add…” for a catalogue template — an "
                   "extra, a beast, an NPC — or a blank one to type off the page.")

        self.detail_title = QLabel("")
        self.detail_title.setWordWrap(True)
        self._detail_body = QWidget()
        self._detail_lay = QVBoxLayout(self._detail_body)
        self._detail_lay.setContentsMargins(0, 0, 0, 0)
        detail_scroll = QScrollArea()
        detail_scroll.setWidgetResizable(True)
        detail_scroll.setWidget(self._detail_body)
        detail_panel = QWidget()
        dp = QVBoxLayout(detail_panel)
        dp.setContentsMargins(8, 4, 8, 4)
        dp.addWidget(self.detail_title)
        dp.addWidget(detail_scroll, 1)

        split = QSplitter()
        split.addWidget(self.table)
        split.addWidget(detail_panel)
        split.setSizes([720, 560])

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addLayout(bar)
        outer.addWidget(split, 1)
        self.reload()

    # ------------------------------------------------------------------ #
    # plumbing
    # ------------------------------------------------------------------ #

    def _party(self):
        return self._ctx["party"]

    def _accent(self) -> str:
        """The window's splat accent. The roster belongs to the PARTY, not to any one
        member, so it takes the party's shared palette rather than an entry's — an
        adversary has no splat of its own."""
        splats = {m.character.exalt_type for m in self._party().members}
        return accent_light(theme.palette(splats.pop() if len(splats) == 1 else None))

    def _entries(self) -> list[Adversary]:
        return self._party().adversaries

    def _current(self) -> Adversary | None:
        return next((a for a in self._entries() if a.id == self._selected), None)

    def _index(self) -> int | None:
        return next((i for i, a in enumerate(self._entries())
                     if a.id == self._selected), None)

    def reload(self) -> None:
        """Rebuild the table for the party in ctx, keeping the selection on the same
        ENTRY if it is still on the roster."""
        self._fill_table()
        self._sync_detail()

    def _rebuild(self) -> None:
        """A change that moved the LIST — refill, re-derive the pane, and tell the
        window, which redraws the same roster on the Party tab."""
        self.reload()
        self._on_change()

    def select(self, entry_id: str) -> None:
        """Select an entry by id — the seam "Edit" on a Party-tab roster card uses.

        ⚠ By ID, never by row. This table is sortable and a duplicate lands in the
        MIDDLE of the list, so a row number names a different adversary the moment
        either happens."""
        self._selected = entry_id
        self._fill_table()
        self._sync_detail()

    def _tracked(self) -> None:
        """A tracker click: re-render this row, and let the Party tab's copy of the same
        entry catch up."""
        self._refresh_row()
        self._on_change()

    # ------------------------------------------------------------------ #
    # the roster table
    # ------------------------------------------------------------------ #

    def _damage_cell(self, a: Adversary) -> str:
        """The at-a-glance damage readout — the column that replaces the webapp's card
        stack. Marks counted by type, then the deepest wound penalty."""
        marks = adv.normalize_damage(a)
        counts = {d: sum(1 for m in marks if m == d) for d in Damage}
        total = sum(counts.values())
        if not total:
            return ""
        penalty = adv.worst_penalty(a)
        shown = ("" if penalty is None
                 else "Incap" if penalty == adv.INCAPACITATED else str(penalty))
        return (f"{counts[Damage.BASHING]}/ {counts[Damage.LETHAL]}x "
                f"{counts[Damage.AGGRAVATED]}*  ({shown})")

    def _fill_table(self) -> None:
        # ⚠ Sorting OFF across the fill: with it on Qt re-sorts after every insert,
        # which scrambles the order a squad was added in.
        self.table.setSortingEnabled(False)
        self.table.blockSignals(True)
        self.table.clear()
        restore = None
        for entry in self._entries():
            item = QTreeWidgetItem([entry.name or "(unnamed)",
                                    adv.category_label(entry),
                                    self._damage_cell(entry),
                                    viewmod.summary_line(self._ruleset, entry)])
            item.setData(0, Qt.UserRole, entry.id)
            self.table.addTopLevelItem(item)
            if entry.id == self._selected:
                restore = item
        self.table.blockSignals(False)
        self.table.setSortingEnabled(True)
        if restore is not None:
            self.table.setCurrentItem(restore)
        elif self.table.topLevelItemCount():
            self.table.setCurrentItem(self.table.topLevelItem(0))
            self._selected = self.table.currentItem().data(0, Qt.UserRole)
        else:
            self._selected = None
        for button in (self.dup_btn, self.reset_btn, self.delete_btn):
            button.setEnabled(self._selected is not None)

    def _refresh_row(self) -> None:
        """Re-render the selected row only, so an edit tracks the table without a full
        rebuild (which would steal focus mid-keystroke)."""
        item = self.table.currentItem()
        entry = self._current()
        if item is None or entry is None:
            return
        item.setText(0, entry.name or "(unnamed)")
        item.setText(1, adv.category_label(entry))
        item.setText(2, self._damage_cell(entry))
        item.setText(3, viewmod.summary_line(self._ruleset, entry))

    def _selection_changed(self) -> None:
        item = self.table.currentItem()
        self._selected = None if item is None else item.data(0, Qt.UserRole)
        for button in (self.dup_btn, self.reset_btn, self.delete_btn):
            button.setEnabled(self._selected is not None)
        self._sync_detail()

    # ------------------------------------------------------------------ #
    # toolbar actions
    # ------------------------------------------------------------------ #

    def build_add_dialog(self) -> CatalogueDialog:
        """The template picker, BUILT but not run — `exec()` blocks a headless run, so
        this is the seam the tests drive (the shape `GearPage` uses)."""
        templates = sorted(self._ctx.get("adversary_catalog", {}).values(),
                           key=lambda t: (adv.category_label(t), t.name))
        rows = [(t.id, t.name, viewmod.summary_line(self._ruleset, t),
                 "\n".join(x for x in (adv.category_label(t), t.nature, t.notes) if x))
                for t in templates]
        pal = theme.palette(None)
        splats = {m.character.exalt_type for m in self._party().members}
        if len(splats) == 1:
            pal = theme.palette(splats.pop())
        return CatalogueDialog(
            pal, "Add an adversary", rows, self._add,
            subtitle=_ADD_SUBTITLE if rows else "",
            # ⚠ EVERY category, not the first — a template filed under two headings
            # must be findable under both, which is the point of the list.
            group_of=adv.catalogue_groups(templates),
            custom_label="Blank adversary", parent=self)

    def _open_catalogue(self) -> None:
        self.build_add_dialog().exec()

    def _add(self, key) -> None:
        """A template id, or None for the dialog's Custom button — a blank entry."""
        template = self._ctx.get("adversary_catalog", {}).get(key or "")
        if template is None:
            entry = adv.add_blank(self._party())
            self._notify("Added a blank adversary — fill it in on the right", "info")
        else:
            entry = adv.add_from_template(self._party(), template)
            self._notify(f"Added {entry.name}", "info")
        self._selected = entry.id
        self._rebuild()

    def _duplicate(self) -> None:
        index = self._index()
        if index is None:
            return
        copy = adv.duplicate(self._party(), index)
        self._selected = copy.id
        self._rebuild()

    def _reset(self) -> None:
        entry = self._current()
        if entry is None:
            return
        adv.reset_tracking(entry)
        if self._trackers is not None:
            self._trackers.sync()
        self._tracked()

    def _delete(self) -> None:
        index = self._index()
        if index is None:
            return
        gone = adv.remove(self._party(), index)
        self._selected = None
        self._rebuild()
        self._notify(f"Removed {gone}", "info")

    # ------------------------------------------------------------------ #
    # the detail pane — trackers over the editor
    # ------------------------------------------------------------------ #

    def _muted(self, text: str, *, italic: bool = False) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet(f"color:{MUTED};"
                            + (" font-style:italic;" if italic else ""))
        return label

    def _panel(self, title: str) -> QVBoxLayout:
        """A titled card appended to the detail pane; returns the body to fill."""
        frame = QFrame()
        frame.setObjectName("advPanel")
        frame.setStyleSheet(
            f"QFrame#advPanel {{ background:{CARD}; border-radius:6px; }}")
        body = QVBoxLayout(frame)
        body.setContentsMargins(10, 8, 10, 8)
        body.setSpacing(4)
        head = QLabel(title)
        head.setWordWrap(True)
        head.setStyleSheet(f"font-weight:700; letter-spacing:1px; color:{self._accent()};")
        body.addWidget(head)
        self._detail_lay.addWidget(frame)
        return body

    def _labelled(self, lay, caption: str, widget, tooltip: str = "") -> None:
        """One captioned row. ⚠ A QSpinBox is NOT stretched: a two-digit number in a
        550px-wide box reads as a text field someone forgot to size, and the printed
        numbers here are all small."""
        row = QHBoxLayout()
        label = QLabel(caption)
        label.setStyleSheet(f"color:{MUTED};")
        label.setMinimumWidth(118)
        if tooltip:
            label.setToolTip(tooltip)
            widget.setToolTip(tooltip)
        row.addWidget(label)
        if isinstance(widget, QSpinBox):
            widget.setFixedWidth(88)
            row.addWidget(widget)
            row.addStretch(1)
        else:
            row.addWidget(widget, 1)
        lay.addLayout(row)

    def _sync_detail(self) -> None:
        clear_layout(self._detail_lay)
        self._trackers = None
        entry = self._current()
        if entry is None:
            self.detail_title.setText("")
            self._detail_lay.addWidget(self._muted(
                "Select an adversary to edit it, or Add one."))
            self._detail_lay.addStretch(1)
            return
        self.detail_title.setText(entry.name or "(unnamed)")
        self.detail_title.setStyleSheet(
            f"font-weight:700; font-size:14px; color:{self._accent()};")
        self._tracker_panel(entry)
        self._identity_panel(entry)
        self._traits_panel(entry)
        self._combat_panel(entry)
        self._pools_panel(entry)
        self._prose_panel(entry)
        self._detail_lay.addStretch(1)

    # ---- trackers -------------------------------------------------------- #

    def _tracker_panel(self, a: Adversary) -> None:
        """The shared trackers widget, held so a click can repaint it in place.

        ⚠ It is NOT re-created per click. The detail pane sits in a QScrollArea, and
        rebuilding it under the button that was just pressed threw the focus to the end
        of the tab chain and dragged the scroll to the bottom of the pane on every
        damage mark (human, 2026-08-28)."""
        self._trackers = AdversaryTrackers(a, self._accent(), prefix="adv",
                                           on_change=self._tracked)
        self._detail_lay.addWidget(self._trackers)

    def _cycle(self, index: int) -> None:
        if self._trackers is not None and self._current() is not None:
            self._trackers.cycle(index)

    def _count(self, index: int) -> None:
        if self._trackers is not None and self._current() is not None:
            self._trackers.count(index)

    # ---- the editor ------------------------------------------------------ #

    def _text_line(self, a: Adversary, field: str) -> QLineEdit:
        edit = QLineEdit(getattr(a, field))
        edit.setObjectName(f"adv.{field}")
        edit.textChanged.connect(
            lambda t, f=field: (setattr(a, f, t), self._refresh_row()))
        return edit

    def _int_spin(self, a: Adversary, field: str, *, nullable: bool = False) -> QSpinBox:
        """One printed number. A nullable one runs from -1, shown as "—": absent is not
        zero (a bear has no printed dodge; Nagezzer "does not dodge")."""
        spin = QSpinBox()
        spin.setObjectName(f"adv.{field}")
        spin.setRange(-1 if nullable else 0, 999)
        if nullable:
            spin.setSpecialValueText(_ABSENT)
        value = getattr(a, field)
        spin.setValue(-1 if value is None else value)
        spin.valueChanged.connect(
            lambda v, f=field: (setattr(a, f, None if (nullable and v < 0) else v),
                                self._refresh_row()))
        return spin

    def _identity_panel(self, a: Adversary) -> None:
        body = self._panel("IDENTITY")
        self._labelled(body, "Name", self._text_line(a, "name"))
        # Several labels, all equal — a skeletal legionnaire is Undead AND a Soldier,
        # and the roster files it under both. ⚠ Committed on `editingFinished`, not per
        # keystroke: splitting on every comma mid-type would fight the typist.
        categories = QLineEdit(adv.category_line(a.categories))
        categories.setObjectName("adv.categories")
        categories.setPlaceholderText("Extra, Guild")
        categories.editingFinished.connect(
            lambda: (setattr(a, "categories", adv.parse_categories(categories.text())),
                     self._refresh_row()))
        self._labelled(body, "Categories", categories,
                       "Free text, comma-separated — Extra, Beast, Spirit, whatever "
                       "groups your roster. An entry is filed under every one of them.")
        for field, label, tooltip in _IDENTITY[1:]:
            self._labelled(body, label, self._text_line(a, field), tooltip)
        if a.template_id:
            body.addWidget(self._muted(
                f"From the {a.template_id} template — an independent copy since the "
                f"moment it was made.", italic=True))

    def _trait_grid(self, body, a: Adversary, field: str, keys: list[str]) -> None:
        """The Attributes or Virtues grid. ⚠ Wrapped at four pairs a row: Qt has no
        flex-wrap and a no-wrap row crushes its later children to slivers."""
        values = getattr(a, field)
        row = None
        for position, key in enumerate(keys):
            if position % 4 == 0:
                row = QHBoxLayout()
                body.addLayout(row)
            caption = QLabel(key[:3].title())
            caption.setStyleSheet(f"color:{MUTED};")
            caption.setMinimumWidth(34)
            row.addWidget(caption)
            spin = QSpinBox()
            spin.setObjectName(f"adv.{field}.{key}")
            spin.setRange(0, 20)
            spin.setSpecialValueText(_ABSENT)
            spin.setValue(values.get(key, 0))
            spin.valueChanged.connect(
                lambda v, f=field, k=key: self._write_trait(a, f, k, v))
            row.addWidget(spin)
        if row is not None:
            row.addStretch(1)

    def _write_trait(self, a: Adversary, field: str, key: str, value: int) -> None:
        """Write one Attribute/Virtue, DELETING the key at 0 — storing a zero would
        claim the book printed one (models/adversary.py)."""
        values = dict(getattr(a, field))
        if value:
            values[key] = value
        else:
            values.pop(key, None)
        setattr(a, field, values)
        self._refresh_row()

    def _codec_line(self, a: Adversary, field: str) -> QLineEdit:
        """An Abilities/Backgrounds line as the book prints it. ⚠ `trait_line` fills the
        box and `parse_traits` reads it back — a CODEC PAIR, not a formatter plus a
        parser. Committed on `editingFinished`, never per keystroke: parsing "Melee 3 (Sw"
        mid-word and writing it back would fight the typist."""
        edit = QLineEdit(adv.trait_line(getattr(a, field)))
        edit.setObjectName(f"adv.{field}")
        edit.editingFinished.connect(
            lambda f=field: (setattr(a, f, adv.parse_traits(edit.text())),
                             self._refresh_row()))
        return edit

    def _traits_panel(self, a: Adversary) -> None:
        body = self._panel("TRAITS")
        body.addWidget(self._muted(
            "Leave a box at “—” where the block prints nothing — a beast has three of "
            "the nine, and 0 is not the same as absent."))
        self._trait_grid(body, a, "attributes", _ATTRIBUTES)
        body.addWidget(self._muted("Virtues"))
        self._trait_grid(body, a, "virtues", _VIRTUES)
        self._labelled(body, "Abilities", self._codec_line(a, "abilities"),
                       "As printed: Melee 3 (Swords +2), Dodge 2, Awareness 1")
        self._labelled(body, "Backgrounds", self._codec_line(a, "backgrounds"))

    def _armor_combo(self, a: Adversary, field: str, options) -> QComboBox:
        combo = QComboBox()
        combo.setObjectName(f"adv.{field}")
        combo.addItem("(none)", "")
        for entry in options:
            combo.addItem(entry.name, entry.id)
        # ⚠ Index the list this was built from, never read the key back out of the
        # widget — Qt stores item data as a QVariant and hands a str-valued Enum back
        # as a plain str (CLAUDE.md's Qt trap). These ids are already plain strings, so
        # the rule costs nothing here and keeps the shape right.
        combo.setCurrentIndex(max(0, combo.findData(getattr(a, field) or "")))
        combo.currentIndexChanged.connect(
            lambda i, f=field: (setattr(a, f, combo.itemData(i) or ""),
                                self._refresh_row()))
        return combo

    def _combat_panel(self, a: Adversary) -> None:
        body = self._panel("COMBAT")
        for field, label, tooltip in _NULLABLE:
            self._labelled(body, label, self._int_spin(a, field, nullable=True), tooltip)
        for field, label, tooltip in _SOAK:
            self._labelled(body, label, self._int_spin(a, field), tooltip)
        self._labelled(body, "Armour",
                       self._armor_combo(a, "armor_id", adv.armor_options(self._ruleset)),
                       "Mundane armour only. Adds to natural soak; its mobility penalty "
                       "comes off the dodge pool automatically.")
        self._labelled(body, "Shield",
                       self._armor_combo(a, "shield_id", adv.shield_options(self._ruleset)),
                       "Shields give no soak. They add their mobility penalty on top of "
                       "the armour's, and make the bearer harder to hit (p.335).")

        body.addWidget(self._muted(
            "Attacks — one per line, as printed: "
            "Bite: Speed 6 Accuracy 7 Damage 1L Defense 5"))
        attacks = QPlainTextEdit("\n".join(adv.attack_line(x) for x in a.attacks))
        attacks.setObjectName("adv.attacks")
        attacks.setFixedHeight(72)
        attacks.textChanged.connect(
            lambda: (setattr(a, "attacks", adv.parse_attacks(attacks.toPlainText())),
                     self._refresh_row()))
        body.addWidget(attacks)

        health = QLineEdit(adv.format_health(a.health_levels))
        health.setObjectName("adv.health_levels")
        # Re-lengthening the track re-lengths the MARKS with it, so the tracker above is
        # rebuilt — the one edit in this pane that legitimately redraws it.
        health.editingFinished.connect(
            lambda: self._set_health(a, health.text()))
        self._labelled(body, "Health levels", health,
                       "As printed, repeats allowed: -0/-1 x 7/-2 x 12/-4/Incap")

    def _set_health(self, a: Adversary, text: str) -> None:
        levels = adv.expand_health(text or "")
        if levels == a.health_levels:
            return
        a.health_levels = levels
        adv.normalize_damage(a)          # marks are positional; re-length them
        self._sync_detail()
        self._refresh_row()

    def _pools_panel(self, a: Adversary) -> None:
        body = self._panel("POOLS")
        for field, label, tooltip in _POOLS:
            self._labelled(body, label, self._int_spin(a, field), tooltip)

    def _prose_panel(self, a: Adversary) -> None:
        """Charms, Spells and Powers are FREE TEXT and must stay that way: the book
        prints "All Solar Charms the Storyteller cares to give him" (p.303), which is
        not a list of ids and would fail the loader's link-checking."""
        body = self._panel("PROSE")
        for field, label, tooltip in _PROSE:
            edit = QPlainTextEdit(getattr(a, field))
            edit.setObjectName(f"adv.{field}")
            edit.setFixedHeight(56)
            if tooltip:
                edit.setToolTip(tooltip)
            edit.textChanged.connect(
                lambda f=field, w=edit: (setattr(a, f, w.toPlainText()),
                                         self._refresh_row()))
            body.addWidget(self._muted(label))
            body.addWidget(edit)
