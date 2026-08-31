"""The Qt Advantages page (exalted_builder/qt/advantages.py) — Backgrounds, Merits &
Flaws, Fetters and Passions on one surface, in both regimes.

Covers what the widget decides for itself: which controls a regime gets, that the caps
and prices come from the engine, that the labels keyed to a Background's rating move
when it does, and that the in-play card routes a purchase through
`advancement.gain_merit_or_flaw` rather than choosing a side of its own, and that a
purchase configured in the catalogue dialog lands as configured.

⚠ The dialogs are reached through `AdvantagesPage._build_*_dialog`, which returns one
WITHOUT running it. `exec()` would block a headless run, so the `_open_*` wrappers are
not testable and the builders are the seam.
"""

from pathlib import Path

import pytest

# ⚠ PySide6 is the OPTIONAL `qt` extra (pyproject), so it is legitimately absent on a
# machine that only runs the webapp. Skip the module rather than letting a bare import
# turn into a COLLECTION ERROR — that kills the whole run, not just these tests.
pytest.importorskip("PySide6", reason="the optional [qt] extra is not installed")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QLabel, QLineEdit, QPushButton,
                               QSpinBox)

import exalted_builder
from exalted_builder import persistence
from exalted_builder.engine import advancement, lifecycle, validate
from exalted_builder.models.character import (BackgroundEntry, Character,
                                              HearthstoneEntry, MeritFlawPurchase)
from exalted_builder.qt import catalogue
from exalted_builder.qt.advantages import AdvantagesPage
from exalted_builder.qt.catalogue import CatalogueDialog
from exalted_builder.qt.editor import DotTrack
from exalted_builder.ui import theme
from exalted_builder.ui import view as viewmod

EXAMPLE = Path(exalted_builder.__file__).parent.parent / "examples" / "ashes-of-dawn.character.json"

MUTATION = "mf.mutation"            # kind: "either" — a Merit OR a Flaw
PRODIGY = "mf.prodigy"              # tier menu leading with a tier Solars may not take


def _page(ruleset, character, notes=None):
    sink = notes if notes is not None else []
    return AdvantagesPage(ruleset, {"char": character},
                          notify=lambda text, kind="info": sink.append((kind, text)))


def _solar(**kw) -> Character:
    c = Character(id="c.adv", name="Test", exalt_type="Solar", caste="dawn",
                  essence_rating=2)
    for k, v in kw.items():
        setattr(c, k, v)
    return c


def _locked_with_xp(ruleset, character, amount=100):
    lifecycle.lock_chargen(character, ruleset)
    advancement.add_xp(character, amount)
    return character


def _widgets(page, kind):
    """Widgets in the DETAIL PANE — where every editor lives since the tab became
    tables + a detail pane (shape B, human 2026-08-21). Select a row first."""
    return page._detail_body.findChildren(kind)


def _labels(page) -> list[str]:
    return [w.text() for w in _widgets(page, QLabel)]


def _tab(page, label: str):
    """Switch to a sub-tab and return its table."""
    for i in range(page.tabs.count()):
        if page.tabs.tabText(i) == label:
            page.tabs.setCurrentIndex(i)
            return page._current_table()
    raise AssertionError(f"no {label!r} sub-tab; have "
                         f"{[page.tabs.tabText(i) for i in range(page.tabs.count())]}")


def _tab_labels(page) -> list[str]:
    return [page.tabs.tabText(i) for i in range(page.tabs.count())]


def _notes_text(page, tab_label: str) -> list[str]:
    """The contextual note lines above one table (budgets, pricing rules, caps)."""
    notes = page._notes[tab_label]
    out = []
    for i in range(notes.count()):
        widget = notes.itemAt(i).widget()
        if widget is not None and hasattr(widget, "text"):
            out.append(widget.text())
    return out


def _rows(table) -> list[str]:
    return [table.topLevelItem(i).text(0) for i in range(table.topLevelItemCount())]


def _pick(page, tab_label: str, index: int = 0):
    """Select one table row, which is what builds its editor in the detail pane."""
    table = _tab(page, tab_label)
    assert table.topLevelItemCount() > index, f"{tab_label} has no row {index}"
    table.setCurrentItem(table.topLevelItem(index))
    return table


def _pick_named(page, tab_label: str, name: str):
    table = _tab(page, tab_label)
    for i in range(table.topLevelItemCount()):
        if table.topLevelItem(i).text(0) == name:
            table.setCurrentItem(table.topLevelItem(i))
            return table
    raise AssertionError(f"{name!r} not in {tab_label}: {_rows(table)}")


def _select(dialog, key: str) -> None:
    """Drive the catalogue dialog's list to the row carrying `key`, which is what
    repaints its extras and re-labels the confirm button."""
    for i in range(dialog.list.count()):
        if dialog.list.item(i).data(Qt.UserRole) == key:
            dialog.list.setCurrentRow(i)
            return
    raise AssertionError(f"{key} is not offered by this dialog")


