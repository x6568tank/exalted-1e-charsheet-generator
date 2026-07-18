import pytest
from nicegui.elements.select import Select
from nicegui.testing import User

MAIN = "tests/_ui_main.py"

@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_reload_with_custom_gear_renders(user: User) -> None:
    # off-catalog weapon/armor/nature must not crash the render (was a 500)
    await user.open('/custom')
    await user.should_see("Weapons")

@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_typing_custom_name_keeps_stats(user: User) -> None:
    from tests import _ui_main as M  # same process → same module object
    await user.open('/blank')
    sels = [e for e in user.client.elements.values() if isinstance(e, Select)]
    wsel = next(s for s in sels if s._props.get('label') == 'Weapon')
    wsel._handle_new_value("Homebrew Daiklave")
    wsel.set_value("Homebrew Daiklave")
    wp = M.CHAR_BLANK.weapons[0]
    assert wp.name == "Homebrew Daiklave"
    assert (wp.accuracy, wp.damage) == (7, 9)   # typed stats preserved, not zeroed


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_play_tab_renders(user: User) -> None:
    # the in-play tracker renders its sections without error
    await user.open('/play')
    await user.should_see("Health")
    await user.should_see("Limit")
    await user.should_see("Clear motes spent")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_xp_tab_shows_reduce_card(user: User) -> None:
    # the post-lock XP tab renders the new trait-reduction card
    await user.open('/xp')
    await user.should_see("Reduce a Trait")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_dragonblooded_editor_renders(user: User) -> None:
    # a Dragon-Blooded character renders the editor with the Origin dropdown and
    # DB-specific budget headers (35 ability dots, 7/6/4 attributes, pick 3 favored)
    await user.open('/db')
    await user.should_see("Origin")
    await user.should_see("Fire Caste")            # the Aspect info box
    await user.should_see("35 dots")               # DB Dynastic ability budget
    await user.should_see("prioritise 7/6/4")
