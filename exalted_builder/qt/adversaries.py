"""exalted_builder/qt/adversaries.py — the Adversaries tab of the native Party window.

Input: a RuleSet, the shared context (for `party` and `adversary_catalog`). Output: the
settled collection layout — a toolbar (Add / Duplicate / Reset / Delete), a sortable
table of the roster, and the selected entry's trackers-and-editor in a detail pane.
Mechanism: `reload()` refills the table from `party.adversaries` and re-selects what was
selected; every widget in the detail pane writes its own field straight to the model and
re-syncs only the row it changed, so a keystroke never rebuilds the pane under the
cursor. Every computed number comes from `engine.adversaries`; every roster mutation
goes through it too.

⚠ **This tab EDITS an adversary. The Party tab RUNS a fight.** The program draws the
roster two times, and that is correct. Here the roster is a collection, as Gear and
Advantages are: a table, with the detail pane that the webapp showed as a modal dialog. On
the Party tab, the roster is a grid of live tracker cards next to the characters in the
fight (`qt/party.py::_adversary_card`). One detail pane shows the health of ONE adversary,
and a Storyteller runs a fight against many (human's ruling). `AdversaryTrackers` below is
the ONE tracker that both surfaces use. ⚠ The **Damage** column of the table is not
decoration. It is the readout that the user reads on this tab.

⚠ **An `Adversary` is NOT a `Character`.** No code here validates, prices or locks. Use no
dot tracks. The user types these values from a page, or invents them. The user never buys
them. Thus a stepper with a rules limit states a rule that does not apply.

⚠ **This surface has produced a dead field one time.** `powers`, `combat_pool` and
`cost_to_dematerialize` existed in the model, no widget could edit them, and the save
removed them. `tests/test_qt_adversaries.py` reads `Adversary.model_fields` and drives
each widget. Thus a new field fails the test until you connect both ends.
"""

from __future__ import annotations

from typing import Callable

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

# Qt has no flex-wrap. A health track has 22 boxes on a Deathlord. Thus this row wraps by
# construction. `qt/play.py` holds this number for the same reason.
_BOXES_PER_ROW = 11

_ATTRIBUTES = ["strength", "dexterity", "stamina", "charisma", "manipulation",
               "appearance", "perception", "intelligence", "wits"]
_VIRTUES = ["compassion", "conviction", "temperance", "valor"]

# ⚠ In the trait grids, `0` MEANS ABSENT. A beast prints three of the nine Attributes, and
# p.316 gives the defaults for the others as Intelligence 1, Perception 2, Wits 3. No
# printed block gives a rating of zero. Thus the box shows "—" at its minimum, and the grid
# never reports that the book printed a 0.
_ABSENT = "—"

# The combat numbers that can be absent. ⚠ Absent is NOT zero. The Bear prints no dodge
# figure (p.316), and Nagezzer prints "Does not dodge" (p.307). Their spin boxes start at
# -1, which shows as "—". Thus the user can set both states.
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

# ⚠ `categories` is NOT in this table. It is a comma-separated codec line, not a plain
# string field. `_identity_panel` builds it.
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

# The three prose fields with a catalogue behind them. `notes` is the fourth member
# of `_PROSE` and has none.
_PICKABLE_PROSE = frozenset({"powers", "charms", "spells"})

_ADD_SUBTITLE = ("Pick a template to start from — you get an editable copy, and the "
                 "catalogue entry is untouched.")


