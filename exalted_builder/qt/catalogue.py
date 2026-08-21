"""exalted_builder/qt/catalogue.py — the native browse-before-you-choose dialog.

Input: `(key, name, summary, full)` rows, the same shape `ui/catalogue.py` takes, plus
an `on_pick` callback. Output: a modal list filtered live by a text box, with the
selected row's full text beside it; picking calls `on_pick(key)`, the Custom button
calls `on_pick(None)`, and the dialog closes either way. Mechanism: a QListWidget whose
items carry the key in `Qt.UserRole` and are hidden (never removed) by the filter, so
the selection survives typing.

Pure UI — no game logic. The caller hands it an already-filtered list and owns what
happens to the character, exactly as the web dialog's contract says.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QPushButton, QTextBrowser, QVBoxLayout,
)

from exalted_builder.ui.theme import Palette

from .theme import MUTED, accent


class CatalogueDialog(QDialog):
    """The modal itself. `open_catalogue` is the ordinary way in."""

    def __init__(self, pal: Palette, title: str,
                 entries: Sequence[tuple[str, str, str, str | None]],
                 on_pick: Callable[[str | None], None], *,
                 subtitle: str = "", custom_label: str = "Custom",
                 allow_custom: bool = True, parent=None):
        super().__init__(parent)
        self._entries = list(entries)
        self._on_pick = on_pick
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
            item = QListWidgetItem(f"{name}\n{summary}" if summary else name)
            item.setData(Qt.UserRole, key)
            self.list.addItem(item)
        self.list.currentItemChanged.connect(lambda *_: self._show_detail())
        self.list.itemDoubleClicked.connect(lambda *_: self._choose())
        body.addWidget(self.list, 3)
        self.detail = QTextBrowser()
        body.addWidget(self.detail, 2)
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

        if self.list.count():
            self.list.setCurrentRow(0)
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
            return
        key = item.data(Qt.UserRole)
        row = next((e for e in self._entries if e[0] == key), None)
        self.detail.setPlainText("" if row is None else (row[3] or row[2] or ""))

    def _choose(self) -> None:
        item = self.list.currentItem()
        if item is None or item.isHidden():
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
