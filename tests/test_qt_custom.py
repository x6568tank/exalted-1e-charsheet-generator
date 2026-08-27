"""The Qt Custom page (exalted_builder/qt/custom.py) — authoring homebrew Charms and
spells.

Covers what the widget decides for itself: that the library table lists the rows on
DISK for the active kind, that a row the loader rejected is still shown and still
openable, that selecting one loads it into the form, that Save writes through
`custom_content` and re-merges into the live rule set, that Delete pings the shell, and
that the JSON dialog round-trips a row.

⚠ Every test passes `custom_dir=tmp_path`. The page defaults to the USER'S REAL library
(`custom_content.custom_data_dir()`), and a test that forgot would read — and Save would
write — the human's own homebrew.

⚠ The layout is the settled COLLECTION one (sub-tab per kind + sortable table +
splitter + detail pane), not the NiceGUI page's three columns. The webapp's JSON column
is a toolbar DIALOG here, reached through `_build_json_dialog`, which returns one
WITHOUT running it — `exec()` blocks a headless run (the seam `GearPage` uses).

⚠ Controls are addressed by objectName (`custom.<field>`), never by position.
"""

import json
from pathlib import Path

import pytest

# ⚠ PySide6 is the OPTIONAL `qt` extra (pyproject), so it is legitimately absent on a
# machine that only runs the webapp. Skip the module rather than letting a bare import
# turn into a COLLECTION ERROR — that kills the whole run, not just these tests.
pytest.importorskip("PySide6", reason="the optional [qt] extra is not installed")

from PySide6.QtWidgets import QComboBox, QLabel, QLineEdit, QPushButton, QTextEdit

from exalted_builder import custom_content
from exalted_builder.models.character import Character
from exalted_builder.qt.custom import CustomPage
from exalted_builder.ui import view as viewmod


def _page(ruleset, tmp_path, notes=None, on_change=None):
    sink = notes if notes is not None else []
    page = CustomPage(ruleset, {"char": Character(id="c.custom", exalt_type="Solar")},
                      custom_dir=Path(tmp_path),
                      notify=lambda text, kind="info": sink.append((kind, text)),
                      on_change=on_change)
    page.reload()
    return page


def _author(page, name, **fields):
    """Author one row through the page, the way a user does."""
    page._new()
    page._form["name"] = name
    page._form.update(fields)
    page._save()
    return page._editing


def _names(page, kind="charm"):
    table = page._tables[kind]
    return [table.topLevelItem(i).text(1) for i in range(table.topLevelItemCount())]


def _item(page, name, kind="charm"):
    table = page._tables[kind]
    return next(table.topLevelItem(i) for i in range(table.topLevelItemCount())
                if table.topLevelItem(i).text(1) == name)


def _control(page, field, kind=QLineEdit):
    return page._detail_body.findChild(kind, f"custom.{field}")


# --------------------------------------------------------------------------- #
# the library
# --------------------------------------------------------------------------- #

def test_the_library_lists_what_is_on_disk(ruleset, tmp_path, qtbot):
    page = _page(ruleset, tmp_path)
    qtbot.addWidget(page)
    assert _names(page) == []
    _author(page, "Blade of the Setting Sun", category="melee")
    _author(page, "Whisper of Forgotten Names", category="occult")
    assert sorted(_names(page)) == ["Blade of the Setting Sun",
                                    "Whisper of Forgotten Names"]
    assert "2 Charm(s)" in page.readout.text()


def test_the_table_has_a_header_and_is_sortable(ruleset, tmp_path, qtbot):
    page = _page(ruleset, tmp_path)
    qtbot.addWidget(page)
    table = page._tables["charm"]
    headers = [table.headerItem().text(i) for i in range(table.columnCount())]
    assert headers == ["", "Name", "Detail"]
    assert table.isSortingEnabled()
    assert not table.header().isSortIndicatorShown()


def test_charms_and_spells_are_separate_sub_tabs(ruleset, tmp_path, qtbot):
    page = _page(ruleset, tmp_path)
    qtbot.addWidget(page)
    _author(page, "Blade of the Setting Sun", category="melee")
    page.tabs.setCurrentIndex(1)
    assert page._kind == "spell"
    _author(page, "Ivory Orchid Petal")
    assert _names(page, "spell") == ["Ivory Orchid Petal"]
    # ⚠ The Charm is still in the OTHER table, not merged into this one.
    assert _names(page, "charm") == ["Blade of the Setting Sun"]


