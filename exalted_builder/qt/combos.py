"""exalted_builder/qt/combos.py — the Combos sub-tab, under Charms.

Input: a RuleSet and the Character in the shared context. Output: the collection surface.
It has a readout, an action toolbar, a sortable table of the Combos of the character, and
a splitter that puts the members of the selected row in a detail pane. Mechanism:
`reload()` rebuilds the table from `view.build_combo_view` or `build_array_view`. A
selected row builds its member editor. Every mutation goes through `engine.combo_actions`.
A purchase after the lock goes through `engine.advancement`.

⚠ **This is ONE tab, and it renders one of TWO systems. It never renders both.** A
Charm-Slot splat (Alchemical, p.89-90) builds **Arrays** in place of Combos.
`view.uses_arrays` is the one place that decides which system. The noun, the presenter,
the engine calls and the cost sentence all read it. A splat that builds neither system has
no sub-tab (`view.has_combos_tab`; the dead can never learn Combos, E:Ab p.234).
`CharmsPage` checks that flag before it constructs this page.

⚠ **The two sides of the lock have different SHAPES. One side is not the other side with
the controls disabled.** At chargen, the user assembles a Combo in place: create it empty,
add and remove members, and pay in bonus points. In play, the user **buys it whole**:
`advancement.add_combo` prices the finished set, checks its legality and logs it in one
call. Thus the toolbar action becomes a compose-and-buy dialog, and the table becomes
read-only. A Combo that the user bought is fixed. To remove one is an XP undo in the
Experience card of the shell. It is not an edit to the list.

⚠ **This page is a SUB-TAB of Charms. It is not on the rail** (human's ruling). A Combo is
assembled from Charms that the character owns. The webapp keeps its top-level tab, thus
`view.visible_tabs` names one, and the shell discards that answer. Do not change the
presenter to agree with the shell.

This module has no game logic. `ui/view.py` supplies every row, every cost and every issue.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QPushButton, QScrollArea, QSplitter, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

from exalted_builder.engine import advancement, combo_actions, costs, validate
from exalted_builder.ui import theme
from exalted_builder.ui import view as viewmod

from .layout import clear_layout, empty_note
from .theme import MUTED, accent as accent_light

_COLUMNS = ("", "Name", "Charms", "Cost")

_COMBO_BLURB = ("A Combo combines two or more known instant-duration Charms — at most "
                "one Simple, at most one Extra Action (core pp.213-214).")
_ARRAY_BLURB = ("An Array links two or more installed Attribute-based Charms into a "
                "permanent pattern, cutting their combined installation cost to "
                "three-fourths (p.89).")


class CombosPage(QWidget):
    """The sub-tab widget. `reload()` rebuilds for the character in ctx. `notify` shows a
    temporary message. `on_change` calls the owning page, thus that page and the shell
    calculate their readouts again."""

    def __init__(self, ruleset, ctx, *, notify=None, on_change=None, parent=None):
        super().__init__(parent)
        self._ruleset = ruleset
        self._ctx = ctx
        self._notify = notify or (lambda text, kind="info": None)
        self._on_change = on_change
        # The INDEX of the selected row into character.combos or .arrays. ⚠ Drop this
        # index on a rebuild that adds or removes a row. An index is a position, and a
        # delete gives a new number to every row after it.
        self._selected: int | None = None

        self.readout = QLabel("")
        self.readout.setWordWrap(True)
        self.readout.setContentsMargins(8, 4, 8, 4)

        bar = QHBoxLayout()
        bar.setContentsMargins(8, 0, 8, 0)
        self.add_btn = QPushButton("Add")
        self.add_btn.setObjectName("combos.add")
        self.add_btn.clicked.connect(self._add)
        bar.addWidget(self.add_btn)
        self.buy_btn = QPushButton("Buy…")
        self.buy_btn.setObjectName("combos.buy")
        self.buy_btn.clicked.connect(self._open_buy)
        bar.addWidget(self.buy_btn)
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setObjectName("combos.delete")
        self.delete_btn.clicked.connect(self._delete)
        bar.addWidget(self.delete_btn)
        bar.addStretch(1)

        self.table = QTreeWidget()
        self.table.setObjectName("combos.table")
        self.table.setColumnCount(len(_COLUMNS))
        self.table.setHeaderLabels(list(_COLUMNS))
        self.table.setRootIsDecorated(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(-1, Qt.AscendingOrder)
        self.table.header().setSortIndicatorShown(False)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.header().setStretchLastSection(False)
        self.table.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.header().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.header().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self._empty_note = empty_note(self.table, "")

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
        split.setSizes([520, 600])

        self.blurb = QLabel("")
        self.blurb.setWordWrap(True)
        self.blurb.setContentsMargins(8, 2, 8, 4)
        self.blurb.setStyleSheet(f"color:{MUTED};")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.readout)
        outer.addLayout(bar)
        outer.addWidget(split, 1)
        outer.addWidget(self.blurb)
        self.reload()

    # ------------------------------------------------------------------ #
    # which system, and plumbing
    # ------------------------------------------------------------------ #

    def _char(self):
        return self._ctx["char"]

    def _accent(self) -> str:
        return accent_light(theme.palette(self._char().exalt_type))

    def _arrays(self) -> bool:
        """⚠ Read this value on each call. Never cache it in `__init__`. The user can
        change the splat on the Identity tab while this page exists. With a cached value,
        an Alchemical builds Combos."""
        return viewmod.uses_arrays(self._ruleset, self._char())

    def _noun(self) -> str:
        return "Array" if self._arrays() else "Combo"

    def _locked(self) -> bool:
        return self._char().chargen_locked

    def _rows(self):
        if self._arrays():
            view = viewmod.build_array_view(self._ruleset, self._char())
            return view.arrays, view.addable, view.total_cost
        view = viewmod.build_combo_view(self._ruleset, self._char())
        return view.combos, view.addable, view.total_cost

    def _owned(self):
        return self._char().arrays if self._arrays() else self._char().combos

    def _muted(self, text: str, *, italic: bool = False) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet(f"color:{MUTED};"
                            + (" font-style:italic;" if italic else ""))
        return label

    def reload(self) -> None:
        self._fill_table()
        self._sync_readout()
        self._sync_actions()
        self._sync_detail()

    def _rebuild(self) -> None:
        """Apply a change that moved the LIST. ⚠ Drop the selection first. The selection is
        a POSITION, and an add or a delete gives a new number to every row after it."""
        self._selected = None
        self.reload()
        if self._on_change is not None:
            self._on_change()

    def _sync_readout(self) -> None:
        rows, addable, total = self._rows()
        noun = self._noun()
        if self._locked():
            available = advancement.xp_available(self._char())
            bits = [f"{len(rows)} {noun}(s)", f"{available} XP available"]
            self.readout.setText(" · ".join(bits))
            self.readout.setStyleSheet(
                "color:%s;" % ("#15803d" if available >= 0 else "#b91c1c"))
        else:
            self.readout.setText(
                f"{len(rows)} {noun}(s) · {total} bonus point(s) (1 per Charm)")
            self.readout.setStyleSheet(f"color:{self._accent()};")
        self.blurb.setText(_ARRAY_BLURB if self._arrays() else _COMBO_BLURB)
        if not addable and not self._locked():
            self.blurb.setText(
                self.blurb.text() + "\n" + self._nothing_to_add_message())
            self.blurb.setStyleSheet("color:#b45309;")
        else:
            self.blurb.setStyleSheet(f"color:{MUTED};")

    def _nothing_to_add_message(self) -> str:
        return ("No unlinked Attribute-based Charms — install Charms on the tree tabs "
                "first." if self._arrays() else
                "No instant-duration Charms known yet — learn Charms on the tree tabs "
                "first.")

    def _sync_actions(self) -> None:
        """⚠ The two sides of the lock give DIFFERENT actions. They are not the same
        actions disabled. At chargen, the user builds a Combo. In play, the user buys a
        finished Combo."""
        locked = self._locked()
        self.add_btn.setVisible(not locked)
        self.add_btn.setText(f"+ {self._noun()}")
        self.buy_btn.setVisible(locked)
        self.buy_btn.setText(f"Buy {self._noun()}…")
        self.delete_btn.setEnabled(not locked and self._selected is not None)
        self.delete_btn.setToolTip(
            f"A bought {self._noun()} is fixed — undo the purchase in the Experience "
            f"card" if locked else f"Delete this {self._noun()}")

    # ------------------------------------------------------------------ #
    # the table
    # ------------------------------------------------------------------ #

    def _fill_table(self) -> None:
        rows, _addable, _total = self._rows()
        locked = self._locked()
        # ⚠ Write the empty-table message on each fill. Do not set it one time. This tab
        # names its own subject, a Combo or the Array of an Alchemical. The method also
        # changes at the lock: assembled in place at chargen, bought whole in play.
        self._empty_note.setText(
            f"No {self._noun()}s yet.\n\n"
            + (f"Use “Buy {self._noun()}…” — in play one is bought whole, and priced "
               f"in XP." if locked
               else f"Use “+ {self._noun()}” and add Charms this character already "
                    f"owns."))
        self.table.setSortingEnabled(False)
        self.table.blockSignals(True)
        self.table.clear()
        restore = None
        for row in rows:
            errors = bool(row.issues)
            item = QTreeWidgetItem([
                "⚠" if errors else "",
                row.name,
                str(len(row.members)),
                # ⚠ The bonus-point price applies to CHARGEN only. In play, the user has
                # paid for the Combo, and its XP price is on the ledger. A BP price next to
                # a bought Combo shows a cost that the user does not owe.
                "—" if locked else f"{row.cost} BP"])
            item.setData(0, Qt.UserRole, row.index)
            if errors:
                for column in range(len(_COLUMNS)):
                    item.setToolTip(column, "\n".join(row.issues))
            self.table.addTopLevelItem(item)
            if row.index == self._selected:
                restore = item
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(-1, Qt.AscendingOrder)
        self.table.header().setSortIndicatorShown(False)
        if restore is not None:
            self.table.setCurrentItem(restore)
        elif self.table.topLevelItemCount():
            self.table.setCurrentItem(self.table.topLevelItem(0))
        else:
            self._selected = None
        self.table.blockSignals(False)
        item = self.table.currentItem()
        self._selected = None if item is None else item.data(0, Qt.UserRole)

    def _selection_changed(self) -> None:
        item = self.table.currentItem()
        self._selected = None if item is None else item.data(0, Qt.UserRole)
        self._sync_actions()
        self._sync_detail()

    # ------------------------------------------------------------------ #
    # the detail pane — the members
    # ------------------------------------------------------------------ #

    def _sync_detail(self) -> None:
        # ⚠ Use `clear_layout`. Never write a teardown loop. This pane holds rows only.
        clear_layout(self._detail_lay)
        rows, addable, _total = self._rows()
        row = next((r for r in rows if r.index == self._selected), None)
        if row is None:
            self.detail_title.setText("")
            self._detail_lay.addWidget(self._muted(
                f"Select a {self._noun()}, or make one."
                if not self._locked() else f"Select a {self._noun()}."))
            self._detail_lay.addStretch(1)
            return

        self.detail_title.setText(row.name)
        self.detail_title.setStyleSheet(
            f"font-weight:700; font-size:14px; color:{self._accent()};")

        if not self._locked():
            name = QLineEdit(row.name)
            name.setObjectName("combos.name")
            # ⚠ Do not rebuild on each keystroke. A rebuild deletes the box that the user
            # types into. This code updates the table cell alone.
            name.textChanged.connect(lambda text, i=row.index: self._rename(i, text))
            self._labelled(self._detail_lay, "Name", name)

        self._detail_lay.addWidget(self._heading("Charms"))
        if not row.members:
            self._detail_lay.addWidget(self._muted(
                "(empty — add Charms below)" if not self._locked() else "(empty)"))
        for member in row.members:
            line = QHBoxLayout()
            label = QLabel(member.name)
            label.setWordWrap(True)
            line.addWidget(label, 1)
            detail = QLabel(self._member_detail(member))
            detail.setStyleSheet(f"color:{MUTED};")
            line.addWidget(detail)
            if not self._locked():
                drop = QPushButton("✕")
                drop.setObjectName(f"combos.drop.{member.id}")
                drop.clicked.connect(
                    lambda _=False, i=row.index, cid=member.id: self._drop(i, cid))
                line.addWidget(drop)
            self._detail_lay.addLayout(line)

        if self._arrays() and row.install_loose:
            # The installation discount is the mechanical purpose of an Array. Thus show
            # the Personal Essence that this Array saves.
            self._detail_lay.addWidget(self._muted(
                f"Installs for {row.install_arrayed}m instead of {row.install_loose}m — "
                f"saves {row.install_loose - row.install_arrayed}m committed Essence."))

        if not self._locked():
            pool = self._addable_for(row, addable)
            if pool:
                self._detail_lay.addWidget(self._heading("Add a Charm"))
                picker = QListWidget()
                picker.setObjectName("combos.addable")
                for member in pool:
                    entry = QListWidgetItem(
                        f"{member.name} · {self._member_detail(member)}")
                    entry.setData(Qt.UserRole, member.id)
                    picker.addItem(entry)
                picker.setMaximumHeight(180)
                picker.itemDoubleClicked.connect(
                    lambda entry, i=row.index: self._add_member(
                        i, entry.data(Qt.UserRole)))
                self._detail_lay.addWidget(picker)
                add = QPushButton("Add selected")
                add.setObjectName("combos.add_member")
                add.clicked.connect(
                    lambda: self._add_selected(row.index, picker))
                self._detail_lay.addWidget(add)

        for message in row.issues:
            line = QLabel(f"• {message}")
            line.setWordWrap(True)
            line.setStyleSheet("color:#b91c1c;")
            self._detail_lay.addWidget(line)
        self._detail_lay.addStretch(1)

    def _addable_for(self, row, addable):
        """The Charms that the user can still add to this Combo or Array.

        ⚠ For an ARRAY, remove every Charm that is in ANY Array, not the members of this
        Array only. A Charm can join one Array only (p.90), and the engine refuses a
        second use. Thus an offer of such a Charm gives a refusal and nothing else.
        """
        taken = {m.id for m in row.members}
        if self._arrays():
            taken |= combo_actions.linked_array_charms(self._char())
        return [m for m in addable if m.id not in taken]

    def _member_detail(self, member) -> str:
        return (f"{member.attribute} {member.rating}" if self._arrays()
                else member.type)

    def _heading(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(f"font-weight:600; color:{self._accent()};")
        return label

    def _labelled(self, lay, caption: str, widget) -> None:
        row = QHBoxLayout()
        label = QLabel(caption)
        label.setStyleSheet(f"color:{MUTED};")
        label.setMinimumWidth(64)
        row.addWidget(label)
        row.addWidget(widget, 1)
        lay.addLayout(row)

    # ------------------------------------------------------------------ #
    # mutations
    # ------------------------------------------------------------------ #

    def _act(self, call) -> bool:
        """Run one engine call. Change a refusal into a notification. ⚠ Catch
        `advancement.AdvancementError`. Every action module raises that type."""
        try:
            message = call()
        except advancement.AdvancementError as exc:
            self._notify(str(exc), "warning")
            return False
        if message:
            self._notify(message, "info")
        return True

    def _add(self) -> None:
        add = combo_actions.add_array if self._arrays() else combo_actions.add_combo
        if self._act(lambda: add(self._char())):
            self._rebuild()
            # Select the new row. The row is empty, and the user opens the member picker
            # next.
            if self.table.topLevelItemCount():
                self.table.setCurrentItem(
                    self.table.topLevelItem(self.table.topLevelItemCount() - 1))

    def _delete(self) -> None:
        if self._selected is None:
            return
        drop = (combo_actions.remove_array if self._arrays()
                else combo_actions.remove_combo)
        if self._act(lambda: drop(self._char(), self._selected)):
            self._rebuild()

    def _add_selected(self, index: int, picker: QListWidget) -> None:
        item = picker.currentItem()
        if item is None:
            self._notify(f"Pick a Charm to add to this {self._noun()}.", "info")
            return
        self._add_member(index, item.data(Qt.UserRole))

    def _add_member(self, index: int, charm_id: str) -> None:
        add = (combo_actions.add_array_member if self._arrays()
               else combo_actions.add_combo_member)
        if self._act(lambda: add(self._char(), index, charm_id)):
            self._members_changed(index)

    def _drop(self, index: int, charm_id: str) -> None:
        drop = (combo_actions.remove_array_member if self._arrays()
                else combo_actions.remove_combo_member)
        if self._act(lambda: drop(self._char(), index, charm_id)):
            self._members_changed(index)

    def _members_changed(self, index: int) -> None:
        """A change to the members moves the cost and the issues. It does NOT change the
        set of rows. Thus the selection stays. `_rebuild` drops the selection."""
        self._selected = index
        self.reload()
        if self._on_change is not None:
            self._on_change()

    def _rename(self, index: int, name: str) -> None:
        rename = (combo_actions.rename_array if self._arrays()
                  else combo_actions.rename_combo)
        rename(self._char(), index, name)
        self.detail_title.setText(name)
        item = self.table.currentItem()
        if item is not None:
            item.setText(1, name)

    # ------------------------------------------------------------------ #
    # buying one whole, in play
    # ------------------------------------------------------------------ #

    def _build_buy_dialog(self) -> QDialog:
        """Compose a whole Combo, then buy it. This function BUILDS the dialog and does
        not run it. `exec()` stops a headless run, and the tests drive this seam.
        `GearPage` uses the same shape.

        ⚠ The chargen builder can save an empty state. This path cannot. The engine prices
        and validates the finished set, and it accepts all of it or none of it.
        """
        arrays = self._arrays()
        noun = self._noun()
        char, ruleset = self._char(), self._ruleset
        eligible = (validate.eligible_array_charms(ruleset, char) if arrays
                    else validate.eligible_combo_charms(ruleset, char))
        if arrays:
            linked = combo_actions.linked_array_charms(char)
            eligible = [cid for cid in eligible if cid not in linked]

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Buy a {noun}")
        dialog.setMinimumSize(520, 460)
        lay = QVBoxLayout(dialog)
        lay.addWidget(self._muted(_ARRAY_BLURB if arrays else _COMBO_BLURB))
        if not eligible:
            lay.addWidget(self._muted(self._nothing_to_add_message()))
            close = QPushButton("Close")
            close.clicked.connect(dialog.reject)
            lay.addWidget(close)
            return dialog

        picker = QListWidget()
        picker.setObjectName("combos.buy.charms")
        picker.setSelectionMode(QAbstractItemView.MultiSelection)
        for charm_id in eligible:
            charm = ruleset.charms[charm_id]
            entry = QListWidgetItem(charm.name)
            entry.setData(Qt.UserRole, charm_id)
            picker.addItem(entry)
        # ⚠ Set no current item. A multi-select list marks row 0 by default. That row reads
        # as selected, but `selectedItems()` is empty and Buy stays disabled. The user then
        # sees a selection and a disabled button, and cannot find the reason.
        picker.setCurrentRow(-1)
        lay.addWidget(picker, 1)

        name = QLineEdit()
        name.setObjectName("combos.buy.name")
        name.setPlaceholderText(f"{noun.lower()} name")
        self._labelled(lay, "Name", name)

        price = QLabel("")
        price.setObjectName("combos.buy.price")
        # ⚠ Set word wrap on. The sentence carries the page citation. Without wrap, the
        # dialog edge cuts it to "…minimum Ability ratings (p.21".
        price.setWordWrap(True)
        lay.addWidget(price)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(dialog.reject)
        buttons.addWidget(cancel)
        buy = QPushButton(f"Buy {noun}")
        buy.setObjectName("combos.buy.confirm")
        buttons.addWidget(buy)
        lay.addLayout(buttons)

        def picked() -> list[str]:
            return [i.data(Qt.UserRole) for i in picker.selectedItems()]

        def resync() -> None:
            ids = picked()
            cost = (costs.array_cost(ruleset, ids) if arrays
                    else costs.combo_cost(ruleset, ids))
            available = advancement.xp_available(char)
            price.setText(
                f"{cost} XP — {available} available. "
                + ("An Array costs the sum of its Charms' minimum Attribute ratings "
                   "(p.89)." if arrays else
                   "A Combo costs the sum of its Charms' minimum Ability ratings "
                   "(p.213)."))
            # ⚠ Disable Buy on an EMPTY selection, and not on an unaffordable one only. A
            # purchase of nothing costs zero, and it logs an XP entry for an illegal Combo.
            buy.setEnabled(bool(ids) and cost <= available)

        picker.itemSelectionChanged.connect(resync)
        buy.clicked.connect(lambda: self._buy(dialog, name.text(), picked()))
        resync()
        return dialog

    def _open_buy(self) -> None:
        self._build_buy_dialog().exec()

    def _buy(self, dialog, name: str, charm_ids: list[str]) -> None:
        purchase = (advancement.add_array if self._arrays()
                    else advancement.add_combo)
        try:
            purchase(self._ruleset, self._char(), name.strip(), list(charm_ids))
        except advancement.AdvancementError as exc:
            self._notify(str(exc), "warning")
            return
        cost = (costs.array_cost(self._ruleset, charm_ids) if self._arrays()
                else costs.combo_cost(self._ruleset, charm_ids))
        self._notify(f"Bought {name.strip() or self._noun()} — {cost} XP", "info")
        dialog.accept()
        self._rebuild()
