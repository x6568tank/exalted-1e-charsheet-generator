"""Two browser sessions must not share one Character.

✅ **These tests are LIVE as of 2026-09-11.** They were written first, they failed
on the tree of that day, and they carried `xfail(strict=True)` until
`register_pages` resolved one context for each session. The XPASS was the gate,
and the markers are deleted.

⚠ Do not "fix" a failure here by changing an assertion. These tests describe the
contract. A failure means two browsers share a Character again.

⚠ The negative control, run on 2026-09-11: make `session_key` return a constant.
Both tests go red again. Use that mutation, and not a reading of the code, to
confirm that these tests still see the property they name. The copy rule they
depend on has its own file, `tests/test_session_context_factory.py`.

This is phase P0 of `docs/plans/vtt.md`. The design is section 3.8 of
`docs/plans/hosting-state-model.md`. The defect it removed is section 3.1 of the
same file.

⚠ Read `test_the_harness_gives_two_independent_sessions` first. A shared harness
client makes the other two tests fail for a reason that is not the defect, and a
red run would then prove nothing. That test is the discriminator.

The two tests cover two phases, because a rule that operates in one phase and not
in the other is this project's usual defect ("the house bug"):

1. Two sessions on '/'.
2. The '/gm' -> '/' navigation, which repoints `ctx["char"]` by reference and then
   does a full page load. It is the phase that leaks first.
"""

import pytest
from nicegui.elements.input import Input
from nicegui.testing import User

from ._isolation_names import EDIT_NAME, MEMBER_NAME, START_NAME

MAIN = "tests/_isolation_main.py"


def _name_box(user: User) -> Input:
    """The Identity 'Name' field of the Edit tab. See ui/editor.py:762."""
    return next(e for e in user.client.elements.values()
                if isinstance(e, Input) and e._props.get("label") == "Name")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_harness_gives_two_independent_sessions(create_user) -> None:
    """The control. It says that the harness gives two clients.

    ⚠ Without it, a red run below is ambiguous: a harness that hands both users one
    client produces the same failure as an app that hands both users one Character.
    Read this test first when one of the other two fails.
    """
    a, b = create_user(), create_user()
    await a.open("/")
    await b.open("/")

    assert a.client.id != b.client.id, (
        "The harness gave both users one client. The isolation tests below cannot "
        "tell app sharing from harness sharing until this passes."
    )


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_second_session_does_not_see_the_first_sessions_edit(create_user) -> None:
    """Phase 1. Session A renames the character. Session B must not see the name."""
    a, b = create_user(), create_user()

    await a.open("/")
    _name_box(a).set_value(EDIT_NAME)
    assert _name_box(a).value == EDIT_NAME, "Session A did not apply its own edit."

    await b.open("/")
    assert _name_box(b).value == START_NAME, (
        f"Session B opened '/' and found {_name_box(b).value!r}. Two sessions share "
        f"one Character object — see hosting-state-model.md section 3.1."
    )


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_gm_navigation_does_not_repoint_another_session(create_user) -> None:
    """Phase 2. Session A opens a party member in the builder. Session B must keep
    its own character.

    `gm.open_in_builder` calls `builder.open_member`, which repoints `ctx["char"]`
    at the party member by reference, and then navigates. The navigation is a full
    page load, thus session B rebuilds from `ctx` and gets the party member.
    """
    a, b = create_user(), create_user()

    await a.open("/gm")
    # ⚠ Click the marked button. `find("Builder")` matches TWO buttons, and
    # `find(...).elements` is an unordered set, thus it can click the incorrect one.
    a.find(marker="open-in-builder-0").click()

    # ⚠ Do not assert `should_see(MEMBER_NAME)` here. The '/gm' card prints the
    # member name, thus the assertion passes when the click does nothing. Assert on
    # the builder's own Name field after the navigation instead.
    await a.should_see("Identity")
    assert _name_box(a).value == MEMBER_NAME, (
        f"Session A is not in the builder on the party member — the Name field reads "
        f"{_name_box(a).value!r}. The click or the navigation did not happen, thus "
        f"this test cannot see the leak it exists to find."
    )

    await b.open("/")
    assert _name_box(b).value == START_NAME, (
        f"Session B opened '/' and found {_name_box(b).value!r}. Session A's party "
        f"navigation repointed the shared ctx for everybody."
    )