def test_a_rejected_row_is_shown_and_still_openable(ruleset, tmp_path, qtbot):
    """⚠ A row the loader threw out is not in `ruleset.charms` at all — and it is
    exactly the row a user needs to open in order to fix it. The form loads from DISK
    for this reason."""
    page = _page(ruleset, tmp_path)
    qtbot.addWidget(page)
    # A prerequisite that resolves to nothing: the loader drops the row, non-fatally.
    broken = {"id": "custom.orphan", "name": "Orphaned Charm", "category": "melee",
              "exalt_type": "Solar", "type": "Supplemental",
              "prerequisites": [["no.such.charm"]],
              "source": {"book": "Homebrew"}}
    (tmp_path / "charms").mkdir(exist_ok=True)
    (tmp_path / "charms" / "orphan.json").write_text(json.dumps([broken]))
    page.reload()
    assert "Orphaned Charm" in _names(page)
    assert "custom.orphan" not in ruleset.charms          # the loader did drop it
    item = _item(page, "Orphaned Charm")
    assert item.text(0) == "⚠"
    page._edit("custom.orphan")
    assert page._form["name"] == "Orphaned Charm"         # opened off the disk anyway


def test_a_valid_row_is_marked_and_not_flagged(ruleset, tmp_path, qtbot):
    """The negative control for the ⚠ above."""
    page = _page(ruleset, tmp_path)
    qtbot.addWidget(page)
    _author(page, "Blade of the Setting Sun", category="melee")
    assert _item(page, "Blade of the Setting Sun").text(0) == "✎"


# --------------------------------------------------------------------------- #
# the form
# --------------------------------------------------------------------------- #

def test_selecting_a_row_loads_it_into_the_form(ruleset, tmp_path, qtbot):
    page = _page(ruleset, tmp_path)
    qtbot.addWidget(page)
    row_id = _author(page, "Blade of the Setting Sun", category="melee")
    page._new()
    assert page._editing == ""
    page._tables["charm"].setCurrentItem(_item(page, "Blade of the Setting Sun"))
    assert page._editing == row_id
    assert _control(page, "name").text() == "Blade of the Setting Sun"
    assert row_id in page.detail_title.text()


def test_a_new_row_survives_a_table_rebuild(ruleset, tmp_path, qtbot):
    """⚠ THE invariant that makes this collection different. Every other tab re-selects
    its first row when the old selection is gone; here that would overwrite a
    half-written new Charm the moment the table rebuilt."""
    page = _page(ruleset, tmp_path)
    qtbot.addWidget(page)
    _author(page, "Blade of the Setting Sun", category="melee")
    page._new()
    page._form["name"] = "Half Written"
    page._fill_tables()
    assert page._editing == ""
    assert page._form["name"] == "Half Written"
    assert page._tables["charm"].currentItem() is None


def test_switching_kind_starts_a_new_row_of_that_kind(ruleset, tmp_path, qtbot):
    page = _page(ruleset, tmp_path)
    qtbot.addWidget(page)
    assert "category" in page._form                       # a Charm form
    page.tabs.setCurrentIndex(1)
    assert page._kind == "spell" and page._editing == ""
    assert "circle" in page._form and "category" not in page._form


def test_a_new_style_category_reveals_the_style_name_box(ruleset, tmp_path, qtbot):
    """⚠ A Martial Arts style is not a separate thing to create — the sentinel category
    writes `martial_arts:<slug>` and the picker derives the style from that string."""
    page = _page(ruleset, tmp_path)
    qtbot.addWidget(page)
    assert _control(page, "style_name") is None
    page._form["category"] = viewmod.NEW_STYLE
    page._rebuild()
    assert _control(page, "style_name") is not None


def test_an_extra_requirement_row_can_be_added_and_dropped(ruleset, tmp_path, qtbot):
    page = _page(ruleset, tmp_path)
    qtbot.addWidget(page)
    add = page._detail_body.findChild(QPushButton, "custom.extra_reqs.add")
    add.click()
    assert len(page._form["extra_reqs"]) == 1
    assert page._detail_body.findChild(QComboBox, "custom.extra_reqs.0.kind") is not None
    page._detail_body.findChild(QPushButton, "custom.extra_reqs.0.remove").click()
    assert page._form["extra_reqs"] == []


