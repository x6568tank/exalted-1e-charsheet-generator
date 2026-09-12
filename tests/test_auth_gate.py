"""The login gate of the hosted server.

Section 5 piece 3 of `docs/plans/hosting-state-model.md`, recorded in section 5.1d.

⚠ The subject is each ROUTE, not the pages that exist today. The gate is a
middleware so that a new route is gated with no change. Thus the first case
enumerates the page routes of the app and does not name them. Its guard asserts
that the enumeration found '/' and '/gm', thus an empty list cannot pass it.

⚠ The main file is production wiring. A gate that a test fixture installs proves
nothing about the server. `test_server_main.py` asserts that `main` installs it.
"""

from __future__ import annotations

import asyncio

import pytest
from nicegui import Client
from nicegui.testing import User

pytest.importorskip("bcrypt")

from exalted_builder.server import auth, config, db  # noqa: E402
from exalted_builder.server.throttle import LoginThrottle  # noqa: E402

from . import _auth_state as state  # noqa: E402

MAIN = "tests/_auth_main.py"


async def _sign_up(user: User, username: str, *, start: str = "/signup") -> None:
    await user.open(start)
    user.find(marker="signup-username").type(username)
    user.find(marker="signup-password").type(state.PASSWORD)
    user.find(marker="signup-confirm").type(state.PASSWORD)
    user.find(marker="signup-submit").click()


async def _until_cleared(user: User) -> None:
    """Wait until `submit` has cleared the password field."""
    (field,) = user.find(marker="login-password").elements
    for _ in range(200):
        if not field.value:
            return
        await asyncio.sleep(0.01)
    raise AssertionError("The login did not finish: the password field is not cleared.")


async def _log_in(user: User, username: str, password: str = state.PASSWORD,
                  *, start: str = "/login") -> None:
    await user.open(start)
    user.find(marker="login-username").type(username)
    user.find(marker="login-password").type(password)
    user.find(marker="login-submit").click()


# --------------------------------------------------------------------------- #
# The gate
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_each_page_route_sends_a_visitor_with_no_login_to_the_login_page(
        user: User) -> None:
    """🐞 The defect that the gate removes. Before piece 3, each route served the
    character, the party and the homebrew library to any visitor."""
    paths = set(Client.page_routes.values())
    assert {"/", "/gm"} <= paths, (
        f"The enumeration found {sorted(paths)}. It must find the builder and the "
        "party page, or this case covers nothing.")

    for path in sorted(paths - auth.OPEN_PATHS):
        response = await user.http_client.get(path, follow_redirects=False)
        assert response.status_code == 303, (
            f"{path} answered {response.status_code} to a visitor with no login.")
        assert response.headers["location"].startswith("/login"), (
            f"{path} redirected to {response.headers['location']}, not the login page.")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_login_page_opens_with_no_login(user: User) -> None:
    await user.open("/")
    await user.should_see(marker="login-submit")
    await user.should_not_see("Identity")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_nicegui_assets_are_open(user: User) -> None:
    """The login page needs the NiceGUI scripts. A gate over them renders a blank
    page, and the User harness does not load scripts, thus it cannot see that."""
    response = await user.http_client.get("/login", follow_redirects=False)
    assert response.status_code == 200

    asset = next(line for line in response.text.split('"')
                 if line.startswith("/_nicegui/") and line.endswith(".js"))
    response = await user.http_client.get(asset, follow_redirects=False)

    assert response.status_code == 200, f"{asset} answered {response.status_code}."


