"""The native Party window (exalted_builder/qt/party.py) and its wiring to the builder.

Covers what this window decides for itself: that it is a SECOND window over the SAME
context (so "Open in builder" needs no syncing), that a card is a live tracker whose
clicks go through `engine.play`, that the roster and the builder cannot end up pointing
at different objects, and that the ST reference screen renders — or says why it cannot.

⚠ Play-state is validation-isolated (decision 0006). Nothing here asserts that a mark
moved a budget, a pool maximum or a validation issue; `tests/test_play.py` enforces the
direction.

⚠ Cards are addressed by objectName (`party.0.health.3`, `party.1.notes`), never by
position in a `findChildren` list — a party is several identically-shaped cards.
"""

from html import escape

import pytest

pytest.importorskip("PySide6", reason="the optional [qt] extra is not installed")

from PySide6.QtWidgets import QMessageBox, QPlainTextEdit, QPushButton, QSpinBox

from exalted_builder.models.character import Character, Damage, PlayState
from exalted_builder.models.party import Party, PartyMember
from exalted_builder.qt.party import PartyWindow, reference_html


@pytest.fixture
def make_window(ruleset, qtbot):
    """A PartyWindow over a fresh context, plus the calls it made back to the builder."""
    def build(party=None, character=None):
        calls = {"opened": [], "closed": 0}
        ctx = {"char": character if character is not None else _solar(),
               "party": party if party is not None else Party(id="p.test"),
               "party_path": None, "member": None, "dir": None,
               "adversary_catalog": {}}
        window = PartyWindow(ruleset, ctx,
                             on_open_member=lambda i: calls["opened"].append(i),
                             on_close_member=lambda: calls.update(
                                 closed=calls["closed"] + 1))
        qtbot.addWidget(window)
        return window, ctx, calls
    return build


def _solar(name="Dace", **kw) -> Character:
    c = Character(id=f"c.{name}", name=name, exalt_type="Solar", caste="dawn",
                  essence_rating=2)
    for k, v in kw.items():
        setattr(c, k, v)
    return c


def _party(*characters) -> Party:
    return Party(id="p", members=[PartyMember(character=c) for c in characters])


def _named(page, name, kind=QPushButton):
    found = [w for w in page.findChildren(kind) if w.objectName() == name]
    assert found, f"no {kind.__name__} named {name!r}"
    return found[0]


# --------------------------------------------------------------------------- #
# The window
# --------------------------------------------------------------------------- #

def test_the_window_has_the_three_tabs(make_window):
    window, _ctx, _calls = make_window()
    assert [window.tabs.tabText(i) for i in range(window.tabs.count())] == [
        "Party", "Adversaries", "Reference"]


def test_it_is_a_top_level_window_and_themes_itself(make_window):
    """⚠ A top-level window inherits NEITHER the builder's palette nor its stylesheet —
    the trap that left every QDialog in the port drawing the platform's light grey."""
    window, _ctx, _calls = make_window(_party(_solar()))
    assert window.parent() is None
    assert "QToolBar" in window.styleSheet()


def test_the_title_follows_the_party_name(make_window):
    window, _ctx, _calls = make_window()
    window.name_edit.setText("Tuesday Game")
    assert "Tuesday Game" in window.windowTitle()


def test_a_single_splat_party_takes_that_splats_chrome(make_window):
    """One splat throughout ⇒ that splat's accent. A MIXED party falls back to the
    default, because its identity lives on the cards, which are tinted per character."""
    abyssal = make_window(_party(_solar("Ash", exalt_type="Abyssal")))[0]
    mixed = make_window(_party(_solar(), _solar("Ash", exalt_type="Abyssal")))[0]
    assert abyssal._pal().splat_label != mixed._pal().splat_label


# --------------------------------------------------------------------------- #
# Members
# --------------------------------------------------------------------------- #

def test_a_card_is_drawn_per_member(make_window):
    window, _ctx, _calls = make_window(_party(_solar(), _solar("Jade")))
    assert _named(window.party_page, "party.0.notes", QPlainTextEdit) is not None
    assert _named(window.party_page, "party.1.notes", QPlainTextEdit) is not None


def test_a_health_box_click_marks_the_characters_own_play_state(make_window):
    character = _solar()
    window, _ctx, _calls = make_window(_party(character))
    _named(window.party_page, "party.0.health.0").click()
    assert character.play.health[0] == Damage.BASHING


def test_merely_opening_the_window_writes_no_play_state(make_window):
    """⚠ Reading through `char.play or PlayState()`, never `engineplay.play_state`: a
    character who has never been played must not save dirty because a GM looked at them."""
    character = _solar()
    make_window(_party(character))
    assert character.play is None