# --------------------------------------------------------------------------- #
# it builds, in both regimes and for a splat with no M&F rows yet
# --------------------------------------------------------------------------- #

def test_page_builds_for_a_fresh_character(qtbot, ruleset):
    page = _page(ruleset, _solar())
    qtbot.addWidget(page)
    # Shape B: a sub-tab per category, not stacked panels (human, 2026-08-21).
    assert _tab_labels(page) == ["Backgrounds", "Merits & Flaws"]


def test_page_builds_for_the_example_and_reports_only_its_own_issues(qtbot, ruleset):
    char = persistence.load_character(EXAMPLE)
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    # This line carries the Background/Merit/Artifact findings and nothing else. ⚠ NOT
    # the bonus-point total — the shell's readout bar already prints that sentence, and
    # printing it here too put it on screen twice.
    assert "bonus points" not in page.issues.text()
    assert "Charm" not in page.issues.text()
    assert page.issues.text() == "No Background or Merit issues."


def test_post_lock_the_issue_line_becomes_the_experience_line(qtbot, ruleset):
    char = _locked_with_xp(ruleset, _solar(), 30)
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    assert "30 XP available" in page.issues.text()


# --------------------------------------------------------------------------- #
# Backgrounds
# --------------------------------------------------------------------------- #

def test_chargen_backgrounds_get_a_dot_track_capped_by_the_engine(qtbot, ruleset):
    char = _solar(backgrounds=[BackgroundEntry(name="Resources", rating=2)])
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    b = validate.effective_budgets(ruleset, char)
    track = _widgets(page, DotTrack)[0]
    assert track._hi == validate.background_rating_cap(b, char, "Resources")


def test_post_lock_backgrounds_get_a_free_spinbox_capped_by_the_post_lock_rule(qtbot, ruleset):
    """In play a Background moves through the story, not through XP: an editable
    current value, no cost, no log row — and the ceiling is the engine's post-lock
    one, never a hardcoded 5."""
    char = _solar(backgrounds=[BackgroundEntry(name="Resources", rating=2)])
    _locked_with_xp(ruleset, char)
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    b = validate.effective_budgets(ruleset, char)
    spin = _widgets(page, QSpinBox)[0]
    assert spin.maximum() == validate.background_rating_cap(b, char, "Resources",
                                                            post_lock=True)
    before = len(char.xp_log)
    spin.setValue(4)
    assert char.backgrounds[0].rating == 4
    assert len(char.xp_log) == before          # free — no XP row


def test_a_barred_background_is_capped_at_zero_not_merely_flagged(qtbot, ruleset):
    """A cap the player can click past is not a ceiling. The bar itself is
    engine.merits' (a Flaw may close a Background outright); the widget must ask."""
    char = _solar(backgrounds=[BackgroundEntry(name="Followers", rating=1)])
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    b = validate.effective_budgets(ruleset, char)
    expected = validate.background_rating_cap(b, char, "Followers")
    assert _widgets(page, DotTrack)[0]._hi == expected


def test_the_artifact_row_says_what_its_dots_buy(qtbot, ruleset):
    """The artifacts live on the Gear tab; the Background is what PAYS for them, so the
    rule is stated on both surfaces rather than owned silently by one."""
    char = _solar(backgrounds=[BackgroundEntry(name="Artifact", rating=3)])
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    assert any("buys 3 dot(s) of artifacts" in text for text in _labels(page))


def test_raising_a_background_repaints_its_rung_without_rebuilding_the_row(qtbot, ruleset):
    """The rung under a row is keyed to the rating, so it must follow a dot click —
    and the click must not replace the widgets around it."""
    char = _solar(backgrounds=[BackgroundEntry(name="Resources", rating=1)])
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    track = _widgets(page, DotTrack)[0]
    notes = _widgets(page, QLineEdit)
    before = [text for text in _labels(page)]
    track._click(3)
    assert char.backgrounds[0].rating == 3
    assert _labels(page) != before                      # the rung moved
    assert _widgets(page, QLineEdit) == notes           # the same note box, still live


def test_the_hearthstone_denominator_moves_with_the_manse_rating(qtbot, ruleset):
    """⚠ Both halves of "N / M" move: the numerator when a stone is added or re-rated,
    the DENOMINATOR when the Manse rating does — a Manse raised from •• to ••••• is a
    bigger Manse and legalises the stone that was over budget a moment ago. A
    build-time allowance froze the denominator at whatever the rating happened to be."""
    manse = BackgroundEntry(name="Manse", rating=2,
                            hearthstones=[HearthstoneEntry(name="Stone", rating=3)])
    char = _solar(backgrounds=[manse])
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    assert any("Hearthstones: 3 / 2 levels" in text for text in _labels(page))
    _widgets(page, DotTrack)[0]._click(5)
    assert manse.rating == 5
    assert any("Hearthstones: 3 / 5 levels" in text for text in _labels(page))


