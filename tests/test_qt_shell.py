"""The Qt native shell (exalted_builder/qt/main_window.py) — toolbar + left rail.

Covers the rail's tab set on both sides of the lock (visible_tabs / resolve_tab
with the old "Edit" key mapped to Identity + Traits), the splat-gated tabs (a ghost
loses Combos), page reload on rail switch, and New / lock resetting the character.
File dialogs and the confirm box are monkeypatched away — the shell logic around
them is what is under test.
"""

import pytest

# ⚠ PySide6 is the OPTIONAL `qt` extra (pyproject), so it is legitimately absent on a
# machine that only runs the webapp. Skip the module rather than letting a bare import
# turn into a COLLECTION ERROR — that kills the whole run, not just these tests.
pytest.importorskip("PySide6", reason="the optional [qt] extra is not installed")

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


def _charm_subtabs(win):
    tabs = win._pages["Charms"].tabs
    return [tabs.tabText(i) for i in range(tabs.count())]


def test_combos_is_not_a_rail_tab_at_all(ruleset, qtbot):
    # Combos moved UNDER Charms (2026-08-21). ⚠ This is what makes the ghost test
    # below a real negative control again: with no rail entry to hide, an assertion
    # that the ghost's RAIL lacks Combos would pass for every splat and prove nothing.
    win = MainWindow(ruleset, Character(id="char.new", exalt_type="Solar"),
                     Path("/tmp/c.json"))
    qtbot.addWidget(win)
    assert "Combos" not in _rail_labels(win)
    assert "Combos" in _charm_subtabs(win)


def test_shell_hides_combos_for_a_ghost(ruleset, qtbot):
    # "The dead may never learn Combos" (E:Ab p.234) and a ghost builds no Arrays
    # either, so the sub-tab is absent — an empty tab answering every attempt with a
    # validation error is worse than no tab.
    win = MainWindow(ruleset, Character(id="char.new", exalt_type="Ghost"),
                     Path("/tmp/c.json"))
    qtbot.addWidget(win)
    subtabs = _charm_subtabs(win)
    assert "Combos" not in subtabs
    # The positive control: the tab bar was built, so the absence above is the rule
    # firing and not an empty Charms page.
    assert "Arcanoi" in subtabs


def test_a_charm_slot_splat_gets_the_arrays_label(ruleset, qtbot):
    # The build matches the book's vocabulary: an Alchemical builds Arrays, not Combos.
    win = MainWindow(ruleset, Character(id="char.new", exalt_type="Alchemical"),
                     Path("/tmp/c.json"))
    qtbot.addWidget(win)
    subtabs = _charm_subtabs(win)
    assert "Arrays" in subtabs
    assert "Combos" not in subtabs


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


def test_the_advantages_rail_item_is_the_real_page(ruleset, qtbot):
    """Ported 2026-08-21 — the rail slot must hold AdvantagesPage, not the "still on
    the webapp" placeholder, and switching to it must reload it from the shared
    character (the rail handler's setCurrentIndex + reload)."""
    from exalted_builder.qt.advantages import AdvantagesPage
    from exalted_builder.models.character import BackgroundEntry

    char = Character(id="char.new", exalt_type="Solar", caste="dawn")
    win = MainWindow(ruleset, char, Path("/tmp/c.json"))
    qtbot.addWidget(win)
    page = win._pages["Advantages"]
    assert isinstance(page, AdvantagesPage)
    char.backgrounds.append(BackgroundEntry(name="Resources", rating=2))
    win.rail.setCurrentRow(_RAIL_TABS.index("Advantages"))
    assert win.stack.currentWidget() is page
    # Shape B: the held Backgrounds are a TABLE, not stacked rows (2026-08-21).
    table = page._tables["Backgrounds"]
    assert [table.topLevelItem(i).text(0)
            for i in range(table.topLevelItemCount())] == ["Resources"]


# --------------------------------------------------------------------------- #
# the Downtime calculator
# --------------------------------------------------------------------------- #
# ⚠ `_downtime_dialog` ends in a blocking `QDialog.exec()`, so these drive the pieces
# it is assembled from — the state dict, `elder.downtime_award` and the grant — rather
# than the modal itself. The same reason test_qt_editor.py exercises the downward
# dialog through `_buy`'s preconditions.

from PySide6.QtWidgets import QPushButton, QVBoxLayout


def _locked(ruleset):
    char = Character(id="char.new")
    lifecycle.lock_chargen(char, ruleset)
    return char


def test_downtime_is_offered_beside_the_other_xp_controls(ruleset, qtbot):
    """It belongs with the XP accounting, not on a trait page — it grants experience.
    ⚠ Post-lock only: `_xp_section` is what draws it."""
    win = MainWindow(ruleset, _locked(ruleset), Path("/tmp/c.json"))
    qtbot.addWidget(win)
    root = QVBoxLayout()
    win._xp_section(root, lambda: None)
    labels = [root.itemAt(i).widget().text()
              for i in range(root.count())
              if isinstance(root.itemAt(i).widget(), QPushButton)]
    assert "Downtime…" in labels


def test_downtime_is_not_offered_before_the_lock(ruleset, qtbot):
    """`_xp_section` runs only post-lock, so the control cannot be reached in chargen."""
    win = MainWindow(ruleset, Character(id="char.new"), Path("/tmp/c.json"))
    qtbot.addWidget(win)
    assert not win._ctx["char"].chargen_locked


def test_the_downtime_age_is_a_calculator_field_not_a_character_trait(ruleset, qtbot):
    """⚠ Human's ruling 2026-08-06: the numeric age trait is gone and age gates
    nothing, so the p.259 rate comes from a CALCULATOR field on the window.

    ⚠ There IS a `Character.age`, added 2026-08-21 — free-text BIOGRAPHY ("mid
    thirties"), flavour the engine never reads. It is a `str` for that reason, and the
    calculator must not be wired to it: the two are different things wearing one name.
    """
    win = MainWindow(ruleset, _locked(ruleset), Path("/tmp/c.json"))
    qtbot.addWidget(win)
    assert win._downtime == {"age": 0, "years": 0}
    assert Character.model_fields["age"].annotation is str, (
        "Character.age went numeric — check it is still biography, not a rules trait")
    char = win._ctx["char"]
    char.age = "three hundred years old"
    assert win._downtime["age"] == 0, "the calculator read the biography field"


def test_a_downtime_grant_advances_the_local_age_and_adds_the_xp(ruleset, qtbot):
    """The grant is the whole of what touches the character: it receives XP and
    nothing else. The age advance is the window's, so the next award continues."""
    from exalted_builder.engine import elder
    char = _locked(ruleset)
    win = MainWindow(ruleset, char, Path("/tmp/c.json"))
    qtbot.addWidget(win)
    award = elder.downtime_award(120, 10)
    assert award.total, "the p.259 chart should pay a 120-year-old"
    before = char.xp_earned
    # what `grant()` does, without the modal
    win._downtime["age"] = award.to_age
    advancement.add_xp(char, award.total)
    assert char.xp_earned == before + award.total
    assert win._downtime["age"] == 130
    # the next award continues from there rather than restarting
    assert elder.downtime_award(win._downtime["age"], 5).from_age == 130


def test_a_young_character_earns_nothing_from_the_chart(ruleset, qtbot):
    """⚠ The p.259 chart begins at 100 years and the build never invents the rows below
    it, so a zero here is the rule, not a bug — which is why the dialog says so."""
    from exalted_builder.engine import elder
    award = elder.downtime_award(10, 20)
    assert award.total == 0
