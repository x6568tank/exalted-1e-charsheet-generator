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
from ..engine import derive, dice
from ..models.character import Character, Damage, PlayState, new_character_id
from ..models.party import Party, PartyMember
from ..models.rules import RuleSet
from ..server.config import storage_secret
from . import adversaries as adversaries_mod
from . import app as sheet_app
from . import builder as builder_mod
from . import pdf
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


def batch_roller_panel(pal: theme.Palette, state: dict, rows, on_roll) -> None:
    """The Storyteller's batch roll (decision 0019).

    One editable dice count per roster row, one name for the batch, one press.
    The log collapses to the batch's name; opening it shows each row's own line.

    ⚠ Read 0019 before changing this. Every count here is TYPED — nothing reads a
    character's pool, and nothing may. With six rows on screen, filling them from
    a named roll is the obvious convenience and is precisely what the decision
    rejects: the app would be claiming to know what six sheets are rolling, and
    "add their Charm dice" is the next ask. A row's name is the CHARACTER's,
    which asserts nothing about a pool; a roll's name would.

    `on_roll` refreshes this panel alone — a roll must not rebuild the roster
    above it, whose cards carry the GM's damage trackers.
    """
    def _set(key, value) -> None:
        state[key] = value

    with ui.card().classes(f"w-full p-3 {pal.card_soft} gap-2"):
        with ui.row().classes("w-full items-end gap-2 flex-wrap"):
            ui.label("BATCH ROLL").classes(
                "text-xs font-bold tracking-widest").style(f"color:{pal.accent}")
            # The batch's name: free text, and what the collapsed fold shows.
            ui.input("Name this roll", value=state["name"],
                     placeholder="Join Battle",
                     on_change=lambda e: _set("name", e.value)
                     ).classes("flex-1 min-w-40").props("dense outlined")
            ui.number("Target", value=state["target_number"], min=2, max=10,
                      format="%d",
                      on_change=lambda e: _set("target_number", e.value)
                      ).classes("w-24").props("dense outlined")
            ui.button("Roll all", icon="casino", on_click=on_roll).props(
                f"color={pal.button}").mark("batch-roll")
        with ui.row().classes("gap-4 items-center"):
            ui.switch("10s count double", value=state["doubles_tens"],
                      on_change=lambda e: _set("doubles_tens", e.value)
                      ).props("dense").classes("text-xs")
            ui.switch("Can botch", value=state["can_botch"],
                      on_change=lambda e: _set("can_botch", e.value)
                      ).props("dense").classes("text-xs")

        if not rows:
            ui.label("No one on the roster to roll for yet.").classes(
                "text-xs text-gray-600")
        for row in viewmod.batch_rows(state, rows):
            with ui.row().classes("w-full items-end gap-2 no-wrap"):
                # The tick is rebuilt from state on every repaint rather than
                # left to hold its own value, because typing dice ticks it on —
                # see view.set_batch_count.
                tick = ui.checkbox(value=row.included).props("dense")
                tick.on_value_change(
                    lambda e, k=row.key: viewmod.set_batch_included(
                        state, k, bool(e.value)))
                ui.label(row.name).classes("text-sm w-40 shrink-0 truncate")
                ui.number("Dice", value=row.count, min=0, max=dice.MAX_DICE,
                          format="%d",
                          on_change=lambda e, k=row.key, t=tick: (
                              viewmod.set_batch_count(state, k, e.value),
                              t.set_value(k in state["included"]))
                          ).classes("w-24").props("dense outlined")
                ui.number("Rolls", value=row.times, min=1,
                          max=viewmod.MAX_BATCH_REPEATS, format="%d",
                          on_change=lambda e, k=row.key: viewmod.set_batch_times(
                              state, k, e.value)).classes("w-20").props(
                    "dense outlined")
                ui.input("Label (yours)", value=row.label,
                         on_change=lambda e, k=row.key: state["labels"].__setitem__(
                             k, e.value)).classes("flex-1 min-w-32").props(
                    "dense outlined")
        ui.label("Tick who is rolling and type the dice each picks up; 'Rolls' "
                 "takes that many for one character. An unticked row, or one at "
                 "0 dice, sits out. Stunts, difficulty and Charms are yours — "
                 "this does not know.").classes("text-xs text-gray-500")

        if state["log"]:
            ui.separator()
            for batch in state["log"]:
                with ui.expansion(batch.caption,
                                  value=batch.key in state["open"],
                                  on_value_change=lambda e, k=batch.key: (
                                      state["open"].add(k) if e.value
                                      else state["open"].discard(k))
                                  ).classes("w-full").props("dense"):
                    for entry in batch.rolls:
                        _batch_line(entry, pal)
                    ui.label(batch.detail).classes("text-xs text-gray-500")
            ui.label("This session only — nothing is saved to any character."
                     ).classes("text-xs text-gray-500")


