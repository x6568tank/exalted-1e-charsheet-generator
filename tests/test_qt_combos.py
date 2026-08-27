"""The Qt Combos sub-tab (exalted_builder/qt/combos.py) and `engine/combo_actions.py`.

Covers what the widget decides for itself: that ONE tab renders one of TWO systems
(Combos, or Arrays for a Charm-Slot splat) and never both, that the toolbar SWAPS at the
lock rather than greying, that a member add moves the cost without losing the selection,
that an Array's add-pool excludes every Charm linked into any Array, and that the buy
dialog refuses an empty or unaffordable pick.

⚠ The two sides of the lock are different SHAPES. At chargen a Combo is assembled in
place and priced in bonus points; in play it is bought WHOLE through
`advancement.add_combo`, and a bought one is fixed — undo it in the Experience card.

⚠ `isVisible()` is useless on a child of a widget that was never shown — it is False
however the widget is configured, so a negative assertion passes vacuously
(`test_qt_advantages.py:490` recorded this first). `isHidden()` throughout.

⚠ The buy dialog is reached through `_build_buy_dialog`, which returns one WITHOUT
running it: `exec()` blocks a headless run (the seam `GearPage` uses).
"""

from pathlib import Path

import pytest

# ⚠ PySide6 is the OPTIONAL `qt` extra (pyproject), so it is legitimately absent on a
# machine that only runs the webapp. Skip the module rather than letting a bare import
# turn into a COLLECTION ERROR — that kills the whole run, not just these tests.
pytest.importorskip("PySide6", reason="the optional [qt] extra is not installed")

from PySide6.QtWidgets import QLabel, QListWidget, QPushButton

from exalted_builder import persistence
from exalted_builder.engine import advancement, combo_actions, lifecycle
from exalted_builder.models.character import Character
from exalted_builder.qt.charms import CharmsPage
from exalted_builder.qt.combos import CombosPage
from exalted_builder.ui import view as viewmod

_EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def _load(stem):
    return persistence.load_character(_EXAMPLES / f"{stem}.character.json",
                                      absorb_custom=False)


def _page(ruleset, character, notes=None, on_change=None):
    sink = notes if notes is not None else []
    return CombosPage(ruleset, {"char": character},
                      notify=lambda text, kind="info": sink.append((kind, text)),
                      on_change=on_change)


def _names(page):
    table = page.table
    return [table.topLevelItem(i).text(1) for i in range(table.topLevelItemCount())]


def _addable(page):
    return page._detail_body.findChild(QListWidget, "combos.addable")


def _first_addable(page):
    picker = _addable(page)
    return picker.item(0).data(0x0100) if picker and picker.count() else None   # UserRole


# --------------------------------------------------------------------------- #
# one tab, two systems
# --------------------------------------------------------------------------- #

def test_a_solar_builds_combos(ruleset, qtbot):
    page = _page(ruleset, _load("ashes-of-dawn"))
    qtbot.addWidget(page)
    assert not page._arrays() and page._noun() == "Combo"
    assert "Combo" in page.blurb.text() and "pp.213-214" in page.blurb.text()


def test_an_alchemical_builds_arrays_instead(ruleset, qtbot):
    """⚠ The two systems are MUTUALLY EXCLUSIVE per splat, and the noun, the presenter
    and the engine calls all key off `view.uses_arrays` — never a splat-name check."""
    page = _page(ruleset, _load("gearheart"))
    qtbot.addWidget(page)
    assert page._arrays() and page._noun() == "Array"
    assert "Array" in page.blurb.text() and "p.89" in page.blurb.text()
    assert page.add_btn.text() == "+ Array"


def test_the_system_is_read_per_call_not_cached(ruleset, qtbot):
    """⚠ The splat can change on the Identity tab while this page exists; a cached
    answer would leave an Alchemical building Combos."""
    char = _load("ashes-of-dawn")
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    assert page._noun() == "Combo"
    page._ctx["char"] = _load("gearheart")
    assert page._noun() == "Array"


def test_a_splat_that_builds_neither_gets_no_sub_tab(ruleset, qtbot):
    """The dead may never learn Combos (E:Ab p.234), and an empty tab answering every
    attempt with a validation error is worse than no tab."""
    ghost = Character(id="c.ghost", exalt_type="Ghost", essence_rating=2)
    assert not viewmod.has_combos_tab(ruleset, ghost)
    page = CharmsPage(ruleset, {"char": ghost})
    qtbot.addWidget(page)
    assert not any(page.tabs.tabText(i) in ("Combos", "Arrays")
                   for i in range(page.tabs.count()))


# --------------------------------------------------------------------------- #
# building one at chargen
# --------------------------------------------------------------------------- #

