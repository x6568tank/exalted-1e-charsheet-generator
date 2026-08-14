"""The inventory — one filterable view over everything owned.

The human's model, 2026-08-13: "you have your inventory, which is Everything, but you
can filter it down to certain types of goods, some of which would overlap."

⚠ The two load-bearing facts, and both are easy to break later:

  * it is a VIEW, not a storage shape. The four lists stay typed and separate because
    they carry different fields, and because `character.weapons` is indexed by position
    elsewhere (the dice-pool sidebar);
  * the filters are NOT a partition. An artifact daiklave answers to `weapon` AND
    `artifact`, so the counts sum to more than the number of rows. A future change that
    "fixes" that has broken the feature.
"""

from pathlib import Path

import pytest

import exalted_builder
from exalted_builder import rules_db
from exalted_builder.models.character import (Armor, ArtifactEntry, BackgroundEntry,
                                              Character, GearEntry, Weapon)
from exalted_builder.ui import view as viewmod

DATA_DIR = Path(exalted_builder.__file__).parent / "data"


@pytest.fixture(scope="module")
def rs():
    return rules_db.load_ruleset(DATA_DIR)


def _packrat() -> Character:
    c = Character(id="inv", exalt_type="Solar", caste="dawn", essence_rating=2)
    c.weapons.append(Weapon(name="Daiklave", artifact_rating=2))
    c.weapons.append(Weapon(name="Long Bow"))
    c.weapons.append(Weapon(name="Frog Crotch Arrow", quantity=20))
    c.armor.append(Armor(name="Buff Jacket", soak_lethal=3))
    c.artifacts.append(ArtifactEntry(name="Tattered Wings", rating=2))
    c.gear.append(GearEntry(name="Fine clothes", resources_cost=2))
    return c


def test_everything_owned_appears_once(rs):
    rows = viewmod.inventory_rows(rs, _packrat())
    assert [r.name for r in rows] == [
        "Daiklave", "Long Bow", "Frog Crotch Arrow", "Buff Jacket",
        "Tattered Wings", "Fine clothes"]
    assert [r.list_name for r in rows] == [
        "weapons", "weapons", "weapons", "armor", "artifacts", "gear"]
    # The index is the position in its OWN list — the route back to the editable row.
    assert [(r.list_name, r.index) for r in rows if r.list_name == "weapons"] == [
        ("weapons", 0), ("weapons", 1), ("weapons", 2)]


def test_the_categories_OVERLAP_by_design(rs):
    """An artifact daiklave is a weapon and an artifact; an arrow is a weapon and
    ammunition. The filters intersect rather than partition, so the counts sum to more
    than the rows — which is the point, not a bug."""
    rows = viewmod.inventory_rows(rs, _packrat())
    by_name = {r.name: r for r in rows}
    assert set(by_name["Daiklave"].kinds) == {"weapon", "artifact"}
    assert set(by_name["Frog Crotch Arrow"].kinds) == {"weapon", "ammunition"}
    assert set(by_name["Buff Jacket"].kinds) == {"armor"}
    assert set(by_name["Fine clothes"].kinds) == {"goods"}

    counts = viewmod.inventory_counts(rows)
    assert counts == {"all": 6, "weapon": 3, "armor": 1, "artifact": 2, "goods": 1,
                      "ammunition": 1}
    assert sum(v for k, v in counts.items() if k != "all") > counts["all"]


def test_filtering_picks_rows_whose_kinds_intersect(rs):
    rows = viewmod.inventory_rows(rs, _packrat())
    assert [r.name for r in viewmod.filter_inventory(rows, "artifact")] == [
        "Daiklave", "Tattered Wings"]
    assert [r.name for r in viewmod.filter_inventory(rows, "weapon")] == [
        "Daiklave", "Long Bow", "Frog Crotch Arrow"]
    assert len(viewmod.filter_inventory(rows, "all")) == 6


