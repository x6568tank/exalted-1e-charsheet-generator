"""The Qt Identity + Traits pages (exalted_builder/qt/editor.py) — retained-mode
trait surface.

Covers the DotTrack control (chargen free setter, post-lock XP buyer), the two pages
(Identity's structural + bio + caste info; Traits' favoured picks + dot tracks), the
structural cascades and the scroll-hold. The post-lock downward dialog is exercised
only through its `_buy` preconditions — a modal QDialog.exec() would block a headless
test.
"""

from PySide6.QtWidgets import QApplication, QPushButton

from exalted_builder.engine import advancement, lifecycle
from exalted_builder.models.character import AbilityName, AttributeName, Character
from exalted_builder.qt.editor import DotTrack, IdentityPage, TraitsPage, _FavoredPicker


def _identity(ruleset, character, **kw):
    return IdentityPage(ruleset, {"char": character},
                        notify=lambda *a, **k: None,
                        on_theme_change=lambda: None, **kw)


def _traits(ruleset, character, **kw):
    return TraitsPage(ruleset, {"char": character},
                      notify=lambda *a, **k: None, **kw)


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
# The two pages — chargen side
# --------------------------------------------------------------------------- #

def test_pages_build_for_a_fresh_character(qtbot, ruleset):
    from PySide6.QtWidgets import QLabel
    char = Character(id="char.new")
    idp = _identity(ruleset, char)
    trp = _traits(ruleset, char)
    qtbot.addWidget(idp)
    qtbot.addWidget(trp)
    id_text = " | ".join(l.text() for l in idp.findChildren(QLabel))
    tr_text = " | ".join(l.text() for l in trp.findChildren(QLabel))
    assert "Identity" in id_text and "Biography" in id_text and "Caste" in id_text
    assert "Favoured Picks" in tr_text and "Attributes" in tr_text


def test_identity_bio_fields_bind_to_the_model(qtbot, ruleset):
    from PySide6.QtWidgets import QLineEdit, QTextEdit
    char = Character(id="char.new")
    page = _identity(ruleset, char)
    qtbot.addWidget(page)
    edits = page.findChildren(QLineEdit)
    # the bio fields are the trailing seven (Name/Concept/Anima and Nature's internal
    # line edit come first); Sex is the first of them
    edits[-7].setText("M")
    assert char.sex == "M"
    backs = page.findChildren(QTextEdit)      # Description, Backstory, Notes
    backs[1].setPlainText("Born in the River Province")
    assert char.backstory == "Born in the River Province"


def test_traits_changed_updates_ability_tally(qtbot, ruleset):
    char = Character(id="char.new")
    page = _traits(ruleset, char)
    qtbot.addWidget(page)
    before = _ability_tally_text(page)
    char.abilities[AbilityName.MELEE] = 3
    page._changed()
    after = _ability_tally_text(page)
    assert before != after


def test_identity_structural_switch_cascades(qtbot, ruleset):
    char = Character(id="char.new")
    page = _identity(ruleset, char)
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


def test_traits_post_lock_buy_spends_xp(qtbot, ruleset):
    char = Character(id="char.new")
    advancement.add_xp(char, 50)
    lifecycle.lock_chargen(char, ruleset)
    page = _traits(ruleset, char)
    qtbot.addWidget(page)
    available = advancement.xp_available(char)
    page._buy("attributes.strength", 1, 2, lambda: None)
    assert char.attributes[AttributeName.STRENGTH] == 2
    assert advancement.xp_available(char) < available


def test_traits_pre_lock_buy_falls_through(qtbot, ruleset):
    char = Character(id="char.new")
    page = _traits(ruleset, char)
    qtbot.addWidget(page)
    # Pre-lock the buy handler returns False so the track free-sets instead.
    assert page._buy("attributes.strength", 1, 2, lambda: None) is False


def test_traits_reload_holds_scroll_position(qtbot, ruleset):
    # A body rebuild (here: adding a craft) can yank the scrollbar, so reload must
    # hold the scroll position where it was.
    char = Character(id="c", exalt_type="Solar")
    page = _traits(ruleset, char)
    qtbot.addWidget(page)
    page.resize(1000, 700)
    page.show()
    for _ in range(6):
        QApplication.processEvents()
    bar = page._body_scroll.verticalScrollBar()
    assert bar.maximum() > 0                # the form really overflows
    bar.setValue(bar.maximum() // 2)
    saved = bar.value()
    page.add_craft()                        # a body reload
    for _ in range(6):
        QApplication.processEvents()
    assert bar.value() == saved


def test_traits_removing_a_favored_chip_holds_scroll(qtbot, ruleset):
    # The nasty one: deleting a FOCUSED chip (its ✕) makes Qt's focus handling
    # scroll the body to whatever focusable widget it picks next — a QSpinBox deep
    # in the form. The picker parks focus on its combo before deleting, and the
    # reload's scroll-hold catches the residue, so the view must stay put.
    char = Character(id="c", exalt_type="Solar")
    char.favored_abilities = [AbilityName.MELEE, AbilityName.DODGE,
                              AbilityName.ARCHERY]
    page = _traits(ruleset, char)
    qtbot.addWidget(page)
    page.resize(1000, 700)
    page.show()
    QApplication.processEvents()
    qtbot.wait(250)                       # let the construction scroll-hold release
    bar = page._body_scroll.verticalScrollBar()
    assert bar.maximum() > 0
    bar.setValue(bar.maximum() // 2)
    QApplication.processEvents()
    saved = bar.value()
    picker = page.findChildren(_FavoredPicker)[0]
    picker.findChildren(QPushButton)[0].setFocus()     # as a real click would
    QApplication.processEvents()
    picker._remove("melee")                # the whole removal path
    for _ in range(8):
        QApplication.processEvents()
    assert bar.value() == saved


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def _ability_tally_text(page) -> str:
    from PySide6.QtWidgets import QLabel
    for label in page._body_container.findChildren(QLabel):
        if "dots spent" in label.text():
            return label.text()
    return ""
