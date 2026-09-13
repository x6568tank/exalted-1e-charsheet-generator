"""
server/campaigns.py — the campaign pages of the hosted server.

Step 2 of the build order in `docs/plans/p3-tables.md`, sections 7 and 11. The
rulings are `docs/plans/vtt.md` section 9.10:

  * The Campaigns section of `/home`: the campaigns of the account, New
    campaign, Join a campaign (a code, then a base to bring or "just watch"), and
    the requests that wait for a Storyteller.
  * `/table/<id>`: the campaign, its characters and its members. The Storyteller
    also sees the join code and the requests, with Approve and Reject.

⚠ `TableStore.access` is the check. The page calls it in the page body, before
it reads anything of the table, and each handler calls it again. The store also
refuses each Storyteller operation. A hidden button is not a check.

⚠ A campaign of which the account is not a member gets the same answer as a
campaign that does not exist. A pending request gives no access.

⚠ Cancel one request with `TableStore.withdraw`, never with `leave`. `leave` also
ends the membership of a member who asked to bring another character.
"""

from __future__ import annotations

from collections.abc import Callable

from nicegui import ui

from ..models.character import Character
from ..models.rules import RuleSet
from ..ui import theme
from . import chrome, db
from .characters import CharacterRow, CharacterStore
from .quota import QuotaExceeded
from .tables import STORYTELLER, TableRow, TableStore, TableStoreError

TABLE_PATH = chrome.TABLE_PATH
table_url = chrome.table_url

# The value of the join form for "just watch": a request with no base.
WATCH = "watch"

# The words for each kind of carried homebrew, singular and plural.
_CARRIED_WORDS = {"charms": ("Charm", "Charms"), "spells": ("spell", "spells"),
                  "rituals": ("ritual", "rituals")}


def carried_summary(character: Character) -> str | None:
    """Return one line that names the homebrew that `character` carries, or None.

    Section 4 of p3-tables.md: the Storyteller sees this before an approval.
    """
    parts = []
    for key, (one, many) in _CARRIED_WORDS.items():
        rows = [row for row in (character.custom_definitions or {}).get(key, [])
                if isinstance(row, dict)]
        if rows:
            names = ", ".join(str(row.get("name") or row.get("id") or "?") for row in rows)
            parts.append(f"{len(rows)} {one if len(rows) == 1 else many} ({names})")
    return "Carries homebrew: " + "; ".join(parts) if parts else None


def _username(tables: TableStore, user_id: int) -> str:
    return db.username_for(tables.db_path, user_id) or "(a deleted account)"


def _plural(count: int, one: str, many: str) -> str:
    return f"{count} {one if count == 1 else many}"


# --------------------------------------------------------------------------- #
# /home — the Campaigns section
# --------------------------------------------------------------------------- #


