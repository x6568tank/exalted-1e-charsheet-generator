"""
server/home.py — the landing page and the character pages of the hosted server.

Section 5 piece 4 of `docs/plans/hosting-state-model.md`; the site map and the
rulings of `docs/plans/vtt.md` sections 9.2 to 9.4:

  * `/home` lists the characters of the account: the drafts and the bases, then
    the campaign copies. It makes a new character and imports one from a file.
  * `/character/<id>` shows one character. A draft or a copy opens in the
    builder. A locked base opens on a read-only page: a base takes no XP, and a
    campaign copy is where a character advances (section 9.2).
  * There is no `/gm` on the server until P3 (ruled 2026-09-12, 9.3a).

⚠ The ownership check is `CharacterStore.owned`, in the page body, before the
registry. A character of another account gets the same answer as one that does
not exist, and no context is made for it.

⚠ One context for each CHARACTER, keyed on its id. Thus two devices on one
character share it, and two devices can open two characters (section 9.1). One
RuleSet for each ACCOUNT: all its characters see the homebrew of its library.
"""

from __future__ import annotations

from collections.abc import Callable

from nicegui import ui

from .. import custom_content, persistence, rules_db
from ..engine import lifecycle
from ..models.character import Character, new_character_id
from ..models.party import Party
from ..models.rules import RuleSet
from ..ui import app as sheet_app
from ..ui import builder, theme
from ..ui import view as viewmod
from . import auth
from .characters import CharacterRow, CharacterStore, CharacterStoreError
from .session import SessionRegistry

HOME_PATH = auth.HOME_PATH
CHARACTER_PATH = "/character"


def character_url(character_id: str) -> str:
    """Return the page of the character `character_id`."""
    return f"{CHARACTER_PATH}/{character_id}"


class AccountRulesets:
    """One RuleSet for each account: the book with the library of the account.

    Made on first use, and kept. The Custom tab and an import reload it in place,
    thus each character of the account sees a change at once.
    """

    def __init__(self, book: RuleSet, store: CharacterStore) -> None:
        self._book = book
        self._store = store
        self._rulesets: dict[int, RuleSet] = {}

    def for_account(self, user_id: int) -> RuleSet:
        """Return the RuleSet of account `user_id`."""
        if user_id not in self._rulesets:
            self._rulesets[user_id] = rules_db.with_custom_layer(
                self._book, self._store.custom_dir(user_id))
        return self._rulesets[user_id]


def import_character(store: CharacterStore, rulesets: AccountRulesets, user_id: int,
                     text: str) -> tuple[CharacterRow, list[str]]:
    """Store the character in the JSON `text` as a new character of `user_id`.

    Put the homebrew that the file carries into the library of the account, and
    reload the RuleSet of the account. Return the new row and the ids of the
    homebrew rows that were added. A parse error propagates.
    """
    character = persistence.character_from_json(text)
    custom_dir = store.custom_dir(user_id)
    added = custom_content.absorb_definitions(character, custom_dir=custom_dir)
    if added:
        rules_db.reload_custom_layer(rulesets.for_account(user_id), custom_dir)
    return store.create(user_id, character), added


def register_character_pages(store: CharacterStore, book: RuleSet,
                             current_user_id: Callable[[], int | None],
                             adversary_catalog: dict) -> SessionRegistry:
    """Register `/home` and `/character/<id>`. Return the registry of the contexts.

    `current_user_id` returns the account of the request. The server gives
    `auth.current_user_id`; the gate sends a visitor with no login away first.
    """
    rulesets = AccountRulesets(book, store)

    def factory(character_id: str) -> dict:
        row = store.row(character_id)
        if row is None:
            raise KeyError(character_id)
        path = store.path_for(row)
        return {"char": store.load(row), "path": path, "dir": path.parent,
                "home_dir": store.account_dir(row.owner_id),
                "custom_dir": store.custom_dir(row.owner_id),
                "ruleset": rulesets.for_account(row.owner_id),
                "party": Party(id="party.new"), "party_path": None, "member": None,
                "adversary_catalog": adversary_catalog, "row": row}

    sessions = SessionRegistry(factory=factory)

    def _account() -> int:
        user_id = current_user_id()
        if user_id is None:
            raise PermissionError("No account is logged in. The login gate did not run.")
        return user_id

    @ui.page(HOME_PATH)
    def home_page() -> None:
        _build_home(store, rulesets, sessions, _account())

    @ui.page(CHARACTER_PATH + "/{character_id}")
    def character_page(character_id: str) -> None:
        user_id = _account()
        row = store.owned(user_id, character_id)
        if row is None:
            _not_found()
            return
        ctx = sessions.ctx_for(row.id)
        if not row.is_copy and ctx["char"].chargen_locked:
            _build_base(store, sessions, row, ctx, user_id)
            return

        def after_lock() -> None:
            store.save(row, ctx["char"])
            ui.navigate.to(character_url(row.id))

        builder.build_app(ctx["ruleset"], ctx["char"], ctx["path"], ctx=ctx, hosted=True,
                          home_path=HOME_PATH,
                          on_lock=None if row.is_copy else after_lock)

    return sessions