def test_the_mote_input_clamps_to_the_pool(make_window):
    character = _solar()
    window, _ctx, _calls = make_window(_party(character))
    spin = _named(window.party_page, "party.0.motes_personal_spent", QSpinBox)
    spin.setValue(spin.maximum())
    assert character.play.motes_personal_spent == spin.maximum()


def test_a_merged_pool_gets_ONE_mote_input(ruleset, make_window, monkeypatch):
    """⚠ "All of which is considered Peripheral" (p.41). A Personal box would sit at a
    permanent 0/0 and read as broken — `PlayView.single_pool` exists for exactly this,
    and the card must honour it the way the Play tab does."""
    from exalted_builder.ui import view as viewmod
    real = viewmod.build_play_view

    def merged(rs, character):
        play = real(rs, character)
        play.single_pool = True
        return play

    monkeypatch.setattr(viewmod, "build_play_view", merged)
    window, _ctx, _calls = make_window(_party(_solar()))
    window.party_page.reload()
    assert not [w for w in window.party_page.findChildren(QSpinBox)
                if w.objectName() == "party.0.motes_personal_spent"]
    assert _named(window.party_page, "party.0.motes_peripheral_spent", QSpinBox)


def test_card_notes_write_to_the_member_not_the_character(make_window):
    party = _party(_solar())
    window, _ctx, _calls = make_window(party)
    _named(window.party_page, "party.0.notes", QPlainTextEdit).setPlainText("owes money")
    assert party.members[0].notes == "owes money"


def test_session_notes_write_to_the_party(make_window):
    party = _party(_solar())
    window, _ctx, _calls = make_window(party)
    _named(window.party_page, "party.session_notes",
           QPlainTextEdit).setPlainText("they burned the docks")
    assert party.session_notes == "they burned the docks"


def test_adding_a_character_holds_it_by_reference(make_window):
    """⚠ BY REFERENCE is what makes "Open in builder" need no syncing code: the card and
    the builder edit one object."""
    character = _solar()
    window, ctx, _calls = make_window()
    window.add_character(character)
    assert ctx["party"].members[0].character is character
    character.name = "Renamed"
    window.party_page.reload()
    assert ctx["party"].members[0].character.name == "Renamed"


def test_the_builder_button_asks_the_builder_to_retarget(make_window):
    window, _ctx, calls = make_window(_party(_solar(), _solar("Jade")))
    _named(window.party_page, "party.1.builder").click()
    assert calls["opened"] == [1]


def test_removing_a_member_drops_the_builders_pointer(make_window, monkeypatch):
    """⚠ The builder may be pointed at the member that just went away, or at one whose
    index has shifted. A stale pointer attributes a later save to the wrong member."""
    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **k: QMessageBox.StandardButton.Yes)
    party = _party(_solar(), _solar("Jade"))
    window, ctx, calls = make_window(party)
    window._remove_member(0)
    assert [m.character.name for m in party.members] == ["Jade"]
    assert calls["closed"] == 1


def test_removing_a_member_can_be_declined(make_window, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **k: QMessageBox.StandardButton.No)
    party = _party(_solar())
    window, _ctx, calls = make_window(party)
    window._remove_member(0)
    assert len(party.members) == 1 and calls["closed"] == 0


# --------------------------------------------------------------------------- #
# Party bundles
# --------------------------------------------------------------------------- #

def test_loading_a_party_swaps_the_bundle_and_drops_the_pointer(make_window):
    window, ctx, calls = make_window(_party(_solar()))
    loaded = _party(_solar("Ash"), _solar("Jade"))
    loaded.name = "The Circle"
    window.apply_party(loaded, None)
    assert ctx["party"] is loaded
    assert calls["closed"] == 1
    assert window.name_edit.text() == "The Circle"
    assert _named(window.party_page, "party.1.notes", QPlainTextEdit) is not None


def test_a_new_party_leaves_no_members_and_no_adversaries(make_window):
    window, ctx, _calls = make_window(_party(_solar()))
    window.apply_party(Party(id="party.new"), None)
    assert ctx["party"].members == [] and ctx["party"].adversaries == []


def test_exporting_an_empty_party_offers_no_dialog(make_window):
    """A "Print all" over nobody is a message, not an empty PDF."""
    window, _ctx, _calls = make_window()
    assert window.build_export_dialog(None) is None


def test_the_party_export_is_titled_for_the_whole_party(make_window):
    window, _ctx, _calls = make_window(_party(_solar(), _solar("Jade")))
    dialog = window.build_export_dialog(None)
    assert "2 character sheets" in dialog.windowTitle()


def test_one_members_export_is_titled_for_that_member(make_window):
    party = _party(_solar())
    window, _ctx, _calls = make_window(party)
    dialog = window.build_export_dialog(party.members[0].character)
    assert dialog.windowTitle() == "Export character sheet"


