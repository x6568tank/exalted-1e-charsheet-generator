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

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QLabel, QMessageBox, QPlainTextEdit, QPushButton,
                               QSpinBox)

from exalted_builder.models.character import Character, Damage, PlayState
from exalted_builder.models.party import Party, PartyMember
from exalted_builder.qt.party import (PartyWindow, ReferencePage,
                                      reference_html)
from exalted_builder.qt.sheet import screen_colors
from exalted_builder.ui import theme


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


def test_the_reference_screen_follows_the_partys_accent(ruleset, qtbot):
    """The window re-themes when the party becomes single-splat, and the reference is a
    document inside it — `apply_chrome` has to re-render it, since a document's colours
    are baked into its HTML and no palette change reaches them."""
    page = ReferencePage(ruleset)
    qtbot.addWidget(page)
    default = page.view.toHtml()
    page.apply_colors(theme.palette("Lunar"))
    assert page.view.toHtml() != default
    assert screen_colors("Lunar").accent in reference_html(
        ruleset, screen_colors("Lunar"))


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


# --------------------------------------------------------------------------- #
# The opposition, on the party's own tab
#
# ⚠ **The port dropped this and the tests could not see it.** The webapp renders the
# roster as a card grid on the party page; the native app compressed it into a table
# plus ONE detail pane, so a Storyteller running a fight could see exactly one bandit's
# health at a time — "gming combat is a challenge" (human, 2026-08-28). Every adversary
# test was green throughout, because they all addressed the tab that DID exist. The
# shape a port compresses is where its missing controls are.
# --------------------------------------------------------------------------- #

def _adversary(name="Bandit", entry_id="adv.1", **kw):
    from exalted_builder.engine import adversaries as adv
    from exalted_builder.models.adversary import Adversary
    return Adversary(id=entry_id, name=name, categories=["Extra"], willpower=3,
                     health_levels=adv.expand_health("-1/-3/I"), **kw)


def test_every_adversary_gets_a_tracker_card_on_the_party_tab(make_window):
    party = _party(_solar())
    party.adversaries = [_adversary(), _adversary("Bear", "adv.2")]
    window, _ctx, _calls = make_window(party)
    for entry_id in ("adv.1", "adv.2"):
        assert _boxes(window.party_page, f"adv.{entry_id}.health.")
        assert _boxes(window.party_page, f"adv.{entry_id}.willpower_spent.")


def test_a_roster_card_click_marks_that_entry_and_no_other(make_window):
    from exalted_builder.engine import adversaries as adv
    party = _party(_solar())
    first, second = _adversary(), _adversary("Bear", "adv.2")
    party.adversaries = [first, second]
    window, _ctx, _calls = make_window(party)
    _named(window.party_page, "adv.adv.2.health.0").click()
    assert adv.normalize_damage(second)[0] == Damage.BASHING
    assert all(m is None for m in adv.normalize_damage(first))


def test_a_roster_card_click_reaches_the_adversaries_tab(make_window):
    """⚠ The roster is drawn on TWO surfaces now. A click on either has to reach the
    other, or the table's Damage column and the card disagree about the same bandit."""
    party = _party(_solar())
    party.adversaries = [_adversary()]
    window, _ctx, _calls = make_window(party)
    _named(window.party_page, "adv.adv.1.health.0").click()
    assert window.adversaries_page.table.topLevelItem(0).text(2) == "1/ 0x 0*  (-1)"


def test_a_roster_card_click_does_not_rebuild_the_card_under_it(make_window):
    """The same guard as the detail pane's, on the surface a fight is actually run from.
    Negative-control it by calling `_reload_roster()` from `_on_adversary_changed`."""
    party = _party(_solar())
    party.adversaries = [_adversary()]
    window, _ctx, _calls = make_window(party)
    before = _named(window.party_page, "adv.adv.1.health.0")
    before.click()
    assert _named(window.party_page, "adv.adv.1.health.0") is before
    assert before.text() == Damage.BASHING.value


def test_edit_on_a_roster_card_raises_the_adversaries_tab_on_that_entry(make_window):
    """⚠ The card carries NO editor — two editors for one model is how the
    `powers`/`combat_pool` dead fields got in. "Edit" jumps to the one that exists."""
    party = _party(_solar())
    party.adversaries = [_adversary(), _adversary("Bear", "adv.2")]
    window, _ctx, _calls = make_window(party)
    _named(window.party_page, "adv.adv.2.edit").click()
    assert window.tabs.currentWidget() is window.adversaries_page
    assert window.adversaries_page._current().name == "Bear"


