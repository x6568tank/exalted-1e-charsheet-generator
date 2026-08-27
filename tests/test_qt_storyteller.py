"""The Qt ST Options page (exalted_builder/qt/storyteller.py) — the table's optional
rules.

Covers what the widget decides for itself: that every rule is offered on the sub-tab for
its scope, that a rule which cannot bite is DIMMED rather than hidden, that the two
control shapes write the three stored types correctly, that the lock makes the whole tab
read-only, that flipping a rule restates the notes around it, and that the shell's
`on_change` hook actually fires.

⚠ The layout is the settled COLLECTION one (sub-tab per scope + sortable table +
splitter + detail pane), not the NiceGUI page's card stack. Tests address the tables and
the detail pane, never a card.

⚠ Controls are addressed by objectName (`houserule.<field>`), never by position in a
`findChildren` list — a checkbox found by index is how a test passed a wrong assertion
into existence on the Gear tab.
"""

from pathlib import Path

import pytest

# ⚠ PySide6 is the OPTIONAL `qt` extra (pyproject), so it is legitimately absent on a
# machine that only runs the webapp. Skip the module rather than letting a bare import
# turn into a COLLECTION ERROR — that kills the whole run, not just these tests.
pytest.importorskip("PySide6", reason="the optional [qt] extra is not installed")

from PySide6.QtWidgets import QCheckBox, QComboBox

from exalted_builder.engine import lifecycle
from exalted_builder.models.character import Character
from exalted_builder.qt.storyteller import StorytellerPage
from exalted_builder.ui import view as viewmod


def _page(ruleset, character, notes=None, on_change=None):
    sink = notes if notes is not None else []
    return StorytellerPage(ruleset, {"char": character},
                           notify=lambda text, kind="info": sink.append((kind, text)),
                           on_change=on_change)


def _solar(**kw) -> Character:
    c = Character(id="c.st", name="Test", exalt_type="Solar", caste="dawn",
                  essence_rating=2)
    for k, v in kw.items():
        setattr(c, k, v)
    return c


def _labels(page, scope):
    table = page._tables[scope]
    return [table.topLevelItem(i).text(0) for i in range(table.topLevelItemCount())]


def _item(page, scope, field):
    table = page._tables[scope]
    return next(table.topLevelItem(i) for i in range(table.topLevelItemCount())
                if table.topLevelItem(i).data(0, 0x0100) == field)   # Qt.UserRole


def _select(page, scope, field):
    """Select a rule, which is what builds its control in the detail pane."""
    from exalted_builder.qt.storyteller import _SCOPES
    page.tabs.setCurrentIndex(_SCOPES.index(scope))
    page._tables[scope].setCurrentItem(_item(page, scope, field))


def _control(page, field, kind=QCheckBox):
    return page.findChild(kind, f"houserule.{field}")


def _row(ruleset, character, field):
    return next(r for r in viewmod.build_house_rules(ruleset, character)
                if r.field == field)


# --------------------------------------------------------------------------- #
# the collection
# --------------------------------------------------------------------------- #

def test_every_rule_is_offered_on_the_sub_tab_for_its_scope(ruleset, qtbot):
    char = _solar()
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    rows = viewmod.build_house_rules(ruleset, char)
    for scope in ("table", "character"):
        expected = [r.label for r in rows if r.scope == scope]
        assert sorted(_labels(page, scope)) == sorted(expected)
    assert page.tabs.count() == 2
    assert [page.tabs.tabText(i) for i in range(2)] == ["Table-wide", "This character"]


def test_the_tables_have_headers_so_the_columns_align(ruleset, qtbot):
    page = _page(ruleset, _solar())
    qtbot.addWidget(page)
    table = page._tables["table"]
    headers = [table.headerItem().text(i) for i in range(table.columnCount())]
    assert headers == ["Rule", "Setting", "Source"]
    assert table.isSortingEnabled()


