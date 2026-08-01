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
async def test_colleges_are_bought_on_their_own_dot_track_in_play(user: User) -> None:
    """Was the XP tab's separate College card, which duplicated the editor's panel.
    Decision 0013 deleted the duplicate: a College is now bought by clicking its dots,
    and the 0→1 step routes to `learn_college` (flat p.265 cost) while the rest scale.
    The engine half is pinned in test_advancement; this is the panel surviving."""
    await user.open('/sidxp')
    await user.should_see("Astrological Colleges")
