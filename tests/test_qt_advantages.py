"""The Qt Advantages page (exalted_builder/qt/advantages.py) — Backgrounds, Merits &
Flaws, Fetters and Passions on one surface, in both regimes.

Covers what the widget decides for itself: which controls a regime gets, that the caps
and prices come from the engine, that the labels keyed to a Background's rating move
when it does, and that the in-play card routes a purchase through
`advancement.gain_merit_or_flaw` rather than choosing a side of its own. The catalogue
dialog is exercised through its list and its `on_pick` contract — `exec()` would block
a headless run.
"""

from pathlib import Path

import pytest

# ⚠ PySide6 is the OPTIONAL `qt` extra (pyproject), so it is legitimately absent on a
# machine that only runs the webapp. Skip the module rather than letting a bare import
# turn into a COLLECTION ERROR — that kills the whole run, not just these tests.
pytest.importorskip("PySide6", reason="the optional [qt] extra is not installed")

from PySide6.QtWidgets import QLabel, QLineEdit, QPushButton, QSpinBox

import exalted_builder
from exalted_builder import persistence
from exalted_builder.engine import advancement, lifecycle, validate
from exalted_builder.models.character import (BackgroundEntry, Character,
                                              HearthstoneEntry, MeritFlawPurchase)
from exalted_builder.qt.advantages import AdvantagesPage
from exalted_builder.qt.catalogue import CatalogueDialog
from exalted_builder.qt.editor import DotTrack
from exalted_builder.ui import theme

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
    return page._body_container.findChildren(kind)


def _labels(page) -> list[str]:
    return [w.text() for w in _widgets(page, QLabel)]


# --------------------------------------------------------------------------- #
# it builds, in both regimes and for a splat with no M&F rows yet
# --------------------------------------------------------------------------- #

def test_page_builds_for_a_fresh_character(qtbot, ruleset):
    page = _page(ruleset, _solar())
    qtbot.addWidget(page)
    assert "Backgrounds" in " ".join(_labels(page))


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
    assert "Custom Merit / Flaw" in _labels(page)
    # A custom row offers no catalogue combo, so it never joins the filter's row list.
    assert page._mf_rows == []


def test_the_filter_reoptions_the_rows_in_place(qtbot, ruleset):
    """⚠ The filter must NOT rebuild the body: a rebuilt search box has lost focus and
    would eat every character after the first. And a row's own held entry survives a
    filter that excludes it — a combo raises when its value is not among its
    options."""
    mp = MeritFlawPurchase(merit_id=PRODIGY, tier="aptitude")
    page = _page(ruleset, _solar(merits_flaws=[mp]))
    qtbot.addWidget(page)
    combo, _mp = page._mf_rows[0]
    everything = combo.count()
    searches = [w for w in _widgets(page, QLineEdit)
                if w.placeholderText().startswith("search")]
    assert len(searches) == 1
    searches[0].setText("zzzz-matches-nothing")
    assert combo.count() < everything
    assert combo.findData(PRODIGY) >= 0                 # the held entry stayed
    assert searches[0] is [w for w in _widgets(page, QLineEdit)
                           if w.placeholderText().startswith("search")][0]


def test_a_two_sided_row_offers_the_side_control(qtbot, ruleset):
    mp = MeritFlawPurchase(merit_id=MUTATION)
    page = _page(ruleset, _solar(merits_flaws=[mp]))
    qtbot.addWidget(page)
    assert "Taken" in _labels(page)


def test_adding_from_the_catalogue_opens_the_row_on_an_available_tier(qtbot, ruleset):
    char = _solar()
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    page._pick_mf(PRODIGY)
    assert char.merits_flaws[0].merit_id == PRODIGY
    assert char.merits_flaws[0].tier in validate.merit_tiers_available(
        ruleset.merits_flaws[PRODIGY], "Solar", "dawn")


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
    assert page._drop_idx == "0"                        # the card opens on the first
    page._drop_mf()
    assert char.merits_flaws == []


def test_a_non_experience_table_says_so_instead_of_offering_zero_xp_buttons(qtbot, ruleset):
    from exalted_builder.models.character import HouseRules
    char = _solar(house_rules=HouseRules(mf_change_method="swap"))
    _locked_with_xp(ruleset, char)
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    assert any("method (Player's Guide p.17)" in text for text in _labels(page))
    assert not any(w.text() == "Gain" for w in _widgets(page, QPushButton))


def test_the_gain_preview_prices_the_pending_pick(qtbot, ruleset):
    """Buying blind off a menu label is how you take a Flaw by accident: the preview
    names the side and the price before Gain is pressed, and nothing is bought until
    it is."""
    char = _locked_with_xp(ruleset, _solar())
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    page._pick_gain(MUTATION)
    text = " ".join(_labels(page))
    assert "Merit OR Flaw" in text and "points =" in text
    assert char.merits_flaws == []


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


def test_a_ghost_gets_both_panels_with_the_live_cap(qtbot, ruleset):
    char = _ghost()
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    text = " ".join(_labels(page))
    assert "Fetters" in text and "Passions" in text
    # The cap is Willpower + Essence and it MOVES, so it is a live number on both
    # sides of the lock rather than a chargen note.
    assert "cap = Willpower + Essence" in text


def test_a_fetter_is_read_only_post_lock_and_bought_through_the_engine(qtbot, ruleset):
    """Post-lock a Fetter is BOUGHT, so the row's rating is read-only and moves through
    the priced controls."""
    from exalted_builder.models.character import FetterEntry
    char = _ghost(fetters=[FetterEntry(name="Grave", rating=1)])
    _locked_with_xp(ruleset, char)
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    assert _widgets(page, DotTrack) == []               # no free setter on the row
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
