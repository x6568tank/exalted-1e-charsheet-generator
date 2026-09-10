"""exalted_builder/qt/layout.py — layout teardown and the empty-table note, in ONE place.

Two shapes that every surface in the port needs.

`clear_layout` — input: a QLayout. Output: the layout is empty, and every descendant
stops painting immediately. Mechanism: take each item; hide, unparent and
`deleteLater()` a widget; RECURSE into a nested layout.

`empty_note` — input: a collection table and a sentence. Output: the sentence shows over
the table while the table holds no rows. The model's own signals drive it.

⚠ **`item.widget()` is None for a `QLayout`.** A widget-only sweep detaches nothing
inside a row. Thus the previous build continues to paint ON TOP of the next build. Every
surface here builds its content as rows. Thus every surface has this risk.

⚠ **`deleteLater()` alone is deferred to the event loop.** A rebuild that runs more than
once synchronously leaves widgets that paint at stale geometry. Each build stacks on the
last one. Hide and unparent the widget immediately. `deleteLater()` then frees the C++
object.

⚠ **Call `clear_layout`. Do not write a new teardown loop.**

⚠ Test a teardown with repeated rebuilds. Count the live descendants. One rebuild passes
while the layout leaks.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QLayout, QTreeWidget, QVBoxLayout

from .theme import MUTED


def empty_note(tree: QTreeWidget, text: str) -> QLabel:
    """Give `tree` a message that shows while it holds no rows. Returns the label.

    Input: a collection table and the sentence to show when the table is empty. Output:
    a muted label over the table's viewport, visible at zero rows only. Mechanism: a
    layout on the viewport puts the label in position. The model's own row signals show
    and hide it.

    ⚠ **An empty table looks the same as a broken table.** A heading over a large blank
    area reads as "nothing loaded". The detail pane's "select something, or add one" is
    on the other side of a splitter. It does not correct this.

    ⚠ **The MODEL's signals drive the label. The callers do not.** If each `_fill_table`
    had to show and hide the label, a new one would be written without it. `tree.clear()`
    emits `modelReset`. Thus the label stays correct through every rebuild.
    """
    label = _EmptyNote(text, tree.model())
    lay = QVBoxLayout(tree.viewport())
    lay.setContentsMargins(24, 24, 24, 24)
    lay.addWidget(label)
    lay.addStretch(1)
    return label


class _EmptyNote(QLabel):
    """The label, and the RECEIVER of the model's signals.

    ⚠ A closure here causes a crash. The tables on Advantages and Custom are rebuilt with
    their sub-tab pages. Thus the label is destroyed while its model continues to exist. A
    closure continues to send to a deleted C++ object ("libshiboken: Internal C++ object
    already deleted"). Qt removes a connection when its RECEIVER is destroyed. Thus the
    slot must be a bound method of a QObject. This class supplies that QObject.
    """

    def __init__(self, text: str, model, parent=None):
        super().__init__(text, parent)
        self._model = model
        self.setObjectName("emptyNote")
        self.setWordWrap(True)
        self.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.setStyleSheet(f"color:{MUTED};")
        for signal in (model.rowsInserted, model.rowsRemoved, model.modelReset,
                       model.layoutChanged):
            signal.connect(self.sync)
        self.sync()

    def sync(self, *_args) -> None:
        """Show the note only while the table holds no rows."""
        self.setVisible(self._model.rowCount() == 0)


def clear_layout(lay: QLayout) -> None:
    """Empty `lay`, detaching every widget and nested layout under it."""
    while lay.count():
        item = lay.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.hide()
            widget.setParent(None)
            widget.deleteLater()
            continue
        child = item.layout()
        if child is not None:
            clear_layout(child)
