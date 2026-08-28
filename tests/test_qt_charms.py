"""The Qt Charms tab (exalted_builder/qt/charms.py) — QGraphicsView charm trees.

Ports the qt_tree spike's layout/routing coverage into the port: per-splat tab sets,
node/edge/root counts, the tidy-tree layout, wheel zoom, and selection → detail. The
layout and routing functions are pure, so they test without a widget at all.
"""

import pytest

# ⚠ PySide6 is the OPTIONAL `qt` extra (pyproject), so it is legitimately absent on a
# machine that only runs the webapp. Skip the module rather than letting a bare import
# turn into a COLLECTION ERROR — that kills the whole run, not just these tests.
pytest.importorskip("PySide6", reason="the optional [qt] extra is not installed")

from types import SimpleNamespace

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import (QCheckBox, QLabel, QLineEdit, QPushButton,
                               QSpinBox)

from exalted_builder.engine import (advancement, charm_actions, lifecycle,
                                    refit, validate)
from exalted_builder.models.character import (AbilityName, Character,
                                               MeritFlawPurchase, PathRating)
from exalted_builder.models.rules import Orientation
from exalted_builder.qt.charms import (CharmsPage, CharmTreeView, DotTrack,
                                       trees_for,
                                       EdgeItem, NodeItem, _tree_positions, populate)
from exalted_builder.ui import view as viewmod
from exalted_builder.ui.view import build_charm_detail, build_thaum_picker


def _visible_tabs(page):
    return [page.tabs.tabText(i) for i in range(page.tabs.count())]


def _open_paths(page):
    """Switch to the Paths tab; returns it."""
    for i in range(page.tabs.count()):
        if page.tabs.tabText(i) == "Paths":
            page.tabs.setCurrentIndex(i)
            return page.tabs.widget(i)
    raise AssertionError("no Paths tab")


def _select_path(page, path_id):
    """Select one Path in the list and return the bound rating DotTrack."""
    _open_paths(page)
    lst = page._paths_list
    for row in range(lst.count()):
        if lst.item(row).data(Qt.UserRole) == path_id:
            lst.setCurrentRow(row)
            return page._path_box.findChild(DotTrack)
    raise AssertionError(f"no list row for {path_id}")


def test_solar_page_tabs(ruleset, qtbot):
    # ⚠ Combos sits between the trees and Spells since 2026-08-21 — it moved here from
    # the rail, because a Combo is assembled out of Charms the character already owns.
    page = CharmsPage(ruleset, {"char": Character(id="char.new", exalt_type="Solar")})
    qtbot.addWidget(page)
    assert _visible_tabs(page) == ["Charms", "Martial Arts", "Combos", "Spells",
                                   "Thaumaturgy"]
    assert "abilities" in page._tree_views


def test_ghost_page_tabs(ruleset, qtbot):
    page = CharmsPage(ruleset, {"char": Character(id="char.new", exalt_type="Ghost")})
    qtbot.addWidget(page)
    tabs = _visible_tabs(page)
    assert "Charms" not in tabs          # ghosts have no Charm trees
    assert "Arcanoi" in tabs
    assert "Spells" not in tabs          # ghosts cannot learn necromancy
    assert "arcanoi" in page._tree_views


def test_melee_tree_renders_nodes_edges(qtbot, ruleset):
    char = Character(id="char.new")
    page = CharmsPage(ruleset, {"char": char})
    qtbot.addWidget(page)
    view = page._tree_views["abilities"]
    graph = view.graph
    assert graph is not None
    scene = view.scene()
    node_items = [i for i in scene.items() if isinstance(i, NodeItem)]
    edge_items = [i for i in scene.items() if isinstance(i, EdgeItem)]
    assert len(node_items) == len(graph.nodes)
    assert len(edge_items) == len(graph.edges)


def test_tree_positions_centers_parent_over_children():
    # A 3-node tree: a parent with two children of equal width. The parent sits at
    # the centre of its children's span, above them.
    graph = SimpleNamespace(
        nodes=[SimpleNamespace(id=n) for n in ("root", "a", "b")],
        edges=[("root", "a"), ("root", "b")])
    width = {"root": 100, "a": 60, "b": 60}
    pos = _tree_positions(graph, width)
    assert pos["root"][1] < pos["a"][1]
    children_centre = (pos["a"][0] + pos["b"][0]) / 2
    assert abs(pos["root"][0] - children_centre) < 1e-6


def test_wide_levels_sub_row():
    # A parent with eleven children (Prismatic Arrangement of Creation) must not sit
    # them all on one row — the level sub-rows at MAX_LEVEL_NODES (6 + 5).
    nodes = [SimpleNamespace(id="center")] + [SimpleNamespace(id=f"c{i}") for i in range(11)]
    edges = [("center", f"c{i}") for i in range(11)]
    graph = SimpleNamespace(nodes=nodes, edges=edges)
    width = {n.id: 100.0 for n in nodes}
    pos = _tree_positions(graph, width)
    child_ys = {pos[f"c{i}"][1] for i in range(11)}
    assert len(child_ys) >= 2


def test_click_selects_node_and_shows_detail(qtbot, ruleset):
    char = Character(id="char.new")
    page = CharmsPage(ruleset, {"char": char})
    qtbot.addWidget(page)
    view = page._tree_views["abilities"]
    node_item = next(i for i in view.scene().items() if isinstance(i, NodeItem))
    node_item.setSelected(True)
    qtbot.wait(5)
    detail = page.detail.toPlainText()
    assert len(detail) > 0


def _learnable_char():
    """A Solar with a few ability dots, so some Charms are actually available — a
    fresh Character's abilities are all 0 and nothing passes a prerequisite."""
    char = Character(id="char.new")
    for ab in (AbilityName.MELEE, AbilityName.ARCHERY, AbilityName.DODGE,
               AbilityName.OCCULT):
        char.abilities[ab] = 3
    return char


def _first_available(ruleset, char):
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    view = page._tree_views["abilities"]
    return [i.node.id for i in view.scene().items()
            if isinstance(i, NodeItem) and i.node.state == "available"]


def test_charms_learn_appends_in_chargen(qtbot, ruleset):
    char = _learnable_char()
    avail = _first_available(ruleset, char)
    assert avail
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    page._toggle_charm(avail[0])
    assert avail[0] in char.charms


def test_charms_buy_post_lock_spends_xp(qtbot, ruleset):
    char = _learnable_char()
    advancement.add_xp(char, 100)
    lifecycle.lock_chargen(char, ruleset)
    avail = _first_available(ruleset, char)
    assert avail
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    available_before = advancement.xp_available(char)
    page._toggle_charm(avail[0])
    assert avail[0] in char.charms
    assert advancement.xp_available(char) < available_before


def test_charms_learn_thaum_art(qtbot, ruleset):
    char = _learnable_char()
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    picker = build_thaum_picker(ruleset, char)
    arts = [r for r in picker.arts if r.available]
    assert arts
    page._toggle_thaum("art", arts[0])
    after = build_thaum_picker(ruleset, char)
    assert any(r.id == arts[0].id and r.owned for r in after.arts)


def test_charms_learn_thaum_art_specialty(qtbot, ruleset):
    char = _learnable_char()
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    picker = build_thaum_picker(ruleset, char)
    art = next((a for a in picker.arts if a.specialties), None)
    assert art is not None
    spec = next((s for s in art.specialties if s.available), None)
    assert spec is not None
    page._toggle_thaum("art_specialty", art, spec)
    after = build_thaum_picker(ruleset, char)
    owned_specs = {s.name for a in after.arts for s in a.specialties if s.owned}
    assert spec.name in owned_specs


def test_charms_thaum_buy_flips_button_and_unlearns(qtbot, ruleset):
    char = _learnable_char()
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    picker = build_thaum_picker(ruleset, char)
    formula = next(r for r in picker.formulas if r.available)
    page._selected_thaum = ("formula", formula)
    page._toggle_thaum("formula", formula)
    assert page._selected_thaum[1].owned       # the button now reads "Drop"
    # ⚠ Owned does NOT mean the orientation pick goes away — it means it offers the
    # regions still missing, beside the Add-version button (p.124, a flat point each).
    # This asserted the opposite until 2026-08-28, when the combo's disappearance was
    # the very bug: it made every version after the first unbuyable in this shell.
    # ⚠ isVisibleTo, not isVisible: the page is never shown in these tests,
    # so isVisible() is False for every widget on it regardless.
    assert page._orientation_btn.isVisibleTo(page)
    offered = {page._orientation_combo.itemText(i)
               for i in range(page._orientation_combo.count())}
    assert offered == {o.value for o in Orientation} - set(
        page._selected_thaum[1].orientations)
    page._toggle_thaum("formula", page._selected_thaum[1])
    assert not page._selected_thaum[1].owned   # unlearned


def test_charms_thaum_orientation_combo_for_first_buy(qtbot, ruleset):
    char = _learnable_char()
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    picker = build_thaum_picker(ruleset, char)
    formula = next(r for r in picker.formulas if r.available)
    page._selected_thaum = ("formula", formula)
    page._update_action()
    assert page._orientation_combo.isEnabled()      # a first purchase needs the region
    assert page._orientation_combo.count() == 5