# --------------------------------------------------------------------------- #
# The pages
# --------------------------------------------------------------------------- #


def _header(pal, title: str) -> ui.row:
    """Draw the top bar of the builder. Return the row for its buttons."""
    with ui.header().classes("items-center justify-between px-4").style(
            f"background:{pal.accent}"):
        ui.label(title).classes("text-lg font-bold text-white")
        buttons = ui.row().classes("items-center gap-2")
    ui.query("body").style(f"background:{pal.bg};color:{pal.ink}")
    return buttons


def _logout_button() -> None:
    ui.button("Log out", icon="logout", on_click=lambda: ui.navigate.to("/logout")).props(
        "flat color=white").mark("top-bar-logout")


def _not_found() -> None:
    """The answer for a character of another account and for one that is absent."""
    pal = theme.palette(None)
    with _header(pal, "Exalted 1e"):
        ui.button("Home", icon="home", on_click=lambda: ui.navigate.to(HOME_PATH)).props(
            "flat color=white").mark("top-bar-home")
    ui.label("There is no such character.").classes("text-base p-4").mark("not-found")


def _build_home(store: CharacterStore, rulesets: AccountRulesets,
                sessions: SessionRegistry, user_id: int) -> None:
    pal = theme.palette(None)
    with _header(pal, "Exalted 1e — Your characters"):
        ui.button("Wiki", icon="menu_book", on_click=lambda: ui.navigate.to("/wiki")).props(
            "flat color=white")
        _logout_button()

    def new_character() -> None:
        row = store.create(user_id, Character(id=new_character_id()))
        ui.navigate.to(character_url(row.id))

    async def on_import(e) -> None:
        try:
            row, added = import_character(store, rulesets, user_id, await e.file.text())
        except Exception as ex:                     # noqa: BLE001 - surface any parse or write error
            ui.notify(f"Import failed: {ex}", type="negative")
            return
        if added:
            ui.notify(f"Imported {len(added)} homebrew definition(s) into your library",
                      type="info")
        ui.navigate.to(character_url(row.id))

    def make_copy(row: CharacterRow) -> None:
        try:
            copy = store.make_copy(user_id, row.id)
        except CharacterStoreError as ex:
            ui.notify(str(ex), type="warning")
            return
        ui.navigate.to(character_url(copy.id))

    def confirm_delete(row: CharacterRow, name: str) -> None:
        with ui.dialog() as dialog, ui.card().classes(f"w-[28rem] p-4 gap-2 {pal.card_solid}"):
            ui.label(f"Delete {name}?").classes("text-base font-bold")
            ui.label("This removes the character and its file. It cannot be undone. "
                     "Campaign copies made from it stay.").classes("text-xs")
            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancel", on_click=dialog.close).props("flat")

                def confirm() -> None:
                    dialog.close()
                    _delete(store, sessions, user_id, row)
                    listing.refresh()
                    ui.notify(f"Deleted {name}", type="info")

                ui.button("Delete", on_click=confirm, color="negative").mark("home-confirm-delete")
        dialog.open()

    with ui.row().classes("w-full items-center gap-2 p-2"):
        ui.button("New character", icon="person_add", on_click=new_character).props(
            f"color={pal.button}").mark("home-new")
        ui.upload(label="Import a .character.json", auto_upload=True, on_upload=on_import) \
            .props("accept=.json flat dense").classes("max-w-[16rem]").mark("home-import")

    @ui.refreshable
    def listing() -> None:
        rows = store.list_for(user_id)
        entries = {row.id: _entry(store, row) for row in rows}
        characters = [row for row in rows if not row.is_copy]
        copies = [row for row in rows if row.is_copy]

        with ui.card().classes(f"w-full p-3 gap-1 {pal.card}"):
            ui.label(f"CHARACTERS ({len(characters)})").classes(
                "text-xs font-bold tracking-widest").style(f"color:{pal.accent}")
            if not characters:
                ui.label("None yet. Press New character, or import a file.").classes(
                    "text-xs text-gray-500")
            for row in characters:
                name, stage = entries[row.id]
                with ui.row().classes("w-full items-center gap-2 no-wrap").mark(
                        f"home-row-{row.id}"):
                    ui.link(name, character_url(row.id)).classes("text-sm flex-1")
                    ui.label(stage).classes("text-xs text-gray-600")
                    if stage == "Base":
                        ui.button("Make a campaign copy", icon="content_copy",
                                  on_click=lambda _=None, r=row: make_copy(r)).props(
                            "flat dense size=sm").mark(f"home-copy-{row.id}")
                    ui.button(icon="delete",
                              on_click=lambda _=None, r=row, n=name: confirm_delete(r, n)
                              ).props("flat dense size=sm color=negative").mark(
                        f"home-delete-{row.id}")

        with ui.card().classes(f"w-full p-3 gap-1 {pal.card}"):
            ui.label(f"CAMPAIGN COPIES ({len(copies)})").classes(
                "text-xs font-bold tracking-widest").style(f"color:{pal.accent}")
            if not copies:
                ui.label("A campaign copy is made from a locked base. It takes XP; the "
                         "base does not.").classes("text-xs text-gray-500")
            for row in copies:
                name, _stage = entries[row.id]
                origin = (f"Copy of {entries[row.base_id][0]}" if row.base_id in entries
                          else "Its base is deleted")
                with ui.row().classes("w-full items-center gap-2 no-wrap").mark(
                        f"home-row-{row.id}"):
                    ui.link(name, character_url(row.id)).classes("text-sm flex-1")
                    ui.label(origin).classes("text-xs text-gray-600")
                    ui.button(icon="delete",
                              on_click=lambda _=None, r=row, n=name: confirm_delete(r, n)
                              ).props("flat dense size=sm color=negative").mark(
                        f"home-delete-{row.id}")

    listing()


