"""The Qt Gear page (exalted_builder/qt/gear.py) — the inventory, the shop, the
artifacts budget and the services price list.

Covers what the widget decides for itself: that the inventory filter chips move the
list, that a row's editor is built on expand and reaches the right object, that the
shop's rows and chips come from the presenter and the purchase from the engine, that a
merged artifact row exposes BOTH editors, and that a rebuild does not leak widgets.

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


def _stat(page, field):
    """The stat spin box for one field. ⚠ Addressed by objectName, never by position:
    the head row's quantity box is a QSpinBox too and indexing finds it first."""
    return page.findChild(QSpinBox, f"stat.{field}")


# --------------------------------------------------------------------------- #
# the inventory
# --------------------------------------------------------------------------- #

def test_inventory_lists_every_owned_kind(ruleset, qtbot):
    char = _solar(weapons=[Weapon(name="Hatchet")],
                  armor=[Armor(name="Buff Jacket")],
                  gear=[GearEntry(name="Rope")])
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    labels = _texts(page)
    assert "Hatchet" in labels and "Buff Jacket" in labels and "Rope" in labels
    assert "3 items owned" in page.readout.text()


def test_a_filter_chip_narrows_the_list_and_names_itself(ruleset, qtbot):
    char = _solar(weapons=[Weapon(name="Hatchet")], gear=[GearEntry(name="Rope")])
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    page._set_filter("weapon")
    labels = _texts(page)
    assert "Hatchet" in labels
    assert "Rope" not in labels
    # ⚠ EVERY state names its filter. The unfiltered heading is a strict PREFIX of the
    # filtered one, so a match on "Inventory (2)" alone cannot tell the two apart.
    assert any("showing Weapon (1)" in text for text in labels)


def test_the_unfiltered_heading_also_names_its_filter(ruleset, qtbot):
    page = _page(ruleset, _solar(gear=[GearEntry(name="Rope")]))
    qtbot.addWidget(page)
    assert any("showing Everything (1)" in text for text in _texts(page))


def test_an_empty_filter_is_not_offered_as_a_chip(ruleset, qtbot):
    page = _page(ruleset, _solar(gear=[GearEntry(name="Rope")]))
    qtbot.addWidget(page)
    captions = [b.text() for b in page.findChildren(QPushButton)]
    assert any(c.startswith("Goods (") for c in captions)
    assert not any(c.startswith("Weapon (") for c in captions)


def test_the_row_editor_is_built_on_expand_not_before(ruleset, qtbot):
    page = _page(ruleset, _solar(weapons=[Weapon(name="Hatchet", accuracy=1)]))
    qtbot.addWidget(page)
    # Collapsed: no stat spin boxes anywhere on the page.
    assert not _stat(page, "accuracy")
    _button(page, "Edit").setChecked(True)
    assert _stat(page, "accuracy")


def test_editing_a_stat_writes_through_to_the_model(ruleset, qtbot):
    char = _solar(weapons=[Weapon(name="Hatchet", accuracy=1)])
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    _button(page, "Edit").setChecked(True)
    _stat(page, "speed").setValue(3)
    assert char.weapons[0].speed == 3


def test_the_mobility_penalty_editor_accepts_the_negative_it_is_stored_as(ruleset,
                                                                          qtbot):
    # ⚠ `Armor.mobility_penalty` is stored NEGATIVE. A spin box floored at 0 would make
    # every printed armour penalty unenterable, and a consumer reading it as a
    # magnitude adds dice instead of removing them.
    char = _solar(armor=[Armor(name="Buff Jacket")])
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    _button(page, "Edit").setChecked(True)
    _stat(page, "mobility_penalty").setValue(-2)
    assert char.armor[0].mobility_penalty == -2


def test_deleting_a_row_removes_it(ruleset, qtbot):
    char = _solar(gear=[GearEntry(name="Rope")])
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    _button(page, "Edit").setChecked(True)
    _button(page, "Delete").click()
    assert char.gear == []
    assert "0 items owned" in page.readout.text()


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
    assert len([b for b in page.findChildren(QPushButton) if b.text() == "Edit"]) == 1
    _button(page, "Edit").setChecked(True)
    # ⚠ BOTH halves are editable under the one Edit. The stat line has no row of its
    # own, so a panel ignoring `linked_index` would make it silently uneditable.
    assert "Stat line" in _texts(page)
    assert any(b.text() == "Save to library" for b in page.findChildren(QPushButton))


def test_the_merged_row_still_answers_the_weapon_filter(ruleset, qtbot):
    # Merging two rows must not cost the object a filter it used to appear under.
    page = _page(ruleset, _daiklave_owner(ruleset))
    qtbot.addWidget(page)
    page._set_filter("weapon")
    assert "Daiklave" in _texts(page)


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
    shown = {dialog._group_of[key] for i, (key, *_rest) in enumerate(dialog._entries)
             if not dialog.list.item(i).isHidden()}
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
    page.reload()
    baseline = len(page.findChildren(QLabel))
    for _ in range(5):
        page.reload()
    assert len(page.findChildren(QLabel)) == baseline


def test_leaving_an_untouched_name_combo_does_not_collapse_the_row(ruleset, qtbot):
    """⚠ `editingFinished` fires on every focus loss, and a name change rebuilds the
    body — so an untouched combo must stay silent or tabbing past it closes the editor
    the player is working in."""
    char = _solar(weapons=[Weapon(name="Hatchet")])
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    _button(page, "Edit").setChecked(True)
    combo = page.findChild(_FilterCombo)
    combo.lineEdit().editingFinished.emit()
    assert _stat(page, "speed") is not None      # the editor is still open


def test_changing_the_name_combo_does_repick(ruleset, qtbot):
    # The positive control for the guard above: a real change still lands.
    char = _solar(weapons=[Weapon(name="Hatchet")])
    page = _page(ruleset, char)
    qtbot.addWidget(page)
    _button(page, "Edit").setChecked(True)
    combo = page.findChild(_FilterCombo)
    combo.setCurrentText("Long Bow")
    combo.lineEdit().editingFinished.emit()
    assert char.weapons[0].name == "Long Bow"


@pytest.mark.parametrize("locked", [False, True])
def test_the_gear_page_builds_for_every_splat(ruleset, qtbot, locked):
    """The render matrix. Unit tests assert the implemented thing directly; this
    proves the page BUILDS for shapes nobody wrote a test for — a splat with no
    Charms (Mortal), a splat with no castes, and both sides of the lock.

    Drives every shop chip and expands every row editor, because a crash in one of
    those is invisible to a page that merely constructed.
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
        for button in page.findChildren(QPushButton):
            if button.text() == "Edit":
                button.setChecked(True)
