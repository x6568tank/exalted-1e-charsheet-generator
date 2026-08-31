"""Mundane goods and the services price list — Manacle and Coin p.123.

The human's ruling of 2026-08-13 is the whole shape of this file: the price tables hold
two different kinds of thing, and only one of them is inventory.

  * `goods` — something the character then HOLDS (clothes, jewelry, an animal, an
    estate). Ownable, and they land in `Character.gear`.
  * `service` — upkeep, an event, a commission, a rental. Priced, never owned, shown as
    a REFERENCE price list. A character does not carry a month of stabling in her pack.

⚠ The distinction is DATA (`GearType.kind`), not a name check. Nothing may decide it by
reading a row's name.
"""

from pathlib import Path

import pytest

import exalted_builder
from exalted_builder import rules_db
from exalted_builder.models.character import BackgroundEntry, Character, GearEntry

DATA_DIR = Path(exalted_builder.__file__).parent / "data"


@pytest.fixture(scope="module")
def rs():
    return rules_db.load_ruleset(DATA_DIR)


def test_the_price_table_loaded(rs):
    """93 rows: 43 off M&C p.123, 13 Everyday Wonders p.125, 22 phase-1, 15 phase-2.

    2026-08-15, the phase-1 scan of the never-opened books — 20 off Kingdom of Halta
    pp.89-93 and 2 off Bastions of the North (the ice weasel fur p.39, the glider
    p.98). Five printed entries carry TWO Resources costs each, and the rules
    authority ruled the encoding by WHY there are two (docs/status/phase-1-scan.md):
    genuinely different products split into a row apiece (cat claws 2, ground charms
    3, lucky rock 2), an open-ended "better versions cost more" tier stays ONE row at
    the defined price (hunter's shirt), and a remoteness premium stays one row priced
    OUTSIDE the region of origin (mother's moss, ice weasel fur, glider) — which is
    what the other Haltan rows already carry, per the p.89 blanket rule that costs run
    one dot lower within the Republic.

    2026-08-15, phase 2 — 9 off Scavenger Sons: the Deep-Forest Drugs (pp.32-33) and
    Southern Magical Gemstones (p.47) sections and the water shoes (p.55). The same
    three-way encoding applies: soma and the water shoes are remoteness premiums priced
    outside their region of origin, the life flowers and dreamstones are two products
    apiece and split, and bright morning stays one row at the general price because its
    higher Realm figure is a LEGALITY premium (the drug is illegal there), not a
    remoteness one. The six Marukan horse breeds (p.88) are gear rows AND adversary-roster
    templates on the rules authority's ruling. Creatures of the Wyld yielded nothing
    — see phase-2-scan.md.
    """
    gear = rs.gear_catalog
    assert len(gear) == 93
    assert sum(1 for g in gear.values() if g.kind == "goods") == 66
    assert sum(1 for g in gear.values() if g.kind == "service") == 27


def test_a_sample_of_the_page(rs):
    """Spot values, transcribed from the page rather than remembered."""
    g = rs.gear_catalog["gear.fine-camel-horse"]
    assert (g.name, g.resources_cost, g.kind) == ("Fine camel/horse", 3, "goods")
    assert g.cash == "6 minae 950 dinars"
    assert (g.source.book, g.source.page) == ("Manacle and Coin", 123)
    assert rs.gear_catalog["gear.peasant-clothes"].resources_cost == 1
    assert rs.gear_catalog["gear.imperial-jewelry"].resources_cost == 5


def test_upkeep_and_commissions_are_services_not_goods(rs):
    """The rows that would be absurd as inventory. If one of these ever flips to
    `goods` it will appear in the Add-goods dialog, which is the visible failure."""
    for gid in ("gear.staff-a-grand-palace-for-a-month",
                "gear.fodder-for-horse-per-month",
                "gear.rent-a-mercenary-company-for-a-month",
                "gear.passage-across-the-inland-sea",
                "gear.donatives-necessary-to-be-named-an-imperial-pref"):
        assert rs.gear_catalog[gid].kind == "service", gid


def test_erect_a_manse_is_reference_and_says_why(rs):
    """⚠ The row that is NOT gear at all: erecting a Manse is the construction cost of
    a BACKGROUND. It stays in the table (the page prints it) as a service, with a note
    saying where the thing itself lives — authoring it as goods would put a Manse in
    the character's pack."""
    rows = [g for g in rs.gear_catalog.values() if g.name.startswith("Erect a Manse")]
    assert len(rows) == 2
    for g in rows:
        assert g.kind == "service"
        assert "Manse Background" in g.notes


