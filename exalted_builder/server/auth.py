"""
server/auth.py — the login gate of the hosted server.

Section 5 piece 3 of `docs/plans/hosting-state-model.md`. It supplies:

  * `AuthGate`, a middleware that sends each request without a login to `/login`.
    The public pages are the exceptions: `/`, `/about` and `/wiki`.
  * The `/login`, `/signup` and `/logout` pages.
  * `current_user_id`, the account of the request. `server/home.py` gives each
    page the characters of that account and no other.

⚠ The gate is a MIDDLEWARE, not a call in each page. A call in each page leaves
open each route that does not make the call, and no test of an existing page
reports it. The middleware covers each route, and each new route, by default.
`OPEN_PATHS` is the list of exceptions.

⚠ The pages of `server/home.py` raise when `current_user_id` gives None. Thus a
page that the gate does not cover fails. It does not fall back to the browser key,
which serves a context to a visitor with no account.

⚠ The login state is in `app.storage.user`. NiceGUI keeps that store on the server
and keys it on the signed session cookie. Thus a logout removes the login, and a
copied cookie does not keep it.

⚠ `server/throttle.py` limits the login attempts by username. Known limit, not
solved here: the session id does not change at login. See section 5.1d.
"""

from __future__ import annotations

import math
from pathlib import Path
from urllib.parse import quote

from fastapi import Request
from fastapi.responses import RedirectResponse
from nicegui import app, run, ui
from starlette.middleware.base import BaseHTTPMiddleware

from ..ui import theme
from . import config, db, site
from .throttle import LoginThrottle

# The paths that a visitor with no login can open. The icon is here because the
# login page shows it. "/" and "/about" are the public front page and the About
# page, by the site map of docs/plans/vtt.md section 9.4.
# The two files for crawlers are open too (`server/crawl.py`).
OPEN_PATHS = frozenset({"/", "/about", "/login", "/signup", "/logout", "/favicon.ico",
                        "/robots.txt", "/sitemap.xml"})

# The public wiki: "/wiki" and each path under it. Section 9.5 of vtt.md.
# ⚠ Public ON PURPOSE (human ruling, 2026-09-12). `tests/test_auth_gate.py` names
# it, thus a new public route fails that test until it is named there too.
WIKI_PATH = "/wiki"

# The page after a login with no `redirect_to`. It is gated. It lists the
# characters of the account (`server/home.py`, section 9.4).
HOME_PATH = "/home"

# The static files, the uploads and the socket of NiceGUI. A page needs them to
# render, the login page included. A client id from a gated page is necessary to
# use the upload and the socket routes, and a visitor with no login gets none.
_OPEN_PREFIXES = ("/_nicegui/", "/_nicegui_ws/")

# The keys in `app.storage.user`.
USER_ID = "user_id"
USERNAME = "username"
LOGIN_EPOCH = "login_epoch"

# Why an account needs an email. The signup form and `/account` show it.
NO_EMAIL_NOTE = ("Without an email, you cannot prove the account is yours if you "
                 "forget the password.")

# The attribute of `app.state` that holds the account database. `register_auth_pages`
# sets it. The desktop has no accounts and does not set it: then no login epoch is
# checked. ⚠ Not a module global: a NiceGUI main-file test imports this module again,
# and the gate of an earlier import then reads a global that nothing set.
_DB_PATH_STATE = "exalted_account_db"


def _db_path() -> Path | None:
    return getattr(app.state, _DB_PATH_STATE, None)


def is_open_path(path: str) -> bool:
    """Return True if a visitor with no login can open `path`."""
    return (path in OPEN_PATHS or path.startswith(_OPEN_PREFIXES)
            or path == WIKI_PATH or path.startswith(WIKI_PATH + "/"))


def current_user_id() -> int | None:
    """Return the id of the account of the current request, or None.

    Return None also if the login recorded an older login epoch than the database
    holds, and remove that login. A password change, a reset, "Log out other
    devices" and a delete raise the epoch.
    """
    value = app.storage.user.get(USER_ID)
    if not isinstance(value, int):
        return None
    path = _db_path()
    if path is not None and \
            app.storage.user.get(LOGIN_EPOCH, 0) != db.login_epoch(path, value):
        log_out()
        return None
    return value


