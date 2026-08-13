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


def test_a_granted_stat_line_is_not_a_SECOND_artifact_in_the_inventory(rs):
    """The inventory reads `artifact_items`, the same enumeration the budget reads, so
    a weapon row that is the stat line of a standalone artifact is tagged once. Reading
    `artifact_rating` directly instead would show two artifacts where the budget counts
    one — the inventory and the validator must not disagree about what is owned."""
    from exalted_builder.engine import artifacts as artifactsmod
    c = Character(id="g", exalt_type="Solar", caste="dawn", essence_rating=2)
    key = artifactsmod.item_key(artifactsmod.SOURCE_ARTIFACT, "Daiklave")
    c.artifacts.append(ArtifactEntry(name="Daiklave", rating=2))
    c.weapons.append(Weapon(name="Daiklave", artifact_rating=2, from_artifact=key))
    rows = viewmod.inventory_rows(rs, c)
    assert viewmod.inventory_counts(rows)["artifact"] == 1
    # …and it is the standalone row that carries the artifact tag, not the stat line.
    assert [set(r.kinds) for r in rows] == [{"weapon"}, {"artifact"}]


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
