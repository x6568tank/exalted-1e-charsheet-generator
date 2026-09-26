"""The site menu: `server/nav.py`, the HTML drawer of `server/site.py` and the
Quasar drawer of `server/chrome.py`.

PRODUCTION wiring for the page cases: `tests/_auth_main.py` runs
`server/main.build_server`, which sets the campaign provider.

⚠ A campaign name is on `/home` in the Campaigns section too. Thus the page cases
read the addresses of the entries IN the drawer, not the text of the page.
"""

from __future__ import annotations

import pytest
from nicegui import ui
from nicegui.testing import User

pytest.importorskip("bcrypt")

from exalted_builder import build_info  # noqa: E402
from exalted_builder.server import chrome, db, nav, site  # noqa: E402
from exalted_builder.server.characters import CharacterStore  # noqa: E402
from exalted_builder.server.tables import TableStore  # noqa: E402
from exalted_builder.models.character import Character  # noqa: E402
from exalted_builder.ui import wiki_view  # noqa: E402

from . import _auth_state as state  # noqa: E402

MAIN = "tests/_auth_main.py"

_CAMPAIGNS = [("/table/a", "Nexus Nights"), ("/table/b", "<b>Loud</b>")]


@pytest.fixture(autouse=True)
def _no_build_line(monkeypatch):
    """⚠ The build line depends on the machine: a checkout has one, a copy with no
    `.git` has none. Remove it, thus the group counts here do not change by machine.
    `tests/test_build_info.py` covers the line."""
    monkeypatch.setattr(build_info, "label", lambda: "")


@pytest.fixture
def campaigns(monkeypatch):
    """Give the menu two campaigns. Record each call of the provider."""
    calls = []

    def provider():
        calls.append(1)
        return _CAMPAIGNS

    monkeypatch.setattr(nav, "_campaigns", provider)
    return calls


def _links(groups) -> list[nav.Link]:
    return [link for group in groups for link in group]


# --------------------------------------------------------------------------- #
# nav.groups
# --------------------------------------------------------------------------- #


def test_a_visitor_gets_log_in_and_sign_up_and_no_campaigns(campaigns) -> None:
    keys = [link.key for link in _links(nav.groups(None))]
    assert "login" in keys and "signup" in keys
    assert "home" not in keys and "logout" not in keys
    assert campaigns == []


def test_an_account_gets_its_campaigns_below_your_characters(campaigns) -> None:
    (places, _reference, account) = nav.groups("gil")
    assert [link.label for link in places] == [
        "Front page", "Your characters", "Nexus Nights", "<b>Loud</b>"]
    assert [link.sub for link in places] == [False, False, True, True]
    assert [link.key for link in account] == ["account", "account-settings", "logout"]


def test_the_account_group_names_the_login_and_is_not_a_link(campaigns) -> None:
    (_places, _reference, account) = nav.groups("gil")
    (who, _settings, _logout) = account
    assert who.label == "Logged in as gil"
    assert who.href == "", "The account line is a link."


def test_the_menu_lists_each_wiki_section() -> None:
    hrefs = {link.href for link in _links(nav.groups(None))}
    for slug, _title in wiki_view.SECTIONS:
        assert f"/wiki/{slug}" in hrefs


def test_a_live_page_opens_the_wiki_and_about_in_a_new_tab(campaigns) -> None:
    (places, reference, account) = nav.groups("gil", live=True)
    assert all(link.new_tab for link in reference)
    assert not any(link.new_tab for link in places + account)
    assert not any(link.new_tab for link in _links(nav.groups("gil")))


# --------------------------------------------------------------------------- #
# The HTML drawer
# --------------------------------------------------------------------------- #


def test_the_html_drawer_escapes_a_campaign_name(campaigns) -> None:
    html = site.header_bar("", "gil")
    assert "&lt;b&gt;Loud&lt;/b&gt;" in html
    assert "<b>Loud</b>" not in html


def test_the_html_bar_names_the_login_in_the_menu_and_the_log_out_button(campaigns) -> None:
    html = site.header_bar("", "gil")
    drawer = html[html.index('<nav class="drawer"'):html.index("</nav>")]
    quick = html[html.index('<nav class="quick"'):]
    assert "Logged in as gil" in drawer
    assert '<a href=""' not in drawer, "The account line is a link."
    assert nav.logout_label("gil") in quick
    assert "gil" in nav.logout_label("gil") and "Log out" in nav.logout_label("gil")


