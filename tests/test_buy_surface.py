"""The Buy surface — one shop over every priced catalogue.

The human's unification of 2026-08-13: "Add weapon" / "Add armor" / "Add goods" opened
the same dialog against three catalogues, which is three shops. This is one.

Two rules it must not break, both of them decisions:

  * **services are never bought** (ruling 2026-08-13) — the price tables' upkeep,
    events, commissions and rentals are a reference list, not inventory;
  * **artifacts are sold only in play** (decision 0017) — the Artifact Background is the
    pre-game channel, "the number of dots… the character must spend TO START THE GAME
    OWNING one of these" (core p.342), and cash is the in-play one. A shop that offered
    them at chargen would be the hole that decision closes.
"""

import pytest
from nicegui import ui as _ui
from nicegui.testing import User

MAIN = "tests/_ui_main.py"


def _offered(user: User) -> set[str]:
    """Row names inside the OPEN dialog. ⚠ Scoped to the dialog's descendants: the Gear
    tab lists the same item names in the inventory and the per-kind editors behind it,
    so a bare `should_not_see` asserts against the wrong widget and passes regardless."""
    dialog = next(e for e in user.client.elements.values() if isinstance(e, _ui.dialog))
    return {d.text for d in dialog.descendants() if isinstance(d, _ui.label)}


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_one_shop_spans_weapons_armour_and_goods(user: User) -> None:
    await user.open('/inventory')
    user.find(marker="buy-button").click()
    await user.should_see("Buy")
    offered = _offered(user)
    assert "Daiklave" in offered           # weapons
    assert "Buff Jacket" in offered        # armour
    assert "Fine clothes" in offered       # goods


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_shop_never_sells_a_SERVICE(user: User) -> None:
    """Upkeep and rentals are priced but not ownable — they belong to the reference
    panel, and a shop that sold "a month of stabling" would put it in the pack."""
    await user.open('/inventory')
    user.find(marker="buy-button").click()
    await user.should_see("Buy")
    offered = _offered(user)
    assert not [t for t in offered if t.startswith("Rent a mercenary")], offered
    assert not [t for t in offered if t.startswith("Staff a grand palace")], offered


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_artifacts_are_UNBUYABLE_at_chargen_and_buyable_in_play(user: User) -> None:
    """Decision 0017, enforced at the OFFER as well as the bar. The validator already
    refuses a purchased artifact at chargen; a shop that still listed one would be
    permission that reveals nothing — the mirror of the mortal-Artifact bug, where a
    granted permission moved the bar but not the offer."""
    # ⚠ Probe with an artifact that is NOT also a gear row. Twenty catalogue artifacts
    # (Daiklave, Grand Daiklave, Myrmidon Carapace…) are ALSO weapons or armour, so they
    # are offered at chargen as gear whatever this rule says — and that is correct: such
    # a row carries `artifact_rating`, so the Artifact budget counts it exactly as it
    # counts one bought with Background dots. The rule here governs the ARTIFACT
    # channel, and a probe that ignored the overlap would assert nothing.
    await user.open('/inventory')                    # CHAR_INV is unlocked
    user.find(marker="buy-button").click()
    await user.should_see("Buy")
    assert "Dragon Tear Tiara" not in _offered(user)

    await user.open('/artifact-bought')              # …and this one is locked
    user.find(marker="buy-button").click()
    await user.should_see("Buy")
    assert "Dragon Tear Tiara" in _offered(user)


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_buying_an_artifact_in_play_is_NOT_charged_to_the_background(user: User) -> None:
    """The buy path for decision 0017's second channel. CHAR_ARTIFACT_BOUGHT is locked,
    holds Artifact •• and one Background-funded artifact — so the budget reads 1/1 and
    must still read 1/1 after a cash purchase, with the bought item declared beside it.
    """
    await user.open('/artifact-bought')
    await user.should_see("1/1")
    user.find(marker="buy-button").click()
    await user.should_see("Buy")
    rows = [e for e in user.client.elements.values()
            if isinstance(e, _ui.label) and e.text == "Dragon Tear Tiara"
            and e._event_listeners]
    assert len(rows) == 1
    el = rows[0]
    el._handle_event({"id": el.id, "listener_id": list(el._event_listeners)[0],
                      "args": {}})
    await user.should_see("bought with Resources")
    await user.should_see("1/1")          # the Background still paid for exactly one