def test_a_stranded_stone_on_a_demesne_row_stays_visible(qtbot, ruleset):
    """Flipped to Demesne the row grows no stones, but one already held must stay
    editable and deletable rather than becoming an Issue with no control behind it."""
    manse = BackgroundEntry(name="Manse", rating=3, is_demesne=True,
                            hearthstones=[HearthstoneEntry(name="Orphan", rating=1)])
    page = _page(ruleset, _solar(backgrounds=[manse]))
    qtbot.addWidget(page)
    assert any(w.text() == "Orphan" for w in _widgets(page, QLineEdit))


def test_picking_from_the_background_catalogue_appends_a_row(qtbot, ruleset):
    char = _solar()
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    page._pick_bg("Resources")
    assert [bg.name for bg in char.backgrounds] == ["Resources"]
    page._pick_bg(None)                                 # Custom — a blank free-text row
    assert [bg.name for bg in char.backgrounds] == ["Resources", ""]


def test_the_background_dialog_adds_at_the_rating_chosen_in_it(qtbot, ruleset):
    """The rating is set beside the printed ladder that describes each rung, and it is
    the rating that lands — not a default of 1 to be corrected on the row afterwards."""
    char = _solar()
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    dialog = page._build_bg_dialog()
    qtbot.addWidget(dialog)
    _select(dialog, "Resources")
    dialog.extras_box.findChildren(QSpinBox)[0].setValue(3)
    assert "•••" in dialog.choose_btn.text()
    dialog._choose()
    assert [(bg.name, bg.rating) for bg in char.backgrounds] == [("Resources", 3)]


def test_the_background_dialog_will_not_exceed_the_characters_cap(qtbot, ruleset):
    """A cap you can click past is not a cap — the spinner's maximum is the same
    `_bg_cap_for` answer the row's dot track uses, not a fixed 5."""
    char = _solar()
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    b = validate.effective_budgets(ruleset, char)
    dialog = page._build_bg_dialog()
    qtbot.addWidget(dialog)
    _select(dialog, "Resources")
    spin = dialog.extras_box.findChildren(QSpinBox)[0]
    assert spin.maximum() == page._bg_cap_for(b, "Resources")


def test_a_custom_background_ignores_a_rating_left_over_from_a_browsed_row(qtbot, ruleset):
    """Custom has no printed ladder to read a rating off, so it starts at 1 — the
    pending rating belongs to the entry it was chosen for and must not leak."""
    char = _solar()
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    page._pending_bg.update(name="Resources", rating=4)
    page._pick_bg(None)
    assert [(bg.name, bg.rating) for bg in char.backgrounds] == [("", 1)]


def test_removing_a_background_row(qtbot, ruleset):
    char = _solar(backgrounds=[BackgroundEntry(name="Resources", rating=1),
                               BackgroundEntry(name="Allies", rating=1)])
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    page._remove_bg(0)
    assert [bg.name for bg in char.backgrounds] == ["Allies"]


# --------------------------------------------------------------------------- #
# Merits & Flaws — chargen
# --------------------------------------------------------------------------- #

def test_changing_a_row_entry_resets_the_tier_to_one_this_splat_may_choose(qtbot, ruleset):
    """⚠ Prodigy's menu leads with `favored`, which a Solar is barred from. Resetting
    to the first AUTHORED tier hands the player a row that flags itself immediately."""
    mp = MeritFlawPurchase(merit_id="", custom_name="x")
    char = _solar(merits_flaws=[mp])
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    page._set_merit(mp, PRODIGY)
    assert mp.tier in validate.merit_tiers_available(ruleset.merits_flaws[PRODIGY],
                                                     "Solar", "dawn")


def test_changing_a_row_entry_clears_the_old_entrys_values(qtbot, ruleset):
    mp = MeritFlawPurchase(merit_id=MUTATION, taken_as="flaw", points=4, detail="old",
                           arena="combat", stipulations=2)
    char = _solar(merits_flaws=[mp])
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    page._set_merit(mp, PRODIGY)
    assert (mp.taken_as, mp.points, mp.detail, mp.arena, mp.stipulations) == \
        ("", 0, "", "", 0)


def test_a_custom_row_is_keyed_on_the_empty_merit_id_not_the_name(qtbot, ruleset):
    """⚠ The discriminator must be a field nothing on the screen can edit: the name
    input writes `custom_name` on every keystroke, so a blanked name must still render
    as custom rather than falling through to the definition-driven controls."""
    mp = MeritFlawPurchase(merit_id="", custom_name="")
    page = _page(ruleset, _solar(merits_flaws=[mp]))
    qtbot.addWidget(page)
    _pick(page, "Merits & Flaws")
    assert any("Custom Merit / Flaw" in text for text in _labels(page))
    # A custom row offers no catalogue combo, so it never joins the entry-combo list.
    assert page._mf_rows == []


