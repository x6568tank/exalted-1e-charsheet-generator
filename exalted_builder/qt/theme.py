"""exalted_builder/qt/theme.py — the native-app theme.

This is a DESKTOP app. It does not copy the web app (human's ruling). It has one dark
scheme: the Qt6 dark-grey look, made brighter. The splat shows as LIGHT theming on text
and borders. It does not wash the page or the cards. The base (BG / CARD / INK) is one
dark neutral for every splat. The accent of the splat is made lighter, and it paints the
toolbar, the headings, the selected tab and the chips.

`apply(win, pal)` sets a QPalette and a QSS on a window. Thus a splat change re-themes the
shell. The Tailwind class strings of the web app do not transfer here. The accent hex in
the Palette is the one asset that transfers.
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QWidget

from exalted_builder.ui.theme import Palette

# The dark base. It is brighter than Qt's default dark grey (human's ruling).
BG = "#333338"          # page: a medium dark grey
CARD = "#3d3d45"        # cards: a small step lighter than the page
INPUT = "#52525c"       # editable fields: a large step lighter than CARD. ⚠ A step of
                        # +10 over CARD looks the same as CARD on a real display, and
                        # the field then reads as not editable.
TREE = "#41414a"        # charm-tree canvas: a small step lighter than the page
INK = "#e6e4e0"         # body text: off-white
MUTED = "#9a9894"       # secondary text
CUSTOM = "#a78bfa"      # the homebrew mark. It is violet, and it is NOT a splat accent.
                        # Thus "no rulebook gives this" looks the same on every splat.
                        # The text-violet-700 of the webapp is dark and is not visible here.


def accent(pal: Palette) -> str:
    """The splat accent LIGHTENED for use as text/fills on the dark base.

    Input: a Palette. Output: the accent hex, mixed toward white. The printed accents are
    dark (Solar amber #8a5a1a, Dragon-Blooded crimson #8a1a1a). They are correct on
    parchment, but they are not visible on a dark page. The mix keeps the hue of each
    splat and makes the colour readable."""
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
    """The shell stylesheet. The toolbar takes the accent of the splat. The tab underline
    and the selected states show the accent as small light areas on the dark base.
    Elements have no borders. The lighter card shade on the dark page divides them."""
    ac = accent(pal)
    return f"""
QToolBar {{ background:{ac}; color:#1a1a1a; }}
QToolBar QToolButton {{ color:#1a1a1a; }}
/* ⚠ Paint the BAR, not the tabs only. `background:transparent` on a tab shows what the
   base style paints below it. On Linux/Fusion that is the dark BG of the window, which
   is correct. The Windows style paints a LIGHT tab strip there. Thus every sub-tab row
   in the port (Charms, Gear, Advantages, Custom, the party window) becomes a white band
   on Windows, and the same build is correct on Linux. This is the same type of fault as
   the QDialog rule below. An unstyled class falls back to the chrome of the PLATFORM,
   and that chrome is light.
   ⚠ You cannot cause this fault on Linux. Neither Fusion nor the "Windows" style paints
   the strip. Thus a render test here cannot guard it. */
QTabWidget {{ background:{BG}; }}
QTabWidget::pane {{ border:none; background:{BG}; }}
QTabBar {{ background:{BG}; border:none; }}
QTabBar::tab {{ background:{BG}; color:{INK}; padding:6px 14px; }}
QTabBar::tab:selected {{ color:{ac}; font-weight:bold;
                        border-bottom:2px solid {ac}; }}
QScrollArea {{ background:{BG}; border:none; }}
QScrollArea QWidget#qt_scrollarea_viewport {{ background:{BG}; }}
QScrollArea > QWidget > QWidget {{ background:{BG}; }}
QLabel {{ color:{INK}; }}
QPushButton {{ background:{CARD}; color:{INK}; border:none;
               border-radius:4px; padding:4px 10px; }}
QPushButton:hover {{ background:{ac}; color:#1a1a1a; }}
/* ⚠ Without this rule, a DISABLED button looks the same as an enabled button. The rule
   above gives the card shade to every QPushButton, and a stylesheet beats the palette
   that Qt makes grey. Thus every "Add" button with unsatisfied prerequisites reads as
   clickable, across the whole port. */
QPushButton:disabled {{ background:{BG}; color:{MUTED}; }}
QPushButton:disabled:hover {{ background:{BG}; color:{MUTED}; }}
/* ⚠ The SAME defect occurs one widget class over. A disabled QCheckBox draws the same
   bright indicator as an enabled one, because the stylesheet renderer removes the grey
   of the base style. Thus the read-only lock on the ST Options tab and the unavailable
   pool boxes on Play read as clickable. Style the DISABLED states only. The enabled
   look is the native one.
   ⚠ Keep checked-disabled different from unchecked-disabled. If you style
   `::indicator:disabled` alone, the tick becomes empty, and a locked rule that is ON
   reads as OFF. The filled MUTED square shows "on, and frozen". */
QCheckBox:disabled {{ color:{MUTED}; }}
QCheckBox::indicator:disabled {{ background:{BG}; border:1px solid {MUTED};
                                 border-radius:3px; }}
QCheckBox::indicator:checked:disabled {{ background:{MUTED}; border:1px solid {MUTED}; }}
/* ⚠ A QDialog is a top-level WINDOW. It does not get the QPalette of the main window.
   If no rule here names it, every dialog in the port draws the light #efefef of the
   platform. It shows as a thin light edge around the catalogue and the details popover,
   whose content fills the area. It shows as a large light page around a dialog that has
   margins. This rule corrects every dialog. */
QDialog {{ background:{BG}; }}
/* ⚠ A class that this list does not name is unstyled. QTextEdit was here and
   QPlainTextEdit was absent. Thus a paste box drew white on white next to a correctly
   themed read-only pane. When you add a class here, check its SIBLING classes. */
QLineEdit, QSpinBox, QComboBox, QListWidget, QTextEdit, QPlainTextEdit {{
    background:{INPUT}; color:{INK}; border:none;
    border-radius:4px; padding:2px 5px; }}
QComboBox QAbstractItemView {{ background:{INPUT}; color:{INK};
    selection-background-color:{ac}; selection-color:#1a1a1a; }}
QCompleter QAbstractItemView {{ background:{INPUT}; color:{INK};
    selection-background-color:{ac}; selection-color:#1a1a1a; }}
QTextBrowser {{ background:{CARD}; color:{INK}; border:none; }}
/* ⚠ Style the trees here. Do not leave them to the QPalette. A stylesheet on the window
   gives every descendant to the stylesheet renderer, and that renderer ignores
   `QPalette.Base`. Thus the Gear and Advantages trees paint WHITE on the dark page while
   every other widget is correct. AN ANCESTOR STYLESHEET ALWAYS BEATS A PALETTE THAT YOU
   SET ON THE WIDGET. */
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
