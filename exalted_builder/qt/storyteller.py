"""exalted_builder/qt/storyteller.py — the ST Options tab: the table's optional rules.

Input: a RuleSet and the Character in the shared context. Output: the collection surface.
It has a readout line, one sub-tab for each scope with a sortable table of rules, and a
splitter that puts the control of the selected rule in a detail pane. Mechanism:
`reload()` rebuilds both tables from `view.build_house_rules`, then selects the rule that
was selected before. A change to a control writes through
`engine.house_rule_actions.set_rule` and reloads, because a house rule changes what the
OTHER rows report about themselves.

⚠ **The toggles are frozen at the lock.** This is the difference between this tab and the
other collections. The toggles change the PRICE of chargen. Thus a change after the lock
prices an approved chargen again. After the lock, every control is disabled, and the
readout shows the Unlock route. This is the route for any other chargen correction. The
tab of the webapp operates in the same way.

⚠ **`on_change` is REQUIRED here.** `magic_for_everyone` gives free purchases, and
`godblooded_inheritance_rating` changes the bonus-point pool. Thus a change moves the
readout bar of the shell. A page that you add to the shell takes this hook contract from
the other pages.

⚠ **This tab has no action toolbar.** The collection layout puts the actions in a toolbar,
and this collection has no actions. The books fix the rules. Thus you cannot add, buy or
delete a rule. This absence is intended.

This module has no game logic. `ui/view.py` supplies every row, every note and every
label. The one mutation goes through `engine.house_rule_actions`.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QHBoxLayout, QHeaderView, QLabel,
    QScrollArea, QSplitter, QTabWidget, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
    QWidget,
)

from exalted_builder.engine import house_rule_actions
from exalted_builder.ui import theme
from exalted_builder.ui import view as viewmod

from .layout import clear_layout
from .theme import MUTED, accent as accent_light

_COLUMNS = ("Rule", "Setting", "Source")

# The scopes, in the order that the tab shows them. ⚠ Read the scopes from the presenter.
# Do not write them in the code. `HouseRules` marks each field TABLE-WIDE or
# PER-CHARACTER. A party-wide "apply to all" control can change a TABLE-WIDE field only.
_SCOPES = ("table", "character")

_LOCKED_NOTE = (
    "Chargen is locked, so these are read-only. They change how bonus points are "
    "spent and were frozen into the chargen snapshot at the lock — changing one now "
    "would re-price a chargen that has already been signed off. Use Unlock in the top "
    "bar if a table rule really did change."
)


class StorytellerPage(QWidget):
    """The tab widget. `reload()` rebuilds the tables for the character in ctx. `notify`
    shows a temporary message. `on_change` calls the shell, thus the shell calculates its
    readout bar and its status strip again after a rule changes the accounting."""

    def __init__(self, ruleset, ctx, *, notify=None, on_change=None, parent=None):
        super().__init__(parent)
        self._ruleset = ruleset
        self._ctx = ctx
        self._notify = notify or (lambda text, kind="info": None)
        self._on_change = on_change
        # The selection is the FIELD NAME of the rule, not a row position. The set of rows
        # is fixed, and a field name stays correct through a rebuild. Thus a different rule
        # cannot move into the selected position.
        self._selected: str | None = None

        self.readout = QLabel("")
        self.readout.setWordWrap(True)
        self.readout.setContentsMargins(8, 4, 8, 4)

        # ---- a sortable table per scope ------------------------------- #
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self._tables: dict[str, QTreeWidget] = {}
        for scope in _SCOPES:
            table = QTreeWidget()
            table.setObjectName(f"houserules.{scope}")
            table.setColumnCount(len(_COLUMNS))
            table.setHeaderLabels(list(_COLUMNS))
            table.setRootIsDecorated(False)
            table.setAlternatingRowColors(True)
            table.setSortingEnabled(True)
            # ⚠ The table is sortable, but it starts unsorted. `setSortingEnabled(True)`
            # sorts by column 0 immediately. That puts the rules in alphabetical order and
            # removes the order of the presenter, which is the order of the BOOKS, with
            # Magic for Everyone first. `-1` removes the indicator and keeps the insertion
            # order until the user clicks a header.
            table.sortByColumn(-1, Qt.AscendingOrder)
            # ⚠ Also hide the indicator. `setSortingEnabled(True)` shows it. With no
            # section to mark, Qt draws the arrow over the LAST header. The table then
            # reads as sorted by Source.
            table.header().setSortIndicatorShown(False)
            table.setSelectionMode(QAbstractItemView.SingleSelection)
            # ⚠ Give the free width to the RULE column, not to the last column.
            # QHeaderView stretches its last section by default. Thus "Sidereal may hold
            # Celestial Manse above 3 dots" becomes "…Manse abo…", and empty space stays
            # below the Source header.
            table.header().setStretchLastSection(False)
            table.header().setSectionResizeMode(0, QHeaderView.Stretch)
            table.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
            table.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
            table.itemSelectionChanged.connect(self._selection_changed)
            self._tables[scope] = table
            self.tabs.addTab(table, viewmod.HOUSE_RULE_SCOPES[scope][0])
        self.tabs.currentChanged.connect(lambda *_: self._selection_changed())

        # ---- the detail pane ------------------------------------------ #
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
        split.addWidget(self.tabs)
        split.addWidget(detail_panel)
        split.setSizes([620, 560])

        # The text of the scope goes BELOW the splitter. It describes the full sub-tab. It
        # does not describe the selected rule.
        self.scope_note = QLabel("")
        self.scope_note.setWordWrap(True)
        self.scope_note.setContentsMargins(8, 2, 8, 4)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.readout)
        outer.addWidget(split, 1)
        outer.addWidget(self.scope_note)
        self.reload()

    # ------------------------------------------------------------------ #
    # plumbing
    # ------------------------------------------------------------------ #

    def _char(self):
        return self._ctx["char"]

    def _accent(self) -> str:
        return accent_light(theme.palette(self._char().exalt_type))

    def _rows(self) -> list:
        return viewmod.build_house_rules(self._ruleset, self._char())

    def _locked(self) -> bool:
        return self._char().chargen_locked

    def reload(self) -> None:
        """Rebuild both tables for the character in ctx, keeping the selection."""
        self._fill_tables()
        self._sync_readout()
        self._sync_detail()

    def _muted(self, text: str, *, italic: bool = False) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet(f"color:{MUTED};"
                            + (" font-style:italic;" if italic else ""))
        return label

    def _sync_readout(self) -> None:
        rows = self._rows()
        on = sum(1 for r in rows if not r.options and r.value)
        inert = sum(1 for r in rows if r.inert)
        # ⚠ Count the boolean toggles only. A multiple-choice rule always holds a value.
        # If you count it, the readout reports rules as on for every character, before the
        # Storyteller changes anything.
        bits = [f"{len(rows)} optional rules", f"{on} switched on"]
        if inert:
            bits.append(f"{inert} cannot affect this character")
        text = " · ".join(bits)
        if self._locked():
            self.readout.setText(f"{text}\n{_LOCKED_NOTE}")
            self.readout.setStyleSheet("color:#b45309;")
        else:
            self.readout.setText(text)
            self.readout.setStyleSheet(f"color:{self._accent()};")

    # ------------------------------------------------------------------ #
    # the tables
    # ------------------------------------------------------------------ #

    def _fill_tables(self) -> None:
        rows = self._rows()
        dim = QBrush(QColor(MUTED))
        for scope, table in self._tables.items():
            # ⚠ Turn sorting OFF for the full fill. If sorting is on, Qt sorts again after
            # each insert, and the order of the book citations is lost. The code below
            # restores the sort that the user selected. If it only enabled sorting again,
            # every reload would apply column 0 ascending, and each toggle causes a reload.
            column = table.header().sortIndicatorSection()
            order = table.header().sortIndicatorOrder()
            shown = table.header().isSortIndicatorShown()
            table.setSortingEnabled(False)
            table.blockSignals(True)
            table.clear()
            restore = None
            for row in [r for r in rows if r.scope == scope]:
                item = QTreeWidgetItem([row.label,
                                        viewmod.house_rule_setting_label(row),
                                        row.citation])
                item.setData(0, Qt.UserRole, row.field)
                if row.note:
                    for column in range(len(_COLUMNS)):
                        item.setToolTip(column, row.note)
                if row.inert:
                    # Make the row dim. Never hide it. A Storyteller who looks for a
                    # toggle must find it, and must read why it has no effect.
                    for column in range(len(_COLUMNS)):
                        item.setForeground(column, dim)
                table.addTopLevelItem(item)
                if row.field == self._selected:
                    restore = item
            table.setSortingEnabled(True)
            table.sortByColumn(column if shown else -1, order)
            table.header().setSortIndicatorShown(shown)
            if restore is not None:
                table.setCurrentItem(restore)
            elif table.topLevelItemCount():
                table.setCurrentItem(table.topLevelItem(0))
            # ⚠ Keep the signals blocked ACROSS `setCurrentItem`. This code fills both
            # tables in one pass. An unblocked selection on the inactive table sends
            # `_selection_changed`, which reads the ACTIVE table. That writes over
            # `self._selected` during the loop, and the table that is not yet filled
            # loses its selection.
            table.blockSignals(False)
        # The tables now hold a selection that no signal reported. Adopt it here. If you
        # do not, the detail pane shows "select a rule" next to a selected row.
        item = self._active_table().currentItem()
        self._selected = None if item is None else item.data(0, Qt.UserRole)

    def _active_table(self) -> QTreeWidget:
        return self._tables[_SCOPES[self.tabs.currentIndex()]]

    def _selection_changed(self) -> None:
        item = self._active_table().currentItem()
        self._selected = None if item is None else item.data(0, Qt.UserRole)
        self._sync_detail()

    # ------------------------------------------------------------------ #
    # the detail pane
    # ------------------------------------------------------------------ #

    def _sync_detail(self) -> None:
        """Rebuild the right-hand pane for the current selection."""
        # ⚠ Use `clear_layout`. Never write a teardown loop here. `item.widget()` is None
        # for a nested QLayout. Thus a widget-only sweep lets the old rows paint over the
        # new rows. `qt/layout.py` holds both traps.
        clear_layout(self._detail_lay)
        scope = _SCOPES[self.tabs.currentIndex()]
        heading, blurb = viewmod.HOUSE_RULE_SCOPES[scope]
        self.scope_note.setText(f"{heading} — {blurb}")
        self.scope_note.setStyleSheet(f"color:{MUTED};")

        row = next((r for r in self._rows() if r.field == self._selected), None)
        if row is None:
            self.detail_title.setText("")
            self._detail_lay.addWidget(self._muted("Select a rule to change it."))
            self._detail_lay.addStretch(1)
            return

        self.detail_title.setText(row.label)
        self.detail_title.setStyleSheet(
            f"font-weight:700; font-size:14px; color:{self._accent()};")
        self._detail_lay.addWidget(self._muted(row.citation))
        self._detail_lay.addWidget(self._muted(row.description))
        self._detail_lay.addWidget(self._control(row))
        if row.note:
            note = QLabel(row.note)
            note.setWordWrap(True)
            note.setStyleSheet(
                f"font-style:italic; color:{MUTED if row.inert else self._accent()};")
            self._detail_lay.addWidget(note)
        if self._locked():
            # Keep this text short. The readout above holds the full explanation. A long
            # paragraph next to the control makes the pane difficult to read.
            self._detail_lay.addWidget(
                self._muted("Read-only: chargen is locked.", italic=True))
        self._detail_lay.addStretch(1)

    def _control(self, row) -> QWidget:
        """The one editing control for a rule. A toggle gets a checkbox. A multiple-choice
        rule gets a combo box. The control takes the name of the field that it writes.
        Thus a test can address the rule by name, not by a position in the child list."""
        if row.options:
            combo = QComboBox()
            combo.setObjectName(f"houserule.{row.field}")
            for value, label in row.options.items():
                combo.addItem(label, value)
            combo.setCurrentIndex(max(0, combo.findData(str(row.value))))
            combo.setEnabled(not self._locked())
            # ⚠ Write the value that you index out of `row.options`. Never read the value
            # back from the widget. Qt returns item data as a QVariant, and an Enum with a
            # str value returns as a plain str.
            keys = list(row.options)
            combo.currentIndexChanged.connect(
                lambda index, f=row.field: self._set(f, keys[index]))
            holder = QWidget()
            lay = QHBoxLayout(holder)
            lay.setContentsMargins(0, 0, 0, 0)
            caption = QLabel("Setting")
            caption.setStyleSheet(f"color:{MUTED};")
            caption.setMinimumWidth(64)
            lay.addWidget(caption)
            lay.addWidget(combo, 1)
            return holder
        box = QCheckBox("Permission granted" if row.scope == "character"
                        else "Switched on")
        box.setObjectName(f"houserule.{row.field}")
        box.setChecked(bool(row.value))
        box.setEnabled(not self._locked())
        box.toggled.connect(lambda on, f=row.field: self._set(f, on))
        return box

    def _set(self, field: str, value) -> None:
        """Write one rule, then rebuild. The WHOLE tab reloads, not the one row. The note
        of a rule reports its current value, for example "granting 2 free purchases" or
        "offering all 61 Backgrounds". Thus a change to a rule rewrites its own line."""
        house_rule_actions.set_rule(self._char(), field, value)
        self.reload()
        if self._on_change is not None:
            self._on_change()