def test_switching_a_requirements_axis_clears_its_traits(ruleset, tmp_path, qtbot):
    """⚠ The traits go WITH the axis: an Ability value is not a legal Attribute, and
    leaving them renders a picker holding options its own list does not contain."""
    page = _page(ruleset, tmp_path)
    qtbot.addWidget(page)
    page._form["extra_reqs"] = [{"kind": "ability", "traits": ["melee"], "rating": 3}]
    page._rebuild()
    combo = page._detail_body.findChild(QComboBox, "custom.extra_reqs.0.kind")
    combo.setCurrentIndex(1)                              # -> Attribute
    assert page._form["extra_reqs"][0]["kind"] == "attribute"
    assert page._form["extra_reqs"][0]["traits"] == []


def test_the_description_writes_through(ruleset, tmp_path, qtbot):
    """⚠ `QTextEdit.textChanged` carries NO argument, so the text must come off the
    widget — QLineEdit's signal does carry one, which is the trap."""
    page = _page(ruleset, tmp_path)
    qtbot.addWidget(page)
    box = page._detail_body.findChild(QTextEdit, "custom.description")
    box.setPlainText("A stance of iron.")
    assert page._form["description"] == "A stance of iron."


# --------------------------------------------------------------------------- #
# save / delete
# --------------------------------------------------------------------------- #

def test_saving_writes_the_library_and_merges_the_rule_set(ruleset, tmp_path, qtbot):
    page = _page(ruleset, tmp_path)
    qtbot.addWidget(page)
    row_id = _author(page, "Blade of the Setting Sun", category="melee")
    assert row_id in ruleset.charms
    assert ruleset.charms[row_id].custom
    assert [r["name"] for r in custom_content.library_charms(tmp_path)] == \
        ["Blade of the Setting Sun"]


def test_saving_stays_on_the_row_it_just_wrote(ruleset, tmp_path, qtbot):
    """Saving does not clear the form — staying on the row is what makes "save, look at
    the tree, adjust" work."""
    page = _page(ruleset, tmp_path)
    qtbot.addWidget(page)
    row_id = _author(page, "Blade of the Setting Sun", category="melee")
    assert page._editing == row_id
    assert _control(page, "name").text() == "Blade of the Setting Sun"


def test_the_id_follows_the_name_until_the_first_save_then_freezes(ruleset, tmp_path,
                                                                   qtbot):
    """⚠ Characters reference the id, so an edit must never change it — a rename after
    the first save keeps the original id."""
    page = _page(ruleset, tmp_path)
    qtbot.addWidget(page)
    row_id = _author(page, "Blade of the Setting Sun", category="melee")
    page._form["name"] = "Renamed Entirely"
    page._save()
    assert page._editing == row_id
    assert ruleset.charms[row_id].name == "Renamed Entirely"


def test_homebrew_cannot_shadow_a_printed_id(ruleset, tmp_path, qtbot):
    """The book always wins an id collision. The page hands `reserved_ids` to the saver
    and recomputes them per save, because the custom half of `ruleset.charms` changes
    underneath it — a snapshot taken once would go stale after the first Save."""
    notes = []
    page = _page(ruleset, tmp_path, notes=notes)
    qtbot.addWidget(page)
    printed = next(i for i, c in ruleset.charms.items() if not c.custom)
    assert printed in page._reserved()
    # Drive the refusal through the page, not the saver: the page is what decides which
    # ids are reserved, and that is the half that can be wrong.
    page._paste(json.dumps({"id": printed, "name": "Impostor", "category": "melee",
                            "exalt_type": "Solar", "type": "Supplemental",
                            "source": {"book": "Homebrew"}}))
    page._save()
    assert ruleset.charms[printed].custom is False        # still the book's
    assert any("not a custom id" in text or "already used" in text
               for _, text in notes)


def test_deleting_removes_the_row_and_pings_the_shell(ruleset, tmp_path, qtbot):
    """⚠ The hook is load-bearing: a deleted Charm a character owns stays on the sheet
    as an `unknown-charm` error, which the shell's readout bar reports."""
    pings = []
    page = _page(ruleset, tmp_path, on_change=lambda: pings.append(1))
    qtbot.addWidget(page)
    row_id = _author(page, "Blade of the Setting Sun", category="melee")
    pings.clear()
    custom_content.delete_charm(row_id, custom_dir=tmp_path)
    page._new()
    page.reload()
    page._ping()
    assert _names(page) == []
    assert pings


