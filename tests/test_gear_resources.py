"""The Resources System (Exalted core p.325) as an affordability HINT.

    "Items in Exalted do not generally have a value in game-world money attached to
    them. Instead, they are rated with the number of dots in Resources a character must
    possess in order to purchase them."

    * cost LOWER than her Resources — an out-of-pocket expense; "within reason, the
      character can purchase as many of the items as she wants";
    * cost EQUAL — "a serious expense. When she buys it, she lowers her Resources rating
      by 1 until it is increased through roleplaying";
    * cost GREATER — "too expensive for her, and she cannot afford to buy it".

⚠ The human's ruling, 2026-08-12: this informs a PURCHASE and must never become a
validation of what a character OWNS, and the printed drop-by-one is NOT applied
automatically. The rule contradicts an ownership invariant in its own middle clause —
buying at cost EQUAL leaves the character holding an item that now costs more than she
has — and gear arrives as loot and gifts besides.
"""

from pathlib import Path

import pytest
from nicegui import ui

import exalted_builder
from exalted_builder import rules_db
from exalted_builder.engine import validate
from exalted_builder.models.character import BackgroundEntry, Character
from exalted_builder.ui import catalogue as cataloguemod

DATA_DIR = Path(exalted_builder.__file__).parent / "data"


@pytest.fixture(scope="module")
def rs():
    return rules_db.load_ruleset(DATA_DIR)


def _with_resources(rating: int) -> Character:
    c = Character(id="res", name="Buyer", exalt_type="Solar", caste="dawn",
                  essence_rating=2)
    if rating:
        c.backgrounds = [BackgroundEntry(name="Resources", rating=rating)]
    return c


def test_the_three_printed_cases(rs):
    c = _with_resources(2)
    assert validate.gear_affordability(c, 1) == "easy"
    assert validate.gear_affordability(c, 2) == "serious"
    assert validate.gear_affordability(c, 3) == "unaffordable"
    # Resources 0 affords nothing that carries a price — cost > rating.
    assert validate.gear_affordability(_with_resources(0), 1) == "unaffordable"


def test_gear_with_no_printed_cost_says_nothing(rs):
    """56 of the 122 catalogue rows carry no `resources_cost`, and a missing price is
    not a free item — the dialog must stay silent rather than call it affordable."""
    assert validate.gear_affordability(_with_resources(2), 0) == ""
    assert cataloguemod.gear_cost_note(0, "") == ""


def test_the_three_bows_are_the_worked_example(rs):
    """The human verified Self/Long/Composite Bow at Resources 1/2/3 against the p.330
    table (2026-08-12). Against Resources 2 they are exactly the three printed cases,
    which makes this the one test that would catch the values drifting."""
    costs = {w.name: w.resources_cost for w in rs.weapon_catalog.values()}
    assert (costs["Self Bow"], costs["Long Bow"], costs["Composite Bow"]) == (1, 2, 3)
    c = _with_resources(2)
    assert [validate.gear_affordability(c, costs[n])
            for n in ("Self Bow", "Long Bow", "Composite Bow")] == [
        "easy", "serious", "unaffordable"]


def test_resources_reads_the_highest_row_not_the_sum(rs):
    """Resources is ONE lifestyle rating. `background_rating` sums duplicate rows, which
    is right for Connections and wrong here: two rows of 2 is a character who wrote it
    down twice, not a character with 4."""
    c = _with_resources(2)
    c.backgrounds.append(BackgroundEntry(name="Resources", rating=2))
    assert validate.gear_affordability(c, 3) == "unaffordable"


def test_nothing_validates_ownership(rs):
    """The rule's own middle clause produces a character holding gear she could not now
    buy: pay 3 at Resources 3, and the book leaves her at 2 owning a 3-cost item. No
    issue may be raised for that, on either side of the lock."""
    from exalted_builder.engine import lifecycle
    from exalted_builder.models.character import Weapon
    c = _with_resources(2)
    c.attributes = {a: 1 for a in c.attributes}
    c.weapons = [Weapon(name="Composite Bow", accuracy=0, damage=5, resources_cost=3)]
    assert not [i for i in validate.validate_chargen(rs, c) if "resource" in i.code]
    lifecycle.lock_chargen(c, rs)
    assert not [i for i in validate.validate(rs, c) if "resource" in i.code]


# --------------------------------------------------------------------------- #
# The dialog itself — the half an engine test cannot see
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_weapon_dialog_prices_each_row_against_this_character(user) -> None:
    """The point of the feature: the cost is answered for THIS character, at the moment
    of choosing. Asserted on the summary labels rather than the page text, so a note
    that never reached a row cannot pass."""
    await user.open('/gear-resources')
    user.find("Add weapon").click()
    texts = [el.text or "" for el in user.find(ui.label).elements]
    joined = "\n".join(texts)
    assert "Resources ● — within your means" in joined, "the under-cost case is missing"
    assert "Resources ●● — a serious expense (buying it drops Resources by 1)" in joined
    assert "Resources ●●● — beyond your Resources" in joined


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_an_unaffordable_row_is_faded_but_still_pickable(user) -> None:
    """A hint, never a gate (human's ruling): the sheet is a tracker and a character can
    be GIVEN what she could not buy, so the row fades and still picks. A test that only
    checked the fade would pass against a dialog that refused the click."""
    await user.open('/gear-resources')
    user.find("Add weapon").click()
    faded = [el for el in user.client.elements.values()
             if isinstance(el, ui.column) and "opacity-50" in " ".join(el.classes)]
    assert faded, "no row faded though the character cannot afford a Composite Bow"
    user.find("Composite Bow").click()
    await user.should_see("Composite Bow")
