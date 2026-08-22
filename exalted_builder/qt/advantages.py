"""exalted_builder/qt/advantages.py — the Advantages tab: Backgrounds, Merits & Flaws,
and (for the splats that have them) Fetters and Passions.

Input: a RuleSet and the shared context's Character. Output: one scrollable surface
carrying every list this tab owns, in whichever regime the character's lock state calls
for — chargen editors against the dot/bonus-point budgets, or the in-play cards that
spend experience. Mechanism: the panels are rebuilt by `reload()`; anything a keystroke
touches (a name, a note) writes straight to the model and re-syncs only its own labels,
so the widget the player is typing into is never replaced under them.

Mode comes from the character, never from the caller (`_locked`), exactly as
ui/advantages.py does:

* **pre-lock** — Backgrounds against the chargen dot budget with the pre-bonus cap;
  M&F against bonus points, a Merit charging and a Flaw granting.
* **post-lock** — Backgrounds free and story-driven with no log row; M&F through
  `advancement.gain_merit_or_flaw` / `drop_merit`, XP-priced and debt-aware.

Zero game logic: budgets, caps, prices, legality and the merit-vs-flaw side resolution
all come from the engine, and no Merit id is named here (decision 0011).
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
from .layout import clear_layout
from .editor import DotTrack, _FilterCombo
from .theme import MUTED, accent as accent_light

# The issue codes this tab can do something about. The shell's readout bar reports the
# whole list; repeating all of it here would make both readouts noise. Artifact codes
# are in because the Artifact BACKGROUND rating is edited here and the budget findings
# key off it (the Gear tab renders the same findings beside the items — one issue list,
# so the two cannot disagree).
_MY_ISSUES = ("background", "merit", "flaw", "artifact")

_MF_SIDES = {"": "All", "merit": "Merits", "flaw": "Flaws"}

_TABLE_COLUMNS = {
    "Backgrounds": ["Background", "Rating", "Note"],
    "Merits & Flaws": ["Entry", "Side", "Cost", "Detail"],
    "Fetters & Passions": ["Name", "Kind", "Rating", "Note"],
}


def _DOTS_FILLED(rating: int) -> str:
    """A rating as filled/empty pips for a table cell. ⚠ Sorts as text, which is why the
    filled pips come first — "●●○○○" orders correctly against "●○○○○"."""
    rating = max(0, min(5, int(rating or 0)))
    return "●" * rating + "○" * (5 - rating)



def _resync(holder) -> None:
    """Re-label a catalogue dialog's confirm button, if it exists yet.

    ⚠ No-op on the first pass, and that is not a guard against a bug: the dialog's
    constructor selects row 0, so `extras` runs — and syncs — before
    `CatalogueDialog.__init__` has returned and the caller could stash the reference.
    `_show_detail` labels the button itself straight afterwards, so nothing is missed.
    """
    dialog = holder.get("dialog")
    if dialog is not None:
        dialog.refresh_confirm()


class AdvantagesPage(QWidget):
    """The tab widget. `reload()` rebuilds the body for the character in ctx; `notify`
    surfaces transient messages; `on_change` pings the shell so its readout bar and
    status strip re-derive."""

    def __init__(self, ruleset, ctx, *, notify=None, on_change=None, parent=None):
        super().__init__(parent)
        self._ruleset = ruleset
        self._ctx = ctx
        self._notify = notify or (lambda text, kind="info": None)
        self._on_change = on_change
        # The pending in-play purchase — nothing is bought until Gain is pressed.
        self._gain: dict = {"id": "", "tier": "", "points": 0, "taken_as": "",
                            "detail": ""}
        # The add-dialogs' pending picks — the controls now live in the dialog, so the
        # chosen rating/tier has to survive until the confirm button commits it.
        self._pending_mf: dict = {}
        self._pending_bg: dict = {}
        self._mf_filter: dict[str, str] = {"text": "", "kind": "", "category": ""}
        self._mf_rows: list[tuple[QComboBox, MeritFlawPurchase]] = []
        self._mf_count: QLabel | None = None
        self._drop_idx: str = ""

        # The selected row as `(list_name, index)`. ⚠ A POSITION — `_rebuild` drops it,
        # because adding or removing a row renumbers everything after it.
        self._selected: tuple[str, int] | None = None
        self._search = ""

        self.issues = QLabel("")
        self.issues.setWordWrap(True)
        self.issues.setContentsMargins(8, 4, 8, 4)

        # ---- the action toolbar -------------------------------------- #
        # ⚠ Actions live HERE, not in the content. The add button is per-SUB-TAB —
        # "+ Background" on one, "Gain a Merit or Flaw…" on another — because what you
        # can add depends on which collection you are looking at, and three always-on
        # buttons would offer two you cannot use.
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
        """Empty `lay`, detaching every descendant NOW. One line, because the shape is
        subtle enough that six hand-written copies produced a wrong one — see
        `qt/layout.py`, which owns both traps and the reason they matter."""
        clear_layout(lay)

    def reload(self) -> None:
        """Rebuild the sub-tabs and their tables for the character in ctx, keeping the
        selection and the active tab where the player left them."""
        self._mf_rows = []
        self._mf_count = None
        remembered_tab = self.tabs.tabText(self.tabs.currentIndex())
        # ⚠ Signals blocked across the rebuild: `clear()` fires `currentChanged`, which
        # would run `_tab_changed` against half-built tables. (The QTabWidget
        # construction trap, same as the Charms tab's.)
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
        """A change that moved the LISTS. ⚠ Drops the selection first: it is a position,
        and adding or removing a row renumbers every row after it."""
        self._selected = None
        self.reload()

    def _categories(self) -> list[str]:
        """The sub-tabs this character gets. Fetters and Passions are ghost-only, and an
        empty tab is worse than no tab."""
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
        # ⚠ An explicit initial sort. Without one Qt picks its own indicator and the
        # first fill came out reverse-alphabetical, which reads as a bug rather than a
        # sort. The player can still click any header.
        table.sortByColumn(0, Qt.AscendingOrder)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.header().setSectionResizeMode(0, QHeaderView.Stretch)
        table.header().setSectionResizeMode(
            len(_TABLE_COLUMNS[label]) - 1, QHeaderView.Stretch)
        table.itemSelectionChanged.connect(self._selection_changed)
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
        """A change that only moves the readouts. Re-derives this tab's issue line and
        pings the shell (whose readout bar owns the bonus-point total)."""
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
            # The bonus-point total is the SHELL's readout bar; printing it here too
            # put the same sentence on screen twice.
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
        """Run an engine advancement call and surface its refusal. True when the
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

    def _clamp(self, text: str, limit: int = 220) -> str:
        """The one-line-ish summary a row carries. The web app clamps its catalogue
        blurb with CSS; Qt has no line-clamp, and a Manse's full printed paragraph
        pushed everything else off the panel. The whole text stays in the tooltip and
        in the catalogue dialog, which is where it is read."""
        text = " ".join(text.split())
        return text if len(text) <= limit else text[:limit].rstrip() + "…"

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
        """Rebuild every visible table and its contextual notes, restoring the selection
        where its row is still shown."""
        b = validate.effective_budgets(self._ruleset, self._char())
        for label, table in self._tables.items():
            self._clear_lay(self._notes[label])
            # ⚠ Sorting OFF across the fill: with it on Qt re-sorts after every insert,
            # which is quadratic and scrambles insertion order.
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
            # Backgrounds change in play through the story (a Manse falls, an Ally is
            # made), not by spending XP: editable current value, no cost, no log row.
            notes.addWidget(self._muted("Free in play — the story gives and takes "
                                        "these; no XP, no log row."))
        else:
            notes.addWidget(self._muted(
                f"{validate.background_dots_budget(b, char)} dots to spend; "
                f"≤{b.background_cap_pre_bp} in any one before bonus points."))
        catalog = self._bg_catalog()
        for idx, bg in enumerate(char.backgrounds):
            effective = validate.effective_background_rating(ruleset, char, bg.name)
            # Where a splat's book separates what you BUY from what it is WORTH
            # (Mountain Folk Resources: dots + 2, max 3 dots), the table says both.
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
            # ⚠ The custom-row discriminator is the EMPTY `merit_id`, never
            # `custom_name`'s truthiness — the name input writes that on every keystroke.
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
            # Under the other two methods, changes "do not cost or reward" and belong to
            # chargen, so say so rather than offering buttons that all read 0 XP.
            notes.addWidget(self._muted(
                f"This table uses the '{method}' method (Player's Guide p.17), under "
                f"which gaining or losing a Merit costs and rewards nothing. Unlock "
                f"chargen to edit them."))
            return
        notes.addWidget(self._muted(
            "Gaining a Merit or losing a Flaw costs twice its point value; losing a "
            "Merit or gaining a Flaw pays the same. An unaffordable change runs a debt "
            "against future XP."))
        # The p.17 cap applies in play too, and here it truncates the XP AWARD rather
        # than a bonus-point grant — a Flaw past the ceiling pays for its legal part
        # only. Silently paying less than the table expects is the worse failure, so the
        # remaining room is stated before anything is bought.
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
        """Point the add button at the active sub-tab, and show Drop only where it can
        actually run."""
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
        # "Lose / buy off" is an XP transaction and only exists post-lock, on a held
        # M&F row. Pre-lock the row is simply deleted, from its own editor.
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

        ⚠ Reads the table selection, not a separate "Held" combo. The old card carried
        its own dropdown of held entries beside the table listing the same ones — two
        controls naming one thing, and the one you were looking at was not the one the
        button acted on."""
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
        """The splat-filtered catalogue. The origin matters for `excluded_origins` (the
        ancient-only Savant): a modern Dragon King must not see it, an ancient one
        must."""
        return validate.background_catalogue_for(self._ruleset, self._char())

    def _bg_type(self, bg, catalog):
        """The catalogue entry a row names, or None for free text. Resolved through the
        SPLAT-FILTERED catalogue, which is what makes a Dragon-Blooded Manse row find
        the Dragon-Blooded allowance rather than the corebook's — the six Manse variants
        share two names between them, so a global lookup by name would answer for
        whichever copy it met first."""
        return {t.name.strip().lower(): t
                for t in catalog}.get(bg.name.strip().lower())

    def _background_editor(self, lay, bg, idx, b) -> None:
        """One Background in the detail pane: name, rating, note, hearthstones, and the
        printed text — the blurb plus the whole dot LADDER with the rung held marked.

        ⚠ A Background's printed text differs per rating, so one paragraph is not the
        answer; `view.background_ladder` is the one copy of that rendering (the
        catalogue dialog shows it too) and must not be re-implemented here.
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
            """Repaint everything keyed to this row's NAME and RATING. ⚠ Anything
            reading a Background rating must be driven from here — two consumers have
            gone stale in the web panel by not being."""
            rung_text = viewmod.background_rung(catalog, bg.name, bg.rating)
            # Where a splat's book separates what you BUY from what it is WORTH
            # (Mountain Folk Resources: dots + 2, max 3 dots), say so.
            effective = validate.effective_background_rating(ruleset, char, bg.name)
            if effective != bg.rating:
                note_text = f"effective {bg.name} {effective}"
                rung_text = f"{rung_text}  ·  {note_text}" if rung_text else note_text
            # The link to the Gear tab, where the artifacts themselves live: the
            # Background is what PAYS for them, so this says what it bought.
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
            # The ceiling comes from the engine, not a hardcoded 5: only the
            # `bind_post_lock` rules bind post-lock (Sidereal Celestial Manse ≤3, MF
            # Artifact ≤10), so a locked Unenlightened Mountain Folk can be given
            # Backing 4 by the story and a mortal granted an artifact.
            spin = QSpinBox()
            spin.setRange(0, validate.background_rating_cap(b, char, bg.name,
                                                            post_lock=True))
            spin.setValue(bg.rating)
            spin.valueChanged.connect(
                lambda v, bg=bg: (setattr(bg, "rating", v), sync()))
            self._labelled(lay, "Rating", spin)
        else:
            # ⚠ ONE copy of the cap rule: the add-dialog's spinner asks `_bg_cap_for`
            # too. A second implementation here would let the two ceilings drift apart.
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

        # The Demesne toggle sits on every Background that COULD grow stones, including
        # one already flipped — otherwise flipping it would hide the control that flips
        # it back. The picker sits only on rows that actually grow them.
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

        # The stones held, shown whenever any are held — even on a row flipped to
        # Demesne or renamed off a Manse, so a stranded stone stays visible and
        # deletable rather than becoming an Issue with no control behind it.
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

        # A dropdown pick changes which controls the entry needs (a Manse grows stones),
        # so it rebuilds; typing must NOT, or the combo being typed into is replaced.
        combo.editTextChanged.connect(
            lambda t, bg=bg: (setattr(bg, "name", t), sync()))
        combo.activated.connect(lambda _i: self.reload())
        sync()

    def _refresh_selected_row(self) -> None:
        """Re-render just the selected table row after an edit. ⚠ Never a full refill —
        that would replace the widget being typed into."""
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
        """The stones on one Manse row plus a running total against the allowance.
        Returns the total's sync function — the caller chains it onto the row's rating
        change, because BOTH halves of "4 / 3" move: the numerator when a stone is
        added or re-rated, the DENOMINATOR when the Manse rating does (a bigger Manse
        legalises the stone that was over budget a moment ago)."""
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
        """The Hearthstone picker for one Manse row. Each stone shows what it would COST
        against the row's remaining allowance — the same `hearthstone_allowance` the
        validator reads, so the picker and the Issue cannot disagree."""
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
            # ⚠ The over-budget warning goes FIRST. The dialog clamps a row's summary to
            # a few words, so anything tacked on the end of the description is exactly
            # what gets cut — and this is the one part of the line that must survive.
            note = "⚠ exceeds this Manse's remaining levels — " if over else ""
            rows.append((s.name, s.name,
                         f"{note}{s.rating_notes or ('•' * s.rating)} — {s.description}",
                         s.description))
        ratings = {s.name: s.rating for s in stones}

        def pick(name) -> None:
            # Custom (name is None) adds a blank stone rather than doing nothing: a
            # Hearthstone is unique per Manse (S&S p.67) and the printed ten are
            # examples, so "my own stone" is the common case. It gets a rating control
            # like any other, because the rating is what the rule measures.
            bg.hearthstones.append(HearthstoneEntry(
                name="" if name is None else name,
                rating=1 if name is None else ratings.get(name, 1)))
            self.reload()

        open_catalogue(self, self._pal(), "Hearthstones", rows, pick)

    # ⚠ Each `_build_*_dialog` returns the dialog WITHOUT running it, and the `_open_*`
    # wrapper execs it. `exec()` blocks, so a test can only reach the in-dialog rating
    # and tier controls through the builder.
    def _open_bg_catalogue(self) -> None:
        self._build_bg_dialog().exec()

    def _build_bg_dialog(self) -> CatalogueDialog:
        """Browse the splat-filtered catalogue, set the rating, and add it — or choose
        Custom for a blank row. The dialog is where a rating gets CHOSEN, so its full
        text carries the whole printed ladder and the spinner sits directly under it;
        the row itself shows only the rung the character holds."""
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
            # ⚠ The cap is per-NAME and can be 0 (a Flaw may bar a Background outright).
            # A spinner whose maximum is 0 is the correct, clickable-nowhere answer —
            # the confirm hook is what refuses it, so the reason can be stated.
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
        """The highest rating `name` may be taken at — the same two-sided answer
        `_backgrounds_panel.cap_for` gives: engine.merits' bar or lowered cap, and
        engine.validate's data ceiling, whichever is tighter."""
        mf = meritsmod.merits_and_flaws_calc(self._ruleset, self._char())
        key = (name or "").strip().lower()
        if key in mf.barred_backgrounds:
            return 0
        data_cap = validate.background_rating_cap(b, self._char(), name)
        merit_cap = mf.background_caps.get(key)
        return data_cap if merit_cap is None else min(data_cap, merit_cap)

    def _pick_bg(self, name) -> None:
        # Custom rows start at 1: there is no printed ladder to read a rating off, and
        # the row's own dot track is where it gets set.
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
        """Every entry this character may take, Merits before Flaws then by name. The
        splat/caste/Essence filter is the engine's, never restated here."""
        char = self._char()
        return [m for m in sorted(self._ruleset.merits_flaws.values(),
                                  key=lambda m: (m.kind != "merit", m.name))
                if validate.merit_available_to(m, char.exalt_type, char.caste,
                                               origin=char.origin,
                                               starting_essence=essence_start)]

    def _mf_matches(self, m) -> bool:
        """Does this entry survive the filter bar? A two-sided entry answers to BOTH
        side filters — it is genuinely either, and hiding it from both is how a player
        loses Prodigy. Text matches name, category and rules text."""
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

    # ⚠ The on-page filter bar (search + Merit/Flaw side + category) is GONE, not
    # lost: filtering belongs where the choosing happens, so the two catalogue dialogs
    # now carry category CHIPS (`group_of`) and their own search box. `_mf_matches`
    # survives and still gates what a dialog offers; with no bar to set `_mf_filter` it
    # simply passes everything, which is what a dialog that filters itself wants.

    def _merit_rules_text(self, lay, definition, *, with_description: bool = True) -> None:
        """The printed cost line, restrictions, gates and rules text under a row. The
        cost line always shows: a few qualifiers cannot be priced by the engine (a
        per-caste rate, a relative one), so the ST must see what the book says.

        `with_description=False` omits the trailing rules text, for the catalogue
        dialog — its detail pane is already showing that same string in full, and
        printing it twice (once scrollable, once truncated) reads as a bug, because it
        is one (human, 2026-08-21). The cost/restriction/requires lines are NOT in the
        detail pane, so they stay."""
        if definition.cost_note:
            lay.addWidget(self._muted(definition.cost_note))
        if definition.exalt_types:
            lay.addWidget(self._muted("Restricted to: " + ", ".join(definition.exalt_types),
                                      italic=True))
        # What the entry requires, so a player sees the gate BEFORE the issues panel
        # tells them they failed it. Tier-keyed groups are shown whole — which tier
        # needs what is the point of Innocuous.
        wants = [" or ".join(f"{r.trait} {r.rating}" for r in group)
                 for groups in definition.trait_prerequisites.values()
                 for group in groups]
        if definition.max_purchases_from_trait:
            wants.append(f"at most {definition.max_purchases_from_trait} purchases")
        if definition.prerequisite_note:
            wants.append(definition.prerequisite_note)
        if wants:
            lay.addWidget(self._muted("Requires: " + "; ".join(wants), italic=True))
        if with_description and definition.description:
            text = self._muted(self._clamp(definition.description, 320))
            text.setToolTip(definition.description)
            lay.addWidget(text)

    # ------------------------------------------------------------------ #
    # Merits & Flaws — chargen
    # ------------------------------------------------------------------ #

    def _chargen_merit_notes(self, notes, eff, b) -> None:
        """The bonus-point arithmetic, above the table it describes.

        A MERIT costs bonus points; a FLAW grants them, which is why the grant is
        reported separately rather than as a negative.
        """
        ruleset, char = self._ruleset, self._char()
        spent = validate.merit_bonus_point_cost(ruleset, char)
        line = f"−{spent} bonus points spent"
        if eff.bonus_point_grant:
            line += f", +{eff.bonus_point_grant} granted by Flaws"
        notes.addWidget(self._muted(line))
        # "Characters with more than 10 points of Flaws receive no bonus points for the
        # excess" (PG p.17). Say so when it bites — the grant above is the CAPPED
        # number, and a player who took 13 points and sees "+10" cannot tell the cap
        # from a bug in our arithmetic.
        if eff.flaw_points_raw > eff.bonus_point_grant:
            notes.addWidget(self._warn(
                f"⚠ {eff.flaw_points_raw} points of Flaws taken, "
                f"{eff.bonus_point_grant} granted — the excess "
                f"{eff.flaw_points_raw - eff.bonus_point_grant} is lost to the "
                f"{meritsmod.FLAW_POINT_CAP}-point cap (p.17). The Flaws still apply."))
        # Say which held Merits this build treats as narrative, rather than letting a
        # player wonder why nothing changed.
        if eff.narrative_only:
            names = ", ".join(sorted(ruleset.merits_flaws[m].name
                                     for m in eff.narrative_only
                                     if m in ruleset.merits_flaws))
            if names:
                notes.addWidget(self._muted(
                    f"Narrative only in this build: {names}.", italic=True))

    def _merit_editor(self, lay, mp, idx, b) -> None:
        """One held Merit or Flaw in the detail pane.

        ⚠ Every control is on its own labelled line. The shipped card packed them into
        two horizontal rows because Qt has no wrapping row and the panel was
        width-starved; a detail pane is not, so the workaround goes.

        Post-lock the entry itself is READ-ONLY: a held Merit is not swapped for another,
        it is dropped (toolbar) and a new one gained. What the pane adds post-lock, which
        the shipped card could not show at all, is the printed rules text of what you
        actually hold.
        """
        ruleset, char = self._ruleset, self._char()
        locked = self._locked()
        definition = ruleset.merits_flaws.get(mp.merit_id)

        # A player-authored "Custom" row (2026-08-10): no catalogue entry, no mechanical
        # effect — just a name the sheet renders. It gets a plain text input and NONE of
        # the definition-driven controls, every one of which reads `definition`.
        # ⚠ The discriminator is the EMPTY `merit_id`, never `custom_name`'s truthiness:
        # the name input below writes that field on every keystroke.
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
            # ⚠ Whatever the row already holds stays selectable: an off-catalogue id (a
            # save opened without its data) must not vanish from its own dropdown.
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
            # Read-only summary of the recorded choices; the toolbar's Drop is the only
            # post-lock mutation.
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

        # Which side a two-sided entry was taken on. No blank option is defaulted: the
        # value decides whether this charges bonus points or grants them, so it must be
        # a deliberate pick — an unrecorded choice shows empty and validate flags it.
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
            # Only the options this splat may actually choose, priced from the same
            # table the pricer reads — Lucky is 1-5 but 1-3 for a Sidereal. A tier
            # already recorded stays selectable.
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
            # Arena drives the same-arena stacking reduction (p.122); free text, because
            # the page's list is examples, not a set. Only for the entry with that rule.
            if meritsmod.uses_arena(definition):
                arena = QLineEdit(mp.arena)
                arena.setPlaceholderText("arena (combat, food…)")
                arena.textChanged.connect(
                    lambda t, mp=mp: (setattr(mp, "arena", t),
                                      self._refresh_selected_row(), self._changed()))
                self._labelled(lay, "Arena", arena)
        elif definition.variable_cost:
            # A variable-cost entry's value lives on the PURCHASE — the page leaves it
            # to the table. Without this control it stayed 0, which made all 11 of them
            # inert at chargen: no bonus points, no effect.
            rate = meritsmod.forfeit_rate(definition)
            spin = QSpinBox()
            spin.setRange(0, 20)
            if rate:
                # Collect DOTS and multiply rather than collecting points and flooring
                # back: the dots are what the player chooses ("three points for every
                # Physical Attribute dot"), and entering points can lose a remainder.
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
        # WHICH artifact a per-entry limit measures (Damaged Artifact). The condition is
        # the catalogue's `per_entry` flag, never the entry's id — decision 0011 again.
        if any(limit.per_entry for limit in definition.points_limits):
            items = artifactsmod.artifact_items(char)
            art = QComboBox()
            art.addItem("", "")
            for item in items:
                art.addItem(f"{item.name} ({item.rating})", item.key)
            # A key that no longer resolves — the artifact was renamed or deleted —
            # stays selectable and is labelled broken rather than vanishing silently.
            if mp.artifact_key and art.findData(mp.artifact_key) < 0:
                art.addItem(f"{mp.artifact_key}  (missing)", mp.artifact_key)
            art.setCurrentIndex(max(0, art.findData(mp.artifact_key or "")))
            art.currentIndexChanged.connect(
                lambda _i, mp=mp, a=art: (setattr(mp, "artifact_key", a.currentData() or ""),
                                          self._changed()))
            self._labelled(lay, "Artifact", art)
            if not items:
                lay.addWidget(self._warn("no artifacts owned"))
        # Stipulations are dots, so they need a number rather than a note — "an extra
        # dot … for every major stipulation applied to the Inheritance, up a maximum of
        # three" (p.24).
        if definition.takes_stipulations:
            stip = QSpinBox()
            stip.setRange(0, 3)
            stip.setValue(mp.stipulations)
            stip.valueChanged.connect(
                lambda v, mp=mp: (setattr(mp, "stipulations", v), self._changed()))
            self._labelled(lay, "Stipulations", stip)
        # A structured detail is a CLOSED set, not free text: which Attribute category a
        # forfeit comes from, which Attribute gets Legendary Attribute's raised ceiling.
        # Both were free-text once and both failed silently.
        choices = meritsmod.detail_choices(definition)
        if choices:
            detail = QComboBox()
            detail.addItem("", "")
            for c in choices:
                detail.addItem(c, c)
            # A stored detail can legitimately be off-list: validate compares
            # `detail.strip().title()`, so "strength" passes validation while never
            # matching the title-cased option. Normalise the same way, then keep
            # anything still unmatched as its own option.
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
        # Changing the entry clears every value that belonged to the old one — side,
        # tier, points, arena and detail all mean something entry-specific, and a
        # carried-over value silently mis-prices. The tier resets to the new entry's
        # first AVAILABLE option rather than to blank, so a row is never left on a dead
        # tier or on one this splat is barred from.
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
        """Browse the filtered set, configure it, and take it — or choose Custom for a
        display-only player-authored row. Never a blind "add" that appends the cheapest
        entry. The tier / points / side controls are the same block the in-play card
        uses, so the row lands fully specified instead of on a default tier the player
        never saw."""
        rows = [(m.id, viewmod.merit_option_label(m), m.description, m.description)
                for m in available]
        holder: dict = {}
        # ⚠ The category chips are where the page's old filter bar went. Filtering
        # belongs where the choosing happens, not beside the list of what you already
        # hold — five printed categories make five chips, and the dialog's own search
        # box replaces the bar's text field.
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
            # `merit_id` is required but deliberately empty: it resolves to nothing in
            # the catalogue, so the engine skips the row entirely — the "no mechanical
            # effect" the Custom option promises.
            char.merits_flaws.append(
                MeritFlawPurchase(merit_id="", custom_name="New custom Merit / Flaw"))
            self.reload()
            return
        definition = self._ruleset.merits_flaws.get(key)
        if definition is None:
            return
        # The dialog's controls have already chosen these. Fall back to the splat-aware
        # default tier for a caller that picked without them (the tests do).
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
        """Browse, configure and BUY in one dialog. The tier, the point value and the
        Merit-or-Flaw side are set beside the entry's printed text, and the confirm
        button carries the resulting XP — so no purchase is committed from a menu label
        alone (human, 2026-08-21: picking an entry appeared to do nothing, because the
        controls were on a card below the fold)."""
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
            # A fresh selection starts a fresh purchase. Every value is entry-specific,
            # and a tier carried over from the previous row silently mis-prices — the
            # same reason `_set_merit` clears on change.
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
        """Confirmed out of the dialog: `self._gain` is already fully specified by the
        extras controls, so this commits it."""
        if key is None:
            self._custom_gain()
            return
        self._gain_mf()

    def _custom_gain(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Custom Merit / Flaw")
        lay = QVBoxLayout(dialog)
        lay.addWidget(self._muted("Display-only — recorded on the sheet, no mechanical "
                                  "effect (2026-08-10)."))
        name = QLineEdit()
        name.setPlaceholderText("name (e.g. a bloodline trait)")
        lay.addWidget(name)

        def go() -> None:
            text = name.text().strip()
            if not text:
                self._notify("Give the custom Merit / Flaw a name.", "warning")
                return
            # Empty `merit_id` — resolves to nothing, so the engine treats the row as
            # no-effect (the Custom option's contract).
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
        """True when the entry can be taken either way and no side has been chosen.
        The side is what makes the transaction positive or negative, so a purchase in
        this condition is half-specified and must not be allowed to land."""
        return definition.kind == "either" and not state.get("taken_as")

    def _mf_purchase_block(self, definition, lay, state, on_sync=None):
        """Build the entry-specific purchase controls into `lay`, driving the mutable
        `state` dict (taken_as / tier / points / detail). Input: the definition, a
        layout, the state, and an optional callback fired after each change. Output:
        a `sync()` callable that refreshes the banner and the price line from `state`.

        ⚠ `sync()` refreshes text IN PLACE and never rebuilds a widget. The controls
        call it from their own change signals, and deleting a widget from inside its
        own handler is the Qt crash this shape exists to avoid.

        Shared by the in-play card and the catalogue dialog, so the two surfaces cannot
        drift into pricing the same purchase differently.
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
            # For a two-sided entry the chosen side decides the direction of the
            # transaction, so it drives this banner too — an unchosen one says so
            # rather than implying the Merit branch.
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
        # The value controls, entry-aware — the same set chargen offers. This was ONE
        # free-text box doing double duty (a tier key for a menu-priced entry, a point
        # value for a variable-cost one), which is the shape that produced the
        # splat-filter bug.
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
            # ⚠ A variable-cost entry OPENS AT ONE, never at zero (human's ruling,
            # 2026-08-21). At zero it prices to nothing, so confirming it would add a
            # row that neither costs nor pays — a purchase that looks made and did
            # nothing. The opening value is seeded into `state` as well as the spinner,
            # because the confirm button prices `state`, not the widget.
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
        """Gain a Merit or Flaw in play. Which side of the transaction it is depends on
        the ENTRY, not on the button — so the branch and both refusals live in
        `advancement.gain_merit_or_flaw`, shared with the web shell."""
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
    # The two behave very differently and the panels must not blur that:
    #   * a FETTER is bought — pool dots, then bonus points, then experience;
    #   * a PASSION is not bought at ANY point. Its dots come from the Virtues and the
    #     player only distributes them (p.283). So its "pool" readout is a derivation
    #     that keeps moving after the lock, and there is no price anywhere on it.

    def _has_fetters(self) -> bool:
        char = self._char()
        b = self._ruleset.budgets_for(char.exalt_type, char.origin, char.upbringing)
        return bool(b.fetter_dots or char.fetters)

    def _has_passions(self) -> bool:
        return bool(self._char().passions or self._has_fetters())

    def _fetter_editor(self, lay, fetter, idx, b) -> None:
        """One Fetter in the detail pane. Pre-lock a free dot track; post-lock the
        rating is read-only pips and moves only through the priced controls (p.283)."""
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
        """⚠ The cap is Willpower + Essence and it MOVES, so it is a live number on
        both sides of the lock rather than a chargen note."""
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

        ⚠ A FREE dot track on both sides of the lock, deliberately: a Passion
        distributes a DERIVED pool (its dots come from the Virtues, E:Ab p.283) and is
        never bought, so the post-lock XP stepper the Traits tab uses would be wrong.
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

        # The pool this Passion draws on, per Virtue, so the player can see what is left
        # to distribute without leaving the entry they are editing.
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
        # Open on the Fetter being looked at, so Raise/Shift act on the selection
        # rather than on whichever happens to be first.
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
        """The one experience operation on a Passion (p.283, 20 XP): move a dot from one
        to another. The TOTAL cannot change — the Virtues set it."""
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
