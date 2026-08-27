"""The Qt theme (exalted_builder/qt/theme.py) — the rules a stylesheet must carry.

⚠ **A QSS rule is invisible to every other test in the suite.** The port shipped with no
`QPushButton:disabled` rule, so every unmet-prerequisite "Add" across the whole app
looked clickable while 2,837 tests were green; the same hole for `QCheckBox` made the ST
Options tab's read-only lock indistinguishable from a live one. Both were found by
rendering the widget and LOOKING.

These tests render instead of grepping the stylesheet: they compare the actual pixels of
an enabled control against a disabled one. A rule that exists but does not bite (wrong
selector, overridden by a later rule) fails here; a reworded stylesheet does not.

⚠ Checked-disabled must differ from unchecked-disabled too. Styling
`QCheckBox::indicator:disabled` alone replaces the tick with nothing, and a locked rule
that is ON would then render exactly like one that is OFF.
"""

import pytest

# ⚠ PySide6 is the OPTIONAL `qt` extra (pyproject), so it is legitimately absent on a
# machine that only runs the webapp. Skip the module rather than letting a bare import
# turn into a COLLECTION ERROR — that kills the whole run, not just these tests.
pytest.importorskip("PySide6", reason="the optional [qt] extra is not installed")

from PySide6.QtCore import QRect
from PySide6.QtWidgets import QCheckBox, QPushButton, QVBoxLayout, QWidget

from exalted_builder.qt import theme as qtheme
from exalted_builder.ui import theme

# The checkbox INDICATOR only — the little box, not its caption.
#
# ⚠ Comparing whole checkboxes proves nothing. Qt dims the disabled TEXT on its own, so
# "enabled" and "disabled" images differ whether or not the indicator was fixed: this
# test passed against the very defect it is named for until it was cropped. The
# indicator is what a player looks at to see whether a control is live.
_INDICATOR = QRect(0, 0, 18, 18)


def _render(qtbot, make, crop=None):
    """Render one control inside a themed host and return its pixels."""
    host = QWidget()
    lay = QVBoxLayout(host)
    widget = make()
    lay.addWidget(widget)
    qtheme.apply(host, theme.palette("Solar"))
    qtbot.addWidget(host)
    host.show()
    qtbot.waitExposed(host)
    image = widget.grab().toImage()
    return image if crop is None else image.copy(crop)


def _brightness(image) -> float:
    """Mean channel value over an image, 0 (black) to 255 (white)."""
    total = 0
    for y in range(image.height()):
        for x in range(image.width()):
            colour = image.pixelColor(x, y)
            total += colour.red() + colour.green() + colour.blue()
    return total / (image.width() * image.height() * 3)


def _button(enabled):
    def make():
        b = QPushButton("Add")
        b.setEnabled(enabled)
        return b
    return make


def _check(enabled, checked):
    def make():
        b = QCheckBox("Switched on")
        b.setChecked(checked)
        b.setEnabled(enabled)
        return b
    return make


def test_a_disabled_button_does_not_look_live(qtbot):
    """The original defect: the QSS gives every QPushButton the card shade, and a
    stylesheet beats the palette Qt would otherwise have greyed."""
    live = _render(qtbot, _button(True))
    dead = _render(qtbot, _button(False))
    assert live != dead


def test_a_disabled_checkbox_indicator_does_not_look_live(qtbot):
    """The same defect one widget class over — the state the ST Options lock relies on.

    ⚠ Compares BRIGHTNESS, not pixel equality. Qt's own drawing of the two states is not
    byte-identical (antialiasing on the border), so `!=` passed against the very defect
    this is named for; the measured gap was 7 out of 255, and INVERTED for a ticked box
    — the disabled one came out brighter. A player reads "live" off the bright fill, so
    that is what the assertion measures."""
    for checked in (False, True):
        live = _brightness(_render(qtbot, _check(True, checked), _INDICATOR))
        dead = _brightness(_render(qtbot, _check(False, checked), _INDICATOR))
        assert dead < live - 20, f"checked={checked}: live {live}, disabled {dead}"


def test_a_disabled_checkbox_still_shows_whether_it_is_on(qtbot):
    """⚠ The negative control for the fix above. Greying the indicator by replacing its
    drawing loses the tick, and a locked rule that is ON reads as OFF."""
    off = _brightness(_render(qtbot, _check(False, False), _INDICATOR))
    on = _brightness(_render(qtbot, _check(False, True), _INDICATOR))
    assert abs(on - off) > 20, f"off {off}, on {on}"