def _linked_daiklave() -> tuple[Character, str]:
    from exalted_builder.engine import artifacts as artifactsmod
    c = Character(id="g", exalt_type="Solar", caste="dawn", essence_rating=2)
    key = artifactsmod.item_key(artifactsmod.SOURCE_ARTIFACT, "Daiklave")
    c.artifacts.append(ArtifactEntry(name="Daiklave", rating=2))
    c.weapons.append(Weapon(name="Daiklave", artifact_rating=2, accuracy=3,
                            from_artifact=key))
    return c, key


def test_a_granted_stat_line_is_ONE_row_with_its_artifact(rs):
    """An artifact and the stat line `grant_gear` stamped for it are ONE OBJECT, and the
    inventory shows one row (the human, 2026-08-13 click-through: two peer rows for one
    daiklave "feels odd, and a little obtuse").

    The merge is display-only — `character.weapons` still holds the stat line, so the
    dice-pool sidebar's positional indices and the typed lists are untouched. What
    changes is that the row answers to BOTH filters instead of the pair splitting one
    object across two lines.
    """
    c, _ = _linked_daiklave()
    rows = viewmod.inventory_rows(rs, c)
    assert len(rows) == 1
    row = rows[0]
    assert set(row.kinds) == {"weapon", "artifact"}
    # It is the ARTIFACT that owns the row — that is the object; the weapon is its
    # stat line, and rides in `detail` and as the linked editor.
    assert (row.list_name, row.index) == ("artifacts", 0)
    assert (row.linked_list_name, row.linked_index) == ("weapons", 0)
    assert "Acc" in row.detail
    assert row.artifact_rating == 2
    # …and the budget still counts one, which is what it counted before the merge.
    assert viewmod.inventory_counts(rows)["artifact"] == 1


def test_the_merged_row_answers_to_BOTH_filters(rs):
    """The merge must not cost the weapon filter its row — a daiklave you cannot find
    under Weapons is a worse answer than two rows."""
    c, _ = _linked_daiklave()
    rows = viewmod.inventory_rows(rs, c)
    assert [r.name for r in viewmod.filter_inventory(rows, "weapon")] == ["Daiklave"]
    assert [r.name for r in viewmod.filter_inventory(rows, "artifact")] == ["Daiklave"]
    assert viewmod.inventory_counts(rows) == {
        "all": 1, "weapon": 1, "armor": 0, "artifact": 1, "goods": 0, "ammunition": 0}


def test_an_ORPHANED_stat_line_stands_on_its_own(rs):
    """`from_artifact` pointing at an artifact that has been renamed or deleted must not
    silently swallow the gear row. Same failure direction `artifact_items` chose: the
    orphan is visible on its own line rather than merged into nothing and lost — and
    because nothing now claims it as a stat line, it counts as an artifact ON ITS OWN,
    which is the budget's answer too. A merge that hid it would make it free.
    """
    c, _ = _linked_daiklave()
    c.artifacts.clear()
    rows = viewmod.inventory_rows(rs, c)
    assert [(r.name, set(r.kinds)) for r in rows] == [("Daiklave", {"weapon", "artifact"})]
    assert rows[0].linked_list_name == ""
    assert viewmod.inventory_counts(rows)["artifact"] == 1


def test_an_UNLINKED_gear_row_sharing_a_name_is_still_its_own_row(rs):
    """The merge keys on `from_artifact`, not on the name. A player who owns the
    artifact and separately hand-enters a same-named weapon has two objects as far as
    the budget is concerned (`artifact_items` charges both), and the inventory must not
    hide one of them behind the other."""
    c, _ = _linked_daiklave()
    c.weapons.append(Weapon(name="Daiklave", artifact_rating=2))   # no from_artifact
    rows = viewmod.inventory_rows(rs, c)
    assert len(rows) == 2
    assert viewmod.inventory_counts(rows)["artifact"] == 2