def current_username() -> str | None:
    """Return the username of the account of the current request, or None.

    ⚠ Read the database, not the name that the login stored. A rename on another
    device changes the database only.
    """
    user_id = current_user_id()
    if user_id is None:
        return None
    path = _db_path()
    return app.storage.user.get(USERNAME) if path is None else db.username_for(path, user_id)


def log_in(user_id: int, username: str) -> None:
    """Record the login of account `user_id` for the current browser, at the
    current login epoch of the account."""
    app.storage.user[USER_ID] = user_id
    app.storage.user[USERNAME] = username
    path = _db_path()
    app.storage.user[LOGIN_EPOCH] = 0 if path is None else db.login_epoch(path, user_id)


def log_out() -> None:
    """Remove the login of the current browser."""
    app.storage.user.pop(USER_ID, None)
    app.storage.user.pop(USERNAME, None)
    app.storage.user.pop(LOGIN_EPOCH, None)


def safe_target(target: str | None) -> str:
    """Return `target` if it is a path of this server. Return `HOME_PATH` in all
    other cases.

    ⚠ The login page sends the browser to `redirect_to`. An absolute URL there
    sends a player from this server to any site. "//host" is an absolute URL too.
    An open path is refused, because `/logout` there logs the player out again.
    """
    if (not target or not target.startswith("/") or target.startswith("//")
            or "\\" in target or target.split("?")[0] in OPEN_PATHS):
        return HOME_PATH
    return target


def login_url(target: str) -> str:
    """Return the URL of the login page that returns to `target`."""
    return f"/login?redirect_to={quote(safe_target(target), safe='/')}"


class AuthGate(BaseHTTPMiddleware):
    """Send each request without a login to the login page.

    ⚠ Install it BEFORE `ui.run`. `ui.run` then adds the session middleware
    outside it, thus `app.storage.user` is ready when this runs.
    """

    async def dispatch(self, request: Request, call_next):
        if not is_open_path(request.url.path) and current_user_id() is None:
            return RedirectResponse(login_url(request.url.path), status_code=303)
        return await call_next(request)


def install_gate() -> None:
    """Add `AuthGate` to the NiceGUI app. Do nothing if it is there."""
    if not any(middleware.cls is AuthGate for middleware in app.user_middleware):
        app.add_middleware(AuthGate)


def wait_text(seconds: float) -> str:
    """Return the refusal text for a login that must wait `seconds`."""
    if seconds < 60:
        return f"Too many failed attempts. Try again in {math.ceil(seconds)} seconds."
    return f"Too many failed attempts. Try again in {math.ceil(seconds / 60)} minutes."


def form_frame(current: str, username: str | None = None, *, cards: int = 1
               ) -> ui.element | list[ui.element]:
    """Draw the header bar and the footer of the public pages, and `cards` form
    cards between them. Return the card, or the list of the cards if `cards` is
    more than 1. `current` marks the button of the page in the header bar.
    `username` gives the menu of that login."""
    ui.colors(primary=theme.palette(None).accent)
    # The public pages have no padding around the header bar. NiceGUI pads its content.
    ui.add_head_html(f"<style>{site.style_sheet()}"
                     ".nicegui-content{padding:0;gap:0;align-items:stretch}</style>")
    ui.add_body_html(site.MENU_SCRIPT)
    ui.html(site.header_bar(current, username), sanitize=False)
    with ui.element("main").classes("page w-full"):
        made = [ui.element("section").classes("card auth") for _ in range(cards)]
    ui.html(site.FOOTER, sanitize=False)
    return made[0] if cards == 1 else made


def form_heading(title: str, lead: str) -> None:
    ui.html(f'<h1>{site.esc(title)}</h1><p class="lead muted">{site.esc(lead)}</p>',
            sanitize=False)


def form_aside(lines: list[str]) -> ui.element:
    """Draw the note area at the bottom of the card. Each item of `lines` is HTML
    that the caller escaped. Return the area, for more lines."""
    with ui.element("div").classes("aside") as area:
        for line in lines:
            ui.html(f"<p>{line}</p>", sanitize=False)
    return area


