"""exalted_builder/qt/catalogue.py — the native browse-before-you-choose dialog.

Input: `(key, name, summary, full)` rows, the same shape `ui/catalogue.py` takes, plus
an `on_pick` callback and the optional `extras`, `confirm`, `group_of` (one group per
key, or several), `custom_kinds`
and `dimmed`. Output: a modal list filtered live by a text box and by type chips, with
the selected row's full text beside it and the caller's own controls under that text;
confirming calls `on_pick(key)`, a Custom button calls `on_pick(None)` or
`on_pick("custom:<kind>")`, and the dialog closes either way. Mechanism: a QListWidget
whose items carry the key in `Qt.UserRole` and are hidden (never removed) by the
filter, so the selection survives typing; changing the selection re-runs `extras` into
a container the dialog owns and `confirm` to re-label the button.

This module is UI only. It contains no game logic. The caller supplies a list that is
already filtered, supplies the controls that each entry needs, and owns the change to the
character. This agrees with the contract of the web dialog.

⚠ The dialog never reads an entry and never prices one. It cannot identify a Merit or a
Flaw. Do not give it that ability.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QPushButton, QTextBrowser, QVBoxLayout, QWidget,
)

from exalted_builder.ui.theme import Palette

from .layout import clear_layout
from .theme import MUTED, accent


BLURB_WORDS = 14
ALL_GROUPS = "All"


def _blurb(summary: str, limit: int = BLURB_WORDS) -> str:
    """A row's second line, cut to `limit` words. Input: a summary that may be a whole
    printed paragraph. Output: at most `limit` words, ellipsed if cut.

    ⚠ This cut is for display only. The filter matches the FULL summary (see
    `_apply_filter`), and the detail pane shows the full text. If you cut either one, the
    user cannot find an entry by a word that the entry shows.
    """
    words = (summary or "").split()
    if len(words) <= limit:
        return " ".join(words)
    return " ".join(words[:limit]) + "…"


class CatalogueDialog(QDialog):
    """The modal itself. `open_catalogue` is the ordinary way in."""

    def __init__(self, pal: Palette, title: str,
                 entries: Sequence[tuple[str, str, str, str | None]],
                 on_pick: Callable[[str | None], None], *,
                 subtitle: str = "", custom_label: str = "Custom",
                 allow_custom: bool = True,
                 group_of: dict[str, str | Sequence[str]] | None = None,
                 custom_kinds: dict[str, str] | None = None,
                 dimmed: set[str] | None = None,
                 extras: Callable[[str, QVBoxLayout], None] | None = None,
                 confirm: Callable[[str], tuple[str, bool]] | None = None,
                 keep_open: bool = False,
                 parent=None):
        super().__init__(parent)
        # Keep the dialog open after a pick, for a field that takes MANY entries. The
        # Charm list of an adversary takes approximately twelve picks, and each reopen
        # loses the filter. Cancel becomes Done. The count line reports each pick,
        # because nothing else on the screen changes. The default is False.
        self._keep_open = keep_open
        self._picked = 0
        self._entries = list(entries)
        self._on_pick = on_pick
        self._extras = extras
        self._confirm = confirm
        # ⚠ A row can be in MORE THAN ONE group. `group_of` takes a string or a list of
        # strings for each key, and this code makes a list of both forms. An adversary
        # carries more than one label, and the user must find it under each label. Other
        # callers supply one string.
        self._group_of = {key: [value] if isinstance(value, str) else list(value)
                          for key, value in dict(group_of or {}).items()}
        self._dimmed = set(dimmed or ())
        self._group = ALL_GROUPS
        self.setWindowTitle(title)
        self.resize(820, 560)

        root = QVBoxLayout(self)
        head = QLabel(title)
        head.setStyleSheet(f"font-weight:700; color:{accent(pal)};")
        root.addWidget(head)
        if subtitle:
            sub = QLabel(subtitle)
            sub.setStyleSheet(f"color:{MUTED};")
            root.addWidget(sub)

        self.search = QLineEdit()
        self.search.setPlaceholderText("filter by name or text…")
        self.search.textChanged.connect(lambda *_: self._apply_filter())
        root.addWidget(self.search)

        # Type chips. A dialog that shows four catalogues gives too many names without
        # them, and the text box helps only a user who knows what to type. The chips come
        # from the `group_of` of the caller. The dialog classifies nothing.
        self.group_buttons: dict[str, QPushButton] = {}
        groups = [g for g in dict.fromkeys(
            g for values in self._group_of.values() for g in values) if g]
        if groups:
            chips = QHBoxLayout()
            for group in [ALL_GROUPS] + groups:
                chip = QPushButton(group)
                chip.setCheckable(True)
                chip.setChecked(group == ALL_GROUPS)
                chip.clicked.connect(
                    lambda _checked=False, g=group: self._set_group(g))
                chips.addWidget(chip)
                self.group_buttons[group] = chip
            chips.addStretch(1)
            root.addLayout(chips)

        body = QHBoxLayout()
        self.list = QListWidget()
        for key, name, summary, _full in self._entries:
            blurb = _blurb(summary)
            item = QListWidgetItem(f"{name}\n{blurb}" if blurb else name)
            item.setData(Qt.UserRole, key)
            if key in self._dimmed:
                # The price is above the Resources of this character. Make the row DIM.
                # Do not remove it and do not disable it. Core p.325 makes the cost a
                # guide, and the program deducts nothing. Thus the shop shows a price and
                # never refuses a purchase.
                item.setForeground(QColor(MUTED))
            self.list.addItem(item)
        # ⚠ Connect this signal AFTER the code below builds the buttons. `_show_detail`
        # re-labels `choose_btn`. A selection signal that arrives before that button
        # exists causes an AttributeError.
        body.addWidget(self.list, 3)
        # The right column holds the full printed text, and the controls of the caller
        # below it. Thus the rating that the user sets is next to the printed text that
        # describes that rating.
        side = QVBoxLayout()
        self.detail = QTextBrowser()
        side.addWidget(self.detail, 1)
        self.extras_box = QWidget()
        self.extras_lay = QVBoxLayout(self.extras_box)
        self.extras_lay.setContentsMargins(0, 0, 0, 0)
        side.addWidget(self.extras_box)
        self.extras_box.setVisible(self._extras is not None)
        body.addLayout(side, 2)
        root.addLayout(body, 1)

        self.count = QLabel("")
        self.count.setStyleSheet(f"color:{MUTED};")
        root.addWidget(self.count)

        buttons = QHBoxLayout()
        # In keep-open mode, a pick does not close the dialog. The dismiss button closes
        # it, and its label says so.
        cancel = QPushButton("Done" if keep_open else "Cancel")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        buttons.addStretch(1)
        # `custom_kinds` is the multi-kind form of the Custom button. To make an entry and
        # to buy an entry are ONE surface. When the user selects a kind, the shop knows
        # which list holds the blank row. The kind returns to the caller as
        # `custom:<kind>`. The dialog never decides what a blank row is.
        for kind, label in (custom_kinds or {}).items():
            button = QPushButton(label)
            button.setToolTip("Add a blank row of your own instead")
            button.clicked.connect(
                lambda _checked=False, k=kind: self._custom(f"custom:{k}"))
            buttons.addWidget(button)
        if allow_custom and not custom_kinds:
            custom = QPushButton(custom_label)
            custom.setToolTip("Add a free-text entry of your own instead")
            custom.clicked.connect(lambda *_: self._custom(None))
            buttons.addWidget(custom)
        self.choose_btn = QPushButton("Choose")
        self.choose_btn.clicked.connect(self._choose)
        buttons.addWidget(self.choose_btn)
        root.addLayout(buttons)

        self.list.currentItemChanged.connect(lambda *_: self._show_detail())
        self.list.itemDoubleClicked.connect(lambda *_: self._choose())

        if self.list.count():
            self.list.setCurrentRow(0)
        else:
            self._show_detail()      # no rows: clear the pane and disable the button
        self._apply_filter("")

    # ---- behaviour ------------------------------------------------------- #

    def _set_group(self, group: str) -> None:
        """Select one type chip. Only one chip can be active. The buttons are checkable,
        thus the active chip stays down. `setChecked` here releases the other chips."""
        self._group = group
        for name, chip in self.group_buttons.items():
            chip.setChecked(name == group)
        self._apply_filter()
        # ⚠ A chip click moves the selection. Text in the search box does NOT move it.
        # If the code hides the selected row, the confirm button stays enabled for a row
        # that is not on the screen, and `_choose` then refuses without a message. Text
        # is an exception, because the selection must stay through an incomplete word.
        current = self.list.currentItem()
        if current is None or current.isHidden():
            first = next((i for i in range(self.list.count())
                          if not self.list.item(i).isHidden()), None)
            self.list.setCurrentRow(-1 if first is None else first)

    def _apply_filter(self, _text: str | None = None) -> None:
        """Hide each row that the text box and the active type chip do not match. Never
        remove a row. Thus the selection stays through a filter that excludes it, and the
        counts stay correct."""
        needle = self.search.text().strip().lower()
        shown = 0
        for i, (key, name, summary, full) in enumerate(self._entries):
            hay = f"{name} {summary} {full or ''}".lower()
            match = needle in hay and (self._group == ALL_GROUPS
                                       or self._group in self._group_of.get(key, ()))
            self.list.item(i).setHidden(not match)
            shown += bool(match)
        total = len(self._entries)
        self.count.setText(f"{total} entries" if shown == total
                           else f"{shown} of {total} shown — clear the filter to see the rest")

    def _show_detail(self) -> None:
        item = self.list.currentItem()
        if item is None:
            self.detail.setPlainText("")
            self._clear_extras()
            self._sync_confirm(None)
            return
        key = item.data(Qt.UserRole)
        row = next((e for e in self._entries if e[0] == key), None)
        self.detail.setPlainText("" if row is None else (row[3] or row[2] or ""))
        self._clear_extras()
        if self._extras is not None and key is not None:
            self._extras(key, self.extras_lay)
        self._sync_confirm(key)

    def _clear_extras(self, lay=None) -> None:
        """Remove the controls of the caller between two selections. `qt/layout.py` holds
        this shape and its two traps. The caller builds its controls as rows, and a
        widget-only sweep lets the previous entry paint on top of the next entry."""
        clear_layout(self.extras_lay if lay is None else lay)

    def _sync_confirm(self, key: str | None) -> None:
        """Re-label the confirm button for the selected entry, and enable or disable it.
        The caller decides the label and the state. This refuses a purchase that is not
        fully specified, for example a Merit/Flaw entry with no side selected. The refusal
        happens HERE, before the program changes the character."""
        if self._confirm is None:
            self.choose_btn.setEnabled(key is not None)
            return
        if key is None:
            self.choose_btn.setEnabled(False)
            return
        label, enabled = self._confirm(key)
        self.choose_btn.setText(label)
        self.choose_btn.setEnabled(enabled)

    def refresh_confirm(self) -> None:
        """Re-run the `confirm` hook without rebuilding the extras. The caller calls
        this when one of its own controls changes the price or the legality."""
        item = self.list.currentItem()
        self._sync_confirm(None if item is None else item.data(Qt.UserRole))

    def _choose(self) -> None:
        item = self.list.currentItem()
        if item is None or item.isHidden() or not self.choose_btn.isEnabled():
            return
        if self._keep_open:
            # ⚠ `on_pick` runs and the dialog stays open. Do NOT call accept() here. The
            # exec() loop in `open_catalogue` then stops, and the next pick goes to a
            # closed dialog.
            self._on_pick(item.data(Qt.UserRole))
            self._picked += 1
            self.count.setText(
                f"Added {item.text().splitlines()[0]}  ·  {self._picked} picked")
            return
        self.accept()
        self._on_pick(item.data(Qt.UserRole))

    def _custom(self, key: str | None = None) -> None:
        """A Custom button. `key` is None for the one-button form, and the caller then
        decides what a blank row is. `key` is `custom:<kind>` when the caller supplied
        `custom_kinds`, and the kind is then part of the result."""
        self.accept()
        self._on_pick(key)


def open_catalogue(parent, pal: Palette, title: str,
                   entries: Sequence[tuple[str, str, str, str | None]],
                   on_pick: Callable[[str | None], None], **kwargs) -> CatalogueDialog:
    """Build and run a `CatalogueDialog`. Returns it, so a test can drive the list
    without a click."""
    dialog = CatalogueDialog(pal, title, entries, on_pick, parent=parent, **kwargs)
    dialog.exec()
    return dialog