class HomeCampaigns:
    """The Campaigns section of `/home` for account `user_id`.

    `refresh` redraws the list of `/home`. The home page calls `draw` inside that
    list, thus a change here redraws the characters and the campaigns together.
    """

    def __init__(self, tables: TableStore, store: CharacterStore, user_id: int,
                 refresh: Callable[[], None]) -> None:
        self.tables = tables
        self.store = store
        self.user_id = user_id
        self.refresh = refresh
        self.pal = theme.palette(None)

    def table_names(self) -> dict[str, str]:
        """Return the name of each campaign that the account runs or is a member of."""
        return {table.id: table.name for table in self.tables.for_user(self.user_id)}

    # ---- dialogs ------------------------------------------------------------ #

    def open_new(self) -> None:
        """Open the New campaign form. A campaign made here opens at once."""
        with ui.dialog() as dialog, ui.card().classes(
                f"w-[28rem] p-4 gap-2 {self.pal.card_solid}"):
            ui.label("New campaign").classes("text-base font-bold")
            ui.label("You are its Storyteller. Players join with a code, and you "
                     "approve each request.").classes("text-xs")
            name = ui.input("Name").classes("w-full").mark("campaign-name")

            def create() -> None:
                try:
                    table = self.tables.create(self.user_id, name.value or "")
                except TableStoreError as exc:
                    ui.notify(str(exc), type="warning")
                    return
                dialog.close()
                ui.navigate.to(table_url(table.id))

            name.on("keydown.enter", create)
            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button("Create", on_click=create).props(
                    f"color={self.pal.button}").mark("campaign-create")
        dialog.open()

    def open_join(self, bases: dict[str, str], base_id: str | None = None) -> None:
        """Open the Join a campaign form. `bases` maps the id of each locked base
        of the account to its name. `base_id` is the choice at the start."""
        options = {**bases, WATCH: "Just watch"}
        start = base_id if base_id in bases else next(iter(bases), WATCH)
        with ui.dialog() as dialog, ui.card().classes(
                f"w-[28rem] p-4 gap-2 {self.pal.card_solid}"):
            ui.label("Join a campaign").classes("text-base font-bold")
            ui.label("Ask the Storyteller for the code. The Storyteller approves "
                     "each request. An approval makes a campaign copy of the "
                     "character that you bring.").classes("text-xs")
            code = ui.input("Code").classes("w-full").props(
                "autocapitalize=characters").mark("join-code")
            choice = ui.select(options, value=start, label="Bring").classes(
                "w-full").mark("join-base")
            if not bases:
                ui.label("You have no base character. Finish and lock a character "
                         "to bring it, or join to watch.").classes("text-xs opacity-70")

            def send() -> None:
                base = None if choice.value == WATCH else choice.value
                try:
                    self.tables.request(self.user_id, code.value or "", base)
                except TableStoreError as exc:
                    ui.notify(str(exc), type="warning")
                    return
                dialog.close()
                self.refresh()
                ui.notify("Request sent. It waits for the Storyteller.", type="info")

            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button("Send request", on_click=send).props(
                    f"color={self.pal.button}").mark("join-send")
        dialog.open()

    # ---- the section -------------------------------------------------------- #

    def draw(self, bases: dict[str, str], names: dict[str, str]) -> None:
        """Draw the section. `bases` are the locked bases of the account, and
        `names` gives the name of each character of the account."""
        pal = self.pal
        tables = self.tables.for_user(self.user_id)
        rows = self.store.list_for(self.user_id)

        with ui.row().classes("w-full items-end justify-between gap-2"):
            chrome.section_label(pal, "CAMPAIGNS", len(tables))
            with ui.row().classes("gap-2"):
                ui.button("Join a campaign", icon="group_add",
                          on_click=lambda: self.open_join(bases)).props(
                    f"outline dense no-caps color={pal.button}").mark("home-join")
                ui.button("New campaign", icon="add", on_click=self.open_new).props(
                    f"dense no-caps color={pal.button}").mark("home-new-campaign")
        if not tables:
            ui.label("Run a campaign with New campaign, or join one with the code "
                     "that its Storyteller gives you.").classes("text-sm opacity-70")
        with chrome.grid():
            for table in tables:
                mine = [names.get(row.id, "?") for row in rows if row.table_id == table.id]
                self._campaign_card(table, mine)

        waiting = self.tables.requests_by(self.user_id)
        if waiting:
            chrome.section_label(pal, "WAITING FOR THE STORYTELLER", len(waiting))
            with ui.column().classes("w-full gap-2"):
                for request in waiting:
                    table = self.tables.table(request.table_id)
                    what = (f"to bring {names.get(request.base_id, 'a character')}"
                            if request.base_id else "to watch")
                    with ui.card().classes(f"w-full px-3 py-2 {pal.card_soft}").mark(
                            f"home-request-{request.id}"):
                        with ui.row().classes("w-full items-center justify-between gap-2"):
                            with ui.column().classes("gap-0"):
                                ui.label(table.name if table else "A deleted campaign") \
                                    .classes("text-base font-bold")
                                ui.label(f"You asked {what}.").classes("text-sm opacity-80")
                            ui.button("Withdraw", icon="undo",
                                      on_click=lambda _=None, r=request.id:
                                      self._withdraw(r)).props(
                                "flat dense no-caps").mark(f"home-withdraw-{request.id}")

    def _campaign_card(self, table: TableRow, mine: list[str]) -> None:
        pal = self.pal
        is_st = table.storyteller_id == self.user_id
        members = len(self.tables.members(table.id))
        with ui.card().classes(f"p-0 gap-0 overflow-hidden {pal.card}").mark(
                f"home-campaign-{table.id}"):
            ui.element("div").classes("w-full h-1").style(f"background:{pal.accent}")
            with ui.link(target=table_url(table.id)).classes(
                    "w-full no-underline text-inherit px-3 pt-2 pb-2 hover:bg-black/5"):
                with ui.row().classes("w-full items-start justify-between no-wrap gap-2"):
                    ui.label(table.name).classes("text-base font-bold truncate min-w-0")
                    ui.badge("Storyteller" if is_st else "Player").props("outline").style(
                        f"color:{pal.accent}")
                if mine:
                    ui.label("Your characters: " + ", ".join(mine)).classes("text-sm")
                elif not is_st:
                    ui.label("Watching").classes("text-sm opacity-80")
                ui.label(_plural(members, "member", "members")).classes(
                    "text-xs opacity-60")
                if is_st:
                    ui.label(f"Code {table.join_code}").classes(
                        "text-xs font-mono opacity-80 pt-1")
                    waiting = len(self.tables.pending(self.user_id, table.id))
                    if waiting:
                        ui.label(_plural(waiting, "request waiting", "requests waiting")) \
                            .classes("text-xs font-bold").style(f"color:{pal.accent}")

    def _withdraw(self, request_id: int) -> None:
        if self.tables.withdraw(self.user_id, request_id):
            ui.notify("Request withdrawn.", type="info")
        self.refresh()


