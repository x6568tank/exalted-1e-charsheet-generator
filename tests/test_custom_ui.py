"""Render tests for the custom-content page (ui/custom.py).

The page's logic is pure and covered in tests/test_custom_content.py; what only a
render can catch is the class of bug this project has hit repeatedly — a NiceGUI
`ui.select` whose initial value is not among its options 500s at render time, and
every dropdown on this page is built from the rule set.

One route per test module state, per the harness's one-build-per-session rule: the
page mutates the RuleSet it is handed, so it gets its own in tests/_ui_main.py.
"""

import json

import pytest
from nicegui.testing import User

MAIN = "tests/_ui_main.py"


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_page_renders_with_every_kind_tab(user: User) -> None:
    await user.open('/custom-content')
    await user.should_see("Custom content")
    await user.should_see("Charms")
    await user.should_see("Spells")
    await user.should_see("Rituals")


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
async def test_the_prerequisite_dropdown_excludes_virtual_path_rows(user: User) -> None:
    """The 60 Dragon-King Path powers are projected into the charm catalogue as
    VIRTUAL rows so Combos and the sheet can name them — but they are never
    learnable, so offering one as a custom-Charm prerequisite would build a Charm
    nobody can ever learn (`charm_matches_splat` rejects virtual rows first)."""
    from nicegui import ui as _ui

    await user.open('/custom-content')
    prereq = next(e for e in user.client.elements.values()
                  if isinstance(e, _ui.select) and e.props.get("label") == "Prerequisites")
    assert not any(str(opt).startswith("dk.path.") for opt in prereq.options)
    assert "dk.path.dk.celestial-air.dot1" not in prereq.options


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_category_change_redraws_the_prerequisite_list(user: User) -> None:
    """The list is this tree's Charms. ⚠ The Category select stored its value and
    redrew nothing, thus a list built from it stayed on the first tree."""
    from nicegui import ui as _ui

    def prerequisites():
        return next(e for e in user.client.elements.values()
                    if isinstance(e, _ui.select) and e.props.get("label") == "Prerequisites")

    await user.open('/custom-content')
    assert "solar.melee.excellent-strike" in prerequisites().options

    category = next(e for e in user.client.elements.values()
                    if isinstance(e, _ui.select) and e.props.get("label") == "Category")
    category.set_value("archery")
    # ⚠ The redraw runs after the event loop turns. `should_see("Prerequisites")`
    # returns at once on the OLD select, thus wait for the list itself.
    import asyncio
    for _ in range(40):
        if "solar.archery.wise-arrow" in prerequisites().options:
            break
        await asyncio.sleep(0.05)

    assert "solar.archery.wise-arrow" in prerequisites().options
    assert "solar.melee.excellent-strike" not in prerequisites().options


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_json_pane_offers_paste_and_upload(user: User) -> None:
    await user.open('/custom-content')
    await user.should_see("JSON")
    await user.should_see("Import .json")
    await user.should_see("Load")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_export_downloads_every_charm_on_disk(user: User) -> None:
    """The rejected row goes too. It is on disk, and the receiver can fix it."""
    await user.open('/custom-content')
    await user.should_see("House Strike")

    user.find("custom-export").click()
    response = await user.download.next()

    ids = {r["id"] for r in json.loads(response.text)}
    assert ids == {"custom.house-strike", "custom.orphan"}


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_export_and_the_json_pane_follow_the_kind_tab(user: User) -> None:
    """After a switch to Rituals, the export gives the ritual and the pane shows a
    ritual row. ⚠ A button or a pane that reads the kind at build time still gives
    Charms here. The pane did give a SPELL row for a ritual until 2026-09-12."""
    from nicegui import ui as _ui

    await user.open('/custom-content')
    tabs = next(e for e in user.client.elements.values() if isinstance(e, _ui.tabs))
    tabs.set_value("ritual")
    await user.should_see("Salt Road Whisper")

    pane = json.loads(next(e for e in user.client.elements.values()
                           if isinstance(e, _ui.code)).content)
    assert "level" in pane and "circle" not in pane

    user.find("custom-export").click()
    response = await user.download.next()

    assert [r["id"] for r in json.loads(response.text)] == ["custom.salt-road-whisper"]


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_charm_form_shows_the_tree_it_joins(user: User) -> None:
    """The preview panel is on the Charms kind and names the tree. ⚠ Its graph
    container has a fixed height: a container with none draws at zero, and a
    render test still passes (docs: harness-has-no-layout)."""
    from nicegui import ui as _ui

    await user.open('/custom-content')
    await user.should_see("WHERE IT GOES — MELEE")
    graph = [e for e in user.client.elements.values() if e.props.get("id") == "custom-graph"]
    assert graph and "h-[28rem]" in graph[0].classes

    tabs = next(e for e in user.client.elements.values() if isinstance(e, _ui.tabs))
    tabs.set_value("ritual")
    await user.should_see("Salt Road Whisper")
    await user.should_not_see("WHERE IT GOES")


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


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_ritual_library_lists_and_forms(user: User) -> None:
    """The Rituals kind (2026-08-28). ⚠ Its fields are TEXT, not numbers — a ritual
    prints no stat block, so a cost reads "1 mote or one Willpower" (p.148-150).

    ⚠ This is also the guard for the LIBRARY refresh on a kind switch. The list
    filters on the active kind at render time and `_switch_kind` repainted only the
    form, so the column kept the previous kind's rows — seeing the ritual here is
    what proves the left column moved with the tab."""
    from nicegui import ui as _ui

    await user.open('/custom-content')
    tabs = next(e for e in user.client.elements.values() if isinstance(e, _ui.tabs))
    tabs.set_value("ritual")
    await user.should_see("Salt Road Whisper")
    await user.should_see("Level")
    await user.should_see("Roll")
    await user.should_see("Resources")
