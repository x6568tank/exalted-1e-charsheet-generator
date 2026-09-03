"""Catalogue picker dialogs — the browse-before-you-choose affordance.

`catalogue_dialog` is the shared pop-up the "add" buttons open — artifacts, gear,
Backgrounds, Hearthstones and Merits & Flaws: a filterable list of name + one-line
summary, with the full description collapsible, plus a "Custom" row for free-text
items. A row's own combobox (`DescribedSelect`) still edits it afterwards; the dialog
is what lets a player read the catalogue BEFORE choosing.

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
from . import view as viewmod


# --------------------------------------------------------------------------- #
# Gear stat lines — the "summary" for weapons and armour, which have no prose.
# The exact format of editor._weapon_summary/_armor_summary, but from the CATALOGUE
# entry directly: base stats, no character, no derived material tag (that needs a
# character; the dialog is pre-pick and character-independent).
# --------------------------------------------------------------------------- #

# ⚠ These three moved to `view.py` on 2026-08-21 and are RE-EXPORTED here, because the
# Qt shell needs them and must not import this module — `ui/catalogue.py` imports
# nicegui, and "nothing outside ui/ imports nicegui" is the invariant the whole port
# rests on. Callers and tests keep working; the definitions live in one place.
catalog_weapon_summary = viewmod.catalog_weapon_summary
catalog_armor_summary = viewmod.catalog_armor_summary
gear_cost_note = viewmod.gear_cost_note
_AFFORDABILITY_NOTE = viewmod._AFFORDABILITY_NOTE


# --------------------------------------------------------------------------- #
# Row icons — "what am I looking at?" at a glance
# --------------------------------------------------------------------------- #
# Keyed on the tags the data already carries, so nothing new is authored per entry and
# an untagged entry simply gets the dialog's default. Order matters: the FIRST tag that
# matches wins, so the specific kinds are listed before the generic ones — an arrow is
# tagged ["archery", "ammunition"] and must not read as a bow.
#
# ⚠ NiceGUI ships TWO icon fonts and a bare name resolves against the older one,
# **Material Icons**. A name that exists only in **Material Symbols** — `swords` is the
# one this build wanted — renders as NOTHING: no error, no fallback, just a blank where
# the icon should be. Quasar's `sym_o_` prefix selects Material Symbols Outlined; keep
# the prefix on any Symbols-only name.
#
# To check a name before adding it, read the glyph order of the fonts NiceGUI ships:
#
#   pip install --target /tmp/ft fonttools brotli
#   PYTHONPATH=/tmp/ft python -c "from fontTools.ttLib import TTFont; \
#     print('swords' in TTFont('<nicegui>/static/fonts/<hash>.woff2').getGlyphOrder())"
#
# (the hashed filenames are mapped to font families in nicegui/static/fonts.css). Every
# bare name below was verified present in Material Icons Outlined that way.
_ICON_BY_TAG: tuple[tuple[str, str], ...] = (
    ("ammunition", "north_east"),          # an arrow in flight
    # The Hearthstone elements come BEFORE the generic hearthstone entry: every stone
    # carries both tags, and the element is the more useful half on a list of ten.
    ("air", "air"),
    ("earth", "landscape"),
    ("fire", "local_fire_department"),
    ("water", "water_drop"),
    ("wood", "park"),
    ("hearthstone", "diamond"),
    ("shield", "shield"),
    ("helm", "sports_motorsports"),
    ("archery", "sports_martial_arts"),
    ("thrown", "sports_handball"),
    ("melee", "sym_o_swords"),
    ("martial_arts", "sports_mma"),
    ("weapon", "sym_o_swords"),
    ("armor", "security"),
    ("protection", "security"),
    ("senses", "visibility"),
    ("communication", "campaign"),
    ("transport", "sailing"),
    ("tool", "handyman"),
    ("combat", "sym_o_swords"),
)


# The default `render_cap` for a caller that asks to be capped without naming a
# number. See `catalogue_dialog`.
#
# ⚠ OPT-IN, never a default. Capping every caller silently truncated the artifact
# shop — "Dragon Tear Tiara" sits past row 200 and stopped being offered, which
# `test_artifacts_are_UNBUYABLE_at_chargen_and_buyable_in_play` caught. A dialog the
# player scrolls must show everything; only the Charm-sized lists want the cap.
#
# ⚠ NICEGUI-ONLY, and the Qt dialog not having one is not an oversight to correct. A
# NiceGUI row is ~4 DOM elements pushed over a socket; a Qt row is one
# QListWidgetItem, and `qt/catalogue.py` builds all 1,861 Charms in 23 ms and filters
# them in 6. Capping there would hide rows for no gain.
_DEFAULT_RENDER_CAP = 200


def icon_for(tags: Sequence[str], default: str = "") -> str:
    """The dialog icon for an entry with these tags, or `default` when none match.

    Presentation only — an icon is never a discriminator. (The catalogue dialogs' own
    scar: a "kind" flag anything on screen can edit turns into a broken row. An icon
    derived from tags at render time cannot be edited into a lie.)"""
    have = {t.lower() for t in tags}
    for tag, icon in _ICON_BY_TAG:
        if tag in have:
            return icon
    return default


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
    allow_custom: bool = True,
    subtitle: str = "",
    dimmed: frozenset[str] | set[str] = frozenset(),
    icons: dict[str, str] | None = None,
    default_icon: str = "",
    group_of: dict[str, str] | None = None,
    custom_kinds: dict[str, str] | None = None,
    keep_open: bool = False,
    render_cap: int | None = None,
) -> None:
    """Open a modal listing catalogue entries to choose from.

    `entries` is a list of ``(key, name, summary, full_or_none)``. `key` is what
    `on_pick` receives — the catalogue id, or the name where ids don't exist; `name`
    is the bold display label; `summary` is the clamped one-liner; `full` (when
    present) is shown in a "Full description" expansion. Clicking a row calls
    `on_pick(key)` and closes. The "Custom" row calls `on_pick(None)` and closes.

    The list is filtered live by a text input over name + summary + full.

    `icons` maps a key to a Material icon name (see `icon_for`, which derives one from
    an entry's tags); `default_icon` covers the keys it omits. Both are optional — a
    dialog that passes neither renders exactly as it did before.

    `keep_open` leaves the dialog up after a pick instead of closing it, for the
    fields that take MANY entries — an adversary's Charm list is a dozen picks, and
    a dozen reopens loses the filter each time. Each pick notifies instead, and a
    Done button becomes the way out. Default False, so every existing caller behaves
    exactly as it did.

    `render_cap` builds at most that many rows per open (True takes the default 200).
    ⚠ Only for lists too big to render whole — the Charm catalogue is 1,861 rows at
    ~4 elements each. It hides rows, so a caller whose user SCROLLS to find things
    must not pass it; the filter and the chips still see every entry, so narrowing
    always reaches what the cap hid.

    `dimmed` holds keys to render faded — gear the character cannot afford (core p.325).
    They stay PICKABLE: the affordability of a purchase is the Storyteller's business,
    the sheet is a tracker, and a character can be given what she could not buy. This is
    a hint, never a gate; nothing here validates.
    """
    _filter = {"text": "", "group": ""}
    _names = {e[0]: e[1] for e in entries}
    _cap = _DEFAULT_RENDER_CAP if render_cap is True else render_cap

    with ui.dialog() as dialog, ui.card().classes(
            f"w-[46rem] max-w-[92vw] h-[85vh] flex flex-col p-4 gap-2 {pal.card_solid}"):
        ui.label(title).classes("text-base font-bold").style(f"color:{pal.accent}")
        if subtitle:
            ui.label(subtitle).classes("text-xs text-gray-600")

        search = ui.input(placeholder="Filter…", on_change=lambda e: _apply(e.value)
                          ).props("dense clearable").classes("w-full")

        def _matches(e, term: str) -> bool:
            group = _filter["group"]
            if group and (group_of or {}).get(e[0]) != group:
                return False
            t = term.lower()
            hay = " ".join(x for x in (e[1], e[2], e[3]) if x).lower()
            return not t or t in hay

        # Type filter. A dialog spanning several catalogues is a wall of names without
        # it — the text box can only be used by someone who already knows what to type,
        # which is not the person browsing a shop. Chips are built from `group_of`, so a
        # caller that passes none gets exactly the dialog it had before.
        if group_of:
            groups = list(dict.fromkeys(group_of.values()))

            def _set_group(g: str) -> None:
                _filter["group"] = g
                _list.refresh()

            with ui.row().classes("w-full gap-1 flex-wrap items-center"):
                for g, label in [("", "Everything")] + [(x, x) for x in groups]:
                    n = (len(entries) if not g
                         else sum(1 for e in entries if group_of.get(e[0]) == g))
                    ui.button(f"{label} ({n})", on_click=lambda g=g: _set_group(g)
                              ).props("dense flat"
                                      + ("" if _filter["group"] == g else " outline")
                                      ).classes("text-xs")

        @ui.refreshable
        def _list() -> None:
            term = _filter["text"]
            shown = 0
            hidden = 0
            for entry in entries:
                if not _matches(entry, term):
                    continue
                # ⚠ Render cap, when the caller asked for one. The Charm catalogue
                # is 1,861 rows at ~4 elements each, so an uncapped open builds
                # ~7,500 elements before anything is visible. RENDERING only — the
                # filter and the chips still see every entry, so narrowing always
                # reaches what the cap hid.
                if _cap is not None and shown >= _cap:
                    hidden += 1
                    continue
                shown += 1
                key, name, summary, full = entry
                faded = " opacity-50" if key in dimmed else ""
                with ui.column().classes(
                        f"w-full gap-1 border-b border-{pal.fam}-900/10 pb-1{faded}"):
                    # The pick affordance is the NAME LABEL itself, not the enclosing
                    # row — the NiceGUI user harness dispatches clicks only to the
                    # element's own listeners and never bubbles, so a row-level handler
                    # would make the dialog unclickable in tests. The name and the
                    # expansion stay siblings: a click on the expansion header must
                    # toggle the full text, not pick the entry.
                    with ui.column().classes("w-full gap-0 cursor-pointer"):
                        icon = (icons or {}).get(key, default_icon)
                        with ui.row().classes("items-center gap-2 no-wrap"):
                            if icon:
                                # Part of the pick target, not decoration beside it: a
                                # click that lands on the icon must still choose the row.
                                ui.icon(icon).classes("text-base opacity-60"
                                                      ).on("click", lambda k=key: _pick(k))
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
                            # `whitespace-pre-line` because a `full` may be STRUCTURED,
                            # not one paragraph: a Background's is the blurb followed by
                            # its printed dot ladder, one rung per line. A plain label
                            # collapses those newlines and runs six rungs together into
                            # a wall of text. Blank lines inside the string survive too,
                            # which is what separates the rungs; runs of spaces still
                            # collapse, so ordinary prose entries are unaffected.
                            ui.label(full).classes(
                                "text-xs leading-relaxed whitespace-pre-line")
            if not shown:
                ui.label("Nothing matches the filter.").classes(
                    "text-xs italic opacity-60")
            elif hidden:
                ui.label(f"…and {hidden} more. Narrow the filter to see them."
                         ).classes("text-xs italic opacity-60 pt-1"
                                   ).mark("cat-truncated")

        def _apply(value) -> None:
            _filter["text"] = value or ""
            _list.refresh()

        def _pick(key) -> None:
            # Run on_pick BEFORE closing: close() fires the value-change handler that
            # clears the dialog, deleting the slot this handler is running in. A pick
            # callback that opens a nested dialog (the play Custom prompt) would raise
            # "the parent element this slot belongs to has been deleted" if the close
            # ran first. (The nested prompt itself must ALSO be built inside
            # client.layout so its canary survives the outer's clear — see
            # _custom_gain in ui/advantages.py.)
            on_pick(key)
            if keep_open:
                # Nothing closes, so the pick needs its own acknowledgement — the
                # list does not change under a click and the field being written is
                # behind the dialog.
                ui.notify(f"Added {_names.get(key, 'entry')}", type="positive")
                return
            dialog.close()

        def _custom() -> None:
            on_pick(None)
            if not keep_open:
                dialog.close()

        # "Custom" needs a TYPE when the dialog spans several catalogues — a blank row
        # has to go in some list. `custom_kinds` maps a kind key to its label and turns
        # the single Custom row into one per kind ("Custom weapon", "Custom armour"),
        # which is what let the per-panel Add buttons be deleted: making a thing and
        # buying a thing are now the same surface.
        if custom_kinds:
            with ui.row().classes("w-full items-center gap-3 flex-wrap"):
                ui.icon("add").classes(f"text-{pal.fam}-700")
                for kind, label in custom_kinds.items():
                    ui.label(label).classes(
                        "text-sm font-semibold cursor-pointer"
                    ).on("click", lambda k=kind: (on_pick(f"custom:{k}"),
                                                  dialog.close())
                         ).mark(f"cat-custom-{kind}")
            ui.separator()
        elif allow_custom:
            with ui.row().classes("w-full items-center gap-2 cursor-pointer"):
                ui.icon("add").classes(f"text-{pal.fam}-700")
                ui.label(custom_label).classes("text-sm font-semibold"
                                               ).on("click", _custom).mark("cat-custom")
            ui.separator()

        # The list scrolls; the Custom row and title stay put. `flex-1 min-h-0` lets the
        # scroll area shrink below its content (the classic flexbox scroll trap).
        # ⚠ A QScrollArea does NOT size itself from `max-h`, so height changes applied
        # to it read as no-ops: the CARD is the real height constraint, and the scroll
        # area fills the leftover space under the title/search/Custom row.
        with ui.scroll_area().classes("w-full flex-1 min-h-0"):
            _list()

        # Only when the dialog stays up: picking is no longer the way out of it.
        if keep_open:
            with ui.row().classes("justify-end w-full"):
                ui.button("Done", icon="check", on_click=dialog.close
                          ).props("flat").mark("cat-done")

    # A dialog is only HIDDEN when closed, never removed — the NiceGUI docstring says
    # so outright. Each open builds a fresh dialog with every entry's labels, so a
    # heavy catalogue (170 M&F rows ≈ 800 elements) would otherwise accumulate a copy
    # in the client on every open. Clear it on ANY dismissal (pick, custom, ESC,
    # click-outside) — the value-change-to-closed event fires for all of them. `_pick`
    # and `_custom` also call `dialog.close()`, so this is the single deletion point.
    dialog.on_value_change(lambda e: dialog.clear() if not e.value else None)

    dialog.open()


# --------------------------------------------------------------------------- #
# The trait reference dialog
# --------------------------------------------------------------------------- #

def trait_reference_dialog(pal: theme.Palette, info: viewmod.TraitInfo) -> None:
    """Open a read-only modal showing one trait's core-book text (`viewmod.TraitInfo`).

    Renders the description, then the rung ladder with the character's own rating
    highlighted, then the trait's ordered (heading, body) sections. Purely
    descriptive — nothing here edits the character; the dot row beside the ⓘ does that.
    """
    with ui.dialog() as dialog, ui.card().classes(
            f"w-[40rem] max-w-[92vw] max-h-[85vh] flex flex-col p-4 gap-2 {pal.card_solid}"):
        ui.label(info.title).classes("text-base font-bold").style(f"color:{pal.accent}")
        ui.label(info.subtitle).classes("text-xs text-gray-600")

        with ui.scroll_area().classes("w-full flex-1 min-h-0"):
            for para in info.description.split("\n\n"):
                if para.strip():
                    ui.label(para).classes("text-sm whitespace-pre-line")
            if info.ladder:
                ui.separator().classes("my-2")
                for rating, text, current in info.ladder:
                    with ui.row().classes("w-full items-start gap-2 no-wrap"):
                        # Rung 0 is "Unskilled", which prints as a cross on the page
                        # rather than as no dots — an empty cell would read as a
                        # missing value instead of a rung.
                        pips = "●" * rating if rating else "✕"
                        ui.label(pips).classes("text-sm w-16 shrink-0").style(
                            f"color:{pal.accent}")
                        label = ui.label(text).classes("text-sm flex-1")
                        if current:
                            label.classes("font-bold")
            for heading, body in info.sections:
                ui.separator().classes("my-2")
                ui.label(heading).classes("text-xs font-semibold").style(
                    f"color:{pal.accent}")
                ui.label(body).classes("text-sm whitespace-pre-line")

        ui.button("Close", on_click=dialog.close).props(f"flat dense color={pal.button}")

    # Same lifecycle as `catalogue_dialog`: close only hides, so delete on any dismissal.
    dialog.on_value_change(lambda e: dialog.clear() if not e.value else None)
    dialog.open()