def test_filtering_moved_into_the_catalogue_dialog_as_category_chips(qtbot, ruleset):
    """⚠ The page's old search + side + category bar is GONE, deliberately: filtering
    belongs where the CHOOSING happens, not beside the list of what you already hold.
    The five printed categories are chips on the dialog, and its own search box
    replaces the bar's text field."""
    page = _page(ruleset, _solar())
    qtbot.addWidget(page)
    # Nothing on the page filters the held list by category any more...
    assert not [w for w in page.findChildren(QLineEdit)
                if w.placeholderText().startswith("search")]
    # ...because the dialog does it.
    dialog = page._build_mf_dialog(page._available_merits())
    qtbot.addWidget(dialog)
    assert set(dialog.group_buttons) >= {"Mental", "Physical", "Social",
                                         "Supernatural"}


def test_a_dialog_chip_narrows_the_offer_to_that_category(qtbot, ruleset):
    page = _page(ruleset, _solar())
    qtbot.addWidget(page)
    dialog = page._build_mf_dialog(page._available_merits())
    qtbot.addWidget(dialog)
    dialog._set_group("Physical")
    # ⚠ `_group_of` holds a LIST per key since 2026-08-27; M&F pass one group per row.
    shown = {group
             for i, (key, *_rest) in enumerate(dialog._entries)
             if not dialog.list.item(i).isHidden()
             for group in dialog._group_of[key]}
    assert shown == {"Physical"}


def test_a_merits_rules_text_is_printed_WHOLE_in_the_detail_pane(qtbot, ruleset):
    """⚠ The pane clamped the printed text at 320 characters and put the rest in a
    TOOLTIP — a leftover from when this was a card in a stack with no room. It is now
    the scrolling half of a splitter, and the Backgrounds pane beside it has always
    printed its blurb in full, so a long Merit read as truncated for no reason
    (human, 2026-08-30). Picks the LONGEST description in the rule set so the test
    cannot rot into probing a short one."""
    longest = max(ruleset.merits_flaws.values(),
                  key=lambda m: len(m.description or ""))
    assert len(longest.description) > 320, "no entry long enough to prove the clamp gone"
    page = _page(ruleset, _solar(merits_flaws=[MeritFlawPurchase(merit_id=longest.id)]))
    qtbot.addWidget(page)
    _pick(page, "Merits & Flaws")
    printed = " ".join(_labels(page))
    whole = " ".join(longest.description.split())
    assert whole in printed
    # ...and the tooltip is not where the tail lives any more.
    assert "…" not in printed


def test_a_two_sided_row_offers_the_side_control(qtbot, ruleset):
    mp = MeritFlawPurchase(merit_id=MUTATION)
    page = _page(ruleset, _solar(merits_flaws=[mp]))
    qtbot.addWidget(page)
    _pick(page, "Merits & Flaws")
    assert "Taken" in _labels(page)


def test_adding_from_the_catalogue_opens_the_row_on_an_available_tier(qtbot, ruleset):
    char = _solar()
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    page._pick_mf(PRODIGY)
    assert char.merits_flaws[0].merit_id == PRODIGY
    assert char.merits_flaws[0].tier in validate.merit_tiers_available(
        ruleset.merits_flaws[PRODIGY], "Solar", "dawn")


def test_the_chargen_dialog_takes_the_entry_at_the_tier_chosen_in_it(qtbot, ruleset):
    """Chargen buys through the same block the in-play card uses, so the row lands
    fully specified rather than on a default tier the player never saw. ⚠ Prodigy's
    menu leads with a tier Solars may not take — the dialog must open on an AVAILABLE
    one, exactly as the row does."""
    char = _solar()
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    dialog = page._build_mf_dialog(page._available_merits())
    qtbot.addWidget(dialog)
    _select(dialog, PRODIGY)
    tiers = validate.merit_tiers_available(ruleset.merits_flaws[PRODIGY],
                                           "Solar", "dawn")
    assert page._pending_mf["tier"] in tiers
    assert "Take (" in dialog.choose_btn.text()
    dialog._choose()
    assert char.merits_flaws[0].merit_id == PRODIGY
    assert char.merits_flaws[0].tier in tiers


def test_the_chargen_dialog_also_refuses_a_sideless_two_sided_entry(qtbot, ruleset):
    """The same refusal as in play — an `either` entry taken with no side is
    half-specified in both regimes."""
    char = _solar()
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    dialog = page._build_mf_dialog(page._available_merits())
    qtbot.addWidget(dialog)
    _select(dialog, MUTATION)
    assert not dialog.choose_btn.isEnabled()
    dialog._choose()                                    # a disabled button buys nothing
    assert char.merits_flaws == []


def test_the_custom_option_appends_a_row_with_no_mechanical_effect(qtbot, ruleset):
    char = _solar()
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    page._pick_mf(None)
    assert char.merits_flaws[0].merit_id == ""
    assert char.merits_flaws[0].custom_name