def _entry(store: CharacterStore, row: CharacterRow) -> tuple[str, str]:
    """Return the name and the stage ("Draft", "Base", "Copy") that the list shows.

    The file gives both. A file that does not read is listed, so it can be deleted."""
    try:
        character = store.load(row)
    except Exception:                               # noqa: BLE001 - list it, do not crash the page
        return f"(unreadable: {row.id})", "Unreadable"
    name = character.name or "Unnamed character"
    if row.is_copy:
        return name, "Copy"
    return name, "Base" if character.chargen_locked else "Draft"


def _delete(store: CharacterStore, sessions: SessionRegistry, user_id: int,
            row: CharacterRow) -> None:
    """Delete the character, and stop an open page of it from writing its file again.

    ⚠ A page that is still open holds the context, and its auto-save writes to
    `ctx["path"]`. Without the None, that write makes the file again, with no row.
    The page then reports that the auto-save failed."""
    if row.id in sessions:
        sessions.ctx_for(row.id)["path"] = None
        sessions.discard(row.id)
    store.delete(user_id, row.id)


def _build_base(store: CharacterStore, sessions: SessionRegistry, row: CharacterRow,
                ctx: dict, user_id: int) -> None:
    """The read-only page of a locked base (section 9.2). A base takes no XP."""
    character = ctx["char"]
    ruleset = ctx["ruleset"]
    pal = theme.palette(character.exalt_type)

    def unlock() -> None:
        lifecycle.unlock_chargen(character)
        store.save(row, character)
        ui.navigate.to(character_url(row.id))

    def make_copy() -> None:
        try:
            copy = store.make_copy(user_id, row.id)
        except CharacterStoreError as ex:
            ui.notify(str(ex), type="warning")
            return
        ui.navigate.to(character_url(copy.id))

    def download() -> None:
        ui.download.content(persistence.character_to_json(character).encode("utf-8"),
                            persistence.suggested_filename(character))

    with _header(pal, f"Exalted 1e — {pal.splat_label} Base"):
        ui.button("Home", icon="home", on_click=lambda: ui.navigate.to(HOME_PATH)).props(
            "flat color=white").mark("top-bar-home")
        ui.button("Make a campaign copy", icon="content_copy", on_click=make_copy).props(
            "flat color=white").mark("base-copy")
        ui.button("Unlock to edit", icon="lock_open", on_click=unlock).props(
            "flat color=white").mark("base-unlock")
        ui.button("Download a copy", icon="download", on_click=download).props(
            "flat color=white").mark("top-bar-download")
        _logout_button()

    ui.label("A base character. It takes no XP. Make a campaign copy to play and "
             "advance it; the base stays as it is.").classes("text-sm p-2").mark("base-note")
    sheet_app.render_sheet(viewmod.build_sheet_view(ruleset, character))
