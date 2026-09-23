"""The login gate of the hosted server.

Section 5 piece 3 of `docs/plans/hosting-state-model.md`, recorded in section 5.1d.

⚠ The subject is each ROUTE, not the pages that exist today. The gate is a
middleware so that a new route is gated with no change. Thus the first case
enumerates the routes of the app and does not name them. Its guard asserts that
the enumeration found `/home` and the character page, thus an empty list cannot
pass it.
The public routes ARE named, in `PUBLIC_ROUTES`, because each is a ruling.

⚠ The main file is production wiring. A gate that a test fixture installs proves
nothing about the server. `test_server_main.py` asserts that `main` installs it.
"""

from __future__ import annotations

import asyncio
import re

import pytest
from nicegui import Client
from nicegui.testing import User

pytest.importorskip("bcrypt")

from exalted_builder.models.character import Character  # noqa: E402
from exalted_builder.server import auth, config, db  # noqa: E402
from exalted_builder.server.characters import CharacterStore  # noqa: E402
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


# The routes that a visitor with no login can open, BY NAME. Each is public on
# purpose, by a ruling of the human: the login pages (section 5.1d), and the front
# page, About and the wiki (docs/plans/vtt.md 9.4 and 9.5, 2026-09-12).
# ⚠ A route that opens without a name here fails the first case. Do not add a name
# to make it pass without a ruling.
PUBLIC_ROUTES = frozenset({
    "/", "/about", "/login", "/signup", "/logout",
    "/wiki", "/wiki/charms", "/wiki/charms/{entry_id}",
    "/wiki/martial-arts", "/wiki/martial-arts/{entry_id}",
    "/wiki/spells", "/wiki/spells/{entry_id}",
    "/wiki/merits", "/wiki/merits/{entry_id}",
    "/wiki/backgrounds", "/wiki/backgrounds/{entry_id}",
    "/wiki/thaumaturgy", "/wiki/thaumaturgy/{entry_id}",
    "/wiki/powers", "/wiki/powers/{entry_id}",
    "/wiki/traits", "/wiki/traits/{entry_id}",
    "/wiki/castes", "/wiki/castes/{entry_id}",
    "/wiki/equipment", "/wiki/equipment/{entry_id}",
    "/wiki/artifacts", "/wiki/artifacts/{entry_id}",
    "/wiki/st-screen",
})


def _app_routes() -> set[str]:
    """Return the path of each route of the app, the NiceGUI pages and the plain
    routes both. The NiceGUI assets and the socket are not included."""
    from nicegui import app
    from starlette.routing import Route

    paths = set(Client.page_routes.values())
    paths |= {route.path for route in app.routes
              if isinstance(route, Route) and not route.path.startswith("/_nicegui")}
    return paths


def _concrete(path: str) -> str:
    """Put a value in each path parameter of `path`."""
    return re.sub(r"\{[^}]+\}", "x", path)


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_each_route_that_is_not_named_public_sends_a_visitor_to_the_login_page(
        user: User) -> None:
    """🐞 The defect that the gate removes. Before piece 3, each route served the
    character, the party and the homebrew library to any visitor.

    The enumeration reads the routes of the app, not a list of pages. Thus a new
    route is in it with no change here, a plain FastAPI route too."""
    paths = _app_routes()
    assert {auth.HOME_PATH, "/character/{character_id}", "/",
            "/wiki/charms/{entry_id}"} <= paths, (
        f"The enumeration found {sorted(paths)}. It must find the home page, the "
        "character page and the public pages, or this case covers nothing.")

    for path in sorted(paths - PUBLIC_ROUTES - {"/favicon.ico"}):
        response = await user.http_client.get(_concrete(path), follow_redirects=False)
        assert response.status_code == 303, (
            f"{path} answered {response.status_code} to a visitor with no login.")
        assert response.headers["location"].startswith("/login"), (
            f"{path} redirected to {response.headers['location']}, not the login page.")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_each_route_named_public_opens_with_no_login(user: User) -> None:
    """The control for the case above: the public list is not stale. A name here
    for a route that no longer exists, or that the gate closes, fails."""
    paths = _app_routes()
    assert PUBLIC_ROUTES <= paths, f"Named public, but absent: {sorted(PUBLIC_ROUTES - paths)}."

    for path in sorted(PUBLIC_ROUTES - {"/logout"}):
        response = await user.http_client.get(_concrete(path), follow_redirects=False)
        assert response.status_code in (200, 404), (
            f"{path} answered {response.status_code} to a visitor with no login.")


@pytest.mark.parametrize("path", ["/wikipedia", "/wiki-admin", "/homepage", "/about/x",
                                  "/gm", "/home"])
