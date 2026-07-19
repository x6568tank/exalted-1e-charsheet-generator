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


def _background_options(user: User) -> set:
    """All option labels offered by the editor's Background selects."""
    opts: set = set()
    for e in user.client.elements.values():
        if isinstance(e, Select) and e._props.get('label') == 'Background':
            options = e._props.get('options') or []
            for o in options:
                opts.add(o.get('label') if isinstance(o, dict) else o)
    return opts


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_db_editor_offers_breeding_not_solar(user: User) -> None:
    # a Dragon-Blooded editor autofills Breeding/Connections and drops Contacts;
    # a Solar editor does the opposite. (The harness characters carry a Background
    # row so the autofill Select renders.)
    await user.open('/db')
    db_opts = _background_options(user)
    assert "Breeding" in db_opts and "Connections" in db_opts
    assert "Contacts" not in db_opts

    await user.open('/custom')
    solar_opts = _background_options(user)
    assert "Contacts" in solar_opts
    assert "Breeding" not in solar_opts


def _has_accent(user: User, color: str) -> bool:
    """True if any rendered element carries `color` in its inline style — how the
    per-splat accent (headings, owned nodes) reaches the DOM."""
    for e in user.client.elements.values():
        style = getattr(e, "_style", {}) or {}
        if any(color in str(v) for v in style.values()):
            return True
    return False


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_dragonblooded_picker_renders_red(user: User) -> None:
    # the charm-tree picker builds for a Dragon-Blooded character (red palette),
    # applying the DB red accent rather than the Solar gold.
    await user.open('/dbpicker')
    await user.should_see("Live Validation")
    assert _has_accent(user, "#8a1a1a")             # DB red accent
    assert not _has_accent(user, "#8a5a1a")         # not the Solar gold


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_db_picker_shows_standard_path_banner(user: User) -> None:
    # a Dragon-Blooded with no Immaculate Charm is on the standard 7-Charm path
    await user.open('/dbpicker')
    await user.should_see("Standard path")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_db_picker_shows_immaculate_path_banner(user: User) -> None:
    # holding a Dragon-style (Immaculate) Charm flips the banner to the Immaculate path
    await user.open('/dbpicker-immaculate')
    await user.should_see("Immaculate path")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_dragonblooded_sheet_renders_red(user: User) -> None:
    # the read-only sheet themes from the SheetView's exalt type
    await user.open('/dbsheet')
    await user.should_see("Cathak")
    assert _has_accent(user, "#8a1a1a")             # DB red accent, not Solar gold


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_changing_exalt_type_rethemes_chrome_live(user: User) -> None:
    # changing the Exalt-type dropdown in the full builder must re-paint the header
    # chrome (red for Dragon-Blooded) live, without a tab switch or reload.
    await user.open('/builder')
    assert _has_accent(user, "#8a5a1a")             # starts on the Solar gold header
    sels = [e for e in user.client.elements.values() if isinstance(e, Select)]
    esel = next(s for s in sels if s._props.get('label') == 'Exalt type')
    esel.set_value("Dragon-Blooded")
    assert _has_accent(user, "#8a1a1a")             # header now the DB red, live