# --------------------------------------------------------------------------- #
# Merits & Flaws — in play
# --------------------------------------------------------------------------- #

def test_gaining_a_two_sided_entry_with_no_side_is_refused_by_the_engine(qtbot, ruleset):
    """The refusal text belongs to `advancement.gain_merit_or_flaw`; the widget only
    surfaces it."""
    notes = []
    char = _locked_with_xp(ruleset, _solar())
    page = _page(ruleset, char, notes)
    qtbot.addWidget(page)
    page._gain.update(id=MUTATION, points=2)
    page._gain_mf()
    assert char.merits_flaws == []
    assert notes and notes[-1][0] == "warning" and "which side" in notes[-1][1]


def test_gaining_a_flaw_pays_the_character(qtbot, ruleset):
    char = _locked_with_xp(ruleset, _solar())
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    before = advancement.xp_available(char)
    page._gain.update(id=MUTATION, taken_as="flaw", points=2)
    page._gain_mf()
    assert advancement.xp_available(char) > before
    assert char.merits_flaws[-1].taken_as == "flaw"


def test_dropping_a_held_entry_needs_a_selection(qtbot, ruleset):
    notes = []
    char = _locked_with_xp(ruleset, _solar())
    page = _page(ruleset, char, notes)
    qtbot.addWidget(page)
    page._drop_idx = ""
    page._drop_mf()
    assert notes and notes[-1][0] == "warning"


def test_dropping_a_held_entry_removes_it(qtbot, ruleset):
    char = _locked_with_xp(ruleset, _solar())
    advancement.gain_merit_or_flaw(ruleset, char, MUTATION, taken_as="flaw", points=2)
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    # ⚠ Drop acts on the TABLE selection. The old card carried its own "Held" dropdown
    # beside a table listing the same entries — two controls naming one thing, and the
    # one you were looking at was not the one the button acted on.
    _pick(page, "Merits & Flaws")
    # ⚠ `isHidden()`, not `isVisible()`: a widget whose parent is never shown reports
    # isVisible() False however it is configured, so the positive form silently fails
    # in the offscreen harness.
    assert not page.drop_btn.isHidden() and page.drop_btn.isEnabled()
    page._drop_selected()
    assert char.merits_flaws == []


def test_a_non_experience_table_says_so_instead_of_offering_zero_xp_buttons(qtbot, ruleset):
    from exalted_builder.models.character import HouseRules
    char = _solar(house_rules=HouseRules(mf_change_method="swap"))
    _locked_with_xp(ruleset, char)
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    # The pricing rules sit above the table they govern, not in the detail pane.
    _tab(page, "Merits & Flaws")
    notes = " ".join(_notes_text(page, "Merits & Flaws"))
    assert "method (Player's Guide p.17)" in notes
    assert not any(w.text() == "Gain" for w in page.findChildren(QPushButton))
    # ⚠ And no Drop either: under a non-experience method a change "costs and rewards
    # nothing", so a button that always reads 0 XP would be a lie.
    assert page.drop_btn.isHidden()


def _dialog_labels(dialog) -> str:
    return " ".join(w.text() for w in dialog.findChildren(QLabel))


def test_the_gain_dialog_prices_the_pending_pick(qtbot, ruleset):
    """Buying blind off a menu label is how you take a Flaw by accident: the dialog
    names the side and the price beside the entry's own text, and nothing is bought
    until the confirm button is pressed."""
    char = _locked_with_xp(ruleset, _solar())
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    dialog = page._build_gain_dialog(page._available_merits())
    qtbot.addWidget(dialog)
    _select(dialog, MUTATION)
    text = _dialog_labels(dialog)
    assert "Merit OR Flaw" in text and "points =" in text
    assert char.merits_flaws == []


def test_a_two_sided_entry_cannot_be_confirmed_until_a_side_is_chosen(qtbot, ruleset):
    """The side is what makes the transaction positive or negative, so it is not a
    detail to fix up afterwards — the button refuses and says which choice is missing."""
    char = _locked_with_xp(ruleset, _solar())
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    dialog = page._build_gain_dialog(page._available_merits())
    qtbot.addWidget(dialog)
    _select(dialog, MUTATION)
    assert not dialog.choose_btn.isEnabled()
    assert "Choose Merit or Flaw" in dialog.choose_btn.text()

    side = next(w for w in dialog.extras_box.findChildren(QComboBox)
                if w.findData("flaw") >= 0)
    side.setCurrentIndex(side.findData("flaw"))
    assert dialog.choose_btn.isEnabled()
    # A Flaw PAYS: the button has to say so, or it reads as a cost.
    assert "pays" in dialog.choose_btn.text()


