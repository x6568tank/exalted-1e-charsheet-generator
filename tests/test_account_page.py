"""Account management in the browser: the login epoch and the `/account` page.
`docs/plans/account-management.md`.

PRODUCTION wiring: `tests/_auth_main.py` runs `server/main.build_server` and installs
the gate.
"""

from __future__ import annotations

import asyncio

import pytest
from nicegui.testing import User
from nicegui.testing.user_navigate import UserNavigate

pytest.importorskip("bcrypt")

from exalted_builder.server import db  # noqa: E402

from . import _auth_state as state  # noqa: E402
from .test_auth_gate import _sign_up  # noqa: E402

MAIN = "tests/_auth_main.py"


async def _home_status(user: User) -> int:
    response = await user.http_client.get("/home", follow_redirects=False)
    return response.status_code


# ---- the login epoch ------------------------------------------------------------ #


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_raised_epoch_ends_the_login(user: User) -> None:
    await _sign_up(user, "Harmonious")
    await user.should_see(marker="home-new")
    assert await _home_status(user) == 200, "The control: the login works."

    db.raise_login_epoch(state.DB, db.user_id_for(state.DB, "Harmonious"))

    assert await _home_status(user) == 303


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_an_operator_reset_ends_the_login(user: User) -> None:
    await _sign_up(user, "Harmonious")
    await user.should_see(marker="home-new")

    db.set_password(state.DB, "Harmonious", "a new password")

    assert await _home_status(user) == 303


# ---- the /account page ------------------------------------------------------------ #

NEW_PASSWORD = "battery staple"


async def _account(user: User, name: str = "Harmonious") -> int:
    """Sign up as `name`, open /account and return the account id."""
    await _sign_up(user, name)
    await user.should_see(marker="home-new")
    await user.open("/account")
    await user.should_see(marker="account-email")
    return db.user_id_for(state.DB, name)


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_menu_links_the_account_page(user: User) -> None:
    await _sign_up(user, "Harmonious")
    await user.should_see(marker="home-new")
    response = await user.http_client.get("/")
    assert 'href="/account"' in response.text


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_page_sets_the_email_with_the_password(user: User) -> None:
    user_id = await _account(user)

    user.find(marker="account-email").type("jade@example.com")
    user.find(marker="account-email-password").type(state.PASSWORD)
    user.find(marker="account-email-save").click()
    await user.should_see("Saved.")

    assert db.email_for(state.DB, user_id) == "jade@example.com"


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_wrong_password_sets_no_email(user: User) -> None:
    user_id = await _account(user)

    user.find(marker="account-email").type("jade@example.com")
    user.find(marker="account-email-password").type("wrong horse")
    user.find(marker="account-email-save").click()
    await user.should_see("The current password is wrong.")

    assert db.email_for(state.DB, user_id) is None


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_page_changes_the_password_and_keeps_this_login(user: User) -> None:
    user_id = await _account(user)

    user.find(marker="account-current").type(state.PASSWORD)
    user.find(marker="account-new").type(NEW_PASSWORD)
    user.find(marker="account-again").type(NEW_PASSWORD)
    user.find(marker="account-password-save").click()
    await user.should_see("Every other device is logged out.")

    assert db.authenticate(state.DB, "Harmonious", NEW_PASSWORD) == user_id
    assert db.login_epoch(state.DB, user_id) == 1
    assert await _home_status(user) == 200, "The change logged out this browser too."


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_two_different_new_passwords_change_nothing(user: User) -> None:
    await _account(user)

    user.find(marker="account-current").type(state.PASSWORD)
    user.find(marker="account-new").type(NEW_PASSWORD)
    user.find(marker="account-again").type("battery stapler")
    user.find(marker="account-password-save").click()
    await user.should_see("The two passwords are different.")

    assert db.authenticate(state.DB, "Harmonious", state.PASSWORD) is not None


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_log_out_other_devices_keeps_this_login(user: User) -> None:
    user_id = await _account(user)

    user.find(marker="account-logout-others").click()
    await user.should_see("Every other device is logged out.")

    assert db.login_epoch(state.DB, user_id) == 1
    assert await _home_status(user) == 200


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_wrong_password_deletes_nothing(user: User) -> None:
    await _account(user)

    user.find(marker="account-delete-password").type("wrong horse")
    user.find(marker="account-delete").click()
    await user.should_see("The current password is wrong.")

    assert db.user_id_for(state.DB, "Harmonious") is not None


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_page_deletes_the_account_and_logs_out(user: User, monkeypatch) -> None:
    """The page goes to the front page, which is plain HTML. The harness cannot open
    plain HTML as a page, thus this case records the target and does not follow it."""
    user_id = await _account(user)
    targets: list[str] = []
    monkeypatch.setattr(UserNavigate, "to", lambda self, target, *a, **k: targets.append(target))

    user.find(marker="account-delete-password").type(state.PASSWORD)
    user.find(marker="account-delete").click()
    for _ in range(200):
        if targets:
            break
        await asyncio.sleep(0.01)

    assert targets == ["/"]
    assert db.username_for(state.DB, user_id) is None
    assert await _home_status(user) == 303


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_delete_names_the_campaigns_it_deletes(user: User) -> None:
    from exalted_builder.server.tables import TableStore

    await _sign_up(user, "Harmonious")
    await user.should_see(marker="home-new")
    TableStore(db_path=state.DB, root=state.ROOT).create(
        db.user_id_for(state.DB, "Harmonious"), "The Scarlet Gambit")

    await user.open("/account")

    await user.should_see("The Scarlet Gambit")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_signup_records_an_email(user: User) -> None:
    await user.open("/signup")
    user.find(marker="signup-username").type("Harmonious")
    user.find(marker="signup-email").type("jade@example.com")
    user.find(marker="signup-password").type(state.PASSWORD)
    user.find(marker="signup-confirm").type(state.PASSWORD)
    user.find(marker="signup-submit").click()
    await user.should_see(marker="home-new")

    assert db.email_for(state.DB, db.user_id_for(state.DB, "Harmonious")) == \
        "jade@example.com"


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_page_says_when_there_is_no_email(user: User) -> None:
    await _account(user)
    await user.should_see("cannot prove")


