"""exalted_builder/qt/catalogue.py — the native browse-before-you-choose dialog.

Input: `(key, name, summary, full)` rows, the same shape `ui/catalogue.py` takes, plus
an `on_pick` callback and two optional hooks, `extras` and `confirm`. Output: a modal
list filtered live by a text box, with the selected row's full text beside it and the
caller's own controls under that text; confirming calls `on_pick(key)`, the Custom
button calls `on_pick(None)`, and the dialog closes either way. Mechanism: a
QListWidget whose items carry the key in `Qt.UserRole` and are hidden (never removed)
by the filter, so the selection survives typing; changing the selection re-runs
`extras` into a container the dialog owns and `confirm` to re-label the button.

Pure UI — no game logic. The caller hands it an already-filtered list, supplies whatever
per-entry controls that entry needs, and owns what happens to the character, exactly as
the web dialog's contract says. ⚠ The dialog never reads or prices an entry itself: it
cannot tell a Merit from a Flaw, and must not learn to.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QPushButton, QTextBrowser, QVBoxLayout, QWidget,
)

from exalted_builder.ui.theme import Palette

from .theme import MUTED, accent


BLURB_WORDS = 14


def _blurb(summary: str, limit: int = BLURB_WORDS) -> str:
    """A row's second line, cut to `limit` words. Input: a summary that may be a whole
    printed paragraph. Output: at most `limit` words, ellipsed if cut.

    ⚠ Display only. The filter matches the FULL summary (see `_apply_filter`) and the
    detail pane shows the full text — clamping either would make entries unfindable by
    a word they visibly contain (human, 2026-08-21: the long rows scroll off the screen).
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
                 extras: Callable[[str, QVBoxLayout], None] | None = None,
                 confirm: Callable[[str], tuple[str, bool]] | None = None,
                 parent=None):
        super().__init__(parent)
        self._entries = list(entries)
        self._on_pick = on_pick
        self._extras = extras
        self._confirm = confirm
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
        self.search.textChanged.connect(self._apply_filter)
        root.addWidget(self.search)

        body = QHBoxLayout()
        self.list = QListWidget()
        for key, name, summary, _full in self._entries:
            blurb = _blurb(summary)
            item = QListWidgetItem(f"{name}\n{blurb}" if blurb else name)
            item.setData(Qt.UserRole, key)
            self.list.addItem(item)
        # ⚠ Connected AFTER the buttons are built, further down: `_show_detail` now
        # re-labels `choose_btn`, so a selection signal arriving before that button
        # exists would be an AttributeError.
        body.addWidget(self.list, 3)
        # The right-hand column is the full printed text with the caller's controls
        # directly beneath it — the whole point of buying from in here is that the
        # rating you set sits next to the ladder that describes it.
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
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        buttons.addStretch(1)
        if allow_custom:
            custom = QPushButton(custom_label)
            custom.setToolTip("Add a free-text entry of your own instead")
            custom.clicked.connect(self._custom)
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

    def _apply_filter(self, text: str) -> None:
        """Hide the rows that do not match; never remove them, so the current
        selection survives a filter that excludes it and the counts stay honest."""
        needle = (text or "").strip().lower()
        shown = 0
        for i, (_key, name, summary, full) in enumerate(self._entries):
            hay = f"{name} {summary} {full or ''}".lower()
            match = needle in hay
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
        """Tear the caller's controls down between selections.

        ⚠ RECURSES into nested layouts. The caller builds its controls as rows, and a
        `QHBoxLayout` yields `item.widget() is None` — so a widget-only sweep detaches
        nothing inside one and the previous entry's text paints on top of the next
        (human, 2026-08-21).

        ⚠ `deleteLater` alone leaves the widget parented and visible until the event
        loop runs, so hide and unparent it NOW. Same shape as `AdvantagesPage._clear_lay`.
        """
        lay = self.extras_lay if lay is None else lay
        while lay.count():
            item = lay.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
            elif item.layout() is not None:
                self._clear_extras(item.layout())

    def _sync_confirm(self, key: str | None) -> None:
        """Re-label the confirm button for the selected entry and enable or disable it.
        The caller decides both — a half-specified purchase (no Merit/Flaw side chosen)
        is refused HERE, before anything lands on the character."""
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
        self.accept()
        self._on_pick(item.data(Qt.UserRole))

    def _custom(self) -> None:
        self.accept()
        self._on_pick(None)


def open_catalogue(parent, pal: Palette, title: str,
                   entries: Sequence[tuple[str, str, str, str | None]],
                   on_pick: Callable[[str | None], None], **kwargs) -> CatalogueDialog:
    """Build and run a `CatalogueDialog`. Returns it, so a test can drive the list
    without a click."""
    dialog = CatalogueDialog(pal, title, entries, on_pick, parent=parent, **kwargs)
    dialog.exec()
    return dialog