def _batch_line(entry, pal: theme.Palette) -> None:
    """One row's result inside an opened batch: whose it was, what it came to,
    and the faces."""
    with ui.row().classes("w-full items-baseline gap-2 no-wrap"):
        ui.label(entry.outcome).classes("text-sm font-bold w-24 shrink-0").style(
            f"color:{'#b45309' if entry.botch else pal.accent}")
        with ui.column().classes("gap-0 min-w-0"):
            ui.label(entry.label).classes("text-sm leading-tight")
            ui.label(entry.faces_text).classes(
                "text-xs text-gray-600 leading-tight")


def party_palette(party: Party) -> theme.Palette:
    """The page chrome for a party: the shared splat when every member is the same
    Exalt type, else the default. A mixed party carries its splat identity on the
    individual cards instead, which are always tinted per character."""
    splats = {m.character.exalt_type for m in party.members}
    return theme.palette(splats.pop() if len(splats) == 1 else None)


def build_gm(ruleset: RuleSet, ctx: dict, *, with_header: bool = True,
             hosted: bool = False, builder_path: str = "/") -> None:
    """Render the party page over the shared app context (see builder.make_context).
    `ctx["party"]` is the roster; `ctx["party_path"]` is where it last saved.

    `builder_path` is the route of the builder. The two ways back to the builder
    go there. The hosted server moves the builder off "/", which is public there.

    `hosted` says that this session runs on a server and owns a directory there.
    It selects the same third save branch that `builder.build_app` does. See
    hosting-state-model.md section 5.1b.

    ⚠ Only the party SAVE reads it. The party PDF export and the party LOAD stay
    two-way on purpose: an export is an artefact the player keeps, and a load
    comes from the player's own machine by upload."""

    def party() -> Party:
        return ctx["party"]

    # ⚠ Outside `body`, like the Play tab's roller state: the page is rebuilt on
    # every roster change and a batch mid-setup — typed counts, a half-written
    # name, the session's log — must survive that. Decision 0019: a roll is a
    # transcript, not state, and is never written to a character.
    batch_state = viewmod.new_batch_state()

    def roll_batch() -> None:
        if viewmod.roll_batch(batch_state, viewmod.batch_roster(party())) is None:
            ui.notify("No rows to roll — tick someone and give them dice.", type="warning")
        batch_roller.refresh()

    @ui.refreshable
    def batch_roller() -> None:
        batch_roller_panel(party_palette(party()), batch_state,
                           viewmod.batch_roster(party()), roll_batch)

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
        ui.navigate.to(builder_path)

    # ---- party save / load ------------------------------------------------ #
    # Deployment-aware in the same way as the builder's character Save/Load:
    # hosted writes to the session's own directory, a native window gets the OS
    # dialogs, and a plain browser gets download/upload.
    def _hosted_party_save() -> None:
        """Write the party into the directory that this session owns.

        Use `ctx["party_path"]` if a previous save set one, and otherwise a name
        derived from the party, inside `ctx["dir"]`.

        ⚠ `ctx["dir"]` is the session's own folder on a hosted run. Do not call
        `persistence.default_save_dir()` here: it is process-wide, and a handler
        that reads it takes the session back out of its directory. See
        hosting-state-model.md section 3.7b.
        """
        target = ctx["party_path"] or (
            ctx["dir"] / persistence.suggested_party_filename(party()))
        try:
            persistence.save_party(party(), target, custom_dir=ctx["custom_dir"])
        except Exception as ex:                         # noqa: BLE001 - surface write errors
            ui.notify(f"Save failed: {ex}", type="negative")
            return
        ctx["party_path"] = target
        ui.notify(f"Saved party to {target.name}", type="positive")

    async def save_party() -> None:
        win = builder_mod._native_window()
        default_name = persistence.suggested_party_filename(party())
        if hosted:
            _hosted_party_save()
            return
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
            persistence.save_party(party(), target, custom_dir=ctx["custom_dir"])
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

    def _party_download_copy(filename: str) -> None:
        """Send the party to the browser as `filename`. Do not change `ctx`.

        The hosted "Download a copy" button calls this directly. See
        hosting-state-model.md section 5.1c.
        """
        ui.download.content(persistence.party_to_json(party()).encode("utf-8"), filename)
        ui.notify(f"Downloading {filename}", type="positive")

    def _party_download(name: str, dialog) -> None:
        filename = persistence.normalize_party_filename(name, party())
        _party_download_copy(filename)
        # ⚠ Desktop only. Here the download IS the save, thus it sets the
        # destination. On a hosted run this line moves the party save target.
        ctx["party_path"] = ctx["dir"] / filename
        dialog.close()

    # ---- print / PDF export ----------------------------------------------- #
    def export_pdf(character: Character | None = None) -> None:
        """One member's sheet, or every member's in one document. Same renderer
        the builder's Print button uses — `ui/pdf.py` takes SheetViews and nothing
        else, so the party case is a list rather than a second layout."""
        members = [character] if character is not None else [
            m.character for m in party().members]
        if not members:
            ui.notify("The party is empty.", type="info")
            return
        views = [viewmod.build_sheet_view(ruleset, c) for c in members]
        default = (pdf.suggested_filename(views[0]) if character is not None
                   else f"{(party().name or 'party').replace(' ', '-')}-sheets.pdf")

        with ui.dialog() as dialog, ui.card().classes("gap-2"):
            ui.label("Export character sheet" if character is not None
                     else f"Export {len(views)} character sheets").classes(
                "text-lg font-bold")
            if character is None:
                ui.label("One party member per page.").classes(
                    "text-sm text-gray-600")
            paper = ui.radio(list(pdf.PAPER_SIZES), value="A4").props("inline")
            name_input = ui.input("File name", value=default).classes("w-96")
            with ui.row():
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button("Export PDF", icon="picture_as_pdf",
                          on_click=lambda: _do_export(views, paper.value,
                                                      name_input.value, dialog))
        dialog.open()

    async def _do_export(views, paper: str, name: str, dialog) -> None:
        try:
            data = (pdf.build_pdf(views[0], paper=paper or "A4") if len(views) == 1
                    else pdf.build_party_pdf(views, paper=paper or "A4",
                                             party_name=party().name))
        except Exception as ex:                         # noqa: BLE001 - surface render errors
            ui.notify(f"Export failed: {ex}", type="negative")
            return
        # ⚠ A party export whose name field was cleared must not be named after the
        # first member — it holds everyone's sheet.
        filename = pdf.normalize_pdf_filename(
            name, views[0],
            fallback="" if len(views) == 1 else f"{party().name or 'party'}-sheets")
        dialog.close()
        win = builder_mod._native_window()
        if win is None:
            ui.download.content(data, filename)
            ui.notify(f"Downloading {filename}", type="positive")
            return
        chosen = await win.create_file_dialog(
            builder_mod._dialog_type("save"), directory=str(ctx["dir"]),
            save_filename=filename)
        if not chosen:                                  # cancelled
            return
        target = Path(chosen if isinstance(chosen, str) else chosen[0])
        try:
            target.write_bytes(data)
        except Exception as ex:                         # noqa: BLE001 - surface write errors
            ui.notify(f"Export failed: {ex}", type="negative")
            return
        ui.notify(f"Sheets written to {target}", type="positive")

    def _apply_loaded_party(loaded: Party, path: Path | None) -> None:
        ctx["party"] = loaded
        ctx["party_path"] = path
        builder_mod.close_member(ctx)
        body.refresh()
        ui.notify(f"Loaded party {loaded.name or '(unnamed)'} "
                  f"({len(loaded.members)} character(s))", type="positive")

    def do_load_party(path_str: str, dialog) -> None:
        try:
            loaded = persistence.load_party(path_str, custom_dir=ctx["custom_dir"])
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
            # ⚠ Desktop only: a hosted path is a path on the SERVER. See the same
            # note in builder._open_browser_load_dialog.
            if not hosted:
                ui.label("…or load by path:").classes("text-xs text-gray-600 mt-2")
                path_input = ui.input("Path to .party.json",
                                      value=str(ctx["party_path"] or "")) \
                    .classes("w-96").mark("load-by-path")
            with ui.row():
                ui.button("Cancel", on_click=dialog.close).props("flat")
                if not hosted:
                    ui.button("Load path",
                              on_click=lambda: do_load_party(path_input.value, dialog))
        dialog.open()

    # ---- adding a character to the party ---------------------------------- #
    def do_add_from_path(path_str: str, dialog) -> None:
        try:
            loaded = persistence.load_character(path_str, custom_dir=ctx["custom_dir"])
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
        """One dialog in both deployments. ⚠ Never jump straight to the OS file picker
        when native: that makes the other two sources — the character open in the
        builder, and a blank one — unreachable there."""
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
                # ⚠ Desktop only: a hosted path is a path on the SERVER.
                if not hosted:
                    ui.label("…or add by path:").classes("text-xs text-gray-600 mt-2")
                    path_input = ui.input("Path to .character.json").classes("w-96") \
                        .mark("load-by-path")
                    ui.button("Add path", icon="add",
                              on_click=lambda: do_add_from_path(path_input.value, dialog)
                              ).props("flat")

            ui.separator()
            if not in_party(open_char):
                ui.button(f"Add “{open_char.name or 'the character open in the builder'}”",
                          icon="person", on_click=lambda: add_open_character(dialog)).props(
                    "flat").tooltip("The character currently open on the builder tabs")
            ui.button("Add a blank character", icon="note_add",
                      on_click=lambda: (dialog.close(),
                                        add_character(Character(id=new_character_id())))).props("flat")
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
            # ⚠ `view.spent_motes`, not `cur.*` — see its docstring; a committed
            # artifact shrinks the pool under an already-legal spend.
            spent_p, spent_pp = viewmod.spent_motes(cv.play, cur)
            with ui.row().classes("gap-3 items-end no-wrap"):
                _mote_input(character, "Personal", "motes_personal_spent",
                            spent_p, cv.play.personal_max)
                _mote_input(character, "Peripheral", "motes_peripheral_spent",
                            spent_pp, cv.play.peripheral_max)
            # ⚠ The COMPACT form — see qt/party.py. Short, but never absent: an
            # unexplained short pool reads as a defect.
            _committed = viewmod.committed_note(cv.play, compact=True)
            if _committed:
                ui.label(_committed).classes("text-xs opacity-70")

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

            # --- The Great Geas (Mountain Folk, CH6 p.235) ---------------- #
            # Divergence triggers as a reference panel: the Geas is Storyteller-
            # adjudicated and never engine-enforced (it is an ST call whether an
            # oath was broken, an Exalt slain, etc.), so the 9-clause table lives
            # here as the sheet's copy of the page — the human's ruling, 2026-08-07.
            if derive.limit_label(ruleset, character) == "Divergence":
                with ui.expansion("The Great Geas — Divergence triggers").classes(
                        "w-full"):
                    for clause in (
                        "Breaking a sworn oath — 5 points (once broken, an oath no "
                        "longer has power).",
                        "Fighting against a Celestial Exalt except in self-defense or "
                        "at the behest of another Celestial Exalt — 5 points at the "
                        "beginning of hostilities.",
                        "Slaying one of the Exalted — 5 points for striking the "
                        "deathblow against a Celestial, 3 against a Terrestrial.",
                        "Giving aid to an enemy of Creation (the banished and dead "
                        "Primordials and their servants, denizens of the Wyld, most "
                        "Darkbroods) — 4 points per instance.",
                        "Associating with the enemies of Creation in any nonhostile "
                        "manner — 2 points per week.",
                        "Accepting worship from mortals — 3 points per week.",
                        "Asserting authority and leadership over a community of "
                        "mortals — 1 point per week.",
                        "Dwelling more than a month aboveground except in service to "
                        "the Exalted — 1 point per month after the first.",
                        "Refusing to build an artifact for a Celestial Exalt of higher "
                        "Essence when properly commanded — 1 point per week of "
                        "disobedience (Enlightened only)."):
                        ui.label(f"• {clause}").classes("text-xs text-gray-700")
                    ui.label("When Divergence reaches 10, the pool resets to 0 and the "
                             "character suffers misfortune as though they broke an oath "
                             "sanctified by an Eclipse Caste Solar. For every full "
                             "month the Jadeborn live underground without gaining "
                             "Divergence, they lose one point.").classes(
                        "text-xs italic text-gray-600 mt-1")

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
                ui.button(icon="picture_as_pdf",
                          on_click=lambda c=character: export_pdf(c)).props(
                    "flat dense").tooltip("Export a print-ready PDF sheet")
                ui.button("Builder", icon="open_in_new",
                          on_click=lambda i=index: open_in_builder(i)).props(
                    "flat dense").mark(f"open-in-builder-{index}")
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
                ui.button("Add character", icon="person_add", on_click=add_to_party).props(
                    "flat").mark("gm-add-character")
                ui.button("Save party", icon="save",
                          on_click=save_party).props("flat").mark("gm-save-party")
                if hosted:
                    # On the desktop, Save party is already the download. Section 5.1c.
                    ui.button("Download a copy", icon="download",
                              on_click=lambda: _party_download_copy(
                                  persistence.suggested_party_filename(party()))
                              ).props("flat").mark("gm-download-party")
                ui.button("Load party", icon="folder_open", on_click=load_party).props(
                    "flat").mark("gm-load-party")
                ui.button("Print all", icon="picture_as_pdf",
                          on_click=lambda: export_pdf()).props("flat").tooltip(
                    "Export every member's sheet as one PDF, one per page")
                ui.button("New party", icon="group_add", on_click=confirm_new_party).props("flat")
                if hosted:
                    # The server registers `/logout`. See server/auth.py.
                    ui.button("Log out", icon="logout",
                              on_click=lambda: ui.navigate.to("/logout")
                              ).props("flat").mark("gm-logout")

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

            # The opposition, below the party they are fighting. Same page on
            # purpose: a GM tracking a fight is tracking both sides of it.
            adversaries_mod.build_roster(ruleset, ctx.get("adversary_catalog", {}),
                                         party, pal, body.refresh)

            # BELOW both rosters, because it rolls for both: a batch lists party
            # members and adversaries alike (a dice count does not care which).
            batch_roller()

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
                      on_click=lambda: ui.navigate.to(builder_path)).props(
                "flat color=white").mark("gm-builder")
    body()


def main() -> None:
    parser = argparse.ArgumentParser(description="Exalted 1e GM party page")
    parser.add_argument("party", nargs="?", help="path to a .party.json")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()

    ruleset = rules_db.load_app_ruleset(_DATA_DIR)
    character = Character(id=new_character_id())
    path = persistence.default_save_dir() / persistence.suggested_filename(character)
    ctx = builder_mod.make_context(character, path)
    if args.party:
        ctx["party"] = persistence.load_party(args.party)
        ctx["party_path"] = Path(args.party)

    # Register both routes, so "Open in builder" works from a standalone party run.
    builder_mod.register_pages(ruleset, ctx)
    # The routes above resolve one context for each browser session, thus they
    # read the session cookie. ⚠ Without a secret both pages raise at load.
    ui.run(title="Exalted 1e — Party", reload=False, show=args.show, port=args.port,
           storage_secret=storage_secret())


if __name__ in {"__main__", "__mp_main__"}:
    main()
