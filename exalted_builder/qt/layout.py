"""exalted_builder/qt/layout.py — layout teardown and the empty-table note, in ONE place.

Two shapes that every surface in the port needs and that six hand-written copies got
wrong between them:

`clear_layout` — input: a QLayout. Output: it is emptied and every descendant detached
from rendering immediately. Mechanism: take each item; hide, unparent and
`deleteLater()` a widget; RECURSE into a nested layout.

`empty_note` — input: a collection table and a sentence. Output: that sentence shows
over the table while it holds no rows, driven by the model's own signals.

⚠ **This exists because the same six-line loop was written six times and the sixth was
wrong.** Both halves of it are non-obvious and both have shipped as bugs:

* **`item.widget()` is None for a `QLayout`.** A widget-only sweep detaches nothing
  inside a row, so the previous build keeps painting ON TOP of the next — the "ghosty
  duplicate" the human reported against the Advantages spike (2026-08-21), and before
  that `_clear_lay` in milestone 1 and `CatalogueDialog._clear_extras` in milestone 3.
  Every surface here builds its content as rows, so every surface hits this.
* **`deleteLater()` alone is deferred to the event loop.** A rebuild that runs several
  times synchronously (constructors, the first tab-change signal, `_sync_tabs`) leaves
  widgets that are merely pending-delete still painting at stale geometry, stacking each
  build on the last. Hide and unparent NOW; `deleteLater()` still frees the C++ object.

**Call this. Do not write a fresh loop** — that instruction was already in
`docs/plans/qt-port.md` and was not enough, which is why the shape is now a function
rather than a warning.

⚠ Test a teardown by THRASHING the rebuild and counting live descendants. A single
rebuild passes while leaking.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QLayout, QTreeWidget, QVBoxLayout

from .theme import MUTED


def empty_note(tree: QTreeWidget, text: str) -> QLabel:
    """Give `tree` a message that shows while it holds no rows. Returns the label.

    Input: a collection table and the sentence to show when it is empty. Output: a
    muted label laid over the table's viewport, visible only at zero rows. Mechanism:
    a layout on the viewport positions it; the model's own row signals toggle it, so
    nothing has to remember to.

    ⚠ **An empty table is indistinguishable from a broken one.** A header over a large
    blank rectangle reads as "nothing loaded" — reported against the adversary roster
    the first time it was opened (human, 2026-08-27), and every collection tab in the
    port had the same hole. The detail pane's "select something, or add one" sits on the
    far side of a splitter and does not answer it.

    ⚠ **Driven by the MODEL's signals, not by the callers.** Six `_fill_table`s would
    otherwise each have to toggle it, and the seventh would be written without. The
    repeated-warning-into-a-mechanism rule: `tree.clear()` emits `modelReset`, so this
    stays correct through every rebuild for free.
    """
    label = _EmptyNote(text, tree.model())
    lay = QVBoxLayout(tree.viewport())
    lay.setContentsMargins(24, 24, 24, 24)
    lay.addWidget(label)
    lay.addStretch(1)
    return label


class _EmptyNote(QLabel):
    """The label itself, and the RECEIVER of the model's signals.

    ⚠ A plain closure here is a crash. The tables on Advantages and Custom are rebuilt
    with their sub-tab pages, so the label is destroyed while its model outlives it —
    and a closure keeps firing into a deleted C++ object ("libshiboken: Internal C++
    object already deleted"). Qt drops a connection automatically when its RECEIVER is
    destroyed, so the slot has to be a bound method of a QObject, which is what this
    class exists to be.
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
