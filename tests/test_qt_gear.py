"""The Qt Gear page (exalted_builder/qt/gear.py) — the inventory, the shop, the
artifacts budget and the services price list.

Covers what the widget decides for itself: that the inventory table lists every owned
kind, that the filter and search narrow it, that selecting a row builds the editor for
its kind in the detail pane, that the shop's rows and chips come from the presenter and
the purchase from the engine, that a merged artifact row exposes BOTH editors, and that
a rebuild does not leak widgets.

⚠ The layout is the CHARMS tab's (toolbar + splitter + table + detail pane), not the
NiceGUI page's. Tests address the table and the detail pane, never an accordion.

⚠ The dialogs are reached through `GearPage._build_*_dialog`, which returns one WITHOUT
running it. `exec()` would block a headless run, so the `_open_*` wrappers are not
testable and the builders are the seam. (Same shape as the Advantages page.)
"""

from pathlib import Path

import pytest

# ⚠ PySide6 is the OPTIONAL `qt` extra (pyproject), so it is legitimately absent on a
# machine that only runs the webapp. Skip the module rather than letting a bare import
# turn into a COLLECTION ERROR — that kills the whole run, not just these tests.
pytest.importorskip("PySide6", reason="the optional [qt] extra is not installed")

from PySide6.QtWidgets import QLabel, QPushButton, QSpinBox

from exalted_builder.engine import artifacts as artifactsmod, gear_actions, lifecycle
from exalted_builder.models.character import (Armor, ArtifactEntry, BackgroundEntry,
                                              Character, GearEntry, Weapon)
from exalted_builder.qt.catalogue import ALL_GROUPS
from exalted_builder.qt.editor import _FilterCombo
from exalted_builder.qt.gear import GearPage


def _page(ruleset, character, notes=None):
    sink = notes if notes is not None else []
    return GearPage(ruleset, {"char": character},
                    notify=lambda text, kind="info": sink.append((kind, text)))


def _solar(**kw) -> Character:
    c = Character(id="c.gear", name="Test", exalt_type="Solar", caste="dawn",
                  essence_rating=2)
    for k, v in kw.items():
        setattr(c, k, v)
    return c


def _texts(widget, kind=QLabel):
    return [w.text() for w in widget.findChildren(kind)]


def _button(page, caption):
    return next(b for b in page.findChildren(QPushButton) if b.text() == caption)


def _names(page):
    """The Name column of every visible inventory row."""
    table = page.table
    return [table.topLevelItem(i).text(0) for i in range(table.topLevelItemCount())]


def _row(page, name):
    """One inventory row by name."""
    table = page.table
    return next(table.topLevelItem(i) for i in range(table.topLevelItemCount())
                if table.topLevelItem(i).text(0) == name)


def _select(page, name):
    """Select an inventory row, which is what builds its editor in the detail pane."""
    page.table.setCurrentItem(_row(page, name))


def _stat(page, field):
    """The stat spin box for one field. ⚠ Addressed by objectName, never by position:
    the quantity box is a QSpinBox too and indexing finds it first."""
    return page.findChild(QSpinBox, f"stat.{field}")


def _set_filter(page, kind):
    page.filter_combo.setCurrentIndex(page.filter_combo.findData(kind))


# --------------------------------------------------------------------------- #
# the inventory
# --------------------------------------------------------------------------- #

def test_inventory_lists_every_owned_kind(ruleset, qtbot):
    char = _solar(weapons=[Weapon(name="Hatchet")],
                  armor=[Armor(name="Buff Jacket")],
                  gear=[GearEntry(name="Rope")])
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    assert set(_names(page)) == {"Hatchet", "Buff Jacket", "Rope"}
    assert "3 items owned" in page.readout.text()


