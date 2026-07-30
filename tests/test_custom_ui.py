"""Render tests for the custom-content page (ui/custom.py).

The page's logic is pure and covered in tests/test_custom_content.py; what only a
render can catch is the class of bug this project has hit repeatedly — a NiceGUI
`ui.select` whose initial value is not among its options 500s at render time, and
every dropdown on this page is built from the rule set.

One route per test module state, per the harness's one-build-per-session rule: the
page mutates the RuleSet it is handed, so it gets its own in tests/_ui_main.py.
"""

import pytest
from nicegui.testing import User

MAIN = "tests/_ui_main.py"


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_page_renders_with_both_tabs(user: User) -> None:
    await user.open('/custom-content')
    await user.should_see("Custom content")
    await user.should_see("Charms")
    await user.should_see("Spells")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_library_lists_the_users_own_charms(user: User) -> None:
    await user.open('/custom-content')
    await user.should_see("House Strike")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_rejected_row_is_listed_with_its_reason(user: User) -> None:
    """The one screen that can fix a broken row must show it. `custom.orphan`
    requires a Charm that does not exist, so the loader drops it."""
    await user.open('/custom-content')
    await user.should_see("Orphan Charm")
    await user.should_see("LIBRARY PROBLEMS")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_form_renders_every_dropdown(user: User) -> None:
    """Each of these is a select built from the rule set — the render is the only
    place a bad initial value shows up."""
    await user.open('/custom-content')
    await user.should_see("Category")
    await user.should_see("Type")
    await user.should_see("Splat")
    await user.should_see("Duration")
    await user.should_see("Prerequisites")
    await user.should_see("Sorcery initiation")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_json_pane_offers_paste_and_upload(user: User) -> None:
    await user.open('/custom-content')
    await user.should_see("JSON")
    await user.should_see("Import .json")
    await user.should_see("Load")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_sheet_badges_custom_content_and_flags_a_missing_row(user: User) -> None:
    """The end of the chain: a character holding one homebrew Charm and one id that
    resolves to nothing renders both markers rather than crashing or hiding either."""
    await user.open('/custom-sheet')
    await user.should_see("House Strike")
    await user.should_see("✎")                     # homebrew marker
    await user.should_see("custom.gone-missing")   # the dead spell id, still shown
    await user.should_see("⚠")
