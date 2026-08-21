"""The Qt Charms tab (exalted_builder/qt/charms.py) — QGraphicsView charm trees.

Ports the qt_tree spike's layout/routing coverage into the port: per-splat tab sets,
node/edge/root counts, the tidy-tree layout, wheel zoom, and selection → detail. The
layout and routing functions are pure, so they test without a widget at all.
"""

from types import SimpleNamespace

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QLineEdit, QPushButton

from exalted_builder.engine import advancement, lifecycle, refit
from exalted_builder.models.character import (AbilityName, Character,
                                               MeritFlawPurchase, PathRating)
from exalted_builder.qt.charms import (CharmsPage, CharmTreeView, EdgeItem,
                                       NodeItem, _tree_positions, populate)
from exalted_builder.ui.view import build_thaum_picker


def _visible_tabs(page):
    return [page.tabs.tabText(i) for i in range(page.tabs.count())]


def test_solar_page_tabs(ruleset, qtbot):
    page = CharmsPage(ruleset, {"char": Character(id="char.new", exalt_type="Solar")})
    qtbot.addWidget(page)
    assert _visible_tabs(page) == ["Charms", "Martial Arts", "Spells", "Thaumaturgy"]
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


def test_paths_pre_lock_rating_combo_writes_paths(ruleset, qtbot):
    char = Character(id="dk", exalt_type="Dragon-Kings", caste="pterok")
    page = CharmsPage(ruleset, {"char": char}, notify=lambda *a, **k: None)
    qtbot.addWidget(page)
    page._path_combos["dk.solid-earth"].setCurrentIndex(2)
    assert any(p.path_id == "dk.solid-earth" and p.rating == 2 for p in char.paths)
    page._path_combos["dk.solid-earth"].setCurrentIndex(0)
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
    page._path_adv("dk.solid-earth", +1)
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
    page._path_adv("dk.solid-earth", +1)
    assert any(p.path_id == "dk.solid-earth" and p.rating == 3 for p in char.paths)
    assert messages
