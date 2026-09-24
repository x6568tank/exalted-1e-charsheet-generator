"""
server/chrome.py — the parts that the logged-in pages share: the page paths, the
top bar and the card grid.

`server/home.py` and `server/campaigns.py` both use them. Thus neither module
imports the other.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from nicegui import ui

from ..models.character import Character
from ..models.rules import RuleSet
from ..ui import app as sheet_app
from ..ui import theme
from ..ui import view as viewmod
from ..ui import wiki_view
from . import auth, nav, site
from .characters import CharacterRow, CharacterStore

HOME_PATH = auth.HOME_PATH
CHARACTER_PATH = "/character"
TABLE_PATH = "/table"


def character_url(character_id: str) -> str:
    """Return the page of the character `character_id`."""
    return f"{CHARACTER_PATH}/{character_id}"


def table_url(table_id: str) -> str:
    """Return the page of the campaign `table_id`."""
    return f"{TABLE_PATH}/{table_id}"


def nav_drawer(pal, *, live: bool = False, current: str = "") -> ui.left_drawer:
    """Draw the site menu, closed. Return it, for `menu_button`.

    The entries come from `nav.groups`, thus they agree with the menu of the public
    pages. `live` opens the wiki and About in a new tab. `current` marks the entry
    of that key. ⚠ Call it at the top level of the page, not in the header.
    """
    drawer = ui.left_drawer(value=False).props(
        "overlay behavior=mobile width=280").classes("p-0 gap-0").style(
        f"background:{pal.bg};color:{pal.ink}").mark("nav-drawer")
    with drawer:
        # The head repeats the menu button of the top bar, and closes the menu.
        with ui.row().classes(
                "w-full items-center gap-3 px-4 h-16 no-wrap cursor-pointer text-white "
                "text-lg font-bold").style(f"background:{pal.accent}").on(
                "click", drawer.hide).mark("nav-drawer-head"):
            ui.icon("menu", size="24px")
            ui.label(site.SITE_NAME)
    with drawer, ui.list().classes("w-full py-2"):
        for number, group in enumerate(nav.groups(auth.current_username(), live=live)):
            if number:
                ui.separator().classes("my-1")
            for link in group:
                if not link.href:
                    with ui.item().classes("text-[13.5px] opacity-75").mark("nav-account"):
                        with ui.item_section().props("avatar").classes("min-w-0 pr-4"):
                            ui.icon(link.icon, size="22px").style(f"color:{pal.accent}")
                        ui.item_section(link.label)
                    continue
                item = ui.item().props("clickable tag=a").classes(
                    "min-h-0 py-1 pl-10 text-[13.5px]" if link.sub else "font-medium")
                item.props["href"] = link.href
                if link.new_tab:
                    item.props["target"] = "_blank"
                    item.props["rel"] = "noopener"
                if current and link.key == current:
                    item.props["active"] = True
                    item.props["active-class"] = "nav-on"
                with item:
                    with ui.item_section().props("avatar").classes("min-w-0 pr-4"):
                        ui.icon(link.icon, size="18px" if link.sub else "22px").style(
                            f"color:{pal.accent}")
                    ui.item_section(link.label)
                    if link.new_tab:
                        with ui.item_section().props("side"):
                            ui.icon("open_in_new", size="16px").classes("opacity-50")
    ui.add_css(f".nav-on{{color:{pal.accent};"
               f"background:color-mix(in srgb,{pal.accent} 14%,transparent)}}")
    return drawer


def menu_button(drawer: ui.left_drawer, title: str | None = None) -> None:
    """Draw the button that opens the site menu. `title` adds the page title to
    the button."""
    with ui.button(on_click=drawer.toggle).props(
            "flat no-caps color=white" + ("" if title else " round")).classes(
            "px-2" if title else "").mark("nav-menu"):
        ui.icon("menu")
        if title:
            ui.label(title).classes("text-lg font-bold ml-2")


def header(pal, title: str, *, current: str = "") -> ui.row:
    """Draw the site menu and the top bar of the builder. Return the row for its
    buttons. The title opens the menu."""
    drawer = nav_drawer(pal, current=current)
    with ui.header().classes("items-center justify-between px-4").style(
            f"background:{pal.accent}"):
        menu_button(drawer, title)
        buttons = ui.row().classes("items-center gap-2")
    ui.query("body").style(f"background:{pal.bg};color:{pal.ink}")
    return buttons


def table_not_found() -> None:
    """The answer for a campaign of which the account is not a member, and for one
    that is absent."""
    with header(theme.palette(None), "Exalted 1e"):
        home_button()
    ui.label("There is no such campaign.").classes("text-base p-4").mark("table-not-found")


def home_button() -> None:
    ui.button("Home", icon="home", on_click=lambda: ui.navigate.to(HOME_PATH)).props(
        "flat color=white").mark("top-bar-home")


def logout_button() -> None:
    ui.button(nav.logout_label(auth.current_username()), icon="account_circle",
              on_click=lambda: ui.navigate.to("/logout")).props(
        "flat no-caps color=white").mark("top-bar-logout")


def grid():
    """A grid of cards that fills the column and wraps."""
    return ui.element("div").classes("grid gap-3 w-full").style(
        "grid-template-columns: repeat(auto-fill, minmax(15rem, 1fr))")


def section_label(pal, title: str, count: int) -> None:
    """Draw a section title with its count, for example "CHARACTERS (2)"."""
    ui.label(f"{title} ({count})").classes(
        "text-xs font-bold tracking-widest pt-2").style(f"color:{pal.accent}")


def require_account(current_user_id: Callable[[], int | None]) -> int:
    """Return the account of the request. Raise if there is none: the gate did not run."""
    user_id = current_user_id()
    if user_id is None:
        raise PermissionError("No account is logged in. The login gate did not run.")
    return user_id


# --------------------------------------------------------------------------- #
# The character card
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Entry:
    """What a character card shows. The file gives all of it."""

    name: str
    stage: str               # "Draft", "Base", "Copy" or "Unreadable"
    exalt_type: str | None
    kind: str                # "Solar · Dawn", "Mortal", ...
    essence: int | None


def entry(store: CharacterStore, ruleset: RuleSet, row: CharacterRow) -> Entry:
    """Return what the card of `row` shows. A file that does not read gives an
    "Unreadable" entry, thus a list can still show it and delete it."""
    try:
        character = store.load(row)
    except Exception:                               # noqa: BLE001 - list it, do not crash the page
        return Entry(f"(unreadable: {row.id})", "Unreadable", None, "", None)
    caste = ruleset.castes.get(character.caste) if character.caste else None
    kind = character.exalt_type + (f" · {caste.label}" if caste is not None else "")
    stage = "Copy" if row.is_copy else ("Base" if character.chargen_locked else "Draft")
    return Entry(character.name or "Unnamed character", stage, character.exalt_type,
                 kind, character.essence_rating)


def character_card(entry: Entry, row: CharacterRow, detail: str | None = None,
                   link: bool = True):
    """Draw a card for one character, tinted by its splat. Return the row that
    holds its action buttons.

    With `link`, the name and the details are ONE link to the character page.
    Give `link=False` for the character of another account: its page is refused.
    """
    cpal = theme.palette(entry.exalt_type)
    card = ui.card().classes(f"p-0 gap-0 overflow-hidden {cpal.card}").mark(
        f"home-row-{row.id}")
    with card:
        ui.element("div").classes("w-full h-1").style(f"background:{cpal.accent}")
        body = (ui.link(target=character_url(row.id)).classes(
                    "w-full no-underline text-inherit px-3 pt-2 pb-1 hover:bg-black/5")
                if link else ui.column().classes("w-full gap-0 px-3 pt-2 pb-1"))
        with body:
            with ui.row().classes("w-full items-start justify-between no-wrap gap-2"):
                ui.label(entry.name).classes("text-base font-bold truncate min-w-0")
                ui.badge(entry.stage).props("outline").style(f"color:{cpal.accent}")
            ui.label(entry.kind).classes("text-sm opacity-80")
            if entry.essence is not None:
                ui.label(f"Essence {entry.essence}").classes("text-xs opacity-60")
            if detail:
                ui.label(detail).classes("text-xs opacity-70 pt-1")
        actions = ui.row().classes("w-full items-center justify-end gap-1 px-2 pb-1")
    return actions


def sheet_dialog(ruleset: RuleSet, character: Character, marker: str) -> None:
    """Open the sheet of `character`, read-only, in a dialog. `marker` marks the
    sheet.

    ⚠ `render_sheet` adds a body style to the page head. The page keeps its colours
    only because each logged-in page sets an inline body style, which wins.
    """
    with ui.dialog().props("full-width") as dialog, ui.card().classes("w-full"):
        with ui.row().classes("w-full justify-end"):
            ui.button(icon="close", on_click=dialog.close).props("flat dense")
        with ui.column().classes("w-full").mark(marker):
            sheet_app.render_sheet(viewmod.build_sheet_view(ruleset, character))
    dialog.open()


def homebrew_dialog(ruleset: RuleSet, kind: str, rows: list[dict], row_id: str) -> None:
    """Open row `row_id` of `rows` in a dialog, as the wiki shows an entry.

    `kind` is "charms", "spells" or "rituals". `wiki_view.homebrew_page` makes the
    page over `ruleset`. A row that does not load shows its name and its text.
    """
    page = wiki_view.homebrew_page(ruleset, kind, rows, row_id)
    raw = next((row for row in rows if row.get("id") == row_id), {})
    with ui.dialog() as dialog, ui.card().classes("w-[36rem] max-w-full p-4 gap-2").mark(
            "homebrew-entry"):
        with ui.row().classes("w-full items-start justify-between no-wrap"):
            with ui.column().classes("gap-0 min-w-0"):
                if page is not None:
                    ui.label(page.kicker).classes("text-xs font-bold tracking-wide").style(
                        f"color:{page.accent}" if page.accent else "")
                ui.label(page.title if page is not None
                         else str(raw.get("name") or row_id)).classes("text-lg font-bold")
            ui.button(icon="close", on_click=dialog.close).props("flat dense round")
        if page is None:
            ui.label("This row does not load. It has errors that its author must "
                     "fix.").classes("text-xs font-bold text-amber-800")
            paragraphs = [str(raw["description"])] if raw.get("description") else []
        else:
            with ui.column().classes("w-full gap-0").mark("homebrew-entry-facts"):
                for fact in page.facts:
                    ui.label(f"{fact.label}: {fact.value}").classes("text-sm")
                if page.section == "charms":
                    groups = [" or ".join(link.text for link in group)
                              for group in page.prerequisites]
                    ui.label("Prerequisite Charms: " + ("; ".join(groups) or "None")
                             ).classes("text-sm")
            paragraphs = page.paragraphs
        for paragraph in paragraphs:
            ui.label(paragraph).classes("text-sm whitespace-pre-line")
        if page is not None and page.source:
            ui.label(page.source).classes("text-xs opacity-60")
    dialog.open()
