"""
server/home.py — the landing page and the character pages of the hosted server.

Section 5 piece 4 of `docs/plans/hosting-state-model.md`; the site map and the
rulings of `docs/plans/vtt.md` sections 9.2 to 9.4:

  * `/home` lists the characters of the account: the drafts and the bases, then
    the campaign copies. It makes a new character and imports one from a file.
  * `/character/<id>` shows one character. A draft or a copy opens in the
    builder. A locked base opens on a read-only page: a base takes no XP, and a
    campaign copy is where a character advances (section 9.2).
  * A copy in a campaign has no Unlock, no Adjust XP and no Downtime. The
    Storyteller does these on the table view (p3-tables.md section 6, Q5, Q6).
  * A copy in a campaign takes the TABLE-WIDE house rules of its table each time
    its context is made. Its ST Options tab is read-only (section 5, Q2).
  * A draft for a campaign (step 6b) does the same, and its Finish & Lock sends
    the join request (`TableStore.send_draft`).
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
from ..engine.house_rule_actions import apply_table_rules
from ..models.character import Character, new_character_id
from ..models.party import Party
from ..models.rules import RuleSet
from ..ui import app as sheet_app
from ..ui import builder, theme
from ..ui.assets import cytoscape_head_html
from ..ui import custom as custom_mod
from ..ui import view as viewmod
from . import chrome
from .campaigns import HomeCampaigns
from .characters import CharacterRow, CharacterStore, CharacterStoreError
from .quota import QuotaExceeded
from .session import SessionRegistry
from .tables import TableStore, TableStoreError

HOME_PATH = chrome.HOME_PATH
CHARACTER_PATH = chrome.CHARACTER_PATH
character_url = chrome.character_url

# The largest file that the import control accepts. A character file is some
# kilobytes; a file with a large homebrew library is more. The account quota is
# 10 MB (server/quota.py), thus one import can never fill an account.
#
# ⚠ The browser applies this limit, not the server. `ui.upload` sets the Quasar
# `max-file-size` prop, and the upload route of NiceGUI reads the whole body. Thus
# this refuses the file that a person picks by mistake. It does not refuse a
# request that a program makes. That request needs the client id of a page of the
# account, thus a visitor with no login cannot make one.
MAX_IMPORT_BYTES = 2 * 1024 * 1024


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
                             adversary_catalog: dict,
                             tables: TableStore) -> SessionRegistry:
    """Register `/home` and `/character/<id>`. Return the registry of the contexts.

    `current_user_id` returns the account of the request. The server gives
    `auth.current_user_id`; the gate sends a visitor with no login away first.
    `tables` gives the Campaigns section of `/home`.
    """
    rulesets = AccountRulesets(book, store)

    def factory(character_id: str) -> dict:
        row = store.row(character_id)
        if row is None:
            raise KeyError(character_id)
        path = store.path_for(row)
        character = store.load(row)
        table_id = row.table_id or tables.draft_table(row.id)
        if table_id is not None:
            # ⚠ Site 3 of p3-tables.md section 5: the table's values, whatever the
            # file says. A copy that missed a switch is in step at its next load.
            # A draft for a campaign (step 6b) is built under them too.
            if apply_table_rules(tables.house_rules(table_id), character):
                # The auto-save takes its first digest after this, thus it would
                # not write the change. A full account keeps the old file.
                try:
                    store.save(row, character)
                except (QuotaExceeded, OSError):
                    pass
        return {"char": character, "path": path, "dir": path.parent,
                "home_dir": store.account_dir(row.owner_id),
                "custom_dir": store.custom_dir(row.owner_id),
                "ruleset": rulesets.for_account(row.owner_id),
                "party": Party(id="party.new"), "party_path": None, "member": None,
                "adversary_catalog": adversary_catalog, "row": row}

    sessions = SessionRegistry(factory=factory)

    def _account() -> int:
        return chrome.require_account(current_user_id)

    @ui.page(HOME_PATH)
    def home_page() -> None:
        _build_home(store, tables, rulesets, sessions, _account())

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

        # A draft for a campaign (step 6b). Read at each open: the tag goes at the lock.
        draft_for = None if row.is_copy else tables.draft_table(row.id)
        draft_table = tables.table(draft_for) if draft_for is not None else None

        def after_lock() -> None:
            store.save(row, ctx["char"])
            if draft_table is not None:
                try:
                    request = tables.send_draft(user_id, row.id)
                    if request is not None and request.approved:
                        ui.notify(f"Added to {draft_table.name}.", type="positive")
                    elif request is not None:
                        ui.notify(f"Sent to {draft_table.name}. It waits for the "
                                  "Storyteller.", type="positive")
                except TableStoreError as exc:
                    ui.notify(str(exc), type="warning")
            ui.navigate.to(character_url(row.id))

        builder.build_app(ctx["ruleset"], ctx["char"], ctx["path"], ctx=ctx, hosted=True,
                          home_path=HOME_PATH,
                          on_lock=None if row.is_copy else after_lock,
                          in_campaign=row.table_id is not None,
                          campaign_draft=draft_table.name if draft_table else None)

    return sessions


# --------------------------------------------------------------------------- #
# The pages
# --------------------------------------------------------------------------- #


def _not_found() -> None:
    """The answer for a character of another account and for one that is absent."""
    pal = theme.palette(None)
    with chrome.header(pal, "Exalted 1e"):
        chrome.home_button()
    ui.label("There is no such character.").classes("text-base p-4").mark("not-found")


def _build_home(store: CharacterStore, tables: TableStore, rulesets: AccountRulesets,
                sessions: SessionRegistry, user_id: int) -> None:
    pal = theme.palette(None)
    # The Homebrew tab draws a Charm tree.
    ui.add_head_html(cytoscape_head_html())
    with chrome.header(pal, "Exalted 1e — Your characters"):
        ui.button("Wiki", icon="menu_book", on_click=lambda: ui.navigate.to("/wiki")).props(
            "flat color=white")
        chrome.logout_button()

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

    def on_rejected(_) -> None:
        """Tell the user why the import control took no file.

        The browser rejects a file that is larger than `MAX_IMPORT_BYTES`, or that
        is not a `.json` file. Without this, the control takes the file and does
        nothing, and the page gives no message.
        """
        ui.notify(f"Import failed: a character file must be a .json file of "
                  f"{MAX_IMPORT_BYTES // 2**20} MB or less.", type="negative")

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

    ruleset = rulesets.for_account(user_id)

    page = ui.column().classes("w-full px-4 py-2 gap-2")

    # Two sections: the characters, and the homebrew library of the account. The
    # library belongs to the account, not to one character, thus it is here and
    # not a tab of the character page.
    with page:
        with ui.tabs(value="characters").classes("w-full") as section_tabs:
            ui.tab("characters", label="Characters", icon="groups")
            ui.tab("homebrew", label="Homebrew", icon="construction")
        # ⚠ No slide animation: the two panels differ in width, and the slide
        # drew both at once for its length.
        with ui.tab_panels(section_tabs, value="characters", animated=False).classes(
                "w-full bg-transparent"):
            with ui.tab_panel("homebrew").classes("p-0"):
                custom_mod.build_custom(ruleset, custom_dir=store.custom_dir(user_id),
                                        with_header=False, show_path=False)
            with ui.tab_panel("characters").classes("p-0"):
                # The characters sit in a centred column; the homebrew form
                # needs the full width.
                characters_panel = ui.column().classes(
                    "w-full max-w-5xl mx-auto gap-4")

    with characters_panel:
        # The upload control of Quasar draws a blue box with a progress readout.
        # It stays hidden; the Import button opens its file picker.
        upload = ui.upload(auto_upload=True, on_upload=on_import,
                           max_file_size=MAX_IMPORT_BYTES,
                           on_rejected=on_rejected).props(
            "accept=.json").classes("hidden").mark("home-import")
        with ui.row().classes("w-full items-end justify-between gap-2 pt-2"):
            with ui.column().classes("gap-0"):
                ui.label("Your characters").classes("text-2xl font-bold").style(
                    f"color:{pal.accent}")
                ui.label("A draft becomes a base when you finish and lock it. Play "
                         "a base through a campaign copy.").classes("text-sm opacity-70")
            with ui.row().classes("gap-2"):
                ui.button("Import from file", icon="upload_file",
                          on_click=lambda: upload.run_method("pickFiles")).props(
                    f"outline color={pal.button}")
                ui.button("New character", icon="person_add", on_click=new_character).props(
                    f"color={pal.button}").mark("home-new")

    @ui.refreshable
    def listing() -> None:
        rows = store.list_for(user_id)
        entries = {row.id: chrome.entry(store, ruleset, row) for row in rows}
        characters = [row for row in rows if not row.is_copy]
        copies = [row for row in rows if row.is_copy]
        bases = {row.id: entries[row.id].name for row in characters
                 if entries[row.id].stage == "Base"}
        campaign_names = campaigns.table_names()

        chrome.section_label(pal, "CHARACTERS", len(characters))
        if not characters:
            with ui.card().classes(f"w-full p-8 items-center gap-1 {pal.card_soft}"):
                ui.icon("person_add").classes("text-5xl opacity-40")
                ui.label("No characters yet").classes("text-base font-bold")
                ui.label("Start one with New character, or import a .character.json "
                         "that you downloaded.").classes("text-sm opacity-70")
        with chrome.grid():
            for row in characters:
                entry = entries[row.id]
                draft_for = tables.draft_table(row.id)
                detail = (f"For {campaign_names[draft_for]}"
                          if draft_for in campaign_names else None)
                with chrome.character_card(entry, row, detail=detail):
                    if entry.stage == "Base":
                        ui.button("Campaign copy", icon="content_copy",
                                  on_click=lambda _=None, r=row: make_copy(r)).props(
                            "flat dense no-caps size=sm").mark(f"home-copy-{row.id}") \
                            .tooltip("Make a campaign copy to play and advance")
                        ui.button("Join", icon="group_add",
                                  on_click=lambda _=None, r=row.id:
                                  campaigns.open_join(bases, r)).props(
                            "flat dense no-caps size=sm").mark(f"home-join-with-{row.id}") \
                            .tooltip("Join a campaign with this character")
                    _delete_button(row, entry.name)

        chrome.section_label(pal, "CAMPAIGN COPIES", len(copies))
        if not copies:
            ui.label("A campaign copy is made from a locked base. It takes XP; the "
                     "base does not.").classes("text-sm opacity-70")
        with chrome.grid():
            for row in copies:
                entry = entries[row.id]
                origin = (f"Copy of {entries[row.base_id].name}" if row.base_id in entries
                          else "Its base is deleted")
                if row.table_id in campaign_names:
                    origin += f" · In {campaign_names[row.table_id]}"
                with chrome.character_card(entry, row, detail=origin):
                    _delete_button(row, entry.name)

        campaigns.draw(bases, {row_id: e.name for row_id, e in entries.items()})

    def _delete_button(row: CharacterRow, name: str) -> None:
        ui.button(icon="delete_outline",
                  on_click=lambda _=None, r=row, n=name: confirm_delete(r, n)).props(
            "flat dense round size=sm color=negative").mark(
            f"home-delete-{row.id}").tooltip("Delete")

    campaigns = HomeCampaigns(tables, store, user_id, refresh=lambda: listing.refresh())

    with characters_panel:
        listing()


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

    with chrome.header(pal, f"Exalted 1e — {pal.splat_label} Base"):
        chrome.home_button()
        ui.button("Make a campaign copy", icon="content_copy", on_click=make_copy).props(
            "flat color=white").mark("base-copy")
        ui.button("Unlock to edit", icon="lock_open", on_click=unlock).props(
            "flat color=white").mark("base-unlock")
        ui.button("Download a copy", icon="download", on_click=download).props(
            "flat color=white").mark("top-bar-download")
        chrome.logout_button()

    ui.label("A base character. It takes no XP. Make a campaign copy to play and "
             "advance it; the base stays as it is.").classes("text-sm p-2").mark("base-note")
    sheet_app.render_sheet(viewmod.build_sheet_view(ruleset, character))
