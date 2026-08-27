"""exalted_builder/qt/combos.py — the Combos sub-tab, under Charms.

Input: a RuleSet and the shared context's Character. Output: the settled collection
surface — a readout, an action toolbar, a sortable table of the character's Combos, and
a splitter with the selected one's members in a detail pane. Mechanism: `reload()`
rebuilds the table from `view.build_combo_view` (or `build_array_view`); selecting a row
builds its member editor; every mutation goes through `engine.combo_actions`, and a
post-lock purchase through `engine.advancement`.

⚠ **This is ONE tab rendering one of TWO systems, never both.** A Charm-Slot splat
(Alchemical, p.89-90) builds **Arrays** instead of Combos, and `view.uses_arrays` is the
one place that decides which — the noun, the presenter, the engine calls and the cost
sentence all key off it. A splat that builds neither has no sub-tab at all
(`view.has_combos_tab`; the dead may never learn Combos, E:Ab p.234), which `CharmsPage`
checks before constructing this.

⚠ **The two sides of the lock are different SHAPES, not the same shape disabled.**
At chargen a Combo is assembled in place — created empty, members added and removed,
priced in bonus points. In play it is **bought whole**: `advancement.add_combo` prices
the finished set, checks its legality and logs it in one go, so the toolbar's action
becomes a compose-and-buy dialog and the table goes read-only. A bought Combo is fixed;
taking one back is an XP undo in the shell's Experience card, not a list edit.

⚠ **It lives here and not on the rail.** Combos are a Charms SUB-TAB in the native shell
(2026-08-21, the human's call) because a Combo is assembled out of Charms the character
already owns. The webapp keeps its top-level tab, so `view.visible_tabs` still names one
and the shell discards that answer — do not "fix" the presenter to match.

Zero game logic. Every row, cost and issue comes from `ui/view.py`.
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
    """The sub-tab widget. `reload()` rebuilds for the character in ctx; `notify`
    surfaces transient messages; `on_change` pings the owning page so its readout and
    the shell's re-derive."""

    def __init__(self, ruleset, ctx, *, notify=None, on_change=None, parent=None):
        super().__init__(parent)
        self._ruleset = ruleset
        self._ctx = ctx
        self._notify = notify or (lambda text, kind="info": None)
        self._on_change = on_change
        # The selected row's INDEX into character.combos / .arrays. ⚠ Dropped on a
        # rebuild that added or removed a row: an index is a position, and deleting one
        # renumbers everything after it.
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
        """⚠ Read per call, never cached in `__init__`. The splat can change on the
        Identity tab while this page exists, and a cached answer would leave an
        Alchemical building Combos."""
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
        """A change that moved the LIST. ⚠ Drops the selection first — it is a POSITION,
        and adding or deleting renumbers every row after it."""
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
        """⚠ The two sides of the lock offer DIFFERENT actions, not the same ones
        greyed. At chargen you build a Combo up; in play you buy a finished one."""
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
        # ⚠ The empty-table message is re-texted per fill, not set once: this tab names
        # its own subject (a Combo, or an Alchemical's Array) and the way in changes at
        # the lock — assembled in place at chargen, bought whole in play.
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
                # ⚠ The bonus-point price is a CHARGEN fact. In play the thing has
                # already been paid for and its XP price is on the ledger, so quoting
                # BP beside a bought Combo invents a cost that is not owed.
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
        # ⚠ `clear_layout`, never a hand-written loop — this pane is nothing but rows.
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
            # ⚠ No rebuild per keystroke: it would tear down the box being typed into.
            # The table cell is re-synced on its own.
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
            # The installation discount is the mechanical POINT of an Array, so say what
            # this one actually saves in committed Personal Essence.
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
        """What may still go in this one.

        ⚠ For an ARRAY the pool excludes every Charm linked into ANY Array, not merely
        this one's own members — a Charm may join only one (p.90), and the engine
        refuses a reuse, so offering it would produce nothing but a rejection.
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
        """Run one engine call, turning a refusal into a notification. ⚠ Catches
        `advancement.AdvancementError` — the type every action module raises."""
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
            # Land on the row just made: it is empty, and the member picker is the next
            # thing the player wants.
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
        """A membership change moves the cost and the issues but NOT the row set, so the
        selection survives — unlike `_rebuild`, which drops it."""
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
        """Compose a whole one, then buy it — BUILT but not run, because `exec()` blocks
        a headless run and this is the seam the tests drive (the shape `GearPage` uses).

        ⚠ Unlike the chargen builder there is no empty state to save: the engine prices
        and validates the finished set, all or nothing.
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
        # ⚠ No current item: a multi-select list highlights row 0 by default, which reads
        # as "already picked" while `selectedItems()` is empty and Buy is disabled — the
        # user sees a selection and a dead button and cannot tell why.
        picker.setCurrentRow(-1)
        lay.addWidget(picker, 1)

        name = QLineEdit()
        name.setObjectName("combos.buy.name")
        name.setPlaceholderText(f"{noun.lower()} name")
        self._labelled(lay, "Name", name)

        price = QLabel("")
        price.setObjectName("combos.buy.price")
        # ⚠ Wrapped: the sentence carries the page citation, and unwrapped it clipped to
        # "…minimum Ability ratings (p.21" against the dialog edge.
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
            # ⚠ Disabled on an EMPTY pick too, not only on an unaffordable one: a zero
            # -cost purchase of nothing would log an XP entry for an illegal Combo.
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