def test_a_members_sheet_renders_read_only(make_window):
    party = _party(_solar())
    window, _ctx, _calls = make_window(party)
    dialog = window.build_sheet_dialog(party.members[0].character)
    assert "Dace" in dialog.windowTitle()


# --------------------------------------------------------------------------- #
# The reference screen
# --------------------------------------------------------------------------- #

def test_the_reference_screen_renders_every_table(ruleset):
    html = reference_html(ruleset)
    screen = ruleset.st_screen
    assert screen is not None, "the corebook ST screen should be loaded"
    # Escaped, because the titles are data: one of them is "Health, Wounds & Recovery".
    for group in screen.groups:
        assert escape(group.title) in html
        for table in group.tables:
            assert escape(table.title) in html


def test_a_ruleset_with_no_st_screen_says_so(ruleset):
    """⚠ The screen is OPTIONAL data. A missing st_screen.json must read as an
    explanation, not as an empty tab that looks broken."""
    stripped = ruleset.model_copy(update={"st_screen": None})
    assert "No Storyteller reference screen" in reference_html(stripped)


def test_reference_cells_are_escaped(ruleset):
    """The tables are rendered as HTML, so a cell containing < or & must not become
    markup — the ST screen is data and the renderer must not trust it."""
    screen = ruleset.st_screen.model_copy(deep=True)
    screen.groups[0].tables[0].rows = [["a < b & c"] * len(
        screen.groups[0].tables[0].columns or ["x"])]
    html = reference_html(ruleset.model_copy(update={"st_screen": screen}))
    assert "a &lt; b &amp; c" in html


# --------------------------------------------------------------------------- #
# Adding a character
# --------------------------------------------------------------------------- #

def test_the_add_dialog_offers_the_character_open_in_the_builder(make_window):
    """⚠ Not just the file picker. At a table the commonest case is "the one I just made"
    — jumping straight to the OS dialog would make it unreachable from here."""
    character = _solar()
    window, ctx, _calls = make_window(character=character)
    dialog = window.build_add_character_dialog()
    _named(dialog, "party.addOpen").click()
    assert ctx["party"].members[0].character is character


def test_the_add_dialog_drops_the_open_character_once_it_is_in_the_party(make_window):
    """Offering it twice would let one Character sit on the roster as two members."""
    character = _solar()
    window, _ctx, _calls = make_window(_party(character), character=character)
    dialog = window.build_add_character_dialog()
    assert not [w for w in dialog.findChildren(QPushButton)
                if w.objectName() == "party.addOpen"]


def test_the_add_dialog_can_add_a_blank_character(make_window):
    window, ctx, _calls = make_window()
    _named(window.build_add_character_dialog(), "party.addBlank").click()
    assert len(ctx["party"].members) == 1


# --------------------------------------------------------------------------- #
# The per-splat halves of a card
# --------------------------------------------------------------------------- #

def _boxes(page, prefix):
    return [w for w in page.findChildren(QPushButton)
            if w.objectName().startswith(prefix)]


def test_a_solar_card_gets_limit_and_no_clarity(make_window):
    window, _ctx, _calls = make_window(_party(_solar()))
    assert len(_boxes(window.party_page, "party.0.limit.")) == 10
    assert not _boxes(window.party_page, "party.0.clarity_temporary.")


def test_an_alchemical_card_gets_clarity_and_no_limit(ruleset, make_window):
    """Clarity replaces Limit for an Alchemical (p.69) — never both on one card."""
    from exalted_builder.engine import derive
    character = _solar("Gear", exalt_type="Alchemical", caste="orichalcum")
    if not derive.uses_clarity(ruleset, character):
        pytest.skip("this build's Alchemical definition does not carry Clarity")
    window, _ctx, _calls = make_window(_party(character))
    assert len(_boxes(window.party_page,
                      "party.0.clarity_temporary.")) == derive.CLARITY_MAX
    assert not _boxes(window.party_page, "party.0.limit.")


def test_only_a_jadeborn_card_offers_the_great_geas(ruleset, make_window):
    """⚠ Divergence is Storyteller-adjudicated and never engine-enforced, so the nine
    clauses ride the card as its copy of the page (the human's ruling, 2026-08-07) —
    and a control only that splat has must not appear on anyone else's card."""
    from exalted_builder.engine import derive
    jadeborn = _solar("Stone", exalt_type="Mountain-Folk", caste="")
    window, _ctx, _calls = make_window(_party(_solar(), jadeborn))
    assert not _boxes(window.party_page, "party.0.geas")
    if derive.limit_label(ruleset, jadeborn) != "Divergence":
        pytest.skip("this build's Mountain Folk definition does not use Divergence")
    assert _boxes(window.party_page, "party.1.geas")
