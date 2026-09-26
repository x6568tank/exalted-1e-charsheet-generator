"""
server/nav.py — the entries of the site menu, the drawer at the left of each
hosted page.

The public pages draw the drawer in plain HTML (`server/site.py`). The NiceGUI
pages draw it with Quasar (`server/chrome.py`). Both read `groups`, thus the two
drawers show the same entries.

⚠ The campaigns come from a provider that `server/main.build_server` sets. This
module does not import the table store, and a page with no provider shows no
campaigns.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Optional

from .. import build_info
from ..ui import wiki_view

FRONT_PATH = "/"
HOME_PATH = "/home"
WIKI_PATH = "/wiki"
ABOUT_PATH = "/about"
ACCOUNT_PATH = "/account"

# The icon of each wiki section. The wiki tab strip and the menu use it. "Merits &
# Flaws" takes the icon of the builder's Advantages tab, and "Charms" the icon of
# its Charms tab.
SECTION_ICONS = {"charms": "account_tree", "martial-arts": "sports_martial_arts",
                 "spells": "auto_fix_high", "thaumaturgy": "local_fire_department",
                 "powers": "landscape", "merits": "workspace_premium",
                 "backgrounds": "diversity_3", "traits": "person", "castes": "wb_sunny",
                 "equipment": "inventory_2", "artifacts": "diamond",
                 "st-screen": "table_chart"}


@dataclass(frozen=True)
class Link:
    """One entry of the menu.

    `key` is the name of the page, for the mark of the current page. `sub` indents
    the entry below the entry before it. `new_tab` opens the address in a new tab.
    An empty `href` makes the entry a line of text, not a link.
    """

    href: str
    icon: str
    label: str
    key: str = ""
    sub: bool = False
    new_tab: bool = False


# The provider of the campaigns of the current request: (address, name) pairs.
_campaigns: Optional[Callable[[], Sequence[tuple[str, str]]]] = None


def set_campaign_source(provider: Optional[Callable[[], Sequence[tuple[str, str]]]]) -> None:
    """Set the function that gives the campaigns of the current request."""
    global _campaigns
    _campaigns = provider


def groups(username: Optional[str], *, live: bool = False) -> list[list[Link]]:
    """Return the menu entries, in groups that the drawer separates with a line.

    `username` is None for a visitor with no login. Then the menu has Log in and
    Sign up, and no campaigns. `live` is True on a page that holds work in
    progress: the character page and the campaign page. Then the wiki and About
    open in a new tab.
    """
    places = [Link(FRONT_PATH, "home", "Front page", "front")]
    if username:
        places.append(Link(HOME_PATH, "edit", "Your characters", "home"))
        campaigns = _campaigns() if _campaigns is not None else ()
        places.extend(Link(href, "groups", name, sub=True) for href, name in campaigns)
    else:
        places.append(Link("/login", "login", "Log in", "login"))
        places.append(Link("/signup", "person_add", "Sign up", "signup"))

    reference = [Link(WIKI_PATH, "menu_book", "Wiki", "wiki", new_tab=live)]
    reference.extend(Link(f"{WIKI_PATH}/{slug}", SECTION_ICONS[slug], title, sub=True,
                          new_tab=live)
                     for slug, title in wiki_view.SECTIONS)
    reference.append(Link(ABOUT_PATH, "info", "About", "about", new_tab=live))

    result = [places, reference]
    if username:
        result.append([Link("", "account_circle", f"Logged in as {username}", "account"),
                       Link(ACCOUNT_PATH, "manage_accounts", "Account settings",
                            "account-settings"),
                       Link("/logout", "logout", "Log out", "logout")])
    build = build_info.label()
    if build:
        result.append([Link("", "tag", build, "build")])
    return result


def logout_label(username: Optional[str]) -> str:
    """Return the label of the Log out control of the top bar. It names the login."""
    return f"{username} · Log out" if username else "Log out"
