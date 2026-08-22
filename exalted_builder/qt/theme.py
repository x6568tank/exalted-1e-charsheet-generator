"""exalted_builder/qt/theme.py — the native-app theme.

The human's direction (2026-08-20): a DESKTOP app, not a web-app mimicry. One unified
DARK scheme — the Qt6 dark-grey look, brightened — with the splat showing through as
LIGHT theming on text and borders, not as page/card washes. The base (BG / CARD / INK)
is a single dark neutral for every splat; the splat's accent is lightened (the printed
palette accents are dark tones that would vanish on a dark base) and used for the
toolbar, the headings, the selected tab and chips.

`apply(win, pal)` sets a QPalette + QSS on a window, so a splat change re-themes the
shell. The web app's Tailwind class strings don't translate; the accent hex in the
Palette is the asset that does.
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QWidget

from exalted_builder.ui.theme import Palette

# The unified dark base — brighter than Qt's default dark grey, per the human.
BG = "#333338"          # page: a medium dark grey
CARD = "#3d3d45"        # cards: a touch lighter than the page
INPUT = "#52525c"       # editable fields: a clear step lighter than CARD — the old
                        # #47474f was only +10 over the card and read as the same
                        # shade on a real display (the "fill-in invisible" report).
TREE = "#41414a"        # charm-tree canvas: a little lighter than the page
INK = "#e6e4e0"         # body text: off-white
MUTED = "#9a9894"       # secondary text


def accent(pal: Palette) -> str:
    """The splat accent LIGHTENED for use as text/fills on the dark base.

    The printed palette accents are dark (Solar amber #8a5a1a, Dragon-Blooded crimson
    #8a1a1a) — fine on parchment, invisible on a dark page. Lightening toward white
    keeps each splat's hue while making it readable."""
    rgb = tuple(int(pal.accent[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % tuple(round(c * 0.35 + 255 * 0.65) for c in rgb)


def qpalette(pal: Palette) -> QPalette:
    """The base Qt palette: dark neutral window, off-white text, lighter inputs."""
    p = QPalette()
    p.setColor(QPalette.Window, QColor(BG))
    p.setColor(QPalette.WindowText, QColor(INK))
    p.setColor(QPalette.Base, QColor(CARD))
    p.setColor(QPalette.Text, QColor(INK))
    p.setColor(QPalette.Button, QColor(BG))
    p.setColor(QPalette.ButtonText, QColor(INK))
    p.setColor(QPalette.Highlight, QColor(accent(pal)))
    p.setColor(QPalette.HighlightedText, QColor("#1a1a1a"))
    p.setColor(QPalette.ToolTipBase, QColor(CARD))
    p.setColor(QPalette.ToolTipText, QColor(INK))
    return p


def qss(pal: Palette) -> str:
    """The shell stylesheet. The toolbar is the splat's accent; the tab underline and
    the selected states carry it as light touches on the dark base. No element
    borders — the lighter card shade on the dark page is the delineation."""
    ac = accent(pal)
    return f"""
QToolBar {{ background:{ac}; color:#1a1a1a; }}
QToolBar QToolButton {{ color:#1a1a1a; }}
QTabWidget::pane {{ border:none; background:{BG}; }}
QTabBar::tab {{ background:transparent; color:{INK}; padding:6px 14px; }}
QTabBar::tab:selected {{ color:{ac}; font-weight:bold;
                        border-bottom:2px solid {ac}; }}
QScrollArea {{ background:{BG}; border:none; }}
QScrollArea QWidget#qt_scrollarea_viewport {{ background:{BG}; }}
QScrollArea > QWidget > QWidget {{ background:{BG}; }}
QLabel {{ color:{INK}; }}
QPushButton {{ background:{CARD}; color:{INK}; border:none;
               border-radius:4px; padding:4px 10px; }}
QPushButton:hover {{ background:{ac}; color:#1a1a1a; }}
QLineEdit, QSpinBox, QComboBox, QListWidget, QTextEdit {{
    background:{INPUT}; color:{INK}; border:none;
    border-radius:4px; padding:2px 5px; }}
QComboBox QAbstractItemView {{ background:{INPUT}; color:{INK};
    selection-background-color:{ac}; selection-color:#1a1a1a; }}
QCompleter QAbstractItemView {{ background:{INPUT}; color:{INK};
    selection-background-color:{ac}; selection-color:#1a1a1a; }}
QTextBrowser {{ background:{CARD}; color:{INK}; border:none; }}
/* ⚠ The trees MUST be styled here, not left to the QPalette. Setting a stylesheet on
   the window hands the stylesheet renderer every descendant, and it ignores
   `QPalette.Base` — so the Gear and Advantages trees painted WHITE on the dark page
   while every other widget themed correctly. Same trap as the QTextEdit-in-a-_Panel
   one: an ancestor stylesheet beats a set palette, every time. */
QTreeWidget, QTreeView {{ background:{CARD}; color:{INK}; border:none;
                          alternate-background-color:{CARD}; }}
QTreeWidget::item, QTreeView::item {{ padding:2px 0px; }}
QTreeWidget::item:selected, QTreeView::item:selected {{
    background:{ac}; color:#1a1a1a; }}
QHeaderView::section {{ background:{BG}; color:{MUTED}; border:none;
                        padding:4px 6px; font-weight:600; }}
QTreeWidget QHeaderView::section:hover {{ color:{INK}; }}
QListWidget#appRail {{ background:{BG}; border:none; }}
QListWidget#appRail::item {{ padding:8px 10px; border-radius:4px; }}
QListWidget#appRail::item:hover {{ background:{CARD}; }}
QListWidget#appRail::item:selected {{ background:{ac}; color:#1a1a1a; font-weight:600; }}
"""


def apply(win: QWidget, pal: Palette) -> None:
    """Theme `win` and everything under it for the splat's palette."""
    win.setPalette(qpalette(pal))
    win.setStyleSheet(qss(pal))