def test_the_public_prefixes_are_exact(path: str) -> None:
    """⚠ `/wiki` is open with each path under it. A path that only starts with the
    same letters is not."""
    assert not auth.is_open_path(path)


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_dot_segment_under_the_wiki_does_not_reach_the_party(user: User) -> None:
    response = await user.http_client.get("/wiki/../gm", follow_redirects=False)

    assert "gm-save-party" not in response.text
    assert response.headers.get("X-Nicegui-Content") != "page"


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_login_page_opens_with_no_login(user: User) -> None:
    await user.open(auth.HOME_PATH)
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
async def test_signup_logs_in_and_opens_the_home_page(user: User) -> None:
    await _sign_up(user, "Harmonious")
    await user.should_see(marker="home-new")

    user_id = db.authenticate(state.DB, "Harmonious", state.PASSWORD)
    assert user_id is not None, "Signup made no account."


async def _new_character(user: User) -> dict:
    """Press New character on /home. Return the context of the new character."""
    await user.should_see(marker="home-new")
    before = set(state.REGISTRY.keys())
    user.find(marker="home-new").click()
    await user.should_see("Identity")
    (key,) = set(state.REGISTRY.keys()) - before
    return state.REGISTRY.ctx_for(key)


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_save_folder_is_the_account_folder(user: User) -> None:
    """The ruling of 2026-09-11: the save folder belongs to the account, not to
    the browser. Piece 4 puts each character in `characters/` below it."""
    await _sign_up(user, "Harmonious")
    ctx = await _new_character(user)

    user_id = db.authenticate(state.DB, "Harmonious", state.PASSWORD)
    assert ctx["path"].parent == state.ROOT / f"user-{user_id}" / "characters"


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_two_browsers_of_one_character_share_one_context(create_user) -> None:
    """Section 9.1: two devices on the same character share it. With a context
    for each browser, the phone would edit a second copy and the last save wins."""
    db.create_user(state.DB, "Harmonious", state.PASSWORD)

    laptop, phone = create_user(), create_user()
    await _log_in(laptop, "Harmonious")
    ctx = await _new_character(laptop)
    await _log_in(phone, "Harmonious")
    await phone.should_see(marker="home-new")
    await phone.open(f"/character/{ctx['char'].id}")
    await phone.should_see("Identity")

    assert len(state.REGISTRY.keys()) == 1, (
        f"One character made {len(state.REGISTRY.keys())} contexts.")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_two_accounts_get_two_contexts(create_user) -> None:
    """The control for the case above. One context for two ACCOUNTS is the defect
    of section 3.1."""
    db.create_user(state.DB, "Harmonious", state.PASSWORD)
    db.create_user(state.DB, "Radiant", state.PASSWORD)

    first, second = create_user(), create_user()
    await _log_in(first, "Harmonious")
    one = await _new_character(first)
    await _log_in(second, "Radiant")
    two = await _new_character(second)

    assert one is not two
    assert one["home_dir"] != two["home_dir"], "Two accounts save in one folder."


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_wrong_password_stays_on_the_login_page(user: User) -> None:
    db.create_user(state.DB, "Harmonious", state.PASSWORD)

    await _log_in(user, "Harmonious", "wrong horse")
    await user.should_see("Wrong username or password.")

    response = await user.http_client.get(auth.HOME_PATH, follow_redirects=False)
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
    """A deep link to a character survives the login (docs/plans/vtt.md 9.4)."""
    user_id = db.create_user(state.DB, "Harmonious", state.PASSWORD)
    row = CharacterStore(db_path=state.DB, root=state.ROOT).create(
        user_id, Character(id="x", name="Deep Linked"))

    await user.open(f"/character/{row.id}")
    await user.should_see(marker="login-submit")
    user.find(marker="login-username").type("Harmonious")
    user.find(marker="login-password").type(state.PASSWORD)
    user.find(marker="login-submit").click()

    await user.should_see(marker="top-bar-save")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_logout_closes_the_gate(user: User) -> None:
    """The Log out button goes to `/logout`. That route logs out and sends the
    browser to the public front page, which is plain HTML. The harness cannot open
    plain HTML as a page, thus this case follows the route itself."""
    await _sign_up(user, "Harmonious")
    await user.should_see(marker="top-bar-logout")

    response = await user.http_client.get("/logout", follow_redirects=False)
    assert response.headers["location"] == "/"

    response = await user.http_client.get(auth.HOME_PATH, follow_redirects=False)
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

    response = await user.http_client.get(auth.HOME_PATH, follow_redirects=False)
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
    ctx = await _new_character(user)
    ctx["path"].unlink()
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
    "elsewhere", "", None, "/logout", "/login?redirect_to=/gm", "/", "/about",
])
def test_an_unsafe_redirect_target_becomes_the_home_page(target) -> None:
    """⚠ An absolute URL in `redirect_to` sends a player from this server to any
    site. `/logout` there logs the player out at once. "/" is the public front page
    now: a login goes to `/home` (docs/plans/vtt.md 9.4)."""
    assert auth.safe_target(target) == auth.HOME_PATH


@pytest.mark.parametrize("target", ["/home", "/gm", "/gm?x=1", "/wiki/charms"])
def test_a_path_of_this_server_is_kept(target: str) -> None:
    assert auth.safe_target(target) == target