# --------------------------------------------------------------------------- #
# /table/<id>
# --------------------------------------------------------------------------- #


def register_table_page(tables: TableStore, store: CharacterStore, book: RuleSet,
                        current_user_id: Callable[[], int | None]) -> None:
    """Register `/table/<id>`.

    `book` gives the labels of the castes on the character cards. `current_user_id`
    returns the account of the request.
    """

    @ui.page(TABLE_PATH + "/{table_id}")
    def table_page(table_id: str) -> None:
        user_id = chrome.require_account(current_user_id)
        # ⚠ Before anything that reads the table.
        role = tables.access(user_id, table_id)
        table = tables.table(table_id) if role is not None else None
        if table is None:
            _not_found()
            return
        _build_table(tables, store, book, user_id, table)


def _not_found() -> None:
    """The answer for a campaign of which the account is not a member, and for
    one that is absent."""
    with chrome.header(theme.palette(None), "Exalted 1e"):
        chrome.home_button()
    ui.label("There is no such campaign.").classes("text-base p-4").mark("table-not-found")


def _build_table(tables: TableStore, store: CharacterStore, book: RuleSet,
                 user_id: int, table: TableRow) -> None:
    pal = theme.palette(None)
    is_st = table.storyteller_id == user_id

    with chrome.header(pal, "Exalted 1e — Campaign"):
        chrome.home_button()
        chrome.logout_button()

    page = ui.column().classes("w-full max-w-5xl mx-auto px-4 py-2 gap-4")
    with page:
        with ui.column().classes("gap-0 pt-2"):
            ui.label(table.name).classes("text-2xl font-bold").style(
                f"color:{pal.accent}").mark("table-title")
            ui.label("You are the Storyteller." if is_st else
                     f"Storyteller: {_username(tables, table.storyteller_id)}").classes(
                "text-sm opacity-70")
        if is_st:
            with ui.card().classes(f"w-full px-4 py-3 gap-1 {pal.card}").mark("table-code"):
                ui.label("JOIN CODE").classes("text-xs font-bold tracking-widest").style(
                    f"color:{pal.accent}")
                ui.label(table.join_code).classes("text-3xl font-mono font-bold")
                ui.label("Give this code to your players. A code lets a player ask to "
                         "join; you approve each request below.").classes(
                    "text-sm opacity-70")

    def still_storyteller() -> bool:
        """⚠ Each handler asks again. The Storyteller can delete the campaign on a
        second device while this page is open."""
        if tables.access(user_id, table.id) == STORYTELLER:
            return True
        ui.notify("You are not the Storyteller of this campaign.", type="negative")
        return False

    def approve(request_id: int) -> None:
        if not still_storyteller():
            return
        try:
            tables.approve(user_id, request_id)
        except (TableStoreError, QuotaExceeded) as exc:
            ui.notify(str(exc), type="warning")
        else:
            ui.notify("Approved.", type="positive")
        body.refresh()

    def reject(request_id: int) -> None:
        if not still_storyteller():
            return
        try:
            tables.reject(user_id, request_id)
        except TableStoreError as exc:
            ui.notify(str(exc), type="warning")
        body.refresh()

    @ui.refreshable
    def body() -> None:
        copies = tables.characters(table.id)
        chrome.section_label(pal, "CHARACTERS", len(copies))
        if not copies:
            ui.label("No characters yet. An approved request that brings a character "
                     "puts its campaign copy here.").classes("text-sm opacity-70")
        with chrome.grid():
            for row in copies:
                chrome.character_card(chrome.entry(store, book, row), row,
                                      detail=f"Played by {_username(tables, row.owner_id)}",
                                      link=row.owner_id == user_id)

        members = tables.members(table.id)
        chrome.section_label(pal, "MEMBERS", len(members))
        with ui.row().classes("gap-2"):
            if not members:
                ui.label("No members yet.").classes("text-sm opacity-70")
            for member in members:
                ui.chip(_username(tables, member), icon="person").props("outline")

        if is_st:
            _requests(tables, store, book, user_id, table, approve, reject)

    with page:
        body()