# --------------------------------------------------------------------------- #
# Signup and login
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_signup_logs_in_and_opens_the_builder(user: User) -> None:
    await _sign_up(user, "Harmonious")
    await user.should_see("Identity")

    user_id = db.authenticate(state.DB, "Harmonious", state.PASSWORD)
    assert user_id is not None, "Signup made no account."


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_save_folder_is_the_account_folder(user: User) -> None:
    """The ruling of 2026-09-11: the context and the save folder belong to the
    account, not to the browser."""
    await _sign_up(user, "Harmonious")
    await user.should_see("Identity")

    user_id = db.authenticate(state.DB, "Harmonious", state.PASSWORD)
    key = auth.user_key(user_id)

    assert state.REGISTRY.keys() == [key], (
        f"The registry holds {state.REGISTRY.keys()}, not the account key {key}.")
    ctx = state.REGISTRY.ctx_for(key)
    assert ctx["path"].parent == state.ROOT / key


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_two_browsers_of_one_account_share_one_context(create_user) -> None:
    """The discriminator for the account key. With the browser key, two browsers
    get two contexts and two folders, and a player's phone shows no character."""
    db.create_user(state.DB, "Harmonious", state.PASSWORD)

    laptop, phone = create_user(), create_user()
    await _log_in(laptop, "Harmonious")
    await laptop.should_see("Identity")
    await _log_in(phone, "Harmonious")
    await phone.should_see("Identity")

    assert len(state.REGISTRY.keys()) == 1, (
        f"One account made {len(state.REGISTRY.keys())} contexts.")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_two_accounts_get_two_contexts(create_user) -> None:
    """The control for the case above. One context for two ACCOUNTS is the defect
    of section 3.1."""
    db.create_user(state.DB, "Harmonious", state.PASSWORD)
    db.create_user(state.DB, "Radiant", state.PASSWORD)

    first, second = create_user(), create_user()
    await _log_in(first, "Harmonious")
    await first.should_see("Identity")
    await _log_in(second, "Radiant")
    await second.should_see("Identity")

    keys = state.REGISTRY.keys()
    assert len(keys) == 2
    paths = {state.REGISTRY.ctx_for(key)["path"].parent for key in keys}
    assert len(paths) == 2, f"Two accounts save in one folder: {paths}."


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_wrong_password_stays_on_the_login_page(user: User) -> None:
    db.create_user(state.DB, "Harmonious", state.PASSWORD)

    await _log_in(user, "Harmonious", "wrong horse")
    await user.should_see("Wrong username or password.")

    response = await user.http_client.get("/", follow_redirects=False)
    assert response.status_code == 303, "A wrong password opened the gate."


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_refused_signup_shows_the_reason(user: User) -> None:
    db.create_user(state.DB, "Harmonious", state.PASSWORD)

    await _sign_up(user, "Harmonious")
    await user.should_see("That username is taken.")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_login_returns_to_the_page_that_was_asked_for(user: User) -> None:
    db.create_user(state.DB, "Harmonious", state.PASSWORD)

    await user.open("/gm")
    await user.should_see(marker="login-submit")
    user.find(marker="login-username").type("Harmonious")
    user.find(marker="login-password").type(state.PASSWORD)
    user.find(marker="login-submit").click()

    await user.should_see(marker="gm-save-party")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_logout_closes_the_gate(user: User) -> None:
    await _sign_up(user, "Harmonious")
    await user.should_see(marker="top-bar-logout")

    user.find(marker="top-bar-logout").click()
    await user.should_see(marker="login-submit")

    response = await user.http_client.get("/", follow_redirects=False)
    assert response.status_code == 303, "The gate is open after a logout."


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_login_needs_the_case_of_the_signup(user: User) -> None:
    """The human's ruling, 2026-09-11: usernames are case-sensitive."""
    db.create_user(state.DB, "Harmonious", state.PASSWORD)

    await _log_in(user, "harmonious")
    await user.should_see("Wrong username or password.")


# --------------------------------------------------------------------------- #
# The rate limit, the contact line and the quota, through the pages
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_login_page_applies_the_rate_limit(user: User) -> None:
    """🐞 The mechanism, not the class. `test_login_throttle.py` tests the
    throttle; this case shows the login page calls it. After the free attempts,
    even the CORRECT password is refused."""
    db.create_user(state.DB, "Harmonious", state.PASSWORD)

    await user.open("/login")
    for _ in range(LoginThrottle.FREE_ATTEMPTS):
        user.find(marker="login-username").clear().type("Harmonious")
        user.find(marker="login-password").clear().type("wrong horse")
        user.find(marker="login-submit").click()
        # ⚠ Settle on the cleared field, not on the error text. The text stays from
        # the first failure, and `submit` reads the field when its task RUNS: an
        # unsettled loop sends the correct password below in the wrong attempts.
        await _until_cleared(user)
        await user.should_see("Wrong username or password.")

    user.find(marker="login-password").clear().type(state.PASSWORD)
    user.find(marker="login-submit").click()
    await user.should_see("Too many failed attempts")

    response = await user.http_client.get("/", follow_redirects=False)
    assert response.status_code == 303, "The correct password passed the rate limit."


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_login_page_gives_the_admin_contact(user: User, monkeypatch) -> None:
    monkeypatch.setenv(config.ADMIN_CONTACT_ENV, "admin@example.com")

    await user.open("/login")

    await user.should_see("Forgot your password? Email admin@example.com.")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_no_contact_line_without_an_address(user: User, monkeypatch) -> None:
    monkeypatch.delenv(config.ADMIN_CONTACT_ENV, raising=False)

    await user.open("/login")
    await user.should_see(marker="login-submit")

    await user.should_not_see(marker="login-contact")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_save_in_a_full_account_folder_is_refused(user: User) -> None:
    """The quota through a real click. A full folder refuses Save with a message,
    and the character file is not written."""
    await _sign_up(user, "Harmonious")
    await user.should_see("Identity")

    ctx = state.REGISTRY.ctx_for(state.REGISTRY.keys()[0])
    ctx["path"].parent.mkdir(parents=True, exist_ok=True)
    (ctx["path"].parent / "filler.bin").write_bytes(b"x" * (10 * 1024 * 1024))

    user.find(marker="top-bar-save").click()

    await user.should_see("no space left")
    assert not ctx["path"].exists(), "Save wrote into a full folder."


# --------------------------------------------------------------------------- #
# The redirect target
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("target", [
    "https://elsewhere.example", "//elsewhere.example", "/\\elsewhere.example",
    "elsewhere", "", None, "/logout", "/login?redirect_to=/gm",
])
def test_an_unsafe_redirect_target_becomes_the_root(target) -> None:
    """⚠ An absolute URL in `redirect_to` sends a player from this server to any
    site. `/logout` there logs the player out at once."""
    assert auth.safe_target(target) == "/"


@pytest.mark.parametrize("target", ["/", "/gm", "/gm?x=1"])
def test_a_path_of_this_server_is_kept(target: str) -> None:
    assert auth.safe_target(target) == target
