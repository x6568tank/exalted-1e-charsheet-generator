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
from PySide6.QtWidgets import QCheckBox, QLabel, QLineEdit, QPushButton

from exalted_builder.engine import advancement, lifecycle, refit, validate
from exalted_builder.models.character import (AbilityName, Character,
                                               MeritFlawPurchase, PathRating)
from exalted_builder.qt.charms import (CharmsPage, CharmTreeView, DotTrack,
                                       trees_for,
                                       EdgeItem, NodeItem, _tree_positions, populate)
from exalted_builder.ui.view import build_thaum_picker


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
    assert not page._orientation_combo.isEnabled()   # owned -> no orientation pick
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