def _own_a_ritual(ruleset, char, page):
    """Buy the first available ritual in its Realm version and select it."""
    row = next(r for r in build_thaum_picker(ruleset, char).rituals if r.available)
    page._selected_thaum = ("ritual", row)
    page._update_action()
    page._toggle_thaum("ritual", row)
    return page._selected_thaum[1]


def test_a_further_regional_version_can_be_bought(qtbot, ruleset):
    """p.124: each extra regional version is a flat point on top. The control for it
    did not exist in this shell — the combo vanished once the row was owned, and
    `add_thaum_orientation` had no Qt caller at all."""
    char = _learnable_char()
    char.abilities[AbilityName.OCCULT] = 5
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    owned = _own_a_ritual(ruleset, char, page)
    assert owned.orientations == [Orientation.REALM.value]
    page._orientation_combo.setCurrentIndex(
        [page._orientation_combo.itemText(i)
         for i in range(page._orientation_combo.count())].index(Orientation.NORTH.value))
    page._add_orientation()
    after = next(r for r in build_thaum_picker(ruleset, char).rituals
                 if r.key == owned.key)
    assert set(after.orientations) == {Orientation.REALM.value, Orientation.NORTH.value}


def test_the_detail_panel_names_the_versions_you_know(qtbot, ruleset):
    """⚠ The panel is rebuilt after a purchase, not only the button. It was written
    from the pre-purchase row, so the line moved only when you re-clicked the entry."""
    char = _learnable_char()
    char.abilities[AbilityName.OCCULT] = 5
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    _own_a_ritual(ruleset, char, page)
    assert f"Known in: {Orientation.REALM.value}" in page.detail.toPlainText()
    page._orientation_combo.setCurrentIndex(0)
    page._add_orientation()
    text = page.detail.toPlainText()
    assert "Known in:" in text and Orientation.REALM.value in text


def test_all_five_versions_leaves_nothing_to_add(qtbot, ruleset):
    """The negative control for the control above: with every region known there is
    no purchase left, so neither the combo nor the button may offer one."""
    char = _learnable_char()
    char.abilities[AbilityName.OCCULT] = 5
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    _own_a_ritual(ruleset, char, page)
    for _ in range(4):
        page._orientation_combo.setCurrentIndex(0)
        page._add_orientation()
    assert page._orientation_combo.count() == 0
    assert not page._orientation_btn.isVisibleTo(page)


def test_a_custom_ritual_can_be_written_for_this_character(qtbot, ruleset):
    """p.148: the chapter prints five rituals and expects more. The webapp has had
    this control since Thaumaturgy shipped; the port had no way to write one."""
    char = _learnable_char()
    char.abilities[AbilityName.OCCULT] = 3
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    page._add_custom_ritual("Whisper of the Salt Road", 2)
    entry = next((r for r in char.thaumaturgy.rituals if r.name == "Whisper of the Salt Road"),
                 None)
    assert entry is not None and entry.level == 2
    assert entry.ritual_id == ""          # inline on the character, not a library id
    rows = build_thaum_picker(ruleset, char).rituals
    written = next(r for r in rows if r.name == "Whisper of the Salt Road")
    assert written.owned and written.custom


def test_the_rituals_tab_carries_the_authoring_row(qtbot, ruleset):
    """⚠ Drives the real WIDGETS, by name. `_add_custom_ritual` being right proves
    nothing about whether anything on screen calls it — the control is the half that
    was missing, not the engine call."""
    char = _learnable_char()
    char.abilities[AbilityName.OCCULT] = 3
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    name = page.findChild(QLineEdit, "thaum.custom_ritual.name")
    level = page.findChild(QSpinBox, "thaum.custom_ritual.level")
    add = page.findChild(QPushButton, "thaum.custom_ritual.add")
    assert name is not None and level is not None and add is not None
    name.setText("Rite of the Quiet Hour")
    level.setValue(3)
    add.click()
    assert any(r.name == "Rite of the Quiet Hour" for r in char.thaumaturgy.rituals)
    assert name.text() == ""              # cleared, so a second click is not a repeat


def test_writing_a_ritual_the_character_cannot_learn_is_refused(qtbot, ruleset):
    """The Occult gate is the engine's (p.148) and must reach this control — a level
    the character cannot buy is refused, not silently written onto the sheet."""
    said = []
    char = _learnable_char()
    char.abilities[AbilityName.OCCULT] = 1
    page = CharmsPage(ruleset, {"char": char},
                      notify=lambda text, kind="info": said.append((kind, text)))
    qtbot.addWidget(page)
    page._add_custom_ritual("Too Ambitious", 5)
    # ⚠ `thaumaturgy` stays None when nothing was bought — the state is created on the
    # first purchase, so "no state at all" is itself the assertion that none happened.
    assert char.thaumaturgy is None or not any(
        r.name == "Too Ambitious" for r in char.thaumaturgy.rituals)
    assert said and said[-1][0] == "warning"


def test_charms_remove_in_chargen(qtbot, ruleset):
    char = _learnable_char()
    avail = _first_available(ruleset, char)
    char.charms.append(avail[0])
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    page._toggle_charm(avail[0])
    assert avail[0] not in char.charms


def test_wheel_zoom_scales(qtbot, ruleset):
    char = Character(id="char.new")
    page = CharmsPage(ruleset, {"char": char})
    qtbot.addWidget(page)
    view = page._tree_views["abilities"]
    before = view.transform().m11()
    event = QWheelEvent(QPoint(50, 50), QPoint(50, 50), QPoint(0, 0),
                        QPoint(0, 120), Qt.MouseButton.NoButton,
                        Qt.KeyboardModifier.NoModifier,
                        Qt.ScrollPhase.NoScrollPhase, False)
    view.wheelEvent(event)
    assert view.transform().m11() != before


# ------------------------------------------------------------------ #
# the splat-specific picker extras
# ------------------------------------------------------------------ #

def test_lunar_gets_form_library_and_solar_does_not(ruleset, qtbot):
    lunar = CharmsPage(ruleset, {"char": Character(
        id="c.lunar", exalt_type="Lunar", caste="full-moon")},
        notify=lambda *a, **k: None)
    qtbot.addWidget(lunar)
    solar = CharmsPage(ruleset, {"char": Character(id="c.solar", exalt_type="Solar")},
                       notify=lambda *a, **k: None)
    qtbot.addWidget(solar)
    assert "Form Library" in _visible_tabs(lunar)
    assert "Form Library" not in _visible_tabs(solar)


def test_form_library_totem_and_rows_edit_through(ruleset, qtbot):
    char = Character(id="c.lunar", exalt_type="Lunar", caste="full-moon")
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    page._add_form()
    page._totem_field.setText("Wolf")
    idx = next(i for i in range(page.tabs.count())
               if page.tabs.tabText(i) == "Form Library")
    by_placeholder = {e.placeholderText(): e
                      for e in page.tabs.widget(idx).findChildren(QLineEdit)}
    by_placeholder["Animal"].setText("Dire Wolf")
    by_placeholder["Notes"].setText("Totem form")
    assert char.totem == "Wolf"
    assert char.animal_forms[0].name == "Dire Wolf"
    assert char.animal_forms[0].notes == "Totem form"


def test_form_library_add_and_remove_forms(ruleset, qtbot):
    char = Character(id="c.lunar", exalt_type="Lunar", caste="full-moon")
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    page._add_form()
    char.animal_forms[0].name = "Wolf"
    page._add_form()
    assert len(char.animal_forms) == 2
    page._remove_form(0)
    assert [f.name for f in char.animal_forms] == [""]


_VAT_CHARM = "alchemical.close-combat.tactical-analysis-engrams"


def _vat_page(ruleset, char, qtbot):
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    return page


def test_alchemical_gets_vat_refit_and_solar_does_not(ruleset, qtbot):
    alch = _vat_page(ruleset, Character(
        id="c.alch", exalt_type="Alchemical", caste="orichalcum"), qtbot)
    solar = _vat_page(ruleset, Character(id="c.solar", exalt_type="Solar"), qtbot)
    assert "Vat Refit" in _visible_tabs(alch)
    assert "Vat Refit" not in _visible_tabs(solar)


def test_vat_refit_install_moves_panoply_to_charms(ruleset, qtbot):
    char = Character(id="c.alch", exalt_type="Alchemical", caste="orichalcum")
    char.retainer_charms.append(_VAT_CHARM)
    page = _vat_page(ruleset, char, qtbot)
    page._do_install(_VAT_CHARM)
    assert _VAT_CHARM in char.charms
    assert _VAT_CHARM not in char.retainer_charms


def test_vat_refit_uninstall_moves_charms_to_panoply(ruleset, qtbot):
    char = Character(id="c.alch", exalt_type="Alchemical", caste="orichalcum")
    char.charms.append(_VAT_CHARM)
    page = _vat_page(ruleset, char, qtbot)
    page._do_uninstall(_VAT_CHARM)
    assert _VAT_CHARM not in char.charms
    assert _VAT_CHARM in char.retainer_charms


