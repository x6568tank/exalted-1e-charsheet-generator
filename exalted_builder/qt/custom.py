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

⚠ **This is the ONE collection whose detail pane is not a projection of a selected row.**
Every other tab's pane shows what you clicked; here it also has to hold an UNSAVED new
row, because the form is where authoring happens. `_editing == ""` is that state, and
`New` is what enters it. A rebuild must not silently re-select a table row and throw the
half-written form away.

⚠ **`on_change` is REQUIRED.** Deleting a custom Charm a character owns does not remove
it from that character — the id stays and becomes an `unknown-charm` validation error, so
the shell's readout bar is stale without the ping. (`CharmsPage` shipped without this
hook for want of the same check.)

⚠ **The webapp's third column became a TOOLBAR ACTION, not a nested tab.** `ui/custom.py`
puts library / form / JSON side by side; the collection layout has one detail pane, and
JSON in-and-out is an *action* on the row rather than a property of it. Nesting a second
level of tabs inside the pane was the alternative and is worse.

Zero game logic. Form ⇄ payload shuffling is `view.custom_*`, validity is the pydantic
models, the filesystem is `custom_content`, and the merge back into the live rule set is
`rules_db.reload_custom_layer`.
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
from .layout import clear_layout
from .theme import CUSTOM, MUTED, accent as accent_light

_KINDS = ("charm", "spell", "gear")
_KIND_LABELS = {"charm": "Charms", "spell": "Spells", "gear": "Gear"}
# Gear carries a Kind column: the four catalogues are ONE concept on screen (things you
# own), so they share a list rather than splitting it into four more sub-tabs.
_COLUMNS = {"charm": ("", "Name", "Detail"),
            "spell": ("", "Name", "Detail"),
            "gear": ("", "Name", "Kind", "Detail")}

# ⚠ Gear IS authorable here as of 2026-08-27, which REVERSES the 2026-08-13 ruling that
# "no authoring form was needed: you tweak an item on a character and click once"
# (`docs/status/custom-content.md`). The human reopened it. The old flow made you give a
# character an item in order to invent one — Buy → "Custom weapon" → a blank row on
# somebody's sheet → edit → save → delete the row you never wanted.
#
# ⚠ BOTH entry points stay (the human's call): the Gear tab's button is retroactive
# ("I tweaked this and want to keep it"), this form is deliberate ("I want to design
# one"). They cannot drift because both write through `custom_content.save_gear_row`.
_GEAR_BLURB = (
    "Pick a kind and fill in the stats, or press “Save to my library” on any Gear-tab "
    "row to keep something you tweaked there. Both land in the same library.")

# ⚠ None, NOT a large number. The three multi-picks here (prerequisites,
# extra-requirement traits, open-to tiers) are unbounded in the models, and
# `_FavoredPicker` PRINTS its cap in the placeholder — 999 put "(pick 999)" on screen.
_NO_CAP = None

# How many characters a delete could affect is unknowable from here (saves live wherever
# the user put them), so this says what actually happens rather than guessing a number.
_DELETE_WARNING = (
    "Any character that already owns it keeps the id: the Charm shows on the sheet as a "
    "missing row (⚠) with an error, and comes back if you re-create it with the same "
    "name. Nothing else is changed.")

# ⚠ A DIFFERENT warning from the Charm one, because the consequence is different.
# Saves carry inline COPIES of gear (decision 0007 — ids for invariant content, inline
# copies for variable), so deleting a library weapon does not orphan anything a
# character owns; only the shop's offer goes away. Telling the user the Charm story
# here would be a lie in the frightening direction.
_GEAR_DELETE_WARNING = (
    "Characters that already own one keep it: a save carries its own copy of every "
    "weapon, armour and item, so nothing on a sheet changes. It only disappears from "
    "Buy.")

_JSON_BLURB = ("The same row as text — copy it out to share, or paste one in and press "
               "Load to fill the form. An array of rows is a bulk import and is saved "
               "straight away.")


