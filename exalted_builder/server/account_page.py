"""
server/account_page.py — `/account`: the email, the password, the logins and the
delete of the account of the request. docs/plans/account-management.md.

Each change asks for the current password. The gate sends a visitor with no login
to the login page first.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from nicegui import run, ui

from . import accounts, auth, db, nav, site
from .characters import CharacterStore
from .session import SessionRegistry
from .tables import TableStore
from .throttle import LoginThrottle


def _password(label: str, marker: str) -> ui.input:
    return ui.input(label, password=True, password_toggle_button=True).classes(
        "w-full q-mt-sm").mark(marker)


def _message() -> ui.label:
    return ui.label().classes("q-mt-xs")


def _say(label: ui.label, text: str, *, error: bool, note: bool = False) -> None:
    """Show `text` in `label`: red for an error, amber for a `note`, green for all else."""
    label.text = text
    tone = ("text-negative" if error else "text-amber-800" if note else "text-positive")
    label.classes(replace=f"q-mt-xs {tone}")


async def _password_ok(db_path: Path, user_id: int, throttle: LoginThrottle,
                       field: ui.input, message: ui.label) -> bool:
    """Check the password in `field` against account `user_id`, through `throttle`.

    Return True if it is correct. Else show the refusal in `message`, clear `field`,
    and return False. The key is the username, thus the login page has the same count.
    """
    name = db.normalise_username(db.username_for(db_path, user_id) or "")
    # ⚠ `begin` counts the attempt before the await. See server/throttle.py.
    wait = throttle.begin(name)
    if wait > 0:
        text = auth.wait_text(wait)
    elif await run.io_bound(db.password_matches, db_path, user_id, field.value or ""):
        throttle.succeeded(name)
        return True
    else:
        text = "The current password is wrong."
    field.value = ""
    _say(message, text, error=True)
    return False


def register_account_page(db_path: Path, characters: CharacterStore, tables: TableStore,
                          sessions: SessionRegistry, throttle: LoginThrottle) -> None:
    """Register `/account` against the database at `db_path`.

    `sessions` is the character registry. The delete stops the open pages of the
    characters of the account through it. `throttle` limits the guesses at the
    current password. ⚠ Give the instance of the login page.
    """

    @ui.page(nav.ACCOUNT_PATH, title="Account — Exalted 1e")
    def account_page(renamed: str = ""):
        user_id = auth.current_user_id()
        if user_id is None:
            return None
        auth.bind_page(user_id)
        username = auth.current_username() or ""
        (email_card, name_card, password_card, logins_card, colours_card,
         delete_card) = auth.form_frame("account", username, cards=6, grid=True)

        with email_card:
            auth.form_heading("Account", f"Logged in as {username}.")
            stored = db.email_for(db_path, user_id)
            email = ui.input("Email", value=stored or "").classes("w-full").mark(
                "account-email")
            email.props["hint"] = ("The server admin sends a new password only to "
                                   "this address.")
            email_password = _password("Current password", "account-email-password")
            email_message = _message()
            if stored is None:
                _say(email_message, auth.NO_EMAIL_NOTE, error=False, note=True)

            async def save_email() -> None:
                if not await _password_ok(db_path, user_id, throttle, email_password,
                                          email_message):
                    return
                try:
                    await run.io_bound(db.set_email, db_path, user_id, email.value or "")
                except db.AccountError as exc:
                    _say(email_message, str(exc), error=True)
                    return
                email_password.value = ""
                _say(email_message, "Saved.", error=False)

            ui.button("Save email", icon="save", on_click=save_email).props(
                "unelevated").classes("w-full q-mt-md").mark("account-email-save")

        with name_card:
            ui.html("<h1>Username</h1>", sanitize=False)
            new_name = ui.input("New username").classes("w-full").mark("account-username")
            new_name.props["hint"] = (f"{db.USERNAME_RULE} Case-sensitive. Your old "
                                      "name becomes free for others.")
            name_password = _password("Current password", "account-username-password")
            name_message = _message()
            if renamed and renamed == username:
                _say(name_message, f"Changed. You log in as {username} now.", error=False)

            async def rename() -> None:
                if not await _password_ok(db_path, user_id, throttle, name_password,
                                          name_message):
                    return
                try:
                    name = await run.io_bound(db.rename_user, db_path, user_id,
                                              name_password.value or "",
                                              new_name.value or "")
                except db.AccountError as exc:
                    _say(name_message, str(exc), error=True)
                    return
                auth.log_in(user_id, name)
                # Draw the page again: the header bar and the menu show the name.
                ui.navigate.to(f"{nav.ACCOUNT_PATH}?renamed={quote(name)}")

            ui.button("Change username", icon="badge", on_click=rename).props(
                "unelevated").classes("w-full q-mt-md").mark("account-username-save")

        with password_card:
            ui.html("<h1>Password</h1>", sanitize=False)
            current = _password("Current password", "account-current")
            new = _password("New password", "account-new")
            new.props["hint"] = f"At least {db.MIN_PASSWORD_LENGTH} characters."
            again = _password("New password again", "account-again")
            password_message = _message()

            async def change() -> None:
                if (new.value or "") != (again.value or ""):
                    _say(password_message, "The two passwords are different.", error=True)
                    return
                if not await _password_ok(db_path, user_id, throttle, current,
                                          password_message):
                    return
                try:
                    await run.io_bound(db.change_password, db_path, user_id,
                                       current.value or "", new.value or "")
                except db.AccountError as exc:
                    _say(password_message, str(exc), error=True)
                    return
                # The change raised the epoch. Record it, thus this browser stays in.
                auth.log_in(user_id, username)
                auth.end_stale_pages()
                current.value = new.value = again.value = ""
                _say(password_message, "Changed. Every other device is logged out.",
                     error=False)

            ui.button("Change password", icon="key", on_click=change).props(
                "unelevated").classes("w-full q-mt-md").mark("account-password-save")

        with logins_card:
            ui.html("<h1>Devices</h1>", sanitize=False)
            ui.html('<p class="lead muted">End each login but this one: another '
                    'computer, a phone, a borrowed browser.</p>', sanitize=False)
            logins_message = _message()

            def log_out_others() -> None:
                db.raise_login_epoch(db_path, user_id)
                auth.log_in(user_id, username)
                auth.end_stale_pages()
                _say(logins_message, "Every other device is logged out.", error=False)

            ui.button("Log out other devices", icon="devices",
                      on_click=log_out_others).props("unelevated outline").classes(
                "w-full q-mt-sm").mark("account-logout-others")

        with colours_card.mark("account-colours"):
            ui.html("<h1>Site colours</h1>", sanitize=False)
            ui.html('<p class="lead muted">The colours of each page that shows no one '
                    'character. A character keeps the colours of its splat. Each '
                    'device of this account shows the choice.</p>' + site.theme_choices(nav.ACCOUNT_PATH),
                    sanitize=False)

        delete_card.classes(add="danger")
        with delete_card:
            ui.html("<h1>Delete account</h1>", sanitize=False)
            text = ('<p class="lead muted">This deletes each of your characters, your '
                    'campaign copies and your homebrew. It cannot be undone.</p>')
            campaigns = accounts.campaigns_run(tables, user_id)
            if campaigns:
                # ⚠ A list inside a <p> is invalid HTML. The browser moves it out.
                names = "".join(
                    f"<li>{site.esc(name)} — {members} "
                    f"member{'s' if members != 1 else ''}</li>"
                    for name, members in campaigns)
                text += ('<p class="lead muted">It also deletes the campaigns you run. '
                         'Each player keeps a copy of their character.</p>'
                         f'<ul class="campaigns">{names}</ul>')
            ui.html(text, sanitize=False)
            delete_password = _password("Current password", "account-delete-password")
            delete_message = _message()

            async def delete() -> None:
                if not await _password_ok(db_path, user_id, throttle, delete_password,
                                          delete_message):
                    return
                accounts.delete_account(user_id, characters=characters, tables=tables,
                                        sessions=sessions)
                auth.log_out()
                ui.navigate.to(nav.FRONT_PATH)
                # ⚠ After the navigation: this page ends too.
                auth.end_stale_pages()

            ui.button("Delete my account", icon="delete_forever", on_click=delete).props(
                "unelevated color=negative").classes("w-full q-mt-md").mark(
                "account-delete")
        return None