def test_deleting_an_unsaved_row_says_so_rather_than_crashing(ruleset, tmp_path, qtbot):
    notes = []
    page = _page(ruleset, tmp_path, notes=notes)
    qtbot.addWidget(page)
    page._new()
    page._delete()
    assert any("has not been saved" in text for _, text in notes)


# --------------------------------------------------------------------------- #
# JSON in / out
# --------------------------------------------------------------------------- #

def test_the_json_dialog_shows_the_current_row(ruleset, tmp_path, qtbot):
    page = _page(ruleset, tmp_path)
    qtbot.addWidget(page)
    _author(page, "Blade of the Setting Sun", category="melee")
    dialog = page._build_json_dialog()
    qtbot.addWidget(dialog)
    payload = json.loads(dialog.findChild(QTextEdit, "custom.json.out").toPlainText())
    assert payload["name"] == "Blade of the Setting Sun"
    assert payload["category"] == "melee"


def test_pasting_one_row_fills_the_form_without_saving(ruleset, tmp_path, qtbot):
    """⚠ The user gets to see and adjust it first — that is the whole reason the pane is
    two-way."""
    page = _page(ruleset, tmp_path)
    qtbot.addWidget(page)
    row = {"id": "custom.pasted", "name": "Pasted Charm", "category": "melee",
           "exalt_type": "Solar", "type": "Supplemental",
           "source": {"book": "Homebrew"}}
    page._paste(json.dumps(row))
    assert page._form["name"] == "Pasted Charm"
    assert custom_content.library_charms(tmp_path) == []   # nothing written yet


def test_pasting_an_array_is_a_bulk_import(ruleset, tmp_path, qtbot):
    page = _page(ruleset, tmp_path)
    qtbot.addWidget(page)
    rows = [{"id": f"custom.bulk{n}", "name": f"Bulk {n}", "category": "melee",
             "exalt_type": "Solar", "type": "Supplemental",
             "source": {"book": "Homebrew"}} for n in range(3)]
    page._paste(json.dumps(rows))
    assert len(custom_content.library_charms(tmp_path)) == 3
    assert sorted(_names(page)) == ["Bulk 0", "Bulk 1", "Bulk 2"]


def test_bad_json_is_reported_not_raised(ruleset, tmp_path, qtbot):
    notes = []
    page = _page(ruleset, tmp_path, notes=notes)
    qtbot.addWidget(page)
    page._paste("{not json at all")
    assert notes and notes[-1][0] == "warning"


# --------------------------------------------------------------------------- #
# the Gear sub-tab — list + delete, and deliberately no authoring form
# --------------------------------------------------------------------------- #

def _seed_gear(tmp_path):
    custom_content.save_gear_row("weapons", {
        "id": "custom.singing-edge", "name": "Singing Edge", "accuracy": 3,
        "damage": 6, "resources_cost": 4}, custom_dir=tmp_path)
    custom_content.save_gear_row("armor", {
        "id": "custom.dawn-plate", "name": "Dawn Plate", "weight": "Heavy",
        "soak_lethal": 8, "soak_bashing": 10}, custom_dir=tmp_path)


def _gear_page(ruleset, tmp_path, notes=None):
    page = _page(ruleset, tmp_path, notes=notes)
    page.tabs.setCurrentIndex(2)
    page.reload()
    return page


def test_the_gear_list_shows_every_kind_with_its_stats(ruleset, tmp_path, qtbot):
    """⚠ The Detail column is the regression guard for `reload_custom_layer` skipping
    the gear catalogues: unmerged rows fall back to the bare name, so a stat line here
    proves the re-merge ran."""
    _seed_gear(tmp_path)
    page = _gear_page(ruleset, tmp_path)
    qtbot.addWidget(page)
    table = page._tables["gear"]
    rows = {table.topLevelItem(i).text(1): (table.topLevelItem(i).text(2),
                                            table.topLevelItem(i).text(3))
            for i in range(table.topLevelItemCount())}
    assert set(rows) == {"Singing Edge", "Dawn Plate"}
    assert rows["Singing Edge"][0] == "Weapon"
    assert rows["Dawn Plate"][0] == "Armour"
    assert "Acc+3" in rows["Singing Edge"][1]          # a real stat line, not the name
    assert "2 gear row(s)" in page.readout.text()


