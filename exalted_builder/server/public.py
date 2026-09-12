"""
server/public.py — the front page and the About page of the hosted server.

Section 9.4 of `docs/plans/vtt.md`. `/` and `/about` need no login. The builder is
at `auth.HOME_PATH` on the hosted server, because `/` is this front page.

⚠ The About text is a DRAFT. The human owns it (vtt.md 9.4) and must approve it
before a deployment shows it.
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
             "Charms, spells, martial arts, Merits and Flaws, Backgrounds. No login."),
            account,
            ("/about", "info", "About this site", "What it is, and who runs it"),
        ])
        + "</section>")
    return page(f"{SITE_NAME} — character builder and wiki", body, username=username,
                description="A character builder and a rules reference for the First "
                            "Edition of Exalted.")


def _about_page():
    contact = config.admin_contact()
    contact_html = (f'<p>Write to <a href="mailto:{esc(contact)}">{esc(contact)}</a>.</p>'
                    if contact else "<p>No contact address is set on this server.</p>")
    # ⚠ DRAFT — the human approves this text before it is deployed. See the module
    # docstring.
    body = (
        '<article class="card narrow prose">'
        '<p class="card-title">About this site</p>'
        '<p class="card-title">What it is</p>'
        "<p>This site builds and checks characters for the First Edition of Exalted. "
        "It counts the points of character creation, records experience after it, "
        "and prints a character sheet. The wiki shows the Charms, spells, martial-arts "
        "styles, Merits and Flaws, and Backgrounds that the builder knows.</p>"
        "<p>It uses First Edition rules only.</p>"
        '<p class="card-title" style="margin-top:14px">Who runs it</p>'
        "<p>One fan runs this site for their own games and for their friends.</p>"
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
