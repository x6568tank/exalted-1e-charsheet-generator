"""exalted_builder/qt/gear.py — the Gear tab: everything the character OWNS.

Input: a RuleSet and the shared context's Character. Output: a master-detail surface —
a readout bar, an action toolbar, a splitter holding the inventory table (and the
services price list on its own sub-tab) beside the selected item's editor, and the
artifacts budget line beneath. Mechanism: `reload()` rebuilds the table and re-selects
whatever was selected before; changing the selection rebuilds only the detail pane, and
anything a keystroke touches writes straight to the model and re-syncs its own labels.

⚠ **This tab uses the shape of the Charms tab** (human's ruling). A desktop app puts the
actions in a toolbar, the lists in a table with a header, and the selected item in a
detail pane. Do not copy a NiceGUI page: a Buy button in the content flow, an accordion
"Edit" expander and a stack of cards read as a web page. **A new surface here copies the
layout of `qt/charms.py`. It does not copy `ui/<tab>.py`.**

⚠ Keep the four lists on ONE tab. If the STATS of an artifact daiklave are on one surface
and its BUDGET is on a different surface, the user can enter the same object two times and
pay for it two times (`docs/status/rated-artifacts.md`).

Zero game logic. Every mutation goes through `engine.gear_actions`, every derived list
and every line of text through `ui/view.py`.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QPushButton, QScrollArea, QSpinBox, QSplitter, QTabWidget, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

from exalted_builder import custom_content as customs, rules_db
from exalted_builder.engine import (artifacts as artifactsmod, derive as derivemod,
                                    gear_actions, validate)
from exalted_builder.ui import theme
from exalted_builder.ui import view as viewmod

from .catalogue import CatalogueDialog
from .layout import clear_layout, empty_note
from .editor import _FilterCombo
from .theme import MUTED, accent as accent_light

# The issue codes that this tab can correct. ⚠ Put the artifact findings HERE, with the
# panel that makes them. A report on a surface that does not edit its subject is the house
# bug in the UI. The Advantages tab shows the same findings next to the Artifact
# Background. There is ONE issue list, thus the two surfaces always agree.
_MY_ISSUES = ("artifact", "hearthstone")

_COLUMNS = ("Name", "Qty", "Res", "Kind", "Detail")

# The stat editors for each kind, as `(field, label, signed)`. Use this table. Do not
# write fifteen spin boxes. Thus the two kinds keep the same layout and the same limits.
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
    """The tab widget. `reload()` rebuilds the table for the character in ctx. `notify`
    shows a temporary message. `on_change` calls the shell, thus the shell calculates its
    readout bar and its status strip again."""

    def __init__(self, ruleset, ctx, *, notify=None, on_change=None, parent=None):
        super().__init__(parent)
        self._ruleset = ruleset
        self._ctx = ctx
        self._notify = notify or (lambda text, kind="info": None)
        self._on_change = on_change
        self._filter = "all"
        self._search = ""
        # The selected row, as `(list_name, index)`. ⚠ Keep this key, thus a rebuild can
        # select the row again. But an add or a delete moves the positions. Thus
        # `_rebuild` clears the key. If it kept the key, it would select a different row.
        self._selected: tuple[str, int] | None = None

        self.readout = QLabel("")
        self.readout.setWordWrap(True)
        self.readout.setContentsMargins(8, 4, 8, 4)

        # ---- the action toolbar -------------------------------------- #
        # ⚠ Put the actions HERE, not in the content flow. A Buy button in the middle of
        # the page with a sentence next to it is a web control.
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
        empty_note(self.table,
                   "Nothing owned yet.\n\nUse “Buy…” for anything a book prices, "
                   "“+ Artifact” for a rated one — or buy a blank row and rename it.")

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

        # The budget line goes BELOW the splitter, across both panes. It describes the
        # collection. It does not describe the selected row.
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
        """Empty `lay`, and detach every descendant immediately. ⚠ Call `qt/layout.py`.
        That module holds the two traps in this operation."""
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
        """Apply a change that moved the LISTS. Rebuild the page and call the shell.

        ⚠ Drop the selection first. The selection is a POSITION, and an add or a delete
        gives a new number to every row after it. A key that stays selects a different row.
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

        ⚠ Block the signals across the refill. `clear()` sends `currentIndexChanged`. If
        that signal passes, the filter returns to "all" on each rebuild of the table, and
        the user cannot keep a filter.
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
        # ⚠ Turn sorting OFF across the fill. If sorting is on, Qt sorts again after each
        # insert. That is slow, and it loses the order in which the user added the items.
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
            # Carry the linked half with the row. Thus the detail pane can draw both
            # editors, and it does not calculate the merge again.
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
        """Draw the cells of the selected row again after an edit. Thus the table agrees
        with the detail pane. ⚠ Do not do a full rebuild here. A rebuild takes the focus
        away while the user types."""
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
        # A merged row is ONE object with TWO stored halves: the artifact, and the stat
        # line that `grant_gear` made for it. ⚠ Without this code, the user cannot edit the
        # stat line. There are no panels for each kind, and the merged row is the only
        # place that shows the stat line.
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
        # ⚠ Show the armour default to the user. Do not select it silently. The armour row
        # of a character has no weight, and `ArmorType` needs one.
        extra = " (armour weight defaults to Light)" if kind == "armor" else ""
        # ⚠ Re-merge the custom layer NOW. `reload_custom_layer` must include the gear
        # catalogues. If it does not, the new row appears only after a restart.
        # ⚠ Do not rebuild the page. A save to the LIBRARY does not change the lists of the
        # character, and `_rebuild` drops the selection. A rebuild moves the user out of
        # the row that they edited. The shop reads `view.shop_rows` on each open.
        rules_db.reload_custom_layer(self._ruleset)
        self._notify(f"Saved {item.name} to your library{extra}. It is in Buy now, and "
                     f"on the Custom tab’s Gear list.", "positive")

    def _stat_grid(self, lay, item, specs, resync) -> None:
        """The stat spin boxes, wrapped at three pairs a row.

        ⚠ Qt has no flex-wrap. A row that does not wrap makes its last children very
        narrow. Thirteen weapon stats on one line are unreadable. Thus this grid wraps.
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
            # Give each box the name of the field that it writes. Thus a test addresses
            # the stat by name, not by a position in the child list. ⚠ The quantity box is
            # also a QSpinBox, and an index finds that box first.
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

    def _attune_controls(self, lay, item) -> None:
        """The commitment toggle and its pool, for an item that prints a cost.

        ⚠ Do NOT put these two controls in `_WEAPON_STATS` or `_ARMOR_STATS`. That table
        is `(field, label, signed)`, and it drives spin boxes. A bool and a two-value
        choice are neither. If you widen the triple for these two, a spin box appears on
        the field of a checkbox.

        Show these controls only when `attunement > 0`. ⚠ No code here attunes an item
        automatically. The flag records that the user commits the motes. Thus this control
        stays inside the tracker rules of `engine/play.py`.
        """
        if item.attunement <= 0:
            return
        # ⚠ Merged-pool characters (ghosts, Beacon of Power holders) have one pool to
        # commit into; the choice is hidden rather than defaulted, and `derive` ignores
        # the stored value for them.
        merged = derivemod.essence_pool_is_merged(self._ruleset, self._char())

        pool = QComboBox()
        pool.setObjectName("attunedPool")
        pool.addItem("Personal", "personal")
        pool.addItem("Peripheral", "peripheral")
        pool.setCurrentIndex(max(0, pool.findData(item.attuned_pool)))
        pool.currentIndexChanged.connect(
            lambda _i: (setattr(item, "attuned_pool", pool.currentData()),
                        self._changed()))

        box = QCheckBox(f"Attuned — commit {item.attunement} motes")
        box.setObjectName("attunedBox")
        box.setChecked(item.attuned)
        box.toggled.connect(
            lambda on: (setattr(item, "attuned", on),
                        pool.setVisible(on and not merged), self._changed()))
        pool.setVisible(item.attuned and not merged)

        row = QHBoxLayout()
        row.addWidget(box)
        row.addWidget(pool)
        row.addStretch(1)
        lay.addLayout(row)

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

        ⚠ Send the signal only when the text CHANGED. `editingFinished` occurs on each
        loss of focus, and `on_pick` rebuilds the table. Thus a tab past a combo that the
        user did not edit moves the user out of the row.
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
            # The EFFECTIVE stats, with the material included, and the material tag of the
            # wielder. `view.weapon_stat_line` is the one copy of this format. The rows of
            # the shop use it too.
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

        # Gear that stacks. Ammunition is the usual case, because a character holds many
        # arrows. A stack of javelins is also permitted. ⚠ This value is a COUNT only. No
        # engine module reads it, because the program derives no attack (decision 0008).
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
        self._attune_controls(lay, weapon)

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
        self._attune_controls(lay, armor)
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

        # Put a LABEL on this column. A "•••" next to an item with no label is unclear.
        # Every other dot column on the sheet shows a rated trait. This column does not.
        # It shows the COST of the item.
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
                # A catalogue pick can grant a stat line and change the budget. Thus
                # rebuild all of it. ⚠ Write the spin box value first. The rebuild then
                # reads the new rating, not the old one.
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

        # ⚠ When this artifact has a gear stat line (`Weapon.from_artifact`), the pair is
        # ONE object, and the gear row owns the commitment (human's ruling). Thus the
        # editor points at that row. It does not show a second set of controls. Two
        # editable attunements for one daiklave count the motes two times.
        # `from_artifact` exists to prevent that.
        stat_line = artifactsmod.stat_line_row(
            char, artifactsmod.item_key(artifactsmod.SOURCE_ARTIFACT, artifact.name))
        if stat_line is not None:
            pointer = QLabel("Attunement is on its stat line below — one object, "
                             "one commitment.")
            pointer.setObjectName("attunementPointer")
            pointer.setWordWrap(True)
            pointer.setStyleSheet(f"color:{MUTED};")
            lay.addWidget(pointer)
        else:
            attune = QSpinBox()
            attune.setObjectName("stat.attunement")
            attune.setRange(0, 99)
            attune.setValue(artifact.attunement)
            attune.valueChanged.connect(
                lambda v: (setattr(artifact, "attunement", v), self._changed()))
            self._labelled(lay, "Attune", attune)
            self._attune_controls(lay, artifact)

        # The acquisition channel. Show it AFTER THE LOCK ONLY. At creation, the Background
        # is the only channel (core p.342, "to start the game owning"). Thus a choice here
        # offers an illegal pick. `validate` refuses it in both cases. This control stops
        # the user before the refusal.
        if char.chargen_locked:
            acquired = QComboBox()
            for value, label in ((artifactsmod.ACQUIRED_BACKGROUND, "Background"),
                                 (artifactsmod.ACQUIRED_PURCHASED, "Bought"),
                                 (artifactsmod.ACQUIRED_LEGENDARY, "Merit")):
                acquired.addItem(label, value)
            acquired.setCurrentIndex(max(0, acquired.findData(artifact.acquired)))
            # ⚠ Write this through the engine. Never use `setattr`. A change to the channel
            # must write the stat line that this artifact granted again. If it does not,
            # the two halves disagree, and the budget receives the wrong charge.
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
        """One shop over every priced catalogue. This function BUILDS the dialog and does
        not run it.

        ⚠ There is ONE shop, not one dialog for each panel. The kind is in the row KEY.
        Thus one dialog adds to four lists of different types, and `gear_actions.buy`
        reads the kind back.

        `_open_shop` runs the dialog. `exec()` stops a headless run, thus the tests drive
        this seam. `AdvantagesPage` uses the same shape.
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
        # ⚠ Calculate this list on each OPEN. Never capture it. The list depends on
        # character state that changes on ANOTHER tab, for example the Legendary Artifact
        # Merit. A captured copy becomes stale: the user takes the Merit, returns here, and
        # the artifact that they paid ten bonus points for is not in the list.
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

        ⚠ A character cannot carry a month of stabling. Thus these rows are a price list
        that the user reads and never owns (human's ruling). The rule also applies to the
        OFFER, thus `view.shop_rows` omits them. This panel is a sub-tab, not a card below
        the inventory, because it is reference material.
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
                # ⚠ `GearType.cash` is reference text. Never calculate with it. M&C p.122
                # states that the Resources ladder is not linear, and that a conversion is
                # a decision of the Storyteller. Thus print this text without change, and
                # calculate nothing from it. ⚠ Always print it: a PRICE list that shows no
                # prices is the house bug.
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