def test_the_table_has_a_header_so_the_columns_align(ruleset, qtbot):
    # The native affordance the QLabel rows did not have: real columns, sortable.
    page = _page(ruleset, _solar(gear=[GearEntry(name="Rope")]))
    qtbot.addWidget(page)
    headers = [page.table.headerItem().text(i)
               for i in range(page.table.columnCount())]
    assert headers == ["Name", "Qty", "Res", "Kind", "Detail"]
    assert page.table.isSortingEnabled()


def test_the_filter_narrows_the_table(ruleset, qtbot):
    char = _solar(weapons=[Weapon(name="Hatchet")], gear=[GearEntry(name="Rope")])
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    _set_filter(page, "weapon")
    assert _names(page) == ["Hatchet"]


def test_the_filter_survives_a_table_rebuild(ruleset, qtbot):
    """⚠ `clear()` on the combo emits currentIndexChanged, so a refill that does not
    block signals resets the filter to "all" every time the table rebuilds — which
    makes the filter impossible to keep."""
    char = _solar(weapons=[Weapon(name="Hatchet")], gear=[GearEntry(name="Rope")])
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    _set_filter(page, "weapon")
    page.reload()
    assert page._filter == "weapon"
    assert _names(page) == ["Hatchet"]


def test_the_search_box_narrows_by_name(ruleset, qtbot):
    char = _solar(weapons=[Weapon(name="Hatchet")], gear=[GearEntry(name="Rope")])
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    page.search_box.setText("rop")
    assert _names(page) == ["Rope"]


def test_an_empty_filter_is_not_offered(ruleset, qtbot):
    page = _page(ruleset, _solar(gear=[GearEntry(name="Rope")]))
    qtbot.addWidget(page)
    offered = [page.filter_combo.itemData(i)
               for i in range(page.filter_combo.count())]
    assert "goods" in offered
    assert "weapon" not in offered


def test_selecting_a_row_builds_the_editor_for_its_kind(ruleset, qtbot):
    char = _solar(weapons=[Weapon(name="Hatchet", accuracy=1)],
                  gear=[GearEntry(name="Rope")])
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    _select(page, "Rope")
    assert _stat(page, "accuracy") is None     # goods have no weapon stats
    _select(page, "Hatchet")
    assert _stat(page, "accuracy") is not None


def test_the_detail_pane_titles_the_selection(ruleset, qtbot):
    page = _page(ruleset, _solar(weapons=[Weapon(name="Hatchet")]))
    qtbot.addWidget(page)
    _select(page, "Hatchet")
    assert page.detail_title.text() == "Hatchet"


def test_editing_a_stat_writes_through_to_the_model(ruleset, qtbot):
    char = _solar(weapons=[Weapon(name="Hatchet", accuracy=1)])
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    _select(page, "Hatchet")
    _stat(page, "speed").setValue(3)
    assert char.weapons[0].speed == 3


def test_a_stat_edit_updates_the_table_row_without_losing_the_selection(ruleset, qtbot):
    """The table must track the detail pane. ⚠ Via a per-row refresh, not a full
    rebuild — rebuilding mid-keystroke would drop focus out of the spin box."""
    char = _solar(weapons=[Weapon(name="Hatchet")])
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    _select(page, "Hatchet")
    _stat(page, "damage").setValue(7)
    assert "Dmg+7" in _row(page, "Hatchet").text(4)
    assert page._selected == ("weapons", 0)


def test_the_mobility_penalty_editor_accepts_the_negative_it_is_stored_as(ruleset,
                                                                          qtbot):
    # ⚠ `Armor.mobility_penalty` is stored NEGATIVE. A spin box floored at 0 would make
    # every printed armour penalty unenterable, and a consumer reading it as a
    # magnitude adds dice instead of removing them.
    char = _solar(armor=[Armor(name="Buff Jacket")])
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    _select(page, "Buff Jacket")
    _stat(page, "mobility_penalty").setValue(-2)
    assert char.armor[0].mobility_penalty == -2


