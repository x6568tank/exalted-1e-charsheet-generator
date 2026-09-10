"""exalted_builder/qt/advantages.py — the Advantages tab: Backgrounds, Merits & Flaws,
and (for the splats that have them) Fetters and Passions.

Input: a RuleSet and the Character in the shared context. Output: one scrollable surface
with every list that this tab owns. The lock state of the character selects the mode.
Mechanism: `reload()` rebuilds the panels. A keystroke on a name or a note writes to the
model and updates its own labels only. ⚠ Thus no code replaces the widget that the user
types into.

⚠ Read the mode from the character (`_locked`). Never take it from the caller.
`ui/advantages.py` does the same.

* **Before the lock** — the Backgrounds use the chargen dot budget, with the limit that
  applies before bonus points. Merits and Flaws use bonus points: a Merit costs points, and
  a Flaw gives points.
* **After the lock** — the Backgrounds are free and the story drives them, and they add no
  log row. Merits and Flaws go through `advancement.gain_merit_or_flaw` and `drop_merit`.
  The engine prices them in XP and applies the debt rules.

This module has no game logic. The engine supplies the budgets, the limits, the prices, the
legality and the Merit-or-Flaw side. ⚠ No code here names a Merit id (decision 0011).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QPushButton, QScrollArea, QSpinBox, QSplitter, QTabWidget,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from exalted_builder.engine import (advancement, artifacts as artifactsmod,
                                    costs as costsmod, derive as derivemod,
                                    merits as meritsmod, validate)
from exalted_builder.models.character import (BackgroundEntry, FetterEntry,
                                              HearthstoneEntry, MeritFlawPurchase,
                                              PassionEntry)
from exalted_builder.models.rules import VirtueName
from exalted_builder.ui import theme
from exalted_builder.ui import view as viewmod

from .catalogue import CatalogueDialog, open_catalogue
from .layout import clear_layout, empty_note
from .editor import DotTrack, _FilterCombo
from .theme import MUTED, accent as accent_light

# The issue codes that this tab can correct. The readout bar of the shell reports the full
# list. A second copy of that list here makes both readouts difficult to read. The artifact
# codes are here, because the user edits the Artifact BACKGROUND rating on this tab and the
# budget findings read that rating. The Gear tab shows the same findings next to the items.
# There is ONE issue list, thus the two surfaces always agree.
_MY_ISSUES = ("background", "merit", "flaw", "artifact")

_MF_SIDES = {"": "All", "merit": "Merits", "flaw": "Flaws"}

_TABLE_COLUMNS = {
    "Backgrounds": ["Background", "Rating", "Note"],
    "Merits & Flaws": ["Entry", "Side", "Cost", "Detail"],
    "Fetters & Passions": ["Name", "Kind", "Rating", "Note"],
}

# The text for an EMPTY table. ⚠ A heading over a blank area reads as "nothing loaded", not
# as "nothing yet". See `qt/layout.py::empty_note`. Each message names its own action,
# because the toolbar button is different on each sub-tab.
_EMPTY_NOTES = {
    "Backgrounds": "No Backgrounds yet.\n\nUse “+ Background” — contacts, artifacts, "
                   "a manse, the people who owe you.",
    "Merits & Flaws": "No Merits or Flaws yet.\n\nUse “+ Merit / Flaw”. A Flaw refunds "
                      "bonus points rather than costing them.",
    # ⚠ The toolbar button here is "+ Fetter" or "+ Passion", and the splat decides which
    # one (`_has_fetters`). Thus this note names both. It must not name a button that is
    # not on the screen.
    "Fetters & Passions": "Nothing here yet.\n\nFetters and Passions are what hold the "
                          "dead to Creation (E:Ab p.126-127) — add one from the toolbar.",
}


def _DOTS_FILLED(rating: int) -> str:
    """A rating as filled pips and empty pips, for a table cell. ⚠ Qt sorts this cell as
    text. Thus the filled pips must come first. "●●○○○" then sorts after "●○○○○"."""
    rating = max(0, min(5, int(rating or 0)))
    return "●" * rating + "○" * (5 - rating)



def _resync(holder) -> None:
    """Re-label a catalogue dialog's confirm button, if it exists yet.

    ⚠ This function does nothing on the first call, and that is correct. The constructor of
    the dialog selects row 0. Thus `extras` runs, and it calls this function, before
    `CatalogueDialog.__init__` returns and the caller stores the reference. `_show_detail`
    labels the button after that. Thus no label is lost.
    """
    dialog = holder.get("dialog")
    if dialog is not None:
        dialog.refresh_confirm()


class AdvantagesPage(QWidget):
    """The tab widget. `reload()` rebuilds the body for the character in ctx. `notify` shows
    a temporary message. `on_change` calls the shell, thus the shell calculates its readout
    bar and its status strip again."""

    def __init__(self, ruleset, ctx, *, notify=None, on_change=None, parent=None):
        super().__init__(parent)
        self._ruleset = ruleset
        self._ctx = ctx
        self._notify = notify or (lambda text, kind="info": None)
        self._on_change = on_change
        # The in-play purchase that waits. ⚠ Nothing is bought until the user clicks Gain.
        self._gain: dict = {"id": "", "tier": "", "points": 0, "taken_as": "",
                            "detail": ""}
        # The selections that the add dialogs hold. The controls are in the dialog. Thus the
        # selected rating or tier must stay until the confirm button commits it.
        self._pending_mf: dict = {}
        self._pending_bg: dict = {}
        self._mf_filter: dict[str, str] = {"text": "", "kind": "", "category": ""}
        self._mf_rows: list[tuple[QComboBox, MeritFlawPurchase]] = []
        self._mf_count: QLabel | None = None
        self._drop_idx: str = ""

        # The selected row, as `(list_name, index)`. ⚠ This is a POSITION. `_rebuild` drops
        # it, because an add or a remove gives a new number to every row after it.
        self._selected: tuple[str, int] | None = None
        self._search = ""

        self.issues = QLabel("")
        self.issues.setWordWrap(True)
        self.issues.setContentsMargins(8, 4, 8, 4)

        # ---- the action toolbar -------------------------------------- #
        # ⚠ Put the actions HERE, not in the content. Each SUB-TAB has its own add button:
        # "+ Background" on one, "Gain a Merit or Flaw…" on another. The collection decides
        # what the user can add. Three buttons that are always visible offer two actions
        # that the user cannot use.
        bar = QHBoxLayout()
        bar.setContentsMargins(8, 0, 8, 0)
        self.add_btn = QPushButton("")
        self.add_btn.clicked.connect(self._add_for_current_tab)
        bar.addWidget(self.add_btn)
        self.drop_btn = QPushButton("Lose / buy off")
        self.drop_btn.clicked.connect(self._drop_selected)
        bar.addWidget(self.drop_btn)
        bar.addSpacing(12)
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("filter by name…")
        self.search_box.setClearButtonEnabled(True)
        self.search_box.textChanged.connect(self._search_changed)
        bar.addWidget(self.search_box, 1)

        # ---- the tables ------------------------------------------------ #
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.currentChanged.connect(self._tab_changed)
        self._tables: dict[str, QTreeWidget] = {}
        self._notes: dict[str, QVBoxLayout] = {}

        # ---- the detail pane -------------------------------------------- #
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
        split.setSizes([680, 500])
        self._scroll = detail_scroll

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.issues)
        outer.addLayout(bar)
        outer.addWidget(split, 1)
        self.reload()

    # ------------------------------------------------------------------ #
    # plumbing
    # ------------------------------------------------------------------ #

    def _char(self):
        return self._ctx["char"]

    def _locked(self) -> bool:
        return self._char().chargen_locked

    def _pal(self):
        return theme.palette(self._char().exalt_type)

    def _accent(self) -> str:
        return accent_light(self._pal())

    def _clear_lay(self, lay) -> None:
        """Empty `lay`, and detach every descendant immediately. ⚠ Call `qt/layout.py`.
        That module holds the two traps in this operation."""
        clear_layout(lay)

    def reload(self) -> None:
        """Rebuild the sub-tabs and their tables for the character in ctx. Keep the
        selection and the active tab."""
        self._mf_rows = []
        self._mf_count = None
        remembered_tab = self.tabs.tabText(self.tabs.currentIndex())
        # ⚠ Block the signals across the rebuild. `clear()` sends `currentChanged`, and
        # `_tab_changed` then reads tables that are not complete. The Charms tab has the
        # same trap.
        self.tabs.blockSignals(True)
        try:
            self.tabs.clear()
            self._tables = {}
            self._notes = {}
            for label in self._categories():
                self.tabs.addTab(self._table_page(label), label)
            index = next((i for i in range(self.tabs.count())
                          if self.tabs.tabText(i) == remembered_tab), 0)
            self.tabs.setCurrentIndex(index)
        finally:
            self.tabs.blockSignals(False)
        self._fill_tables()
        self._sync_toolbar()
        self._sync_detail()
        self._changed()

    def _rebuild(self) -> None:
        """Apply a change that moved the LISTS. ⚠ Drop the selection first. It is a
        position, and an add or a remove gives a new number to every row after it."""
        self._selected = None
        self.reload()

    def _categories(self) -> list[str]:
        """The sub-tabs for this character. Only a ghost has Fetters and Passions. ⚠ Do not
        show an empty tab."""
        cats = ["Backgrounds", "Merits & Flaws"]
        if self._has_fetters() or self._has_passions():
            cats.append("Fetters & Passions")
        return cats

    def _table_page(self, label: str) -> QWidget:
        """One sub-tab: a contextual note line over the table for that category."""
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        notes = QVBoxLayout()
        lay.addLayout(notes)
        self._notes[label] = notes
        table = QTreeWidget()
        table.setHeaderLabels(_TABLE_COLUMNS[label])
        table.setRootIsDecorated(False)
        table.setAlternatingRowColors(True)
        table.setSortingEnabled(True)
        # ⚠ Set the initial sort. Without it, Qt selects its own indicator, and the first
        # fill comes out in reverse alphabetical order. That reads as a defect. The user can
        # still click any header.
        table.sortByColumn(0, Qt.AscendingOrder)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.header().setSectionResizeMode(0, QHeaderView.Stretch)
        table.header().setSectionResizeMode(
            len(_TABLE_COLUMNS[label]) - 1, QHeaderView.Stretch)
        table.itemSelectionChanged.connect(self._selection_changed)
        empty_note(table, _EMPTY_NOTES[label])
        lay.addWidget(table, 1)
        self._tables[label] = table
        return page

    def _search_changed(self, text: str) -> None:
        self._search = (text or "").strip().lower()
        self._fill_tables()
        self._sync_detail()

    def _tab_changed(self, *_) -> None:
        self._sync_toolbar()
        self._sync_detail()

    def _current_table(self) -> QTreeWidget | None:
        return self._tables.get(self.tabs.tabText(self.tabs.currentIndex()))

    def _selection_changed(self) -> None:
        table = self._current_table()
        item = None if table is None else table.currentItem()
        self._selected = None if item is None else item.data(0, Qt.UserRole)
        self._sync_toolbar()
        self._sync_detail()

    def _changed(self) -> None:
        """Apply a change that moves the readouts only. Calculate the issue line of this tab
        again, and call the shell. The readout bar of the shell holds the bonus-point
        total."""
        ruleset, char = self._ruleset, self._char()
        if char.chargen_locked:
            available = advancement.xp_available(char)
            debt = advancement.xp_debt(char)
            text = f"{available} XP available"
            if debt:
                text += (f" · ⚠ {debt} XP owed — all further experience clears this "
                         f"first.")
            self.issues.setText(text)
            self.issues.setStyleSheet(
                "font-weight:600; color:%s;"
                % ("#15803d" if available >= 0 else "#b91c1c"))
        else:
            # The readout bar of the SHELL shows the bonus-point total. ⚠ Do not print it
            # here. The screen then shows the same sentence two times.
            view = viewmod.build_sheet_view(ruleset, char)
            mine = [i for i in view.issues
                    if i.code != "bonus-points"
                    and any(k in i.code for k in _MY_ISSUES)]
            self.issues.setText("\n".join(f"• {i.message}" for i in mine) if mine
                                else "No Background or Merit issues.")
            worst = ("#b91c1c" if any(i.severity == "error" for i in mine)
                     else "#b45309" if mine else self._accent())
            self.issues.setStyleSheet(f"color:{worst};")
        if self._on_change is not None:
            self._on_change()

    def _do(self, action) -> bool:
        """Run one engine advancement call, and show a refusal. Returns True when the
        character changed."""
        try:
            action()
        except advancement.AdvancementError as ex:
            self._notify(str(ex), "warning")
            return False
        return True

    def _muted(self, text: str, *, italic: bool = False) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet(f"color:{MUTED};" + (" font-style:italic;" if italic else ""))
        return label

    def _warn(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet("color:#d19a3a; font-weight:600;")
        return label

    # ------------------------------------------------------------------ #
    # body
    # ------------------------------------------------------------------ #

    # ------------------------------------------------------------------ #
    # the tables
    # ------------------------------------------------------------------ #

    def _fill_tables(self) -> None:
        """Rebuild every visible table and its notes. Select the same row again, when the
        table still shows it."""
        b = validate.effective_budgets(self._ruleset, self._char())
        for label, table in self._tables.items():
            self._clear_lay(self._notes[label])
            # ⚠ Turn sorting OFF across the fill. If sorting is on, Qt sorts again after
            # each insert. That is slow, and it loses the insertion order.
            table.setSortingEnabled(False)
            table.blockSignals(True)
            table.clear()
            builder = {"Backgrounds": self._fill_backgrounds,
                       "Merits & Flaws": self._fill_merits,
                       "Fetters & Passions": self._fill_fetters_passions}[label]
            builder(table, self._notes[label], b)
            table.blockSignals(False)
            table.setSortingEnabled(True)
            self._restore_selection(table)

    def _restore_selection(self, table) -> None:
        for i in range(table.topLevelItemCount()):
            if table.topLevelItem(i).data(0, Qt.UserRole) == self._selected:
                table.setCurrentItem(table.topLevelItem(i))
                return
        if table.topLevelItemCount() and table is self._current_table():
            table.setCurrentItem(table.topLevelItem(0))

    def _add_row(self, table, key, columns) -> None:
        if self._search and self._search not in str(columns[0]).lower():
            return
        item = QTreeWidgetItem([str(c) for c in columns])
        item.setData(0, Qt.UserRole, key)
        table.addTopLevelItem(item)

    def _fill_backgrounds(self, table, notes, b) -> None:
        ruleset, char = self._ruleset, self._char()
        if self._locked():
            # In play, the story changes a Background: a Manse falls, or a character makes
            # an Ally. The user does not spend XP. Thus the current value is editable, it
            # costs nothing, and it adds no log row.
            notes.addWidget(self._muted("Free in play — the story gives and takes "
                                        "these; no XP, no log row."))
        else:
            notes.addWidget(self._muted(
                f"{validate.background_dots_budget(b, char)} dots to spend; "
                f"≤{b.background_cap_pre_bp} in any one before bonus points."))
        catalog = self._bg_catalog()
        for idx, bg in enumerate(char.backgrounds):
            effective = validate.effective_background_rating(ruleset, char, bg.name)
            # A book of a splat can separate what the user BUYS from what the Background is
            # WORTH. Mountain Folk Resources is dots + 2, with a maximum of 3 dots. The
            # table shows both numbers.
            rating = _DOTS_FILLED(bg.rating)
            if effective != bg.rating:
                rating += f"  (effective {effective})"
            note = bg.note
            if bg.hearthstones:
                stones = f"{len(bg.hearthstones)} hearthstone(s)"
                note = f"{note} · {stones}" if note else stones
            if bg.is_demesne:
                note = f"Demesne · {note}" if note else "Demesne"
            self._add_row(table, ("backgrounds", idx), (bg.name or "—", rating, note))

    def _fill_merits(self, table, notes, b) -> None:
        ruleset, char = self._ruleset, self._char()
        if not ruleset.merits_flaws:
            # decision 0011: the file is optional.
            notes.addWidget(self._muted("This rule set ships no Merits or Flaws."))
            return
        eff = meritsmod.merits_and_flaws_calc(ruleset, char)
        if self._locked():
            self._play_merit_notes(notes, eff)
        for idx, mp in enumerate(char.merits_flaws):
            definition = ruleset.merits_flaws.get(mp.merit_id)
            # ⚠ An EMPTY `merit_id` identifies a custom row. Never test `custom_name` for a
            # value. The name input writes `custom_name` on each keystroke.
            if not mp.merit_id:
                self._add_row(table, ("merits_flaws", idx),
                              (mp.custom_name or "Custom", "custom", "", mp.detail))
                continue
            name = definition.name if definition is not None else mp.merit_id
            side = mp.taken_as or (definition.kind if definition else "")
            cost = viewmod.merit_tier_label(mp.tier) if mp.tier else ""
            if mp.points:
                cost = f"{cost} ({mp.points})" if cost else str(mp.points)
            detail = mp.detail or mp.arena
            if definition is None:
                detail = "not in the rule set"
            self._add_row(table, ("merits_flaws", idx), (name, side, cost, detail))
        if eff.granted_merits:
            names = ", ".join(sorted(ruleset.merits_flaws[m].name
                                     for m in eff.granted_merits
                                     if m in ruleset.merits_flaws))
            notes.addWidget(self._muted(f"Granted free by another Merit: {names}",
                                        italic=True))

    def _play_merit_notes(self, notes, eff) -> None:
        """The in-play pricing rules, above the table they govern."""
        method = advancement.mf_change_method(self._char())
        if method != "experience":
            # Under the other two methods, a change "does not cost or reward", and it
            # belongs to chargen. Show that text. Do not offer buttons that all show 0 XP.
            notes.addWidget(self._muted(
                f"This table uses the '{method}' method (Player's Guide p.17), under "
                f"which gaining or losing a Merit costs and rewards nothing. Unlock "
                f"chargen to edit them."))
            return
        notes.addWidget(self._muted(
            "Gaining a Merit or losing a Flaw costs twice its point value; losing a "
            "Merit or gaining a Flaw pays the same. An unaffordable change runs a debt "
            "against future XP."))
        # The limit on p.17 also applies in play. Here it reduces the XP AWARD, not a
        # bonus-point grant. A Flaw above the limit pays for its legal part only. ⚠ Show the
        # remaining room before the purchase. An award that is smaller than the table gives,
        # with no message, is the worse failure.
        room = max(0, meritsmod.FLAW_POINT_CAP - eff.flaw_points_raw)
        if room:
            notes.addWidget(self._muted(
                f"{eff.flaw_points_raw} of {meritsmod.FLAW_POINT_CAP} points of Flaws "
                f"taken — a new Flaw pays for at most {room} more."))
        else:
            notes.addWidget(self._warn(
                f"⚠ {eff.flaw_points_raw} points of Flaws taken — at the "
                f"{meritsmod.FLAW_POINT_CAP}-point cap (p.17). A further Flaw still "
                f"applies, but pays no XP."))

    def _fill_fetters_passions(self, table, notes, b) -> None:
        char = self._char()
        notes.addWidget(self._muted(
            "Passion dots are a LIVE DERIVATION of the Virtues (E:Ab p.283) — never "
            "bought with bonus points or XP, on either side of the lock."))
        if self._has_fetters():
            for idx, f in enumerate(char.fetters):
                self._add_row(table, ("fetters", idx),
                              (f.name or "—", "Fetter", _DOTS_FILLED(f.rating), f.note))
        if self._has_passions():
            for idx, p in enumerate(char.passions):
                self._add_row(table, ("passions", idx),
                              (p.name or "—", f"Passion · {p.virtue}",
                               _DOTS_FILLED(p.rating), p.note))

    # ------------------------------------------------------------------ #
    # the toolbar
    # ------------------------------------------------------------------ #

    def _sync_toolbar(self) -> None:
        """Point the add button at the active sub-tab. Show Drop only where it can run."""
        label = self.tabs.tabText(self.tabs.currentIndex())
        locked, char = self._locked(), self._char()
        if label == "Backgrounds":
            self.add_btn.setText("+ Background")
            self.add_btn.setEnabled(True)
        elif label == "Merits & Flaws":
            self.add_btn.setText("Gain a Merit or Flaw…" if locked
                                 else "+ Merit or Flaw")
            self.add_btn.setEnabled(bool(self._ruleset.merits_flaws))
        else:
            self.add_btn.setText("+ Fetter" if self._has_fetters() else "+ Passion")
            self.add_btn.setEnabled(True)
        # "Lose / buy off" is an XP transaction. It exists after the lock only, on a row
        # that the character holds. Before the lock, the user deletes the row in its own
        # editor.
        selected_mf = (self._selected is not None
                       and self._selected[0] == "merits_flaws")
        self.drop_btn.setVisible(
            locked and label == "Merits & Flaws"
            and advancement.mf_change_method(char) == "experience")
        self.drop_btn.setEnabled(selected_mf)

    def _add_for_current_tab(self) -> None:
        label = self.tabs.tabText(self.tabs.currentIndex())
        if label == "Backgrounds":
            self._open_bg_catalogue()
        elif label == "Merits & Flaws":
            available = self._available_merits(
                validate.effective_budgets(self._ruleset, self._char()).essence_start
                if self._locked() else None)
            if self._locked():
                self._open_gain_catalogue(available)
            else:
                self._open_mf_catalogue(available)
        elif self._has_fetters():
            self._add_fetter_row()
        else:
            self._add_passion(None)

    def _drop_selected(self) -> None:
        """Lose / buy off the SELECTED Merit or Flaw.

        ⚠ Read the table selection. Do not add a separate "Held" combo box. Two controls
        that name the same entry are ambiguous, and the button then acts on the control
        that the user does not read."""
        if self._selected is None or self._selected[0] != "merits_flaws":
            return
        self._drop_idx = str(self._selected[1])
        self._drop_mf()

    # ------------------------------------------------------------------ #
    # the detail pane
    # ------------------------------------------------------------------ #

    def _sync_detail(self) -> None:
        """Rebuild the right-hand pane for the current selection."""
        self._clear_lay(self._detail_lay)
        self._mf_rows = []
        table = self._current_table()
        item = None if table is None else table.currentItem()
        if item is None or self._selected is None:
            self.detail_title.setText("")
            self._detail_lay.addWidget(self._muted(
                "Select an entry to edit it, or add one from the toolbar."))
            self._detail_lay.addStretch(1)
            return
        list_name, index = self._selected
        owner = getattr(self._char(), list_name)
        if not (0 <= index < len(owner)):
            self.detail_title.setText("")
            self._detail_lay.addStretch(1)
            return
        self.detail_title.setText(item.text(0))
        self.detail_title.setStyleSheet(
            f"font-weight:700; font-size:14px; color:{self._accent()};")
        b = validate.effective_budgets(self._ruleset, self._char())
        editor = {"backgrounds": self._background_editor,
                  "merits_flaws": self._merit_editor,
                  "fetters": self._fetter_editor,
                  "passions": self._passion_editor}[list_name]
        editor(self._detail_lay, owner[index], index, b)
        self._detail_lay.addStretch(1)

    def _labelled(self, lay, caption: str, widget) -> None:
        row = QHBoxLayout()
        label = QLabel(caption)
        label.setStyleSheet(f"color:{MUTED};")
        label.setMinimumWidth(88)
        row.addWidget(label)
        row.addWidget(widget, 1)
        lay.addLayout(row)

    def _heading(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(f"font-weight:600; color:{self._accent()};")
        return label

    def _delete_button(self, lay, on_click, caption: str = "Remove") -> None:
        row = QHBoxLayout()
        button = QPushButton(caption)
        button.clicked.connect(lambda _=False: on_click())
        row.addWidget(button)
        row.addStretch(1)
        lay.addLayout(row)

    # ------------------------------------------------------------------ #
    # Backgrounds — one editor, two regimes
    # ------------------------------------------------------------------ #

    def _bg_catalog(self):
        """The catalogue, filtered by splat. ⚠ The origin controls `excluded_origins`. For
        example, only an ancient Dragon King can see the Savant Background. A modern Dragon
        King must not see it."""
        return validate.background_catalogue_for(self._ruleset, self._char())

    def _bg_type(self, bg, catalog):
        """The catalogue entry that a row names. Returns None for free text. ⚠ Resolve the
        name through the SPLAT-FILTERED catalogue. Thus a Dragon-Blooded Manse row finds
        the Dragon-Blooded allowance, not the corebook allowance. The six Manse variants
        share two names, thus a global lookup by name returns the first copy that it
        finds."""
        return {t.name.strip().lower(): t
                for t in catalog}.get(bg.name.strip().lower())

    def _background_editor(self, lay, bg, idx, b) -> None:
        """One Background in the detail pane. It shows the name, the rating, the note, the
        hearthstones and the printed text. The printed text is the description and the full
        dot LADDER, with the rung of the character marked.

        ⚠ The printed text of a Background is different for each rating. Thus one paragraph
        is not sufficient. `view.background_ladder` is the one copy of that rendering, and
        the catalogue dialog uses it too. Do not write a second copy here.
        """
        ruleset, char = self._ruleset, self._char()
        locked = self._locked()
        catalog = self._bg_catalog()
        descriptions = {t.name: t.description for t in catalog}

        combo = _FilterCombo()
        combo.setEditable(True)
        for name in [t.name for t in catalog]:
            combo.addItem(name)
        combo.setCurrentText(bg.name)
        self._labelled(lay, "Background", combo)

        rung = self._muted("", italic=True)
        stones_sync = [None]

        def sync() -> None:
            """Repaint every widget that reads the NAME and the RATING of this row. ⚠ Call
            each consumer of a Background rating from here. A consumer that this function
            does not call shows an old value."""
            rung_text = viewmod.background_rung(catalog, bg.name, bg.rating)
            # A book of a splat can separate what the user BUYS from what the Background is
            # WORTH. Mountain Folk Resources is dots + 2, with a maximum of 3 dots.
            effective = validate.effective_background_rating(ruleset, char, bg.name)
            if effective != bg.rating:
                note_text = f"effective {bg.name} {effective}"
                rung_text = f"{rung_text}  ·  {note_text}" if rung_text else note_text
            # The link to the Gear tab, which holds the artifacts. This Background PAYS for
            # them. Thus this line names what the Background bought.
            if bg.name.strip().lower() == artifactsmod.ARTIFACT_BACKGROUND:
                owned = len(artifactsmod.budgeted_items(char))
                buys = f"buys {bg.rating} dot(s) of artifacts · {owned} owned"
                rung_text = f"{rung_text}  ·  {buys}" if rung_text else buys
            rung.setText(rung_text)
            rung.setVisible(bool(rung_text))
            if stones_sync[0] is not None:
                stones_sync[0]()
            self._refresh_selected_row()
            self._changed()

        if locked:
            # ⚠ Read the maximum from the engine. Do not write 5 in the code. After the
            # lock, the `bind_post_lock` rules apply and no others: a Sidereal Celestial
            # Manse is 3 or less, and a Mountain Folk Artifact is 10 or less. Thus the story
            # can give Backing 4 to a locked Unenlightened Mountain Folk, and it can give an
            # artifact to a mortal.
            spin = QSpinBox()
            spin.setRange(0, validate.background_rating_cap(b, char, bg.name,
                                                            post_lock=True))
            spin.setValue(bg.rating)
            spin.valueChanged.connect(
                lambda v, bg=bg: (setattr(bg, "rating", v), sync()))
            self._labelled(lay, "Rating", spin)
        else:
            # ⚠ There is ONE copy of the limit rule. The spin box of the add dialog also
            # calls `_bg_cap_for`. A second implementation here gives two different limits.
            self._labelled(lay, "Rating",
                           DotTrack(lambda bg=bg: bg.rating,
                                    lambda v, bg=bg: setattr(bg, "rating", v),
                                    0, self._bg_cap_for(b, bg.name),
                                    accent=self._accent(), on_change=sync))

        note = QLineEdit(bg.note)
        note.setPlaceholderText("note")
        note.textChanged.connect(
            lambda t, bg=bg: (setattr(bg, "note", t), self._refresh_selected_row()))
        self._labelled(lay, "Note", note)

        # ⚠ Put the Demesne toggle on every Background that CAN have hearthstones, and also
        # on a Background that the user has already set to Demesne. If you remove it, the
        # user cannot set the Background back. Put the picker only on a row that has
        # hearthstones.
        bg_type = self._bg_type(bg, catalog)
        if artifactsmod.grows_hearthstones(bg_type):
            demesne = QCheckBox("Demesne rather than Manse — grows no Hearthstones")
            demesne.setChecked(bg.is_demesne)
            demesne.toggled.connect(
                lambda on, bg=bg: (setattr(bg, "is_demesne", bool(on)), self.reload()))
            lay.addWidget(demesne)
        if (not bg.is_demesne) and artifactsmod.grows_hearthstones(bg_type):
            stones = QPushButton("Hearthstones…")
            stones.clicked.connect(lambda _=False, bg=bg: self._open_hearthstones(bg))
            lay.addWidget(stones)

        # ⚠ Show the hearthstones on every row that holds one. Also show them on a row that
        # the user set to Demesne, and on a row that the user renamed from a Manse. Thus a
        # stone that has no Manse stays visible, and the user can delete it. If you hide it,
        # it becomes an Issue with no control.
        if bg.hearthstones:
            stones_sync[0] = self._hearthstone_rows(lay, bg, catalog)

        self._delete_button(lay, lambda idx=idx: self._remove_bg(idx))

        text = descriptions.get(bg.name, "")
        if text:
            lay.addWidget(self._muted(text))
        lay.addWidget(rung)
        ladder = viewmod.background_ladder(catalog, bg.name)
        if ladder:
            lay.addWidget(self._heading("What each rating buys"))
            for rating, (dots, line) in enumerate(ladder):
                entry = QLabel(f"{dots}  {line}")
                entry.setWordWrap(True)
                held = rating == bg.rating
                entry.setStyleSheet(f"color:{self._accent()}; font-weight:600;" if held
                                    else f"color:{MUTED};")
                lay.addWidget(entry)

        # A dropdown selection changes the controls that the entry needs, because a Manse
        # has hearthstones. Thus a selection rebuilds the pane. ⚠ Typing must NOT rebuild
        # it. A rebuild replaces the combo box that the user types into.
        combo.editTextChanged.connect(
            lambda t, bg=bg: (setattr(bg, "name", t), sync()))
        combo.activated.connect(lambda _i: self.reload())
        sync()

    def _refresh_selected_row(self) -> None:
        """Draw the selected table row again after an edit. ⚠ Never refill the full table. A
        refill replaces the widget that the user types into."""
        table = self._current_table()
        item = None if table is None else table.currentItem()
        if item is None or self._selected is None:
            return
        list_name, index = self._selected
        owner = getattr(self._char(), list_name)
        if not (0 <= index < len(owner)):
            return
        row = owner[index]
        if list_name == "backgrounds":
            item.setText(0, row.name or "—")
            item.setText(1, _DOTS_FILLED(row.rating))
            item.setText(2, row.note)
        elif list_name == "merits_flaws":
            item.setText(0, self._held_name(row).replace("  (custom)", ""))
            item.setText(3, row.detail or row.arena)
        else:
            item.setText(0, row.name or "—")
            item.setText(2, _DOTS_FILLED(row.rating))

    def _hearthstone_rows(self, lay, bg, catalog):
        """The hearthstones on one Manse row, and a total against the allowance. Returns the
        sync function of that total. ⚠ The caller must also call this function when the
        rating of the row changes. BOTH parts of "4 / 3" move: the first number changes when
        the user adds a stone or changes its rating, and the second number changes with the
        Manse rating. A larger Manse makes a stone legal that was above the allowance."""
        char = self._char()
        total = QLabel("")
        total.setContentsMargins(24, 0, 0, 0)

        def sync_total() -> None:
            allowance = (None if bg.is_demesne
                         else artifactsmod.hearthstone_allowance(
                             self._bg_type(bg, catalog), bg.rating))
            if allowance is None:
                total.setVisible(False)
                return
            total.setVisible(True)
            held = artifactsmod.hearthstone_total(bg)
            over = held > allowance.combined_max
            total.setText(f"Hearthstones: {held} / {allowance.combined_max} levels")
            total.setStyleSheet("color:%s;" % ("#b91c1c" if over else MUTED)
                                + (" font-weight:600;" if over else ""))

        for sidx, stone in enumerate(bg.hearthstones):
            row = QHBoxLayout()
            row.setContentsMargins(24, 0, 0, 0)
            name = QLineEdit(stone.name)
            name.setPlaceholderText("Hearthstone")
            name.textChanged.connect(lambda t, s=stone: setattr(s, "name", t))
            row.addWidget(name, 1)
            rating = QSpinBox()
            rating.setRange(0, 5)
            rating.setValue(stone.rating)
            rating.valueChanged.connect(
                lambda v, s=stone: (setattr(s, "rating", v), sync_total()))
            row.addWidget(rating)
            drop = QPushButton("✕")
            drop.clicked.connect(
                lambda _=False, bg=bg, sidx=sidx: (bg.hearthstones.pop(sidx),
                                                   self.reload()))
            row.addWidget(drop)
            lay.addLayout(row)
        lay.addWidget(total)
        sync_total()
        return sync_total

    def _open_hearthstones(self, bg) -> None:
        """The Hearthstone picker for one Manse row. Each stone shows its COST against the
        remaining allowance of the row. ⚠ Read the same `hearthstone_allowance` that the
        validator reads. Thus the picker and the Issue always agree."""
        ruleset = self._ruleset
        catalog = self._bg_catalog()
        stones = artifactsmod.hearthstones(ruleset.artifact_catalog)
        allowance = artifactsmod.hearthstone_allowance(self._bg_type(bg, catalog),
                                                       bg.rating)
        held = artifactsmod.hearthstone_total(bg)
        remaining = max(0, allowance.combined_max - held) if allowance else 0
        rows = []
        for s in stones:
            over = s.rating > remaining or (allowance and allowance.individual_max
                                            and s.rating > allowance.individual_max)
            # ⚠ Put the over-allowance warning FIRST. The dialog cuts the summary of a row
            # to a few words. Thus it removes text at the end of the description, and this
            # warning is the part that must stay.
            note = "⚠ exceeds this Manse's remaining levels — " if over else ""
            rows.append((s.name, s.name,
                         f"{note}{s.rating_notes or ('•' * s.rating)} — {s.description}",
                         s.description))
        ratings = {s.name: s.rating for s in stones}

        def pick(name) -> None:
            # Custom, where the name is None, adds a blank stone. It must not do nothing. A
            # Hearthstone is unique to its Manse (S&S p.67), and the ten printed stones are
            # examples. Thus a stone of the user's own design is the usual case. It gets a
            # rating control, because the rule measures the rating.
            bg.hearthstones.append(HearthstoneEntry(
                name="" if name is None else name,
                rating=1 if name is None else ratings.get(name, 1)))
            self.reload()

        open_catalogue(self, self._pal(), "Hearthstones", rows, pick)

    # ⚠ Each `_build_*_dialog` returns the dialog and does NOT run it. The `_open_*` wrapper
    # runs it. `exec()` stops a headless run. Thus a test reaches the rating control and the
    # tier control in the dialog through the builder only.
    def _open_bg_catalogue(self) -> None:
        self._build_bg_dialog().exec()

    def _build_bg_dialog(self) -> CatalogueDialog:
        """Show the catalogue that the splat filter gives, set the rating, and add the
        entry. The Custom button adds a blank row. The user SELECTS a rating in this dialog.
        Thus its full text holds the printed ladder, and the spin box is below that text.
        The row shows the rung of the character only."""
        catalog = self._bg_catalog()
        rows = []
        for t in sorted(catalog, key=lambda t: t.name):
            ladder = viewmod.background_ladder(catalog, t.name)
            full = t.description + (
                "\n\n" + "\n\n".join(f"{dot}  {text}" for dot, text in ladder)
                if ladder else "")
            rows.append((t.name, t.name, t.description, full))

        b = validate.effective_budgets(self._ruleset, self._char())
        holder: dict = {}

        def extras(key, lay) -> None:
            # ⚠ The limit belongs to the NAME, and it can be 0. A Flaw can refuse a
            # Background. A spin box with a maximum of 0 is the correct control. The confirm
            # hook refuses the entry, thus the dialog can state the reason.
            cap = self._bg_cap_for(b, key)
            self._pending_bg.clear()
            self._pending_bg.update(name=key, rating=min(1, cap))
            row = QHBoxLayout()
            row.addWidget(QLabel("Rating"))
            spin = QSpinBox()
            spin.setRange(0, max(0, cap))
            spin.setValue(self._pending_bg["rating"])
            spin.valueChanged.connect(
                lambda v: (self._pending_bg.update(rating=v), _resync(holder)))
            row.addWidget(spin)
            row.addStretch(1)
            lay.addLayout(row)
            if cap == 0:
                lay.addWidget(self._warn("A Flaw this character holds bars this "
                                         "Background entirely."))
            else:
                lay.addWidget(self._muted(f"Highest this character may take: {cap}"))

        def confirm(key) -> tuple[str, bool]:
            if self._bg_cap_for(b, key) == 0:
                return "Barred by a Flaw", False
            rating = self._pending_bg.get("rating", 1)
            return f"Add at {'•' * rating if rating else '0'}", True

        dialog = CatalogueDialog(self._pal(), "Backgrounds", rows, self._pick_bg,
                                 extras=extras, confirm=confirm, parent=self)
        holder["dialog"] = dialog
        return dialog

    def _bg_cap_for(self, b, name: str) -> int:
        """The highest rating for `name`. It is the same answer that
        `_backgrounds_panel.cap_for` gives. It is the smaller of two values: the refusal or
        the lowered limit of `engine.merits`, and the data limit of `engine.validate`."""
        mf = meritsmod.merits_and_flaws_calc(self._ruleset, self._char())
        key = (name or "").strip().lower()
        if key in mf.barred_backgrounds:
            return 0
        data_cap = validate.background_rating_cap(b, self._char(), name)
        merit_cap = mf.background_caps.get(key)
        return data_cap if merit_cap is None else min(data_cap, merit_cap)

    def _pick_bg(self, name) -> None:
        # A custom row starts at 1. It has no printed ladder that gives a rating. The user
        # sets the rating on the dot track of the row.
        pending = self._pending_bg if self._pending_bg.get("name") == name else {}
        self._char().backgrounds.append(BackgroundEntry(
            name="" if name is None else name,
            rating=1 if name is None else pending.get("rating", 1)))
        self._pending_bg.clear()
        self.reload()

    def _remove_bg(self, idx: int) -> None:
        del self._char().backgrounds[idx]
        self.reload()

    # ------------------------------------------------------------------ #
    # Merits & Flaws — the shared filter bar
    # ------------------------------------------------------------------ #

    def _available_merits(self, essence_start=None) -> list:
        """Every entry that this character can take. The Merits come first, then the Flaws,
        and each group is in name order. ⚠ The engine supplies the splat, caste and Essence
        filter. Do not write that filter here."""
        char = self._char()
        return [m for m in sorted(self._ruleset.merits_flaws.values(),
                                  key=lambda m: (m.kind != "merit", m.name))
                if validate.merit_available_to(m, char.exalt_type, char.caste,
                                               origin=char.origin,
                                               starting_essence=essence_start)]

    def _mf_matches(self, m) -> bool:
        """True when this entry passes the filter bar. ⚠ An entry with two sides passes BOTH
        side filters, because it is a Merit or a Flaw. If it fails both filters, the user
        cannot find it. The text filter matches the name, the category and the rules
        text."""
        want = self._mf_filter["kind"]
        if want and m.kind not in (want, "either"):
            return False
        if self._mf_filter["category"] and m.category != self._mf_filter["category"]:
            return False
        text = self._mf_filter["text"].strip().lower()
        if text:
            hay = f"{m.name} {m.category or ''} {m.description or ''}".lower()
            if text not in hay:
                return False
        return True

    # ⚠ This page has no filter bar, and that is intended. The filter belongs where the user
    # selects an entry. Thus the two catalogue dialogs hold the category CHIPS (`group_of`)
    # and their own search box. `_mf_matches` stays, and it still controls what a dialog
    # offers. No control sets `_mf_filter`, thus `_mf_matches` accepts every entry. A dialog
    # that filters itself needs that behaviour.

    def _merit_rules_text(self, lay, definition, *, with_description: bool = True) -> None:
        """The printed cost line, the restrictions, the requirements and the rules text
        below a row. ⚠ Always show the cost line. The engine cannot price some qualifiers,
        for example a rate for each caste or a relative rate. Thus the Storyteller must read
        what the book states.

        `with_description=False` removes the rules text at the end. The catalogue dialog
        uses that form, because its detail pane already shows the same text in full. ⚠ The
        same text two times, one copy scrollable and one copy cut, is a defect. The cost
        line, the restriction line and the requires line are NOT in the detail pane, thus
        they stay."""
        if definition.cost_note:
            lay.addWidget(self._muted(definition.cost_note))
        if definition.exalt_types:
            lay.addWidget(self._muted("Restricted to: " + ", ".join(definition.exalt_types),
                                      italic=True))
        # The requirements of the entry. Thus the user reads them BEFORE the issues panel
        # reports a failure. ⚠ `view.py` builds this text. Thus the two shells state the
        # same requirements. Both shells omitted `prerequisites` when each built its own.
        wants = viewmod.merit_requirement_line(
            self._ruleset, definition,
            meritsmod.merits_and_flaws_calc(self._ruleset, self._char()))
        if wants:
            lay.addWidget(self._muted("Requires: " + wants, italic=True))
        if with_description and definition.description:
            # ⚠ Show the WHOLE text. Do not cut it. This detail pane is a scrolling half of
            # a splitter, and the Backgrounds pane next to it prints its description in
            # full. A cut rules text with the rest in a TOOLTIP reads as a defect (human's
            # ruling).
            lay.addWidget(self._muted(" ".join(definition.description.split())))

    # ------------------------------------------------------------------ #
    # Merits & Flaws — chargen
    # ------------------------------------------------------------------ #

    def _chargen_merit_notes(self, notes, eff, b) -> None:
        """The bonus-point arithmetic, above the table it describes.

        A MERIT costs bonus points. A FLAW gives bonus points. Thus this panel reports the
        grant as its own number. It does not report it as a negative cost.
        """
        ruleset, char = self._ruleset, self._char()
        spent = validate.merit_bonus_point_cost(ruleset, char)
        line = f"−{spent} bonus points spent"
        if eff.bonus_point_grant:
            line += f", +{eff.bonus_point_grant} granted by Flaws"
        notes.addWidget(self._muted(line))
        # "Characters with more than 10 points of Flaws receive no bonus points for the
        # excess" (PG p.17). ⚠ Show this line when the limit applies. The grant above is the
        # LIMITED number. A user who took 13 points and reads "+10" cannot identify the
        # limit without this line.
        if eff.flaw_points_raw > eff.bonus_point_grant:
            notes.addWidget(self._warn(
                f"⚠ {eff.flaw_points_raw} points of Flaws taken, "
                f"{eff.bonus_point_grant} granted — the excess "
                f"{eff.flaw_points_raw - eff.bonus_point_grant} is lost to the "
                f"{meritsmod.FLAW_POINT_CAP}-point cap (p.17). The Flaws still apply."))
        # Name the Merits that this build treats as narrative. Without this line, the user
        # cannot find the reason that nothing changed.
        if eff.narrative_only:
            names = ", ".join(sorted(ruleset.merits_flaws[m].name
                                     for m in eff.narrative_only
                                     if m in ruleset.merits_flaws))
            if names:
                notes.addWidget(self._muted(
                    f"Narrative only in this build: {names}.", italic=True))

    def _merit_editor(self, lay, mp, idx, b) -> None:
        """One held Merit or Flaw in the detail pane.

        ⚠ Put every control on its own line, with a label. Qt has no wrapping row, and a
        narrow panel needs two horizontal rows. A detail pane is wide, thus it does not need
        that arrangement.

        After the lock, the entry is READ-ONLY. The user does not exchange a held Merit for
        another one. The user drops it from the toolbar and gains a new one. After the lock,
        this pane adds the printed rules text of the entry that the character holds.
        """
        ruleset, char = self._ruleset, self._char()
        locked = self._locked()
        definition = ruleset.merits_flaws.get(mp.merit_id)

        # A "Custom" row that the user writes. It has no catalogue entry and no mechanical
        # effect. It is a name that the sheet prints. It gets a plain text input, and NONE
        # of the controls that read `definition`.
        # ⚠ An EMPTY `merit_id` identifies this row. Never test `custom_name` for a value.
        # The name input below writes that field on each keystroke.
        if not mp.merit_id:
            lay.addWidget(self._muted("Custom Merit / Flaw — narrative only."))
            name = QLineEdit(mp.custom_name)
            name.textChanged.connect(
                lambda t, mp=mp: (setattr(mp, "custom_name", t),
                                  self._refresh_selected_row(), self._changed()))
            self._labelled(lay, "Name", name)
            if not locked:
                self._delete_button(lay, lambda idx=idx: self._remove_merit(idx))
            return

        if locked:
            self._labelled(lay, "Entry", QLabel(
                definition.name if definition is not None else mp.merit_id))
        else:
            available = self._available_merits(b.essence_start)
            labels = {m.id: viewmod.merit_option_label(m) for m in available}
            # ⚠ Keep the value that the row holds in the list. An id that the catalogue does
            # not hold, for example from a save that opened without its data, must stay in
            # its own dropdown.
            opts = dict(labels)
            if mp.merit_id:
                opts.setdefault(mp.merit_id, labels.get(mp.merit_id, mp.merit_id))
            combo = QComboBox()
            for key, label in opts.items():
                combo.addItem(label, key)
            found = combo.findData(mp.merit_id)
            combo.setCurrentIndex(found if found >= 0 else -1)
            combo.currentIndexChanged.connect(
                lambda _i, mp=mp, c=combo: self._set_merit(mp, c.currentData() or ""))
            self._labelled(lay, "Entry", combo)
            self._mf_rows.append((combo, mp))

        if definition is None:
            lay.addWidget(self._muted(
                "Not in the rule set — the data that defined it is missing."))
            if not locked:
                self._delete_button(lay, lambda idx=idx: self._remove_merit(idx))
            return

        if locked:
            # A read-only summary of the recorded choices. After the lock, the Drop action
            # in the toolbar is the only mutation.
            side = mp.taken_as or definition.kind
            self._labelled(lay, "Taken as", QLabel(side))
            if mp.tier:
                self._labelled(lay, "Buying",
                               QLabel(viewmod.merit_tier_label(mp.tier)))
            if mp.points:
                self._labelled(lay, "Points", QLabel(str(mp.points)))
            if mp.arena:
                self._labelled(lay, "Arena", QLabel(mp.arena))
            if mp.detail:
                self._labelled(lay, "Applies to", QLabel(mp.detail))
            self._merit_rules_text(lay, definition)
            return

        # The side that the user selected for an entry with two sides. ⚠ Do not select a
        # default. This value decides if the entry costs bonus points or gives them. Thus
        # the user must select it. An unrecorded choice shows an empty control, and
        # `validate` reports it.
        if definition.kind == "either":
            side = QComboBox()
            side.addItem("", "")
            side.addItem("as Merit", "merit")
            side.addItem("as Flaw", "flaw")
            side.setCurrentIndex(max(0, side.findData(mp.taken_as or "")))
            side.currentIndexChanged.connect(
                lambda _i, mp=mp, s=side: (setattr(mp, "taken_as", s.currentData() or ""),
                                           self.reload()))
            self._labelled(lay, "Taken", side)
        if definition.cost_options:
            # Offer the options that this splat can select, and price them from the table
            # that the pricer reads. Lucky is 1-5, and it is 1-3 for a Sidereal. ⚠ Keep a
            # tier that the row already holds in the list.
            opts = validate.merit_cost_options(definition, char.exalt_type, char.caste)
            tiers = validate.merit_tiers_available(definition, char.exalt_type, char.caste)
            tier_opts = {t: f"{viewmod.merit_tier_label(t)} ({v})"
                         for t, v in opts.items() if t in tiers}
            if mp.tier:
                tier_opts.setdefault(
                    mp.tier,
                    f"{viewmod.merit_tier_label(mp.tier)} ({opts.get(mp.tier, '?')})")
            tier = QComboBox()
            for key, label in tier_opts.items():
                tier.addItem(label, key)
            tier.setCurrentIndex(max(0, tier.findData(mp.tier)))
            tier.currentIndexChanged.connect(
                lambda _i, mp=mp, t=tier: (setattr(mp, "tier", t.currentData() or ""),
                                           self._refresh_selected_row(), self._changed()))
            self._labelled(lay, "Oath" if meritsmod.uses_arena(definition) else "Buying",
                           tier)
            # The arena drives the stacking reduction for the same arena (p.122). It is free
            # text, because the list on the page gives examples, not a closed set. Show this
            # control for the entry with that rule only.
            if meritsmod.uses_arena(definition):
                arena = QLineEdit(mp.arena)
                arena.setPlaceholderText("arena (combat, food…)")
                arena.textChanged.connect(
                    lambda t, mp=mp: (setattr(mp, "arena", t),
                                      self._refresh_selected_row(), self._changed()))
                self._labelled(lay, "Arena", arena)
        elif definition.variable_cost:
            # The value of a variable-cost entry belongs to the PURCHASE, because the page
            # leaves it to the table. ⚠ Without this control, the value stays 0. All eleven
            # of these entries then do nothing at chargen: no bonus points, and no effect.
            rate = meritsmod.forfeit_rate(definition)
            spin = QSpinBox()
            spin.setRange(0, 20)
            if rate:
                # ⚠ Collect the DOTS and multiply them. Do not collect points and divide
                # them. The user selects the dots: "three points for every Physical
                # Attribute dot". An entry in points can lose a remainder.
                spin.setValue(mp.points // rate)
                spin.valueChanged.connect(
                    lambda v, mp=mp, r=rate: (setattr(mp, "points", v * r),
                                              self._refresh_selected_row(),
                                              self._changed()))
                self._labelled(
                    lay, f"{meritsmod.forfeit_trait_label(definition)} dots", spin)
            else:
                spin.setValue(mp.points)
                spin.valueChanged.connect(
                    lambda v, mp=mp: (setattr(mp, "points", v),
                                      self._refresh_selected_row(), self._changed()))
                self._labelled(lay, "Points", spin)
        # The artifact that a per-entry limit measures, for example Damaged Artifact. ⚠ Read
        # the `per_entry` flag of the catalogue. Never read the id of the entry
        # (decision 0011).
        if any(limit.per_entry for limit in definition.points_limits):
            items = artifactsmod.artifact_items(char)
            art = QComboBox()
            art.addItem("", "")
            for item in items:
                art.addItem(f"{item.name} ({item.rating})", item.key)
            # ⚠ Keep a key that does not resolve, because the user renamed or deleted the
            # artifact. Mark it as broken. It must not go away without a message.
            if mp.artifact_key and art.findData(mp.artifact_key) < 0:
                art.addItem(f"{mp.artifact_key}  (missing)", mp.artifact_key)
            art.setCurrentIndex(max(0, art.findData(mp.artifact_key or "")))
            art.currentIndexChanged.connect(
                lambda _i, mp=mp, a=art: (setattr(mp, "artifact_key", a.currentData() or ""),
                                          self._changed()))
            self._labelled(lay, "Artifact", art)
            if not items:
                lay.addWidget(self._warn("no artifacts owned"))
        # A stipulation is a number of dots, thus this control is a number, not a note: "an
        # extra dot … for every major stipulation applied to the Inheritance, up a maximum
        # of three" (p.24).
        if definition.takes_stipulations:
            stip = QSpinBox()
            stip.setRange(0, 3)
            stip.setValue(mp.stipulations)
            stip.valueChanged.connect(
                lambda v, mp=mp: (setattr(mp, "stipulations", v), self._changed()))
            self._labelled(lay, "Stipulations", stip)
        # ⚠ A structured detail is a CLOSED set. It is not free text. Examples: the Attribute
        # category that a forfeit comes from, and the Attribute that Legendary Attribute
        # raises. As free text, both of these fail and report no error.
        choices = meritsmod.detail_choices(definition)
        if choices:
            detail = QComboBox()
            detail.addItem("", "")
            for c in choices:
                detail.addItem(c, c)
            # ⚠ A stored detail can be outside the list, and that is legal. `validate`
            # compares `detail.strip().title()`. Thus "strength" passes validation, and it
            # never matches the option in title case. Normalise the value in the same way.
            # Then keep each value that does not match as its own option.
            current = mp.detail.strip().title() if mp.detail else ""
            if mp.detail and detail.findData(current) < 0:
                current = mp.detail
                detail.addItem(f"{current}  (not a choice)", current)
            detail.setCurrentIndex(max(0, detail.findData(current)))
            detail.currentIndexChanged.connect(
                lambda _i, mp=mp, d=detail: (setattr(mp, "detail", d.currentData() or ""),
                                             self._refresh_selected_row(),
                                             self._changed()))
            self._labelled(lay, "Applies to", detail)
        else:
            note = QLineEdit(mp.detail)
            note.setPlaceholderText(definition.repeatable_by or "note")
            note.textChanged.connect(
                lambda t, mp=mp: (setattr(mp, "detail", t),
                                  self._refresh_selected_row(), self._changed()))
            self._labelled(lay, "Note", note)
        self._delete_button(lay, lambda idx=idx: self._remove_merit(idx))
        self._merit_rules_text(lay, definition)

    def _set_merit(self, mp, merit_id: str) -> None:
        # ⚠ A change to the entry clears every value of the old entry. The side, the tier,
        # the points, the arena and the detail each belong to one entry. A value that stays
        # gives the wrong price, and it reports no error. The tier takes the first AVAILABLE
        # option of the new entry, not a blank value. Thus a row never holds a tier that
        # does not exist, or a tier that this splat cannot take.
        char = self._char()
        mp.merit_id = merit_id or ""
        mp.tier = viewmod.default_merit_tier(self._ruleset.merits_flaws.get(mp.merit_id),
                                             char.exalt_type, char.caste)
        mp.taken_as, mp.points, mp.detail, mp.arena = "", 0, "", ""
        mp.stipulations = 0
        self.reload()

    def _remove_merit(self, idx: int) -> None:
        del self._char().merits_flaws[idx]
        self.reload()

    def _open_mf_catalogue(self, available) -> None:
        self._build_mf_dialog(available).exec()

    def _build_mf_dialog(self, available) -> CatalogueDialog:
        """Show the filtered set, configure an entry, and take it. The Custom button adds a
        row that the user writes, and that row has no mechanical effect. ⚠ Never add the
        cheapest entry without a selection. The tier, points and side controls are the same
        block that the in-play card uses. Thus the row is fully specified, and it does not
        take a default tier that the user did not see."""
        rows = [(m.id, viewmod.merit_option_label(m), m.description, m.description)
                for m in available]
        holder: dict = {}
        # ⚠ The category chips are the filter for this page. The filter belongs where the
        # user selects an entry. It does not belong next to the list of entries that the
        # character holds. The five printed categories give five chips, and the search box
        # of the dialog supplies the text filter.
        groups = {m.id: m.category for m in available if m.category}

        def extras(key, lay) -> None:
            definition = self._ruleset.merits_flaws.get(key)
            if definition is None:
                return
            char = self._char()
            self._pending_mf.clear()
            self._pending_mf.update(
                id=key, taken_as="", points=0, detail="",
                tier=viewmod.default_merit_tier(definition, char.exalt_type, char.caste))
            self._mf_purchase_block(
                definition, lay, self._pending_mf,
                on_sync=lambda: _resync(holder))
            self._merit_rules_text(lay, definition, with_description=False)

        def confirm(key) -> tuple[str, bool]:
            definition = self._ruleset.merits_flaws.get(key)
            if definition is None:
                return "Take", False
            if self._mf_side_needed(definition, self._pending_mf):
                return "Choose Merit or Flaw first", False
            points, _xp = self._mf_price(definition, self._pending_mf)
            return f"Take ({points} points)", True

        dialog = CatalogueDialog(
            self._pal(), "Merits & Flaws", rows, self._pick_mf,
            subtitle=f"{len(available)} available to this character",
            group_of=groups, extras=extras, confirm=confirm, parent=self)
        holder["dialog"] = dialog
        return dialog

    def _pick_mf(self, key) -> None:
        char = self._char()
        if key is None:
            # `merit_id` is a required field, and this code leaves it empty. It resolves to
            # nothing in the catalogue, thus the engine skips the row. That gives the "no
            # mechanical effect" that the Custom option states.
            char.merits_flaws.append(
                MeritFlawPurchase(merit_id="", custom_name="New custom Merit / Flaw"))
            self.reload()
            return
        definition = self._ruleset.merits_flaws.get(key)
        if definition is None:
            return
        # The controls of the dialog have already set these values. Use the default tier of
        # the splat for a caller that selects an entry without those controls. The tests do
        # that.
        pending = self._pending_mf if self._pending_mf.get("id") == key else {}
        char.merits_flaws.append(MeritFlawPurchase(
            merit_id=key,
            tier=pending.get("tier") or viewmod.default_merit_tier(
                definition, char.exalt_type, char.caste),
            taken_as=pending.get("taken_as", ""),
            points=pending.get("points", 0),
            detail=pending.get("detail", "")))
        self._pending_mf.clear()
        self.reload()

    # ------------------------------------------------------------------ #
    # Merits & Flaws — in play
    # ------------------------------------------------------------------ #

    def _held_name(self, mp) -> str:
        if mp.custom_name:
            return mp.custom_name + "  (custom)"
        name = (self._ruleset.merits_flaws[mp.merit_id].name
                if mp.merit_id in self._ruleset.merits_flaws else mp.merit_id)
        return name + (f" ({mp.tier})" if mp.tier else "")

    def _open_gain_catalogue(self, available) -> None:
        self._build_gain_dialog(available).exec()

    def _build_gain_dialog(self, available) -> CatalogueDialog:
        """Show, configure and BUY an entry in one dialog. The tier, the point value and the
        Merit-or-Flaw side are next to the printed text of the entry, and the confirm button
        shows the XP cost. ⚠ Thus a purchase never comes from a menu label alone. With the
        controls on a card below the visible area, a selection appears to do nothing."""
        rows = [(m.id, f"{m.name} {m.cost_note or ''}".strip(), m.description,
                 m.description)
                for m in available if self._mf_matches(m)]
        holder: dict = {}
        # See `_build_mf_dialog`: the page's old filter bar became these chips.
        groups = {m.id: m.category
                  for m in available if m.category and self._mf_matches(m)}

        def extras(key, lay) -> None:
            definition = self._ruleset.merits_flaws.get(key)
            if definition is None:
                return
            # A new selection starts a new purchase. Each value belongs to one entry. ⚠ A
            # tier that stays from the previous row gives the wrong price, and it reports no
            # error. `_set_merit` clears its values for the same reason.
            self._gain.clear()
            self._gain.update(id=key, taken_as="", tier="", points=0, detail="")
            self._mf_purchase_block(
                definition, lay, self._gain,
                on_sync=lambda: _resync(holder))
            self._merit_rules_text(lay, definition, with_description=False)

        def confirm(key) -> tuple[str, bool]:
            definition = self._ruleset.merits_flaws.get(key)
            if definition is None:
                return "Gain", False
            if self._mf_side_needed(definition, self._gain):
                return "Choose Merit or Flaw first", False
            _points, xp = self._mf_price(definition, self._gain)
            side = self._gain.get("taken_as") or definition.kind
            return (f"Gain — pays {xp} XP" if side == "flaw"
                    else f"Gain for {xp} XP"), True

        dialog = CatalogueDialog(
            self._pal(), "Merits & Flaws", rows, self._pick_gain,
            subtitle=f"{len(rows)} available to this character",
            group_of=groups, extras=extras, confirm=confirm, parent=self)
        holder["dialog"] = dialog
        return dialog

    def _pick_gain(self, key) -> None:
        """Commit the purchase that the dialog confirmed. The extras controls have already
        specified every value in `self._gain`."""
        if key is None:
            self._custom_gain()
            return
        self._gain_mf()

    def _custom_gain(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Custom Merit / Flaw")
        lay = QVBoxLayout(dialog)
        lay.addWidget(self._muted("Display-only — recorded on the sheet, no mechanical "
                                  "effect."))
        name = QLineEdit()
        name.setPlaceholderText("name (e.g. a bloodline trait)")
        lay.addWidget(name)

        def go() -> None:
            text = name.text().strip()
            if not text:
                self._notify("Give the custom Merit / Flaw a name.", "warning")
                return
            # An empty `merit_id` resolves to nothing. Thus the engine gives the row no
            # effect. That is the contract of the Custom option.
            self._char().merits_flaws.append(
                MeritFlawPurchase(merit_id="", custom_name=text))
            dialog.accept()
            self.reload()

        add = QPushButton("Add")
        add.clicked.connect(go)
        lay.addWidget(add)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(dialog.reject)
        lay.addWidget(cancel)
        dialog.exec()

    # ------------------------------------------------------------------ #
    # the shared Merit/Flaw purchase controls
    # ------------------------------------------------------------------ #

    def _mf_price(self, definition, state) -> tuple[int, int]:
        """Input: a definition and a pending-purchase `state` dict. Output:
        `(points, xp)` for that entry at the selected tier / point value / side."""
        char = self._char()
        price = validate.merit_points(
            definition,
            MeritFlawPurchase(merit_id=definition.id, tier=state.get("tier", ""),
                              points=state.get("points", 0),
                              taken_as=state.get("taken_as", ""),
                              detail=state.get("detail", "")),
            char.exalt_type, char.caste)
        xp = price * self._ruleset.xp_costs_for(char.exalt_type).new_merit_bp_multiplier
        return price, xp

    def _mf_side_needed(self, definition, state) -> bool:
        """True when the entry has two sides and the user has selected no side. ⚠ The side
        makes the transaction a cost or a grant. Thus a purchase in this state is not fully
        specified, and the program must refuse it."""
        return definition.kind == "either" and not state.get("taken_as")

    def _mf_purchase_block(self, definition, lay, state, on_sync=None):
        """Build the entry-specific purchase controls into `lay`, driving the mutable
        `state` dict (taken_as / tier / points / detail). Input: the definition, a
        layout, the state, and an optional callback fired after each change. Output:
        a `sync()` callable that refreshes the banner and the price line from `state`.

        ⚠ `sync()` writes the text IN PLACE. It never rebuilds a widget. The controls call
        it from their own change signals. A delete of a widget inside its own handler causes
        a Qt crash.

        The in-play card and the catalogue dialog both use this function. Thus the two
        surfaces always give the same price for the same purchase.
        """
        char = self._char()
        head = QHBoxLayout()
        name = QLabel(definition.name)
        name.setStyleSheet("font-weight:600;")
        head.addWidget(name)
        head.addWidget(self._muted(definition.cost_note or ""))
        head.addStretch(1)
        lay.addLayout(head)

        banner = QLabel("")
        banner.setWordWrap(True)
        lay.addWidget(banner)
        price_line = self._muted("")
        controls = QHBoxLayout()

        def sync() -> None:
            # For an entry with two sides, the selected side decides if the transaction is a
            # cost or a grant. Thus it also sets this text. ⚠ With no side selected, the text
            # says so. It must not show the Merit side.
            effective = (state.get("taken_as", "") if definition.kind == "either"
                         else definition.kind)
            banner.setText(
                "Flaw — GAINING this pays the character" if effective == "flaw"
                else "Merit — gaining this costs XP" if effective == "merit"
                else "Merit OR Flaw — choose a side before gaining it")
            banner.setStyleSheet("font-weight:600; color:%s;" % (
                "#4ade80" if effective == "flaw"
                else "#d19a3a" if effective == "merit" else "#f87171"))
            points, xp = self._mf_price(definition, state)
            price_line.setText(f"At the selected tier: {points} points = {xp} XP")
            if on_sync is not None:
                on_sync()

        if definition.kind == "either":
            controls.addWidget(QLabel("Take it"))
            side = QComboBox()
            side.addItem("", "")
            side.addItem("as Merit", "merit")
            side.addItem("as Flaw", "flaw")
            side.setCurrentIndex(max(0, side.findData(state.get("taken_as", ""))))
            side.currentIndexChanged.connect(
                lambda _i, s=side: (state.update(taken_as=s.currentData() or ""), sync()))
            controls.addWidget(side)
        # The value controls. They read the entry, and they are the set that chargen offers.
        # ⚠ Do not use one free-text box for two purposes: a tier key for a menu-priced
        # entry, and a point value for a variable-cost entry. That shape caused a defect in
        # the splat filter.
        if definition.cost_options:
            opts = validate.merit_cost_options(definition, char.exalt_type, char.caste)
            tiers = validate.merit_tiers_available(definition, char.exalt_type, char.caste)
            controls.addWidget(QLabel("Oath" if meritsmod.uses_arena(definition)
                                      else "Buying"))
            tier = QComboBox()
            for key, value in opts.items():
                if key in tiers:
                    tier.addItem(f"{viewmod.merit_tier_label(key)} ({value})", key)
            tier.setCurrentIndex(max(0, tier.findData(state.get("tier") or "")))
            state["tier"] = tier.currentData() or ""
            tier.currentIndexChanged.connect(
                lambda _i, t=tier: (state.update(tier=t.currentData() or ""), sync()))
            controls.addWidget(tier)
        elif definition.variable_cost:
            # ⚠ A variable-cost entry STARTS AT ONE. It never starts at zero (human's
            # ruling). At zero, its price is nothing. A confirm then adds a row that costs
            # nothing and gives nothing, and the purchase appears to succeed. ⚠ Write the
            # start value into `state` and into the spin box. The confirm button prices
            # `state`, not the widget.
            rate = meritsmod.forfeit_rate(definition)
            spin = QSpinBox()
            spin.setRange(0, 20)
            if rate:
                controls.addWidget(QLabel(
                    f"{meritsmod.forfeit_trait_label(definition)} dots"))
                dots = (state.get("points", 0) // rate) or 1
                state["points"] = dots * rate
                spin.setValue(dots)
                spin.valueChanged.connect(
                    lambda v, r=rate: (state.update(points=v * r), sync()))
            else:
                controls.addWidget(QLabel("Points"))
                state["points"] = state.get("points", 0) or 1
                spin.setValue(state["points"])
                spin.valueChanged.connect(lambda v: (state.update(points=v), sync()))
            controls.addWidget(spin)
        choices = meritsmod.detail_choices(definition)
        if choices:
            controls.addWidget(QLabel("Applies to"))
            detail = QComboBox()
            detail.addItem("", "")
            for c in choices:
                detail.addItem(c, c)
            detail.setCurrentIndex(max(0, detail.findData(state.get("detail") or "")))
            detail.currentIndexChanged.connect(
                lambda _i, d=detail: (state.update(detail=d.currentData() or ""), sync()))
            controls.addWidget(detail)
        controls.addStretch(1)
        lay.addLayout(controls)
        lay.addWidget(price_line)
        sync()
        return sync

    def _gain_mf(self) -> None:
        """Gain a Merit or a Flaw in play. ⚠ The ENTRY decides the side of the transaction.
        The button does not. Thus `advancement.gain_merit_or_flaw` holds the branch and both
        refusals, and the web shell calls the same function."""
        if self._do(lambda: advancement.gain_merit_or_flaw(
                self._ruleset, self._char(), self._gain.get("id") or "",
                tier=self._gain.get("tier", ""),
                taken_as=self._gain.get("taken_as", ""),
                points=self._gain.get("points", 0),
                detail=self._gain.get("detail", ""))):
            self.reload()

    def _drop_mf(self) -> None:
        if self._drop_idx == "":
            self._notify("Pick a held Merit or Flaw first.", "warning")
            return
        if self._do(lambda: advancement.drop_merit(self._ruleset, self._char(),
                                                   int(self._drop_idx))):
            self.reload()

    # ------------------------------------------------------------------ #
    # Fetters and Passions (ghosts only, E:Ab p.126-127, p.283)
    # ------------------------------------------------------------------ #
    # ⚠ The two are different, and the panels must show that difference:
    #   * The user BUYS a Fetter: with pool dots, then with bonus points, then with
    #     experience.
    #   * The user NEVER buys a Passion. Its dots come from the Virtues, and the user
    #     distributes them (p.283). Thus its "pool" readout is a derivation that changes
    #     after the lock, and no control on it shows a price.

    def _has_fetters(self) -> bool:
        char = self._char()
        b = self._ruleset.budgets_for(char.exalt_type, char.origin, char.upbringing)
        return bool(b.fetter_dots or char.fetters)

    def _has_passions(self) -> bool:
        return bool(self._char().passions or self._has_fetters())

    def _fetter_editor(self, lay, fetter, idx, b) -> None:
        """One Fetter in the detail pane. Before the lock, it has a dot track that costs
        nothing. After the lock, the rating is read-only pips, and it changes through the
        priced controls only (p.283)."""
        locked = self._locked()
        name = QLineEdit(fetter.name)
        name.setPlaceholderText("what anchors you")
        name.textChanged.connect(
            lambda t, f=fetter: (setattr(f, "name", t),
                                 self._refresh_selected_row(), self._changed()))
        self._labelled(lay, "Fetter", name)
        if locked:
            pips = QLabel("●" * fetter.rating + "○" * (5 - fetter.rating))
            pips.setStyleSheet(f"color:{self._accent()};")
            self._labelled(lay, "Rating", pips)
        else:
            self._labelled(lay, "Rating",
                           DotTrack(lambda f=fetter: f.rating,
                                    lambda v, f=fetter: setattr(f, "rating", v),
                                    0, 5, accent=self._accent(),
                                    on_change=self.reload))
        note = QLineEdit(fetter.note)
        note.setPlaceholderText("note")
        note.textChanged.connect(
            lambda t, f=fetter: (setattr(f, "note", t), self._refresh_selected_row()))
        self._labelled(lay, "Note", note)
        lay.addWidget(self._fetter_budget_label(b))
        if locked:
            self._fetter_play_controls(lay)
        else:
            self._delete_button(lay, lambda idx=idx: self._remove_fetter(idx))

    def _fetter_budget_label(self, b) -> QLabel:
        """⚠ The limit is Willpower + Essence, and it CHANGES. Thus show it as a live number
        on both sides of the lock. Do not show it as a chargen note."""
        ruleset, char = self._ruleset, self._char()
        spent = derivemod.fetter_dots_spent(char)
        cap = derivemod.fetter_cap(char, ruleset)
        text = f"{spent} of {cap} dots (cap = Willpower + Essence, p.127)"
        if not self._locked():
            text += f" · {b.fetter_dots} at chargen, ≤{b.fetter_cap_pre_bp} pre-bonus"
        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet("color:#b91c1c; font-weight:600;" if spent > cap
                            else f"color:{MUTED};")
        return label

    def _passion_editor(self, lay, passion, idx, b) -> None:
        """One Passion in the detail pane.

        ⚠ Use a dot track that costs nothing, on both sides of the lock. A Passion
        distributes a DERIVED pool. Its dots come from the Virtues (E:Ab p.283), and the
        user never buys it. Thus the XP stepper of the Traits tab is incorrect here.
        """
        char = self._char()
        name = QLineEdit(passion.name)
        name.setPlaceholderText("what drives you")
        name.textChanged.connect(
            lambda t, p=passion: (setattr(p, "name", t),
                                  self._refresh_selected_row(), self._changed()))
        self._labelled(lay, "Passion", name)
        self._labelled(lay, "Virtue", QLabel(str(passion.virtue.value).title()))
        self._labelled(lay, "Rating",
                       DotTrack(lambda p=passion: p.rating,
                                lambda v, p=passion: setattr(p, "rating", v),
                                0, 5, accent=self._accent(), on_change=self.reload))
        note = QLineEdit(passion.note)
        note.setPlaceholderText("note")
        note.textChanged.connect(
            lambda t, p=passion: (setattr(p, "note", t), self._refresh_selected_row()))
        self._labelled(lay, "Note", note)

        # The pool of this Passion, for each Virtue. Thus the user reads the dots that stay
        # to distribute, and stays on the entry that they edit.
        pool = derivemod.passion_pool(char)
        left = derivemod.passion_dots_unspent(char)
        lay.addWidget(self._heading("Dots from the Virtues"))
        for virtue in VirtueName:
            if not pool[virtue] and not any(p.virtue == virtue for p in char.passions):
                continue
            remaining = left[virtue]
            colour = ("#b91c1c" if remaining < 0
                      else "#d19a3a" if remaining > 0 else "#15803d")
            line = QLabel(f"{str(virtue.value).title()}: "
                          f"{pool[virtue] - remaining} of {pool[virtue]} distributed")
            line.setStyleSheet(f"color:{colour};")
            lay.addWidget(line)
        add = QPushButton(f"+ Another {str(passion.virtue.value).title()} Passion")
        add.clicked.connect(lambda _=False, v=passion.virtue: self._add_passion(v))
        lay.addWidget(add)
        if self._locked():
            self._passion_shift_controls(lay)
        self._delete_button(lay, lambda idx=idx: self._remove_passion(idx))

    def _fetter_play_controls(self, lay) -> None:
        """Post-lock: raise, form and shift, each at its printed price (p.283)."""
        ruleset, char = self._ruleset, self._char()
        lay.addWidget(self._heading("In play"))
        row = QHBoxLayout()
        which = QComboBox()
        for f in char.fetters:
            if f.name:
                which.addItem(f.name, f.name)
        # Open on the selected Fetter. Thus Raise and Shift act on that Fetter, and not on
        # the first Fetter in the list.
        if self._selected is not None and self._selected[0] == "fetters":
            held = char.fetters[self._selected[1]].name
            found = which.findData(held)
            if found >= 0:
                which.setCurrentIndex(found)
        row.addWidget(which, 1)
        raise_btn = QPushButton("Raise")
        raise_btn.clicked.connect(lambda: self._do_reload(
            lambda: advancement.raise_fetter(ruleset, char, which.currentData() or "")))
        row.addWidget(raise_btn)
        lay.addLayout(row)

        row = QHBoxLayout()
        shift_to = QLineEdit()
        shift_to.setPlaceholderText("shift focus to…")
        row.addWidget(shift_to, 1)
        shift = QPushButton(
            f"Shift ({ruleset.xp_costs_for(char.exalt_type).shift_fetter} XP)")
        shift.clicked.connect(lambda: self._do_reload(
            lambda: advancement.shift_fetter(ruleset, char, which.currentData() or "",
                                             shift_to.text().strip())))
        row.addWidget(shift)
        lay.addLayout(row)

        row = QHBoxLayout()
        new_name = QLineEdit()
        new_name.setPlaceholderText("form a new Fetter…")
        row.addWidget(new_name, 1)
        form = QPushButton(f"Form ({costsmod.new_fetter_cost(ruleset, char)} XP)")
        form.clicked.connect(lambda: self._do_reload(
            lambda: advancement.add_fetter(ruleset, char, new_name.text().strip())))
        row.addWidget(form)
        lay.addLayout(row)

    def _do_reload(self, action) -> None:
        if self._do(action):
            self.reload()

    def _add_fetter_row(self) -> None:
        self._char().fetters.append(FetterEntry(name="", rating=1))
        self.reload()

    def _remove_fetter(self, idx: int) -> None:
        del self._char().fetters[idx]
        self.reload()

    def _passion_shift_controls(self, lay) -> None:
        """The one experience operation on a Passion (p.283, 20 XP). It moves a dot from one
        Passion to another. ⚠ The TOTAL cannot change. The Virtues set it."""
        ruleset, char = self._ruleset, self._char()
        row = QHBoxLayout()
        row.addWidget(QLabel("Shift from"))
        frm = QComboBox()
        for p in char.passions:
            if p.name:
                frm.addItem(p.name, p.name)
        row.addWidget(frm, 1)
        to = QLineEdit()
        to.setPlaceholderText("…to (new or existing)")
        row.addWidget(to, 1)
        shift = QPushButton(
            f"Shift ({ruleset.xp_costs_for(char.exalt_type).shift_passion} XP)")
        shift.clicked.connect(lambda: self._do_reload(
            lambda: advancement.shift_passion(ruleset, char, frm.currentData() or "",
                                              to.text().strip())))
        row.addWidget(shift)
        lay.addLayout(row)

    def _add_passion(self, virtue) -> None:
        self._char().passions.append(PassionEntry(name="", virtue=virtue, rating=1))
        self.reload()

    def _remove_passion(self, idx: int) -> None:
        del self._char().passions[idx]
        self.reload()