# ---- rename -------------------------------------------------------------------------- #


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_page_renames_the_account(user: User) -> None:
    user_id = await _account(user)

    user.find(marker="account-username").type("Radiant")
    user.find(marker="account-username-password").type(state.PASSWORD)
    user.find(marker="account-username-save").click()
    await user.should_see("You log in as Radiant now.")

    assert db.username_for(state.DB, user_id) == "Radiant"
    response = await user.http_client.get("/")
    assert "Logged in as Radiant" in response.text


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_another_device_shows_the_new_name(user: User) -> None:
    """⚠ The browser stores the username at the login. A rename on another device
    changes the database only. The pages must read the name from the database."""
    user_id = await _account(user)

    db.rename_user(state.DB, user_id, state.PASSWORD, "Radiant")

    response = await user.http_client.get("/")
    assert "Logged in as Radiant" in response.text
    assert "Harmonious" not in response.text


# ---- the throttle on the current password (server review finding 5) -------------- #

# Each action: (the password field, the extra fields, the save button).
_ACTIONS = {
    "email": ("account-email-password", {"account-email": "jade@example.com"},
              "account-email-save"),
    "rename": ("account-username-password", {"account-username": "Radiant"},
               "account-username-save"),
    "password": ("account-current", {"account-new": NEW_PASSWORD,
                                     "account-again": NEW_PASSWORD},
                 "account-password-save"),
    "delete": ("account-delete-password", {}, "account-delete"),
}


async def _attempt(user: User, action: str, password: str) -> None:
    """Fill the form of `action` with `password` and press its button. Wait until
    the page clears the password field, which it does at each refusal."""
    field, extra, button = _ACTIONS[action]
    for marker, value in extra.items():
        user.find(marker=marker).clear().type(value)
    user.find(marker=field).clear().type(password)
    (box,) = user.find(marker=field).elements
    user.find(marker=button).click()
    for _ in range(100):
        if not box.value:
            return
        await asyncio.sleep(0.02)
    raise AssertionError("The page did not refuse the attempt.")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
@pytest.mark.parametrize("action", sorted(_ACTIONS))
async def test_guesses_at_the_current_password_are_throttled(user: User, action) -> None:
    user_id = await _account(user)
    for _ in range(5):
        await _attempt(user, action, "wrong horse")
    await user.should_see("The current password is wrong.")

    await _attempt(user, action, state.PASSWORD)

    await user.should_see("Too many failed attempts.")
    assert db.username_for(state.DB, user_id) == "Harmonious"
    assert db.email_for(state.DB, user_id) is None
    assert db.authenticate(state.DB, "Harmonious", state.PASSWORD) == user_id


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_account_page_and_the_login_share_one_count(create_user) -> None:
    """A guesser cannot get five guesses here and five more at the login."""
    owner, other = create_user(), create_user()
    await _account(owner)
    for _ in range(5):
        await _attempt(owner, "email", "wrong horse")

    await other.open("/login")
    other.find(marker="login-username").type("Harmonious")
    other.find(marker="login-password").type(state.PASSWORD)
    other.find(marker="login-submit").click()

    await other.should_see("Too many failed attempts.")
