"""A raised login epoch ends the pages that are open, not only the next request.

⚠ "The house bug" (docs/lessons.md): the epoch check exists, and it operates in the
HTTP gate only. An open page is a socket, and its handlers capture `user_id` at
the build. Thus a page that was open before "Log out other devices", a password
change or an operator reset keeps each control. Reproduced in Chromium: after the
owner changed the password, the open `/home` of the old login deleted a
character. `test_account_page.py` tests the next GET only, thus it passes.

PRODUCTION wiring: `tests/_auth_main.py`.
"""

from __future__ import annotations

import contextlib

import pytest
from nicegui import Client
from nicegui.testing import User

from exalted_builder.server import auth, db

pytest.importorskip("bcrypt")

from . import _auth_state as state  # noqa: E402
from .test_auth_gate import _sign_up  # noqa: E402

MAIN = "tests/_auth_main.py"


def _ended(client_id: str) -> bool:
    """True if the page has no element left, thus no handler and no upload route.
    The client itself goes a moment later (`auth._delete_later`)."""
    client = Client.instances.get(client_id)
    return client is None or not client.elements


def _characters(user_id: int) -> int:
    return len(list((state.ROOT / f"user-{user_id}" / "characters").glob("*.json")))


async def _open_home(user: User, name: str = "Harmonious") -> tuple[int, str]:
    """Sign up as `name` and open /home. Return the account and the page client."""
    await _sign_up(user, name)
    await user.should_see(marker="home-new")
    (button,) = user.find(marker="home-new").elements
    return db.user_id_for(state.DB, name), button.client.id


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_an_open_page_of_an_old_login_ends(user: User) -> None:
    user_id, client_id = await _open_home(user)
    before = _characters(user_id)

    db.raise_login_epoch(state.DB, user_id)
    auth.end_stale_pages()

    assert _ended(client_id), (
        "The page of the old login is still live. Its handlers still run.")
    with contextlib.suppress(AssertionError):
        user.find(marker="home-new").click()
    assert _characters(user_id) == before, "A page of an old login made a character."


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_an_operator_reset_ends_the_open_pages(user: User) -> None:
    """The operator resets from another process. The sweep reads the database,
    thus it sees the reset with no call from this process."""
    user_id, client_id = await _open_home(user)

    db.set_password(state.DB, "Harmonious", "a new password")
    auth.end_stale_pages()

    assert _ended(client_id)


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_current_page_stays(user: User) -> None:
    """The control: a sweep with no change of epoch ends nothing."""
    user_id, client_id = await _open_home(user)

    auth.end_stale_pages()

    assert not _ended(client_id)
    user.find(marker="home-new").click()


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_log_out_other_devices_keeps_the_page_that_asks(user: User) -> None:
    """The account page logs this browser in again at the new epoch. Its own page
    must not end, and the sweep runs at once."""
    await _sign_up(user, "Harmonious")
    await user.should_see(marker="home-new")
    await user.open("/account")
    await user.should_see(marker="account-email")
    (button,) = user.find(marker="account-logout-others").elements

    user.find(marker="account-logout-others").click()
    await user.should_see("Every other device is logged out.")

    assert not _ended(button.client.id)
