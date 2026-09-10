"""exalted_builder/qt/custom.py — the Custom tab: author your own Charms and spells.

Input: a RuleSet (updated IN PLACE as rows are saved — see `rules_db.reload_custom_layer`)
and the shared context. Output: the settled collection surface — a readout, an action
toolbar, a sub-tab per kind holding a sortable table of the library, and a splitter with
the selected row's authoring form in a detail pane. Mechanism: `reload()` re-merges the
library into the live rule set and rebuilds the tables; selecting a row loads it into the
form; Save writes through `custom_content` and re-merges.

⚠ **A Martial Arts style is not a separate thing to create.** Picking "New Martial Arts
style…" in the category dropdown writes `martial_arts:<slug>` and the picker derives its
style groups from that string, so there is no Styles sub-tab and never should be.

⚠ **This is the ONE collection whose detail pane does not show the selected row only.**
The pane of each other tab shows the row that the user clicked. This pane must also hold
an UNSAVED new row, because the user authors content in the form. `_editing == ""` is that
state, and the `New` action enters it. ⚠ A rebuild must not select a table row and delete
a form that the user has partly written.

⚠ **`on_change` is REQUIRED.** A delete of a custom Charm does not remove that Charm from
a character that owns it. The id stays, and it becomes an `unknown-charm` validation
error. Without the call, the readout bar of the shell is stale.

⚠ **The third column of the webapp is a TOOLBAR ACTION here, not a nested tab.**
`ui/custom.py` puts the library, the form and the JSON side by side. The collection layout
has one detail pane, and JSON import and export is an *action* on the row, not a property
of it. Do not put a second level of tabs in the pane.

This module has no game logic. `view.custom_*` moves data between the form and the
payload. The pydantic models decide validity. `custom_content` reads and writes the
filesystem. `rules_db.reload_custom_layer` merges the library into the live rule set.
"""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QFileDialog, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton,
    QScrollArea, QSpinBox, QSplitter, QTabWidget, QTextEdit, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

from exalted_builder import custom_content, rules_db
from exalted_builder.custom_content import CustomContentError
from exalted_builder.models.rules import CharmType, SpellCircle
from exalted_builder.ui import theme
from exalted_builder.ui import view as viewmod

from .editor import _FavoredPicker, _FilterCombo
from .layout import clear_layout, empty_note
from .theme import CUSTOM, MUTED, accent as accent_light

_KINDS = ("charm", "spell", "ritual", "gear")
_KIND_LABELS = {"charm": "Charms", "spell": "Spells", "ritual": "Rituals",
                "gear": "Gear"}

# The three kinds that are not gear share ONE code path. `view.CUSTOM_KINDS` drives it.
# BOTH shells read that table, thus the two Custom pages always agree. ⚠ GEAR is not in
# the table. Its four catalogues need a subkind. Each `if self._kind == "gear"` branch
# below handles that difference.
_KIND = viewmod.CUSTOM_KINDS
_NAME_HINT = {"charm": "the Charm's printed name", "spell": "the spell's name",
              "ritual": "the ritual's name", "gear": "what it is called"}
# Gear has a Kind column. On the screen, the four catalogues are ONE concept: the items
# that a character owns. Thus they share one list. Do not divide them into four sub-tabs.
_COLUMNS = {"charm": ("", "Name", "Detail"),
            "spell": ("", "Name", "Detail"),
            "ritual": ("", "Name", "Detail"),
            "gear": ("", "Name", "Kind", "Detail")}

# The text for an EMPTY library. ⚠ A heading over a blank area reads as "nothing loaded",
# not as "nothing yet". See `qt/layout.py::empty_note`. On this tab, empty is the NORMAL
# state for most users. Thus this text says what the library is FOR. It does not say how
# to fill it only.
_EMPTY_NOTES = {
    "charm": "Your Charm library is empty.\n\nAnything you write here is yours and "
             "yours alone — it never goes in the rulebook data, and a character who "
             "owns it carries a copy in their save.",
    "spell": "Your spell library is empty.\n\nWrite a spell here and it becomes "
             "learnable by every character you make.",
    "ritual": "Your ritual library is empty.\n\nThe chapter prints five rituals and "
              "says outright that more should be written (p.148). One written here "
              "joins the catalogue in Thaumaturgy, priced by its level like any "
              "other — or invent one for a single character from the picker itself.",
    "gear": "Your gear library is empty.\n\nAuthor a weapon, armour or an artifact "
            "here, or save one off a character's Gear tab — both write the same row.",
}

# ⚠ The user CAN author gear here (human's ruling; `docs/status/custom-content.md`).
# Without this form, the user must give an item to a character to invent one: Buy, then
# "Custom weapon", then a blank row on a sheet, then edit, then save, then delete the row.
#
# ⚠ Keep BOTH entry points (human's ruling). The button on the Gear tab keeps an item that
# the user has already changed. This form designs a new item. They cannot become
# different, because both write through `custom_content.save_gear_row`.
_GEAR_BLURB = (
    "Pick a kind and fill in the stats, or press “Save to my library” on any Gear-tab "
    "row to keep something you tweaked there. Both land in the same library.")

# ⚠ Use None. Do NOT use a large number. The models put no limit on the three multiple
# selections here: prerequisites, extra-requirement traits and open-to tiers.
# `_FavoredPicker` PRINTS its limit in the placeholder, thus 999 shows "(pick 999)".
_NO_CAP = None

# This code cannot count the characters that a delete affects, because the user keeps the
# saves in any directory. Thus this text states what happens. It gives no number.
_DELETE_WARNING = (
    "Any character that already owns it keeps the id: the Charm shows on the sheet as a "
    "missing row (⚠) with an error, and comes back if you re-create it with the same "
    "name. Nothing else is changed.")

# ⚠ This warning is DIFFERENT from the Charm warning, because the result is different. A
# save holds an inline COPY of each gear row (decision 0007: ids for invariant content,
# inline copies for variable content). Thus a delete of a library weapon breaks nothing
# that a character owns. Only the offer in the shop goes away. Do not show the Charm text
# here. It states a larger consequence than the real one.
_GEAR_DELETE_WARNING = (
    "Characters that already own one keep it: a save carries its own copy of every "
    "weapon, armour and item, so nothing on a sheet changes. It only disappears from "
    "Buy.")

_JSON_BLURB = ("The same row as text — copy it out to share, or paste one in and press "
               "Load to fill the form. An array of rows is a bulk import and is saved "
               "straight away.")