class _Collapsible(QWidget):
    """A titled section that folds away. ⚠ Built from a QPushButton and a plain
    container rather than a QGroupBox: `qt/theme.py::qss` names no QGroupBox, and an
    unstyled one draws its own border and title on the dark page."""

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
    """The tab widget. `reload()` re-merges the library and rebuilds the tables;
    `notify` surfaces transient messages; `on_change` pings the shell so its readout bar
    re-derives after a delete orphans a Charm a character owns."""

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
        self._editing = ""          # the id being replaced; "" is a new, unsaved row
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
            # ⚠ NAME takes the slack and DETAIL is capped. With Detail on
            # ResizeToContents it sized to its own content first and left Name ~75px,
            # so every row read "Singing E…" / "Wound Dr…" — the one column you
            # identify a row by, truncated, while dead space sat to the right.
            # Detail is secondary here (the pane repeats it) and stays draggable.
            for column in range(len(columns)):
                table.header().setSectionResizeMode(
                    column,
                    QHeaderView.Stretch if column == 1
                    else QHeaderView.Interactive if column == len(columns) - 1
                    else QHeaderView.ResizeToContents)
            table.header().resizeSection(len(columns) - 1, 170)
            table.itemSelectionChanged.connect(self._selection_changed)
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

        # Library problems sit UNDER the splitter, spanning both: they are about the
        # library as a whole, not about whichever row is selected.
        self.problems = QLabel("")
        self.problems.setWordWrap(True)
        self.problems.setContentsMargins(8, 2, 8, 4)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.readout)
        outer.addLayout(bar)
        outer.addWidget(split, 1)
        outer.addWidget(self.problems)
        # ⚠ The FORM only — `reload()` is deliberately NOT called here, unlike every
        # sibling page. This is the one tab whose refresh reads the FILESYSTEM, and the
        # shell builds all nine pages up front: calling it here would make constructing
        # a MainWindow re-scan the user's homebrew library, in all 300-odd Qt tests and
        # on every window. The shell calls `reload()` when the tab is shown, which is
        # the right moment and the only moment the library can have changed.
        self._sync_detail()

    # ------------------------------------------------------------------ #
    # plumbing
    # ------------------------------------------------------------------ #

    def _accent(self) -> str:
        return accent_light(theme.palette(None))

    def _reserved(self) -> set[str]:
        """The BOOK's ids, so homebrew can never shadow printed content. Recomputed per
        call — the custom half of `ruleset.charms` changes underneath us."""
        if self._kind == "gear":
            # ⚠ Gear carries no `custom` FIELD — the loader TAGS it, because the models
            # are frozen and shared with the book data. Reading `.custom` here raises.
            catalog = getattr(self._ruleset,
                              viewmod.CUSTOM_GEAR_KINDS[self._gear_kind][0])
            return {i for i, row in catalog.items() if "custom" not in row.tags}
        pool = self._ruleset.charms if self._kind == "charm" else self._ruleset.spells
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
            custom_content.library_spells(self._root)) if r.kind == self._kind]

    def reload(self) -> None:
        """Re-merge the library into the live rule set, then rebuild everything that
        reads it. Problems are SHOWN rather than raised — the loader's non-fatal
        contract for custom data (a typo in homebrew must not stop the app)."""
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
        charms = custom_content.library_charms(self._root)
        spells = custom_content.library_spells(self._root)
        gear = sum(len(custom_content.library_gear(kind, self._root))
                   for kind in viewmod.CUSTOM_GEAR_KINDS)
        bits = [f"{len(charms)} Charm(s)", f"{len(spells)} spell(s)",
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

        ⚠ Only the ACTIVE kind's table is filled. Both were, once — and filling the
        inactive one moved `self._editing` through `_selection_changed`, which reads
        whichever table is on top, throwing away a half-written form on the other tab.
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
            # ⚠ The gear KIND rides on the item: `delete_gear` needs it, and it cannot
            # be re-derived from the id (the four files share one id namespace).
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
        # ⚠ Restore ONLY an explicit match, and never fall back to row 0. Every other
        # collection selects its first row when the old selection is gone; here that
        # would overwrite an unsaved new row the moment the table rebuilt.
        table.setCurrentItem(restore)
        table.blockSignals(False)

    def _kind_changed(self, index: int) -> None:
        self._kind = _KINDS[index]
        # ⚠ Before `_new()`, and here rather than only in `reload()`: the action set
        # depends on the KIND, and switching sub-tabs is the one thing that changes it.
        # Wired only to `reload()` at first, which left New and Import dead after a trip
        # to the Gear tab and back — the tab that disabled them.
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

        Gear has no form — it loads the raw row so the pane and the JSON dialog can show
        it, and `_save` refuses.

        ⚠ Not from `ruleset.charms`: a row the loader REJECTED is not in the rule set at
        all, and that is exactly the row a user needs to open in order to fix it.
        """
        if self._kind == "gear":
            raw = next((r for r in custom_content.library_gear(self._gear_kind,
                                                               self._root)
                        if r.get("id") == row_id), {})
            self._set_form(viewmod.custom_gear_form(self._gear_kind, raw),
                           editing=row_id)
            return
        rows = (custom_content.library_charms(self._root) if self._kind == "charm"
                else custom_content.library_spells(self._root))
        raw = next((r for r in rows if r.get("id") == row_id), {})
        self._set_form(viewmod.custom_charm_form(raw) if self._kind == "charm"
                       else viewmod.custom_spell_form(raw), editing=row_id)

    def _set_form(self, form: dict, editing: str = "") -> None:
        self._form, self._editing = form, editing
        self._fill_tables()
        self._sync_detail()

    def _new(self) -> None:
        """A blank row of the current kind.

        ⚠ Gear needs a KIND before it can have a form — the four catalogues are four
        models with four field sets, and there is no neutral blank row. `_gear_kind`
        carries the answer and the pane asks for it when it is empty."""
        if self._kind == "gear":
            self._gear_kind = self._gear_kind or "weapons"
            self._set_form(viewmod.custom_gear_form(self._gear_kind))
            return
        self._gear_kind = ""
        self._set_form(viewmod.custom_charm_form() if self._kind == "charm"
                       else viewmod.custom_spell_form())

    def _sync_actions(self) -> None:
        """Which toolbar actions this kind has.

        ⚠ Import stays off for gear: `parse_rows` yields bare rows, and a gear row does
        not say WHICH of the four catalogues it belongs to. `New` does — its Kind picker
        is what supplies the answer. Everything else is live on every kind.
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
        return (viewmod.custom_charm_payload(self._form) if self._kind == "charm"
                else viewmod.custom_spell_payload(self._form))

    def _save(self) -> None:
        if self._kind == "gear":
            self._save_gear()
            return
        form = self._form
        # The id follows the NAME for a new row, so a rename before the first save does
        # not leave a stale id behind. Once saved it is frozen: characters reference it,
        # so an edit must never change it.
        if not self._editing:
            form["id"] = custom_content.make_id(form.get("name", ""))
        try:
            saver = (custom_content.save_charm if self._kind == "charm"
                     else custom_content.save_spell)
            saved = saver(self._payload(), custom_dir=self._root,
                          reserved_ids=self._reserved())
        except CustomContentError as exc:
            self._notify(str(exc), "warning")
            return
        rules_db.reload_custom_layer(self._ruleset, self._root)
        # Saving does not clear the form: the row is on disk and in the rule set now, and
        # staying on it is what makes "save, look at the tree, adjust" work.
        self._set_form(self._form, editing=saved.id)
        self._sync_readout()
        pool = self._ruleset.charms if self._kind == "charm" else self._ruleset.spells
        if saved.id not in pool:
            self._notify(f"Saved {saved.name}, but it did not load — see the problems "
                         f"below the list", "warning")
        else:
            self._notify(f"Saved {saved.name}", "info")
        self._ping()

    def _save_gear(self) -> None:
        """Write one library gear row. Mirrors `_save`, but through `save_gear_row` —
        which takes a plain dict and a KIND, because the four catalogues are four
        models and `custom_content` deliberately holds no game logic."""
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
        elif self._kind == "charm":
            gone = custom_content.delete_charm(self._editing, custom_dir=self._root)
        else:
            gone = custom_content.delete_spell(self._editing, custom_dir=self._root)
        self._new()
        self.reload()
        self._notify(f"Deleted {name}" if gone else f"{name} was not there", "info")
        # ⚠ The character is NOT edited by a delete — the id stays on the sheet and turns
        # into an `unknown-charm` error, which the shell's readout bar reports.
        self._ping()

    # ------------------------------------------------------------------ #
    # JSON in / out
    # ------------------------------------------------------------------ #

    def _build_json_dialog(self) -> QDialog:
        """The JSON pane as a dialog, BUILT but not run — `exec()` blocks a headless
        run, so this is the seam the tests drive (the shape `GearPage` uses)."""
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
        # ⚠ Read-only for gear: Load writes through the CHARM/spell savers, and a gear
        # row needs a target catalogue that a pasted row does not name.
        # ⚠ Copy-out works for gear; Load does not. `_paste` routes through the
        # Charm/spell savers, and a pasted gear row does not name which of the four
        # catalogues it belongs to — the form's Kind picker is what supplies that.
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
            # A single pasted row fills the form WITHOUT saving: the user gets to see and
            # adjust it first, which is the whole reason the pane is two-way.
            self._load_row(rows[0])
            self._notify("Loaded into the form — press Save to keep it", "info")
        else:
            self._apply_rows(rows, label="Paste")

    def _load_row(self, row: dict) -> None:
        rid = custom_content.normalize_id(str(row.get("id", "")))
        self._set_form(viewmod.custom_charm_form(row) if self._kind == "charm"
                       else viewmod.custom_spell_form(row), editing=rid)

    def _apply_rows(self, rows: list[dict], *, label: str) -> None:
        """Save every row. One row also loads into the form, so a paste of a single
        Charm is an edit rather than a blind write; several are a bulk import and are
        reported as a count."""
        saved, failed = 0, []
        saver = (custom_content.save_charm if self._kind == "charm"
                 else custom_content.save_spell)
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
        """A plain field write. ⚠ Does NOT rebuild — a rebuild under a keystroke
        destroys the widget being typed into and drops the caret."""
        def _set(value) -> None:
            self._form[key] = value
        return _set

    def _rebuild(self) -> None:
        """A STRUCTURAL change: which controls exist has changed (a new style name box,
        an extra-requirement row added or its axis switched)."""
        self._sync_detail()

    def _labelled(self, lay, caption: str, widget, *, width: int = 96) -> None:
        row = QHBoxLayout()
        label = QLabel(caption)
        label.setStyleSheet(f"color:{MUTED};")
        label.setMinimumWidth(width)
        # ⚠ TOP, not Qt's default vertical centre. The Description box is 90px+ tall and
        # a centred caption floats to the middle of it — far from the field it names, and
        # scrolled clean out of view when the row straddles the viewport edge.
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

        ⚠ The value written is indexed out of `options`, NEVER read back off the widget.
        Qt hands item data back as a QVariant and a str-valued Enum returns as a plain
        `str`, which succeeds on write and fails later somewhere else.
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
        # ⚠ `clear_layout`, never a hand-written loop — `item.widget()` is None for a
        # nested QLayout, and this form is nothing but nested rows.
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
        self._labelled(lay, "Name", self._line("name", "the Charm's printed name"))
        if self._kind == "charm":
            self._charm_fields(lay)
        else:
            self._spell_fields(lay)

        description = QTextEdit(str(self._form.get("description") or ""))
        description.setObjectName("custom.description")
        description.setMinimumHeight(90)
        # ⚠ An inline stylesheet, because an ancestor stylesheet beats a set palette and
        # a QTextEdit inside a themed page otherwise paints the card shade.
        description.setStyleSheet("background:#52525c; color:#e6e4e0; border:none;"
                                  " border-radius:4px;")
        # ⚠ `textChanged` on a QTextEdit carries NO argument (QLineEdit's does), so the
        # text comes off the widget.
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

        ⚠ A flat DICT validated on save, not `setattr` down a model like the Gear tab's
        editors. `WeaponType` and friends are FROZEN and shared with the book data, so
        there is no instance to mutate — this follows the Custom tab's own Charm-form
        pattern instead.
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
        # ⚠ Frozen once saved, like a Charm's category is not: changing the kind changes
        # the MODEL, and the row already sits in one of four files under one id.
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
        """Change which catalogue a NEW row is for. Starts a fresh form: the four models
        have four field sets, so carrying values across would keep keys the new model
        rejects."""
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
            # ⚠ Inline: an ancestor stylesheet beats a set palette, and a QTextEdit
            # otherwise paints the card shade.
            box.setStyleSheet("background:#52525c; color:#e6e4e0; border:none;"
                              " border-radius:4px;")
            box.textChanged.connect(
                lambda: self._form.__setitem__(spec.key, box.toPlainText()))
            return box
        if spec.kind == "text":
            return self._line(spec.key)
        # ⚠ `signed` exists for `mobility_penalty`, which is stored NEGATIVE
        # (`docs/status/gear-and-inventory.md`). A 0-floored box would make a penalty
        # impossible to enter, and a consumer reading it as a magnitude ADDS dice.
        spin = self._spin(spec.key, -20 if spec.kind == "signed" else 0, 99)
        spin.setMaximumWidth(90)
        # Parked left with the slack after it: `_labelled` stretches its widget, and a
        # one-digit soak box 540px wide reads as an unfinished form.
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

        # Every Charm in the rule set, homebrew included, so a custom tree can hang off a
        # printed Charm or another custom one. ⚠ Virtual rows are excluded — they are
        # never learnable, so a prerequisite on one would be unsatisfiable.
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
        """The repeatable "and also needs…" editor: any number of AND rows, each an OR
        over Abilities or over Attributes.

        Separate from the primary `min_ability`, which is the gate derived from the
        Charm's category and is what pricing and the Caste/Favoured discount key off.
        These rows are pure requirements — adding one never makes a Charm cheaper.
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
                # ⚠ The traits go WITH the axis: an Ability value is not a legal
                # Attribute, and leaving them renders a picker holding options its own
                # list does not contain.
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
        """"Any three Lore Charms" — a COUNT over a category, which the id-based
        prerequisite list cannot express (three groups each listing all eleven Lore
        Charms would be satisfied three times over by one owned Charm)."""
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
        """Splat mechanics: the fields a homebrew Charm rarely needs, and that mean
        nothing outside the splat that invented them. Folded away by default so the
        common case — a category, a cost and a couple of minimums — stays a short form.

        Everything here is written only when it differs from the model default, so an
        ordinary Charm's JSON does not grow a dozen zeroes (`view.custom_charm_payload`).
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
