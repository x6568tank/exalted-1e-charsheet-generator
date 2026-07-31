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
    await user.should_see("Fire Aspect")           # DB caste slot is labelled "Aspect"
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
    await user.open('/db-advantages')
    db_opts = _background_options(user)
    assert "Breeding" in db_opts and "Connections" in db_opts
    assert "Contacts" not in db_opts

    await user.open('/custom-advantages')
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
async def test_sheet_shows_charm_and_spell_descriptions(user: User) -> None:
    # the read-only sheet lists each Charm/spell with its description sub-line
    await user.open('/sheet-desc')
    await user.should_see("Fire and Stones Strike")
    await user.should_see("Adds an extra die of damage")     # the Charm's description
    await user.should_see("Death of Obsidian Butterflies")
    await user.should_see("razor-sharp obsidian")            # the spell's description


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_dragonblooded_sheet_renders_red(user: User) -> None:
    # the read-only sheet themes from the SheetView's exalt type
    await user.open('/dbsheet')
    await user.should_see("Cathak")
    await user.should_see("Fire Aspect")            # DB sheet labels the slot "Aspect"
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


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_picker_splits_abilities_from_martial_arts_styles(user: User) -> None:
    # the picker's Category dropdown is split by a toggle: ability pages vs martial-arts
    # pages. Every martial_arts:* category — including the enlightenment tree, which
    # initiates the Dragon Paths — belongs on the Martial Arts side.
    from nicegui.elements.toggle import Toggle
    await user.open('/dbpicker')
    sel = next(s for s in user.client.elements.values()
               if isinstance(s, Select) and s._props.get('label') == 'Category')
    opts = list(sel.options)
    assert "melee" in opts
    assert "martial_arts:five-dragon" not in opts    # martial arts — on the other side
    assert "martial_arts:enlightenment" not in opts

    toggle = next(t for t in user.client.elements.values() if isinstance(t, Toggle))
    toggle.set_value("styles")
    opts = list(sel.options)
    assert "martial_arts:five-dragon" in opts
    assert "martial_arts:enlightenment" in opts
    assert "melee" not in opts


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_picker_spells_page_lists_descriptions_inline(user: User) -> None:
    # the Spells page is its own toggle group (not a card under the Occult graph) and
    # prints each spell's description on the row, rather than only on hover
    from nicegui.elements.toggle import Toggle
    await user.open('/dbpicker')
    toggle = next(t for t in user.client.elements.values() if isinstance(t, Toggle))
    assert "spells" in toggle.options
    toggle.set_value("spells")
    await user.should_see("Terrestrial Circle")
    await user.should_see("Death of Obsidian Butterflies")
    await user.should_see("razor-sharp obsidian")        # description, inline
    await user.should_see("needs a Charm granting the Terrestrial Circle")   # locked reason


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_picker_circle_dropdown_swaps_the_spell_list(user: User) -> None:
    # an Abyssal reaches both tracks; the Circle dropdown picks which one circle's
    # spells are listed (sorcery Terrestrial→Celestial, then necromancy)
    from nicegui.elements.toggle import Toggle
    await user.open('/abpicker')
    next(t for t in user.client.elements.values() if isinstance(t, Toggle)).set_value("spells")
    circle = next(s for s in user.client.elements.values()
                  if isinstance(s, Select) and s._props.get('label') == 'Circle')
    assert list(circle.options) == ["Terrestrial", "Celestial", "Shadowlands", "Labyrinth", "Void"]
    await user.should_see("Death of Obsidian Butterflies")      # a Terrestrial spell
    circle.set_value("Shadowlands")
    await user.should_see("Hungry Creeping Shadow")             # a Shadowlands spell
    await user.should_not_see("Death of Obsidian Butterflies")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_sheet_hides_the_spells_panel_for_a_non_sorcerer(user: User) -> None:
    # no spells → no half-width panel saying "—"; the Charms panel takes the row
    await user.open('/dbsheet')
    await user.should_not_see("Spells (0)")
    await user.should_not_see("CHARMS & SORCERY")     # heading drops the sorcery half
    await user.should_see("Charms (0)")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_sheet_still_shows_the_spells_panel_for_a_sorcerer(user: User) -> None:
    await user.open('/sheet-desc')
    await user.should_see("Spells (1)")
    await user.should_see("CHARMS & SORCERY")   # _heading upper-cases


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_background_select_options_carry_their_descriptions(user: User) -> None:
    """The catalog descriptions must reach the rendered option dicts, which is what
    the QSelect `option` slot turns into a hover tooltip. Checked on the real page
    because `_props` is observable: writing options schedules an update that rebuilds
    them from the labels, so a naive assignment is silently discarded."""
    from exalted_builder.ui.editor import DescribedSelect
    await user.open('/custom-advantages')
    sels = [e for e in user.client.elements.values() if isinstance(e, DescribedSelect)]
    bg = next(s for s in sels if s._props.get('label') == 'Background')
    described = {o['label']: o.get('description') for o in bg._props['options']}
    assert described.get('Artifact', '').startswith('Wondrous devices')
    # Every offered Background carries one; a blank would render as a missing tooltip.
    assert all(described.values()), [k for k, v in described.items() if not v]
    # The tooltip slot itself is registered, else the descriptions are never shown.
    assert 'q-tooltip' in bg.slots['option'].template
