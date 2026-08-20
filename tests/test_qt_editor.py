"""The Qt Edit tab (exalted_builder/qt/editor.py) — retained-mode trait surface.

Covers the DotTrack control (chargen free setter, post-lock XP buyer), the EditPage
build + side column, and the structural cascades. The post-lock downward dialog is
exercised only through its `_buy` preconditions — a modal QDialog.exec() would block
a headless test.
"""

from exalted_builder.engine import advancement, lifecycle
from exalted_builder.models.character import AbilityName, AttributeName, Character
from exalted_builder.qt.editor import DotTrack, EditPage, _FavoredPicker


def _page(ruleset, character, **kw):
    return EditPage(ruleset, {"char": character}, notify=lambda *a, **k: None, **kw)


# --------------------------------------------------------------------------- #
# DotTrack
# --------------------------------------------------------------------------- #

def test_dot_track_renders_pips_and_clicks_set(qtbot):
    value = {"v": 1}
    track = DotTrack(lambda: value["v"], lambda v: value.__setitem__("v", v),
                     0, 5, accent="#000000")
    qtbot.addWidget(track)
    assert len(track._pips) == 5
    track._click(4)
    assert value["v"] == 4
    assert len(track._pips) == 5


def test_dot_track_shows_enough_pips_to_step_a_too_high_value_down(qtbot):
    value = {"v": 7}
    track = DotTrack(lambda: value["v"], lambda v: value.__setitem__("v", v),
                     0, 5, accent="#000000")
    qtbot.addWidget(track)
    # hi is 5 but the value is 7 — the row must offer pip 7 so it can be clicked down.
    assert len(track._pips) == 7
    track._click(7)          # stepping down clamps to the hard ceiling of 5
    assert value["v"] == 5


def test_dot_track_clicking_current_top_steps_down(qtbot):
    value = {"v": 3}
    track = DotTrack(lambda: value["v"], lambda v: value.__setitem__("v", v),
                     0, 5, accent="#000000")
    qtbot.addWidget(track)
    track._click(3)
    assert value["v"] == 2


def test_dot_track_clamps_to_lo(qtbot):
    value = {"v": 2}
    track = DotTrack(lambda: value["v"], lambda v: value.__setitem__("v", v),
                     1, 5, accent="#000000")
    qtbot.addWidget(track)
    track._click(1)          # step down from 2 → 1
    assert value["v"] == 1
    track._click(1)          # step down from 1 → clamped at lo 1
    assert value["v"] == 1


def test_favored_picker_adds_and_removes_chips(qtbot):
    changes = []
    picker = _FavoredPicker({"melee": "Melee", "dodge": "Dodge", "brawl": "Brawl"},
                            ["melee"], 3, "#000000", lambda p: changes.append(list(p)))
    qtbot.addWidget(picker)
    # The combo holds every option (so clicking shows the list) and starts blank.
    assert picker.combo.count() == 3
    assert picker.combo.currentText() == ""
    # typing a valid name + Enter adds it as a chip and fires on_change.
    picker.combo.lineEdit().setText("Dodge")
    picker.combo.lineEdit().returnPressed.emit()
    assert changes[-1] == ["melee", "dodge"]
    assert picker._picked == ["melee", "dodge"]
    # removing a chip fires on_change again.
    picker._remove("melee")
    assert changes[-1] == ["dodge"]


def test_dot_track_fires_on_change(qtbot):
    calls = []
    value = {"v": 1}
    track = DotTrack(lambda: value["v"], lambda v: value.__setitem__("v", v),
                     0, 5, accent="#000000", on_change=lambda: calls.append(1))
    qtbot.addWidget(track)
    track._click(3)
    assert calls == [1]


# --------------------------------------------------------------------------- #
# EditPage — chargen side
# --------------------------------------------------------------------------- #

def test_edit_page_builds_for_a_fresh_character(qtbot, ruleset):
    char = Character(id="char.new")
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    # The chargen side column carries Live Validation + Bonus Points.
    text = page._side.findChild(type(page._side)).text() if False else ""
    all_text = _side_text(page)
    assert "Live Validation" in all_text
    assert "Bonus Points" in all_text


def test_edit_page_changed_updates_ability_tally(qtbot, ruleset):
    char = Character(id="char.new")
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    before = _ability_tally_text(page)
    char.abilities[AbilityName.MELEE] = 3
    page._changed()
    after = _ability_tally_text(page)
    assert before != after


def test_edit_page_structural_switch_cascades(qtbot, ruleset):
    char = Character(id="char.new")
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    page.set_exalt_type("Dragon-Blooded")
    assert char.exalt_type == "Dragon-Blooded"
    assert char.caste in {cd.id for cd in ruleset.castes.values()
                          if cd.exalt_type == "Dragon-Blooded"}
    assert char.origin == "dynastic"
    # Mortal has no castes — switching clears the stale one.
    page.set_exalt_type("Mortal")
    assert char.exalt_type == "Mortal"
    assert char.caste == ""
    assert char.origin == "heroic"


def test_edit_page_post_lock_buy_spends_xp(qtbot, ruleset):
    char = Character(id="char.new")
    advancement.add_xp(char, 50)
    lifecycle.lock_chargen(char, ruleset)
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    available = advancement.xp_available(char)
    page._buy("attributes.strength", 1, 2, lambda: None)
    assert char.attributes[AttributeName.STRENGTH] == 2
    assert advancement.xp_available(char) < available


def test_edit_page_pre_lock_buy_falls_through(qtbot, ruleset):
    char = Character(id="char.new")
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    # Pre-lock the buy handler returns False so the track free-sets instead.
    assert page._buy("attributes.strength", 1, 2, lambda: None) is False


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def _side_text(page) -> str:
    """The concatenated text of the side column's labels."""
    from PySide6.QtWidgets import QLabel
    return " | ".join(label.text() for label in page._side.findChildren(QLabel))


def _ability_tally_text(page) -> str:
    from PySide6.QtWidgets import QLabel
    for label in page._body_container.findChildren(QLabel):
        if "dots spent" in label.text():
            return label.text()
    return ""