def test_deleting_a_row_removes_it(ruleset, qtbot):
    char = _solar(gear=[GearEntry(name="Rope")])
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    _select(page, "Rope")
    _button(page, "Delete").click()
    assert char.gear == []
    assert _names(page) == []
    assert "0 items owned" in page.readout.text()


def test_the_actions_live_in_the_toolbar_not_the_content(ruleset, qtbot):
    """⚠ The native shape, and the reason this tab was rebuilt: a Buy button floating
    mid-page with a sentence beside it is a web call-to-action."""
    page = _page(ruleset, _solar())
    qtbot.addWidget(page)
    assert page.buy_btn.text() == "Buy…"
    assert page.add_artifact_btn.text() == "+ Artifact"


def test_the_price_list_is_its_own_subtab(ruleset, qtbot):
    # Reference material, not something owned — so it is not a card under the inventory.
    page = _page(ruleset, _solar())
    qtbot.addWidget(page)
    assert [page.tabs.tabText(i) for i in range(page.tabs.count())] == ["Inventory",
                                                                       "Prices"]


# --------------------------------------------------------------------------- #
# the merged artifact row
# --------------------------------------------------------------------------- #

def _daiklave_owner(ruleset) -> Character:
    """A character owning an artifact that HAS a gear half, granted properly."""
    char = _solar(backgrounds=[BackgroundEntry(name="Artifact", rating=3)])
    gear_actions.add_artifact(ruleset, char, "Daiklave")
    return char


def test_an_artifact_with_a_stat_line_is_one_row_with_both_editors(ruleset, qtbot):
    char = _daiklave_owner(ruleset)
    assert len(char.artifacts) == 1 and len(char.weapons) == 1
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    # ONE row, not two peers (human, 2026-08-14: two rows for one Crimson Bow "feels
    # odd, and a little obtuse").
    assert _names(page) == ["Daiklave"]
    _select(page, "Daiklave")
    # ⚠ BOTH halves are editable in the one detail pane. The stat line has no row of
    # its own, so a pane ignoring `linked_index` would make it silently uneditable —
    # the artifact's Rating spin box AND the weapon's stat grid must both be present.
    assert "Stat line" in _texts(page)
    assert _stat(page, "accuracy") is not None


def test_the_merged_row_still_answers_the_weapon_filter(ruleset, qtbot):
    # Merging two rows must not cost the object a filter it used to appear under.
    page = _page(ruleset, _daiklave_owner(ruleset))
    qtbot.addWidget(page)
    _set_filter(page, "weapon")
    assert _names(page) == ["Daiklave"]


# --------------------------------------------------------------------------- #
# the shop
# --------------------------------------------------------------------------- #

def test_the_shop_offers_type_chips_from_the_presenter(ruleset, qtbot):
    page = _page(ruleset, _solar())
    qtbot.addWidget(page)
    dialog = page._build_shop_dialog()
    qtbot.addWidget(dialog)
    assert set(dialog.group_buttons) >= {ALL_GROUPS, "Weapon", "Armour", "Goods"}


def test_a_type_chip_hides_the_other_kinds(ruleset, qtbot):
    page = _page(ruleset, _solar())
    qtbot.addWidget(page)
    dialog = page._build_shop_dialog()
    qtbot.addWidget(dialog)
    dialog._set_group("Armour")
    # ⚠ `_group_of` holds a LIST per key since 2026-08-27 (a row may sit in several
    # groups — an adversary is filed under all of its categories). Gear passes one group
    # per row, so the flattened set is still a single kind.
    shown = {group for i, (key, *_rest) in enumerate(dialog._entries)
             if not dialog.list.item(i).isHidden()
             for group in dialog._group_of[key]}
    assert shown == {"Armour"}


def test_a_chip_click_rehomes_a_hidden_selection(ruleset, qtbot):
    # ⚠ Hiding the selected row would leave the confirm button labelled and enabled
    # for something off screen, and `_choose` then silently refuses.
    page = _page(ruleset, _solar())
    qtbot.addWidget(page)
    dialog = page._build_shop_dialog()
    qtbot.addWidget(dialog)
    dialog._set_group("Goods")
    assert not dialog.list.currentItem().isHidden()