def register_auth_pages(db_path: Path, throttle: LoginThrottle | None = None) -> None:
    """Register `/login`, `/signup` and `/logout` against the database at `db_path`.

    `throttle` limits the login attempts. Omit it to make a new one.
    """
    setattr(app.state, _DB_PATH_STATE, db_path)
    throttle = LoginThrottle() if throttle is None else throttle

    @ui.page("/login", title="Log in — Exalted 1e")
    def login_page(redirect_to: str = HOME_PATH):
        target = safe_target(redirect_to)
        if current_user_id() is not None:
            return RedirectResponse(target, status_code=303)

        with form_frame("login"):
            form_heading("Log in", "Build characters and keep them on the server.")
            username = ui.input("Username").props("autofocus").classes(
                "w-full").mark("login-username")
            password = ui.input("Password", password=True,
                                password_toggle_button=True).classes(
                "w-full").mark("login-password")
            error = ui.label().classes("text-negative q-mt-xs")

            async def submit() -> None:
                name = db.normalise_username(username.value or "")
                # ⚠ `begin` counts the attempt before the await. See server/throttle.py.
                wait = throttle.begin(name)
                if wait > 0:
                    error.text = wait_text(wait)
                    password.value = ""
                    return
                user_id = await run.io_bound(
                    db.authenticate, db_path, name, password.value or "")
                if user_id is None:
                    error.text = "Wrong username or password."
                    password.value = ""
                    return
                throttle.succeeded(name)
                log_in(user_id, name)
                ui.navigate.to(target)

            password.on("keydown.enter", submit)
            ui.button("Log in", icon="login", on_click=submit).props("unelevated").classes(
                "w-full q-mt-md").mark("login-submit")
            signup = site.esc(f"/signup?redirect_to={quote(target, safe='/')}")
            with form_aside([f'No account? <a href="{signup}">Make an account</a>.']):
                contact = config.admin_contact()
                if contact:
                    ui.label(f"Forgot your password? Email {contact}.").classes(
                        "muted").mark("login-contact")
        return None

    @ui.page("/signup", title="Make an account — Exalted 1e")
    def signup_page(redirect_to: str = HOME_PATH):
        target = safe_target(redirect_to)
        if current_user_id() is not None:
            return RedirectResponse(target, status_code=303)

        with form_frame("signup"):
            form_heading("Make an account", "An account keeps your characters on the server.")
            username = ui.input("Username").props("autofocus").classes(
                "w-full").mark("signup-username")
            username.props["hint"] = f"{db.USERNAME_RULE} Case-sensitive."
            email = ui.input("Email (optional)").classes(
                "w-full q-mt-sm").mark("signup-email")
            email.props["hint"] = NO_EMAIL_NOTE
            password = ui.input("Password", password=True,
                                password_toggle_button=True).classes(
                "w-full q-mt-sm").mark("signup-password")
            password.props["hint"] = f"At least {db.MIN_PASSWORD_LENGTH} characters."
            confirm = ui.input("Password again", password=True).classes(
                "w-full q-mt-sm").mark("signup-confirm")
            error = ui.label().classes("text-negative q-mt-xs")

            async def submit() -> None:
                if (password.value or "") != (confirm.value or ""):
                    error.text = "The two passwords are different."
                    return
                try:
                    user_id = await run.io_bound(
                        db.create_user, db_path, username.value or "", password.value or "",
                        email=email.value or "")
                except db.AccountError as exc:
                    error.text = str(exc)
                    return
                log_in(user_id, db.normalise_username(username.value or ""))
                ui.navigate.to(target)

            confirm.on("keydown.enter", submit)
            ui.button("Make account", icon="person_add", on_click=submit).props(
                "unelevated").classes("w-full q-mt-md").mark("signup-submit")
            login = site.esc(login_url(target))
            form_aside([f'Have an account? <a href="{login}">Log in</a>.'])
        return None

    @ui.page("/logout")
    def logout_page():
        log_out()
        return RedirectResponse("/", status_code=303)