def test_a_purchased_artifact_says_so(rs):
    """Provenance rides along (decision 0017), because "which of these did the
    Background pay for" is a question the inventory is the natural place to answer."""
    from exalted_builder.engine import artifacts as artifactsmod
    c = Character(id="p", exalt_type="Solar", caste="dawn", essence_rating=2)
    c.artifacts.append(ArtifactEntry(name="Bought Blade", rating=2,
                                     acquired=artifactsmod.ACQUIRED_PURCHASED))
    c.artifacts.append(ArtifactEntry(name="Heirloom", rating=2))
    rows = viewmod.inventory_rows(rs, c)
    assert [(r.name, r.acquired) for r in rows] == [
        ("Bought Blade", "purchased"), ("Heirloom", "background")]


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_panel_lists_everything_with_its_filters(user) -> None:
    await user.open('/inventory')
    await user.should_see("Inventory (6) · showing Everything (6)")
    await user.should_see("Weapon (3)")
    await user.should_see("Artifact (2)")
    await user.should_see("Goods (1)")
    await user.should_see("Fine clothes")
    await user.should_see("×20")               # the arrow stack


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_a_filter_narrows_the_list(user) -> None:
    """The binding test: the filter has to be wired to the panel, not merely computed.
    Clicking Goods must drop the weapons off the list."""
    def _names() -> set[str]:
        # ⚠ Scoped to the inventory's own rows by MARKER. The per-type editors below
        # list the same items, so `should_not_see("Buff Jacket")` after a filter click
        # asserts against the Armor panel and passes whatever the filter did.
        return {e.text for e in user.client.elements.values()
                if "inv-row" in getattr(e, "_markers", [])}

    await user.open('/inventory')
    assert "Buff Jacket" in _names()
    user.find("Goods (1)").click()
    await user.should_see("showing Goods (1)")
    assert _names() == {"Fine clothes"}
    user.find("Weapon (3)").click()
    await user.should_see("showing Weapon (3)")
    assert _names() == {"Daiklave", "Long Bow", "Frog Crotch Arrow"}
    user.find("Everything (6)").click()
    await user.should_see("showing Everything (6)")
    assert len(_names()) == 6


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_gear_tab_holds_every_owned_thing_in_one_place(user) -> None:
    """The point of the 2026-08-13 split: one tab for possessions. Weapons, armour and
    goods came off the Edit tab and artifacts off Advantages, because an artifact whose
    STATS lived on one tab and whose BUDGET lived on another is what let a daiklave be
    entered and charged twice.

    Asserts every panel is present together — a move that dropped one on the floor
    would otherwise be invisible until someone went looking for it in the browser.
    """
    await user.open('/inventory')
    for panel in ("Inventory", "Weapons", "Armor", "Goods", "Artifacts",
                  "Prices — services & upkeep"):
        await user.should_see(panel)


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_edit_tab_no_longer_carries_equipment(user) -> None:
    """The negative control for the move. Without it the panels could have been COPIED
    rather than moved and every assertion above would still pass — with two surfaces
    editing one list, which is the bug the split exists to prevent."""
    await user.open('/blank')
    await user.should_see("Attributes")           # the Edit tab is intact…
    await user.should_not_see("Add weapon")       # …and no longer sells gear
    await user.should_not_see("Add goods")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_each_row_carries_its_OWN_editor(user) -> None:
    """The three per-kind panels are gone (2026-08-13, the human's call: "the worst part
    of the three extra panels — the three extra panels"). An inventory that lists
    everything, beside panels that edit the same objects, is four surfaces for one job —
    and only the list could show a daiklave as both weapon and artifact.

    Each row now expands to the editor for ITS kind, reached through `row.list_name` /
    `row.index`, which is what those fields on the view exist for.
    """
    from nicegui import ui as _ui
    await user.open('/inventory')
    await user.should_see("Inventory")
    # Weapon stats, armour stats and a goods price all reachable from the one list.
    labels = {e.text for e in user.client.elements.values() if isinstance(e, _ui.label)}
    assert any("Soak" in t for t in labels), "no armour editor in the inventory"
    assert any("Acc" in t for t in labels), "no weapon editor in the inventory"
    # …and the panels that used to hold them are not also on the page. Probed with the
    # armour panel's full title: "Goods" and "Weapons" survive as a row TAG and a filter
    # chip, so a bare word cannot tell a deleted panel from live UI — the negative
    # control has to name something only the panel said.
    assert "Armor (sets soak)" not in labels