def test_duplicating_from_a_roster_card_goes_through_the_engine(make_window):
    party = _party(_solar())
    party.adversaries = [_adversary()]
    window, _ctx, _calls = make_window(party)
    _named(window.party_page, "adv.adv.1.duplicate").click()
    assert [a.name for a in party.adversaries] == ["Bandit", "Bandit 2"]
    assert _boxes(window.party_page, "adv.adv.2.health.")


def test_an_adversary_added_on_its_own_tab_appears_on_the_party_tab(make_window):
    """The mirror direction, through the tab the human actually adds one from."""
    party = _party(_solar())
    window, _ctx, _calls = make_window(party)
    window.adversaries_page._add(None)                    # the dialog's Custom button
    entry_id = party.adversaries[0].id
    assert _boxes(window.party_page, f"adv.{entry_id}.health.")


def test_an_empty_roster_says_so_rather_than_leaving_a_blank(make_window):
    """⚠ An empty surface is indistinguishable from a broken one — the reason
    `layout.empty_note` exists for the tables."""
    window, _ctx, _calls = make_window(_party(_solar()))
    assert [w for w in window.party_page.findChildren(QLabel)
            if "No adversaries yet" in w.text()]


def test_a_roster_card_prints_the_stats_a_roll_is_called_against(make_window):
    """Trackers alone are not enough to run a fight off: the attack lines, the soak and
    the traits have to be on the card, which is what the webapp's card carried."""
    from exalted_builder.models.adversary import AdversaryAttack
    party = _party(_solar())
    party.adversaries = [_adversary(
        attributes={"strength": 4}, soak_lethal=3,
        attacks=[AdversaryAttack(name="Bite", speed=6, accuracy=7, damage=1,
                                 damage_type="L", defense=5)])]
    window, _ctx, _calls = make_window(party)
    text = " ".join(w.text() for w in window.party_page.findChildren(QLabel))
    assert "Bite" in text
    assert "Str 4" in text


def test_a_member_card_click_leaves_the_tabs_scroll_where_it_was(make_window, qtbot):
    """⚠ The adversary detail pane's bug (human, 2026-08-28) on the surface one tab
    over, found by the same probe and never separately reported. A play-state click used
    to `reload()` every card, which deletes the box under the cursor; Qt passes the focus
    on and the scroll area follows it. Measured before the fix: 354 → 463, with the focus
    left in the toolbar's party-name field.

    Negative-control it by putting `self.reload()` back into `_health`'s handler."""
    window, _ctx, _calls = make_window(_party(*[_solar(f"PC{i}") for i in range(6)]))
    window.resize(900, 600)
    window.show()
    qtbot.waitExposed(window)
    bar = window.party_page._scroll.verticalScrollBar()
    assert bar.maximum() > 0, "the tab has to overflow for this to mean anything"
    bar.setValue(bar.maximum() // 2)
    button = _named(window.party_page, "party.2.health.1")
    button.setFocus(Qt.FocusReason.MouseFocusReason)
    qtbot.wait(10)
    at = bar.value()
    button.click()
    qtbot.wait(10)
    assert bar.value() == at
    assert window.focusWidget() is button
    assert button.text() == Damage.BASHING.value


def test_a_member_card_click_still_moves_that_cards_readouts(make_window, qtbot):
    """⚠ "Nothing was rebuilt" must not become "nothing was updated". The heading counts
    the marks, so it has to be re-texted in place — a card that repaints the box and not
    the penalty is worse than one that redraws everything."""
    character = _solar()
    window, _ctx, _calls = make_window(_party(character))
    _named(window.party_page, "party.0.health.0").click()
    headings = [w.text() for w in window.party_page.findChildren(QLabel)
                if w.text().startswith("HEALTH")]
    assert headings and "1/ 0x 0*" in headings[0]


def test_a_click_on_one_card_does_not_touch_another(make_window):
    first, second = _solar("One"), _solar("Two")
    window, _ctx, _calls = make_window(_party(first, second))
    _named(window.party_page, "party.1.health.0").click()
    assert second.play.health[0] == Damage.BASHING
    assert first.play is None


def test_reset_on_a_roster_card_repaints_rather_than_rebuilding(make_window):
    """⚠ The same defect one BUTTON over, in code written to fix it: `_reload_roster()`
    here would delete the Reset button that was just clicked. Repaint, and it survives."""
    from exalted_builder.engine import adversaries as adv
    party = _party(_solar())
    entry = _adversary()
    party.adversaries = [entry]
    window, _ctx, _calls = make_window(party)
    _named(window.party_page, "adv.adv.1.health.0").click()
    button = _named(window.party_page, "adv.adv.1.reset")
    button.click()
    assert all(m is None for m in adv.normalize_damage(entry))
    assert _named(window.party_page, "adv.adv.1.reset") is button
    # and the box it repainted is empty again
    assert _named(window.party_page, "adv.adv.1.health.0").text() == ""
