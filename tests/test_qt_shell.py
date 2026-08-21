"""The Qt native shell (exalted_builder/qt/main_window.py) — toolbar + left rail.

Covers the rail's tab set on both sides of the lock (visible_tabs / resolve_tab
with the old "Edit" key mapped to Identity + Traits), the splat-gated tabs (a ghost
loses Combos), page reload on rail switch, and New / lock resetting the character.
File dialogs and the confirm box are monkeypatched away — the shell logic around
them is what is under test.
"""

from pathlib import Path

from PySide6.QtGui import QPalette

from exalted_builder.engine import advancement, lifecycle
from exalted_builder.models.character import Character
from exalted_builder.qt import theme as qtheme
from exalted_builder.qt.main_window import MainWindow, _RAIL_LABELS, _RAIL_TABS
from exalted_builder.ui.theme import palette


def _rail_labels(win):
    return [win.rail.item(i).text() for i in range(win.rail.count())]


def _visible(win):
    return [win.rail.item(i).text() for i in range(win.rail.count())
            if not win.rail.item(i).isHidden()]


def test_shell_rail_for_a_fresh_character(ruleset, qtbot):
    win = MainWindow(ruleset, Character(id="char.new"), Path("/tmp/c.json"))
    qtbot.addWidget(win)
    assert _rail_labels(win) == [_RAIL_LABELS[n] for n in _RAIL_TABS]
    assert "Play" not in _visible(win)          # Play is locked-only


def test_theme_does_not_border_every_widget():
    # A visible border on every input/button/card read as "a border around every
    # element" — the flat design leaves borders off everything; the card shade and
    # the accent carry the structure.
    solar_qss = qtheme.qss(palette("Solar"))
    assert "QLineEdit, QSpinBox, QComboBox, QListWidget, QTextEdit {" in solar_qss
    assert "border:none" in solar_qss


def test_shell_themes_to_the_splat_palette(ruleset, qtbot):
    # The desktop look: ONE unified dark base for every splat; switching splat moves
    # the ACCENT (toolbar, headings) — lightened from the printed palette so it reads
    # on the dark base — not the page background.
    win = MainWindow(ruleset, Character(id="char.new", exalt_type="Solar"),
                     Path("/tmp/c.json"))
    qtbot.addWidget(win)
    assert win.palette().color(QPalette.Window).name() == qtheme.BG
    assert qtheme.accent(palette("Solar")) in win.styleSheet()
    win._ctx["char"].exalt_type = "Dragon-Blooded"
    win._apply_chrome()
    assert qtheme.accent(palette("Dragon-Blooded")) in win.styleSheet()
    assert win.palette().color(QPalette.Window).name() == qtheme.BG


def test_shell_central_widget_has_the_pages(ruleset, qtbot):
    # Regression: the tab bar was built but never made the central widget, so the
    # window's content area rendered blank gray under the toolbar.
    win = MainWindow(ruleset, Character(id="char.new"), Path("/tmp/c.json"))
    qtbot.addWidget(win)
    assert win.centralWidget() is not None
    assert win._pages["Identity"] is not None
    assert win._pages["Traits"] is not None
    assert win._pages["Identity"].isVisibleTo(win)


def test_shell_readout_and_status_strips_exist(ruleset, qtbot):
    win = MainWindow(ruleset, Character(id="char.new"), Path("/tmp/c.json"))
    qtbot.addWidget(win)
    assert "bonus points" in win.readout.text()
    assert "Willpower" in win.status.text()


def test_shell_adds_play_at_the_lock(ruleset, qtbot):
    char = Character(id="char.new")
    win = MainWindow(ruleset, char, Path("/tmp/c.json"))
    qtbot.addWidget(win)
    advancement.add_xp(char, 10)
    lifecycle.lock_chargen(char, ruleset)
    win._sync_tabs()
    assert "Play" in _visible(win)


def test_shell_hides_combos_for_a_ghost(ruleset, qtbot):
    win = MainWindow(ruleset, Character(id="char.new", exalt_type="Ghost"),
                     Path("/tmp/c.json"))
    qtbot.addWidget(win)
    assert "Combos" not in _visible(win)


def test_shell_lands_on_identity_when_play_disappears(ruleset, qtbot):
    char = Character(id="char.new")
    win = MainWindow(ruleset, char, Path("/tmp/c.json"))
    qtbot.addWidget(win)
    advancement.add_xp(char, 10)
    lifecycle.lock_chargen(char, ruleset)
    win._sync_tabs()
    win._state["tab"] = "Play"
    win.rail.setCurrentRow(_RAIL_TABS.index("Play"))
    lifecycle.unlock_chargen(char)
    win._sync_tabs()
    # resolve_tab returns the old "Edit"; the shell lands on Identity.
    assert win._state["tab"] == "Identity"


def test_shell_switching_to_sheet_reloads_it(ruleset, qtbot):
    char = Character(id="char.new", name="Shown")
    win = MainWindow(ruleset, char, Path("/tmp/c.json"))
    qtbot.addWidget(win)
    sheet = win._pages["Sheet"]
    char.name = "Renamed"
    win.rail.setCurrentRow(_RAIL_TABS.index("Sheet"))
    assert "Renamed" in sheet.view.toPlainText()


def test_shell_new_resets_the_character(ruleset, qtbot, monkeypatch):
    char = Character(id="char.new", name="Old")
    win = MainWindow(ruleset, char, Path("/tmp/c.json"))
    qtbot.addWidget(win)
    monkeypatch.setattr("exalted_builder.qt.main_window.QMessageBox.question",
                        staticmethod(lambda *a, **k: 16384))   # Yes
    win._confirm_new()
    assert win._ctx["char"] is not char
    assert win._ctx["char"].name == ""
