"""Render tests for the Storyteller's batch roll on the party page (0019).

BINDING tests: they open the page, type counts and press Roll. The one that
matters asserts an ABSENCE — that no roster row offers a NAMED roll to fill its
count from. That is the wire decision 0019 rejects, and with six rows on screen
it is the convenience a later session will reach for.
"""

import pytest
from nicegui.elements.input import Input
from nicegui.elements.number import Number
from nicegui.testing import User

MAIN = "tests/_ui_main.py"


def _numbers(user: User, label: str):
    return [e for e in user.client.elements.values()
            if isinstance(e, Number) and e._props.get("label") == label]


async def _roll(user: User, *counts: int, name: str = "") -> None:
    if name:
        next(e for e in user.client.elements.values()
             if isinstance(e, Input) and e._props.get("label") == "Name this roll"
             ).set_value(name)
    for box, count in zip(_numbers(user, "Dice"), counts):
        box.set_value(count)
    user.find(marker="batch-roll").click()


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_panel_lists_a_row_per_party_member(user: User) -> None:
    await user.open('/gm-batch')
    await user.should_see("BATCH ROLL")
    await user.should_see("Yarak")
    await user.should_see("Taban")
    await user.should_see("Name this roll")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_rolling_folds_the_batch_under_its_name(user: User) -> None:
    """The log collapses to the batch's name; the rows live inside it."""
    await user.open('/gm-batch')
    await _roll(user, 5, 3, name="Join Battle")
    await user.should_see("Join Battle")
    await user.should_see("2 rolls · TN 7")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_each_row_is_labelled_with_whose_dice_they_were(user: User) -> None:
    """⚠ A CHARACTER's name on a result asserts nothing about a pool. A ROLL's
    name would, and that is what 0019 forbids — see the module docstring."""
    await user.open('/gm-batch')
    await _roll(user, 4, 4, name="Perception check")
    await user.should_see("Yarak")
    await user.should_see("Taban")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_row_left_at_zero_sits_the_batch_out(user: User) -> None:
    await user.open('/gm-batch')
    await _roll(user, 6, 0, name="Only one of them")
    await user.should_see("1 roll · TN 7")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_rolling_with_no_dice_typed_warns_instead_of_rolling(user: User) -> None:
    await user.open('/gm-batch')
    user.find(marker="batch-roll").click()
    await user.should_see("No dice typed")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_no_row_offers_a_named_roll_to_fill_its_count(user: User) -> None:
    """⚠ THE test in this file. A select of roll names beside each row — "Join
    Battle for everyone" — is the wire 0019 rejects by name: the app would be
    claiming to know what every sheet is rolling, and Charm dice is the next ask.
    The counts are typed, so the only controls on a row are a number and a label."""
    await user.open('/gm-batch')
    from nicegui.elements.select import Select
    selects = [e for e in user.client.elements.values() if isinstance(e, Select)]
    labels = {(s._props.get("label") or "") for s in selects}
    assert not [l for l in labels if "roll" in l.lower() or "pool" in l.lower()]
    await user.should_see("Stunts, difficulty and Charms are yours")
