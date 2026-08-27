"""exalted_builder/qt/trackers.py — the clickable tracker box, in ONE place.

Input: a name, a size, a fill colour and the splat accent. Output: a flat square
QPushButton the caller connects a click to. `MARK_FILL` is the colour a damage type
paints its box.

⚠ **One damage tracker, not three.** The Play tab, the party cards and the adversary
roster all draw the same boxes, and the roster's whole reason for existing is that a
Storyteller should not have to learn a second one (`docs/status/adversary-roster.md`).
Three copies of a colour map is how they drift.

⚠ A box's own `:hover` is set explicitly. The shell stylesheet paints every
QPushButton's hover the splat accent — which is exactly the colour a FILLED box already
is — so an empty box would read as full under the mouse.

⚠ Boxes are NAMED after what they track (`play.health.3`, `adv.<id>.health.0`), never
left to their position in a `findChildren` list: these surfaces are full of same-shaped
boxes and an index picks whichever was built first.
"""

from __future__ import annotations

from PySide6.QtWidgets import QPushButton

from exalted_builder.models.character import Damage

MARK_FILL = {
    Damage.BASHING: "#6b7280",       # grey
    Damage.LETHAL: "#c0392b",        # red
    Damage.AGGRAVATED: "#9b59b6",    # purple
}


def box(name: str, size: int, fill: str, accent: str, text: str = "") -> QPushButton:
    """One tracker box: `size`x`size`, filled with `fill`, outlined on hover."""
    button = QPushButton(text)
    button.setObjectName(name)
    button.setFixedSize(size, size)
    button.setFlat(True)
    button.setStyleSheet(
        f"QPushButton {{ background:{fill}; color:#f4f2ee; border:none;"
        f" border-radius:3px; font-weight:700; padding:0px; }}"
        f"QPushButton:hover {{ background:{fill}; border:1px solid {accent}; }}")
    return button
