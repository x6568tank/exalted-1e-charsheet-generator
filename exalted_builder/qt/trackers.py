"""exalted_builder/qt/trackers.py — the clickable tracker box, in ONE place.

Input: a name, a size, a fill colour and the splat accent. Output: a flat square
QPushButton the caller connects a click to. `MARK_FILL` is the colour a damage type
paints its box.

⚠ **One damage tracker, not three.** The Play tab, the party cards and the adversary
roster draw the same boxes. A Storyteller must not have to learn a second tracker
(`docs/status/adversary-roster.md`). Three copies of a colour map become different.

⚠ A box sets its own `:hover`. The shell stylesheet paints the hover of every
QPushButton with the splat accent. A FILLED box is already that colour. Thus an empty box
reads as full below the pointer.

⚠ Give each box a NAME for what it tracks (`play.health.3`, `adv.<id>.health.0`). Do not
use its position in a `findChildren` list. These surfaces contain many boxes of the same
shape, and an index selects the box that was built first.
"""

from __future__ import annotations

from PySide6.QtWidgets import QPushButton

from exalted_builder.models.character import Damage

MARK_FILL = {
    Damage.BASHING: "#6b7280",       # grey
    Damage.LETHAL: "#c0392b",        # red
    Damage.AGGRAVATED: "#9b59b6",    # purple
}


def _style(fill: str, accent: str) -> str:
    return (f"QPushButton {{ background:{fill}; color:#f4f2ee; border:none;"
            f" border-radius:3px; font-weight:700; padding:0px; }}"
            f"QPushButton:hover {{ background:{fill}; border:1px solid {accent}; }}")


def box(name: str, size: int, fill: str, accent: str, text: str = "") -> QPushButton:
    """One tracker box: `size`x`size`, filled with `fill`, outlined on hover."""
    button = QPushButton(text)
    button.setObjectName(name)
    button.setFixedSize(size, size)
    button.setFlat(True)
    button.setStyleSheet(_style(fill, accent))
    return button


def restyle(button: QPushButton, fill: str, accent: str, text: str = "") -> None:
    """Repaint an existing box, in place.

    Input: a box from `box`, its new fill and text. Output: the same button, repainted.

    ⚠ **A tracker repaints with RESTYLE. It must not rebuild its panel.** A rebuild
    deletes the button that the user clicked. Qt then gives the focus to a different
    widget, and a `QScrollArea` scrolls to that widget. Thus the pane moves to the bottom.
    A rebuild also moves the focus out of the surface, and the keyboard stops to operate.
    """
    button.setText(text)
    button.setStyleSheet(_style(fill, accent))
