"""Render tests for the GM party page (ui/gm.py), via the NiceGUI User simulation.

Each test drives its OWN route with its own party (see tests/_ui_main.py), and
asserts through the rendered UI rather than by reaching back into the harness
module's globals — the harness does not reliably hand a test the same module
object the page closed over. Anything that genuinely wants to inspect state is a
pure test instead (see tests/test_party.py and tests/test_builder.py)."""

import pytest
from nicegui.elements.label import Label
from nicegui.testing import User
from nicegui.testing.user_interaction import UserInteraction

MAIN = "tests/_ui_main.py"


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_party_page_shows_every_member(user: User) -> None:
    await user.open('/gm')
    await user.should_see("Ashes of Dawn")
    await user.should_see("Cathak Jade")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_party_page_labels_each_member_with_its_own_splat(user: User) -> None:
    # a mixed party: the Solar keeps "Caste", the Dragon-Blooded gets "Aspect"
    await user.open('/gm')
    await user.should_see("Dawn Caste · Solar")
    await user.should_see("Fire Aspect · Dragon-Blooded")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_party_page_renders_the_tracker_sections(user: User) -> None:
    await user.open('/gm')
    await user.should_see("HEALTH")
    await user.should_see("ESSENCE (motes spent)")
    await user.should_see("LIMIT")
    await user.should_see("SESSION NOTES")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_party_page_shows_the_permanent_readout(user: User) -> None:
    # soak / Dodge / Essence at a glance; a fresh Solar has Stamina 1, Dodge 0, Essence 2
    await user.open('/gm')
    await user.should_see("Soak 1B / 0L / 0A  ·  Dodge 0  ·  Essence 2")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_party_page_offers_the_per_member_actions(user: User) -> None:
    await user.open('/gm')
    await user.should_see("Sheet")          # the read-only sheet dialog
    await user.should_see("Builder")        # hands this member to the builder


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_empty_party_explains_itself(user: User) -> None:
    await user.open('/gm-empty')
    await user.should_see("No characters in the party yet.")
    await user.should_not_see("HEALTH")     # no cards, so no trackers


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_party_page_shows_the_storyteller_reference(user: User) -> None:
    # The static ST reference screen renders as an expansion with its combat tables,
    # even on an empty party (it's rules reference, not per-character).
    await user.open('/gm-empty')
    await user.should_see("Storyteller Reference")
    await user.should_see("Combat Resolution")     # page 2
    await user.should_see("Feats of Strength")
    await user.should_see("Common Actions")        # page 3
    await user.should_see("Anima Banner")
    await user.should_see("Virtues")               # page 4
    await user.should_see("Diseases")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_builder_always_offers_a_way_to_the_party_page(user: User) -> None:
    """The party page is the ONLY place characters are added to a party, so the
    builder must link to it even when the party is still empty — gating the button
    on a non-empty party made an empty one reachable only by typing the URL."""
    await user.open('/builder')             # a solo character, no party
    await user.should_see("Party")


# --------------------------------------------------------------------------- #
# The trackers
# --------------------------------------------------------------------------- #

def _click(user: User, element) -> None:
    """Click `element` through its registered handler. The tracker boxes are
    clickable <div>s rather than buttons (a q-btn's own background beats the gold
    fill), so they are not reachable by button text."""
    UserInteraction(user, {element}, None).click()


def _health_boxes(user: User) -> list:
    """Every clickable health box on the page, in render order. The 2rem height
    distinguishes them from the smaller Willpower/Limit dot boxes."""
    return [e for e in user.client.elements.values()
            if isinstance(e, Label) and not e.is_deleted and "cursor-pointer" in e._classes
            and e._style.get("height") == "2rem"]


def _damage_tallies(user: User) -> list[str]:
    """Each card's "N/ Nx N*" marked-damage tally, in card order — the page's own
    readout of what has been marked, so a test never has to inspect the model."""
    return [e.text for e in user.client.elements.values()
            if isinstance(e, Label) and not e.is_deleted
            and e.text.endswith("*") and "x " in e.text]


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_marking_damage_hits_only_that_member(user: User) -> None:
    """The point of the grid: several trackers on one page must stay independent."""
    await user.open('/gm-click')
    boxes = _health_boxes(user)
    assert len(boxes) == 14                          # a 7-box track for each of two characters
    assert _damage_tallies(user) == ["0/ 0x 0*", "0/ 0x 0*"]

    _click(user, boxes[7])                           # the SECOND card's first box
    # The card refreshes as a background task, so settle before reading the DOM.
    await user.should_see("1/ 0x 0*")

    assert _damage_tallies(user) == ["0/ 0x 0*", "1/ 0x 0*"]


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_health_box_cycles_through_the_damage_types(user: User) -> None:
    """Same cycle as the Play tab: empty → / bashing → x lethal → * aggravated → empty."""
    await user.open('/gm-cycle')
    for expected in ("1/ 0x 0*", "0/ 1x 0*", "0/ 0x 1*", "0/ 0x 0*"):
        _click(user, _health_boxes(user)[0])         # re-read: the card refreshes each click
        await user.should_see(expected)
        assert _damage_tallies(user) == [expected]


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_marking_damage_reports_the_wound_penalty(user: User) -> None:
    """The card reads the penalty off the deepest marked box, as the Play tab does."""
    await user.open('/gm-penalty')
    await user.should_see("Penalty: none")
    _click(user, _health_boxes(user)[1])             # the -1 box
    await user.should_see("Penalty: -1")
