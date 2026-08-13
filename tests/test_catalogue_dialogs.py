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

def _pick_in_dialog(user, name: str) -> None:
    """Click the row whose name label is EXACTLY `name`, by dispatching to its own
    listener. `user.find(name).click()` matches every element CONTAINING the text —
    including input values and longer names ("Daiklave" also matches "Grand Daiklave",
    "Reaver Daiklave") — and which one it lands on varies with per-run string hashing.
    """
    rows = [e for e in user.client.elements.values()
            if isinstance(e, ui.label) and e.text == name and e._event_listeners]
    assert len(rows) == 1, f"{len(rows)} clickable labels read exactly {name!r}"
    el = rows[0]
    el._handle_event({"id": el.id, "listener_id": list(el._event_listeners)[0],
                      "args": {}})


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_shop_autofills_a_weapons_printed_stats(user) -> None:
    """Was `test_the_weapon_dialog_…`, against the per-panel dialog. Browsing moved to
    the single Buy surface on 2026-08-13 — four dialogs over four catalogues is four
    shops — so the autofill contract is asserted there now."""
    await user.open('/blank-gear')
    user.find(marker="buy-button").click()
    await user.should_see("Buy")
    _pick_in_dialog(user, "Daiklave")
    # The new row's stat summary reflects the autofilled catalogue stats (Acc+2,
    # Dmg+5L) — the existing blank row on /blank reads Acc+7, so this must be new.
    await user.should_see("Acc+2")
    await user.should_see("Dmg+5L")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_shop_can_MAKE_a_thing_as_well_as_sell_one(user) -> None:
    """The last per-panel button died here (2026-08-13). "Custom weapon" lives in the
    Buy dialog now, because a shop spanning four catalogues CAN know which list a blank
    row belongs in once you say which kind you are making — and three editor panels
    beside an inventory that already lists everything was four surfaces for one job.
    """
    await user.open('/blank-gear')
    user.find(marker="buy-button").click()
    await user.should_see("Buy")
    user.find(marker="cat-custom-weapons").click()
    # The blank row's name field is a free-text combobox (ui.select, with_input) — the
    # same shape an existing weapon row uses. /blank starts with one weapon, so the new
    # row is the LAST weapon select. The rebuild is async, so poll.
    import asyncio
    sels = []
    for _ in range(20):
        sels = [el for el in user.find(ui.select).elements
                if el.props.get("label") == "Weapon"]
        if len(sels) >= 2:
            break
        await asyncio.sleep(0.05)
    assert len(sels) >= 2, "Custom weapon did not append a second select"
    new_sel = sels[-1]
    new_sel._handle_new_value("Homebrew Lance")
    new_sel.set_value("Homebrew Lance")
    await user.should_see("Homebrew Lance")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_shop_autofills_an_armours_printed_soak(user) -> None:
    await user.open('/blank-gear')
    user.find(marker="buy-button").click()
    await user.should_see("Buy")
    _pick_in_dialog(user, "Buff Jacket")
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


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_background_dialogs_ladder_is_readable_line_by_line(user) -> None:
    """The dialog is where a RATING gets chosen, so its full text is the whole printed
    ladder — and a plain NiceGUI label collapses newlines, which ran six rungs together
    into one paragraph (human, click-through 2026-08-12). Two halves, both required: the
    text must carry blank lines BETWEEN rungs, and the label must be told to render
    them. Asserting only the string would pass against a wall of text on screen."""
    await user.open('/backgrounds-ladder-dialog')
    user.find("Add background").click()
    full = next(el for el in user.find(ui.label).elements
                if "Two allies or one significant one" in (el.text or ""))
    assert "\n\n••  " in full.text, \
        "the rungs are not separated by a blank line"
    assert "whitespace-pre-line" in full.classes, \
        "the label collapses the newlines it was given"