def test_confirming_the_gain_dialog_buys_the_configured_entry(qtbot, ruleset):
    """The dialog is the whole transaction — the side chosen in it is the side that
    lands on the character, not a default filled in afterwards."""
    char = _locked_with_xp(ruleset, _solar())
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    before = advancement.xp_available(char)
    dialog = page._build_gain_dialog(page._available_merits())
    qtbot.addWidget(dialog)
    _select(dialog, MUTATION)
    side = next(w for w in dialog.extras_box.findChildren(QComboBox)
                if w.findData("flaw") >= 0)
    side.setCurrentIndex(side.findData("flaw"))
    # Mutation is variable-cost, so the point value is part of the configuration.
    dialog.extras_box.findChildren(QSpinBox)[0].setValue(2)
    dialog._choose()
    assert char.merits_flaws[-1].merit_id == MUTATION
    assert char.merits_flaws[-1].taken_as == "flaw"
    assert advancement.xp_available(char) > before


def test_a_variable_cost_entry_opens_at_one_point_not_zero(qtbot, ruleset):
    """Human's ruling, 2026-08-21. At zero a variable-cost entry prices to nothing, so
    confirming it adds a row that neither costs nor pays — a purchase that looks made
    and did nothing. ⚠ The value must be seeded into the STATE, not just the spinner:
    the confirm button prices the state."""
    char = _locked_with_xp(ruleset, _solar())
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    dialog = page._build_gain_dialog(page._available_merits())
    qtbot.addWidget(dialog)
    _select(dialog, MUTATION)
    assert dialog.extras_box.findChildren(QSpinBox)[0].value() == 1
    assert page._gain["points"] >= 1

    # ...and the price shown follows from it, rather than reading "0 points".
    side = next(w for w in dialog.extras_box.findChildren(QComboBox)
                if w.findData("flaw") >= 0)
    side.setCurrentIndex(side.findData("flaw"))
    _points, xp = page._mf_price(ruleset.merits_flaws[MUTATION], page._gain)
    assert xp > 0 and str(xp) in dialog.choose_btn.text()


def test_switching_entries_does_not_carry_the_previous_tier_over(qtbot, ruleset):
    """A tier is entry-specific; carrying one across a selection change silently
    mis-prices the new entry (the reason `_set_merit` clears on change)."""
    char = _locked_with_xp(ruleset, _solar())
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    available = page._available_merits()
    dialog = page._build_gain_dialog(available)
    qtbot.addWidget(dialog)
    _select(dialog, MUTATION)
    page._gain.update(taken_as="flaw", points=4)
    other = next(m.id for m in available if m.id != MUTATION)
    _select(dialog, other)
    assert page._gain["id"] == other
    assert page._gain["taken_as"] == ""
    # ⚠ NOT `points == 0`: a variable-cost entry legitimately opens at 1, so assert the
    # stale value is gone rather than a literal that only holds while `other` happens
    # to be fixed-cost.
    assert page._gain["points"] != 4


# --------------------------------------------------------------------------- #
# Fetters and Passions (ghosts only)
# --------------------------------------------------------------------------- #

def _ghost(**kw) -> Character:
    c = Character(id="c.g", exalt_type="Ghost", essence_rating=2)
    for k, v in kw.items():
        setattr(c, k, v)
    return c


def test_a_solar_gets_no_fetter_or_passion_panel(qtbot, ruleset):
    page = _page(ruleset, _solar())
    qtbot.addWidget(page)
    text = " ".join(_labels(page))
    assert "Fetters" not in text and "Passions" not in text


def test_a_ghost_gets_the_fetters_and_passions_tab_with_the_live_cap(qtbot, ruleset):
    from exalted_builder.models.character import FetterEntry
    char = _ghost(fetters=[FetterEntry(name="Grave", rating=1)])
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    assert "Fetters & Passions" in _tab_labels(page)
    _pick(page, "Fetters & Passions")
    # The cap is Willpower + Essence and it MOVES, so it is a live number on both
    # sides of the lock rather than a chargen note.
    assert any("cap = Willpower + Essence" in text for text in _labels(page))


def test_a_fetter_is_read_only_post_lock_and_bought_through_the_engine(qtbot, ruleset):
    """Post-lock a Fetter is BOUGHT, so the row's rating is read-only and moves through
    the priced controls."""
    from exalted_builder.models.character import FetterEntry
    char = _ghost(fetters=[FetterEntry(name="Grave", rating=1)])
    _locked_with_xp(ruleset, char)
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    _pick_named(page, "Fetters & Passions", "Grave")
    assert _widgets(page, DotTrack) == []               # no free setter on the entry
    assert any(w.text().startswith("Form (") for w in _widgets(page, QPushButton))
    assert any(w.text() == "Raise" for w in _widgets(page, QPushButton))