def test_the_html_bar_escapes_the_username(campaigns) -> None:
    html = site.header_bar("", "<b>gil</b>")
    assert "<b>gil</b>" not in html
    assert "&lt;b&gt;gil&lt;/b&gt;" in html


def test_a_visitor_has_no_account_line() -> None:
    assert "Logged in as" not in site.header_bar("", None)


def test_the_html_drawer_marks_the_current_page() -> None:
    html = site.drawer_html(None, "about")
    assert html.count('aria-current="page"') == 1
    assert 'href="/about" class="on" aria-current="page"' in html


def test_the_public_page_has_the_menu_and_its_script() -> None:
    body = site.page("T", "<p>x</p>").body.decode()
    assert '<details class="menu">' in body
    assert site.MENU_SCRIPT in body


# --------------------------------------------------------------------------- #
# The Quasar drawer, on the pages of the hosted server
# --------------------------------------------------------------------------- #


async def _sign_up(user: User, username: str) -> int:
    await user.open("/signup")
    user.find(marker="signup-username").type(username)
    user.find(marker="signup-password").type(state.PASSWORD)
    user.find(marker="signup-confirm").type(state.PASSWORD)
    user.find(marker="signup-submit").click()
    await user.should_see(marker="home-new")
    return db.authenticate(state.DB, username, state.PASSWORD)


def _drawer_items(user: User) -> dict[str, ui.item]:
    """Return the entries of the one site menu of the page, by address."""
    (drawer,) = user.find(marker="nav-drawer").elements
    return {item.props["href"]: item for item in drawer.descendants()
            if isinstance(item, ui.item) and "href" in item.props}


def _drawer_text(user: User) -> list[str]:
    """Return the text of each label in the one site menu of the page."""
    (drawer,) = user.find(marker="nav-drawer").elements
    return [element.text for element in drawer.descendants()
            if isinstance(element, ui.item_section) and getattr(element, "text", "")]


def _logout_text(user: User) -> str:
    """Return the label of the Log out control: a button, or a menu item that
    holds its label in a child section."""
    (control,) = user.find(marker="top-bar-logout").elements
    return " ".join(text for element in [control, *control.descendants()]
                    if (text := getattr(element, "text", "")))


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_home_menu_lists_the_campaigns_of_the_account(user: User) -> None:
    user_id = await _sign_up(user, "Menuholder")
    other = db.create_user(state.DB, "Stranger", state.PASSWORD)
    tables = TableStore(db_path=state.DB, root=state.ROOT)
    mine = tables.create(user_id, "Nexus Nights")
    theirs = tables.create(other, "Elsewhere")

    await user.open("/home")
    await user.should_see(marker="nav-menu")
    items = _drawer_items(user)
    assert chrome.table_url(mine.id) in items
    assert chrome.table_url(theirs.id) not in items
    assert "target" not in items["/wiki"].props
    assert "Logged in as Menuholder" in _drawer_text(user)
    assert _logout_text(user) == nav.logout_label("Menuholder")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_character_page_opens_the_wiki_in_a_new_tab(user: User) -> None:
    user_id = await _sign_up(user, "Sheetholder")
    row = CharacterStore(db_path=state.DB, root=state.ROOT).create(
        user_id, Character(id="x", name="Menu Test"))

    await user.open(chrome.character_url(row.id))
    await user.should_see(marker="top-bar-save")
    items = _drawer_items(user)
    assert items["/wiki"].props["target"] == "_blank"
    assert items["/about"].props["target"] == "_blank"
    assert "target" not in items["/home"].props
    assert "Logged in as Sheetholder" in _drawer_text(user)
    assert _logout_text(user) == nav.logout_label("Sheetholder")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_campaign_page_has_the_menu(user: User) -> None:
    user_id = await _sign_up(user, "Tableholder")
    table = TableStore(db_path=state.DB, root=state.ROOT).create(user_id, "Menu Table")

    await user.open(chrome.table_url(table.id))
    await user.should_see(marker="table-title")
    items = _drawer_items(user)
    assert items["/wiki"].props["target"] == "_blank"
    assert chrome.table_url(table.id) in items
    assert "Logged in as Tableholder" in _drawer_text(user)
    assert _logout_text(user) == nav.logout_label("Tableholder")