def test_the_ARMOUR_side_of_the_merge_works_too(rs):
    """The merge loops over weapons AND armour, but every other test here exercises the
    weapon half. The Armor of Aquatic Puissance (Savage Seas p.124) is the catalogue's
    first armour-side merge, so the shape now has real content behind it and a bug here
    would be invisible until someone owned one.

    ⚠ Also pins the SIGN: `mobility_penalty` is stored negative, and the stat line must
    render it as the printed -2, not +2.
    """
    from exalted_builder.engine import artifacts as artifactsmod
    c = Character(id="am", exalt_type="Solar", caste="dawn", essence_rating=2)
    key = artifactsmod.item_key(artifactsmod.SOURCE_ARTIFACT, "Armor of Aquatic Puissance")
    c.artifacts.append(ArtifactEntry(name="Armor of Aquatic Puissance", rating=4))
    c.armor.append(Armor(name="Armor of Aquatic Puissance", soak_lethal=10, soak_bashing=12,
                         mobility_penalty=-2, fatigue=1, artifact_rating=4,
                         attunement=8, from_artifact=key))
    rows = viewmod.inventory_rows(rs, c)
    assert len(rows) == 1
    row = rows[0]
    assert set(row.kinds) == {"artifact", "armor"}
    assert (row.list_name, row.index) == ("artifacts", 0)
    assert (row.linked_list_name, row.linked_index) == ("armor", 0)
    assert "Soak" in row.detail and "Mob-2" in row.detail, row.detail
    assert viewmod.inventory_counts(rows) == {
        "all": 1, "weapon": 0, "armor": 1, "artifact": 1, "goods": 0, "ammunition": 0}


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_a_merged_row_carries_BOTH_editors(user) -> None:
    """The binding test for the merge, and the reason it needs one: the stat line no
    longer has a row of its own, so if the merged row does not render the linked editor
    the weapon's stats become UNEDITABLE — a regression the pure view tests cannot see,
    because the view is right and the panel is what dropped it.

    Names the surface the merge produces, not the helper: `inventory_rows` returning a
    good `linked_index` proves nothing about whether `build_gear` reads it.
    """
    from nicegui import ui as _ui
    await user.open('/inventory-merged')
    await user.should_see("Inventory")
    names = [e.text for e in user.client.elements.values()
             if "inv-row" in getattr(e, "_markers", [])]
    assert names == ["Daiklave"], names          # one object, one row
    labels = {e.text for e in user.client.elements.values() if isinstance(e, _ui.label)}
    assert any("Acc" in t for t in labels), "the stat line lost its editor in the merge"
    await user.should_see("Stat line")
    await user.should_see("Artifact ••")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_merged_row_is_reachable_under_both_filters(user) -> None:
    """The merge must not cost the object a filter. Clicking Weapon and clicking
    Artifact must each land on the same single row."""
    def _names() -> set[str]:
        return {e.text for e in user.client.elements.values()
                if "inv-row" in getattr(e, "_markers", [])}

    await user.open('/inventory-merged')
    user.find("Weapon (1)").click()
    await user.should_see("showing Weapon (1)")
    assert _names() == {"Daiklave"}
    user.find("Artifact (1)").click()
    await user.should_see("showing Artifact (1)")
    assert _names() == {"Daiklave"}


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_shop_filters_by_type(user) -> None:
    """The Buy dialog spans four catalogues, which is a wall of names without a type
    filter — the text box only helps someone who already knows what to type, which is
    not the person browsing a shop."""
    from nicegui import ui as _ui
    await user.open('/inventory')
    user.find(marker="buy-button").click()
    await user.should_see("Buy")
    dialog = next(e for e in user.client.elements.values() if isinstance(e, _ui.dialog))
    chips = {b.text for b in dialog.descendants() if isinstance(b, _ui.button)}
    assert any(c.startswith("Everything (") for c in chips), chips
    assert any(c.startswith("Weapon (") for c in chips), chips
    assert any(c.startswith("Armour (") for c in chips), chips
    assert any(c.startswith("Goods (") for c in chips), chips