def test_a_passion_keeps_a_free_dot_track_after_the_lock(qtbot, ruleset):
    """⚠ A Passion is not bought at ANY point — its dots come from the Virtues and the
    player only distributes them (p.283) — so the post-lock XP stepper would be wrong
    here."""
    from exalted_builder.models.character import PassionEntry
    from exalted_builder.models.rules import VirtueName
    char = _ghost(passions=[PassionEntry(name="Revenge", virtue=VirtueName.CONVICTION,
                                         rating=1)])
    _locked_with_xp(ruleset, char)
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    _pick_named(page, "Fetters & Passions", "Revenge")
    tracks = _widgets(page, DotTrack)
    assert tracks, "a locked Passion still gets a free dot track"
    before = len(char.xp_log)
    tracks[-1]._click(3)
    assert char.passions[0].rating == 3
    assert len(char.xp_log) == before                   # free, never a purchase


# --------------------------------------------------------------------------- #
# The shared catalogue dialog
# --------------------------------------------------------------------------- #

def test_catalogue_dialog_filters_by_hiding_not_removing(qtbot, ruleset):
    picks = []
    rows = [("a", "Alpha", "first", "the full alpha text"),
            ("b", "Beta", "second", "the full beta text")]
    dialog = CatalogueDialog(theme.palette("Solar"), "Things", rows, picks.append)
    qtbot.addWidget(dialog)
    assert dialog.list.count() == 2
    dialog.search.setText("beta")
    assert dialog.list.item(0).isHidden() and not dialog.list.item(1).isHidden()
    assert "1 of 2 shown" in dialog.count.text()
    # A hidden row cannot be chosen even while it is the current one.
    dialog.list.setCurrentRow(0)
    dialog._choose()
    assert picks == []
    dialog.list.setCurrentRow(1)
    dialog._choose()
    assert picks == ["b"]


def test_catalogue_dialog_custom_picks_none(qtbot, ruleset):
    picks = []
    dialog = CatalogueDialog(theme.palette("Solar"), "Things",
                             [("a", "Alpha", "first", None)], picks.append)
    qtbot.addWidget(dialog)
    dialog._custom()
    assert picks == [None]


def test_selecting_a_second_entry_detaches_the_first_ones_controls(qtbot, ruleset):
    """⚠ The previous entry's widgets painted ON TOP of the next one's
    (human, 2026-08-21). The cause was a widget-only sweep: the caller builds its
    controls as nested rows, and a layout answers `item.widget() is None`, so nothing
    inside one was ever detached. Counting the LIVE descendants is what catches it —
    a stale row is still a child of the extras box."""
    char = _locked_with_xp(ruleset, _solar())
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    available = page._available_merits()
    dialog = page._build_gain_dialog(available)
    qtbot.addWidget(dialog)

    _select(dialog, MUTATION)
    first = len(dialog.extras_box.findChildren(QLabel))
    assert first                                     # it built something to begin with
    other = next(m.id for m in available if m.id != MUTATION)
    for _ in range(3):                               # thrash it; leaks accumulate
        _select(dialog, other)
        _select(dialog, MUTATION)
    assert len(dialog.extras_box.findChildren(QLabel)) == first


def test_the_dialog_does_not_reprint_the_description_the_detail_pane_shows(qtbot, ruleset):
    """Once scrollable in the detail pane and once truncated underneath reads as a bug
    (human, 2026-08-21). The cost/restriction/requires lines are NOT in the pane, so
    those stay."""
    char = _locked_with_xp(ruleset, _solar())
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    dialog = page._build_gain_dialog(page._available_merits())
    qtbot.addWidget(dialog)
    _select(dialog, MUTATION)
    description = ruleset.merits_flaws[MUTATION].description
    assert description in dialog.detail.toPlainText()
    extras = " ".join(w.text() for w in dialog.extras_box.findChildren(QLabel))
    assert description[:40] not in extras


def test_a_long_summary_is_cut_to_a_few_words_in_the_list(qtbot, ruleset):
    """A whole printed paragraph on every row scrolled the list off the screen
    (human, 2026-08-21). The full text still reaches the detail pane."""
    paragraph = " ".join(f"word{i}" for i in range(60))
    dialog = CatalogueDialog(theme.palette("Solar"), "Things",
                             [("a", "Alpha", paragraph, None)], lambda _k: None)
    qtbot.addWidget(dialog)
    label = dialog.list.item(0).text()
    assert label.startswith("Alpha\n")
    assert label.endswith("…")
    # The ellipsis is glued to the last kept word, so the token count is the limit.
    assert len(label.split("\n")[1].split()) == catalogue.BLURB_WORDS
    assert paragraph in dialog.detail.toPlainText()


def test_the_filter_still_matches_words_the_clamped_row_no_longer_shows(qtbot, ruleset):
    """⚠ The clamp is DISPLAY only. Filtering the truncated text would make an entry
    unfindable by a word its own description contains."""
    paragraph = " ".join(f"word{i}" for i in range(60))
    dialog = CatalogueDialog(theme.palette("Solar"), "Things",
                             [("a", "Alpha", paragraph, None),
                              ("b", "Beta", "nothing alike", None)], lambda _k: None)
    qtbot.addWidget(dialog)
    assert "word55" not in dialog.list.item(0).text()    # clamped away
    dialog.search.setText("word55")
    assert not dialog.list.item(0).isHidden() and dialog.list.item(1).isHidden()