def test_the_gear_table_has_a_kind_column_the_others_do_not(ruleset, tmp_path, qtbot):
    page = _gear_page(ruleset, tmp_path)
    qtbot.addWidget(page)
    gear = page._tables["gear"]
    assert [gear.headerItem().text(i) for i in range(gear.columnCount())] == \
        ["", "Name", "Kind", "Detail"]
    charm = page._tables["charm"]
    assert [charm.headerItem().text(i) for i in range(charm.columnCount())] == \
        ["", "Name", "Detail"]


def test_gear_can_be_authored_but_not_imported(ruleset, tmp_path, qtbot):
    """⚠ Import stays off: `parse_rows` yields bare rows and a gear row does not name
    WHICH of the four catalogues it belongs to. New does, via the Kind picker."""
    page = _gear_page(ruleset, tmp_path)
    qtbot.addWidget(page)
    assert page.new_btn.isEnabled()
    assert not page.import_btn.isEnabled()
    page.tabs.setCurrentIndex(0)
    assert page.new_btn.isEnabled() and page.import_btn.isEnabled()


@pytest.mark.parametrize("kind,extra,check", [
    ("weapons", {"accuracy": 3, "damage": 6}, "weapon_catalog"),
    ("armor", {"soak_lethal": 8, "soak_bashing": 10}, "armor_catalog"),
    ("gear", {"category": "Tools"}, "gear_catalog"),
    ("artifacts", {"rating": 3}, "artifact_catalog"),
])
def test_every_gear_kind_can_be_authored_from_the_form(ruleset, tmp_path, qtbot,
                                                        kind, extra, check):
    """⚠ Reverses the 2026-08-13 ruling, reopened by the human 2026-08-27. The old flow
    made you give a character an item in order to invent one."""
    page = _gear_page(ruleset, tmp_path)
    qtbot.addWidget(page)
    page._switch_gear_kind(kind)
    page._form["name"] = f"Test {kind}"
    page._form.update(extra)
    page._save()
    assert page._editing.startswith("custom.")
    assert page._editing in getattr(ruleset, check)
    assert [r["name"] for r in custom_content.library_gear(kind, tmp_path)] == \
        [f"Test {kind}"]


def test_a_blank_form_of_every_kind_saves(ruleset, tmp_path, qtbot):
    """⚠ The required-field guard. `ArmorType.soak_lethal` and `ArtifactType.rating`
    have NO model default, so a payload that drops empty values makes the row
    unloadable — and `rating` is `ge=1`, so a zero is not a legal blank either."""
    page = _gear_page(ruleset, tmp_path)
    qtbot.addWidget(page)
    for kind in ("weapons", "armor", "gear", "artifacts"):
        page._switch_gear_kind(kind)
        page._form["name"] = f"Blank {kind}"
        page._save()
        assert page._editing in getattr(
            ruleset, viewmod.CUSTOM_GEAR_KINDS[kind][0]), kind


def test_the_kind_picker_freezes_once_the_row_is_saved(ruleset, tmp_path, qtbot):
    """Changing the kind changes the MODEL, and the row already sits in one of four
    files under one id."""
    page = _gear_page(ruleset, tmp_path)
    qtbot.addWidget(page)
    picker = page._detail_body.findChild(QComboBox, "custom.gear_kind")
    assert picker.isEnabled()
    page._form["name"] = "Singing Edge"
    page._save()
    assert not page._detail_body.findChild(QComboBox, "custom.gear_kind").isEnabled()


def test_mobility_penalty_accepts_a_negative(ruleset, tmp_path, qtbot):
    """⚠ `Armor.mobility_penalty` is stored NEGATIVE. A 0-floored spin box makes a
    penalty impossible to enter, and a consumer reading it as a magnitude ADDS dice."""
    from PySide6.QtWidgets import QSpinBox
    page = _gear_page(ruleset, tmp_path)
    qtbot.addWidget(page)
    page._switch_gear_kind("armor")
    box = page._detail_body.findChild(QSpinBox, "custom.mobility_penalty")
    assert box.minimum() < 0
    box.setValue(-2)
    page._form["name"] = "Dawn Plate"
    page._save()
    assert ruleset.armor_catalog[page._editing].mobility_penalty == -2


def test_a_homebrew_weapon_cannot_shadow_a_printed_one(ruleset, tmp_path, qtbot):
    """⚠ Gear carries no `custom` FIELD — the loader TAGS it, because the models are
    frozen and shared with the book data. `_reserved` reading `.custom` would raise."""
    page = _gear_page(ruleset, tmp_path)
    qtbot.addWidget(page)
    page._switch_gear_kind("weapons")
    reserved = page._reserved()
    assert reserved and all("custom" not in ruleset.weapon_catalog[i].tags
                            for i in reserved)


