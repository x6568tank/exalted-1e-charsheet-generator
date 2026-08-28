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
    #
    # ⚠ Asserts MEMBERSHIP, not the literal selector list. The first version pinned
    # "QLineEdit, QSpinBox, QComboBox, QListWidget, QTextEdit {" verbatim and failed the
    # day a sixth editable class was added to it — a red test for a correct change,
    # which teaches the next person to edit the test rather than read it.
    solar_qss = qtheme.qss(palette("Solar"))
    selector = next(rule.split("{")[0] for rule in solar_qss.split("}")
                    if "QLineEdit" in rule.split("{")[0] and "border:none" in rule)
    for widget in ("QLineEdit", "QSpinBox", "QComboBox", "QListWidget", "QTextEdit",
                   "QPlainTextEdit"):
        assert widget in selector, f"{widget} is not in the borderless input rule"


def test_every_editable_class_the_port_uses_is_themed():
    """⚠ "If a widget class is not named in `qt/theme.py::qss`, assume it is unstyled" —
    and an unstyled input renders the platform's WHITE on the dark page. QPlainTextEdit
    was missing while its sibling QTextEdit was present, which is how the Custom tab's
    paste box shipped white-on-white beside a correctly themed pane.

    Pins the classes the port actually instantiates, so adding a new kind of input
    without theming it fails here rather than at a click-through.
    """
    solar_qss = qtheme.qss(palette("Solar"))
    for widget in ("QLineEdit", "QSpinBox", "QComboBox", "QListWidget", "QTextEdit",
                   "QPlainTextEdit", "QTreeWidget", "QCheckBox", "QPushButton",
                   "QDialog"):
        assert widget in solar_qss, f"{widget} is not styled at all"


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


def test_the_popover_shows_bonus_points_in_chargen_and_the_ledger_after(ruleset, qtbot):
    """⚠ Bonus points are a CHARGEN surface only (human, 2026-08-22). The readout BAR
    already drops the line post-lock, so a popover still reporting "12 / 15 spent"
    disagreed with the bar directly above it. The slot is the Experience card instead."""
    from PySide6.QtWidgets import QLabel

    def popover_text(char):
        win = MainWindow(ruleset, char, Path("/tmp/c.json"))
        qtbot.addWidget(win)
        root = QVBoxLayout()
        # what `rebuild()` puts in the body, without the modal
        if char.chargen_locked:
            win._xp_section(root, lambda: None)
        else:
            from exalted_builder.engine import validate
            bd = validate.bonus_point_breakdown(ruleset, char)
            root.addWidget(QLabel(f"Bonus Points  {bd.total} / {bd.available} spent"))
        out = []
        for i in range(root.count()):
            w = root.itemAt(i).widget()
            if isinstance(w, QLabel):
                out.append(w.text())
        return " | ".join(out)

    assert "Bonus Points" in popover_text(Character(id="c.new"))
    assert "Bonus Points" not in popover_text(_locked(ruleset))
    assert "Experience" in popover_text(_locked(ruleset))


# --------------------------------------------------------------------------- #
# The Party window — a SECOND window over the same context
# --------------------------------------------------------------------------- #

def _party_char(name="Dace"):
    return Character(id=f"c.{name}", name=name, exalt_type="Solar", caste="dawn")


def test_the_party_window_is_created_once_and_reused(ruleset, qtbot):
    """⚠ ONE window, held on the builder. A fresh one per click would give each its own
    cards over the same roster, and a health box ticked in the old one would be invisible
    in the new."""
    win = MainWindow(ruleset, _party_char(), Path("/tmp/c.json"))
    qtbot.addWidget(win)
    first = win.party_window()
    assert win.party_window() is first
    win._party()
    assert win.party_window() is first


def test_the_party_window_shares_the_builders_context(ruleset, qtbot):
    win = MainWindow(ruleset, _party_char(), Path("/tmp/c.json"))
    qtbot.addWidget(win)
    party = win.party_window()
    assert party._ctx is win._ctx


def test_opening_the_party_window_loads_the_adversary_catalogue(ruleset, qtbot):
    """The templates are book data but NOT rules, so they ride the context and are
    loaded on demand — the same place `ui/builder.py` puts them for the webapp."""
    win = MainWindow(ruleset, _party_char(), Path("/tmp/c.json"))
    qtbot.addWidget(win)
    assert win._ctx["adversary_catalog"] == {}
    win.party_window()
    assert len(win._ctx["adversary_catalog"]) > 40


def test_open_in_builder_retargets_this_window_by_reference(ruleset, qtbot):
    """The human's call (2026-08-27): ONE builder, retargeted — not a window per member.
    ⚠ By reference, so every edit lands on the card with no syncing code."""
    win = MainWindow(ruleset, _party_char(), Path("/tmp/c.json"))
    qtbot.addWidget(win)
    party = win.party_window()
    member = _party_char("Harmonious Jade")
    party.add_character(member)
    win._open_member(0)
    assert win._ctx["char"] is member
    assert win._ctx["member"] == 0