def test_adding_a_combo_lands_on_it_with_its_member_picker(ruleset, qtbot):
    char = _load("ashes-of-dawn")
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    assert _names(page) == []
    page._add()
    assert len(char.combos) == 1
    assert page._selected == 0
    assert _addable(page) is not None          # the next thing the player wants


def test_adding_a_member_moves_the_cost_and_keeps_the_selection(ruleset, qtbot):
    """⚠ A membership change moves the cost and the issues but NOT the row set, so the
    selection survives — unlike a rebuild, which drops it because an index is a
    position."""
    char = _load("ashes-of-dawn")
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    page._add()
    page._add_member(0, _first_addable(page))
    assert len(char.combos[0].charm_ids) == 1
    assert page._selected == 0
    assert "1 bonus point(s)" in page.readout.text()
    assert page.table.topLevelItem(0).text(3) == "1 BP"


def test_dropping_a_member_puts_it_back_in_the_pool(ruleset, qtbot):
    char = _load("ashes-of-dawn")
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    page._add()
    before = _addable(page).count()
    charm_id = _first_addable(page)
    page._add_member(0, charm_id)
    assert _addable(page).count() == before - 1
    page._drop(0, charm_id)
    assert char.combos[0].charm_ids == []
    assert _addable(page).count() == before


def test_deleting_a_combo_drops_the_selection(ruleset, qtbot):
    char = _load("ashes-of-dawn")
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    page._add()
    page._delete()
    assert char.combos == []
    assert _names(page) == []


def test_an_illegal_combo_is_flagged_not_refused(ruleset, qtbot):
    """⚠ Legality is reported as an issue on the ROW, not enforced at add time — a
    half-built Combo must be inspectable rather than refused mid-assembly. An empty one
    is the simplest case: too few Charms."""
    char = _load("ashes-of-dawn")
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    page._add()
    rows, _addable_rows, _total = page._rows()
    assert rows[0].issues                              # the engine says so
    assert page.table.topLevelItem(0).text(0) == "⚠"   # and the table shows it


# --------------------------------------------------------------------------- #
# Arrays — the one-Array-per-Charm rule
# --------------------------------------------------------------------------- #

def test_an_arrays_pool_excludes_charms_linked_into_any_array(ruleset, qtbot):
    """⚠ A Charm may join only ONE Array (p.90). The pool must exclude every LINKED
    Charm, not merely this Array's own members — the engine refuses a reuse, so offering
    one produces nothing but a rejection."""
    char = _load("gearheart")
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    linked = combo_actions.linked_array_charms(char)
    assert linked                                      # the example already has some
    page._add()
    picker = _addable(page)
    offered = {picker.item(i).data(0x0100) for i in range(picker.count())}
    assert offered and not (offered & linked)


def test_an_array_shows_what_it_saves_in_committed_essence(ruleset, qtbot):
    """The installation discount is the mechanical POINT of an Array."""
    char = _load("gearheart")
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    rows, _a, _t = page._rows()
    row = next(r for r in rows if r.install_loose)
    page.table.setCurrentItem(next(
        page.table.topLevelItem(i) for i in range(page.table.topLevelItemCount())
        if page.table.topLevelItem(i).text(1) == row.name))
    texts = [w.text() for w in page._detail_body.findChildren(QLabel)]
    assert any("committed Essence" in t for t in texts)


# --------------------------------------------------------------------------- #
# the lock — a different SHAPE, not the same one greyed
# --------------------------------------------------------------------------- #

def _locked_solar(ruleset, xp=40):
    char = _load("ashes-of-dawn")
    lifecycle.lock_chargen(char, ruleset)
    advancement.add_xp(char, xp)
    return char


def test_the_toolbar_swaps_at_the_lock(ruleset, qtbot):
    """⚠ `isHidden`, not `isVisible` — the latter is False on a child of a widget that
    was never shown, so the assertion would pass vacuously either way."""
    page = _page(ruleset, _load("ashes-of-dawn"))
    qtbot.addWidget(page)
    assert not page.add_btn.isHidden() and page.buy_btn.isHidden()

    locked = _page(ruleset, _locked_solar(ruleset))
    qtbot.addWidget(locked)
    assert locked.add_btn.isHidden() and not locked.buy_btn.isHidden()
    assert not locked.delete_btn.isEnabled()


def test_a_bought_combo_quotes_no_bonus_points(ruleset, qtbot):
    """⚠ The BP price is a CHARGEN fact. In play the Combo is already paid for and its
    XP price is on the ledger, so quoting BP beside it invents a cost that is not owed."""
    char = _locked_solar(ruleset)
    eligible = list(viewmod.build_combo_view(ruleset, char).addable)
    advancement.add_combo(ruleset, char, "Bought One",
                          [m.id for m in eligible[:2]])
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    assert page.table.topLevelItem(0).text(3) == "—"