def test_an_inert_rule_is_dimmed_and_not_hidden(ruleset, qtbot):
    """A Solar is not a Sidereal, so the Celestial Manse permission cannot bite — but an
    ST hunting for the toggle must still find it and be told why."""
    char = _solar()
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    row = _row(ruleset, char, "st_celestial_manse_over_three")
    assert row.inert
    item = _item(page, "character", "st_celestial_manse_over_three")
    from exalted_builder.qt.theme import MUTED
    assert item.foreground(0).color().name() == MUTED
    assert "No effect" in item.toolTip(0)


def test_a_live_rule_is_not_dimmed(ruleset, qtbot):
    """The negative control for the dimming: an ordinary Solar's foreign-Charm row is a
    real permission (Dawn is not a generalist caste, so use a table-wide rule that
    always bites)."""
    char = _solar()
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    assert not _row(ruleset, char, "all_backgrounds_available").inert
    item = _item(page, "table", "all_backgrounds_available")
    from exalted_builder.qt.theme import MUTED
    assert item.foreground(0).color().name() != MUTED


def test_the_setting_column_reads_the_current_value(ruleset, qtbot):
    char = _solar()
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    assert _item(page, "table", "magic_for_everyone").text(1) == "Off"
    _select(page, "table", "magic_for_everyone")
    _control(page, "magic_for_everyone").setChecked(True)
    assert _item(page, "table", "magic_for_everyone").text(1) == "On"


def test_a_multiple_choice_rule_shows_its_option_not_a_boolean(ruleset, qtbot):
    """⚠ `bool("backgrounds")` is True — a select rendered as On/Off is the shape that
    hides the M&F method entirely."""
    page = _page(ruleset, _solar())
    qtbot.addWidget(page)
    assert _item(page, "table", "mf_change_method").text(1) == "Experience"


# --------------------------------------------------------------------------- #
# the detail pane
# --------------------------------------------------------------------------- #

def test_selecting_a_rule_builds_its_checkbox_with_the_citation(ruleset, qtbot):
    page = _page(ruleset, _solar())
    qtbot.addWidget(page)
    _select(page, "table", "magic_for_everyone")
    assert page.detail_title.text() == "Magic for Everyone"
    box = _control(page, "magic_for_everyone")
    assert box is not None and not box.isChecked()
    texts = [w.text() for w in page._detail_body.findChildren(type(page.readout))]
    assert any("Player's Guide p.115" in t for t in texts)


def test_a_checkbox_writes_a_bool(ruleset, qtbot):
    char = _solar()
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    _select(page, "table", "magic_for_everyone")
    _control(page, "magic_for_everyone").setChecked(True)
    assert char.house_rules.magic_for_everyone is True


def test_the_mf_method_select_writes_its_stored_string(ruleset, qtbot):
    """⚠ Not `bool(value)`: that turns "backgrounds" into True and silently rewrites the
    rule to something else."""
    char = _solar()
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    _select(page, "table", "mf_change_method")
    combo = _control(page, "mf_change_method", QComboBox)
    combo.setCurrentIndex(combo.findData("backgrounds"))
    assert char.house_rules.mf_change_method == "backgrounds"


def test_the_inheritance_select_writes_an_int_and_a_none(ruleset, qtbot):
    """The option keys are strings; the model wants an int, or None for per-character."""
    char = _solar()
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    _select(page, "table", "godblooded_inheritance_rating")
    combo = _control(page, "godblooded_inheritance_rating", QComboBox)
    combo.setCurrentIndex(combo.findData("3"))
    assert char.house_rules.godblooded_inheritance_rating == 3
    combo = _control(page, "godblooded_inheritance_rating", QComboBox)
    combo.setCurrentIndex(combo.findData("per-character"))
    assert char.house_rules.godblooded_inheritance_rating is None