def test_vat_refit_blocked_install_button_is_disabled(ruleset, qtbot):
    char = Character(id="c.alch", exalt_type="Alchemical", caste="orichalcum")
    char.retainer_charms.append(_VAT_CHARM)
    char.general_charm_slots = 0
    char.dedicated_charm_slots = 1     # only Dedicated free; the Charm is not CF
    page = _vat_page(ruleset, char, qtbot)
    assert refit.install_block_reason(ruleset, char, _VAT_CHARM)
    idx = next(i for i in range(page.tabs.count())
               if page.tabs.tabText(i) == "Vat Refit")
    install_btns = [b for b in page.tabs.widget(idx).findChildren(QPushButton)
                    if b.text() == "Install"]
    assert install_btns
    assert not install_btns[0].isEnabled()
    assert install_btns[0].toolTip()


def _elemental_char():
    return Character(id="gb", exalt_type="God-Blooded", caste="god-blooded",
                     origin="Elemental")


def test_elemental_origin_godblooded_gets_the_tab(ruleset, qtbot):
    elemental = CharmsPage(ruleset, {"char": _elemental_char()},
                           notify=lambda *a, **k: None)
    qtbot.addWidget(elemental)
    divine = CharmsPage(ruleset, {"char": Character(
        id="gb2", exalt_type="God-Blooded", caste="god-blooded", origin="Divine")},
        notify=lambda *a, **k: None)
    qtbot.addWidget(divine)
    assert "Elemental Powers" in _visible_tabs(elemental)
    assert "Elemental Powers" not in _visible_tabs(divine)