def test_the_cash_column_is_reference_text_never_arithmetic(rs):
    """M&C p.122 says outright that the Resources ladder is not linear and that
    converting it is a Storyteller judgement, so the printed jade/silver equivalents are
    stored verbatim and nothing computes with them."""
    g = rs.gear_catalog["gear.buy-an-estate"]
    assert g.cash == "7 talents 35 talents"
    assert isinstance(g.cash, str)


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_goods_section_and_the_price_list_both_render(user) -> None:
    await user.open('/goods')
    # "Goods" is a filter chip on the inventory now, not a panel of its own — the three
    # per-kind panels were folded into the inventory rows on 2026-08-13.
    await user.should_see("Inventory")
    await user.should_see("Prices — services & upkeep")
    await user.should_see("Reference only")
    # A service row is VISIBLE as a price…
    await user.should_see("Rent a mercenary company for a month")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_add_goods_dialog_offers_goods_and_NOT_services(user) -> None:
    """The binding test: the ruling is only real if the dialog refuses to sell a month
    of stabling. Asserted on the dialog, not on the catalogue — a filter that exists in
    the data and is not applied by the caller is this build's recurring bug."""
    from nicegui import ui as _ui
    await user.open('/goods')
    user.find(marker="buy-button").click()
    await user.should_see("Buy")
    # ⚠ Scoped to the DIALOG's own descendants. `should_not_see` would pass or fail on
    # the services price list rendered on the page BEHIND the dialog — the panel this
    # very feature adds — so the obvious assertion tests the wrong surface.
    dialog = next(e for e in user.client.elements.values()
                  if isinstance(e, _ui.dialog))
    offered = {d.text for d in dialog.descendants() if isinstance(d, _ui.label)}
    assert "Fine camel/horse" in offered
    assert not [t for t in offered if t.startswith("Rent a mercenary")], offered


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_picking_goods_appends_a_row_carrying_its_price(user) -> None:
    from nicegui import ui as _ui
    await user.open('/goods')
    user.find(marker="buy-button").click()
    await user.should_see("Buy")
    rows = [e for e in user.client.elements.values()
            if isinstance(e, _ui.label) and e.text == "Fine camel/horse"
            and e._event_listeners]
    assert len(rows) == 1
    el = rows[0]
    el._handle_event({"id": el.id, "listener_id": list(el._event_listeners)[0],
                      "args": {}})
    # The row shows the item and its printed cost, LABELLED — a bare dot column reads
    # as a rated trait, which a price is not.
    await user.should_see("Res •••")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_price_list_actually_shows_PRICES(user) -> None:
    """⚠ `GearType.cash` had ZERO read sites when this panel first shipped: it printed a
    name and a dot column, so a PRICE list showed no prices and the browser called it
    useless. The jade/silver equivalents are the one thing a reference panel is for —
    they exist nowhere else on the sheet.

    Also asserts the category headings, without which 25 rows are an undifferentiated
    wall, and the Manse note, which is the row that most needs explaining.
    """
    await user.open('/goods')
    await user.should_see("Rent a mercenary company for a month")
    await user.should_see("2 talents 10 talents")          # its printed cash price
    await user.should_see("Realm Expenses")                # a category heading
    await user.should_see("Ships and Property")
    await user.should_see("Manse Background")              # the Erect a Manse note


# --- p.125, the page that was column-scrambled ------------------------------- #

def test_the_everyday_wonders_landed(rs):
    """M&C p.125, parsed by `tools/parse_mc_prices.py` after the generic extractor
    interleaved the two columns into nonsense ("Burning incense Healing"). The parser
    was proved by re-reading p.123 and reproducing all 43 rows authored from that
    page's clean extraction."""
    g = rs.gear_catalog["gear.seven-bounties-paste"]
    assert (g.resources_cost, g.kind) == (3, "goods")
    assert g.category == "Everyday Wonders — Healing"
    assert g.cash == "2 bars / 6 dirhams"
    assert (g.source.book, g.source.page) == ("Manacle and Coin", 125)
    # A sacrifice is an ACT, not a thing carried.
    assert rs.gear_catalog["gear.large-animal-sacrifices"].kind == "service"


def test_created_walkaway_is_transcribed_as_printed(rs):
    """⚠ A printed oddity, not corrected: its three siblings are '… charm' and this row
    is not, and the word appears nowhere else in the book. CONFIRMED by the rules
    authority 2026-08-13 — the entry is just "Created walkaway", and whether the book
    dropped a word is unknowable from the page. Do not complete it."""
    g = rs.gear_catalog["gear.created-walkaway"]
    assert g.name == "Created walkaway"
    assert "Do not complete it" in g.notes


def test_the_seven_wonders_carry_a_RESOURCES_price_as_well_as_a_rating(rs):
    """Decision 0017 made concrete: `rating` is what the Artifact Background spends to
    START THE GAME owning it (core p.342), `resources_cost` is what cash buys in play
    (M&C p.125). They are different scales and must not be conflated — a daiklave is
    Artifact •• and Resources ••••."""
    art = {a.name.replace("\u2019", "'"): a for a in rs.artifact_catalog.values()}
    assert (art["Daiklave"].rating, art["Daiklave"].resources_cost) == (2, 4)
    assert (art["Grand Daiklave"].rating, art["Grand Daiklave"].resources_cost) == (3, 5)
    assert (art["Hearthstone Amulet"].rating,
            art["Hearthstone Amulet"].resources_cost) == (1, 3)
    priced = [a for a in rs.artifact_catalog.values() if a.resources_cost]
    assert len(priced) == 7, "only the seven wonders M&C prices"


def test_the_price_lists_scroll_area_keeps_a_definite_height() -> None:
    """⚠ A layout guard, because no render test can catch this one: the rows were in the
    DOM and `should_see` passed while the browser showed an empty panel.

    `ui.scroll_area` needs a definite height. `flex-1 min-h-0` supplies one only when the
    PARENT is a fixed-height flex column — true of the catalogue dialog's `h-[85vh]`
    card, false of this panel — and combining it with an inline height is worse than
    either alone: `flex: 1 1 0%` collapses the area to a zero basis and `min-h-0` removes
    the content floor that would have rescued it.
    """
    import inspect

    from exalted_builder.ui import gear as gearmod
    src = inspect.getsource(gearmod)
    area = src[src.index("with ui.scroll_area()"):][:200]
    assert "height:" in area, "the price list's scroll area lost its explicit height"
    assert "flex-1" not in area, (
        "flex-1 on a scroll area whose parent has no height collapses it to nothing")