def test_buying_a_weapon_appends_it_with_its_catalogue_stats(ruleset, qtbot):
    char = _solar()
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    page._buy("weapon:Long Bow")
    assert [w.name for w in char.weapons] == ["Long Bow"]
    # The catalogue's stats came with it — a name-only append would mean the shop
    # picked nothing.
    catalogue_entry = next(w for w in ruleset.weapon_catalog.values()
                           if w.name == "Long Bow")
    assert char.weapons[0].accuracy == catalogue_entry.accuracy
    assert char.weapons[0].damage == catalogue_entry.damage


def test_a_custom_kind_adds_a_blank_row_of_that_kind(ruleset, qtbot):
    # Making a thing and buying a thing are ONE surface — the kind rides back in the
    # key, so the shop knows which list a blank row belongs in.
    char = _solar()
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    page._buy("custom:armor")
    assert len(char.armor) == 1 and char.armor[0].name == ""
    assert char.weapons == [] and char.gear == []


def test_the_shop_offers_no_artifacts_at_chargen(ruleset, qtbot):
    # Decision 0017: the Artifact Background is the pre-game channel, cash is in-play.
    page = _page(ruleset, _solar())
    qtbot.addWidget(page)
    dialog = page._build_shop_dialog()
    qtbot.addWidget(dialog)
    assert "Artifact" not in dialog.group_buttons
    assert "artifacts" not in [b.text() for b in dialog.findChildren(QPushButton)]


def test_the_shop_offers_artifacts_once_locked(ruleset, qtbot):
    char = _solar()
    lifecycle.lock_chargen(char, ruleset)
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    dialog = page._build_shop_dialog()
    qtbot.addWidget(dialog)
    assert "Artifact" in dialog.group_buttons


def test_a_cash_bought_artifact_is_not_charged_to_the_background(ruleset, qtbot):
    char = _solar()
    lifecycle.lock_chargen(char, ruleset)
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    art = next(a for a in ruleset.artifact_catalog.values() if a.resources_cost)
    page._buy(f"artifact:{art.name}")
    assert char.artifacts[-1].acquired == artifactsmod.ACQUIRED_PURCHASED
    assert artifactsmod.budgeted_items(char) == []


def test_services_are_never_offered_in_the_shop(ruleset, qtbot):
    # The ruling holds at the OFFER, not just in the data: a character does not carry
    # a month of stabling in her pack.
    page = _page(ruleset, _solar())
    qtbot.addWidget(page)
    dialog = page._build_shop_dialog()
    qtbot.addWidget(dialog)
    keys = {key for key, *_rest in dialog._entries}
    services = {f"goods:{g.id}" for g in ruleset.gear_catalog.values()
                if g.kind == "service"}
    assert services and not (keys & services)


# --------------------------------------------------------------------------- #
# artifacts and the price list
# --------------------------------------------------------------------------- #

def test_the_artifacts_header_states_the_corebook_rule(ruleset, qtbot):
    char = _solar(backgrounds=[BackgroundEntry(name="Artifact", rating=3)],
                  artifacts=[ArtifactEntry(name="Raptor wings", rating=3)])
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    assert any("Artifacts (1/1" in text for text in _texts(page))


def test_picking_an_artifact_grants_its_stat_line(ruleset, qtbot):
    char = _solar(backgrounds=[BackgroundEntry(name="Artifact", rating=3)])
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    page._pick_artifact("Daiklave")
    # ⚠ The pair is counted ONCE — the grant stamps `from_artifact`.
    assert len(char.weapons) == 1 and char.weapons[0].from_artifact
    assert len(artifactsmod.budgeted_items(char)) == 1


