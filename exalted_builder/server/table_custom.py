"""
server/table_custom.py — `/table/<id>/custom`, the homebrew of a campaign.

Step 7 of `docs/plans/p3-tables.md` section 14 (ruled 2026-09-23):

  * The Storyteller gets the authoring page (`ui/custom.build_custom`) on the
    homebrew of the table. A save reloads each kept RuleSet that holds it.
  * A member or a watcher reads the rows. There is no editor on the rows of the
    table.
  * Each member, the Storyteller too, sees the rows of their own library that the
    table does not have. A member proposes one; the Storyteller adds one at once.
    The Storyteller approves a proposal in the ST tab of the table view.
  * A member gets the editor on their OWN library below (human, 2026-09-24). A
    saved row then appears in the list of rows to propose.

⚠ `TableStore.access` is the check, in the page body, before anything of the table
is read. Each handler calls the store, which checks it again.
"""

from __future__ import annotations

from collections.abc import Callable

from nicegui import ui

from .. import custom_content
from ..ui import custom as custom_mod
from ..ui import theme
from . import chrome
from .characters import CharacterStore
from .rulesets import Rulesets
from .table_homebrew import TableHomebrew, TableHomebrewError
from .tables import CARRIED_KINDS, STORYTELLER, TableStore, library_rows

# The heading of each kind of homebrew, in the order of the page.
_KIND_LABELS = {"charms": "Charms", "spells": "Spells", "rituals": "Rituals",
                "weapons": "Weapons", "armor": "Armour", "gear": "Gear",
                "artifacts": "Artifacts"}


def custom_url(table_id: str) -> str:
    """Return the address of the homebrew page of table `table_id`."""
    return f"{chrome.table_url(table_id)}/custom"


def register_table_custom(tables: TableStore, store: CharacterStore, rulesets: Rulesets,
                          homebrew: TableHomebrew,
                          current_user_id: Callable[[], int | None]) -> None:
    """Register `/table/<id>/custom`."""

    @ui.page(chrome.TABLE_PATH + "/{table_id}/custom")
    def custom_page(table_id: str) -> None:
        user_id = chrome.require_account(current_user_id)
        # ⚠ Before anything that reads the table.
        role = tables.access(user_id, table_id)
        table = tables.table(table_id) if role is not None else None
        if table is None:
            chrome.table_not_found()
            return
        _build(tables, store, rulesets, homebrew, user_id, table, role == STORYTELLER)


def _rows(folder, kind: str) -> list[dict]:
    if kind in CARRIED_KINDS:
        return list(library_rows(kind, folder).values())
    return [row for row in custom_content.library_gear(kind, folder) if row.get("id")]


def _build(tables: TableStore, store: CharacterStore, rulesets: Rulesets,
           homebrew: TableHomebrew, user_id: int, table, is_st: bool) -> None:
    pal = theme.palette(None)
    folder = tables.homebrew_dir(table.id)
    ui.query("body").style(f"background:{pal.bg};color:{pal.ink}")
    drawer = chrome.nav_drawer(pal)
    with ui.header().classes("items-center px-4 py-1 gap-1 no-wrap").style(
            f"background:{pal.accent}"):
        chrome.menu_button(drawer)
        chrome.home_button()
        ui.label("›").classes("text-white/70")
        ui.button(table.name, on_click=lambda: ui.navigate.to(chrome.table_url(table.id))
                  ).props("flat no-caps color=white").classes(
            "min-w-0 max-w-[45vw] truncate").mark("homebrew-campaign")
        ui.label("› Homebrew").classes("text-white/90 shrink-0")

    # ⚠ The editor is one row of fixed cards that does not wrap. It needs the full
    # width, as on `/home`. Each viewer has an editor, thus the page has no limit.
    with ui.column().classes("w-full px-4 py-2 gap-4"):
        if is_st:
            ui.label("The homebrew of this campaign. Each character in it can buy these "
                     "rows. Players propose rows from their own libraries; you approve "
                     "them in the ST tab.").classes("text-sm opacity-80")
            custom_mod.build_custom(rulesets.for_table(table.id), custom_dir=folder,
                                    with_header=False, show_path=False,
                                    reload=lambda: rulesets.reload_table(table.id))
            _from_library(pal, tables, store, homebrew, user_id, table, is_st)
            return
        _read_only(pal, folder)
        offer = _from_library(pal, tables, store, homebrew, user_id, table, is_st)

        def reload() -> list[str]:
            problems = rulesets.reload_account(user_id)
            offer()
            return problems

        with ui.column().classes("w-full gap-1 pt-4").mark("table-member-editor"):
            ui.label("WRITE A NEW ROW").classes("text-xs font-bold tracking-wide")
            ui.label("A row that you save here goes to your own library, as on your "
                     "Homebrew page. Then propose it above.").classes("text-sm opacity-80")
            custom_mod.build_custom(rulesets.for_account(user_id),
                                    custom_dir=store.custom_dir(user_id),
                                    with_header=False, show_path=False, reload=reload)