def test_flipping_a_rule_restates_the_notes_around_it(ruleset, qtbot):
    """The notes report what a rule is currently WORTH, so the whole tab reloads rather
    than the one row — the Background count moves the moment the toggle does."""
    char = _solar()
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    _select(page, "table", "all_backgrounds_available")
    before = _row(ruleset, char, "all_backgrounds_available").note
    _control(page, "all_backgrounds_available").setChecked(True)
    after = _row(ruleset, char, "all_backgrounds_available").note
    assert before != after and "Offering all" in after
    assert any("Offering all" in w.text()
               for w in page._detail_body.findChildren(type(page.readout)))


def test_the_readout_counts_the_toggles_that_are_on(ruleset, qtbot):
    """⚠ Only the BOOLEAN rules count. A select always holds a value, so counting it
    would report a character as having rules on before the ST touched anything."""
    char = _solar()
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    assert "0 switched on" in page.readout.text()
    _select(page, "table", "magic_for_everyone")
    _control(page, "magic_for_everyone").setChecked(True)
    assert "1 switched on" in page.readout.text()


# --------------------------------------------------------------------------- #
# the lock
# --------------------------------------------------------------------------- #

def test_the_lock_makes_every_control_read_only(ruleset, qtbot):
    """⚠ These toggles change how chargen is PRICED and are frozen into the snapshot at
    the lock, so flipping one afterwards would re-price a signed-off chargen."""
    char = _solar()
    lifecycle.lock_chargen(char, ruleset)
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    _select(page, "table", "magic_for_everyone")
    assert not _control(page, "magic_for_everyone").isEnabled()
    _select(page, "table", "mf_change_method")
    assert not _control(page, "mf_change_method", QComboBox).isEnabled()
    assert "Unlock" in page.readout.text()


def test_unlocking_re_enables_the_controls(ruleset, qtbot):
    """The negative control for the lock: read-only must not be a one-way door, and
    `reload()` is what the shell calls when the tab comes back into view."""
    char = _solar()
    lifecycle.lock_chargen(char, ruleset)
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    lifecycle.unlock_chargen(char)
    page.reload()
    _select(page, "table", "magic_for_everyone")
    assert _control(page, "magic_for_everyone").isEnabled()
    assert "Unlock" not in page.readout.text()


# --------------------------------------------------------------------------- #
# the shell contract
# --------------------------------------------------------------------------- #

def test_flipping_a_rule_pings_the_shell(ruleset, qtbot):
    """⚠ The hook is load-bearing, not decorative: Magic for Everyone grants free
    purchases and the Inheritance rating moves the bonus-point pool, so the shell's
    readout bar is stale without it. `CharmsPage` shipped without this hook."""
    pings = []
    char = _solar()
    page = _page(ruleset, char, on_change=lambda: pings.append(1))
    qtbot.addWidget(page)
    _select(page, "table", "magic_for_everyone")
    _control(page, "magic_for_everyone").setChecked(True)
    assert pings


def test_the_shell_wires_the_page_with_on_change(ruleset, qtbot):
    """The hook contract, asserted at the CONSTRUCTOR rather than the page — that is
    where it went missing last time."""
    from exalted_builder.qt.main_window import MainWindow
    win = MainWindow(ruleset, _solar(), Path("st.json"))
    qtbot.addWidget(win)
    page = win._pages["ST"]
    assert isinstance(page, StorytellerPage)
    assert page._on_change is not None


def test_a_rebuild_does_not_leak_widgets(ruleset, qtbot):
    """⚠ Thrash the rebuild and count. A single reload passes while leaking — the
    `clear_layout` trap that shipped six times."""
    page = _page(ruleset, _solar())
    qtbot.addWidget(page)
    _select(page, "table", "magic_for_everyone")
    baseline = len(page._detail_body.findChildren(QCheckBox))
    for _ in range(6):
        page.reload()
    assert len(page._detail_body.findChildren(QCheckBox)) == baseline