# --------------------------------------------------------------------------- #
# shape B — what the tables-plus-detail-pane layout guarantees
# --------------------------------------------------------------------------- #

def test_a_background_shows_its_whole_printed_ladder_with_the_rung_held(qtbot, ruleset):
    """⚠ A Background's printed text differs PER RATING, so one paragraph is not the
    answer. The pane shows the blurb, then every rung, with the one held called out —
    the thing the card stack had no room for and the reason the spike's candidates
    were rejected until they had it."""
    char = _solar(backgrounds=[BackgroundEntry(name="Resources", rating=2)])
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    _pick_named(page, "Backgrounds", "Resources")
    labels = _labels(page)
    assert any("What each rating buys" in text for text in labels)
    catalog = validate.background_catalogue_for(ruleset, char)
    ladder = viewmod.background_ladder(catalog, "Resources")
    assert ladder, "Resources has no transcribed ladder to probe with"
    for dots, line in ladder:
        assert any(line in text for text in labels)


def test_the_ladder_is_the_shared_presenter_not_a_second_rendering(qtbot, ruleset):
    # ⚠ `view.background_ladder` already renders this for the catalogue dialog. A
    # second copy here is how two renderings of one rule drift apart.
    char = _solar(backgrounds=[BackgroundEntry(name="Resources", rating=3)])
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    _pick_named(page, "Backgrounds", "Resources")
    catalog = validate.background_catalogue_for(ruleset, char)
    held = viewmod.background_ladder(catalog, "Resources")[3][1]
    assert any(held in text for text in _labels(page))


def test_selecting_a_different_entry_replaces_the_editor(qtbot, ruleset):
    """⚠ The ghosting bug, at the page level. The detail pane is torn down between
    selections, and a widget-only sweep leaves the previous entry's controls painted on
    top of the next — `qt/layout.py` owns the fix; this pins that the page uses it."""
    char = _solar(backgrounds=[BackgroundEntry(name="Resources", rating=2),
                               BackgroundEntry(name="Allies", rating=1)])
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    for _ in range(6):
        _pick_named(page, "Backgrounds", "Resources")
        _pick_named(page, "Backgrounds", "Allies")
    # One entry is being edited, so exactly one rating control exists.
    assert len(_widgets(page, DotTrack)) == 1
    assert page.detail_title.text() == "Allies"


def test_the_add_button_follows_the_active_sub_tab(qtbot, ruleset):
    page = _page(ruleset, _solar())
    qtbot.addWidget(page)
    _tab(page, "Backgrounds")
    assert page.add_btn.text() == "+ Background"
    _tab(page, "Merits & Flaws")
    assert page.add_btn.text() == "+ Merit or Flaw"


def test_post_lock_the_add_button_becomes_the_gain_dialog(qtbot, ruleset):
    page = _page(ruleset, _locked_with_xp(ruleset, _solar()))
    qtbot.addWidget(page)
    _tab(page, "Merits & Flaws")
    assert page.add_btn.text() == "Gain a Merit or Flaw…"


def test_a_solar_gets_no_fetters_and_passions_tab(qtbot, ruleset):
    page = _page(ruleset, _solar())
    qtbot.addWidget(page)
    # An empty tab answering every attempt with a validation error is worse than none.
    assert "Fetters & Passions" not in _tab_labels(page)


def test_the_chargen_budget_sits_above_the_table_it_governs(qtbot, ruleset):
    page = _page(ruleset, _solar())
    qtbot.addWidget(page)
    _tab(page, "Backgrounds")
    assert any("dots to spend" in text
               for text in _notes_text(page, "Backgrounds"))


def test_post_lock_a_held_merit_shows_its_rules_text(qtbot, ruleset):
    """What the shipped card could NOT do: post-lock it listed held entries in a
    dropdown and showed nothing about them. The pane prints the printed text."""
    char = _locked_with_xp(ruleset, _solar())
    advancement.gain_merit_or_flaw(ruleset, char, MUTATION, taken_as="flaw", points=2)
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    _pick(page, "Merits & Flaws")
    description = ruleset.merits_flaws[MUTATION].description
    assert any(description[:40] in text for text in _labels(page))


def test_the_table_row_tracks_an_edit_without_losing_the_selection(qtbot, ruleset):
    char = _solar(backgrounds=[BackgroundEntry(name="Resources", rating=1)])
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    table = _pick_named(page, "Backgrounds", "Resources")
    _widgets(page, DotTrack)[0]._click(4)
    assert char.backgrounds[0].rating == 4
    assert table.topLevelItem(0).text(1).startswith("●●●●")
    assert page._selected == ("backgrounds", 0)