class AdversaryTrackers(QWidget):
    """One adversary's live trackers — health, Willpower, Essence — as a widget.

    Input: an `Adversary`, the accent to paint it in, a name `prefix` for the boxes and
    an `on_change` the owner uses to re-render whatever else shows these numbers.
    Output: up to three panels, each a heading over its boxes. Mechanism: a click writes
    through `engine.adversaries` and then RESTYLES the boxes and re-texts the headings it
    changed; nothing here is ever torn down by its own click.

    ⚠ **There is ONE trackers widget, and two surfaces use it.** The Adversaries detail
    pane and the roster cards of the Party tab draw the same boxes for the same entries. A
    second copy becomes different, and the user then gets two answers to "how much damage
    does this adversary have".

    ⚠ **`framed` changes the presentation only.** In the detail pane, each panel is its own
    card. On a roster card, the card supplies the shade, and a card inside a card reads as
    a rendering fault.

    ⚠ **`dense` also changes the presentation only. It is a MODE, not a second widget.** It
    puts the three panels SIDE BY SIDE, and it does not stack them. The roster blocks of
    the party page need this. Three stacked panels with headings are approximately 130px
    for each adversary, and six of them fill the screen. A second compact widget breaks the
    one-widget rule above. `dense` also removes the frame, because cards side by side
    inside a card are the fault that `framed` describes.

    ⚠ **A click never rebuilds this widget** (see `trackers.restyle`). One change makes the
    boxes longer: an edit to `health_levels`. That change goes through the rebuild of the
    owner, not through this widget.
    """

    def __init__(self, entry: Adversary, accent: str, *, prefix: str = "adv",
                 on_change=None, framed: bool = True, box_size: int = 28,
                 boxes_per_row: int = _BOXES_PER_ROW, dense: bool = False, parent=None):
        super().__init__(parent)
        self._a = entry
        self._accent = accent
        self._prefix = prefix
        self._on_change = on_change or (lambda: None)
        self._framed = framed and not dense
        self._dense = dense
        self._box_size = box_size
        self._per_row = boxes_per_row

        self._health_boxes: list = []
        self._wp_boxes: list = []
        self._health_head: QLabel | None = None
        self._wp_head: QLabel | None = None
        self._essence_head: QLabel | None = None
        self._motes_spin: QSpinBox | None = None

        self._lay = QHBoxLayout(self) if dense else QVBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(10 if dense else (4 if self._framed else 3))
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self._build()
        if dense:
            self._lay.addStretch(1)
        # ⚠ Set a HARD minimum height after you build the widget. A card is a stack of
        # labels that wrap, and a QLabel that wraps answers `heightForWidth`. Thus the
        # QGridLayout above it calculates a card height that is too small. Each label then
        # becomes shorter, but these fixed-size boxes CANNOT. The health row is then cut to
        # half height, and it paints through the Willpower heading below it. A minimum
        # height is a limit that no parent layout can go below. A size policy is not
        # sufficient. ⚠ No test can see this fault. Only a render shows it.
        self.setMinimumHeight(self._lay.minimumSize().height())

    # ---- construction ---------------------------------------------------- #

    def _panel(self, title: str) -> tuple[QVBoxLayout, QLabel]:
        """A heading over a body. `framed` puts them on a card. Returns both. Each heading
        here carries a live count, and `sync` writes that text again."""
        # ⚠ Do NOT set word wrap. A QLabel that wraps answers `heightForWidth`, and
        # `QGridLayout` ignores that value. These headings are on cards that a grid lays
        # out. Thus a wrap makes the card too short, and it cuts the boxes below.
        head = QLabel(title)
        head.setStyleSheet(f"font-weight:700; letter-spacing:1px; color:{self._accent};"
                           + ("" if self._framed else " font-size:11px;"))
        body = QVBoxLayout()
        # ⚠ Set the margins to zero. A nested QVBoxLayout takes an 11px default on all four
        # sides. Three of them on one card add 66px of empty space between each heading and
        # its boxes.
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(3)
        if self._dense:
            # Give each panel a COLUMN, side by side. Keep each heading over its own boxes.
            # ⚠ A heading carries a live count that `sync` writes again. Thus it cannot
            # become one shared caption.
            column = QVBoxLayout()
            column.setContentsMargins(0, 0, 0, 0)
            column.setSpacing(2)
            column.addWidget(head)
            column.addLayout(body)
            self._lay.addLayout(column)
            return body, head
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
            # Put the wound penalty in a CAPTION. Do not put it in a tooltip only. During a
            # fight, a Storyteller reads the next box to mark from the card. A tooltip needs
            # a hover, and six cards can be on the screen.
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
            # ⚠ Do not rebuild from a spin box. A redraw deletes the widget while the user
            # types, and it takes the focus. Write the heading text again instead.
            spin.valueChanged.connect(self._write_motes)
            self._motes_spin = spin
            row = QHBoxLayout()
            label = QLabel("Motes spent")
            label.setStyleSheet(f"color:{MUTED};" + (" font-size:11px;"
                                                     if self._dense else ""))
            # ⚠ Set a MINIMUM width in the detail pane. The row is wide there, and the label
            # must align with the labels above it. A dense column does not have those 90px.
            # Thus dense mode sets its own width.
            if not self._dense:
                label.setMinimumWidth(90)
            row.addWidget(label)
            spin.setFixedWidth(64 if self._dense else 88)
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

        ⚠ This method uses the boxes that it BUILT. A change to `health_levels` makes the
        track longer, and the rebuild of the owner does that. This method draws the old
        length and reports no error."""
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
            # ⚠ Block the signals. "Reset" writes 0 to the model, then calls this code. An
            # unblocked `setValue` writes that value back through `_write_motes`. That has
            # no effect now. A later change to a limit makes it a loop.
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
        # ⚠ Every Qt page takes an `on_change`. This page needs one. The Party tab draws
        # the same roster. An edit here that sends no signal leaves the two surfaces with
        # different damage values.
        self._on_change = on_change or (lambda: None)
        # The ID of the selected entry, not its row. ⚠ An add, a duplicate and a delete
        # move the positions. This roster is the one list that inserts in the MIDDLE,
        # because a duplicate goes next to its original. Thus an index selects a
        # different entry.
        self._selected: str | None = None
        # The live trackers of the selected entry. Thus a click repaints the boxes. It does
        # not rebuild the pane that holds them.
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
        # ⚠ The table is sortable, but it starts unsorted. The roster order carries
        # meaning here, and the order on the other collection tabs does not. A duplicate
        # goes next to its original, thus a squad stays together. An alphabetical default
        # separates the squad on the click that creates it. `sortByColumn(-1)` removes the
        # indicator and keeps the header clickable.
        self.table.sortByColumn(-1, Qt.AscendingOrder)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.header().setStretchLastSection(False)
        self.table.header().setSectionResizeMode(3, QHeaderView.Stretch)
        # ⚠ Set the widths. Do not leave them to Qt. A list of categories needs more space
        # than one word. In a 90px column, "Undead · Sold…" cuts the cell that the user
        # files a squad by. Keep the mode Interactive, thus the user can drag the columns.
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
        """The splat accent of the window. The roster belongs to the PARTY, not to one
        member. Thus it takes the shared palette of the party. An adversary has no splat."""
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
        """Apply a change that moved the LIST. Refill the table, build the pane again, and
        call the window. The window draws the same roster on the Party tab again."""
        self.reload()
        self._on_change()

    def select(self, entry_id: str) -> None:
        """Select an entry by id. The "Edit" control on a Party-tab roster card calls this.

        ⚠ Select by ID. Never select by row. This table is sortable, and a duplicate goes
        into the MIDDLE of the list. After either action, a row number names a different
        adversary."""
        self._selected = entry_id
        self._fill_table()
        self._sync_detail()

    def _tracked(self) -> None:
        """Apply a tracker click. Draw this row again, and call the window. The Party tab
        then draws the same entry again."""
        self._refresh_row()
        self._on_change()

    # ------------------------------------------------------------------ #
    # the roster table
    # ------------------------------------------------------------------ #

    def _damage_cell(self, a: Adversary) -> str:
        """The damage readout of one row. Output: the count of marks for each damage type,
        then the largest wound penalty."""
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
        # ⚠ Turn sorting OFF across the fill. If sorting is on, Qt sorts again after each
        # insert, and the order of a squad is lost.
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
        """Draw the selected row again. Thus the table agrees with the edit. ⚠ Do not do a
        full rebuild. A rebuild takes the focus away while the user types."""
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
        """The template picker. This function BUILDS the dialog and does not run it.
        `exec()` stops a headless run, thus the tests drive this seam. `GearPage` uses the
        same shape."""
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
            # ⚠ Supply EVERY category, not the first one. The user must find a template
            # under each of its headings.
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
        """One row with a caption. ⚠ Do NOT stretch a QSpinBox. A two-digit number in a box
        of 550px reads as a text field with the wrong size. The printed numbers here are
        all small."""
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

        ⚠ Do NOT create this widget again on each click. The detail pane is in a
        QScrollArea. A rebuild below the button that the user pressed moves the focus to
        the end of the tab chain, and the pane then scrolls to its bottom on each damage
        mark."""
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
        """One printed number. A number that can be absent starts at -1, which shows as
        "—". ⚠ Absent is not zero. A bear prints no dodge, and Nagezzer "does not
        dodge"."""
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
        # An entry can have more than one label, and the labels have equal rank. A skeletal
        # legionnaire is Undead AND a Soldier, and the roster files it under both. ⚠ Commit
        # on `editingFinished`, not on each keystroke. A split at each comma during typing
        # changes the text below the cursor.
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
        """The Attributes grid or the Virtues grid. ⚠ Wrap it at four pairs for each row.
        Qt has no flex-wrap, and a row that does not wrap makes its last children very
        narrow."""
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
        """Write one Attribute or Virtue. ⚠ DELETE the key at 0. A stored zero reports that
        the book printed a zero (`models/adversary.py`)."""
        values = dict(getattr(a, field))
        if value:
            values[key] = value
        else:
            values.pop(key, None)
        setattr(a, field, values)
        self._refresh_row()

    def _codec_line(self, a: Adversary, field: str) -> QLineEdit:
        """An Abilities line or a Backgrounds line, in the format that the book prints.
        ⚠ `trait_line` fills the box, and `parse_traits` reads it back. They are a CODEC
        PAIR. They are not a formatter and a separate parser. ⚠ Commit on
        `editingFinished`, never on each keystroke. To parse "Melee 3 (Sw" and write it
        back changes the text below the cursor."""
        edit = QLineEdit(adv.trait_line(getattr(a, field)))
        edit.setObjectName(f"adv.{field}")
        edit.editingFinished.connect(
            lambda f=field: (setattr(a, f, adv.parse_traits(edit.text())),
                             self._refresh_row()))
        return edit

    # ------------------------------------------------------------------ #
    # Catalogue picking into the free-text fields
    # ------------------------------------------------------------------ #

    def _party_palette(self):
        """The party's shared palette — the same one `build_add_dialog` picks."""
        splats = {m.character.exalt_type for m in self._party().members}
        return theme.palette(splats.pop() if len(splats) == 1 else None)

    def build_pick_dialog(self, kind: str, title: str,
                          apply: Callable[[str], None]) -> CatalogueDialog:
        """One "add from catalogue" dialog. This function BUILDS it and does not run it.
        `exec()` stops a headless run, thus the tests drive this seam. `build_add_dialog`
        uses the same shape.

        `apply` receives the printed NAME, never the row key. ⚠ No code here filters by
        splat, and no code checks a prerequisite. See `view.adversary_picker_rows`.
        """
        rows, group_of = viewmod.adversary_picker_rows(self._ruleset, kind)
        names = viewmod.picker_names(rows)

        def _pick(key) -> None:
            name = names.get(key or "")
            if name:
                apply(name)

        return CatalogueDialog(
            self._party_palette(), title, rows, _pick,
            subtitle="Nothing here is checked against prerequisites, minimums or "
                     "splat — this is the Storyteller's roster.",
            allow_custom=False, keep_open=True,
            group_of=group_of or None, parent=self)

    def _pick_button(self, kind: str, title: str,
                     apply: Callable[[str], None]) -> QPushButton:
        button = QPushButton("Add from catalogue")
        button.setObjectName(f"adv.pick.{kind}")
        # Size the button to its text, not to the panel. A full-width button below a field
        # reads as a section divider, not as a control for that field.
        button.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        button.setToolTip("Browse the catalogue and append names here. "
                          "No prerequisites, no minimums, no splat filter.")
        button.clicked.connect(
            lambda *_: self.build_pick_dialog(kind, title, apply).exec())
        # ⚠ Attach the handler to the button. Thus a test can DRIVE the real handler. A
        # click opens a modal `exec()`, which stops a headless run. A test that writes its
        # own append tests a copy of the code. `docs/lessons.md` calls that testing the
        # effect in place of the buy path.
        button._apply = apply
        return button

    def _traits_panel(self, a: Adversary) -> None:
        body = self._panel("TRAITS")
        body.addWidget(self._muted(
            "Leave a box at “—” where the block prints nothing — a beast has three of "
            "the nine, and 0 is not the same as absent."))
        self._trait_grid(body, a, "attributes", _ATTRIBUTES)
        body.addWidget(self._muted("Virtues"))
        self._trait_grid(body, a, "virtues", _VIRTUES)
        for field, label, tooltip in (
                ("abilities", "Abilities",
                 "As printed: Melee 3 (Swords +2), Dodge 2, Awareness 1"),
                ("backgrounds", "Backgrounds", "")):
            edit = self._codec_line(a, field)
            self._labelled(body, label, edit, tooltip)
            # ⚠ `setText` does NOT send `editingFinished`, and that signal commits this
            # box. Thus the pick writes the model here. Write through the codec. Never
            # append to the string. Thus the codec pair stays correct.
            def _apply(name: str, a=a, f=field, w=edit) -> None:
                w.setText(adv.append_trait(w.text(), name))
                setattr(a, f, adv.parse_traits(w.text()))
                self._refresh_row()
            self._labelled(body, "", self._pick_button(field, label, _apply))

    def _armor_combo(self, a: Adversary, field: str, options) -> QComboBox:
        combo = QComboBox()
        combo.setObjectName(f"adv.{field}")
        combo.addItem("(none)", "")
        for entry in options:
            combo.addItem(entry.name, entry.id)
        # ⚠ Index the list that built this widget. Never read the key back from the widget.
        # Qt stores item data as a QVariant, and it returns an Enum with a str value as a
        # plain str. These ids are plain strings. Thus this rule has no cost here, and it
        # keeps the shape correct.
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
        # A change to the track length also changes the length of the MARKS. Thus this code
        # rebuilds the tracker above. This is the one edit in this pane that rebuilds it.
        health.editingFinished.connect(
            lambda: self._set_health(a, health.text()))
        self._labelled(body, "Health levels", health,
                       "As printed, repeats allowed: -0/-1 x 7/-2 x 12/-4/Incap")

    def _set_health(self, a: Adversary, text: str) -> None:
        levels = adv.expand_health(text or "")
        if levels == a.health_levels:
            return
        a.health_levels = levels
        adv.normalize_damage(a)          # the marks are positional. Set their length again.
        self._sync_detail()
        self._refresh_row()

    def _pools_panel(self, a: Adversary) -> None:
        body = self._panel("POOLS")
        for field, label, tooltip in _POOLS:
            self._labelled(body, label, self._int_spin(a, field), tooltip)

    def _prose_panel(self, a: Adversary) -> None:
        """Charms, Spells and Powers are FREE TEXT. ⚠ Keep them free text. The book prints
        "All Solar Charms the Storyteller cares to give him" (p.303). That is not a list of
        ids, and the link check of the loader refuses it."""
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
            # `notes` is prose with no catalogue behind it; the other three have one.
            if field in _PICKABLE_PROSE:
                def _apply(name: str, w=edit) -> None:
                    # setPlainText fires textChanged, which is what writes the model.
                    w.setPlainText(adv.append_prose(w.toPlainText(), name))
                row = QHBoxLayout()
                row.addWidget(self._pick_button(field, label, _apply))
                row.addStretch(1)
                body.addLayout(row)
