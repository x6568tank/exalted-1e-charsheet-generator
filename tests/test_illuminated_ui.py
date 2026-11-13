"""Render tests for the Cult of the Illuminated UI (Phase 4).

A `ui.select` whose value is not in its options raises at RENDER time, not in a unit
test. Each control here is a select seeded from character state.

One route per test (see tests/test_gm.py): a @ui.page route builds once per session.

These tests prove that the pages render and that the strings reach the DOM. They do
NOT prove the layout. A browser click-through is still necessary.
"""

import pytest
from nicegui.testing import User

MAIN = "tests/_ui_main.py"


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_editor_shows_the_training_camp_panel(user: User) -> None:
    """The panel is its own full-width panel between Identity and Attributes, NOT inside
    the caste-info card — that row is `items-stretch`, so putting it there stretched the
    row and left a gap under the shorter Identity panel."""
    await user.open('/ill-editor')
    await user.should_see("Training Camp & Calling")
    await user.should_see("Training camp")          # the select's own label
    await user.should_see("Kether Rock")
    # The camp's Ability floors, including the OR pair rendered as one line.
    await user.should_see("Archery or Brawl 1")
    await user.should_see("Survival 3")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_editor_shows_the_camps_free_charms_and_pair_choice(user: User) -> None:
    await user.open('/ill-editor')
    await user.should_see("Free Charms")
    await user.should_see("Ox-Body Technique")
    # The "one of the following pairs" choice, with the taken pair selected.
    await user.should_see("One of the following pairs of Charms")
    await user.should_see("Durability of Oak Meditation + Iron Skin Concentration")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_editor_shows_the_calling_and_its_abilities(user: User) -> None:
    await user.open('/ill-editor')
    await user.should_see("Calling")
    await user.should_see("Deacon")
    await user.should_see("Spy, assassin and commando")
    # The five Calling Abilities, and the discounted-Charm count.
    await user.should_see("Investigation, Larceny, Melee, Stealth, Survival")
    await user.should_see("Calling Charms")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_editor_marks_calling_abilities_on_the_abilities_panel(user: User) -> None:
    """● Caste · ✦ Favoured · ✧ Calling, and the marks concatenate — Melee is both a
    Dawn Caste Ability and a Deacon Calling Ability, so it shows ●✧."""
    await user.open('/ill-editor')
    await user.should_see("✧")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_tabernacle_editor_shows_the_style_choice_instead_of_pairs(user: User) -> None:
    """The other grant shape: "two Charms from ONE of four martial arts". Only Snake
    Style exists in the Solar data, but all four options must still render."""
    await user.open('/ill-editor-tabernacle')
    await user.should_see("The Sequestered Tabernacle")
    await user.should_see("Two Charms from one martial arts style")
    await user.should_see("Snake Style")          # the resolved value of that select
    await user.should_see("Harmonious Presence Meditation")
    # Its Ability floor differs from Kether Rock's.
    await user.should_see("Presence 3")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_sheet_lists_granted_charms_as_granted(user: User) -> None:
    """Granted Charms live outside `character.charms`, so the sheet had to be taught
    about them — the same miss Beastman Gifts had. They are labelled, because they cost
    neither a pick nor XP."""
    await user.open('/ill-sheet')
    await user.should_see("Ox-Body Technique (granted)")
    await user.should_see("Iron Skin Concentration (granted)")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_standard_solar_editor_has_no_camp_panel(user: User) -> None:
    """The panel is gated on the ORIGIN's budget, not on the splat, so an ordinary
    Solar must not grow an empty Training Camp box."""
    await user.open('/blank')
    await user.should_not_see("Training Camp & Calling")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_plain_solar_can_reach_the_illuminated_origin(user: User) -> None:
    """A Solar gets the Origin dropdown (`_SPLAT_ORIGINS` has a "Solar" key). Without
    it the origin cannot be selected in the UI while each engine test passes."""
    await user.open('/solar-origin')
    await user.should_see("Origin")
    await user.should_see("Standard")           # the default, shown as the select value
    # No camp panel yet — a standard Solar has no camps.
    await user.should_not_see("Training Camp & Calling")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_editor_renders_the_which_charms_sub_select(user: User) -> None:
    """A style choice shows a second, multi-select control for the two Charms, with
    the chosen Charms as its value.

    A multi-select puts its selected labels in the DOM (as chips), thus the label and
    the picks can be asserted."""
    await user.open('/ill-editor-tabernacle')
    await user.should_see("Which 2?")             # the sub-select's own label
    # The two Snake Charms seeded in _ui_main.py, shown as chips.
    await user.should_see("Striking Cobra Technique")
    await user.should_see("Serpentine Evasion")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_cult_dragonblooded_editor_renders_the_camp_panel_without_a_calling(
        user: User) -> None:
    """Cult p.96 gives a Dragon-Blooded a training camp but no Calling, so the panel's
    left half renders and its right half must not — an empty Calling select would be a
    control with nothing in it."""
    await user.open('/cult-db-editor')
    await user.should_see("Training Camp")
    await user.should_see("The Sequestered Tabernacle")
    await user.should_see("Walker-Among-Irises Perception")   # a fixed DB grant
    # Not even in the heading: the panel names what it contains.
    await user.should_not_see("Calling")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_flat_pool_choice_renders_one_control_carrying_its_picks(
        user: User) -> None:
    """The pool shape has no style step: its Charm multi-select IS the choice, so it
    carries the printed label rather than the "Which 3?" follow-up wording, and its
    chips show three Charms drawn from two different styles."""
    await user.open('/cult-db-editor')
    await user.should_see("Three Charms from the Tabernacle's list (pick 3)")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_camp_from_another_splats_cult_does_not_blank_the_editor(
        user: User) -> None:
    """A stored camp of a different splat does not break the page. `camp_for`
    resolves against ALL camps, and a value outside the options raises at BUILD time.

    The page renders with a camp that the character can attend. The mismatch shows as
    `camp-wrong-origin` in the issue panel."""
    await user.open('/cult-db-crossed')
    await user.should_see("Training Camp")
    await user.should_see("The Sequestered Tabernacle")
