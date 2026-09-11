"""Every tab's Save button must call the callback that its caller supplied.

⚠ This is the only test in the suite that clicks Save. Before it, the seven
`build_*` tabs took a `save_path` and wrote the file themselves, and no test
touched that path. A tab could have ignored its third argument and the suite
stayed green.

The contract is `save_fn(character)`, and nothing more. A tab does not see a
path, thus a tab cannot assume a file system. See
`docs/plans/hosting-state-model.md` section 3.5.

⚠ The negative control, and the reason to trust these seven cases: delete the
`save_fn(character)` call in ONE tab. Exactly that tab's case must go red and
the other six must stay green. Run it per tab — the seven wirings are seven
separate opportunities for the house bug, and one shared assertion would hide
six of them.

⚠ Each case asserts the callback received the character by IDENTITY. A test that
only counts the calls passes when a tab saves the wrong character, which is the
failure that a party of several members makes reachable.
"""

import pytest
from nicegui.testing import User

from . import _save_fn_state as state

MAIN = "tests/_save_fn_main.py"

# The route and the key in `_save_fn_state.CHARS`, for each tab that has a Save
# button. `custom` is absent on purpose: it edits the rule set, not a character.
TABS = [
    ("editor", "/save-editor"),
    ("gear", "/save-gear"),
    ("advantages", "/save-advantages"),
    ("picker", "/save-picker"),
    ("combos", "/save-combos"),
    ("storyteller", "/save-storyteller"),
    ("play", "/save-play"),
]


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
@pytest.mark.parametrize(("tab", "route"), TABS, ids=[t for t, _ in TABS])
async def test_the_save_button_calls_the_supplied_callback(
        user: User, tab: str, route: str) -> None:
    """Click Save on one tab. The callback runs once, with that tab's character."""
    state.CALLS.clear()
    await user.open(route)

    user.find("tab-save").click()
    await user.should_see("Save")          # let the click's handler run

    assert state.CALLS, (
        f"the {tab} tab's Save button did not call its save callback. The tab "
        "either kept a write path of its own or dropped the third argument.")
    assert len(state.CALLS) == 1, f"the {tab} tab saved {len(state.CALLS)} times"
    assert state.CALLS[0] is state.CHARS[tab], (
        f"the {tab} tab saved the wrong character object")


def test_build_app_rejects_a_save_callback() -> None:
    """`build_app` takes a path, and the seven tabs take a callback.

    ⚠ This asymmetry misled the refactor that introduced it: four harness call
    sites were converted to a callback and the failure arrived as an
    `os.PathLike` error from inside NiceGUI, in a page handler, naming neither
    `build_app` nor the argument. The guard names it at the call.
    """
    from exalted_builder.ui import builder

    with pytest.raises(TypeError, match="not a save callback"):
        builder.build_app(None, state.CHARS["editor"], lambda character: None)


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_building_a_tab_does_not_save(user: User) -> None:
    """The control. Rendering a tab must not call the callback.

    ⚠ Without it, a case above passes on a tab that saves at build time, which
    would write a file on every page load.
    """
    state.CALLS.clear()
    await user.open("/save-editor")
    await user.should_see("Save")

    assert state.CALLS == [], "the editor tab saved while it was being built"
