"""Render tests for the Sidereal College UI — the sheet panel (ui/app.py) and the
XP tab's buy/raise rows (ui/xp.py), via the NiceGUI User simulation.

These exist because the College engine landed well before any UI could reach it,
and because a `ui.select` whose value is not in its options raises at render time
rather than in a unit test (see CLAUDE.md's NiceGUI 3.x gotcha). One route per
test, per tests/test_gm.py's note."""

import pytest
from nicegui.testing import User

MAIN = "tests/_ui_main.py"


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_sheet_shows_the_college_panel(user: User) -> None:
    await user.open('/sidsheet')
    await user.should_see("Astrological Colleges")
    await user.should_see("★ The Shield")        # own Maiden's house is marked
    await user.should_see("The Gull")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_xp_tab_offers_college_buy_and_raise(user: User) -> None:
    await user.open('/sidxp')
    await user.should_see("Astrological Colleges")
    await user.should_see("Raise college")
    await user.should_see("New college")
    await user.should_see("5 XP")                # flat new_college cost (p.265)