def test_the_price_list_prints_the_cash_column(ruleset, qtbot):
    # ⚠ `GearType.cash` is this panel's whole point and its only read site — a PRICE
    # list showing no prices is the house bug, and it shipped that way once.
    page = _page(ruleset, _solar())
    qtbot.addWidget(page)
    priced = [g for g in ruleset.gear_catalog.values() if g.kind == "service" and g.cash]
    assert priced
    labels = _texts(page)
    assert any(g.cash in labels for g in priced)


def test_the_readout_reports_artifact_issues_beside_the_artifacts(ruleset, qtbot):
    # ⚠ A report sitting on a surface that no longer edits the thing it reports about
    # is the house bug in UI form.
    char = _solar(artifacts=[ArtifactEntry(name="Raptor wings", rating=5)])
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    assert "artifact" in page.readout.text().lower()


# --------------------------------------------------------------------------- #
# teardown
# --------------------------------------------------------------------------- #

def test_thrashing_the_rebuild_does_not_leak_widgets(ruleset, qtbot):
    """⚠ A teardown sweep must RECURSE into nested layouts — `item.widget()` is None
    for a QLayout, and this page builds every row as one. A single rebuild passes
    while leaking, so thrash it and count live descendants."""
    char = _solar(weapons=[Weapon(name="Hatchet")],
                  gear=[GearEntry(name="Rope")])
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    _select(page, "Hatchet")
    page.reload()
    baseline = len(page.findChildren(QLabel))
    for _ in range(5):
        page.reload()
        _select(page, "Hatchet")
        _select(page, "Rope")
        _select(page, "Hatchet")
    assert len(page.findChildren(QLabel)) == baseline


def test_leaving_an_untouched_name_combo_is_silent(ruleset, qtbot):
    """⚠ `editingFinished` fires on every focus loss, and a name change rebuilds the
    table — so an untouched combo must stay silent, or tabbing past it drops the player
    out of the row they are working in."""
    char = _solar(weapons=[Weapon(name="Hatchet")])
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    _select(page, "Hatchet")
    combo = page.findChild(_FilterCombo)
    combo.lineEdit().editingFinished.emit()
    assert page._selected == ("weapons", 0)      # still on the row being edited


def test_changing_the_name_combo_does_repick(ruleset, qtbot):
    # The positive control for the guard above: a real change still lands.
    char = _solar(weapons=[Weapon(name="Hatchet")])
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    _select(page, "Hatchet")
    combo = page.findChild(_FilterCombo)
    combo.setCurrentText("Long Bow")
    combo.lineEdit().editingFinished.emit()
    assert char.weapons[0].name == "Long Bow"


@pytest.mark.parametrize("locked", [False, True])
def test_the_gear_page_builds_for_every_splat(ruleset, qtbot, locked):
    """The render matrix. Unit tests assert the implemented thing directly; this
    proves the page BUILDS for shapes nobody wrote a test for — a splat with no
    Charms (Mortal), a splat with no castes, and both sides of the lock.

    Drives every shop chip, selects every inventory row (which builds its editor) and
    opens the Prices sub-tab, because a crash in any of those is invisible to a page
    that merely constructed.
    """
    from exalted_builder.engine import lifecycle
    for splat in ruleset.exalts:
        char = Character(id="c.matrix", name="Test", exalt_type=splat,
                         weapons=[Weapon(name="Hatchet")],
                         armor=[Armor(name="Buff Jacket")],
                         gear=[GearEntry(name="Rope")],
                         artifacts=[ArtifactEntry(name="Dragon Tear Tiara", rating=2)])
        if locked:
            lifecycle.lock_chargen(char, ruleset)
        page = _page(ruleset, char)
        qtbot.addWidget(page)
        dialog = page._build_shop_dialog()
        qtbot.addWidget(dialog)
        for group in list(dialog.group_buttons):
            dialog._set_group(group)
        for i in range(page.table.topLevelItemCount()):
            page.table.setCurrentItem(page.table.topLevelItem(i))
        page.tabs.setCurrentIndex(1)      # the Prices sub-tab
