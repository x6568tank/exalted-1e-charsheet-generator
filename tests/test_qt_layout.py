"""exalted_builder/qt/layout.py — the one teardown, tested where it lives.

⚠ This helper exists because the same six-line loop was hand-written six times and the
sixth was wrong. Its two halves are both non-obvious and both have shipped as bugs, so
each gets a test that FAILS against the naive version:

* a widget-only sweep leaves nested layouts untouched (the "ghosty duplicate");
* `deleteLater()` alone leaves the widget parented and painting until the event loop
  runs.

⚠ The leak test THRASHES the rebuild. A single teardown passes while leaking.
"""

import pytest

# ⚠ PySide6 is the OPTIONAL `qt` extra (pyproject), so it is legitimately absent on a
# machine that only runs the webapp. Skip the module rather than letting a bare import
# turn into a COLLECTION ERROR — that kills the whole run, not just these tests.
pytest.importorskip("PySide6", reason="the optional [qt] extra is not installed")

from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from exalted_builder.qt.layout import clear_layout


def _nested(host: QWidget) -> QVBoxLayout:
    """A layout shaped like every surface in the app: labels at the top level, and more
    labels inside a nested row — which is where the naive sweep fails."""
    lay = host.layout() or QVBoxLayout(host)
    lay.addWidget(QLabel("top level"))
    row = QHBoxLayout()
    row.addWidget(QLabel("inside a row"))
    row.addWidget(QLabel("also inside"))
    lay.addLayout(row)
    deeper = QHBoxLayout()
    inner = QVBoxLayout()
    inner.addWidget(QLabel("two levels down"))
    deeper.addLayout(inner)
    lay.addLayout(deeper)
    return lay


def test_it_empties_the_layout(qtbot):
    host = QWidget()
    qtbot.addWidget(host)
    lay = _nested(host)
    assert lay.count()
    clear_layout(lay)
    assert lay.count() == 0


def test_it_recurses_into_nested_layouts(qtbot):
    """⚠ The bug that keeps recurring. `item.widget()` is None for a `QLayout`, so a
    widget-only sweep detaches nothing inside a row and the previous build paints ON
    TOP of the next."""
    host = QWidget()
    qtbot.addWidget(host)
    _nested(host)
    assert len(host.findChildren(QLabel)) == 4
    clear_layout(host.layout())
    assert host.findChildren(QLabel) == []


def test_it_unparents_immediately_not_on_the_event_loop(qtbot):
    """⚠ `deleteLater()` is deferred, and a build whose children are merely
    pending-delete keeps painting at stale geometry on top of the next one. The
    detach has to have happened by the time this function returns."""
    host = QWidget()
    qtbot.addWidget(host)
    lay = QVBoxLayout(host)
    label = QLabel("doomed")
    lay.addWidget(label)
    assert label.parent() is host
    clear_layout(lay)
    assert label.parent() is None
    assert label.isHidden()


def test_thrashing_a_rebuild_does_not_leak(qtbot):
    """A single teardown passes while leaking — so rebuild several times and count."""
    host = QWidget()
    qtbot.addWidget(host)
    lay = QVBoxLayout(host)
    for _ in range(6):
        clear_layout(lay)
        lay.addWidget(QLabel("top level"))
        row = QHBoxLayout()
        row.addWidget(QLabel("inside a row"))
        lay.addLayout(row)
    assert len(host.findChildren(QLabel)) == 2


def test_an_already_empty_layout_is_fine(qtbot):
    host = QWidget()
    qtbot.addWidget(host)
    lay = QVBoxLayout(host)
    clear_layout(lay)
    clear_layout(lay)
    assert lay.count() == 0


def test_a_naive_widget_only_sweep_would_fail_these(qtbot):
    """The negative control: the loop this helper replaced, run against the same
    fixture, leaves the nested labels behind. Without this, the two tests above look
    like they are asserting something trivially true of any teardown."""
    host = QWidget()
    qtbot.addWidget(host)
    lay = _nested(host)
    while lay.count():                       # the WRONG shape, deliberately
        item = lay.takeAt(0)
        if item.widget() is not None:
            item.widget().setParent(None)
    assert len(host.findChildren(QLabel)) == 3      # the three nested ones survive
