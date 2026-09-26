"""The site colours: a visitor selects the palette of a splat for each page that
shows no one character. `server/site.py`, "The site colours of the visitor".

PRODUCTION wiring: `tests/_auth_main.py` runs `server/main.build_server` and installs
the gate. The cookie comes from the browser, thus each case that reads a colour
reads it from the page that the server sends.
"""

from __future__ import annotations

import pytest
from nicegui import ui
from nicegui.testing import User

from exalted_builder.server import db, nav, site
from exalted_builder.ui import theme

pytest.importorskip("bcrypt")

from . import _auth_state as state  # noqa: E402
from .test_auth_gate import _sign_up  # noqa: E402

MAIN = "tests/_auth_main.py"
LUNAR = theme.palette("Lunar").accent
SOLAR = theme.palette("Solar").accent
DB_CHARM = "/wiki/charms/dragonblooded.air-dragon.air-dragons-sight"


def _accent_of(html: str) -> str:
    """Return the `--accent` value of the style sheet of a public page."""
    start = html.index("--accent:") + len("--accent:")
    return html[start:html.index(";", start)]


# ---- the menu, with no server ---------------------------------------------------- #


def test_the_menu_shows_a_swatch_for_each_palette() -> None:
    html = site.drawer_html(None)

    assert 'data-testid="nav-colours"' in html
    for splat in theme.splat_keys():
        assert f"splat={splat}" in html, splat


def test_the_swatches_come_before_the_build_line() -> None:
    groups = [[nav.Link("/", "home", "Front")], [nav.Link("", "tag", "Build x", nav.BUILD_KEY)]]

    assert nav.colours_position(groups) == 1
    assert nav.colours_position(groups[:1]) == 1, "No build line: the end of the menu."


def test_a_live_page_has_no_swatches() -> None:
    """⚠ A swatch opens the page again, and a live page holds work in progress."""
    assert 'data-testid="nav-colours"' not in site.drawer_html(None, live=True)


# ---- the route --------------------------------------------------------------------- #


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_route_sets_the_cookie_and_returns(user: User) -> None:
    response = await user.http_client.get(
        "/theme", params={"splat": "Lunar", "back": "/wiki"}, follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/wiki"
    assert f"{site.THEME_COOKIE}=Lunar" in response.headers["set-cookie"]


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_route_returns_to_this_server_only(user: User) -> None:
    for back in ("//evil.example/", "https://evil.example/", "/\\evil.example"):
        response = await user.http_client.get(
            "/theme", params={"splat": "Lunar", "back": back}, follow_redirects=False)
        assert response.headers["location"] == "/", back


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_public_page_takes_the_colours_of_the_visitor(user: User) -> None:
    before = (await user.http_client.get("/")).text
    await user.http_client.get("/theme", params={"splat": "Lunar"})
    after = (await user.http_client.get("/about")).text

    assert _accent_of(before) == SOLAR, "The control: the default palette."
    assert _accent_of(after) == LUNAR
    assert 'class="on" aria-current="true" title="Lunar"' in after


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_an_unknown_splat_removes_the_colours(user: User) -> None:
    await user.http_client.get("/theme", params={"splat": "Lunar"})
    await user.http_client.get("/theme", params={"splat": "Fair Folk"})

    assert _accent_of((await user.http_client.get("/")).text) == SOLAR


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_forged_cookie_gives_the_default_colours(user: User) -> None:
    user.http_client.cookies.set(site.THEME_COOKIE, "</style><script>x</script>")

    html = (await user.http_client.get("/")).text

    assert _accent_of(html) == SOLAR
    assert "<script>x</script>" not in html


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_page_of_one_splat_keeps_its_colours(user: User) -> None:
    await user.http_client.get("/theme", params={"splat": "Lunar"})

    html = (await user.http_client.get(DB_CHARM)).text

    assert _accent_of(html) == theme.palette("Dragon-Blooded").accent


# ---- the NiceGUI pages -------------------------------------------------------------- #


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_home_page_takes_the_colours_of_the_visitor(user: User) -> None:
    await _sign_up(user, "Harmonious")
    await user.should_see(marker="home-new")
    await user.http_client.get("/theme", params={"splat": "Lunar"})

    await user.open("/home")

    (bar,) = user.find(ui.header).elements
    assert bar.style.get("background") == LUNAR
    await user.should_see(marker="nav-colours")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_account_page_is_a_grid_with_a_colours_card(user: User) -> None:
    await _sign_up(user, "Harmonious")
    await user.should_see(marker="home-new")
    await user.http_client.get("/theme", params={"splat": "Sidereal"})

    await user.open(nav.ACCOUNT_PATH)

    (card,) = user.find(marker="account-colours").elements
    # ⚠ The harness has no layout. Test the structure: the cards are in the grid.
    assert "account-grid" in card.parent_slot.parent.classes
    (html,) = [child for child in card.default_slot.children if "theme-grid" in
               getattr(child, "content", "")]
    for splat in theme.splat_keys():
        assert f'data-splat="{splat}"' in html.content, splat
    assert 'class="on" aria-current="true" data-splat="Sidereal"' in html.content
    assert "back=%2Faccount" in html.content


# ---- the account --------------------------------------------------------------------- #


async def _logged_in(user: User) -> int:
    await _sign_up(user, "Harmonious")
    await user.should_see(marker="home-new")
    return db.user_id_for(state.DB, "Harmonious")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_login_keeps_the_colours_on_the_account(user: User) -> None:
    user_id = await _logged_in(user)

    await user.http_client.get("/theme", params={"splat": "Lunar"})

    assert db.theme_for(state.DB, user_id) == "Lunar"


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_another_device_of_the_login_shows_the_colours(user: User) -> None:
    """A device with the login and no cookie of its own."""
    await _logged_in(user)
    await user.http_client.get("/theme", params={"splat": "Lunar"})

    user.http_client.cookies.delete(site.THEME_COOKIE)

    assert _accent_of((await user.http_client.get("/")).text) == LUNAR


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_account_colours_come_before_the_cookie(user: User) -> None:
    user_id = await _logged_in(user)
    db.set_theme(state.DB, user_id, "Lunar")

    user.http_client.cookies.set(site.THEME_COOKIE, "Sidereal")

    assert _accent_of((await user.http_client.get("/")).text) == LUNAR


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_an_unknown_splat_removes_the_account_colours(user: User) -> None:
    user_id = await _logged_in(user)
    await user.http_client.get("/theme", params={"splat": "Lunar"})

    await user.http_client.get("/theme", params={"splat": "Fair Folk"})

    assert db.theme_for(state.DB, user_id) is None
    assert _accent_of((await user.http_client.get("/")).text) == SOLAR


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_visitor_with_no_login_writes_no_account(user: User) -> None:
    await user.http_client.get("/theme", params={"splat": "Lunar"})
    await _logged_in(user)

    assert db.theme_for(state.DB, db.user_id_for(state.DB, "Harmonious")) is None
    assert _accent_of((await user.http_client.get("/")).text) == LUNAR, (
        "The cookie still gives the colours.")


def test_a_deleted_account_keeps_no_colours(tmp_path) -> None:
    path = tmp_path / "users.db"
    db.init_db(path)
    user_id = db.create_user(path, "Harmonious", "correct horse")
    db.set_theme(path, user_id, "Lunar")

    db.tombstone_user(path, user_id)

    assert db.theme_for(path, user_id) is None
