"""Catalogue picker dialogs (2026-08-10).

The five "add" surfaces open a browse-before-you-choose dialog now: name + summary
with the full description collapsible, plus a "Custom" row for free-text items. These
tests drive the dialogs through the NiceGUI user harness — open the dialog, pick an
entry, and confirm the row lands with its stats autofilled; or pick Custom and get a
blank free-text row.
"""

import pytest
from nicegui import ui

MAIN = "tests/_ui_main.py"


# --------------------------------------------------------------------------- #
# Equipment (weapons / armour) on the editor
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_weapon_dialog_lists_catalogue_entries_and_autofills(user) -> None:
    await user.open('/blank')
    user.find("Add weapon").click()
    # The dialog opens with a known weapon; picking it appends a row with stats.
    user.find("Daiklave").click()
    # The new row's stat summary reflects the autofilled catalogue stats (Acc+2,
    # Dmg+5L) — the existing blank row on /blank reads Acc+7, so this must be new.
    await user.should_see("Acc+2")
    await user.should_see("Dmg+5L")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_weapon_dialog_custom_row_makes_a_blank_free_text_weapon(user) -> None:
    await user.open('/blank')
    user.find("Add weapon").click()
    user.find(marker="cat-custom").click()
    # The blank row's name field is a free-text combobox (ui.select, with_input) —
    # the same shape the existing weapon row uses. /blank starts with one weapon, so
    # the custom row is the LAST weapon select. The body rebuild is async, so poll.
    import asyncio
    sels = []
    for _ in range(20):
        sels = [el for el in user.find(ui.select).elements
                if el.props.get("label") == "Weapon"]
        if len(sels) >= 2:
            break
        await asyncio.sleep(0.05)
    assert len(sels) >= 2, "the custom weapon row did not append a second select"
    new_sel = sels[-1]
    new_sel._handle_new_value("Homebrew Lance")
    new_sel.set_value("Homebrew Lance")
    await user.should_see("Homebrew Lance")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_armor_dialog_lists_catalogue_entries_and_autofills(user) -> None:
    await user.open('/blank')
    user.find("Add armor").click()
    user.find("Buff Jacket").click()
    # A catalogue armour row carries its printed soak (3L/4B).
    await user.should_see("Soak 3L/4B")


# --------------------------------------------------------------------------- #
# Artifacts and backgrounds on the Advantages tab
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_artifact_dialog_pick_autofills_name_and_rating(user) -> None:
    await user.open('/artifacts-advantages')
    # The fixture already holds one artifact (Tattered Wings, Artifact ••), so after
    # the pick there are two rows; Echo Jewel's is the last. The body rebuild after
    # the dialog closes is async, so the count is polled rather than read once.
    user.find("Add artifact").click()
    user.find("Echo Jewel").click()
    await user.should_see("Echo Jewel")
    import asyncio
    numbers = []
    for _ in range(20):
        numbers = [el for el in user.find(ui.number).elements
                   if el.props.get("label") == "Rating"]
        if len(numbers) >= 2:
            break
        await asyncio.sleep(0.05)
    assert len(numbers) >= 2, "the pick should have added a second artifact row"
    # The fixture holds Tattered Wings (••) and the pick adds Echo Jewel (•); element
    # order is not stable, so the two ratings are checked as a set, not positionally.
    assert {n.value for n in numbers} == {2, 1}, "Echo Jewel must arrive as Artifact •"


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_background_dialog_pick_adds_a_background_row(user) -> None:
    await user.open('/merits-backgrounds')
    user.find("Add background").click()
    user.find("Allies").click()
    await user.should_see("Allies")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_locked_custom_merit_row_renders_by_name_in_play(user) -> None:
    """The play surface's "Held" dropdown must offer a custom M&F row by its name —
    a custom purchase has an empty `merit_id`, and the built options must come from
    `custom_name` or the select crashes on a value it does not offer (the build-time
    raise class)."""
    await user.open('/mf-custom-xp')
    held = [sel for sel in user.find(ui.select).elements
            if sel.props.get("label") == "Held"]
    assert held, "the play 'Held' dropdown did not render"
    options = " ".join(str(o) for o in (held[0].options or {}).values())
    assert "Bloodline trait" in options, \
        "the custom M&F row must be offerable in the play Held dropdown"
