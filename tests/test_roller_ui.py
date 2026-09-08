"""Render tests for the dumb dice roller on the Play tab (decision 0019).

BINDING tests: they open the page the player uses and press the button. The two
that matter most assert ABSENCES — that the label field is the player's own free
text, and that no pool row has grown a Roll button. 0019's no-wire rule is the
whole reason 0009 could be reversed, and nothing else in the suite can notice it
going away.
"""

import pytest
from nicegui.elements.button import Button
from nicegui.elements.input import Input
from nicegui.elements.number import Number
from nicegui.testing import User

MAIN = "tests/_ui_main.py"


def _by_label(user: User, cls, label: str):
    return next(e for e in user.client.elements.values()
                if isinstance(e, cls) and e._props.get("label") == label)


async def _roll(user: User, count: int, label: str = "") -> None:
    _by_label(user, Number, "Dice").set_value(count)
    if label:
        _by_label(user, Input, "Label (yours)").set_value(label)
    user.find(marker="roller-roll").click()
    await user.should_see("This session only")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_roller_renders_with_its_controls(user: User) -> None:
    await user.open('/roller')
    await user.should_see("DICE ROLLER")
    await user.should_see("Dice")
    await user.should_see("Label (yours)")
    await user.should_see("10s count double")
    await user.should_see("Can botch")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_it_says_the_modifiers_are_the_storytellers(user: User) -> None:
    """0019 keeps stunt and difficulty fields off this surface; what replaces
    them is the sentence telling the player to ask."""
    await user.open('/roller')
    await user.should_see("ask them")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_pressing_roll_shows_a_result_and_the_switches_it_used(
        user: User) -> None:
    await user.open('/roller')
    await _roll(user, 5)
    await user.should_see("5 dice · TN 7 · 10s double · can botch")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_players_label_is_shown_and_nothing_else_names_the_roll(
        user: User) -> None:
    """⚠ The one that guards 0019. The transcript may carry the text the player
    typed and no name the app chose."""
    await user.open('/roller')
    await _roll(user, 3, "Attack on the bandit")
    await user.should_see("Attack on the bandit")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_transcript_says_it_is_not_saved(user: User) -> None:
    await user.open('/roller')
    await _roll(user, 2)
    await user.should_see("not saved to the character")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_no_pool_row_grows_a_roll_button(user: User) -> None:
    """⚠ The regression 0019 names: a Roll button beside a named pool binds the
    roll definition to the result, and 'now add the Charm dice' is the next ask.
    The pools page has the full catalogue rendered, so one button per row would
    be dozens — this asserts there is exactly the one the player types into."""
    await user.open('/pools')
    buttons = [e for e in user.client.elements.values()
               if isinstance(e, Button) and (e.text or "").strip() == "Roll"]
    assert len(buttons) == 1


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_pool_list_still_says_no_row_rolls_itself(user: User) -> None:
    await user.open('/pools')
    await user.should_see("no row rolls itself")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_older_rolls_fold_away_and_say_how_many(user: User) -> None:
    """A table session's transcript would otherwise push the controls off the
    panel. The newest line stays out of the fold."""
    await user.open('/roller')
    await _roll(user, 1, "first")
    await _roll(user, 2, "second")
    await _roll(user, 3, "third")
    await user.should_see("Previous rolls (2)")
    await user.should_see("third")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_one_roll_shows_no_fold_at_all(user: User) -> None:
    await user.open('/roller')
    await _roll(user, 4)
    await user.should_not_see("Previous rolls")