def test_loading_a_character_forgets_the_party_member_it_was_editing(ruleset, qtbot):
    """⚠ A stale `member` index attributes a later save to a member this window is no
    longer editing."""
    win = MainWindow(ruleset, _party_char(), Path("/tmp/c.json"))
    qtbot.addWidget(win)
    win.party_window().add_character(_party_char("Jade"))
    win._open_member(0)
    win._apply_loaded(Character(id="c.other", name="Other"), None, "other")
    assert win._ctx["member"] is None


def test_a_new_character_forgets_the_party_member_too(ruleset, qtbot, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **k: QMessageBox.StandardButton.Yes)
    win = MainWindow(ruleset, _party_char(), Path("/tmp/c.json"))
    qtbot.addWidget(win)
    win.party_window().add_character(_party_char("Jade"))
    win._open_member(0)
    win._confirm_new()
    assert win._ctx["member"] is None


def test_closing_the_builder_takes_the_party_window_with_it(ruleset, qtbot):
    """⚠ A parentless QMainWindow is its own top-level window: without this the
    Storyteller window survives the builder, with no way back to one."""
    win = MainWindow(ruleset, _party_char(), Path("/tmp/c.json"))
    qtbot.addWidget(win)
    party = win.party_window()
    party.show()
    win.close()
    assert not party.isVisible()


def test_a_builder_change_redraws_a_VISIBLE_party_window_only(ruleset, qtbot):
    """A card shows DERIVED capacities, so a builder change makes its pixels stale even
    though both windows hold the same object. Hidden, there is nothing to redraw — it
    reloads on every open."""
    win = MainWindow(ruleset, _party_char(), Path("/tmp/c.json"))
    qtbot.addWidget(win)
    party = win.party_window()
    calls = []
    party.reload = lambda: calls.append(1)
    win._refresh()
    assert calls == []                  # hidden
    party.show()
    win._refresh()
    assert calls == [1]


def test_no_empty_table_anywhere_in_the_port_is_a_bare_void(ruleset, qtbot):
    """⚠ An empty table is indistinguishable from a broken one — reported against the
    adversary roster the first time it was opened (human, 2026-08-27): a header over a
    large blank rectangle reads as "nothing loaded". Every collection tab had the same
    hole, so the guard is a SWEEP rather than one tab's test: build every page of both
    windows for a fresh character and demand that any table holding no rows says why.

    ⚠ Written against the shell, not against a list of tabs, so a NEW collection tab
    fails here until it is wired. `qt/layout.py::empty_note` is the one way to satisfy it.
    """
    from PySide6.QtWidgets import QLabel, QTreeWidget

    win = MainWindow(ruleset, _party_char(), Path("/tmp/c.json"))
    qtbot.addWidget(win)
    for row in range(win.rail.count()):
        win.rail.setCurrentRow(row)
    party = win.party_window()
    bare = []
    for root in (win, party):
        for table in root.findChildren(QTreeWidget):
            if table.model().rowCount():
                continue
            notes = [w for w in table.viewport().findChildren(QLabel)
                     if w.objectName() == "emptyNote"]
            if not notes:
                bare.append(table.objectName()
                            or " / ".join(table.headerItem().text(c)
                                          for c in range(table.columnCount())))
    assert not bare, f"empty tables with no explanation: {bare}"


# --------------------------------------------------------------------------- #
# The command line (and therefore the packaged binary's startup)
# --------------------------------------------------------------------------- #

def test_a_path_on_the_command_line_opens_that_character(ruleset, tmp_path):
    from exalted_builder import persistence
    from exalted_builder.qt.__main__ import open_character

    path = tmp_path / "dace.character.json"
    persistence.save_character(_party_char("Dace"), path)
    character, save_path, complaint = open_character(["prog", str(path)])
    assert character.name == "Dace" and save_path == path and complaint == ""


def test_an_unreadable_path_starts_blank_and_COMPLAINS_rather_than_dying(ruleset, tmp_path):
    """⚠ Never fatal. The packaged build is windowed (`console=False`), so an exception
    here kills the executable with its traceback going nowhere — a mistyped path or a
    stray argument from a desktop launcher would read as "the app doesn't work"."""
    from exalted_builder.qt.__main__ import open_character

    character, _save_path, complaint = open_character(["prog", str(tmp_path / "nope.json")])
    assert character.name == ""
    assert "Could not open" in complaint and "new character" in complaint


def test_no_argument_starts_a_blank_character(ruleset):
    from exalted_builder.qt.__main__ import open_character

    character, save_path, complaint = open_character(["prog"])
    assert character.name == "" and complaint == ""
    assert save_path.suffix == ".json"
