"""exalted_builder/qt/layout.py — layout teardown, in ONE place.

Input: a QLayout. Output: it is emptied and every descendant detached from rendering
immediately. Mechanism: take each item; hide, unparent and `deleteLater()` a widget;
RECURSE into a nested layout.

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

from PySide6.QtWidgets import QLayout


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
