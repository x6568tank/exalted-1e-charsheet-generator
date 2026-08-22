"""exalted_builder/qt/gear.py — the Gear tab: everything the character OWNS.

Input: a RuleSet and the shared context's Character. Output: a master-detail surface —
a readout bar, an action toolbar, a splitter holding the inventory table (and the
services price list on its own sub-tab) beside the selected item's editor, and the
artifacts budget line beneath. Mechanism: `reload()` rebuilds the table and re-selects
whatever was selected before; changing the selection rebuilds only the detail pane, and
anything a keystroke touches writes straight to the model and re-syncs its own labels.

⚠ **This is the Charms tab's shape, deliberately** (human, 2026-08-21). The first
version was the NiceGUI page transliterated — a floating Buy button with a sentence
beside it, accordion "Edit" expanders, and a stack of cards in a scroll area. It worked
and read as a web page. A desktop app puts actions in a toolbar, lists in a table with
a header, and the thing you selected in a detail pane. **A new surface here copies
`qt/charms.py`'s layout, not `ui/<tab>.py`'s.**

⚠ Keep the four lists on ONE tab. Splitting an artifact daiklave's STATS onto one
surface and its BUDGET onto another is what let the same object be entered twice and
charged twice (`docs/status/rated-artifacts.md`).

Zero game logic. Every mutation goes through `engine.gear_actions`, every derived list
and every line of text through `ui/view.py`.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QPushButton, QScrollArea, QSpinBox, QSplitter, QTabWidget, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

from exalted_builder import custom_content as customs
from exalted_builder.engine import (artifacts as artifactsmod, derive as derivemod,
                                    gear_actions, validate)
from exalted_builder.ui import theme
from exalted_builder.ui import view as viewmod

from .catalogue import CatalogueDialog
from .layout import clear_layout
from .editor import _FilterCombo
from .theme import MUTED, accent as accent_light

# The issue codes this tab can do something about. ⚠ Artifact findings belong HERE,
# with the panel that produces them — a report sitting on a surface that no longer
# edits the thing it reports about is the house bug in UI form. The Advantages tab
# renders the same findings beside the Artifact Background; one issue list, so the two
# cannot disagree.
_MY_ISSUES = ("artifact", "hearthstone")

_COLUMNS = ("Name", "Qty", "Res", "Kind", "Detail")

# The per-kind stat editors, as `(field, label, signed)`. A table rather than fifteen
# hand-built spin boxes, so the two kinds cannot drift in layout or in bounds.
#
# ⚠ `mobility_penalty` is stored NEGATIVE (`docs/status/gear-and-inventory.md`), so it
# is signed and its floor is below zero. A consumer that reads it as a magnitude adds
# dice instead of removing them.
_WEAPON_STATS = (("speed", "Spd", True), ("accuracy", "Acc", True),
                 ("damage", "Dmg", True), ("defense", "Def", True),
                 ("rate", "Rate", False), ("range", "Rng", False),
                 ("min_strength", "Min Str", False),
                 ("min_dexterity", "Min Dex", False),
                 ("min_martial_arts", "Min MA", False),
                 ("max_strength", "Max Str", False),
                 ("artifact_rating", "Art", False), ("attunement", "Attune", False),
                 ("resources_cost", "Res", False))

_ARMOR_STATS = (("soak_lethal", "Soak L", False), ("soak_bashing", "Soak B", False),
                ("mobility_penalty", "Mob", True), ("fatigue", "Ftg", False),
                ("artifact_rating", "Art", False), ("attunement", "Attune", False),
                ("resources_cost", "Res", False))

_SHOP_SUBTITLE = ("Everything a book prices, against your Resources, plus your own "
                  "library. Nothing is deducted — the cost is a hint (core p.325).")

_RES_TOOLTIP = ("The Resources rating needed to buy one (M&C p.123). A record of the "
                "price, not a trait.")


class GearPage(QWidget):
    """The tab widget. `reload()` rebuilds the table for the character in ctx; `notify`
    surfaces transient messages; `on_change` pings the shell so its readout bar and
    status strip re-derive."""

    def __init__(self, ruleset, ctx, *, notify=None, on_change=None, parent=None):
        super().__init__(parent)
        self._ruleset = ruleset
        self._ctx = ctx
        self._notify = notify or (lambda text, kind="info": None)
        self._on_change = on_change
        self._filter = "all"
        self._search = ""
        # The selected row as `(list_name, index)`. ⚠ Kept so a rebuild can re-select
        # what the player was editing — but positions shift when a row is added or
        # deleted, so `_rebuild` clears it rather than re-selecting whatever slid into
        # that slot.
        self._selected: tuple[str, int] | None = None

        self.readout = QLabel("")
        self.readout.setWordWrap(True)
        self.readout.setContentsMargins(8, 4, 8, 4)

        # ---- the action toolbar -------------------------------------- #
        # ⚠ Actions live HERE, not in the content flow. A Buy button floating mid-page
        # with an explanatory sentence beside it is a web call-to-action.
        bar = QHBoxLayout()
        bar.setContentsMargins(8, 0, 8, 0)
        self.buy_btn = QPushButton("Buy…")
        self.buy_btn.setObjectName("buyButton")
        self.buy_btn.clicked.connect(self._open_shop)
        bar.addWidget(self.buy_btn)
        self.add_artifact_btn = QPushButton("+ Artifact")
        self.add_artifact_btn.clicked.connect(self._open_artifact_catalogue)
        bar.addWidget(self.add_artifact_btn)
        bar.addSpacing(12)
        show = QLabel("Show:")
        show.setStyleSheet(f"color:{MUTED};")
        bar.addWidget(show)
        self.filter_combo = QComboBox()
        self.filter_combo.currentIndexChanged.connect(self._filter_changed)
        bar.addWidget(self.filter_combo)
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("filter by name…")
        self.search_box.setClearButtonEnabled(True)
        self.search_box.textChanged.connect(self._search_changed)
        bar.addWidget(self.search_box, 1)

        # ---- the inventory table ------------------------------------- #
        self.table = QTreeWidget()
        self.table.setColumnCount(len(_COLUMNS))
        self.table.setHeaderLabels(list(_COLUMNS))
        self.table.setRootIsDecorated(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.header().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.itemSelectionChanged.connect(self._selection_changed)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.addTab(self.table, "Inventory")
        self.prices = QWidget()
        self._prices_lay = QVBoxLayout(self.prices)
        prices_scroll = QScrollArea()
        prices_scroll.setWidgetResizable(True)
        prices_scroll.setWidget(self.prices)
        self.tabs.addTab(prices_scroll, "Prices")
        self.tabs.currentChanged.connect(lambda *_: self._sync_detail())

        # ---- the detail pane ----------------------------------------- #
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
        split.setSizes([720, 460])

        # The budget line sits UNDER the splitter, spanning both — it is about the
        # collection, not about whichever row happens to be selected.
        self.budget = QLabel("")
        self.budget.setWordWrap(True)
        self.budget.setContentsMargins(8, 2, 8, 4)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.readout)
        outer.addLayout(bar)
        outer.addWidget(split, 1)
        outer.addWidget(self.budget)
        self.reload()

    # ------------------------------------------------------------------ #
    # plumbing
    # ------------------------------------------------------------------ #

    def _char(self):
        return self._ctx["char"]

    def _pal(self):
        return theme.palette(self._char().exalt_type)

    def _accent(self) -> str:
        return accent_light(self._pal())

    def _clear_lay(self, lay) -> None:
        """Empty `lay`, detaching every descendant NOW. One line, because the shape is
        subtle enough that six hand-written copies produced a wrong one — see
        `qt/layout.py`, which owns both traps and the reason they matter."""
        clear_layout(lay)

    def reload(self) -> None:
        """Rebuild the table and the price list for the character in ctx, keeping the
        selection where the player left it."""
        self._sync_filter_combo()
        self._fill_table()
        self._fill_prices()
        self._sync_readout()
        self._sync_detail()

    def _rebuild(self) -> None:
        """A change that moved the LISTS — rebuild everything and ping the shell.

        ⚠ Drops the selection first. It is a POSITION, and adding or deleting a row
        renumbers every row after it, so a surviving key would re-select whatever slid
        into that slot.
        """
        self._selected = None
        self.reload()
        if self._on_change is not None:
            self._on_change()

    def _changed(self) -> None:
        """A change that only moves the readouts — a stat edit, a rename, a quantity."""
        self._sync_readout()
        self._refresh_selected_row()
        if self._on_change is not None:
            self._on_change()

    def _sync_readout(self) -> None:
        ruleset, char = self._ruleset, self._char()
        rows = viewmod.inventory_rows(ruleset, char)
        res = validate.effective_background_rating(ruleset, char, "Resources")
        bits = [f"{len(rows)} items owned",
                f"Resources {'•' * res if res else '—'}"]
        issues = [i for i in viewmod.build_sheet_view(ruleset, char).issues
                  if any(k in i.code for k in _MY_ISSUES)]
        self.readout.setText(" · ".join(bits)
                             + ("" if not issues
                                else "\n" + "\n".join(f"• {i.message}" for i in issues)))
        worst = ("#b91c1c" if any(i.severity == "error" for i in issues)
                 else "#b45309" if issues else self._accent())
        self.readout.setStyleSheet(f"color:{worst};")
        self.budget.setText(viewmod.artifacts_header(ruleset, char))
        self.budget.setStyleSheet(f"font-weight:600; color:{self._accent()};")
        for extra in (viewmod.artifacts_bought_note(char),
                      viewmod.artifacts_also_counted(char)):
            if extra:
                self.budget.setText(self.budget.text() + " · " + extra)

    def _muted(self, text: str, *, italic: bool = False) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet(f"color:{MUTED};"
                            + (" font-style:italic;" if italic else ""))
        return label

    def _heading(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(f"font-weight:600; color:{self._accent()};")
        return label

    # ------------------------------------------------------------------ #
    # the inventory table
    # ------------------------------------------------------------------ #

    def _sync_filter_combo(self) -> None:
        """Re-option the kind filter with live counts, without disturbing the choice.

        ⚠ Signals blocked across the refill: `clear()` emits `currentIndexChanged`, and
        letting that through would reset the filter to "all" every time the table
        rebuilds — the shape that makes a filter un-keepable.
        """
        rows = viewmod.inventory_rows(self._ruleset, self._char())
        counts = viewmod.inventory_counts(rows)
        self.filter_combo.blockSignals(True)
        self.filter_combo.clear()
        for kind in viewmod.INVENTORY_FILTERS:
            n = counts.get(kind, 0)
            if kind != "all" and not n:
                continue          # an empty filter is noise, not a choice
            self.filter_combo.addItem(viewmod.inventory_filter_label(kind, n), kind)
        index = self.filter_combo.findData(self._filter)
        if index < 0:
            index, self._filter = 0, "all"
        self.filter_combo.setCurrentIndex(index)
        self.filter_combo.blockSignals(False)

    def _filter_changed(self, _index: int) -> None:
        self._filter = self.filter_combo.currentData() or "all"
        self._fill_table()
        self._sync_detail()

    def _search_changed(self, text: str) -> None:
        self._search = (text or "").strip().lower()
        self._fill_table()
        self._sync_detail()

    def _fill_table(self) -> None:
        """Rebuild the rows for the active filter, restoring the selection if its row
        is still shown."""
        ruleset, char = self._ruleset, self._char()
        rows = viewmod.inventory_rows(ruleset, char)
        # ⚠ Sorting OFF across the fill: with it on, Qt re-sorts after every insert,
        # which is quadratic and scrambles the order the items were added in.
        self.table.setSortingEnabled(False)
        self.table.blockSignals(True)
        self.table.clear()
        restore = None
        for row in viewmod.filter_inventory(rows, self._filter):
            if self._search and self._search not in row.name.lower():
                continue
            item = QTreeWidgetItem([
                row.name or "—",
                str(row.quantity) if row.quantity > 1 else "",
                "•" * row.resources_cost,
                " · ".join(viewmod.inventory_row_tags(row)),
                row.detail])
            item.setToolTip(2, _RES_TOOLTIP)
            key = (row.list_name, row.index)
            item.setData(0, Qt.UserRole, key)
            # The linked half rides along so the detail pane can render both editors
            # without re-deriving the merge.
            item.setData(1, Qt.UserRole,
                         (row.linked_list_name, row.linked_index)
                         if row.linked_list_name else None)
            self.table.addTopLevelItem(item)
            if key == self._selected:
                restore = item
        self.table.blockSignals(False)
        self.table.setSortingEnabled(True)
        if restore is not None:
            self.table.setCurrentItem(restore)
        elif self.table.topLevelItemCount():
            self.table.setCurrentItem(self.table.topLevelItem(0))
        else:
            self._selected = None

    def _refresh_selected_row(self) -> None:
        """Re-render just the selected row's cells after an edit, so the table tracks
        the detail pane without a full rebuild (which would steal focus mid-keystroke)."""
        item = self.table.currentItem()
        if item is None or self._selected is None:
            return
        list_name, index = self._selected
        for row in viewmod.inventory_rows(self._ruleset, self._char()):
            if (row.list_name, row.index) == (list_name, index):
                item.setText(0, row.name or "—")
                item.setText(1, str(row.quantity) if row.quantity > 1 else "")
                item.setText(2, "•" * row.resources_cost)
                item.setText(3, " · ".join(viewmod.inventory_row_tags(row)))
                item.setText(4, row.detail)
                return

    def _selection_changed(self) -> None:
        item = self.table.currentItem()
        self._selected = None if item is None else item.data(0, Qt.UserRole)
        self._sync_detail()

    # ------------------------------------------------------------------ #
    # the detail pane
    # ------------------------------------------------------------------ #

    def _sync_detail(self) -> None:
        """Rebuild the right-hand pane for the current selection."""
        self._clear_lay(self._detail_lay)
        if self.tabs.currentIndex() != 0:
            self.detail_title.setText("")
            self._detail_lay.addWidget(self._muted(
                "The price list is reference only — nothing here is owned or tracked."))
            self._detail_lay.addStretch(1)
            return
        item = self.table.currentItem()
        if item is None or self._selected is None:
            self.detail_title.setText("")
            self._detail_lay.addWidget(self._muted(
                "Select an item to edit it, or Buy something."))
            self._detail_lay.addStretch(1)
            return
        list_name, index = self._selected
        self.detail_title.setText(item.text(0))
        self.detail_title.setStyleSheet(
            f"font-weight:700; font-size:14px; color:{self._accent()};")
        tags = item.text(3)
        if tags:
            self._detail_lay.addWidget(self._muted(tags))
        self._row_editor(self._detail_lay, list_name, index)
        # A merged row is one object with TWO stored halves — the artifact and the stat
        # line `grant_gear` stamped for it. ⚠ Without this the stat line is uneditable:
        # there are no per-kind panels, and the merged row is the only place it appears.
        linked = item.data(1, Qt.UserRole)
        if linked:
            self._detail_lay.addWidget(self._heading("Stat line"))
            self._row_editor(self._detail_lay, linked[0], linked[1])
        self._detail_lay.addStretch(1)

    def _row_editor(self, lay, list_name: str, index: int) -> None:
        owner = getattr(self._char(), list_name)
        if not (0 <= index < len(owner)):
            return
        builder = {"weapons": self._weapon_editor, "armor": self._armor_editor,
                   "gear": self._goods_editor, "artifacts": self._artifact_editor}
        builder[list_name](lay, index, owner[index])

    # ---- the per-kind editors ------------------------------------------ #

    def _delete_button(self, list_name: str, index: int) -> QPushButton:
        button = QPushButton("Delete")
        button.setToolTip("Deleting a row IS selling it — core p.145 prints no rate "
                          "for a sale, so nothing is refunded.")
        if list_name == "artifacts":
            button.clicked.connect(
                lambda: (gear_actions.remove_artifact(self._char(), index),
                         self._rebuild()))
        else:
            button.clicked.connect(
                lambda: (gear_actions.remove_row(self._char(), list_name, index),
                         self._rebuild()))
        return button

    def _library_button(self, kind: str, item) -> QPushButton:
        button = QPushButton("Save to library")
        button.setToolTip("Save to my library — it becomes buyable for every character")
        button.clicked.connect(lambda: self._save_to_library(kind, item))
        return button

    def _save_to_library(self, kind: str, item) -> None:
        """Put this row in the user's library so every future character can buy it."""
        try:
            customs.save_gear_row(kind, gear_actions.library_payload(kind, item),
                                  reserved_ids=gear_actions.reserved_ids(self._ruleset))
        except customs.CustomContentError as ex:
            self._notify(str(ex), "warning")
            return
        # ⚠ The armour default is SAID OUT LOUD rather than guessed silently: a
        # character's armour row carries no weight and `ArmorType` requires one.
        extra = " (armour weight defaults to Light)" if kind == "armor" else ""
        self._notify(f"Saved {item.name} to your library{extra}. It will appear in Buy "
                     f"the next time the app loads its rules.", "positive")

    def _stat_grid(self, lay, item, specs, resync) -> None:
        """The stat spin boxes, wrapped at three pairs a row.

        ⚠ Qt has no flex-wrap, and a no-wrap row crushes its later children to slivers
        (the lesson the Advantages merit rows already paid for). Thirteen weapon stats
        on one line are unreadable, so the grid wraps by construction.
        """
        row = None
        for position, (field, label, signed) in enumerate(specs):
            if position % 3 == 0:
                row = QHBoxLayout()
                lay.addLayout(row)
            caption = QLabel(label)
            caption.setStyleSheet(f"color:{MUTED};")
            caption.setMinimumWidth(48)
            row.addWidget(caption)
            spin = QSpinBox()
            # Named after the field it writes, so a test addresses the stat it means
            # rather than a position in the child list — the quantity box is a QSpinBox
            # too, and indexing found that one first.
            spin.setObjectName(f"stat.{field}")
            spin.setRange(-20 if signed else 0, 99)
            spin.setValue(getattr(item, field))
            spin.valueChanged.connect(
                lambda v, f=field: (setattr(item, f, v), resync(), self._changed()))
            row.addWidget(spin)
            if position % 3 == 2:
                row.addStretch(1)
        if row is not None and len(specs) % 3:
            row.addStretch(1)

    def _material_combo(self, item, resync) -> QComboBox:
        """The magical material. "" is mundane; the bonus applies only for the matching
        Exalt (p.341), which `derive.applied_material` decides — not this combo."""
        combo = QComboBox()
        combo.addItem("— none —", "")
        for material in self._ruleset.material_catalog.values():
            combo.addItem(material.name, material.id)
        combo.setCurrentIndex(max(0, combo.findData(item.material or "")))
        combo.currentIndexChanged.connect(
            lambda _i: (setattr(item, "material", combo.currentData() or ""),
                        resync(), self._changed()))
        return combo

    def _name_combo(self, names, current, on_pick) -> _FilterCombo:
        """An editable combo over a catalogue: pick an entry to autofill, or type a name
        the catalogue does not hold. Free text is a rename, never a failed lookup.

        ⚠ Fires only when the text actually CHANGED. `editingFinished` fires on every
        focus loss, and `on_pick` rebuilds the table — so tabbing past an untouched combo
        would drop the player out of the row they are working in, for no edit at all.
        """
        combo = _FilterCombo()
        combo.setEditable(True)
        combo.addItems(names)
        combo.setCurrentText(current or "")
        seen = {"text": current or ""}

        def fire() -> None:
            text = combo.currentText()
            if text == seen["text"]:
                return
            seen["text"] = text
            on_pick(text)

        combo.lineEdit().editingFinished.connect(fire)
        combo.activated.connect(lambda _i: fire())
        return combo

    def _labelled(self, lay, caption: str, widget) -> None:
        row = QHBoxLayout()
        label = QLabel(caption)
        label.setStyleSheet(f"color:{MUTED};")
        label.setMinimumWidth(64)
        row.addWidget(label)
        row.addWidget(widget, 1)
        lay.addLayout(row)

    def _buttons_row(self, lay, kind: str, item, index: int) -> None:
        row = QHBoxLayout()
        row.addWidget(self._library_button(kind, item))
        row.addWidget(self._delete_button(kind, index))
        row.addStretch(1)
        lay.addLayout(row)

    def _weapon_editor(self, lay, index, weapon) -> None:
        ruleset, char = self._ruleset, self._char()
        summary = QLabel("")
        summary.setWordWrap(True)
        summary.setStyleSheet(f"color:{MUTED};")

        def resync() -> None:
            # The EFFECTIVE stats (material folded in) and the wielder's material tag —
            # `view.weapon_stat_line` is the one copy of the format, shared with the
            # shop's pre-pick rows.
            material = derivemod.applied_material(ruleset, char, weapon)
            summary.setText(viewmod.weapon_stat_line(
                derivemod.effective_weapon(ruleset, char, weapon),
                material=material.name if material else ""))

        names = [w.name for w in ruleset.weapon_catalog.values()]
        self._labelled(lay, "Weapon", self._name_combo(
            names, weapon.name,
            lambda text: (gear_actions.set_weapon(ruleset, char, index, text),
                          self._rebuild())))
        lay.addWidget(summary)

        # Stackable gear. Ammunition is the case that put it here — a player holds
        # arrows by the score — but nothing stops a stack of javelins. It is a COUNT
        # and nothing more: no engine reads it, because nothing derives an attack
        # (decision 0008).
        qty = QSpinBox()
        qty.setRange(1, 999)
        qty.setValue(weapon.quantity)
        qty.valueChanged.connect(
            lambda v: (setattr(weapon, "quantity", v), self._changed()))
        self._labelled(lay, "Quantity", qty)

        dtype = QComboBox()
        dtype.addItems(["L", "B"])
        dtype.setCurrentText(weapon.damage_type or "L")
        dtype.currentTextChanged.connect(
            lambda t: (setattr(weapon, "damage_type", t or "L"), resync(),
                       self._changed()))
        self._labelled(lay, "Damage", dtype)
        self._labelled(lay, "Material", self._material_combo(weapon, resync))

        lay.addWidget(self._heading("Stats"))
        self._stat_grid(lay, weapon, _WEAPON_STATS, resync)

        notes = QLineEdit(weapon.notes)
        notes.setPlaceholderText("notes")
        notes.textChanged.connect(
            lambda t: (setattr(weapon, "notes", t), self._changed()))
        self._labelled(lay, "Notes", notes)
        self._buttons_row(lay, "weapons", weapon, index)
        resync()

    def _armor_editor(self, lay, index, armor) -> None:
        ruleset, char = self._ruleset, self._char()
        summary = QLabel("")
        summary.setWordWrap(True)
        summary.setStyleSheet(f"color:{MUTED};")

        def resync() -> None:
            material = derivemod.applied_material(ruleset, char, armor)
            summary.setText(viewmod.armor_stat_line(
                derivemod.effective_armor(ruleset, char, armor),
                material=material.name if material else ""))

        names = [a.name for a in ruleset.armor_catalog.values()]
        self._labelled(lay, "Armour", self._name_combo(
            names, armor.name,
            lambda text: (gear_actions.set_armor(ruleset, char, index, text),
                          self._rebuild())))
        lay.addWidget(summary)
        self._labelled(lay, "Material", self._material_combo(armor, resync))
        lay.addWidget(self._heading("Stats"))
        self._stat_grid(lay, armor, _ARMOR_STATS, resync)
        self._buttons_row(lay, "armor", armor, index)
        resync()

    def _goods_editor(self, lay, index, item) -> None:
        name = QLineEdit(item.name)
        name.setPlaceholderText("item")
        name.textChanged.connect(
            lambda t: (setattr(item, "name", t), self._changed()))
        self._labelled(lay, "Item", name)

        qty = QSpinBox()
        qty.setRange(1, 999)
        qty.setValue(item.quantity)
        qty.valueChanged.connect(
            lambda v: (setattr(item, "quantity", v), self._changed()))
        self._labelled(lay, "Quantity", qty)

        # LABELLED. A bare "•••" beside an item is unreadable — the browser asked what
        # it meant (2026-08-13), and every other dot column on the sheet is a rated
        # trait, which this is not: it is what the thing COST.
        cost = QSpinBox()
        cost.setRange(0, 10)
        cost.setValue(item.resources_cost)
        cost.setToolTip(_RES_TOOLTIP)
        cost.valueChanged.connect(
            lambda v: (setattr(item, "resources_cost", v), self._changed()))
        self._labelled(lay, "Resources", cost)

        note = QLineEdit(item.note)
        note.setPlaceholderText("note")
        note.textChanged.connect(
            lambda t: (setattr(item, "note", t), self._changed()))
        self._labelled(lay, "Note", note)
        self._buttons_row(lay, "gear", item, index)

    def _artifact_editor(self, lay, index, artifact) -> None:
        ruleset, char = self._ruleset, self._char()
        catalog = artifactsmod.purchasable_artifacts(ruleset.artifact_catalog, char)
        description = QLabel("")
        description.setWordWrap(True)
        description.setStyleSheet(f"color:{MUTED};")

        rating = QSpinBox()
        rating.setRange(1, 5)
        rating.setValue(artifact.rating)

        def sync_description() -> None:
            entry = next((a for a in catalog if a.name == artifact.name), None)
            description.setText(entry.description if entry else "")
            description.setVisible(bool(description.text()))

        def on_name(text: str) -> None:
            if gear_actions.set_artifact(ruleset, char, index, text):
                # A catalogue pick may have granted a stat line and changed the budget,
                # so everything goes — but the spin box is pushed first so the rebuild
                # reads the new rating rather than the stale one.
                rating.setValue(artifact.rating)
                self._rebuild()
                return
            sync_description()
            self._changed()

        self._labelled(lay, "Artifact", self._name_combo(
            [a.name for a in catalog], artifact.name, on_name))
        lay.addWidget(description)
        rating.valueChanged.connect(
            lambda v: (setattr(artifact, "rating", v), self._changed()))
        self._labelled(lay, "Rating", rating)

        # How it was acquired. POST-LOCK ONLY: at creation the Background is the only
        # channel there is (core p.342, "to start the game owning"), so offering the
        # choice would be offering an illegal pick. `validate` bars it either way; this
        # stops the player reaching the bar.
        if char.chargen_locked:
            acquired = QComboBox()
            for value, label in ((artifactsmod.ACQUIRED_BACKGROUND, "Background"),
                                 (artifactsmod.ACQUIRED_PURCHASED, "Bought"),
                                 (artifactsmod.ACQUIRED_LEGENDARY, "Merit")):
                acquired.addItem(label, value)
            acquired.setCurrentIndex(max(0, acquired.findData(artifact.acquired)))
            # ⚠ Through the engine, never `setattr`: changing the channel must re-stamp
            # any stat line this artifact granted, or the two drift and the orphan is
            # charged to the wrong budget.
            acquired.currentIndexChanged.connect(
                lambda _i: (gear_actions.set_acquired(char, index,
                                                      acquired.currentData()),
                            self._rebuild()))
            self._labelled(lay, "Acquired", acquired)

        note = QLineEdit(artifact.note)
        note.setPlaceholderText("note")
        note.textChanged.connect(
            lambda t: (setattr(artifact, "note", t), self._changed()))
        self._labelled(lay, "Note", note)
        self._buttons_row(lay, "artifacts", artifact, index)
        sync_description()

    # ------------------------------------------------------------------ #
    # Buy
    # ------------------------------------------------------------------ #

    def _build_shop_dialog(self) -> CatalogueDialog:
        """One shop over every priced catalogue, BUILT but not run.

        ⚠ It replaced four per-panel dialogs, which were four shops; the kind rides in
        the row KEY so one dialog appends to four differently typed lists
        (`gear_actions.buy` reads it back).

        Split from `_open_shop` because `exec()` blocks a headless run, so this is the
        seam the tests drive — the same shape `AdvantagesPage` uses.
        """
        shop = viewmod.shop_rows(self._ruleset, self._char())
        return CatalogueDialog(
            self._pal(), "Buy",
            [(r.key, r.name, r.summary, r.full) for r in shop],
            self._buy,
            subtitle=_SHOP_SUBTITLE,
            group_of={r.key: r.group for r in shop},
            dimmed={r.key for r in shop if r.affordability == "unaffordable"},
            custom_kinds=viewmod.shop_custom_kinds(self._char()),
            parent=self)

    def _open_shop(self) -> None:
        self._build_shop_dialog().exec()

    def _buy(self, key) -> None:
        message = gear_actions.buy(self._ruleset, self._char(), key or "")
        if message:
            self._notify(message, "positive")
        self._rebuild()

    def _build_artifact_dialog(self) -> CatalogueDialog:
        # ⚠ Recomputed per OPEN, never captured. The list depends on character state
        # that changes on ANOTHER tab — taking or dropping the Legendary Artifact Merit
        # — and a captured copy is the stale-closure trap verbatim: a player takes the
        # Merit, comes back, and the artifact she just paid ten bonus points for is not
        # in the list.
        catalog = artifactsmod.purchasable_artifacts(
            self._ruleset.artifact_catalog, self._char())
        rows = [(a.name, a.name, f"{a.rating_notes or ('•' * a.rating)} — "
                 f"{a.description}", a.description) for a in catalog]
        return CatalogueDialog(self._pal(), "Artifacts", rows, self._pick_artifact,
                               custom_label="Custom artifact", parent=self)

    def _open_artifact_catalogue(self) -> None:
        self._build_artifact_dialog().exec()

    def _pick_artifact(self, name) -> None:
        gear_actions.add_artifact(self._ruleset, self._char(), name)
        self._rebuild()

    # ------------------------------------------------------------------ #
    # the services price list
    # ------------------------------------------------------------------ #

    def _fill_prices(self) -> None:
        """The other half of the same tables, and NOT inventory: upkeep, events,
        commissions and rentals.

        ⚠ A character does not carry a month of stabling in her pack, so these are a
        price list she can consult and never own (human's ruling 2026-08-13) — the
        ruling holds at the OFFER too, which is why `view.shop_rows` skips them. It
        gets its own sub-tab rather than a card under the inventory: it is reference
        material, not something owned.
        """
        self._clear_lay(self._prices_lay)
        services = viewmod.service_rows(self._ruleset, self._char())
        if not services:
            return
        self._prices_lay.addWidget(self._muted(
            "Reference only — not owned, and nothing here is tracked. Jade and silver "
            "are the printed equivalents (M&C p.123); the conversion is the "
            "Storyteller's call, so nothing is computed from them."))
        last_category = ""
        for category, name, dots, cash, notes, affordable in services:
            if category != last_category:
                last_category = category
                self._prices_lay.addWidget(self._heading(category))
            row = QHBoxLayout()
            dot_label = QLabel("•" * dots)
            dot_label.setMinimumWidth(56)
            row.addWidget(dot_label)
            name_label = QLabel(name)
            row.addWidget(name_label, 1)
            if cash:
                # ⚠ `GearType.cash` is reference text, never arithmetic. M&C p.122 says
                # outright that the Resources ladder is not linear and converting it is
                # a Storyteller judgement, so this is printed verbatim and nothing
                # computes from it. It is also this panel's whole point: a PRICE list
                # showing no prices is the house bug, and it shipped that way once.
                cash_label = QLabel(cash)
                cash_label.setStyleSheet(f"color:{MUTED};")
                row.addWidget(cash_label)
            if not affordable:
                for widget in (dot_label, name_label):
                    widget.setStyleSheet(f"color:{MUTED};")
            self._prices_lay.addLayout(row)
            if notes:
                self._prices_lay.addWidget(self._muted(notes, italic=True))
        self._prices_lay.addStretch(1)