def test_deleting_a_gear_row_removes_it_from_disk_and_the_catalogue(ruleset, tmp_path,
                                                                    qtbot):
    _seed_gear(tmp_path)
    page = _gear_page(ruleset, tmp_path)
    qtbot.addWidget(page)
    table = page._tables["gear"]
    row = next(table.topLevelItem(i) for i in range(table.topLevelItemCount())
               if table.topLevelItem(i).text(1) == "Singing Edge")
    table.setCurrentItem(row)
    assert page._gear_kind == "weapons"                 # routed to the right catalogue
    assert custom_content.delete_gear(page._gear_kind, page._editing,
                                      custom_dir=tmp_path) is True
    page._new()
    page.reload()
    assert [r["name"] for r in custom_content.library_gear("weapons", tmp_path)] == []
    assert "custom.singing-edge" not in ruleset.weapon_catalog


def test_the_gear_delete_warning_is_not_the_charm_one(ruleset, tmp_path, qtbot):
    """⚠ Different consequence, different sentence. Saves carry inline COPIES of gear
    (decision 0007), so deleting a library weapon orphans nothing on a sheet — telling
    the user the Charm story would frighten them about a thing that cannot happen."""
    from exalted_builder.qt.custom import _DELETE_WARNING, _GEAR_DELETE_WARNING
    assert "missing row" in _DELETE_WARNING
    assert "missing row" not in _GEAR_DELETE_WARNING
    assert "own copy" in _GEAR_DELETE_WARNING


def test_the_json_dialog_is_read_only_for_gear(ruleset, tmp_path, qtbot):
    """Load writes through the Charm/spell savers, and a pasted gear row does not name
    which of the four catalogues it belongs to."""
    _seed_gear(tmp_path)
    page = _gear_page(ruleset, tmp_path)
    qtbot.addWidget(page)
    table = page._tables["gear"]
    table.setCurrentItem(table.topLevelItem(0))
    dialog = page._build_json_dialog()
    qtbot.addWidget(dialog)
    assert not dialog.findChild(QPushButton, "custom.json.load").isEnabled()
    assert json.loads(
        dialog.findChild(QTextEdit, "custom.json.out").toPlainText())["name"]


# --------------------------------------------------------------------------- #
# the shell contract
# --------------------------------------------------------------------------- #

def test_the_shell_wires_the_page_with_on_change(ruleset, qtbot):
    """The hook contract, asserted at the CONSTRUCTOR rather than the page — that is
    where it went missing on CharmsPage."""
    from exalted_builder.qt.main_window import MainWindow
    win = MainWindow(ruleset, Character(id="c.x", exalt_type="Solar"), Path("x.json"))
    qtbot.addWidget(win)
    page = win._pages["Custom"]
    assert isinstance(page, CustomPage)
    assert page._on_change is not None


def test_building_the_shell_does_not_read_the_users_library(ruleset, qtbot, monkeypatch):
    """⚠ This page's refresh reads the FILESYSTEM, and the shell builds all nine pages up
    front — so `reload()` is deliberately NOT called in the constructor. Without this the
    user's homebrew library is re-scanned on every window and in every Qt test."""
    from exalted_builder.qt import custom as custommod
    from exalted_builder.qt.main_window import MainWindow
    reads = []
    monkeypatch.setattr(custommod.custom_content, "library_charms",
                        lambda *a, **k: reads.append(1) or [])
    monkeypatch.setattr(custommod.custom_content, "library_spells",
                        lambda *a, **k: reads.append(1) or [])
    win = MainWindow(ruleset, Character(id="c.x", exalt_type="Solar"), Path("x.json"))
    qtbot.addWidget(win)
    assert reads == []
    win._pages["Custom"].reload()
    assert reads                                          # and it DOES read when shown


def test_a_rebuild_does_not_leak_widgets(ruleset, tmp_path, qtbot):
    """⚠ Thrash the rebuild and count. A single reload passes while leaking — the
    `clear_layout` trap that shipped six times."""
    page = _page(ruleset, tmp_path)
    qtbot.addWidget(page)
    baseline = len(page._detail_body.findChildren(QLabel))
    for _ in range(6):
        page.reload()
    assert len(page._detail_body.findChildren(QLabel)) == baseline
