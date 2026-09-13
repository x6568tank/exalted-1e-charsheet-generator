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

from ..models.rules import RuleSet
from ..ui import theme
from . import auth
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


def header(pal, title: str) -> ui.row:
    """Draw the top bar of the builder. Return the row for its buttons."""
    with ui.header().classes("items-center justify-between px-4").style(
            f"background:{pal.accent}"):
        ui.label(title).classes("text-lg font-bold text-white")
        buttons = ui.row().classes("items-center gap-2")
    ui.query("body").style(f"background:{pal.bg};color:{pal.ink}")
    return buttons


def home_button() -> None:
    ui.button("Home", icon="home", on_click=lambda: ui.navigate.to(HOME_PATH)).props(
        "flat color=white").mark("top-bar-home")


def logout_button() -> None:
    ui.button("Log out", icon="logout", on_click=lambda: ui.navigate.to("/logout")).props(
        "flat color=white").mark("top-bar-logout")


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
