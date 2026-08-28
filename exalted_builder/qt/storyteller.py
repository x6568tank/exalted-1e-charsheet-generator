"""exalted_builder/qt/storyteller.py — the ST Options tab: the table's optional rules.

Input: a RuleSet and the shared context's Character. Output: the settled collection
surface — a readout line, a sub-tab per scope holding a sortable table of rules, and a
splitter with the selected rule's control in a detail pane. Mechanism: `reload()`
rebuilds both tables from `view.build_house_rules` and re-selects the rule that was
selected before; flipping a control writes through `engine.house_rule_actions.set_rule`
and reloads, because a house rule changes what OTHER rows say about themselves.

⚠ **The toggles are frozen at the lock**, and that is the whole reason this tab differs
from the other collections. They change how chargen is PRICED, so flipping one after
the fact retroactively re-prices a signed-off chargen. Post-lock every control is
disabled and the readout points at Unlock — the same route as any other chargen
correction. The webapp's tab does exactly this.

⚠ **`on_change` is REQUIRED here.** `magic_for_everyone` grants free purchases and
`godblooded_inheritance_rating` moves the bonus-point pool, so a flip moves the shell's
readout bar. (`CharmsPage` shipped without the hook for want of this check — a page
added to the shell inherits a hook contract from its siblings.)

⚠ **No action toolbar, deliberately.** The collection layout puts actions in one, and
this collection has none: the rules are fixed by the books, so there is nothing to add,
buy or delete. The absence is written down so it reads as a decision, not as drift.

Zero game logic. Every row, every note and every label comes from `ui/view.py`; the one
mutation goes through `engine.house_rule_actions`.
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

# The scopes, in the order the tab shows them. ⚠ Read from the presenter rather than
# hardcoded: `HouseRules` marks each field TABLE-WIDE or PER-CHARACTER, and a party-wide
# "apply to all" control may only ever touch the first of these.
_SCOPES = ("table", "character")

_LOCKED_NOTE = (
    "Chargen is locked, so these are read-only. They change how bonus points are "
    "spent and were frozen into the chargen snapshot at the lock — changing one now "
    "would re-price a chargen that has already been signed off. Use Unlock in the top "
    "bar if a table rule really did change."
)


class StorytellerPage(QWidget):
    """The tab widget. `reload()` rebuilds the tables for the character in ctx;
    `notify` surfaces transient messages; `on_change` pings the shell so its readout bar
    and status strip re-derive after a rule moves the accounting."""

    def __init__(self, ruleset, ctx, *, notify=None, on_change=None, parent=None):
        super().__init__(parent)
        self._ruleset = ruleset
        self._ctx = ctx
        self._notify = notify or (lambda text, kind="info": None)
        self._on_change = on_change
        # The selection is the rule's FIELD NAME, not a row position — the row set is
        # fixed and a field survives any rebuild, so there is no slid-into-that-slot
        # hazard here.
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
            # ⚠ Sortable, but not sorted to start with. Enabling sorting sorts by
            # column 0 immediately, which threw the rules into alphabetical order and
            # lost the presenter's — which is the order the BOOKS introduce them in,
            # Magic for Everyone first. `-1` clears the indicator and leaves insertion
            # order until the player clicks a header.
            table.sortByColumn(-1, Qt.AscendingOrder)
            # ⚠ And hide the indicator explicitly: `setSortingEnabled(True)` turns it on,
            # and with no section to point at Qt drew the little arrow over the LAST
            # header instead, as though the rules were sorted by Source.
            table.header().setSortIndicatorShown(False)
            table.setSelectionMode(QAbstractItemView.SingleSelection)
            # ⚠ The RULE column takes the slack, not the last one. QHeaderView stretches
            # its last section by default, so with both on, "Sidereal may hold Celestial
            # Manse above 3 dots" elided to "…Manse abo…" while dead space sat under
            # the Source header.
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

        # The scope's blurb sits UNDER the splitter: it is about the whole sub-tab, not
        # about whichever rule happens to be selected.
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
        # ⚠ Only the boolean toggles are counted as "on". A multiple-choice rule always
        # holds a value, so counting it would report every character as having rules
        # switched on before the ST has touched anything.
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
            # ⚠ Sorting OFF across the fill: with it on Qt re-sorts after every insert,
            # which scrambles the order the books are cited in. The player's chosen sort
            # is restored afterwards — re-enabling alone would silently re-impose column
            # 0 ascending on every reload, and a reload happens on every toggle.
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
                    # Dimmed, never hidden — an ST hunting for a toggle must find it and
                    # be told why it does nothing (the presenter's whole premise).
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
            # ⚠ Signals stay blocked ACROSS `setCurrentItem`. Both tables are filled in
            # one pass, so an unblocked select on the inactive one would fire
            # `_selection_changed`, which reads the ACTIVE table — overwriting
            # `self._selected` halfway through the loop and losing the restore for the
            # table not yet filled.
            table.blockSignals(False)
        # The tables now hold a selection that no signal announced, so adopt it here or
        # the detail pane reads "select a rule" beside a visibly selected row.
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
        # ⚠ `clear_layout`, never a hand-written loop — `item.widget()` is None for a
        # nested QLayout, so a widget-only sweep leaves the old rows painting over the
        # new ones (qt/layout.py owns both traps).
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
            # Short here on purpose — the readout above already carries the full
            # explanation, and repeating a five-line paragraph beside the control it
            # describes is the wall of text the webapp's card avoided.
            self._detail_lay.addWidget(
                self._muted("Read-only: chargen is locked.", italic=True))
        self._detail_lay.addStretch(1)

    def _control(self, row) -> QWidget:
        """The one editing control for a rule: a checkbox for a toggle, a combo for a
        multiple-choice rule. Named after the field it writes so a test addresses the
        rule it means rather than a position in the child list."""
        if row.options:
            combo = QComboBox()
            combo.setObjectName(f"houserule.{row.field}")
            for value, label in row.options.items():
                combo.addItem(label, value)
            combo.setCurrentIndex(max(0, combo.findData(str(row.value))))
            combo.setEnabled(not self._locked())
            # ⚠ The value written is the one indexed out of `row.options`, never read
            # back off the widget — Qt hands item data back as a QVariant and a
            # str-valued Enum returns as a plain str (CLAUDE.md's Qt trap).
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
        """Write one rule and rebuild. The WHOLE tab reloads rather than just the row:
        a rule's note reports what it is currently worth ("granting 2 free purchases",
        "offering all 61 Backgrounds"), so flipping one restates its own line."""
        house_rule_actions.set_rule(self._char(), field, value)
        self.reload()
        if self._on_change is not None:
            self._on_change()
