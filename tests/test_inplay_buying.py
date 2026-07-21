"""The chargen tabs become XP shops once chargen is locked.

Edit and XP share one slot on the tab bar (build the baseline, then spend against
it), while Charms and Combos stay put and switch mode: free picks before the lock,
priced purchases through engine.advancement after it.
"""

import pytest
from nicegui.testing import User

from exalted_builder.ui import builder

MAIN = "tests/_ui_main.py"


# ---- tab bar (pure) ------------------------------------------------------- #

def test_edit_tab_is_chargen_only():
    tabs = builder.visible_tabs(locked=False)
    assert "Edit" in tabs and "XP" not in tabs


def test_xp_tab_replaces_edit_once_locked():
    tabs = builder.visible_tabs(locked=True)
    assert "XP" in tabs and "Edit" not in tabs


def test_charms_and_combos_are_on_the_bar_in_both_stages():
    for locked in (False, True):
        assert {"Charms", "Combos"} <= set(builder.visible_tabs(locked))


def test_locking_moves_the_editor_tab_to_xp():
    assert builder.resolve_tab("Edit", locked=True) == "XP"
    assert builder.resolve_tab("XP", locked=False) == "Edit"


def test_resolve_tab_leaves_a_still_visible_tab_alone():
    assert builder.resolve_tab("Charms", locked=True) == "Charms"
    assert builder.resolve_tab("Play", locked=False) == "Play"


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_finish_and_lock_swaps_the_edit_tab_for_xp(user: User) -> None:
    # the whole point: XP stops being a bolted-on extra tab and takes Edit's place
    from nicegui.elements.tabs import Tab
    await user.open('/builder-lock')
    named = {t.props.get('name'): t for t in user.client.elements.values() if isinstance(t, Tab)}
    assert named["Edit"].visible and not named["XP"].visible
    user.find("Finish & Lock").click()
    await user.should_see("VALIDATION")      # locking lands on the Sheet
    assert named["XP"].visible and not named["Edit"].visible


# ---- the picker in play --------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_locked_picker_shows_xp_instead_of_the_chargen_pool(user: User) -> None:
    # in play the budget on show is experience, not the chargen Charm pool
    await user.open('/inplay-picker')
    await user.should_see("50 XP available")
    await user.should_not_see("Charms: 2 · Spells: 0")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_selecting_a_charm_in_play_buys_it_with_xp(user: User) -> None:
    # the detail card sells instead of toggling, and the purchase runs through the
    # engine: the price leaves the XP pool (50 - 8) and the Charm becomes Known.
    await user.open('/inplay-picker-buy')
    await user.should_see("Buy · 8 XP")      # Melee is a Dawn caste ability → 8, not 10
    user.find("Buy · 8 XP").click()
    await user.should_see("Known.")
    await user.should_see("42 XP available")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_known_charm_offers_no_remove_in_play(user: User) -> None:
    # nothing is droppable post-lock: the only refund is undo on the XP tab
    await user.open('/inplay-picker-known')
    await user.should_see("Known.")
    await user.should_not_see("Remove")


# ---- the Combos tab in play ----------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_locked_combos_tab_buys_whole_combos(user: User) -> None:
    await user.open('/inplay-combos')
    await user.should_see("Buy a Combo")
    await user.should_not_see("New Combo name")     # the chargen assemble-in-place form


# ---- the XP tab no longer sells Charms ------------------------------------ #

@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_xp_tab_no_longer_has_a_charm_picker(user: User) -> None:
    # Charms/spells/Ox-Body/Combos moved to the tabs that browse them
    await user.open('/xp')
    await user.should_see("Raise a Trait")
    await user.should_not_see("Learn Charm")
    await user.should_not_see("Buy Ox-Body")
    await user.should_not_see("Add Combo")