class _Collapsible(QWidget):
    """A section with a title that the user can fold. ⚠ Build it from a QPushButton and a
    plain container. Do not use a QGroupBox. `qt/theme.py::qss` names no QGroupBox, and an
    unstyled QGroupBox draws its own border and title on the dark page."""

    def __init__(self, title: str, accent: str, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        self._title = title
        self._button = QPushButton(f"▸  {title}")
        self._button.setStyleSheet(
            f"text-align:left; font-weight:600; color:{accent}; background:transparent;")
        self._button.clicked.connect(self._toggle)
        lay.addWidget(self._button)
        self._body = QWidget()
        self._body_lay = QVBoxLayout(self._body)
        self._body_lay.setContentsMargins(12, 2, 0, 2)
        self._body.setVisible(False)
        lay.addWidget(self._body)

    def _toggle(self) -> None:
        shown = not self._body.isVisible()
        self._body.setVisible(shown)
        self._button.setText(f"{'▾' if shown else '▸'}  {self._title}")

    def body(self) -> QVBoxLayout:
        return self._body_lay


class CustomPage(QWidget):
    """The tab widget. `reload()` merges the library again and rebuilds the tables.
    `notify` shows a temporary message. `on_change` calls the shell, thus the readout bar
    is correct after a delete leaves a character with an unknown Charm id."""

    def __init__(self, ruleset, ctx, *, notify=None, on_change=None,
                 custom_dir: Path | None = None, parent=None):
        super().__init__(parent)
        self._ruleset = ruleset
        self._ctx = ctx
        self._notify = notify or (lambda text, kind="info": None)
        self._on_change = on_change
        self._root = (custom_dir if custom_dir is not None
                      else custom_content.custom_data_dir())
        self._kind = "charm"
        self._form = viewmod.custom_charm_form()
        self._editing = ""          # the id that this form replaces. "" is a new row.
        self._gear_kind = ""        # which gear catalogue `_editing` belongs to

        self.readout = QLabel("")
        self.readout.setWordWrap(True)
        self.readout.setContentsMargins(8, 4, 8, 4)

        # ---- the action toolbar -------------------------------------- #
        bar = QHBoxLayout()
        bar.setContentsMargins(8, 0, 8, 0)
        self.new_btn = QPushButton("New")
        self.new_btn.setObjectName("custom.new")
        self.new_btn.clicked.connect(self._new)
        bar.addWidget(self.new_btn)
        self.delete_btn = QPushButton("Delete…")
        self.delete_btn.setObjectName("custom.delete")
        self.delete_btn.clicked.connect(self._delete)
        bar.addWidget(self.delete_btn)
        self.json_btn = QPushButton("JSON…")
        self.json_btn.setObjectName("custom.json")
        self.json_btn.setToolTip("Copy this row out, or paste one in")
        self.json_btn.clicked.connect(self._open_json)
        bar.addWidget(self.json_btn)
        self.import_btn = QPushButton("Import…")
        self.import_btn.setObjectName("custom.import")
        self.import_btn.setToolTip("Import a .json file of one row or many")
        self.import_btn.clicked.connect(self._open_import)
        bar.addWidget(self.import_btn)
        bar.addStretch(1)
        self.path_label = QLabel("")
        self.path_label.setStyleSheet(f"color:{MUTED};")
        bar.addWidget(self.path_label)

        # ---- a table per kind ---------------------------------------- #
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self._tables: dict[str, QTreeWidget] = {}
        for kind in _KINDS:
            columns = _COLUMNS[kind]
            table = QTreeWidget()
            table.setObjectName(f"custom.library.{kind}")
            table.setColumnCount(len(columns))
            table.setHeaderLabels(list(columns))
            table.setRootIsDecorated(False)
            table.setAlternatingRowColors(True)
            table.setSortingEnabled(True)
            table.sortByColumn(-1, Qt.AscendingOrder)
            table.header().setSortIndicatorShown(False)
            table.setSelectionMode(QAbstractItemView.SingleSelection)
            table.header().setStretchLastSection(False)
            # ⚠ Give the free width to NAME, and set a maximum on DETAIL. With Detail on
            # ResizeToContents, Detail takes its content width first and leaves Name
            # approximately 75px. Each row then reads "Singing E…" or "Wound Dr…", and the
            # user identifies a row by that column. Detail is secondary, because the pane
            # repeats it. Keep Detail draggable.
            for column in range(len(columns)):
                table.header().setSectionResizeMode(
                    column,
                    QHeaderView.Stretch if column == 1
                    else QHeaderView.Interactive if column == len(columns) - 1
                    else QHeaderView.ResizeToContents)
            table.header().resizeSection(len(columns) - 1, 170)
            table.itemSelectionChanged.connect(self._selection_changed)
            empty_note(table, _EMPTY_NOTES[kind])
            self._tables[kind] = table
            self.tabs.addTab(table, _KIND_LABELS[kind])
        self.tabs.currentChanged.connect(self._kind_changed)

        # ---- the detail pane (the authoring form) --------------------- #
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
        split.setSizes([460, 720])

        # The library problems go BELOW the splitter, across both panes. They describe the
        # full library. They do not describe the selected row.
        self.problems = QLabel("")
        self.problems.setWordWrap(True)
        self.problems.setContentsMargins(8, 2, 8, 4)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.readout)
        outer.addLayout(bar)
        outer.addWidget(split, 1)
        outer.addWidget(self.problems)
        # ⚠ Build the FORM only. Do NOT call `reload()` here. The other pages call it in
        # their constructors. The refresh of this tab reads the FILESYSTEM, and the shell
        # builds all nine pages at start. Thus a call here makes each new MainWindow scan
        # the homebrew library of the user, in every Qt test and for every window. The
        # shell calls `reload()` when it shows the tab. The library can change before that
        # moment only.
        self._sync_detail()

    # ------------------------------------------------------------------ #
    # plumbing
    # ------------------------------------------------------------------ #

    def _accent(self) -> str:
        return accent_light(theme.palette(None))

    def _reserved(self) -> set[str]:
        """The ids from the BOOKS. Thus homebrew can never hide printed content.
        ⚠ Calculate this set on each call. The custom part of `ruleset.charms` changes."""
        if self._kind == "gear":
            # ⚠ A gear row has no `custom` FIELD. The loader TAGS it, because the models
            # are frozen and the book data uses them too. A read of `.custom` here raises.
            catalog = getattr(self._ruleset,
                              viewmod.CUSTOM_GEAR_KINDS[self._gear_kind][0])
            return {i for i, row in catalog.items() if "custom" not in row.tags}
        pool = getattr(self._ruleset, _KIND[self._kind].pool)
        return {i for i, row in pool.items() if not row.custom}

    def _library_rows(self) -> list:
        if self._kind == "gear":
            return viewmod.build_custom_gear_library(
                self._ruleset,
                {kind: custom_content.library_gear(kind, self._root)
                 for kind in viewmod.CUSTOM_GEAR_KINDS})
        return [r for r in viewmod.build_custom_library(
            self._ruleset,
            custom_content.library_charms(self._root),
            custom_content.library_spells(self._root),
            custom_content.library_rituals(self._root)) if r.kind == self._kind]

    def reload(self) -> None:
        """Merge the library into the live rule set again, then rebuild everything that
        reads it. ⚠ SHOW a problem. Do not raise it. The loader has a non-fatal contract
        for custom data: an error in homebrew must not stop the app."""
        rules_db.reload_custom_layer(self._ruleset, self._root)
        self._fill_tables()
        self._sync_readout()
        self._sync_actions()
        self._sync_detail()

    def _muted(self, text: str, *, italic: bool = False) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet(f"color:{MUTED};"
                            + (" font-style:italic;" if italic else ""))
        return label

    def _sync_readout(self) -> None:
        gear = sum(len(custom_content.library_gear(kind, self._root))
                   for kind in viewmod.CUSTOM_GEAR_KINDS)
        bits = [f"{len(_KIND['charm'].library(self._root))} Charm(s)",
                f"{len(_KIND['spell'].library(self._root))} spell(s)",
                f"{len(_KIND['ritual'].library(self._root))} ritual(s)",
                f"{gear} gear row(s)"]
        self.readout.setText("Your library — " + " · ".join(bits))
        self.readout.setStyleSheet(f"color:{self._accent()};")
        self.path_label.setText(f"Library: {self._root}")
        problems = list(self._ruleset.custom_problems)
        if problems:
            self.problems.setText("LIBRARY PROBLEMS\n"
                                  + "\n".join(f"• {p}" for p in problems))
            self.problems.setStyleSheet("color:#b91c1c;")
        else:
            self.problems.setText("")

    # ------------------------------------------------------------------ #
    # the library tables
    # ------------------------------------------------------------------ #

    def _fill_tables(self) -> None:
        """Rebuild the table for the active kind, restoring the selection.

        ⚠ Fill the table of the ACTIVE kind only. A fill of the inactive table changes
        `self._editing` through `_selection_changed`, which reads the table that is on top.
        That deletes a form that the user has partly written on the other tab.
        """
        kind = self._kind
        table = self._tables[kind]
        table.setSortingEnabled(False)
        table.blockSignals(True)
        table.clear()
        restore = None
        columns = _COLUMNS[kind]
        for row in self._library_rows():
            mark = "⚠" if not row.valid else "✎"
            cells = ([mark, row.name, viewmod.CUSTOM_GEAR_KINDS[row.subkind][1],
                      row.detail] if kind == "gear"
                     else [mark, row.name, row.detail])
            item = QTreeWidgetItem(cells)
            item.setData(0, Qt.UserRole, row.id)
            # ⚠ Store the gear KIND on the item. `delete_gear` needs it, and you cannot
            # calculate it from the id. The four files share one id namespace.
            item.setData(1, Qt.UserRole, row.subkind)
            item.setToolTip(0, row.problem or "Custom content")
            item.setForeground(0, QBrush(QColor("#b91c1c" if not row.valid else CUSTOM)))
            if not row.valid:
                for column in range(len(columns)):
                    item.setToolTip(column, row.problem or "Rejected by the loader")
            table.addTopLevelItem(item)
            if row.id and row.id == self._editing:
                restore = item
        table.setSortingEnabled(True)
        table.sortByColumn(-1, Qt.AscendingOrder)
        table.header().setSortIndicatorShown(False)
        # ⚠ Select a row ONLY when it matches the old selection. Never select row 0 as a
        # fallback. Each other collection selects its first row when the old selection is
        # absent. Here that writes over an unsaved new row at each rebuild of the table.
        table.setCurrentItem(restore)
        table.blockSignals(False)

    def show_kind(self, kind: str) -> None:
        """Select the sub-tab for `kind` ("charm" / "spell" / "ritual" / "gear").

        ⚠ The seam for anything that means "the Gear tab" rather than "tab 2".
        `_KINDS` is display order and has already changed once — every caller that
        addressed a sub-tab by POSITION pointed at the wrong kind the moment Rituals
        went in between, which is the address-by-name lesson in its own file."""
        self.tabs.setCurrentIndex(_KINDS.index(kind))

    def _kind_changed(self, index: int) -> None:
        self._kind = _KINDS[index]
        # ⚠ Call this before `_new()`, and call it here, not in `reload()` only. The set of
        # actions depends on the KIND, and a change of sub-tab changes the kind. Without
        # this call, New and Import stay disabled after the user opens the Gear sub-tab and
        # returns.
        self._sync_actions()
        self._new()

    def _selection_changed(self) -> None:
        table = self._tables[self._kind]
        item = table.currentItem()
        if item is None:
            return
        row_id = item.data(0, Qt.UserRole)
        if row_id == self._editing:
            return
        self._gear_kind = item.data(1, Qt.UserRole) or ""
        self._edit(row_id)

    def _edit(self, row_id: str) -> None:
        """Load one library row into the form, straight off the DISK.

        Gear has no form. This method loads the raw row, thus the pane and the JSON dialog
        can show it, and `_save` refuses it.

        ⚠ Do not read `ruleset.charms`. The rule set does not hold a row that the loader
        REJECTED, and the user must open that row to correct it.
        """
        if self._kind == "gear":
            raw = next((r for r in custom_content.library_gear(self._gear_kind,
                                                               self._root)
                        if r.get("id") == row_id), {})
            self._set_form(viewmod.custom_gear_form(self._gear_kind, raw),
                           editing=row_id)
            return
        raw = next((r for r in _KIND[self._kind].library(self._root)
                    if r.get("id") == row_id), {})
        self._set_form(_KIND[self._kind].form(raw), editing=row_id)

    def _set_form(self, form: dict, editing: str = "") -> None:
        self._form, self._editing = form, editing
        self._fill_tables()
        self._sync_detail()

    def _new(self) -> None:
        """A blank row of the current kind.

        ⚠ Gear needs a KIND before it can have a form. The four catalogues are four models
        with four sets of fields, and there is no common blank row. `_gear_kind` holds the
        kind, and the pane asks the user for it when that value is empty."""
        if self._kind == "gear":
            self._gear_kind = self._gear_kind or "weapons"
            self._set_form(viewmod.custom_gear_form(self._gear_kind))
            return
        self._gear_kind = ""
        self._set_form(_KIND[self._kind].form())

    def _sync_actions(self) -> None:
        """Which toolbar actions this kind has.

        ⚠ Keep Import disabled for gear. `parse_rows` returns plain rows, and a gear row
        does not name WHICH of the four catalogues holds it. `New` stays enabled, because
        its Kind picker supplies that name. Every other action is enabled for every kind.
        """
        importable = self._kind != "gear"
        self.new_btn.setEnabled(True)
        self.new_btn.setToolTip("Author a new row")
        self.import_btn.setEnabled(importable)
        self.import_btn.setToolTip(
            "Import a .json file of one row or many" if importable
            else "A pasted gear row does not name which catalogue it belongs to — "
                 "author it with New instead")

    # ------------------------------------------------------------------ #
    # save / delete
    # ------------------------------------------------------------------ #

    def _payload(self) -> dict:
        if self._kind == "gear":
            return viewmod.custom_gear_payload(self._gear_kind, self._form)
        return _KIND[self._kind].payload(self._form)

    def _save(self) -> None:
        if self._kind == "gear":
            self._save_gear()
            return
        form = self._form
        # For a new row, the id follows the NAME. Thus a rename before the first save
        # leaves no old id. ⚠ After the save, the id is frozen. Characters refer to it,
        # thus an edit must never change it.
        if not self._editing:
            form["id"] = custom_content.make_id(form.get("name", ""))
        try:
            saved = _KIND[self._kind].save(self._payload(), custom_dir=self._root,
                          reserved_ids=self._reserved())
        except CustomContentError as exc:
            self._notify(str(exc), "warning")
            return
        rules_db.reload_custom_layer(self._ruleset, self._root)
        # A save does not clear the form. The row is on the disk and in the rule set. The
        # form stays on that row, thus the user can save it, examine the tree and edit it.
        self._set_form(self._form, editing=saved.id)
        self._sync_readout()
        if saved.id not in getattr(self._ruleset, _KIND[self._kind].pool):
            self._notify(f"Saved {saved.name}, but it did not load — see the problems "
                         f"below the list", "warning")
        else:
            self._notify(f"Saved {saved.name}", "info")
        self._ping()

    def _save_gear(self) -> None:
        """Write one library gear row. This method agrees with `_save`, but it calls
        `save_gear_row`. That function takes a plain dict and a KIND, because the four
        catalogues are four models, and `custom_content` holds no game logic."""
        if not self._editing:
            self._form["id"] = custom_content.make_id(self._form.get("name", ""))
        payload = self._payload()
        try:
            custom_content.save_gear_row(self._gear_kind, payload,
                                         custom_dir=self._root,
                                         reserved_ids=self._reserved())
        except CustomContentError as exc:
            self._notify(str(exc), "warning")
            return
        rules_db.reload_custom_layer(self._ruleset, self._root)
        self._set_form(self._form, editing=payload["id"])
        self._sync_readout()
        catalog = getattr(self._ruleset,
                          viewmod.CUSTOM_GEAR_KINDS[self._gear_kind][0])
        if payload["id"] not in catalog:
            self._notify(f"Saved {payload['name']}, but it did not load — see the "
                         f"problems below the list", "warning")
        else:
            self._notify(f"Saved {payload['name']} — it is in Buy now.", "info")
        self._ping()

    def _ping(self) -> None:
        if self._on_change is not None:
            self._on_change()

    def _delete(self) -> None:
        if not self._editing:
            self._notify("Nothing to delete — this row has not been saved yet.", "info")
            return
        name = self._form.get("name") or self._editing
        warning = (_GEAR_DELETE_WARNING if self._kind == "gear" else _DELETE_WARNING)
        answer = QMessageBox.question(
            self, f"Delete {name}?",
            f"{warning}\n\nDelete it?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        if self._kind == "gear":
            gone = custom_content.delete_gear(self._gear_kind, self._editing,
                                              custom_dir=self._root)
        else:
            gone = _KIND[self._kind].delete(self._editing, custom_dir=self._root)
        self._new()
        self.reload()
        self._notify(f"Deleted {name}" if gone else f"{name} was not there", "info")
        # ⚠ A delete does NOT change the character. The id stays on the sheet and becomes
        # an `unknown-charm` error. The readout bar of the shell reports that error.
        self._ping()

    # ------------------------------------------------------------------ #
    # JSON in / out
    # ------------------------------------------------------------------ #

    def _build_json_dialog(self) -> QDialog:
        """The JSON pane, as a dialog. This function BUILDS it and does not run it.
        `exec()` stops a headless run, thus the tests drive this seam. `GearPage` uses the
        same shape."""
        dialog = QDialog(self)
        dialog.setWindowTitle("JSON")
        dialog.setMinimumSize(560, 520)
        lay = QVBoxLayout(dialog)
        lay.addWidget(self._muted(_JSON_BLURB))
        payload = self._payload()
        if not self._editing:
            payload["id"] = (custom_content.make_id(self._form.get("name", ""))
                             or "(from the name)")
        out = QTextEdit()
        out.setObjectName("custom.json.out")
        out.setReadOnly(True)
        out.setPlainText(json.dumps(payload, indent=2))
        lay.addWidget(out, 1)
        paste = QPlainTextEdit()
        paste.setObjectName("custom.json.in")
        paste.setPlaceholderText("Paste a row, or an array of them…")
        lay.addWidget(paste, 1)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        close = QPushButton("Close")
        close.clicked.connect(dialog.reject)
        buttons.addWidget(close)
        load = QPushButton("Load")
        load.setObjectName("custom.json.load")
        load.clicked.connect(lambda: (self._paste(paste.toPlainText()), dialog.accept()))
        # ⚠ Make this pane read-only for gear. Copy-out operates for gear. Load does not.
        # `_paste` writes through the Charm and spell savers, and a pasted gear row does
        # not name which of the four catalogues holds it. The Kind picker of the form
        # supplies that name.
        if self._kind == "gear":
            paste.setEnabled(False)
            paste.setPlaceholderText("Gear rows are copy-out only — use New to author "
                                     "one, so its kind is known.")
            load.setEnabled(False)
        buttons.addWidget(load)
        lay.addLayout(buttons)
        return dialog

    def _open_json(self) -> None:
        self._build_json_dialog().exec()

    def _paste(self, text: str) -> None:
        try:
            rows = custom_content.parse_rows(text)
        except CustomContentError as exc:
            self._notify(str(exc), "warning")
            return
        if len(rows) == 1:
            # One pasted row fills the form and does NOT save it. Thus the user can examine
            # the row and change it first.
            self._load_row(rows[0])
            self._notify("Loaded into the form — press Save to keep it", "info")
        else:
            self._apply_rows(rows, label="Paste")

    def _load_row(self, row: dict) -> None:
        rid = custom_content.normalize_id(str(row.get("id", "")))
        self._set_form(_KIND[self._kind].form(row), editing=rid)

    def _apply_rows(self, rows: list[dict], *, label: str) -> None:
        """Save every row. One row also loads into the form. Thus a paste of one Charm is
        an edit, and the user sees it. More than one row is a bulk import, and this method
        reports a count."""
        saved, failed = 0, []
        saver = _KIND[self._kind].save
        for row in rows:
            try:
                saver(row, custom_dir=self._root, reserved_ids=self._reserved())
                saved += 1
            except CustomContentError as exc:
                failed.append(f"{row.get('name') or row.get('id') or '?'}: {exc}")
        self.reload()
        if len(rows) == 1 and saved:
            self._load_row(rows[0])
        for message in failed[:3]:
            self._notify(message, "warning")
        if saved:
            self._notify(f"{label}: imported {saved} row(s)", "info")
        self._ping()

    def _open_import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import homebrew", str(self._root),
            "JSON files (*.json);;All files (*)")
        if not path:
            return
        try:
            text = Path(path).read_text(encoding="utf-8")
        except OSError as exc:
            self._notify(f"Could not read that file: {exc}", "warning")
            return
        try:
            rows = custom_content.parse_rows(text)
        except CustomContentError as exc:
            self._notify(str(exc), "warning")
            return
        self._apply_rows(rows, label=Path(path).name)

    # ------------------------------------------------------------------ #
    # the form
    # ------------------------------------------------------------------ #

    def _bind(self, key: str):
        """Write one plain field. ⚠ Do NOT rebuild here. A rebuild during a keystroke
        deletes the widget that the user types into, and the cursor is lost."""
        def _set(value) -> None:
            self._form[key] = value
        return _set

    def _rebuild(self) -> None:
        """Apply a STRUCTURAL change. The set of controls has changed, for example a new
        style-name box, a new extra-requirement row, or a change to the axis of a row."""
        self._sync_detail()

    def _labelled(self, lay, caption: str, widget, *, width: int = 96) -> None:
        row = QHBoxLayout()
        label = QLabel(caption)
        label.setStyleSheet(f"color:{MUTED};")
        label.setMinimumWidth(width)
        # ⚠ Align to the TOP. Do not use the vertical centre, which is the default of Qt.
        # The Description box is more than 90px high, and a centred caption moves to the
        # middle of it. The caption is then far from its field, and it can be outside the
        # viewport when the row crosses the edge.
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        row.addWidget(label)
        row.addWidget(widget, 1)
        lay.addLayout(row)

    def _line(self, key: str, placeholder: str = "") -> QLineEdit:
        widget = QLineEdit(str(self._form.get(key) or ""))
        widget.setObjectName(f"custom.{key}")
        widget.setPlaceholderText(placeholder)
        widget.textChanged.connect(self._bind(key))
        return widget

    def _spin(self, key: str, low: int, high: int) -> QSpinBox:
        widget = QSpinBox()
        widget.setObjectName(f"custom.{key}")
        widget.setRange(low, high)
        widget.setValue(int(self._form.get(key) or 0))
        widget.valueChanged.connect(self._bind(key))
        return widget

    def _check(self, key: str, caption: str, tip: str = "") -> QCheckBox:
        widget = QCheckBox(caption)
        widget.setObjectName(f"custom.{key}")
        widget.setChecked(bool(self._form.get(key)))
        if tip:
            widget.setToolTip(tip)
        widget.toggled.connect(self._bind(key))
        return widget

    def _combo(self, key: str, options: dict, *, on_pick=None,
               editable: bool = False) -> QComboBox:
        """A dropdown over `options` (stored value -> label).

        ⚠ Index the value out of `options`. NEVER read it back from the widget. Qt returns
        item data as a QVariant, and an Enum with a str value returns as a plain `str`. The
        write then succeeds, and a later operation fails.
        """
        widget = _FilterCombo() if editable else QComboBox()
        widget.setObjectName(f"custom.{key}")
        keys = list(options)
        for value, label in options.items():
            widget.addItem(label, value)
        current = str(self._form.get(key) or "")
        widget.setCurrentIndex(max(0, keys.index(current) if current in keys else 0))
        set_value = self._bind(key)

        def picked(index: int) -> None:
            if 0 <= index < len(keys):
                set_value(keys[index])
            if on_pick is not None:
                on_pick()
        widget.currentIndexChanged.connect(picked)
        return widget

    def _picker(self, key: str, options: dict) -> _FavoredPicker:
        return _FavoredPicker(options, list(self._form.get(key) or []), _NO_CAP,
                              self._accent(), self._bind(key))

    def _heading(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(f"font-weight:600; color:{self._accent()};")
        return label

    def _sync_detail(self) -> None:
        """Rebuild the authoring form for the current row."""
        # ⚠ Use `clear_layout`. Never write a teardown loop. `item.widget()` is None for a
        # nested QLayout, and this form holds nested rows only.
        clear_layout(self._detail_lay)
        kind_label = _KIND_LABELS[self._kind][:-1]
        self.detail_title.setText(f"New {kind_label.lower()}" if not self._editing
                                  else f"Editing {self._editing}")
        self.detail_title.setStyleSheet(
            f"font-weight:700; font-size:14px; color:{self._accent()};")

        lay = self._detail_lay
        if self._kind == "gear":
            self._gear_detail(lay)
            return
        self._labelled(lay, "Name", self._line("name", _NAME_HINT[self._kind]))
        {"charm": self._charm_fields, "spell": self._spell_fields,
         "ritual": self._ritual_fields}[self._kind](lay)

        description = QTextEdit(str(self._form.get("description") or ""))
        description.setObjectName("custom.description")
        description.setMinimumHeight(90)
        # ⚠ Set an inline stylesheet. An ancestor stylesheet beats a palette that you set
        # on the widget. Without this, a QTextEdit in a themed page paints the card shade.
        description.setStyleSheet("background:#52525c; color:#e6e4e0; border:none;"
                                  " border-radius:4px;")
        # ⚠ The `textChanged` signal of a QTextEdit sends NO argument. The signal of a
        # QLineEdit sends one. Thus read the text from the widget.
        description.textChanged.connect(
            lambda: self._form.__setitem__("description", description.toPlainText()))
        self._labelled(lay, "Description", description)

        source = QHBoxLayout()
        source.addWidget(self._line("book", "source book"), 1)
        page = QSpinBox()
        page.setObjectName("custom.page")
        page.setRange(0, 9999)
        page.setSpecialValueText("—")
        page.setValue(int(self._form.get("page") or 0))
        page.valueChanged.connect(lambda v: self._form.__setitem__("page", v or None))
        source.addWidget(page)
        self._labelled(lay, "Source", _wrap(source))

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        save = QPushButton("Save")
        save.setObjectName("custom.save")
        save.clicked.connect(self._save)
        buttons.addWidget(save)
        lay.addLayout(buttons)
        lay.addStretch(1)

    def _gear_detail(self, lay) -> None:
        """The gear authoring form, built from `view.CUSTOM_GEAR_FIELDS`.

        ⚠ Use a flat DICT, and validate it on save. Do not use `setattr` on a model, as the
        editors of the Gear tab do. `WeaponType` and the other gear models are FROZEN, and
        the book data uses them. Thus there is no instance to change. This form follows the
        Charm form of this tab.
        """
        kind_row = QHBoxLayout()
        caption = QLabel("Kind")
        caption.setStyleSheet(f"color:{MUTED};")
        caption.setMinimumWidth(96)
        kind_row.addWidget(caption)
        picker = QComboBox()
        picker.setObjectName("custom.gear_kind")
        keys = list(viewmod.CUSTOM_GEAR_KINDS)
        for key, (_attribute, label) in viewmod.CUSTOM_GEAR_KINDS.items():
            picker.addItem(label, key)
        picker.setCurrentIndex(max(0, keys.index(self._gear_kind)
                                   if self._gear_kind in keys else 0))
        # ⚠ Freeze the kind after the save. The category of a Charm is not frozen, but a
        # change to the kind changes the MODEL, and the row is already in one of the four
        # files under one id.
        picker.setEnabled(not self._editing)
        picker.setToolTip("Which catalogue it goes in. Fixed once saved — delete and "
                          "re-make it to change kind."
                          if self._editing else "Which catalogue it goes in")
        picker.currentIndexChanged.connect(
            lambda i: self._switch_gear_kind(keys[i]) if 0 <= i < len(keys) else None)
        kind_row.addWidget(picker, 1)
        lay.addLayout(kind_row)

        self.detail_title.setText(
            f"New {viewmod.CUSTOM_GEAR_KINDS[self._gear_kind][1].lower()}"
            if not self._editing else f"Editing {self._editing}")
        self.detail_title.setStyleSheet(
            f"font-weight:700; font-size:14px; color:{self._accent()};")

        self._labelled(lay, "Name", self._line("name", "what it is called"))
        for spec in viewmod.CUSTOM_GEAR_FIELDS[self._gear_kind]:
            widget = self._gear_control(spec)
            if spec.tip:
                widget.setToolTip(spec.tip)
            self._labelled(lay, spec.label, widget)

        if self._gear_kind == "gear":
            source = QHBoxLayout()
            source.addWidget(self._line("book", "source book"), 1)
            page = QSpinBox()
            page.setObjectName("custom.page")
            page.setRange(0, 9999)
            page.setSpecialValueText("—")
            page.setValue(int(self._form.get("page") or 0))
            page.valueChanged.connect(lambda v: self._form.__setitem__("page", v or None))
            source.addWidget(page)
            self._labelled(lay, "Source", _wrap(source))

        row = next((r for r in self._library_rows() if r.id == self._editing), None)
        if row is not None and not row.valid:
            problem = QLabel(row.problem or "The loader rejected this row.")
            problem.setWordWrap(True)
            problem.setStyleSheet("color:#b91c1c;")
            lay.addWidget(problem)
        lay.addWidget(self._muted(_GEAR_BLURB, italic=True))

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        save = QPushButton("Save")
        save.setObjectName("custom.save")
        save.clicked.connect(self._save)
        buttons.addWidget(save)
        lay.addLayout(buttons)
        lay.addStretch(1)

    def _switch_gear_kind(self, kind: str) -> None:
        """Change the catalogue of a NEW row. This method starts an empty form. The four
        models have four sets of fields. Thus values that move across keep keys that the
        new model refuses."""
        self._gear_kind = kind
        self._set_form(viewmod.custom_gear_form(kind))

    def _gear_control(self, spec):
        """One control for a `view.GearField` spec."""
        if spec.kind == "choice":
            return self._combo(spec.key, dict(spec.options))
        if spec.kind == "longtext":
            box = QTextEdit(str(self._form.get(spec.key) or ""))
            box.setObjectName(f"custom.{spec.key}")
            box.setMinimumHeight(70)
            # ⚠ Set the stylesheet inline. An ancestor stylesheet beats a palette that you
            # set on the widget, and a QTextEdit then paints the card shade.
            box.setStyleSheet("background:#52525c; color:#e6e4e0; border:none;"
                              " border-radius:4px;")
            box.textChanged.connect(
                lambda: self._form.__setitem__(spec.key, box.toPlainText()))
            return box
        if spec.kind == "text":
            return self._line(spec.key)
        # ⚠ `signed` exists for `mobility_penalty`. That field is stored NEGATIVE
        # (`docs/status/gear-and-inventory.md`). A box with a floor of 0 prevents the entry
        # of a penalty, and a consumer that reads the value as a magnitude ADDS dice.
        spin = self._spin(spec.key, -20 if spec.kind == "signed" else 0, 99)
        spin.setMaximumWidth(90)
        # Put the box at the left, with the free space after it. `_labelled` stretches its
        # widget, and a one-digit soak box of 540px reads as an incomplete form.
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(spin)
        row.addStretch(1)
        return _wrap(row)

    def _spell_fields(self, lay) -> None:
        self._labelled(lay, "Circle",
                       self._combo("circle", {c.value: c.value for c in SpellCircle}))
        cost = QHBoxLayout()
        cost.addWidget(QLabel("Motes"))
        cost.addWidget(self._spin("motes", 0, 999))
        cost.addWidget(QLabel("WP"))
        cost.addWidget(self._spin("willpower", 0, 99))
        cost.addStretch(1)
        self._labelled(lay, "Cost", _wrap(cost))
        self._labelled(lay, "Cost text",
                       self._line("cost_raw", "variable costs, e.g. '1m per die'"))

    def _ritual_fields(self, lay) -> None:
        """⚠ Cost, Roll and Resources are free TEXT. They are not numbers. The source gives
        a ritual no stat block. The heading is the name with its dot rating, and the rest
        is prose. Thus a printed cost reads "1 mote or one Willpower" (p.148-150)."""
        level = self._spin("level", 1, 5)
        level.setToolTip("A thaumaturge needs Occult equal to the ritual's level "
                         "(p.148); the level is also what it costs to buy.")
        # ⚠ Put this box in a row with a stretch. Do not give it to `_labelled` alone. A
        # full-width QSpinBox puts its arrows at the far edge of the pane, where they read
        # as cut. The Motes/WP row of the spell form uses this shape.
        row = QHBoxLayout()
        row.addWidget(level)
        row.addStretch(1)
        self._labelled(lay, "Level", _wrap(row))
        self._labelled(lay, "Cost", self._line("cost", "e.g. 1 mote or one Willpower"))
        self._labelled(lay, "Roll", self._line("roll", "many rituals print none"))
        self._labelled(lay, "Resources",
                       self._line("resources", "components, e.g. Resources 2"))

    def _charm_fields(self, lay) -> None:
        ruleset = self._ruleset
        self._labelled(lay, "Category",
                       self._combo("category", viewmod.custom_category_options(ruleset),
                                   on_pick=self._rebuild, editable=True))
        if self._form.get("category") == viewmod.NEW_STYLE:
            style = self._line("style_name", "e.g. Falling Blossom")
            style.setToolTip("Creates martial_arts:<name> — the picker groups it as its "
                             "own style")
            self._labelled(lay, "Style name", style)
        self._labelled(lay, "Type",
                       self._combo("type", {e.value: e.value for e in CharmType}))
        self._labelled(lay, "Splat",
                       self._combo("exalt_type", {e: e for e in sorted(ruleset.exalts)}))

        mins = QHBoxLayout()
        mins.addWidget(QLabel("Min ability"))
        mins.addWidget(self._spin("min_ability", 0, 5))
        mins.addWidget(QLabel("Min essence"))
        mins.addWidget(self._spin("min_essence", 1, 10))
        mins.addStretch(1)
        self._labelled(lay, "Minimums", _wrap(mins))

        cost = QHBoxLayout()
        for caption, key, high in (("Motes", "motes", 999), ("WP", "willpower", 99),
                                   ("Health", "health", 99)):
            cost.addWidget(QLabel(caption))
            cost.addWidget(self._spin(key, 0, high))
        cost.addStretch(1)
        self._labelled(lay, "Cost", _wrap(cost))
        health_type = self._combo("health_type", viewmod.HEALTH_TYPE_OPTIONS)
        health_type.setToolTip("Which kind of health level the Charm spends. Every "
                               "printed Charm just says 'health level', so 'unspecified' "
                               "is the norm.")
        self._labelled(lay, "HL type", health_type)
        self._labelled(lay, "", self._check("committed", "Motes stay committed"))
        duration = self._combo("duration",
                               {d: d for d in viewmod.CHARM_DURATIONS}, editable=True)
        duration.setEditable(True)
        duration.setCurrentText(str(self._form.get("duration") or "Instant"))
        # Free text is legal here — the one field the book leaves open-ended.
        duration.lineEdit().editingFinished.connect(
            lambda: self._form.__setitem__("duration", duration.currentText()))
        self._labelled(lay, "Duration", duration)
        self._labelled(lay, "Cost text",
                       self._line("cost_raw", "variable costs, e.g. '1m per die'"))

        self._extra_requirements(lay)
        self._breadth_requirements(lay)

        # Offer every Charm in the rule set, and include the homebrew Charms. Thus a custom
        # tree can start at a printed Charm or at a custom one. ⚠ Remove the virtual rows.
        # A character can never learn one, thus a prerequisite on one is never satisfied.
        prereqs = {c.id: (f"✎ {c.name}" if c.custom else c.name)
                   for c in sorted(ruleset.charms.values(), key=lambda c: c.name)
                   if not c.virtual}
        lay.addWidget(self._heading("Prerequisites"))
        lay.addWidget(self._picker("prerequisites", prereqs))
        mode = self._combo("prereq_mode",
                           {"all": "all required", "any": "any one of them"})
        mode.setToolTip("Prerequisites are AND-of-OR; these are the two shapes the form "
                        "writes. Anything more complex: use the JSON pane.")
        self._labelled(lay, "Mode", mode)
        self._labelled(lay, "Sorcery", self._combo(
            "grants_circle",
            {"": "grants no sorcery circle"}
            | {c.value: f"grants the {c.value} Circle" for c in SpellCircle}))
        self._advanced_fields(lay)

    def _extra_requirements(self, lay) -> None:
        """The repeatable "and also needs…" editor. It holds any number of AND rows, and
        each row is an OR over Abilities or over Attributes.

        ⚠ These rows are separate from `min_ability`. `min_ability` is the gate that comes
        from the category of the Charm, and the price and the Caste/Favoured discount read
        it. These rows are requirements only. A new row never makes a Charm cheaper.
        """
        rows = self._form.setdefault("extra_reqs", [])
        header = QHBoxLayout()
        header.addWidget(self._heading("Also requires"))
        add = QPushButton("+ requirement")
        add.setObjectName("custom.extra_reqs.add")
        add.setToolTip("An extra Ability or Attribute minimum, on top of the one above")
        add.clicked.connect(lambda: (rows.append(
            {"kind": "ability", "traits": [], "rating": 1}), self._rebuild()))
        header.addWidget(add)
        header.addStretch(1)
        lay.addLayout(header)
        if not rows:
            lay.addWidget(self._muted("No extra trait minimums — the Charm gates only on "
                                      "the Ability above."))
        for index, req in enumerate(rows):
            row = QHBoxLayout()
            kind = QComboBox()
            kind.setObjectName(f"custom.extra_reqs.{index}.kind")
            for value, label in (("ability", "Ability"), ("attribute", "Attribute")):
                kind.addItem(label, value)
            kind.setCurrentIndex(0 if req.get("kind") != "attribute" else 1)

            def set_kind(i, r=req, idx=index) -> None:
                # ⚠ Clear the traits when the axis changes. An Ability value is not a legal
                # Attribute. If the traits stay, the picker holds options that its own list
                # does not contain.
                r["kind"] = "ability" if i == 0 else "attribute"
                r["traits"] = []
                self._rebuild()
            kind.currentIndexChanged.connect(set_kind)
            row.addWidget(kind)
            picker = _FavoredPicker(
                viewmod.extra_req_trait_options(req.get("kind", "ability")),
                list(req.get("traits") or []), _NO_CAP, self._accent(),
                lambda picks, r=req: r.update(traits=picks))
            picker.setObjectName(f"custom.extra_reqs.{index}.traits")
            picker.setToolTip("Several traits in one row means ANY ONE of them satisfies "
                              "it; add another row for a second, separate requirement.")
            row.addWidget(picker, 1)
            rating = QSpinBox()
            rating.setObjectName(f"custom.extra_reqs.{index}.rating")
            rating.setRange(1, 10)
            rating.setValue(int(req.get("rating") or 1))
            rating.setToolTip("Minimum rating")
            rating.valueChanged.connect(lambda v, r=req: r.update(rating=v))
            row.addWidget(rating)
            drop = QPushButton("✕")
            drop.setObjectName(f"custom.extra_reqs.{index}.remove")
            drop.clicked.connect(
                lambda _=False, i=index: (rows.pop(i), self._rebuild()))
            row.addWidget(drop)
            lay.addLayout(row)

    def _breadth_requirements(self, lay) -> None:
        """A COUNT over a category, for example "any three Lore Charms". ⚠ The prerequisite
        list uses ids, and it cannot state this rule. Three groups that each list all
        eleven Lore Charms accept one owned Charm three times."""
        rows = self._form.setdefault("breadth_reqs", [])
        header = QHBoxLayout()
        header.addWidget(self._heading("Also requires N Charms of a kind"))
        add = QPushButton("+ breadth")
        add.setObjectName("custom.breadth_reqs.add")
        add.setToolTip('A breadth prerequisite, e.g. "any three Lore Charms"')
        add.clicked.connect(lambda: (rows.append(
            {"category": "lore", "count": 3, "label": ""}), self._rebuild()))
        header.addWidget(add)
        header.addStretch(1)
        lay.addLayout(header)
        options = viewmod.extra_req_trait_options("ability")
        for index, req in enumerate(rows):
            row = QHBoxLayout()
            count = QSpinBox()
            count.setObjectName(f"custom.breadth_reqs.{index}.count")
            count.setRange(1, 20)
            count.setValue(int(req.get("count") or 1))
            count.valueChanged.connect(lambda v, r=req: r.update(count=v))
            row.addWidget(count)
            category = _FilterCombo()
            category.setObjectName(f"custom.breadth_reqs.{index}.category")
            keys = list(options)
            for value, label in options.items():
                category.addItem(label, value)
            current = str(req.get("category") or "")
            category.setCurrentIndex(keys.index(current) if current in keys else 0)
            category.setToolTip("Counted by the Charm's category — a Craft Charm printed "
                                "in another book still counts toward 'any three Craft "
                                "Charms'")
            category.currentIndexChanged.connect(
                lambda i, r=req, k=keys: r.update(category=k[i]) if 0 <= i < len(k)
                else None)
            row.addWidget(category, 1)
            drop = QPushButton("✕")
            drop.setObjectName(f"custom.breadth_reqs.{index}.remove")
            drop.clicked.connect(
                lambda _=False, i=index: (rows.pop(i), self._rebuild()))
            row.addWidget(drop)
            lay.addLayout(row)

    def _advanced_fields(self, lay) -> None:
        """The splat mechanics. A homebrew Charm needs these fields rarely, and they have
        no meaning outside their own splat. This section is folded by default. Thus the
        usual form stays short: a category, a cost and two or three minimums.

        This form writes a field here only when its value differs from the model default.
        Thus the JSON of an ordinary Charm holds no unnecessary zeroes
        (`view.custom_charm_payload`).
        """
        section = _Collapsible("Advanced (splat mechanics)", self._accent())
        body = section.body()
        element = self._combo("element", viewmod.charm_element_options(self._ruleset))
        element.setToolTip("Dragon-Blooded organise Charms by element; it groups the "
                           "picker")
        self._labelled(body, "Elemental tree", element, width=120)
        attribute = self._combo(
            "min_attribute", {"": "—"} | viewmod.extra_req_trait_options("attribute"))
        attribute.setToolTip("RETARGETS the 'Min ability' above at an Attribute instead "
                             "(the Attribute-keyed splats, e.g. Lunar). Unlike the extra "
                             "requirements, this one drives pricing and the "
                             "Caste/Favoured discount.")
        self._labelled(body, "Gate on Attribute", attribute, width=120)
        body.addWidget(self._check(
            "open_to_all", "Any splat may learn it",
            "The Terrestrial Martial Arts case — learnable by anyone with a tutor"))
        self._labelled(body, "Open to tiers",
                       self._picker("open_to_tiers",
                                    viewmod.charm_tier_options(self._ruleset)), width=120)
        body.addWidget(self._check(
            "immaculate", "Immaculate Order Charm",
            "Dragon-Blooded Fivefold Dragon Method — also priced on the Immaculate row"))
        body.addWidget(self._check(
            "no_foreign_learning", "Barred from foreign learning",
            "Unreachable even by the Eclipse/Moonshadow generalist rule (p.127)"))
        body.addWidget(self._muted("Alchemical only"))
        alchemical = QHBoxLayout()
        alchemical.addWidget(QLabel("Install"))
        alchemical.addWidget(self._spin("installation_cost", 0, 99))
        alchemical.addWidget(QLabel("Clarity"))
        alchemical.addWidget(self._spin("permanent_clarity", 0, 99))
        alchemical.addStretch(1)
        body.addLayout(alchemical)
        body.addWidget(self._check("arrayable", "Usable in Arrays"))
        body.addWidget(self._check("permanent_install", "Can never be uninstalled"))
        body.addWidget(self._muted(
            "Repeatable Charms (Ox-Body-style variants) are not editable here — use "
            "JSON… in the toolbar.", italic=True))
        lay.addWidget(section)


def _wrap(lay) -> QWidget:
    """A layout as a widget, so it can go in a `_labelled` row."""
    holder = QWidget()
    holder.setLayout(lay)
    return holder
