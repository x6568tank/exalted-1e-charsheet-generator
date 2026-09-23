"""
server/public.py — the front page and the About page of the hosted server.

Section 9.4 of `docs/plans/vtt.md`. `/` and `/about` need no login. The builder is
at `auth.HOME_PATH` on the hosted server, because `/` is this front page.

⚠ The About text is Lorem Ipsum, by the human's choice (2026-09-12), until the human
writes it. The contact line and the unofficial-fan-site notice are real.
"""

from __future__ import annotations

from . import auth, config
from .site import SITE_NAME, esc, item_list, page, replace_route


def _front_page():
    username = auth.current_username()
    if username:
        account = ("/home", "edit", "Your characters", f"Logged in as {username}")
    else:
        account = ("/login", "login", "Log in or make an account",
                   "Build characters and keep them on the server")
    body = (
        '<section class="card narrow">'
        f'<p class="card-title">{SITE_NAME}</p>'
        '<p class="lead">A character builder and a rules reference for the First Edition '
        "of Exalted.</p>"
        + item_list([
            ("/wiki", "menu_book", "The Wiki",
             "Charms, spells, martial arts, Merits, castes, equipment, artifacts. No login."),
            account,
            ("/about", "info", "About this site", "What it is, and who runs it"),
        ])
        + "</section>")
    return page(f"{SITE_NAME} — character builder and wiki", body, current="front",
                username=username,
                description="A character builder and a rules reference for the First "
                            "Edition of Exalted.")


def _about_page():
    contact = config.admin_contact()
    contact_html = (f'<p>Write to <a href="mailto:{esc(contact)}">{esc(contact)}</a>.</p>'
                    if contact else "<p>No contact address is set on this server.</p>")
    # ⚠ PLACEHOLDER. The human asked for Lorem Ipsum in place of the draft on
    # 2026-09-12. The human writes the text. The contact line and the notice stay.
    body = (
        '<article class="card narrow prose">'
        '<p class="card-title">About this site</p>'
        "<p>Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod "
        "tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, "
        "quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo "
        "consequat.</p>"
        "<p>Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore "
        "eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt "
        "in culpa qui officia deserunt mollit anim id est laborum.</p>"
        '<p class="card-title" style="margin-top:14px">Contact</p>'
        f"{contact_html}"
        '<p class="card-title" style="margin-top:14px">Not an official product</p>'
        "<p>This is an unofficial fan site. It is not affiliated with, endorsed by, or "
        "sponsored by the publisher or the owners of Exalted. Exalted and the text "
        "that the wiki shows belong to their owners.</p>"
        "</article>")
    return page(f"About — {SITE_NAME}", body, current="about",
                username=auth.current_username(),
                description="What this Exalted First Edition site is, and who runs it.")


def register_public_pages() -> None:
    """Register `/` and `/about`. Replace earlier routes of the same paths."""
    replace_route("/", _front_page, name="front-page")
    replace_route("/about", _about_page, name="about")