def _requests(tables: TableStore, store: CharacterStore, book: RuleSet, user_id: int,
              table: TableRow, approve: Callable[[int], None],
              reject: Callable[[int], None]) -> None:
    """Draw the requests of `table` for its Storyteller, with what each base carries."""
    pal = theme.palette(None)
    requests = tables.pending(user_id, table.id)
    with ui.column().classes("w-full gap-2").mark("table-requests"):
        chrome.section_label(pal, "REQUESTS", len(requests))
        if not requests:
            ui.label("No requests are waiting.").classes("text-sm opacity-70")
        for request in requests:
            who = _username(tables, request.user_id)
            base = store.row(request.base_id) if request.base_id else None
            with ui.card().classes(f"w-full px-3 py-2 gap-1 {pal.card_soft}").mark(
                    f"table-request-{request.id}"):
                with ui.row().classes("w-full items-center justify-between gap-2"):
                    with ui.column().classes("gap-0 min-w-0"):
                        ui.label(who).classes("text-base font-bold")
                        if base is None:
                            ui.label("Asks to watch.").classes("text-sm opacity-80")
                        else:
                            _request_base(store, book, base)
                    with ui.row().classes("gap-1"):
                        ui.button("Approve", icon="check",
                                  on_click=lambda _=None, r=request.id: approve(r)).props(
                            f"dense no-caps color={pal.button}").mark(
                            f"table-approve-{request.id}")
                        ui.button("Reject", icon="close",
                                  on_click=lambda _=None, r=request.id: reject(r)).props(
                            "flat dense no-caps color=negative").mark(
                            f"table-reject-{request.id}")


def _request_base(store: CharacterStore, book: RuleSet, base: CharacterRow) -> None:
    """Draw what a request brings: the base and the homebrew that it carries."""
    shown = chrome.entry(store, book, base)
    ui.label(f"Asks to bring {shown.name} ({shown.kind}).").classes("text-sm opacity-80")
    try:
        summary = carried_summary(store.load(base))
    except Exception:                               # noqa: BLE001 - the entry says unreadable
        summary = None
    if summary:
        ui.label(summary).classes("text-xs")