def test_post_lock_list_edits_are_refused_by_the_engine(ruleset):
    """The engine is the guard, not the greyed button — both shells go through it."""
    char = _locked_solar(ruleset)
    for call in (lambda: combo_actions.add_combo(char),
                 lambda: combo_actions.remove_combo(char, 0),
                 lambda: combo_actions.add_combo_member(char, 0, "x"),
                 lambda: combo_actions.remove_combo_member(char, 0, "x")):
        with pytest.raises(advancement.AdvancementError):
            call()


# --------------------------------------------------------------------------- #
# buying one whole
# --------------------------------------------------------------------------- #

def test_the_buy_dialog_refuses_an_empty_pick(ruleset, qtbot):
    """⚠ Disabled on an EMPTY pick too, not only an unaffordable one: a zero-cost
    purchase of nothing would log an XP entry for an illegal Combo."""
    page = _page(ruleset, _locked_solar(ruleset))
    qtbot.addWidget(page)
    dialog = page._build_buy_dialog()
    qtbot.addWidget(dialog)
    assert not dialog.findChild(QPushButton, "combos.buy.confirm").isEnabled()


def test_the_buy_dialog_prices_the_pick_and_buys_it(ruleset, qtbot):
    char = _locked_solar(ruleset)
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    dialog = page._build_buy_dialog()
    qtbot.addWidget(dialog)
    picker = dialog.findChild(QListWidget, "combos.buy.charms")
    picker.item(0).setSelected(True)
    picker.item(1).setSelected(True)
    price = dialog.findChild(QLabel, "combos.buy.price")
    assert "XP" in price.text() and "p.213" in price.text()
    assert dialog.findChild(QPushButton, "combos.buy.confirm").isEnabled()
    spent_before = advancement.xp_spent(char)
    page._buy(dialog, "Test Combo", [picker.item(i).data(0x0100) for i in (0, 1)])
    assert [c.name for c in char.combos] == ["Test Combo"]
    assert advancement.xp_spent(char) > spent_before


def test_an_unaffordable_combo_cannot_be_bought(ruleset, qtbot):
    page = _page(ruleset, _locked_solar(ruleset, xp=0))
    qtbot.addWidget(page)
    dialog = page._build_buy_dialog()
    qtbot.addWidget(dialog)
    picker = dialog.findChild(QListWidget, "combos.buy.charms")
    picker.item(0).setSelected(True)
    picker.item(1).setSelected(True)
    assert not dialog.findChild(QPushButton, "combos.buy.confirm").isEnabled()


# --------------------------------------------------------------------------- #
# the shell contract
# --------------------------------------------------------------------------- #

def test_building_a_combo_pings_the_owning_page(ruleset, qtbot):
    """⚠ A Combo costs bonus points at chargen and XP in play, so it moves the Charms
    tab's readout AND the shell's — the hook contract every sibling page has."""
    pings = []
    page = _page(ruleset, _load("ashes-of-dawn"), on_change=lambda: pings.append(1))
    qtbot.addWidget(page)
    page._add()
    assert pings
    pings.clear()
    page._add_member(0, _first_addable(page))
    assert pings


def test_the_charms_tab_wires_the_sub_tab_with_on_change(ruleset, qtbot):
    page = CharmsPage(ruleset, {"char": _load("ashes-of-dawn")})
    qtbot.addWidget(page)
    index = next(i for i in range(page.tabs.count())
                 if page.tabs.tabText(i) == "Combos")
    sub = page.tabs.widget(index)
    assert isinstance(sub, CombosPage)
    assert sub._on_change is not None


def test_the_shared_detail_pane_is_hidden_on_the_combos_sub_tab(ruleset, qtbot):
    """⚠ This is the ONE sub-tab that brings its own detail pane. Every other one is a
    content pane that FEEDS the shared `QTextBrowser`, so leaving it up put TWO detail
    panes on screen — the real one, and an empty column saying "Select an entry to see
    details." Found by rendering, invisible to every other test."""
    page = CharmsPage(ruleset, {"char": _load("ashes-of-dawn")})
    qtbot.addWidget(page)
    combos = next(i for i in range(page.tabs.count())
                  if page.tabs.tabText(i) == "Combos")
    charms = next(i for i in range(page.tabs.count())
                  if page.tabs.tabText(i) == "Charms")
    page.tabs.setCurrentIndex(combos)
    assert page._detail_panel.isHidden()
    page.tabs.setCurrentIndex(charms)
    assert not page._detail_panel.isHidden()


def test_a_rebuild_does_not_leak_widgets(ruleset, qtbot):
    """⚠ Thrash the rebuild and count. A single reload passes while leaking."""
    char = _load("ashes-of-dawn")
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    page._add()
    baseline = len(page._detail_body.findChildren(QPushButton))
    for _ in range(6):
        page.reload()
    assert len(page._detail_body.findChildren(QPushButton)) == baseline
