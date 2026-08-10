"""Catalogue picker dialogs — the browse-before-you-choose affordance.

The five "add" surfaces (weapons, armour, artifacts, backgrounds, Merits & Flaws) are
comboboxes today: clicking "Add" appends a blank row and the player types into a
`ui.select`. A `DescribedSelect` gives a hover tooltip, but nothing lets the player
BROWSE the catalogue before choosing. `catalogue_dialog` is the shared pop-up every add
button opens: a filterable list of name + one-line summary, with the full description
collapsible, plus a "Custom" row for free-text items.

Pure UI — no game logic, no validation. It reads whatever list the caller hands it
(already filtered by availability/splat) and calls `on_pick(key)` when a row is clicked
or `on_pick(None)` when Custom is chosen; the caller is responsible for appending to the
character, exactly as its add button did before.

The "1-2 sentence summary" is a Tailwind `line-clamp-2` on the full text, not a separate
authored field — no brittle sentence-splitting, and when the vision-model prose lands
later the dialog shows it automatically.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from nicegui import ui

from ..models.rules import ArmorType, WeaponType
from . import theme


# --------------------------------------------------------------------------- #
# Gear stat lines — the "summary" for weapons and armour, which have no prose.
# The exact format of editor._weapon_summary/_armor_summary, but from the CATALOGUE
# entry directly: base stats, no character, no derived material tag (that needs a
# character; the dialog is pre-pick and character-independent).
# --------------------------------------------------------------------------- #

def catalog_weapon_summary(wt: WeaponType) -> str:
    """One-line stat summary for a catalogue weapon, matching the row readout's shape."""
    return (f"Acc{wt.accuracy:+d} Dmg{wt.damage:+d}{wt.damage_type} "
            f"Def{wt.defense:+d} Spd{wt.speed:+d}")


def catalog_armor_summary(at: ArmorType) -> str:
    """One-line stat summary for a catalogue armour, matching the row readout's shape."""
    return (f"Soak {at.soak_lethal}L/{at.soak_bashing}B "
            f"Mob{at.mobility_penalty:+d} Ftg{at.fatigue}")


# --------------------------------------------------------------------------- #
# The dialog
# --------------------------------------------------------------------------- #

def catalogue_dialog(
    pal: theme.Palette,
    title: str,
    entries: Sequence[tuple[str, str, str, str | None]],
    on_pick: Callable[[str | None], None],
    *,
    custom_label: str = "Custom",
    subtitle: str = "",
) -> None:
    """Open a modal listing catalogue entries to choose from.

    `entries` is a list of ``(key, name, summary, full_or_none)``. `key` is what
    `on_pick` receives — the catalogue id, or the name where ids don't exist; `name`
    is the bold display label; `summary` is the clamped one-liner; `full` (when
    present) is shown in a "Full description" expansion. Clicking a row calls
    `on_pick(key)` and closes. The "Custom" row calls `on_pick(None)` and closes.

    The list is filtered live by a text input over name + summary + full.
    """
    _filter = {"text": ""}

    with ui.dialog() as dialog, ui.card().classes(
            f"w-[46rem] max-w-[92vw] h-[85vh] flex flex-col p-4 gap-2 {pal.card_solid}"):
        ui.label(title).classes("text-base font-bold").style(f"color:{pal.accent}")
        if subtitle:
            ui.label(subtitle).classes("text-xs text-gray-600")

        search = ui.input(placeholder="Filter…", on_change=lambda e: _apply(e.value)
                          ).props("dense clearable").classes("w-full")

        def _matches(e, term: str) -> bool:
            t = term.lower()
            hay = " ".join(x for x in (e[1], e[2], e[3]) if x).lower()
            return not t or t in hay

        @ui.refreshable
        def _list() -> None:
            term = _filter["text"]
            for entry in entries:
                if not _matches(entry, term):
                    continue
                key, name, summary, full = entry
                with ui.column().classes(
                        f"w-full gap-1 border-b border-{pal.fam}-900/10 pb-1"):
                    # The pick affordance is the NAME LABEL itself, not the enclosing
                    # row — the NiceGUI user harness dispatches clicks only to the
                    # element's own listeners and never bubbles, so a row-level handler
                    # would make the dialog unclickable in tests. The name and the
                    # expansion stay siblings: a click on the expansion header must
                    # toggle the full text, not pick the entry.
                    with ui.column().classes("w-full gap-0 cursor-pointer"):
                        ui.label(name).classes("text-sm font-semibold leading-tight"
                                               ).on("click", lambda k=key: _pick(k))
                        if summary:
                            ui.label(summary).classes(
                                "text-xs opacity-70 line-clamp-2 leading-snug"
                                ).on("click", lambda k=key: _pick(k))
                    # Only offer the "Full description" expansion when the text is long
                    # enough that the two-line clamp actually hides something — a
                    # 6-word background ("Aides and friends…") must not get a
                    # pointless expander, while a 100-word M&F rules text must. The
                    # callers pass `full` for every prose entry and the length gate
                    # decides; ~160 chars ≈ two lines in this dialog.
                    if full and len(full) > 160:
                        with ui.expansion("Full description", icon="article"
                                          ).classes("w-full"):
                            ui.label(full).classes("text-xs leading-relaxed")
            if not any(_matches(e, _filter["text"]) for e in entries):
                ui.label("Nothing matches the filter.").classes(
                    "text-xs italic opacity-60")

        def _apply(value) -> None:
            _filter["text"] = value or ""
            _list.refresh()

        def _pick(key) -> None:
            dialog.close()
            on_pick(key)

        def _custom() -> None:
            dialog.close()
            on_pick(None)

        with ui.row().classes("w-full items-center gap-2 cursor-pointer"):
            ui.icon("add").classes(f"text-{pal.fam}-700")
            ui.label(custom_label).classes("text-sm font-semibold"
                                           ).on("click", _custom).mark("cat-custom")
        ui.separator()

        # The list scrolls; the Custom row and title stay put. `flex-1 min-h-0` lets the
        # scroll area shrink below its content (the classic flexbox scroll trap) — a
        # QScrollArea does NOT size itself from `max-h`, which is why the height changes
        # before this looked like no-ops: the card is the real height constraint, and
        # the scroll area fills the leftover space under the title/search/Custom row.
        with ui.scroll_area().classes("w-full flex-1 min-h-0"):
            _list()

    dialog.open()
