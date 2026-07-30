"""
ui/gm.py — the Storyteller's party page (GM mode).

Several characters on screen at once as compact cards, each a live play-state
tracker: health boxes, motes spent, temporary Willpower, Limit — the same widgets
the Play tab uses (imported from ui/play.py, not reimplemented), plus the few
permanent numbers worth having at the table (soak, Dodge, Essence). Each card
carries free-text GM notes; the page carries session notes. The whole roster
saves as one `.party.json` bundle embedding full character copies.

Scope is deliberate: cards edit **play-state and notes only**. Permanent traits
are read-only here — "Open in builder" points the normal builder at that party
member instead. Since the roster holds the same Character object, builder edits
land back in the party with no syncing, and there is never a second Cytoscape
charm picker on the page.

Play-state remains an isolated layer: nothing on this page enters chargen
validation, the XP audit, or the permanent derivations. There is ZERO game logic
here — every number shown comes from view.build_party_card_view.

Run:
    python -m exalted_builder.ui.gm [path/to/foo.party.json] [--show] [--port N]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from nicegui import ui

from .. import persistence, rules_db
from ..engine import derive
from ..models.character import Character, Damage, PlayState
from ..models.party import Party, PartyMember
from ..models.rules import RuleSet
from . import app as sheet_app
from . import builder as builder_mod
from . import play as play_mod
from . import theme
from . import view as viewmod

_PKG = Path(__file__).resolve().parents[1]
_DATA_DIR = _PKG / "data"


def _member_label(member: PartyMember) -> str:
    """The name to show for a roster entry, never blank."""
    return member.character.name or "(unnamed)"


def _render_ref_table(table, pal: theme.Palette) -> None:
    """Draw one static reference table (models.rules.RefTable). Pure display — the
    data is already render-ready, so there is no logic here, only NiceGUI calls."""
    ui.label(table.title).classes("text-xs font-bold tracking-widest mt-2").style(
        f"color:{pal.accent}")
    if table.columns:
        cols = [{"name": f"c{i}", "label": c, "field": f"c{i}", "align": "left"}
                for i, c in enumerate(table.columns)]
        rows = [{"id": str(i), **{f"c{j}": cell for j, cell in enumerate(r)}}
                for i, r in enumerate(table.rows)]
        ui.table(columns=cols, rows=rows, row_key="id").props(
            "dense flat bordered wrap-cells").classes("w-full text-sm")
    else:
        for r in table.rows:
            ui.label("  ·  ".join(r)).classes("text-sm")
    if table.note:
        ui.label(table.note).classes("text-xs text-gray-500 italic")


def _reference_panel(ruleset: RuleSet, pal: theme.Palette) -> None:
    """The Storyteller reference screen as one default-collapsed expansion. Absent
    when no st_screen.json is loaded (the RuleSet field is None)."""
    screen = ruleset.st_screen
    if screen is None:
        return
    with ui.expansion(screen.title, icon="menu_book").classes(
            f"w-full {pal.card_soft}").props("dense"):
        for group in screen.groups:
            ui.label(group.title).classes("text-sm font-bold tracking-wide mt-3 mb-1").style(
                f"color:{pal.accent}")
            for table in group.tables:
                _render_ref_table(table, pal)


def party_palette(party: Party) -> theme.Palette:
    """The page chrome for a party: the shared splat when every member is the same
    Exalt type, else the default. A mixed party carries its splat identity on the
    individual cards instead, which are always tinted per character."""
    splats = {m.character.exalt_type for m in party.members}
    return theme.palette(splats.pop() if len(splats) == 1 else None)


def build_gm(ruleset: RuleSet, ctx: dict, *, with_header: bool = True) -> None:
    """Render the party page over the shared app context (see builder.make_context).
    `ctx["party"]` is the roster; `ctx["party_path"]` is where it last saved."""

    def party() -> Party:
        return ctx["party"]

    # ---- roster mutations ------------------------------------------------- #
    def add_character(character: Character) -> None:
        party().members.append(PartyMember(character=character))
        body.refresh()
        ui.notify(f"Added {character.name or 'character'} to the party", type="positive")

    def remove_member(index: int, dialog) -> None:
        removed = _member_label(party().members[index])
        del party().members[index]
        # The builder may have been pointed at the member that just went away, or at
        # one whose index has now shifted; drop the pointer rather than leave it stale.
        builder_mod.close_member(ctx)
        dialog.close()
        body.refresh()
        ui.notify(f"Removed {removed} from the party", type="warning")

    def confirm_remove(index: int) -> None:
        name = _member_label(party().members[index])
        with ui.dialog() as dialog, ui.card():
            ui.label(f"Remove {name} from the party?").classes("text-lg font-bold")
            ui.label("Their notes and tracked play-state in this party are lost. "
                     "Any separately saved .character.json is untouched.").classes("text-sm")
            with ui.row():
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button("Remove", on_click=lambda: remove_member(index, dialog)).props("color=red")
        dialog.open()

    def new_party(dialog) -> None:
        ctx["party"] = Party(id="party.new")
        ctx["party_path"] = None
        builder_mod.close_member(ctx)
        dialog.close()
        body.refresh()
        ui.notify("Started a new party", type="positive")

    def confirm_new_party() -> None:
        with ui.dialog() as dialog, ui.card():
            ui.label("Start a new party?").classes("text-lg font-bold")
            ui.label("Any unsaved changes to the current party will be lost.").classes("text-sm")
            with ui.row():
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button("New party", on_click=lambda: new_party(dialog)).props("color=primary")
        dialog.open()

    def open_in_builder(index: int) -> None:
        builder_mod.open_member(ctx, index)
        ui.navigate.to("/")

    # ---- party save / load ------------------------------------------------ #
    # Deployment-aware in the same way as the builder's character Save/Load: a
    # native window gets the OS dialogs, a plain browser gets download/upload.
    async def save_party() -> None:
        win = builder_mod._native_window()
        default_name = persistence.suggested_party_filename(party())
        if win is None:
            _open_browser_party_save(default_name)
            return
        chosen = await win.create_file_dialog(
            builder_mod._dialog_type("save"), directory=str(ctx["dir"]),
            save_filename=default_name)
        if not chosen:                                  # cancelled
            return
        target = Path(chosen if isinstance(chosen, str) else chosen[0])
        try:
            persistence.save_party(party(), target)
        except Exception as ex:                         # noqa: BLE001 - surface write errors
            ui.notify(f"Save failed: {ex}", type="negative")
            return
        ctx["party_path"] = target
        ui.notify(f"Saved party to {target}", type="positive")

    def _open_browser_party_save(default_name: str) -> None:
        with ui.dialog() as dialog, ui.card():
            ui.label("Save party").classes("text-lg font-bold")
            ui.label("Downloads to your browser's download folder.").classes("text-sm text-gray-600")
            name_input = ui.input("File name", value=default_name).classes("w-96")
            with ui.row():
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button("Download", icon="download",
                          on_click=lambda: _party_download(name_input.value, dialog))
        dialog.open()

    def _party_download(name: str, dialog) -> None:
        filename = persistence.normalize_party_filename(name, party())
        ui.download.content(persistence.party_to_json(party()).encode("utf-8"), filename)
        ctx["party_path"] = ctx["dir"] / filename
        dialog.close()
        ui.notify(f"Downloading {filename}", type="positive")

    def _apply_loaded_party(loaded: Party, path: Path | None) -> None:
        ctx["party"] = loaded
        ctx["party_path"] = path
        builder_mod.close_member(ctx)
        body.refresh()
        ui.notify(f"Loaded party {loaded.name or '(unnamed)'} "
                  f"({len(loaded.members)} character(s))", type="positive")

    def do_load_party(path_str: str, dialog) -> None:
        try:
            loaded = persistence.load_party(path_str)
        except Exception as ex:                         # noqa: BLE001 - surface any load error
            ui.notify(f"Load failed: {ex}", type="negative")
            return
        dialog.close()
        _apply_loaded_party(loaded, Path(path_str))

    async def _on_party_upload(e, dialog) -> None:
        # NiceGUI 3.x: the event carries a FileUpload at e.file, read asynchronously.
        try:
            loaded = persistence.party_from_json(await e.file.text())
        except Exception as ex:                         # noqa: BLE001 - surface parse errors
            ui.notify(f"Load failed: {ex}", type="negative")
            return
        dialog.close()
        _apply_loaded_party(loaded, None)

    async def load_party() -> None:
        win = builder_mod._native_window()
        if win is None:
            _open_browser_party_load()
            return
        chosen = await win.create_file_dialog(
            builder_mod._dialog_type("open"), directory=str(ctx["dir"]), allow_multiple=False,
            file_types=("Party files (*.json)", "All files (*.*)"))
        if not chosen:                                  # cancelled
            return
        path = chosen[0] if isinstance(chosen, (list, tuple)) else chosen
        do_load_party(path, builder_mod._NullDialog())

    def _open_browser_party_load() -> None:
        with ui.dialog() as dialog, ui.card().classes("gap-2"):
            ui.label("Load a party").classes("text-lg font-bold")
            ui.upload(label="Choose a .party.json file", auto_upload=True,
                      on_upload=lambda e: _on_party_upload(e, dialog)).classes("w-96")
            ui.label("…or load by path:").classes("text-xs text-gray-600 mt-2")
            path_input = ui.input("Path to .party.json",
                                  value=str(ctx["party_path"] or "")).classes("w-96")
            with ui.row():
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button("Load path", on_click=lambda: do_load_party(path_input.value, dialog))
        dialog.open()

    # ---- adding a character to the party ---------------------------------- #
    def do_add_from_path(path_str: str, dialog) -> None:
        try:
            loaded = persistence.load_character(path_str)
        except Exception as ex:                         # noqa: BLE001 - surface any load error
            ui.notify(f"Load failed: {ex}", type="negative")
            return
        dialog.close()
        add_character(loaded)

    async def _on_character_upload(e, dialog) -> None:
        try:
            loaded = persistence.character_from_json(await e.file.text())
        except Exception as ex:                         # noqa: BLE001 - surface parse errors
            ui.notify(f"Load failed: {ex}", type="negative")
            return
        dialog.close()
        add_character(loaded)

    def in_party(character: Character) -> bool:
        """True if this exact object is already a member (identity, not equality —
        two characters may legitimately share a name)."""
        return any(m.character is character for m in party().members)

    def add_open_character(dialog) -> None:
        """Add whatever the builder currently holds. Added BY REFERENCE, like every
        other roster entry, so continuing to edit it in the builder keeps the card
        in step (see builder.open_member)."""
        dialog.close()
        add_character(ctx["char"])
        builder_mod.open_member(ctx, len(party().members) - 1)

    async def browse_for_character(dialog) -> None:
        win = builder_mod._native_window()
        if win is None:
            return
        chosen = await win.create_file_dialog(
            builder_mod._dialog_type("open"), directory=str(ctx["dir"]), allow_multiple=False,
            file_types=("Character files (*.json)", "All files (*.*)"))
        if not chosen:                                      # cancelled
            return
        path = chosen[0] if isinstance(chosen, (list, tuple)) else chosen
        do_add_from_path(path, dialog)

    def add_to_party() -> None:
        """One dialog in both deployments. It used to jump straight to the OS file
        picker when native, which made the other two sources (the character open in
        the builder, and a blank one) unreachable there."""
        native = builder_mod._native_window() is not None
        open_char = ctx["char"]
        with ui.dialog() as dialog, ui.card().classes("gap-2"):
            ui.label("Add a character to the party").classes("text-lg font-bold")
            ui.label("Stored in the party bundle — the character's own file is untouched."
                     ).classes("text-xs text-gray-600")

            if native:
                ui.button("Browse for a .character.json…", icon="folder_open",
                          on_click=lambda: browse_for_character(dialog)).props("flat")
            else:
                ui.upload(label="Choose a .character.json file", auto_upload=True,
                          on_upload=lambda e: _on_character_upload(e, dialog)).classes("w-96")
                ui.label("…or add by path:").classes("text-xs text-gray-600 mt-2")
                path_input = ui.input("Path to .character.json").classes("w-96")
                ui.button("Add path", icon="add",
                          on_click=lambda: do_add_from_path(path_input.value, dialog)).props("flat")

            ui.separator()
            if not in_party(open_char):
                ui.button(f"Add “{open_char.name or 'the character open in the builder'}”",
                          icon="person", on_click=lambda: add_open_character(dialog)).props(
                    "flat").tooltip("The character currently open on the builder tabs")
            ui.button("Add a blank character", icon="note_add",
                      on_click=lambda: (dialog.close(),
                                        add_character(Character(id="char.new")))).props("flat")
            with ui.row().classes("justify-end w-full"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
        dialog.open()

    def show_sheet(character: Character) -> None:
        with ui.dialog().props("full-width") as dialog, ui.card().classes("w-full"):
            with ui.row().classes("w-full justify-end"):
                ui.button(icon="close", on_click=dialog.close).props("flat dense")
            sheet_app.render_sheet(viewmod.build_sheet_view(ruleset, character))
        dialog.open()

    # ---- one card --------------------------------------------------------- #
    def _card(index: int, member: PartyMember) -> None:
        character = member.character
        cv = viewmod.build_party_card_view(ruleset, character)
        pal = theme.palette(character.exalt_type)
        cur = character.play or PlayState()
        marks = list(cur.health) + [None] * max(0, len(cv.play.health_boxes) - len(cur.health))

        with ui.card().classes(f"w-full p-3 gap-2 {pal.card_soft}"):
            # --- name + identity ------------------------------------------ #
            with ui.row().classes("w-full items-center justify-between no-wrap"):
                with ui.column().classes("gap-0 min-w-0"):
                    ui.label(cv.name).classes("text-base font-bold truncate").style(
                        f"color:{pal.accent}")
                    ui.label(cv.identity_line).classes("text-xs text-gray-600 truncate")
                if cv.chargen_locked:
                    ui.icon("lock").classes("text-gray-500").tooltip("Chargen locked — in play")

            # --- health --------------------------------------------------- #
            ui.label("HEALTH  ·  / bashing   x lethal   * aggravated").classes(
                "text-xs font-bold tracking-widest").style(f"color:{pal.accent}")
            with ui.row().classes("gap-1 flex-wrap items-end"):
                for i, box in enumerate(cv.play.health_boxes):
                    play_mod.health_box(character, i, box.label, marks[i],
                                        len(cv.play.health_boxes), pal, body.refresh)
            counts = {d: sum(1 for m in marks if m == d) for d in Damage}
            with ui.row().classes("items-center gap-3"):
                ui.label(f"{counts[Damage.BASHING]}/ {counts[Damage.LETHAL]}x "
                         f"{counts[Damage.AGGRAVATED]}*").classes("text-xs text-gray-600")
                ui.label(f"Penalty: {play_mod.worst_penalty(cv.play, marks)}").classes(
                    "text-xs font-semibold").style(f"color:{pal.accent}")

            # --- motes ---------------------------------------------------- #
            ui.label("ESSENCE (motes spent)").classes(
                "text-xs font-bold tracking-widest").style(f"color:{pal.accent}")
            with ui.row().classes("gap-3 items-end no-wrap"):
                _mote_input(character, "Personal", "motes_personal_spent",
                            cur.motes_personal_spent, cv.play.personal_max)
                _mote_input(character, "Peripheral", "motes_peripheral_spent",
                            cur.motes_peripheral_spent, cv.play.peripheral_max)

            # --- temporary Willpower + Limit ------------------------------ #
            ui.label(f"WILLPOWER  ({cv.play.willpower_max - cur.willpower_spent}"
                     f"/{cv.play.willpower_max})").classes(
                "text-xs font-bold tracking-widest").style(f"color:{pal.accent}")
            with ui.row().classes("gap-1 flex-wrap"):
                for i in range(cv.play.willpower_max):
                    play_mod.count_box(character, i, i < cur.willpower_spent,
                                       "willpower_spent", cv.play.willpower_max, body.refresh)

            # Alchemicals have Clarity in place of Limit (p.69). Only the temporary
            # half is clickable; the permanent half is derived.
            if derive.uses_clarity(ruleset, character):
                cl = derive.clarity(ruleset, character)
                ui.label(f"CLARITY  ({cl.total}/{derive.CLARITY_MAX}  ·  "
                         f"{cl.permanent} perm + {cl.temporary} temp  ·  band "
                         f"{cl.band})").classes(
                    "text-xs font-bold tracking-widest").style(f"color:{pal.accent}")
                with ui.row().classes("gap-1 flex-wrap"):
                    for i in range(derive.CLARITY_MAX):
                        play_mod.count_box(character, i, i < cur.clarity_temporary,
                                           "clarity_temporary", derive.CLARITY_MAX,
                                           body.refresh)
            else:
                lim = derive.limit_label(ruleset, character).upper()   # "PARADOX" for a Sidereal
                ui.label(f"{lim}  ({cur.limit}/10"
                         f"{f'  — {lim} BREAK' if cur.limit >= 10 else ''})").classes(
                    "text-xs font-bold tracking-widest").style(f"color:{pal.accent}")
                with ui.row().classes("gap-1 flex-wrap"):
                    for i in range(10):
                        play_mod.count_box(character, i, i < cur.limit, "limit", 10,
                                           body.refresh)

            # --- permanent numbers worth having at the table -------------- #
            ui.label(f"Soak {cv.soak.bashing}B / {cv.soak.lethal}L / {cv.soak.aggravated}A"
                     f"  ·  Dodge {cv.dodge}  ·  Essence {cv.essence_rating}").classes(
                "text-xs text-gray-700")

            # --- notes ---------------------------------------------------- #
            # NOTE: no body.refresh() on change — refreshing per keystroke would
            # tear down the textarea mid-typing and steal focus. The value is
            # written straight to the model; nothing else on the card depends on it.
            ui.textarea(placeholder="Notes…", value=member.notes,
                        on_change=lambda e, m=member: setattr(m, "notes", e.value)
                        ).props("outlined dense autogrow").classes("w-full text-sm")

            with ui.row().classes("gap-1 justify-end w-full"):
                ui.button("Sheet", icon="description",
                          on_click=lambda c=character: show_sheet(c)).props("flat dense")
                ui.button("Builder", icon="open_in_new",
                          on_click=lambda i=index: open_in_builder(i)).props("flat dense")
                ui.button(icon="delete", on_click=lambda i=index: confirm_remove(i)).props(
                    "flat dense color=red").tooltip("Remove from party")

    def _mote_input(character: Character, label: str, field: str, value: int, cap: int) -> None:
        with ui.column().classes("gap-0"):
            ui.number(label, value=value, min=0, max=cap, format="%d",
                      on_change=lambda e, f=field, c=cap: (
                          play_mod.set_motes(character, f, e.value, c),
                          body.refresh())).props("dense").classes("w-24")
            ui.label(f"{max(0, cap - value)}/{cap} left").classes("text-xs text-gray-600")

    # ---- body ------------------------------------------------------------- #
    @ui.refreshable
    def body() -> None:
        p = party()
        with ui.column().classes("w-full max-w-7xl mx-auto gap-3 p-2"):
            with ui.row().classes("w-full items-center gap-2"):
                ui.input("Party name", value=p.name,
                         on_change=lambda e: setattr(p, "name", e.value)
                         ).props("dense outlined").classes("w-64")
                ui.space()
                ui.button("Add character", icon="person_add", on_click=add_to_party).props("flat")
                ui.button("Save party", icon="save", on_click=save_party).props("flat")
                ui.button("Load party", icon="folder_open", on_click=load_party).props("flat")
                ui.button("New party", icon="group_add", on_click=confirm_new_party).props("flat")

            _reference_panel(ruleset, pal)

            if not p.members:
                with ui.card().classes("w-full p-6 items-center"):
                    ui.label("No characters in the party yet.").classes("text-base font-bold")
                    ui.label("Use “Add character” to load a .character.json, or load a "
                             "saved .party.json.").classes("text-sm text-gray-600")
            else:
                # auto-fit columns: cards stay readable from one to many characters
                with ui.grid().classes("w-full gap-3").style(
                        "grid-template-columns:repeat(auto-fit,minmax(20rem,1fr))"):
                    for index, member in enumerate(p.members):
                        _card(index, member)

            ui.label("SESSION NOTES").classes("text-xs font-bold tracking-widest mt-2")
            # Same no-refresh rule as the per-character notes above.
            ui.textarea(placeholder="What happened, what's next, who owes whom…",
                        value=p.session_notes,
                        on_change=lambda e: setattr(p, "session_notes", e.value)
                        ).props("outlined autogrow").classes("w-full")

    pal = party_palette(party())
    ui.add_head_html(pal.head_style())
    if with_header:
        with ui.header().classes("items-center justify-between px-4").style(
                f"background:{pal.accent}"):
            ui.label("Exalted 1e — Party").classes("text-lg font-bold text-white")
            ui.button("Builder", icon="edit",
                      on_click=lambda: ui.navigate.to("/")).props("flat color=white")
    body()


def main() -> None:
    parser = argparse.ArgumentParser(description="Exalted 1e GM party page")
    parser.add_argument("party", nargs="?", help="path to a .party.json")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()

    ruleset = rules_db.load_app_ruleset(_DATA_DIR)
    character = Character(id="char.new")
    path = persistence.default_save_dir() / persistence.suggested_filename(character)
    ctx = builder_mod.make_context(character, path)
    if args.party:
        ctx["party"] = persistence.load_party(args.party)
        ctx["party_path"] = Path(args.party)

    # Register both routes, so "Open in builder" works from a standalone party run.
    builder_mod.register_pages(ruleset, ctx)
    ui.run(title="Exalted 1e — Party", reload=False, show=args.show, port=args.port)


if __name__ in {"__main__", "__mp_main__"}:
    main()
