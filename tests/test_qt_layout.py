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


# --------------------------------------------------------------------------- #
# The empty-table note
# --------------------------------------------------------------------------- #

def _tree(qtbot, rows=0):
    from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem
    tree = QTreeWidget()
    tree.setColumnCount(1)
    qtbot.addWidget(tree)
    for i in range(rows):
        tree.addTopLevelItem(QTreeWidgetItem([f"row {i}"]))
    return tree


def test_the_note_shows_only_while_the_table_is_empty(qtbot):
    from PySide6.QtWidgets import QTreeWidgetItem

    from exalted_builder.qt.layout import empty_note
    tree = _tree(qtbot)
    note = empty_note(tree, "Nothing yet.")
    assert note.isVisibleTo(tree)
    tree.addTopLevelItem(QTreeWidgetItem(["a bandit"]))
    assert not note.isVisibleTo(tree)
    tree.takeTopLevelItem(0)
    assert note.isVisibleTo(tree)


def test_the_note_survives_a_clear_and_refill(qtbot):
    """⚠ `clear()` emits modelReset, not rowsRemoved. A note wired only to the row
    signals comes back from a rebuild permanently hidden — and every `_fill_table` in
    the port clears before it fills."""
    from PySide6.QtWidgets import QTreeWidgetItem

    from exalted_builder.qt.layout import empty_note
    tree = _tree(qtbot, rows=3)
    note = empty_note(tree, "Nothing yet.")
    assert not note.isVisibleTo(tree)
    tree.clear()
    assert note.isVisibleTo(tree)
    tree.addTopLevelItem(QTreeWidgetItem(["back"]))
    assert not note.isVisibleTo(tree)


def test_the_note_is_the_receiver_so_a_dead_label_cannot_be_signalled(qtbot):
    """⚠ A plain closure crashes here: the Advantages and Custom tables are rebuilt with
    their sub-tab pages, so the label dies while its model lives on, and the next signal
    fires into a deleted C++ object. Qt drops a connection when its RECEIVER dies — which
    only works because the slot is a bound method of the label.

    ⚠ The failure is ASYNCHRONOUS to the test that causes it: the RuntimeError surfaces
    inside Qt's event loop, so without `capture_exceptions` it fails whichever test runs
    next and this one passes. Negative-controlled by putting the closure back.
    """
    from PySide6.QtWidgets import QApplication, QTreeWidgetItem

    from exalted_builder.qt.layout import empty_note
    tree = _tree(qtbot)
    note = empty_note(tree, "Nothing yet.")
    # The contract, asserted structurally: the slot is a BOUND METHOD OF THE LABEL, which
    # is the only reason Qt can drop the connection when the label dies. A closure would
    # satisfy every behavioural test above and still crash in the app.
    assert note.sync.__self__ is note
    note.setParent(None)
    note.deleteLater()
    del note
    QApplication.processEvents()                 # the delete actually happens here
    tree.addTopLevelItem(QTreeWidgetItem(["a bandit"]))
    tree.clear()
