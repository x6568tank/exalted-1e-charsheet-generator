"""exalted_builder/qt/adversaries.py — the Adversaries tab of the native Party window.

Input: a RuleSet, the shared context (for `party` and `adversary_catalog`). Output: the
settled collection layout — a toolbar (Add / Duplicate / Reset / Delete), a sortable
table of the roster, and the selected entry's trackers-and-editor in a detail pane.
Mechanism: `reload()` refills the table from `party.adversaries` and re-selects what was
selected; every widget in the detail pane writes its own field straight to the model and
re-syncs only the row it changed, so a keystroke never rebuilds the pane under the
cursor. Every computed number comes from `engine.adversaries`; every roster mutation
goes through it too.

⚠ **The webapp renders this as CARDS; the native app does not.** A card stack was the
webapp's answer to "several entries, each with trackers"; here the roster is a
collection like Gear and Advantages, and the editor that was a modal dialog there is the
detail pane. The one thing cards did better — seeing six bandits' damage at once — is
kept as the table's **Damage** column, which is why that column is not decoration.

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
    QLineEdit, QPlainTextEdit, QPushButton, QScrollArea, QSpinBox, QSplitter,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from exalted_builder.engine import adversaries as adv
from exalted_builder.models.adversary import Adversary
from exalted_builder.models.rules import Damage
from exalted_builder.ui import theme
from exalted_builder.ui import view as viewmod

from .catalogue import CatalogueDialog
from .layout import clear_layout
from .theme import CARD, INPUT, MUTED, accent as accent_light
from .trackers import MARK_FILL, box as tracker_box

_COLUMNS = ("Name", "Category", "Damage", "Stats")

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

_IDENTITY = (
    ("name", "Name", ""),
    ("category", "Category",
     "Free text — Extra, Beast, Spirit, whatever groups your roster"),
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


class AdversariesPage(QWidget):
    """The tab widget. `reload()` rebuilds the roster table for the party in ctx;
    `notify` surfaces transient messages."""

    def __init__(self, ruleset, ctx, *, notify=None, parent=None):
        super().__init__(parent)
        self._ruleset = ruleset
        self._ctx = ctx
        self._notify = notify or (lambda text, kind="info": None)
        # The selected entry's ID, not its row. ⚠ Positions shift on add, duplicate and
        # delete — the roster is the one list here that inserts in the MIDDLE (a
        # duplicate sits beside its original), so an index would re-select a neighbour.
        self._selected: str | None = None

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
        self.table.header().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.itemSelectionChanged.connect(self._selection_changed)

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
        split.setSizes([560, 620])

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
        """A change that moved the LIST — refill and re-derive the pane."""
        self.reload()

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
            item = QTreeWidgetItem([entry.name or "(unnamed)", entry.category,
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
        item.setText(1, entry.category)
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
                           key=lambda t: (t.category, t.name))
        rows = [(t.id, t.name, viewmod.summary_line(self._ruleset, t),
                 "\n".join(x for x in (t.category, t.nature, t.notes) if x))
                for t in templates]
        pal = theme.palette(None)
        splats = {m.character.exalt_type for m in self._party().members}
        if len(splats) == 1:
            pal = theme.palette(splats.pop())
        return CatalogueDialog(
            pal, "Add an adversary", rows, self._add,
            subtitle=_ADD_SUBTITLE if rows else "",
            group_of={t.id: t.category for t in templates},
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
        self._sync_detail()
        self._refresh_row()

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
        marks = adv.normalize_damage(a)
        penalty = adv.worst_penalty(a)
        shown = ("none" if penalty is None
                 else "Incap" if penalty == adv.INCAPACITATED else str(penalty))
        body = self._panel(f"HEALTH   ·   penalty {shown}   ·   "
                           f"/ bashing   x lethal   * aggravated")
        if not a.health_levels:
            body.addWidget(self._muted("No health track — set one under Combat below."))
        row = None
        for i in range(len(a.health_levels)):
            if i % _BOXES_PER_ROW == 0:
                row = QHBoxLayout()
                row.setSpacing(4)
                body.addLayout(row)
            cell = QVBoxLayout()
            cell.setSpacing(1)
            caption = QLabel(adv.level_label(a.health_levels[i]))
            caption.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            caption.setStyleSheet(f"color:{MUTED}; font-size:10px;")
            cell.addWidget(caption)
            mark = marks[i]
            button = tracker_box(f"adv.health.{i}", 28,
                                 MARK_FILL[mark] if mark else INPUT,
                                 self._accent(), mark.value if mark else "")
            button.clicked.connect(
                lambda _c=False, index=i: self._cycle(index))
            cell.addWidget(button)
            row.addLayout(cell)
        if row is not None:
            row.addStretch(1)

        if a.willpower:
            wp = self._panel(f"WILLPOWER   ({a.willpower - a.willpower_spent}"
                             f"/{a.willpower})")
            track = QHBoxLayout()
            track.setSpacing(4)
            for i in range(a.willpower):
                button = tracker_box(f"adv.willpower_spent.{i}", 20,
                                     self._accent() if i < a.willpower_spent
                                     else INPUT, self._accent())
                button.clicked.connect(
                    lambda _c=False, index=i: self._count(index))
                track.addWidget(button)
            track.addStretch(1)
            wp.addLayout(track)

        cap = adv.mote_cap(a)
        if cap:
            shape = ("one pool" if a.essence_pool
                     else f"{a.personal_essence} personal + "
                          f"{a.peripheral_essence} peripheral")
            motes = self._panel(f"ESSENCE   ({max(0, cap - a.motes_spent)}/{cap} left "
                                f"— {shape})")
            spin = QSpinBox()
            spin.setObjectName("adv.motes_spent")
            spin.setRange(0, cap)
            spin.setValue(a.motes_spent)
            # ⚠ No pane rebuild from a spin box: a redraw deletes the widget
            # mid-keystroke and takes the focus with it. Only the row re-renders.
            spin.valueChanged.connect(
                lambda v: (adv.set_motes_spent(a, v), self._refresh_row()))
            self._labelled(motes, "Motes spent", spin)

    def _cycle(self, index: int) -> None:
        entry = self._current()
        if entry is None:
            return
        adv.cycle_mark(entry, index)
        self._sync_detail()
        self._refresh_row()

    def _count(self, index: int) -> None:
        entry = self._current()
        if entry is None:
            return
        adv.set_count(entry, "willpower_spent", index, entry.willpower)
        self._sync_detail()
        self._refresh_row()

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
        for field, label, tooltip in _IDENTITY:
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