def test_elemental_powers_listed_but_locked_without_merit(ruleset, qtbot):
    page = CharmsPage(ruleset, {"char": _elemental_char()},
                      notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    assert page._elemental_list.count() == 9
    page._elemental_list.setCurrentRow(0)
    row = page._elemental_list.item(0).data(Qt.UserRole)
    assert page._selected_elemental == row.id
    assert not row.available
    assert not page.action_btn.isEnabled()
    assert row.reason in page.detail.toPlainText()


def test_elemental_powers_learn_and_drop_in_chargen(ruleset, qtbot):
    char = _elemental_char()
    char.merits_flaws.append(MeritFlawPurchase(merit_id="mf.elemental-dominion"))
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    page._toggle_elemental("elemental.aegis")
    assert "elemental.aegis" in char.elemental_powers
    page._toggle_elemental("elemental.aegis")
    assert "elemental.aegis" not in char.elemental_powers


def test_elemental_powers_buy_post_lock_spends_xp_and_locks_button(ruleset, qtbot):
    char = _elemental_char()
    char.merits_flaws.append(MeritFlawPurchase(merit_id="mf.elemental-dominion"))
    advancement.add_xp(char, 100)
    lifecycle.lock_chargen(char, ruleset)
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    available_before = advancement.xp_available(char)
    page._toggle_elemental("elemental.aegis")
    assert "elemental.aegis" in char.elemental_powers
    assert advancement.xp_available(char) == available_before - 14
    # owned post-lock: the button is disabled and points at the Edit tab's undo
    lst = page._elemental_list
    for i in range(lst.count()):
        if lst.item(i).data(Qt.UserRole).id == "elemental.aegis":
            lst.setCurrentRow(i)
            break
    assert not page.action_btn.isEnabled()
    assert "known" in page.action_btn.text().lower()


def test_dragonkings_get_paths_tab_and_solar_does_not(ruleset, qtbot):
    dk = CharmsPage(ruleset, {"char": Character(
        id="dk", exalt_type="Dragon-Kings", caste="pterok")},
        notify=lambda *a, **k: None)
    qtbot.addWidget(dk)
    solar = CharmsPage(ruleset, {"char": Character(id="s", exalt_type="Solar")},
                       notify=lambda *a, **k: None)
    qtbot.addWidget(solar)
    assert "Paths" in _visible_tabs(dk)
    assert "Paths" not in _visible_tabs(solar)


def test_paths_pre_lock_dot_track_writes_paths(ruleset, qtbot):
    char = Character(id="dk", exalt_type="Dragon-Kings", caste="pterok")
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    track = _select_path(page, "dk.solid-earth")
    # A chargen Path rating is a free setter — the dot track writes character.paths.
    track._pips[2].clicked.emit(2)
    assert any(p.path_id == "dk.solid-earth" and p.rating == 2 for p in char.paths)
    # Clicking the current top pip steps it back down; from 1 a further click removes
    # the Path entirely (rating 0).
    track._pips[0].clicked.emit(1)
    track._pips[0].clicked.emit(1)
    assert not any(p.path_id == "dk.solid-earth" for p in char.paths)


def test_paths_favoured_renders_saved_breed_path(ruleset, qtbot):
    char = Character(id="dk", exalt_type="Dragon-Kings", caste="pterok")
    char.favored_path = "dk.celestial-air"     # a breed path — illegal-but-possible
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    assert page._fav_path_combo.currentData() == "dk.celestial-air"


def test_paths_favoured_pick_sets_favored_path(ruleset, qtbot):
    # ⚠ The handler used to read a shared loop variable instead of its own combo,
    # so any pick silently wrote '' (the same closure bug as the rating combos).
    char = Character(id="dk", exalt_type="Dragon-Kings", caste="pterok")
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    page._fav_path_combo.setCurrentIndex(page._fav_path_combo.findData("dk.solid-earth"))
    assert char.favored_path == "dk.solid-earth"
    # the rebuilt combo still shows the pick
    assert page._fav_path_combo.currentData() == "dk.solid-earth"


def test_paths_favoured_stale_id_does_not_crash(ruleset, qtbot):
    # A save from before a catalogue rename can carry a favoured_path id that is no
    # longer in ruleset.paths — the page must still build (trap #3's Qt form: never
    # index the catalogue with a saved id).
    char = Character(id="dk", exalt_type="Dragon-Kings", caste="pterok")
    char.favored_path = "dk.renamed-away"
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    assert page._fav_path_combo.currentData() == "dk.renamed-away"


def test_paths_post_lock_learn_spends_xp(ruleset, qtbot):
    char = Character(id="dk", exalt_type="Dragon-Kings", caste="pterok")
    advancement.add_xp(char, 100)
    lifecycle.lock_chargen(char, ruleset)
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    available_before = advancement.xp_available(char)
    _select_path(page, "dk.solid-earth")
    assert "XP" in page.action_btn.text()   # the Learn button carries the price
    page._path_act()
    assert any(p.path_id == "dk.solid-earth" and p.rating == 1 for p in char.paths)
    assert advancement.xp_available(char) < available_before


def test_paths_post_lock_essence_cap_refuses(ruleset, qtbot):
    char = Character(id="dk", exalt_type="Dragon-Kings", caste="pterok")
    char.paths.append(PathRating(path_id="dk.solid-earth", rating=3))
    advancement.add_xp(char, 100)
    lifecycle.lock_chargen(char, ruleset)
    messages = []
    page = CharmsPage(ruleset, {"char": char},
                      notify=lambda t, k="info": messages.append(t))
    qtbot.addWidget(page)
    _select_path(page, "dk.solid-earth")
    page._path_act()
    assert any(p.path_id == "dk.solid-earth" and p.rating == 3 for p in char.paths)
    assert messages


def test_paths_selection_fills_detail_and_hides_on_other_tabs(ruleset, qtbot):
    char = Character(id="dk", exalt_type="Dragon-Kings", caste="pterok")
    char.paths.append(PathRating(path_id="dk.solid-earth", rating=2))
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    track = _select_path(page, "dk.solid-earth")
    assert page._selected_path == "dk.solid-earth"
    assert not page._path_box.isHidden()       # the rating row is up
    assert "Solid Earth" in page.detail.toPlainText()
    assert track is not None
    # Leaving the Paths tab hides the rating row and drops the selection.
    page.tabs.setCurrentIndex(0)
    assert page._path_box.isHidden()
    assert page._selected_path is None


# ---- Augmentation templates (Alchemical) ---------------------------------- #

def test_alchemical_gets_augmentations_tab(ruleset, qtbot):
    page = CharmsPage(ruleset, {"char": Character(id="a", exalt_type="Alchemical")},
                      notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    assert "Augmentations" in _visible_tabs(page)
    # two type cards, each with a Pick Attributes button and a title
    aug_page = page.tabs.widget(_visible_tabs(page).index("Augmentations"))
    buttons = [b.text() for b in aug_page.findChildren(QPushButton)]
    assert buttons.count("Pick Attributes") == 2
    titles = [lbl.text() for lbl in aug_page.findChildren(QLabel)]
    assert "Transitory Augmentation" in titles
    assert "Sustained Augmentation" in titles


def test_augmentation_templates_collapse_into_two_tree_nodes(ruleset, qtbot):
    # The 18 '<Type> Augmentation of <Attribute>' templates render as ONE node per
    # type (Transitory / Sustained) in every tree — including 'general' itself —
    # not as eighteen disconnected nodes.
    char = Character(id="a", exalt_type="Alchemical")
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    view = page._tree_views["abilities"]
    cats = [view.category_combo.itemData(j) for j in range(view.category_combo.count())]
    assert "general" in cats
    for j in range(view.category_combo.count()):
        view.category_combo.setCurrentIndex(j)
        qtbot.wait(5)
        labels = [n.label for n in view.graph.nodes]
        # no raw '<Type> Augmentation of <Attribute>' variants leak anywhere...
        assert all("Augmentation of" not in l for l in labels)
        # ...and any summary nodes present are exactly the two types
        summaries = {l for l in labels
                     if l in ("Transitory Augmentation", "Sustained Augmentation")}
        assert summaries <= {"Transitory Augmentation", "Sustained Augmentation"}
    # a tree whose Charms NAME a template as a prerequisite shows BOTH summary nodes
    view.category_combo.setCurrentIndex(view.category_combo.findData("close_combat"))
    qtbot.wait(5)
    labels = [n.label for n in view.graph.nodes]
    assert {"Transitory Augmentation", "Sustained Augmentation"} <= set(labels)
    # 'general' itself renders as exactly the two summary nodes
    view.category_combo.setCurrentIndex(view.category_combo.findData("general"))
    qtbot.wait(5)
    assert {n.label for n in view.graph.nodes} == \
        {"Transitory Augmentation", "Sustained Augmentation"}


def test_augment_toggle_installs_and_removes(ruleset, qtbot):
    char = Character(id="a", exalt_type="Alchemical")
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    aug_id = next(cid for cid in ruleset.charms
                  if cid.startswith("alchemical.general."))
    cb = QCheckBox("Strength")
    cb.toggled.connect(lambda checked, cid=aug_id, c=cb: page._toggle_augment(cid, c))
    cb.setChecked(True)
    assert aug_id in char.charms
    cb.setChecked(False)
    assert aug_id not in char.charms


# ---- Elemental Powers pre-lock price ------------------------------------- #

def test_elemental_pre_lock_button_shows_bp_price(ruleset, qtbot):
    # A chargen Elemental Power costs bonus points (PG p.68) — the Learn button
    # carries the BP price on the chargen side, the way Thaumaturgy rows do.
    page = CharmsPage(ruleset, {"char": _elemental_char()},
                      notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    page._elemental_list.setCurrentRow(0)
    assert "BP" in page.action_btn.text()


# ---- Form Library Add button anchoring ------------------------------------ #

def test_form_library_add_button_is_pinned_below_the_list(ruleset, qtbot):
    # The "+ Add form" button lives in the page layout (pinned at the bottom), NOT
    # inside the scrolling forms list — adding forms must never move it.
    page = CharmsPage(ruleset, {"char": Character(id="l", exalt_type="Lunar")},
                      notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    form_page = page.tabs.widget(_visible_tabs(page).index("Form Library"))
    add = next(b for b in form_page.findChildren(QPushButton) if b.text() == "+ Add form")
    assert add.parentWidget() is form_page


# ---- Round two: augmentation in other trees, readouts, BP past the pool ------ #

def test_augmentation_summary_node_selects_and_offers_pick(ruleset, qtbot):
    # Selecting a collapsed 'Transitory Augmentation' node shows the type's detail
    # and a Pick Attributes action (a Charm detail would not exist for the summary).
    char = Character(id="a", exalt_type="Alchemical")
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    view = page._tree_views["abilities"]
    view.category_combo.setCurrentIndex(view.category_combo.findData("general"))
    qtbot.wait(5)
    node_item = next(i for i in view.scene().items()
                     if isinstance(i, NodeItem) and i.node.id.startswith("augment:"))
    node_item.setSelected(True)
    qtbot.wait(5)
    assert page._selected_augment == "Transitory Augmentation"
    assert page._selected_node is None
    assert "Installed:" in page.detail.toPlainText()
    assert page.action_btn.text() == "Pick Attributes"


def test_alchemical_slots_readout_tracks_live_load(ruleset, qtbot):
    # The Slots readout is the LIVE load, not the frozen chargen snapshot — buying a
    # Charm moves it.
    char = Character(id="a", exalt_type="Alchemical")
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    page._update_readout()
    before = page.readout.text()
    assert "Slots:" in before
    cid = next(c.id for c in ruleset.charms.values()
               if c.exalt_type == "Alchemical"
               and validate.charm_occupies_slot(ruleset, char, c))
    char.charms.append(cid)
    page._update_readout()
    assert page.readout.text() != before


def test_dragonking_readout_shows_path_dots_not_charms(ruleset, qtbot):
    char = Character(id="dk", exalt_type="Dragon-Kings", caste="pterok")
    char.paths.append(PathRating(path_id="dk.solid-earth", rating=2))
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    assert "Path dots: 2" in page.readout.text()
    assert "Charms:" not in page.readout.text()


def test_chargen_pick_bp_zero_until_pool_full(ruleset, qtbot):
    char = Character(id="s", exalt_type="Solar")
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    melee = [c.id for c in ruleset.charms.values()
             if c.category == "melee" and c.exalt_type == "Solar"]
    assert page._chargen_pick_bp(charm_id=melee[0]) == 0      # pool has room
    for cid in melee[:10]:
        char.charms.append(cid)
    # a candidate NOT already held — the 12th melee Charm
    assert page._chargen_pick_bp(charm_id=melee[11]) > 0       # pool full


def test_chargen_learn_button_shows_bp_when_pool_full(ruleset, qtbot):
    melee = [c.id for c in ruleset.charms.values()
             if c.category == "melee" and c.exalt_type == "Solar"]
    full = Character(id="s", exalt_type="Solar")
    for cid in melee[:10]:
        full.charms.append(cid)
    page = CharmsPage(ruleset, {"char": full}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    page._selected_node = melee[10]
    page._update_action()
    assert "BP" in page.action_btn.text()
    empty = Character(id="s2", exalt_type="Solar")
    page2 = CharmsPage(ruleset, {"char": empty}, notify=lambda *a, **k: None)
    qtbot.addWidget(page2)
    page2._selected_node = melee[0]
    page2._update_action()
    assert "BP" not in page2.action_btn.text()


# --------------------------------------------------------------------------- #
# The per-build memo (charms.py `_cached`)
# --------------------------------------------------------------------------- #

def test_the_build_cache_does_not_change_which_trees_are_found(ruleset):
    """`trees_for` memoizes three whole-catalogue scans across one rebuild. The memo is
    an optimisation ONLY: passing a cache must produce exactly the uncached answer, for
    a splat with an augmentation category (Alchemical) and one without."""
    for exalt_type, caste in (("Alchemical", "orichalcum"), ("Solar", "dawn"),
                              ("Ghost", "")):
        char = Character(id="c.cache", exalt_type=exalt_type, caste=caste,
                         essence_rating=3)
        for group in ("abilities", "styles", "arcanoi"):
            shared: dict = {}
            assert (trees_for(ruleset, char, exalt_type, group, shared)
                    == trees_for(ruleset, char, exalt_type, group)), (exalt_type, group)


def test_the_build_cache_scans_for_the_augmentation_category_once(ruleset):
    """⚠ The regression this guards is a PERFORMANCE one, so it pins the MECHANISM
    rather than a timing or a ratio: `augmentation_category` scans the whole Charm
    catalogue through `charm_matches_splat`, and uncached it ran once per collapsed
    tree — ~190,000 calls and a visible pause on the tab (human, 2026-08-21). With a
    shared cache it must run exactly once no matter how many groups are asked for."""
    import exalted_builder.qt.charms as charmsmod

    char = Character(id="c.cache", exalt_type="Alchemical", caste="orichalcum",
                     essence_rating=3)
    calls = []
    real = charmsmod.augmentation_category

    def counted(rs, ch):
        calls.append(1)
        return real(rs, ch)

    charmsmod.augmentation_category = counted
    try:
        shared: dict = {}
        for group in ("abilities", "styles", "arcanoi"):
            charmsmod.trees_for(ruleset, char, "Alchemical", group, shared)
        assert len(calls) == 1, f"scanned {len(calls)} times with a shared cache"

        calls.clear()
        for group in ("abilities", "styles", "arcanoi"):
            charmsmod.trees_for(ruleset, char, "Alchemical", group)
        # The negative control: uncached it is scanned once per COLLAPSED TREE. The
        # exact number is a property of the data, so assert only that it is more than
        # one — that is the whole difference, and it will not rot when a Charm is
        # added.
        assert len(calls) > 1
    finally:
        charmsmod.augmentation_category = real


# ---- Variant-menu packages (Ox-Body, Deadly Beastman Gifts) ---------------- #
# ⚠ The dialog is reached through `_build_package_dialog`, which returns one WITHOUT
# running it — `exec()` would block a headless run. Same seam as Gear/Advantages.

def _ox_char():
    char = Character(id="c.ox")
    char.abilities[AbilityName.ENDURANCE] = 3
    return char


def _gift_char():
    char = Character(id="c.lunar", exalt_type="Lunar", caste="full-moon")
    char.essence_rating = 3
    return char


def _select_charm_node(page, qtbot, charm_id, category):
    """Select one Charm's node in the abilities tree, the way a click does."""
    view = page._tree_views["abilities"]
    view.category_combo.setCurrentIndex(view.category_combo.findData(category))
    qtbot.wait(5)
    node_item = next(i for i in view.scene().items()
                     if isinstance(i, NodeItem) and i.node.id == charm_id)
    node_item.setSelected(True)
    qtbot.wait(5)


def test_ox_body_node_offers_the_chooser_not_learn(ruleset, qtbot):
    # Ox-Body is bought as a PACKAGE into character.ox_body — an ordinary Learn would
    # be refused by charm_actions, so the button must open the chooser instead.
    char = _ox_char()
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    _select_charm_node(page, qtbot, validate.ox_body_charm_id(ruleset, char),
                       "endurance")
    assert page.action_btn.text() == "Choose a package…"
    assert "Bought: 0 / 3" in page.detail.toPlainText()


def test_ox_body_dialog_buys_one_package(ruleset, qtbot):
    char = _ox_char()
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    oid = validate.ox_body_charm_id(ruleset, char)
    dialog = page._build_package_dialog(oid)
    qtbot.addWidget(dialog)
    assert not dialog.confirm.isEnabled()          # nothing picked yet
    key = next(iter(dialog.checks))
    dialog.checks[key].setChecked(True)
    assert dialog.confirm.isEnabled()
    dialog.confirm.click()
    assert [p.variant for p in char.ox_body] == [key]
    assert oid not in char.charms                  # never the ordinary Charm list


def test_a_one_pick_menu_replaces_rather_than_blocking(ruleset, qtbot):
    # Ox-Body picks exactly one variant, so its rows read as radio buttons: choosing
    # a second replaces the first instead of greying every other row out.
    char = _ox_char()
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    dialog = page._build_package_dialog(validate.ox_body_charm_id(ruleset, char))
    qtbot.addWidget(dialog)
    first, second = list(dialog.checks)[:2]
    dialog.checks[first].setChecked(True)
    assert dialog.checks[second].isEnabled()
    dialog.checks[second].setChecked(True)
    assert dialog.selection == [second]
    assert dialog.confirm.isEnabled()


def test_ox_body_dialog_removes_a_chargen_package(ruleset, qtbot):
    char = _ox_char()
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    oid = validate.ox_body_charm_id(ruleset, char)
    dialog = page._build_package_dialog(oid)
    qtbot.addWidget(dialog)
    dialog.checks[next(iter(dialog.checks))].setChecked(True)
    dialog.confirm.click()
    assert len(char.ox_body) == 1
    fresh = page._build_package_dialog(oid)
    qtbot.addWidget(fresh)
    remove = next(b for b in fresh.findChildren(QPushButton) if b.text() == "Remove")
    remove.click()
    assert char.ox_body == []


def test_a_locked_package_dialog_prices_in_xp_and_offers_no_remove(ruleset, qtbot):
    char = _ox_char()
    char.essence_rating = 2
    lifecycle.lock_chargen(char, ruleset)
    char.xp_earned = 50
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    dialog = page._build_package_dialog(validate.ox_body_charm_id(ruleset, char))
    qtbot.addWidget(dialog)
    assert "XP" in dialog.confirm.text()
    assert not [b for b in dialog.findChildren(QPushButton) if b.text() == "Remove"]


def test_gift_dialog_needs_two_and_honours_the_chain(ruleset, qtbot):
    char = _gift_char()
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    dialog = page._build_package_dialog(validate.gift_charm_id(ruleset, char))
    qtbot.addWidget(dialog)
    # A Gift behind a prerequisite starts disabled, and the prerequisite picked in
    # the SAME purchase unlocks it (p.124).
    assert not dialog.checks["spider-foot-climbing"].isEnabled()
    dialog.checks["bestial-reflexes"].setChecked(True)
    assert dialog.checks["spider-foot-climbing"].isEnabled()
    assert not dialog.confirm.isEnabled()          # 1 of 2 picked
    dialog.checks["spider-foot-climbing"].setChecked(True)
    assert dialog.confirm.isEnabled()
    dialog.confirm.click()
    assert [p.gifts for p in char.beastman_gifts] == \
        [["bestial-reflexes", "spider-foot-climbing"]]


def test_unchecking_a_gift_prunes_what_depended_on_it(ruleset, qtbot):
    char = _gift_char()
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    dialog = page._build_package_dialog(validate.gift_charm_id(ruleset, char))
    qtbot.addWidget(dialog)
    dialog.checks["bestial-reflexes"].setChecked(True)
    dialog.checks["spider-foot-climbing"].setChecked(True)
    dialog.checks["bestial-reflexes"].setChecked(False)
    assert dialog.selection == []                  # the dependant went with its root


def test_an_ordinary_charm_still_has_no_package_dialog(ruleset, qtbot):
    # The negative control: only the two package Charms get the chooser, and the
    # discriminator is the character's own package ids, not a name or a category.
    char = _ox_char()
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    ordinary = next(cid for cid in ruleset.charms if cid.startswith("solar.melee."))
    assert page._build_package_dialog(ordinary) is None


def test_picking_a_gift_does_not_rebuild_the_rows(ruleset, qtbot):
    # ⚠ The scroll bar jumped to the bottom on every click: rebuilding the rows under
    # the click deletes the focused checkbox, focus moves on, and a QScrollArea
    # scrolls to whatever has it. A pick changes no row's EXISTENCE, so it syncs in
    # place — the identity of the widgets is the thing being asserted.
    char = _gift_char()
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    dialog = page._build_package_dialog(validate.gift_charm_id(ruleset, char))
    qtbot.addWidget(dialog)
    before = dict(dialog.checks)
    dialog.checks["bestial-reflexes"].setChecked(True)
    assert dialog.checks == before                 # the same widget objects, updated
    assert dialog.checks["spider-foot-climbing"].isEnabled()


def test_charms_tab_tells_the_shell_its_budget_moved(ruleset, qtbot):
    # ⚠ Spending on the Charms tab moves the SHELL's readout bar (a Charm pick past
    # the free pool costs bonus points), and CharmsPage was the one page the shell
    # built without an on_change hook — so the bar sat stale until another tab was
    # touched. Every purchase path here funnels through _update_readout.
    char = _learnable_char()
    beats = []
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None,
                      on_change=lambda: beats.append(1))
    qtbot.addWidget(page)
    beats.clear()
    cid = next(c.id for c in ruleset.charms.values()
               if c.id.startswith("solar.melee.") and
               validate.meets_charm_requirements(ruleset, char, c))
    page._toggle_charm(cid)
    assert cid in char.charms
    assert beats                                    # the shell was told


def test_the_shell_wires_the_charms_tab_to_its_readout(ruleset, qtbot):
    # The other half of the same bug: the hook exists only if the shell passes it.
    from pathlib import Path

    from exalted_builder.qt.main_window import MainWindow
    win = MainWindow(ruleset, _learnable_char(), Path("unused.json"))
    qtbot.addWidget(win)
    assert win._pages["Charms"]._on_change == win._refresh


# --- the Splat dropdown (foreign Charms, core p.127) ------------------------- #
#
# The web picker has ONE shared Splat dropdown over a group toggle; the Qt tab set
# gives each tree tab its own, offering only the splats with trees in that group.


def _eclipse(**kw) -> Character:
    """An Eclipse with the generalist privilege actually open — the caste allows it
    (data-driven, `CasteDefinition.foreign_charms`) and the Storyteller has said yes,
    which is the pre-lock half of the rule."""
    from exalted_builder.models.character import HouseRules
    char = Character(id="x", exalt_type="Solar", caste="eclipse", essence_rating=5,
                     house_rules=HouseRules(st_foreign_charms=True), **kw)
    char.abilities = {a: 5 for a in AbilityName}
    return char


def _splat_row(page, tab_label):
    """The (combo, label) pair of one tree tab's Splat dropdown."""
    for i in range(page.tabs.count()):
        if page.tabs.tabText(i) == tab_label:
            view = page.tabs.widget(i).findChild(CharmTreeView)
            return view, view.splat_combo
    raise AssertionError(f"no {tab_label} tab")


def test_splat_dropdown_is_hidden_without_the_privilege(ruleset, qtbot):
    page = CharmsPage(ruleset, {"char": Character(id="c", exalt_type="Solar",
                                                  caste="dawn")})
    qtbot.addWidget(page)
    _, combo = _splat_row(page, "Charms")
    assert [combo.itemData(i) for i in range(combo.count())] == ["Solar"]
    # ⚠ `isHidden()`, not `isVisible()`: a widget whose parent was never shown reports
    # isVisible() False however it is configured, so the negative form passes vacuously
    # (test_qt_advantages.py:490 records the same trap).
    assert combo.isHidden()             # one entry is no choice at all


def test_eclipse_is_offered_other_splats(ruleset, qtbot):
    page = CharmsPage(ruleset, {"char": _eclipse()})
    qtbot.addWidget(page)
    _, combo = _splat_row(page, "Charms")
    offered = [combo.itemData(i) for i in range(combo.count())]
    assert offered[0] == "Solar"                    # the character's own, first
    assert "Dragon-Blooded" in offered
    assert offered[1:] == sorted(offered[1:])


def test_switching_splat_restocks_the_categories_and_the_tree(ruleset, qtbot):
    page = CharmsPage(ruleset, {"char": _eclipse()})
    qtbot.addWidget(page)
    view, combo = _splat_row(page, "Charms")
    native = [view.category_combo.itemData(i)
              for i in range(view.category_combo.count())]
    native_nodes = {n.id for n in view.graph.nodes}

    combo.setCurrentIndex([combo.itemData(i)
                           for i in range(combo.count())].index("Dragon-Blooded"))
    foreign_nodes = {n.id for n in view.graph.nodes}
    assert foreign_nodes and not (foreign_nodes & native_nodes)
    assert view.category_combo.count()              # landed on a real category
    assert all(n.startswith("dragonblooded.") for n in foreign_nodes)
    # Back again — the native page is unchanged, not a merged pile.
    combo.setCurrentIndex(0)
    assert [view.category_combo.itemData(i)
            for i in range(view.category_combo.count())] == native
    assert {n.id for n in view.graph.nodes} == native_nodes


def test_a_purchase_does_not_revert_a_foreign_tree_to_the_native_splat(ruleset, qtbot):
    """⚠ The house bug this port is prone to: the refresh-after-buy path had its own
    hardcoded `character.exalt_type`, so the tree silently snapped back to the native
    splat on the next click. Nothing else on screen showed it."""
    char = _eclipse(chargen_locked=False)
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    view, combo = _splat_row(page, "Charms")
    combo.setCurrentIndex([combo.itemData(i)
                           for i in range(combo.count())].index("Dragon-Blooded"))
    before = {n.id for n in view.graph.nodes}
    cid = next(n.id for n in view.graph.nodes if n.state == "available")

    page._toggle_charm(cid)
    assert cid in char.charms
    assert {n.id for n in view.graph.nodes} == before      # still the foreign page


# --- the detail card's five flag lines --------------------------------------- #
#
# ⚠ These were absent from the Qt detail panel for six shipped milestones: it rendered
# the stat block and nothing else. Four of the five change what the Charm COSTS.


def _flags(page, detail):
    return page._charm_flags_html(detail)


def test_no_flags_renders_nothing(ruleset, qtbot):
    """Nothing is rendered as nothing, never as an empty box."""
    char = _learnable_char()
    page = CharmsPage(ruleset, {"char": char})
    qtbot.addWidget(page)
    plain = build_charm_detail(ruleset, char, _first_available(ruleset, char)[0])
    assert _flags(page, plain) == ""


def test_a_foreign_charm_says_it_costs_double(ruleset, qtbot):
    char = _eclipse()
    page = CharmsPage(ruleset, {"char": char})
    qtbot.addWidget(page)
    view, combo = _splat_row(page, "Charms")
    combo.setCurrentIndex([combo.itemData(i)
                           for i in range(combo.count())].index("Dragon-Blooded"))
    detail = build_charm_detail(ruleset, char, view.graph.nodes[0].id)
    out = _flags(page, detail)
    assert "Dragon-Blooded Charm" in out and "double" in out and "p.127" in out


def test_a_calling_charm_is_marked_discounted(ruleset, qtbot):
    char = Character(id="c", exalt_type="Solar", caste="dawn", origin="illuminated",
                     camp="kether-rock", calling="deacon")
    calling = validate.calling_charm_ids(ruleset, char)
    if not calling:
        pytest.skip("no Calling in this ruleset discounts any Charm")
    page = CharmsPage(ruleset, {"char": char})
    qtbot.addWidget(page)
    detail = build_charm_detail(ruleset, char, sorted(calling)[0])
    assert "Calling Charm" in _flags(page, detail)


def test_a_camp_granted_charm_says_it_cost_no_pick(ruleset, qtbot):
    char = _learnable_char()
    cid = _first_available(ruleset, char)[0]
    char.granted_charms = [cid]
    page = CharmsPage(ruleset, {"char": char})
    qtbot.addWidget(page)
    out = _flags(page, build_charm_detail(ruleset, char, cid))
    assert "training camp" in out and "no Charm pick" in out


def test_an_immaculate_charm_is_named_as_one(ruleset, qtbot):
    cid = next((c.id for c in ruleset.charms.values()
                if validate.is_immaculate_charm(c)), None)
    if cid is None:
        pytest.skip("no Immaculate Charm in this ruleset")
    char = Character(id="c", exalt_type="Dragon-Blooded")
    page = CharmsPage(ruleset, {"char": char})
    qtbot.addWidget(page)
    detail = build_charm_detail(ruleset, char, cid)
    assert "Immaculate Order Charm" in _flags(page, detail)


def test_a_homebrew_charm_is_marked_as_unbacked(ruleset, qtbot):
    cid = next((c.id for c in ruleset.charms.values() if getattr(c, "custom", False)),
               None)
    if cid is None:
        # ⚠ Negative control rebuilt on a synthetic subject rather than deleted: the
        # shipped catalogue holds no homebrew, so there is no real Charm to assert on.
        page = CharmsPage(ruleset, {"char": _learnable_char()})
        qtbot.addWidget(page)
        fake = SimpleNamespace(id="custom.x", custom=True, foreign_splat="")
        assert "homebrew" in _flags(page, fake)
        return
    page = CharmsPage(ruleset, {"char": _learnable_char()})
    qtbot.addWidget(page)
    assert "homebrew" in _flags(page, build_charm_detail(ruleset, _learnable_char(), cid))


# --- "Add another" for generic repeatable Charms ----------------------------- #
#
# Owned-but-under-cap is the one state the single action button cannot express: it
# reads "Remove", and a repeatable Charm wants one MORE copy.

# ⚠ A GENERIC repeatable — no variants, so N copies live as duplicate ids in
# `character.charms`. Not Environmental Hazard-Resisting Meditation, which looks
# repeatable but carries four versions and is therefore a variant MENU: it is bought
# as a package into `character.variant_purchases` and never toggled.
REPEATABLE = "mountainfolk.foundation.essence-satiation-method"


def _repeatable_char():
    """A Jadeborn who can learn REPEATABLE. Its cap trait is Essence and it also
    carries the printed flat ceiling of three (CH6 pp.245-246), so with Essence 3 the
    two agree and the copy cap is 3."""
    return Character(id="c", exalt_type="Mountain-Folk", caste="jade",
                     essence_rating=3)


def _select(page, charm_id):
    """Select one node in the current tab's scene, as a click would.

    ⚠ Clears first: a QGraphicsScene selection is not exclusive, so setSelected(True)
    on a second node leaves BOTH selected and `_tree_detail` keeps reading the first —
    a test that moved the selection would go on asserting about the old node."""
    view = page.tabs.currentWidget().findChild(CharmTreeView)
    view.scene().clearSelection()
    for item in view.scene().items():
        if isinstance(item, NodeItem) and item.node.id == charm_id:
            item.setSelected(True)
            return item
    raise AssertionError(f"{charm_id} is not on the current tree")


def _show_repeatable(ruleset, page, charm_id):
    """Open the tab and category holding `charm_id`, then select it."""
    category = ruleset.charms[charm_id].category
    for i in range(page.tabs.count()):
        view = page.tabs.widget(i).findChild(CharmTreeView)
        if view is None or view.category_combo is None:
            continue
        for row in range(view.category_combo.count()):
            if view.category_combo.itemData(row) == category:
                page.tabs.setCurrentIndex(i)
                view.category_combo.setCurrentIndex(row)
                return _select(page, charm_id)
    raise AssertionError(f"no tab offers {category}")


def test_add_another_is_hidden_until_the_charm_is_owned(ruleset, qtbot):
    char = _repeatable_char()
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    _show_repeatable(ruleset, page, REPEATABLE)
    assert page.again_btn.isHidden()               # unowned: Learn, not Add another
    page._toggle_charm(REPEATABLE)
    _select(page, REPEATABLE)
    assert not page.again_btn.isHidden()


def test_add_another_appends_a_copy_rather_than_removing(ruleset, qtbot):
    """⚠ The whole point: `toggle_charm` on an owned Charm REMOVES it. A second copy
    has to call the learn half directly."""
    char = _repeatable_char()
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    _show_repeatable(ruleset, page, REPEATABLE)
    page._toggle_charm(REPEATABLE)
    assert char.charms.count(REPEATABLE) == 1
    _select(page, REPEATABLE)
    page._add_another()
    assert char.charms.count(REPEATABLE) == 2
    # The selection survives the rebuild, so a third copy is one click, not three.
    assert page._selected_node == REPEATABLE
    assert not page.again_btn.isHidden()


def test_add_another_disappears_at_the_cap(ruleset, qtbot):
    char = _repeatable_char()
    cap = validate._repeatable_purchase_cap(ruleset.charms[REPEATABLE], char)
    assert cap == 3                                  # the printed flat ceiling
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    _show_repeatable(ruleset, page, REPEATABLE)
    page._toggle_charm(REPEATABLE)
    for _ in range(cap - 1):
        _select(page, REPEATABLE)
        page._add_another()
    assert char.charms.count(REPEATABLE) == cap
    _select(page, REPEATABLE)
    assert page.again_btn.isHidden()


def test_add_another_is_offered_post_lock_with_its_xp_price(ruleset, qtbot):
    """⚠ This used to be refused. `charm_actions.learn_charm`'s post-lock guard was a
    bare `charm_id in character.charms` with no cap in it, so it caught repeatables in
    a net meant for ordinary Charms — and made `advancement.learn_charm`'s deliberate,
    page-cited support for exactly this purchase (CH6 pp.245-246) unreachable from
    either shell."""
    from exalted_builder.engine import costs
    char = _repeatable_char()
    char.charms = [REPEATABLE]
    char.chargen_locked = True
    char.xp_earned = 100
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    _show_repeatable(ruleset, page, REPEATABLE)
    _select(page, REPEATABLE)
    assert not page.again_btn.isHidden()
    price = costs.charm_cost(ruleset, char, ruleset.charms[REPEATABLE])
    assert f"{price} XP" in page.again_btn.text()

    spent = advancement.xp_spent(char)
    page._add_another()
    assert char.charms.count(REPEATABLE) == 2
    assert advancement.xp_spent(char) - spent == price      # and it was charged


def test_a_non_repeatable_charm_still_cannot_be_bought_twice(ruleset, qtbot):
    """The negative control for the guard that was loosened: an ordinary Charm has no
    cap, and re-learning it post-lock must still be refused."""
    char = _learnable_char()
    cid = _first_available(ruleset, char)[0]
    assert validate._repeatable_purchase_cap(ruleset.charms[cid], char) == 0
    char.charms = [cid]
    char.chargen_locked = True
    char.xp_earned = 100
    with pytest.raises(advancement.AdvancementError):
        charm_actions.learn_charm(ruleset, char, cid)
    assert char.charms.count(cid) == 1


def test_the_cap_still_binds_post_lock(ruleset, qtbot):
    char = _repeatable_char()
    cap = validate._repeatable_purchase_cap(ruleset.charms[REPEATABLE], char)
    char.charms = [REPEATABLE] * cap
    char.chargen_locked = True
    char.xp_earned = 500
    with pytest.raises(advancement.AdvancementError):
        charm_actions.learn_charm(ruleset, char, REPEATABLE)
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    _show_repeatable(ruleset, page, REPEATABLE)
    _select(page, REPEATABLE)
    assert page.again_btn.isHidden()


def test_add_another_hides_when_the_selection_moves_on(ruleset, qtbot):
    """⚠ The button is hidden at the TOP of _update_action, not per branch: a dozen
    early returns would each have to remember, and one that forgot would offer
    "Add another" against somebody else's Charm."""
    char = _repeatable_char()
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    _show_repeatable(ruleset, page, REPEATABLE)
    page._toggle_charm(REPEATABLE)
    _select(page, REPEATABLE)
    assert not page.again_btn.isHidden()
    other = next(n.id for n in
                 page.tabs.currentWidget().findChild(CharmTreeView).graph.nodes
                 if n.id != REPEATABLE)
    _select(page, other)
    assert page.again_btn.isHidden()


# --- the martial-arts style panel -------------------------------------------- #


def _styles_view(page):
    for i in range(page.tabs.count()):
        if page.tabs.tabText(i) == "Martial Arts":
            page.tabs.setCurrentIndex(i)
            return page.tabs.widget(i).findChild(CharmTreeView)
    raise AssertionError("no Martial Arts tab")


def _pick_category(view, key):
    for row in range(view.category_combo.count()):
        if view.category_combo.itemData(row) == key:
            view.category_combo.setCurrentIndex(row)
            return True
    return False


def test_a_style_tree_shows_its_style_text(ruleset, qtbot):
    page = CharmsPage(ruleset, {"char": _learnable_char()})
    qtbot.addWidget(page)
    view = _styles_view(page)
    key = view.category_combo.currentData()
    style = viewmod.style_for_category(ruleset, key)
    assert style is not None, f"{key} was expected to be an authored style"
    assert not view.style_head.isHidden()
    assert style.name in view.style_head.text()
    # Collapsed by default — the canvas is what the tab is for.
    assert view.style_body.isHidden()
    view.style_head.setChecked(True)
    assert not view.style_body.isHidden()
    if style.preamble:
        assert style.preamble.split("\n")[0][:40] in view.style_body.toHtml()


def test_a_category_with_no_authored_style_renders_nothing(ruleset, qtbot):
    """⚠ None is an ordinary answer, not an error: `martial_arts:enlightenment` is the
    Dragon-Path initiation tree, not a style. An empty panel would be worse than none."""
    char = Character(id="c", exalt_type="Dragon-Blooded")
    char.abilities[AbilityName.MARTIAL_ARTS] = 5
    char.abilities[AbilityName.OCCULT] = 5
    char.essence_rating = 3
    page = CharmsPage(ruleset, {"char": char})
    qtbot.addWidget(page)
    view = _styles_view(page)
    if not _pick_category(view, "martial_arts:enlightenment"):
        pytest.skip("this character's Martial Arts tab does not offer enlightenment")
    assert viewmod.style_for_category(ruleset, "martial_arts:enlightenment") is None
    assert view.style_head.isHidden() and view.style_body.isHidden()


def test_the_style_panel_follows_the_category(ruleset, qtbot):
    page = CharmsPage(ruleset, {"char": _learnable_char()})
    qtbot.addWidget(page)
    view = _styles_view(page)
    keys = [view.category_combo.itemData(i)
            for i in range(view.category_combo.count())]
    styled = [k for k in keys if viewmod.style_for_category(ruleset, k) is not None]
    if len(styled) < 2:
        pytest.skip("needs two authored styles on one tab")
    _pick_category(view, styled[0])
    first = view.style_head.text()
    _pick_category(view, styled[1])
    assert view.style_head.text() != first
    assert viewmod.style_for_category(ruleset, styled[1]).name in view.style_head.text()


def test_the_expanded_state_survives_a_category_change(ruleset, qtbot):
    page = CharmsPage(ruleset, {"char": _learnable_char()})
    qtbot.addWidget(page)
    view = _styles_view(page)
    keys = [view.category_combo.itemData(i)
            for i in range(view.category_combo.count())]
    styled = [k for k in keys if viewmod.style_for_category(ruleset, k) is not None]
    if len(styled) < 2:
        pytest.skip("needs two authored styles on one tab")
    _pick_category(view, styled[0])
    view.style_head.setChecked(True)
    _pick_category(view, styled[1])
    assert not view.style_body.isHidden()
    assert view.style_head.text().startswith("▾")     # the arrow agrees


def test_a_charm_tree_tab_has_no_style_panel(ruleset, qtbot):
    """The Charms tab's categories are Abilities, never styles."""
    page = CharmsPage(ruleset, {"char": _learnable_char()})
    qtbot.addWidget(page)
    view = page._tree_views["abilities"]
    assert view.style_head.isHidden()


# --- Alchemical submodules (p.89) -------------------------------------------- #
#
# A submodule upgrades ONE Charm, so it is bought on that Charm's detail panel. The Qt
# detail pane is a QTextBrowser, so the rows live in their own box beneath it.

GAS = "alchemical.close-combat.chemical-fog-generator"     # four submodules, two tiers


def _alch(**kw):
    char = Character(id="a", exalt_type="Alchemical", caste="orichalcum", **kw)
    for ab in (AbilityName.MELEE, AbilityName.MARTIAL_ARTS):
        char.abilities[ab] = 5
    return char


def _sub_buttons(page):
    return [b for b in page._submodule_box.findChildren(QPushButton)]


def test_a_charm_without_submodules_shows_no_panel(ruleset, qtbot):
    char = _learnable_char()
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    page._selected_node = _first_available(ruleset, char)[0]
    page._update_action()
    assert page._submodule_box.isHidden()      # most Charms have none


def test_the_panel_lists_every_submodule_of_the_selected_charm(ruleset, qtbot):
    char = _alch()
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    page._selected_node = GAS
    page._update_action()
    assert not page._submodule_box.isHidden()
    names = {s.name for s in ruleset.charms[GAS].submodules}
    shown = {l.text() for l in page._submodule_box.findChildren(QLabel)}
    assert names <= shown


def test_adding_a_submodule_at_chargen_appends_it(ruleset, qtbot):
    char = _alch()
    char.charms = [GAS]
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    page._selected_node = GAS
    page._update_action()
    page._learn_submodule(GAS, "knockout-gas")
    assert [(s.charm_id, s.key) for s in char.submodules] == [(GAS, "knockout-gas")]
    # The rows rebuilt, so the same one now offers Remove rather than Add.
    assert any(b.text() == "Remove" for b in _sub_buttons(page))
    page._drop_submodule(GAS, "knockout-gas")
    assert char.submodules == []


def test_a_blocked_submodule_is_disabled_with_its_reason(ruleset, qtbot):
    """The nerve/soul gases want Essence 3; a starting Alchemical has Essence 1."""
    char = _alch()
    char.charms = [GAS]
    assert char.essence_rating < 3
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    page._selected_node = GAS
    page._update_action()
    blocked = [b for b in _sub_buttons(page) if not b.isEnabled()]
    assert blocked and all(b.toolTip() for b in blocked)


def test_the_engine_refuses_a_blocked_submodule_even_unasked(ruleset, qtbot):
    """⚠ The gate is in engine.charm_actions, not in the button's enabled state: a
    shell that never asked could otherwise append a submodule whose minimum is unmet."""
    from exalted_builder.engine import advancement as adv
    char = _alch()
    char.charms = [GAS]
    with pytest.raises(adv.AdvancementError):
        charm_actions.learn_submodule(ruleset, char, GAS, "nerve-gas")
    assert char.submodules == []


def test_the_panel_clears_when_the_selection_moves_on(ruleset, qtbot):
    char = _alch()
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    page._selected_node = GAS
    page._update_action()
    assert not page._submodule_box.isHidden()
    page._selected_node = None
    page._update_action()
    assert page._submodule_box.isHidden()


def test_a_submodule_purchase_moves_the_shell_readout(ruleset, qtbot):
    """It spends bonus points, so the shell's bar has to hear about it."""
    char = _alch()
    char.charms = [GAS]
    beats = []
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None,
                      on_change=lambda: beats.append(1))
    qtbot.addWidget(page)
    page._selected_node = GAS
    page._update_action()
    beats.clear()
    page._learn_submodule(GAS, "knockout-gas")
    assert beats


# --- the Immaculate-vs-standard path banner (Dragon-Blooded) ----------------- #


def _db(**kw):
    char = Character(id="d", exalt_type="Dragon-Blooded", caste="air", **kw)
    char.abilities[AbilityName.MARTIAL_ARTS] = 5
    char.essence_rating = 3
    return char


def test_a_dragon_blooded_is_told_which_chargen_path_they_are_on(ruleset, qtbot):
    char = _db()
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    b = ruleset.budgets_for("Dragon-Blooded", char.origin, char.upbringing)
    text = page.readout.text()
    assert "Standard path" in text
    assert str(b.charm_count) in text            # from the budget, never hardcoded
    assert "Immaculate" in text                  # and how to switch


def test_an_immaculate_charm_switches_the_path_line(ruleset, qtbot):
    """⚠ Immaculate is a DATA flag on the Charm (the five Dragon-style trees), not
    "is a martial art" — Five-Dragon Style is Martial Arts and does not switch."""
    cid = next((c.id for c in ruleset.charms.values()
                if validate.is_immaculate_charm(c)
                and c.exalt_type == "Dragon-Blooded"), None)
    assert cid is not None, "no Dragon-Blooded Immaculate Charm to test with"
    char = _db()
    char.charms = [cid]
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    b = ruleset.budgets_for("Dragon-Blooded", char.origin, char.upbringing)
    text = page.readout.text()
    assert "Immaculate path" in text and "Standard path" not in text
    assert str(b.immaculate_charm_count) in text
    assert "waived" in text


def test_no_other_splat_gets_a_path_line(ruleset, qtbot):
    page = CharmsPage(ruleset, {"char": _learnable_char()})
    qtbot.addWidget(page)
    assert page._immaculate_path_line() == ""
    assert "path" not in page.readout.text()


def test_the_path_line_is_chargen_only(ruleset, qtbot):
    """Post-lock the budget that matters is XP; the chargen path is settled."""
    char = _db()
    char.chargen_locked = True
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    assert "path" not in page.readout.text()


# --- the chargen BP preview agrees with what is actually charged ------------- #


def _bp_spent(ruleset, char):
    view = viewmod.build_sheet_view(ruleset, char)
    msg = next((i.message for i in view.issues if i.code == "bonus-points"), "0")
    return int(msg.split(" of ")[0])


def test_the_pick_that_flips_the_immaculate_path_quotes_its_real_price(ruleset, qtbot):
    """⚠ A Dragon-Blooded's free pool is 7 on the standard path and 5 on the Immaculate
    one, so the pick that FLIPS the path changes its own denominator. Deriving the pool
    size before staging the candidate sliced the staged pool at 7 when it had become 5:
    the button quoted 7 BP for a pick the accounting charged 21."""
    char = Character(id="d", exalt_type="Dragon-Blooded", caste="air", essence_rating=3)
    char.abilities = {a: 5 for a in AbilityName}
    for c in ruleset.charms.values():
        if c.exalt_type == "Dragon-Blooded" and "enlighten" in (c.category or ""):
            char.charms.append(c.id)          # the DB p241 Dragon-style gate
    immaculate = [c.id for c in ruleset.charms.values()
                  if validate.is_immaculate_charm(c)
                  and c.exalt_type == "Dragon-Blooded"
                  and validate.meets_charm_requirements(ruleset, char, c)]
    assert immaculate, "no reachable Immaculate Charm to flip the path with"
    b = ruleset.budgets_for("Dragon-Blooded", char.origin, char.upbringing)
    assert b.immaculate_charm_count < b.charm_count      # the flip SHRINKS the pool
    for c in ruleset.charms.values():                    # fill the standard pool
        if len(char.charms) >= b.charm_count:
            break
        if (c.exalt_type == "Dragon-Blooded" and c.id not in char.charms
                and not validate.is_immaculate_charm(c)
                and validate.meets_charm_requirements(ruleset, char, c)):
            char.charms.append(c.id)

    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    cand = immaculate[0]
    assert not validate.immaculate_martial_artist(ruleset, char)
    quoted = page._chargen_pick_bp(charm_id=cand)
    before = _bp_spent(ruleset, char)
    char.charms.append(cand)
    charged = _bp_spent(ruleset, char) - before
    assert validate.immaculate_martial_artist(ruleset, char)   # the pick flipped it
    assert quoted == charged, f"button quoted {quoted} BP, accounting charged {charged}"


def test_an_ordinary_pick_still_quotes_its_price(ruleset, qtbot):
    """The negative control: the fix must not disturb the common case, where the
    candidate does not move the pool size at all."""
    char = _learnable_char()
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    avail = _first_available(ruleset, char)
    for cid in avail[:8]:                     # spend past the free pool
        quoted = page._chargen_pick_bp(charm_id=cid)
        before = _bp_spent(ruleset, char)
        char.charms.append(cid)
        assert quoted == _bp_spent(ruleset, char) - before


# --- post-lock Remove is the LAST XP entry only ------------------------------ #
#
# ⚠ The button read "Remove <Charm>" and was ENABLED post-lock, but `drop_charm`
# refuses every post-lock removal — so it failed on every click. The log is
# append-only and undo is LIFO (decision 0004), so the only Charm that can come back
# is the one the most recent entry bought.


def _locked_with_two_charms(ruleset):
    char = _learnable_char()
    avail = _first_available(ruleset, char)
    char.chargen_locked = True
    char.xp_earned = 200
    first, second = avail[0], avail[1]
    charm_actions.learn_charm(ruleset, char, first)
    charm_actions.learn_charm(ruleset, char, second)
    return char, first, second


def test_the_last_purchase_can_be_removed(ruleset, qtbot):
    char, _first, second = _locked_with_two_charms(ruleset)
    spent = advancement.xp_spent(char)
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    page._selected_node = second
    page._update_action()
    assert page.action_btn.isEnabled()
    assert page.action_btn.text().startswith("Remove")
    assert page.action_btn.toolTip() == ""

    page._toggle_charm(second)
    assert second not in char.charms
    assert advancement.xp_spent(char) < spent          # the XP came back
    assert len(char.xp_log) == 1                       # and the ledger row went


def test_an_earlier_purchase_is_disabled_with_the_reason(ruleset, qtbot):
    char, first, _second = _locked_with_two_charms(ruleset)
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    page._selected_node = first
    page._update_action()
    assert not page.action_btn.isEnabled()
    assert "most recent" in page.action_btn.toolTip()


def test_removing_the_last_one_promotes_the_one_before_it(ruleset, qtbot):
    """LIFO: undo the top row and the next becomes removable in turn."""
    char, first, second = _locked_with_two_charms(ruleset)
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    page._toggle_charm(second)
    page._selected_node = first
    page._update_action()
    assert page.action_btn.isEnabled()


def test_a_chargen_charm_is_still_removed_outright(ruleset, qtbot):
    """The negative control: pre-lock nothing about this changed."""
    char = _learnable_char()
    cid = _first_available(ruleset, char)[0]
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    page._toggle_charm(cid)
    assert cid in char.charms
    page._toggle_charm(cid)
    assert cid not in char.charms
    assert char.xp_log == []


def test_a_charm_bought_before_a_trait_raise_is_not_removable(ruleset, qtbot):
    """⚠ The last entry need not be a Charm at all. Raising an Ability after buying a
    Charm makes that Charm un-undoable until the raise is undone first — which is what
    LIFO means and what the tooltip has to say."""
    char, _first, second = _locked_with_two_charms(ruleset)
    advancement.raise_ability(ruleset, char, AbilityName.MELEE)
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    page._selected_node = second
    page._update_action()
    assert not page.action_btn.isEnabled()
    assert "most recent" in page.action_btn.toolTip()