def _read_only(pal, folder) -> None:
    """The rows of the campaign, with their text. No editor."""
    ui.label("Campaign homebrew").classes("text-lg font-bold").style(f"color:{pal.accent}")
    ui.label("The Storyteller keeps this list. Propose a row of your own library "
             "below.").classes("text-sm opacity-80")
    shown = False
    for kind, label in _KIND_LABELS.items():
        rows = sorted(_rows(folder, kind), key=lambda r: str(r.get("name") or r["id"]))
        if not rows:
            continue
        shown = True
        ui.label(label.upper()).classes("text-xs font-bold tracking-wide pt-2")
        for row in rows:
            with ui.column().classes(f"w-full px-3 py-2 gap-0 rounded {pal.card_soft}"):
                ui.label(str(row.get("name") or row["id"])).classes("font-bold").mark(
                    f"table-homebrew-row-{row['id']}")
                if row.get("description"):
                    ui.label(str(row["description"])).classes("text-sm whitespace-pre-line")
    if not shown:
        ui.label("The campaign has no homebrew yet.").classes("text-sm opacity-70")


def _from_library(pal, tables: TableStore, store: CharacterStore,
                  homebrew: TableHomebrew, user_id: int, table,
                  is_st: bool) -> Callable[[], None]:
    """Draw the rows of the library of the viewer that the campaign does not have,
    and the proposals of the viewer that wait. Return the function that draws them
    again."""

    @ui.refreshable
    def section() -> None:
        campaign = tables.homebrew_dir(table.id)
        mine = store.custom_dir(user_id)
        ui.label("FROM YOUR LIBRARY").classes("text-xs font-bold tracking-wide pt-2")
        waiting = {(p.kind, p.row_id) for p in homebrew.proposals_by(user_id, table.id)}
        offered = 0
        for kind in CARRIED_KINDS:
            have = library_rows(kind, campaign)
            for row_id, row in sorted(library_rows(kind, mine).items()):
                if row_id in have or (kind, row_id) in waiting:
                    continue
                offered += 1
                with ui.row().classes("w-full items-center justify-between gap-2"):
                    ui.label(f"{row.get('name') or row_id} · "
                             f"{_KIND_LABELS[kind][:-1]}").classes("text-sm")
                    ui.button("Add" if is_st else "Propose", icon="send",
                              on_click=lambda _=None, k=kind, r=row_id: propose(k, r)
                              ).props(f"dense no-caps size=sm color={pal.button}").mark(
                        f"table-propose-{kind}-{row_id}")
        if not offered:
            ui.label("Your library has nothing that the campaign does not have."
                     ).classes("text-sm opacity-70")
        proposals = homebrew.proposals_by(user_id, table.id)
        if proposals:
            with ui.column().classes("w-full gap-1 pt-2").mark("table-my-proposals"):
                ui.label("YOUR PROPOSALS").classes("text-xs font-bold tracking-wide")
                for proposal in proposals:
                    with ui.row().classes("w-full items-center justify-between gap-2"):
                        ui.label(", ".join(proposal.names) + " · waits for the "
                                 "Storyteller").classes("text-sm")
                        ui.button("Withdraw", icon="undo",
                                  on_click=lambda _=None, p=proposal.id: withdraw(p)
                                  ).props("flat dense no-caps size=sm").mark(
                            f"table-withdraw-{proposal.id}")

    def propose(kind: str, row_id: str) -> None:
        try:
            proposal = homebrew.propose(user_id, table.id, kind, row_id)
        except TableHomebrewError as exc:
            ui.notify(str(exc), type="warning")
            section.refresh()
            return
        if proposal.approved:
            ui.notify(f"Added {', '.join(proposal.names)} to the campaign.",
                      type="positive")
            # The editor above lists the rows of the campaign. Draw it again.
            ui.navigate.to(custom_url(table.id))
            return
        ui.notify("Sent to the Storyteller.", type="positive")
        section.refresh()

    def withdraw(proposal_id: int) -> None:
        homebrew.withdraw(user_id, table.id, proposal_id)
        section.refresh()

    with ui.column().classes("w-full gap-1"):
        section()
    return section.refresh
